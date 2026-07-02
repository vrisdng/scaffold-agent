"""Trace logging hook for latency_triage."""

from __future__ import annotations

from pathlib import Path

from maikit_core.trace import TraceRecord, append_trace


def log_trace(record: TraceRecord, trace_path: Path = Path(".maikit/traces.jsonl")) -> None:
    """Append one trace record to the local JSONL trace store."""
    append_trace(record, trace_path)
