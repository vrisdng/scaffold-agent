"""Streamlit trace dashboard."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from maikit_core.trace import DEFAULT_TRACE_STORE, TraceRecord, read_traces


COLUMN_MAP = {
    "run_id": "Run ID",
    "platform": "Platform",
    "prompt_version": "Prompt Version",
    "schema_validation": "Schema",
    "model_calls": "Model Calls",
    "estimated_tokens": "Tokens",
    "budget_status": "Budget",
    "requires_human_approval": "Approval",
    "latency_ms": "Latency",
}


def load_dashboard_traces(trace_path: Path | None = None) -> list[TraceRecord]:
    """Loads traces for the dashboard."""
    path = trace_path or Path(os.getenv("MAIKIT_TRACE_STORE", str(DEFAULT_TRACE_STORE)))
    return read_traces(path)


def main() -> None:
    st.set_page_config(page_title="MaiKit Traces", layout="wide")
    st.title("MaiKit Traces")

    traces = load_dashboard_traces()
    if not traces:
        st.info("No traces found. Run `maikit run` first.")
        return

    agent_options = sorted({trace.agent_name for trace in traces})
    platform_options = sorted({trace.platform for trace in traces})
    prompt_options = sorted({trace.prompt_version for trace in traces})
    budget_options = sorted({trace.budget_status for trace in traces})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        selected_agents = st.multiselect("Agent", agent_options, default=agent_options)
    with col2:
        selected_platforms = st.multiselect("Platform", platform_options, default=platform_options)
    with col3:
        selected_prompts = st.multiselect("Prompt", prompt_options, default=prompt_options)
    with col4:
        selected_budgets = st.multiselect("Budget", budget_options, default=budget_options)

    filtered = [
        trace
        for trace in traces
        if trace.agent_name in selected_agents
        and trace.platform in selected_platforms
        and trace.prompt_version in selected_prompts
        and trace.budget_status in selected_budgets
    ]

    rows = []
    for trace in filtered:
        dumped = trace.model_dump()
        rows.append({label: dumped[key] for key, label in COLUMN_MAP.items()})

    st.dataframe(rows, hide_index=True, use_container_width=True)
    if not filtered:
        st.warning("No traces match the selected filters.")
        return

    selected_run_id = st.selectbox("Run Detail", [trace.run_id for trace in filtered])
    selected_trace = next(trace for trace in filtered if trace.run_id == selected_run_id)
    st.json(selected_trace.model_dump())


if __name__ == "__main__":
    main()
