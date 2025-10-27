# Example Implementation: DeepSeek OCR Integration

## 1. NEW FILE: `src/second_brain/ocr/deepseek_ocr.py`
```python
"""
DeepSeek OCR engine - alternative to OpenAI Vision
Matches existing OCRResult interface for drop-in compatibility
"""

import asyncio
import base64
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
import requests
from PIL import Image
import torch

from ..config import Config
from ..database.models import OCRResult, TextBlock  # Use EXISTING types!

class DeepSeekOCR:
    """DeepSeek OCR implementation matching OpenAIVisionOCR interface"""
    
    def __init__(self, config: Config):
        self.config = config
        self.docker_url = config.get('ocr.deepseek_docker_url', 'http://localhost:8001')
        self.use_docker = config.get('ocr.deepseek_docker', True)
        self.mode = config.get('ocr.deepseek_mode', 'optimal')
        
        if not self.use_docker:
            # Load model locally (optional)
            self._load_local_model()
    
    def process_frame(self, screenshot_path: str) -> OCRResult:
        """
        Process single frame - MATCHES OpenAIVisionOCR.process_frame signature
        This ensures drop-in compatibility
        """
        image = Image.open(screenshot_path)
        
        if self.use_docker:
            result = self._process_via_docker(image)
        else:
            result = self._process_local(image)
        
        # Convert to existing OCRResult format
        return self._convert_to_ocr_result(result)
    
    def process_batch(self, screenshot_paths: List[str]) -> List[OCRResult]:
        """
        NEW capability: Batch processing with image combination
        This is what saves money - 30 frames → 1 API call
        """
        from ..capture.image_combiner import combine_screenshots
        
        # Combine screenshots
        images = [Image.open(p) for p in screenshot_paths]
        combined = combine_screenshots(images, strategy='vertical_stack')
        
        # Process combined image
        result = self._process_via_docker(combined)
        
        # Split results back to individual frames
        return self._split_batch_results(result, len(screenshot_paths))
    
    def _process_via_docker(self, image: Image.Image) -> Dict:
        """Call Dockerized DeepSeek OCR API"""
        import io
        
        # Convert PIL to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        # Call API
        files = {'file': ('screenshot.png', img_byte_arr, 'image/png')}
        data = {
            'prompt': '<image>\n<|grounding|>Convert the document to markdown.',
            'mode': self.mode
        }
        
        response = requests.post(
            f"{self.docker_url}/ocr/image",
            files=files,
            data=data,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            # Fall back to OpenAI on failure
            raise Exception(f"DeepSeek OCR failed: {response.text}")
    
    def _convert_to_ocr_result(self, deepseek_result: Dict) -> OCRResult:
        """Convert DeepSeek format to existing OCRResult format"""
        
        # Extract text blocks (matching existing format)
        blocks = []
        if 'result' in deepseek_result:
            text = deepseek_result['result']
            
            # Parse markdown sections as blocks
            import re
            sections = re.split(r'\n#+\s', text)
            
            for idx, section in enumerate(sections):
                if section.strip():
                    blocks.append(TextBlock(
                        text=section.strip(),
                        confidence=deepseek_result.get('confidence', 0.95),
                        bbox=None,  # DeepSeek provides these in grounding mode
                        block_type='text'
                    ))
        
        # Return in existing format
        return OCRResult(
            text=deepseek_result.get('result', ''),
            blocks=blocks,
            confidence=deepseek_result.get('confidence', 0.95),
            metadata={
                'engine': 'deepseek',
                'compression_ratio': deepseek_result.get('compression_ratio', 10.0),
                'vision_tokens': deepseek_result.get('vision_tokens', 100)
            }
        )
```

## 2. NEW FILE: `src/second_brain/capture/screenshot_buffer.py`
```python
"""
Screenshot buffering for batch processing
Works alongside existing capture_service.py
"""

import time
from collections import deque
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class BufferedFrame:
    path: str
    timestamp: datetime
    app_bundle_id: str

class ScreenshotBuffer:
    """Buffer screenshots for batch OCR processing"""
    
    def __init__(self, 
                 duration_seconds: int = 30,
                 max_size: int = 30):
        self.buffer = deque(maxlen=max_size)
        self.duration = duration_seconds
        self.last_flush = time.time()
    
    def add(self, frame_path: str, metadata: dict) -> bool:
        """Add frame to buffer, return True if should flush"""
        self.buffer.append(BufferedFrame(
            path=frame_path,
            timestamp=datetime.now(),
            app_bundle_id=metadata.get('app_bundle_id')
        ))
        
        return self.should_flush()
    
    def should_flush(self) -> bool:
        """Determine if buffer should be processed"""
        if not self.buffer:
            return False
            
        # Flush if buffer full or time elapsed
        time_elapsed = time.time() - self.last_flush
        return len(self.buffer) >= 30 or time_elapsed >= self.duration
    
    def get_batch(self) -> List[str]:
        """Get all buffered frames and clear buffer"""
        batch = [frame.path for frame in self.buffer]
        self.buffer.clear()
        self.last_flush = time.time()
        return batch
```

