# Context7 MCP Integration

## What Was Installed

Context7 MCP has been successfully integrated into your SecondBrain CLI on the `codex-version` branch.

### 1. MCP Configuration (Cursor)
- **Location**: `~/.cursor/mcp.json`
- **Status**: ✅ Configured and fixed
- **API Key**: Configured with your Context7 API key
- **Usage**: Available in Cursor IDE through MCP tools

### 2. CLI Integration (SecondBrain)

#### Added Files:
- `src/second_brain/context7_client.py` - Context7 HTTP client wrapper
- `src/second_brain/embeddings/` - Embedding service for semantic search
- Updated `requirements.txt` with MCP and httpx dependencies
- Updated `config.py` with Context7 configuration

#### New CLI Commands:
```bash
# Search for a library and fetch its documentation
second-brain docs search "deepseek-ocr"
second-brain docs search "modelcontextprotocol python-sdk" --topic "server"
second-brain docs search "fastapi" --save fastapi-docs.md

# Fetch documentation by exact library ID
second-brain docs fetch "/deepseek-ai/deepseek-ocr"
second-brain docs fetch "/modelcontextprotocol/python-sdk" --topic "server"

# Batch fetch multiple libraries from JSON file
second-brain docs batch docs-libraries.json --output-dir docs-output
```

## How to Use

### In Cursor IDE
Context7 is now available through MCP. After restarting Cursor, you can use Context7 tools to:
- Resolve library names to Context7 IDs
- Fetch documentation for libraries
- Get up-to-date docs for your development

### In SecondBrain CLI

1. **Activate the virtual environment:**
```bash
cd /Users/davidmontgomery/secondbrain
source venv/bin/activate
```

2. **Search and download documentation:**
```bash
# Search for DeepSeek OCR docs
second-brain docs search "deepseek-ocr" --save docs/deepseek-ocr.md

# Search for MCP Python SDK docs
second-brain docs search "modelcontextprotocol python-sdk" --topic "server" --save docs/mcp-server.md
```

3. **Batch download multiple libraries:**
```bash
# Create a libraries file (already created: docs-libraries.json)
second-brain docs batch docs-libraries.json --output-dir docs/
```

## Example Libraries File

The file `docs-libraries.json` contains:
```json
[
  {
    "name": "deepseek-ai deepseek-ocr"
  },
  {
    "name": "modelcontextprotocol python-sdk",
    "topic": "server"
  },
  {
    "name": "fastapi",
    "topic": "routing"
  }
]
```

## Configuration

### Context7 API Key
Set in `~/.env` or configure in `config.py`:
```bash
export CONTEXT7_API_KEY="ctx7sk-44085384-6ccc-4905-9c14-a5f723022f72"
```

### SecondBrain Config
The Context7 configuration was added to `src/second_brain/config.py`:
```python
"context7": {
    "api_key": os.getenv("CONTEXT7_API_KEY", "..."),
    "enabled": True,
}
```

## Testing

Run the help command to see all available options:
```bash
second-brain docs --help
second-brain docs search --help
second-brain docs fetch --help
second-brain docs batch --help
```

## Benefits

1. **Always Up-to-Date**: Fetch the latest library documentation on demand
2. **Focused Context**: Request specific topics within libraries
3. **Batch Processing**: Download multiple libraries at once
4. **Integration**: Use Context7 both in Cursor and from command line
5. **Local Storage**: Save documentation files locally for offline reference

## Next Steps

As per your `CLAUDE.md`, use Context7 to fetch docs for:
- `/websites/modelcontextprotocol_io_specification` - MCP spec
- `/deepseek-ai/deepseek-ocr` - DeepSeek OCR implementation  
- `/modelcontextprotocol/python-sdk` - MCP Python SDK

These will help with implementing the DeepSeek OCR integration and MCP server for SecondBrain.

## Branches

- `main` - Original codebase
- `deepseek-ocr` - For DeepSeek OCR integration work
- `codex-version` ⭐ (current) - Context7 MCP integrated

## Installation Complete! ✅

Context7 MCP is now fully integrated into both Cursor and your SecondBrain CLI.

