# Graph Report - C:\Users\priya\Desktop\Ladder\Upwork_automation\backend  (2026-04-30)

## Corpus Check
- Large corpus: 228 files · ~95,987 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 1520 nodes · 3470 edges · 58 communities detected
- Extraction: 61% EXTRACTED · 39% INFERRED · 0% AMBIGUOUS · INFERRED: 1360 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Revision Downgrade|Revision Downgrade]]
- [[_COMMUNITY_Generate Init__|Generate Init__]]
- [[_COMMUNITY_Validate Return|Validate Return]]
- [[_COMMUNITY_Register Get_or_create_job_output|Register Get_or_create_job_output]]
- [[_COMMUNITY_Authresponse Login|Authresponse Login]]
- [[_COMMUNITY_Init__ Airtableclient|Init__ Airtableclient]]
- [[_COMMUNITY_Build Extract_title|Build Extract_title]]
- [[_COMMUNITY_Rollback Gate|Rollback Gate]]
- [[_COMMUNITY_Workflow Validation|Workflow Validation]]
- [[_COMMUNITY_Structural Make|Structural Make]]
- [[_COMMUNITY_Events Probe_firecrawl_job|Events Probe_firecrawl_job]]
- [[_COMMUNITY_Job_explanation_service Workflow_intent_service|Job_explanation_service Workflow_intent_service]]
- [[_COMMUNITY_Init__ Skill_loader|Init__ Skill_loader]]
- [[_COMMUNITY_Jobs Run_uat|Jobs Run_uat]]
- [[_COMMUNITY_Dispatch Basehttpmiddleware|Dispatch Basehttpmiddleware]]
- [[_COMMUNITY_Test_profile Action_catalog|Test_profile Action_catalog]]
- [[_COMMUNITY_Test_jobs Register|Test_jobs Register]]
- [[_COMMUNITY_Build_user_prompt Prompt|Build_user_prompt Prompt]]
- [[_COMMUNITY_B13 Layer|B13 Layer]]
- [[_COMMUNITY_Webhook Node|Webhook Node]]
- [[_COMMUNITY_Prompt_builder Test_ai_prompt_builder|Prompt_builder Test_ai_prompt_builder]]
- [[_COMMUNITY_Trigger_catalog Affiliate|Trigger_catalog Affiliate]]
- [[_COMMUNITY_Refresh_n8n_source_pack Ascii_normalize|Refresh_n8n_source_pack Ascii_normalize]]
- [[_COMMUNITY_Test_outputs Create_job|Test_outputs Create_job]]
- [[_COMMUNITY_Flow Modules|Flow Modules]]
- [[_COMMUNITY_Jobs_dashboard_service Jobs_dashboard|Jobs_dashboard_service Jobs_dashboard]]
- [[_COMMUNITY_Svg_structural_validator Localname|Svg_structural_validator Localname]]
- [[_COMMUNITY_Global_rate_limiter Inmemoryglobalratelimiter|Global_rate_limiter Inmemoryglobalratelimiter]]
- [[_COMMUNITY_Test_projects_api Job_url|Test_projects_api Job_url]]
- [[_COMMUNITY_Usage_service Build_totals_payload|Usage_service Build_totals_payload]]
- [[_COMMUNITY_Test_migration_20260408_cutover Insert_seed_rows|Test_migration_20260408_cutover Insert_seed_rows]]
- [[_COMMUNITY_Svg_visual_validator Parse_vision_payload|Svg_visual_validator Parse_vision_payload]]
- [[_COMMUNITY_Test_migration_20260414_job_explanation Run_alembic|Test_migration_20260414_job_explanation Run_alembic]]
- [[_COMMUNITY_Downgrade Allow|Downgrade Allow]]
- [[_COMMUNITY_Downgrade Add|Downgrade Add]]
- [[_COMMUNITY_Downgrade Add|Downgrade Add]]
- [[_COMMUNITY_Downgrade Add|Downgrade Add]]
- [[_COMMUNITY_Downgrade Update|Downgrade Update]]
- [[_COMMUNITY_Downgrade Add|Downgrade Add]]
- [[_COMMUNITY_Test_migration_20260410_allow_ghl Run_alembic|Test_migration_20260410_allow_ghl Run_alembic]]
- [[_COMMUNITY_Handlers Error_payload|Handlers Error_payload]]
- [[_COMMUNITY_Test_performance_smoke Register|Test_performance_smoke Register]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Router|Router]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]
- [[_COMMUNITY_Init__|Init__]]

