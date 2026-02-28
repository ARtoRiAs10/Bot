"""
main.py — YouTube Telegram Bot (OpenRouter Edition)
Run: python main.py
"""

import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from bot.handlers import (
    cmd_start, cmd_help, cmd_reset, cmd_language,
    cmd_summary, cmd_deepdive, cmd_actionpoints,
    handle_message, handle_error,
)
from bot.utils import logger


def main():
    # ─── 1. Validate Environment ─────────────────────────────────────────────
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set in .env")
        return

    # Using OpenRouter Key instead of direct Gemini Key
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        logger.error("❌ OPENROUTER_API_KEY not set in .env")
        return

    # Log the startup status
    logger.info("🚀 Starting YouTube Bot via OpenRouter Gateway")
    logger.info("📡 Using Hybrid Provider Rotation (Scraper + AI)")

    # ─── 2. Build Application ────────────────────────────────────────────────
    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start",        cmd_start))
    app.add_handler(CommandHandler("help",         cmd_help))
    app.add_handler(CommandHandler("reset",        cmd_reset))
    app.add_handler(CommandHandler("language",     cmd_language))
    app.add_handler(CommandHandler("summary",      cmd_summary))
    app.add_handler(CommandHandler("deepdive",     cmd_deepdive))
    app.add_handler(CommandHandler("actionpoints", cmd_actionpoints))

    # All text messages (URLs and Questions)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Global Error Handler
    app.add_error_handler(handle_error)

    # ─── 3. Run Bot ──────────────────────────────────────────────────────────
    logger.info("🤖 Bot is live! Press Ctrl+C to stop.")
    
    # drop_pending_updates=True prevents the bot from replying to old messages
    # that were sent while the bot was offline.
    app.run_polling(allowed_updates=["message"], drop_pending_updates=True)


if __name__ == "__main__":
    main()