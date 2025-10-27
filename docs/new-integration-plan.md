# SecondBrain Enhancement Plan: DeepSeek OCR + MCP Integration

## CRITICAL: This ADDS to your existing system, doesn't replace it!

## What You Already Have (KEEP ALL OF THIS)
- ✅ `capture/capture_service.py` - Screenshot capture at 1-2 fps
- ✅ `ocr/openai_ocr.py` - GPT-5 vision OCR 
- ✅ `pipeline/processing_pipeline.py` - Processing queue
- ✅ `database/` - SQLite + schema.sql
- ✅ Chroma embeddings for semantic search
- ✅ Timeline UI (React + Vite)
- ✅ FastAPI server with `/api/frames`, `/api/apps`
- ✅ CLI interface with start/stop/status/query

## What We're ADDING (Not Replacing)

### 1. DeepSeek OCR as Alternative Engine (`ocr/deepseek_ocr.py`)
```python
# NEW FILE: src/second_brain/ocr/deepseek_ocr.py
# Parallel to your existing openai_ocr.py

class DeepSeekOCR:
    """Alternative OCR engine using DeepSeek's 10-20x compression"""
    
    def __init__(self, config: Config):
        self.config = config
        self.use_docker = config.get('ocr.deepseek_docker', True)
        # Can coexist with OpenAI OCR
        
    def process_frame(self, screenshot_path: str) -> OCRResult:
        """Process single frame - matches OpenAI OCR interface"""
        # Implementation that matches your existing OCRResult type
        
    def process_batch(self, screenshots: List[str]) -> List[OCRResult]:
        """NEW: Batch processing with compression"""
        # Combine images, compress, return results
```

### 2. Screenshot Buffer Enhancement (`capture/screenshot_buffer.py`)
```python
# NEW FILE: src/second_brain/capture/screenshot_buffer.py
# Works WITH your existing capture_service.py

class ScreenshotBuffer:
    """Buffer screenshots for batch processing"""
    
    def __init__(self, buffer_duration: int = 30):
        self.buffer = deque(maxlen=60)
        
    def should_flush(self) -> bool:
        """Decide when to process batch"""
        return len(self.buffer) >= 30 or time_elapsed > buffer_duration
```

### 3. Modified Pipeline to Support Both OCR Engines
```python
# MODIFY: src/second_brain/pipeline/processing_pipeline.py

class ProcessingPipeline:
    def __init__(self, config: Config):
        self.config = config
        
        # Choose OCR engine based on config
        ocr_engine = config.get('ocr.engine', 'openai')
        
        if ocr_engine == 'openai':
            self.ocr = OpenAIVisionOCR(config)  # Your existing
        elif ocr_engine == 'deepseek':
            self.ocr = DeepSeekOCR(config)      # New addition
        elif ocr_engine == 'hybrid':
            # Use both! DeepSeek for bulk, OpenAI for priority
            self.primary_ocr = DeepSeekOCR(config)
            self.fallback_ocr = OpenAIVisionOCR(config)
            
        # Add buffer for batch processing
        self.buffer = ScreenshotBuffer() if ocr_engine in ['deepseek', 'hybrid'] else None
```

### 4. MCP Server Addition (`mcp_server/`)
```python
# NEW DIRECTORY: src/second_brain/mcp_server/
# Exposes your EXISTING functionality via MCP

from ..database import Database
from ..capture import CaptureService

class SecondBrainMCPServer:
    """MCP interface to existing SecondBrain functionality"""
    
    def __init__(self, db: Database):
        self.db = db  # Use your existing database
        
    async def search_memory(self, query: str):
        # Calls your existing db.search_frames()
        
    async def get_screenshot(self, timestamp: str):
        # Calls your existing db.get_frame()
```

### 5. Config Updates (ADD to existing)
```json
{
  "capture": {
    "fps": 1,
    "max_disk_usage_gb": 100,
    "min_free_space_gb": 10,
    "buffer_enabled": true,  // NEW
    "buffer_duration": 30    // NEW
  },
  "ocr": {
    "engine": "hybrid",  // NEW: openai, deepseek, or hybrid
    "model": "gpt-5",
    "rate_limit_rpm": 50,
    "deepseek_docker": true,  // NEW
    "deepseek_mode": "optimal",  // NEW
    "batch_size": 30  // NEW
  }
}
```

## Implementation Steps (Incremental!)

