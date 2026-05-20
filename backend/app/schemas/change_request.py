"""Pydantic schemas for ChangeRequest payloads.

Separation from the ORM model lets the API contract evolve independently
of the internal storage.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.change_enums import (
    ChangeStatus,
    ChangeType,
    ImpactLevel,
    RiskBand,
)

# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class ChangeRequestCreate(BaseModel):
    """Payload for creating a new change request.

    Note we don't accept status or risk_score here - status starts at DRAFT
    and risk is computed server-side from the structured inputs.
    """

    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=10000)
    change_type: ChangeType = ChangeType.NORMAL
    impact: ImpactLevel
    downtime_minutes: int = Field(ge=0, le=10080)  # max one week of downtime
    affected_ci_count: int = Field(ge=1, le=10000)
    is_security_related: bool = False
    rollback_plan: str | None = Field(default=None, max_length=10000)
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None


class ChangeRequestUpdate(BaseModel):
    """Partial update - any field omitted is left as-is.

    Status changes go through /transitions, not this endpoint.
    """

    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10, max_length=10000)
    change_type: ChangeType | None = None
    impact: ImpactLevel | None = None
    downtime_minutes: int | None = Field(default=None, ge=0, le=10080)
    affected_ci_count: int | None = Field(default=None, ge=1, le=10000)
    is_security_related: bool | None = None
    rollback_plan: str | None = Field(default=None, max_length=10000)
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None


class TransitionRequest(BaseModel):
    """Payload for POST /change-requests/{id}/transitions."""

    name: str = Field(min_length=1, max_length=64)
    reason: str | None = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class RequesterSummary(BaseModel):
    """Lightweight user representation embedded in change responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str


class ChangeStatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: ChangeStatus
    to_status: ChangeStatus
    actor_role: str
    reason: str | None
    created_at: datetime


class ChangeRequestRead(BaseModel):
    """Full change request representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    title: str
    description: str
    change_type: ChangeType
    status: ChangeStatus

    impact: ImpactLevel
    risk_score: int
    risk_band: RiskBand

    downtime_minutes: int
    affected_ci_count: int
    is_security_related: bool

    rollback_plan: str | None

    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None

    requester: RequesterSummary

    created_at: datetime
    updated_at: datetime


class ChangeRequestListItem(BaseModel):
    """Trimmed-down representation for list views.

    Omits description and rollback_plan to keep list payloads light.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    title: str
    change_type: ChangeType
    status: ChangeStatus
    impact: ImpactLevel
    risk_score: int
    risk_band: RiskBand
    requester: RequesterSummary
    scheduled_start: datetime | None
    created_at: datetime
    updated_at: datetime


class ChangeRequestDetail(ChangeRequestRead):
    """Full record + state machine info + history."""

    available_transitions: list[str]
    status_history: list[ChangeStatusHistoryRead]
    risk_breakdown: dict[str, int]
