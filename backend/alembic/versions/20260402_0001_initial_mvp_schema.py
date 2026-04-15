"""Initial MVP schema.

Revision ID: 20260402_0001
Revises:
Create Date: 2026-04-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260402_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("upwork_profile_url", sa.String(length=2048), nullable=True),
        sa.Column("upwork_profile_id", sa.String(length=120), nullable=True),
        sa.Column("upwork_profile_markdown", sa.Text(), nullable=True),
        sa.Column("proposal_template", sa.Text(), nullable=True),
        sa.Column("doc_template", sa.Text(), nullable=True),
        sa.Column("loom_template", sa.Text(), nullable=True),
        sa.Column("workflow_template_notes", sa.Text(), nullable=True),
        sa.Column("custom_global_instruction", sa.Text(), nullable=True),
        sa.Column("custom_prompt_blocks", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("job_url", sa.String(length=2048), nullable=False),
        sa.Column("upwork_job_id", sa.String(length=128), nullable=True),
        sa.Column("job_markdown", sa.Text(), nullable=True),
        sa.Column("notes_markdown", sa.Text(), nullable=True),
        sa.Column("platform_detected", sa.String(length=64), server_default="n8n", nullable=False),
        sa.Column("status", sa.String(length=64), server_default="draft", nullable=False),
        sa.Column("plan_approved", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_submitted_to_upwork", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=True),
        sa.Column("airtable_record_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_user_created_at", "jobs", ["user_id", "created_at"], unique=False)
    op.create_index("ix_jobs_upwork_job_id", "jobs", ["upwork_job_id"], unique=False)
    op.create_index("ix_jobs_status", "jobs", ["status"], unique=False)
    op.create_index("ix_jobs_platform_detected", "jobs", ["platform_detected"], unique=False)

    op.create_table(
        "job_outputs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("google_doc_url", sa.String(length=2048), nullable=True),
        sa.Column("google_doc_markdown", sa.Text(), nullable=True),
        sa.Column("workflow_jsons", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("loom_script", sa.Text(), nullable=True),
        sa.Column("proposal_text", sa.Text(), nullable=True),
        sa.Column("extra_files_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("edit_log_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )

    op.create_table(
        "user_connectors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("connector_name", sa.String(length=64), nullable=False),
        sa.Column("credential_ref", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=64), server_default="connected", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "connector_name", name="uq_user_connectors_user_connector"),
    )


def downgrade() -> None:
    op.drop_table("user_connectors")

    op.drop_table("job_outputs")

    op.drop_index("ix_jobs_platform_detected", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_upwork_job_id", table_name="jobs")
    op.drop_index("ix_jobs_user_created_at", table_name="jobs")
    op.drop_table("jobs")

    op.drop_table("user_profiles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
