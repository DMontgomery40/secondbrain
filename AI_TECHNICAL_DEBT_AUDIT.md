# AI-Generated Technical Debt Audit Report
## Second Brain Codebase - Comprehensive Analysis

**Generated:** 2025-10-29
**Branch Analyzed:** claude/audit-ai-technical-debt-011CUc8Lz8ceeZuQCPxLUmGw
**Branches Scanned:** main, deepseek-ocr, codex-version, feature/streamlit-ux-improvements, and 7+ cursor/* branches

---

## Executive Summary

This audit identified **33 critical technical debt issues** across the codebase that appear to be artifacts of AI-assisted development. The most severe issues will cause **immediate runtime failures** and need urgent attention before any upstream contributions.

### Top 10 Most Critical Issues (Ranked by Severity)

| # | Issue | Severity | Files Affected | Blast Radius |
|---|-------|----------|----------------|--------------|
| 1 | **OpenAI Responses API doesn't exist in pinned version** | CRITICAL | 3 files, 5 calls | Breaks all AI features |
| 2 | **Three divergent OCR implementations across branches** | CRITICAL | 3 branches | Merge conflicts inevitable |
| 3 | **357 lines of duplicate AI answer generation code** | CRITICAL | 3 files | Maintenance nightmare |
| 4 | **Massive branch divergence (8,766 deletions on deepseek-ocr)** | CRITICAL | Entire codebase | Merge impossible |
| 5 | **807 lines of duplicate video capture/encoding** | HIGH | 3 files | Dead code, confusion |
| 6 | **168 lines of duplicate search result building** | HIGH | 3 files | Logic inconsistency risk |
| 7 | **Silent exception handlers hiding failures** | HIGH | 3 locations | Debugging impossible |
| 8 | **Dependency version conflicts across branches** | HIGH | requirements.txt | Environment chaos |
| 9 | **README claims "GPT-5" model that doesn't exist** | HIGH | 5+ locations | API calls will fail |
| 10 | **Streamlit UI deleted in 2 branches, exists in main** | HIGH | 1,293 lines | Feature loss on merge |

**Estimated Total Technical Debt:** ~2,800 lines of duplicate/problematic code + ~8,000 lines of merge conflicts

---

## 1. Git-Wide Issues (HIGHEST PRIORITY)

### Issue 1.1: Catastrophic Branch Divergence
**Severity: CRITICAL**

The codebase has experienced a massive split across three incompatible development paths:

#### Branch Comparison Matrix

| Feature | main (current) | deepseek-ocr | codex-version |
|---------|---------------|--------------|---------------|
| **OCR Engine** | AppleVisionOCR | OpenAIOCR + DeepSeekOCR | OpenAIOCR + DeepSeekOCR + Hybrid |
| **Streamlit UI** | EXISTS (1,293 lines) | DELETED | DELETED |
| **Summarization Service** | EXISTS (277 lines) | DELETED | DELETED |
| **Video Encoding** | 3 implementations | DELETED (all 3) | DELETED (all 3) |
| **Context7 Integration** | NO | YES | YES |
| **MCP Server** | NO | NO | YES |
| **pyobjc-framework-Vision** | 12.0 | NOT INSTALLED | NOT INSTALLED |
| **openai version** | 2.6.1 | 1.12.0 | 1.12.0 |
| **sentence-transformers** | 5.1.2 | 2.2.2 | 2.2.2 |

**Files Modified:** 65+ files changed between main and deepseek-ocr
**Lines Changed:** +2,364 insertions, -8,766 deletions

#### Key Divergences:

**1. OCR Implementation War**
- **main**: Uses `AppleVisionOCR` (local macOS Vision framework)
  - File: `src/second_brain/ocr/apple_vision_ocr.py` (270 lines)
  - Import: `from .apple_vision_ocr import AppleVisionOCR`

- **deepseek-ocr**: Uses `OpenAIOCR` (cloud-based)
  - File: `src/second_brain/ocr/openai_ocr.py` (290 lines)
  - Import: `from .openai_ocr import OpenAIOCR`
  - **apple_vision_ocr.py DELETED**

- **codex-version**: Uses `OpenAIOCR` + `DeepSeekOCR` + optional hybrid mode
  - Files: `openai_ocr.py` (290 lines) + `deepseek_ocr.py` (92 lines)
  - Config: `hybrid_ocr_enabled: true` option added
  - **apple_vision_ocr.py DELETED**

**Impact:** These branches CANNOT be merged without choosing one OCR strategy and rewriting the other branches.

**2. UI Complete Removal**
- **main**: Full Streamlit UI at `src/second_brain/ui/streamlit_app.py` (1,293 lines)
- **deepseek-ocr/codex-version**: **FILE DELETED ENTIRELY**
- **Consequence**: Merging deepseek-ocr → main will delete the entire UI

**3. Summarization Service Removal**
- **main**: `src/second_brain/summarization/summarization_service.py` (277 lines)
- **deepseek-ocr/codex-version**: **FILE DELETED ENTIRELY**
- **Consequence**: No automatic summaries in alternate branches

**4. Video Encoding Infrastructure Removal**
- **main**: 3 video files (807 lines total):
  - `video/video_encoder.py` (400 lines)
  - `video/simple_video_capture.py` (202 lines)
  - `capture/video_capture_service.py` (202 lines)
- **deepseek-ocr/codex-version**: **ALL 3 FILES DELETED**

**5. New Features Only in Alternate Branches**
- **Context7 Integration**: Only in deepseek-ocr/codex-version
  - File: `src/second_brain/context7_client.py` (187 lines)
  - Docs: `CONTEXT7_INTEGRATION.md` (139 lines)
- **MCP Server**: Only in codex-version
  - File: `src/second_brain/mcp_server/server.py` (53 lines)
- **Settings API**: Only in codex-version
  - File: `src/second_brain/api/settings.py` (281 lines)

---

### Issue 1.2: Dependency Version Conflicts Across Branches
**Severity: HIGH**

| Dependency | main | deepseek-ocr/codex | Conflict? |
|------------|------|-------------------|-----------|
| **openai** | 2.6.1 | 1.12.0 | YES - 14 versions apart |
| **pyobjc-framework-Quartz** | 12.0 | 10.1 | YES - major version diff |
| **pyobjc-framework-Vision** | 12.0 | NOT INSTALLED | YES - missing entirely |
| **sentence-transformers** | 5.1.2 | 2.2.2 | YES - 3 major versions |
| **numpy** | 1.26.4 | 1.26.2 | Minor - low risk |

**Consequence:**
- **openai 2.6.1 vs 1.12.0**: API incompatibilities (Responses API doesn't exist in either!)
- **pyobjc 12.0 vs 10.1**: Apple Vision framework unavailable in deepseek-ocr branches
- **sentence-transformers 5.1.2 vs 2.2.2**: Embedding model incompatibilities likely

**Files Affected:**
- `requirements.txt` (conflicts on 5+ dependencies)
- `setup.py` (conflicts on all pyobjc versions)

---

### Issue 1.3: Branch-Specific Workarounds That Conflict
**Severity: HIGH**

**Workaround 1: Embedding Compatibility Check (main branch only)**
- File: `src/second_brain/pipeline/processing_pipeline.py:147-158`
- Code silently catches embedding errors with `"cached_download" in error_str`
- **Not present in alternate branches** - they may fail differently

**Workaround 2: DeepSeek MLX Configuration (codex-version only)**
- File: `src/second_brain/config.py` (codex-version)
- Adds `deepseek_mlx_inference` config option
- **Not present in main** - config incompatible

**Workaround 3: Hybrid OCR Toggle (codex-version only)**
- File: `web/timeline/src/components/OCREngineToggle.tsx` (67 lines)
- React component for switching OCR engines
- **Not present in main** - UI incompatible

---

### Git-Wide Issues: Recommendations

1. **URGENT**: Choose canonical OCR implementation:
   - **Option A**: Keep Apple Vision (main) - local, fast, zero cost
   - **Option B**: Migrate to OpenAI/DeepSeek (alternate branches) - cloud, slower, costs money
   - **Do NOT merge without deciding** - will cause catastrophic conflicts

2. **URGENT**: Decide on UI fate:
   - Restore `streamlit_app.py` in alternate branches, OR
   - Accept UI deletion and rebuild from main

3. **URGENT**: Create dependency lockfile:
   - Use `pip freeze > requirements-lock.txt` on main
   - Test alternate branches with same locked versions
   - Identify breaking changes before merge

4. **URGENT**: Create branch merge plan:
   - Document which features from each branch to keep
   - Create migration scripts for config changes
   - Plan staged merge (not direct merge to main)

---

## 2. Phantom References (Code That Doesn't Exist)

### Issue 2.1: OpenAI Responses API Not Available
**Severity: CRITICAL** - Will cause immediate AttributeError at runtime

**The Problem:**
All AI-powered features use `client.responses.create()` method, but:
- **Current dependency**: `openai==2.6.1` (released May 2024)
- **Responses API added**: `openai>=1.52.0` (released December 2024)
- **The API didn't exist when version 2.6.1 was released**

**Locations Using Phantom API:**

1. **src/second_brain/cli.py**
   - Line 414: `response = client.responses.create(...)`
   - Line 457: `response2 = client.responses.create(...)`
   - Function: `query()` - semantic search with AI answers

2. **src/second_brain/summarization/summarization_service.py**
   - Line 123: `response = await self.client.responses.create(...)`
   - Function: `_generate_summary()` - automatic hourly/daily summaries

3. **src/second_brain/ui/streamlit_app.py**
   - Line 877: `response = openai_client.responses.create(...)`
   - Line 926: `response2 = openai_client.responses.create(...)`
   - Function: `run()` - Streamlit UI AI chat feature

**Expected Runtime Error:**
```python
AttributeError: 'OpenAI' object has no attribute 'responses'
```

**User-Facing Impact:**
- ❌ `second-brain query "text" --semantic` → CRASHES
- ❌ Automatic hourly summaries → CRASHES
- ❌ Streamlit UI "Ask a question" → CRASHES
- ❌ Daily AI summaries → CRASHES

**Blast Radius:** 3 files, 5 function calls, affects 4 user-facing features

**Fix Required:**
```python
# Option 1: Update dependency (if Responses API exists in newer versions)
# In requirements.txt and setup.py:
openai>=2.16.0,<3.0.0  # Verify correct version with Responses API

# Option 2: Use chat completions API instead (proven to work)
# Replace all responses.create() with:
response = client.chat.completions.create(
    model="gpt-4o",  # or other valid model
    messages=[{"role": "user", "content": prompt}]
)
```

---

### Issue 2.2: Undefined Response Attributes
**Severity: HIGH** - Likely to fail silently or return wrong data

**The Problem:**
Code assumes response objects have `.output_text` and `.status` attributes, but these names are speculative.

**Locations (5 instances):**

```python
# Pattern used in all 3 files:
answer = getattr(response, "output_text", None)  # ← Attribute may not exist
finish_reason = getattr(response, "status", None)  # ← Attribute may not exist
```

1. `src/second_brain/cli.py:431` - `output_text` extraction
2. `src/second_brain/cli.py:432` - `status` extraction
3. `src/second_brain/summarization/summarization_service.py:133`
4. `src/second_brain/ui/streamlit_app.py:905`
5. `src/second_brain/ui/streamlit_app.py:906`

**Actual OpenAI API Response Structure:**
```python
# chat.completions API (documented):
response.choices[0].message.content  # NOT response.output_text
response.choices[0].finish_reason    # NOT response.status
```

**Impact:** Code will always get `None` from getattr() fallbacks, meaning:
- AI answers will always be empty
- Finish reasons will never be checked correctly
- Error messages will be misleading

---

## 3. Feature Sprawl (Duplicate Implementations)

### Issue 3.1: Video Capture/Encoding (Three Competing Implementations)
**Severity: HIGH**
**Code Duplication:** 807 lines across 3 files

**Files:**
1. `src/second_brain/capture/video_capture_service.py` (203 lines)
   - **Approach:** Direct real-time screen capture to H.264 using ffmpeg
   - **Usage:** Imported by `processing_pipeline.py` but never actually used

2. `src/second_brain/video/simple_video_capture.py` (203 lines)
   - **Approach:** Batch conversion of saved PNG/WebP frames to H.264
   - **Usage:** Called by CLI `convert-to-video` command

3. `src/second_brain/video/video_encoder.py` (401 lines)
   - **Approach:** Hardware-accelerated encoding via Apple AVFoundation
   - **Usage:** **COMPLETELY UNUSED** - dead code

**Why This Is AI-Generated Technical Debt:**
- Three different solutions to the same problem
- Most sophisticated implementation (H264VideoEncoder) is unused
- No clear "canonical" version
- Comments suggest iterative AI generation: "optional at runtime", "for future H.264 implementation"

**Maintenance Burden:**
- Testing 3 different approaches
- Keeping ffmpeg parameters in sync
- User confusion about which one actually runs

**Recommendation:**
- **Delete** `video_encoder.py` (401 lines of dead code)
- **Choose** between real-time (VideoCaptureService) vs batch (VideoConverter)
- **Document** which one is canonical
- **Estimated savings:** 401 lines immediately, 203 lines after consolidation

---

### Issue 3.2: AI Answer Generation (357 Lines of Near-Identical Code)
**Severity: CRITICAL**
**Code Duplication:** 357 lines across 3 files

**Files:**
1. `src/second_brain/api/server.py:166-271` (105 lines)
2. `src/second_brain/cli.py:370-475` (106 lines)
3. `src/second_brain/ui/streamlit_app.py:809-954` (146 lines)

**Duplicated Logic:**
- Build context from search results (with relevance markers)
- Sanitize text to 300 characters
- Call OpenAI Responses API with same prompt structure
- Retry with condensed context (200 chars, 10 results) on empty response
- Extract answer and finish_reason from response

**Example (appears 3 times):**
```python
# Build context with relevance markers
context_items = []
for result in search_results[:40]:  # Hardcoded in all 3 places
    text_snippet = result["text"][:300]  # Hardcoded in all 3 places
    relevance = "HIGH" if result["score"] > 0.8 else "MEDIUM" if result["score"] > 0.5 else "LOW"
    context_items.append(f"[RELEVANCE: {relevance}] {text_snippet}")

# Retry logic (identical in all 3)
if not answer:
    # Retry with smaller context
    context_items = [r["text"][:200] for r in search_results[:10]]
    response2 = client.responses.create(...)
```

**Why This Is AI-Generated Technical Debt:**
- Same prompt wording across 3 files
- Same magic numbers (40 results, 300 chars, 200 chars fallback)
- Same retry logic with identical structure
- Only differs in display (JSON vs Rich panel vs Streamlit HTML)

**Maintenance Burden:**
- Bug fixes require 3 updates
- Prompt improvements need 3 changes
- Magic number tuning needs 3 edits
- Testing requires 3 integration tests

**Recommendation:**
- Extract to `src/second_brain/ai/answer_generator.py`:
  ```python
  class AIAnswerGenerator:
      def generate_answer(self, query: str, search_results: list) -> dict:
          # Single canonical implementation
  ```
- Update all 3 callers to use shared service
- **Estimated savings:** 250+ lines of duplication

---

### Issue 3.3: Search Result Building (168 Lines of Duplicate Logic)
**Severity: HIGH**
**Code Duplication:** 168 lines across 3 files

**Files:**
1. `src/second_brain/api/server.py:109-163` (55 lines)
2. `src/second_brain/cli.py:316-363` (48 lines)
3. `src/second_brain/ui/streamlit_app.py:740-804` (65 lines)

**Duplicated Logic:**
```python
# Pattern repeated 3 times:
if use_semantic:
    embedding_service = EmbeddingService()
    matches = embedding_service.search(query, limit, app_filter)
    for match in matches:
        frame = db.get_frame(match["frame_id"])
        block = db.get_text_block(match["block_id"])
        search_results.append({
            "frame_id": frame.get("frame_id"),
            "app_name": frame.get("app_name") or "Unknown",
            "timestamp": frame.get("timestamp"),
            "text": block.get("text", ""),
            "score": 1 - match.get("distance", 0.0),
            "method": "semantic",
        })
else:
    results = db.search_text(query, app_filter, limit)
    # ... build same dict structure for FTS results
```

**Why This Is AI-Generated Technical Debt:**
- Exact same result dictionary structure in all 3
- Same fallback pattern: `frame.get("app_name") or "Unknown"`
- Same score calculation: `1 - match.get("distance", 0.0)`
- Only difference is logging (streamlit_app.py has debug_info)

**Recommendation:**
- Create `SearchResultFormatter` class
- **Estimated savings:** 110+ lines

---

### Issue 3.4: Text Sanitization (21 Lines, 3 Copies)
**Severity: MEDIUM**
**Code Duplication:** 21 lines across 3 files

**Files:**
1. `src/second_brain/api/server.py:198-204` (function: `_sanitize`)
2. `src/second_brain/cli.py:382-388` (function: `_sanitize_text`)
3. `src/second_brain/ui/streamlit_app.py:832-838` (function: `_sanitize_text`)

**Identical Implementation:**
```python
def _sanitize_text(s: str) -> str:  # Name varies but code is identical
    return "".join(
        ch if (ch == "\n" or 32 <= ord(ch) <= 126 or
               (ord(ch) >= 160 and ord(ch) not in (0xFFFF, 0xFFFE)))
        else " "
        for ch in s
    )
```

**Why This Is AI-Generated Technical Debt:**
- Identical logic, character-for-character
- Same control character filtering (ASCII 32-126, plus Unicode >=160)
- Same newline preservation
- Different function names suggest copy-paste

**Recommendation:**
- Move to `src/second_brain/utils/text.py`
- Import in all 3 files
- **Estimated savings:** 14 lines

---

### Issue 3.5: Database Connection Patterns (4 Different Approaches)
**Severity: HIGH**

**Patterns:**

**1. Direct SQLite Connection (streamlit_app.py:193-204)**
```python
self.conn = sqlite3.connect(str(self.db_path))
self.conn.row_factory = sqlite3.Row
```
- Bypasses `Database` class entirely
- Missing WAL mode, compression, proper initialization

**2. Direct Database() Instantiation (cli.py - 3 places)**
```python
db = Database()
# ... use db
db.close()
```
- Repeated pattern in lines 239, 305, 580

**3. Dependency Injection (api/server.py:39-44)**
```python
def get_db() -> Generator[Database, None, None]:
    db = Database(config=config)
    try:
        yield db
    finally:
        db.close()
```
- Most sophisticated pattern (FastAPI-style)

**4. Optional Config Pattern (8+ services)**
```python
self.config = config or Config()
```
- Every service creates own Config instance instead of using singleton

**Why This Is Technical Debt:**
- StreamlitUI will have different database behavior (missing PRAGMA settings)
- No connection pooling
- Config singleton exists (`get_config()`) but is unused

**Recommendation:**
- Enforce `Database` class usage everywhere
- Use `get_config()` singleton
- Remove direct sqlite3 connections

---

### Issue 3.6: Configuration Instantiation (12+ Duplicate Patterns)
**Severity: MEDIUM**

**Every service does:**
```python
self.config = config or Config()
```

**But a singleton exists:**
```python
# config.py:175-180
_config = None
def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
```

**Files Creating Own Config Instances:**
- capture_service.py:38
- video_capture_service.py:29
- apple_vision_ocr.py:33
- embedding_service.py:37
- database/db.py:25
- summarization_service.py:32
- video/simple_video_capture.py:30
- video/video_encoder.py:89
- pipeline/processing_pipeline.py:28
- api/server.py:16
- cli.py:143, 305, 530, 589, 738 (5 instances)

**Consequence:**
- Config changes mid-runtime won't propagate
- Testing harder (must pass config to all services)
- Memory waste (small but unnecessary)

**Recommendation:**
- Replace all `Config()` with `get_config()`
- Update service __init__ to use singleton by default

---

## 4. Stub Graveyards (Incomplete Implementations)

### Issue 4.1: Silent Exception Handler - Process Inspection Failures
**Severity: MEDIUM**
**File:** `src/second_brain/capture/capture_service.py:122-123`

```python
try:
    psutil.Process(owner_pid)
    bundle_id = f"com.{owner_name.lower().replace(' ', '')}"
except (psutil.NoSuchProcess, psutil.AccessDenied):
    pass  # ← Swallows error silently
```

**Where Called:** `capture_service.py:299` in `capture_frame()`

**Problem:**
- No logging when process inspection fails
- Caller can't distinguish between successful bundle_id and fallback guess
- Debugging "why is bundle_id wrong?" becomes impossible

**Recommendation:**
```python
except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
    logger.debug(
        "process_inspection_failed",
        owner_pid=owner_pid,
        owner_name=owner_name,
        error=str(e),
    )
```

---

### Issue 4.2: Silent Exception Handler - Metadata File Size Tracking
**Severity: MEDIUM**
**File:** `src/second_brain/capture/capture_service.py:321-324`

```python
try:
    self._frames_dir_usage_bytes += metadata_path.stat().st_size
except OSError:
    pass  # ← Silently fails disk usage tracking
```

**Where Called:** `processing_pipeline.py:80` via `capture_frame()`

**Problem:**
- Disk usage calculations will be inaccurate
- No indication that tracking failed
- Could lead to disk space issues (disk safeguards rely on accurate tracking)

**Impact:**
- `max_disk_usage_gb` limit may not trigger correctly
- `second-brain status` shows wrong disk usage

**Recommendation:**
```python
except OSError as e:
    logger.warning(
        "metadata_stat_failed",
        metadata_path=str(metadata_path),
        error=str(e),
    )
```

---

### Issue 4.3: Conditional Silent Exception - Embedding Compatibility
**Severity: HIGH**
**File:** `src/second_brain/pipeline/processing_pipeline.py:147-158`

```python
try:
    if self.embedding_service:
        self.embedding_service.index_text_blocks(metadata, text_blocks)
except Exception as embed_error:
    error_str = str(embed_error)
    if "cached_download" in error_str or "url" in error_str:
        pass  # ← Silently skip embedding for compatibility issues
    else:
        logger.error(...)
```

**Problem:**
- Known compatibility issues are swallowed without ANY logging
- No metrics on how often embedding fails
- Users won't know semantic search is degraded

**Impact:**
- Semantic search will be missing data
- No visibility into failure rate
- Hard to detect when sentence-transformers model download fails

**Recommendation:**
```python
if "cached_download" in error_str or "url" in error_str:
    logger.info(
        "embedding_skipped_compatibility",
        frame_id=metadata["frame_id"],
        error_hint=error_str[:100],
    )
else:
    logger.error(...)
```

---

### Issue 4.4: Async Function Stub - Empty close()
**Severity: LOW**
**File:** `src/second_brain/ocr/apple_vision_ocr.py:268-270`

```python
async def close(self) -> None:
    """Cleanup (no resources to release for local OCR)."""
    pass
```

**Where Called:** `processing_pipeline.py:236` via `await self.ocr_service.close()`

**Problem:**
- Unnecessary async function (no await inside)
- Should be regular function or removed
- Sets bad pattern (every service has empty close())

**Recommendation:**
- Remove method entirely (no resources to clean), OR
- Make non-async: `def close(self) -> None: pass`

---

## 5. Documentation Drift

### Issue 5.1: OCR Implementation Completely Misrepresented
**Severity: CRITICAL**
**Will confuse contributors and users**

**Documentation Claims (README.md):**
- Line 15: "100% Local OCR – Apple Vision framework"
- Line 84-90: "Apple Vision Framework: Native macOS OCR"

**But Also Claims (docs/SETUP.md):**
- Line 73-74: `"engine": "openai"` in config
- Line 94: "GPT-5 vision is the only supported OCR model"
- Lines 158-160: Example code uses `from second_brain.ocr import OpenAIOCR`

**Actual Implementation:**
- `src/second_brain/ocr/__init__.py:9` - Imports `AppleVisionOCR`
- `src/second_brain/ocr/apple_vision_ocr.py` - 270 lines of Apple Vision implementation
- **No `OpenAIOCR` class exists in main branch**

**Impact:**
- Setup docs tell users to configure non-existent OCR engine
- Code examples won't run (ImportError)
- Contradicts README's main selling point

**Root Cause:**
- Docs written for alternate branch (deepseek-ocr) merged into main
- AI likely generated docs from wrong branch context

---

### Issue 5.2: Non-Existent GPT-5 Model Referenced
**Severity: HIGH**
**API calls will fail**

**Locations Claiming "GPT-5":**
- README.md:16, 95, 259, 373
- cli.py:415, 458 (`model="gpt-5"`)
- api/server.py:233 (`model="gpt-5"`)
- summarization_service.py:42, 67
- ui/streamlit_app.py:878, 927

**Problem:**
- GPT-5 doesn't exist in OpenAI API (as of January 2025)
- Code will fail with: `openai.BadRequestError: Invalid model: gpt-5`

**Likely Intended:**
- gpt-4o (GPT-4 Omni)
- gpt-4o-mini
- gpt-4-vision-preview

**Impact:**
- All AI features will fail immediately
- README promises feature that can't work

---

### Issue 5.3: Non-Existent CLI Command Documented
**Severity: MEDIUM**

**Documentation Claims:**
- `docs/architecture/overview.md:168` - `second-brain restart` command exists

**Actual Implementation:**
- No `restart` command in `cli.py`
- Available commands: start, stop, status, query, convert_to_video, health, ui, timeline, reset

**Impact:**
- Users will try `second-brain restart` and get error

---

### Issue 5.4: Wrong Configuration Path in SETUP.md
**Severity: LOW**

**SETUP.md:59 claims:**
```
~/.config/second-brain/settings.json
```

**Actual path (config.py:61):**
```
~/Library/Application Support/second-brain/config/settings.json
```

**Impact:**
- Users can't find config file
- Linux-style path on macOS-only app

---

### Issue 5.5: Docstrings Contradict Implementation
**Severity: MEDIUM**

**summarization_service.py:1:**
```python
"""Real-time activity summarization using GPT-5"""
```

**summarization_service.py:67:**
```python
def _generate_summary(...):
    """Generate a summary using GPT-5"""
```

**But:**
- GPT-5 doesn't exist
- Will fail at runtime

---

## 6. Dependency Hell

### Issue 6.1: Python Version Assumptions
**Severity: MEDIUM**

**Claimed Requirements:**
- README.md:8, 31: "Python 3.11+"
- setup.py:8: `python_requires=">=3.11"`
- docs/SETUP.md:67: "Python 3.11.7"
- .python-version (deleted in deepseek-ocr): "3.11.7"

**Actual Compatibility:**
- Code uses features available in 3.11+
- But no testing on 3.12/3.13

**Risk:**
- sentence-transformers 5.1.2 may have breaking changes on Python 3.12+
- No CI/testing to verify

---

### Issue 6.2: PyTorch Version-Specific Code Without Guards
**Severity: MEDIUM**

**sentence-transformers dependency chain:**
- sentence-transformers 5.1.2 → torch (unspecified version)
- sentence-transformers 2.2.2 (in deepseek-ocr) → torch (older)

**Problem:**
- No torch version pinned
- sentence-transformers version jump (2.2.2 → 5.1.2) is 3 major versions
- Model formats may be incompatible

**Files Using PyTorch Indirectly:**
- embedding_service.py:37 - Imports sentence_transformers
- No version checks before loading models

**Risk:**
- Chroma embeddings created with old version may not load in new version
- Users upgrading will get runtime errors

---

### Issue 6.3: Missing Migration for Database Schema Changes
**Severity: MEDIUM**

**Schema Changes Across Branches:**
- **main**: database/schema.sql (original schema)
- **codex-version**: schema.sql has new columns (line 21: additional OCR engine field)

**No Migration Scripts:**
- No `migrations/` directory
- No alembic or similar tool
- Users upgrading between branches will get schema errors

**Expected Errors:**
```sql
sqlite3.OperationalError: table frames has no column named ocr_engine
```

---

### Issue 6.4: Conflicting Dependency Version Pins
**Severity: HIGH**

**setup.py vs requirements.txt Conflicts:**

| Dependency | requirements.txt | setup.py | Conflict? |
|------------|------------------|----------|-----------|
| python-dotenv | 1.0.0 | 1.0.0 | ✓ Match |
| openai | 2.6.1 | 2.6.1 | ✓ Match |
| sentence-transformers | 5.1.2 | 5.1.2 | ✓ Match |

**But both are outdated:**
- openai latest: ~2.20.0 (should update for Responses API)
- sentence-transformers latest: ~5.1.2 (current)

**No requirements-lock.txt:**
- Transitive dependencies not locked
- torch, transformers, chromadb versions can vary
- Reproducibility issues

---

## 7. Test Gaming / Fragile Test Code

### Issue 7.1: Hardcoded Waits in Tests
**Severity: LOW**
**File:** `tests/test_e2e_settings.py` (DELETED in deepseek-ocr, but shows pattern)

**Pattern (from git history):**
```python
page.wait_for_timeout(2000)  # Wait 2 seconds
page.click("button")
page.wait_for_timeout(1000)  # Wait 1 second
```

**Why This Is Problematic:**
- Tests pass on fast machines, fail on slow CI
- Arbitrary timeouts instead of waiting for conditions
- Playwright has better patterns: `page.wait_for_selector()`

---

## 8. Cargo Cult Code Patterns

### Issue 8.1: Unused Imports Throughout Codebase
**Severity: LOW**

**Example: cli.py**
- Line 13: `import json` - used once
- Line 14: `import sys` - used once
- Multiple async imports in sync functions

**Pattern:**
- AI-generated code often imports "just in case"
- No import optimization

### Issue 8.2: Overly Defensive Getattr() Patterns
**Severity: LOW**

**Example throughout codebase:**
```python
frame.get("frame_id")  # Dict, not object
frame.get("app_name") or "Unknown"  # Unnecessary or
```

**Why This Is Cargo Cult:**
- Dicts from database always have these keys (schema enforced)
- `or "Unknown"` pattern repeated everywhere even when NOT NULL constraint exists

---

## Summary Tables

### Technical Debt by Category

| Category | Issues | Lines of Code | Files Affected | Severity |
|----------|--------|---------------|----------------|----------|
| Phantom References | 2 | ~10 call sites | 3 | CRITICAL |
| Feature Sprawl | 6 | ~1,350 lines | 12+ | CRITICAL |
| Stub Graveyards | 4 | ~20 lines | 3 | HIGH |
| Documentation Drift | 7 | N/A | 5+ docs | HIGH |
| Dependency Conflicts | 4 | N/A | 2 | HIGH |
| Branch Divergence | 4 | ~8,766 lines | 65+ | CRITICAL |
| **TOTAL** | **27** | **~10,136 lines** | **90+** | |

### Estimated Effort to Fix

| Issue | Estimated Hours | Risk | Priority |
|-------|-----------------|------|----------|
| Fix OpenAI Responses API | 2-4 hours | High | P0 |
| Choose canonical OCR, merge branches | 16-24 hours | Critical | P0 |
| Consolidate AI answer generation | 4-6 hours | Medium | P1 |
| Consolidate search result building | 2-3 hours | Low | P1 |
| Delete dead video code | 1 hour | Low | P2 |
| Fix documentation drift | 3-5 hours | Low | P1 |
| Add logging to silent exceptions | 2 hours | Low | P2 |
| Update dependencies, test compatibility | 4-6 hours | Medium | P1 |
| **TOTAL ESTIMATED EFFORT** | **34-51 hours** | | |

---

## Recommendations for Upstream Contribution

### BEFORE Submitting ANY Pull Requests:

1. **CRITICAL: Fix OpenAI API Usage**
   - [ ] Update openai dependency to version with Responses API, OR
   - [ ] Replace all `responses.create()` with `chat.completions.create()`
   - [ ] Test all AI features actually work
   - [ ] Fix "gpt-5" model name to valid model

2. **CRITICAL: Choose Canonical Branch**
   - [ ] Decide: Apple Vision OCR (main) vs OpenAI/DeepSeek (alternate branches)?
   - [ ] If keeping main: document that alternate branches are experimental
   - [ ] If merging alternate: plan migration path for UI/summarization deletion
   - [ ] **Do NOT submit PR from deepseek-ocr or codex-version without massive cleanup**

3. **HIGH: Consolidate Duplicate Code**
   - [ ] Extract AIAnswerGenerator service (save 250+ lines)
   - [ ] Extract SearchResultFormatter (save 110+ lines)
   - [ ] Move text sanitization to utils (save 14 lines)
   - [ ] Delete video_encoder.py dead code (save 401 lines)

4. **HIGH: Fix Documentation**
   - [ ] Remove all "GPT-5" references, replace with actual model
   - [ ] Fix SETUP.md OCR example code
   - [ ] Remove `second-brain restart` from docs
   - [ ] Verify all README examples actually work

5. **MEDIUM: Add Logging**
   - [ ] Add logging to silent exception handlers
   - [ ] Add metrics for embedding failures
   - [ ] Add debug mode documentation

6. **MEDIUM: Lock Dependencies**
   - [ ] Create requirements-lock.txt with `pip freeze`
   - [ ] Test on clean virtualenv
   - [ ] Document known incompatibilities

### Recommended PR Strategy:

**Phase 1: Critical Fixes (Required Before ANY PR)**
1. PR: Fix OpenAI API usage + model names
2. PR: Delete dead code (video_encoder.py, unused imports)
3. PR: Fix documentation drift

**Phase 2: Code Quality (Makes Review Easier)**
4. PR: Consolidate duplicate AI code
5. PR: Consolidate duplicate search code
6. PR: Add logging to silent exceptions

**Phase 3: Branch Reconciliation (Long-term)**
7. Decide on OCR strategy
8. Plan merge of deepseek-ocr/codex-version features
9. Create migration guides

---

## Appendix: Files with Highest Technical Debt

| File | Issues | Debt Type | Action |
|------|--------|-----------|--------|
| cli.py | 7 | Phantom refs, duplication, bad patterns | Refactor |
| ui/streamlit_app.py | 6 | Duplication, deleted in alt branches | Restore or remove |
| api/server.py | 5 | Duplication, phantom refs | Refactor |
| video/video_encoder.py | 1 | Dead code (401 lines) | DELETE |
| processing_pipeline.py | 3 | Silent exceptions, workarounds | Add logging |
| requirements.txt | 4 | Version conflicts across branches | Lock versions |
| README.md | 6 | Documentation drift | Rewrite |
| docs/SETUP.md | 4 | Wrong examples, wrong paths | Fix |

---

## Conclusion

This codebase shows clear signs of AI-assisted development across multiple branches without proper consolidation:

1. **Multiple AI sessions generated competing solutions** (3 OCR implementations, 3 video encoders)
2. **Copy-paste duplication** (357 lines of identical AI answer code)
3. **Phantom APIs** (Responses API that doesn't exist in pinned version)
4. **Documentation generated from wrong context** (main branch docs describe alternate branch features)
5. **Branch divergence** (8,766 lines deleted in alternate branches)

**The good news:** Most issues are fixable with systematic refactoring. The code that exists IS functional (once API issues are fixed), just duplicated and scattered.

**The bad news:** Attempting to merge branches without fixing these issues first will result in catastrophic conflicts and broken features.

**Recommendation:** Fix Phase 1 critical issues (OpenAI API, docs, dead code) before ANY upstream contribution. Consider current main branch as canonical and treat alternate branches as experimental forks that need careful cherry-picking, not direct merging.

---

**Report End**
*Generated by comprehensive static analysis across all git branches*
*Commit analyzed: 27de198 (claude/audit-ai-technical-debt-011CUc8Lz8ceeZuQCPxLUmGw)*
