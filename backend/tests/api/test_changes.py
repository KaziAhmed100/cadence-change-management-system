"""End-to-end tests for the /change-requests endpoints.

We exercise the full pipeline: routing, RBAC, validation, service, state
machine, persistence, response shape.
"""

from datetime import UTC, datetime, timedelta


def _valid_create_payload(**overrides) -> dict:
    """Baseline payload with the minimum required fields, overridable per test."""
    base = {
        "title": "Test change",
        "description": "A reasonable description of the proposed change.",
        "change_type": "normal",
        "impact": "team",
        "downtime_minutes": 15,
        "affected_ci_count": 2,
        "is_security_related": False,
        "rollback_plan": "Revert the deploy via the previous artifact.",
    }
    base.update(overrides)
    return base


class TestCreate:
    def test_requester_can_create_change_request(self, client, requester_auth_header) -> None:
        response = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(),
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "draft"
        assert body["reference"].startswith("CHG-")
        assert body["risk_score"] >= 1
        assert body["risk_band"] in ("low", "medium", "high", "critical")
        assert body["requester"]["email"] == "test-requester@example.com"

    def test_validation_rejects_short_title(self, client, requester_auth_header) -> None:
        response = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(title="hi"),
        )
        assert response.status_code == 422

    def test_validation_rejects_invalid_impact(self, client, requester_auth_header) -> None:
        response = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(impact="catastrophic"),
        )
        assert response.status_code == 422

    def test_creating_change_assigns_unique_reference(self, client, requester_auth_header) -> None:
        r1 = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(title="First change"),
        )
        r2 = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(title="Second change"),
        )
        assert r1.json()["reference"] != r2.json()["reference"]


class TestList:
    def test_requester_sees_only_own_changes(
        self,
        client,
        db_session,
        requester_user,
        admin_user,
        requester_auth_header,
    ) -> None:
        # Create a CR owned by the requester
        client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(title="Mine"),
        )
        # Manually create one owned by the admin
        from app.schemas.change_request import ChangeRequestCreate
        from app.services.change_request_service import create_change_request

        create_change_request(
            db_session,
            admin_user,
            ChangeRequestCreate(**_valid_create_payload(title="Not mine")),
        )
        db_session.commit()

        response = client.get("/api/v1/change-requests", headers=requester_auth_header)
        assert response.status_code == 200
        titles = [c["title"] for c in response.json()]
        assert "Mine" in titles
        assert "Not mine" not in titles

    def test_admin_sees_all_changes(self, client, requester_auth_header, admin_auth_header) -> None:
        client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(title="Requester's change"),
        )
        response = client.get("/api/v1/change-requests", headers=admin_auth_header)
        assert response.status_code == 200
        titles = [c["title"] for c in response.json()]
        assert "Requester's change" in titles

    def test_filter_by_status(self, client, requester_auth_header) -> None:
        client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(),
        )
        response = client.get(
            "/api/v1/change-requests?status=draft",
            headers=requester_auth_header,
        )
        assert response.status_code == 200
        assert all(c["status"] == "draft" for c in response.json())

    def test_filter_by_status_excludes_other_statuses(self, client, requester_auth_header) -> None:
        client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(),
        )
        response = client.get(
            "/api/v1/change-requests?status=approved",
            headers=requester_auth_header,
        )
        assert response.status_code == 200
        assert response.json() == []


