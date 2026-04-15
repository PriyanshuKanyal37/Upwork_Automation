from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PublishRequest:
    connector_name: str
    title: str
    content_markdown: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PublishResult:
    connector_name: str
    status: str
    external_id: str | None = None
    external_url: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ConnectorHealthResult:
    connector_name: str
    status: str
    message: str
    is_connected: bool
    action_required: bool
    checked_live: bool
    details: dict[str, Any] | None = None

