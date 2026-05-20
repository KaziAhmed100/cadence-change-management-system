"""SQLAlchemy engine and session factory.

We use a single engine per process (the standard pattern for sync SQLAlchemy)
and a sessionmaker that produces short-lived sessions, one per HTTP request.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

# Engine config:
# - pool_pre_ping catches stale connections from the DB closing them on idle
#   (relevant on Railway/managed Postgres where this happens regularly)
# - future=True opts into 2.0-style behavior
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    future=True,
    # Tighten the pool for the demo footprint. We'll bump this later if needed.
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request.

    The session is closed in the `finally` block so it's released even when
    an endpoint raises. We don't commit here - that's the endpoint's job, so
    each endpoint controls its own transaction boundary explicitly.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
