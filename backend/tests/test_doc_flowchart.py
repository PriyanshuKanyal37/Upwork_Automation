from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.application.output.diagram_models import DiagramConnection, DiagramSpec, DiagramStep
from app.application.output.diagram_quality_validator import validate_diagram_quality
from app.application.output.diagram_spec_service import DiagramSpecBuildResult
from app.application.output.service import _extract_flowchart_source_section

_FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + (b"x" * 2048)


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


def _make_spec(layout_family: str = "roadmap_cards") -> DiagramSpec:
    steps = [
        DiagramStep(id="s1", title="Analyze requirements", detail="Map goals and constraints"),
        DiagramStep(id="s2", title="Design approach", detail="Pick tools and sequencing"),
        DiagramStep(id="s3", title="Implement workflow", detail="Build and validate"),
        DiagramStep(id="s4", title="Deliver and monitor", detail="Publish and track outcomes"),
    ]
    return DiagramSpec(
        title="Automation Delivery Plan",
        orientation="horizontal",
        layout_family=layout_family,  # type: ignore[arg-type]
        creativity_level="high",
        steps=steps,
        connections=[
            DiagramConnection(source_id="s1", target_id="s2"),
            DiagramConnection(source_id="s2", target_id="s3"),
            DiagramConnection(source_id="s3", target_id="s4"),
        ],
    )


def test_generate_doc_flowchart_on_demand(client: TestClient, monkeypatch) -> None:
    _register(client, "FlowchartUser")
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

    async def fake_build_diagram_spec(**kwargs) -> DiagramSpecBuildResult:
        assert kwargs["markdown"]
        assert kwargs["instruction"] == "Make it more implementation focused"
        return DiagramSpecBuildResult(
            spec=_make_spec("swimlane_process"),
            source="llm",
            input_tokens=123,
            output_tokens=77,
            model_name="gpt-test-model",
        )

    seen_dims: dict[str, tuple[int, int]] = {}

    def fake_render_diagram_svg(*, spec: DiagramSpec, width: int = 1600, height: int = 1200) -> str:
        assert spec.orientation == "horizontal"
        assert 1200 <= width <= 1600
        assert 700 <= height <= 1200
        seen_dims["render"] = (width, height)
        return "<svg>diagram</svg>"

    async def fake_convert_svg_to_png(*, svg_content: str, width: int = 1600, height: int = 1200) -> bytes:
        assert svg_content == "<svg>diagram</svg>"
        assert seen_dims.get("render") == (width, height)
        seen_dims["convert"] = (width, height)
        return _FAKE_PNG_BYTES

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
            assert image_bytes == _FAKE_PNG_BYTES
            assert mime_type == "image/png"
            assert filename.endswith("-flowchart.png")
            return "https://drive.google.com/uc?export=view&id=img_123"

    monkeypatch.setattr(output_service, "resolve_google_access_token", fake_resolve_google_access_token)
    monkeypatch.setattr(output_service, "build_diagram_spec", fake_build_diagram_spec)
    monkeypatch.setattr(output_service, "render_diagram_svg", fake_render_diagram_svg)
    monkeypatch.setattr(output_service, "convert_svg_to_png", fake_convert_svg_to_png)
    monkeypatch.setattr(output_service, "GoogleDocsClient", FakeGoogleDocsClient)

    response = client.post(
        f"/api/v1/jobs/{job_id}/outputs/doc-flowchart/generate",
        json={"instruction": "Make it more implementation focused"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Diagram generated and staged for publishing"
    flowchart = payload["doc_flowchart"]
    assert flowchart is not None
    assert flowchart["status"] == "ready"
    assert flowchart["image_url"].startswith("https://drive.google.com/uc?export=view&id=")
    assert flowchart["layout_family"] == "swimlane_process"
    assert flowchart["orientation"] == "horizontal"
    assert flowchart["creativity_level"] == "high"
    assert flowchart["model_name"] == "gpt-test-model"
    assert flowchart["spec_source"] == "llm"
    assert flowchart["input_tokens"] == 123
    assert flowchart["output_tokens"] == 77
    assert flowchart["estimated_credits_used"] == 0
    assert flowchart["flowchart_instruction"] == "Make it more implementation focused"
    assert flowchart["request_id"].startswith("diagram-")
    assert flowchart["render_mode"] == "ai"
    assert flowchart["quality_status"] == "passed"
    assert flowchart["quality_score"] >= 70
    assert flowchart["connection_style"] == "clean"
    assert flowchart["inline_svg_data_url"].startswith("data:image/svg+xml;base64,")
    assert seen_dims.get("render") == seen_dims.get("convert")


def test_generate_doc_flowchart_archives_previous_version(client: TestClient, monkeypatch) -> None:
    _register(client, "FlowchartArchiveUser")
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

    async def fake_build_diagram_spec(**kwargs) -> DiagramSpecBuildResult:
        return DiagramSpecBuildResult(
            spec=_make_spec(),
            source="fallback",
            input_tokens=0,
            output_tokens=0,
            model_name=None,
        )

    def fake_render_diagram_svg(*, spec: DiagramSpec, width: int = 1600, height: int = 1200) -> str:
        return "<svg>diagram</svg>"

    async def fake_convert_svg_to_png(*, svg_content: str, width: int = 1600, height: int = 1200) -> bytes:
        return _FAKE_PNG_BYTES

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
    monkeypatch.setattr(output_service, "build_diagram_spec", fake_build_diagram_spec)
    monkeypatch.setattr(output_service, "render_diagram_svg", fake_render_diagram_svg)
    monkeypatch.setattr(output_service, "convert_svg_to_png", fake_convert_svg_to_png)
    monkeypatch.setattr(output_service, "GoogleDocsClient", FakeGoogleDocsClient)

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


def test_quality_validator_passes_clean_horizontal_spec() -> None:
    result = validate_diagram_quality(spec=_make_spec("roadmap_cards"), width=1600, height=1200)
    assert result.passed is True
    assert result.status == "passed"
    assert result.score >= 70


def test_quality_validator_rejects_backward_non_feedback_edges() -> None:
    spec = _make_spec("roadmap_cards")
    spec.connections = [
        DiagramConnection(source_id="s3", target_id="s1", edge_type="sequence"),
    ]
    result = validate_diagram_quality(spec=spec, width=1600, height=1200)
    assert result.passed is False
    assert any(issue.startswith("edge_backward") for issue in result.errors)
