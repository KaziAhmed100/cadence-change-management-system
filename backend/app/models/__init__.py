"""Model package.

All ORM models must be imported here so that Alembic's autogenerate sees them
when it runs `Base.metadata.create_all` (and so SQLAlchemy resolves any
cross-model relationships at import time).
"""

from app.models.user import User

__all__ = ["User"]
