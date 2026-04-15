# Incident Runbook

Last Updated: 2026-04-03

## Severity Guide

1. `SEV-1`: Production unavailable or data corruption risk.
2. `SEV-2`: Core flow degraded (jobs blocked, queue stuck).
3. `SEV-3`: Partial feature degradation with workaround.

## 1. Firecrawl Extraction Failures

Symptoms:
1. Jobs move to `failed`.
2. `extraction_error` indicates Firecrawl failure.
3. `external_api_failures_total` increases in `/api/v1/metrics`.

Immediate actions:
1. Confirm `FIRECRAWL_API_KEY` is valid.
2. Check Firecrawl status and API response patterns.
3. Keep user flow active via manual fallback endpoint:
   - `POST /api/v1/jobs/{job_id}/manual-markdown`

Recovery:
1. Fix API key/network issue.
2. Re-trigger extraction for affected jobs if needed.
3. Monitor failure metric trend for stabilization.

## 2. Queue Backlog / Worker Stuck

Symptoms:
1. `queue_depth_current` keeps increasing.
2. Jobs remain in `processing`.
3. Worker logs show repeated retries/errors.

Immediate actions:
1. Verify worker service is running.
2. Verify Redis connectivity (`REDIS_URL`).
3. Check worker logs for repeated exception class.
4. Scale worker instances if needed.

Recovery:
1. Restart worker service.
2. Clear invalid poison messages if identified.
3. Re-run extraction on affected jobs.
4. Confirm `queue_completed_total` resumes increasing.

## 3. Connector Outages

Symptoms:
1. Connector status endpoint returns non-healthy state.
2. OAuth-backed connectors show `expired` or `error`.

Immediate actions:
1. Identify affected connector names and users.
2. Move connector status to `pending_oauth` if re-auth is needed.
3. Notify impacted users to reconnect.

Recovery:
1. Complete re-auth and refresh connector refs.
2. Validate `GET /api/v1/connectors/{connector_name}/status`.
3. Confirm dependent flows recover.

## 4. Escalation Checklist

1. Record start time and impacted endpoints.
2. Capture request IDs from logs.
3. Capture metrics snapshot before and after mitigation.
4. File postmortem with root cause and preventive actions.

## 5. AI Provider Outage / Circuit Open

Symptoms:
1. Generation calls fail with `provider_unavailable`.
2. `/api/v1/metrics` shows spikes in:
   - `ai_provider_failures_total`
   - `ai_provider_circuit_open_total`
   - `ai_fallback_total`
3. `job_generation_runs.failure_code` shifts to provider errors.

Immediate actions:
1. Confirm provider credentials and connectivity (`OPENAI_API_KEY`, egress/network).
2. Validate primary provider status page and quota limits.
3. Verify fallback route is configured for affected artifact type.
4. Keep user communication explicit: temporary provider outage, retry is safe.

Recovery:
1. Wait for circuit cool-down (`AI_PROVIDER_CIRCUIT_OPEN_SECONDS`) or resolve provider issue.
2. Re-run failed generations from UI/API regenerate path.
3. Confirm recovery by checking:
   - new `job_generation_runs.status=success`
   - stabilization of provider failure metrics.

## 6. AI Budget Lockout / Guardrail Spike

Symptoms:
1. Generation fails with `budget_exceeded` or `policy_denied`.
2. `/api/v1/metrics` shows spikes in:
   - `ai_policy_denied_total`
   - `ai_guardrail_block_total`

Immediate actions:
1. Confirm policy env values:
   - `AI_MAX_INPUT_TOKENS_PER_RUN`
   - `AI_MAX_OUTPUT_TOKENS_PER_RUN`
   - `AI_DAILY_COST_LIMIT_USD`
2. Query failed runs and validate if blocking is expected.
3. If false positives are found, tune thresholds and redeploy.

Recovery:
1. Apply policy threshold adjustments through config rollout.
2. Retry blocked runs only after policy correction.
3. Capture before/after metrics and add postmortem notes.

## 7. AI Data Correction and Replay

Use when generation persisted partial output or failed after retries.

Steps:
1. Identify affected run IDs from `job_generation_runs`.
2. Verify latest `artifact_versions_json` for each artifact.
3. Re-run only failed artifact(s) using targeted regenerate endpoint.
4. Preserve history; do not delete previous versions.
5. If approved set is impacted, require re-approval before publish.
