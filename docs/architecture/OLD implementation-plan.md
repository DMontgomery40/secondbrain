# Implementation Plan - CLI MVP (4 Weeks)

## Week 1: Capture Loop + OCR Foundation

### Day 1-2: Project Setup
- [x] Create architecture documentation
- [ ] Initialize Python 3.11 virtual environment
- [ ] Set up project structure
- [ ] Create requirements.txt with core dependencies
- [ ] Initialize git repository with .gitignore
- [ ] Set up logging infrastructure

### Day 3-4: Capture Service
- [ ] Implement screenshot capture using `screencapture`
- [ ] Create frame storage directory structure
- [ ] Implement metadata extraction (window title, app bundle ID)
- [ ] Add timestamp and UUID generation
- [ ] Implement disk quota checking
- [ ] Create capture loop with 1-2 fps timing
- [ ] Add graceful shutdown handling

### Day 5-7: OCR Pipeline Foundation
- [ ] Set up OpenAI API client with retry logic
- [ ] Implement rate limiting for API calls
- [ ] Create OCR queue system with batch processing
- [ ] Design vision prompt for text extraction
- [ ] Implement text extraction with semantic context
- [ ] Add confidence scoring and error handling
- [ ] Implement text normalization (whitespace deduplication)
- [ ] Create block type detection from GPT response

**Deliverable**: Working capture service that saves frames + metadata, with basic OCR extraction

---

## Week 2: Storage & Indexing

### Day 8-9: Database Schema
- [ ] Create SQLite database initialization script
- [ ] Implement `frames` table with indexes
- [ ] Implement `text_blocks` table with foreign keys
- [ ] Implement `windows` table for app tracking
- [ ] Set up FTS5 virtual table with trigram tokenization
- [ ] Create database migration system
- [ ] Add database connection pooling

### Day 10-11: Data Persistence Layer
- [ ] Create database abstraction layer (DAO pattern)
- [ ] Implement frame insertion with transaction handling
- [ ] Implement text block batch insertion
- [ ] Add window tracking logic (first_seen/last_seen)
- [ ] Create FTS5 index update triggers
- [ ] Implement data validation and error handling

### Day 12-14: Vector Embeddings
- [ ] Set up sentence-transformers (MiniLM-L6-v2)
- [ ] Implement embedding generation for text blocks
- [ ] Set up Chroma vector store
- [ ] Create embedding batch processing
- [ ] Implement vector index updates
- [ ] Add embedding cache to avoid recomputation
- [ ] Test semantic similarity search

**Deliverable**: Complete storage pipeline with full-text and semantic search capabilities

---

## Week 3: Query Interface (CLI)

### Day 15-16: CLI Framework
- [ ] Set up Click or Typer for CLI framework
- [ ] Implement `second-brain` entry point
- [ ] Create command structure (query, status, start, stop)
- [ ] Add argument parsing and validation
- [ ] Implement colorized output (rich or colorama)
- [ ] Add progress indicators for long operations

### Day 17-18: Search Implementation
- [ ] Implement FTS5 text search with ranking
- [ ] Add filter support (app, date range)
- [ ] Implement semantic search via vector similarity
- [ ] Create result ranking algorithm (relevance + recency)
- [ ] Add result formatting with context snippets
- [ ] Implement pagination for large result sets

### Day 19-20: Service Management
- [ ] Implement `second-brain start` command
- [ ] Implement `second-brain stop` command
- [ ] Implement `second-brain status` command
- [ ] Add health check (FPS, queue depth, disk usage)
- [ ] Create process management (PID file handling)
- [ ] Add service restart capability

### Day 21: Shell Integration
- [ ] Research shell history integration (`fc -R`)
- [ ] Implement command-to-frame correlation
- [ ] Add terminal output detection heuristics
- [ ] Create shell history search filter

**Deliverable**: Fully functional CLI with search, filters, and service management

---

## Week 4: Reliability, Testing & Packaging

### Day 22-23: Reliability & Error Handling
- [ ] Implement crash recovery for capture service
- [ ] Add automatic restart on failure
- [ ] Implement queue overflow handling
- [ ] Add disk space monitoring with auto-pause
- [ ] Create comprehensive error logging
- [ ] Implement graceful degradation (OCR failures)
- [ ] Add data corruption detection and recovery

### Day 24-25: launchd Integration
- [ ] Create launchd plist file
- [ ] Implement installation script
- [ ] Add uninstallation script
- [ ] Configure auto-start on login
- [ ] Set up log rotation
- [ ] Test service persistence across reboots

### Day 26-27: Testing
- [ ] Create sample frame dataset for testing
- [ ] Write unit tests for capture service
- [ ] Write unit tests for OCR pipeline
- [ ] Write unit tests for storage layer
- [ ] Write integration tests for full pipeline
- [ ] Test CLI commands end-to-end
- [ ] Performance testing (capture latency, query speed)
- [ ] Test disk quota enforcement

### Day 28: Documentation & Polish
- [ ] Write user installation guide
- [ ] Create CLI usage documentation
- [ ] Document configuration options
- [ ] Add troubleshooting guide
- [ ] Create sample queries and use cases
- [ ] Polish error messages and help text
- [ ] Final code cleanup and refactoring

**Deliverable**: Production-ready CLI MVP with tests, documentation, and launchd integration

---

## Success Criteria

### Functional Requirements
- ✅ Captures 1-2 fps screenshots with metadata
- ✅ Extracts text via OCR with >80% accuracy
- ✅ Stores data in SQLite with FTS5 indexing
- ✅ Supports full-text search with filters
- ✅ Supports semantic search via embeddings
- ✅ CLI returns results in <500ms for text search
- ✅ Service runs reliably as launchd agent
- ✅ Respects disk quotas and auto-pauses

### Non-Functional Requirements
- ✅ Uses <2GB disk per day
- ✅ CPU usage <5% during capture
- ✅ Memory usage <500MB
- ✅ Handles crashes gracefully
- ✅ Comprehensive logging
- ✅ >80% test coverage

---

## Risk Mitigation

### Technical Risks
1. **API costs**: Monitor usage, implement rate limiting, and batch processing
2. **API reliability**: Implement retry logic with exponential backoff
3. **Performance issues**: Implement async operations and queue management
4. **Disk space**: Aggressive compression and retention policies
5. **OCR accuracy**: Tune prompts and implement confidence thresholds

### Timeline Risks
1. **API integration delays**: Test OpenAI API early, have fallback plan
2. **Rate limiting issues**: Implement proper queuing and backoff strategies
3. **Vector search complexity**: Start with FTS5 only, add embeddings later if needed
4. **launchd issues**: Test early and often on clean macOS install

---

## Post-MVP Enhancements (Future)
- [ ] Browser extension for URL capture
- [ ] Git integration for repo/branch context
- [ ] ActivityWatch integration
- [ ] Obsidian plugin for note linking
- [ ] Local LLM integration for advanced queries
- [ ] Encryption at rest (SQLCipher)
- [ ] Multi-monitor support
- [ ] Video clip generation for playback
- [ ] Export to Markdown bundles
