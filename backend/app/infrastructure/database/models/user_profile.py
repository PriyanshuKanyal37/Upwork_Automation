from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    upwork_profile_url: Mapped[str | None] = mapped_column(String(2048))
    upwork_profile_id: Mapped[str | None] = mapped_column(String(120))
    upwork_profile_markdown: Mapped[str | None] = mapped_column(Text)
    proposal_template: Mapped[str | None] = mapped_column(Text)
    doc_template: Mapped[str | None] = mapped_column(Text)
    loom_template: Mapped[str | None] = mapped_column(Text)
    workflow_template_notes: Mapped[str | None] = mapped_column(Text)
    custom_global_instruction: Mapped[str | None] = mapped_column(Text)
    custom_prompt_blocks: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
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
