"""User model.

A user has an email (login), a hashed password, a display name, an active
flag, and a single role. We deliberately store the role as a string column
(matching the Role enum values) rather than using Postgres's native enum
type - SQL enums are painful to modify with Alembic, and a CHECK constraint
plus the Python enum gives us 95% of the safety with none of the migration
pain.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.roles import Role
from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    # Postgres gen_random_uuid() (from pgcrypto, enabled in init.sql) generates
    # the UUID server-side so we don't depend on app-side UUID generation
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=__import__("sqlalchemy").text("gen_random_uuid()"),
    )

    # CITEXT (case-insensitive text, from the citext extension) means we don't
    # have to LOWER() every email lookup. Falls back to TEXT in tests if needed.
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(String(32), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        # Belt and suspenders: enforce role values at the DB level too. If we
        # ever add a new role we'll bump this constraint in a migration.
        CheckConstraint(
            "role IN ('admin', 'change_manager', 'approver', 'requester')",
            name="ck_users_role_valid",
        ),
    )

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"

    @property
    def role_enum(self) -> Role:
        """Convenience accessor for the typed enum value."""
        return Role(self.role)
