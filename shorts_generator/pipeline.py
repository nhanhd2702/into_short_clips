"""End-to-end orchestrator.

Two modes:
  * mode="local" (default) — yt-dlp + faster-whisper + Ollama/OpenAI/Gemini + ffmpeg/opencv.
                              Self-hosted, 100% offline ready.
  * mode="api"            — MuAPI does download / transcribe / LLM / autocrop.
                              Fast, no local deps, pay-per-call.
"""
import datetime
from typing import Dict, List, Optional

from .clipper import crop_highlights
from .downloader import download_youtube
from .highlights import call_muapi_llm, get_highlights
from .run_context import create_run_directory, save_manifest
from .transcriber import transcribe
from .validation import validate_common_args, validate_source_media


def _compute_status(selected: int, succeeded: int) -> str:
    if selected == 0:
        return "failure"
    if succeeded == selected and succeeded > 0:
        return "success"
    if succeeded > 0:
        return "partial_success"
    return "failure"


def _run_local(
    youtube_url: str,
    num_clips: int,
    aspect_ratio: str,
    download_format: str,
    language: Optional[str],
    out_dir: Optional[str] = None,
    crop_style: str = "blur",
    overwrite: bool = False,
) -> Dict:
    from .local.clipper import crop_highlights_local
    from .local.downloader import download_youtube_local
    from .local.llm import call_local_llm, verify_llm_provider_readiness
    from .local.transcriber import transcribe_local

    # Pre-flight LLM readiness check: fails fast before download or long transcription
    verify_llm_provider_readiness()

    # Isolate output run directory
    run_dir, run_id = create_run_directory(
        source=youtube_url,
        base_out_dir=out_dir,
        overwrite=overwrite,
    )

    source_path = download_youtube_local(youtube_url, fmt=download_format, out_dir=run_dir)

    transcript = transcribe_local(source_path, language=language, out_dir=run_dir)
    if not transcript["segments"]:
        raise RuntimeError(
            "Whisper produced no segments. The video may have no detectable speech."
        )

    highlights_result = get_highlights(transcript, num_clips=num_clips, llm_fn=call_local_llm)
    all_highlights: List[Dict] = highlights_result.get("highlights", [])
    if not all_highlights:
        raise RuntimeError("Highlight generator returned zero clips.")

    top = sorted(all_highlights, key=lambda h: int(h.get("score", 0)), reverse=True)[:num_clips]
    selected_count = len(top)
    print(f"[pipeline/local] cropping {selected_count} of {len(all_highlights)} candidates to {run_dir} [style={crop_style}]", flush=True)

    shorts = crop_highlights_local(
        source_path, top, aspect_ratio=aspect_ratio, out_dir=run_dir, crop_style=crop_style
    )

    succeeded = sum(1 for s in shorts if s.get("clip_url") and s.get("status") == "success")
    failed = len(shorts) - succeeded
    status = _compute_status(selected_count, succeeded)

    result_data = {
        "run_id": run_id,
        "out_dir": run_dir,
        "mode": "local",
        "status": status,
        "requested": num_clips,
        "selected": selected_count,
        "succeeded": succeeded,
        "failed": failed,
        "source_video_url": source_path,
        "transcript": transcript,
        "highlights": all_highlights,
        "shorts": shorts,
    }

    manifest = {
        **result_data,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config": {
            "num_clips": num_clips,
            "aspect_ratio": aspect_ratio,
            "crop_style": crop_style,
            "download_format": download_format,
            "language": language,
        },
    }
    save_manifest(run_dir, manifest)

    return result_data


def _run_api(
    youtube_url: str,
    num_clips: int,
    aspect_ratio: str,
    download_format: str,
    language: Optional[str],
    out_dir: Optional[str] = None,
    overwrite: bool = False,
) -> Dict:
    run_dir, run_id = create_run_directory(
        source=youtube_url,
        base_out_dir=out_dir,
        overwrite=overwrite,
    )

    source_url = download_youtube(youtube_url, fmt=download_format)

    transcript = transcribe(source_url, language=language)
    if not transcript["segments"]:
        raise RuntimeError(
            "Whisper produced no segments. The video may have no detectable speech."
        )

    highlights_result = get_highlights(transcript, num_clips=num_clips, llm_fn=call_muapi_llm)
    all_highlights: List[Dict] = highlights_result.get("highlights", [])
    if not all_highlights:
        raise RuntimeError("Highlight generator returned zero clips.")

    top = sorted(all_highlights, key=lambda h: int(h.get("score", 0)), reverse=True)[:num_clips]
    selected_count = len(top)
    print(f"[pipeline] cropping {selected_count} of {len(all_highlights)} candidates", flush=True)

    shorts = crop_highlights(source_url, top, aspect_ratio=aspect_ratio)

    succeeded = sum(1 for s in shorts if s.get("clip_url") and s.get("status") == "success")
    failed = len(shorts) - succeeded
    status = _compute_status(selected_count, succeeded)

    result_data = {
        "run_id": run_id,
        "out_dir": run_dir,
        "mode": "api",
        "status": status,
        "requested": num_clips,
        "selected": selected_count,
        "succeeded": succeeded,
        "failed": failed,
        "source_video_url": source_url,
        "transcript": transcript,
        "highlights": all_highlights,
        "shorts": shorts,
    }

    manifest = {
        **result_data,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config": {
            "num_clips": num_clips,
            "aspect_ratio": aspect_ratio,
            "download_format": download_format,
            "language": language,
        },
    }
    save_manifest(run_dir, manifest)

    return result_data


def generate_shorts(
    youtube_url: str,
    num_clips: int = 3,
    aspect_ratio: str = "9:16",
    download_format: str = "720",
    language: Optional[str] = None,
    mode: str = "local",
    out_dir: Optional[str] = None,
    crop_style: str = "blur",
    overwrite: bool = False,
) -> Dict:
    """Run the full pipeline and return a structured result with consistent status and run isolation."""
    mode = (mode or "local").lower()

    # Pre-flight argument & source validation
    validate_common_args(
        num_clips=num_clips,
        aspect_ratio=aspect_ratio,
        crop_style=crop_style,
        mode=mode,
        type_mode="speech",
        out_dir=out_dir,
    )
    validate_source_media(youtube_url, need_audio=True)

    if mode == "local":
        return _run_local(
            youtube_url,
            num_clips,
            aspect_ratio,
            download_format,
            language,
            out_dir=out_dir,
            crop_style=crop_style,
            overwrite=overwrite,
        )
    if mode == "api":
        return _run_api(
            youtube_url,
            num_clips,
            aspect_ratio,
            download_format,
            language,
            out_dir=out_dir,
            overwrite=overwrite,
        )
    raise ValueError(f"Unknown mode: {mode!r}. Use 'local' or 'api'.")
