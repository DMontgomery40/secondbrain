# CLAUDE.md - SecondBrain DeepSeek/MCP Enhancement

## PROJECT CONTEXT
ENHANCE existing macOS secondbrain (GPT-5 OCR → SQLite/Chroma → Timeline UI) by ADDING:
1. DeepSeek OCR as alternative/hybrid engine (10-20x compression)
2. Screenshot buffering for batch processing
3. MCP server to expose functionality to AI assistants

## CRITICAL: DO NOT REPLACE EXISTING CODE
- KEEP: `capture_service.py`, `openai_ocr.py`, `processing_pipeline.py`, database layer, Timeline UI
- ADD: `deepseek_ocr.py`, `screenshot_buffer.py`, `mcp_server/`
- MODIFY: `processing_pipeline.py` to support engine selection, `config.py` for new options

## USE CONTEXT7 FOR LATEST DOCS
- **MCP**: `/websites/modelcontextprotocol_io_specification`
- **DeepSeek OCR**: `/deepseek-ai/deepseek-ocr`
- **MCP Python SDK**: `/modelcontextprotocol/python-sdk`

## KEY EXISTING TYPES TO MATCH
```python
# From existing codebase - match these interfaces!
@dataclass
class OCRResult:
    text: str
    blocks: List[TextBlock]
    confidence: float
    metadata: dict

class ProcessingPipeline:
    def process_frame(self, frame_path: str) -> OCRResult
    
class Database:
    def insert_frame_text(self, frame_id: int, result: OCRResult)
    def search_frames(self, query: str, semantic: bool = False)
```

## NEW COMPONENTS TO ADD

### 1. DeepSeek OCR (`ocr/deepseek_ocr.py`)
```python
class DeepSeekOCR:
    def process_frame(self, path: str) -> OCRResult:  # Match existing interface!
        # Single frame processing
        
    def process_batch(self, paths: List[str]) -> List[OCRResult]:  # NEW capability
        # Combine → DeepSeek → Split results
        # Target: 10x compression, 100 vision tokens
```

### 2. Screenshot Buffer (`capture/screenshot_buffer.py`)
```python
class ScreenshotBuffer:
    def add(self, frame_path: str)
    def should_flush(self) -> bool  # 30s or 30 frames
    def get_batch(self) -> List[str]
```

### 3. MCP Server (`mcp_server/server.py`)
```python
# Uses EXISTING database, doesn't create new one!
class SecondBrainMCPServer:
    def __init__(self, existing_db_path: str):
        self.db = Database(existing_db_path)  # Your existing DB
        
    tools = [
        "search_memory",    # Calls db.search_frames()
        "get_screenshot",   # Calls db.get_frame()
        "analyze_activity", # New analysis on existing data
        "compress_batch"    # Trigger DeepSeek reprocessing
    ]
```

## CONFIG ADDITIONS (to existing config.json)
```json
{
  "ocr": {
    "engine": "hybrid",          // NEW: openai|deepseek|hybrid
    "deepseek_docker": true,     // NEW
    "batch_size": 30,            // NEW
    "buffer_duration": 30        // NEW
  }
}
```

## INTEGRATION POINTS

### Modify `processing_pipeline.py`:
```python
def __init__(self, config):
    # Add engine selection
    if config.ocr.engine == 'deepseek':
        self.ocr = DeepSeekOCR(config)
    elif config.ocr.engine == 'hybrid':
        self.ocr = HybridOCR(openai, deepseek)  # Use both!
    else:
        self.ocr = OpenAIVisionOCR(config)  # Default/existing
        
    # Add optional buffering
    self.buffer = ScreenshotBuffer() if config.ocr.buffer_duration else None
```

### Database Migration (minor):
```sql
-- Add to existing schema
ALTER TABLE frame_text ADD COLUMN ocr_engine TEXT DEFAULT 'openai';
ALTER TABLE frame_text ADD COLUMN compression_ratio REAL;
```

## DOCKER SETUP (Separate service)
```bash
# Clone Bogdanovich77 fixed Docker
git clone https://github.com/Bogdanovich77/DeekSeek-OCR---Dockerized-API
docker-compose up -d  # Runs on port 8001
```

## TESTING STRATEGY
1. Run DeepSeek in parallel, don't disable OpenAI
2. Compare results: `SELECT * FROM frame_text WHERE ocr_engine='deepseek'`
3. Gradually increase DeepSeek usage via config
4. Keep OpenAI as fallback for failures

## CLI ADDITIONS (backwards compatible)
```bash
# Existing commands unchanged
second-brain start              # Respects config.ocr.engine

# New commands
second-brain start --ocr-engine deepseek --buffer-duration 60
second-brain reprocess --engine deepseek --from 2024-01-01
second-brain mcp-server        # Start MCP on port 3000
```

## FILE CHANGES SUMMARY
```
ADD:
- src/second_brain/ocr/deepseek_ocr.py
- src/second_brain/capture/screenshot_buffer.py  
- src/second_brain/mcp_server/*.py
- docker-compose.yml

MODIFY (minimally):
- src/second_brain/pipeline/processing_pipeline.py (add engine selection)
- src/second_brain/config.py (add new config keys)
- src/second_brain/database/schema.sql (add 2 columns)

UNCHANGED:
- capture/capture_service.py
- ocr/openai_ocr.py
- web/timeline/*
- All existing tests
```

## PERFORMANCE TARGETS
- Existing: 1 frame → 1 GPT-5 call
- Enhanced: 30 frames → 1 DeepSeek call (10x compression)
- Cost reduction: 99%+ on OCR
- Maintain: 97% accuracy

## QUICK VALIDATION
```python
# Test that both engines work
from ocr.openai_ocr import OpenAIVisionOCR
from ocr.deepseek_ocr import DeepSeekOCR

openai_result = openai.process_frame("test.png")
deepseek_result = deepseek.process_frame("test.png")

assert type(openai_result) == type(deepseek_result) == OCRResult
```

## ERROR HANDLING
- DeepSeek fails → Fall back to OpenAI
- Buffer full → Flush early
- Docker down → Use OpenAI only
- MCP disconnect → Main app unaffected

## THIS IS AN ENHANCEMENT, NOT A REWRITE!