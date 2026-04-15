from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    repo_backend = Path(__file__).resolve().parents[1]
    db_path = repo_backend / "ci_migration.db"

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    if db_path.exists():
        db_path.unlink()

    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=repo_backend,
            env=env,
            check=True,
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "base"],
            cwd=repo_backend,
            env=env,
            check=True,
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=repo_backend,
            env=env,
            check=True,
        )
    finally:
        if db_path.exists():
            db_path.unlink()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
