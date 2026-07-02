"""Budget accounting helpers for local agent runs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from maikit_core.agent_spec import BudgetConfig


class Usage(BaseModel):
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    subagents: int = Field(ge=0)
    estimated_input_tokens: int = Field(default=0, ge=0)
    estimated_reasoning_tokens: int = Field(default=0, ge=0)
    estimated_output_tokens: int = Field(default=0, ge=0)
    estimated_tokens: int = Field(ge=0)
    input_cost_usd: float = Field(default=0, ge=0)
    reasoning_cost_usd: float = Field(default=0, ge=0)
    output_cost_usd: float = Field(default=0, ge=0)
    total_cost_usd: float = Field(default=0, ge=0)


class BudgetDecision(BaseModel):
    status: Literal["ok", "exceeded"]
    exceeded_limits: list[str] = Field(default_factory=list)
    on_exceed: str
    total_cost_usd: float = Field(ge=0)
    max_estimated_cost_usd: float = Field(ge=0)
    budget_used_pct: float = Field(ge=0)


def check_budget(usage: Usage, budget: BudgetConfig) -> BudgetDecision:
    """Checks run usage against the configured agent budget."""
    exceeded_limits: list[str] = []
    if usage.model_calls > budget.max_model_calls:
        exceeded_limits.append("max_model_calls")
    if usage.tool_calls > budget.max_tool_calls:
        exceeded_limits.append("max_tool_calls")
    if usage.subagents > budget.max_subagents:
        exceeded_limits.append("max_subagents")
    if usage.estimated_tokens > budget.max_estimated_tokens:
        exceeded_limits.append("max_estimated_tokens")
    if usage.total_cost_usd > budget.max_estimated_cost_usd:
        exceeded_limits.append("max_estimated_cost_usd")

    if budget.max_estimated_cost_usd:
        used_pct = round(
            (usage.total_cost_usd / budget.max_estimated_cost_usd) * 100,
            4,
        )
    else:
        used_pct = 0

    return BudgetDecision(
        status="exceeded" if exceeded_limits else "ok",
        exceeded_limits=exceeded_limits,
        on_exceed=budget.on_exceed,
        total_cost_usd=usage.total_cost_usd,
        max_estimated_cost_usd=budget.max_estimated_cost_usd,
        budget_used_pct=used_pct,
    )
