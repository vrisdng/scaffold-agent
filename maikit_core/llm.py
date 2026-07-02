"""LiteLLM gateway wrapper with deterministic local fallback."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from maikit_core.agent_spec import AgentSpec
from maikit_core.schemas import TriageResult


def generate_triage_result(
    input_text: str,
    spec: AgentSpec,
    prompt_text: str | None = None,
) -> TriageResult:
    """Generates a triage result using LiteLLM when explicitly enabled.

    The default path is deterministic so the MVP works without credentials or
    network access. Set MAIKIT_USE_LLM=1 to attempt a live LiteLLM call.
    """
    if os.getenv("MAIKIT_USE_LLM") == "1":
        live_result = _try_litellm(input_text, spec, prompt_text)
        if live_result is not None:
            return live_result

    return deterministic_triage_result(input_text, spec)


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

    missing_info = ["time window", "p95/p99", "deploy id"] if is_latency else [
        "time window",
        "affected users",
        "recent changes",
    ]
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


def estimate_run_tokens(input_text: str, prompt_text: str | None = None) -> int:
    """Returns a rough deterministic token estimate for MVP traces."""
    prompt_chars = len(prompt_text or "")
    estimated = int((len(input_text) + prompt_chars) / 4) + 250
    return max(1450, estimated)


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
) -> TriageResult | None:
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
        response: Any = litellm.completion(
            model=spec.model.name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        content = response["choices"][0]["message"]["content"]
        return TriageResult.model_validate(json.loads(content))
    except Exception:
        if os.getenv("MAIKIT_STRICT_LLM") == "1":
            raise
        return None
