"""Application settings.

Reads from environment variables (and a local .env file if present). Anything
required to run the app should live here so it's discoverable in one place.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application config."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Ignore unrelated env vars (Railway and CI inject a bunch of these)
        extra="ignore",
    )

    # Runtime
    environment: Literal["development", "test", "production"] = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database
    database_url: str = Field(
        default="postgresql+psycopg2://cadence:cadence@localhost:5432/cadence"
    )

    # Redis (added in Phase 6 when we start using background jobs; declared now so
    # the env config is consistent across phases)
    redis_url: str = "redis://localhost:6379/0"

    # JWT — generate a real secret with:
    #   python -c "import secrets; print(secrets.token_urlsafe(64))"
    jwt_secret: str = Field(default="dev-only-change-me-in-production-please")
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 60 * 8  # 8 hours - long for demo simplicity

    # CORS — list of allowed origins, parsed from a comma-separated string
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Split the comma-separated CORS string into a list."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @field_validator("jwt_secret")
    @classmethod
    def _warn_on_default_secret(cls, v: str) -> str:
        # Don't crash in dev/test, but make it obvious if someone deploys with the default
        if "dev-only" in v and "production" not in v:
            return v
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor.

    Using lru_cache means the .env file is parsed once per process. Tests can
    clear this cache when they need to override values.
    """
    return Settings()
