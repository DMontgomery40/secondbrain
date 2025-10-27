# Integrating Second Brain with AGRO RAG Engine

This guide explains how to integrate Second Brain's visual memory with AGRO RAG engine using the Model Context Protocol (MCP).

## Overview

Second Brain now exposes its visual memory capabilities through MCP (Model Context Protocol), allowing AGRO and other AI tools to query screenshots, OCR text, and application context alongside code search.

**Benefits:**
- Query visual memory when investigating code issues
- Find when specific code or errors appeared on screen
- Correlate code changes with temporal context
- Augment code search with visual evidence

## Architecture

```
┌─────────────┐         MCP Tools          ┌───────────────┐
│    AGRO     │ ◄────────────────────────► │ Second Brain  │
│ RAG Engine  │   - search_memory          │  MCP Server   │
│             │   - get_frame_context      │               │
│             │   - get_timeline           │               │
│             │   - get_app_activity       │               │
│             │   - get_usage_stats        │               │
└─────────────┘                            └───────────────┘
      │                                            │
      │                                            │
      ▼                                            ▼
┌─────────────┐                          ┌───────────────┐
│   Qdrant    │                          │    SQLite     │
│ Code Vector │                          │ FTS5 + Frames │
│    Store    │                          │               │
└─────────────┘                          └───────────────┘

Combined Results: Code Context + Visual Memory
```

## Installation

### 1. Install MCP SDK in Second Brain

```bash
cd secondbrain
source venv/bin/activate
pip install "mcp[cli]>=0.9.0"
```

Or install from requirements.txt:

```bash
pip install -r requirements.txt
```

### 2. Verify Installation

```bash
second-brain --help
```

You should see the `mcp` command listed.

## Usage

### Starting the MCP Server

Second Brain supports two transport modes:

#### **stdio Transport** (for Claude Desktop)
```bash
second-brain mcp --transport stdio
```

#### **SSE Transport** (for HTTP clients like AGRO)
```bash
second-brain mcp --transport sse --host 127.0.0.1 --port 8100
```

The SSE server exposes:
- **SSE endpoint**: `http://127.0.0.1:8100/sse`
- **Messages endpoint**: `http://127.0.0.1:8100/messages` (POST)

## Available MCP Tools

### 1. `search_memory`

**Purpose**: Full-text search across OCR-extracted text from screenshots.

**Parameters:**
- `query` (required): Search query string (supports FTS5 syntax)
- `app_filter` (optional): Filter by app bundle ID (e.g., "com.microsoft.VSCode")
- `start_date` (optional): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format
- `limit` (optional): Max results (default: 10, max: 100)

**Returns:** `SearchResults` with matching frames and text blocks

**Example:**
```json
{
  "query": "authentication error",
  "app_filter": "com.apple.Terminal",
  "start_date": "2025-10-20",
  "limit": 5
}
```

**Response:**
```json
{
  "query": "authentication error",
  "total_results": 3,
  "results": [
    {
      "frame": {
        "frame_id": "abc-123",
        "timestamp": 1730000000,
        "iso_timestamp": "2025-10-26T14:53:20+00:00",
        "window_title": "Terminal",
        "app_name": "Terminal",
        "app_bundle_id": "com.apple.Terminal",
        "file_path": "2025/10/26/14-53-20-123.png"
      },
      "text_block": {
        "block_id": "def-456",
        "text": "Error: authentication failed for user@example.com",
        "confidence": 0.98,
        "block_type": "terminal"
      },
      "relevance_score": 1.234
    }
  ]
}
```

---

### 2. `get_frame_context`

**Purpose**: Get complete context for a specific frame including all OCR text.

**Parameters:**
- `frame_id` (required): Unique frame identifier

**Returns:** `FrameContext` with metadata, text blocks, and screenshot path

**Example:**
```json
{
  "frame_id": "abc-123"
}
```

---

### 3. `get_timeline`

**Purpose**: Get chronological sequence of frames within a time range.

**Parameters:**
- `start_date` (required): Start date in YYYY-MM-DD format
- `end_date` (required): End date in YYYY-MM-DD format
- `app_filter` (optional): Filter by app bundle ID
- `limit` (optional): Max frames (default: 50, max: 500)

**Returns:** `Timeline` with frames in chronological order

**Example:**
```json
{
  "start_date": "2025-10-26",
  "end_date": "2025-10-27",
  "app_filter": "com.microsoft.VSCode",
  "limit": 100
}
```

---

### 4. `get_app_activity`

**Purpose**: Get recent frames from a specific application.

**Parameters:**
- `app_bundle_id` (required): Application bundle identifier
- `limit` (optional): Max frames (default: 20, max: 200)

**Returns:** `AppActivity` with recent frames from the application

**Example:**
```json
{
  "app_bundle_id": "com.microsoft.VSCode",
  "limit": 50
}
```

---

### 5. `get_usage_stats`

**Purpose**: Get overall usage statistics and most-used applications.

**Parameters:** None

**Returns:** `UsageStats` with system-wide statistics

**Example:**
```json
{}
```

**Response:**
```json
{
  "total_frames": 5420,
  "total_text_blocks": 18765,
  "total_apps": 15,
  "database_size_mb": 1250.45,
  "oldest_frame": 1729000000,
  "newest_frame": 1730000000,
  "top_apps": [
    {
      "app_bundle_id": "com.microsoft.VSCode",
      "app_name": "Visual Studio Code",
      "first_seen": 1729000000,
      "last_seen": 1730000000,
      "frame_count": 2345
    }
  ]
}
```

## Configuring AGRO to Use Second Brain

### Option 1: MCP Client Configuration

If AGRO has MCP client support, add Second Brain to your MCP client config:

