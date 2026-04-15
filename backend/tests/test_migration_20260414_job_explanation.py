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


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return {str(row[1]) for row in rows}


def _seed_job(conn: sqlite3.Connection) -> str:
    user_id = uuid4().hex
    job_id = uuid4().hex
    conn.execute(
        "INSERT INTO users (id, display_name, email, password_hash) VALUES (?, ?, ?, ?)",
        (user_id, "Explain User", f"explain-{uuid4().hex[:8]}@example.com", "hash"),
    )
    conn.execute(
        "INSERT INTO jobs (id, user_id, job_url, status) VALUES (?, ?, ?, ?)",
        (job_id, user_id, f"https://www.upwork.com/jobs/flow~{uuid4().hex}", "ready"),
    )
    conn.commit()
    return job_id


def test_migration_0012_adds_and_removes_job_explanation_column() -> None:
    db_path = Path(tempfile.gettempdir()) / f"job_explanation_{uuid4().hex}.db"
    database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    _run_alembic(command="upgrade", revision="20260412_0011", database_url=database_url)

    with sqlite3.connect(db_path) as conn:
        assert "job_explanation" not in _table_columns(conn, "jobs")
        job_id = _seed_job(conn)

    _run_alembic(command="upgrade", revision="20260414_0012", database_url=database_url)

    with sqlite3.connect(db_path) as conn:
        assert "job_explanation" in _table_columns(conn, "jobs")
        conn.execute(
            "UPDATE jobs SET job_explanation = ? WHERE id = ?",
            ("🧠 Summary.\n\n- 🎯 Goal.\n- 🧩 Scope.\n- 🛠️ Skills.\n- ⏱️ Constraints.", job_id),
        )
        conn.commit()
        row = conn.execute("SELECT job_explanation FROM jobs WHERE id = ?", (job_id,)).fetchone()
        assert row is not None
        assert isinstance(row[0], str)
        assert "Summary" in row[0]

    _run_alembic(command="downgrade", revision="20260412_0011", database_url=database_url)

    with sqlite3.connect(db_path) as conn:
        assert "job_explanation" not in _table_columns(conn, "jobs")
