# MaiKit

MaiKit is a local-first scaffold generator for AI agent interfaces.

## Setup

Use a virtual environment from a fresh checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Optional extras:

```bash
python -m pip install -e ".[llm]"       # live LiteLLM calls
python -m pip install -e ".[adapters]"  # Slack, Telegram, MCP, cron adapter deps
```

## MVP Commands

```bash
maikit new latency-triage --targets cli slack telegram mcp cron
maikit run latency-triage "pricing-api latency spiked after latest deploy"
maikit eval latency-triage
maikit dashboard
```

The default run path is deterministic and does not require live API keys.
