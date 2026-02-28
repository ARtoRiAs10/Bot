"""
session.py — Per-user isolated sessions.
Each Telegram chat_id gets its own video, Q&A index, language, and history.
PDF requirement: "Must handle multiple users simultaneously."
"""

import time
from dataclasses import dataclass, field
from typing import Optional
from bot.transcript import VideoData
from bot.qa_engine import QAIndex
from bot.utils import logger

TTL = 3600 * 6   # 6 hours idle before session expires


@dataclass
class UserSession:
    chat_id:  int
    language: str = "English"
    video:    Optional[VideoData] = None
    qa_index: Optional[QAIndex]  = None
    history:  list[dict] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)

    def has_video(self) -> bool:
        return self.video is not None and self.qa_index is not None

    def load_video(self, video: VideoData):
        self.video    = video
        self.qa_index = QAIndex(video)
        self.history  = []    # fresh conversation for new video
        self.touch()

    def add_history(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def touch(self):
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > TTL


class SessionStore:
    def __init__(self):
        self._store: dict[int, UserSession] = {}

    def get(self, chat_id: int) -> UserSession:
        self._cleanup()
        if chat_id not in self._store:
            self._store[chat_id] = UserSession(chat_id=chat_id)
            logger.info(f"New session: {chat_id}")
        self._store[chat_id].touch()
        return self._store[chat_id]

    def reset(self, chat_id: int) -> UserSession:
        self._store.pop(chat_id, None)
        return self.get(chat_id)

    def _cleanup(self):
        for cid in [c for c, s in self._store.items() if s.is_expired()]:
            del self._store[cid]
            logger.info(f"Session expired: {cid}")

    @property
    def active(self) -> int:
        return len(self._store)


store = SessionStore()
