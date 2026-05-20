"""Unit tests for the user service.

These tests hit the DB but not the HTTP layer - they exercise the service
functions directly. That separation lets us test business rules without
worrying about request/response plumbing.
"""

import pytest

from app.core.roles import Role
from app.core.security import verify_password
from app.schemas.user import UserCreate
from app.services.user_service import (
    UserAlreadyExistsError,
    create_user,
    get_user_by_email,
    get_user_by_id,
)


class TestCreateUser:
    def test_creates_user_with_hashed_password(self, db_session) -> None:
        user = create_user(
            db_session,
            UserCreate(
                email="alice@example.com",
                full_name="Alice Example",
                password="MySecret123!",
                role=Role.REQUESTER,
            ),
        )
        # Stored password must not be the plaintext
        assert user.hashed_password != "MySecret123!"
        # But it must verify against the plaintext
        assert verify_password("MySecret123!", user.hashed_password)
        # And basic fields should be set as expected
        assert user.email == "alice@example.com"
        assert user.role == "requester"
        assert user.is_active is True

    def test_email_is_normalized_to_lowercase(self, db_session) -> None:
        user = create_user(
            db_session,
            UserCreate(
                email="Bob@Example.com",
                full_name="Bob",
                password="Password123!",
                role=Role.REQUESTER,
            ),
        )
        assert user.email == "bob@example.com"

    def test_duplicate_email_raises(self, db_session) -> None:
        payload = UserCreate(
            email="dup@example.com",
            full_name="First",
            password="Password123!",
            role=Role.REQUESTER,
        )
        create_user(db_session, payload)
        with pytest.raises(UserAlreadyExistsError):
            create_user(db_session, payload)


class TestGetters:
    def test_get_by_email_returns_none_when_missing(self, db_session) -> None:
        assert get_user_by_email(db_session, "ghost@example.com") is None

    def test_get_by_email_is_case_insensitive(self, db_session) -> None:
        create_user(
            db_session,
            UserCreate(
                email="Carol@Example.com",
                full_name="Carol",
                password="Password123!",
                role=Role.REQUESTER,
            ),
        )
        # Lookup with different casing should still find them
        found = get_user_by_email(db_session, "CAROL@EXAMPLE.COM")
        assert found is not None
        assert found.email == "carol@example.com"

    def test_get_by_id_roundtrips(self, db_session) -> None:
        created = create_user(
            db_session,
            UserCreate(
                email="dave@example.com",
                full_name="Dave",
                password="Password123!",
                role=Role.APPROVER,
            ),
        )
        fetched = get_user_by_id(db_session, created.id)
        assert fetched is not None
        assert fetched.id == created.id
