"""Health check endpoint.

Two reasons this exists:
1. Deployment platforms (Railway, K8s) need a readiness probe
2. It's the canonical "is the backend reachable" check during local dev
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
def liveness() -> dict[str, str]:
    """Returns 200 if the API process is running. Does not touch the DB."""
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness check (includes DB)")
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    """Returns 200 only if the DB connection is also healthy.

    Use this for orchestrator readiness probes - it's the right signal for
    "should we send traffic here yet?".
    """
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