## God Nodes (most connected - your core abstractions)
1. `AppException` - 102 edges
2. `User` - 79 edges
3. `AIException` - 52 edges
4. `ProviderGenerateRequest` - 50 edges
5. `AnthropicProviderAdapter` - 40 edges
6. `ProviderGenerateResult` - 37 edges
7. `ArtifactPayload` - 33 edges
8. `_generate_artifacts()` - 28 edges
9. `ProviderName` - 27 edges
10. `get_settings()` - 27 edges

## Surprising Connections (you probably didn't know these)
- `test_routing_defaults_match_blueprint_for_understanding_and_workflow()` --calls--> `get_route_for_task()`  [INFERRED]
  C:\Users\priya\Desktop\Ladder\Upwork_automation\backend\tests\test_ai_foundation.py → C:\Users\priya\Desktop\Ladder\Upwork_automation\backend\app\application\ai\routing.py
- `configure_logging()` --calls--> `get_settings()`  [INFERRED]
  C:\Users\priya\Desktop\Ladder\Upwork_automation\backend\app\infrastructure\logging\setup.py → C:\Users\priya\Desktop\Ladder\Upwork_automation\backend\app\infrastructure\config\settings.py
- `JobClassificationExecution` --uses--> `ProviderName`  [INFERRED]
  C:\Users\priya\Desktop\Ladder\Upwork_automation\backend\app\application\ai\job_classifier_service.py → C:\Users\priya\Desktop\Ladder\Upwork_automation\backend\app\application\ai\contracts.py
- `RouteRule` --uses--> `ProviderName`  [INFERRED]
  C:\Users\priya\Desktop\Ladder\Upwork_automation\backend\app\application\ai\routing.py → C:\Users\priya\Desktop\Ladder\Upwork_automation\backend\app\application\ai\contracts.py
- `DiagramSpecBuildResult` --uses--> `ProviderName`  [INFERRED]
  C:\Users\priya\Desktop\Ladder\Upwork_automation\backend\app\application\output\diagram_spec_service.py → C:\Users\priya\Desktop\Ladder\Upwork_automation\backend\app\application\ai\contracts.py

## Communities

### Community 0 - "Revision Downgrade"
Cohesion: 0.02
Nodes (102): Initial MVP schema.  Revision ID: 20260402_0001 Revises: Create Date: 2026-04-02, Add extraction tracking fields to jobs.  Revision ID: 20260402_0002 Revises: 202, Add AI layer tracking and revision tables.  Revision ID: 20260403_0003 Revises:, Consolidate AI tracking schema into minimal tables.  Revision ID: 20260403_0004, Base, Base, configure_broker(), is_dramatiq_enabled() (+94 more)

### Community 1 - "Generate Init__"
Cohesion: 0.04
Nodes (72): _build_user_prompt(), generate_svg_flowchart(), _strip_preamble(), SvgGenerationError, SvgGenerationResult, AIProviderAdapter, AnthropicProviderAdapter, AIProviderAdapter (+64 more)

### Community 2 - "Validate Return"
Cohesion: 0.04
Nodes (95): ABC, AppException, ArtifactValidator, ArtifactValidator, Validate generated artifact payload and return validation result., ArtifactPayload, ArtifactType, AutomationPlatform (+87 more)

### Community 3 - "Register Get_or_create_job_output"
Cohesion: 0.04
Nodes (96): estimate_call_cost_usd(), get_workflow_example(), _load_examples(), pick_example(), _score_category(), assert_safe_input(), assert_safe_output(), _build_category_index() (+88 more)

### Community 4 - "Authresponse Login"
Cohesion: 0.04
Nodes (102): AuthResponse, login(), LoginRequest, me(), register(), RegisterRequest, _set_session_cookie(), update_me() (+94 more)

### Community 5 - "Init__ Airtableclient"
Cohesion: 0.04
Nodes (87): AirtableClient, Scaffold client for future Airtable publish activation., get_current_user(), connector_status(), google_oauth_callback(), remove_connector(), ConnectorHealthResult, PublishRequest (+79 more)

