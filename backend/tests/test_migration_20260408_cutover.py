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


def _insert_seed_rows(conn: sqlite3.Connection) -> tuple[str, str]:
    # SQLAlchemy's UUID on SQLite stores compact 32-char hex by default.
    user_id = uuid4().hex
    job_id = uuid4().hex
    output_id = uuid4().hex

    conn.execute(
        "INSERT INTO users (id, display_name, email, password_hash) VALUES (?, ?, ?, ?)",
        (user_id, "Cutover User", f"cutover-{uuid4().hex[:8]}@example.com", "hash"),
    )
    conn.execute(
        "INSERT INTO jobs (id, user_id, job_url, status) VALUES (?, ?, ?, ?)",
        (job_id, user_id, f"https://www.upwork.com/jobs/flow~{uuid4().hex}", "ready"),
    )
    conn.execute(
        """
        INSERT INTO job_outputs (
            id,
            job_id,
            job_type,
            automation_platform,
            classification_confidence,
            classification_reasoning,
            classified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            output_id,
            job_id,
            "automation",
            "n8n",
            "high",
            "Explicit n8n mention in job description.",
            "2026-04-08T12:00:00Z",
        ),
    )
    conn.commit()
    return user_id, job_id


def test_upgrade_backfills_jobs_and_drops_classification_columns_from_job_outputs() -> None:
    db_path = Path(tempfile.gettempdir()) / f"cutover_upgrade_{uuid4().hex}.db"
    database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    _run_alembic(command="upgrade", revision="20260407_0005", database_url=database_url)

    with sqlite3.connect(db_path) as conn:
        _, job_id = _insert_seed_rows(conn)

    _run_alembic(command="upgrade", revision="20260408_0006", database_url=database_url)

    with sqlite3.connect(db_path) as conn:
        jobs_columns = _table_columns(conn, "jobs")
        outputs_columns = _table_columns(conn, "job_outputs")

        assert "job_type" in jobs_columns
        assert "automation_platform" in jobs_columns
        assert "classification_confidence" in jobs_columns
        assert "classification_reasoning" in jobs_columns
        assert "classified_at" in jobs_columns

        assert "job_type" not in outputs_columns
        assert "automation_platform" not in outputs_columns
        assert "classification_confidence" not in outputs_columns
        assert "classification_reasoning" not in outputs_columns
        assert "classified_at" not in outputs_columns

        row = conn.execute(
            """
            SELECT
                job_type,
                automation_platform,
                classification_confidence,
                classification_reasoning,
                classified_at
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "automation"
        assert row[1] == "n8n"
        assert row[2] == "high"
        assert row[3] == "Explicit n8n mention in job description."
        assert row[4] is not None


def test_upgrade_constraints_and_downgrade_round_trip_backfill() -> None:
    db_path = Path(tempfile.gettempdir()) / f"cutover_roundtrip_{uuid4().hex}.db"
    database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    _run_alembic(command="upgrade", revision="20260407_0005", database_url=database_url)
    with sqlite3.connect(db_path) as conn:
        _, job_id = _insert_seed_rows(conn)

    _run_alembic(command="upgrade", revision="20260408_0006", database_url=database_url)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE jobs
            SET
                job_type = ?,
                automation_platform = ?,
                classification_confidence = ?,
                classification_reasoning = ?,
                classified_at = ?
            WHERE id = ?
            """,
            (
                "automation",
                "make",
                "medium",
                "Platform changed based on latest notes.",
                "2026-04-08T12:30:00Z",
                job_id,
            ),
        )
        conn.commit()

        for column, value in (
            ("job_type", "invalid_value"),
            ("automation_platform", "not_supported"),
            ("classification_confidence", "certain"),
        ):
            try:
                conn.execute(f"UPDATE jobs SET {column} = ? WHERE id = ?", (value, job_id))
                conn.commit()
                assert False, f"Expected check constraint failure for {column}"
            except sqlite3.IntegrityError:
                conn.rollback()

    _run_alembic(command="downgrade", revision="20260407_0005", database_url=database_url)

    with sqlite3.connect(db_path) as conn:
        jobs_columns = _table_columns(conn, "jobs")
        outputs_columns = _table_columns(conn, "job_outputs")

        assert "job_type" not in jobs_columns
        assert "automation_platform" not in jobs_columns
        assert "classification_confidence" not in jobs_columns
        assert "classification_reasoning" not in jobs_columns
        assert "classified_at" not in jobs_columns

        assert "job_type" in outputs_columns
        assert "automation_platform" in outputs_columns
        assert "classification_confidence" in outputs_columns
        assert "classification_reasoning" in outputs_columns
        assert "classified_at" in outputs_columns

        row = conn.execute(
            """
            SELECT
                job_type,
                automation_platform,
                classification_confidence,
                classification_reasoning,
                classified_at
            FROM job_outputs
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "automation"
        assert row[1] == "make"
        assert row[2] == "medium"
        assert row[3] == "Platform changed based on latest notes."
        assert row[4] is not None
        assert str(row[4]).startswith("2026-04-08 12:30:00")
