# Architecture Overview - Second Brain CLI MVP

## System Design

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     Second Brain CLI                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Capture    │───▶│     OCR      │───▶│   Storage    │  │
│  │   Service    │    │   Pipeline   │    │   + Index    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │          │
│         │                    │                    │          │
│         ▼                    ▼                    ▼          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Query Interface (CLI)                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Capture Service
**Purpose**: Continuously capture screenshots and window metadata

**Technology**:
- macOS `screencapture` command or Quartz Display Services
- Accessibility API for window metadata
- Python 3.11 with asyncio for async capture loop

**Output**:
- PNG frames: `~/Library/Application Support/second-brain/frames/YYYY/MM/DD/HH-MM-SS-mmm.png`
- Metadata JSON: `~/Library/Application Support/second-brain/frames/YYYY/MM/DD/HH-MM-SS-mmm.json`

**Metadata Schema**:
```json
{
  "timestamp": "2025-10-26T17:24:36.123Z",
  "frame_id": "uuid-v4",
  "window_title": "Visual Studio Code",
  "app_bundle_id": "com.microsoft.VSCode",
  "app_name": "Visual Studio Code",
  "screen_resolution": "1920x1080",
  "file_path": "frames/2025/10/26/17-24-36-123.png",
  "file_size_bytes": 1234567
}
```

### 2. OCR Pipeline
**Purpose**: Extract text from captured frames using OpenAI Vision API

**Technology**:
- OpenAI GPT-5 Vision API
- Batch processing with queue management
- Automatic retry logic with exponential backoff
- Rate limiting to respect API quotas

**Output**:
- Extracted text with structured analysis
- Context understanding (code vs prose, UI elements)
- Semantic descriptions of visual content
- Optional: Bounding box estimation via prompt engineering

**Text Block Schema**:
```json
{
  "frame_id": "uuid-v4",
  "block_id": "uuid-v4",
  "text": "extracted text content",
  "normalized_text": "deduplicated whitespace version",
  "confidence": 0.95,
  "block_type": "paragraph|heading|code|terminal|ui_element",
  "semantic_context": "description of what's happening in the frame",
  "bbox": {"x": 100, "y": 200, "width": 300, "height": 50}
}
```

### 3. Storage & Indexing
**Purpose**: Persist and index data for fast retrieval

**Technology**:
- SQLite with FTS5 for full-text search
- Chroma or FAISS for vector embeddings
- sentence-transformers (MiniLM or bge-small)

**Database Schema**:
```sql
-- Core tables
CREATE TABLE frames (
    frame_id TEXT PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    window_title TEXT,
    app_bundle_id TEXT,
    app_name TEXT,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    screen_resolution TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE text_blocks (
    block_id TEXT PRIMARY KEY,
    frame_id TEXT NOT NULL,
    text TEXT NOT NULL,
    normalized_text TEXT,
    confidence REAL,
    bbox_x INTEGER,
    bbox_y INTEGER,
    bbox_width INTEGER,
    bbox_height INTEGER,
    block_type TEXT,
    FOREIGN KEY (frame_id) REFERENCES frames(frame_id)
);

CREATE TABLE windows (
    window_id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_bundle_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL
);

-- Full-text search
CREATE VIRTUAL TABLE text_blocks_fts USING fts5(
    block_id UNINDEXED,
    frame_id UNINDEXED,
    text,
    normalized_text,
    content=text_blocks,
    content_rowid=rowid,
    tokenize='trigram'
);

-- Indexes
CREATE INDEX idx_frames_timestamp ON frames(timestamp);
CREATE INDEX idx_frames_app ON frames(app_bundle_id);
CREATE INDEX idx_text_blocks_frame ON text_blocks(frame_id);
```

### 4. Query Interface (CLI)
**Purpose**: Search and retrieve captured memory

**Commands**:
```bash
# Basic search
second-brain query "search term"

# Filtered search
second-brain query "search term" --app "VSCode" --date "2025-10-26"

# Date range
second-brain query "search term" --from "2025-10-20" --to "2025-10-26"

# Semantic search
second-brain query "search term" --semantic

# Status and health
second-brain status
second-brain health

# Service control
second-brain start
second-brain stop
second-brain restart
```

## Data Flow

1. **Capture Loop** (1-2 fps)
   - Take screenshot → Save PNG
   - Query Accessibility API → Save metadata JSON
   - Add to OCR queue

2. **OCR Processing** (async worker)
   - Read frame from queue
   - Run OCR extraction
   - Parse and normalize text
   - Store in database
   - Generate embeddings
   - Update vector index

3. **Query Execution**
   - Parse query and filters
   - Execute FTS5 search OR vector similarity search
   - Rank results by relevance + recency
   - Return matches with context

## Storage Locations

```
~/Library/Application Support/second-brain/
├── frames/                    # Raw screenshot storage
│   └── YYYY/MM/DD/
│       ├── HH-MM-SS-mmm.png
│       └── HH-MM-SS-mmm.json
├── database/
│   └── memory.db             # SQLite database
├── embeddings/
│   └── chroma/               # Vector store
├── logs/
│   ├── capture.log
│   ├── ocr.log
│   └── query.log
└── config/
    └── settings.json
```

## Configuration

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
    "engine": "openai",
    "model": "gpt-5",
    "api_key_env": "OPENAI_API_KEY",
    "batch_size": 5,
    "max_retries": 3,
    "rate_limit_rpm": 50,
    "include_semantic_context": true
  },
  "storage": {
    "retention_days": 90,
    "compression": true
  },
  "embeddings": {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "dimension": 384
  }
}
```

## Performance Targets

- Capture latency: < 100ms per frame
- OCR processing: < 3s per frame (API call + processing)
- Query response: < 500ms for text search
- Query response: < 1s for semantic search
- Disk usage: ~1-2 GB per day (with compression)
- API cost: ~$0.01-0.05 per day (depending on capture rate)

## Privacy & Security

- All data stored locally
- No network calls (except for optional LLM API)
- Configurable app exclusions
- Automatic cleanup of old data
- Optional encryption at rest (future)
