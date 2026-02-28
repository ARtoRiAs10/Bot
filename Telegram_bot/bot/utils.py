"""
utils.py — URL parsing, language detection, formatting helpers
"""

import re
import logging
import os

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── YouTube URL ──────────────────────────────────────────────────────────────
YOUTUBE_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)"
    r"([a-zA-Z0-9_-]{11})"
)

def extract_video_id(text: str) -> str | None:
    m = YOUTUBE_REGEX.search(text)
    return m.group(1) if m else None

def is_youtube_url(text: str) -> bool:
    return extract_video_id(text) is not None

def build_youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


# ─── Language Detection ───────────────────────────────────────────────────────
LANGUAGE_KEYWORDS: dict[str, list[str]] = {
    "Hindi":   ["hindi", "हिंदी", "हिन्दी"],
    "Tamil":   ["tamil", "தமிழ்"],
    "Kannada": ["kannada", "ಕನ್ನಡ"],
    "Telugu":  ["telugu", "తెలుగు"],
    "Marathi": ["marathi", "मराठी"],
    "Bengali": ["bengali", "bangla", "বাংলা"],
    "English": ["english"],
}

def detect_requested_language(text: str) -> str | None:
    t = text.lower()
    for lang, kws in LANGUAGE_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return lang
    return None


# ─── Timestamp ────────────────────────────────────────────────────────────────
def seconds_to_ts(s: float) -> str:
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ─── Message Splitting ────────────────────────────────────────────────────────
def split_message(text: str, max_len: int = 4000) -> list[str]:
    """Split long text at newlines to fit Telegram's 4096-char limit."""
    if len(text) <= max_len:
        return [text]
    parts, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            if current:
                parts.append(current.strip())
            current = line
        else:
            current += ("\n" if current else "") + line
    if current.strip():
        parts.append(current.strip())
    return parts


def sanitize_error(error_message: str) -> str:
    """
    Scans a technical error string and returns a clean version for the user.
    """
    msg = error_message.lower()
    
    if "429" in msg or "quota" in msg or "limit exceeded" in msg:
        return "⏳ The AI is currently at its limit. Please wait a moment and try again."
    
    if "overloaded" in msg or "503" in msg:
        return "🚀 AI servers are currently busy. Please retry in a minute."
        
    if "timeout" in msg:
        return "⏰ The request took too long. Please try again."

    # Default fallback for unknown errors
    return "❌ An error occurred while processing your request."