from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.application.output.service import (
    _build_deterministic_mermaid,
    _extract_flowchart_source_section,
    _extract_key_points,
    _extract_mermaid_code,
)

# Fake PNG ≥ 1024 bytes for tests — avoids network calls to Kroki.
# 1×1 red pixel with IDAT chunk padded to exceed the 1024-byte minimum size check.
_FAKE_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x04\x00IDATx\xda\xed\xc1\x01"
    b"\x01\x00\x00\x00\x82\x20\xff\xafnH@\x01\x00\x00\x00\x01\x00\x00\x00"
    b"\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    + b"\x00" * 960
    + b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def _fake_render_mermaid_via_kroki(mermaid_code: str, *, theme: str = "forest") -> bytes:
    return _FAKE_PNG


def test_parser_prefers_flow_at_a_glance_section() -> None:
    doc = (
        "# Project\n"
        "## How I'll solve it\n"
        "- Build API and validation\n"
        "## The flow at a glance\n"
        "1. Capture leads -> validate\n"
        "2. Route records -> notify team\n"
        "## Why me\n"
        "- Delivered similar systems\n"
    )
    result = _extract_flowchart_source_section(doc)
    assert result is not None
    kind, text = result
    assert kind == "flow_at_a_glance"
    assert "Capture leads" in text
    assert "Build API" not in text


def test_parser_falls_back_to_how_ill_solve_it() -> None:
    doc = (
        "# Project\n"
        "## How I'll solve it\n"
        "- Phase 1 - ingest source data\n"
        "- Phase 2 - transform and validate\n"
        "- Phase 3 - publish and monitor\n"
        "## Immediate Next Actions\n"
        "- Confirm access\n"
    )
    result = _extract_flowchart_source_section(doc)
    assert result is not None
    kind, text = result
    assert kind == "how_ill_solve_it"
    assert "Phase 2" in text
    assert "Confirm access" not in text


def test_parser_falls_back_to_execution_plan() -> None:
    doc = (
        "# Project\n"
        "## Execution Plan\n"
        "1. Analyze sources\n"
        "2. Build workflow\n"
        "3. Verify outputs\n"
        "## Timeline\n"
        "- 2 weeks\n"
    )
    result = _extract_flowchart_source_section(doc)
    assert result is not None
    kind, text = result
    assert kind == "execution_plan"
    assert "Build workflow" in text
    assert "2 weeks" not in text


def test_parser_returns_none_without_supported_heading() -> None:
    doc = (
        "# Project\n"
        "## Problem\n"
        "- Current process is manual\n"
        "## Why me\n"
        "- Similar work delivered\n"
    )
    assert _extract_flowchart_source_section(doc) is None


def test_extract_key_points_from_bullets() -> None:
    text = (
        "- Phase 1 - analyze requirements and constraints\n"
        "- Phase 2 - design solution architecture\n"
        "- Phase 3 - implement core workflow\n"
        "- Phase 4 - test and validate end to end\n"
        "- Phase 5 - deploy and monitor production\n"
    )
    points = _extract_key_points(text)
    assert len(points) == 5
    assert "Phase 1" in points[0]
    assert "Phase 5" in points[4]


def test_extract_key_points_deduplicates() -> None:
    text = (
        "- Analyze requirements\n"
        "- Analyze requirements\n"
        "- Build workflow\n"
    )
    points = _extract_key_points(text)
    assert len(points) == 2


def test_extract_key_points_skips_short_lines() -> None:
    text = "ok\n- This is a proper point with enough words\n- ab"
    points = _extract_key_points(text)
    assert len(points) == 1
    assert "proper point" in points[0]


def test_build_deterministic_mermaid_structure() -> None:
    points = [
        "Analyze project requirements",
        "Design the solution approach",
        "Implement the core workflow",
        "Test and validate all components",
        "Deploy to production environment",
        "Monitor and iterate based on feedback",
    ]
    code = _build_deterministic_mermaid(points=points, title="Test Flow", instruction=None)
    assert "flowchart TD" in code
    assert '["Analyze project requirements"]' in code
    assert '["Deploy to production environment"]' in code
    assert "subgraph" not in code


