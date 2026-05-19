# Local development setup

Cadence needs two services running locally for development: **PostgreSQL 16** and **Redis 7**. There are two supported paths to get them. Both end in the same place — the backend connects to `localhost:5432` for Postgres and `localhost:6379` for Redis. Pick whichever fits your environment.

## Option A — Docker Compose (recommended for personal machines)

The repository ships a `docker-compose.yml` that brings up both services with healthchecks, the right extensions pre-loaded, and persistent volumes. From the repository root:

```bash
docker compose up -d           # start both services
docker compose ps              # verify both report (healthy)
docker compose down            # stop services (data persists)
docker compose down -v         # stop and wipe data
```

This is the simplest path if your machine has Docker Desktop installed and unrestricted access to Docker Hub.

## Option B — Native install (for machines where Docker is unavailable)

Some corporate / managed devices run TLS-inspecting endpoint security agents (CrowdStrike Falcon, Netskope, Zscaler, GlobalProtect HIP) that interfere with Docker image pulls from Docker Hub's CDN, surfacing as `local error: tls: bad record MAC` during `docker compose up`. When that happens, install Postgres and Redis natively as Windows services. The connection strings are identical, so nothing in the application changes.

### PostgreSQL 16 (Windows)

1. Download the installer from <https://www.postgresql.org/download/windows/>
2. Run with these choices: superuser password `postgres`, port `5432`, default locale, skip Stack Builder
3. Create the application database and user:

   ```powershell
   $env:Path += ";C:\Program Files\PostgreSQL\16\bin"
   psql -U postgres
   ```

   Then in the psql prompt:

   ```sql
   CREATE USER cadence WITH PASSWORD 'cadence';
   CREATE DATABASE cadence OWNER cadence;
   \c cadence
   CREATE EXTENSION IF NOT EXISTS "pgcrypto";
   CREATE EXTENSION IF NOT EXISTS "citext";
   GRANT ALL PRIVILEGES ON DATABASE cadence TO cadence;
   \q
   ```

4. Verify:

   ```powershell
   psql -U cadence -d cadence -c "\dx"
   ```

   Expected output: `pgcrypto`, `citext`, `plpgsql`.

### Redis (Windows via Memurai)

Redis Labs doesn't ship an official Windows build. Memurai is a Redis-compatible server for Windows endorsed by the Redis team for development use.

1. Download from <https://www.memurai.com/get-memurai> — Developer Edition
2. Install with defaults; it registers as a Windows service on port `6379`
3. Verify:

   ```powershell
   & "C:\Program Files\Memurai\memurai-cli.exe" ping
   ```

   Should print `PONG`.

## After either option

Confirm both services accept connections:

```powershell
Test-NetConnection localhost -Port 5432
Test-NetConnection localhost -Port 6379
```

Both should report `TcpTestSucceeded : True`. You're now ready to run the backend (Phase 2) and frontend (Phase 8).
