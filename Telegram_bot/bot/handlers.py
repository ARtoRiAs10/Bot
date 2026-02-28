"""
handlers.py — All Telegram command and message handlers.
Refactored for OpenRouter and safe Error Handling (masking technical crashes).
"""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction

from bot.transcript import fetch_video_data
from bot.summarizer import (
    generate_summary,
    generate_deep_dive,
    generate_action_points,
    generate_simplified_explanation,
)
from bot.qa_engine import answer_question
from bot.session import store
from bot.cache import get_video, set_video, get_summary, set_summary
from bot.utils import (
    extract_video_id, is_youtube_url,
    detect_requested_language, split_message, logger,
)


# ─── /start ───────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *YouTube AI Assistant* — powered by Gemini 2.0\n\n"
        "Send me any YouTube link and I'll:\n"
        "📌 Give you 5 key points\n"
        "⏱ Highlight important timestamps\n"
        "🧠 Extract the core takeaway\n"
        "💬 Answer your questions about the video\n"
        "🌐 Respond in Hindi, Tamil, Telugu, Kannada & more\n\n"
        "━━━━━━━━━━━━━━━\n"
        "*Commands:*\n"
        "/summary — Regenerate summary\n"
        "/deepdive — In-depth analysis\n"
        "/actionpoints — Extract action items\n"
        "/language Hindi — Switch language\n"
        "/reset — Start fresh\n"
        "/help — Show this message",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


# ─── /reset ───────────────────────────────────────────────────────────────────
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store.reset(update.effective_chat.id)
    await update.message.reply_text(
        "🔄 Session cleared! Send me a new YouTube link."
    )


# ─── /language ────────────────────────────────────────────────────────────────
async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = store.get(update.effective_chat.id)
    if context.args:
        lang = " ".join(context.args).title()
        session.language = lang
        await update.message.reply_text(
            f"🌐 Language set to *{lang}*!",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            f"🌐 Current language: *{session.language}*\n\n"
            "Change with: `/language Hindi`\n"
            "Supported: English, Hindi, Tamil, Telugu, Kannada, Marathi, Bengali",
            parse_mode=ParseMode.MARKDOWN,
        )


# ─── /summary ────────────────────────────────────────────────────────────────
async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = store.get(update.effective_chat.id)
    if not session.has_video():
        await update.message.reply_text("⚠️ Please send a YouTube link first!")
        return
    await _send_summary(update, session)


# ─── /deepdive ────────────────────────────────────────────────────────────────
async def cmd_deepdive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = store.get(chat_id)
    if not session.has_video():
        await update.message.reply_text("⚠️ Please send a YouTube link first!")
        return

    msg = await update.message.reply_text("🔍 Performing deep analysis… please wait.")
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    try:
        result = generate_deep_dive(session.video, session.language)
        await msg.delete()
        await _send_long(update, result)
    except ValueError as e:
        await msg.edit_text(f"⚠️ {str(e)}")
    except Exception as e:
        logger.error(f"DeepDive System Error: {e}", exc_info=True)
        await msg.edit_text("❌ An internal error occurred during analysis. Please try again later.")


# ─── /actionpoints ───────────────────────────────────────────────────────────
async def cmd_actionpoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = store.get(chat_id)
    if not session.has_video():
        await update.message.reply_text("⚠️ Please send a YouTube link first!")
        return

    msg = await update.message.reply_text("⚙️ Extracting action points…")
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    try:
        result = generate_action_points(session.video, session.language)
        await msg.delete()
        await _send_long(update, result)
    except ValueError as e:
        await msg.edit_text(f"⚠️ {str(e)}")
    except Exception as e:
        logger.error(f"ActionPoints System Error: {e}", exc_info=True)
        await msg.edit_text("❌ Failed to extract actions due to a system error.")


