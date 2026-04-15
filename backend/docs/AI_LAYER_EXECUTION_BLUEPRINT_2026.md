# AI Layer Execution Blueprint 2026 (Final)

Last Updated: 2026-04-03  
Status: Approved working blueprint for full product AI layer (not MVP scope).

---

## 1) Product Intent (Locked)

1. This is a full product system, not an MVP shortcut.
2. One-click generation must produce all required job artifacts.
3. Regeneration must support per-artifact custom instruction and multi-version comparison.
4. The system must prioritize n8n workflow output quality, while supporting Make.com when required.

---

## 2) Confirmed Decisions (Locked)

1. Extraction fallback is strict.
- Firecrawl success: continue.
- Firecrawl empty/error: require user manual full job post paste before generation.

2. Generation mode is one-click full generation.
- System generates all relevant artifacts from understood job context.
- User can regenerate a single artifact later with custom instruction.

3. Regeneration is non-destructive.
- New versions are created.
- Existing selected version is not overwritten.
- UI can toggle between versions (e.g., version 1/2/3).

4. Google Docs behavior.
- Export creates a new doc each time.

5. Workflow platform behavior.
- Primary business default: n8n.
- If job text explicitly mentions Make.com only, system asks user at generation start:
  - Use Make.com workflow
  - Use n8n workflow
- If unclear, default to n8n and show platform toggle.

6. Workflow quality expectation.
- Generated workflow must be import-ready and visually understandable.
- n8n workflow should include connected nodes and explanatory sticky note style guidance.

7. Model lock for key tasks.
- Job understanding uses `gpt-5.4-mini`.
- n8n workflow generation uses `claude-sonnet-4-5`.

---

## 3) Core Architecture Addition: Job Understanding Layer

## What it is
A structured interpretation step that converts raw job text into a machine-usable contract before any artifact generation.

## Why it is required
1. Prevents hallucinated generation from noisy markdown.
2. Detects exactly what deliverables are needed.
3. Enables correct platform branching (n8n vs Make.com).
4. Allows confidence gating before expensive model calls.

## Output contract (internal object)
1. `summary_short`: short plain-language summary.
2. `deliverables_required`: proposal, cover letter, screening answers, workflow, doc.
3. `screening_questions`: list of extracted questions.
4. `automation_platform_preference`: n8n, make, both, unknown.
5. `constraints`: tone, budget, deadline, tools, must-haves.
6. `extraction_confidence`: high, medium, low.
7. `missing_fields`: missing critical details to ask user.

## Confidence rule
1. High/medium confidence: generation allowed.
2. Low confidence: block generation and request user clarification/manual correction.

---

## 4) End-to-End AI Runtime (Final Flow)

1. Job text source resolved.
- Firecrawl markdown or manual user paste.

2. Job understanding pass.
- Build structured job contract.
- Validate minimum required fields.

3. Generation planning pass.
- Decide required artifacts.
- Decide workflow platform path.
- Decide model route per artifact.

4. Policy gate pass.
- Cost/budget checks.
- Safety checks.
- Throttle/quota checks.

5. Multi-artifact generation pass.
- Proposal/copy outputs.
- Screening question answers.
- Loom script.
- Workflow JSON and visual metadata.

6. Deterministic validation pass.
- Workflow schema checks.
- Artifact content contract checks.

7. Persistence pass.
- Save outputs.
- Save generation run metadata.
- Save output revisions.

8. Review pass.
- User sees generated set.
- User can regenerate single artifact with custom instruction.

9. Approval pass.
- Selected revision set is frozen.

10. Publish pass.
- New Google Doc creation if requested.
- Connector publish references persisted.

11. Submission and outcome tracking pass.
- Existing job lifecycle updates continue.

---

## 5) Multi-Model Strategy (Agreed Direction)

## Routing design
1. Use model routing by task type, not one model for all tasks.
2. Keep first release to 2-3 active models total to reduce complexity.
3. Support provider-level fallback when primary provider/API is unavailable.
4. If all fallback providers fail, surface a clear user-facing failure reason (`provider_unavailable`) and keep run auditable.

