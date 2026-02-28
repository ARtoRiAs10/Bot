"""
main.py — YouTube Telegram Bot (OpenRouter Edition)
Run: python main.py
"""

import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

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

# ─── ADDED: Render Keep-Alive Logic (Does not affect bot logic) ──────────────
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive"

def run_flask():
    # Use the port Render provides or default to 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """Starts a dummy server so Render doesn't kill the process."""
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
# ─────────────────────────────────────────────────────────────────────────────

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

    # START KEEP ALIVE HERE
    keep_alive()

    # Log the startup status
    logger.info("🚀 Starting YouTube Bot via OpenRouter Gateway")
    logger.info("📡 Using Hybrid Provider Rotation (Scraper + AI)")

    # ─── 2. Build Application ────────────────────────────────────────────────
    app_tg = Application.builder().token(token).build()

    # Commands
    app_tg.add_handler(CommandHandler("start",        cmd_start))
    app_tg.add_handler(CommandHandler("help",         cmd_help))
    app_tg.add_handler(CommandHandler("reset",        cmd_reset))
    app_tg.add_handler(CommandHandler("language",     cmd_language))
    app_tg.add_handler(CommandHandler("summary",      cmd_summary))
    app_tg.add_handler(CommandHandler("deepdive",     cmd_deepdive))
    app_tg.add_handler(CommandHandler("actionpoints", cmd_actionpoints))

    # All text messages (URLs and Questions)
    app_tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Global Error Handler
    app_tg.add_error_handler(handle_error)

    # ─── 3. Run Bot ──────────────────────────────────────────────────────────
    logger.info("🤖 Bot is live! Press Ctrl+C to stop.")
    
    # drop_pending_updates=True prevents the bot from replying to old messages
    # that were sent while the bot was offline.
    app_tg.run_polling(allowed_updates=["message"], drop_pending_updates=True)


if __name__ == "__main__":
    main()
