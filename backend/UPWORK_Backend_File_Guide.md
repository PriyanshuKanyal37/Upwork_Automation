# UPWORK Backend File Guide

Version: 1.0  
Last Updated: 2026-04-03  
Scope: Backend source files and what each file does.

Update policy:
1. This file is updated after every backend phase.
2. New files must be documented before phase sign-off.
3. If file responsibility changes, update purpose/features section.

---

## Phase Coverage

1. `B0` Foundation: completed
2. `B1` Auth: completed
3. `B2` DB + migrations: completed
4. `B3` User profile APIs: completed
5. `B4` Job intake + duplicate flow: completed
6. `B5` Firecrawl extraction + manual fallback: completed
7. `B6` Queue workers + retry-safe extraction orchestration: completed
8. `B7` Output persistence + targeted regenerate edit loop: completed
9. `B8` Connector management + status checks: completed
10. `B9` History + outcome/submission tracking APIs: completed
11. `B10` Reliability + observability + rate-limit policy: completed
12. `B11` Testing + CI/CD hardening: completed
13. `B12` Launch readiness + runbooks: completed

---

## Root Files

1. `pyproject.toml`
   - Purpose: Dependency and tool configuration.
   - Features: runtime deps, dev deps, pytest/ruff/mypy config.
2. `.env.example`
   - Purpose: environment variable template.
   - Features: DB, auth, rate limit, Firecrawl settings.
3. `.gitignore`
   - Purpose: local/runtime file ignore rules.
   - Features: venv/cache/db ignore.
4. `README.md`
   - Purpose: run and migration guide.
   - Features: uv workflow, endpoint list, migration commands.
5. `alembic.ini`
   - Purpose: Alembic configuration entrypoint.
   - Features: migration script location and DB URL source.
6. `scripts/check_migrations.py`
   - Purpose: migration reproducibility check utility.
   - Features: upgrade/downgrade/upgrade cycle on clean DB.
7. `../.github/workflows/backend-ci.yml`
   - Purpose: CI pipeline for backend validation.
   - Features: lint + type-check + migration check + tests.
8. `scripts/run_uat.py`
   - Purpose: executable end-to-end UAT flow.
   - Features: local E2E checks and markdown sign-off report generation.
9. `docs/DEPLOYMENT_RUNBOOK.md`
   - Purpose: production deployment order/run instructions.
10. `docs/PRODUCTION_SECRET_CHECKLIST.md`
   - Purpose: production secret/config readiness checklist.
11. `docs/INCIDENT_RUNBOOK.md`
   - Purpose: incident handling steps for core failure classes.
12. `docs/BACKUP_ROLLBACK_RUNBOOK.md`
   - Purpose: backup and rollback procedures.
13. `docs/UAT_SIGNOFF_2026-04-03.md`
   - Purpose: captured UAT sign-off artifact for current release.

---

## API Bootstrap

1. `app/main.py`
   - Purpose: FastAPI app initialization.
   - Features: middleware, exception handlers, API router, `/health`.
2. `app/interfaces/api/router.py`
   - Purpose: root API router registration.
   - Features: mounts health, auth, profile, jobs routers under `/api/v1`.

---

## Config and Infra

1. `app/infrastructure/config/settings.py`
   - Purpose: typed settings object.
   - Features: env-based config, DB URL async normalization, auth/firecrawl controls.
2. `app/infrastructure/http/request_context.py`
   - Purpose: per-request context storage.
   - Features: request-id bind/get/reset helpers.
3. `app/infrastructure/http/middleware.py`
   - Purpose: request middleware.
   - Features: request-id propagation, latency logging.
4. `app/infrastructure/logging/setup.py`
   - Purpose: structured logging setup.
   - Features: JSON logs, request-id enrichment.
5. `app/infrastructure/errors/exceptions.py`
   - Purpose: typed app exception definition.
   - Features: status code, code, message, details.
6. `app/infrastructure/errors/handlers.py`
   - Purpose: global exception handlers.
   - Features: standardized error payloads for app/validation/unhandled errors.
7. `app/infrastructure/security/passwords.py`
   - Purpose: password hashing/verification.
   - Features: `pwdlib` argon2 hashing.
8. `app/infrastructure/security/tokens.py`
   - Purpose: session token encode/decode.
   - Features: JWT session token creation and validation.
9. `app/infrastructure/security/login_rate_limiter.py`
   - Purpose: login brute-force protection.
   - Features: in-memory attempt window, reset/clear support.
