# 🎬 YouTube Telegram Bot

A Telegram bot that ingests any YouTube video, extracts a full timestamped transcript, and lets users chat with the video — asking questions, generating summaries, deep-dives, and action points — all powered by **OpenRouter** (with any model of your choice) and a local FAISS semantic search index.

---

## 📁 Directory Structure

```
Bot/
│
├── Telegram_bot/
│   ├── main.py              ← Entry point; starts the Telegram polling loop
│   ├── handlers.py          ← Command & message handlers (/start, /summary, Q&A, etc.)
│   ├── transcript.py        ← YouTube transcript extraction via youtube-transcript-api
│   ├── summarizer.py        ← Gemini-powered summary / DeepDive / ActionPoints
│   ├── qa_engine.py         ← FAISS-based RAG question answering
│   ├── embedder.py          ← Local sentence-transformers embeddings (no API cost)
│   ├── session.py           ← Per-user session & state management
│   ├── cache.py             ← In-memory transcript & summary caching
│   └── utils.py             ← URL parsing, message formatting helpers
│
├── Dockerfile
├── LICENSE                  ← Apache-2.0
└── README.md
```

---

## ⚙️ How It Works

### 1 — Transcript Extraction
The bot uses **`youtube-transcript-api`** to pull the raw caption/transcript data directly from YouTube (works for any video with auto-generated or manual captions). The transcript is chunked into overlapping segments and stored per user session.

```python
from youtube_transcript_api import YouTubeTranscriptApi

transcript = YouTubeTranscriptApi.get_transcript(video_id)
# Returns: [{"text": "...", "start": 12.4, "duration": 3.1}, ...]
```

### 2 — Semantic Indexing (FAISS + sentence-transformers)
Each transcript chunk is embedded locally using `all-MiniLM-L6-v2` (runs on CPU, ~5 ms/query, zero API cost) and inserted into a **FAISS** flat index. At query time the top-4 relevant chunks are retrieved in milliseconds.

### 3 — OpenRouter for Generation
Only the retrieved chunks (not the entire transcript) are sent to **OpenRouter** for answering questions, summarising, or producing action points. OpenRouter gives you access to dozens of models (GPT-4o, Claude, Gemini, Mistral, etc.) through a single API. This keeps token usage low and responses grounded.

```python
import requests

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "mistralai/mistral-7b-instruct",   # or any model on OpenRouter
        "messages": [
            {"role": "system", "content": "You are a helpful video assistant."},
            {"role": "user", "content": f"Context:\n{relevant_chunks}\n\nQuestion: {question}"}
        ]
    }
)
```

### Data Flow

```
YouTube URL
    │
    ▼
youtube-transcript-api ──► raw transcript chunks
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
            FAISS index                     in-memory cache
         (sentence-transformers)        (skip re-fetch for same URL)
                    │
              top-k chunks
                    │
                    ▼
              OpenRouter      ──► formatted Telegram reply
```

---

## 🚀 Setup

### Step 1 — Create a Telegram Bot

1. Open Telegram → search **@BotFather**
2. Send `/newbot`, follow the prompts, copy the token (`7123:AAHxxx...`)
3. Set bot commands via `/setcommands`:

```
start        - Start the bot
summary      - Re-generate video summary
deepdive     - In-depth analysis
actionpoints - Extract action items
language     - Change response language
reset        - Clear session
help         - Show help
```

### Step 2 — Get an OpenRouter API Key

1. Visit **https://openrouter.ai/keys**
2. Sign in / sign up → **Create Key** → copy it (starts with `sk-or-...`)
3. Browse available models at **https://openrouter.ai/models** — many are free or very cheap

### Step 3 — Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=7123456789:AAHxxx_your_token
OPENROUTER_API_KEY=sk-or-your_openrouter_key
OPENROUTER_MODEL=mistralai/mistral-7b-instruct   # any model slug from openrouter.ai/models
```

### Step 4 — Install & Run

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Note: first run downloads the embedding model (~80 MB, one-time only)
# and PyTorch (~200 MB) — this is expected

# Start the bot
python Telegram_bot/main.py
```

---

## 📱 Usage

| Action | What to do |
|---|---|
| Load a video | Send any YouTube URL |
| Auto-summary | Generated automatically after the video loads |
| Ask questions | Type any question once a video is loaded |
| Topic not in video | Bot replies "This topic is not covered in the video." |
| Change language | "Summarize in Hindi" or `/language Tamil` |
| Deep analysis | `/deepdive` |
| Extract tasks | `/actionpoints` |
| Redo summary | `/summary` |
| New video | Send a new URL or `/reset` |

