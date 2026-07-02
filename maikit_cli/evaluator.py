"""JSON eval runner for generated agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from maikit_cli.runner import run_agent


class EvalError(RuntimeError):
    """Raised when eval cases cannot be loaded or executed."""


class EvalCase(BaseModel):
    name: str
    input: str
    expected: dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    name: str
    passed: bool
    failures: list[str] = Field(default_factory=list)


class EvalSummary(BaseModel):
    total: int
    passed: int
    failed: int
    results: list[EvalResult]


def run_evals(
    agent_dir: Path,
    trace_store: Path | None = None,
    write_traces: bool = False,
) -> EvalSummary:
    """Runs generated JSON eval cases against the local deterministic runner."""
    cases = _load_eval_cases(agent_dir / "evals" / "eval_cases.json")
    results: list[EvalResult] = []

    for case in cases:
        result = run_agent(
            agent_dir,
            case.input,
            trace_store=trace_store,
            write_trace=write_traces,
        )
        failures = _compare_expected(result.model_dump(), case.expected)
        results.append(
            EvalResult(name=case.name, passed=not failures, failures=failures)
        )

    passed = sum(1 for result in results if result.passed)
    return EvalSummary(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )


def _load_eval_cases(path: Path) -> list[EvalCase]:
    if not path.exists():
        raise EvalError(f"Eval suite does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvalError(f"Eval suite is not valid JSON: {path}: {exc}") from exc

    if not isinstance(payload, list):
        raise EvalError(f"Eval suite must be a JSON list: {path}")
    return [EvalCase.model_validate(item) for item in payload]


def _compare_expected(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for key, expected_value in expected.items():
        if key.endswith("_contains"):
            actual_key = key.removesuffix("_contains")
            actual_value = actual.get(actual_key, [])
            missing = [item for item in expected_value if item not in actual_value]
            if missing:
                failures.append(f"{actual_key} missing expected values: {missing}")
        elif key.endswith("_min"):
            actual_key = key.removesuffix("_min")
            if actual.get(actual_key, 0) < expected_value:
                failures.append(f"{actual_key} is below minimum {expected_value}")
        elif key.endswith("_max"):
            actual_key = key.removesuffix("_max")
            if actual.get(actual_key, 0) > expected_value:
                failures.append(f"{actual_key} is above maximum {expected_value}")
        elif actual.get(key) != expected_value:
            failures.append(
                f"{key} expected {expected_value!r}, got {actual.get(key)!r}"
            )
    return failures
