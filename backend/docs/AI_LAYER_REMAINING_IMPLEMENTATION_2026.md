# AI Layer Remaining Implementation 2026 (Sub-Phase Plan)

Last Updated: 2026-04-03  
Status: Execution-ready sub-phase breakdown for full AI layer completion.

---

## 1) Scope and Intent

This document decomposes the remaining AI phases (`B13` to `B16`) into implementation sub-phases that can be executed and tracked.

Source alignment:
1. `AI_LAYER_EXECUTION_BLUEPRINT_2026.md`
2. `BACKEND_REMAINING_SCOPE_2026.md`
3. `BACKEND_FULL_PIPELINE_MERMAID_2026.md`

---

## 2) Phase Decomposition (Mini Phases)

## B13 - AI Provider and Orchestration Foundation

### B13.1 AI Module Skeleton and Core Contracts
1. Create `app/application/ai/` module.
2. Add `contracts.py` for canonical request/response DTOs.
3. Add `errors.py` for typed AI failure taxonomy.
4. Add `routing.py` for fixed-per-artifact model mapping.
5. Add base interfaces for providers and validators.

Exit:
1. AI module compiles, imports cleanly, and has stable public contracts.

### B13.2 Provider Adapter Layer (OpenAI First, Extensible)
1. Add provider abstraction: `AIProviderAdapter`.
2. Implement OpenAI adapter with timeout and bounded retries.
3. Add provider result normalization into internal contract shape.
4. Add provider failure mapping (`provider_timeout`, `provider_unavailable`, `rate_limited`).

Exit:
1. One adapter call returns normalized structured output and usage metadata.

### B13.3 Job Understanding Layer
1. Add `job_understanding_service.py`.
2. Implement understanding prompt builder from job markdown + profile context.
3. Enforce output contract:
   - `summary_short`
   - `deliverables_required`
   - `screening_questions`
   - `automation_platform_preference`
   - `constraints`
   - `extraction_confidence`
   - `missing_fields`
4. Implement confidence gate (`high|medium` allow, `low` block).

Exit:
1. Job understanding object is generated, validated, and gateable.

### B13.4 Prompt Versioning and Hashing
1. Add prompt template registry per artifact type.
2. Compute stable prompt hash and prompt version.
3. Persist hash/version in `job_generation_runs`.
4. Add deterministic template composition order.
5. Keep prompts split per task under `app/application/ai/prompt/` for maintainability.

Exit:
1. Every AI call can be traced to exact prompt version/hash.

### B13.5 Artifact Generation Planning and Routing
1. Build generation planner from job understanding contract.
2. Select required artifacts automatically.
3. Implement platform branching:
   - default `n8n`
   - ask/override path when Make-only intent detected
4. Map each artifact to fixed model route for first release.

Exit:
1. Planner emits deterministic artifact execution plan per job.

### B13.6 Deterministic Validators
1. Add `validators/` package for artifact contract checks.
2. Add workflow JSON schema validation (import-ready contract).
3. Add content validators for proposal/loom/doc/screening outputs.
4. Fail with typed `invalid_output` reason on schema mismatch.

Exit:
1. Invalid model outputs are rejected before persistence.

### B13.7 Persistence Integration for AI Tracking
1. Create run lifecycle helpers for `job_generation_runs` (`running/success/failed`).
2. Write `artifact_versions_json` append logic.
3. Write `ai_usage_summary_json` aggregation logic per job.
4. Ensure all failure reasons and retry counts are persisted.

Exit:
1. Full run telemetry and version history are queryable from DB.

---

## B14 - Generation APIs and Worker Runtime

### B14.1 Public API Contracts
1. Add `POST /api/v1/jobs/{job_id}/generate`.
2. Add `POST /api/v1/jobs/{job_id}/outputs/{output_type}/regenerate`.
3. Add `GET /api/v1/jobs/{job_id}/generation-runs`.
4. Add `POST /api/v1/jobs/{job_id}/approve`.
5. Add request/response schemas and typed error responses.

Exit:
1. API surface for generate/regenerate/audit/approve is complete.

### B14.2 Queue Contracts and Worker for AI Runs
1. Add queue task contract for generation jobs.
2. Add AI generation worker with per-job lock and idempotency key support.
3. Support inline and queued execution parity.
4. Ensure safe duplicate suppression on concurrent triggers.

Exit:
1. AI generation can run asynchronously and safely under concurrency.

### B14.3 Full Generation Orchestration
1. Wire `/generate` endpoint to orchestrator service.
2. Execute flow:
   - understanding
   - planning
   - policy gate
   - artifact generation
   - validation
   - persistence
3. Return run id and status snapshot to client.

Exit:
1. One request can generate the full artifact set end-to-end.

### B14.4 Targeted Regeneration Orchestration
1. Wire per-artifact regenerate endpoint to orchestrator.
2. Support custom instruction per regenerate call.
3. Ensure non-destructive versioning (no overwrite).
4. Keep selected version unchanged unless explicitly approved.

Exit:
1. Regenerate only updates target artifact with a new version entry.

