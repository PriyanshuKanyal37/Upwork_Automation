from uuid import UUID, uuid4

from fastapi.testclient import TestClient


def _register(client: TestClient, name: str) -> None:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 201


def test_connector_crud_and_status(client: TestClient) -> None:
    _register(client, "ConnectorUser")

    create = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "google_docs",
            "credential_ref": "oauth://google/user_123",
            "status": "pending_oauth",
        },
    )
    assert create.status_code == 201
    created = create.json()["connector"]
    assert created["connector_name"] == "google_docs"
    assert created["credential_ref"] == "oauth://google/user_123"
    assert created["status"] == "pending_oauth"

    listed = client.get("/api/v1/connectors")
    assert listed.status_code == 200
    list_payload = listed.json()["connectors"]
    assert len(list_payload) == 1
    assert list_payload[0]["connector_name"] == "google_docs"

    fetched = client.get("/api/v1/connectors/google_docs")
    assert fetched.status_code == 200
    assert fetched.json()["connector"]["status"] == "pending_oauth"

    status_check = client.get("/api/v1/connectors/google_docs/status")
    assert status_check.status_code == 200
    status_payload = status_check.json()["connector_status"]
    assert status_payload["connector_name"] == "google_docs"
    assert status_payload["is_connected"] is False
    assert status_payload["action_required"] is False

    updated = client.patch(
        "/api/v1/connectors/google_docs",
        json={"status": "connected"},
    )
    assert updated.status_code == 200
    assert updated.json()["connector"]["status"] == "connected"

    deleted = client.delete("/api/v1/connectors/google_docs")
    assert deleted.status_code == 204

    missing = client.get("/api/v1/connectors/google_docs")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "connector_not_found"


def test_connector_rejects_invalid_name_and_raw_secret(client: TestClient) -> None:
    _register(client, "ConnectorUser2")

    invalid_name = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "dropbox",
            "credential_ref": "oauth://dropbox/user123",
            "status": "connected",
        },
    )
    assert invalid_name.status_code == 422
    assert invalid_name.json()["error"]["code"] == "invalid_connector_name"

    removed_connector = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "upwork",
            "credential_ref": "oauth://upwork/user123",
            "status": "connected",
        },
    )
    assert removed_connector.status_code == 422
    assert removed_connector.json()["error"]["code"] == "invalid_connector_name"

    raw_secret = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "google_docs",
            "credential_ref": "plain-text-secret-value",
            "status": "connected",
        },
    )
    assert raw_secret.status_code == 422
    assert raw_secret.json()["error"]["code"] == "invalid_credential_ref"


def test_connector_accepts_raw_firecrawl_key_and_normalizes_scheme(client: TestClient) -> None:
    _register(client, "ConnectorFirecrawlRawUser")

    created = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "firecrawl",
            "credential_ref": "fc-d2cac543ce814e83bbc16fb7fe09303e",
            "status": "connected",
        },
    )
    assert created.status_code == 201
    payload = created.json()["connector"]
    assert payload["credential_ref"] == "firecrawl://fc-d2cac543ce814e83bbc16fb7fe09303e"

    patched = client.patch(
        "/api/v1/connectors/firecrawl",
        json={"credential_ref": "fc-updated-key-123", "status": "connected"},
    )
    assert patched.status_code == 200
    assert patched.json()["connector"]["credential_ref"] == "firecrawl://fc-updated-key-123"


def test_connector_rejects_napkin_connector(client: TestClient) -> None:
    _register(client, "ConnectorNoNapkinUser")

    response = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "napkin",
            "credential_ref": "napkin://nk-user-key-123",
            "status": "connected",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_connector_name"


def test_connector_unique_constraint_and_auth(client: TestClient) -> None:
    _register(client, "ConnectorUser3")

    first = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "firecrawl",
            "credential_ref": "firecrawl://fc-user123",
            "status": "connected",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "firecrawl",
            "credential_ref": "firecrawl://fc-user123-v2",
            "status": "connected",
        },
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "connector_already_exists"

    client.post("/api/v1/auth/logout")
    unauth = client.get("/api/v1/connectors")
    assert unauth.status_code == 401
    assert unauth.json()["error"]["code"] == "unauthorized"


def test_connector_live_status_probe(client: TestClient, monkeypatch) -> None:
    _register(client, "ConnectorLiveUser")
    create = client.post(
        "/api/v1/connectors",
        json={
            "connector_name": "google_docs",
            "credential_ref": "oauth://google?access_token=test-token",
            "status": "connected",
        },
    )
    assert create.status_code == 201

    from app.interfaces.api.v1 import connectors as connectors_api

    async def fake_live_probe(**kwargs):
        return {
            "connector_name": "google_docs",
            "status": "connected",
            "message": "Google Docs connector is healthy",
            "is_connected": True,
            "action_required": False,
            "checked_live": True,
            "details": {"expires_in": 1800},
        }

    monkeypatch.setattr(connectors_api, "run_live_connector_health_check", fake_live_probe)
    monkeypatch.setattr(connectors_api, "serialize_live_health", lambda x: x)

    live_status = client.get("/api/v1/connectors/google_docs/status?live=true")
    assert live_status.status_code == 200
    payload = live_status.json()["connector_status"]
    assert payload["checked_live"] is True
    assert payload["is_connected"] is True


def test_google_oauth_start_returns_authorization_url(client: TestClient, monkeypatch) -> None:
    _register(client, "GoogleOauthStartUser")

    from app.interfaces.api.v1 import connectors as connectors_api

    monkeypatch.setattr(
        connectors_api,
        "build_google_authorization_url",
        lambda *, user_id: ("https://accounts.google.com/o/oauth2/v2/auth?state=test-state", "test-state"),
    )

    response = client.get("/api/v1/connectors/google/oauth/start")
    assert response.status_code == 200
    payload = response.json()
    assert payload["authorization_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert payload["state"] == "test-state"
    assert payload["redirect_uri"].endswith("/api/v1/connectors/google/callback")


def test_google_oauth_callback_upserts_google_docs_connector(client: TestClient, monkeypatch) -> None:
    _register(client, "GoogleOauthCallbackUser")
    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    user_id = UUID(me_response.json()["user"]["id"])

    from app.interfaces.api.v1 import connectors as connectors_api
    from app.infrastructure.integrations.google_oauth_flow import GoogleOAuthTokens

    monkeypatch.setattr(connectors_api, "decode_google_oauth_state", lambda _: user_id)

    async def fake_exchange_google_auth_code(*, code: str, redirect_uri: str) -> GoogleOAuthTokens:
        assert code == "code-123"
        assert redirect_uri.endswith("/api/v1/connectors/google/callback")
        return GoogleOAuthTokens(access_token="access-123", refresh_token="refresh-123")

    monkeypatch.setattr(connectors_api, "exchange_google_auth_code", fake_exchange_google_auth_code)

    callback = client.get("/api/v1/connectors/google/callback?code=code-123&state=state-123")
    assert callback.status_code == 200
    callback_payload = callback.json()
    assert callback_payload["message"] == "Google Docs connected successfully"
    connector = callback_payload["connector"]
    assert connector["connector_name"] == "google_docs"
    assert connector["status"] == "connected"
    assert connector["credential_ref"].startswith("oauth://google_docs?")

    fetched = client.get("/api/v1/connectors/google_docs")
    assert fetched.status_code == 200
    assert fetched.json()["connector"]["status"] == "connected"
