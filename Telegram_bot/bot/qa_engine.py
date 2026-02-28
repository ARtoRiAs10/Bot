"""
qa_engine.py — RAG-based Q&A engine.

Pipeline:
  1. Embed all transcript chunks locally (free, sentence-transformers)
  2. Build FAISS index (in-memory, per video)
  3. On question: embed query → retrieve top-k chunks → send to Gemini
  4. Gemini answers ONLY from retrieved chunks → no hallucinations

PDF requirement: "Answers must be grounded in the transcript. No hallucinations."
"""
"""
qa_engine.py — RAG-based Q&A engine.
Updated for OpenRouter compatibility and strict error sanitization.
"""

import os
import time
import numpy as np
from openai import OpenAI
from bot.transcript import VideoData
from bot.embedder import embed_texts, embed_query
from bot.utils import logger

# ─── Config ───────────────────────────────────────────────────────────────────
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Using StepFun for Q&A to preserve Gemini quota for transcription
MODEL_NAME = "stepfun/step-3.5-flash:free"
TOP_K      = int(os.getenv("TOP_K_CHUNKS", 4))

try:
    import faiss
    FAISS_OK = True
except ImportError:
    FAISS_OK = False
    logger.warning("faiss-cpu not found — using numpy fallback")


# ─── QAIndex ─────────────────────────────────────────────────────────────────
class QAIndex:
    """
    Per-video FAISS index.
    Built once when a video is loaded, stored in the user session.
    """

    def __init__(self, video: VideoData):
        self.video_id = video.video_id
        self.title    = video.title

        if not video.chunks:
            raise ValueError("No transcript chunks available to index.")

        self.chunks = video.chunks
        texts = [c["text"] for c in self.chunks]

        logger.info(f"Embedding {len(texts)} chunks for {video.video_id}…")
        self.embeddings = embed_texts(texts)   # (N, dim), already L2-normalized

        dim = self.embeddings.shape[1]
        if FAISS_OK:
            self.index = faiss.IndexFlatIP(dim)   # cosine sim on normalized vecs
            self.index.add(self.embeddings)
        else:
            self.index = None

        logger.info(f"QA index built: {len(self.chunks)} chunks, dim={dim}")

    def search(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """Return top-k most relevant transcript chunks for a query."""
        q = embed_query(query).reshape(1, -1)

        if FAISS_OK and self.index:
            scores, indices = self.index.search(q, top_k)
            return [self.chunks[i] for i in indices[0] if i < len(self.chunks)]
        else:
            sims = self.embeddings @ q.T
            top_idx = np.argsort(sims[:, 0])[::-1][:top_k]
            return [self.chunks[i] for i in top_idx]


# ─── Answer Generation ────────────────────────────────────────────────────────
def answer_question(
    qa_index: QAIndex,
    question: str,
    language: str = "English",
    history: list[dict] | None = None,
) -> str:
    """
    Retrieve relevant chunks → build grounded prompt → call OpenRouter.
    Returns the answer string, or a sanitized error message.
    """
    relevant = qa_index.search(question, top_k=TOP_K)
    if not relevant:
        return "NOT_COVERED"

    context_str = "\n\n---\n\n".join(
        f"[Timestamp: {c['timestamp']}]\n{c['text']}"
        for c in relevant
    )

    # Conversation history for multi-turn Q&A (last 6 turns)
    history_text = ""
    if history:
        pairs = history[-6:]
        history_text = "\n".join(
            f"{'User' if m.get('role')=='user' else 'Assistant'}: {m.get('content')}"
            for m in pairs
        )
        history_text = f"\nPrevious conversation:\n{history_text}\n"

    prompt = f"""
You are a precise Q&A assistant for the YouTube video: "{qa_index.title}".
{history_text}
You MUST answer ONLY using the transcript context below.
If the answer is not present in the context, output exactly: NOT_COVERED
Never guess, infer beyond the text, or use outside knowledge.
Respond in **{language}**.
When relevant, cite the timestamp (e.g. "At 3:45, the speaker says…").

TRANSCRIPT CONTEXT:
{context_str}

USER QUESTION: {question}

ANSWER:"""

    # ─── OpenRouter Call with Sanitized Errors ────────────────────────────────
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=800,
            )
            answer = response.choices[0].message.content.strip()

            # Normalise "I don't know" phrases to NOT_COVERED
            not_covered_phrases = [
                "not covered", "not mentioned", "not discussed",
                "not in the video", "not found", "no information",
                "cannot find", "does not appear", "does not mention"
            ]
            if any(p in answer.lower() for p in not_covered_phrases) or len(answer) < 2:
                return "NOT_COVERED"

            return answer

        except Exception as e:
            err_msg = str(e).lower()
            
            # 1. Handle Rate Limits internally (Retry once after 60s)
            if any(x in err_msg for x in ["429", "rate", "limit", "quota"]) and attempt == 0:
                logger.warning(f"QA Rate limit hit for {MODEL_NAME}. Attempting 60s retry...")
                time.sleep(60)
                continue
            
            # 2. Log technical details to console (for you)
            logger.error(f"Internal QA Error: {e}")

            # 3. Raise Clean, Non-Technical Errors (for the user)
            if any(x in err_msg for x in ["429", "rate", "limit", "quota"]):
                raise ValueError("⏳ The AI is currently at capacity. Please wait a minute and try again.")
            
            if "context_length" in err_msg or "too many tokens" in err_msg:
                raise ValueError("📏 This video's content is too large for the current AI model.")

            # Generic fallback to hide technical jargon
            raise ValueError("❌ I couldn't generate an answer right now. Please try a different question.")

    raise ValueError("⏳ AI providers are currently busy. Please try again in 2 minutes.")