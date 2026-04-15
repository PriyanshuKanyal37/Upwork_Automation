from uuid import uuid4

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.application.ai.contracts import ProviderGenerateRequest, ProviderGenerateResult, ProviderName
from app.application.ai.providers.base import AIProviderAdapter
from app.infrastructure.integrations.firecrawl_client import FirecrawlExtractionError


def _register_and_login(client: TestClient) -> str:
    email = f"profile-{uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": "Profile User", "email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 201
    return email


def test_profile_create_get_and_partial_update(client: TestClient) -> None:
    _register_and_login(client)

    create_response = client.post(
        "/api/v1/profile",
        json={
            "upwork_profile_url": "https://www.upwork.com/freelancers/~01abc123def4567890",
            "upwork_profile_id": "  freelancer_001  ",
            "proposal_template": "  Proposal template body  ",
            "custom_prompt_blocks": [
                {"title": "Tone", "content": "Use practical language", "enabled": True}
            ],
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["upwork_profile_id"] == "freelancer_001"
    assert created["proposal_template"] == "Proposal template body"
    assert len(created["custom_prompt_blocks"]) == 1

    get_response = client.get("/api/v1/profile")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["upwork_profile_id"] == "freelancer_001"
    assert fetched["proposal_template"] == "Proposal template body"

    patch_response = client.patch(
        "/api/v1/profile",
        json={
            "doc_template": "  Updated doc template ",
            "workflow_template_notes": "  ",
            "custom_prompt_blocks": [
                {"title": "CTA", "content": "End with direct call to action", "enabled": False}
            ],
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["doc_template"] == "Updated doc template"
    assert patched["workflow_template_notes"] is None
    assert patched["custom_prompt_blocks"][0]["enabled"] is False


def test_profile_duplicate_create_is_idempotent_update(client: TestClient) -> None:
    _register_and_login(client)

    first = client.post(
        "/api/v1/profile",
        json={"proposal_template": "Template A"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/profile",
        json={"proposal_template": "Template B"},
    )
    assert second.status_code == 200
    assert second.json()["proposal_template"] == "Template B"


def test_profile_get_not_found_before_create(client: TestClient) -> None:
    _register_and_login(client)
    response = client.get("/api/v1/profile")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "profile_not_found"


def test_profile_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/profile")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_profile_custom_prompt_block_validation(client: TestClient) -> None:
    _register_and_login(client)

    response = client.post(
        "/api/v1/profile",
        json={
            "custom_prompt_blocks": [
                {"title": " ", "content": "Valid content", "enabled": True},
            ]
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_profile_extract_upwork_creates_profile_and_saves_markdown(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register_and_login(client)
    from app.application.profile import service as profile_service

    async def fake_extract(_: str, api_key: str | None = None) -> str:  # noqa: ARG001
        return "## Upwork Profile\n- Python\n- FastAPI\n- Automation"

    monkeypatch.setattr(profile_service, "extract_markdown_from_url", fake_extract)

    response = client.post(
        "/api/v1/profile/extract-upwork",
        json={"upwork_profile_url": "https://www.upwork.com/freelancers/~01abc123def4567890"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["extracted"] is True
    assert payload["profile"]["upwork_profile_url"] == "https://upwork.com/freelancers/~01abc123def4567890"
    assert payload["profile"]["upwork_profile_id"] == "01abc123def4567890"
    assert "Upwork Profile" in payload["profile"]["upwork_profile_markdown"]


def test_profile_extract_upwork_update_refreshes_existing_profile(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register_and_login(client)
    from app.application.profile import service as profile_service

    calls = {"count": 0}

    async def fake_extract(_: str, api_key: str | None = None) -> str:  # noqa: ARG001
        calls["count"] += 1
        if calls["count"] == 1:
            return "## First Markdown"
        return "## Refreshed Markdown"

    monkeypatch.setattr(profile_service, "extract_markdown_from_url", fake_extract)

    create = client.post(
        "/api/v1/profile/extract-upwork",
        json={"upwork_profile_url": "https://upwork.com/freelancers/~01abc123def4567890"},
    )
    assert create.status_code == 200

    refresh = client.patch("/api/v1/profile/extract-upwork", json={})
    assert refresh.status_code == 200
    refreshed = refresh.json()
    assert refreshed["profile"]["upwork_profile_markdown"] == "## Refreshed Markdown"


def test_profile_extract_upwork_rejects_invalid_url(client: TestClient) -> None:
    _register_and_login(client)
    response = client.post(
        "/api/v1/profile/extract-upwork",
        json={"upwork_profile_url": "https://example.com/profile/abc"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_upwork_profile_url"


def test_profile_extract_upwork_maps_firecrawl_failure(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register_and_login(client)
    from app.application.profile import service as profile_service

    async def fake_extract(_: str, api_key: str | None = None) -> str:  # noqa: ARG001
        raise FirecrawlExtractionError(message="source blocked", code="firecrawl_http_error")

    monkeypatch.setattr(profile_service, "extract_markdown_from_url", fake_extract)

    response = client.post(
        "/api/v1/profile/extract-upwork",
        json={"upwork_profile_url": "https://upwork.com/freelancers/~01abc123def4567890"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["extracted"] is False
    assert payload["message"] == "Failed to extract Upwork profile markdown"
    assert payload["profile"]["upwork_profile_id"] == "01abc123def4567890"
    assert payload["profile"]["upwork_profile_markdown"] is None


def test_profile_extract_upwork_blocks_login_gated_shell_content(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register_and_login(client)
    from app.application.profile import service as profile_service

    async def fake_extract(_: str, api_key: str | None = None) -> str:  # noqa: ARG001
        return (
            "Secondary\n"
            "- [Development & IT](https://www.upwork.com/cat/dev-it)\n"
            "- [AI Services](https://www.upwork.com/cat/ai)\n"
            "[honeypot do not click](https://www.upwork.com/honey-pot-do-not-click)\n"
            "This freelancer's profile is only available to Upwork customers. "
            "Please login or sign up to view their profile."
        )

    monkeypatch.setattr(profile_service, "extract_markdown_from_url", fake_extract)

    response = client.post(
        "/api/v1/profile/extract-upwork",
        json={"upwork_profile_url": "https://upwork.com/freelancers/~01abc123def4567890"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["extracted"] is False
    assert payload["profile"]["upwork_profile_id"] == "01abc123def4567890"
    assert payload["profile"]["upwork_profile_markdown"] is None


def test_profile_extract_upwork_refresh_failure_keeps_existing_markdown(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register_and_login(client)
    from app.application.profile import service as profile_service

    calls = {"count": 0}

    async def fake_extract(_: str, api_key: str | None = None) -> str:  # noqa: ARG001
        calls["count"] += 1
        if calls["count"] == 1:
            return "## Valid Profile Markdown\n- Python\n- FastAPI"
        return (
            "Secondary\n"
            "- [Development & IT](https://www.upwork.com/cat/dev-it)\n"
            "- [AI Services](https://www.upwork.com/cat/ai)\n"
            "This freelancer's profile is only available to Upwork customers."
        )

    monkeypatch.setattr(profile_service, "extract_markdown_from_url", fake_extract)

    first = client.post(
        "/api/v1/profile/extract-upwork",
        json={"upwork_profile_url": "https://upwork.com/freelancers/~01abc123def4567890"},
    )
    assert first.status_code == 200
    assert "Valid Profile Markdown" in first.json()["profile"]["upwork_profile_markdown"]

    refresh = client.patch("/api/v1/profile/extract-upwork", json={})
    assert refresh.status_code == 200
    assert refresh.json()["extracted"] is False
    assert refresh.json()["profile"]["upwork_profile_id"] == "01abc123def4567890"

    get_profile = client.get("/api/v1/profile")
    assert get_profile.status_code == 200
    assert "Valid Profile Markdown" in get_profile.json()["upwork_profile_markdown"]


def test_profile_beautify_manual_creates_or_updates_profile(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register_and_login(client)
    from app.application.profile import service as profile_service

    class _FakeProfileBeautifyProvider(AIProviderAdapter):
        provider = ProviderName.OPENAI

        async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
            assert request.model_name == "gpt-5.4-mini"
            return ProviderGenerateResult(
                provider=ProviderName.OPENAI,
                model_name=request.model_name,
                output_text=(
                    "# Professional Profile\n"
                    "## Headline\n- Automation Engineer\n"
                    "## Summary\n- Builds scalable workflow systems.\n"
                    "## Core Skills\n- Python\n- FastAPI\n"
                    "## Services\n- API automation\n"
                    "## Tools & Platforms\n- n8n\n- Upwork\n"
                    "## Experience Highlights\n- Delivered automation projects.\n"
                    "## Domain Expertise\n- SaaS\n"
                    "## Portfolio/Case Notes\n- Not provided\n"
                    "## Communication & Working Style\n- Clear and proactive.\n"
                    "## Availability\n- Not provided\n"
                    "## Additional Notes\n- Not provided"
                ),
                input_tokens=120,
                output_tokens=180,
                latency_ms=60,
            )

    monkeypatch.setattr(profile_service, "OpenAIProviderAdapter", _FakeProfileBeautifyProvider)
    response = client.post(
        "/api/v1/profile/beautify-manual",
        json={
            "raw_profile_text": (
                "python fastapi api dev, did many projects, n8n automation, good communication"
            )
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model_name"] == "gpt-5.4-mini"
    assert payload["input_tokens"] == 120
    assert payload["output_tokens"] == 180
    assert "Professional Profile" in payload["beautified_markdown"]
    assert "Professional Profile" in payload["profile"]["upwork_profile_markdown"]


def test_profile_beautify_manual_maps_provider_failure(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _register_and_login(client)
    from app.application.profile import service as profile_service

    class _FailingProfileBeautifyProvider(AIProviderAdapter):
        provider = ProviderName.OPENAI

        async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:  # noqa: ARG002
            raise RuntimeError("provider_down")

    monkeypatch.setattr(profile_service, "OpenAIProviderAdapter", _FailingProfileBeautifyProvider)
    response = client.post(
        "/api/v1/profile/beautify-manual",
        json={"raw_profile_text": "experienced automation engineer with python and workflow expertise"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "profile_beautify_failed"


def test_profile_beautify_manual_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/profile/beautify-manual",
        json={"raw_profile_text": "experienced automation engineer with python and workflow expertise"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
