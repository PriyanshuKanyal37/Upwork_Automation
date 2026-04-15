from __future__ import annotations

from typing import Any
from uuid import UUID

from app.infrastructure.logging.setup import get_logger

logger = get_logger("app.audit")


def log_status_change(
    *,
    entity: str,
    entity_id: UUID,
    user_id: UUID,
    previous_status: str | None,
    next_status: str,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    logger.info(
        "audit.status_change",
        extra={
            "entity": entity,
            "entity_id": str(entity_id),
            "user_id": str(user_id),
            "previous_status": previous_status,
            "next_status": next_status,
            "source": source,
            "metadata": metadata or {},
        },
    )
