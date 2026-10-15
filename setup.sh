#!/usr/bin/env bash
# ============================================================
# 1-CLICK SETUP SCRIPT FOR LINUX / MACOS
# ============================================================
set -e

echo "=== [1/4] Checking Python ==="
PYTHON_CMD="python3"
if ! command -v python3 &>/dev/null; then
    PYTHON_CMD="python"
fi
$PYTHON_CMD -V

echo "=== [2/4] Setting up virtual environment (.venv) ==="
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements-local.txt

echo "=== [3/4] Checking Ollama ==="
if command -v ollama &>/dev/null; then
    echo "Ollama is installed. Pulling qwen2.5:3b..."
    ollama pull qwen2.5:3b || true
else
    echo "Notice: Ollama not found. Install it via 'curl -fsSL https://ollama.com/install.sh | sh' if you want 100% offline mode."
fi

echo "=== [4/4] Environment file ==="
if [ ! -f ".env" ]; then
    cp .env.example .env
fi
mkdir -p input output

echo "=== Setup complete! ==="
echo "Usage: ./run.sh 'video.mp4' 3"