10. `app/infrastructure/integrations/firecrawl_client.py`
   - Purpose: Firecrawl extraction client.
   - Features: API-key gated calls, timeout/backoff retry, markdown extraction, typed errors, retryable/non-retryable classification.
11. `app/infrastructure/queue/broker.py`
   - Purpose: Dramatiq broker bootstrap.
   - Features: queue-driver toggle and Redis broker wiring.
12. `app/infrastructure/queue/contracts.py`
   - Purpose: queue task envelope for job extraction.
   - Features: user/job IDs, idempotency key, payload serialization.
13. `app/infrastructure/queue/dispatch.py`
   - Purpose: queue dispatch adapter.
   - Features: task creation and enqueue decision by queue driver.
14. `app/infrastructure/queue/locks.py`
   - Purpose: distributed lock helpers.
   - Features: per-job lock acquire/release with Redis token guard.
15. `app/infrastructure/http/global_rate_limiter.py`
   - Purpose: global request rate limiter.
   - Features: high-limit in-memory per-path/client limiter with retry-after.
16. `app/infrastructure/http/idempotency.py`
   - Purpose: idempotency replay store.
   - Features: in-memory idempotency cache with TTL and bounded capacity.
17. `app/infrastructure/observability/metrics.py`
   - Purpose: runtime metrics aggregation.
   - Features: HTTP, worker, external API, and queue depth metrics snapshot/reset.
18. `app/infrastructure/audit/events.py`
   - Purpose: standardized audit event logger.
   - Features: status transition audit logging helper.

---

## Database

1. `app/infrastructure/database/base.py`
   - Purpose: SQLAlchemy declarative base.
2. `app/infrastructure/database/session.py`
   - Purpose: async engine/session setup.
   - Features: async session dependency for routes/services.
3. `app/infrastructure/database/models/user.py`
   - Purpose: `users` table model.
   - Features: login identity and password hash.
4. `app/infrastructure/database/models/user_profile.py`
   - Purpose: `user_profiles` model.
   - Features: profile context, templates, custom prompt blocks.
5. `app/infrastructure/database/models/job.py`
   - Purpose: `jobs` model.
   - Features: intake URL, dedupe fields, status lifecycle.
6. `app/infrastructure/database/models/job_output.py`
   - Purpose: `job_outputs` model.
   - Features: generated artifacts and edit logs.
7. `app/infrastructure/database/models/user_connector.py`
   - Purpose: `user_connectors` model.
   - Features: connector ref storage and uniqueness.
8. `app/infrastructure/database/models/job_generation_run.py`
   - Purpose: `job_generation_runs` model.
   - Features: per-run AI generation metadata (provider/model/tokens/cost/latency/retries/failure).
9. `app/infrastructure/database/models/__init__.py`
   - Purpose: model exports for metadata discovery.

---

## Application Services

1. `app/application/auth/service.py`
   - Purpose: auth use-cases.
   - Features: register/login, credential checks, user serialization.
2. `app/application/profile/service.py`
   - Purpose: profile use-cases.
   - Features: create/get/update profile, payload sanitization.
3. `app/application/job/service.py`
   - Purpose: job intake and lifecycle use-cases.
   - Features:
     - URL canonicalization
     - Upwork job-id extraction
     - duplicate detection
     - duplicate decision update
     - extraction status helpers (`processing`, `ready`, `failed`)
     - retry-aware extraction execution for worker mode
     - manual markdown save
4. `app/application/output/service.py`
   - Purpose: output persistence and edit-loop use-cases.
   - Features:
     - get output by job
     - upsert output fields
     - target-only regenerate update
     - append edit log entries on save/regenerate
5. `app/application/connector/service.py`
   - Purpose: connector use-cases.
   - Features:
     - connector allowlist validation (airtable, firecrawl, google_docs, n8n)
     - secure credential-ref validation (reference schemes only)
     - connector CRUD
     - connector status health summary
6. `app/application/job/history_service.py`
   - Purpose: history and lifecycle update use-cases.
   - Features:
     - list jobs with filters
     - job detail with optional output payload
     - status/outcome update
     - submission-flag update (`is_submitted_to_upwork`, `submitted_at`)

---

## API Routers and Dependencies

1. `app/interfaces/api/dependencies/auth.py`
   - Purpose: authenticated user dependency.
   - Features: session-cookie validation and user fetch.
2. `app/interfaces/api/v1/health.py`
   - Purpose: health endpoints.
3. `app/interfaces/api/v1/auth.py`
   - Purpose: auth endpoints.
   - Features: register/login/logout/me and session cookie setting.
4. `app/interfaces/api/v1/profile.py`
   - Purpose: user profile endpoints.
   - Features: create/get/patch with validation.
