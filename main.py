"""CLI entry point.

Usage:
    # Cắt video trò chuyện / podcast (theo lời thoại):
    python main.py "video.mp4" --type speech --num-clips 3

    # Cắt video thể thao / hành động (theo âm lượng hò reo, đập bóng/cầu):
    python main.py "match.mov" --type sports --num-clips 10 --duration 45

    # Tự động nhận diện loại video (Mặc định):
    python main.py "video.mp4" --num-clips 3

Exit codes:
    0: Success - all selected clips rendered successfully
    1: Pipeline failure - zero clips rendered or unrecoverable error
    2: Validation error - invalid parameters, missing file, or unsupported format
    3: Partial success - at least one clip rendered, but some clips failed
"""
import argparse
import json
import os
import sys

# Reconfigure stdout/stderr to UTF-8 so output works reliably across Windows / macOS / Linux
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from shorts_generator import (
    ValidationError,
    generate_shorts,
    generate_sports_shorts,
    validate_common_args,
    validate_source_media,
)


def _write_json(path: str, data: dict) -> None:
    """Safely write JSON output if a path is specified."""
    if not path:
        return
    try:
        out_parent = os.path.dirname(os.path.abspath(path))
        if out_parent:
            os.makedirs(out_parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n[JSON] Full result written to {path}", flush=True)
    except Exception as e:
        print(f"\n[WARNING] Could not write JSON output to {path}: {e}", file=sys.stderr)


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
        choices=["local", "api"],
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
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite existing output directory instead of creating a new isolated run directory",
    )
    parser.add_argument("--output-json", default=None, help="Write the full result JSON to this path")
    args = parser.parse_args()

    # 1. Early argument & media validation (Exit code 2 on failure)
    try:
        validate_common_args(
            num_clips=args.num_clips,
            duration=args.duration,
            aspect_ratio=args.aspect_ratio,
            crop_style=args.crop_style,
            mode=args.mode,
            type_mode=args.type,
            out_dir=args.output_dir,
        )
        validate_source_media(
            args.url,
            need_audio=True,  # Audio is required for both speech transcription and sports energy peaks
        )
    except ValidationError as val_err:
        print(f"\n[VALIDATION ERROR] {val_err}", file=sys.stderr)
        _write_json(
            args.output_json,
            {
                "status": "failure",
                "error": str(val_err),
                "error_type": "ValidationError",
                "requested": args.num_clips,
                "selected": 0,
                "succeeded": 0,
                "failed": 0,
                "shorts": [],
            },
        )
        return 2
    except Exception as e:
        print(f"\n[VALIDATION UNEXPECTED ERROR] {e}", file=sys.stderr)
        _write_json(
            args.output_json,
            {
                "status": "failure",
                "error": str(e),
                "error_type": type(e).__name__,
                "requested": args.num_clips,
                "selected": 0,
                "succeeded": 0,
                "failed": 0,
                "shorts": [],
            },
        )
        return 2

    # 2. Pipeline Execution (Exit code 1 on unhandled exception)
    result = None

    try:
        if args.type == "sports":
            print("[generator] Running in SPORTS mode (Audio Energy Peaks + 9:16 Pillarbox Blur)...", flush=True)
            result = generate_sports_shorts(
                source_path=args.url,
                num_clips=args.num_clips,
                clip_duration=args.duration,
                aspect_ratio=args.aspect_ratio,
                crop_style=args.crop_style,
                out_dir=args.output_dir,
                overwrite=args.overwrite,
            )

        elif args.type == "speech":
            print(f"[generator] Running in SPEECH mode (Whisper + LLM highlight detection)...", flush=True)
            result = generate_shorts(
                youtube_url=args.url,
                num_clips=args.num_clips,
                aspect_ratio=args.aspect_ratio,
                download_format=args.format,
                language=args.language,
                mode=args.mode,
                out_dir=args.output_dir,
                crop_style=args.crop_style,
                overwrite=args.overwrite,
            )

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
                    overwrite=args.overwrite,
                )
            except Exception as e:
                err_msg = str(e)
                if "no detectable speech" in err_msg.lower() or "produced no segments" in err_msg.lower():
                    print(f"[generator] No continuous speech detected ({err_msg}).", flush=True)
                    print("[generator] Automatically switching to SPORTS / ACTION highlight mode...", flush=True)
                    result = generate_sports_shorts(
                        source_path=args.url,
                        num_clips=args.num_clips,
                        clip_duration=args.duration,
                        aspect_ratio=args.aspect_ratio,
                        crop_style=args.crop_style,
                        out_dir=args.output_dir,
                        overwrite=args.overwrite,
                    )
                else:
                    raise

    except ValidationError as val_err:
        print(f"\n[VALIDATION ERROR] {val_err}", file=sys.stderr)
        _write_json(
            args.output_json,
            {
                "status": "failure",
                "error": str(val_err),
                "error_type": "ValidationError",
                "requested": args.num_clips,
                "selected": 0,
                "succeeded": 0,
                "failed": 0,
                "shorts": [],
            },
        )
        return 2

    except Exception as e:
        print(f"\n[PIPELINE FAILURE] {e}", file=sys.stderr)
        _write_json(
            args.output_json,
            {
                "status": "failure",
                "error": str(e),
                "error_type": type(e).__name__,
                "requested": args.num_clips,
                "selected": 0,
                "succeeded": 0,
                "failed": 0,
                "shorts": [],
            },
        )
        return 1

    # 3. Analyze status and counts
    requested = result.get("requested", args.num_clips)
    selected = result.get("selected", len(result.get("shorts", [])))
    succeeded = result.get("succeeded", sum(1 for s in result.get("shorts", []) if s.get("clip_url")))
    failed = result.get("failed", len(result.get("shorts", [])) - succeeded)

    if selected == 0:
        overall_status = "failure"
    elif succeeded == selected and succeeded > 0:
        overall_status = "success"
    elif succeeded > 0:
        overall_status = "partial_success"
    else:
        overall_status = "failure"

    result["status"] = overall_status
    result["requested"] = requested
    result["selected"] = selected
    result["succeeded"] = succeeded
    result["failed"] = failed

    # 4. Summary presentation
    print("\n" + "=" * 72)
    print(f"Status:        {overall_status.upper()}")
    print(f"Mode:          {result.get('mode', args.mode)}")
    print(f"Source video:  {result.get('source_video_url', args.url)}")
    print(f"Clips:         Requested={requested} | Found/Selected={selected} | Succeeded={succeeded} | Failed={failed}")
    print("=" * 72)

    for i, s in enumerate(result.get("shorts", []), 1):
        st = s.get("status", "success" if s.get("clip_url") else "failed").upper()
        print(f"\n#{i} [{st}] score={s.get('score', 0)}  {s.get('start_time', 0.0):.1f}s → {s.get('end_time', 0.0):.1f}s")
        print(f"     title:  {s.get('title', '(untitled)')}")
        if s.get("hook_sentence"):
            print(f"     hook:   {s.get('hook_sentence')}")
        if s.get("clip_url"):
            print(f"     clip:   {s['clip_url']}")
        else:
            print(f"     clip:   FAILED ({s.get('error')})")

    _write_json(args.output_json, result)

    # 5. Exit with standardized status codes
    # 0 = All selected clips succeeded
    # 3 = Partial success
    # 1 = Complete failure (zero clips succeeded)
    if overall_status == "success":
        return 0
    elif overall_status == "partial_success":
        return 3
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
