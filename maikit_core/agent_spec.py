"""Pydantic models and loading helpers for generated agent specs."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class AgentSpecError(ValueError):
    """Raised when an agent specification is missing or invalid."""


class StrictModel(BaseModel):
    """Base model that rejects unknown fields in MVP contracts."""

    model_config = ConfigDict(extra="forbid")


class LlmModelConfig(StrictModel):
    provider: str = Field(min_length=1)
    name: str = Field(min_length=1)
    fallback: str | None = None


class PromptConfig(StrictModel):
    version: str = Field(min_length=1)
    file: str = Field(min_length=1)


class OutputSchemaConfig(StrictModel):
    name: str = Field(min_length=1)


class BudgetConfig(StrictModel):
    max_model_calls: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    max_subagents: int = Field(ge=0)
    max_estimated_tokens: int = Field(ge=0)
    max_estimated_cost_usd: float = Field(default=1.0, ge=0)
    on_exceed: Literal["ask_human", "stop", "warn"] = "ask_human"


class PolicyConfig(StrictModel):
    allowed_actions: list[str] = Field(default_factory=list)
    blocked_actions: list[str] = Field(default_factory=list)
    approval_required: list[str] = Field(default_factory=list)

    @field_validator("allowed_actions", "blocked_actions", "approval_required")
    @classmethod
    def _validate_actions(cls, actions: list[str]) -> list[str]:
        cleaned: list[str] = []
        for action in actions:
            value = action.strip()
            if not value:
                raise ValueError("actions must be non-empty strings")
            if value not in cleaned:
                cleaned.append(value)
        return cleaned


class PlatformsConfig(StrictModel):
    cli: bool
    slack: bool
    telegram: bool
    discord: bool = False
    mcp: bool
    cron: bool


class ObservabilityConfig(StrictModel):
    prompt_versioning: bool
    trace_logging: bool
    cost_tracking: bool
    latency_tracking: bool
    store_inputs: Literal["redacted", "raw", "none"] = "redacted"


class AgentSpec(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    model: LlmModelConfig
    prompt: PromptConfig
    output_schema: OutputSchemaConfig
    budget: BudgetConfig
    policy: PolicyConfig
    platforms: PlatformsConfig
    observability: ObservabilityConfig


def load_agent_spec(path: Path) -> AgentSpec:
    """Loads and validates an agent specification.

    Args:
        path: Path to an agent.yaml file.

    Returns:
        A validated AgentSpec.

    Raises:
        AgentSpecError: If the file is missing, malformed, or invalid.
    """
    if not path.exists():
        raise AgentSpecError(f"{path} does not exist")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AgentSpecError(f"{path.name} is not valid YAML: {exc}") from exc
    except OSError as exc:
        raise AgentSpecError(f"Could not read {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise AgentSpecError(
            f"{path.name} must contain a YAML mapping at the top level"
        )

    try:
        return AgentSpec.model_validate(data)
    except ValidationError as exc:
        raise AgentSpecError(
            f"{path.name} is invalid:\n{_format_validation_errors(exc)}"
        ) from exc


def _format_validation_errors(exc: ValidationError) -> str:
    lines: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        message = error["msg"]
        lines.append(f"- {location}: {message}")
    return "\n".join(lines)
