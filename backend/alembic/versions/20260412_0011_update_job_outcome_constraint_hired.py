"""Update jobs outcome check constraint to allow hired, remove legacy values.

Revision ID: 20260412_0011
Revises: 20260412_0010
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260412_0011"
down_revision: str | None = "20260412_0010"
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
            "outcome IS NULL OR outcome IN ('sent','not_sent','hired')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_check_constraints("jobs")}

    with op.batch_alter_table("jobs") as batch_op:
        if "jobs_outcome_check" in existing:
            batch_op.drop_constraint("jobs_outcome_check", type_="check")
        batch_op.create_check_constraint(
            "jobs_outcome_check",
            "outcome IS NULL OR outcome IN ('sent','replied','interview','closed','no_reply','not_sent')",
        )
