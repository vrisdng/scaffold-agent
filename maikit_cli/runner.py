"""Local CLI run implementation for generated agents."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from maikit_cli.scaffold import normalize_agent_name
from maikit_core.agent_spec import AgentSpec, AgentSpecError, load_agent_spec
from maikit_core.budget import Usage, check_budget
from maikit_core.env import load_default_env_files, load_env_file
from maikit_core.llm import generate_triage_completion
from maikit_core.policy import evaluate_policy
from maikit_core.schemas import TriageResult
from maikit_core.trace import (
    DEFAULT_TRACE_STORE,
    TraceRecord,
    append_trace,
    next_run_id,
    redact_input,
)


class RunnerError(RuntimeError):
    """Raised when a local agent run cannot be completed."""


def run_agent(
    agent_dir: Path,
    input_text: str,
    trace_store: Path | None = None,
    write_trace: bool = True,
) -> TriageResult:
    """Runs a generated agent locally and writes a trace record."""
    started = time.perf_counter()
    load_default_env_files(_project_root_for_agent(agent_dir))
    load_env_file(agent_dir / ".env")
    spec = _load_runner_spec(agent_dir)
    if spec.output_schema.name != "TriageResult":
        raise RunnerError(
            f"Unsupported output_schema.name '{spec.output_schema.name}'. "
            "The MVP supports TriageResult."
        )

    prompt_text = _load_prompt(agent_dir, spec)
    completion = generate_triage_completion(input_text, spec, prompt_text)
    result = TriageResult.model_validate(completion.result.model_dump())
    token_usage = completion.token_usage
    cost = completion.cost
    usage = Usage(
        model_calls=1,
        tool_calls=0,
        subagents=0,
        estimated_input_tokens=token_usage.input_tokens,
        estimated_reasoning_tokens=token_usage.reasoning_tokens,
        estimated_output_tokens=token_usage.output_tokens,
        estimated_tokens=token_usage.total_tokens,
        input_cost_usd=cost.input_cost_usd,
        reasoning_cost_usd=cost.reasoning_cost_usd,
        output_cost_usd=cost.output_cost_usd,
        total_cost_usd=cost.total_cost_usd,
    )
    budget_decision = check_budget(usage, spec.budget)
    blocked_actions = list(
        dict.fromkeys([*result.blocked_actions, *spec.policy.blocked_actions])
    )
    policy_decision = evaluate_policy(blocked_actions, spec.policy)
    result = result.model_copy(
        update={
            "blocked_actions": blocked_actions,
            "requires_human_approval": (
                result.requires_human_approval
                or policy_decision.requires_human_approval
                or budget_decision.status == "exceeded"
            ),
        }
    )

    if write_trace and spec.observability.trace_logging:
        trace_path = trace_store or DEFAULT_TRACE_STORE
        latency_ms = max(1, int((time.perf_counter() - started) * 1000))
        record = TraceRecord(
            run_id=next_run_id(trace_path),
            agent_name=spec.name,
            platform="cli",
            prompt_version=spec.prompt.version,
            model=spec.model.name,
            input_redacted=redact_input(input_text, spec.observability.store_inputs),
            schema_validation="passed",
            model_calls=usage.model_calls,
            tool_calls=usage.tool_calls,
            subagents=usage.subagents,
            estimated_input_tokens=usage.estimated_input_tokens,
            estimated_reasoning_tokens=usage.estimated_reasoning_tokens,
            estimated_output_tokens=usage.estimated_output_tokens,
            estimated_tokens=usage.estimated_tokens,
            input_cost_usd=usage.input_cost_usd,
            reasoning_cost_usd=usage.reasoning_cost_usd,
            output_cost_usd=usage.output_cost_usd,
            total_cost_usd=usage.total_cost_usd,
            budget_limit_usd=budget_decision.max_estimated_cost_usd,
            budget_used_pct=budget_decision.budget_used_pct,
            budget_status=budget_decision.status,
            confidence=result.confidence,
            requires_human_approval=result.requires_human_approval,
            latency_ms=latency_ms,
            latency_s=round(latency_ms / 1000, 3),
            token_source=token_usage.source,
            cost_source=cost.source,
            timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        append_trace(record, trace_path)

    return result


def run_agent_by_name(
    name: str,
    input_text: str,
    base_dir: Path | None = None,
    trace_store: Path | None = None,
) -> TriageResult:
    """Finds a generated agent by name and runs it."""
    root = base_dir or Path.cwd()
    agent_dir = root / "generated_agents" / normalize_agent_name(name)
    if not agent_dir.exists():
        raise RunnerError(
            f"Agent '{name}' was not found at {agent_dir}. Run 'maikit new' first."
        )
    return run_agent(agent_dir, input_text, trace_store=trace_store)


def _load_runner_spec(agent_dir: Path) -> AgentSpec:
    try:
        return load_agent_spec(agent_dir / "agent.yaml")
    except AgentSpecError as exc:
        raise RunnerError(str(exc)) from exc


def _load_prompt(agent_dir: Path, spec: AgentSpec) -> str:
    prompt_path = agent_dir / spec.prompt.file
    if not prompt_path.exists():
        raise RunnerError(
            f"Prompt file declared in agent.yaml does not exist: {prompt_path}"
        )
    return prompt_path.read_text(encoding="utf-8")


def _project_root_for_agent(agent_dir: Path) -> Path:
    if agent_dir.parent.name == "generated_agents":
        return agent_dir.parent.parent
    return Path.cwd()
