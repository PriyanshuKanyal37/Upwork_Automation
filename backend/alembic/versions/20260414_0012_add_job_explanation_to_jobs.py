"""Add job explanation field to jobs.

Revision ID: 20260414_0012
Revises: 20260412_0011
Create Date: 2026-04-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260414_0012"
down_revision: str | None = "20260412_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("job_explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "job_explanation")
