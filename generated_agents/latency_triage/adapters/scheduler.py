"""Local APScheduler scaffold for latency_triage."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if (PROJECT_ROOT / "maikit_cli").exists() and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apscheduler.schedulers.blocking import BlockingScheduler  # noqa: E402

from maikit_cli.runner import run_agent  # noqa: E402


AGENT_DIR = Path(__file__).resolve().parents[1]


def scheduled_triage() -> None:
    input_text = os.getenv(
        "MAIKIT_CRON_INPUT",
        "pricing-api latency spiked after latest deploy",
    )
    result = run_agent(AGENT_DIR, input_text)
    print(result.model_dump_json(indent=2))


def main() -> None:
    scheduler = BlockingScheduler()
    scheduler.add_job(scheduled_triage, "interval", minutes=15, id="latency_triage_triage")
    scheduler.start()


if __name__ == "__main__":
    main()
