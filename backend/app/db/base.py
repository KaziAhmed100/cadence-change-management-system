"""SQLAlchemy declarative base.

All ORM models inherit from `Base`. Keeping this in its own file (rather than
in db/session.py) avoids circular imports between models and session config.
"""

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Project-wide declarative base.

    We use a small set of project-wide conventions enforced via mixins below
    rather than overriding metadata directly.
    """

    # SQLAlchemy 2.0 style type annotations
    type_annotation_map: ClassVar[dict[Any, Any]] = {}


class TimestampMixin:
    """Adds created_at / updated_at to any model that uses it.

    `server_default=func.now()` lets Postgres set the default at insert time
    so we don't depend on the app clock being accurate.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
