"""Pydantic schemas for user-related API payloads.

Schemas are the *contract* the API exposes. We deliberately keep them
separate from ORM models so we can evolve internal storage independently
of the public API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.roles import Role


class UserBase(BaseModel):
    """Fields common to most user representations."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)


class UserCreate(UserBase):
    """Payload for creating a user (registration or admin-create).

    Note: in the MVP, only admins create users; there is no public signup.
    The 'register' endpoint exists primarily for testing and for seeding.
    """

    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.REQUESTER


class UserRead(UserBase):
    """User as returned by the API. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None
