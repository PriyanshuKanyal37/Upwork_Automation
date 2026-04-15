# Backend Full Pipeline Mermaid (Current + Target AI)

Last Updated: 2026-04-03  
Scope: Production-level backend flow from request entry to AI generation, approval, and publishing.

This document combines:
1. Existing backend (already implemented).
2. AI orchestration layers (remaining scope to implement).
3. End-to-end pipeline behavior including retries, fallbacks, state transitions, and observability.

---

## 1) System Architecture (Implemented + Planned)

```mermaid
flowchart LR
    U[User / Frontend] --> G[API Gateway: FastAPI app.main]
    G --> MW[Middleware Chain\nrequest-id, timeout, global rate limit, idempotency]

    MW --> AUTH[Auth API\nregister login logout me]
    MW --> PROF[Profile API\nprofile templates + prompt blocks]
    MW --> JOB[Job API\nintake duplicate extract history status]
    MW --> OUT[Output API\nget patch regenerate]
    MW --> CONN[Connector API\nregistry + status]
    MW --> MET[Metrics API]

    AUTH --> APP_AUTH[Auth Service]
    PROF --> APP_PROF[Profile Service]
    JOB --> APP_JOB[Job Service]
    OUT --> APP_OUT[Output Service]
    CONN --> APP_CONN[Connector Service]

    APP_AUTH --> DB[(Neon Postgres)]
    APP_PROF --> DB
    APP_JOB --> DB
    APP_OUT --> DB
    APP_CONN --> DB

    APP_JOB --> QSW{Queue Driver}
    QSW -->|inline| INLINE[Inline Extraction Execution]
    QSW -->|dramatiq| DRQ[Redis + Dramatiq Broker]
    DRQ --> WRK[Extraction Worker]

    INLINE --> FC[Firecrawl Client]
    WRK --> LOCK[Per-job Redis Lock]
    LOCK --> FC

    FC -->|success markdown| APP_JOB
    FC -->|failure| FALL[Manual Markdown Fallback Required]
    FALL --> DB

    APP_JOB --> DB

    subgraph AI_TARGET[Target AI Orchestration Layer to Implement]
        ORCH[Generation Orchestrator]
        PROMPT[Prompt Builder\nprofile + job + prompt blocks + connector context]
        LLM[LLM Provider Adapter\nOpenAI first]
        VALID[Structured Validator\nworkflow JSON + schema checks]
        RUNS[(job_generation_runs + job_outputs JSON versioning)]
        APPV[Approval Gate]
        PUB[Publisher Adapters\nGoogle Docs Airtable etc]
        COST[Per-user cost and quota controls]
        SAFE[Prompt and output safety guardrails]
    end

    APP_JOB -. trigger generate .-> ORCH
    APP_OUT -. trigger regenerate .-> ORCH
    ORCH --> PROMPT --> LLM --> VALID
    VALID --> APP_OUT
    VALID --> RUNS
    RUNS --> DB
    APP_OUT --> APPV --> PUB
    ORCH --> COST
    ORCH --> SAFE
    PUB --> DB

    subgraph OBSERVABILITY[Observability and Reliability]
        LOG[Structured Logs + Request IDs]
        AUDIT[Audit Events]
        METRICS[Metrics Collector]
        RUNBOOKS[Incident + Backup + Deploy Runbooks]
    end

    MW --> LOG
    APP_JOB --> AUDIT
    WRK --> METRICS
    FC --> METRICS
    ORCH --> METRICS
    PUB --> METRICS
    METRICS --> MET
    RUNBOOKS -. operate on .-> G
```

---

## 2) End-to-End Execution Pipeline (Detailed)

