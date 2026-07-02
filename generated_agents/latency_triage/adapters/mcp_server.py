"""Minimal MCP server scaffold for latency_triage."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if (PROJECT_ROOT / "maikit_cli").exists() and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from maikit_cli.runner import run_agent  # noqa: E402


AGENT_DIR = Path(__file__).resolve().parents[1]
mcp = FastMCP("latency_triage")


@mcp.tool()
def triage_incident(input_text: str) -> str:
    """Triage an incident message and return structured JSON."""
    result = run_agent(AGENT_DIR, input_text)
    return result.model_dump_json(indent=2)


if __name__ == "__main__":
    mcp.run()
