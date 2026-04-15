import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from pytest import MonkeyPatch

from app.application.ai.contracts import ProviderGenerateRequest, ProviderGenerateResult, ProviderName
from app.application.ai.contracts import ArtifactPayload, ArtifactType
from app.application.ai.costing import estimate_call_cost_usd
from app.application.ai.providers.base import AIProviderAdapter


class _FakeProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        task = str(request.metadata.get("task", ""))
        artifact_type = str(request.metadata.get("artifact_type", ""))
        if task == "job_understanding":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=(
                    '{"summary_short":"Automation role","deliverables_required":["proposal","workflow","loom_script","doc"],'
                    '"screening_questions":[],"automation_platform_preference":"n8n","constraints":{},'
                    '"extraction_confidence":"high","missing_fields":[]}'
                ),
                input_tokens=30,
                output_tokens=20,
                latency_ms=50,
            )

        if artifact_type == "workflow":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=json.dumps(
                    {
                        "nodes": [{"id": "1", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger"}],
                        "connections": {},
                    }
                ),
                input_tokens=100,
                output_tokens=40,
                latency_ms=80,
            )

        if artifact_type == "proposal":
            text = (
                "Regenerated proposal text with concise delivery plan."
                if "shorter" in request.prompt.lower()
                else "Initial proposal text with execution plan and milestones."
            )
        elif artifact_type == "loom_script":
            text = "Loom script with intro, proof, execution plan, and CTA."
        elif artifact_type == "doc":
            text = "Document markdown with summary and implementation details."
        else:
            text = "Generated artifact content with adequate detail."

        return ProviderGenerateResult(
            provider=ProviderName.OPENAI,
            model_name=request.model_name,
            output_text=text,
            input_tokens=90,
            output_tokens=35,
            latency_ms=70,
        )


class _CostTrackingProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        task = str(request.metadata.get("task", ""))
        artifact_type = str(request.metadata.get("artifact_type", ""))
        if task == "job_understanding":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=(
                    '{"summary_short":"Automation role","deliverables_required":["proposal"],'
                    '"screening_questions":[],"automation_platform_preference":"n8n","constraints":{},'
                    '"extraction_confidence":"high","missing_fields":[]}'
                ),
                input_tokens=100,
                output_tokens=50,
                latency_ms=25,
            )

        if artifact_type == "proposal":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text="Proposal content with delivery milestones.",
                input_tokens=10,
                output_tokens=5,
                latency_ms=15,
            )

        raise AssertionError(f"Unexpected artifact_type in cost test: {artifact_type}")


class _FailingWorkflowProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        task = str(request.metadata.get("task", ""))
        artifact_type = str(request.metadata.get("artifact_type", ""))
        if task == "job_understanding":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=(
                    '{"summary_short":"Automation role","deliverables_required":["workflow"],'
                    '"screening_questions":[],"automation_platform_preference":"n8n","constraints":{},'
                    '"extraction_confidence":"high","missing_fields":[]}'
                ),
                input_tokens=30,
                output_tokens=20,
                latency_ms=20,
            )

        if artifact_type == "workflow":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text="not-valid-json",
                input_tokens=40,
                output_tokens=10,
                latency_ms=20,
            )

        raise AssertionError(f"Unexpected artifact_type in failure test: {artifact_type}")


class _CapturePromptProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI
    seen_prompts: list[str] = []

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        self.seen_prompts.append(request.prompt)
        task = str(request.metadata.get("task", ""))
        artifact_type = str(request.metadata.get("artifact_type", ""))
        if task == "job_understanding":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=(
                    '{"summary_short":"Automation role","deliverables_required":["proposal"],'
                    '"screening_questions":[],"automation_platform_preference":"n8n","constraints":{},'
                    '"extraction_confidence":"high","missing_fields":[]}'
                ),
                input_tokens=30,
                output_tokens=20,
                latency_ms=50,
            )

        if artifact_type == "proposal":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text="Personalized proposal output.",
                input_tokens=60,
                output_tokens=20,
                latency_ms=50,
            )

        raise AssertionError(f"Unexpected artifact_type in capture test: {artifact_type}")


