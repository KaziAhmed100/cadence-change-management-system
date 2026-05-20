"""Seed the database with demo data.

Usage (from backend/ with venv active):
    python -m scripts.seed_demo_data

Idempotent: running it twice on the same DB will leave it in roughly the same
state. Users won't be duplicated. Change requests are skipped if any rows
already exist in the change_requests table.

What gets created:
- 4 demo users (one per role)
- ~10 change requests in a mix of states (draft, submitted, under review,
  approved, scheduled, in progress, implemented, closed, rejected, cancelled)
  so the dashboard has something to display

The CR data is built to look realistic enough that a recruiter clicking around
sees a populated, plausible IT environment - not lorem ipsum.
"""

import logging
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.change_enums import ChangeType, ImpactLevel
from app.core.roles import Role
from app.db.session import SessionLocal
from app.models.change_request import ChangeRequest
from app.models.user import User
from app.schemas.change_request import ChangeRequestCreate
from app.schemas.user import UserCreate
from app.services.change_request_service import apply_transition, create_change_request
from app.services.user_service import UserAlreadyExistsError, create_user, get_user_by_email

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


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


def seed_users(db: Session) -> dict[Role, User]:
    """Create demo users. Returns a {role: user} map for downstream use."""
    users_by_role: dict[Role, User] = {}
    created = 0
    skipped = 0
    for user_data in DEMO_USERS:
        try:
            user = create_user(db, UserCreate(**user_data))
            created += 1
        except UserAlreadyExistsError:
            user = get_user_by_email(db, user_data["email"])
            skipped += 1
        users_by_role[user_data["role"]] = user
    db.commit()
    logger.info("Users: %d created, %d already existed", created, skipped)
    return users_by_role


def _change_request_scenarios(now: datetime) -> list[tuple[dict, list[str]]]:
    """Each entry: (payload kwargs, transitions to apply after creation)."""
    return [
        # 1. Fresh draft
        (
            {
                "title": "Patch Confluence to latest LTS",
                "description": (
                    "Routine patching of the campus Confluence instance to the "
                    "latest long-term-support version. Maintenance window planned "
                    "for next weekend."
                ),
                "change_type": ChangeType.NORMAL,
                "impact": ImpactLevel.DEPARTMENT,
                "downtime_minutes": 30,
                "affected_ci_count": 1,
                "is_security_related": False,
                "rollback_plan": "Revert via snapshot taken before patching.",
            },
            [],
        ),
        # 2. Submitted, waiting for manager pickup
        (
            {
                "title": "Add new VLAN for IoT lab",
                "description": (
                    "Provision a dedicated VLAN for the new IoT teaching lab in "
                    "Engineering Building room 412. Switches and access controls "
                    "to be configured by the network team."
                ),
                "change_type": ChangeType.NORMAL,
                "impact": ImpactLevel.TEAM,
                "downtime_minutes": 0,
                "affected_ci_count": 2,
                "is_security_related": False,
                "rollback_plan": "Remove VLAN config; no downstream impact.",
            },
            ["submit"],
        ),
        # 3. Under review
        (
            {
                "title": "Database failover testing - Banner SIS",
                "description": (
                    "Quarterly DR exercise. Failover Banner SIS to the warm "
                    "standby and validate downstream integrations. Read-only "
                    "interruption expected for ~15 minutes."
                ),
                "change_type": ChangeType.NORMAL,
                "impact": ImpactLevel.UNIVERSITY,
                "downtime_minutes": 15,
                "affected_ci_count": 5,
                "is_security_related": False,
                "rollback_plan": "Standard failback procedure documented in runbook DR-08.",
            },
            ["submit", "start_review"],
        ),
        # 4. Approved, awaiting scheduling
        (
            {
                "title": "Renew TLS certificates - portal.temple.edu",
                "description": (
                    "Annual renewal of TLS certificates for the student portal. "
                    "Zero-downtime rollout via blue/green."
                ),
                "change_type": ChangeType.NORMAL,
                "impact": ImpactLevel.UNIVERSITY,
                "downtime_minutes": 0,
                "affected_ci_count": 3,
                "is_security_related": True,
                "rollback_plan": (
                    "Old certs remain valid for 14 days; revert load-balancer "
                    "config if issues arise."
                ),
            },
            ["submit", "start_review", "approve"],
        ),
        # 5. Scheduled
        (
            {
                "title": "Increase shared storage quota - College of Science",
                "description": (
                    "Bump shared filesystem quota from 50TB to 75TB. Live "
                    "operation, no expected downtime."
                ),
                "change_type": ChangeType.NORMAL,
                "impact": ImpactLevel.DEPARTMENT,
                "downtime_minutes": 0,
                "affected_ci_count": 1,
                "is_security_related": False,
                "rollback_plan": "Revert quota setting; no data movement involved.",
                "scheduled_start": now + timedelta(days=2),
                "scheduled_end": now + timedelta(days=2, hours=1),
            },
            ["submit", "start_review", "approve", "schedule"],
        ),
        # 6. In progress
        (
            {
                "title": "Upgrade core authentication provider",
                "description": (
                    "Upgrade the campus identity provider to v8.2 with the new "
                    "MFA enforcement features. Multi-step rollout coordinated "
                    "with the IAM team."
                ),
                "change_type": ChangeType.MAJOR,
                "impact": ImpactLevel.UNIVERSITY,
                "downtime_minutes": 45,
                "affected_ci_count": 12,
                "is_security_related": True,
                "rollback_plan": (
                    "Roll back to v8.1 via configuration snapshot; MFA "
                    "enforcement can be toggled off independently."
                ),
                "scheduled_start": now - timedelta(minutes=30),
                "scheduled_end": now + timedelta(hours=1),
            },
            ["submit", "start_review", "approve", "schedule", "start_implementation"],
        ),
        # 7. Implemented, awaiting closure
        (
            {
                "title": "Apply emergency security patch CVE-2026-1234",
                "description": (
                    "Critical CVE in web framework affecting public-facing apps. "
                    "Emergency change to apply vendor patch ASAP."
                ),
                "change_type": ChangeType.EMERGENCY,
                "impact": ImpactLevel.EXTERNAL,
                "downtime_minutes": 5,
                "affected_ci_count": 4,
                "is_security_related": True,
                "rollback_plan": (
                    "Vendor-provided rollback script; tested in staging this morning."
                ),
                "scheduled_start": now - timedelta(hours=3),
                "scheduled_end": now - timedelta(hours=2),
            },
            [
                "submit",
                "start_review",
                "approve",
                "schedule",
                "start_implementation",
                "mark_implemented",
            ],
        ),
        # 8. Closed
        (
            {
                "title": "Decommission legacy file share \\\\fs01\\public",
                "description": (
                    "Long-deprecated public share with no activity in 18 months. "
                    "Final removal after backup."
                ),
                "change_type": ChangeType.STANDARD,
                "impact": ImpactLevel.INDIVIDUAL,
                "downtime_minutes": 0,
                "affected_ci_count": 1,
                "is_security_related": False,
                "rollback_plan": "Backup retained for 90 days; can restore if needed.",
                "scheduled_start": now - timedelta(days=5),
                "scheduled_end": now - timedelta(days=4, hours=23),
            },
            [
                "submit",
                "start_review",
                "approve",
                "schedule",
                "start_implementation",
                "mark_implemented",
                "close",
            ],
        ),
        # 9. Rejected
        (
            {
                "title": "Globally disable Powershell on faculty endpoints",
                "description": (
                    "Proposal to disable Powershell on all faculty endpoints "
                    "as a security measure."
                ),
                "change_type": ChangeType.NORMAL,
                "impact": ImpactLevel.UNIVERSITY,
                "downtime_minutes": 0,
                "affected_ci_count": 1500,
                "is_security_related": True,
                "rollback_plan": "Re-enable via GPO.",
            },
            ["submit", "start_review", "reject"],
        ),
        # 10. Cancelled
        (
            {
                "title": "Migrate library catalog to new search engine",
                "description": (
                    "Replace the library catalog's search backend. Scope under "
                    "review with the vendor."
                ),
                "change_type": ChangeType.NORMAL,
                "impact": ImpactLevel.DEPARTMENT,
                "downtime_minutes": 60,
                "affected_ci_count": 2,
                "is_security_related": False,
                "rollback_plan": "Revert DNS to old backend.",
            },
            ["submit", "cancel"],
        ),
    ]