## Routing mode definitions
1. Fixed-per-artifact routing.
- Each artifact type has a preconfigured model/provider mapping.
- Predictable quality and predictable cost.
- Recommended for first production release.

2. Dynamic router.
- Router chooses model at runtime based on complexity, token size, budget, and confidence.
- Better cost optimization but higher implementation complexity and risk.
- Recommended only after stable fixed routing release.

## Recommended task allocation (updated)
1. Job understanding/classification.
- Primary: `gpt-5.4-mini`.
- Fallback: `claude-sonnet-4-5`.

2. Proposal/cover letter/screening answers.
- Primary (recommended): `gpt-5.4-mini` for cost control at scale.
- Fallback: `claude-sonnet-4-5`.
- Escalation rule: if output quality check fails, regenerate on `claude-sonnet-4-5`.

3. Workflow generation and workflow repair.
- Primary: `claude-sonnet-4-5`.
- Fallback: `gpt-5.4`.

4. Regeneration routing.
- Use same artifact-primary model by default.
- If instruction is simple rewrite, allow downshift to lower-cost model.
- If previous run failed validation, force high-reasoning model.

## Provider support policy
1. Provider-agnostic adapter architecture.
2. Active providers: OpenAI, Anthropic, Gemini.
3. Keep a route config table/file so model mapping can change without changing orchestration code.
4. Keep provider health scoring and temporary circuit-breaker behavior per provider.

## Cost governance
1. Define per-run budget cap.
2. Define per-user/day budget cap.
3. Log every run cost estimate and token usage.
4. Deny run with explicit reason when limits exceed.
5. Expose daily and lifetime cost dashboard in product UI.

## Internet research references for model/cost direction
1. OpenAI pricing and model tiers:
- https://developers.openai.com/api/docs/pricing
2. Anthropic model overview and pricing guidance:
- https://platform.claude.com/docs/en/about-claude/models/overview
3. Gemini pricing and model positioning:
- https://ai.google.dev/gemini-api/docs/pricing

## Pricing estimate for 30 jobs/day (using current locked/recommended routing)
Pricing basis used:
1. `gpt-5.4-mini`: input $0.75/1M tokens, output $4.50/1M tokens.
2. `claude-sonnet-4-5`: input $3.00/1M tokens, output $15.00/1M tokens.

Assumed token profile per job:
1. Job understanding (`gpt-5.4-mini`): 2,000 input + 400 output.
2. Proposal/cover/screening (`gpt-5.4-mini`): 6,000 input + 1,800 output.
3. n8n workflow (`claude-sonnet-4-5`): 10,000 input + 3,000 output.

Estimated cost:
1. Understanding per job: $0.0033
2. Proposal/cover/screening per job: $0.0126
3. Workflow per job: $0.0750
4. Total per job: **$0.0909**
5. Daily at 30 jobs: **$2.73/day**
6. Monthly at 30-day month: **$81.81/month**

Cost range guidance (depends on prompt size and retries):
1. Lean usage: ~$53/month
2. Typical usage: ~$82/month
3. Heavy usage: ~$128/month

Fallback impact note:
1. Cross-provider fallback/retries typically add 10-25% extra spend.
2. If fallback triggers often, provider health alerting should be enabled.

---

## 6) Artifact Generation Rules (Final)

1. Proposal and cover letter.
- Generated from job requirements and profile tone.
- Keep concise, human, and role-specific.

2. Screening question answers.
- Detect all questions from job text.
- Generate per-question answers with clear separation.

3. Loom script.
- Structured narrative with opening, proof, execution plan, CTA.

4. Workflow outputs.
- n8n import-ready JSON as primary.
- Make.com variant only when user chooses/requests.
- Include visual explanation metadata for UI viewer.
- Include sticky-note guidance blocks for readability in n8n canvas.

5. Docs output.
- Human-readable document content for web preview first.
- Optional publish to new Google Doc on user action.