5. `app/interfaces/api/v1/jobs.py`
   - Purpose: job intake and extraction endpoints.
   - Features:
     - intake (`/jobs/intake`)
     - duplicate decision
     - extraction trigger (`/extract`)
     - queued extraction response when Dramatiq enabled
     - manual fallback markdown (`/manual-markdown`)
6. `app/interfaces/api/v1/outputs.py`
   - Purpose: output endpoints.
   - Features:
     - get job output
     - patch/upsert output fields (doc/workflow/loom/proposal)
     - regenerate one selected output only
     - workflow payload validation
7. `app/interfaces/api/v1/connectors.py`
   - Purpose: connector APIs.
   - Features:
     - create/list/get/update/delete connector
     - connector health/status endpoint
     - auth-protected per-user connector isolation
8. `app/interfaces/api/v1/jobs.py`
   - Added B9 features:
     - `GET /jobs` (history list with filters)
     - `GET /jobs/{job_id}` (job detail + output)
     - `PATCH /jobs/{job_id}/status-outcome`
     - `PATCH /jobs/{job_id}/submission`
     - B10 compatible with idempotency middleware for write actions
9. `app/interfaces/api/v1/health.py`
   - Added B10 feature:
     - `GET /metrics` observability snapshot endpoint

---

## Workers

1. `app/workers/job_extraction_worker.py`
   - Purpose: background orchestration for extraction.
   - Features: task envelope consumption, retry-safe execution, final failure persistence, duplicate-concurrency lock.

---

## Migrations

1. `alembic/env.py`
   - Purpose: Alembic runtime environment.
   - Features: async migration execution, metadata loading.
2. `alembic/script.py.mako`
   - Purpose: migration template.
3. `alembic/versions/20260402_0001_initial_mvp_schema.py`
   - Purpose: initial schema migration.
   - Features: all 5 MVP tables + indexes/constraints.
4. `alembic/versions/20260402_0002_job_extraction_fields.py`
   - Purpose: extraction failure tracking.
   - Features: `jobs.extraction_error`, `jobs.requires_manual_markdown`.
5. `alembic/versions/20260403_0003_ai_layer_tracking_tables.py`
   - Purpose: AI layer tracking persistence (legacy expanded schema).
   - Features:
     - initially introduced multiple AI tracking tables.
6. `alembic/versions/20260403_0004_consolidate_ai_tracking_tables.py`
   - Purpose: minimal AI schema consolidation.
   - Features:
     - keeps `job_generation_runs` as core AI telemetry table.
     - adds `job_outputs.artifact_versions_json`.
     - adds `job_outputs.approval_snapshot_json`.
     - adds `job_outputs.ai_usage_summary_json`.
     - migrates legacy data into `job_outputs` JSON fields.
     - drops over-normalized tables from `0003`.

---

## Tests

1. `tests/conftest.py`
   - Purpose: test fixtures.
   - Features: test DB env setup, alembic migration bootstrap, auth limiter reset, test client fixture.
2. `tests/test_health.py`
   - Purpose: health route tests.
3. `tests/test_auth.py`
   - Purpose: auth flow tests.
   - Features: register/login/logout/me + rate-limit.
4. `tests/test_profile.py`
   - Purpose: profile API tests.
   - Features: create/get/update, conflict, auth, validation.
5. `tests/test_jobs.py`
   - Purpose: jobs API tests.
   - Features: intake, duplicate flow, extraction success/failure, manual fallback, queued extraction response.
6. `tests/test_queue_contracts.py`
   - Purpose: queue contract tests.
   - Features: task payload roundtrip validation.
7. `tests/test_outputs.py`
   - Purpose: output API tests.
   - Features: create/get/update output, target-only regenerate, workflow validation, auth checks.
8. `tests/test_connectors.py`
   - Purpose: connector API tests.
   - Features: connector CRUD flow, allowlist validation, secure credential-ref enforcement, uniqueness/auth checks.
9. `tests/test_history.py`
   - Purpose: history and lifecycle API tests.
   - Features: list filters, detail with output payload, status/outcome validation, submission validation, auth checks.
10. `tests/test_reliability.py`
   - Purpose: reliability and observability tests.
   - Features: idempotency replay, global limiter enforcement, metrics endpoint shape.
11. `tests/test_worker.py`
   - Purpose: worker integration-style behavior tests.
   - Features: worker success/failure paths, queue metric updates, retry failure behavior.
12. `tests/test_performance_smoke.py`
   - Purpose: minimal performance smoke test.
   - Features: intake->extract->outputs flow within baseline timing threshold.