def test_build_deterministic_mermaid_fallback() -> None:
    points: list[str] = []
    code = _build_deterministic_mermaid(points=points, title="Fallback", instruction=None)
    assert "flowchart TD" in code
    assert "Ingest and validate inputs" in code


def test_extract_mermaid_code_strips_fences() -> None:
    raw = '```mermaid\nflowchart LR\n    A["Start"] --> B["End"]\n```'
    result = _extract_mermaid_code(raw)
    assert result == 'flowchart LR\n    A["Start"] --> B["End"]'


def test_extract_mermaid_code_strips_json_fence() -> None:
    raw = '```\nflowchart TD\n    A --> B\n```'
    result = _extract_mermaid_code(raw)
    assert result == "flowchart TD\n    A --> B"


def test_extract_mermaid_code_handles_no_fences() -> None:
    result = _extract_mermaid_code("flowchart LR\n    A --> B")
    assert result == "flowchart LR\n    A --> B"


def _register(client: TestClient, name: str) -> None:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 201


def _create_job_with_doc(client: TestClient) -> str:
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": f"https://www.upwork.com/jobs/flow~{uuid4().hex}"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    manual = client.post(
        f"/api/v1/jobs/{job_id}/manual-markdown",
        json={"job_markdown": "Need implementation plan with milestones and constraints."},
    )
    assert manual.status_code == 200

    doc_markdown = """# Automation Delivery Plan
## Context
Client needs onboarding automation.
## Goals
- Reduce manual work and errors
## How I'll solve it
- Phase 1 - map source events and contracts
- Phase 2 - build validation and dedup pipeline
- Phase 3 - route records and deliver notifications
## Immediate Next Actions
- Confirm access
"""
    output = client.patch(
        f"/api/v1/jobs/{job_id}/outputs",
        json={"google_doc_markdown": doc_markdown},
    )
    assert output.status_code == 200
    return job_id


