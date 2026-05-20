"""End-to-end tests for the auth endpoints.

These hit FastAPI through the TestClient, so they exercise the full request
pipeline: routing, dependency injection, schema validation, the service
layer, and serialization.
"""


class TestLogin:
    def test_login_with_valid_credentials_returns_token(self, client, requester_user) -> None:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": requester_user.email, "password": "TestPass123!"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str)
        assert body["access_token"]  # non-empty
        assert body["expires_in"] > 0
        # User object is returned alongside the token
        assert body["user"]["email"] == requester_user.email
        assert body["user"]["role"] == "requester"
        # And critically - no password leak
        assert "hashed_password" not in body["user"]
        assert "password" not in body["user"]

    def test_login_rejects_wrong_password(self, client, requester_user) -> None:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": requester_user.email, "password": "wrong"},
        )
        assert response.status_code == 401
        assert "credentials" in response.json()["detail"].lower()

    def test_login_rejects_unknown_email(self, client) -> None:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "whatever"},
        )
        assert response.status_code == 401

    def test_login_rejects_inactive_user(self, client, db_session, requester_user) -> None:
        # Deactivate the user
        requester_user.is_active = False
        db_session.flush()
        response = client.post(
            "/api/v1/auth/login",
            json={"email": requester_user.email, "password": "TestPass123!"},
        )
        assert response.status_code == 401

    def test_login_updates_last_login_at(self, client, db_session, requester_user) -> None:
        before = requester_user.last_login_at
        assert before is None
        client.post(
            "/api/v1/auth/login",
            json={"email": requester_user.email, "password": "TestPass123!"},
        )
        db_session.refresh(requester_user)
        assert requester_user.last_login_at is not None

    def test_login_rejects_malformed_payload(self, client) -> None:
        response = client.post("/api/v1/auth/login", json={"email": "not-an-email"})
        assert response.status_code == 422


class TestMe:
    def test_me_returns_current_user(self, client, requester_user, requester_auth_header) -> None:
        response = client.get("/api/v1/auth/me", headers=requester_auth_header)
        assert response.status_code == 200
        assert response.json()["email"] == requester_user.email

    def test_me_rejects_missing_token(self, client) -> None:
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_me_rejects_invalid_token(self, client) -> None:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer this-is-junk"},
        )
        assert response.status_code == 401

    def test_me_rejects_bearer_without_token(self, client) -> None:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401
