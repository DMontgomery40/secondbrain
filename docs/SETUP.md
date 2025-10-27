# Second Brain - Setup Guide

## Prerequisites

- macOS (required for screen capture APIs)
- Python 3.11 or higher
- OpenAI API key (for OpenAI OCR engine) OR Docker (for DeepSeek OCR engine)
- Node.js 20 or higher (for building the timeline UI)

## Installation

### 1. Clone or Navigate to Project

```bash
cd /Users/gregcmartin/Desktop/Second\ Brain
```

### 2. Create Python Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Package in Development Mode

```bash
pip install -e .
```

### 5. Verify Installation

```bash
second-brain --help
```

### 6. Build the Timeline UI (Optional but recommended)

```bash
cd web/timeline
npm install
npm run build
cd ../..
```

## Configuration

### Environment Variables

The `.env` file has been created with your OpenAI API key. The system will automatically load it.

To modify settings, edit `~/.config/second-brain/settings.json` or use the default configuration.

### Default Configuration

You can edit these settings via:
1. **Timeline UI Settings Panel (⚙️)** - Recommended, provides validation and live stats
2. Manual edit: `~/.config/second-brain/settings.json`

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
    "engine": "openai",              // "openai" or "deepseek"
    "model": "gpt-5",
    "api_key_env": "OPENAI_API_KEY",
    "batch_size": 5,
    "max_retries": 3,
    "rate_limit_rpm": 50,
    "include_semantic_context": true,
    "timeout_seconds": 30,
    // DeepSeek-specific options:
    "deepseek_docker": true,
    "deepseek_docker_url": "http://localhost:8001",
    "deepseek_mode": "optimal",      // tiny|small|base|large|optimal
    "buffer_duration": 30
  },
  "storage": {
    "retention_days": 90,
    "compression": true
  },
  "embeddings": {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "dimension": 384,
    "enabled": true
  },
  "context7": {
    "enabled": true,
    "api_key": "",
    "base_url": "https://api.context7.dev"
  }
}
```

## Data Storage

All data is stored locally in:
```
~/Library/Application Support/second-brain/
├── frames/          # Screenshot storage
├── database/        # SQLite database
├── embeddings/      # Vector embeddings
├── logs/           # Application logs
└── config/         # Configuration files
```

## Usage

### Start the Capture Service

```bash
# Start with default OCR engine (configured in settings)
second-brain start

# Or specify OCR engine on startup
second-brain start --ocr-engine openai
second-brain start --ocr-engine deepseek

# Adjust FPS for cost control
second-brain start --fps 0.5
```

### Check Status

```bash
second-brain status
```

### Check System Health

```bash
second-brain health
```

### Search Your Memory

```bash
# Basic text search
second-brain query "search term"

# Search with app filter
second-brain query "search term" --app "VSCode"

# Search with date range
second-brain query "search term" --from "2025-10-20" --to "2025-10-26"

# Semantic search
second-brain query "search term" --semantic
```

### Launch the Timeline UI

```bash
# Start API + UI (opens browser)
second-brain timeline --host 127.0.0.1 --port 8000
```

The Timeline UI includes:
- **OCR Engine Toggle**: Quick switch between OpenAI and DeepSeek in sidebar
- **Settings Panel (⚙️)**: Comprehensive settings management with live stats
- Application/date filters for focused search
- Horizontal timeline scrubber grouped by day
- Live screenshot preview with OCR text blocks

### Start the MCP Server

Expose your visual memory to AI assistants:

```bash
second-brain mcp-server
```

Configure in Claude Desktop (`~/.config/claude/config.json`):
```json
{
  "mcpServers": {
    "secondbrain": {
      "command": "second-brain",
      "args": ["mcp-server"]
    }
  }
}
```

Available tools: `search_memory`, `get_screenshot`, `get_frames_by_time`, `get_app_activity`, `analyze_activity`

### Stop the Service

```bash
second-brain stop
```

## Testing the OCR

### Test OpenAI OCR

```python
import asyncio
from pathlib import Path
from second_brain.ocr.openai_ocr import OpenAIOCR

async def test_openai():
    ocr = OpenAIOCR()

    # Take a test screenshot
    import subprocess
    test_path = Path("/tmp/test_screenshot.png")
    subprocess.run(["screencapture", "-x", str(test_path)])

    # Extract text
    results = await ocr.extract_text(test_path, "test-frame")

    for block in results:
        print(f"Text: {block['text'][:100]}...")
        print(f"Type: {block['block_type']}")
        print(f"Confidence: {block['confidence']}")
        if 'semantic_context' in block:
            print(f"Context: {block['semantic_context']}")

asyncio.run(test_openai())
```

### Test DeepSeek OCR

First, ensure DeepSeek Docker is running (see DeepSeek Setup section below).

```python
import asyncio
from pathlib import Path
from second_brain.ocr.deepseek_ocr import DeepSeekOCR

async def test_deepseek():
    ocr = DeepSeekOCR()

    # Take a test screenshot
    import subprocess
    test_path = Path("/tmp/test_screenshot.png")
    subprocess.run(["screencapture", "-x", str(test_path)])

    # Extract text
    results = await ocr.extract_text(test_path, "test-frame")

    for block in results:
        print(f"Text: {block['text'][:100]}...")
        print(f"Type: {block['block_type']}")
        print(f"Confidence: {block['confidence']}")

