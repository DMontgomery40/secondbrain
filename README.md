# Second Brain

**Your local-first, AI-powered visual memory system for macOS**

Second Brain is a local-first, high-fidelity desktop memory system for macOS. It captures your screen at 1–2 fps, extracts rich text and context with dual OCR engines (Apple Vision or DeepSeek), indexes everything for instant recall, and ships with an elegant timeline UI with comprehensive settings panel. All data (screenshots, metadata, embeddings, logs) stays on disk in a predictable directory so you maintain full control.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![macOS](https://img.shields.io/badge/macOS-11.0+-blue.svg)](https://www.apple.com/macos/)

---

## Highlights

- **Continuous visual capture** – quartz-backed screenshots with app / window metadata and disk safeguards.
- **Dual OCR engines** – Apple Vision (local, fast, free) or DeepSeek OCR (local, multimodal, 10-20x compression). Switch engines anytime via GUI or CLI.
- **Comprehensive settings panel** – Beautiful GUI for all 30+ configuration options with live system statistics. No more manual JSON editing!
- **Search two ways** – trigram FTS5 for exact matches plus MiniLM-powered semantic search via Chroma.
- **Timeline UI** – React + Vite SPA with filters, OCR engine toggle, complete settings management, and session replay.
- **MCP server** – Model Context Protocol server exposes your memory to AI assistants (Claude, ChatGPT, etc.) via 5 tools.
- **Local API** – FastAPI server with comprehensive endpoints for frames, apps, settings, and system stats.
- **Context7 integration** – Fetch latest library documentation on-demand via CLI.
- **Operational tooling** – CLI commands for start/stop/status/health, timeline launch, MCP server, and service packaging.
- **Privacy-first** – no outbound calls beyond chosen OCR provider; configurable retention windows and storage quotas.
- **AI Summaries** – Automatic hourly summaries using GPT-5 (or GPT-4o-mini)
- **99% Storage Savings** – Smart capture + H.264 video compression (216 GB/day → 1.4 GB/day)
- **Blazing Fast** – 100x faster than cloud OCR, instant search
- **Zero Cost** – No API fees for OCR, optional GPT for summaries

---

## Architecture at a Glance

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             Second Brain                                 │
├──────────────────────────────────────────────────────────────────────────┤
│ Capture → [OpenAI GPT-5 OR DeepSeek] → SQLite + Chroma → UI/API/MCP      │
│    │              │            │              │              │            │
│ Quartz      GPT-5 Vision   DeepSeek     full-text FTS   FastAPI          │
│ metadata    (accurate)     (free)       bm25 ranking    React timeline   │
│ 1-2 fps     semantic       batch OCR    embeddings      Settings panel   │
│             context        10x cheaper  Chroma store    MCP server       │
└──────────────────────────────────────────────────────────────────────────┘
```
=======
- ** 100% Local OCR** – Apple Vision framework for instant text extraction (< 1s per frame)
- ** AI Summaries** – Automatic hourly summaries using GPT-5 (or GPT-4o-mini)
- ** 99% Storage Savings** – Smart capture + H.264 video compression (216 GB/day → 1.4 GB/day)
- ** Beautiful UI** – Streamlit-powered daily review with visual timeline
- ** Privacy First** – All processing local, data never leaves your Mac
- ** Blazing Fast** – 100x faster than cloud OCR, instant search
- ** Zero Cost** – No API fees for OCR, optional GPT for summaries
>>>>>>> origin/main

**New in this version:**
- ✨ DeepSeek OCR integration (10-20x cost reduction, runs locally)
- ✨ Comprehensive settings panel (30+ configurable options)
- ✨ MCP server for AI assistant integration
- ✨ Context7 integration for documentation fetching
- ✨ Image combination for batch processing
  
  DeepSeek OCR runs locally using the MLX backend (Apple Silicon) with the Hugging Face model `mlx-community/DeepSeek-OCR-4bit`.

---

## Quick Start

### System Requirements

**Minimum (Apple Vision OCR):**
- Apple Silicon M1+
- 8 GB RAM
- 50 GB free disk space
- macOS 15+ (Sequoia)

**Recommended (DeepSeek OCR + Reranker - default):**
- Apple Silicon M1/M2/M3/M4
- 16 GB RAM (24 GB+ recommended)
- 100 GB free disk space
- macOS 15+ (Sequoia)

**Model Downloads (first run):**
- DeepSeek-OCR-8bit: 3.85 GB
- BAAI/bge-reranker-large: 2.24 GB
- Total: ~6.1 GB

**Software:**
- Python 3.11+
- Node.js 20+
- ffmpeg (for video conversion): `brew install ffmpeg`
- Screen Recording + Accessibility permissions
- OpenAI API key (optional, for AI summaries)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/gregcmartin/secondbrain.git
cd secondbrain

# 2. Python environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
pip install -e .

# 3. Timeline UI (optional but recommended)
cd web/timeline
npm install
npm run build
cd ../..

# 4. Configure API credentials (optional - for AI summaries)
cp .env.example .env
echo "OPENAI_API_KEY=sk-..." >> .env

# 5. Grant permissions
# System Settings → Privacy & Security → Screen Recording
# Enable for Terminal or your IDE
```

### Startup Scripts

If you prefer quick helpers, use these scripts after installation:

- scripts/start_simple_deepseek.sh
  - DeepSeek OCR via MLX (local, Apple Silicon). Downloads the model on first run.
- scripts/start_og_openai.sh
  - Original GPT‑5 Vision OCR path (requires OPENAI_API_KEY).
- scripts/start_everything_on.sh
  - DeepSeek MLX + OpenAI embeddings + BAAI reranker. If the UI is built (web/timeline/dist), the Timeline server is launched in the background.

### macOS Screen Recording Permission (Required)

If screencapture fails with returncode 1, grant Screen Recording permissions:
- System Settings → Privacy & Security → Screen Recording
- Enable for your terminal app (Terminal/iTerm) and for your Python binary under the venv (you may need to add it manually)
- Also grant Accessibility permission under Privacy & Security → Accessibility (optional but recommended)

### Run the system

```bash
# Start capture service (runs in background)
second-brain start

# View your day in beautiful UI
second-brain ui

# Check status
second-brain status
```

---

## Features

### Smart Capture

- **Adaptive FPS**: 1.0 FPS when active, 0.2 FPS when idle (saves 80% during idle)
- **Frame Change Detection**: Skips duplicate frames automatically (30-50% savings)
- **Activity Monitoring**: Detects keyboard/mouse input to adjust capture rate
- **Disk Safeguards**: Configurable storage limits and free space monitoring

### Local OCR

- **Apple Vision Framework**: Native macOS OCR (same as Rewind)
- **Instant Processing**: < 1 second per frame
- **High Accuracy**: 95% confidence
- **Zero Cost**: No API fees
- **Privacy**: 100% local, data never leaves your Mac

### AI Summaries

- **Automatic**: Hourly summaries generated in background
- **GPT-5 Ready**: Uses GPT-5
- **Stored**: Summaries saved in database for instant access
- **Configurable**: Hourly/daily intervals
- **Raw Data Kept**: Original OCR text preserved

### Storage Optimization

- **Smart Capture**: 30-50% reduction via duplicate detection
- **Adaptive FPS**: 80% reduction during idle
- **Text Compression**: zglib for large text blocks (50-70% savings)
- **H.264 Video**: 96%+ compression for long-term storage
- **Combined**: 99.3% total savings (216 GB/day → 1.4 GB/day)

### Streamlit UI

- **Daily Overview**: AI-generated summaries and statistics
- **Visual Timeline**: Scroll through your day with frame thumbnails
- **Hourly Grouping**: Organized by hour for easy navigation
- **Frame Details**: Click any frame to see full image and OCR text
- **App Statistics**: See which apps you used most
- **Beautiful Design**: Gradient cards and responsive layout

### Search

- **Full-Text Search**: Fast FTS5 with trigram tokenization
- **Semantic Search**: Vector embeddings with Chroma + MiniLM
- **Filters**: By app, date range, time
- **CLI & UI**: Search from command line or Streamlit interface

---

## Storage Efficiency


```
Daily (smart capture):     37 GB/day (83% savings)
Daily (+ video conversion): 1.4 GB/day (99.3% savings)
Cost:                       $0/day (local OCR)
```


---

## CLI Reference

| Command | Description |
|---------|-------------|
| `second-brain start [--fps 1.5] [--ocr-engine openai|deepseek] [--embeddings-provider sbert|openai] [--embeddings-model <name>] [--openai-emb-model <name>] [--enable-reranker/--disable-reranker] [--reranker-model <name>]` | Start capture/OCR pipeline; set embeddings provider/reranker. |
| `second-brain stop` | Send SIGTERM to the running service. |
| `second-brain status` | Inspect frame/text counts, database size, capture window range. |
| `second-brain health` | Quick checklist: process, OCR creds, database, disk headroom. |
| `second-brain query "term" [--app ...] [--from ...] [--to ...] [--rerank]` | Full-text search (FTS5 + bm25), optionally reranked with BAAI. |
| `second-brain query "term" --semantic [--rerank]` | Semantic search over embeddings (provider-configured), optionally reranked. |
| `second-brain timeline [--host 127.0.0.1] [--port 8000] [--no-open]` | Run FastAPI + serve Timeline UI with settings panel. |
| `second-brain ui` | Launch Streamlit UI (port 8501) |
| `second-brain convert-to-video` | Convert frames to H.264 video |
| `second-brain reset` | Delete all data and start fresh |
| `second-brain mcp-server` | Start MCP server to expose memory to AI assistants. |
| `second-brain docs search "library-name" [--save path.md]` | Fetch documentation via Context7. |
| `second-brain docs fetch "/library-id" [--topic "..."]` | Fetch docs by exact library ID. |
| `second-brain docs batch libraries.json --output-dir docs/` | Batch fetch multiple libraries. |

### Examples

```bash
# Search with filters
second-brain query "python code" --app "VSCode" --from 2025-10-20

# Semantic search
second-brain query "machine learning" --semantic

# Convert yesterday's frames to video
second-brain convert-to-video

# Convert specific date and keep originals
second-brain convert-to-video --date 2025-10-27 --keep-frames

# Reset and start fresh (deletes all data)
second-brain reset

# Reset without confirmation prompt
second-brain reset --yes
```

### OCR Engine Selection

You can choose your OCR engine in three ways:

1. **CLI flag:** `second-brain start --ocr-engine deepseek`
2. **GUI toggle:** Click ⚙️ in Timeline UI → OCR Engine
3. **Config file:** Edit `~/Library/Application Support/second-brain/config/settings.json`

**DeepSeek backend (MLX only):**
- Local MLX (Apple Silicon): set `ocr.engine` to `"deepseek"`. Configure `ocr.deepseek_model` if you want a different HF id. Requires `mlx-vlm`; first run downloads the model.

Example config overrides in `settings.json`:

```
{
  "ocr": {
    "engine": "deepseek",
    "deepseek_model": "mlx-community/DeepSeek-OCR-4bit",
    "mlx_max_tokens": 1200,
    "mlx_temperature": 0.0
  },
  "embeddings": {
    "enabled": true,
    "provider": "sbert", // or "openai"
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "openai_model": "text-embedding-3-small",
    "reranker_enabled": true,
    "reranker_model": "BAAI/bge-reranker-large"
  }
}
```

**Embeddings provider:**
- SBERT (local): `embeddings.provider = "sbert"` with `embeddings.model` (e.g. all-MiniLM-L6-v2)
- OpenAI (API): `embeddings.provider = "openai"` with `embeddings.openai_model` (e.g. text-embedding-3-small)

**Reranker:**
- Enable cross-encoder reranker: `embeddings.reranker_enabled = true`, `embeddings.reranker_model = "BAAI/bge-reranker-large"`

**Cost comparison:**
- OpenAI GPT-5: ~$0.01 per frame, very accurate, includes semantic context
- DeepSeek OCR (Docker or MLX): Free/local, 10-20x compression, batch processing

---

| Command | Description |
|---------|-------------|
| `second-brain start [--fps 1.5] [--ocr-engine openai|deepseek] [--embeddings-provider sbert|openai] [--embeddings-model <name>] [--openai-emb-model <name>] [--enable-reranker/--disable-reranker] [--reranker-model <name>]` | Start capture/OCR pipeline; set embeddings provider/reranker. |
| `second-brain stop` | Send SIGTERM to the running service. |
| `second-brain status` | Inspect frame/text counts, database size, capture window range. |
| `second-brain health` | Quick checklist: process, OCR creds, database, disk headroom. |
| `second-brain query "term" [--app ...] [--from ...] [--to ...] [--rerank]` | Full-text search (FTS5 + bm25), optionally reranked with BAAI. |
| `second-brain query "term" --semantic [--rerank]` | Semantic search over embeddings (provider-configured), optionally reranked. |
| `second-brain timeline [--host 127.0.0.1] [--port 8000] [--no-open]` | Run FastAPI + serve Timeline UI with settings panel. |
| `second-brain ui` | Launch Streamlit UI (port 8501) |
| `second-brain convert-to-video` | Convert frames to H.264 video |
| `second-brain reset` | Delete all data and start fresh |
| `second-brain mcp-server` | Start MCP server to expose memory to AI assistants. |
| `second-brain docs search "library-name" [--save path.md]` | Fetch documentation via Context7. |
| `second-brain docs fetch "/library-id" [--topic "..."]` | Fetch docs by exact library ID. |
| `second-brain docs batch libraries.json --output-dir docs/` | Batch fetch multiple libraries. |

```json
{
  "capture": {
| Command | Description |
|---------|-------------|
| `second-brain start [--fps 1.5] [--ocr-engine openai|deepseek] [--embeddings-provider sbert|openai] [--embeddings-model <name>] [--openai-emb-model <name>] [--enable-reranker/--disable-reranker] [--reranker-model <name>]` | Start capture/OCR pipeline; set embeddings provider/reranker. |
| `second-brain stop` | Send SIGTERM to the running service. |
| `second-brain status` | Inspect frame/text counts, database size, capture window range. |
| `second-brain health` | Quick checklist: process, OCR creds, database, disk headroom. |
| `second-brain query "term" [--app ...] [--from ...] [--to ...] [--rerank]` | Full-text search (FTS5 + bm25), optionally reranked with BAAI. |
| `second-brain query "term" --semantic [--rerank]` | Semantic search over embeddings (provider-configured), optionally reranked. |
| `second-brain timeline [--host 127.0.0.1] [--port 8000] [--no-open]` | Run FastAPI + serve Timeline UI with settings panel. |
| `second-brain ui` | Launch Streamlit UI (port 8501) |
| `second-brain convert-to-video` | Convert frames to H.264 video |
| `second-brain reset` | Delete all data and start fresh |
| `second-brain mcp-server` | Start MCP server to expose memory to AI assistants. |
| `second-brain docs search "library-name" [--save path.md]` | Fetch documentation via Context7. |
| `second-brain docs fetch "/library-id" [--topic "..."]` | Fetch docs by exact library ID. |
| `second-brain docs batch libraries.json --output-dir docs/` | Batch fetch multiple libraries. |
    "max_disk_usage_gb": 100,
    "min_free_space_gb": 10
  },
  "ocr": {
| Command | Description |
|---------|-------------|
| `second-brain start [--fps 1.5] [--ocr-engine openai|deepseek] [--embeddings-provider sbert|openai] [--embeddings-model <name>] [--openai-emb-model <name>] [--enable-reranker/--disable-reranker] [--reranker-model <name>]` | Start capture/OCR pipeline; set embeddings provider/reranker. |
| `second-brain stop` | Send SIGTERM to the running service. |
| `second-brain status` | Inspect frame/text counts, database size, capture window range. |
| `second-brain health` | Quick checklist: process, OCR creds, database, disk headroom. |
| `second-brain query "term" [--app ...] [--from ...] [--to ...] [--rerank]` | Full-text search (FTS5 + bm25), optionally reranked with BAAI. |
| `second-brain query "term" --semantic [--rerank]` | Semantic search over embeddings (provider-configured), optionally reranked. |
| `second-brain timeline [--host 127.0.0.1] [--port 8000] [--no-open]` | Run FastAPI + serve Timeline UI with settings panel. |
| `second-brain ui` | Launch Streamlit UI (port 8501) |
| `second-brain convert-to-video` | Convert frames to H.264 video |
| `second-brain reset` | Delete all data and start fresh |
| `second-brain mcp-server` | Start MCP server to expose memory to AI assistants. |
| `second-brain docs search "library-name" [--save path.md]` | Fetch documentation via Context7. |
| `second-brain docs fetch "/library-id" [--topic "..."]` | Fetch docs by exact library ID. |
| `second-brain docs batch libraries.json --output-dir docs/` | Batch fetch multiple libraries. |
  }
}
```

| Command | Description |
|---------|-------------|
| `second-brain start [--fps 1.5] [--ocr-engine openai|deepseek] [--embeddings-provider sbert|openai] [--embeddings-model <name>] [--openai-emb-model <name>] [--enable-reranker/--disable-reranker] [--reranker-model <name>]` | Start capture/OCR pipeline; set embeddings provider/reranker. |
| `second-brain stop` | Send SIGTERM to the running service. |
| `second-brain status` | Inspect frame/text counts, database size, capture window range. |
| `second-brain health` | Quick checklist: process, OCR creds, database, disk headroom. |
| `second-brain query "term" [--app ...] [--from ...] [--to ...] [--rerank]` | Full-text search (FTS5 + bm25), optionally reranked with BAAI. |
| `second-brain query "term" --semantic [--rerank]` | Semantic search over embeddings (provider-configured), optionally reranked. |
| `second-brain timeline [--host 127.0.0.1] [--port 8000] [--no-open]` | Run FastAPI + serve Timeline UI with settings panel. |
| `second-brain ui` | Launch Streamlit UI (port 8501) |
| `second-brain convert-to-video` | Convert frames to H.264 video |
| `second-brain reset` | Delete all data and start fresh |
| `second-brain mcp-server` | Start MCP server to expose memory to AI assistants. |
| `second-brain docs search "library-name" [--save path.md]` | Fetch documentation via Context7. |
| `second-brain docs fetch "/library-id" [--topic "..."]` | Fetch docs by exact library ID. |
| `second-brain docs batch libraries.json --output-dir docs/` | Batch fetch multiple libraries. |

---

## How It Works

### 1. Continuous Capture
- Captures screen at 1 FPS (or 0.2 FPS when idle)
- Skips duplicate frames automatically
- Saves as PNG/WebP with metadata JSON

### 2. Local OCR
- Apple Vision extracts text instantly
- Stores in SQLite with compression
- Indexes for full-text search

### 3. AI Summarization
- Every hour, generates summary of activity
- Uses GPT-5 (or GPT-4o-mini)
- Stores summaries in database

### 4. Long-Term Storage
- Run `convert-to-video` to compress old frames
- 96%+ compression with H.264
- Optionally delete originals to save space

### 5. Review & Search
- Use Streamlit UI for daily review
- Search with CLI or UI
- View any frame with OCR text

---

## Performance

### OCR Processing:
- **Speed**: < 1 second per frame
- **Accuracy**: 95% confidence
- **Success Rate**: 94%+ (750/797 frames)
- **Cost**: $0 (100% local)

### Storage Efficiency:
- **Frame Skipping**: Up to 100% during static content
- **Adaptive FPS**: 80% reduction when idle
- **Video Compression**: 96.25% (tested on 4,232 frames)
- **Database**: 17.93 MB for 797 frames + 750 text blocks

### System Resources:
- **CPU**: ~5% (local OCR is efficient)
- **Memory**: ~500 MB
- **Disk I/O**: Optimized with WAL mode
- **Network**: Zero for OCR, minimal for summaries

---

## Privacy & Security

- **100% Local OCR**: Text extraction never leaves your Mac
- **Local Storage**: All data in `~/Library/Application Support/second-brain/`
- **Optional Cloud**: Only for AI summaries (can be disabled)
- **No Tracking**: No telemetry, no analytics
- **Your Data**: You own it, you control it


---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Inspired by [Rewind](https://www.rewind.ai/) and [Screenpipe](https://github.com/mediar-ai/screenpipe)
- Built with Apple Vision framework, SQLite, and Python
- UI powered by Streamlit
- Video compression via ffmpeg


---

## DeepSeek OCR Setup (Optional)

To use the free DeepSeek OCR engine with local MLX backend (Apple Silicon):

```bash
# MLX-VLM is already in requirements.txt - model downloads automatically on first use

# Switch to DeepSeek in Timeline UI:
# Open http://127.0.0.1:8000 → Click ⚙️ → OCR Engine → DeepSeek → Backend: mlx

# Or via CLI:
second-brain start --ocr-engine deepseek --deepseek-backend mlx
```

DeepSeek performance varies by mode (tiny/small/base/large/optimal) - adjustable in Settings Panel.

---

## Roadmap

| Command | Description |
|---------|-------------|
| `second-brain start [--fps 1.5] [--ocr-engine openai|deepseek] [--embeddings-provider sbert|openai] [--embeddings-model <name>] [--openai-emb-model <name>] [--enable-reranker/--disable-reranker] [--reranker-model <name>]` | Start capture/OCR pipeline; set embeddings provider/reranker. |
| `second-brain stop` | Send SIGTERM to the running service. |
| `second-brain status` | Inspect frame/text counts, database size, capture window range. |
| `second-brain health` | Quick checklist: process, OCR creds, database, disk headroom. |
| `second-brain query "term" [--app ...] [--from ...] [--to ...] [--rerank]` | Full-text search (FTS5 + bm25), optionally reranked with BAAI. |
| `second-brain query "term" --semantic [--rerank]` | Semantic search over embeddings (provider-configured), optionally reranked. |
| `second-brain timeline [--host 127.0.0.1] [--port 8000] [--no-open]` | Run FastAPI + serve Timeline UI with settings panel. |
| `second-brain ui` | Launch Streamlit UI (port 8501) |
| `second-brain convert-to-video` | Convert frames to H.264 video |
| `second-brain reset` | Delete all data and start fresh |
| `second-brain mcp-server` | Start MCP server to expose memory to AI assistants. |
| `second-brain docs search "library-name" [--save path.md]` | Fetch documentation via Context7. |
| `second-brain docs fetch "/library-id" [--topic "..."]` | Fetch docs by exact library ID. |
| `second-brain docs batch libraries.json --output-dir docs/` | Batch fetch multiple libraries. |
