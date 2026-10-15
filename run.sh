#!/usr/bin/env bash
# ============================================================
# 1-CLICK RUNNER FOR LINUX / MACOS
# ============================================================
if [ -z "$1" ]; then
    echo "Usage: ./run.sh <video_path_or_url> [num_clips] [type: auto/speech/sports]"
    exit 0
fi

# Activate venv
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Ensure ollama is running if installed
if command -v ollama &>/dev/null; then
    if ! pgrep -x "ollama" > /dev/null; then
        echo "[Ollama] Starting Ollama serve in background..."
        ollama serve &>/dev/null &
        sleep 2
    fi
fi

python main.py "$@"