class _CrossArtifactCaptureProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI
    prompts_by_artifact: dict[str, str] = {}

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        task = str(request.metadata.get("task", ""))
        artifact_type = str(request.metadata.get("artifact_type", ""))

        if task == "job_understanding":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=(
                    '{"summary_short":"Automation role","deliverables_required":["workflow","doc","loom_script","proposal"],'
                    '"screening_questions":[],"automation_platform_preference":"n8n","constraints":{},'
                    '"extraction_confidence":"high","missing_fields":[]}'
                ),
                input_tokens=40,
                output_tokens=20,
                latency_ms=30,
            )

        self.prompts_by_artifact[artifact_type] = request.prompt

        if artifact_type == "workflow":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=json.dumps(
                    {
                        "nodes": [
                            {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook"},
                            {"id": "2", "name": "CRM Update", "type": "n8n-nodes-base.httpRequest"},
                            {"id": "3", "name": "Slack Notify", "type": "n8n-nodes-base.slack"},
                        ],
                        "connections": {
                            "Webhook": {"main": [[{"node": "CRM Update", "type": "main", "index": 0}]]},
                            "CRM Update": {"main": [[{"node": "Slack Notify", "type": "main", "index": 0}]]},
                        },
                    }
                ),
                input_tokens=80,
                output_tokens=30,
                latency_ms=60,
            )

        if artifact_type == "doc":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=(
                    "# CRM Automation Execution Plan\n"
                    "## Executive Summary\n"
                    "Implement lead qualification and handoff automation."
                ),
                input_tokens=70,
                output_tokens=25,
                latency_ms=55,
            )

        if artifact_type == "loom_script":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=(
                    "Loom script: Explain webhook intake, CRM updates, and slack alerts in 90 seconds."
                ),
                input_tokens=60,
                output_tokens=20,
                latency_ms=45,
            )

        if artifact_type == "proposal":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text="Final proposal text.",
                input_tokens=50,
                output_tokens=20,
                latency_ms=40,
            )

        raise AssertionError(f"Unexpected artifact_type in cross-artifact test: {artifact_type}")


class _LoomTemplateCaptureProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI
    loom_prompt: str | None = None

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        task = str(request.metadata.get("task", ""))
        artifact_type = str(request.metadata.get("artifact_type", ""))
        if task == "job_understanding":
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=(
                    '{"summary_short":"Automation role","deliverables_required":["loom_script"],'
                    '"screening_questions":[],"automation_platform_preference":"n8n","constraints":{},'
                    '"extraction_confidence":"high","missing_fields":[]}'
                ),
                input_tokens=30,
                output_tokens=20,
                latency_ms=30,
            )
        if artifact_type == "loom_script":
            self.loom_prompt = request.prompt
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text="Speaking guide with practical cues.",
                input_tokens=50,
                output_tokens=20,
                latency_ms=30,
            )
        raise AssertionError(f"Unexpected artifact_type in loom-template capture test: {artifact_type}")


class _WorkflowOnlyUnderstandingProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        task = str(request.metadata.get("task", ""))
        if task != "job_understanding":
            raise AssertionError(f"Unexpected task in workflow-only provider: {task}")
        return ProviderGenerateResult(
            provider=ProviderName.OPENAI,
            model_name=request.model_name,
            output_text=(
                '{"summary_short":"Automation role","deliverables_required":["workflow"],'
                '"screening_questions":[],"automation_platform_preference":"unknown","constraints":{},'
                '"extraction_confidence":"high","missing_fields":[]}'
            ),
            input_tokens=20,
            output_tokens=10,
            latency_ms=20,
        )


def _register(client: TestClient, name: str) -> None:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 201


def _create_ready_job(client: TestClient) -> str:
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": f"https://www.upwork.com/jobs/flow~{uuid4().hex}"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]
    manual = client.post(
        f"/api/v1/jobs/{job_id}/manual-markdown",
        json={"job_markdown": "Need n8n automation and proposal support for CRM workflows."},
    )
    assert manual.status_code == 200
    return job_id


