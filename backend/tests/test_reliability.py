from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from pytest import MonkeyPatch


def _register(client: TestClient, name: str) -> None:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 201


def test_idempotency_replays_write_response(client: TestClient) -> None:
    _register(client, "IdempotencyUser")
    headers = {"idempotency-key": "job-intake-key-1"}
    payload = {"job_url": f"https://www.upwork.com/jobs/flow~{uuid4().hex}"}

    first = client.post("/api/v1/jobs/intake", json=payload, headers=headers)
    assert first.status_code == 201
    first_job_id = first.json()["job"]["id"]
    assert first.headers.get("x-idempotent-replay") is None

    second = client.post("/api/v1/jobs/intake", json=payload, headers=headers)
    assert second.status_code == 201
    assert second.headers.get("x-idempotent-replay") == "true"
    assert second.json()["job"]["id"] == first_job_id

    listed = client.get("/api/v1/jobs")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1


def test_global_rate_limiter_blocks_after_threshold(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    from app.infrastructure.http.global_rate_limiter import global_rate_limiter

    original_max = global_rate_limiter._max_attempts
    original_window = global_rate_limiter._window
    monkeypatch.setattr(global_rate_limiter, "_max_attempts", 1)
    monkeypatch.setattr(global_rate_limiter, "_window", timedelta(seconds=60))

    try:
        first = client.get("/api/v1/health")
        assert first.status_code == 200

        second = client.get("/api/v1/health")
        assert second.status_code == 429
        assert second.json()["error"]["code"] == "too_many_requests"
    finally:
        monkeypatch.setattr(global_rate_limiter, "_max_attempts", original_max)
        monkeypatch.setattr(global_rate_limiter, "_window", original_window)


def test_metrics_endpoint_returns_observability_snapshot(client: TestClient) -> None:
    client.get("/api/v1/health")
    metrics = client.get("/api/v1/metrics")
    assert metrics.status_code == 200
    payload = metrics.json()
    for field in (
        "http_requests_total",
        "http_requests_5xx_total",
        "http_request_duration_ms_avg",
        "worker_runs_total",
        "external_api_calls_total",
        "queue_depth_current",
    ):
        assert field in payload