### Example Conversation

```
You:  https://youtube.com/watch?v=dQw4w9WgXcQ
Bot:  ⏳ Fetching transcript and building index…
Bot:  🎥 *Video Title*
      📌 *5 Key Points*
      1. …
      ⏱ *Important Timestamps*
      • 1:23 — Topic starts here
      🧠 *Core Takeaway*
      One-sentence summary.

You:  What did they say about pricing?
Bot:  At 4:32, the speaker explains that pricing…

You:  Summarize in Hindi
Bot:  🌐 Switched to Hindi! Regenerating…

You:  /deepdive
Bot:  🔍 *Deep Dive: Video Title*…

You:  /actionpoints
Bot:  ✅ *Action Points*
      1. …
```

---

## ☁️ Deployment (24/7)

### Docker (Recommended)

```bash
docker build -t yt-telegram-bot .
docker run -d --env-file .env yt-telegram-bot
```

### Railway (Easiest free option)

```bash
git init && git add . && git commit -m "init"
# Push to GitHub, connect repo on railway.app
# Add env vars in the Railway dashboard → Deploy
```

### Render

1. render.com → **New → Background Worker**
2. Build command: `pip install -r requirements.txt`
3. Start command: `python Telegram_bot/main.py`
4. Add env vars → Deploy

### VPS (systemd)

```bash
git clone https://github.com/ARtoRiAs10/Bot && cd Bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env
```

Create `/etc/systemd/system/ytbot.service`:

```ini
[Unit]
Description=YouTube Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/Bot
EnvironmentFile=/home/ubuntu/Bot/.env
ExecStart=/home/ubuntu/Bot/venv/bin/python Telegram_bot/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ytbot && sudo systemctl start ytbot
```

---

## 🏗️ Architecture & Design Decisions

**Why OpenRouter for generation?**
OpenRouter provides a unified API to access virtually any LLM — GPT-4o, Claude, Gemini, Mistral, LLaMA, and more — with a single key and endpoint. This means you can swap models without changing any code, just update `OPENROUTER_MODEL` in your `.env`. Many models on OpenRouter are free or extremely cheap, making it ideal for personal bots.

**Why local embeddings (`sentence-transformers`)?**
Zero API cost. `all-MiniLM-L6-v2` runs on CPU with ~5 ms per query and produces 384-dimensional embeddings that are more than sufficient for accurate semantic retrieval over transcript chunks.

**Why FAISS for Q&A?**
FAISS finds the top-k most relevant chunks in milliseconds even for 2-hour videos with 300+ segments. Sending only those chunks to OpenRouter drastically reduces token usage and prevents hallucinations from irrelevant context.

**Why in-memory caching?**
Transcript fetching and FAISS index building take a few seconds. If a user re-asks a question or requests a different summary format for the same video, both the transcript and embeddings are served from cache instantly with no re-computation.

---

## ⚠️ Known Limitations

| Limitation | Reason |
|---|---|
| Videos without captions | `youtube-transcript-api` requires captions (auto-generated or manual) |
| Age-restricted videos | Cannot be accessed without authentication |
| Live streams | No completed transcript available |
| Very long videos (2h+) | FAISS index and LLM context work best under ~2 hours |
| Rate limits | Depend on the OpenRouter model chosen — check per-model limits at openrouter.ai |
| Music-only videos | No speech captions to extract |

---

## 💰 Cost

| Component | Cost |
|---|---|
| OpenRouter (summary + Q&A) | Free for many models; pay-per-token for premium ones |
| `youtube-transcript-api` | Free |
| Local embeddings (sentence-transformers) | Free forever |
| FAISS vector search | Free |
| Telegram Bot API | Free |
| **Total** | **$0.00** |

---

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| `TELEGRAM_BOT_TOKEN not set` | Check your `.env` file |
| `OPENROUTER_API_KEY not set` | Add your key to `.env` |
| "No transcript available" | The video has no captions — try a different video |
| Rate limit / 429 error | Check your OpenRouter model's rate limits at openrouter.ai |
| Age-restricted video error | Use a public, unrestricted video |
| `torch` install is slow | PyTorch is large (~200 MB) — this is normal on first install |
| Bot not responding | Check `systemctl status ytbot` or your hosting logs |

---

## 📄 License

[Apache-2.0](LICENSE)
