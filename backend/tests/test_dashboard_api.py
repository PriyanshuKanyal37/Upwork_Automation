import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.database.models.job import Job
from app.infrastructure.database.models.job_generation_run import JobGenerationRun
from app.infrastructure.database.session import SessionLocal


def _register(client: TestClient, name: str) -> tuple[str, str, str]:
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    password = "StrongPass123"
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()["user"]["id"], email, password


def _login(client: TestClient, email: str, password: str) -> None:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


async def _seed_sent_job(
    *,
    user_id: str,
    submitted_at: datetime | None,
) -> None:
    async with SessionLocal() as session:
        user_uuid = UUID(user_id)
        now = datetime.now(UTC)
        job = Job(
            user_id=user_uuid,
            job_url=f"https://upwork.com/jobs/~{uuid4().hex}",
            status="ready",
            is_submitted_to_upwork=True,
            submitted_at=submitted_at,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        await session.commit()


async def _seed_unsent_job(*, user_id: str) -> None:
    async with SessionLocal() as session:
        user_uuid = UUID(user_id)
        now = datetime.now(UTC)
        job = Job(
            user_id=user_uuid,
            job_url=f"https://upwork.com/jobs/~{uuid4().hex}",
            status="ready",
            is_submitted_to_upwork=False,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        await session.commit()


async def _seed_run_cost(*, user_id: str, cost_usd: Decimal) -> None:
    async with SessionLocal() as session:
        user_uuid = UUID(user_id)
        now = datetime.now(UTC)
        job = Job(
            user_id=user_uuid,
            job_url=f"https://upwork.com/jobs/~{uuid4().hex}",
            status="ready",
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        await session.flush()
        session.add(
            JobGenerationRun(
                job_id=job.id,
                user_id=user_uuid,
                run_type="generate",
                status="success",
                input_tokens=120,
                output_tokens=60,
                estimated_cost_usd=cost_usd,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


def test_jobs_dashboard_returns_cards_and_leaderboard(client: TestClient) -> None:
    user_a_id, user_a_email, user_a_password = _register(client, "DashA")
    client.post("/api/v1/auth/logout")
    user_b_id, _, _ = _register(client, "DashB")
    client.post("/api/v1/auth/logout")
    user_c_id, _, _ = _register(client, "DashC")
    assert user_c_id

    now = datetime.now(UTC)
    asyncio.run(_seed_sent_job(user_id=user_a_id, submitted_at=now - timedelta(days=1)))
    asyncio.run(_seed_sent_job(user_id=user_a_id, submitted_at=now - timedelta(hours=4)))
    asyncio.run(_seed_unsent_job(user_id=user_a_id))
    asyncio.run(_seed_sent_job(user_id=user_b_id, submitted_at=now - timedelta(hours=3)))
    asyncio.run(_seed_sent_job(user_id=user_b_id, submitted_at=now - timedelta(hours=2)))
    asyncio.run(_seed_sent_job(user_id=user_b_id, submitted_at=now - timedelta(hours=1)))

    asyncio.run(_seed_run_cost(user_id=user_a_id, cost_usd=Decimal("0.400000")))
    asyncio.run(_seed_run_cost(user_id=user_a_id, cost_usd=Decimal("0.200000")))
    asyncio.run(_seed_run_cost(user_id=user_b_id, cost_usd=Decimal("1.250000")))

    _login(client, user_a_email, user_a_password)
    response = client.get("/api/v1/dashboard/jobs?window=week")
    assert response.status_code == 200
    payload = response.json()

    assert payload["window_key"] == "week"
    assert payload["window_days"] == 7
    assert payload["leaderboard_user_count"] >= 3

    current_user = payload["current_user"]
    assert current_user["user_id"] == user_a_id
    assert current_user["proposals_sent_in_window"] == 2
    assert current_user["avg_send_speed_per_day"] == pytest.approx(2 / 7, rel=1e-6)
    assert current_user["total_jobs_sent_all_time"] == 2
    assert current_user["total_ai_cost_usd_all_time"] == pytest.approx(0.6, rel=1e-6)

    leaderboard = payload["leaderboard"]
    assert leaderboard[0]["user_id"] == user_b_id
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[0]["proposals_sent_in_window"] == 3
    assert leaderboard[1]["user_id"] == user_a_id
    assert leaderboard[1]["rank"] == 2


def test_jobs_dashboard_window_day_filters_submissions(client: TestClient) -> None:
    user_id, email, password = _register(client, "DashWindow")

    now = datetime.now(UTC)
    asyncio.run(_seed_sent_job(user_id=user_id, submitted_at=now - timedelta(days=2)))
    asyncio.run(_seed_sent_job(user_id=user_id, submitted_at=now - timedelta(hours=6)))

    _login(client, email, password)

    day_response = client.get("/api/v1/dashboard/jobs?window=day")
    assert day_response.status_code == 200
    day_payload = day_response.json()
    assert day_payload["current_user"]["proposals_sent_in_window"] == 1

    month_response = client.get("/api/v1/dashboard/jobs?window=month")
    assert month_response.status_code == 200
    month_payload = month_response.json()
    assert month_payload["current_user"]["proposals_sent_in_window"] == 2


def test_jobs_dashboard_rejects_invalid_window(client: TestClient) -> None:
    _, email, password = _register(client, "DashInvalidWindow")
    _login(client, email, password)
    response = client.get("/api/v1/dashboard/jobs?window=year")
    assert response.status_code == 422

