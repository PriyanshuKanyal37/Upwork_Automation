"""Add not_sent to jobs outcome check constraint.

Revision ID: 20260410_0008
Revises: 20260410_0007
Create Date: 2026-04-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260410_0008"
down_revision: str | None = "20260410_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_check_constraints("jobs")}

    with op.batch_alter_table("jobs") as batch_op:
        if "jobs_outcome_check" in existing:
            batch_op.drop_constraint("jobs_outcome_check", type_="check")
        batch_op.create_check_constraint(
            "jobs_outcome_check",
            "outcome IS NULL OR outcome IN ('sent','replied','interview','closed','no_reply','not_sent')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_check_constraints("jobs")}

    with op.batch_alter_table("jobs") as batch_op:
        if "jobs_outcome_check" in existing:
            batch_op.drop_constraint("jobs_outcome_check", type_="check")
        batch_op.create_check_constraint(
            "jobs_outcome_check",
            "outcome IS NULL OR outcome IN ('sent','replied','interview','closed','no_reply')",
        )
