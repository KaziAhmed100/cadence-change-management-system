<div align="center">

# Cadence

### A modern IT change management system, built for the way real teams work.

[![CI](https://img.shields.io/badge/CI-pending-lightgrey)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)

</div>

---

> **Status:** In active development. See the [project board](#) for current progress.

## What is this?

Cadence is a self-hosted change management system designed for IT departments that want the structure of enterprise ITSM tools (ServiceNow, Jira Service Management) without the cost, complexity, or sprawl.

It models the full change lifecycle — request, risk-scored routing, conditional approvals, scheduled implementation, rollback planning, and post-implementation review — and gives change managers the calendar, audit trail, and reporting they actually need to run a weekly CAB.

## Why does this exist?

Most universities and mid-sized IT organizations either run their change process out of spreadsheets and email threads, or pay enterprise pricing for software they barely use 20% of. Cadence is the middle ground: ITIL-aligned where it counts, opinionated where vendors overcomplicate, and pleasant to use.

## Architecture

```
┌──────────────────┐      ┌───────────────────┐      ┌──────────────┐
│  Next.js 14      │─────▶│  FastAPI Backend  │─────▶│  PostgreSQL  │
│  (Vercel)        │◀─────│  (Railway)        │◀─────│  (Railway)   │
└──────────────────┘      └───────────────────┘      └──────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  Redis + RQ     │
                          │  (background    │
                          │   jobs, SLAs)   │
                          └─────────────────┘
```

## Tech stack

**Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, React Hook Form + Zod, TanStack Query, FullCalendar, Recharts, NextAuth.js

**Backend:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, python-jose (JWT), Redis + RQ (background jobs)

**Database:** PostgreSQL 16

**Infra:** Docker Compose (local), GitHub Actions (CI), Vercel (frontend), Railway (backend + Postgres + Redis)

For the *why* behind these choices, see [`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md).

## Planned features

- [ ] Risk-scored change requests with impact analysis
- [ ] Conditional approval routing (parallel, sequential, quorum)
- [ ] Change calendar with conflict detection and blackout windows
- [ ] CAB agenda builder and decision recording
- [ ] Implementation sub-tasks and progress tracking
- [ ] Rollback planning and execution workflow
- [ ] Post-implementation review (PIR)
- [ ] Append-only audit trail for every state transition
- [ ] Dashboards: change success rate, lead time, SLA compliance

A more complete feature breakdown will land in the final README at the end of Phase 10.

## Repository layout

```
cadence-change-management-system/
├── backend/         # FastAPI service
├── frontend/        # Next.js 14 application
├── infra/           # Docker Compose, Postgres init, deployment configs
├── docs/            # Architecture notes, design decisions
├── scripts/         # One-off scripts (seeding, migrations, etc.)
└── .github/         # CI workflows, issue/PR templates
```

## Getting started

Cadence needs Postgres 16 and Redis 7 for local development. The repo supports two setup paths:

- **Docker Compose** (recommended for personal machines) — `docker compose up -d` from the repo root
- **Native install** (for managed devices where Docker is restricted) — see [`docs/LOCAL_DEV_SETUP.md`](docs/LOCAL_DEV_SETUP.md)

Backend and frontend setup instructions land in Phase 2 and Phase 8 respectively.

## License

[MIT](LICENSE) © 2026 Kazi Niaz Ahmed
