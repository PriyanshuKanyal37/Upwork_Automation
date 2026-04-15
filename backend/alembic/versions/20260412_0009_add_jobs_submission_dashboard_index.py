"""Add jobs submission index for dashboard queries.

Revision ID: 20260412_0009
Revises: 20260410_0008
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260412_0009"
down_revision: str | None = "20260410_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_jobs_submission_window_user",
        "jobs",
        ["is_submitted_to_upwork", "submitted_at", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_submission_window_user", table_name="jobs")

