"""Change request endpoints.

The API is intentionally REST-ish but pragmatic:
- GET    /change-requests           list with filters
- POST   /change-requests           create (any authenticated user)
- GET    /change-requests/{id}      detail
- PATCH  /change-requests/{id}      partial update
- POST   /change-requests/{id}/transitions   apply a state transition

We don't expose DELETE - changes are cancelled via the state machine, not
hard-deleted. Auditability is the point.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.change_enums import ChangeStatus, ChangeType, RiskBand
from app.db.session import get_db
from app.models.user import User
from app.schemas.change_request import (
    ChangeRequestCreate,
    ChangeRequestDetail,
    ChangeRequestListItem,
    ChangeRequestRead,
    ChangeRequestUpdate,
    ChangeStatusHistoryRead,
    TransitionRequest,
)
from app.services.change_request_service import (
    ChangeRequestNotFoundError,
    _can_edit,
    apply_transition,
    create_change_request,
    get_available_transitions,
    get_change_request,
    get_risk_breakdown,
    list_change_requests,
    update_change_request,
)
from app.services.change_state_machine import (
    InvalidTransitionError,
    TransitionForbiddenError,
    TransitionGuardError,
)

router = APIRouter(prefix="/change-requests", tags=["change-requests"])


def _detail_response(cr: Any, user: User) -> ChangeRequestDetail:
    """Build the full detail payload with derived fields."""
    return ChangeRequestDetail(
        id=cr.id,
        reference=cr.reference,
        title=cr.title,
        description=cr.description,
        change_type=ChangeType(cr.change_type),
        status=ChangeStatus(cr.status),
        impact=cr.impact,
        risk_score=cr.risk_score,
        risk_band=RiskBand(cr.risk_band),
        downtime_minutes=cr.downtime_minutes,
        affected_ci_count=cr.affected_ci_count,
        is_security_related=cr.is_security_related,
        rollback_plan=cr.rollback_plan,
        scheduled_start=cr.scheduled_start,
        scheduled_end=cr.scheduled_end,
        actual_start=cr.actual_start,
        actual_end=cr.actual_end,
        requester=cr.requester,
        created_at=cr.created_at,
        updated_at=cr.updated_at,
        available_transitions=get_available_transitions(cr, user),
        status_history=[ChangeStatusHistoryRead.model_validate(h) for h in cr.status_history],
        risk_breakdown=get_risk_breakdown(cr),
    )


@router.get(
    "",
    response_model=list[ChangeRequestListItem],
    summary="List change requests",
)
def list_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: ChangeStatus | None = Query(default=None, alias="status"),
    change_type: ChangeType | None = Query(default=None),
    risk_band: RiskBand | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """List change requests visible to the current user.

    Requesters see only their own; managers/approvers/admins see all.
    """
    crs = list_change_requests(
        db,
        current_user,
        status=status_filter,
        change_type=change_type,
        risk_band=risk_band,
        limit=limit,
        offset=offset,
    )
    return crs


@router.post(
    "",
    response_model=ChangeRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a change request (starts in DRAFT)",
)
def create_endpoint(
    payload: ChangeRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Any authenticated user can create a change request."""
    cr = create_change_request(db, current_user, payload)
    db.commit()
    db.refresh(cr)
    return cr


@router.get(
    "/{cr_id}",
    response_model=ChangeRequestDetail,
    summary="Get a change request by id",
)
def detail_endpoint(
    cr_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChangeRequestDetail:
    try:
        cr = get_change_request(db, cr_id, current_user)
    except ChangeRequestNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _detail_response(cr, current_user)


@router.patch(
    "/{cr_id}",
    response_model=ChangeRequestDetail,
    summary="Update a change request",
)
def update_endpoint(
    cr_id: uuid.UUID,
    payload: ChangeRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChangeRequestDetail:
    try:
        cr = get_change_request(db, cr_id, current_user)
    except ChangeRequestNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if not _can_edit(cr, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot edit this change in its current state",
        )

    update_change_request(db, cr, payload)
    db.commit()
    db.refresh(cr)
    return _detail_response(cr, current_user)


@router.post(
    "/{cr_id}/transitions",
    response_model=ChangeRequestDetail,
    summary="Apply a state transition (submit, approve, reject, schedule, ...)",
)
def transition_endpoint(
    cr_id: uuid.UUID,
    payload: TransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChangeRequestDetail:
    """Apply one of the named transitions from the state machine.

    The list of legal transitions from the current state is available on
    GET /change-requests/{id} as `available_transitions`.
    """
    try:
        cr = get_change_request(db, cr_id, current_user)
    except ChangeRequestNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        apply_transition(db, cr, current_user, payload.name, payload.reason)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except TransitionForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except TransitionGuardError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    db.commit()
    db.refresh(cr)
    return _detail_response(cr, current_user)