### B14.5 Approval Snapshot and Freeze Behavior
1. Implement approval command that stores selected revisions.
2. Persist immutable approval snapshot in `approval_snapshot_json`.
3. Block publish/submit paths when no approval snapshot exists.
4. Add status transition enforcement around approval.

Exit:
1. Approved revision set is frozen and enforceable.

### B14.6 Retry, Failure Classification, and Policy Responses
1. Add retry strategy per failure class (transient/permanent).
2. Add explicit user-facing failure codes:
   - `provider_unavailable`
   - `invalid_output`
   - `budget_exceeded`
   - `low_confidence_understanding`
3. Ensure run status and API response are consistent.

Exit:
1. Failures are auditable, classifiable, and actionable.

### B14.7 Runtime Integration Tests
1. Add integration tests for full generate success path.
2. Add tests for targeted regenerate and version append semantics.
3. Add tests for low-confidence block and invalid-output rejection.
4. Add tests for retry exhaustion and failure persistence.

Exit:
1. B14 API and runtime behavior is test-verified.

---

## B15 - Connector Real Integrations and Publish Layer

### B15.1 Publish Abstraction and Connector Contracts
1. Add publisher interface with typed request/response contracts.
2. Define adapter outputs: external id/url, status, error code/message.
3. Add publish orchestration service and adapter registry.

Exit:
1. Publish layer supports pluggable connector adapters.

### B15.2 Google OAuth and Token Lifecycle
1. Implement Google OAuth connect flow (per user).
2. Store and refresh tokens securely.
3. Handle token expiry and refresh failure mapping.
4. Add reconnect path for revoked tokens.

Exit:
1. Per-user Google auth is production-safe and refresh-capable.

### B15.3 Google Docs Publish Adapter
1. Implement doc creation adapter (always create new doc per publish action).
2. Push approved content to Google Docs.
3. Persist external references in job/output records.
4. Return publish status and deep links.

Exit:
1. Approved outputs can be exported to new Google Docs repeatedly.

### B15.4 Airtable Publish Adapter
1. Implement Airtable adapter for approved output payloads.
2. Map schema fields and status transitions.
3. Persist Airtable record id and publish metadata.
4. Handle partial publish failure with retry-safe behavior.
5. Allow disabled-by-default scaffold mode so activation is configuration-led.

Exit:
1. At least one non-Google live publish path is functional.

### B15.5 Live Connector Health Checks
1. Add active health probe per connector provider.
2. Expose connector health in API status response.
3. Store recent health events and outage indicators.
4. Integrate health state into publish error messaging.

Exit:
1. Connector status reflects real API health, not only registry state.

### B15.6 Publish Audit and Recovery Semantics
1. Persist publish attempts and outcomes with timestamps.
2. Keep approved state on publish failure (retryable).
3. Add idempotent publish retry behavior.
4. Ensure no destructive rollback of approved revisions.

Exit:
1. Publish path is auditable and operationally retry-safe.

### B15.7 Connector Integration Tests
1. Add adapter unit tests with provider stubs.
2. Add integration tests for token refresh and publish failures.
3. Add tests for persisted external refs and retry semantics.
4. Add smoke tests for health endpoint behavior.

Exit:
1. Connector flows are test-backed and release-ready.

---

## B16 - Hardening, Governance, Observability, and CI Gate

### B16.1 Cost and Quota Governance
1. Enforce per-run budget cap.
2. Enforce per-user daily cap.
3. Deny over-budget runs with explicit reason.
4. Persist usage totals for dashboard reads.

Exit:
1. Cost policies are enforced before expensive generation steps.

### B16.2 Prompt and Output Safety Guardrails
1. Add input prompt guard checks (malicious or unsafe directives).
2. Add output safety checks for policy violations.
3. Add guardrail rejection codes and audit metadata.
4. Add safe fallback messaging to user.

Exit:
1. Unsafe requests/outputs are blocked and traceable.

### B16.3 Provider Health, Fallback, and Circuit Breaking
1. Add provider health scoring.
2. Add temporary circuit breaker per provider/model.
3. Implement automatic fallback to secondary route.
4. Surface user-visible status when all providers unavailable.

Exit:
1. Multi-provider resilience is measurable and operational.

### B16.4 AI Observability and Dashboards
1. Add metrics for:
   - generation success/failure rate
   - fallback count
   - invalid output count
   - policy-denied count
   - latency and token/cost trend
2. Add dashboard views for daily/all-time usage.
3. Add alerts on failure spikes and fallback spikes.

Exit:
1. AI runtime can be monitored with actionable operational signals.

### B16.5 Runbooks and Incident Readiness
1. Update deploy/incident/rollback runbooks for AI failure modes.
2. Add provider outage response checklist.
3. Add budget lockout response checklist.
4. Add data correction and replay guidance for failed runs.

Exit:
1. Ops team has documented, executable incident procedures.

