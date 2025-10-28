# Second Brain

Second Brain is a local-first, high-fidelity desktop memory system for macOS. It captures your screen at 1–2 fps, extracts rich text and context with dual OCR engines (Apple Vision or DeepSeek), indexes everything for instant recall, and ships with an elegant timeline UI with comprehensive settings panel. All data (screenshots, metadata, embeddings, logs) stays on disk in a predictable directory so you maintain full control.

---

## Highlights

- **Continuous visual capture** – quartz-backed screenshots with app / window metadata and disk safeguards.
- **Dual OCR engines** – Apple Vision (local, fast, free) or DeepSeek OCR (local, multimodal, 10-20x compression). Switch engines anytime via GUI or CLI.
- **Comprehensive settings panel** – Beautiful GUI for all 30+ configuration options with live system statistics. No more manual JSON editing!
- **Search two ways** – trigram FTS5 for exact matches plus MiniLM-powered semantic search via Chroma.
- **Timeline UI** – React + Vite SPA with filters, OCR engine toggle, complete settings management, and session replay.
- **MCP server** – Model Context Protocol server exposes your memory to AI assistants (Claude, ChatGPT, etc.) via 5 tools.
- **Local API** – FastAPI server with comprehensive endpoints for frames, apps, settings, and system stats.
- **Operational tooling** – CLI commands for start/stop/status/health, timeline launch, MCP server, and service packaging.
- **Privacy-first** – no outbound calls beyond chosen OCR provider; configurable retention windows and storage quotas.

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

**New in this version:**
- ✨ DeepSeek OCR integration (10-20x cost reduction, runs locally)
- ✨ Comprehensive settings panel (30+ configurable options)
- ✨ MCP server for AI assistant integration
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
- Screen Recording + Accessibility permissions

### Setup

```bash
# 1. Clone
git clone <repo-url> second-brain
cd second-brain

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
# Launch capture + processing pipeline
second-brain start

# Check status after a few minutes
second-brain status

# Explore the timeline (opens browser)
second-brain timeline --port 8000
```

Stop the capture service at any time with `second-brain stop`.

---

## CLI Reference

Command | Description
---|---
`second-brain start [--fps 1.5] [--ocr-engine openai\|deepseek] [--embeddings-provider sbert\|openai] [--embeddings-model <name>] [--openai-emb-model <name>] [--enable-reranker/--disable-reranker] [--reranker-model <name>]` | Start capture/OCR pipeline; set embeddings provider/reranker.
`second-brain stop` | Send SIGTERM to the running service.
`second-brain status` | Inspect frame/text counts, database size, capture window range.
`second-brain health` | Quick checklist: process, OCR creds, database, disk headroom.
`second-brain query "term" [--app ...] [--from ...] [--to ...] [--rerank]` | Full-text search (FTS5 + bm25), optionally reranked with BAAI.
`second-brain query "term" --semantic [--rerank]` | Semantic search over embeddings (provider-configured), optionally reranked.
`second-brain timeline [--host 127.0.0.1] [--port 8000] [--no-open]` | Run FastAPI + serve Timeline UI with settings panel.
`second-brain mcp-server` | Start MCP server to expose memory to AI assistants.

> Tip: Use `scripts/install.sh` to provision the virtualenv, install dependencies, build the package, and optionally register the launchd agent for auto-start on login.

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
- **4 tabbed categories:** Capture, OCR, Storage, Embeddings
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

```json
{
  "capture": {
    "fps": 1,
    "format": "png",
    "quality": 85,
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

## Development & Testing

```bash
pytest tests/test_capture.py tests/test_database.py
```

> The test suite uses `Config()` directly, so run it in an isolated environment (e.g., disposable macOS user or temp directories) to avoid mixing fixtures with your production capture data.

Formatting: the repo ships with `black`, `flake8`, and `mypy` in `requirements.txt` for consistent linting.

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
- ✅ DeepSeek OCR integration (10-20x cost reduction)
- ✅ Comprehensive settings panel (30+ options)
- ✅ MCP server for AI assistant integration
 
- ✅ Dual OCR engine support with GUI toggle

**Planned:**
- Launchd integration via `scripts/install.sh` (scaffolded, needs completion)
- Retention job for pruning old frames & embeddings
- Session reconstruction: auto-stitch contiguous frames into video clips
- Optional local LLM inference (llama.cpp) for offline semantic queries
- Hybrid mode with intelligent engine routing

Contributions via pull requests are welcome. Please open an issue first if you plan large structural changes.

---

## License & Credits

Built with Claude Code. Second Brain is open source software.
