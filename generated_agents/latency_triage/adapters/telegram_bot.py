"""python-telegram-bot scaffold for latency_triage."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if (PROJECT_ROOT / "maikit_cli").exists() and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from maikit_cli.runner import run_agent


AGENT_DIR = Path(__file__).resolve().parents[1]


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    result = run_agent(AGENT_DIR, update.message.text)
    await update.message.reply_text(result.model_dump_json(indent=2))


def main() -> None:
    application = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()


if __name__ == "__main__":
    main()
