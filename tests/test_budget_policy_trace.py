from pathlib import Path

from maikit_core.agent_spec import BudgetConfig, PolicyConfig
from maikit_core.budget import Usage, check_budget
from maikit_core.policy import evaluate_policy
from maikit_core.trace import (
    TraceRecord,
    append_trace,
    next_run_id,
    read_traces,
    redact_input,
)


def test_budget_check_reports_ok_and_exceeded_limits() -> None:
    budget = BudgetConfig(
        max_model_calls=1,
        max_tool_calls=2,
        max_subagents=0,
        max_estimated_tokens=100,
        max_estimated_cost_usd=0.001,
        on_exceed="ask_human",
    )

    ok = check_budget(
        Usage(
            model_calls=1,
            tool_calls=2,
            subagents=0,
            estimated_tokens=100,
            total_cost_usd=0.001,
        ),
        budget,
    )
    exceeded = check_budget(
        Usage(
            model_calls=2,
            tool_calls=3,
            subagents=1,
            estimated_tokens=120,
            total_cost_usd=0.002,
        ),
        budget,
    )

    assert ok.status == "ok"
    assert exceeded.status == "exceeded"
    assert exceeded.exceeded_limits == [
        "max_model_calls",
        "max_tool_calls",
        "max_subagents",
        "max_estimated_tokens",
        "max_estimated_cost_usd",
    ]
    assert exceeded.on_exceed == "ask_human"
    assert exceeded.total_cost_usd == 0.002
    assert exceeded.max_estimated_cost_usd == 0.001
    assert exceeded.budget_used_pct == 200


def test_policy_flags_blocked_and_approval_required_actions() -> None:
    policy = PolicyConfig(
        allowed_actions=["classify_issue"],
        blocked_actions=["rollback"],
        approval_required=["page_engineer"],
    )

    decision = evaluate_policy(["classify_issue", "rollback", "page_engineer"], policy)

    assert decision.allowed_actions == ["classify_issue"]
    assert decision.blocked_actions == ["rollback"]
    assert decision.approval_required_actions == ["page_engineer"]
    assert decision.requires_human_approval is True


def test_trace_records_are_jsonl_and_inputs_are_redacted(tmp_path: Path) -> None:
    trace_path = tmp_path / ".maikit" / "traces.jsonl"
    record = TraceRecord(
        run_id=next_run_id(trace_path),
        agent_name="latency_triage",
        platform="cli",
        prompt_version="triage_v1",
        model="gpt-4.1-mini",
        input_redacted=redact_input(
            "pricing-api token sk-123456 password=secret", "redacted"
        ),
        schema_validation="passed",
        model_calls=1,
        tool_calls=0,
        subagents=0,
        estimated_input_tokens=12,
        estimated_reasoning_tokens=0,
        estimated_output_tokens=34,
        estimated_tokens=46,
        input_cost_usd=0.0000048,
        reasoning_cost_usd=0,
        output_cost_usd=0.0000544,
        total_cost_usd=0.0000592,
        budget_limit_usd=0.05,
        budget_used_pct=0.1184,
        budget_status="ok",
        confidence=0.68,
        requires_human_approval=True,
        latency_ms=25,
        latency_s=0.025,
        token_source="estimated_chars_per_4",
        cost_source="built_in_estimate",
        timestamp="2026-07-02T22:00:00+08:00",
    )

    append_trace(record, trace_path)
    traces = read_traces(trace_path)

    assert traces == [record]
    assert traces[0].run_id == "run_001"
    assert traces[0].estimated_tokens == 46
    assert traces[0].total_cost_usd == 0.0000592
    assert "sk-123456" not in traces[0].input_redacted
    assert "password=secret" not in traces[0].input_redacted
