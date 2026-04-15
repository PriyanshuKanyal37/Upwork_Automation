from __future__ import annotations

import re

from app.application.ai.errors import AIErrorCode, AIException
from app.infrastructure.config.settings import get_settings

_INPUT_BLOCK_PATTERNS = (
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"reveal\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"bypass\s+safety", re.IGNORECASE),
)

_OUTPUT_BLOCK_PATTERNS = (
    # Block explicit key/password assignments with secret-like values.
    re.compile(
        r"(?i)\b(api[_\-\s]?key|secret\s*key|password)\b\s*[:=]\s*[\"']?[A-Za-z0-9_\-\/\+=]{12,}"
    ),
    # Block bearer token leakage.
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9_\-\.=]{12,}"),
    # Block common provider key formats.
    re.compile(r"(?i)\bsk-(?:proj-)?[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"(?i)\bsk-ant-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"(?i)\bAKIA[0-9A-Z]{16}\b"),
    # Block PEM/PKCS private keys.
    re.compile(r"(?i)BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY"),
)


def assert_safe_input(*, content: str, context: str) -> None:
    settings = get_settings()
    if not settings.ai_enable_safety_guardrails:
        return
    for pattern in _INPUT_BLOCK_PATTERNS:
        if pattern.search(content):
            raise AIException(
                code=AIErrorCode.POLICY_DENIED,
                message="Input blocked by AI safety guardrail",
                details={"context": context, "pattern": pattern.pattern},
            )


def assert_safe_output(*, content: str, artifact_type: str) -> None:
    settings = get_settings()
    if not settings.ai_enable_safety_guardrails:
        return
    for pattern in _OUTPUT_BLOCK_PATTERNS:
        if pattern.search(content):
            raise AIException(
                code=AIErrorCode.POLICY_DENIED,
                message="Output blocked by AI safety guardrail",
                details={"artifact_type": artifact_type, "pattern": pattern.pattern},
            )
