from __future__ import annotations

from app.application.ai.contracts import ArtifactPayload, ArtifactType, ValidationIssue, ValidationResult
from app.application.ai.validators.ghl_validator import validate_build_spec
from app.application.ai.validators.make_validator import validate_nested_blueprint
from app.application.ai.validators.text_validator import TextArtifactValidator
from app.application.ai.validators.workflow_validator import WorkflowArtifactValidator

_text_validator = TextArtifactValidator()
_workflow_validator = WorkflowArtifactValidator()

_TEXT_TYPES = {
    ArtifactType.PROPOSAL,
    ArtifactType.COVER_LETTER,
    ArtifactType.LOOM_SCRIPT,
    ArtifactType.DOC,
}


def _invalid_from_errors(*, code: str, message: str, errors: list[str]) -> ValidationResult:
    if not errors:
        return ValidationResult.valid()
    return ValidationResult.invalid(
        [
            ValidationIssue(
                code=code,
                message=f"{message}: {err}",
                path="content_json",
            )
            for err in errors[:10]
        ]
    )


def _validate_make_workflow(artifact: ArtifactPayload) -> ValidationResult:
    if not isinstance(artifact.content_json, dict):
        return ValidationResult.invalid(
            [
                ValidationIssue(
                    code="missing_make_blueprint",
                    message="Make workflow requires blueprint JSON object",
                    path="content_json",
                )
            ]
        )
    return _invalid_from_errors(
        code="invalid_make_blueprint",
        message="Make workflow blueprint failed validation",
        errors=validate_nested_blueprint(artifact.content_json),
    )


def _validate_ghl_workflow(artifact: ArtifactPayload) -> ValidationResult:
    if not isinstance(artifact.content_json, dict):
        return ValidationResult.invalid(
            [
                ValidationIssue(
                    code="missing_ghl_build_spec",
                    message="GHL workflow requires build spec JSON object",
                    path="content_json",
                )
            ]
        )
    return _invalid_from_errors(
        code="invalid_ghl_build_spec",
        message="GHL build spec failed validation",
        errors=validate_build_spec(artifact.content_json),
    )


def validate_artifact_payload(artifact: ArtifactPayload) -> ValidationResult:
    if artifact.artifact_type == ArtifactType.WORKFLOW:
        return _workflow_validator.validate(artifact)
    if artifact.artifact_type == ArtifactType.MAKE_WORKFLOW:
        return _validate_make_workflow(artifact)
    if artifact.artifact_type == ArtifactType.GHL_WORKFLOW:
        return _validate_ghl_workflow(artifact)
    if artifact.artifact_type in _TEXT_TYPES:
        return _text_validator.validate(artifact)
    return ValidationResult.invalid(
        [
            ValidationIssue(
                code="unsupported_artifact_type",
                message="No validator registered for artifact type",
                path="artifact_type",
            )
        ]
    )