```mermaid
flowchart TD
    A1[Client sends request\nPOST /api/v1/jobs/intake] --> A2[Middleware validates\ntimeout, rate limit, idempotency]
    A2 --> A3{Auth session cookie valid}
    A3 -->|No| A4[Return 401]
    A3 -->|Yes| A5[Normalize URL + parse Upwork job id]

    A5 --> A6{Duplicate exists for same user}
    A6 -->|Yes| A7[Return duplicate decision required]
    A6 -->|No| A8[Create job row status=draft]

    A8 --> A9[Client triggers extraction\nPOST /jobs/{id}/extract]
    A9 --> A10{QUEUE_DRIVER}

    A10 -->|inline| A11[Run extraction in request path]
    A10 -->|dramatiq| A12[Enqueue extraction task]
    A12 --> A13[Worker pulls task]
    A13 --> A14[Acquire Redis lock per job]
    A14 --> A15{Lock acquired}
    A15 -->|No| A16[Skip duplicate concurrent task]
    A15 -->|Yes| A17[Call Firecrawl scrape API]

    A11 --> A17
    A17 --> A18{Firecrawl success}
    A18 -->|No| A19[Mark job requires_manual_markdown=true\nstore extraction_error]
    A18 -->|Yes| A20[Store job_markdown + notes_markdown\nstatus=ready]

    A19 --> A21[User posts manual markdown\nPOST /jobs/{id}/manual-markdown]
    A21 --> A22[Store markdown\nstatus=ready]
    A20 --> B1
    A22 --> B1

    B1[Generation entrypoint\nPOST /jobs/{id}/generate] --> B2[Create generation run record\nstatus=running]
    B2 --> B3[Build prompt context\nprofile + templates + job markdown + custom blocks]
    B3 --> B4[Apply budget and quota policy checks]
    B4 --> B5{Policy allows run}
    B5 -->|No| B6[Fail run with reason quota or policy]
    B5 -->|Yes| B7[Call LLM provider adapter]

    B7 --> B8{LLM response valid}
    B8 -->|No| B9[Retry transient errors by policy]
    B9 --> B10{Retry exhausted}
    B10 -->|No| B7
    B10 -->|Yes| B11[Fail run\nstore failure reason]

    B8 -->|Yes| B12[Validate deterministic schemas\nworkflow JSON contract]
    B12 --> B13{Schema valid}
    B13 -->|No| B14[Fail run as invalid_output]
    B13 -->|Yes| B15[Persist outputs\nproposal + loom + doc + workflows]

    B15 --> B16[Create output revision records]
    B16 --> B17[Mark generation run success\nstore tokens, latency, model, cost]
    B17 --> B18[Job status=ready_for_review]

    B18 --> C1[User reviews and edits outputs]
    C1 --> C2{Need targeted regenerate}
    C2 -->|Yes| C3[POST /jobs/{id}/outputs/{type}/regenerate]
    C3 --> C4[Run same orchestration for one output type]
    C4 --> C5[Append edit log + revision]
    C2 -->|No| C6[Proceed to approval]
    C5 --> C6

    C6 --> C7[POST /jobs/{id}/approve]
    C7 --> C8[Freeze approved output set]
    C8 --> C9[Job status=approved]

    C9 --> D1[Publish step by connector adapters]
    D1 --> D2{Google Docs connected}
    D2 -->|Yes| D3[Publish doc and store external URL]
    D2 -->|No| D4[Skip docs publish with reason]

    D3 --> D5{Airtable connected}
    D4 --> D5
    D5 -->|Yes| D6[Push record fields and status]
    D5 -->|No| D7[Skip Airtable publish with reason]

    D6 --> D8[Mark submission metadata]
    D7 --> D8
    D8 --> D9[PATCH /jobs/{id}/submission]
    D9 --> D10[Job status=submitted or closed]

    B6 --> Z1[Audit event + metrics + alert rules]
    B11 --> Z1
    B14 --> Z1
    D10 --> Z2[History API serves final lifecycle]
```

---

## 3) Async Sequence (Request, Queue, AI, and Publish)

