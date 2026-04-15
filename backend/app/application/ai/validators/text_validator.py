from __future__ import annotations

from app.application.ai.contracts import ArtifactPayload, ArtifactType, ValidationIssue, ValidationResult
from app.application.ai.validators.base import ArtifactValidator

_TEXT_ARTIFACTS = {
    ArtifactType.PROPOSAL,
    ArtifactType.COVER_LETTER,
    ArtifactType.LOOM_SCRIPT,
    ArtifactType.DOC,
}


class TextArtifactValidator(ArtifactValidator):
    def validate(self, artifact: ArtifactPayload) -> ValidationResult:
        if artifact.artifact_type not in _TEXT_ARTIFACTS:
            return ValidationResult.invalid(
                [
                    ValidationIssue(
                        code="unsupported_artifact_type",
                        message="Text validator received unsupported artifact type",
                    )
                ]
            )

        if not artifact.content_text:
            return ValidationResult.invalid(
                [ValidationIssue(code="missing_text_content", message="Text content is required")]
            )

        if len(artifact.content_text) < 20:
            return ValidationResult.invalid(
                [ValidationIssue(code="text_too_short", message="Text content is too short")]
            )

        return ValidationResult.valid()
