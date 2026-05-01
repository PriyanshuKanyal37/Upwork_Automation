<!-- converted from AgentLoopr_Upwork_PRD_v2.docx -->



# 1. Problem Statement
Agent Loopr applies for automation jobs on Upwork without reviews or social proof. Generic proposals — paragraphs claiming 'I can do this' — lose to profiles with 50+ reviews every time.

The only way to compete without reviews is to show work before being hired. This tool generates a complete, personalised proposal package for every automation job post so that by the time the client reads the proposal, they have already seen a working workflow and a structured doc built specifically for their use case — prepared before the conversation even started.

# 2. Product Vision

The client experience: Agent Loopr already started working before we spoke. The internal experience: paste, do a quick clarification chat with the AI, click generate, record a Loom under 5 minutes, send.

# 3. Users
Four users. Each has a personal PIN to log in — no passwords, no accounts, just a simple 4-digit PIN set at first launch.


All Airtable logs capture which user generated the run. History view is filterable by user.

# 4. Core User Flow


# 5. Workflow Count Logic
The agent decides how many workflows to generate based on how specific or generic the job post is. It is not a fixed number. Maximum is 5.


The agent surfaces its proposed count during the clarification chat so the user can override before generation. It never pads workflows to fill a number — if 2 are right, it generates 2.

# 6. Output Package
Every run produces four outputs in priority order. The Google Doc is the centrepiece — everything else supports it.


Auto-created in Agent Loopr's Google Drive. 1–2 pages maximum. Shared as a view link embedded in the Upwork proposal. This is a tight, scannable document — not a report.

### Document Structure
- Problem summary — their need restated in sharper language than they used. 2–3 sentences.
- Our approach — the strategic layer: what we're building and why in this order. 3–5 sentences.
- Workflow breakdown — each workflow named and described in 1–2 sentences of plain English.
- Delivery timeline — phase-by-phase, concise.
- Advanced ideas — CONDITIONAL. Only included if the job post has clear expansion potential. Not every doc gets this section. When included: 2–3 ideas max, framed as 'where this goes next.'

Style rules: Short sentences. No em-dashes. No agency jargon. Direct. Reads like a senior engineer's notes, not a pitch deck.


Generated in parallel. Each workflow is standalone and importable. Platform is detected from the job post — defaults to n8n if unspecified.

### Supported Platforms

### Vague Job Post — Category Defaults
Category defaults are only used when no specific tools are mentioned in the job post. They are surfaced in the clarification chat for user confirmation before generation — never applied silently.


### Workflow Validation
Every generated JSON passes a structural validation step before being shown to the user — nodes connected, required fields present, importable. Failed validations regenerate automatically, not surfaced to the user.

### MCP & Advanced Tooling
If the job post references MCP servers, AI agents, or tool orchestration, the agent additionally generates: MCP server config files, LangGraph agent definitions, tool use schemas for Claude API, FastAPI/Express wrapper stubs. These are included as downloadable files alongside the workflows.


The Loom must be under 5 minutes. The script is the spoken layer — it expands on the doc and the workflows, it does not read them out. The doc is the visual anchor on screen. The script is what the user says while pointing at it.

### Script Structure — Fixed
- Opening — Broad summary of the client's need in 2–3 sentences. Then: 'This is right up my alley — I can definitely get this done for you, and here's why.'
- Credibility — Spoken, not written. No name. Reference: years doing AI automation / the relevant discipline as a consultant. Mention working with SME companies. Cue: '[Open agentloopr.com]' — walk through the site briefly, mention role as senior consultant, connect what they do with what the client needs.
- Bridge — 'I went ahead and prepared a walkthrough doc and a sample workflow for you specifically.'
- Doc walkthrough — Walk through each section of the Google Doc. 1–3 spoken sentences per section that add context beyond what is written. Do not read the doc aloud.
- Workflow demo — Cue: '[Switch to n8n / open workflow]'. For each workflow: one sentence on what it does and why it matters for the client's situation.
- Upsell beat — CONDITIONAL. Only included if the doc has an Advanced Ideas section. 30–45 seconds max. Frame as 'a few ideas on where this could go next' — not a sales pitch.
- CTA — Clean, direct close. 'Happy to answer any questions on chat or jump on a call — just drop your availability in the chat and we'll get something scheduled.'

Tone: Confident, conversational, technically credible. Senior engineer on a client call — not a salesperson.


Full proposal text, copy-paste ready. Under 150 words. Persona-neutral — no personal name. Agent Loopr brand voice.



# 7. Per-Output Edit & Feedback Loop
After generation, each of the four output cards has an inline edit control. This allows targeted regeneration without redoing everything.

