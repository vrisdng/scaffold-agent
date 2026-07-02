"""LiteLLM gateway wrapper with deterministic local fallback."""

from __future__ import annotations

import contextlib
import io
import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from maikit_core.agent_spec import AgentSpec
from maikit_core.schemas import TriageResult


@dataclass(frozen=True)
class ModelPricing:
    input_usd_per_1m_tokens: float
    output_usd_per_1m_tokens: float
    source: str


class TokenUsageEstimate(BaseModel):
    input_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    source: str


class CostBreakdown(BaseModel):
    input_cost_usd: float = Field(ge=0)
    reasoning_cost_usd: float = Field(ge=0)
    output_cost_usd: float = Field(ge=0)
    total_cost_usd: float = Field(ge=0)
    source: str


class LlmCompletion(BaseModel):
    result: TriageResult
    token_usage: TokenUsageEstimate
    cost: CostBreakdown


DEFAULT_MODEL_PRICING: dict[str, ModelPricing] = {
    "gpt-4.1-mini": ModelPricing(0.40, 1.60, "built_in_estimate"),
    "gpt-4.1": ModelPricing(2.00, 8.00, "built_in_estimate"),
    "gpt-4o-mini": ModelPricing(0.15, 0.60, "built_in_estimate"),
    "gpt-4o": ModelPricing(2.50, 10.00, "built_in_estimate"),
}


def generate_triage_result(
    input_text: str,
    spec: AgentSpec,
    prompt_text: str | None = None,
) -> TriageResult:
    """Generates a triage result using LiteLLM when explicitly enabled.

    The default path is deterministic so the MVP works without credentials or
    network access. Set MAIKIT_USE_LLM=1 to attempt a live LiteLLM call.
    """
    return generate_triage_completion(input_text, spec, prompt_text).result


def generate_triage_completion(
    input_text: str,
    spec: AgentSpec,
    prompt_text: str | None = None,
) -> LlmCompletion:
    """Generates a triage result plus token and cost accounting metadata."""
    if os.getenv("MAIKIT_USE_LLM") == "1":
        live_completion = _try_litellm(input_text, spec, prompt_text)
        if live_completion is not None:
            return live_completion

    result = deterministic_triage_result(input_text, spec)
    token_usage = estimate_token_usage(
        prompt_text=prompt_text,
        input_text=input_text,
        output_text=result.model_dump_json(),
    )
    cost = estimate_model_cost_usd(spec.model.name, token_usage)
    return LlmCompletion(
        result=result,
        token_usage=token_usage,
        cost=cost,
    )


def deterministic_triage_result(input_text: str, spec: AgentSpec) -> TriageResult:
    """Returns a valid local triage result for demos and tests."""
    lowered = input_text.lower()
    affected_system = _extract_affected_system(lowered)
    is_latency = "latency" in lowered or "slow" in lowered or "p95" in lowered
    mentions_deploy = "deploy" in lowered or "release" in lowered
    mentions_spike = "spike" in lowered or "spiked" in lowered or "increased" in lowered

    if any(term in lowered for term in ["outage", "down", "unavailable", "sev1"]):
        severity = "critical"
    elif any(term in lowered for term in ["error budget", "p99", "timeouts", "sev2"]):
        severity = "high"
    elif is_latency or mentions_spike or mentions_deploy:
        severity = "medium"
    else:
        severity = "low"

    evidence: list[str] = []
    if affected_system:
        evidence.append(f"input names {affected_system}")
    if is_latency:
        evidence.append("input mentions latency symptoms")
    if mentions_spike:
        evidence.append("input describes a spike")
    if mentions_deploy:
        evidence.append("input mentions a recent deploy")

    missing_info = (
        ["time window", "p95/p99", "deploy id"]
        if is_latency
        else [
            "time window",
            "affected users",
            "recent changes",
        ]
    )
    safe_next_action = (
        "check deploy timeline and latency dashboard"
        if is_latency
        else "ask for missing incident details"
    )
    confidence = 0.68 if is_latency and mentions_deploy else 0.55

    return TriageResult(
        issue_type="latency_incident" if is_latency else "general_incident",
        severity=severity,
        affected_system=affected_system,
        evidence=evidence,
        missing_info=missing_info,
        safe_next_action=safe_next_action,
        blocked_actions=list(spec.policy.blocked_actions),
        requires_human_approval=severity in {"medium", "high", "critical"},
        confidence=confidence,
    )


def estimate_run_tokens(
    input_text: str,
    prompt_text: str | None = None,
    output_text: str | None = None,
) -> int:
    """Returns a rough total token estimate for MVP traces."""
    return estimate_token_usage(prompt_text, input_text, output_text).total_tokens


def estimate_token_usage(
    prompt_text: str | None,
    input_text: str,
    output_text: str | None,
) -> TokenUsageEstimate:
    """Estimates input/output tokens without a fixed floor.

    This is intentionally simple for the MVP. Live provider usage, when
    available, replaces this estimate.
    """
    input_tokens = estimate_text_tokens(prompt_text or "") + estimate_text_tokens(
        input_text
    )
    output_tokens = estimate_text_tokens(output_text or "")
    return TokenUsageEstimate(
        input_tokens=input_tokens,
        reasoning_tokens=0,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        source="estimated_chars_per_4",
    )


