-- ----------------------------------------------------------------------------
-- Cadence — Postgres initialization
-- ----------------------------------------------------------------------------
-- This script runs once, the first time the Postgres container starts with a
-- fresh data volume. The database, user, and password are created by the
-- official postgres image based on the POSTGRES_* env vars; everything below
-- runs *after* that.
--
-- For now we only enable a couple of useful extensions. Schema lives in
-- Alembic migrations (added in Phase 2) so we can version it properly.

-- gen_random_uuid() for primary keys without app-side UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Case-insensitive text for email columns (saves a LOWER() everywhere)
CREATE EXTENSION IF NOT EXISTS "citext";
