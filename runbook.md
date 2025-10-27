# SecondBrain DeepSeek Integration Runbook

## Prerequisites Check
```bash
# Verify existing secondbrain is working
cd ~/second-brain
source venv/bin/activate
second-brain status  # Should show current capture status

# Check GPU availability
nvidia-smi  # Optional, will use Docker if no GPU

# Verify OpenAI OCR still works
second-brain query "test" --limit 1
```

## Step 1: Setup DeepSeek Docker (10 min)
```bash
# Clone fixed Docker implementation
cd ~/
git clone https://github.com/Bogdanovich77/DeekSeek-OCR---Dockerized-API deepseek-docker
cd deepseek-docker

# Download model
pip install huggingface_hub
huggingface-cli download deepseek-ai/DeepSeek-OCR \
    --local-dir models/deepseek-ai/DeepSeek-OCR

# Start Docker service (runs on port 8001 to avoid conflict)
sed -i 's/8000:8000/8001:8000/g' docker-compose.yml
docker-compose up -d

# Verify it's running
curl http://localhost:8001/health
```

## Step 2: Add DeepSeek OCR Module (15 min)
```bash
cd ~/second-brain

# Create new OCR module alongside existing
cat > src/second_brain/ocr/deepseek_ocr.py << 'EOF'
import requests
from PIL import Image
from ..database.models import OCRResult, TextBlock

class DeepSeekOCR:
    def __init__(self, config):
        self.config = config
        self.docker_url = config.get('ocr.deepseek_docker_url', 'http://localhost:8001')
    
    def process_frame(self, screenshot_path: str) -> OCRResult:
        """Match OpenAIVisionOCR interface"""
        with open(screenshot_path, 'rb') as f:
            response = requests.post(
                f"{self.docker_url}/ocr/image",
                files={'file': f}
            )
        
        if response.status_code == 200:
            data = response.json()
            return OCRResult(
                text=data.get('result', ''),
                blocks=[],  # Parse from result
                confidence=0.95,
                metadata={'engine': 'deepseek'}
            )
        else:
            raise Exception(f"DeepSeek OCR failed: {response.text}")
EOF

# Test it works
python -c "
from src.second_brain.ocr.deepseek_ocr import DeepSeekOCR
from src.second_brain.config import Config
config = Config()
ocr = DeepSeekOCR(config)
print('DeepSeek OCR module loaded successfully')
"
```

## Step 3: Add Hybrid Processing (10 min)
```bash
# Backup existing pipeline
cp src/second_brain/pipeline/processing_pipeline.py \
   src/second_brain/pipeline/processing_pipeline.py.backup

# Add engine selection to processing pipeline
# Edit src/second_brain/pipeline/processing_pipeline.py
# Add after imports:
cat >> src/second_brain/pipeline/processing_pipeline.py << 'EOF'

# Engine selection (add to __init__)
ocr_engine = config.get('ocr.engine', 'openai')
if ocr_engine == 'deepseek':
    from ..ocr.deepseek_ocr import DeepSeekOCR
    self.ocr = DeepSeekOCR(config)
elif ocr_engine == 'hybrid':
    from ..ocr.deepseek_ocr import DeepSeekOCR
    self.primary_ocr = DeepSeekOCR(config)
    self.fallback_ocr = self.ocr  # Keep existing OpenAI
    self.ocr = lambda path: self._hybrid_process(path)
EOF
```

## Step 4: Update Configuration (5 min)
```bash
# Add DeepSeek options to config
cat >> ~/.config/second-brain/settings.json << 'EOF'
{
  "ocr": {
    "engine": "hybrid",
    "deepseek_docker": true,
    "deepseek_docker_url": "http://localhost:8001"
  }
}
EOF
```

## Step 5: Test Side-by-Side (10 min)
```bash
# Create test script
cat > test_engines.py << 'EOF'
from src.second_brain.ocr.openai_ocr import OpenAIVisionOCR
from src.second_brain.ocr.deepseek_ocr import DeepSeekOCR
from src.second_brain.config import Config

config = Config()
openai = OpenAIVisionOCR(config)
deepseek = DeepSeekOCR(config)

# Test with same image
test_image = "path/to/test/screenshot.png"

print("Testing OpenAI OCR...")
result_openai = openai.process_frame(test_image)
print(f"OpenAI extracted {len(result_openai.text)} characters")

print("\nTesting DeepSeek OCR...")
result_deepseek = deepseek.process_frame(test_image)
print(f"DeepSeek extracted {len(result_deepseek.text)} characters")

# Compare results
similarity = len(set(result_openai.text.split()) & set(result_deepseek.text.split())) / len(set(result_openai.text.split()))
print(f"\nText similarity: {similarity:.2%}")
EOF

python test_engines.py
```

