from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.ai.contracts import ArtifactPayload, ValidationResult


class ArtifactValidator(ABC):
    @abstractmethod
    def validate(self, artifact: ArtifactPayload) -> ValidationResult:
        """Validate generated artifact payload and return validation result."""

