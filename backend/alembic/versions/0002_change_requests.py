"""change requests and status history

Revision ID: 0002_change_requests
Revises: 0001_initial_users
Create Date: 2026-05-19 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_change_requests"
down_revision: str | None = "0001_initial_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Sequence for human-readable change reference numbers.
    # Starting at 1000 gives us CHG-1000 onward - looks more 'real' than CHG-0001
    # would for the very first change in a fresh deployment, but the column
    # default uses lpad to 4 chars so a fresh demo starts at CHG-1000.
    op.execute("CREATE SEQUENCE IF NOT EXISTS change_request_seq START WITH 1000")

    op.create_table(
        "change_requests",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "reference",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'CHG-' || lpad(nextval('change_request_seq')::text, 4, '0')"),
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("impact", sa.String(32), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("risk_band", sa.String(16), nullable=False),
        sa.Column(
            "downtime_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "affected_ci_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "is_security_related",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("rollback_plan", sa.Text(), nullable=True),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "requester_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("reference", name="uq_change_requests_reference"),
        sa.CheckConstraint(
            "change_type IN ('standard', 'normal', 'emergency', 'major')",
            name="ck_change_requests_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'under_review', 'approved', "
            "'rejected', 'scheduled', 'in_progress', 'implemented', "
            "'closed', 'cancelled', 'failed', 'rolled_back')",
            name="ck_change_requests_status_valid",
        ),
        sa.CheckConstraint(
            "impact IN ('individual', 'team', 'department', 'university', 'external')",
            name="ck_change_requests_impact_valid",
        ),
        sa.CheckConstraint(
            "risk_band IN ('low', 'medium', 'high', 'critical')",
            name="ck_change_requests_risk_band_valid",
        ),
        sa.CheckConstraint(
            "risk_score >= 1 AND risk_score <= 10",
            name="ck_change_requests_risk_score_range",
        ),
        sa.CheckConstraint(
            "scheduled_end IS NULL OR scheduled_start IS NULL "
            "OR scheduled_end > scheduled_start",
            name="ck_change_requests_scheduled_window_valid",
        ),
    )
    op.create_index("ix_change_requests_reference", "change_requests", ["reference"])
    op.create_index("ix_change_requests_requester_id", "change_requests", ["requester_id"])
    op.create_index("ix_change_requests_status", "change_requests", ["status"])

    op.create_table(
        "change_status_history",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "change_request_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("change_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(32), nullable=False),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column(
            "actor_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("actor_role", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_change_status_history_change_request_id",
        "change_status_history",
        ["change_request_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_change_status_history_change_request_id",
        table_name="change_status_history",
    )
    op.drop_table("change_status_history")
    op.drop_index("ix_change_requests_status", table_name="change_requests")
    op.drop_index("ix_change_requests_requester_id", table_name="change_requests")
    op.drop_index("ix_change_requests_reference", table_name="change_requests")
    op.drop_table("change_requests")
    op.execute("DROP SEQUENCE IF EXISTS change_request_seq")