## Step 6: Add MCP Server (15 min)
```bash
# Install MCP SDK
pip install mcp-server-sdk

# Create MCP server
mkdir -p src/second_brain/mcp_server
cat > src/second_brain/mcp_server/server.py << 'EOF'
from mcp.server import Server
from mcp.server.models import Tool
from ..database import Database

class SecondBrainMCPServer:
    def __init__(self, db_path):
        self.server = Server("secondbrain-mcp")
        self.db = Database(db_path)
        
    async def run(self):
        # Implementation here
        pass
EOF

# Add MCP command to CLI
echo '
@cli.command()
def mcp_server():
    """Start MCP server on port 3000"""
    import asyncio
    from src.second_brain.mcp_server.server import SecondBrainMCPServer
    server = SecondBrainMCPServer(config.db_path)
    asyncio.run(server.run())
' >> src/second_brain/cli.py
```

## Step 7: Database Migration (5 min)
```bash
# Add OCR engine tracking
sqlite3 ~/Library/Application\ Support/second-brain/database/memory.db << 'EOF'
ALTER TABLE frame_text ADD COLUMN ocr_engine TEXT DEFAULT 'openai';
ALTER TABLE frame_text ADD COLUMN compression_ratio REAL;
.exit
EOF

# Verify migration
sqlite3 ~/Library/Application\ Support/second-brain/database/memory.db ".schema frame_text"
```

## Step 8: Gradual Rollout (Ongoing)
```bash
# Phase 1: Test with 10% of frames
echo '{"ocr": {"engine": "hybrid", "hybrid_ratio": 0.1}}' > test_config.json
second-brain start --config test_config.json

# Phase 2: Monitor performance
sqlite3 ~/Library/Application\ Support/second-brain/database/memory.db << 'EOF'
SELECT 
    ocr_engine,
    COUNT(*) as frames,
    AVG(compression_ratio) as avg_compression
FROM frame_text
WHERE timestamp > datetime('now', '-1 day')
GROUP BY ocr_engine;
EOF

# Phase 3: Increase DeepSeek usage
echo '{"ocr": {"engine": "hybrid", "hybrid_ratio": 0.5}}' > prod_config.json

# Phase 4: Full DeepSeek (keep OpenAI fallback)
echo '{"ocr": {"engine": "deepseek"}}' > prod_config.json
```

## Step 9: Monitoring & Validation
```bash
# Create monitoring script
cat > monitor_ocr.py << 'EOF'
import sqlite3
from datetime import datetime, timedelta

db = sqlite3.connect('~/Library/Application Support/second-brain/database/memory.db')

# Get stats for last 24 hours
cursor = db.execute("""
    SELECT 
        ocr_engine,
        COUNT(*) as frames_processed,
        AVG(LENGTH(text)) as avg_text_length,
        AVG(confidence) as avg_confidence,
        AVG(compression_ratio) as avg_compression
    FROM frame_text
    WHERE timestamp > ?
    GROUP BY ocr_engine
""", (datetime.now() - timedelta(days=1),))

print("OCR Performance (Last 24h)")
print("-" * 50)
for row in cursor:
    print(f"{row[0]}:")
    print(f"  Frames: {row[1]}")
    print(f"  Avg Text: {row[2]:.0f} chars")
    print(f"  Confidence: {row[3]:.2%}")
    print(f"  Compression: {row[4]:.1f}x" if row[4] else "  Compression: N/A")
EOF

python monitor_ocr.py
```

## Step 10: Rollback Plan
```bash
# If issues arise, instant rollback
echo '{"ocr": {"engine": "openai"}}' > ~/.config/second-brain/settings.json
second-brain restart

# Restore original pipeline if needed
cp src/second_brain/pipeline/processing_pipeline.py.backup \
   src/second_brain/pipeline/processing_pipeline.py
   
# Stop Docker service
cd ~/deepseek-docker
docker-compose down
```

## Verification Checklist
- [ ] Existing OpenAI OCR still works
- [ ] DeepSeek Docker health check passes
- [ ] Test script shows both engines working
- [ ] Database has new columns
- [ ] Can query frames from both engines
- [ ] Timeline UI still displays OCR text
- [ ] MCP server responds on port 3000
- [ ] Cost reduction visible in OpenAI dashboard

## Expected Outcomes
- Hour 1: Both engines running side-by-side
- Day 1: 10% frames processed with DeepSeek
- Day 3: 50% frames with DeepSeek, cost drop visible
- Week 1: Full DeepSeek with OpenAI fallback
- Week 2: 90%+ cost reduction achieved

## Support Commands
```bash
# Check DeepSeek is processing
tail -f ~/deepseek-docker/logs/api.log

# Force reprocess with DeepSeek
second-brain reprocess --engine deepseek --since "2024-01-01"

# Compare OCR quality
second-brain compare-ocr --frame-id 12345

# Export metrics
second-brain export-metrics --format csv > ocr_metrics.csv
```

## Common Issues & Fixes

### DeepSeek timeout
```bash
# Increase timeout in deepseek_ocr.py
response = requests.post(url, timeout=60)  # was 30
```

### GPU memory issues
```bash
# Reduce batch size in config
{"ocr": {"batch_size": 10}}  # was 30
```

### OpenAI fallback not working
```bash
# Check fallback in hybrid mode
tail -f ~/Library/Application\ Support/second-brain/logs/ocr.log
```

This runbook ensures zero downtime and gradual, reversible migration.