### B16.6 AI Test Suite in CI
1. Add provider-mocked end-to-end tests for generate/regenerate/approve/publish.
2. Add contract tests for workflow schema and output contracts.
3. Add failure-path tests for timeout, malformed output, quota denial, provider outage.
4. Add performance smoke tests for target latency envelope.

Exit:
1. CI blocks releases when critical AI path contracts break.

### B16.7 Release Gate and Final Sign-Off
1. Define release checklist against all B13-B16 exit criteria.
2. Run staging validation and UAT focused on AI flows.
3. Record final sign-off artifact and rollback readiness.
4. Mark AI layer release-safe only after all gates pass.

Exit:
1. AI product path is operationally stable, measurable, and shippable.

---

## 3) Recommended Execution Order

1. `B13.1 -> B13.7`
2. `B14.1 -> B14.7`
3. `B15.1 -> B15.7`
4. `B16.1 -> B16.7`

Parallelization guidance:
1. During B13, provider adapter work and validator scaffolding can run in parallel.
2. During B14, API schema work can run parallel to worker contract scaffolding.
3. During B15, Google and Airtable adapters can run in parallel after publish abstraction is fixed.
4. During B16, observability and CI test authoring can run in parallel after governance policies land.

---

## 4) Tracking Checklist (Execution Board)

## B13
- [x] B13.1 AI module skeleton and contracts
- [x] B13.2 OpenAI adapter and provider abstraction
- [x] B13.3 Job understanding layer
- [x] B13.4 Prompt versioning and hashing
- [x] B13.5 Artifact planner and routing
- [x] B13.6 Deterministic validators
- [x] B13.7 AI tracking persistence integration

## B14
- [x] B14.1 Generate/regenerate/runs/approve APIs
- [x] B14.2 AI queue contracts and worker execution
- [x] B14.3 Full generation orchestration
- [x] B14.4 Targeted regeneration orchestration
- [x] B14.5 Approval snapshot and freeze behavior
- [x] B14.6 Retry and failure classification
- [x] B14.7 Runtime integration tests

## B15
- [x] B15.1 Publish abstraction and connector contracts
- [x] B15.2 Google OAuth token lifecycle
- [x] B15.3 Google Docs publish adapter
- [x] B15.4 Airtable publish adapter
- [x] B15.5 Live connector health checks
- [x] B15.6 Publish audit and retry-safe recovery
- [x] B15.7 Connector integration tests

## B16
- [x] B16.1 Cost and quota governance
- [x] B16.2 Prompt/output safety guardrails
- [x] B16.3 Provider fallback and circuit breaker
- [x] B16.4 AI observability dashboards and alerts
- [x] B16.5 AI runbook hardening
- [x] B16.6 AI test suite in CI
- [x] B16.7 Final release gate and sign-off

---

## 5) Final Definition of Completion

1. One-click generation is understanding-driven, validated, and fully orchestrated.
2. Per-artifact regeneration is non-destructive and versioned.
3. Approval snapshot is required and enforced before publish.
4. Publish adapters create auditable external references with retry-safe recovery.
5. Cost/safety/provider policies are enforced with explicit user-visible failure reasons.
6. AI metrics, tests, and runbooks are complete enough for production operations.

---

## 6) B16 Implementation Notes (2026-04-03)

1. Governance controls added:
   - per-run token budget enforcement
   - per-user daily cost cap enforcement
   - explicit budget denial code path
2. Safety guardrails added:
   - prompt/input directive block patterns
   - output secret-leak block patterns
   - guardrail metrics counters
3. Provider resilience added:
   - provider/model circuit breaker state
   - fallback tracking metrics
   - open-circuit immediate fail-fast behavior
4. Observability expanded:
   - AI run success/failure counts
   - policy denied / guardrail block counters
   - provider failure / circuit-open counters
   - token and estimated cost totals
5. Ops runbooks updated:
   - incident handling for provider outages and budget lockouts
   - deployment smoke checks for AI hardening
   - rollback guidance for AI regressions
6. Release sign-off artifact added:
   - `docs/AI_RELEASE_GATE_2026-04-03.md`
7. Deferred UI implementation note added:
   - `docs/GOOGLE_CONNECT_UI_BACKLOG.md`

## 7) Post-B16 Intake Hardening (2026-04-03)

1. Job URL intake now uses hybrid parsing:
   - deterministic URL/job-id extraction first
   - cheap LLM fallback only when deterministic parse fails
2. LLM fallback is strict:
   - expects JSON response with `normalized_url` + confidence
   - accepts only `high|medium` confidence
   - re-validates through Upwork URL canonicalizer before persistence
3. Added config toggles for controlled rollout:
   - `AI_ENABLE_JOB_URL_LLM_FALLBACK`
   - `AI_JOB_URL_PARSER_MODEL`
   - `AI_JOB_URL_PARSER_MAX_OUTPUT_TOKENS`

## 8) Provider Runtime Update (2026-04-03)

1. `workflow` generation route is now enforced to Claude (`claude-sonnet-4-5`) at runtime.
2. OpenAI remains primary for non-workflow artifacts.
3. Anthropic provider adapter was added and wired in the provider factory.
