# Second Brain

Second Brain is a local-first, high-fidelity desktop memory system for macOS. It captures your screen at 1–2 fps, extracts rich text and context with GPT-5 vision OCR, indexes everything for instant recall, and ships with an elegant timeline UI for replaying past work sessions. All data (screenshots, metadata, embeddings, logs) stays on disk in a predictable directory so you maintain full control.

---

## Highlights

- **Continuous visual capture** – quartz-backed screenshots with app / window metadata and disk safeguards.
- **GPT-5 vision OCR** – structured text extraction, semantic context, and batching with automatic retry & rate limiting.
- **Search two ways** – trigram FTS5 for exact matches plus MiniLM-powered semantic search via Chroma.
- **MCP Integration** – Model Context Protocol server exposes visual memory to AI tools (AGRO RAG engine, Claude Desktop, etc.).
- **Timeline UI** – React + Vite single-page app for filtering, scrolling, and previewing captured sessions.
- **Local API** – FastAPI server exposes `/api/frames`, `/api/apps`, and static `/frames/<path>` previews.
- **Operational tooling** – CLI commands for start/stop/status/health, timeline launch, MCP server, and service packaging (launchd script).
- **Privacy-first** – no outbound calls beyond OpenAI; configurable retention windows and storage quotas.

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
`second-brain mcp [--transport stdio|sse] [--host 127.0.0.1] [--port 8100]` | Start MCP server to expose visual memory to AI tools (e.g., AGRO RAG engine).

> Tip: Use `scripts/install.sh` to provision the virtualenv, install dependencies, build the package, and optionally register the launchd agent for auto-start on login.

---

## Timeline UI

- Location: `web/timeline` (Vite + React + Typescript)
- Build: `npm run build` → outputs to `web/timeline/dist/`
- Serve: `second-brain timeline` mounts the built assets at `/` and exposes APIs under `/api` plus screenshots under `/frames`.
- Features: application/date filters, horizontal scrubbable timeline by day, live screenshot preview, OCR text pane with block typing, responsive layout.

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

Key config knobs (editable via `~/.config/second-brain/settings.json`):

```json
{
  "capture": {
    "fps": 1,
    "max_disk_usage_gb": 100,
    "min_free_space_gb": 10
  },
  "ocr": {
    "engine": "openai",
    "model": "gpt-5",
    "rate_limit_rpm": 50
  },
  "embeddings": {
    "enabled": true,
    "model": "sentence-transformers/all-MiniLM-L6-v2"
  }
}
```

Adjust FPS to manage API costs, and tweak disk guardrails to suit your storage budget. The capture service keeps a rolling byte counter and will pause automatically if free space is scarce or the configured quota is exceeded.

---

## MCP Integration

Second Brain exposes its visual memory through the **Model Context Protocol (MCP)**, enabling AI tools to query screenshots and OCR text alongside other data sources.

### Starting the MCP Server

```bash
# For Claude Desktop (stdio transport)
second-brain mcp --transport stdio

# For HTTP clients like AGRO (SSE transport)
second-brain mcp --transport sse --port 8100
```

### Available Tools

- **search_memory** – Full-text search across OCR text with optional app/date filters
- **get_frame_context** – Get complete details for a specific frame
- **get_timeline** – Retrieve frames within a date range
- **get_app_activity** – Get recent frames from a specific application
- **get_usage_stats** – Overall statistics and top applications

### Integration Examples

**With AGRO RAG Engine:**
See [`docs/AGRO_INTEGRATION.md`](docs/AGRO_INTEGRATION.md) for detailed setup and usage examples.

**With Claude Desktop:**
Add to your Claude Desktop MCP config:
```json
{
  "mcpServers": {
    "secondbrain": {
      "command": "second-brain",
      "args": ["mcp", "--transport", "stdio"]
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

## Roadmap

- Launchd integration via `scripts/install.sh` (already scaffolded – completes daemon setup).
- Retention job for pruning old frames & embeddings.
- Session reconstruction: auto-stitch contiguous frames into video clips.
- Optional local LLM inference (llama.cpp) for offline semantic queries.

Contributions via pull requests are welcome. Please open an issue first if you plan large structural changes.
