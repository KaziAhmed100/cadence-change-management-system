# Cadence — infra

## Local development

Postgres and Redis run via Docker Compose. From the repository root:

```bash
docker compose up -d           # start
docker compose ps              # check
docker compose down            # stop (data persists)
docker compose down -v         # stop + wipe data
```

The backend and frontend run on the host (not in containers) during development. This is deliberate — it keeps hot reload, debuggers, and editor integrations working without volume gymnastics.

## Production deployment

Documented in detail in Phase 10. Short version:

- **Frontend** → Vercel (auto-deploys from `main`)
- **Backend** → Railway (Dockerfile-based service)
- **Postgres + Redis** → Railway managed services
- **Background worker (RQ)** → Railway service, same image as backend, different start command
