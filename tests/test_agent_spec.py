from pathlib import Path

import pytest

from maikit_core.agent_spec import AgentSpecError, load_agent_spec


VALID_AGENT_YAML = """
name: latency_triage
description: Triage messy latency incident messages.
model:
  provider: openai
  name: gpt-4.1-mini
  fallback: anthropic/claude-3-5-haiku-latest
prompt:
  version: triage_v1
  file: prompts/triage_v1.md
output_schema:
  name: TriageResult
budget:
  max_model_calls: 8
  max_tool_calls: 10
  max_subagents: 2
  max_estimated_tokens: 80000
  on_exceed: ask_human
policy:
  allowed_actions:
    - classify_issue
    - draft_jira_ticket
    - ask_missing_info
  blocked_actions:
    - rollback
    - deploy
    - write_database
    - send_order
  approval_required:
    - create_jira_ticket
    - page_engineer
platforms:
  cli: true
  slack: true
  telegram: true
  mcp: true
  cron: true
observability:
  prompt_versioning: true
  trace_logging: true
  cost_tracking: true
  latency_tracking: true
  store_inputs: redacted
"""


def _write_spec(tmp_path: Path, content: str = VALID_AGENT_YAML) -> Path:
    path = tmp_path / "agent.yaml"
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def test_load_agent_spec_accepts_required_contract(tmp_path: Path) -> None:
    spec = load_agent_spec(_write_spec(tmp_path))

    assert spec.name == "latency_triage"
    assert spec.model.name == "gpt-4.1-mini"
    assert spec.prompt.version == "triage_v1"
    assert spec.output_schema.name == "TriageResult"
    assert spec.budget.max_model_calls == 8
    assert spec.policy.blocked_actions == [
        "rollback",
        "deploy",
        "write_database",
        "send_order",
    ]
    assert spec.platforms.cli is True
    assert spec.observability.store_inputs == "redacted"


def test_load_agent_spec_reports_actionable_validation_errors(tmp_path: Path) -> None:
    bad_yaml = VALID_AGENT_YAML.replace("platforms:", "bad_platforms:")

    with pytest.raises(AgentSpecError) as exc_info:
        load_agent_spec(_write_spec(tmp_path, bad_yaml))

    message = str(exc_info.value)
    assert "agent.yaml is invalid" in message
    assert "platforms" in message
