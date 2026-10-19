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
    exit 2
fi

# 1. Kich hoat moi truong ao
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Loi: Chua tim thay thu muc .venv! Vui long chay ./setup.sh truoc."
    exit 1
fi

# 2. Xac dinh co can Ollama khong
IS_SPORTS=0
for arg in "$@"; do
    if [ "$arg" = "sports" ] || [ "$arg" = "--type=sports" ]; then
        IS_SPORTS=1
        break
    fi
done

if [ "$IS_SPORTS" -eq 0 ]; then
    NEEDS_OLLAMA=1
    if [ -f ".env" ]; then
        if grep -E 'LLM_PROVIDER\s*=\s*["'\'']?(openai|gemini)["'\'']?' .env > /dev/null 2>&1; then
            NEEDS_OLLAMA=0
        fi
    fi

    if [ "$NEEDS_OLLAMA" -eq 1 ] && command -v ollama &>/dev/null; then
        if ! curl -s -f http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
            echo "[Ollama] Dang khoi dong Ollama server ngam..."
            ollama serve &>/dev/null &
            # Polling toi da 15s
            for i in $(seq 1 15); do
                sleep 1
                if curl -s -f http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
                    echo "[Ollama] Server da san sang!"
                    break
                fi
            done
        fi
    fi
fi

# 3. Kiem tra va convert cu phap tham so vi tri neu nguoi dung nhap ngan gon
# Vi du: ./run.sh video.mp4 3 speech
set +e
if [ $# -ge 2 ] && [[ "$2" =~ ^[0-9]+$ ]] && [[ "$3" != --* ]]; then
    VIDEO_ARG="$1"
    NUM_CLIPS="$2"
    TYPE_ARG="${3:-auto}"
    STYLE_ARG="${4:-blur}"
    echo "[Generator] Chay nhanh: $VIDEO_ARG (Clips: $NUM_CLIPS, Type: $TYPE_ARG, Style: $STYLE_ARG)"
    python main.py "$VIDEO_ARG" --num-clips "$NUM_CLIPS" --type "$TYPE_ARG" --crop-style "$STYLE_ARG"
    EXIT_CODE=$?
else
    # Truyen nguyen ven cac tham so command line
    python main.py "$@"
    EXIT_CODE=$?
fi

exit $EXIT_CODE
