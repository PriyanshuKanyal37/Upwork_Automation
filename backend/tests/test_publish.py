import asyncio
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.application.connector.contracts import PublishResult
from app.infrastructure.database.models.job import Job
from app.infrastructure.database.models.job_output import JobOutput
from app.infrastructure.database.session import SessionLocal


def _register(client: TestClient, name: str) -> None:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 201


def _create_job_with_output(client: TestClient) -> str:
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": f"https://www.upwork.com/jobs/flow~{uuid4().hex}"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    manual = client.post(
        f"/api/v1/jobs/{job_id}/manual-markdown",
        json={"job_markdown": "Need proposal + workflow output for publishing."},
    )
    assert manual.status_code == 200

    output = client.patch(
        f"/api/v1/jobs/{job_id}/outputs",
        json={"google_doc_markdown": "## Final Output\nThis is the approved content."},
    )
    assert output.status_code == 200
    return job_id


async def _mark_job_approved(job_id: UUID) -> None:
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        output = await session.scalar(select(JobOutput).where(JobOutput.job_id == job_id))
        assert job is not None
        assert output is not None
        job.status = "ready"
        job.plan_approved = True
        output.approval_snapshot_json = {"approved_revision_map": {"doc": 1}}
        output.artifact_versions_json = [{"artifact_type": "doc", "version_number": 1}]
        await session.commit()


def test_publish_google_docs_and_airtable_scaffold(client: TestClient, monkeypatch) -> None:
    _register(client, "PublishUser")
    job_id = _create_job_with_output(client)
    asyncio.run(_mark_job_approved(UUID(job_id)))

    create_google_connector = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "google_docs",
            "credential_ref": "oauth://google?access_token=test-access-token",
            "status": "connected",
        },
    )
    assert create_google_connector.status_code == 201

    create_airtable_connector = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "airtable",
            "credential_ref": "secret://airtable/user_123",
            "status": "connected",
        },
    )
    assert create_airtable_connector.status_code == 201

    from app.application.connector import publish_service

    async def fake_google_publish(**kwargs):
        return PublishResult(
            connector_name="google_docs",
            status="published",
            external_id="doc_123",
            external_url="https://docs.google.com/document/d/doc_123",
        )

    monkeypatch.setattr(publish_service, "_publish_google_docs", fake_google_publish)

    publish_response = client.post(
        f"/api/v1/jobs/{job_id}/publish",
        json={"connectors": ["google_docs", "airtable"], "title": "Client Ready Output"},
    )
    assert publish_response.status_code == 200
    payload = publish_response.json()
    assert payload["job_id"] == job_id
    assert payload["google_doc_url"] == "https://docs.google.com/document/d/doc_123"
    assert payload["google_doc_open_url"] == "https://docs.google.com/document/d/doc_123"
    by_connector = {item["connector_name"]: item for item in payload["results"]}
    assert by_connector["google_docs"]["status"] == "published"
    assert by_connector["airtable"]["status"] == "skipped"
    assert by_connector["airtable"]["reason"] in {"airtable_publish_not_enabled", "airtable_future_adapter_pending"}
