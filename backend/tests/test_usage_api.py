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


async def _seed_run(
    *,
    user_id: str,
    status: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: Decimal,
    created_at: datetime | None = None,
) -> None:
    async with SessionLocal() as session:
        user_uuid = UUID(user_id)
        now = created_at or datetime.now(UTC)
        job = Job(
            user_id=user_uuid,
            job_url=f"https://upwork.com/jobs/~{uuid4().hex}",
            status="ready",
        )
        session.add(job)
        await session.flush()
        session.add(
            JobGenerationRun(
                job_id=job.id,
                user_id=user_uuid,
                run_type="generate",
                status=status,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost_usd,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


def test_usage_summary_returns_current_user_and_team_breakdown(client: TestClient) -> None:
    user_a_id, user_a_email, user_a_password = _register(client, "UsageA")
    client.post("/api/v1/auth/logout")
    user_b_id, _, _ = _register(client, "UsageB")
    client.post("/api/v1/auth/logout")
    user_c_id, _, _ = _register(client, "UsageC")
    assert user_c_id

    asyncio.run(
        _seed_run(
            user_id=user_a_id,
            status="success",
            input_tokens=100,
            output_tokens=40,
            cost_usd=Decimal("0.500000"),
        )
    )
    asyncio.run(
        _seed_run(
            user_id=user_a_id,
            status="failed",
            input_tokens=50,
            output_tokens=20,
            cost_usd=Decimal("0.200000"),
        )
    )
    asyncio.run(
        _seed_run(
            user_id=user_b_id,
            status="success",
            input_tokens=200,
            output_tokens=80,
            cost_usd=Decimal("1.000000"),
        )
    )

    _login(client, user_a_email, user_a_password)
    response = client.get("/api/v1/usage/summary")
    assert response.status_code == 200
    payload = response.json()

    assert payload["team_user_count"] >= 3
    assert payload["active_user_count"] >= 2

    current = payload["current_user"]
    assert current["user_id"] == user_a_id
    assert current["totals"]["runs_total"] == 2
    assert current["totals"]["runs_success"] == 1
    assert current["totals"]["runs_failed"] == 1
    assert current["totals"]["input_tokens_total"] == 150
    assert current["totals"]["output_tokens_total"] == 60
    assert current["totals"]["estimated_cost_usd_total"] == pytest.approx(0.7, rel=1e-6)

    summed_runs = sum(item["totals"]["runs_total"] for item in payload["team_users"])
    summed_success = sum(item["totals"]["runs_success"] for item in payload["team_users"])
    summed_failed = sum(item["totals"]["runs_failed"] for item in payload["team_users"])
    summed_input = sum(item["totals"]["input_tokens_total"] for item in payload["team_users"])
    summed_output = sum(item["totals"]["output_tokens_total"] for item in payload["team_users"])
    summed_cost = sum(item["totals"]["estimated_cost_usd_total"] for item in payload["team_users"])

    team = payload["team_totals"]
    assert team["runs_total"] == summed_runs
    assert team["runs_success"] == summed_success
    assert team["runs_failed"] == summed_failed
    assert team["input_tokens_total"] == summed_input
    assert team["output_tokens_total"] == summed_output
    assert team["estimated_cost_usd_total"] == pytest.approx(summed_cost, rel=1e-6)

    user_map = {item["user_id"]: item for item in payload["team_users"]}
    assert user_map[user_b_id]["totals"]["estimated_cost_usd_total"] == pytest.approx(1.0, rel=1e-6)
    assert user_map[user_c_id]["totals"]["runs_total"] == 0
    assert user_map[user_c_id]["totals"]["estimated_cost_usd_total"] == pytest.approx(0.0, rel=1e-6)


def test_usage_summary_respects_window_days_filter(client: TestClient) -> None:
    user_id, email, password = _register(client, "UsageWindow")
    old_created_at = datetime.now(UTC) - timedelta(days=45)

    asyncio.run(
        _seed_run(
            user_id=user_id,
            status="success",
            input_tokens=80,
            output_tokens=20,
            cost_usd=Decimal("0.900000"),
            created_at=old_created_at,
        )
    )
    asyncio.run(
        _seed_run(
            user_id=user_id,
            status="success",
            input_tokens=40,
            output_tokens=10,
            cost_usd=Decimal("0.300000"),
        )
    )

    _login(client, email, password)

    full = client.get("/api/v1/usage/summary")
    assert full.status_code == 200
    assert full.json()["current_user"]["totals"]["estimated_cost_usd_total"] == pytest.approx(1.2, rel=1e-6)

    windowed = client.get("/api/v1/usage/summary?window_days=30")
    assert windowed.status_code == 200
    assert windowed.json()["current_user"]["totals"]["estimated_cost_usd_total"] == pytest.approx(0.3, rel=1e-6)
