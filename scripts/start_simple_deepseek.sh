#!/bin/bash
# Simple startup using DeepSeek OCR via local MLX backend (Apple Silicon)
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "❌ Virtualenv not found at $VENV_DIR. Run scripts/install.sh first." >&2
  exit 1
fi

source "$VENV_DIR/bin/activate"

echo "Starting Second Brain (DeepSeek MLX, simple defaults)..."
exec second-brain start --ocr-engine deepseek --deepseek-backend mlx

