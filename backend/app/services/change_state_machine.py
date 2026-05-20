"""Change request state machine.

A hand-rolled state machine. We deliberately chose not to use a library
(see docs/DESIGN_DECISIONS.md) - the state diagram is small enough that
explicit code is clearer than a DSL.

The lifecycle (happy path):

    DRAFT
      |  (submit)
      v
    SUBMITTED
      |  (start_review)
      v
    UNDER_REVIEW
      |  (approve)                      (reject) ----> REJECTED [terminal]
      v
    APPROVED
      |  (schedule)
      v
    SCHEDULED
      |  (start_implementation)
      v
    IN_PROGRESS
      |  (mark_implemented)              (mark_failed) ----> FAILED
      v                                                       |  (rollback)
    IMPLEMENTED                                                v
      |  (close)                                          ROLLED_BACK [terminal]
      v
    CLOSED [terminal]

CANCELLED is reachable from any non-terminal state.

Each transition can have:
- `allowed_roles`: only these roles can perform the transition
- `required_fields`: properties on the CR that must be non-null before the
  transition is allowed (e.g. you can't SCHEDULE without a scheduled_start)
- `guards`: extra validation callables

The TransitionEvent emitted by the machine is structured so Phase 7's audit
trail can consume it directly.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.change_enums import ChangeStatus
from app.core.roles import Role


class InvalidTransitionError(Exception):
    """Raised when a transition is not legal from the current state."""


class TransitionForbiddenError(Exception):
    """Raised when the user doesn't have permission for the transition."""


class TransitionGuardError(Exception):
    """Raised when a transition's guard rejects the change."""


@dataclass(frozen=True)
class TransitionEvent:
    """Structured record of a successful transition.

    The service layer turns this into a ChangeStatusHistory row and (in
    Phase 7) an audit log entry. Centralizing the shape means later phases
    don't need to dig through the state machine.
    """

    from_status: ChangeStatus
    to_status: ChangeStatus
    actor_role: Role
    reason: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _Transition:
    target: ChangeStatus
    allowed_roles: frozenset[Role]
    # Names of attributes on the ChangeRequest that must be non-null.
    # Empty tuple means no field requirements beyond the base record.
    required_fields: tuple[str, ...] = ()
    # Optional callable: (change_request) -> str | None. Return None to pass
    # the guard; return an error message string to reject.
    guard: Callable | None = None


# All four roles can move things from DRAFT to SUBMITTED (their own requests)
_REQUESTER_AND_UP = frozenset({Role.REQUESTER, Role.APPROVER, Role.CHANGE_MANAGER, Role.ADMIN})
_APPROVER_AND_UP = frozenset({Role.APPROVER, Role.CHANGE_MANAGER, Role.ADMIN})
_MANAGER_AND_UP = frozenset({Role.CHANGE_MANAGER, Role.ADMIN})
_ANY = frozenset({Role.REQUESTER, Role.APPROVER, Role.CHANGE_MANAGER, Role.ADMIN})


def _requires_scheduled_window(cr: Any) -> str | None:
    """Guard: a CR can only be SCHEDULED if both start and end are set,
    and end is after start."""
    if cr.scheduled_start is None or cr.scheduled_end is None:
        return "scheduled_start and scheduled_end must be set"
    if cr.scheduled_end <= cr.scheduled_start:
        return "scheduled_end must be after scheduled_start"
    return None


