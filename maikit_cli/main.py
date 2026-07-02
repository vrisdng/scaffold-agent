"""Typer entrypoint for the maikit command."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import typer

from maikit_cli.evaluator import EvalError, run_evals
from maikit_cli.runner import RunnerError, run_agent_by_name
from maikit_cli.scaffold import ScaffoldError, scaffold_agent
from maikit_core.env import load_default_env_files
from maikit_core.trace import DEFAULT_TRACE_STORE


app = typer.Typer(no_args_is_help=True)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def new(
    ctx: typer.Context,
    name: str,
    target: list[str] | None = typer.Option(
        None,
        "--target",
        "-t",
        help="Target adapter to generate. May be repeated.",
    ),
) -> None:
    """Create a generated local agent scaffold."""
    load_default_env_files(Path.cwd())
    try:
        targets = _parse_targets(list(ctx.args), list(target or []))
        agent_dir = scaffold_agent(name, targets, base_dir=Path.cwd())
    except ScaffoldError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    typer.echo(str(agent_dir.relative_to(Path.cwd())))


@app.command("run")
def run_command(name: str, input_text: str) -> None:
    """Run a generated agent locally."""
    load_default_env_files(Path.cwd())
    try:
        result = run_agent_by_name(
            name,
            input_text,
            base_dir=Path.cwd(),
            trace_store=DEFAULT_TRACE_STORE,
        )
    except RunnerError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    typer.echo(result.model_dump_json(indent=2))


@app.command("eval")
def eval_command(name: str) -> None:
    """Run generated JSON eval cases."""
    load_default_env_files(Path.cwd())
    agent_dir = Path.cwd() / "generated_agents" / _normalize_for_cli(name)
    if not agent_dir.exists():
        typer.echo(
            f"Agent '{name}' was not found at {agent_dir}. Run 'maikit new' first.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        summary = run_evals(agent_dir, trace_store=DEFAULT_TRACE_STORE)
    except (EvalError, RunnerError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"{summary.passed}/{summary.total} passed")
    for result in summary.results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"{status} {result.name}")
        for failure in result.failures:
            typer.echo(f"  - {failure}")

    if summary.failed:
        raise typer.Exit(1)


@app.command()
def dashboard(
    port: int = typer.Option(8501, help="Port for the Streamlit dashboard."),
    dry_run: bool = typer.Option(
        False, help="Print the command without starting Streamlit."
    ),
) -> None:
    """Start the local Streamlit trace dashboard."""
    load_default_env_files(Path.cwd())
    script_path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    command = [
        "streamlit",
        "run",
        str(script_path),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]
    display_command = " ".join(shlex.quote(part) for part in command)
    typer.echo(f"Dashboard URL: http://localhost:{port}")
    typer.echo(display_command)

    if dry_run or os.getenv("MAIKIT_DASHBOARD_DRY_RUN") == "1":
        return

    try:
        exit_code = subprocess.call(command)
    except FileNotFoundError as exc:
        typer.echo(
            "streamlit is not installed. Install project dependencies first.", err=True
        )
        raise typer.Exit(1) from exc
    raise typer.Exit(exit_code)


def main() -> None:
    app()


def _parse_targets(extra_args: list[str], repeated_targets: list[str]) -> list[str]:
    targets = list(repeated_targets)
    while extra_args:
        token = extra_args.pop(0)
        if token != "--targets":
            raise ScaffoldError(f"Unexpected argument '{token}'")
        while extra_args and not extra_args[0].startswith("--"):
            targets.append(extra_args.pop(0))
    return targets or ["cli"]


def _normalize_for_cli(name: str) -> str:
    from maikit_cli.scaffold import normalize_agent_name

    return normalize_agent_name(name)


if __name__ == "__main__":
    main()
