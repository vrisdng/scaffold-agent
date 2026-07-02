"""JSONL trace persistence for local MaiKit runs."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field


DEFAULT_TRACE_STORE = Path(".maikit") / "traces.jsonl"


class TraceRecord(BaseModel):
    run_id: str
    agent_name: str
    platform: str
    prompt_version: str
    model: str
    input_redacted: str
    schema_validation: str
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    subagents: int = Field(ge=0)
    estimated_tokens: int = Field(ge=0)
    budget_status: str
    confidence: float = Field(ge=0, le=1)
    requires_human_approval: bool
    latency_ms: int = Field(ge=0)
    timestamp: str


def next_run_id(trace_path: Path = DEFAULT_TRACE_STORE) -> str:
    """Returns the next monotonic run id for the trace file."""
    existing_count = len(read_traces(trace_path))
    return f"run_{existing_count + 1:03d}"


def append_trace(record: TraceRecord, trace_path: Path = DEFAULT_TRACE_STORE) -> None:
    """Appends a trace record to a JSONL store."""
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as file:
        file.write(record.model_dump_json() + "\n")


def read_traces(trace_path: Path = DEFAULT_TRACE_STORE) -> list[TraceRecord]:
    """Reads all valid trace records from a JSONL store."""
    if not trace_path.exists():
        return []

    traces: list[TraceRecord] = []
    with trace_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                traces.append(TraceRecord.model_validate_json(stripped))
            except ValueError as exc:
                raise ValueError(
                    f"Invalid trace record in {trace_path} at line {line_number}: {exc}"
                ) from exc
    return traces


def redact_input(input_text: str, mode: str = "redacted") -> str:
    """Applies the agent's trace input storage policy."""
    if mode == "raw":
        return input_text
    if mode == "none":
        return ""

    redacted = input_text
    redacted = re.sub(r"sk-[A-Za-z0-9_-]+", "<redacted-api-key>", redacted)
    redacted = re.sub(
        r"(?i)\b(password|secret|token|api[_-]?key)\s*[:=]\s*\S+",
        lambda match: f"{match.group(1)}=<redacted>",
        redacted,
    )
    return redacted[:4000]
