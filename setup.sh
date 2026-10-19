#!/usr/bin/env bash
# ============================================================
# 1-CLICK SETUP SCRIPT FOR MACOS & LINUX
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "      AI SHORTS GENERATOR - 1-CLICK SETUP (MACOS / LINUX) "
echo "=========================================================="

OS_NAME="$(uname -s)"
ARCH_NAME="$(uname -m)"
echo "Detected OS: $OS_NAME ($ARCH_NAME)"

# 1. Kiem tra Python 3
echo -e "\n[1/5] Kiem tra phien ban Python 3..."
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            echo "  -> Tim thay Python: $PYTHON_CMD (phien ban $VER)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Khong tim thay Python >= 3.10 tren may!"
    if [ "$OS_NAME" = "Darwin" ]; then
        echo "Vui long cai dat qua Homebrew: brew install python@3.12"
    else
        echo "Vui long cai dat qua package manager (apt/dnf/pacman): sudo apt install python3 python3-venv"
    fi
    exit 1
fi

# 2. Kiem tra FFmpeg
echo -e "\n[2/5] Kiem tra FFmpeg..."
if command -v ffmpeg &>/dev/null; then
    echo "  -> FFmpeg da co san tren he thong!"
else
    echo "  -> Chua tim thay FFmpeg."
    if [ "$OS_NAME" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            echo "  -> Dang tu dong cai dat FFmpeg bang Homebrew..."
            brew install ffmpeg
        else
            echo "CANH BAO: Vui long cai Homebrew (https://brew.sh) hoac go: brew install ffmpeg"
        fi
    else
        if command -v apt-get &>/dev/null; then
            echo "  -> Dang cai dat ffmpeg qua apt-get..."
            sudo apt-get update && sudo apt-get install -y ffmpeg
        fi
    fi
fi

# 3. Tao moi truong ao (.venv) va cai dat thu vien
echo -e "\n[3/5] Khoi tao Virtual Environment (.venv) & cai dat thu vien AI..."
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements-local.txt

# 4. Kiem tra Ollama va tai model qwen2.5:3b (Offline Mode)
echo -e "\n[4/5] Kiem tra Ollama (cho che do Offline)..."
if ! command -v ollama &>/dev/null; then
    echo "  -> Chua tim thay Ollama CLI."
    if [ "$OS_NAME" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            echo "  -> Dang cai dat Ollama qua Homebrew..."
            brew install ollama
        else
            echo "  -> Ban co the tai ung dung Ollama cho macOS tai: https://ollama.com/download/mac"
        fi
    else
        echo "  -> Dang cai dat Ollama tren Linux..."
        curl -fsSL https://ollama.com/install.sh | sh || true
    fi
fi

if command -v ollama &>/dev/null; then
    echo "  -> Khoi dong Ollama serve va tai model qwen2.5:3b..."
    if ! pgrep -x "ollama" > /dev/null; then
        ollama serve &>/dev/null &
        sleep 3
    fi
    ollama pull qwen2.5:3b || echo "Luu y: Kiem tra ket noi mang neu can tai model Ollama."
fi

# 5. Khoi tao .env va cac thu muc
echo -e "\n[5/5] Khoi tao cau hinh .env & thu muc..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  -> Da tao file .env mac dinh!"
fi
mkdir -p input output
chmod +x setup.sh run.sh 2>/dev/null || true

echo -e "\n=========================================================="
echo "      CAI DAT HOAN TAT THANH CONG! (READY TO USE)         "
echo "=========================================================="
echo "Cach su dung ngay:"
echo "  ./run.sh 'video.mp4' 3 speech"
echo "  ./run.sh 'https://www.youtube.com/watch?v=VIDEO_ID' 5"
echo "=========================================================="
