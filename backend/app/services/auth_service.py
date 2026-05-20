"""Auth service - authentication flow logic.

Kept separate from the user service because auth concerns (token minting,
last-login tracking, eventual rate limiting) are orthogonal to user CRUD.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.user import UserRead
from app.services.user_service import get_user_by_email


class InvalidCredentialsError(Exception):
    """Raised when login credentials don't match a user, or the user is inactive.

    We deliberately use a single error type for both 'wrong password' and
    'no such user' - revealing which would help attackers enumerate accounts.
    """


def authenticate(db: Session, email: str, password: str) -> User:
    """Verify credentials and return the user, or raise InvalidCredentialsError.

    Note: passlib's verify is constant-time. We still call it even when the
    user doesn't exist to avoid leaking account existence via response time.
    """
    user = get_user_by_email(db, email)

    if user is None:
        # Dummy verify against a real bcrypt hash to keep timing similar between
        # "no such user" and "wrong password". The hash below is bcrypt's encoding
        # of an arbitrary value that will never match real input - it just makes
        # passlib actually do work rather than short-circuit.
        verify_password(
            password,
            "$2b$12$KIXKuBpNwGRgRYzv/G6vMu3K7zL7ZxOdQ.OdkO3z4F3z5pXyXyXyW",
        )
        raise InvalidCredentialsError("Invalid credentials")

    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid credentials")

    if not user.is_active:
        raise InvalidCredentialsError("Account is inactive")

    return user


def login(db: Session, email: str, password: str) -> TokenResponse:
    """Full login flow: authenticate, update last_login, mint token, return response."""
    settings = get_settings()
    user = authenticate(db, email, password)

    user.last_login_at = datetime.now(UTC)
    db.flush()

    ttl = timedelta(minutes=settings.jwt_access_token_ttl_minutes)
    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        expires_delta=ttl,
    )

    return TokenResponse(
        access_token=token,
        expires_in=int(ttl.total_seconds()),
        user=UserRead.model_validate(user),
    )
