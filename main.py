"""CLI entry point.

Usage:
    # Cắt video trò chuyện / podcast (theo lời thoại):
    python main.py "video.mp4" --type speech --num-clips 3

    # Cắt video thể thao / hành động (theo âm lượng hò reo, đập bóng/cầu):
    python main.py "match.mov" --type sports --num-clips 10 --duration 45

    # Tự động nhận diện loại video (Mặc định):
    python main.py "video.mp4" --num-clips 3
"""
import argparse
import json
import sys
import os

# Reconfigure stdout/stderr to UTF-8 so output works on all platforms
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from shorts_generator import generate_shorts, generate_sports_shorts


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal AI Video Shorts Generator (Speech & Sports)")
    parser.add_argument("url", help="YouTube URL, file:// URL, or local file path")
    parser.add_argument(
        "--type",
        choices=["auto", "speech", "sports"],
        default="auto",
        help="Content type: 'speech' (Whisper+LLM for podcasts/talks), 'sports' (Audio peak detection for matches/action), or 'auto' (default: speech with sports fallback).",
    )
    parser.add_argument(
        "--mode",
        choices=["api", "local"],
        default="local",
        help="Processing mode: 'local' (Ollama/Whisper/FFmpeg - 100%% offline) or 'api' (cloud services).",
    )
    parser.add_argument("--num-clips", type=int, default=3, help="How many shorts to render (default: 3)")
    parser.add_argument("--duration", type=float, default=45.0, help="Clip duration in seconds for sports mode (default: 45.0s)")
    parser.add_argument("--aspect-ratio", default="9:16", help="Output aspect ratio (default: 9:16)")
    parser.add_argument("--format", default="720", help="Source download resolution if YouTube URL (default: 720)")
    parser.add_argument("--language", default=None, help="Force Whisper language code, e.g. 'vi', 'en' (default: auto-detect)")
    parser.add_argument("--output-dir", default=None, help="Custom output directory for generated clips")
    parser.add_argument(
        "--crop-style",
        choices=["blur", "face"],
        default="blur",
        help="9:16 reframe style: 'blur' (Professional 1080x1920 Pillarbox Blur, default) or 'face' (OpenCV face-tracking crop).",
    )
    parser.add_argument("--output-json", default=None, help="Write the full result JSON to this path")
    args = parser.parse_args()

    result = None

    if args.type == "sports":
        print("[generator] Running in SPORTS mode (Audio Energy Peaks + 9:16 Pillarbox Blur)...", flush=True)
        try:
            result = generate_sports_shorts(
                source_path=args.url,
                num_clips=args.num_clips,
                clip_duration=args.duration,
                out_dir=args.output_dir,
            )
        except Exception as e:
            print(f"\nFAILED in sports mode: {e}", file=sys.stderr)
            return 1

    elif args.type == "speech":
        print(f"[generator] Running in SPEECH mode (Whisper + LLM highlight detection)...", flush=True)
        try:
            result = generate_shorts(
                youtube_url=args.url,
                num_clips=args.num_clips,
                aspect_ratio=args.aspect_ratio,
                download_format=args.format,
                language=args.language,
                mode=args.mode,
                out_dir=args.output_dir,
                crop_style=args.crop_style,
            )
        except Exception as e:
            print(f"\nFAILED in speech mode: {e}", file=sys.stderr)
            return 1

    else:  # auto
        print("[generator] Running in AUTO mode: Trying SPEECH detection first...", flush=True)
        try:
            result = generate_shorts(
                youtube_url=args.url,
                num_clips=args.num_clips,
                aspect_ratio=args.aspect_ratio,
                download_format=args.format,
                language=args.language,
                mode=args.mode,
                out_dir=args.output_dir,
                crop_style=args.crop_style,
            )
        except Exception as e:
            err_msg = str(e)
            if "no detectable speech" in err_msg.lower() or "produced no segments" in err_msg.lower():
                print(f"[generator] No continuous speech detected ({err_msg}).", flush=True)
                print("[generator] Automatically switching to SPORTS / ACTION highlight mode...", flush=True)
                try:
                    result = generate_sports_shorts(
                        source_path=args.url,
                        num_clips=args.num_clips,
                        clip_duration=args.duration,
                        out_dir=args.output_dir,
                    )
                except Exception as sports_err:
                    print(f"\nFAILED in sports fallback: {sports_err}", file=sys.stderr)
                    return 1
            else:
                print(f"\nFAILED: {e}", file=sys.stderr)
                return 1

    # In kết quả tóm tắt
    print("\n" + "=" * 72)
    print(f"Mode:          {result.get('mode', args.mode)}")
    print(f"Source video:  {result.get('source_video_url', args.url)}")
    print(f"Highlights:    {len(result.get('highlights', []))} candidates → kept {len(result.get('shorts', []))} clips")
    print("=" * 72)
    for i, s in enumerate(result.get("shorts", []), 1):
        print(f"\n#{i}  score={s.get('score', 0)}  {s.get('start_time', 0.0):.1f}s → {s.get('end_time', 0.0):.1f}s")
        print(f"     title:  {s.get('title', '(untitled)')}")
        if s.get("hook_sentence"):
            print(f"     hook:   {s.get('hook_sentence')}")
        if s.get("clip_url"):
            print(f"     clip:   {s['clip_url']}")
        else:
            print(f"     clip:   FAILED ({s.get('error')})")

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nFull JSON written to {args.output_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
