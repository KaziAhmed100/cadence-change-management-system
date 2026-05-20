"""Alembic migration environment.

We use a programmatic config rather than the alembic.ini one so the DB URL
stays in sync with our Pydantic Settings.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Importing this module triggers registration of all models with Base.metadata
import app.models  # noqa: F401  (side-effect import)
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

config = context.config

# Programmatically override the URL with our application config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what Alembic's autogenerate compares against to detect changes
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection - emits SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the live DB."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Compare type metadata so column type changes are detected
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
