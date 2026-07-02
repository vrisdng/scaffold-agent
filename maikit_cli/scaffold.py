"""Agent scaffold generation."""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


VALID_TARGETS = {"cli", "slack", "telegram", "mcp", "cron"}

ADAPTER_TEMPLATES = {
    "cli": ("adapter_cli.py.j2", "cli.py"),
    "slack": ("adapter_slack_app.py.j2", "slack_app.py"),
    "telegram": ("adapter_telegram_bot.py.j2", "telegram_bot.py"),
    "mcp": ("adapter_mcp_server.py.j2", "mcp_server.py"),
    "cron": ("adapter_scheduler.py.j2", "scheduler.py"),
}


class ScaffoldError(ValueError):
    """Raised when scaffold inputs are invalid."""


def normalize_agent_name(name: str) -> str:
    """Normalizes a user-provided name into the agent.yaml name/path form."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    if not normalized:
        raise ScaffoldError("Agent name must contain at least one letter or number")
    if not re.match(r"^[a-z]", normalized):
        normalized = f"agent_{normalized}"
    return normalized


def scaffold_agent(
    name: str,
    targets: list[str] | tuple[str, ...],
    base_dir: Path | None = None,
) -> Path:
    """Creates a generated agent scaffold and returns its directory."""
    selected_targets = _validate_targets(targets)
    root = base_dir or Path.cwd()
    agent_name = normalize_agent_name(name)
    agent_dir = root / "generated_agents" / agent_name

    for directory in [
        agent_dir,
        agent_dir / "prompts",
        agent_dir / "evals",
        agent_dir / "policies",
        agent_dir / "adapters",
        agent_dir / "observability",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    env = _template_environment()
    platforms = {target: target in selected_targets for target in sorted(VALID_TARGETS)}
    context = {
        "agent_name": agent_name,
        "display_name": name,
        "platforms": platforms,
        "targets": selected_targets,
    }

    _render(env, "agent.yaml.j2", agent_dir / "agent.yaml", context)
    _render(env, "generated_agents_md.j2", agent_dir / "AGENTS.md", context)
    _render(env, "prompt_triage_v1.md.j2", agent_dir / "prompts" / "triage_v1.md", context)
    _render(env, "eval_cases.json.j2", agent_dir / "evals" / "eval_cases.json", context)
    _render(env, "tool_policy.yaml.j2", agent_dir / "policies" / "tool_policy.yaml", context)
    _render(env, "env.example.j2", agent_dir / ".env.example", context)
    _render(
        env,
        "trace_logger.py.j2",
        agent_dir / "observability" / "trace_logger.py",
        context,
    )

    for target in selected_targets:
        template_name, filename = ADAPTER_TEMPLATES[target]
        _render(env, template_name, agent_dir / "adapters" / filename, context)

    return agent_dir


def _validate_targets(targets: list[str] | tuple[str, ...]) -> list[str]:
    if not targets:
        return ["cli"]

    selected: list[str] = []
    for target in targets:
        normalized = target.strip().lower()
        if normalized not in VALID_TARGETS:
            valid = ", ".join(sorted(VALID_TARGETS))
            raise ScaffoldError(f"Invalid target '{target}'. Valid targets: {valid}")
        if normalized not in selected:
            selected.append(normalized)
    return selected


def _template_environment() -> Environment:
    template_dir = Path(__file__).resolve().parent / "templates"
    return Environment(
        loader=FileSystemLoader(template_dir),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )


def _render(
    env: Environment,
    template_name: str,
    output_path: Path,
    context: dict[str, object],
) -> None:
    rendered = env.get_template(template_name).render(**context)
    output_path.write_text(rendered.rstrip() + "\n", encoding="utf-8")