# The transition table. Lookup is by (from_status, transition_name).
# Keeping it as data (rather than methods on each state) makes the whole
# state diagram visible at a glance.
_TRANSITIONS: dict[tuple[ChangeStatus, str], _Transition] = {
    # Author submits their draft for review
    (ChangeStatus.DRAFT, "submit"): _Transition(
        target=ChangeStatus.SUBMITTED,
        allowed_roles=_REQUESTER_AND_UP,
    ),
    # Manager picks it up and starts reviewing
    (ChangeStatus.SUBMITTED, "start_review"): _Transition(
        target=ChangeStatus.UNDER_REVIEW,
        allowed_roles=_MANAGER_AND_UP,
    ),
    # Approve / reject the change
    (ChangeStatus.UNDER_REVIEW, "approve"): _Transition(
        target=ChangeStatus.APPROVED,
        allowed_roles=_APPROVER_AND_UP,
    ),
    (ChangeStatus.UNDER_REVIEW, "reject"): _Transition(
        target=ChangeStatus.REJECTED,
        allowed_roles=_APPROVER_AND_UP,
    ),
    # Lock in an implementation window
    (ChangeStatus.APPROVED, "schedule"): _Transition(
        target=ChangeStatus.SCHEDULED,
        allowed_roles=_MANAGER_AND_UP,
        required_fields=("scheduled_start", "scheduled_end"),
        guard=_requires_scheduled_window,
    ),
    # Implementer starts work
    (ChangeStatus.SCHEDULED, "start_implementation"): _Transition(
        target=ChangeStatus.IN_PROGRESS,
        allowed_roles=_REQUESTER_AND_UP,
    ),
    # Implementation outcomes
    (ChangeStatus.IN_PROGRESS, "mark_implemented"): _Transition(
        target=ChangeStatus.IMPLEMENTED,
        allowed_roles=_REQUESTER_AND_UP,
    ),
    (ChangeStatus.IN_PROGRESS, "mark_failed"): _Transition(
        target=ChangeStatus.FAILED,
        allowed_roles=_REQUESTER_AND_UP,
    ),
    # After a failed change, the rollback was executed
    (ChangeStatus.FAILED, "rollback"): _Transition(
        target=ChangeStatus.ROLLED_BACK,
        allowed_roles=_REQUESTER_AND_UP,
    ),
    # PIR done, archive the record
    (ChangeStatus.IMPLEMENTED, "close"): _Transition(
        target=ChangeStatus.CLOSED,
        allowed_roles=_MANAGER_AND_UP,
    ),
    # Cancellation - allowed from any non-terminal state.
    # We define an entry per state explicitly for clarity (no wildcards).
    (ChangeStatus.DRAFT, "cancel"): _Transition(target=ChangeStatus.CANCELLED, allowed_roles=_ANY),
    (ChangeStatus.SUBMITTED, "cancel"): _Transition(
        target=ChangeStatus.CANCELLED, allowed_roles=_ANY
    ),
    (ChangeStatus.UNDER_REVIEW, "cancel"): _Transition(
        target=ChangeStatus.CANCELLED, allowed_roles=_MANAGER_AND_UP
    ),
    (ChangeStatus.APPROVED, "cancel"): _Transition(
        target=ChangeStatus.CANCELLED, allowed_roles=_MANAGER_AND_UP
    ),
    (ChangeStatus.SCHEDULED, "cancel"): _Transition(
        target=ChangeStatus.CANCELLED, allowed_roles=_MANAGER_AND_UP
    ),
}


def list_available_transitions(current_status: ChangeStatus, actor_role: Role) -> list[str]:
    """All transitions the actor can take from the current state.

    Used to populate UI buttons - the frontend asks 'what can I do with this
    change?' instead of hardcoding logic.
    """
    return [
        name
        for (status, name), t in _TRANSITIONS.items()
        if status == current_status and actor_role in t.allowed_roles
    ]


def transition(
    change_request: Any,
    transition_name: str,
    actor_role: Role,
    reason: str | None = None,
) -> TransitionEvent:
    """Apply a named transition to a change request.

    Returns a TransitionEvent on success. Raises on any failure. The caller
    is responsible for persisting the new state and the event.
    """
    current = ChangeStatus(change_request.status)
    key = (current, transition_name)

    if key not in _TRANSITIONS:
        raise InvalidTransitionError(f"Cannot {transition_name!r} from {current.value!r}")

    t = _TRANSITIONS[key]

    if actor_role not in t.allowed_roles:
        raise TransitionForbiddenError(
            f"Role {actor_role.value!r} cannot {transition_name!r} from " f"{current.value!r}"
        )

    for field_name in t.required_fields:
        if getattr(change_request, field_name) is None:
            raise TransitionGuardError(f"{field_name!r} must be set before {transition_name!r}")

    if t.guard is not None:
        guard_msg = t.guard(change_request)
        if guard_msg is not None:
            raise TransitionGuardError(guard_msg)

    # Apply the transition. We mutate the in-memory object only - the service
    # layer is responsible for committing.
    change_request.status = t.target.value

    return TransitionEvent(
        from_status=current,
        to_status=t.target,
        actor_role=actor_role,
        reason=reason,
    )
