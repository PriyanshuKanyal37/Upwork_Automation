"""Allow ghl in jobs.automation_platform check constraint.

Revision ID: 20260410_0007
Revises: 20260408_0006
Create Date: 2026-04-10
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260410_0007"
down_revision: str | None = "20260408_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("ck_jobs_automation_platform", type_="check")
        batch_op.create_check_constraint(
            "ck_jobs_automation_platform",
            (
                "automation_platform IS NULL OR "
                "automation_platform IN ('n8n','make','ghl','zapier','other_automation','unknown')"
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("ck_jobs_automation_platform", type_="check")
        batch_op.create_check_constraint(
            "ck_jobs_automation_platform",
            (
                "automation_platform IS NULL OR "
                "automation_platform IN ('n8n','make','zapier','other_automation','unknown')"
            ),
        )