def test_generate_doc_flowchart_end_to_end(client: TestClient, monkeypatch) -> None:
    _register(client, "MermaidFlowUser")
    job_id = _create_job_with_doc(client)

    google_connector = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "google_docs",
            "credential_ref": "oauth://google?access_token=test-google-token",
            "status": "connected",
        },
    )
    assert google_connector.status_code == 201

    from app.application.output import service as output_service

    async def fake_resolve_google_access_token(_: str) -> str:
        return "google-access-token"

    async def fake_generate_mermaid(*, prompt: str, retry_count: int = 0) -> tuple[str, str, str, int, int]:
        return (
            'flowchart TD\n'
            '    n0[Map source events and contracts]\n'
            '    n1[Validate input schemas]\n'
            '    n2[Build validation pipeline]\n'
            '    n3[Implement dedup logic]\n'
            '    n4[Route records to targets]\n'
            '    n5[Send notifications]\n'
            '    n0 --> n1\n'
            '    n1 --> n2\n'
            '    n2 --> n3\n'
            '    n3 --> n4\n'
            '    n4 --> n5\n',
            "claude-sonnet-4-6",
            "anthropic",
            850,
            420,
        )

    class FakeGoogleDocsClient:
        async def upload_public_image(
            self,
            *,
            access_token: str,
            image_bytes: bytes,
            mime_type: str,
            filename: str,
        ) -> str:
            assert access_token == "google-access-token"
            assert mime_type == "image/png"
            assert filename.endswith("-flowchart.png")
            assert image_bytes.startswith(b"\x89PNG")
            return "https://drive.google.com/uc?export=view&id=img_mermaid_1"

    monkeypatch.setattr(output_service, "resolve_google_access_token", fake_resolve_google_access_token)
    monkeypatch.setattr(output_service, "GoogleDocsClient", FakeGoogleDocsClient)
    monkeypatch.setattr(output_service, "_generate_mermaid_flowchart", fake_generate_mermaid)
    monkeypatch.setattr(output_service, "_render_mermaid_via_kroki", _fake_render_mermaid_via_kroki)

    response = client.post(
        f"/api/v1/jobs/{job_id}/outputs/doc-flowchart/generate",
        json={"instruction": "Make it implementation focused"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Diagram generated and staged for publishing"
    flowchart = payload["doc_flowchart"]
    assert flowchart is not None
    assert flowchart["status"] == "ready"
    assert flowchart["image_url"].startswith("https://drive.google.com/uc?export=view&id=")
    assert flowchart["render_engine"] == "kroki"
    assert flowchart["render_mode"] == "mermaid_js_official"
    assert flowchart["spec_source"] == "llm_mermaid"
    assert flowchart["quality_status"] == "passed"
    assert flowchart["flowchart_instruction"] == "Make it implementation focused"
    assert flowchart["request_id"].startswith("diagram-")


def test_generate_doc_flowchart_archives_previous(client: TestClient, monkeypatch) -> None:
    _register(client, "MermaidArchiveUser")
    job_id = _create_job_with_doc(client)

    google_connector = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "google_docs",
            "credential_ref": "oauth://google?access_token=test-google-token",
            "status": "connected",
        },
    )
    assert google_connector.status_code == 201

    from app.application.output import service as output_service

    counter = {"n": 0}

    async def fake_resolve_google_access_token(_: str) -> str:
        return "google-access-token"

    async def fake_generate_mermaid(*, prompt: str, retry_count: int = 0) -> tuple[str, str, str, int, int]:
        return (
            'flowchart TD\n'
            '    n0[Step A]\n'
            '    n1[Step B]\n'
            '    n2[Step C]\n'
            '    n3[Step D]\n'
            '    n0 --> n1\n'
            '    n1 --> n2\n'
            '    n2 --> n3\n',
            "claude-sonnet-4-6",
            "anthropic",
            700,
            350,
        )

    class FakeGoogleDocsClient:
        async def upload_public_image(
            self,
            *,
            access_token: str,
            image_bytes: bytes,
            mime_type: str,
            filename: str,
        ) -> str:
            counter["n"] += 1
            return f"https://drive.google.com/uc?export=view&id=img_{counter['n']}"

    monkeypatch.setattr(output_service, "resolve_google_access_token", fake_resolve_google_access_token)
    monkeypatch.setattr(output_service, "GoogleDocsClient", FakeGoogleDocsClient)
    monkeypatch.setattr(output_service, "_generate_mermaid_flowchart", fake_generate_mermaid)
    monkeypatch.setattr(output_service, "_render_mermaid_via_kroki", _fake_render_mermaid_via_kroki)

    first = client.post(
        f"/api/v1/jobs/{job_id}/outputs/doc-flowchart/generate",
        json={"instruction": "First diagram"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/jobs/{job_id}/outputs/doc-flowchart/generate",
        json={"instruction": "Second diagram"},
    )
    assert second.status_code == 200

    detail = client.get(f"/api/v1/jobs/{job_id}/outputs")
    assert detail.status_code == 200
    output = detail.json()["output"]
    latest = output["doc_flowchart"]
    assert latest["image_url"].endswith("img_2")
    assert latest["flowchart_instruction"] == "Second diagram"

    versions = output["artifact_versions_json"]
    assert len(versions) == 1
    assert versions[0]["artifact_type"] == "doc_flowchart"
    assert versions[0]["payload"]["image_url"].endswith("img_1")
    assert versions[0]["payload"]["flowchart_instruction"] == "First diagram"


def test_generate_doc_flowchart_rejects_missing_doc(client: TestClient) -> None:
    _register(client, "MermaidNoDocUser")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": f"https://www.upwork.com/jobs/flow~{uuid4().hex}"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    manual = client.post(
        f"/api/v1/jobs/{job_id}/manual-markdown",
        json={"job_markdown": "Need implementation plan."},
    )
    assert manual.status_code == 200

    response = client.post(
        f"/api/v1/jobs/{job_id}/outputs/doc-flowchart/generate",
        json={"instruction": "test"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "doc_content_missing"
