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
│ Capture → [Apple Vision OR DeepSeek] → SQLite + Chroma → UI/API/MCP      │
│    │              │            │              │              │            │
│ Quartz      Apple Vision   DeepSeek     full-text FTS   FastAPI          │
│ metadata    (local/fast)   (free)       bm25 ranking    React timeline   │
│ 1-2 fps     semantic       batch OCR    embeddings      Settings panel   │
│             context        10x cheaper  Chroma store    MCP server       │
└──────────────────────────────────────────────────────────────────────────┘
```

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
- Apple Silicon M1+ or Intel Mac
- 8 GB RAM
- 50 GB free disk space
- macOS 11.0+ with screen recording permissions

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
- Node.js 20+ (for Timeline UI)
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

# 4. Configure API credentials (optional)
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
| `second-brain start [--fps 1.5] [--ocr-engine openai\|deepseek] [--embeddings-provider sbert\|openai] [--embeddings-model <name>] [--openai-emb-model <name>] [--enable-reranker/--disable-reranker] [--reranker-model <name>]` | Start capture/OCR pipeline; set embeddings provider/reranker. |
| `second-brain stop` | Send SIGTERM to the running service. |
| `second-brain status` | Inspect frame/text counts, database size, capture window range. |
| `second-brain health` | Quick checklist: process, OCR creds, database, disk headroom. |
| `second-brain query "term" [--app ...] [--from ...] [--to ...] [--rerank]` | Full-text search (FTS5 + bm25), optionally reranked with BAAI. |
| `second-brain query "term" --semantic [--rerank]` | Semantic search over embeddings (provider-configured), optionally reranked. |
| `second-brain ui` | Launch Streamlit UI (port 8501) |
| `second-brain timeline [--host 127.0.0.1] [--port 8000] [--no-open]` | Run FastAPI + serve Timeline UI with settings panel. |
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

<<<<<<< HEAD
## Timeline UI

- **Location:** `web/timeline` (Vite + React + TypeScript)
- **Build:** `npm run build` → outputs to `web/timeline/dist/`
- **Serve:** `second-brain timeline` mounts built assets at `/` with APIs under `/api`

### Features

**Core Timeline:**
- Application/date filters
- Horizontal scrubbable timeline grouped by day
- Live screenshot preview
- OCR text pane with block-level viewing
- Responsive layout

**OCR Engine Toggle:**
- Quick switch between OpenAI and DeepSeek
- Cost warnings for expensive options
- Inline in sidebar for easy access

**Comprehensive Settings Panel (⚙️):**
- **5 tabbed categories:** Capture, OCR, Storage, Embeddings, Context7
- **30+ configurable options:** FPS, image quality, disk limits, OCR models, rate limits, retention, etc.
  - **Live system statistics:** Database size, screenshot count, RAM usage, disk space
- **Save/Reset functionality:** Per-category or global reset to defaults
- **No manual JSON editing required!**

During development run `npm run dev` (proxying to API at `localhost:8000`) instead of building.

---

## REST API

### Frames & Data

Endpoint | Description
---|---
`GET /api/frames?limit=200&app_bundle_id=...&start=...&end=...` | List frames with metadata, ISO timestamps, and `screenshot_url`.
`GET /api/frames/{frame_id}` | Retrieve a single frame document.
`GET /api/frames/{frame_id}/text` | Retrieve OCR text blocks for a frame.
`GET /api/apps` | Top application usage stats (first/last seen + frame counts).
`/frames/<Y>/<M>/<D>/<filename>` | Raw screenshot assets (served statically).

### Settings & Configuration

Endpoint | Description
---|---
`GET /api/settings/all` | Get all settings as nested JSON + computed paths.
`POST /api/settings/update` | Update multiple settings at once (body: nested dict).
`POST /api/settings/reset?category=...` | Reset category or all settings to defaults.
`GET /api/settings/ocr-engine` | Get current OCR engine setting.
`POST /api/settings/ocr-engine?engine=...` | Switch OCR engine (openai/deepseek).
`GET /api/settings/stats` | System statistics (DB size, screenshots, RAM, disk, DeepSeek health).

All routes are local-only by default; CORS is wide open so the Timeline SPA can hit the API.

---

## Data & Configuration

```
~/Library/Application Support/second-brain/
├── frames/         # Screenshots + JSON metadata
├── database/       # SQLite (memory.db)
├── embeddings/     # Chroma persistent store (semantic search)
├── logs/           # capture.log, ocr.log, query.log
└── config/         # settings.json (all configuration)
```

### Configuration Options

All settings are now manageable via the **Timeline UI Settings Panel (⚙️)** or by editing `settings.json` directly:
=======
## Data Storage

```
~/Library/Application Support/second-brain/
├── frames/              # Screenshots (PNG/WebP)
│   └── YYYY/MM/DD/
│       ├── HH-MM-SS-mmm.png
│       └── HH-MM-SS-mmm.json
├── videos/              # H.264 compressed videos
│   └── YYYY/MM/DD/
│       └── full_day.mp4
├── database/
│   ├── memory.db        # SQLite database
│   ├── memory.db-wal    # WAL file
│   └── memory.db-shm    # Shared memory
└── embeddings/          # Chroma vector store
    └── chroma/