# ─── Main Message Handler ─────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text    = update.message.text.strip()
    session = store.get(chat_id)

    # ── Language switch request? ──────────────────────────────────────────────
    lang = detect_requested_language(text)
    if lang:
        session.language = lang
        reply = f"🌐 Switched to *{lang}*!\n"
        if session.has_video():
            reply += "Regenerating summary…"
            await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
            await _send_summary(update, session)
        else:
            await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
        return

    # ── YouTube URL? ──────────────────────────────────────────────────────────
    if is_youtube_url(text):
        await _handle_youtube_url(update, context, text, session)
        return

    # ── "Explain in simple terms"? ────────────────────────────────────────────
    if session.has_video() and any(
        kw in text.lower() for kw in ["explain simply", "simplify", "simple terms", "eli5"]
    ):
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        msg = await update.message.reply_text("📝 Simplifying…")
        try:
            result = generate_simplified_explanation(session.video, session.language, text)
            await msg.delete()
            await _send_long(update, result)
        except ValueError as e:
            await msg.edit_text(f"⚠️ {str(e)}")
        except Exception as e:
            logger.error(f"Simplify System Error: {e}", exc_info=True)
            await msg.edit_text("❌ Could not simplify this content right now.")
        return

    # ── No video loaded yet ────────────────────────────────────────────────────
    if not session.has_video():
        await update.message.reply_text(
            "🎬 Please send me a YouTube link first!\n"
            "Example: `https://youtube.com/watch?v=dQw4w9WgXcQ`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── Q&A ───────────────────────────────────────────────────────────────────
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    thinking = await update.message.reply_text("🤔 Searching the transcript…")

    try:
        answer = answer_question(
            qa_index=session.qa_index,
            question=text,
            language=session.language,
            history=session.history,
        )
        session.add_history("user", text)

        if answer == "NOT_COVERED":
            topic_hint = session.video.description or session.video.title
            reply = (
                f"ℹ️ *This topic is not covered in the video.*\n\n"
                f"The video focuses on: _{topic_hint}_\n\n"
                f"Would you like to ask something else?"
            )
            await thinking.delete()
            await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
            return

        session.add_history("assistant", answer)
        await thinking.delete()
        await update.message.reply_text(answer)

    except ValueError as e:
        await thinking.edit_text(f"⚠️ {str(e)}")
    except Exception as e:
        logger.error(f"QA System Error (Missing modules?): {e}", exc_info=True)
        await thinking.edit_text("❌ My Q&A engine encountered a system error. Please try a different question.")


# ─── Private: Load YouTube Video ─────────────────────────────────────────────
def _clean_error_message(error_str: str) -> str:
    """
    Filters out technical API jargon and quota violation details.
    Returns a clean, user-friendly message.
    """
    error_str = error_str.lower()
    
    # Check for Quota / Rate Limits
    if any(k in error_str for k in ["429", "quota", "limit exceeded", "rate"]):
        return "⏳ The AI is currently at its limit. Please wait about 60 seconds and try again."
    
    # Check for Server Overload
    if any(k in error_str for k in ["overloaded", "503", "busy"]):
        return "🚀 The AI servers are busy right now. Please retry in a moment."

    # Extract the main message before the technical 'violations' block if present
    # Usually, the important part is at the beginning before the JSON-like structure
    main_msg = error_str.split("violations {")[0].split("links {")[0].strip()
    
    # Remove common technical prefixes from Gemini's response
    clean_msg = main_msg.replace("failed to answer question:", "").replace("❌", "").strip()
    
    return clean_msg.capitalize() if clean_msg else "An error occurred while processing the video."


async def _handle_youtube_url(update, context, url: str, session):
    chat_id  = update.effective_chat.id
    video_id = extract_video_id(url)

    if not video_id:
        await update.message.reply_text(
            "❌ That doesn't look like a valid YouTube URL.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    loading = await update.message.reply_text(
        "⏳ Bot is watching the video and extracting the transcript…\n"
        "_This usually takes 20–60 seconds._",
        parse_mode=ParseMode.MARKDOWN,
    )
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        # Check transcript cache
        video = get_video(video_id)
        if video:
            await loading.edit_text("⚡ Cache hit — loaded instantly!")
        else:
            video = fetch_video_data(video_id)
            set_video(video_id, video)
            await loading.edit_text(
                f"✅ Transcript extracted!\n"
                f"📹 *{video.title}*\n\n"
                f"Generating summary…",
                parse_mode=ParseMode.MARKDOWN,
            )

        session.load_video(video)
        await loading.delete()
        await _send_summary(update, session)

    except ValueError as e:
        # Sanitizing the technical Gemini Quota/Violation message
        user_friendly_error = _clean_error_message(str(e))
        await loading.edit_text(f"⚠️ {user_friendly_error}")
        
    except Exception as e:
        # Unexpected System Errors (Logged fully for dev, hidden from user)
        logger.error(f"Critical URL Handler Error: {e}", exc_info=True)
        await loading.edit_text(
            "❌ *An internal system error occurred.*\n\n"
            "The technical team has been notified. Please try again later.",
            parse_mode=ParseMode.MARKDOWN
        )

# ─── Private: Send Summary ────────────────────────────────────────────────────
async def _send_summary(update, session):
    video = session.video
    lang  = session.language

    cached = get_summary(video.video_id, lang)
    if cached:
        await _send_long(update, cached)
    else:
        try:
            summary = generate_summary(video, lang)
            set_summary(video.video_id, lang, summary)
            await _send_long(update, summary)
        except ValueError as e:
            await update.message.reply_text(f"⚠️ {str(e)}")
            return
        except Exception as e:
            logger.error(f"Summary Generation Error: {e}", exc_info=True)
            await update.message.reply_text("❌ System error generating summary.")
            return

    await update.message.reply_text(
        "💬 *Ask me anything about this video!*\n"
        "Commands: /deepdive • /actionpoints • /summary • /reset",
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── Private: Send Long Message ───────────────────────────────────────────────
async def _send_long(update, text: str):
    parts = split_message(text, max_len=4000)
    for part in parts:
        try:
            await update.message.reply_text(part, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(part)
        await asyncio.sleep(0.3)


# ─── Error Handler ────────────────────────────────────────────────────────────
async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Global Handler Error: {context.error}", exc_info=True)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An unexpected system error occurred.\n"
            "Try /reset to clear your session."
        )