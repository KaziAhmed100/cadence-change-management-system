"""API v1 router aggregation.

Each endpoint module exports a router; this file mounts them under /api/v1.
Adding a new resource is a two-step change: create the router file, register
it here.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, users

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
