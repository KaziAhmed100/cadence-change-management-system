"""Seed the database with demo users.

Usage (from backend/ with venv active):
    python -m scripts.seed_demo_data

Idempotent: running it twice is a no-op (won't recreate existing users).
Designed to be safe to run against any environment, but obviously the
hardcoded password should never be reused for a real user.
"""

import logging
import sys

from sqlalchemy.orm import Session

from app.core.roles import Role
from app.db.session import SessionLocal
from app.schemas.user import UserCreate
from app.services.user_service import UserAlreadyExistsError, create_user

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# These are the demo accounts surfaced in the README. They're for the deployed
# demo only - we'd never seed an account with a published password in prod.
DEMO_USERS: list[dict] = [
    {
        "email": "admin@cadence.dev",
        "full_name": "Alex Admin",
        "password": "Cadence2026!",
        "role": Role.ADMIN,
    },
    {
        "email": "manager@cadence.dev",
        "full_name": "Morgan Manager",
        "password": "Cadence2026!",
        "role": Role.CHANGE_MANAGER,
    },
    {
        "email": "approver@cadence.dev",
        "full_name": "Avery Approver",
        "password": "Cadence2026!",
        "role": Role.APPROVER,
    },
    {
        "email": "requester@cadence.dev",
        "full_name": "Riley Requester",
        "password": "Cadence2026!",
        "role": Role.REQUESTER,
    },
]


def seed_users(db: Session) -> None:
    created_count = 0
    skipped_count = 0

    for user_data in DEMO_USERS:
        try:
            user = create_user(db, UserCreate(**user_data))
            logger.info("Created %s (%s)", user.email, user.role)
            created_count += 1
        except UserAlreadyExistsError:
            logger.info("Skipped %s (already exists)", user_data["email"])
            skipped_count += 1

    db.commit()
    logger.info("Seed complete: %d created, %d skipped", created_count, skipped_count)


def main() -> int:
    db = SessionLocal()
    try:
        seed_users(db)
    except Exception:
        db.rollback()
        logger.exception("Seed failed")
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
