"""ChangeRequest service.

Business logic: creating change requests, applying updates with re-scoring,
running state transitions atomically with history rows.

This module is intentionally framework-free - no FastAPI imports. The API
layer (endpoints/changes.py) translates HTTP concerns into calls here.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.change_enums import (
    ChangeStatus,
    ChangeType,
    ImpactLevel,
    RiskBand,
)
from app.core.change_risk import RiskInputs, assess_risk
from app.core.roles import Role
from app.models.change_request import ChangeRequest
from app.models.change_status_history import ChangeStatusHistory
from app.models.user import User
from app.schemas.change_request import (
    ChangeRequestCreate,
    ChangeRequestUpdate,
)
from app.services.change_state_machine import (
    TransitionEvent,
    list_available_transitions,
    transition,
)


class ChangeRequestNotFoundError(Exception):
    """Raised when a CR can't be found by id."""


class ChangeRequestAccessDeniedError(Exception):
    """Raised when a user tries to access a CR they're not allowed to.

    Requesters can only see their own CRs; everyone else sees all.
    """


def _compute_risk_for_inputs(
    impact: ImpactLevel,
    downtime_minutes: int,
    affected_ci_count: int,
    is_security_related: bool,
    rollback_plan: str | None,
) -> tuple[int, RiskBand, dict[str, int]]:
    """Helper - extract risk inputs from raw values, compute, return tuple."""
    inputs = RiskInputs(
        impact=impact,
        downtime_minutes=downtime_minutes,
        affected_ci_count=affected_ci_count,
        has_rollback_plan=bool(rollback_plan and rollback_plan.strip()),
        is_security_related=is_security_related,
    )
    assessment = assess_risk(inputs)
    return assessment.score, assessment.band, assessment.breakdown


def create_change_request(
    db: Session,
    requester: User,
    payload: ChangeRequestCreate,
) -> ChangeRequest:
    """Create a new CR in DRAFT state with computed risk."""
    score, band, _breakdown = _compute_risk_for_inputs(
        impact=payload.impact,
        downtime_minutes=payload.downtime_minutes,
        affected_ci_count=payload.affected_ci_count,
        is_security_related=payload.is_security_related,
        rollback_plan=payload.rollback_plan,
    )

    cr = ChangeRequest(
        title=payload.title,
        description=payload.description,
        change_type=payload.change_type.value,
        status=ChangeStatus.DRAFT.value,
        impact=payload.impact.value,
        risk_score=score,
        risk_band=band.value,
        downtime_minutes=payload.downtime_minutes,
        affected_ci_count=payload.affected_ci_count,
        is_security_related=payload.is_security_related,
        rollback_plan=payload.rollback_plan,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        requester_id=requester.id,
    )
    db.add(cr)
    db.flush()  # so we can read cr.id / cr.reference without committing
    return cr


def update_change_request(
    db: Session,
    cr: ChangeRequest,
    payload: ChangeRequestUpdate,
) -> ChangeRequest:
    """Apply a partial update. Re-scores risk if any risk input changed."""
    data = payload.model_dump(exclude_unset=True)

    risk_inputs_changed = any(
        k in data
        for k in (
            "impact",
            "downtime_minutes",
            "affected_ci_count",
            "is_security_related",
            "rollback_plan",
        )
    )

    # Apply scalar updates first
    for key, value in data.items():
        if key in ("impact", "change_type"):
            # Enums - store the string value
            setattr(cr, key, value.value if hasattr(value, "value") else value)
        else:
            setattr(cr, key, value)

    if risk_inputs_changed:
        score, band, _breakdown = _compute_risk_for_inputs(
            impact=ImpactLevel(cr.impact),
            downtime_minutes=cr.downtime_minutes,
            affected_ci_count=cr.affected_ci_count,
            is_security_related=cr.is_security_related,
            rollback_plan=cr.rollback_plan,
        )
        cr.risk_score = score
        cr.risk_band = band.value

    db.flush()
    return cr


def _can_view(cr: ChangeRequest, user: User) -> bool:
    """Authorization predicate for viewing a single CR.

    Requesters see only their own. Everyone else sees everything.
    """
    if user.role == Role.REQUESTER.value:
        return cr.requester_id == user.id
    return True