### How It Works
- Each output card has a collapsed 'Request edit' section below it.
- User types what they want changed — e.g. 'Make the approach section more technical' or 'Add a workflow for email follow-up.'
- Only that output regenerates. The other three remain untouched.
- Edit request and regenerated output are both logged to Airtable against the original run ID.
- User can edit any output multiple times. Each edit is a separate log entry.

This prevents wasted API calls and keeps the review loop fast. The user should be able to go from raw output to Loom-ready in under 2 minutes of reviewing.

# 8. History View
A dedicated History tab in the UI pulls from Airtable and shows all past runs. Filterable by user and date range.

### Table Columns

Clicking any row expands to show the full output package from that run — doc link, workflow list, proposal text, Loom script. Users can re-copy any output from the history view.

# 9. Agent Architecture
The system is a single agentic loop. Claude is the orchestrator — it reads the job post, runs the clarification chat, then calls tools in parallel to produce all outputs. The frontend is React. The backend is a lightweight Node/Express server that manages Claude API calls, Google Docs API, n8n API, and Airtable writes.

### Model Routing — Cost Optimisation
The system is model-agnostic. Model names are passed as config — not hardcoded. Default stack below. Gemini 2.0 Flash is a recommended A/B test for workflow JSON generation specifically (faster, cheaper, strong structured output). Do not lock to any single provider.


### Parallel Generation
Once the user approves the plan, all workflow JSONs are generated simultaneously — not sequentially. Google Doc, Loom script, and proposal are generated in parallel with the workflows. Target: all outputs ready within 90–120 seconds of clicking Generate.

### Tool Inventory
The Claude agent has access to the following tools during a generation run:

- classify_job(job_post) → { category, tools[], platform, specificity_score }
- decide_workflow_count(specificity_score, job_post) → number (1–5)
- generate_workflow(platform, use_case, tools[], name) → validated JSON
- validate_workflow(json) → { pass: bool, errors: [] }
- create_google_doc(title, sections[]) → doc_url
- import_to_n8n(workflow_json) → { success: bool, workflow_id }
- log_to_airtable(run_data) → run_id
- update_airtable_edit(run_id, output_type, edit_request, new_output) → void
- generate_proposal(job_post, doc_url, template_id) → proposal_text

# 10. Frontend Specification
React. Single-page app. Four screens. Clean, functional — this is an internal tool, not a client-facing product. Speed and clarity over design.

### Screen 0 — PIN Login
- Name selector: four avatars/buttons (Shivam, Vansh, Priyanshu, Ayush)
- 4-digit PIN input appears after name selection
- PINs set at first launch per user, stored locally (no server auth needed)
- Session persists for the day — no re-login per run

### Screen 1 — Input
- Large text area: 'Paste job post here'
- Smaller text area below: 'Your notes / thoughts on this job (optional)' — feeds into clarification chat context
- 'Analyse Job' button

### Screen 2 — Clarification Chat
- Chat interface — AI's initial read displayed first
- AI surfaces: detected tools, job category, proposed workflow count + names, any questions
- User types replies to correct or add context — max 3–4 exchanges
- Right panel: confirmed plan summary (tools, platform, workflow names, doc structure outline)
- 'Generate Package' button unlocks after user confirms the plan

### Screen 3 — Output Dashboard
- Google Doc card: link (opens new tab), doc title, page count indicator
- Workflow cards (one per workflow): name, plain-English description, platform badge, 'Download JSON' button, 'Import to n8n' button
- Loom Script panel: full script with labelled section markers, copy button, estimated duration indicator
- Proposal Text panel: full proposal with [LOOM_LINK] and [DOC_LINK] placeholders highlighted, copy button
- Each card has a collapsed 'Request edit' field below it (see Section 7)
- Airtable log confirmation badge: 'Logged ✓'
- 'Start New Application' button

### Screen 4 — History
- Accessible from top nav at all times
- Table view of all past runs pulled from Airtable
- Filter by: user, date range, platform, outcome
- Click any row to expand and re-view full output package
- Outcome dropdown editable inline — user updates after sending/hearing back

# 11. Airtable Schema
Base ID: app1FlYZi49y5tnEr. Create a new table: Upwork Applications.


# 12. Constraints & Non-Negotiables


# 13. Build Order (for Vansh)
Build and test each phase independently before moving to the next.


# 14. Open Items — Action Required


