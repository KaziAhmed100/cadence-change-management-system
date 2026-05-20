"""Pydantic schemas for auth flows."""

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    """Payload for the login endpoint."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """JWT response.

    We return both the token and the user record so the frontend doesn't have
    to make a second /me call right after login. Saves a round trip and is
    standard practice for SPAs.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiry
    user: UserRead
