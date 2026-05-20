"""ChangeRequest model.

The central entity in Cadence. Everything else (approvals in Phase 4, calendar
entries in Phase 5, CAB items in Phase 6, audit records in Phase 7) references
this table.

A note on the id strategy: we have both a UUID `id` (primary key) and a
human-readable `reference` like 'CHG-0142'. The UUID is what we use in URLs,
foreign keys, and APIs - it doesn't leak volume to outsiders and works in
distributed systems. The reference is for humans - what users say out loud
('did you see CHG-142?'), what shows up in emails, what gets pasted in Slack.

The reference uses a database sequence so allocation is atomic even under
concurrent inserts.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ChangeRequest(Base, TimestampMixin):
    __tablename__ = "change_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Human-readable reference, formatted like CHG-0001 from a sequence
    # called change_request_seq. The sequence is created in the migration.
    reference: Mapped[str] = mapped_column(
        String(16),
        unique=True,
        nullable=False,
        server_default=text("'CHG-' || lpad(nextval('change_request_seq')::text, 4, '0')"),
        index=True,
    )

    # Core fields
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Type and status are both string + CHECK constraint (see __table_args__)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )

    # Risk assessment - stored at submission time. Recomputed when inputs change.
    impact: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_band: Mapped[str] = mapped_column(String(16), nullable=False)

    # Risk algorithm inputs - we keep these denormalized so we can re-score
    # without joining other tables, and so we can show them in the UI.
    downtime_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    affected_ci_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    is_security_related: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=text("false")
    )

    # Rollback plan is a free-text field; required for the risk algorithm to
    # not penalize the change. Storing the text rather than a boolean lets
    # reviewers actually evaluate the plan.
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scheduling - filled in before the change moves to SCHEDULED.
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Implementation tracking timestamps
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Who submitted this. We don't allow deleting users that own CRs, so
    # ondelete is RESTRICT (the default).
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    requester = relationship("User", foreign_keys=[requester_id])

    status_history = relationship(
        "ChangeStatusHistory",
        back_populates="change_request",
        cascade="all, delete-orphan",
        order_by="ChangeStatusHistory.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "change_type IN ('standard', 'normal', 'emergency', 'major')",
            name="ck_change_requests_type_valid",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'under_review', 'approved', "
            "'rejected', 'scheduled', 'in_progress', 'implemented', "
            "'closed', 'cancelled', 'failed', 'rolled_back')",
            name="ck_change_requests_status_valid",
        ),
        CheckConstraint(
            "impact IN ('individual', 'team', 'department', 'university', 'external')",
            name="ck_change_requests_impact_valid",
        ),
        CheckConstraint(
            "risk_band IN ('low', 'medium', 'high', 'critical')",
            name="ck_change_requests_risk_band_valid",
        ),
        CheckConstraint(
            "risk_score >= 1 AND risk_score <= 10",
            name="ck_change_requests_risk_score_range",
        ),
        # If both are set, end must be after start.
        CheckConstraint(
            "scheduled_end IS NULL OR scheduled_start IS NULL "
            "OR scheduled_end > scheduled_start",
            name="ck_change_requests_scheduled_window_valid",
        ),
    )

    def __repr__(self) -> str:
        return f"<ChangeRequest {self.reference} status={self.status}>"