asyncio.run(test_deepseek())
```

## Troubleshooting

### API Key Issues

If you get an API key error:
1. Check that `.env` file exists in the project root
2. Verify the `OPENAI_API_KEY` is set correctly
3. Ensure you're running from the project directory or the `.env` is loaded

### Permission Issues

macOS may require permissions for:
- Screen Recording (System Preferences → Security & Privacy → Screen Recording)
- Accessibility (System Preferences → Security & Privacy → Accessibility)

### Rate Limiting

If you hit rate limits:
1. Reduce `capture.fps` in configuration
2. Increase `ocr.rate_limit_rpm` if your API tier allows
3. Check OpenAI API usage dashboard

## Next Steps

1. Start the capture service with `second-brain start`.
2. Run `second-brain status` after a few minutes to verify frames and text blocks are recorded.
3. Build and launch the timeline UI (`npm run build` then `second-brain timeline`) for visual exploration.
4. Configure launchd using `scripts/install.sh` if you want the service to start automatically on login.

## Cost Estimates

### OpenAI GPT-5 OCR

Based on 1 fps capture rate:
- ~3,600 screenshots per hour
- ~86,400 screenshots per day (24/7 capture)
- At $0.01 per 1,000 images (GPT-5 pricing): ~$0.86/day
- Recommended: Use lower fps (0.5 fps) for ~$0.43/day

### DeepSeek OCR

- **100% FREE** - Runs locally in Docker
- No API costs, no rate limits
- 10-20x compression via batch processing
- Slightly lower accuracy than GPT-5, but excellent for most use cases

**Recommendation:** Start with DeepSeek for cost-free operation. Switch to OpenAI for sessions requiring maximum accuracy or semantic context extraction.

Adjust `capture.fps` and `ocr.engine` in configuration to balance costs and quality.

---

## DeepSeek OCR Setup (Optional)

To use the free DeepSeek OCR engine:

### 1. Clone the Dockerized DeepSeek OCR

```bash
# Clone the repository with Docker support
git clone https://github.com/Bogdanovich77/DeekSeek-OCR---Dockerized-API deepseek-docker
cd deepseek-docker
```

### 2. Configure Port (Avoid Conflicts)

Edit `docker-compose.yml` to use port 8001 (Second Brain API uses 8000):

```bash
sed -i '' 's/8000:8000/8001:8000/g' docker-compose.yml
```

Or manually edit:
```yaml
ports:
  - "8001:8000"  # Changed from 8000:8000
```

### 3. Download the Model (Optional - Can Skip for Testing)

The DeepSeek OCR model is large (~3GB). You can skip this initially and test with the demo model:

```bash
# If you want the full model:
pip install huggingface_hub
huggingface-cli download deepseek-ai/DeepSeek-OCR --local-dir models/

# Otherwise, the Docker image includes a demo model
```

### 4. Start the Docker Service

```bash
docker-compose up -d
```

Verify it's running:
```bash
curl http://localhost:8001/health
# Should return: {"status": "healthy"}
```

### 5. Configure Second Brain

Three ways to enable DeepSeek:

**A. Via Timeline UI Settings Panel (Easiest):**
1. Open Timeline: `second-brain timeline`
2. Click the ⚙️ settings button
3. Go to "OCR" tab
4. Change "Engine" to "deepseek"
5. Click "Save Settings"

**B. Via CLI:**
```bash
second-brain start --ocr-engine deepseek
```

**C. Via Config File:**
Edit `~/.config/second-brain/settings.json`:
```json
{
  "ocr": {
    "engine": "deepseek",
    "deepseek_docker_url": "http://localhost:8001"
  }
}
```

### 6. Verify DeepSeek is Working

Check the Settings Panel stats bar - it should show "DeepSeek: Healthy" if the connection is working.

Or test manually:
```bash
# Start capture with DeepSeek
second-brain start --ocr-engine deepseek

# Check status - should show frames being processed
second-brain status

# Check logs
tail -f ~/Library/Application\ Support/second-brain/logs/ocr.log
```

### Troubleshooting DeepSeek

**Docker not running:**
```bash
docker ps  # Should show deepseek container
docker-compose up -d  # Restart if needed
```

**Port conflict (8001 already in use):**
Edit `docker-compose.yml` to use a different port (e.g., 8002) and update Second Brain config:
```json
{
  "ocr": {
    "deepseek_docker_url": "http://localhost:8002"
  }
}
```

**Low accuracy:**
Try different DeepSeek modes in Settings Panel → OCR → DeepSeek Mode:
- `tiny`: Fastest, lowest accuracy
- `small`: Balanced
- `base`: Good accuracy
- `large`: Best accuracy, slower
- `optimal`: Automatic selection (recommended)

---

## Advanced: Context7 Integration

Second Brain can fetch documentation for libraries on-demand via Context7:

### Setup

1. Get a Context7 API key from https://context7.dev
2. Configure via Settings Panel (⚙️) → Context7 tab
3. Or edit config:
```json
{
  "context7": {
    "enabled": true,
    "api_key": "ctx7sk-..."
  }
}
```

### Usage

```bash
# Search for library documentation
second-brain docs search "react" --save react.md

# Fetch specific library by ID
second-brain docs fetch "/facebook/react" --topic "hooks"

# Batch fetch multiple libraries
second-brain docs batch libraries.json --output-dir docs/
```

Where `libraries.json` contains:
```json
{
  "libraries": [
    {"id": "/facebook/react", "topic": "hooks"},
    {"id": "/python/fastapi", "topic": "async"}
  ]
}
```

---

## Summary

You now have a complete Second Brain setup with:
- ✅ Dual OCR engines (OpenAI + DeepSeek)
- ✅ Comprehensive settings management via GUI
- ✅ MCP server for AI assistant integration
- ✅ Timeline UI for visual exploration
- ✅ Optional Context7 documentation fetching

**Next steps:**
1. Choose your OCR engine (DeepSeek for free, OpenAI for max accuracy)
2. Start capturing: `second-brain start`
3. Explore your memory: `second-brain timeline`
4. Integrate with AI: `second-brain mcp-server`
