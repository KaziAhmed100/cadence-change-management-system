"""ChangeStatusHistory model.

Every state transition on a ChangeRequest produces a row here. This is
intentionally separate from the full audit log (Phase 7) - status history
is a first-class domain concept that the UI surfaces ('this change moved
to approved 2 hours ago'), whereas the audit log captures *every* mutation.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ChangeStatusHistory(Base):
    __tablename__ = "change_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=__import__("sqlalchemy").text("gen_random_uuid()"),
    )

    change_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("change_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Both from_status and to_status are stored so the row is self-contained -
    # no need to read the previous history row to reconstruct what happened.
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)

    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)

    # Free-text reason - especially important for rejections and cancellations
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    change_request = relationship("ChangeRequest", back_populates="status_history")
    actor = relationship("User", foreign_keys=[actor_id])
