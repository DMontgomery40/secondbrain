# Second Brain

Second Brain is a local-first, high-fidelity desktop memory system for macOS. It captures your screen at 1–2 fps, extracts rich text and context with GPT-5 vision OCR, indexes everything for instant recall, and ships with an elegant timeline UI for replaying past work sessions. All data (screenshots, metadata, embeddings, logs) stays on disk in a predictable directory so you maintain full control.

---

## Highlights

- **Continuous visual capture** – quartz-backed screenshots with app / window metadata and disk safeguards.
- **GPT-5 vision OCR** – structured text extraction, semantic context, and batching with automatic retry & rate limiting.
- **Search two ways** – trigram FTS5 for exact matches plus MiniLM-powered semantic search via Chroma.
- **Timeline UI** – React + Vite single-page app for filtering, scrolling, and previewing captured sessions.
- **Local API** – FastAPI server exposes `/api/frames`, `/api/apps`, and static `/frames/<path>` previews.
- **Operational tooling** – CLI commands for start/stop/status/health, timeline launch, and service packaging (launchd script).
- **Privacy-first** – no outbound calls beyond OpenAI; configurable retention windows and storage quotas.
- **Manual OCR toggle + Settings Panel** – switch between OpenAI and local DeepSeek OCR, and configure everything from the GUI (no JSON editing).

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                             Second Brain                            │
├─────────────────────────────────────────────────────────────────────┤
│ Capture Loop → GPT-5 OCR → SQLite + Chroma → CLI / API / Timeline UI │
│        │              │                │                │            │
│   screencapture   semantic blocks   full-text FTS   FastAPI server   │
│   Quartz metadata embeddings store  bm25 ranking    React timeline   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- macOS with screen-recording + accessibility permissions.
- Python 3.11+
- Node.js 20+ (for building the timeline UI)
- OpenAI API key with access to `gpt-5` vision.

### Setup

```bash
# 1. Clone
git clone <repo-url> second-brain
cd second-brain

# 2. Python environment
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 3. Timeline UI (optional but recommended)
cd web/timeline
npm install
npm run build
cd ../..

# 4. Configure API credentials
cp .env.example .env
echo "OPENAI_API_KEY=sk-..." >> .env
```

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
`second-brain start [--fps 1.5]` | Start capture/OCR pipeline in the foreground (writes PID file).
`second-brain stop` | Send SIGTERM to the running service.
`second-brain status` | Inspect frame/text counts, database size, capture window range.
`second-brain health` | Quick checklist: process, OpenAI creds, database, disk headroom.
`second-brain query "term" [--app com.apple.Safari] [--from YYYY-MM-DD] [--to YYYY-MM-DD]` | Full-text search (FTS5 + bm25).
`second-brain query "term" --semantic` | Semantic search over GPT indexed embeddings (Chroma + MiniLM).
`second-brain timeline [--host 127.0.0.1] [--port 8000] [--no-open]` | Run FastAPI + serve the timeline SPA (requires prior `npm run build`).
`second-brain mcp-server [--host 127.0.0.1] [--port 3000]` | Start the MCP server over HTTP with search and frame tools.

> Tip: Use `scripts/install.sh` to provision the virtualenv, install dependencies, build the package, and optionally register the launchd agent for auto-start on login.

---

## Timeline UI

- Location: `web/timeline` (Vite + React + Typescript)
- Build: `npm run build` → outputs to `web/timeline/dist/`
- Serve: `second-brain timeline` mounts the built assets at `/` and exposes APIs under `/api` plus screenshots under `/frames`.
- Features: application/date filters, horizontal scrubbable timeline by day, live screenshot preview, OCR text pane with block typing, responsive layout.
- Settings: a gear button in the sidebar opens a full Settings Panel to adjust capture, OCR (engine toggle: OpenAI vs DeepSeek), embeddings, storage, API, logging, and MCP. Changes persist to disk; engine changes restart the capture service automatically.

During development you can run `npm run dev` (proxying to the API at `localhost:8000`) instead of building.

---

## REST API

