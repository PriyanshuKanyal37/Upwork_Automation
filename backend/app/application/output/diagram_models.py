from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DiagramLayoutFamily = Literal[
    "roadmap_cards",
    "zigzag_path",
    "swimlane_process",
    "radial_hub_horizontal",
]


class DiagramStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=140)
    detail: str | None = Field(default=None, max_length=220)
    color_token: str | None = Field(default=None, max_length=40)
    icon_key: str | None = Field(default=None, max_length=40)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        normalized = "".join(ch for ch in value.strip().lower() if ch.isalnum() or ch in {"_", "-"})
        return normalized or "step"

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("detail")
    @classmethod
    def normalize_detail(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = " ".join(value.strip().split())
        return stripped or None


class DiagramConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=32)
    target_id: str = Field(min_length=1, max_length=32)
    label: str | None = Field(default=None, max_length=40)
    edge_type: Literal["sequence", "branch", "merge", "feedback"] = "sequence"

    @field_validator("source_id", "target_id")
    @classmethod
    def normalize_ids(cls, value: str) -> str:
        normalized = "".join(ch for ch in value.strip().lower() if ch.isalnum() or ch in {"_", "-"})
        return normalized or "step"


class DiagramSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=180)
    orientation: Literal["horizontal"] = "horizontal"
    layout_family: DiagramLayoutFamily = "roadmap_cards"
    creativity_level: Literal["low", "medium", "high"] = "medium"
    connection_style: Literal["clean", "orthogonal", "curved"] = "clean"
    steps: list[DiagramStep] = Field(min_length=3, max_length=12)
    connections: list[DiagramConnection] = Field(default_factory=list, max_length=32)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return " ".join(value.strip().split())
