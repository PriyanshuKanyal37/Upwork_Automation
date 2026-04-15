from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class JobOutput(Base):
    __tablename__ = "job_outputs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    google_doc_url: Mapped[str | None] = mapped_column(String(2048))
    google_doc_markdown: Mapped[str | None] = mapped_column(Text)
    workflow_jsons: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    loom_script: Mapped[str | None] = mapped_column(Text)
    proposal_text: Mapped[str | None] = mapped_column(Text)
    extra_files_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    edit_log_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    artifact_versions_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    approval_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ai_usage_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    workflow_explanation: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
