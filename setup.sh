#!/usr/bin/env bash
# ============================================================
# 1-CLICK SETUP SCRIPT FOR MACOS & LINUX
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SPORTS_ONLY=0
for arg in "$@"; do
    if [ "$arg" = "--sports-only" ]; then
        SPORTS_ONLY=1
        break
    fi
done

echo "=========================================================="
echo "      AI SHORTS GENERATOR - 1-CLICK SETUP (MACOS / LINUX) "
if [ "$SPORTS_ONLY" -eq 1 ]; then
    echo "      [Che do: Sports Only - Khong tai Ollama/Model AI]   "
fi
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
        echo "Vui long cai dat qua package manager: sudo apt update && sudo apt install -y python3 python3-venv"
    fi
    exit 1
fi

# 2. Kiem tra FFmpeg
echo -e "\n[2/5] Kiem tra FFmpeg..."
HAS_FFMPEG=0
if command -v ffmpeg &>/dev/null; then
    echo "  -> FFmpeg da co san tren he thong!"
    HAS_FFMPEG=1
else
    echo "  -> Chua tim thay FFmpeg."
    if [ "$OS_NAME" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            echo "  -> Dang tu dong cai dat FFmpeg bang Homebrew..."
            brew install ffmpeg && HAS_FFMPEG=1 || true
        else
            echo "CANH BAO: Vui long cai Homebrew (https://brew.sh) hoac go: brew install ffmpeg"
        fi
    else
        if command -v apt-get &>/dev/null; then
            echo "  -> Dang cai dat ffmpeg qua apt-get..."
            sudo apt-get update && sudo apt-get install -y ffmpeg && HAS_FFMPEG=1 || true
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

# 4. Kiem tra Ollama (neu khong phai SPORTS_ONLY)
if [ "$SPORTS_ONLY" -eq 0 ]; then
    echo -e "\n[4/5] Kiem tra Ollama (cho che do Offline Speech)..."
    if ! command -v ollama &>/dev/null; then
        echo "  -> Chua tim thay Ollama CLI."
        if [ "$OS_NAME" = "Darwin" ]; then
            if command -v brew &>/dev/null; then
                echo "  -> Dang cai dat Ollama qua Homebrew..."
                brew install ollama || true
            else
                echo "  -> Ban co the tai ung dung Ollama cho macOS tai: https://ollama.com/download/mac"
            fi
        else
            echo "  -> Dang cai dat Ollama tren Linux..."
            curl -fsSL https://ollama.com/install.sh | sh || true
        fi
    fi

    if command -v ollama &>/dev/null; then
        echo "  -> Khoi dong Ollama serve va kiem tra model qwen2.5:3b..."
        if ! curl -s -f http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
            ollama serve &>/dev/null &
            sleep 3
        fi
        ollama pull qwen2.5:3b || echo "Luu y: Kiem tra ket noi mang neu can tai model Ollama."
    fi
else
    echo -e "\n[4/5] Bo qua Ollama vi da chon che do --sports-only."
fi

# 5. Khoi tao .env va cac thu muc
echo -e "\n[5/5] Khoi tao cau hinh .env & thu muc..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  -> Da tao file .env mac dinh!"
fi
mkdir -p input output
chmod +x setup.sh run.sh 2>/dev/null || true

# 6. Final verification
ALL_PASSED=1
if [ ! -f ".venv/bin/python" ]; then
    echo "Loi: Khong tim thay Python venv!"
    ALL_PASSED=0
fi

if ! command -v ffmpeg &>/dev/null; then
    echo "Canh bao: FFmpeg chua duoc tim thay trong PATH."
    ALL_PASSED=0
fi

if [ "$ALL_PASSED" -eq 1 ]; then
    echo -e "\n=========================================================="
    echo "      CAI DAT HOAN TAT THANH CONG! (READY TO USE)         "
    echo "=========================================================="
    echo "Cach su dung ngay:"
    echo "  ./run.sh 'video.mp4' 3 speech"
    echo "  ./run.sh 'match.mov' 10 sports"
    echo "  ./run.sh 'https://www.youtube.com/watch?v=VIDEO_ID' 5"
    echo "=========================================================="
    exit 0
else
    echo -e "\n=========================================================="
    echo "  CAI DAT CHUA HOAN TAT! Vui long kiem tra cac canh bao tren."
    echo "=========================================================="
    exit 1
fi
