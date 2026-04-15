from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderName(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class RoutingMode(StrEnum):
    FIXED_PER_ARTIFACT = "fixed_per_artifact"
    DYNAMIC = "dynamic"


class RouteTask(StrEnum):
    JOB_UNDERSTANDING = "job_understanding"
    PROPOSAL = "proposal"
    COVER_LETTER = "cover_letter"
    LOOM_SCRIPT = "loom_script"
    WORKFLOW = "workflow"
    MAKE_WORKFLOW = "make_workflow"
    GHL_WORKFLOW = "ghl_workflow"
    DOC = "doc"
    DIAGRAM = "diagram"


class ArtifactType(StrEnum):
    PROPOSAL = "proposal"
    COVER_LETTER = "cover_letter"
    LOOM_SCRIPT = "loom_script"
    WORKFLOW = "workflow"
    MAKE_WORKFLOW = "make_workflow"
    GHL_WORKFLOW = "ghl_workflow"
    DOC = "doc"


class AutomationPlatformPreference(StrEnum):
    N8N = "n8n"
    MAKE = "make"
    GHL = "ghl"
    BOTH = "both"
    UNKNOWN = "unknown"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class JobType(StrEnum):
    AUTOMATION = "automation"
    AI_ML = "ai_ml"
    WEB_DEV = "web_dev"
    OTHER = "other"


class AutomationPlatform(StrEnum):
    N8N = "n8n"
    MAKE = "make"
    GHL = "ghl"
    ZAPIER = "zapier"
    OTHER = "other_automation"
    UNKNOWN = "unknown"


class JobUnderstandingContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary_short: str = Field(min_length=1, max_length=3000)
    deliverables_required: list[ArtifactType] = Field(default_factory=list)
    screening_questions: list[str] = Field(default_factory=list, max_length=50)
    automation_platform_preference: AutomationPlatformPreference = AutomationPlatformPreference.UNKNOWN
    constraints: dict[str, Any] = Field(default_factory=dict)
    extraction_confidence: ConfidenceLevel
    missing_fields: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("deliverables_required")
    @classmethod
    def dedupe_deliverables(cls, value: list[ArtifactType]) -> list[ArtifactType]:
        return list(dict.fromkeys(value))

    @property
    def is_generation_allowed(self) -> bool:
        return self.extraction_confidence in {ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM}


class GenerationPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: RouteTask
    artifact_type: ArtifactType
    primary_provider: ProviderName
    primary_model: str = Field(min_length=1, max_length=128)
    fallback_provider: ProviderName | None = None
    fallback_model: str | None = Field(default=None, max_length=128)


class GenerationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    user_id: UUID
    routing_mode: RoutingMode
    platform_preference: AutomationPlatformPreference
    requires_platform_confirmation: bool = False
    items: list[GenerationPlanItem] = Field(default_factory=list)
    blocked_reason: str | None = Field(default=None, max_length=256)


class ArtifactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_type: ArtifactType
    content_text: str | None = None
    content_json: dict[str, Any] | list[Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content_text")
    @classmethod
    def normalize_content_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None


class ProviderGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=300_000)
    system_prompt: str | None = Field(default=None, max_length=200_000)
    model_name: str = Field(min_length=1, max_length=128)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, ge=1, le=64_000)
    response_schema: dict[str, Any] | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderGenerateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderName
    model_name: str
    output_text: str | None = None
    output_json: dict[str, Any] | list[Any] | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class JobClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_type: JobType
    automation_platform: AutomationPlatform | None = None
    confidence: Literal["high", "medium", "low"] = "low"
    reasoning: str = Field(default="Classifier fallback", min_length=1, max_length=4000)


class WorkflowIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_type: Literal["webhook", "schedule", "email", "manual", "unknown"] = "unknown"
    source_apps: list[str] = Field(default_factory=list, max_length=20)
    target_apps: list[str] = Field(default_factory=list, max_length=20)
    operations: list[str] = Field(default_factory=list, max_length=20)
    schedule_hint: str | None = Field(default=None, max_length=500)
    reliability_level: Literal["low", "medium", "high"] = "medium"
    confidence: Literal["high", "medium", "low"] = "low"
    reasoning: str = Field(default="Workflow intent fallback", min_length=1, max_length=4000)


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=4000)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    cache_control: dict[str, Any] | None = None


class ToolUse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    input: dict[str, Any] = Field(default_factory=dict)


class ToolChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["auto", "any", "none", "tool"] = "auto"
    name: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None, info: Any) -> str | None:
        choice_type = info.data.get("type")
        if choice_type == "tool":
            if not value or not value.strip():
                raise ValueError("name is required when tool_choice.type is 'tool'")
            return value.strip()
        return value


class ProviderAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[dict[str, Any]] = Field(default_factory=list)
    system_prompt: str | None = Field(default=None, max_length=200_000)
    model_name: str = Field(min_length=1, max_length=128)
    tools: list[ToolDefinition] = Field(default_factory=list)
    tool_choice: ToolChoice | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=8000, ge=1, le=64_000)


class ProviderAgentTurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderName
    model_name: str
    output_text: str | None = None
    tool_uses: list[ToolUse] = Field(default_factory=list)
    stop_reason: str = Field(default="end_turn", min_length=1, max_length=64)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_input_tokens: int = Field(default=0, ge=0)
    cache_creation_input_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class JobUnderstandingExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract: JobUnderstandingContract
    provider: ProviderName
    model_name: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    prompt_version: str | None = Field(default=None, max_length=64)
    prompt_hash: str | None = Field(default=None, max_length=128)


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=1000)
    path: str | None = Field(default=None, max_length=512)


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @classmethod
    def valid(cls) -> ValidationResult:
        return cls(is_valid=True, issues=[])

    @classmethod
    def invalid(cls, issues: list[ValidationIssue]) -> ValidationResult:
        return cls(is_valid=False, issues=issues)