def _can_edit(cr: ChangeRequest, user: User) -> bool:
    """Authorization predicate for editing a CR.

    The requester can edit their own while it's DRAFT. Managers and admins
    can edit any non-terminal CR.
    """
    if user.role in (Role.CHANGE_MANAGER.value, Role.ADMIN.value):
        return ChangeStatus(cr.status) not in ChangeStatus.terminal_states()
    if user.id == cr.requester_id:
        return cr.status == ChangeStatus.DRAFT.value
    return False


def get_change_request(db: Session, cr_id: uuid.UUID, user: User) -> ChangeRequest:
    """Fetch a CR by id, enforcing view permissions.

    Returns the CR with status_history and requester eagerly loaded.
    """
    stmt = (
        select(ChangeRequest)
        .where(ChangeRequest.id == cr_id)
        .options(
            selectinload(ChangeRequest.requester),
            selectinload(ChangeRequest.status_history),
        )
    )
    cr = db.execute(stmt).scalar_one_or_none()

    if cr is None:
        raise ChangeRequestNotFoundError(f"Change request {cr_id} not found")
    if not _can_view(cr, user):
        # Same error as not-found to avoid leaking existence to unauthorized users
        raise ChangeRequestNotFoundError(f"Change request {cr_id} not found")
    return cr


def list_change_requests(
    db: Session,
    user: User,
    status: ChangeStatus | None = None,
    change_type: ChangeType | None = None,
    risk_band: RiskBand | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ChangeRequest]:
    """List CRs with optional filters and per-user authorization."""
    stmt = select(ChangeRequest).options(selectinload(ChangeRequest.requester))

    if user.role == Role.REQUESTER.value:
        stmt = stmt.where(ChangeRequest.requester_id == user.id)

    if status is not None:
        stmt = stmt.where(ChangeRequest.status == status.value)
    if change_type is not None:
        stmt = stmt.where(ChangeRequest.change_type == change_type.value)
    if risk_band is not None:
        stmt = stmt.where(ChangeRequest.risk_band == risk_band.value)

    stmt = stmt.order_by(ChangeRequest.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


def apply_transition(
    db: Session,
    cr: ChangeRequest,
    user: User,
    transition_name: str,
    reason: str | None,
) -> tuple[ChangeRequest, TransitionEvent]:
    """Apply a state transition and write a history row in the same UoW.

    Returns the (mutated) CR and the event for downstream consumers.
    Raises the state machine's errors unchanged so the API can map them.
    """
    actor_role = Role(user.role)
    event = transition(cr, transition_name, actor_role, reason)

    # Side effects that ride along with specific transitions
    if event.to_status == ChangeStatus.IN_PROGRESS and cr.actual_start is None:
        from datetime import UTC, datetime

        cr.actual_start = datetime.now(UTC)
    if event.to_status in (ChangeStatus.IMPLEMENTED, ChangeStatus.FAILED) and cr.actual_end is None:
        from datetime import UTC, datetime

        cr.actual_end = datetime.now(UTC)

    history = ChangeStatusHistory(
        change_request_id=cr.id,
        from_status=event.from_status.value,
        to_status=event.to_status.value,
        actor_id=user.id,
        actor_role=actor_role.value,
        reason=reason,
    )
    db.add(history)
    db.flush()
    return cr, event


def get_available_transitions(cr: ChangeRequest, user: User) -> list[str]:
    """Public wrapper around the state machine helper - keeps endpoints
    decoupled from internal modules."""
    return list_available_transitions(ChangeStatus(cr.status), Role(user.role))


def get_risk_breakdown(cr: ChangeRequest) -> dict[str, int]:
    """Recompute the risk breakdown for display purposes.

    We don't persist the breakdown - it's deterministic from the inputs, so
    re-deriving it on read is fine and avoids drift if we change the algorithm.
    """
    _score, _band, breakdown = _compute_risk_for_inputs(
        impact=ImpactLevel(cr.impact),
        downtime_minutes=cr.downtime_minutes,
        affected_ci_count=cr.affected_ci_count,
        is_security_related=cr.is_security_related,
        rollback_plan=cr.rollback_plan,
    )
    return breakdown


__all__ = [
    "ChangeRequestAccessDeniedError",
    "ChangeRequestNotFoundError",
    "_can_edit",
    "apply_transition",
    "create_change_request",
    "get_available_transitions",
    "get_change_request",
    "get_risk_breakdown",
    "list_change_requests",
    "update_change_request",
]