## Artifact meaning (system term)
1. Artifact means one generated output unit.
- Examples: proposal, cover letter, screening answers, loom script, workflow JSON, doc content.

---

## 7) Data and Versioning Model (Final)

1. Keep one AI telemetry table.
- Tracks model route, prompt hash/version, tokens, latency, cost, retries, failure reason.
- Table: `job_generation_runs`.

2. Keep artifact revisions inside `job_outputs`.
- Column: `artifact_versions_json`.
- Stores per-artifact versions and regeneration history.

3. Keep approval freeze inside `job_outputs`.
- Column: `approval_snapshot_json`.
- Records exact selected versions for publish/submit consistency.

4. Keep usage summary inside `job_outputs`.
- Column: `ai_usage_summary_json`.
- Aggregated per-job usage/cost summary for fast UI reads.

5. Keep routing rules table optional (future only).
- Purpose: update mapping without code deploy.
- Suggested name: `llm_routing_rules`.
- Key fields: artifact_type, primary_provider, primary_model, fallback_provider, fallback_model, max_cost_per_call, active.

---

## 8) Required Backend Implementation Areas

1. Provider adapters.
- `app/infrastructure/ai/providers/*`

2. Prompt and understanding.
- `app/application/ai/prompt_*`
- `app/application/ai/job_understanding_service.py`

3. Orchestration.
- `app/application/ai/orchestrator_service.py`
- `app/application/ai/contracts.py`
- `app/application/ai/errors.py`

4. Validation.
- `app/application/ai/validators/*`

5. Persistence.
- DB model and migration for `job_generation_runs` and `job_outputs` JSON tracking fields.

6. Async runtime.
- generation queue contracts, dispatch, and worker.

7. Publish integrations.
- Google Docs client with per-user OAuth refresh.
- Airtable publish adapter.

8. Observability extension.
- AI metrics, policy-denied metrics, provider failure metrics.
- usage and cost dashboard metrics (daily + all-time).
- provider outage and fallback metrics.
 - user-visible provider status message when all configured providers are unavailable.

9. Workflow intelligence context source.
- Add curated node/pattern knowledge pack for n8n and Make.com generation quality.
- Can be maintained as versioned internal context documents and optional MCP-backed retrieval.

---

## 9) Reliability and Failure Behavior (Final)

1. Firecrawl fails or empty.
- Stop extraction path.
- Require manual full job post paste.

2. Provider transient failure.
- Bounded retry with backoff.

3. Invalid structured output.
- Reject and mark run failure (`invalid_output`).

4. Low understanding confidence.
- Block generation and ask user for correction.

5. Publish failure.
- Keep approved state and allow retry publish.

---

## 10) Phase Execution Plan (Final)

## B13 Foundation
1. Provider adapter abstraction.
2. Job understanding + prompt builder + hash/version.
3. Structured validators.
4. Run/revision DB models + migration.

Exit:
1. Internal orchestration can generate validated artifacts and persist run metadata.

## B14 Runtime Integration
1. AI orchestration integrated into live generation path.
2. Async generation worker support.
3. Retry/policy/failure classification stabilization.

Exit:
1. End-to-end generation and per-artifact regeneration run reliably.

## B15 Publish Integrations
1. Google Docs publish (new doc each action).
2. Airtable publish adapter.
3. Connector live health checks.

Exit:
1. Approved outputs can be published with persisted external references.

## B16 Hardening
1. Cost controls and safety guardrails enforced.
2. Expanded AI observability and quality monitoring.
3. Full AI integration/contract/failure tests in CI.

Exit:
1. AI layer is operationally stable, measurable, and release-safe.

---

## 11) Final Definition of Done

1. Generation is fully backend-orchestrated from extracted/manual job text.
2. Job understanding contract drives all artifact generation.
3. Multi-model routing works with budget and policy controls.
4. Revisions are versioned and user-selectable, not overwritten.
5. Approval snapshot is enforceable before publish.
6. Workflow generation produces import-ready and visually understandable output.
7. Publish integrations work with auditable references.
8. AI layer is covered by integration and failure-path tests.
