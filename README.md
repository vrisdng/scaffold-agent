# MaiKit

MaiKit is a local-first scaffold generator for AI agents. The MVP takes one
portable agent specification and generates runnable local scaffolds for a CLI,
Slack, Telegram, MCP, and cron-style scheduled runs. Each local run validates
structured output, applies policy and budget checks, and records trace metadata
for the dashboard.

The demo agent is a latency incident triage agent.

<!-- Test change: verifying PR workflow. -->

## What Works In This MVP

The main workflow is:

```bash
maikit new latency-triage --targets cli slack telegram mcp cron
maikit run latency-triage "pricing-api latency spiked after latest deploy"
maikit eval latency-triage
maikit dashboard
```

By default, `maikit run` uses a deterministic local fallback. That means the MVP
works without OpenAI, Slack, Telegram, MCP, or cron credentials. Live LLM calls
are optional.

## Setup

Use a virtual environment from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

After activation, `python3` and `maikit` should both resolve inside `.venv`:

```bash
which python3
which maikit
```

If you prefer using the requirements file:

```bash
python -m pip install -r requirements-dev.txt
```

## Optional Extras

The core MVP does not require live external services. Install extras only when
you want those specific paths:

```bash
python -m pip install -e ".[llm]"
python -m pip install -e ".[adapters]"
```

`.[llm]` installs LiteLLM for live model calls. `.[adapters]` installs optional
libraries used by generated Slack, Telegram, MCP, and APScheduler scaffolds.

## Command Reference

### `maikit new`

Generate an agent scaffold.

```bash
maikit new latency-triage --targets cli slack telegram mcp cron
```

What it does:

- Normalizes the name `latency-triage` to `latency_triage`.
- Creates `generated_agents/latency_triage/`.
- Writes `agent.yaml`, prompts, eval cases, policies, adapter files, and trace
  logging helpers.
- Marks the selected target platforms in `agent.yaml`.

Generated files:

```text
generated_agents/latency_triage/
  agent.yaml
  AGENTS.md
  .env.example
  prompts/triage_v1.md
  evals/eval_cases.json
  policies/tool_policy.yaml
  adapters/cli.py
  adapters/slack_app.py
  adapters/telegram_bot.py
  adapters/mcp_server.py
  adapters/scheduler.py
  observability/trace_logger.py
```

Valid targets are:

```text
cli slack telegram mcp cron
```

You can also generate one or a few targets:

```bash
maikit new latency-triage --targets cli mcp
maikit new latency-triage --target cli --target cron
```

### `maikit run`

Run a generated agent locally.

```bash
maikit run latency-triage "pricing-api latency spiked after latest deploy"
```

What it does:

- Loads `generated_agents/latency_triage/agent.yaml`.
- Validates the spec with Pydantic.
- Loads the configured prompt file.
- Produces a `TriageResult` structured output.
- Validates the output schema.
- Applies configured blocked actions and approval behavior.
- Checks the configured budget.
- Writes a JSONL trace record to `.maikit/traces.jsonl`.
- Prints validated JSON to stdout.

Example output:

```json
{
  "issue_type": "latency_incident",
  "severity": "medium",
  "affected_system": "pricing-api",
  "evidence": [
    "input names pricing-api",
    "input mentions latency symptoms",
    "input describes a spike",
    "input mentions a recent deploy"
  ],
  "missing_info": [
    "time window",
    "p95/p99",
    "deploy id"
  ],
  "safe_next_action": "check deploy timeline and latency dashboard",
  "blocked_actions": [
    "rollback",
    "deploy",
    "write_database",
    "send_order"
  ],
  "requires_human_approval": true,
  "confidence": 0.68
}
```

Useful test prompts:

```bash
maikit run latency-triage "checkout-service p99 latency increased after the release"
maikit run latency-triage "auth-api is down and users cannot log in after deploy"
maikit run latency-triage "please rollback pricing-api and deploy a fix immediately"
maikit run latency-triage "pricing-api latency spiked token=abc123 password=secret sk-test123"
```

The last prompt is useful for checking trace redaction in `.maikit/traces.jsonl`.

### `maikit eval`

Run the generated JSON eval suite.

```bash
maikit eval latency-triage
```

What it does:

- Loads `generated_agents/latency_triage/evals/eval_cases.json`.
- Runs each case through the same local runner used by `maikit run`.
- Compares selected output fields against expected values.
- Prints a concise pass/fail summary.
- Exits non-zero if any eval fails.

