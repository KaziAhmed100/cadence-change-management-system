"""User management endpoints (admin-only)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.roles import Role
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.services.user_service import UserAlreadyExistsError, create_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=list[UserRead],
    summary="List all users (admin only)",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def list_users(db: Session = Depends(get_db)) -> list[User]:
    """Return all users in the system. Admin only."""
    stmt = select(User).order_by(User.created_at.desc())
    return list(db.execute(stmt).scalars().all())


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (admin only)",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def create_user_endpoint(
    payload: UserCreate,
    db: Session = Depends(get_db),
) -> User:
    """Create a new user with the specified role. Admin only."""
    try:
        user = create_user(db, payload)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    db.commit()
    db.refresh(user)
    return user
