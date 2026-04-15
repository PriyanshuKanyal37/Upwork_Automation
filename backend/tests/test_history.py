from uuid import uuid4

from fastapi.testclient import TestClient


def _register(client: TestClient, name: str) -> None:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 201


def _create_job(client: TestClient) -> str:
    intake = client.post(
        "/api/v1/jobs/intake",
        json={"job_url": f"https://www.upwork.com/jobs/flow~{uuid4().hex}"},
    )
    assert intake.status_code == 201
    return intake.json()["job"]["id"]


def test_jobs_list_and_filters(client: TestClient) -> None:
    _register(client, "HistoryUserA")
    job_a = _create_job(client)
    _create_job(client)

    status_update = client.patch(
        f"/api/v1/jobs/{job_a}/status-outcome",
        json={"status": "ready", "outcome": "replied"},
    )
    assert status_update.status_code == 200
    assert status_update.json()["job"]["status"] == "ready"
    assert status_update.json()["job"]["outcome"] == "replied"

    submission_update = client.patch(
        f"/api/v1/jobs/{job_a}/submission",
        json={"is_submitted_to_upwork": True},
    )
    assert submission_update.status_code == 200
    submitted_job = submission_update.json()["job"]
    assert submitted_job["is_submitted_to_upwork"] is True
    assert submitted_job["submitted_at"] is not None

    all_jobs = client.get("/api/v1/jobs")
    assert all_jobs.status_code == 200
    assert all_jobs.json()["count"] == 2

    ready_jobs = client.get("/api/v1/jobs?status=ready")
    assert ready_jobs.status_code == 200
    assert ready_jobs.json()["count"] == 1
    assert ready_jobs.json()["jobs"][0]["id"] == job_a

    replied_jobs = client.get("/api/v1/jobs?outcome=replied")
    assert replied_jobs.status_code == 200
    assert replied_jobs.json()["count"] == 1
    assert replied_jobs.json()["jobs"][0]["id"] == job_a

    submitted_jobs = client.get("/api/v1/jobs?is_submitted_to_upwork=true")
    assert submitted_jobs.status_code == 200
    assert submitted_jobs.json()["count"] == 1
    assert submitted_jobs.json()["jobs"][0]["id"] == job_a


def test_job_detail_includes_output_payload(client: TestClient) -> None:
    _register(client, "HistoryUserB")
    job_id = _create_job(client)

    output_update = client.patch(
        f"/api/v1/jobs/{job_id}/outputs",
        json={"proposal_text": "History detail proposal"},
    )
    assert output_update.status_code == 200

    detail = client.get(f"/api/v1/jobs/{job_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["job"]["id"] == job_id
    assert payload["output"] is not None
    assert payload["output"]["proposal_text"] == "History detail proposal"


def test_job_status_submission_validations(client: TestClient) -> None:
    _register(client, "HistoryUserC")
    job_id = _create_job(client)

    invalid_status = client.patch(
        f"/api/v1/jobs/{job_id}/status-outcome",
        json={"status": "unknown_status"},
    )
    assert invalid_status.status_code == 422
    assert invalid_status.json()["error"]["code"] == "invalid_job_status"

    unsupported_status = client.patch(
        f"/api/v1/jobs/{job_id}/status-outcome",
        json={"status": "approved"},
    )
    assert unsupported_status.status_code == 422
    assert unsupported_status.json()["error"]["code"] == "invalid_job_status"

    invalid_outcome = client.patch(
        f"/api/v1/jobs/{job_id}/status-outcome",
        json={"outcome": "maybe"},
    )
    assert invalid_outcome.status_code == 422
    assert invalid_outcome.json()["error"]["code"] == "invalid_job_outcome"

    invalid_submitted_at = client.patch(
        f"/api/v1/jobs/{job_id}/submission",
        json={"is_submitted_to_upwork": False, "submitted_at": "2026-04-03T10:00:00Z"},
    )
    assert invalid_submitted_at.status_code == 422
    assert invalid_submitted_at.json()["error"]["code"] == "invalid_submitted_at"


def test_job_outcome_not_sent_aliases(client: TestClient) -> None:
    _register(client, "HistoryUserD")
    job_id = _create_job(client)

    space_variant = client.patch(
        f"/api/v1/jobs/{job_id}/status-outcome",
        json={"outcome": "not sent"},
    )
    assert space_variant.status_code == 200
    assert space_variant.json()["job"]["outcome"] == "not_sent"

    hyphen_variant = client.patch(
        f"/api/v1/jobs/{job_id}/status-outcome",
        json={"outcome": "not-sent"},
    )
    assert hyphen_variant.status_code == 200
    assert hyphen_variant.json()["job"]["outcome"] == "not_sent"


def test_job_outcome_sent_sets_submission_flags(client: TestClient) -> None:
    _register(client, "HistoryUserE")
    job_id = _create_job(client)

    sent_update = client.patch(
        f"/api/v1/jobs/{job_id}/status-outcome",
        json={"outcome": "sent"},
    )
    assert sent_update.status_code == 200
    job_payload = sent_update.json()["job"]
    assert job_payload["outcome"] == "sent"
    assert job_payload["is_submitted_to_upwork"] is True
    assert job_payload["submitted_at"] is not None


def test_job_outcome_not_sent_clears_submission_flags(client: TestClient) -> None:
    _register(client, "HistoryUserF")
    job_id = _create_job(client)

    initial_submission = client.patch(
        f"/api/v1/jobs/{job_id}/submission",
        json={"is_submitted_to_upwork": True},
    )
    assert initial_submission.status_code == 200
    assert initial_submission.json()["job"]["is_submitted_to_upwork"] is True
    assert initial_submission.json()["job"]["submitted_at"] is not None

    unsent_update = client.patch(
        f"/api/v1/jobs/{job_id}/status-outcome",
        json={"outcome": "not_sent"},
    )
    assert unsent_update.status_code == 200
    job_payload = unsent_update.json()["job"]
    assert job_payload["outcome"] == "not_sent"
    assert job_payload["is_submitted_to_upwork"] is False
    assert job_payload["submitted_at"] is None


def test_jobs_history_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/jobs")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
