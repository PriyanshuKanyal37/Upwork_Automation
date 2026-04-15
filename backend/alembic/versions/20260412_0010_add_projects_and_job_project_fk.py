"""Add projects table and optional jobs.project_id foreign key.

Revision ID: 20260412_0010
Revises: 20260412_0009
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260412_0010"
down_revision: str | None = "20260412_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_projects_user_name"),
    )
    op.create_index("ix_projects_user_created_at", "projects", ["user_id", "created_at"], unique=False)

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.UUID(), nullable=True))
        batch_op.create_foreign_key(
            "fk_jobs_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_jobs_user_project_created_at",
            ["user_id", "project_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_user_project_created_at")
        batch_op.drop_constraint("fk_jobs_project_id_projects", type_="foreignkey")
        batch_op.drop_column("project_id")

    op.drop_index("ix_projects_user_created_at", table_name="projects")
    op.drop_table("projects")

