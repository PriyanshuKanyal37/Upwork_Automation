# Backend Remaining Scope (Post B12)

Last Updated: 2026-04-03  
Status: Core backend platform is complete, but AI product behavior is not complete yet.

---

## 1. Reality Check

Current backend is production-grade in structure, reliability, CI/CD, and operations.
But it is still missing the core AI orchestration layer that turns extracted job data into generated artifacts automatically.

So yes: this is currently a strong platform backend, not yet the full product backend.

---

## 2. What Is Already Done

1. Auth/session, profile, job intake, duplicate flow.
2. Firecrawl extraction + manual fallback.
3. Outputs storage/edit endpoints.
4. Connectors registry (ref-based), status APIs.
5. Job history/outcome/submission APIs.
6. Queue worker (Dramatiq + Redis), retry/locking.
7. Reliability middleware, metrics, audit events.
8. CI/CD, migration checks, runbooks, UAT script.

---

## 3. What Is Still Missing (Critical)

## A. AI Orchestration Core (Highest Priority)

1. LLM provider integration layer (OpenAI first).
2. Prompt orchestration service using:
   - user profile templates
   - job markdown
   - custom prompt blocks
   - connector context (when needed)
3. Automatic generation pipeline for:
   - proposal text
   - loom script
   - workflow JSONs
   - doc markdown
4. Regeneration pipeline driven by edit instructions (LLM-based rewrite).
5. Deterministic output schema validation (especially for workflow JSON artifacts).

## B. Data Model Extensions for AI Runs

1. Add generation run tracking table:
   - `job_generation_runs`
2. Extend `job_outputs` JSON fields for:
   - artifact versions
   - approval snapshot
   - per-job usage summary
3. Persist:
   - model name/version
   - prompt hash/version
   - token usage
   - estimated cost
   - latency
   - retry count
   - failure reason

## C. Execution APIs Not Yet Present

1. `POST /api/v1/jobs/{job_id}/generate` (full generation run).
2. `POST /api/v1/jobs/{job_id}/outputs/{output_type}/regenerate` (targeted AI regenerate).
3. `GET /api/v1/jobs/{job_id}/generation-runs` (audit + debugging).
4. `POST /api/v1/jobs/{job_id}/approve` (locks approved output set for submit path).

## D. Connector Behavior Is Registry-Only (Not Full Integration Yet)

Current connector module stores references and statuses only.
Still missing:
1. Google Docs OAuth flow + token refresh implementation.
2. Real publish/export adapters (Google Docs, Airtable, etc).
3. Connector-specific health checks via live API call.

## E. Product Logic Gaps

1. Full job state machine enforcement (`draft -> processing -> ready -> approved -> submitted -> closed`).
2. Guardrails/policies before submission (quality gates).
3. Idempotent generation jobs with conflict handling between API-triggered and worker-triggered runs.

## F. Testing Gaps for AI Layer

1. Integration tests for generation with mocked LLM provider.
2. Contract tests for structured workflow output.
3. Failure-path tests (timeout, malformed model output, token budget exceeded).
4. Staging E2E suite validating real connector round-trips (where possible).

---

## 4. Proposed Remaining Backend Phases

## B13 - AI Provider and Orchestration Foundation

1. LLM adapter interface + OpenAI implementation.
2. Prompt builder and prompt versioning.
3. Structured output parser/validator.
4. Generation-run persistence models + migrations.

Exit criteria:
1. One endpoint can generate all core outputs from job markdown.
2. Generation metadata is persisted and queryable.

## B14 - Generation APIs + Worker Pipeline

1. Add generate/regenerate endpoints.
2. Queue-backed generation execution.
3. Retry strategy for transient LLM/provider failures.

Exit criteria:
1. End-to-end generation works asynchronously and reliably.
2. Regenerate affects only targeted output.

## B15 - Connector Real Integrations

1. Google Docs OAuth (per-user) and publish flow.
2. Airtable publish adapter.
3. Connector health probes and error mapping.

Exit criteria:
1. Generated output can be pushed to at least one live external system.

## B16 - Hardening of AI Product Path

1. Cost/rate controls per user and per day.
2. Abuse prevention + prompt safety guardrails.
3. Rich observability dashboards for generation quality and failures.
4. AI E2E test suite in CI (mocked provider mode).

Exit criteria:
1. AI generation flow is operationally stable and measurable.

---

## 5. Immediate Next Step

Start with **B13**.  
Without B13, backend cannot perform real automated artifact generation.
