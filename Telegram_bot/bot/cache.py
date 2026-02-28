"""
cache.py — Two-tier cache: Redis → in-memory fallback.
PDF bonus requirement: "Smart caching of transcripts."
"""

import os
import time
import pickle
import logging
from typing import Optional

logger = logging.getLogger(__name__)

USE_REDIS = os.getenv("USE_REDIS", "false").lower() == "true"
TTL       = int(os.getenv("REDIS_TTL_SECONDS", 86400))


class _Redis:
    def __init__(self):
        import redis
        self.r = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD") or None,
            decode_responses=False,
        )
        self.r.ping()
        logger.info("Redis connected")

    def get(self, k):
        try:
            d = self.r.get(f"ytbot:{k}")
            return pickle.loads(d) if d else None
        except Exception as e:
            logger.warning(f"Redis get: {e}")
            return None

    def set(self, k, v):
        try:
            self.r.setex(f"ytbot:{k}", TTL, pickle.dumps(v))
        except Exception as e:
            logger.warning(f"Redis set: {e}")


class _Memory:
    def __init__(self):
        self._s: dict = {}
        logger.info("In-memory cache active")

    def get(self, k):
        e = self._s.get(k)
        if e:
            v, exp = e
            if time.time() < exp:
                return v
            del self._s[k]
        return None

    def set(self, k, v):
        self._s[k] = (v, time.time() + TTL)


def _build():
    if USE_REDIS:
        try:
            return _Redis()
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), using memory")
    return _Memory()


_c = _build()


def get_video(video_id: str):
    return _c.get(f"v:{video_id}")

def set_video(video_id: str, data):
    _c.set(f"v:{video_id}", data)
    logger.info(f"Cached video: {video_id}")

def get_summary(video_id: str, lang: str) -> Optional[str]:
    return _c.get(f"s:{video_id}:{lang}")

def set_summary(video_id: str, lang: str, text: str):
    _c.set(f"s:{video_id}:{lang}", text)
