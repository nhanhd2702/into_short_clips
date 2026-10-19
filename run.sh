#!/usr/bin/env bash
# ============================================================
# 1-CLICK RUNNER FOR MACOS & LINUX
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -z "$1" ]; then
    echo "=========================================================="
    echo "       AI SHORTS GENERATOR - HUONG DAN SU DUNG (MACOS)    "
    echo "=========================================================="
    echo "Cu phap:"
    echo "  ./run.sh <video_path_or_url> [options]"
    echo ""
    echo "Vi du:"
    echo "  1. Cat video tro chuyen / podcast (mac dinh Pillarbox Blur 1080x1920):"
    echo "     ./run.sh 'podcast.mp4' --type speech --num-clips 3"
    echo ""
    echo "  2. Cat video the thao / hanh dong (Audio Energy Peaks):"
    echo "     ./run.sh 'match.mov' --type sports --num-clips 10 --duration 45"
    echo ""
    echo "  3. Cat video tu link YouTube truc tiep:"
    echo "     ./run.sh 'https://www.youtube.com/watch?v=VIDEO_ID' --num-clips 5"
    echo ""
    echo "  4. Cat crop bam mat nguoi noi (Face Tracking):"
    echo "     ./run.sh 'interview.mp4' --crop-style face --num-clips 3"
    echo "=========================================================="
    exit 0
fi

# 1. Kich hoat moi truong ao
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Loi: Chua tim thay thu muc .venv! Vui long chay ./setup.sh truoc."
    exit 1
fi

# 2. Dam bao Ollama dang chay neu duoc cai dat
if command -v ollama &>/dev/null; then
    if ! pgrep -x "ollama" > /dev/null; then
        echo "[Ollama] Dang khoi dong Ollama serve ngam..."
        ollama serve &>/dev/null &
        sleep 2
    fi
fi

# 3. Kiem tra va convert cu phap tham so vi tri neu nguoi dung nhap ngan gon
# Vi du: ./run.sh video.mp4 3 speech
if [ $# -ge 2 ] && [[ "$2" =~ ^[0-9]+$ ]] && [[ "$3" != --* ]]; then
    VIDEO_ARG="$1"
    NUM_CLIPS="$2"
    TYPE_ARG="${3:-auto}"
    STYLE_ARG="${4:-blur}"
    echo "[Generator] Chay nhanh: $VIDEO_ARG (Clips: $NUM_CLIPS, Type: $TYPE_ARG, Style: $STYLE_ARG)"
    python main.py "$VIDEO_ARG" --num-clips "$NUM_CLIPS" --type "$TYPE_ARG" --crop-style "$STYLE_ARG"
else
    # Truyen nguyen ven cac tham so command line
    python main.py "$@"
fi
