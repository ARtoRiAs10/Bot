# 🎬 YouTube Telegram Bot — Gemini Native Edition

Uses **Gemini 1.5 Flash** to watch YouTube videos directly and extract full
timestamped transcripts. No youtube-transcript-api. No external transcript services.

---

## 📁 Directory Structure

```
youtube-telegram-bot/
│
├── main.py                              ← Entry point
│
├── bot/
│   ├── __init__.py
│   ├── handlers.py                      ← Telegram command & message handlers
│   ├── transcript.py                    ← Gemini transcript extraction
│   ├── summarizer.py                    ← Summary / DeepDive / ActionPoints
│   ├── qa_engine.py                     ← FAISS RAG Q&A
│   ├── embedder.py                      ← FREE local sentence-transformers
│   ├── session.py                       ← Per-user session management
│   ├── cache.py                         ← Redis / in-memory caching
│   └── utils.py                         ← Helpers
│
├── skills/
│   └── youtube-summarizer/
│       ├── SKILL.md                     ← OpenClaw skill definition
│       └── references/
│
├── .env                                 ← Your secrets (from .env.example)
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 🔑 How Gemini Replaces youtube-transcript-api

Instead of calling a third-party transcript service, we pass the YouTube URL
directly to Gemini 1.5 Flash as a video input:

```python
model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content([
    {"file_data": {"mime_type": "video/mp4", "file_uri": youtube_url}},
    "Extract the full transcript as JSON with timestamps..."
])
```

Gemini watches the video and returns structured JSON:
```json
{
  "title": "Video Title",
  "duration": "12:34",
  "transcript": [
    {"timestamp": "0:00", "start_seconds": 0, "text": "spoken words"},
    {"timestamp": "0:30", "start_seconds": 30, "text": "more words"}
  ]
}
```

This transcript then feeds the summary generator and FAISS Q&A index.

---

## 🚀 Setup — Step by Step

### Step 1: Get Telegram Bot Token

1. Open Telegram → search `@BotFather`
2. Send `/newbot` → name it → get token like `7123:AAHxxx...`
3. Set commands (send `/setcommands` to BotFather):
```
start - Start the bot
summary - Re-generate video summary
deepdive - In-depth analysis
actionpoints - Extract action items
language - Change response language
reset - Clear session
help - Show help
```

### Step 2: Get FREE Gemini API Key

1. Go to **https://aistudio.google.com/app/apikey**
2. Sign in with Google → **Create API key**
3. Copy the key (starts with `AIza...`)

Free limits: **15 requests/min | 1 million tokens/day**

### Step 3: Configure .env

```bash
cp .env.example .env
```

Edit `.env`:
```env
TELEGRAM_BOT_TOKEN=7123456789:AAHxxx_your_token
GEMINI_API_KEY=AIzaSy_your_gemini_key
GEMINI_MODEL=gemini-1.5-flash
```

### Step 4: Install & Run

```bash
# Create virtual environment
python -m venv venv

# Activate (Mac/Linux):
source venv/bin/activate
# Activate (Windows):
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

First run downloads the local embedding model (~80MB, one-time only).

---

## 📱 Bot Usage

| Action | What to do |
|--------|-----------|
| Load a video | Send any YouTube URL |
| Auto-summary | Bot generates it automatically after loading |
| Ask questions | Type any question after video is loaded |
| Not in video | Bot replies "This topic is not covered in the video." |
| Change language | "Summarize in Hindi" or `/language Tamil` |
| Deep analysis | `/deepdive` |
| Action items | `/actionpoints` |
| Redo summary | `/summary` |
| New video | Send new URL or `/reset` |

### Example Conversation

```
You:  https://youtube.com/watch?v=example
Bot:  ⏳ Gemini is watching the video… (20–60 seconds)
Bot:  🎥 *Video Title*
      📌 *5 Key Points*
      1. ...
      ⏱ *Important Timestamps*
      • 1:23 — Topic starts here
      🧠 *Core Takeaway*
      One sentence summary.

You:  What did they say about pricing?
Bot:  At 4:32, the speaker explains that pricing is...

You:  Summarize in Hindi
Bot:  🌐 Switched to Hindi! Regenerating...
Bot:  🎥 *वीडियो का शीर्षक*
      📌 *5 मुख्य बिंदु*...

You:  /deepdive
Bot:  🔍 *Deep Dive: Video Title*...
```

---

## ☁️ Deploy (24/7 Live)

### Railway (Easiest — Free tier)
```bash
git init && git add . && git commit -m "init"
# Push to GitHub, then connect on railway.app
# Add env vars in Railway dashboard → Deploy
```

### Render
1. render.com → New → Background Worker
2. Build: `pip install -r requirements.txt`
3. Start: `python main.py`
4. Add env vars → Deploy

### VPS (systemd)
```bash
git clone your-repo && cd youtube-telegram-bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env

# systemd service:
sudo nano /etc/systemd/system/ytbot.service
```
```ini
[Unit]
Description=YouTube Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/youtube-telegram-bot
EnvironmentFile=/home/ubuntu/youtube-telegram-bot/.env
ExecStart=/home/ubuntu/youtube-telegram-bot/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable ytbot && sudo systemctl start ytbot
```

---

## 🏗️ Architecture & Design Decisions

**Why Gemini for transcription?**
Gemini 1.5 Flash natively understands YouTube video URLs. No external
transcript API means no failures from disabled captions or rate limiting.
Gemini handles audio quality variations, accents, and multiple speakers better
than auto-captions.

**Why local embeddings (sentence-transformers)?**
Zero API cost. The `all-MiniLM-L6-v2` model runs entirely on CPU in ~5ms per
query. 384-dimensional embeddings are sufficient for accurate semantic search
over transcript chunks.

**Why FAISS for Q&A?**
FAISS finds the most relevant transcript chunks in milliseconds even for
2-hour videos with 300+ chunks. We send only those 4 chunks to Gemini —
drastically reducing token usage and preventing hallucinations.

**Why two-tier caching?**
Gemini transcript calls take 20-60 seconds. If two users send the same video
link, the second gets an instant response from cache. Summary caching is
per-language so Hindi and English summaries are cached separately.

---

## ⚠️ Known Limitations

| Limitation | Reason |
|-----------|--------|
| Videos > ~1 hour may fail | Gemini 1.5 Flash context limit |
| 15 req/min rate limit | Gemini free tier |
| Age-restricted videos | Gemini cannot access them |
| Live streams | No completed transcript available |
| Music-only videos | No speech to transcribe |

---

## 💰 Cost

Running cost with Gemini free tier: **$0.00**

| Component | Cost |
|-----------|------|
| Gemini transcript + summary | Free (1500 req/day) |
| Local embeddings | Free forever |
| FAISS search | Free |
| Telegram bot | Free |

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| `GEMINI_API_KEY not set` | Add key to `.env` |
| Transcript takes > 2 min | Try a shorter video first |
| Rate limit error | Wait 1 minute, try again |
| Age-restricted video error | Use a public video |
| `torch` install slow | PyTorch is large (~200MB). Normal. |