Endpoint | Description
---|---
`GET /api/frames?limit=200&app_bundle_id=com.apple.Safari&start=...&end=...` | List frames with metadata, ISO timestamps, and `screenshot_url`.
`GET /api/frames/{frame_id}` | Retrieve a single frame document.
`GET /api/frames/{frame_id}/text` | Retrieve OCR text blocks for a frame.
`GET /api/apps` | Top application usage stats (first/last seen + frame counts).
`/frames/<Y>/<M>/<D>/<filename>` | Raw screenshot assets (served statically).

All routes are local-only by default; CORS is wide open so the timeline SPA can hit the API.

### Settings API

Endpoint | Description
---|---
`GET /api/settings/ocr-engine` | Get current OCR engine (`openai` or `deepseek`).
`POST /api/settings/ocr-engine` | Set OCR engine. Body: `{ "engine": "openai" | "deepseek" }`. Restarts capture if needed.
`GET /api/settings/all` | Return all settings as nested JSON.
`POST /api/settings/update` | Update any subset of settings; persists to disk and restarts services when required.
`POST /api/settings/reset` | Reset a category or all. Body: `{ "category": "capture" | ... }` or empty to reset all.
`GET /api/settings/stats` | Lightweight system stats for the Settings Panel (db size, screenshots, RAM, DeepSeek health, frames today).
`POST /api/settings/maintenance/compact-db` | Vacuum the database.
`POST /api/settings/maintenance/clear-screenshots` | Clear old screenshots and related records. Body: `{ "retention_days": 90 }`.
`GET /api/settings/logs?file=capture.log` | Download a log file.

---

## Data & Configuration

```
~/Library/Application Support/second-brain/
├── frames/         # Screenshots + JSON metadata
├── database/       # SQLite (memory.db)
├── embeddings/     # Chroma persistent store (semantic search)
├── logs/           # capture.log, ocr.log, query.log (future)
└── config/         # settings.json (auto-created copy of DEFAULT_CONFIG)
```

Configuration is persisted to `~/Library/Application Support/second-brain/config/settings.json` on macOS. You can manage everything from the Timeline UI Settings Panel; manual edits are still supported. Core keys include:

```json
{
  "capture": {
    "fps": 1,
    "max_disk_usage_gb": 100,
    "min_free_space_gb": 10,
    "buffer_enabled": false,
    "buffer_duration": 30
  },
  "ocr": {
    "engine": "openai",            // or "deepseek"
    "model": "gpt-5",
    "rate_limit_rpm": 50,
    "deepseek_docker": true,
    "deepseek_docker_url": "http://localhost:8001",
    "batch_size": 5
  },
  "embeddings": {
    "enabled": true,
    "model": "sentence-transformers/all-MiniLM-L6-v2"
  },
  "api": {
    "host": "127.0.0.1",
    "port": 8000,
    "cors_enabled": true
  },
  "logging": {
    "level": "INFO",
    "file": "capture.log",
    "max_size_mb": 100
  },
  "mcp": {
    "enabled": false,
    "port": 3000,
    "transport": "streamable_http"
  }
}
```

Adjust FPS to manage API costs, and tweak disk guardrails to suit your storage budget. The capture service keeps a rolling byte counter and will pause automatically if free space is scarce or the configured quota is exceeded.

---

## Development & Testing

```bash
pytest tests/test_capture.py tests/test_database.py
```

> The test suite uses `Config()` directly, so run it in an isolated environment (e.g., disposable macOS user or temp directories) to avoid mixing fixtures with your production capture data.

Formatting: the repo ships with `black`, `flake8`, and `mypy` in `requirements.txt` for consistent linting.

---

## Roadmap

- Launchd integration via `scripts/install.sh` (already scaffolded – completes daemon setup).
- Retention job for pruning old frames & embeddings.
- Session reconstruction: auto-stitch contiguous frames into video clips.
- Optional local LLM inference (llama.cpp) for offline semantic queries.
- DeepSeek Docker helper and health UI integration.

Contributions via pull requests are welcome. Please open an issue first if you plan large structural changes.
