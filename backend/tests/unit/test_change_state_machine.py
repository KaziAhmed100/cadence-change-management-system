"""Unit tests for the change request state machine.

These tests don't touch the DB - they exercise the state machine module
directly against in-memory objects. That keeps them fast and lets us focus
on transition correctness.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.change_enums import ChangeStatus
from app.core.roles import Role
from app.services.change_state_machine import (
    InvalidTransitionError,
    TransitionForbiddenError,
    TransitionGuardError,
    list_available_transitions,
    transition,
)


def _cr(status: ChangeStatus, **extra) -> SimpleNamespace:
    """Build a stand-in change_request object the state machine can mutate."""
    defaults = {
        "status": status.value,
        "scheduled_start": None,
        "scheduled_end": None,
    }
    defaults.update(extra)
    return SimpleNamespace(**defaults)


class TestHappyPath:
    """The full draft -> closed lifecycle, one transition at a time."""

    def test_full_lifecycle(self) -> None:
        now = datetime.now(UTC)
        cr = _cr(
            ChangeStatus.DRAFT,
            scheduled_start=now + timedelta(days=1),
            scheduled_end=now + timedelta(days=1, hours=2),
        )

        # submit
        event = transition(cr, "submit", Role.REQUESTER)
        assert event.from_status == ChangeStatus.DRAFT
        assert event.to_status == ChangeStatus.SUBMITTED
        assert cr.status == ChangeStatus.SUBMITTED.value

        # start_review
        transition(cr, "start_review", Role.CHANGE_MANAGER)
        assert cr.status == ChangeStatus.UNDER_REVIEW.value

        # approve
        transition(cr, "approve", Role.APPROVER)
        assert cr.status == ChangeStatus.APPROVED.value

        # schedule
        transition(cr, "schedule", Role.CHANGE_MANAGER)
        assert cr.status == ChangeStatus.SCHEDULED.value

        # start_implementation
        transition(cr, "start_implementation", Role.REQUESTER)
        assert cr.status == ChangeStatus.IN_PROGRESS.value

        # mark_implemented
        transition(cr, "mark_implemented", Role.REQUESTER)
        assert cr.status == ChangeStatus.IMPLEMENTED.value

        # close
        transition(cr, "close", Role.CHANGE_MANAGER)
        assert cr.status == ChangeStatus.CLOSED.value


class TestInvalidTransitions:
    def test_cannot_approve_from_draft(self) -> None:
        cr = _cr(ChangeStatus.DRAFT)
        with pytest.raises(InvalidTransitionError):
            transition(cr, "approve", Role.APPROVER)

    def test_cannot_close_from_in_progress(self) -> None:
        cr = _cr(ChangeStatus.IN_PROGRESS)
        with pytest.raises(InvalidTransitionError):
            transition(cr, "close", Role.CHANGE_MANAGER)

    def test_unknown_transition_name_raises(self) -> None:
        cr = _cr(ChangeStatus.DRAFT)
        with pytest.raises(InvalidTransitionError):
            transition(cr, "yeet", Role.ADMIN)

    def test_no_transitions_from_terminal_state(self) -> None:
        cr = _cr(ChangeStatus.CLOSED)
        # Try a few likely-named transitions
        for name in ("submit", "approve", "schedule", "close", "cancel"):
            with pytest.raises(InvalidTransitionError):
                transition(cr, name, Role.ADMIN)


class TestRoleEnforcement:
    def test_requester_cannot_approve(self) -> None:
        cr = _cr(ChangeStatus.UNDER_REVIEW)
        with pytest.raises(TransitionForbiddenError):
            transition(cr, "approve", Role.REQUESTER)

    def test_requester_cannot_start_review(self) -> None:
        cr = _cr(ChangeStatus.SUBMITTED)
        with pytest.raises(TransitionForbiddenError):
            transition(cr, "start_review", Role.REQUESTER)

    def test_admin_can_do_anything_a_manager_can(self) -> None:
        cr = _cr(ChangeStatus.SUBMITTED)
        # Should not raise
        transition(cr, "start_review", Role.ADMIN)
        assert cr.status == ChangeStatus.UNDER_REVIEW.value


class TestGuards:
    def test_cannot_schedule_without_window(self) -> None:
        cr = _cr(ChangeStatus.APPROVED)
        with pytest.raises(TransitionGuardError, match="scheduled_start"):
            transition(cr, "schedule", Role.CHANGE_MANAGER)

    def test_cannot_schedule_with_end_before_start(self) -> None:
        now = datetime.now(UTC)
        cr = _cr(
            ChangeStatus.APPROVED,
            scheduled_start=now + timedelta(hours=2),
            scheduled_end=now + timedelta(hours=1),
        )
        with pytest.raises(TransitionGuardError, match="must be after"):
            transition(cr, "schedule", Role.CHANGE_MANAGER)

    def test_schedule_with_valid_window_works(self) -> None:
        now = datetime.now(UTC)
        cr = _cr(
            ChangeStatus.APPROVED,
            scheduled_start=now + timedelta(hours=1),
            scheduled_end=now + timedelta(hours=2),
        )
        transition(cr, "schedule", Role.CHANGE_MANAGER)
        assert cr.status == ChangeStatus.SCHEDULED.value


class TestCancellation:
    def test_can_cancel_from_draft(self) -> None:
        cr = _cr(ChangeStatus.DRAFT)
        transition(cr, "cancel", Role.REQUESTER)
        assert cr.status == ChangeStatus.CANCELLED.value

    def test_requester_cannot_cancel_after_under_review(self) -> None:
        cr = _cr(ChangeStatus.UNDER_REVIEW)
        with pytest.raises(TransitionForbiddenError):
            transition(cr, "cancel", Role.REQUESTER)

    def test_manager_can_cancel_after_under_review(self) -> None:
        cr = _cr(ChangeStatus.UNDER_REVIEW)
        transition(cr, "cancel", Role.CHANGE_MANAGER)
        assert cr.status == ChangeStatus.CANCELLED.value


class TestFailureAndRollback:
    def test_mark_failed_then_rollback(self) -> None:
        cr = _cr(ChangeStatus.IN_PROGRESS)
        transition(cr, "mark_failed", Role.REQUESTER)
        assert cr.status == ChangeStatus.FAILED.value
        transition(cr, "rollback", Role.REQUESTER)
        assert cr.status == ChangeStatus.ROLLED_BACK.value


class TestListAvailableTransitions:
    def test_draft_offers_submit_and_cancel(self) -> None:
        opts = list_available_transitions(ChangeStatus.DRAFT, Role.REQUESTER)
        assert "submit" in opts
        assert "cancel" in opts

    def test_requester_doesnt_see_approver_actions(self) -> None:
        opts = list_available_transitions(ChangeStatus.UNDER_REVIEW, Role.REQUESTER)
        assert "approve" not in opts
        assert "reject" not in opts

    def test_terminal_state_has_no_transitions(self) -> None:
        for terminal in ChangeStatus.terminal_states():
            opts = list_available_transitions(terminal, Role.ADMIN)
            assert opts == []
