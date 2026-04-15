"""Add extraction tracking fields to jobs.

Revision ID: 20260402_0002
Revises: 20260402_0001
Create Date: 2026-04-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260402_0002"
down_revision: str | None = "20260402_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("extraction_error", sa.Text(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "requires_manual_markdown",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "requires_manual_markdown")
    op.drop_column("jobs", "extraction_error")