## 3. MODIFY: `src/second_brain/pipeline/processing_pipeline.py`
```python
# Add this to existing processing_pipeline.py

from ..ocr.openai_ocr import OpenAIVisionOCR
from ..ocr.deepseek_ocr import DeepSeekOCR  # NEW
from ..capture.screenshot_buffer import ScreenshotBuffer  # NEW

class ProcessingPipeline:
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        
        # Engine selection (backwards compatible)
        ocr_engine = config.get('ocr.engine', 'openai')
        
        if ocr_engine == 'openai':
            self.ocr = OpenAIVisionOCR(config)  # EXISTING
        elif ocr_engine == 'deepseek':
            self.ocr = DeepSeekOCR(config)  # NEW
        elif ocr_engine == 'hybrid':
            # Use both engines intelligently
            self.primary_ocr = DeepSeekOCR(config)
            self.fallback_ocr = OpenAIVisionOCR(config)
            self.ocr = self._hybrid_ocr  # Method that chooses
        else:
            self.ocr = OpenAIVisionOCR(config)  # Default to existing
        
        # Optional buffering for batch processing
        if ocr_engine in ['deepseek', 'hybrid'] and config.get('ocr.buffer_enabled'):
            self.buffer = ScreenshotBuffer(
                duration_seconds=config.get('ocr.buffer_duration', 30)
            )
        else:
            self.buffer = None
    
    def process_frame(self, frame_id: int, screenshot_path: str, metadata: dict):
        """EXISTING METHOD - Enhanced with optional buffering"""
        
        # If buffering enabled, add to buffer
        if self.buffer:
            should_flush = self.buffer.add(screenshot_path, metadata)
            
            if should_flush:
                # Process entire batch
                batch_paths = self.buffer.get_batch()
                results = self.ocr.process_batch(batch_paths)
                
                # Store all results
                for result in results:
                    self.db.insert_frame_text(frame_id, result)
                
                return  # Batch processed
            else:
                return  # Wait for more frames
        
        # Original single-frame processing (unchanged)
        result = self.ocr.process_frame(screenshot_path)
        self.db.insert_frame_text(frame_id, result)
    
    def _hybrid_ocr(self, screenshot_path: str) -> OCRResult:
        """Hybrid mode: Try DeepSeek first, fall back to OpenAI"""
        try:
            return self.primary_ocr.process_frame(screenshot_path)
        except Exception as e:
            logging.warning(f"DeepSeek failed, using OpenAI: {e}")
            return self.fallback_ocr.process_frame(screenshot_path)
```

## 4. NEW FILE: `src/second_brain/mcp_server/server.py`
```python
"""
MCP Server exposing SecondBrain functionality
Runs as separate service, doesn't interfere with main app
"""

from mcp.server import Server
from mcp.server.models import Tool
from ..database import Database  # Use EXISTING database!

class SecondBrainMCPServer:
    def __init__(self, db_path: str):
        self.server = Server("secondbrain-mcp")
        self.db = Database(db_path)  # Your existing database
        self._register_tools()
    
    def _register_tools(self):
        @self.server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="search_memory",
                    description="Search screen memory",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "semantic": {"type": "boolean"}
                        }
                    }
                ),
                Tool(
                    name="get_screenshot",
                    description="Get screenshot at timestamp",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "timestamp": {"type": "string"}
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            if name == "search_memory":
                # Use existing database method!
                return self.db.search_frames(
                    arguments['query'],
                    semantic=arguments.get('semantic', False)
                )
            elif name == "get_screenshot":
                return self.db.get_frame_by_timestamp(arguments['timestamp'])
    
    async def run(self):
        from mcp.server.transports import StreamableHTTPTransport
        transport = StreamableHTTPTransport(host="127.0.0.1", port=3000)
        await self.server.run(transport)
```

## 5. Configuration Updates
```json
// Add to your existing config
{
  "ocr": {
    "engine": "hybrid",           // openai, deepseek, or hybrid
    "buffer_enabled": true,       // Enable batching
    "buffer_duration": 30,        // Seconds before flush
    "deepseek_docker": true,      // Use Docker API
    "deepseek_docker_url": "http://localhost:8001",
    "deepseek_mode": "optimal"    // tiny, small, base, large, gundam, optimal
  }
}
```

## 6. CLI Additions
```python
# Add to your existing cli.py

@cli.command()
@click.option('--engine', type=click.Choice(['openai', 'deepseek', 'hybrid']))
@click.option('--reprocess', is_flag=True)
def switch_ocr(engine, reprocess):
    """Switch OCR engine (with optional reprocessing)"""
    config.set('ocr.engine', engine)
    
    if reprocess:
        # Reprocess recent frames with new engine
        frames = db.get_frames(since=datetime.now() - timedelta(days=1))
        
        if engine == 'deepseek':
            ocr = DeepSeekOCR(config)
            # Process in batches
            for batch in chunks(frames, 30):
                results = ocr.process_batch(batch)
                for frame_id, result in zip(batch, results):
                    db.update_frame_text(frame_id, result, engine='deepseek')

@cli.command()
def start_mcp():
    """Start MCP server (separate process)"""
    import asyncio
    server = SecondBrainMCPServer(config.db_path)
    asyncio.run(server.run())
```

## This implementation:
- ✅ Matches existing interfaces (OCRResult, TextBlock)
- ✅ Works with existing database
- ✅ Preserves all current functionality
- ✅ Adds new capabilities incrementally
- ✅ Allows gradual migration
- ✅ Provides fallback options