from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_user_created_at", "user_id", "created_at"),
        Index("ix_jobs_upwork_job_id", "upwork_job_id"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_platform_detected", "platform_detected"),
        Index("ix_jobs_submission_window_user", "is_submitted_to_upwork", "submitted_at", "user_id"),
        Index("ix_jobs_user_project_created_at", "user_id", "project_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    job_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    upwork_job_id: Mapped[str | None] = mapped_column(String(128))
    job_markdown: Mapped[str | None] = mapped_column(Text)
    job_explanation: Mapped[str | None] = mapped_column(Text)
    notes_markdown: Mapped[str | None] = mapped_column(Text)
    extraction_error: Mapped[str | None] = mapped_column(Text)
    requires_manual_markdown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    platform_detected: Mapped[str] = mapped_column(String(64), nullable=False, default="n8n")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    plan_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_submitted_to_upwork: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outcome: Mapped[str | None] = mapped_column(String(64))
    job_type: Mapped[str | None] = mapped_column(String(32))
    automation_platform: Mapped[str | None] = mapped_column(String(32))
    classification_confidence: Mapped[str | None] = mapped_column(String(16))
    classification_reasoning: Mapped[str | None] = mapped_column(Text)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    airtable_record_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
