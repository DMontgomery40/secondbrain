#!/bin/bash
# Original simple startup using OpenAI GPT-5 Vision OCR
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
  echo "⚠️  OPENAI_API_KEY is not set. Export it or add to .env before running." >&2
fi

echo "Starting Second Brain (OpenAI GPT-5, simple defaults)..."
exec second-brain start --ocr-engine openai

