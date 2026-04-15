# AgentLoopr Backend

Production-oriented FastAPI backend foundation for AgentLoopr.

## Tech

1. FastAPI
2. SQLAlchemy + Alembic
3. Redis + Dramatiq

## Run Locally

1. Create local venv with `uv` inside `backend/.venv`.
2. Install dependencies into local venv only.
3. Configure `.env` with Neon connection details.
4. Run migrations.
5. Start the API.

```bash
uv venv .venv
.venv\Scripts\activate
uv pip install --python .venv\Scripts\python.exe -e .[dev]
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Run worker (only when `QUEUE_DRIVER=dramatiq`):

```bash
uv run dramatiq app.workers.job_extraction_worker
```

## Migration Commands

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic current
uv run alembic history
```

## Endpoints

1. `GET /health`
2. `GET /api/v1/health`
3. `POST /api/v1/auth/register`
4. `POST /api/v1/auth/login`
5. `POST /api/v1/auth/logout`
6. `GET /api/v1/auth/me`
7. `POST /api/v1/profile`
8. `GET /api/v1/profile`
9. `PATCH /api/v1/profile`
10. `POST /api/v1/jobs/intake`
11. `POST /api/v1/jobs/{job_id}/duplicate-decision`
12. `POST /api/v1/jobs/{job_id}/extract`
13. `POST /api/v1/jobs/{job_id}/manual-markdown`
14. `GET /api/v1/jobs`
15. `GET /api/v1/jobs/{job_id}`
16. `PATCH /api/v1/jobs/{job_id}/status-outcome`
17. `PATCH /api/v1/jobs/{job_id}/submission`
18. `GET /api/v1/jobs/{job_id}/outputs`
19. `PATCH /api/v1/jobs/{job_id}/outputs`
20. `POST /api/v1/jobs/{job_id}/outputs/regenerate`
21. `POST /api/v1/connectors`
22. `GET /api/v1/connectors`
23. `GET /api/v1/connectors/{connector_name}`
24. `PATCH /api/v1/connectors/{connector_name}`
25. `DELETE /api/v1/connectors/{connector_name}`
26. `GET /api/v1/connectors/{connector_name}/status`
27. `GET /api/v1/metrics`

## Environment Variables

Use plain variable names from `.env.example` (no prefix).  
Copy `.env.example` to `.env` and update values as needed.

Database URL note:
1. Use Neon URL in `.env` as `DATABASE_URL`.
2. If you paste `postgresql://...` or `postgres://...`, backend auto-converts to `postgresql+asyncpg://...`.
3. If URL includes `sslmode=require`, backend auto-converts to asyncpg-compatible `ssl=require`.
4. If URL includes `channel_binding=...` (common in some Neon snippets), backend removes it because asyncpg does not accept that parameter.

Session behavior:
1. Successful login/register sets an HTTP-only session cookie.
2. Session default duration is 35 days (`AUTH_SESSION_DAYS`).

Reliability behavior:
1. Global request timeout and global high-limit rate limiting are enabled.
2. Login keeps stricter anti-bruteforce limits.
3. Idempotency replay is enabled for write routes using `Idempotency-Key` header.

## CI/CD

CI means every push/PR is automatically validated before merge/deploy.
CD means code that passes CI is always in deploy-ready state.

Implemented workflow:
1. GitHub Actions workflow: `.github/workflows/backend-ci.yml`
2. Runs on push/PR for backend changes.
3. Executes:
   - `uv run ruff check .`
   - `uv run mypy app tests`
   - `uv run python scripts/check_migrations.py`
   - `uv run pytest`

Migration validation script:
1. `scripts/check_migrations.py`
2. Runs `upgrade -> downgrade base -> upgrade` on clean SQLite DB.
3. Ensures migrations are reproducible and rollback-safe.

Run the same checks locally:

```bash
uv sync --extra dev
uv run ruff check .
uv run mypy app tests
uv run python scripts/check_migrations.py
uv run pytest
```

## Launch Readiness Docs

1. Deployment order and runtime setup:
   - `docs/DEPLOYMENT_RUNBOOK.md`
2. Production secrets checklist:
   - `docs/PRODUCTION_SECRET_CHECKLIST.md`
3. Incident handling:
   - `docs/INCIDENT_RUNBOOK.md`
4. Backup and rollback:
   - `docs/BACKUP_ROLLBACK_RUNBOOK.md`
5. UAT execution and sign-off:
   - `scripts/run_uat.py`
   - latest report in `docs/UAT_SIGNOFF_YYYY-MM-DD.md`

## Project Structure

```text
backend/
  app/
    application/
    domain/
    infrastructure/
      config/
      errors/
      http/
      logging/
    interfaces/
      api/
        v1/
    workers/
  tests/
```