def seed_change_requests(db: Session, users: dict[Role, User]) -> None:
    """Create demo change requests if none exist."""
    existing = db.execute(select(ChangeRequest).limit(1)).scalar_one_or_none()
    if existing is not None:
        logger.info("Change requests: existing rows found, skipping seed")
        return

    requester = users[Role.REQUESTER]
    manager = users[Role.CHANGE_MANAGER]
    approver = users[Role.APPROVER]

    # Map each transition name to the user role that's allowed to do it
    transition_actor: dict[str, User] = {
        "submit": requester,
        "start_review": manager,
        "approve": approver,
        "reject": approver,
        "schedule": manager,
        "start_implementation": requester,
        "mark_implemented": requester,
        "mark_failed": requester,
        "rollback": requester,
        "close": manager,
        "cancel": requester,
    }

    now = datetime.now(UTC)
    created = 0
    for payload_kwargs, transitions in _change_request_scenarios(now):
        cr = create_change_request(db, requester, ChangeRequestCreate(**payload_kwargs))
        for transition_name in transitions:
            actor = transition_actor[transition_name]
            reason: str | None = None
            if transition_name == "reject":
                reason = "Scope too broad - would break too many faculty workflows"
            elif transition_name == "cancel":
                reason = "Vendor delivery slipped; postponing to next semester"
            apply_transition(db, cr, actor, transition_name, reason)
        created += 1

    db.commit()
    logger.info("Change requests: %d created", created)


def main() -> int:
    db = SessionLocal()
    try:
        users = seed_users(db)
        seed_change_requests(db, users)
    except Exception:
        db.rollback()
        logger.exception("Seed failed")
        return 1
    finally:
        db.close()
    logger.info("Seed complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
