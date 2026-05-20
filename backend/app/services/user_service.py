"""User service.

The service layer sits between the HTTP layer (endpoints) and the persistence
layer (models). It owns business logic - the rules that would apply no matter
how the user was created (CLI, API, seed script, etc.).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate


class UserAlreadyExistsError(Exception):
    """Raised when attempting to create a user with an email that's taken."""


def get_user_by_email(db: Session, email: str) -> User | None:
    """Look up a user by email. Returns None if not found."""
    stmt = select(User).where(User.email == email.lower())
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Look up a user by primary key. Returns None if not found."""
    return db.get(User, user_id)


def create_user(db: Session, payload: UserCreate) -> User:
    """Create a new user.

    Raises UserAlreadyExistsError if the email is taken. The caller is
    responsible for committing the transaction.
    """
    existing = get_user_by_email(db, payload.email)
    if existing is not None:
        raise UserAlreadyExistsError(f"User with email {payload.email!r} already exists")

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role.value,
        is_active=True,
    )
    db.add(user)
    db.flush()  # flush so the caller can read user.id without committing
    return user