```json
{
  "mcpServers": {
    "secondbrain": {
      "command": "second-brain",
      "args": ["mcp", "--transport", "stdio"],
      "env": {}
    }
  }
}
```

### Option 2: HTTP Integration

Start Second Brain's MCP server with SSE transport:

```bash
second-brain mcp --transport sse --port 8100
```

Then configure AGRO to connect to `http://127.0.0.1:8100`.

### Option 3: Direct HTTP API (Fallback)

If MCP integration isn't feasible, Second Brain's existing REST API is available:

```bash
second-brain timeline --port 8000
```

Endpoints:
- `GET /api/frames` - List frames
- `GET /api/frames/{frame_id}` - Get specific frame
- `GET /api/frames/{frame_id}/text` - Get OCR text
- `GET /api/apps` - Get app usage stats

## Example Use Cases

### Use Case 1: Debug Error Investigation

**Query in AGRO:** "authentication failed error in login.py"

**Flow:**
1. AGRO searches code index: Finds `login.py` function
2. AGRO calls `search_memory("authentication failed")`
3. Returns: Screenshots showing error in terminal + IDE
4. Combined context: Code + visual evidence of error

### Use Case 2: Code History Reconstruction

**Query in AGRO:** "What was I working on yesterday afternoon?"

**Flow:**
1. AGRO calls `get_timeline("2025-10-26", "2025-10-26")`
2. Filters by IDE: `app_filter="com.microsoft.VSCode"`
3. Returns: Sequence of code screenshots from that time period
4. AGRO analyzes visual timeline + git history

### Use Case 3: Application-Specific Search

**Query in AGRO:** "Find all terminal commands I ran today"

**Flow:**
1. AGRO calls `get_app_activity("com.apple.Terminal", limit=100)`
2. Extracts OCR text from terminal frames
3. Returns: List of commands with timestamps

## Common App Bundle IDs

For filtering by application:

| Application | Bundle ID |
|-------------|-----------|
| Visual Studio Code | `com.microsoft.VSCode` |
| Terminal | `com.apple.Terminal` |
| Safari | `com.apple.Safari` |
| Chrome | `com.google.Chrome` |
| iTerm2 | `com.googlecode.iterm2` |
| PyCharm | `com.jetbrains.pycharm` |
| Cursor | `com.todesktop.230313mzl4w4u92` |
| Xcode | `com.apple.dt.Xcode` |

To discover bundle IDs, run:
```bash
second-brain status
```

Or query:
```bash
second-brain query "pattern" --app <bundle-id>
```

## Performance Considerations

**Search Performance:**
- FTS5 queries: <500ms for most queries
- Typical result set: 10-50 frames
- Database size: ~1-2 GB per day of capture

**Recommendations:**
- Use date filters to narrow search scope
- Use app filters when context is known
- Limit results to avoid overwhelming LLM context
- Cache frequent queries in AGRO

## Security & Privacy

**Local-Only by Default:**
- All data stored locally: `~/Library/Application Support/second-brain/`
- No cloud sync or external calls (except OpenAI OCR)
- MCP server binds to 127.0.0.1 by default

**Considerations:**
- Screenshot data contains sensitive information
- OCR text may include passwords, secrets, etc.
- Recommend encryption at rest (FileVault)
- Review AGRO's data handling policies

## Troubleshooting

### MCP Server Won't Start

```bash
# Check if MCP SDK is installed
pip show mcp

# Reinstall if needed
pip install --upgrade "mcp[cli]"
```

### No Search Results

```bash
# Check if capture service is running
second-brain status

# Start capture if not running
second-brain start

# Verify database has data
second-brain query "test"
```

### AGRO Can't Connect

```bash
# For SSE transport, verify server is running
curl http://127.0.0.1:8100/sse

# Check firewall settings
# Ensure port 8100 is not blocked
```

### OCR Quality Issues

- Adjust capture FPS: `second-brain start --fps 2`
- Check OpenAI API key: `second-brain health`
- Review OCR confidence scores in results

## Advanced Configuration

### Custom Config

Edit `~/.config/second-brain/settings.json`:

```json
{
  "capture": {
    "fps": 1,
    "max_disk_usage_gb": 100
  },
  "ocr": {
    "engine": "openai",
    "model": "gpt-5",
    "rate_limit_rpm": 50
  }
}
```

### Running as Background Service

```bash
# macOS launchd (auto-start on login)
./scripts/install.sh

# Manual background start
nohup second-brain start &
```

## Future Enhancements

**Planned Features:**
1. **Semantic Search**: Vector search over embeddings (Chroma integration)
2. **Unified Vector Store**: Push Second Brain embeddings to AGRO's Qdrant
3. **Session Reconstruction**: Auto-stitch frames into video clips
4. **Code Context Enrichment**: Link frames to git commits

## Support

**Issues:**
- Second Brain: https://github.com/DMontgomery40/secondbrain/issues
- AGRO: https://github.com/DMontgomery40/agro-rag-engine/issues

**Documentation:**
- MCP Specification: https://modelcontextprotocol.io
- Second Brain README: `/README.md`
- AGRO README: https://github.com/DMontgomery40/agro-rag-engine

---

## Quick Start Example

**1. Start Second Brain capture:**
```bash
second-brain start
```

**2. Start MCP server:**
```bash
second-brain mcp --transport sse --port 8100
```

**3. Test with curl:**
```bash
# Health check
curl http://127.0.0.1:8100/sse

# Example tool call (adjust based on MCP protocol)
curl -X POST http://127.0.0.1:8100/messages \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "search_memory", "arguments": {"query": "error", "limit": 5}}}'
```

**4. Integrate with AGRO** (see AGRO's MCP client documentation)

---

**Congratulations!** Second Brain and AGRO are now integrated. Query visual memory alongside code context for enhanced development insights.
