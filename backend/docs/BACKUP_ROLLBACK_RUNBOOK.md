# Backup and Rollback Runbook

Last Updated: 2026-04-03

## 1. Backup Strategy

Primary DB is Neon Postgres.

Before each production release:
1. Create or verify a Neon restore point.
2. Export latest schema and migration version.
3. Confirm rollback owner and decision authority.

## 2. Pre-Release Safety Checklist

1. CI green for release commit.
2. `uv run alembic current` matches expected head.
3. Migration SQL reviewed for destructive operations.
4. Restore plan validated for the current branch.
5. AI hardening policy values reviewed and approved:
   - token caps
   - daily cost cap
   - provider circuit breaker thresholds

## 3. Rollback Decision Rules

Trigger rollback when:
1. `SEV-1` outage persists after first mitigation attempt.
2. Data integrity risk is confirmed.
3. New release introduces non-recoverable regression.

## 4. Rollback Procedure

Application rollback:
1. Re-deploy previous stable backend commit.
2. Restart API and worker services.

Database rollback:
1. If safe and migration supports reversal:
   - `uv run alembic downgrade -1` (or target revision).
2. If unsafe or data mismatch risk:
   - perform Neon point-in-time restore.
3. Switch application `DATABASE_URL` to restored branch/database if required.

AI-specific rollback:
1. If failure is config-only, roll back env values first (no DB rollback required).
2. If failure is provider-level, keep latest deploy and route traffic through fallback provider.
3. If generation quality regression is severe, roll back to previous stable backend commit and rerun approval for affected jobs.

## 5. Post-Rollback Validation

1. Health endpoints return 200.
2. Auth + job intake + output APIs pass smoke checks.
3. Worker processes queued tasks without failures spike.
4. Metrics trend normalizes (`5xx`, queue depth, external failures).
5. AI metrics trend normalizes (`ai_generation_failures_total`, `ai_provider_failures_total`).
6. Regenerate endpoint produces valid artifact versions and no schema errors.

## 6. Communication Template

1. Incident start time.
2. Affected functionality.
3. Rollback action taken.
4. Current system status.
5. ETA for corrective forward fix.
