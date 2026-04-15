"""Add classification and workflow explanation fields to job outputs.

Revision ID: 20260407_0005
Revises: 20260403_0004
Create Date: 2026-04-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260407_0005"
down_revision: str | None = "20260403_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job_outputs", sa.Column("job_type", sa.String(length=32), nullable=True))
    op.add_column("job_outputs", sa.Column("automation_platform", sa.String(length=32), nullable=True))
    op.add_column("job_outputs", sa.Column("classification_confidence", sa.String(length=16), nullable=True))
    op.add_column("job_outputs", sa.Column("classification_reasoning", sa.Text(), nullable=True))
    op.add_column("job_outputs", sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("job_outputs", sa.Column("workflow_explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_outputs", "workflow_explanation")
    op.drop_column("job_outputs", "classified_at")
    op.drop_column("job_outputs", "classification_reasoning")
    op.drop_column("job_outputs", "classification_confidence")
    op.drop_column("job_outputs", "automation_platform")
    op.drop_column("job_outputs", "job_type")
