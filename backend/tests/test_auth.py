from uuid import uuid4

from fastapi.testclient import TestClient


def _unique_email() -> str:
    return f"user-{uuid4().hex[:10]}@example.com"


def test_register_sets_cookie_and_returns_user(client: TestClient) -> None:
    email = _unique_email()

    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": "Priya", "email": email, "password": "StrongPass123"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["user"]["email"] == email
    assert "agentloopr_session=" in response.headers.get("set-cookie", "")

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["user"]["email"] == email


def test_login_logout_flow(client: TestClient) -> None:
    email = _unique_email()
    password = "AnotherPass123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={"display_name": "Agent", "email": email, "password": password},
    )
    assert register_response.status_code == 201

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    me_after_logout = client.get("/api/v1/auth/me")
    assert me_after_logout.status_code == 401


def test_login_rate_limit_blocks_after_threshold(client: TestClient) -> None:
    email = _unique_email()
    valid_password = "ValidPass123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={"display_name": "Rate User", "email": email, "password": valid_password},
    )
    assert register_response.status_code == 201

    for _ in range(8):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPass123"},
        )
        assert response.status_code == 401

    blocked_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPass123"},
    )
    assert blocked_response.status_code == 429
