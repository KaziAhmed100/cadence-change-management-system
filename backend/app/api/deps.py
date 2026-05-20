"""Reusable FastAPI dependencies.

`get_current_user` extracts a User from the Authorization header. `require_role`
is a dependency *factory* that takes a set of allowed roles and returns a
dependency that enforces them. This way every endpoint that needs RBAC is a
one-liner.

Future-proofing note: if we move to permission-based checks later, we add
`require_permission(perm)` here without changing the endpoints that already
use `require_role`.
"""

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.user_service import get_user_by_id

# tokenUrl is a hint for Swagger UI's "Authorize" button - the spec form
# generated there will POST to this URL. Our login endpoint accepts JSON, but
# we expose a swagger-compatible OAuth2 form endpoint at the same URL.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/oauth")

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the User identified by the request's JWT, or 401."""
    try:
        payload = decode_token(token)
        subject = payload.get("sub")
        if not subject:
            raise _CREDENTIALS_EXCEPTION
        user_id = uuid.UUID(subject)
    except (JWTError, ValueError) as exc:
        raise _CREDENTIALS_EXCEPTION from exc

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION
    return user


def require_role(*allowed_roles: Role) -> Callable[..., User]:
    """Build a dependency that enforces the caller's role is in `allowed_roles`.

    Usage in an endpoint:

        @router.post("/users", dependencies=[Depends(require_role(Role.ADMIN))])
        def create_user(...): ...
    """
    allowed_values = {r.value for r in allowed_roles}

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return _checker