def test_generate_runs_inline_and_persists_outputs(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _register(client, "GenUserA")
    job_id = _create_ready_job(client)

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import jobs as jobs_api

    monkeypatch.setattr(jobs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(orchestrator_service, "build_provider_adapter", lambda *_: _FakeProvider())
    monkeypatch.setattr(
        job_understanding_service,
        "build_provider_adapter",
        lambda *_: _FakeProvider(),
    )

    generate = client.post(f"/api/v1/jobs/{job_id}/generate", json={"queue_if_available": False})
    assert generate.status_code == 200
    payload = generate.json()
    assert payload["queued"] is False
    assert payload["run"]["status"] == "success"

    runs = client.get(f"/api/v1/jobs/{job_id}/generation-runs")
    assert runs.status_code == 200
    runs_payload = runs.json()
    assert runs_payload["count"] >= 1
    assert runs_payload["runs"][0]["status"] == "success"

    outputs = client.get(f"/api/v1/jobs/{job_id}/outputs")
    assert outputs.status_code == 200
    output_payload = outputs.json()["output"]
    assert output_payload["proposal_text"] is not None
    assert output_payload["google_doc_markdown"] is not None
    assert len(output_payload["workflow_jsons"]) == 1
    assert len(output_payload["artifact_versions_json"]) >= 3

    job_detail = client.get(f"/api/v1/jobs/{job_id}")
    assert job_detail.status_code == 200
    job_payload = job_detail.json()["job"]
    assert job_payload["job_type"] == "automation"
    assert job_payload["automation_platform"] == "n8n"
    assert job_payload["classification_confidence"] in {"high", "medium", "low"}
    assert job_payload["classification_reasoning"] is not None
    assert job_payload["classified_at"] is not None


def test_targeted_regenerate_and_approve_flow(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _register(client, "GenUserB")
    job_id = _create_ready_job(client)

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import jobs as jobs_api
    from app.interfaces.api.v1 import outputs as outputs_api

    monkeypatch.setattr(jobs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(outputs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(orchestrator_service, "build_provider_adapter", lambda *_: _FakeProvider())
    monkeypatch.setattr(
        job_understanding_service,
        "build_provider_adapter",
        lambda *_: _FakeProvider(),
    )

    first_generate = client.post(f"/api/v1/jobs/{job_id}/generate", json={"queue_if_available": False})
    assert first_generate.status_code == 200

    regenerate = client.post(
        f"/api/v1/jobs/{job_id}/outputs/proposal/regenerate",
        json={"instruction": "Make it shorter.", "queue_if_available": False},
    )
    assert regenerate.status_code == 200
    regen_payload = regenerate.json()
    assert regen_payload["queued"] is False
    assert regen_payload["regenerated_output"] == "proposal"
    assert regen_payload["run"]["run_type"] == "regenerate"
    assert "Regenerated proposal text" in regen_payload["output"]["proposal_text"]

    approve = client.post(f"/api/v1/jobs/{job_id}/approve", json={"notes": "Approved latest outputs"})
    assert approve.status_code == 200
    approve_payload = approve.json()
    assert approve_payload["job"]["status"] == "ready"
    assert approve_payload["job"]["plan_approved"] is True
    assert approve_payload["output"]["approval_snapshot_json"]["approved_revision_map"] != {}


def test_targeted_workflow_regenerate_returns_success(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _register(client, "GenUserWorkflowRegen")
    job_id = _create_ready_job(client)

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import outputs as outputs_api

    monkeypatch.setattr(outputs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(orchestrator_service, "build_provider_adapter", lambda *_: _FakeProvider())
    monkeypatch.setattr(
        job_understanding_service,
        "build_provider_adapter",
        lambda *_: _FakeProvider(),
    )

    regenerate = client.post(
        f"/api/v1/jobs/{job_id}/outputs/workflow/regenerate",
        json={"instruction": "Regenerate workflow with clearer branching", "queue_if_available": False},
    )
    assert regenerate.status_code == 200
    payload = regenerate.json()
    assert payload["queued"] is False
    assert payload["regenerated_output"] == "workflow"
    assert payload["run"]["run_type"] == "regenerate"
    assert payload["output"]["workflow_jsons"] is not None
    assert len(payload["output"]["workflow_jsons"]) >= 1


def test_generation_cost_includes_understanding_call(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _register(client, "GenUsageA")
    job_id = _create_ready_job(client)

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import jobs as jobs_api

    monkeypatch.setattr(jobs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(orchestrator_service, "build_provider_adapter", lambda *_: _CostTrackingProvider())
    monkeypatch.setattr(job_understanding_service, "build_provider_adapter", lambda *_: _CostTrackingProvider())

    generate = client.post(f"/api/v1/jobs/{job_id}/generate", json={"queue_if_available": False})
    assert generate.status_code == 200
    run = generate.json()["run"]

    expected_cost = estimate_call_cost_usd(
        provider=ProviderName.OPENAI,
        input_tokens=100,
        output_tokens=50,
    ) + estimate_call_cost_usd(
        provider=ProviderName.OPENAI,
        input_tokens=10,
        output_tokens=5,
    )
    assert run["status"] == "success"
    assert run["input_tokens"] == 110
    assert run["output_tokens"] == 55
    assert run["estimated_cost_usd"] == pytest.approx(float(expected_cost), rel=1e-6)


def test_failed_generation_still_records_partial_usage(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _register(client, "GenUsageB")
    job_id = _create_ready_job(client)

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import jobs as jobs_api

    monkeypatch.setattr(jobs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(orchestrator_service, "build_provider_adapter", lambda *_: _FailingWorkflowProvider())
    monkeypatch.setattr(job_understanding_service, "build_provider_adapter", lambda *_: _FailingWorkflowProvider())

    generate = client.post(f"/api/v1/jobs/{job_id}/generate", json={"queue_if_available": False})
    assert generate.status_code == 422
    assert generate.json()["error"]["code"] == "invalid_output"

    runs = client.get(f"/api/v1/jobs/{job_id}/generation-runs")
    assert runs.status_code == 200
    run = runs.json()["runs"][0]

    expected_cost = estimate_call_cost_usd(
        provider=ProviderName.OPENAI,
        input_tokens=30,
        output_tokens=20,
    ) + estimate_call_cost_usd(
        provider=ProviderName.OPENAI,
        input_tokens=40,
        output_tokens=10,
    )
    assert run["status"] == "failed"
    assert run["input_tokens"] == 70
    assert run["output_tokens"] == 30
    assert run["estimated_cost_usd"] == pytest.approx(float(expected_cost), rel=1e-6)


def test_generation_prompt_includes_user_templates_and_prompt_blocks(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "GenPromptUser")
    profile_response = client.post(
        "/api/v1/profile",
        json={
            "upwork_profile_markdown": "# Profile\nAutomation expert",
            "proposal_template": "Custom proposal template: Hook, Plan, Proof, CTA",
            "custom_global_instruction": "Keep every sentence direct and practical.",
            "custom_prompt_blocks": [
                {"title": "Style", "content": "Use short bullet points where possible.", "enabled": True},
                {"title": "Disabled", "content": "Do not include this.", "enabled": False},
            ],
        },
    )
    assert profile_response.status_code == 201
    job_id = _create_ready_job(client)

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import jobs as jobs_api

    _CapturePromptProvider.seen_prompts.clear()
    monkeypatch.setattr(jobs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(orchestrator_service, "build_provider_adapter", lambda *_: _CapturePromptProvider())
    monkeypatch.setattr(job_understanding_service, "build_provider_adapter", lambda *_: _CapturePromptProvider())

    generate = client.post(f"/api/v1/jobs/{job_id}/generate", json={"queue_if_available": False})
    assert generate.status_code == 200

    joined_prompts = "\n\n".join(_CapturePromptProvider.seen_prompts)
    assert "Priority Instructions" in joined_prompts
    assert "Custom proposal template: Hook, Plan, Proof, CTA" in joined_prompts
    assert "Keep every sentence direct and practical." in joined_prompts
    assert "Use short bullet points where possible." in joined_prompts
    assert "Do not include this." not in joined_prompts
    assert "Automation expert" in joined_prompts


def test_proposal_prompt_receives_doc_loom_workflow_summaries(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _register(client, "GenCrossCtx")
    job_id = _create_ready_job(client)

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import jobs as jobs_api

    _CrossArtifactCaptureProvider.prompts_by_artifact.clear()
    monkeypatch.setattr(jobs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(orchestrator_service, "build_provider_adapter", lambda *_: _CrossArtifactCaptureProvider())
    monkeypatch.setattr(job_understanding_service, "build_provider_adapter", lambda *_: _CrossArtifactCaptureProvider())

    generate = client.post(f"/api/v1/jobs/{job_id}/generate", json={"queue_if_available": False})
    assert generate.status_code == 200

    proposal_prompt = _CrossArtifactCaptureProvider.prompts_by_artifact.get("proposal", "")
    assert proposal_prompt
    assert "Extra context:" in proposal_prompt
    assert "doc_summary" in proposal_prompt
    assert "loom_summary" in proposal_prompt
    assert "workflow_summary" in proposal_prompt
    assert "CRM Automation Execution Plan" in proposal_prompt
    assert "Webhook, CRM Update, Slack Notify" in proposal_prompt
    loom_prompt = _CrossArtifactCaptureProvider.prompts_by_artifact.get("loom_script", "")
    assert loom_prompt
    assert "job_type" in loom_prompt
    assert "automation_platform" in loom_prompt
    assert "classification_confidence" in loom_prompt
    assert "job_summary" in loom_prompt
    assert "CORE FLOW (MANDATORY IN INTENT)" in loom_prompt
    assert "agency website walkthrough" in loom_prompt.lower()
    assert "Transition cue" in loom_prompt


def test_loom_prompt_prioritizes_user_template_over_global_instruction_in_pipeline(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "GenLoomPriority")
    profile_response = client.post(
        "/api/v1/profile",
        json={
            "upwork_profile_markdown": "# Profile\nAgentLooper senior consultant",
            "loom_template": "Start with my proof stack and keep transitions compact.",
            "custom_global_instruction": "Keep tone concise and practical.",
        },
    )
    assert profile_response.status_code == 201
    job_id = _create_ready_job(client)

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import jobs as jobs_api

    provider = _LoomTemplateCaptureProvider()
    monkeypatch.setattr(jobs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(orchestrator_service, "build_provider_adapter", lambda *_: provider)
    monkeypatch.setattr(job_understanding_service, "build_provider_adapter", lambda *_: provider)

    generate = client.post(f"/api/v1/jobs/{job_id}/generate", json={"queue_if_available": False})
    assert generate.status_code == 200
    assert provider.loom_prompt
    assert "from DB loom_template, highest priority for Loom structure/style" in provider.loom_prompt
    assert "Start with my proof stack and keep transitions compact." in provider.loom_prompt
    assert "User Global Instruction (secondary to artifact template when both are present)" in provider.loom_prompt
    assert provider.loom_prompt.index("from DB loom_template") < provider.loom_prompt.index(
        "User Global Instruction (secondary to artifact template when both are present)"
    )


def test_proposal_regenerate_accepts_user_supplied_loom_doc_context(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "GenProposalCtx")
    job_id = _create_ready_job(client)

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import outputs as outputs_api

    _CapturePromptProvider.seen_prompts.clear()
    monkeypatch.setattr(outputs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(orchestrator_service, "build_provider_adapter", lambda *_: _CapturePromptProvider())
    monkeypatch.setattr(job_understanding_service, "build_provider_adapter", lambda *_: _CapturePromptProvider())

    regenerate = client.post(
        f"/api/v1/jobs/{job_id}/outputs/proposal/regenerate",
        json={
            "instruction": "Use my real recorded Loom context.",
            "queue_if_available": False,
            "proposal_loom_video_url": "https://www.loom.com/share/abc123",
            "proposal_loom_video_summary": "Real Loom shows CRM webhook routing and retry behavior.",
            "proposal_doc_summary": "Execution doc includes milestones and acceptance criteria.",
            "proposal_extra_notes": "Client prefers async updates over calls.",
        },
    )
    assert regenerate.status_code == 200

    joined_prompts = "\n\n".join(_CapturePromptProvider.seen_prompts)
    assert "proposal_loom_video_url" in joined_prompts
    assert "https://www.loom.com/share/abc123" in joined_prompts
    assert "proposal_loom_video_summary" in joined_prompts
    assert "Real Loom shows CRM webhook routing and retry behavior." in joined_prompts
    assert "proposal_doc_summary" in joined_prompts
    assert "Execution doc includes milestones and acceptance criteria." in joined_prompts
    assert "proposal_extra_notes" in joined_prompts
    assert "Client prefers async updates over calls." in joined_prompts


def test_make_workflow_generation_persists_to_workflow_jsons(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "GenMakeUser")
    job_id = _create_ready_job(client)

    manual = client.post(
        f"/api/v1/jobs/{job_id}/manual-markdown",
        json={"job_markdown": "Need Make.com automation to sync lead forms to CRM and alerts."},
    )
    assert manual.status_code == 200

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import jobs as jobs_api

    async def _fake_make_agent(**_: object) -> ArtifactPayload:
        return ArtifactPayload(
            artifact_type=ArtifactType.MAKE_WORKFLOW,
            content_text="Make scenario with trigger -> transform -> CRM upsert.",
            content_json={
                "name": "Lead Intake Make Scenario",
                "flow": [
                    {
                        "id": 1,
                        "module": "scheduler",
                        "version": 1,
                        "parameters": {},
                        "mapper": {},
                        "metadata": {"designer": {"x": 0, "y": 0}},
                    }
                ],
                "metadata": {"instant": False, "zone": "us1.make.com", "scenario": {}},
            },
            metadata={"usage": {"input_tokens": 10, "output_tokens": 5, "latency_ms": 25}},
        )

    monkeypatch.setattr(jobs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(
        job_understanding_service,
        "build_provider_adapter",
        lambda *_: _WorkflowOnlyUnderstandingProvider(),
    )
    monkeypatch.setattr(orchestrator_service, "run_make_agent", _fake_make_agent)

    generate = client.post(f"/api/v1/jobs/{job_id}/generate", json={"queue_if_available": False})
    assert generate.status_code == 200

    outputs = client.get(f"/api/v1/jobs/{job_id}/outputs")
    assert outputs.status_code == 200
    payload = outputs.json()["output"]
    assert len(payload["workflow_jsons"]) == 1
    assert payload["workflow_jsons"][0]["name"] == "make"
    assert payload["workflow_jsons"][0]["workflow_json"]["name"] == "Lead Intake Make Scenario"
    assert payload["workflow_explanation"] == "Make scenario with trigger -> transform -> CRM upsert."


def test_ghl_workflow_generation_persists_to_workflow_jsons(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "GenGhlUser")
    job_id = _create_ready_job(client)

    manual = client.post(
        f"/api/v1/jobs/{job_id}/manual-markdown",
        json={"job_markdown": "Need GoHighLevel (GHL) workflow for new lead follow-up and tag routing."},
    )
    assert manual.status_code == 200

    from app.application.ai import orchestrator_service
    from app.application.ai import job_understanding_service
    from app.interfaces.api.v1 import jobs as jobs_api

    async def _fake_ghl_agent(**_: object) -> ArtifactPayload:
        return ArtifactPayload(
            artifact_type=ArtifactType.GHL_WORKFLOW,
            content_text="GHL checklist with trigger and one tag action.",
            content_json={
                "workflow_name": "Lead Follow Up",
                "workflow_description": "Follow up new inbound leads.",
                "trigger": {
                    "type": "Form Submitted",
                    "category": "Events",
                    "configuration_notes": "Website lead form trigger.",
                    "filter_conditions": [],
                },
                "steps": [
                    {
                        "step_number": 1,
                        "step_type": "action",
                        "name": "Tag lead",
                        "action_name": "Add Contact Tag",
                        "action_category": "Contact",
                        "configuration": {"tag": "new-lead"},
                        "wait_duration": None,
                        "branch_condition": None,
                        "if_true_next_step": None,
                        "if_false_next_step": None,
                        "notes": "Tag each new lead.",
                    }
                ],
                "estimated_build_time_minutes": 20,
                "required_integrations": [],
                "required_custom_fields": [],
            },
            metadata={"usage": {"input_tokens": 12, "output_tokens": 6, "latency_ms": 30}},
        )

    monkeypatch.setattr(jobs_api, "enqueue_job_generation", lambda **_: False)
    monkeypatch.setattr(
        job_understanding_service,
        "build_provider_adapter",
        lambda *_: _WorkflowOnlyUnderstandingProvider(),
    )
    monkeypatch.setattr(orchestrator_service, "run_ghl_agent", _fake_ghl_agent)

    generate = client.post(f"/api/v1/jobs/{job_id}/generate", json={"queue_if_available": False})
    assert generate.status_code == 200

    outputs = client.get(f"/api/v1/jobs/{job_id}/outputs")
    assert outputs.status_code == 200
    payload = outputs.json()["output"]
    assert len(payload["workflow_jsons"]) == 1
    assert payload["workflow_jsons"][0]["name"] == "ghl"
    assert payload["workflow_jsons"][0]["workflow_json"]["workflow_name"] == "Lead Follow Up"
    assert payload["workflow_explanation"] == "GHL checklist with trigger and one tag action."
