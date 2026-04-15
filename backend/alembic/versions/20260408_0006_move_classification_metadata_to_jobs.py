"""Move classification metadata from job_outputs to jobs.

Revision ID: 20260408_0006
Revises: 20260407_0005
Create Date: 2026-04-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260408_0006"
down_revision: str | None = "20260407_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALLOWED_JOB_TYPES = {"automation", "ai_ml", "web_dev", "other"}
_ALLOWED_AUTOMATION_PLATFORMS = {"n8n", "make", "zapier", "other_automation", "unknown"}
_ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def _normalize_enum(raw: object, *, allowed: set[str]) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    return text if text in allowed else None


def _normalize_optional_text(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("job_type", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("automation_platform", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("classification_confidence", sa.String(length=16), nullable=True))
    op.add_column("jobs", sa.Column("classification_reasoning", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True))

    bind = op.get_bind()
    job_outputs = sa.table(
        "job_outputs",
        sa.column("job_id", sa.UUID()),
        sa.column("job_type", sa.String()),
        sa.column("automation_platform", sa.String()),
        sa.column("classification_confidence", sa.String()),
        sa.column("classification_reasoning", sa.Text()),
        sa.column("classified_at", sa.DateTime(timezone=True)),
    )
    jobs = sa.table(
        "jobs",
        sa.column("id", sa.UUID()),
        sa.column("job_type", sa.String()),
        sa.column("automation_platform", sa.String()),
        sa.column("classification_confidence", sa.String()),
        sa.column("classification_reasoning", sa.Text()),
        sa.column("classified_at", sa.DateTime(timezone=True)),
    )

    rows = bind.execute(
        sa.select(
            job_outputs.c.job_id,
            job_outputs.c.job_type,
            job_outputs.c.automation_platform,
            job_outputs.c.classification_confidence,
            job_outputs.c.classification_reasoning,
            job_outputs.c.classified_at,
        )
    ).fetchall()
    for row in rows:
        bind.execute(
            sa.update(jobs)
            .where(jobs.c.id == row.job_id)
            .values(
                job_type=_normalize_enum(row.job_type, allowed=_ALLOWED_JOB_TYPES),
                automation_platform=_normalize_enum(
                    row.automation_platform, allowed=_ALLOWED_AUTOMATION_PLATFORMS
                ),
                classification_confidence=_normalize_enum(
                    row.classification_confidence, allowed=_ALLOWED_CONFIDENCE
                ),
                classification_reasoning=_normalize_optional_text(row.classification_reasoning),
                classified_at=row.classified_at,
            )
        )

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.create_check_constraint(
            "ck_jobs_job_type",
            "job_type IS NULL OR job_type IN ('automation','ai_ml','web_dev','other')",
        )
        batch_op.create_check_constraint(
            "ck_jobs_automation_platform",
            (
                "automation_platform IS NULL OR "
                "automation_platform IN ('n8n','make','zapier','other_automation','unknown')"
            ),
        )
        batch_op.create_check_constraint(
            "ck_jobs_classification_confidence",
            "classification_confidence IS NULL OR classification_confidence IN ('high','medium','low')",
        )

    with op.batch_alter_table("job_outputs") as batch_op:
        batch_op.drop_column("job_type")
        batch_op.drop_column("automation_platform")
        batch_op.drop_column("classification_confidence")
        batch_op.drop_column("classification_reasoning")
        batch_op.drop_column("classified_at")


def downgrade() -> None:
    with op.batch_alter_table("job_outputs") as batch_op:
        batch_op.add_column(sa.Column("job_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("automation_platform", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("classification_confidence", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("classification_reasoning", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True))

    bind = op.get_bind()
    job_outputs = sa.table(
        "job_outputs",
        sa.column("job_id", sa.UUID()),
        sa.column("job_type", sa.String()),
        sa.column("automation_platform", sa.String()),
        sa.column("classification_confidence", sa.String()),
        sa.column("classification_reasoning", sa.Text()),
        sa.column("classified_at", sa.DateTime(timezone=True)),
    )
    jobs = sa.table(
        "jobs",
        sa.column("id", sa.UUID()),
        sa.column("job_type", sa.String()),
        sa.column("automation_platform", sa.String()),
        sa.column("classification_confidence", sa.String()),
        sa.column("classification_reasoning", sa.Text()),
        sa.column("classified_at", sa.DateTime(timezone=True)),
    )

    rows = bind.execute(
        sa.select(
            jobs.c.id,
            jobs.c.job_type,
            jobs.c.automation_platform,
            jobs.c.classification_confidence,
            jobs.c.classification_reasoning,
            jobs.c.classified_at,
        )
    ).fetchall()
    for row in rows:
        bind.execute(
            sa.update(job_outputs)
            .where(job_outputs.c.job_id == row.id)
            .values(
                job_type=row.job_type,
                automation_platform=row.automation_platform,
                classification_confidence=row.classification_confidence,
                classification_reasoning=row.classification_reasoning,
                classified_at=row.classified_at,
            )
        )

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("ck_jobs_classification_confidence", type_="check")
        batch_op.drop_constraint("ck_jobs_automation_platform", type_="check")
        batch_op.drop_constraint("ck_jobs_job_type", type_="check")
        batch_op.drop_column("classified_at")
        batch_op.drop_column("classification_reasoning")
        batch_op.drop_column("classification_confidence")
        batch_op.drop_column("automation_platform")
        batch_op.drop_column("job_type")