### Community 6 - "Build Extract_title"
Cohesion: 0.04
Nodes (89): build_horizontal_layout(), HorizontalLayout, LayoutEdge, LayoutNode, _normalize_points(), _route_points(), DiagramConnection, DiagramSpec (+81 more)

### Community 7 - "Rollback Gate"
Cohesion: 0.03
Nodes (63): create(), from_payload(), JobExtractionTask, JobGenerationTask, enqueue_job_extraction(), enqueue_job_generation(), 1. Scope Gate, 2. Operational Gate (+55 more)

### Community 8 - "Workflow Validation"
Cohesion: 0.03
Nodes (60): Add classification and workflow explanation fields to job outputs.  Revision ID:, BaseSettings, Connection placeholder, Expression syntax in `mapper` values, Make.com Blueprint Structure (verified April 2026), metadata block (scenario settings), Module object shape, Router module (+52 more)

### Community 9 - "Structural Make"
Cohesion: 0.06
Nodes (56): Goal, Google Connect UI Backlog, Implementation Later Checklist, Important Architecture Note, Target UX, _extract_bullet_names(), _load_catalog(), Structural validator for GoHighLevel build specs.  GHL does not support JSON wor (+48 more)

### Community 10 - "Events Probe_firecrawl_job"
Cohesion: 0.08
Nodes (44): queries_with_job_url, queries_with_job_url_no_apify_proxy, queries_with_search_url, Results, Temporary Apify Actor Probe, Verdict, log_status_change(), get_job_detail_for_user() (+36 more)

### Community 11 - "Job_explanation_service Workflow_intent_service"
Cohesion: 0.09
Nodes (36): validate_name(), WorkflowIntent, build_fallback_job_explanation(), _build_user_prompt(), _ensure_sentence(), explain_job_markdown(), _extract_budget_or_timeline(), _extract_context_snippet() (+28 more)

### Community 12 - "Init__ Skill_loader"
Cohesion: 0.07
Nodes (10): Background workers package., _build_example_pair(), _build_system_prompt(), _compact_skill_section(), get_skill_content(), list_available_skills(), System prompt and example loader for the Make.com generator.  Single-shot design, _read_example() (+2 more)

### Community 13 - "Jobs Run_uat"
Cohesion: 0.08
Nodes (25): _normalize_enum(), _normalize_optional_text(), Move classification metadata from job_outputs to jobs.  Revision ID: 20260408_00, upgrade(), Sign-off, Step Results, UAT Sign-off, AgentLoopr Backend (+17 more)

### Community 14 - "Dispatch Basehttpmiddleware"
Cohesion: 0.1
Nodes (13): BaseHTTPMiddleware, IdempotencyRecord, InMemoryLoginRateLimiter, RateLimitResult, GlobalRateLimitMiddleware, IdempotencyMiddleware, RequestContextMiddleware, RequestTimeoutMiddleware (+5 more)

### Community 15 - "Test_profile Action_catalog"
Cohesion: 0.1
Nodes (26): AI, Appointments, Communication, Contact, GoHighLevel Workflow Actions (verified April 2026), Internal Tools (control flow — these are step_type variants, not "action" steps), Marketing, Opportunities (+18 more)

### Community 16 - "Test_jobs Register"
Cohesion: 0.17
Nodes (21): _register(), test_duplicate_decision_not_required_for_non_duplicate_job(), test_duplicate_decision_stop_closes_job(), test_extract_job_markdown_cleans_upwork_navigation_noise(), test_extract_job_markdown_cloudflare_challenge_requires_manual_fallback(), test_extract_job_markdown_enriches_missing_title_with_firecrawl_metadata(), test_extract_job_markdown_failure_requires_fallback(), test_extract_job_markdown_preserves_pre_summary_availability_metadata() (+13 more)

### Community 17 - "Build_user_prompt Prompt"
Cohesion: 0.11
Nodes (13): build_context_block(), build_default_generation_prompt(), normalize_optional_section(), build_user_prompt(), Universal Upwork proposal document prompt (doc_v8).  Design intent -------------, build_user_prompt(), Prompt assembler for the GoHighLevel build-spec generator., build_user_prompt() (+5 more)

