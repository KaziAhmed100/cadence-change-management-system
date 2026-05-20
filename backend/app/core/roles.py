"""Role enum.

The MVP uses coarse role-based access control. Every protected endpoint checks
a user's role against an allowed set. If we ever move to permission-based
checks (Phase 3+ if needed), we'd add a Permission table and a role->permission
mapping; the endpoint dependencies would change but everything else holds.
"""

from enum import Enum


class Role(str, Enum):
    """User roles for the change management process.

    String values are what get stored in the database and returned in JWT
    claims. Don't rename them carelessly - that's a migration.
    """

    ADMIN = "admin"
    CHANGE_MANAGER = "change_manager"
    APPROVER = "approver"
    REQUESTER = "requester"

    @classmethod
    def all(cls) -> list["Role"]:
        return list(cls)