class TestDetail:
    def test_owner_can_read_own_change(self, client, requester_auth_header) -> None:
        create = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(),
        )
        cr_id = create.json()["id"]
        detail = client.get(f"/api/v1/change-requests/{cr_id}", headers=requester_auth_header)
        assert detail.status_code == 200
        body = detail.json()
        assert body["id"] == cr_id
        assert "available_transitions" in body
        assert "status_history" in body
        assert "risk_breakdown" in body
        assert isinstance(body["risk_breakdown"], dict)

    def test_other_requester_cannot_read_someone_elses_change(
        self,
        client,
        requester_auth_header,
        db_session,
    ) -> None:
        # Create a CR owned by the seeded requester
        create = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(),
        )
        cr_id = create.json()["id"]

        # Make a second requester and log in as them
        from app.core.roles import Role
        from app.schemas.user import UserCreate
        from app.services.user_service import create_user

        create_user(
            db_session,
            UserCreate(
                email="other-req@example.com",
                full_name="Other Req",
                password="TestPass123!",
                role=Role.REQUESTER,
            ),
        )
        db_session.commit()
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "other-req@example.com", "password": "TestPass123!"},
        )
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Other requester should get 404 (not 403 - we deliberately don't leak
        # whether the resource exists)
        detail = client.get(f"/api/v1/change-requests/{cr_id}", headers=other_headers)
        assert detail.status_code == 404

    def test_404_for_nonexistent_id(self, client, admin_auth_header) -> None:
        response = client.get(
            "/api/v1/change-requests/00000000-0000-0000-0000-000000000000",
            headers=admin_auth_header,
        )
        assert response.status_code == 404


class TestUpdate:
    def test_owner_can_update_draft(self, client, requester_auth_header) -> None:
        create = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(),
        )
        cr_id = create.json()["id"]
        response = client.patch(
            f"/api/v1/change-requests/{cr_id}",
            headers=requester_auth_header,
            json={"title": "Updated title"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated title"

    def test_updating_risk_inputs_rescores_risk(self, client, requester_auth_header) -> None:
        create = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(
                impact="individual", downtime_minutes=0, affected_ci_count=1
            ),
        )
        body = create.json()
        cr_id = body["id"]
        initial_score = body["risk_score"]

        response = client.patch(
            f"/api/v1/change-requests/{cr_id}",
            headers=requester_auth_header,
            json={
                "impact": "university",
                "downtime_minutes": 240,
                "affected_ci_count": 50,
                "is_security_related": True,
            },
        )
        assert response.status_code == 200
        assert response.json()["risk_score"] > initial_score


class TestTransitions:
    def test_submit_moves_to_submitted(self, client, requester_auth_header) -> None:
        create = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(),
        )
        cr_id = create.json()["id"]
        response = client.post(
            f"/api/v1/change-requests/{cr_id}/transitions",
            headers=requester_auth_header,
            json={"name": "submit"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "submitted"
        assert len(body["status_history"]) == 1
        assert body["status_history"][0]["to_status"] == "submitted"

    def test_invalid_transition_returns_conflict(self, client, requester_auth_header) -> None:
        # Can't approve from draft
        create = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(),
        )
        cr_id = create.json()["id"]
        response = client.post(
            f"/api/v1/change-requests/{cr_id}/transitions",
            headers=requester_auth_header,
            json={"name": "approve"},
        )
        assert response.status_code == 409

    def test_role_forbidden_transition_returns_403(
        self, client, requester_auth_header, admin_auth_header
    ) -> None:
        # Create as admin so requester isn't the owner (avoids the 'edit own'
        # path) and submit it
        create = client.post(
            "/api/v1/change-requests",
            headers=admin_auth_header,
            json=_valid_create_payload(),
        )
        cr_id = create.json()["id"]
        client.post(
            f"/api/v1/change-requests/{cr_id}/transitions",
            headers=admin_auth_header,
            json={"name": "submit"},
        )
        # Now the requester (different user) tries to start review - they can
        # see the CR? Actually they can't, since the requester only sees their
        # own. Use a manager-level role to test the forbidden case instead.
        # We'll test that the requester can't approve from under_review.
        client.post(
            f"/api/v1/change-requests/{cr_id}/transitions",
            headers=admin_auth_header,
            json={"name": "start_review"},
        )
        # Approver can approve, but if a requester tried, they couldn't even
        # see this. So the test we actually want is from the *requester's own*
        # change - they can't start_review on their own draft.
        own_create = client.post(
            "/api/v1/change-requests",
            headers=requester_auth_header,
            json=_valid_create_payload(),
        )
        own_id = own_create.json()["id"]
        client.post(
            f"/api/v1/change-requests/{own_id}/transitions",
            headers=requester_auth_header,
            json={"name": "submit"},
        )
        response = client.post(
            f"/api/v1/change-requests/{own_id}/transitions",
            headers=requester_auth_header,
            json={"name": "start_review"},
        )
        assert response.status_code == 403

    def test_schedule_without_window_returns_422(self, client, admin_auth_header) -> None:
        # Walk to APPROVED then try to schedule without setting the window
        create = client.post(
            "/api/v1/change-requests",
            headers=admin_auth_header,
            json=_valid_create_payload(),
        )
        cr_id = create.json()["id"]
        for t in ("submit", "start_review", "approve"):
            client.post(
                f"/api/v1/change-requests/{cr_id}/transitions",
                headers=admin_auth_header,
                json={"name": t},
            )
        response = client.post(
            f"/api/v1/change-requests/{cr_id}/transitions",
            headers=admin_auth_header,
            json={"name": "schedule"},
        )
        assert response.status_code == 422

    def test_full_happy_path_via_api(self, client, admin_auth_header) -> None:
        # An admin can do every role's job in the MVP
        now = datetime.now(UTC)
        create = client.post(
            "/api/v1/change-requests",
            headers=admin_auth_header,
            json=_valid_create_payload(
                scheduled_start=(now + timedelta(hours=1)).isoformat(),
                scheduled_end=(now + timedelta(hours=2)).isoformat(),
            ),
        )
        cr_id = create.json()["id"]

        for step in (
            "submit",
            "start_review",
            "approve",
            "schedule",
            "start_implementation",
            "mark_implemented",
            "close",
        ):
            r = client.post(
                f"/api/v1/change-requests/{cr_id}/transitions",
                headers=admin_auth_header,
                json={"name": step, "reason": f"step: {step}"},
            )
            assert r.status_code == 200, f"{step}: {r.text}"

        final = client.get(f"/api/v1/change-requests/{cr_id}", headers=admin_auth_header)
        assert final.json()["status"] == "closed"
        assert len(final.json()["status_history"]) == 7
