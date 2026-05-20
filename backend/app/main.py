"""FastAPI application entry point.

Run locally with:  uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Application factory.

    Wrapping the FastAPI() construction in a function makes it trivial to
    spin up a fresh app per test, and keeps the import side-effects small.
    """
    settings = get_settings()

    app = FastAPI(
        title="Cadence API",
        description="Change management system — REST API",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": "cadence-api",
            "version": app.version,
            "docs": "/docs",
        }

    logger.info("Cadence API initialized (env=%s)", settings.environment)
    return app


app = create_app()
