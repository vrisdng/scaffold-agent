import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from maikit_cli.evaluator import run_evals
from maikit_cli.main import app
from maikit_cli.runner import run_agent
from maikit_cli.scaffold import ScaffoldError, scaffold_agent
from maikit_core.agent_spec import load_agent_spec
from maikit_core.trace import read_traces


ALL_TARGETS = ["cli", "slack", "telegram", "mcp", "cron"]


def test_scaffold_generation_creates_selected_agent_files(tmp_path: Path) -> None:
    agent_dir = scaffold_agent("latency-triage", ALL_TARGETS, base_dir=tmp_path)

    assert agent_dir == tmp_path / "generated_agents" / "latency_triage"
    spec = load_agent_spec(agent_dir / "agent.yaml")
    assert spec.name == "latency_triage"
    assert spec.platforms.cli is True
    assert spec.platforms.slack is True
    assert (agent_dir / "prompts" / "triage_v1.md").exists()
    assert (agent_dir / "evals" / "eval_cases.json").exists()
    assert (agent_dir / "policies" / "tool_policy.yaml").exists()
    assert (agent_dir / "observability" / "trace_logger.py").exists()
    for adapter in [
        "cli.py",
        "slack_app.py",
        "telegram_bot.py",
        "mcp_server.py",
        "scheduler.py",
    ]:
        assert (agent_dir / "adapters" / adapter).exists()


def test_scaffold_rejects_invalid_targets(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldError, match="Invalid target"):
        scaffold_agent("latency-triage", ["cli", "email"], base_dir=tmp_path)


def test_run_agent_returns_valid_triage_and_writes_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MAIKIT_USE_LLM", raising=False)
    agent_dir = scaffold_agent("latency-triage", ALL_TARGETS, base_dir=tmp_path)
    trace_path = tmp_path / ".maikit" / "traces.jsonl"

    result = run_agent(
        agent_dir,
        "pricing-api latency spiked after latest deploy",
        trace_store=trace_path,
    )

    assert result.issue_type == "latency_incident"
    assert result.severity == "medium"
    assert result.affected_system == "pricing-api"
    assert "time window" in result.missing_info
    assert result.requires_human_approval is True
    traces = read_traces(trace_path)
    assert len(traces) == 1
    assert traces[0].agent_name == "latency_triage"
    assert traces[0].schema_validation == "passed"
    assert traces[0].budget_status == "ok"
    assert traces[0].estimated_tokens != 1450
    assert traces[0].estimated_input_tokens > 0
    assert traces[0].estimated_output_tokens > 0
    assert traces[0].estimated_reasoning_tokens == 0
    assert traces[0].total_cost_usd > 0
    assert traces[0].budget_limit_usd == 0.05
    assert traces[0].budget_used_pct > 0
    assert traces[0].latency_ms >= 1


def test_eval_runner_passes_generated_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MAIKIT_USE_LLM", raising=False)
    agent_dir = scaffold_agent("latency-triage", ALL_TARGETS, base_dir=tmp_path)

    summary = run_evals(agent_dir, trace_store=tmp_path / ".maikit" / "traces.jsonl")

    assert summary.total == 1
    assert summary.passed == 1
    assert summary.failed == 0


def test_cli_new_run_eval_smoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MAIKIT_USE_LLM", raising=False)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    new_result = runner.invoke(
        app,
        [
            "new",
            "latency-triage",
            "--targets",
            "cli",
            "slack",
            "telegram",
            "mcp",
            "cron",
        ],
    )
    assert new_result.exit_code == 0, new_result.output
    assert "generated_agents/latency_triage" in new_result.output

    run_result = runner.invoke(
        app,
        ["run", "latency-triage", "pricing-api latency spiked after latest deploy"],
    )
    assert run_result.exit_code == 0, run_result.output
    payload = json.loads(run_result.output)
    assert payload["issue_type"] == "latency_incident"
    assert payload["affected_system"] == "pricing-api"
    assert payload["confidence"] == 0.68

    eval_result = runner.invoke(app, ["eval", "latency-triage"])
    assert eval_result.exit_code == 0, eval_result.output
    assert "1/1 passed" in eval_result.output


def test_dashboard_command_can_print_without_starting_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAIKIT_DASHBOARD_DRY_RUN", "1")
    runner = CliRunner()

    result = runner.invoke(app, ["dashboard"])

    assert result.exit_code == 0, result.output
    assert "streamlit run" in result.output
