from __future__ import annotations

import os
from pathlib import Path
import subprocess
import asyncio
import sys
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parents[1]
_WORKER = os.environ.get("PYTEST_XDIST_WORKER", "main")
_PID = os.getpid()
TEST_DB_PATH = BASE_DIR / f"test_agentloopr_{_WORKER}_{_PID}.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["AUTH_SECRET_KEY"] = "test-secret-key-with-more-than-thirty-two-characters"
os.environ["AUTH_COOKIE_SECURE"] = "false"
os.environ["QUEUE_DRIVER"] = "inline"


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    from app.infrastructure.config.settings import get_settings

    get_settings.cache_clear()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BASE_DIR,
        check=True,
        env=os.environ.copy(),
    )
    yield
    from app.infrastructure.database.session import engine

    asyncio.run(engine.dispose())
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(autouse=True)
def reset_login_limiter() -> Iterator[None]:
    from app.infrastructure.security.login_rate_limiter import login_rate_limiter

    login_rate_limiter.clear()
    yield
    login_rate_limiter.clear()


@pytest.fixture(autouse=True)
def reset_global_reliability_stores() -> Iterator[None]:
    from app.infrastructure.http.global_rate_limiter import global_rate_limiter
    from app.infrastructure.http.idempotency import idempotency_store
    from app.infrastructure.observability.metrics import metrics_state

    global_rate_limiter.clear()
    idempotency_store.clear()
    metrics_state.clear()
    yield
    global_rate_limiter.clear()
    idempotency_store.clear()
    metrics_state.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