### Community 18 - "B13 Layer"
Cohesion: 0.13
Nodes (12): 1) Scope and Intent, 2) Phase Decomposition (Mini Phases), AI Layer Remaining Implementation 2026 (Sub-Phase Plan), B13.1 AI Module Skeleton and Core Contracts, B13.2 Provider Adapter Layer (OpenAI First, Extensible), B13.3 Job Understanding Layer, B13.4 Prompt Versioning and Hashing, B13.5 Artifact Generation Planning and Routing (+4 more)

### Community 19 - "Webhook Node"
Cohesion: 0.14
Nodes (13): Access Nested Fields, Common Patterns, Core Variables, Correct Webhook Data Access, CRITICAL: Webhook Data Structure, $env - Environment Variables, Expression Format, $json - Current Node Output (+5 more)

### Community 20 - "Prompt_builder Test_ai_prompt_builder"
Cohesion: 0.24
Nodes (9): _build_personalization_appendix(), build_prompt(), BuiltPrompt, _normalize_optional_text(), test_loom_prompt_enforces_core_flow_and_guardrails(), test_loom_prompt_prioritizes_user_template_before_global_instruction(), test_prompt_builder_appends_user_personalization_layer(), test_prompt_builder_hash_changes_when_context_changes() (+1 more)

### Community 21 - "Trigger_catalog Affiliate"
Cohesion: 0.18
Nodes (10): Affiliate, Appointments, Contact, Courses, Ecommerce, Events, GoHighLevel Workflow Triggers (verified April 2026), Opportunities (+2 more)

### Community 22 - "Refresh_n8n_source_pack Ascii_normalize"
Cohesion: 0.4
Nodes (9): _ascii_normalize(), _build_tags(), _download_bytes(), _download_text(), main(), refresh_examples(), refresh_node_catalog(), refresh_skills_md() (+1 more)

### Community 23 - "Test_outputs Create_job"
Cohesion: 0.5
Nodes (8): _create_job(), _register(), test_job_output_create_get_update_and_edit_log(), test_job_output_requires_auth(), test_patch_output_rejects_removed_classification_fields(), test_regenerate_payload_mismatch_validation(), test_regenerate_updates_only_target_output(), test_workflow_json_structure_validation()

### Community 24 - "Flow Modules"
Cohesion: 0.22
Nodes (8): Built-in control flow modules, Common Make.com Modules (reference), Communication, Data / CRM / Other, Google, HTTP, Important rules, Triggers (always the first module in `flow`)

### Community 25 - "Jobs_dashboard_service Jobs_dashboard"
Cohesion: 0.48
Nodes (6): jobs_dashboard(), get_jobs_dashboard_summary(), _round_cost(), _to_float(), _to_int(), _window_days()

### Community 26 - "Svg_structural_validator Localname"
Cohesion: 0.48
Nodes (6): _localname(), _parse_float(), _parse_viewbox(), Fast structural checks on LLM-produced SVG.      Catches issues before we spend, SvgStructuralResult, validate_svg_structure()

### Community 27 - "Global_rate_limiter Inmemoryglobalratelimiter"
Cohesion: 0.38
Nodes (2): InMemoryGlobalRateLimiter, RateLimitResult

### Community 28 - "Test_projects_api Job_url"
Cohesion: 0.57
Nodes (6): _job_url(), _login(), _register(), test_jobs_can_be_assigned_to_projects_and_filtered(), test_projects_create_and_list_for_current_user(), test_user_cannot_assign_job_to_other_users_project()

### Community 29 - "Usage_service Build_totals_payload"
Cohesion: 0.53
Nodes (5): _build_totals_payload(), get_usage_summary(), _to_float(), _to_int(), usage_summary()

### Community 30 - "Test_migration_20260408_cutover Insert_seed_rows"
Cohesion: 0.73
Nodes (5): _insert_seed_rows(), _run_alembic(), _table_columns(), test_upgrade_backfills_jobs_and_drops_classification_columns_from_job_outputs(), test_upgrade_constraints_and_downgrade_round_trip_backfill()

### Community 31 - "Svg_visual_validator Parse_vision_payload"
Cohesion: 0.6
Nodes (4): _parse_vision_payload(), Vision-based quality check via gpt-5.4-mini.      Returns pass=True if the image, SvgVisualResult, validate_svg_visual()

### Community 32 - "Test_migration_20260414_job_explanation Run_alembic"
Cohesion: 0.7
Nodes (4): _run_alembic(), _seed_job(), _table_columns(), test_migration_0012_adds_and_removes_job_explanation_column()

