"""Shared structured output schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TriageResult(BaseModel):
    issue_type: str
    severity: Literal["low", "medium", "high", "critical"]
    affected_system: str | None = None
    evidence: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    safe_next_action: str
    blocked_actions: list[str] = Field(default_factory=list)
    requires_human_approval: bool
    confidence: float = Field(ge=0, le=1)

    model_config = ConfigDict(extra="forbid")