def estimate_text_tokens(text: str) -> int:
    """Estimates tokens from text length using a common 4 chars/token heuristic."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def estimate_model_cost_usd(
    model_name: str,
    token_usage: TokenUsageEstimate,
) -> CostBreakdown:
    """Estimates USD cost for a run from token counts and model pricing."""
    pricing = _model_pricing(model_name)
    if pricing is None:
        return CostBreakdown(
            input_cost_usd=0,
            reasoning_cost_usd=0,
            output_cost_usd=0,
            total_cost_usd=0,
            source="unknown_model",
        )

    input_cost = token_usage.input_tokens / 1_000_000 * pricing.input_usd_per_1m_tokens
    reasoning_cost = (
        token_usage.reasoning_tokens / 1_000_000 * pricing.output_usd_per_1m_tokens
    )
    output_cost = (
        token_usage.output_tokens / 1_000_000 * pricing.output_usd_per_1m_tokens
    )
    return CostBreakdown(
        input_cost_usd=round(input_cost, 8),
        reasoning_cost_usd=round(reasoning_cost, 8),
        output_cost_usd=round(output_cost, 8),
        total_cost_usd=round(input_cost + reasoning_cost + output_cost, 8),
        source=pricing.source,
    )


def _extract_affected_system(lowered_input: str) -> str | None:
    match = re.search(
        r"\b([a-z0-9]+(?:-[a-z0-9]+)*-(?:api|service|worker|db|frontend|backend))\b",
        lowered_input,
    )
    return match.group(1) if match else None


def _try_litellm(
    input_text: str,
    spec: AgentSpec,
    prompt_text: str | None,
) -> LlmCompletion | None:
    try:
        import litellm  # type: ignore[import-not-found]
    except ImportError:
        return None

    system_prompt = prompt_text or "Return only JSON matching the TriageResult schema."
    user_prompt = (
        "Triage this incident message and return JSON with these keys: "
        "issue_type, severity, affected_system, evidence, missing_info, "
        "safe_next_action, blocked_actions, requires_human_approval, confidence.\n\n"
        f"Message: {input_text}"
    )

    try:
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            response: Any = litellm.completion(
                model=spec.model.name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
            )
        content = response["choices"][0]["message"]["content"]
        result = TriageResult.model_validate(json.loads(content))
        token_usage = _token_usage_from_litellm_response(
            response,
            prompt_text,
            input_text,
            result.model_dump_json(),
        )
        cost = estimate_model_cost_usd(spec.model.name, token_usage)
        return LlmCompletion(
            result=result,
            token_usage=token_usage,
            cost=cost,
        )
    except Exception:
        if os.getenv("MAIKIT_STRICT_LLM") == "1":
            raise
        return None


def _token_usage_from_litellm_response(
    response: Any,
    prompt_text: str | None,
    input_text: str,
    output_text: str,
) -> TokenUsageEstimate:
    usage = _extract_usage(response)
    prompt_tokens = _usage_value(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _usage_value(usage, "completion_tokens", "output_tokens")
    total_tokens = _usage_value(usage, "total_tokens")
    reasoning_tokens = _reasoning_tokens_from_usage(usage)

    if prompt_tokens is not None and completion_tokens is not None:
        visible_output_tokens = max(0, completion_tokens - reasoning_tokens)
        return TokenUsageEstimate(
            input_tokens=prompt_tokens,
            reasoning_tokens=reasoning_tokens,
            output_tokens=visible_output_tokens,
            total_tokens=total_tokens or prompt_tokens + completion_tokens,
            source="provider_usage",
        )

    return estimate_token_usage(prompt_text, input_text, output_text)


def _extract_usage(response: Any) -> Any:
    if isinstance(response, dict):
        return response.get("usage")
    return getattr(response, "usage", None)


def _usage_value(usage: Any, *keys: str) -> int | None:
    for key in keys:
        if isinstance(usage, dict) and usage.get(key) is not None:
            return int(usage[key])
        value = getattr(usage, key, None)
        if value is not None:
            return int(value)
    return None


def _reasoning_tokens_from_usage(usage: Any) -> int:
    details = _usage_nested_value(
        usage,
        "completion_tokens_details",
        "output_tokens_details",
    )
    value = _usage_value(details, "reasoning_tokens")
    return value or 0


def _usage_nested_value(usage: Any, *keys: str) -> Any:
    for key in keys:
        if isinstance(usage, dict) and usage.get(key) is not None:
            return usage[key]
        value = getattr(usage, key, None)
        if value is not None:
            return value
    return None


def _model_pricing(model_name: str) -> ModelPricing | None:
    input_override = os.getenv("MAIKIT_INPUT_COST_PER_1M")
    output_override = os.getenv("MAIKIT_OUTPUT_COST_PER_1M")
    if input_override and output_override:
        return ModelPricing(
            float(input_override),
            float(output_override),
            "env_override",
        )

    normalized = model_name.lower()
    if normalized in DEFAULT_MODEL_PRICING:
        return DEFAULT_MODEL_PRICING[normalized]

    for known_model, pricing in DEFAULT_MODEL_PRICING.items():
        if normalized.startswith(known_model):
            return pricing
    return None
