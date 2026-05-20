"""Pytest fixtures shared across the test suite.

The test strategy:

- Tests run against a *real* Postgres database (not SQLite) so we exercise
  the same SQL dialect, constraints, and extensions that production uses.
- Each test gets a fresh transaction that's rolled back at the end, so tests
  don't leak state.
- The schema is created once per test session (via Alembic) and reused.

To run the tests locally you need a Postgres DB. The default test URL is
configured to use a `cadence_test` database; create it once with:

    psql -U postgres -c "CREATE DATABASE cadence_test OWNER cadence;"
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Import models so they register with Base.metadata
import app.models  # noqa: F401
from app.core.config import Settings, get_settings
from app.core.roles import Role
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.schemas.user import UserCreate
from app.services.user_service import create_user

# ---------------------------------------------------------------------------
# Settings override
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "postgresql+psycopg2://cadence:cadence@localhost:5432/cadence_test"


@pytest.fixture(scope="session", autouse=True)
def _override_settings() -> Generator[None, None, None]:
    """Force the app to use the test database for the whole session."""

    def _test_settings() -> Settings:
        return Settings(  # type: ignore[call-arg]
            environment="test",
            database_url=TEST_DATABASE_URL,
            jwt_secret="test-secret-not-used-in-production-this-is-fine",
        )

    get_settings.cache_clear()
    # Monkey-patch the cached getter
    original_factory = get_settings.__wrapped__
    get_settings.__wrapped__ = _test_settings  # type: ignore[misc]
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.__wrapped__ = original_factory  # type: ignore[misc]
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_engine():
    """One engine for the whole test session."""
    engine = create_engine(TEST_DATABASE_URL, future=True)

    # Make sure required extensions are present (in case the test DB was
    # created without running our init.sql)
    with engine.connect() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "citext"'))
        conn.commit()

    # Drop + recreate the schema so each test session starts clean
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Per-test session wrapped in a transaction that's always rolled back.

    The pattern: open a connection, begin a transaction, bind a session to
    that connection, and at the end roll the transaction back. This is the
    cleanest way to get true isolation between tests without dropping and
    recreating tables.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection, class_=Session)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with the get_db dependency overridden to use the test session."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        # We yield the *same* session the test is using so reads inside the
        # endpoint see writes from the test setup.
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Convenience fixtures - pre-created users for common test scenarios
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user(db_session: Session):
    user = create_user(
        db_session,
        UserCreate(
            email="test-admin@example.com",
            full_name="Test Admin",
            password="TestPass123!",
            role=Role.ADMIN,
        ),
    )
    db_session.flush()
    return user


@pytest.fixture
def requester_user(db_session: Session):
    user = create_user(
        db_session,
        UserCreate(
            email="test-requester@example.com",
            full_name="Test Requester",
            password="TestPass123!",
            role=Role.REQUESTER,
        ),
    )
    db_session.flush()
    return user


@pytest.fixture
def approver_user(db_session: Session):
    user = create_user(
        db_session,
        UserCreate(
            email="test-approver@example.com",
            full_name="Test Approver",
            password="TestPass123!",
            role=Role.APPROVER,
        ),
    )
    db_session.flush()
    return user


def _login_and_get_token(client: TestClient, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def admin_token(client: TestClient, admin_user) -> str:
    return _login_and_get_token(client, admin_user.email, "TestPass123!")


@pytest.fixture
def requester_token(client: TestClient, requester_user) -> str:
    return _login_and_get_token(client, requester_user.email, "TestPass123!")


@pytest.fixture
def admin_auth_header(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def requester_auth_header(requester_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {requester_token}"}
