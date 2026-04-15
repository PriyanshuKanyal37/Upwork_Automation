from uuid import uuid4

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.infrastructure.integrations.firecrawl_client import FirecrawlExtractionError
from app.infrastructure.integrations.firecrawl_client import FirecrawlExtractResult


def _register(client: TestClient, name: str) -> str:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 201
    return email


def test_job_intake_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/~01abcdef1234567890"},
    )
    assert response.status_code == 401


def test_job_intake_single_user_has_no_duplicate(client: TestClient) -> None:
    _register(client, "UserOne")

    response = client.post(
        "/api/v1/jobs/intake",
        json={
            "job_url": "https://www.upwork.com/jobs/n8n-automation-setup~01abcdef1234567890?source=search",
            "notes_markdown": "  client needs CRM automation  ",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["duplicate"]["duplicate_count"] == 0
    assert payload["job"]["status"] == "draft"
    assert payload["job"]["upwork_job_id"] == "01abcdef1234567890"
    assert payload["job"]["notes_markdown"] == "client needs CRM automation"


def test_job_intake_accepts_noisy_text_with_embedded_upwork_url(client: TestClient) -> None:
    _register(client, "NoisyInput")

    response = client.post(
        "/api/v1/jobs/intake",
        json={
            "job_url": (
                "Please check this job and generate all outputs: "
                "https://www.upwork.com/jobs/n8n-automation-setup~01bbccddeeff001122?source=search."
            )
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["job"]["upwork_job_id"] == "01bbccddeeff001122"
    assert payload["job"]["job_url"] == "https://upwork.com/jobs/n8n-automation-setup~01bbccddeeff001122"


def test_job_intake_normalizes_upwork_apply_url_to_details_url(client: TestClient) -> None:
    _register(client, "ApplyUrlInput")

    response = client.post(
        "/api/v1/jobs/intake",
        json={
            "job_url": "https://www.upwork.com/nx/proposals/job/~022040404922862714552/apply/",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["job"]["upwork_job_id"] == "022040404922862714552"
    assert payload["job"]["job_url"] == "https://upwork.com/jobs/~022040404922862714552"


def test_job_intake_uses_llm_fallback_when_no_url_can_be_deterministically_parsed(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "LlmFallback")
    from app.application.job import service as job_service

    async def fake_llm_resolver(_: str) -> str | None:
        return "https://upwork.com/jobs/custom-flow~01cdef1234ab567890"

    monkeypatch.setattr(job_service, "_resolve_job_url_with_llm", fake_llm_resolver)

    response = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "Need help with this job from my message above"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["job"]["upwork_job_id"] == "01cdef1234ab567890"
    assert payload["job"]["job_url"] == "https://upwork.com/jobs/custom-flow~01cdef1234ab567890"


def test_job_duplicate_detected_for_other_user_and_continue_flow(client: TestClient) -> None:
    _register(client, "OwnerA")
    first_response = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/anything~01fedcba9876543210"},
    )
    assert first_response.status_code == 201
    client.post("/api/v1/auth/logout")

    _register(client, "OwnerB")
    second_response = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://upwork.com/jobs/anything~01fedcba9876543210/?utm_source=test"},
    )
    assert second_response.status_code == 201
    second_payload = second_response.json()
    assert second_payload["duplicate"]["duplicate_count"] == 1
    assert second_payload["job"]["status"] == "duplicate_notified"

    job_id = second_payload["job"]["id"]
    decision_response = client.post(
        f"/api/v1/jobs/{job_id}/duplicate-decision",
        json={"action": "continue"},
    )
    assert decision_response.status_code == 200
    decision_payload = decision_response.json()
    assert decision_payload["should_process"] is True
    assert decision_payload["job"]["status"] == "draft"


def test_duplicate_decision_stop_keeps_duplicate_notified(client: TestClient) -> None:
    _register(client, "OwnerX")
    client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01aabbccddeeff1122"},
    )
    client.post("/api/v1/auth/logout")

    _register(client, "OwnerY")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01aabbccddeeff1122"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    response = client.post(
        f"/api/v1/jobs/{job_id}/duplicate-decision",
        json={"action": "stop"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["should_process"] is False
    assert payload["job"]["status"] == "duplicate_notified"


def test_duplicate_decision_not_required_for_non_duplicate_job(client: TestClient) -> None:
    _register(client, "OwnerSolo")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/solo~019876543210abcdef"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    response = client.post(
        f"/api/v1/jobs/{job_id}/duplicate-decision",
        json={"action": "continue"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_decision_not_required"


def test_job_intake_rejects_non_upwork_url(client: TestClient) -> None:
    _register(client, "UrlCheck")
    response = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://example.com/jobs/123"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_job_url"


def test_extract_job_markdown_success(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _register(client, "ExtractorA")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef5678"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    async def fake_extract(_: str, api_key: str | None = None) -> FirecrawlExtractResult:
        return FirecrawlExtractResult(
            markdown=(
                "# AI Automation Specialist Needed\n\n"
                "Posted 2 hours ago\n\n"
                "**Summary**\n\n"
                "We need an automation expert to build a production workflow.\n\n"
                "##### Skills and Expertise\n\n"
                "Python\nAutomation\nn8n\n"
            ),
            metadata=None,
        )

    from app.application.job import service as job_service

    monkeypatch.setattr(job_service, "extract_markdown_bundle_from_url", fake_extract)

    response = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] is False
    assert payload["extracted"] is True
    assert payload["fallback_required"] is False
    assert payload["job"]["status"] == "ready"
    assert "AI Automation Specialist Needed" in payload["job"]["job_markdown"]
    assert isinstance(payload["job"]["job_explanation"], str)
    assert payload["job"]["job_explanation"].strip()


def test_extract_job_markdown_queued_response(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _register(client, "ExtractorQueue")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01aaee1234beef5678"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    from app.interfaces.api.v1 import jobs as jobs_api

    monkeypatch.setattr(jobs_api, "enqueue_job_extraction", lambda **_: True)

    response = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] is True
    assert payload["extracted"] is False
    assert payload["fallback_required"] is False
    assert payload["message"] == "Extraction queued"
    assert payload["job"]["status"] == "processing"


def test_extract_job_markdown_failure_requires_fallback(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "ExtractorB")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef9999"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    async def fake_extract(_: str, api_key: str | None = None) -> FirecrawlExtractResult:
        raise FirecrawlExtractionError(message="blocked by source", code="firecrawl_blocked")

    from app.application.job import service as job_service

    monkeypatch.setattr(job_service, "extract_markdown_bundle_from_url", fake_extract)

    extract_response = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert extract_response.status_code == 200
    extract_payload = extract_response.json()
    assert extract_payload["queued"] is False
    assert extract_payload["extracted"] is False
    assert extract_payload["fallback_required"] is True
    assert extract_payload["job"]["status"] == "failed"
    assert extract_payload["message"] == "Firecrawl failed. Please paste the job text manually."
    assert extract_payload["job"]["requires_manual_markdown"] is True

    manual_response = client.post(
        f"/api/v1/jobs/{job_id}/manual-markdown",
        json={"job_markdown": "## Manual copy\nThis was pasted by user after failure."},
    )
    assert manual_response.status_code == 200
    manual_payload = manual_response.json()
    assert manual_payload["job"]["status"] == "ready"
    assert "pasted by user" in manual_payload["job"]["job_markdown"]
    assert manual_payload["job"]["requires_manual_markdown"] is False
    assert isinstance(manual_payload["job"]["job_explanation"], str)
    assert manual_payload["job"]["job_explanation"].strip()


def test_extract_job_markdown_uses_user_firecrawl_key(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "ExtractorPerUserKey")
    connector = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "firecrawl",
            "credential_ref": "firecrawl://fc-user-key-123",
            "status": "connected",
        },
    )
    assert connector.status_code == 201

    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef7777"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    seen_api_keys: list[str | None] = []

    async def fake_extract(_: str, api_key: str | None = None) -> FirecrawlExtractResult:
        seen_api_keys.append(api_key)
        return FirecrawlExtractResult(
            markdown=(
                "# n8n Expert\n\n"
                "**Summary**\n\n"
                "Need robust workflow automation for client operations.\n\n"
                "##### Skills and Expertise\n\n"
                "n8n\nPython\n"
            ),
            metadata=None,
        )

    from app.application.job import service as job_service

    monkeypatch.setattr(job_service, "extract_markdown_bundle_from_url", fake_extract)

    response = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert response.status_code == 200
    assert response.json()["job"]["status"] == "ready"
    assert seen_api_keys == ["fc-user-key-123"]


def test_extract_job_markdown_cleans_upwork_navigation_noise(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "ExtractorCleaner")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef6666"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    noisy_markdown = """
Secondary

- [Development & IT](https://www.upwork.com/cat/dev-it)
- [AI Services](https://www.upwork.com/cat/ai)

# Train Custom AI/LLM LoRA Model for Brand Illustration Style (FLUX/SDXL)

Posted 1 hour ago

Worldwide

**Summary**

We are seeking an experienced AI Integration Specialist.

- **$250.00**

Fixed-price

##### Skills and Expertise

Python

Artificial Intelligence

##### About the client

Member since Feb 28, 2023

#### Explore similar jobs on Upwork

[Some other listing](https://www.upwork.com/freelance-jobs/apply/other)

### How it works

Create your free profile

Footer navigation
"""

    async def fake_extract(_: str, api_key: str | None = None) -> FirecrawlExtractResult:
        return FirecrawlExtractResult(markdown=noisy_markdown, metadata=None)

    from app.application.job import service as job_service

    monkeypatch.setattr(job_service, "extract_markdown_bundle_from_url", fake_extract)

    response = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["status"] == "ready"
    stored = payload["job"]["job_markdown"]
    assert stored is not None
    assert "Secondary" not in stored
    assert "# Train Custom AI/LLM LoRA Model for Brand Illustration Style (FLUX/SDXL)" in stored
    assert "Posted 1 hour ago" in stored
    assert "Worldwide" in stored
    assert "Explore similar jobs on Upwork" not in stored
    assert "How it works" not in stored
    assert "Footer navigation" not in stored
    assert "Create your free profile" not in stored
    assert "**Summary**" in stored
    assert "AI Integration Specialist" in stored
    assert "##### Skills and Expertise" in stored
    assert "##### About the client" in stored


def test_extract_job_markdown_preserves_pre_summary_metadata_without_h1(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "ExtractorCleanerMeta")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef6655"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    noisy_markdown = """
Secondary
- [Development & IT](https://www.upwork.com/cat/dev-it)

Train Custom AI/LLM LoRA Model for Brand Illustration Style (FLUX/SDXL)
Posted 1 hour ago
Worldwide

**Summary**

Need someone to implement workflows.
"""

    async def fake_extract(_: str, api_key: str | None = None) -> FirecrawlExtractResult:
        return FirecrawlExtractResult(markdown=noisy_markdown, metadata=None)

    from app.application.job import service as job_service

    monkeypatch.setattr(job_service, "extract_markdown_bundle_from_url", fake_extract)

    response = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert response.status_code == 200
    stored = response.json()["job"]["job_markdown"]
    assert stored is not None
    assert "Train Custom AI/LLM LoRA Model for Brand Illustration Style (FLUX/SDXL)" in stored
    assert "Posted 1 hour ago" in stored
    assert "Worldwide" in stored
    assert "**Summary**" in stored
    assert "Secondary" not in stored


def test_extract_job_markdown_enriches_missing_title_with_firecrawl_metadata(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "ExtractorCleanerMetadataTitle")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef6654"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    raw_markdown = """
Secondary

**Summary**

Need someone to implement workflows.
"""

    async def fake_extract(_: str, api_key: str | None = None) -> FirecrawlExtractResult:
        return FirecrawlExtractResult(
            markdown=raw_markdown,
            metadata={
                "title": (
                    "n8n Developer: Build Two Automated Workflows from Spec - "
                    "Freelance Job in Scripts & Utilities - $750.00 Fixed Price, "
                    "posted April 3, 2026 - Upwork"
                ),
                "og:image": "https://www.upwork.com/static/job-hero-image.png",
            },
        )

    from app.application.job import service as job_service

    monkeypatch.setattr(job_service, "extract_markdown_bundle_from_url", fake_extract)

    response = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert response.status_code == 200
    stored = response.json()["job"]["job_markdown"]
    assert stored is not None
    assert stored.startswith("# n8n Developer: Build Two Automated Workflows from Spec")
    assert "Posted April 3, 2026" in stored
    assert "Hero image: https://www.upwork.com/static/job-hero-image.png" in stored
    assert "**Summary**" in stored


def test_extract_job_markdown_private_listing_requires_manual_fallback(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "ExtractorPrivateListing")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef6652"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    private_listing_markdown = """
# Upwork

Secondary

- [Development & IT](https://www.upwork.com/cat/dev-it)

#### This job is a private listing.

**Want to browse more Freelancer jobs?** [Sign Up](https://www.upwork.com/nx/signup)
"""

    async def fake_extract(_: str, api_key: str | None = None) -> FirecrawlExtractResult:
        return FirecrawlExtractResult(markdown=private_listing_markdown, metadata=None)

    from app.application.job import service as job_service

    monkeypatch.setattr(job_service, "extract_markdown_bundle_from_url", fake_extract)

    response = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback_required"] is True
    assert payload["job"]["status"] == "failed"
    assert payload["job"]["requires_manual_markdown"] is True
    assert "quality check failed" in (payload["job"]["extraction_error"] or "").lower()


def test_extract_job_markdown_cloudflare_challenge_requires_manual_fallback(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "ExtractorCloudflareChallenge")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef6651"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    challenge_markdown = """
# Challenge

Cloudflare Ray ID: **9e7e18dc3a5b8062**

Your IP: 195.96.134.15
"""

    async def fake_extract(_: str, api_key: str | None = None) -> FirecrawlExtractResult:
        return FirecrawlExtractResult(markdown=challenge_markdown, metadata=None)

    from app.application.job import service as job_service

    monkeypatch.setattr(job_service, "extract_markdown_bundle_from_url", fake_extract)

    response = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback_required"] is True
    assert payload["job"]["status"] == "failed"
    assert payload["job"]["requires_manual_markdown"] is True
    assert "quality check failed" in (payload["job"]["extraction_error"] or "").lower()


def test_extract_job_markdown_preserves_pre_summary_availability_metadata(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register(client, "ExtractorCleanerAvailability")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef6653"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    raw_markdown = """
Secondary

- [Development & IT](https://www.upwork.com/cat/dev-it)

Less than 30 hrs/week
Hourly
< 1 month
Duration
Intermediate
Experience Level
Posted 2 hours ago
Worldwide

**Summary**

Need someone to build robust automation pipelines.
"""

    async def fake_extract(_: str, api_key: str | None = None) -> FirecrawlExtractResult:
        return FirecrawlExtractResult(markdown=raw_markdown, metadata=None)

    from app.application.job import service as job_service

    monkeypatch.setattr(job_service, "extract_markdown_bundle_from_url", fake_extract)

    response = client.post(f"/api/v1/jobs/{job_id}/extract")
    assert response.status_code == 200
    stored = response.json()["job"]["job_markdown"]
    assert stored is not None
    assert "Less than 30 hrs/week" in stored
    assert "Hourly" in stored
    assert "< 1 month" in stored
    assert "Duration" in stored
    assert "Intermediate" in stored
    assert "Experience Level" in stored
    assert "Posted 2 hours ago" in stored
    assert "Worldwide" in stored
    assert "**Summary**" in stored


def test_regenerate_job_explanation_endpoint(client: TestClient) -> None:
    _register(client, "ExplainEndpointUser")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef6650"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    manual = client.post(
        f"/api/v1/jobs/{job_id}/manual-markdown",
        json={"job_markdown": "Need help building n8n workflow automation for lead intake and CRM sync."},
    )
    assert manual.status_code == 200

    explain = client.post(f"/api/v1/jobs/{job_id}/explain")
    assert explain.status_code == 200
    payload = explain.json()
    assert payload["message"]
    assert isinstance(payload["used_fallback"], bool)
    assert isinstance(payload["job"]["job_explanation"], str)
    assert payload["job"]["job_explanation"].strip()


def test_regenerate_job_explanation_requires_markdown(client: TestClient) -> None:
    _register(client, "ExplainEndpointMissingMarkdown")
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": "https://www.upwork.com/jobs/flow~01feed1234beef6649"},
    )
    assert intake.status_code == 201
    job_id = intake.json()["job"]["id"]

    explain = client.post(f"/api/v1/jobs/{job_id}/explain")
    assert explain.status_code == 422
    assert explain.json()["error"]["code"] == "job_markdown_missing"
