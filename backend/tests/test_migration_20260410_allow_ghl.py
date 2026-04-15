from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parents[1]


def _run_alembic(*, command: str, revision: str, database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["AUTH_SECRET_KEY"] = "test-secret-key-with-more-than-thirty-two-characters"
    env["AUTH_COOKIE_SECURE"] = "false"
    subprocess.run(
        [sys.executable, "-m", "alembic", command, revision],
        cwd=BASE_DIR,
        check=True,
        env=env,
    )


def _seed_job(conn: sqlite3.Connection) -> str:
    user_id = uuid4().hex
    job_id = uuid4().hex
    conn.execute(
        "INSERT INTO users (id, display_name, email, password_hash) VALUES (?, ?, ?, ?)",
        (user_id, "GHL User", f"ghl-{uuid4().hex[:8]}@example.com", "hash"),
    )
    conn.execute(
        "INSERT INTO jobs (id, user_id, job_url, status) VALUES (?, ?, ?, ?)",
        (job_id, user_id, f"https://www.upwork.com/jobs/flow~{uuid4().hex}", "ready"),
    )
    conn.commit()
    return job_id


def test_upgrade_0007_allows_ghl_automation_platform() -> None:
    db_path = Path(tempfile.gettempdir()) / f"allow_ghl_{uuid4().hex}.db"
    database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    _run_alembic(command="upgrade", revision="20260408_0006", database_url=database_url)

    with sqlite3.connect(db_path) as conn:
        job_id = _seed_job(conn)

        try:
            conn.execute(
                "UPDATE jobs SET automation_platform = ? WHERE id = ?",
                ("ghl", job_id),
            )
            conn.commit()
            assert False, "Expected automation_platform check to reject 'ghl' before 0007"
        except sqlite3.IntegrityError:
            conn.rollback()

    _run_alembic(command="upgrade", revision="20260410_0007", database_url=database_url)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET automation_platform = ? WHERE id = ?",
            ("ghl", job_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT automation_platform FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "ghl"

