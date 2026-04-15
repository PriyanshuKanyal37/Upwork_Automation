"""Consolidate AI tracking schema into minimal tables.

Revision ID: 20260403_0004
Revises: 20260403_0003
Create Date: 2026-04-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260403_0004"
down_revision: str | None = "20260403_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Consolidate revision/snapshot/usage data into the existing job_outputs row.
    op.add_column(
        "job_outputs",
        sa.Column("artifact_versions_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    op.add_column(
        "job_outputs",
        sa.Column("approval_snapshot_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )
    op.add_column(
        "job_outputs",
        sa.Column("ai_usage_summary_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Backfill artifact revisions.
        op.execute(
            sa.text(
                """
                WITH revisions AS (
                    SELECT
                        job_id,
                        jsonb_agg(
                            jsonb_build_object(
                                'id', id,
                                'artifact_type', artifact_type,
                                'version_number', version_number,
                                'content_text', content_text,
                                'content_json', content_json,
                                'instruction', instruction,
                                'is_selected', is_selected,
                                'is_approved_snapshot', is_approved_snapshot,
                                'generation_run_id', generation_run_id,
                                'created_at', created_at
                            )
                            ORDER BY artifact_type, version_number
                        ) AS versions
                    FROM job_output_revisions
                    GROUP BY job_id
                )
                UPDATE job_outputs jo
                SET artifact_versions_json = revisions.versions::json
                FROM revisions
                WHERE jo.job_id = revisions.job_id;
                """
            )
        )

        # Backfill latest approval snapshot.
        op.execute(
            sa.text(
                """
                WITH latest_snapshot AS (
                    SELECT DISTINCT ON (job_id)
                        job_id,
                        id,
                        user_id,
                        approved_revision_map,
                        notes,
                        created_at
                    FROM job_approval_snapshots
                    ORDER BY job_id, created_at DESC
                )
                UPDATE job_outputs jo
                SET approval_snapshot_json = jsonb_build_object(
                    'snapshot_id', latest_snapshot.id,
                    'user_id', latest_snapshot.user_id,
                    'approved_revision_map', latest_snapshot.approved_revision_map,
                    'notes', latest_snapshot.notes,
                    'created_at', latest_snapshot.created_at
                )::json
                FROM latest_snapshot
                WHERE jo.job_id = latest_snapshot.job_id;
                """
            )
        )

        # Backfill usage summary per job from llm usage events.
        op.execute(
            sa.text(
                """
                WITH usage_summary AS (
                    SELECT
                        job_id,
                        jsonb_build_object(
                            'total_calls', count(*),
                            'successful_calls', count(*) FILTER (WHERE status = 'success'),
                            'failed_calls', count(*) FILTER (WHERE status <> 'success'),
                            'total_input_tokens', COALESCE(sum(input_tokens), 0),
                            'total_output_tokens', COALESCE(sum(output_tokens), 0),
                            'total_estimated_cost_usd', COALESCE(sum(estimated_cost_usd), 0)
                        ) AS summary
                    FROM llm_usage_events
                    GROUP BY job_id
                )
                UPDATE job_outputs jo
                SET ai_usage_summary_json = usage_summary.summary::json
                FROM usage_summary
                WHERE jo.job_id = usage_summary.job_id;
                """
            )
        )

    # Remove over-normalized tables. Keep only job_generation_runs for AI telemetry.
    op.drop_table("llm_provider_health_events")
    op.drop_table("llm_usage_daily_rollups")
    op.drop_table("llm_usage_events")
    op.drop_table("job_approval_snapshots")
    op.drop_table("job_output_revisions")


def downgrade() -> None:
    # Recreate dropped tables as empty structures.
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
    op.create_index("ix_job_approval_snapshots_job_created_at", "job_approval_snapshots", ["job_id", "created_at"], unique=False)

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
    op.create_index("ix_llm_usage_daily_rollups_user_date", "llm_usage_daily_rollups", ["user_id", "rollup_date"], unique=False)

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

    op.drop_column("job_outputs", "ai_usage_summary_json")
    op.drop_column("job_outputs", "approval_snapshot_json")
    op.drop_column("job_outputs", "artifact_versions_json")
