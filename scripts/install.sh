#!/bin/bash
# Installation script for Second Brain (macOS + MLX DeepSeek)
set -euo pipefail

echo "🧠 Second Brain Installation"
echo "============================"

# macOS check
if [[ "$OSTYPE" != darwin* ]]; then
  echo "❌ This script supports macOS only." >&2
  exit 1
fi

# Python check
if ! command -v python3.11 >/dev/null 2>&1; then
  echo "❌ Python 3.11 is required. Install with: brew install python@3.11" >&2
  exit 1
fi
echo "✓ Python 3.11 found"

# Venv
VENV_DIR=.venv
echo "Creating virtualenv at $VENV_DIR ..."
python3.11 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -V
pip install -U pip wheel setuptools

echo "Installing Python dependencies (MCP temporarily disabled in requirements.txt)..."
pip install -r requirements.txt
pip install -e .

# Create data dirs
echo "Creating data directories..."
mkdir -p "$HOME/Library/Application Support/second-brain/"{frames,database,embeddings,logs,config}
echo "✓ Directories ready"

# UI build (optional)
read -p "Build Timeline UI now (npm install && npm run build)? [Y/n] " -r REPLY
if [[ -z "$REPLY" || "$REPLY" =~ ^[Yy]$ ]]; then
  pushd web/timeline >/dev/null
  npm install
  npm run build
  popd >/dev/null
fi

echo
echo "Screen Recording permission (Required):"
echo "  System Settings → Privacy & Security → Screen Recording"
echo "  Enable for your Terminal/iTerm and for $VENV_DIR/bin/python"
echo "Accessibility (Recommended): Privacy & Security → Accessibility"

echo
echo "✅ Installation complete!"
echo "Next:"
echo "  1) source $VENV_DIR/bin/activate"
echo "  2) Run one of the startup helpers:"
echo "     • scripts/start_simple_deepseek.sh        # DeepSeek MLX (local)"
echo "     • scripts/start_og_openai.sh             # Original GPT‑5 Vision"
echo "     • scripts/start_everything_on.sh         # DeepSeek MLX + OpenAI embeddings + reranker (UI auto if built)"
echo "  3) Or manual commands:"
echo "     • second-brain start --ocr-engine deepseek       (MLX model downloads on first run)"
echo "     • second-brain timeline --port 8000 --no-open    (if UI built)"
echo "  4) See docs/SETUP.md for more details."
