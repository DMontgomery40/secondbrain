#!/bin/bash
# Start Second Brain with all features: DeepSeek OCR + local reranker + Timeline UI
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "❌ Virtualenv not found at $VENV_DIR. Run scripts/install.sh first." >&2
  exit 1
fi

source "$VENV_DIR/bin/activate"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "⚠️  OPENAI_API_KEY is not set. Required for summarization (optional)." >&2
fi

echo "Starting Second Brain (DeepSeek OCR + local reranker + Timeline UI)..."
echo "Models: DeepSeek-OCR-8bit (3.85 GB) + bge-reranker-large (2.24 GB)"

# Optionally start Timeline UI in background if built and uvicorn available
UI_DIST="$ROOT_DIR/web/timeline/dist"
if [[ -d "$UI_DIST" ]]; then
  if python - <<'PY'
try:
    import uvicorn  # noqa
    print('OK')
except Exception:
    pass
PY
  then
    echo "Launching Timeline UI at http://127.0.0.1:8000 (background)..."
    # Run in background; suppress browser open
    nohup second-brain timeline --port 8000 --no-open >/dev/null 2>&1 &
  else
    echo "uvicorn not available; skipping UI start"
  fi
else
  echo "Timeline UI not built (web/timeline/dist missing); skipping UI start"
fi

exec second-brain start \
  --ocr-engine deepseek \
  --embeddings-provider sbert \
  --enable-reranker
