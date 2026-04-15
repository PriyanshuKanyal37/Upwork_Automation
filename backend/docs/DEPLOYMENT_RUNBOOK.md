# Deployment Runbook (Render + Neon)

Last Updated: 2026-04-03

## 1. Required Services

1. `backend-api` (Render Web Service)
2. `backend-worker` (Render Background Worker)
3. `backend-redis` (Render Key Value / Redis)
4. Neon Postgres project + branch (production branch)

## 2. Secrets and Config

Set all required keys from `.env.production.example` on both API and worker.

Critical values:
1. `DATABASE_URL` (Neon)
2. `AUTH_SECRET_KEY`
3. `REDIS_URL`
4. `QUEUE_DRIVER=dramatiq`
5. `FIRECRAWL_API_KEY`
6. `OPENAI_API_KEY`
7. `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`
8. AI hardening controls:
   - `AI_MAX_INPUT_TOKENS_PER_RUN`
   - `AI_MAX_OUTPUT_TOKENS_PER_RUN`
   - `AI_DAILY_COST_LIMIT_USD`
   - `AI_ENABLE_SAFETY_GUARDRAILS`
   - `AI_PROVIDER_FAILURE_THRESHOLD`
   - `AI_PROVIDER_CIRCUIT_OPEN_SECONDS`

## 3. Build and Start Commands

Use the same repository root with `backend/` working directory.

API service:
1. Build command: `uv sync --extra dev`
2. Start command: `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Worker service:
1. Build command: `uv sync --extra dev`
2. Start command: `uv run dramatiq app.workers.job_extraction_worker`

## 4. Migration Order (Mandatory)

1. Deploy code to API + worker without traffic switch.
2. Run DB migration:
   - `uv run alembic upgrade head`
3. Verify migration state:
   - `uv run alembic current`
4. Start/restart worker.
5. Enable/route production traffic to API.

Never run worker against an older schema after new migrations are required.

## 5. Post-Deploy Verification

1. `GET /health` returns `200`.
2. `GET /api/v1/health` returns `200`.
3. `GET /api/v1/metrics` returns metrics JSON.
4. Auth register/login flow works.
5. Job intake + manual markdown flow works.
6. Queue path works (if `QUEUE_DRIVER=dramatiq`).
7. AI generation smoke:
   - one `generate` call returns run id and success path
   - one targeted `regenerate` call appends a new artifact version
8. AI safety/governance smoke:
   - over-budget request returns policy block
   - provider outage returns typed `provider_unavailable`

## 6. Release Gate

Deploy only if:
1. CI workflow is green.
2. Migration check passed.
3. UAT sign-off exists for current release.
4. AI hardening checks passed:
   - runbooks updated
   - AI tests passing
   - metrics endpoint includes AI counters