```

---

## Configuration

Edit `~/.config/second-brain/settings.json` or use environment variables:
>>>>>>> origin/main

```json
{
  "capture": {
    "fps": 1.0,
    "format": "webp",
    "quality": 85,
    "enable_frame_diff": true,
    "similarity_threshold": 0.95,
    "enable_adaptive_fps": true,
    "idle_fps": 0.2,
    "idle_threshold_seconds": 30.0,
    "max_disk_usage_gb": 100,
    "min_free_space_gb": 10
  },
  "ocr": {
    "engine": "openai",           // or "deepseek"
    "model": "gpt-5",
    "rate_limit_rpm": 50,
    "batch_size": 5,
    "deepseek_docker_url": "http://localhost:8001",
    "deepseek_mode": "optimal"    // tiny|small|base|large|optimal
  },
  "storage": {
    "retention_days": 90,
    "compression": true
  },
  "embeddings": {
    "enabled": true,
    "model": "sentence-transformers/all-MiniLM-L6-v2"
  },
  "context7": {
    "enabled": true,
    "api_key": "ctx7sk-..."
  },
  "summarization": {
    "hourly_enabled": true,
    "daily_enabled": true,
    "min_frames": 10
  },
  "video": {
    "segment_duration_minutes": 5,
    "crf": 23,
    "preset": "medium",
    "delete_frames_after_conversion": false
  }
}
```

**Smart Capture:**
- Adaptive FPS: 1.0 fps (active) → 0.2 fps (idle >30s) based on keyboard/mouse activity
- Frame diffing: Perceptual hashing skips duplicates (95% similarity threshold)
- Disk monitoring: Auto-pauses if free space is scarce or quota exceeded

**100% Local by Default:**
- Apple Vision OCR (on-device, free, fast) or DeepSeek OCR (MLX, cutting-edge multimodal)
- No cloud dependencies required

---

## MCP Server

Second Brain includes a Model Context Protocol (MCP) server that exposes your visual memory to AI assistants.

### Available Tools

Tool | Description
---|---
`search_memory` | Search your screen memory (full-text or semantic)
`get_screenshot` | Retrieve screenshot and metadata for a specific frame
`get_frames_by_time` | Get frames within a time range
`get_app_activity` | Get application usage statistics
`analyze_activity` | Analyze user activity patterns over time

### Usage

```bash
# Start the MCP server
second-brain mcp-server

# Configure in Claude Desktop (or other MCP-compatible AI)
# Add to ~/.config/claude/config.json:
{
  "mcpServers": {
    "secondbrain": {
      "command": "second-brain",
      "args": ["mcp-server"]
    }
  }
}
```

---

## Architecture

### Processing Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                      Second Brain                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Capture → OCR → Database → Embeddings → Summaries          │
│     │        │        │          │            │              │
│  Smart   Apple   SQLite    Chroma      GPT-5       │
│  Frame   Vision   WAL      MiniLM                            │
│  Diff    (local)  Compress                                   │
│                                                               │
│  ↓                                                            │
│  Streamlit UI ← Query API ← Search (FTS5 + Semantic)        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

1. **Capture Service**: Screenshots with smart frame diffing and adaptive FPS
2. **OCR Service**: Apple Vision framework for local text extraction
3. **Database**: SQLite with WAL mode, compression, and FTS5 search
4. **Embeddings**: Chroma vector store for semantic search
5. **Summarization**: GPT-5 for automatic activity summaries
6. **Video Converter**: ffmpeg for H.264 batch compression
7. **UI**: Streamlit for daily review and timeline browsing

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

**Completed:**
- ✅ Local OCR (Apple Vision)
- ✅ Smart frame capture
- ✅ Adaptive FPS
- ✅ H.264 video compression
- ✅ AI summarization
- ✅ Streamlit UI
- ✅ DeepSeek OCR integration (10-20x cost reduction)
- ✅ Comprehensive settings panel (30+ options)
- ✅ MCP server for AI assistant integration
- ✅ Context7 integration for documentation
- ✅ Dual OCR engine support with GUI toggle

**Planned:**
- [ ] Session reconstruction (stitch frames into video clips)
- [ ] Retention policies (auto-cleanup old data)
- [ ] Cloud sync (optional)
- [ ] Launchd integration via `scripts/install.sh` (scaffolded, needs completion)
- [ ] Retention job for pruning old frames & embeddings
- [ ] Optional local LLM inference (llama.cpp) for offline semantic queries
- [ ] Hybrid mode with intelligent engine routing

Contributions via pull requests are welcome. Please open an issue first if you plan large structural changes.

---

## License & Credits

Built with Claude Code. Second Brain is open source software.
