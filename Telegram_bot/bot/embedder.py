"""
embedder.py — FREE local embeddings via sentence-transformers.
No API key. No cost. Downloads ~80MB model once, then cached forever.
"""

import os
import numpy as np
from bot.utils import logger

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        logger.info(f"Loading embedding model: {name}…")
        _model = SentenceTransformer(name)
        logger.info("Embedding model ready ✓")
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed list of strings → float32 array of shape (N, dim)."""
    m = _get_model()
    return m.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=32,
    ).astype(np.float32)


def embed_query(query: str) -> np.ndarray:
    """Embed single query string → shape (dim,)."""
    return embed_texts([query])[0]
