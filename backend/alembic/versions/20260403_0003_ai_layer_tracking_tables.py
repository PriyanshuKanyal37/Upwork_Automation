"""Add AI layer tracking and revision tables.

Revision ID: 20260403_0003
Revises: 20260402_0002
Create Date: 2026-04-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260403_0003"
down_revision: str | None = "20260402_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_generation_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("run_type", sa.String(length=32), server_default="generate", nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("routing_mode", sa.String(length=32), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("prompt_hash", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="running", nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_generation_runs_job_created_at", "job_generation_runs", ["job_id", "created_at"], unique=False)
    op.create_index("ix_job_generation_runs_user_created_at", "job_generation_runs", ["user_id", "created_at"], unique=False)
    op.create_index("ix_job_generation_runs_status", "job_generation_runs", ["status"], unique=False)

    op.create_table(
        "job_output_revisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("generation_run_id", sa.UUID(), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("is_selected", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_approved_snapshot", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["generation_run_id"], ["job_generation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "artifact_type", "version_number", name="uq_job_output_revisions_job_artifact_version"),
    )
    op.create_index(
        "ix_job_output_revisions_job_artifact_created_at",
        "job_output_revisions",
        ["job_id", "artifact_type", "created_at"],
        unique=False,
    )

    op.create_table(
        "job_approval_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("approved_revision_map", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_job_approval_snapshots_job_created_at",
        "job_approval_snapshots",
        ["job_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("generation_run_id", sa.UUID(), nullable=True),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=32), server_default="generation", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="success", nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["generation_run_id"], ["job_generation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usage_events_user_created_at", "llm_usage_events", ["user_id", "created_at"], unique=False)
    op.create_index(
        "ix_llm_usage_events_provider_model_created_at",
        "llm_usage_events",
        ["provider", "model_name", "created_at"],
        unique=False,
    )

    op.create_table(
        "llm_usage_daily_rollups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rollup_date", sa.Date(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("calls_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("successful_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_estimated_cost_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rollup_date",
            "user_id",
            "provider",
            "model_name",
            name="uq_llm_usage_daily_rollups_date_user_provider_model",
        ),
    )
    op.create_index(
        "ix_llm_usage_daily_rollups_user_date",
        "llm_usage_daily_rollups",
        ["user_id", "rollup_date"],
        unique=False,
    )

    op.create_table(
        "llm_provider_health_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="degraded", nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_llm_provider_health_events_provider_occurred_at",
        "llm_provider_health_events",
        ["provider", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_llm_provider_health_events_status_occurred_at",
        "llm_provider_health_events",
        ["status", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_llm_provider_health_events_status_occurred_at", table_name="llm_provider_health_events")
    op.drop_index("ix_llm_provider_health_events_provider_occurred_at", table_name="llm_provider_health_events")
    op.drop_table("llm_provider_health_events")

    op.drop_index("ix_llm_usage_daily_rollups_user_date", table_name="llm_usage_daily_rollups")
    op.drop_table("llm_usage_daily_rollups")

    op.drop_index("ix_llm_usage_events_provider_model_created_at", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_user_created_at", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")

    op.drop_index("ix_job_approval_snapshots_job_created_at", table_name="job_approval_snapshots")
    op.drop_table("job_approval_snapshots")

    op.drop_index("ix_job_output_revisions_job_artifact_created_at", table_name="job_output_revisions")
    op.drop_table("job_output_revisions")

    op.drop_index("ix_job_generation_runs_status", table_name="job_generation_runs")
    op.drop_index("ix_job_generation_runs_user_created_at", table_name="job_generation_runs")
    op.drop_index("ix_job_generation_runs_job_created_at", table_name="job_generation_runs")
    op.drop_table("job_generation_runs")