| AGENT LOOPR
Upwork Proposal Automation System
Product Requirements Document  |  v2.0
Internal  —  Builder: Vansh  |  Owner: Shivam |
| --- |
| Status | Ready for Development |
| --- | --- |
| Version | v2.0 — incorporates feedback from Shivam |
| Users | Shivam, Vansh, Priyanshu, Ayush (PIN-protected) |
| Brand | Agent Loopr |
| Scope | Automation jobs only — n8n, Make, Zapier, LangChain/LangGraph |
| Target volume | Up to 25 applications/day |
| Est. API cost | ~$8–12/day at 25 apps with smart model routing |
| Last updated | March 2026 |
| "Paste a job post. Get a tight Google Doc, the right number of workflows, and a Loom script — in under 3 minutes. Record. Send. Convert." |
| --- |
| User | Role | PIN |
| --- | --- | --- |
| Shivam | Product owner, primary applicant | Set at first launch |
| Vansh | Builder + applicant | Set at first launch |
| Priyanshu | Applicant | Set at first launch |
| Ayush | Applicant | Set at first launch |
| Step | Action | Detail |
| --- | --- | --- |
| 01 | PIN login | User selects their name and enters PIN. Simple selector screen. |
| 02 | Paste job post | Large text area for the full job post. Optional second field: 'Your notes on this job' — user can mention tools, approach, or anything they want the AI to factor in. |
| 03 | Clarification chat | AI reads the post and opens a short back-and-forth. It surfaces: detected tools, inferred category, proposed workflow count and names, any ambiguities. Max 3–4 exchanges. User can correct, add context, or approve as-is. |
| 04 | User approves plan | User reviews the AI's confirmed plan (tools, workflow count, approach) and clicks 'Generate'. Nothing is built before this step. |
| 05 | Agent runs (parallel) | Workflows generated simultaneously. Google Doc written. Loom script drafted. Upwork proposal generated. Airtable log created. Target: all outputs ready in 90–120 seconds. |
| 06 | Review + edit | Output dashboard shows all four outputs. Each has an inline 'Request edit' field — user types what to change, that specific output regenerates without touching the others. |
| 07 | Optional: n8n import | One-click push of any workflow JSON to the live n8n instance via API. Or download manually. |
| 08 | Record Loom | User opens n8n, uses the Loom script panel as a teleprompter. Target: under 5 minutes. |
| 09 | Send proposal | Copy-paste proposal into Upwork. Add Loom link. Submit. Update outcome in History tab. |
| Job Post Type | Workflow Count | Example |
| --- | --- | --- |
| Highly specific — one clear task | 1 | "Set up a webhook in n8n to push Typeform responses into Notion" |
| Specific — defined scope, one system | 2–3 | "Automate our HubSpot lead flow — capture, assign, notify team" |
| Moderately generic — multiple implied flows | 3–5 | "We need automation across our sales and onboarding process" |
| Very generic — broad problem statement | 4–5 | "Help us automate our business operations using AI tools" |
| Output 1 — Google Doc (Execution Plan)  [HIGHEST PRIORITY] |
| --- |
| Output 2 — Workflow JSONs (1–5 depending on job post) |
| --- |
| Platform | Output Format | Import Method |
| --- | --- | --- |
| n8n | JSON export | Auto-import via n8n API OR manual download — user chooses per workflow |
| Make / Integromat | JSON export | Manual import |
| Zapier | Zap definition export | Manual setup |
| LangChain / LangGraph | Python files + graph definition | Download, open in Cursor or IDE |
| Category | Default Stack |
| --- | --- |
| CRM automation | HubSpot + Gmail + Slack + n8n |
| Lead generation | Clay / Apollo + HubSpot + Gmail + n8n |
| E-commerce automation | Shopify + Klaviyo + Slack + n8n |
| AI agent / chatbot | OpenAI API + LangChain + Pinecone + FastAPI |
| Data pipeline | Airtable + Google Sheets + Postgres + n8n |
| Document automation | Google Docs API + PDF tools + n8n |
| Social media | Buffer + OpenAI + n8n |
| Support automation | Intercom / Zendesk + OpenAI + n8n |
| Output 3 — Loom Script / Talk Track |
| --- |
| Output 4 — Upwork Proposal Text |
| --- |
| Must Include | Must Avoid |
| --- | --- |
| Loom link placeholder [LOOM_LINK] | Em-dashes |
| Google Doc link placeholder [DOC_LINK] | Agency jargon |
| Their specific tools/use case mirrored back | Personal name references |
| Workflow count mentioned naturally | Generic capability claims |
| Clear CTA — chat or call availability | Anything over 150 words |
| ACTION REQUIRED — Vansh, before building Output 4
Do not build the proposal generator without Shivam's proposal text templates. These templates define the structural logic and voice the generator must replicate. Request them from Shivam before starting Phase 4. |
| --- |
| Field | Type | Notes |
| --- | --- | --- |
| Date | Timestamp | Auto-logged on generation |
| User | Dropdown | Shivam / Vansh / Priyanshu / Ayush |
| Job snippet | Text | First 200 chars of job post |
| Platform | Tag | n8n / Make / Zapier / LangChain |
| Workflow count | Number | How many workflows were generated |
| Google Doc | Link | Opens doc in new tab |
| Outcome | Dropdown | Sent / Replied / Interview / Closed / No reply |
| Edit count | Number | How many post-generation edits were made |
| Notes | Free text | Manually added by user |
| Task | Default Model | Rationale |
| --- | --- | --- |
| Job post classification | Claude Haiku | Fast, cheap, binary output |
| Clarification chat | Claude Haiku | Conversational, low stakes |
| Workflow JSON generation (x1–5) | Claude Sonnet 4 | Technical depth required — A/B test Gemini 2.0 Flash here |
| Google Doc content | Claude Sonnet 4 | Writing quality critical |
| Loom script generation | Claude Sonnet 4 | Tone and structure critical |
| Proposal text generation | Claude Sonnet 4 | Conversion quality matters |
| Workflow JSON validation | Claude Haiku | Structural check only |
| Per-output edit regeneration | Same model as original | Consistency in voice/format |
| run_id | Auto-generated UUID |
| --- | --- |
| timestamp | Date + time of generation |
| user | Shivam / Vansh / Priyanshu / Ayush |
| job_snippet | First 200 chars of job post |
| detected_tools | Comma-separated string |
| job_category | Classified category (e.g. CRM Automation) |
| platform | n8n / Make / Zapier / LangChain |
| workflow_count | Number generated (1–5) |
| workflow_names | Comma-separated workflow names |
| google_doc_url | Link to generated doc |
| proposal_text | Full proposal text stored |
| edit_count | Number of post-gen edits made |
| edit_log | JSON array of {output_type, request, timestamp} |
| outcome | Sent / Replied / Interview / Closed / No reply |
| notes | Free text, manually added |
| Constraint | Rule |
| --- | --- |
| Generation trigger | Nothing generates before user approves the clarification chat plan. No exceptions. |
| Workflow count | Agent decides 1–5 based on job specificity. Never pads. Never exceeds 5. |
| Google Doc length | 1–2 pages maximum. If it's longer, the agent is doing it wrong. |
| Loom target duration | Under 5 minutes. Script must be calibrated to this. |
| Upsell section | Conditional only — included when the job post has clear expansion potential. Not default. |
| Category defaults | Only triggered when no tools mentioned. Always confirmed in clarification chat before use. |
| Proposal templates | Vansh must get templates from Shivam before building Output 4. |
| Branding | All outputs under Agent Loopr. No personal names. |
| Writing style | No em-dashes. No jargon. Short sentences. Every output, every time. |
| Model architecture | Model-agnostic. No hardcoded provider. Config-driven. |
| Cost ceiling | Stay under $15/day at 25 applications. Haiku for cheap steps. |
| Scope | Automation jobs only. No dev/code jobs in this version. |
| Phase | Name | Deliverable | Est. |
| --- | --- | --- | --- |
| 1 | Auth + UI shell | PIN login, 4-user selector, Screen 1 + 2 (input + clarification chat), Claude API wired | 3–4 days |
| 2 | Workflow generation | n8n JSON generation, workflow count logic, validation loop, download working | 3–4 days |
| 3 | Google Docs integration | Auto-create doc in Drive, all sections populated from agent output, link returned to UI | 2–3 days |
| 4 | Loom script + proposal | Script generator (5-part structure), proposal generator — REQUIRES Shivam's templates | 2–3 days |
| 5 | Airtable logging | Write run record on every generation, all fields mapped, edit log working | 1–2 days |
| 6 | Edit loop | Per-output edit field, targeted regeneration, edit logged to Airtable | 1–2 days |
| 7 | History view | Screen 4 — pulls from Airtable, filters, row expand, inline outcome update | 2 days |
| 8 | n8n auto-import | Push workflow to live n8n instance via API, optional per workflow | 1–2 days |
| 9 | Make / Zapier / LangChain | Extend workflow generator to additional platforms | 3–4 days |
| 10 | Polish + cost tuning | Gemini A/B test for workflow gen, Haiku routing audit, error handling, UX refinements | 2 days |
| Item | Owner | Needed By |
| --- | --- | --- |
| Proposal text templates | Shivam → Vansh | Before Phase 4 |
| Google Drive folder + service account access | Shivam → Vansh | Before Phase 3 |
| n8n API key for auto-import | Shivam → Vansh | Before Phase 8 |
| Airtable API key for app1FlYZi49y5tnEr | Shivam → Vansh | Before Phase 5 |
| Agent Loopr website URL confirmation | Shivam | Before Phase 4 |
| Make / Zapier priority at launch vs later | Shivam decision | Before Phase 9 |
| Gemini API key (for A/B test in Phase 10) | Shivam → Vansh | Before Phase 10 |
| Agent Loopr
Upwork Proposal Automation System  —  PRD v2.0
Questions on any section: Shivam has full context. |
| --- |