"""Auth endpoints: login, oauth-form login (for Swagger UI), and current user."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.auth_service import InvalidCredentialsError, login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in with email and password",
)
def login_endpoint(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Standard JSON login. Returns a JWT and the user record."""
    try:
        response = login(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    db.commit()
    return response


@router.post(
    "/login/oauth",
    response_model=TokenResponse,
    summary="Form-encoded login (for Swagger UI's Authorize button)",
    include_in_schema=False,
)
def login_oauth_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """OAuth2 password-flow endpoint that the FastAPI Swagger UI uses.

    Functionally identical to /login but accepts form-encoded data. We keep
    JSON as the primary contract for the SPA; this one exists so the
    "Authorize" button in /docs works out of the box.
    """
    try:
        # OAuth2 spec uses `username`; we treat it as email
        response = login(db, form.username, form.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    db.commit()
    return response


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the currently authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Returns the user record for the authenticated caller."""
    return current_user
