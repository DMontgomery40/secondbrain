#!/bin/bash
# Simple startup using DeepSeek OCR via MLX (Apple Silicon, 3.85 GB download on first run)
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "❌ Virtualenv not found at $VENV_DIR. Run scripts/install.sh first." >&2
  exit 1
fi

source "$VENV_DIR/bin/activate"

echo "Starting Second Brain (DeepSeek OCR - local, multimodal)..."
echo "Note: mlx-community/DeepSeek-OCR-8bit (3.85 GB) will download on first run"
exec second-brain start --ocr-engine deepseek

