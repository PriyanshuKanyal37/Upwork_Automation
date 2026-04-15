from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from app.infrastructure.errors.exceptions import AppException


class AIErrorCode(StrEnum):
    INVALID_ROUTE_CONFIG = "invalid_route_config"
    LOW_CONFIDENCE_UNDERSTANDING = "low_confidence_understanding"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    INVALID_OUTPUT = "invalid_output"
    BUDGET_EXCEEDED = "budget_exceeded"
    POLICY_DENIED = "policy_denied"
    ORCHESTRATION_FAILED = "orchestration_failed"


_STATUS_BY_AI_ERROR_CODE: dict[AIErrorCode, int] = {
    AIErrorCode.INVALID_ROUTE_CONFIG: 500,
    AIErrorCode.LOW_CONFIDENCE_UNDERSTANDING: 422,
    AIErrorCode.PROVIDER_TIMEOUT: 503,
    AIErrorCode.PROVIDER_UNAVAILABLE: 503,
    AIErrorCode.PROVIDER_RATE_LIMITED: 429,
    AIErrorCode.INVALID_OUTPUT: 422,
    AIErrorCode.BUDGET_EXCEEDED: 429,
    AIErrorCode.POLICY_DENIED: 403,
    AIErrorCode.ORCHESTRATION_FAILED: 500,
}


class AIException(AppException):
    def __init__(
        self,
        *,
        code: AIErrorCode,
        message: str,
        details: Mapping[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        resolved_status_code = status_code or _STATUS_BY_AI_ERROR_CODE.get(code, 500)
        super().__init__(
            status_code=resolved_status_code,
            code=code.value,
            message=message,
            details=details,
        )

