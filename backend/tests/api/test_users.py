"""Tests for /api/v1/users endpoints.

The most important thing to verify here is that role-based access control
works correctly - admins can do everything, non-admins are denied.
"""


class TestListUsers:
    def test_admin_can_list_users(self, client, admin_user, admin_auth_header) -> None:
        response = client.get("/api/v1/users", headers=admin_auth_header)
        assert response.status_code == 200
        body = response.json()
        emails = [u["email"] for u in body]
        assert admin_user.email in emails

    def test_requester_cannot_list_users(self, client, requester_auth_header) -> None:
        response = client.get("/api/v1/users", headers=requester_auth_header)
        assert response.status_code == 403

    def test_unauthenticated_cannot_list_users(self, client) -> None:
        response = client.get("/api/v1/users")
        assert response.status_code == 401


class TestCreateUser:
    def test_admin_can_create_user(self, client, admin_auth_header) -> None:
        response = client.post(
            "/api/v1/users",
            headers=admin_auth_header,
            json={
                "email": "newhire@example.com",
                "full_name": "New Hire",
                "password": "WelcomeAboard1!",
                "role": "requester",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "newhire@example.com"
        assert body["role"] == "requester"
        # Make sure no password fields leak in the response
        assert "password" not in body
        assert "hashed_password" not in body

    def test_requester_cannot_create_user(self, client, requester_auth_header) -> None:
        response = client.post(
            "/api/v1/users",
            headers=requester_auth_header,
            json={
                "email": "x@example.com",
                "full_name": "X",
                "password": "Password123!",
                "role": "requester",
            },
        )
        assert response.status_code == 403

    def test_duplicate_email_returns_conflict(self, client, admin_user, admin_auth_header) -> None:
        response = client.post(
            "/api/v1/users",
            headers=admin_auth_header,
            json={
                "email": admin_user.email,
                "full_name": "Duplicate",
                "password": "Password123!",
                "role": "requester",
            },
        )
        assert response.status_code == 409

    def test_invalid_role_is_rejected(self, client, admin_auth_header) -> None:
        response = client.post(
            "/api/v1/users",
            headers=admin_auth_header,
            json={
                "email": "weird@example.com",
                "full_name": "Weird",
                "password": "Password123!",
                "role": "supreme_overlord",
            },
        )
        assert response.status_code == 422

    def test_short_password_is_rejected(self, client, admin_auth_header) -> None:
        response = client.post(
            "/api/v1/users",
            headers=admin_auth_header,
            json={
                "email": "short@example.com",
                "full_name": "Shorty",
                "password": "abc",  # too short
                "role": "requester",
            },
        )
        assert response.status_code == 422
