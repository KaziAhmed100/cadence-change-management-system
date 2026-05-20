"""Change request domain enums.

All of these are stored as VARCHAR + CHECK constraint in Postgres (same pattern
as the Role enum from Phase 2). String values are what go in the DB and in the
API, so don't rename them without a migration.
"""

from enum import Enum


class ChangeType(str, Enum):
    """ITIL-style change types - dictate the workflow.

    - STANDARD: pre-approved, low-risk, repetitive. Auto-approves and skips CAB.
    - NORMAL: standard workflow with CAB review.
    - EMERGENCY: bypass normal lead times for outages/critical patches.
    - MAJOR: high-risk, high-impact. Requires full CAB + executive sign-off.

    For the MVP we model all four but the routing differences mostly land in
    Phase 4 (approval workflows). At this layer the type is just metadata.
    """

    STANDARD = "standard"
    NORMAL = "normal"
    EMERGENCY = "emergency"
    MAJOR = "major"


class ChangeStatus(str, Enum):
    """States in the change lifecycle.

    The state machine in services/change_state_machine.py enforces which
    transitions are legal. Don't add a state here without also adding
    transitions for it.
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

    @classmethod
    def terminal_states(cls) -> set["ChangeStatus"]:
        """States from which no further transitions are allowed."""
        return {cls.CLOSED, cls.CANCELLED, cls.REJECTED, cls.ROLLED_BACK}


class ImpactLevel(str, Enum):
    """How wide the blast radius is if this change goes sideways.

    Drives the risk score. Higher impact = higher risk multiplier.
    """

    INDIVIDUAL = "individual"  # one user / one machine
    TEAM = "team"  # one department or team
    DEPARTMENT = "department"  # a whole department
    UNIVERSITY = "university"  # university-wide
    EXTERNAL = "external"  # affects external partners / public services


class RiskBand(str, Enum):
    """Human-readable risk label, derived from the numeric risk_score.

    The numeric score (1-10) drives logic; the band is what gets shown in
    the UI. See change_risk.py for the score -> band mapping.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
