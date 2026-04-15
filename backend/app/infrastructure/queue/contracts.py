from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class JobExtractionTask:
    user_id: UUID
    job_id: UUID
    idempotency_key: str
    requested_at: str

    @classmethod
    def create(cls, *, user_id: UUID, job_id: UUID) -> "JobExtractionTask":
        seed = f"{user_id}:{job_id}".encode("utf-8")
        idem_key = sha256(seed).hexdigest()
        requested_at = datetime.now(UTC).isoformat()
        return cls(
            user_id=user_id,
            job_id=job_id,
            idempotency_key=idem_key,
            requested_at=requested_at,
        )

    def to_payload(self) -> dict[str, str]:
        return {
            "user_id": str(self.user_id),
            "job_id": str(self.job_id),
            "idempotency_key": self.idempotency_key,
            "requested_at": self.requested_at,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "JobExtractionTask":
        return cls(
            user_id=UUID(str(payload["user_id"])),
            job_id=UUID(str(payload["job_id"])),
            idempotency_key=str(payload["idempotency_key"]),
            requested_at=str(payload["requested_at"]),
        )


@dataclass(frozen=True, slots=True)
class JobGenerationTask:
    user_id: UUID
    job_id: UUID
    run_type: str
    target_artifact: str | None
    instruction: str | None
    additional_context: dict[str, Any] | None
    idempotency_key: str
    requested_at: str

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        job_id: UUID,
        run_type: str,
        target_artifact: str | None = None,
        instruction: str | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> "JobGenerationTask":
        context_serialized = (
            json.dumps(additional_context, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            if additional_context
            else ""
        )
        seed = (
            f"{user_id}:{job_id}:{run_type}:{target_artifact or ''}:{instruction or ''}:{context_serialized}"
        ).encode("utf-8")
        idem_key = sha256(seed).hexdigest()
        requested_at = datetime.now(UTC).isoformat()
        return cls(
            user_id=user_id,
            job_id=job_id,
            run_type=run_type,
            target_artifact=target_artifact,
            instruction=instruction,
            additional_context=additional_context,
            idempotency_key=idem_key,
            requested_at=requested_at,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.user_id),
            "job_id": str(self.job_id),
            "run_type": self.run_type,
            "target_artifact": self.target_artifact,
            "instruction": self.instruction,
            "additional_context": self.additional_context,
            "idempotency_key": self.idempotency_key,
            "requested_at": self.requested_at,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "JobGenerationTask":
        return cls(
            user_id=UUID(str(payload["user_id"])),
            job_id=UUID(str(payload["job_id"])),
            run_type=str(payload["run_type"]),
            target_artifact=str(payload["target_artifact"]) if payload.get("target_artifact") else None,
            instruction=str(payload["instruction"]) if payload.get("instruction") else None,
            additional_context=(payload.get("additional_context") if isinstance(payload.get("additional_context"), dict) else None),
            idempotency_key=str(payload["idempotency_key"]),
            requested_at=str(payload["requested_at"]),
        )
