"""
summarizer.py — Optimized for OpenRouter (Gemini 2.0 Flash).
Handles structured summaries, deep dives, action points, and ELI5 explanations.
"""

import os
import time
import re
from openai import OpenAI
from bot.transcript import VideoData, transcript_to_text_block
from bot.utils import logger

# ─── Config ───────────────────────────────────────────────────────────────────
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Gemini 2.0 Flash via OpenRouter
# MODEL_NAME = "google/gemini-2.0-flash-001"
MODEL_NAME = "stepfun/step-3.5-flash:free"
MAX_TRANSCRIPT_CHARS = 40_000

# ─── Public API ───────────────────────────────────────────────────────────────

def generate_summary(video: VideoData, language: str = "English") -> str:
    """Generate the standard PDF-compliant summary."""
    transcript = _prepare_transcript(video)
    prompt = f"""
You are an expert video analyst. Analyze this transcript and generate a structured summary.
Respond ENTIRELY in {language}.

VIDEO: {video.title}
TRANSCRIPT:
{transcript}

FORMAT:
🎥 *{video.title}*
⏱ Duration: {video.duration or "N/A"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 *5 Key Points*
1. [Point 1]
2. [Point 2]
3. [Point 3]
4. [Point 4]
5. [Point 5]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏱ *Important Timestamps*
• [MM:SS] — [Description]
• [MM:SS] — [Description]
• [MM:SS] — [Description]
• [MM:SS] — [Description]
• [MM:SS] — [Description]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧠 *Core Takeaway*
[One powerful sentence]

💬 *Who Should Watch This*
[1–2 sentences]
"""
    return _call_ai_provider(prompt, max_tokens=1500)

def generate_deep_dive(video: VideoData, language: str = "English") -> str:
    """Thematic analysis mode."""
    transcript = _prepare_transcript(video)
    prompt = f"Perform a deep analytical dive on this video transcript in {language}. Video: {video.title}\n\nTranscript:\n{transcript}"
    return _call_ai_provider(prompt, max_tokens=2000)

def generate_action_points(video: VideoData, language: str = "English") -> str:
    """Extract concrete action items."""
    transcript = _prepare_transcript(video)
    prompt = f"Extract concrete action points from this video in {language}. Video: {video.title}\n\nTranscript:\n{transcript}"
    return _call_ai_provider(prompt, max_tokens=1500)

def generate_simplified_explanation(video: VideoData, language: str = "English", topic: str = "") -> str:
    """ELI5 mode — Explains the video or a specific topic in simple terms."""
    transcript = _prepare_transcript(video)
    about = f' specifically about "{topic}"' if topic else ""
    prompt = f"""
Explain this video content{about} in very simple terms. Respond ENTIRELY in {language}.
VIDEO: {video.title}
TRANSCRIPT:
{transcript}

FORMAT:
📝 *Simple Explanation*
[Explain like I'm 10 years old]

🔑 *Key Terms*
• [Term] -> [Simple meaning]

💡 *Metaphor*
[One metaphor to make it click]
"""
    return _call_ai_provider(prompt, max_tokens=1000)

# ─── OpenRouter Caller ────────────────────────────────────────────────────────

def _call_ai_provider(prompt: str, max_tokens: int = 1500, temperature: float = 0.3) -> str:
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["429", "rate", "limit", "overloaded"]):
                wait_time = 70 * (attempt + 1)
                time.sleep(wait_time)
                continue
            raise ValueError(f"❌ AI Analysis failed: {str(e)}")
    raise ValueError("❌ AI providers busy. Try again in 2 minutes.")

def _prepare_transcript(video: VideoData) -> str:
    text = transcript_to_text_block(video)
    if len(text) > MAX_TRANSCRIPT_CHARS:
        half = MAX_TRANSCRIPT_CHARS // 2
        text = text[:half] + "\n[...]\n" + text[-half:]
    return text