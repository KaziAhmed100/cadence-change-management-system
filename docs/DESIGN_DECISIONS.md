# Design Decisions

This document captures the *why* behind significant technical choices. Each entry is dated so future-me (and reviewers) can see the reasoning at the point the decision was made.

Format: a short rationale, alternatives considered, and the trade-off being accepted.

---

## 2026-05 — Monorepo over polyrepo

Backend and frontend live in one repository. The project is small enough that a polyrepo split adds coordination overhead without clear benefit. A monorepo also makes it trivial to land cross-cutting changes (e.g. a new API endpoint and the UI that consumes it) in a single PR.

**Considered:** separate `cadence-backend` and `cadence-frontend` repos.
**Trade-off:** CI runs on both halves even when only one changed. Mitigated with path-based workflow triggers.

---

## 2026-05 — FastAPI over Django / Express

FastAPI was chosen for the backend over Django and over Node/Express:

- **vs. Django:** Django's ORM and admin are great but the whole batteries-included surface is more than this project needs. FastAPI gives us Pydantic validation, async support, and OpenAPI docs out of the box with a smaller footprint.
- **vs. Express:** Sticking with one language across the backend lets us use Pydantic for schemas, SQLAlchemy for the ORM, and pytest for testing — all mature, opinionated, and well-documented. The Python ecosystem is also closer to what an enterprise ITSM team would use.

**Trade-off:** Python is slower than Node for raw throughput. Not a constraint at portfolio-demo scale.

---

## 2026-05 — RQ over Celery for background jobs

Change management needs background work — sending notifications, escalating stale approvals, running SLA checks, generating reports. We need a job queue.

RQ (Redis Queue) was chosen over Celery because:

- It is **dramatically simpler to operate** — one Redis broker, no separate result backend, no broker/backend split, no celery beat config.
- Our jobs are simple: enqueue, run, retry on failure. We don't need Celery's routing, priorities, or workflow features.
- Less moving parts means less to break in the deployed demo.

**Trade-off:** RQ doesn't have first-class scheduled-task support like Celery Beat. We'll use `rq-scheduler` for periodic SLA-check jobs.

---

## 2026-05 — PostgreSQL over MySQL / MongoDB

Postgres is the right call for this domain:

- Strong relational integrity matters — a change request without an approver, or an approval without a change, is a bug. Foreign keys and constraints catch these at the database layer.
- JSONB columns give us flexibility where we need it (e.g. the approval rule DSL, audit log diffs) without sacrificing relational guarantees elsewhere.
- Excellent support for time-window queries, which we'll lean on for calendar conflict detection.
- The Postgres tooling story on Railway and locally via Docker is excellent.

**Considered:** MongoDB. Rejected — the domain is intrinsically relational. Forcing it into documents would create the same join logic in the application layer, just worse.

---

## 2026-05 — JWT auth with email + password (no OAuth in MVP)

We're going with stateless JWT auth over session cookies, and with email/password over OAuth.

**Why JWT:** Stateless tokens are simpler to operate across two deployed services (Vercel frontend, Railway backend) without sticky sessions or shared Redis sessions. Refresh tokens are stored server-side for revocation.

**Why email/password over OAuth for the MVP:** A demo CMS should let a hiring manager log in with seeded credentials in two seconds. OAuth adds friction (set up a GitHub app, configure redirects on both deployed instances) for no demo benefit. OAuth can be added later as an additional path.

**Trade-off:** Have to implement password hashing, validation, and rate limiting ourselves. All well-understood problems, and good signal for the portfolio.

---

## 2026-05 — Hand-rolled state machine over a library

The Change Request lifecycle is a state machine. Tempting libraries: `python-statemachine`, `transitions`.

We'll hand-roll it instead. Reasons:

- The state machine is small (≈8 states, ≈12 transitions). A library is overkill.
- A hand-rolled implementation is easier to read for a reviewer in the portfolio context — no need to learn library DSL.
- We get to enforce transition guards (e.g. "cannot move to `Approved` without all required approvers"), generate the audit log entry, and fire notifications all in one place. Libraries make this awkward.

**Trade-off:** Have to write our own tests for transition correctness. Already planned.

---

## (More to come as we build)