### Community 33 - "Downgrade Allow"
Cohesion: 0.5
Nodes (1): Allow ghl in jobs.automation_platform check constraint.  Revision ID: 20260410_0

### Community 34 - "Downgrade Add"
Cohesion: 0.5
Nodes (1): Add not_sent to jobs outcome check constraint.  Revision ID: 20260410_0008 Revis

### Community 35 - "Downgrade Add"
Cohesion: 0.5
Nodes (1): Add jobs submission index for dashboard queries.  Revision ID: 20260412_0009 Rev

### Community 36 - "Downgrade Add"
Cohesion: 0.5
Nodes (1): Add projects table and optional jobs.project_id foreign key.  Revision ID: 20260

### Community 37 - "Downgrade Update"
Cohesion: 0.5
Nodes (1): Update jobs outcome check constraint to allow hired, remove legacy values.  Revi

### Community 38 - "Downgrade Add"
Cohesion: 0.5
Nodes (1): Add job explanation field to jobs.  Revision ID: 20260414_0012 Revises: 20260412

### Community 39 - "Test_migration_20260410_allow_ghl Run_alembic"
Cohesion: 0.83
Nodes (3): _run_alembic(), _seed_job(), test_upgrade_0007_allows_ghl_automation_platform()

### Community 40 - "Handlers Error_payload"
Cohesion: 0.67
Nodes (0): 

### Community 41 - "Test_performance_smoke Register"
Cohesion: 1.0
Nodes (2): _register(), test_generation_pipeline_smoke_performance()

### Community 42 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 43 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 49 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 50 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Router"
Cohesion: 1.0
Nodes (0): 

### Community 55 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 56 - "Init__"
Cohesion: 1.0
Nodes (0): 

### Community 57 - "Init__"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **246 isolated node(s):** `Initial MVP schema.  Revision ID: 20260402_0001 Revises: Create Date: 2026-04-02`, `Add extraction tracking fields to jobs.  Revision ID: 20260402_0002 Revises: 202`, `Add AI layer tracking and revision tables.  Revision ID: 20260403_0003 Revises:`, `Consolidate AI tracking schema into minimal tables.  Revision ID: 20260403_0004`, `Add classification and workflow explanation fields to job outputs.  Revision ID:` (+241 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Router`** (1 nodes): `router.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init__`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `Authresponse Login` to `Revision Downgrade`, `Init__ Airtableclient`, `Build Extract_title`, `Rollback Gate`, `Workflow Validation`, `Structural Make`, `Events Probe_firecrawl_job`, `Jobs Run_uat`, `Test_profile Action_catalog`, `B13 Layer`, `Webhook Node`, `Trigger_catalog Affiliate`, `Flow Modules`?**
  _High betweenness centrality (0.143) - this node is a cross-community bridge._
- **Why does `AppException` connect `Init__ Airtableclient` to `Revision Downgrade`, `Validate Return`, `Register Get_or_create_job_output`, `Authresponse Login`, `Build Extract_title`, `Rollback Gate`, `Events Probe_firecrawl_job`, `Job_explanation_service Workflow_intent_service`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Init__ Airtableclient` to `Generate Init__`, `Validate Return`, `Register Get_or_create_job_output`, `Build Extract_title`, `Workflow Validation`, `Structural Make`, `Events Probe_firecrawl_job`, `Dispatch Basehttpmiddleware`, `Svg_visual_validator Parse_vision_payload`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Are the 99 inferred relationships involving `AppException` (e.g. with `AIErrorCode` and `AIException`) actually correct?**
  _`AppException` has 99 INFERRED edges - model-reasoned connections that need verification._
- **Are the 62 inferred relationships involving `User` (e.g. with `ExtractionQualityAssessment` and `Base`) actually correct?**
  _`User` has 62 INFERRED edges - model-reasoned connections that need verification._
- **Are the 49 inferred relationships involving `AIException` (e.g. with `AppException` and `JobClassificationExecution`) actually correct?**
  _`AIException` has 49 INFERRED edges - model-reasoned connections that need verification._
- **Are the 48 inferred relationships involving `ProviderGenerateRequest` (e.g. with `JobClassificationExecution` and `JobExplanationExecution`) actually correct?**
  _`ProviderGenerateRequest` has 48 INFERRED edges - model-reasoned connections that need verification._