from time import perf_counter
from uuid import uuid4

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.infrastructure.integrations.firecrawl_client import FirecrawlExtractResult


def _register(client: TestClient, name: str) -> None:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 201


def test_generation_pipeline_smoke_performance(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _register(client, "SmokePerfUser")

    async def fake_extract(_: str, api_key: str | None = None) -> FirecrawlExtractResult:
        return FirecrawlExtractResult(
            markdown=(
                "# Build CRM Automation Pipeline\n\n"
                "Posted 2 hours ago\n"
                "Worldwide\n\n"
                "**Summary**\n"
                "We need an automation specialist to design and implement an end-to-end CRM automation flow. "
                "The workflow should capture inbound leads, enrich records, route qualified leads to sales, "
                "notify the team in Slack, and create follow-up tasks. Reliability and observability are required.\n\n"
                "##### Skills and Expertise\n"
                "n8n\n"
                "HubSpot\n"
                "Slack API\n"
                "Webhooks\n"
            ),
            metadata=None,
        )

    from app.application.job import service as job_service

    monkeypatch.setattr(job_service, "extract_markdown_bundle_from_url", fake_extract)

    started_at = perf_counter()

    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": f"https://www.upwork.com/jobs/flow~{uuid4().hex}"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    extract = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert extract.status_code == 200
    assert extract.json()["job"]["status"] == "ready"

    save_outputs = client.patch(
        f"/api/v1/jobs/{job_id}/outputs",
        json={
            "proposal_text": "Initial proposal",
            "loom_script": "Initial script",
        },
    )
    assert save_outputs.status_code == 200

    regenerate = client.post(
        f"/api/v1/jobs/{job_id}/outputs/regenerate",
        json={
            "target_output": "proposal_text",
            "instruction": "Shorten it",
            "generated_text": "Short proposal text",
        },
    )
    assert regenerate.status_code == 200
    assert regenerate.json()["output"]["proposal_text"] == "Short proposal text"

    elapsed_seconds = perf_counter() - started_at
    assert elapsed_seconds < 20