Example output:

```text
1/1 passed
PASS pricing_latency_after_deploy
```

Add more eval cases to:

```text
generated_agents/latency_triage/evals/eval_cases.json
```

Supported expectation helpers include exact fields plus suffixes such as:

- `_contains` for list membership checks.
- `_min` for minimum numeric values.
- `_max` for maximum numeric values.

### `maikit dashboard`

Start the local Streamlit trace dashboard.

```bash
maikit dashboard
```

What it does:

- Starts Streamlit on `http://localhost:8501`.
- Loads traces from `.maikit/traces.jsonl`.
- Shows run metadata in a table.
- Provides filters for agent, platform, prompt version, and budget status.
- Shows a selected run detail as JSON.

Use a different port:

```bash
maikit dashboard --port 8502
```

Print the Streamlit command without starting the server:

```bash
maikit dashboard --dry-run
```

## Direct Generated CLI Adapter

The generated agent also has its own runnable CLI adapter:

```bash
python generated_agents/latency_triage/adapters/cli.py \
  "pricing-api latency spiked after latest deploy"
```

This is useful for verifying that generated code can run directly from the
source checkout.

## Deterministic Mode Versus Live LLM Mode

Default mode is deterministic:

- No API keys required.
- No network calls required.
- Stable outputs for tests and demos.
- Good for verifying scaffolding, schema validation, policy, budget, traces,
  evals, and dashboard behavior.

To try live LLM mode:

```bash
python -m pip install -e ".[llm]"
cp generated_agents/latency_triage/.env.example generated_agents/latency_triage/.env
```

Then edit `generated_agents/latency_triage/.env`:

```dotenv
MAIKIT_USE_LLM=1
OPENAI_API_KEY=your-key
```

Run the agent:

```bash
maikit run latency-triage "pricing-api latency spiked after latest deploy"
```

If LiteLLM is unavailable or a live call fails, the runner falls back to the
deterministic result unless `MAIKIT_STRICT_LLM=1` is set.

You can also put `MAIKIT_USE_LLM=1` and provider API keys in the repository root
`.env`. Values already exported in your shell take precedence over `.env` values.

## Trace Store

Runs write trace records to:

```text
.maikit/traces.jsonl
```

Each trace includes run id, agent name, platform, prompt version, model, redacted
input, schema status, model call count, input/reasoning/output token counts,
input/reasoning/output/total estimated cost in USD, numeric budget limit and
used percentage, approval requirement, latency in milliseconds and seconds,
confidence, and timestamp.

Inputs are redacted by default according to `agent.yaml`:

```yaml
observability:
  store_inputs: redacted
```

Budget limits live in `agent.yaml`:

```yaml
budget:
  max_estimated_tokens: 80000
  max_estimated_cost_usd: 0.05
```

The dashboard shows:

```text
Tokens: total (input / reasoning / output)
Cost ($): total (input / reasoning / output)
Budget ($): total spend / limit (used %, status)
Latency (ms): measured wall-clock latency in milliseconds
```

For deterministic fallback runs, reasoning tokens are `0`. For live provider
runs, MaiKit uses provider token usage when LiteLLM exposes it, including
reasoning tokens when present. Reasoning tokens are costed at the output-token
rate unless overridden.

You can override the built-in per-million token price estimates through `.env`:

```dotenv
MAIKIT_INPUT_COST_PER_1M=0.40
MAIKIT_OUTPUT_COST_PER_1M=1.60
```

## Development Commands

Run tests:

```bash
python -m pytest -q
```

Run lint:

```bash
ruff check .
```

Run the full local smoke path:

```bash
maikit new latency-triage --targets cli slack telegram mcp cron
maikit run latency-triage "pricing-api latency spiked after latest deploy"
maikit eval latency-triage
MAIKIT_DASHBOARD_DRY_RUN=1 maikit dashboard
```

## Troubleshooting

If `pytest`, `typer`, or `maikit` cannot be found, the virtual environment is
probably not active or dependencies were not installed:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

If `python3 -m maikit_cli.main ...` fails with `No module named typer`, check
which interpreter is running:

```bash
which python3
python3 -m pip show typer
```

It should point at `.venv/bin/python3`. If it points at Homebrew or system
Python, activate the virtual environment again.

If the dashboard starts but shows no data, run an agent once first:

```bash
maikit run latency-triage "pricing-api latency spiked after latest deploy"
maikit dashboard
```
