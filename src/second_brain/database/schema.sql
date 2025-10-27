-- Second Brain Database Schema
-- SQLite database for storing frame metadata and text blocks

-- Core frames table
CREATE TABLE IF NOT EXISTS frames (
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

-- Text blocks extracted from frames
CREATE TABLE IF NOT EXISTS text_blocks (
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
    ocr_engine TEXT DEFAULT 'openai',
    compression_ratio REAL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (frame_id) REFERENCES frames(frame_id) ON DELETE CASCADE
);

-- Window tracking for app usage patterns
CREATE TABLE IF NOT EXISTS windows (
    window_id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_bundle_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    UNIQUE(app_bundle_id, app_name)
);

-- Full-text search virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS text_blocks_fts USING fts5(
    block_id UNINDEXED,
    frame_id UNINDEXED,
    text,
    normalized_text,
    content=text_blocks,
    content_rowid=rowid,
    tokenize='trigram'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS text_blocks_ai AFTER INSERT ON text_blocks BEGIN
    INSERT INTO text_blocks_fts(rowid, block_id, frame_id, text, normalized_text)
    VALUES (new.rowid, new.block_id, new.frame_id, new.text, new.normalized_text);
END;

CREATE TRIGGER IF NOT EXISTS text_blocks_ad AFTER DELETE ON text_blocks BEGIN
    DELETE FROM text_blocks_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS text_blocks_au AFTER UPDATE ON text_blocks BEGIN
    DELETE FROM text_blocks_fts WHERE rowid = old.rowid;
    INSERT INTO text_blocks_fts(rowid, block_id, frame_id, text, normalized_text)
    VALUES (new.rowid, new.block_id, new.frame_id, new.text, new.normalized_text);
END;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_frames_timestamp ON frames(timestamp);
CREATE INDEX IF NOT EXISTS idx_frames_app ON frames(app_bundle_id);
CREATE INDEX IF NOT EXISTS idx_frames_created ON frames(created_at);
CREATE INDEX IF NOT EXISTS idx_text_blocks_frame ON text_blocks(frame_id);
CREATE INDEX IF NOT EXISTS idx_text_blocks_confidence ON text_blocks(confidence);
CREATE INDEX IF NOT EXISTS idx_windows_app ON windows(app_bundle_id);
CREATE INDEX IF NOT EXISTS idx_windows_last_seen ON windows(last_seen);

-- Metadata table for schema versioning
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO metadata (key, value) VALUES ('schema_version', '1');
INSERT OR IGNORE INTO metadata (key, value) VALUES ('created_at', strftime('%s', 'now'));