### Phase 1: Add DeepSeek OCR (Keep OpenAI Working!)
1. Create `ocr/deepseek_ocr.py` matching your OCRResult interface
2. Add config flag to choose OCR engine
3. Test side-by-side with OpenAI OCR

### Phase 2: Add Buffering (Optional at First)
1. Create `capture/screenshot_buffer.py`
2. Modify `processing_pipeline.py` to optionally use buffer
3. Keep immediate processing as default

### Phase 3: Add MCP Server (Separate Process)
1. Create `mcp_server/` directory
2. Run as separate service on port 3000
3. Exposes your existing database queries

### Phase 4: Hybrid Mode (Best of Both)
1. Use DeepSeek for bulk background processing
2. Keep OpenAI for real-time priority frames
3. Intelligent routing based on queue size

## File Structure (What Gets Added)
```
src/second_brain/
├── capture/
│   ├── capture_service.py      # EXISTING - unchanged
│   └── screenshot_buffer.py    # NEW - optional buffering
├── ocr/
│   ├── __init__.py             # EXISTING
│   ├── openai_ocr.py           # EXISTING - keep as-is
│   └── deepseek_ocr.py         # NEW - alternative engine
├── pipeline/
│   └── processing_pipeline.py  # MODIFY - add engine selection
├── mcp_server/                 # NEW directory
│   ├── __init__.py
│   ├── server.py               # MCP protocol server
│   └── tools.py                # MCP tool definitions
└── config.py                    # MODIFY - add new options
```

## Docker Setup (Optional, Alongside Existing)
```yaml
# docker-compose.yml - ADD to your project
services:
  deepseek-ocr:
    image: deepseek-ocr:latest
    ports:
      - "8001:8000"  # Different port from your FastAPI
    volumes:
      - ./models:/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

## CLI Updates (Backwards Compatible)
```bash
# Existing commands still work
second-brain start             # Uses config engine choice
second-brain status             # Shows OCR engine in use
second-brain query "term"       # Works regardless of OCR

# New optional flags
second-brain start --ocr-engine deepseek
second-brain start --buffer-duration 60
second-brain compress-history  # Reprocess old frames with DeepSeek
```

## Cost Savings Calculation
- Current: Every frame → GPT-5 OCR (~$0.01/frame)
- With DeepSeek Buffer: 30 frames → 1 DeepSeek call (~$0.001 total)
- Savings: 99.9% reduction in OCR costs
- Fallback: Still have GPT-5 for priority/failed frames

## Testing Strategy
1. Run DeepSeek in parallel (don't disable OpenAI)
2. Compare results in database
3. Gradually increase DeepSeek usage
4. Keep OpenAI as fallback

## Migration Path
```python
# Add to your existing CLI
@cli.command()
@click.option('--start-date', default=None)
@click.option('--batch-size', default=100)
def migrate_to_deepseek(start_date, batch_size):
    """Reprocess historical frames with DeepSeek OCR"""
    # Get frames already processed with OpenAI
    frames = db.get_frames(start_date=start_date, ocr_engine='openai')
    
    # Process in batches with DeepSeek
    deepseek = DeepSeekOCR(config)
    for batch in chunks(frames, batch_size):
        results = deepseek.process_batch(batch)
        db.update_ocr_results(results, engine='deepseek')
```

## Key Integration Points

### 1. Database Schema (Minor Addition)
```sql
-- Add to your existing schema.sql
ALTER TABLE frame_text ADD COLUMN ocr_engine TEXT DEFAULT 'openai';
ALTER TABLE frame_text ADD COLUMN compression_ratio REAL;
```

### 2. Processing Pipeline Hook
```python
# In your existing processing_pipeline.py
def process_frame(self, frame_path: str):
    if self.buffer and self.buffer.should_flush():
        # Batch process with DeepSeek
        batch_results = self.process_batch()
        self._store_results(batch_results)
    else:
        # Existing single-frame processing
        result = self.ocr.process_frame(frame_path)
        self._store_result(result)
```

### 3. MCP Integration
```python
# New MCP server uses your EXISTING database
mcp_server = SecondBrainMCPServer(
    db_path=config.db_path,  # Your existing SQLite
    chroma_path=config.chroma_path  # Your existing embeddings
)
```

## This Plan:
- ✅ Keeps ALL your existing code working
- ✅ Adds DeepSeek as an option, not requirement
- ✅ Allows gradual migration
- ✅ Maintains backwards compatibility
- ✅ Preserves your Timeline UI
- ✅ Works with your existing tests
- ✅ Enhances rather than replaces