```mermaid
sequenceDiagram
    autonumber
    participant UI as Frontend
    participant API as FastAPI API
    participant MW as Middleware
    participant APP as App Services
    participant DB as Neon Postgres
    participant Q as Redis/Dramatiq
    participant W as Extraction Worker
    participant FC as Firecrawl
    participant OR as AI Orchestrator
    participant LLM as LLM Provider
    participant VA as Output Validator
    participant PUB as Publisher Adapters

    UI->>API: POST /jobs/intake
    API->>MW: apply timeout/rate/idempotency/request-id
    MW->>APP: authenticated request
    APP->>DB: insert job(status=draft)
    DB-->>APP: job_id
    APP-->>UI: intake response

    UI->>API: POST /jobs/{id}/extract
    API->>APP: extract requested
    alt queue_driver=inline
        APP->>FC: scrape(url)
        FC-->>APP: markdown or error
    else queue_driver=dramatiq
        APP->>Q: enqueue extraction task
        Q-->>W: deliver task
        W->>FC: scrape(url)
        FC-->>W: markdown or error
        W->>DB: update extraction fields
    end

    UI->>API: POST /jobs/{id}/generate
    API->>OR: start generation run
    OR->>DB: create run(status=running)
    OR->>LLM: generate artifacts from prompt context
    LLM-->>OR: proposal/doc/workflow/loom output
    OR->>VA: validate schema and contracts

    alt validation passes
        VA-->>OR: valid
        OR->>DB: upsert outputs + revisions + run success metadata
        OR-->>API: success
        API-->>UI: outputs ready
    else validation fails
        VA-->>OR: invalid
        OR->>DB: run failed with reason
        OR-->>API: generation error
        API-->>UI: failure response
    end

    UI->>API: POST /jobs/{id}/approve
    API->>DB: lock approved output version
    DB-->>API: approved

    UI->>API: POST /jobs/{id}/publish
    API->>PUB: publish approved artifacts
    PUB->>DB: persist external refs/status
    PUB-->>API: publish result
    API-->>UI: publish complete
```

---

## 4) Job Lifecycle State Machine (Target)

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> duplicate_review: duplicate detected
    duplicate_review --> draft: user chooses continue
    duplicate_review --> closed: user chooses skip

    draft --> processing: extraction started
    processing --> ready: extraction success
    processing --> manual_required: extraction failed
    manual_required --> ready: manual markdown submitted

    ready --> generating: generate or regenerate requested
    generating --> review_ready: generation success
    generating --> generation_failed: generation failed
    generation_failed --> generating: retry by policy
    generation_failed --> manual_required: fallback to manual updates

    review_ready --> approved: explicit approval
    approved --> published: connector publish success
    approved --> submitted: manual submission update

    submitted --> closed: outcome finalized
    published --> closed: final close
```

---

## 5) Failure and Recovery Control Flow

```mermaid
flowchart TD
    F1[Failure source] --> F2{Type}

    F2 -->|Rate limit timeout auth| F3[Return typed API error]
    F3 --> F4[Client retry with backoff]

    F2 -->|Firecrawl transient| F5[Retry with bounded backoff]
    F5 --> F6{Recovered}
    F6 -->|Yes| F7[Continue extraction]
    F6 -->|No| F8[Mark manual_required + extraction_error]

    F2 -->|Queue conflict| F9[Redis lock prevents duplicate worker execution]
    F9 --> F10[Drop duplicate task safely]

    F2 -->|LLM malformed output| F11[Validator rejects output]
    F11 --> F12[Generation run failed invalid_output]
    F12 --> F13[Allow targeted regenerate]

    F2 -->|Connector publish failure| F14[Store failed publish reason]
    F14 --> F15[Job remains approved for retry publish]

    F8 --> F16[Audit event]
    F10 --> F16
    F12 --> F16
    F15 --> F16
    F16 --> F17[Metrics update + incident runbook path]
```

---

## 6) Data Lineage (From Input to Final Artifacts)

```mermaid
flowchart LR
    I1[Job URL] --> I2[Extraction markdown]
    I2 --> I3[Prompt context assembly]
    I3 --> I4[LLM generation]
    I4 --> I5[Validated artifacts]
    I5 --> I6[(job_outputs\nartifact_versions_json\napproval_snapshot_json\nai_usage_summary_json)]
    I4 --> I8[(job_generation_runs)]

    I6 --> I9[User edits and regenerate]
    I9 --> I6
    I6 --> I10[Approval snapshot]
    I10 --> I11[Connector publish payloads]
    I11 --> I12[External refs in DB]
```

---

## 7) Implementation Mapping (Phase-to-Diagram)

1. Implemented now:
- API/middleware/auth/profile/job/output/connector/history.
- Firecrawl extraction + manual fallback.
- Queue worker plumbing and reliability controls.

2. Next (B13-B16):
- AI orchestrator + OpenAI adapter + validator + generation run tables.
- Generate/regenerate/approve APIs.
- Connector publish adapters and health probes.
- Cost controls, safety guardrails, AI integration tests.

