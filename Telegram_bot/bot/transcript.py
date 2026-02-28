"""
transcript.py — Optimized for OpenRouter using Gemini 2.0 Flash (2026).
"""

import os
import re
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from openai import OpenAI

# Import internal helpers
try:
    from bot.utils import logger, build_youtube_url
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    def build_youtube_url(vid): return f"https://www.youtube.com/watch?v={vid}"

# ─── Config ───────────────────────────────────────────────────────────────────
# OpenRouter uses the OpenAI-compatible client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Model string for OpenRouter
# MODEL_NAME = "google/gemma-3-27b-it:free"
MODEL_NAME = "google/gemma-3n-e4b-it:free"
# MODEL_NAME = "google/gemini-2.0-flash-001" #Rate Limit issue 15 - 1500 RPM (Free Tier issue)
# MODEL_NAME = "nvidia/nemotron-nano-12b-v2-vl:free"
# MODEL_NAME="qwen/qwen3-vl-30b-a3b-thinking"
# MODEL_NAME = "stepfun/step-3.5-flash:free"

# ─── Data Structures ──────────────────────────────────────────────────────────
@dataclass
class TranscriptEntry:
    timestamp: str
    start_seconds: float
    text: str

@dataclass
class VideoData:
    video_id: str
    url: str
    title: str
    duration: Optional[str]
    description: Optional[str]
    language_original: str
    entries: list[TranscriptEntry]
    full_text: str
    chunks: list[dict] = field(default_factory=list)

# ─── Main Entry Point ─────────────────────────────────────────────────────────
def fetch_video_data(video_id: str) -> VideoData:
    url = build_youtube_url(video_id)
    logger.info(f"Asking OpenRouter ({MODEL_NAME}) to transcribe: {url}")

    raw_json = _openrouter_extract_transcript(url)
    video = _parse_response(video_id, url, raw_json)
    video.chunks = chunk_transcript(video.entries)

    logger.info(f"Success: '{video.title}' | Chunks: {len(video.chunks)}")
    return video

# ─── OpenRouter Extraction Logic ──────────────────────────────────────────────
_TRANSCRIPT_PROMPT = """
You are a professional transcriptionist. 
Watch the YouTube video at the provided URL and return a COMPLETE spoken transcript in JSON format.

JSON Structure:
{
  "title": "Video Title",
  "duration": "MM:SS",
  "description": "Short summary",
  "language_original": "Language",
  "transcript": [
    {"timestamp": "0:00", "start_seconds": 0, "text": "Verbatim speech..."},
    {"timestamp": "0:30", "start_seconds": 30, "text": "More speech..."}
  ]
}

Rules:
- Entry every 25-40 seconds.
- Verbatim speech only.
- Return ONLY raw JSON. No markdown backticks.
"""

def _openrouter_extract_transcript(youtube_url: str) -> dict:
    """
    Sends the request to OpenRouter with automated retry logic.
    """
    for attempt in range(3):
        try:
           
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{_TRANSCRIPT_PROMPT}\n\nURL: {youtube_url}"}
                        ]
                    }
                ],
                temperature=0.1,
                # response_format={"type": "json_object"} # Force JSON mode
            )

            raw_content = response.choices[0].message.content.strip()
            
            # Sanitization in case the model ignores 'json_object' and adds backticks
            clean_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_content, flags=re.MULTILINE)
            
            return json.loads(clean_json)

        except Exception as e:
            err_msg = str(e).lower()
            
            # OpenRouter Rate Limits / Provider Errors
            if any(x in err_msg for x in ["429", "rate", "limit", "quota", "overloaded"]):
                wait_time = 70 * (attempt + 1)
                logger.warning(f"OpenRouter Limit hit. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            logger.error(f"OpenRouter/Gemini Error: {e}")
            raise ValueError(f"❌ Transcription failed via OpenRouter: {str(e)}")

    raise ValueError("❌ Failed after 3 retries due to OpenRouter congestion.")

# ─── Data Parsing & Chunking ──────────────────────────────────────────────────
def _parse_response(video_id: str, url: str, data: dict) -> VideoData:
    raw_entries = data.get("transcript", [])
    if not raw_entries:
        raise ValueError("⚠️ No speech content detected.")

    entries = [
        TranscriptEntry(
            timestamp=str(item.get("timestamp", "0:00")),
            start_seconds=float(item.get("start_seconds", 0)),
            text=str(item.get("text", "")).strip()
        ) for item in raw_entries if item.get("text")
    ]

    return VideoData(
        video_id=video_id,
        url=url,
        title=data.get("title", "YouTube Video"),
        duration=data.get("duration"),
        description=data.get("description"),
        language_original=data.get("language_original", "Unknown"),
        entries=entries,
        full_text=" ".join(e.text for e in entries)
    )

def chunk_transcript(entries: list[TranscriptEntry]) -> list[dict]:
    size = int(os.getenv("CHUNK_SIZE", 400))
    overlap = int(os.getenv("CHUNK_OVERLAP", 50))
    chunks, current_words = [], []
    start_ts, start_sec = "0:00", 0.0

    for entry in entries:
        if not current_words:
            start_ts, start_sec = entry.timestamp, entry.start_seconds
        current_words.extend(entry.text.split())
        if len(current_words) >= size:
            chunks.append({
                "text": " ".join(current_words),
                "timestamp": start_ts,
                "start_seconds": start_sec
            })
            current_words = current_words[-overlap:]
    
    if current_words:
        chunks.append({"text": " ".join(current_words), "timestamp": start_ts, "start_seconds": start_sec})
    return chunks

def transcript_to_text_block(video: VideoData) -> str:
    """
    Format transcript as a readable timestamped block.
    Used internally by summarizer prompts.
    """
    lines = [f"[{e.timestamp}] {e.text}" for e in video.entries]
    return "\n".join(lines)