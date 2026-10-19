"""Argument and media input validation.

Fails fast with clear descriptive error messages before any heavy computation
(Whisper transcription, LLM calls, FFmpeg rendering, or Ollama downloads).
"""
import math
import os
import shutil
import subprocess
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse


class ValidationError(ValueError):
    """Raised when user input, parameters, or source media fail validation."""
    pass


SUPPORTED_ASPECT_RATIOS = ("9:16", "1:1", "16:9")
SUPPORTED_CROP_STYLES = ("blur", "face")
SUPPORTED_TYPES = ("auto", "speech", "sports")
SUPPORTED_MODES = ("local", "api")


def validate_common_args(
    num_clips: int,
    duration: Optional[float] = None,
    aspect_ratio: str = "9:16",
    crop_style: str = "blur",
    mode: str = "local",
    type_mode: str = "auto",
    out_dir: Optional[str] = None,
) -> None:
    """Validate standard CLI and programmatic arguments.

    Raises:
        ValidationError: If any argument is out of bounds or unsupported.
    """
    # 1. num_clips
    if isinstance(num_clips, bool) or not isinstance(num_clips, int):
        raise ValidationError(
            f"Invalid num_clips: expected integer, got {type(num_clips).__name__} ({num_clips!r})"
        )
    if num_clips <= 0:
        raise ValidationError(
            f"num_clips must be a positive integer greater than 0 (got {num_clips})"
        )

    # 2. duration
    if duration is not None:
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ValidationError(
                f"Invalid duration: expected float/int, got {type(duration).__name__} ({duration!r})"
            )
        if not math.isfinite(duration) or duration <= 0:
            raise ValidationError(
                f"duration must be a positive finite number greater than 0 (got {duration})"
            )

    # 3. aspect_ratio
    if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
        raise ValidationError(
            f"Unsupported aspect_ratio: {aspect_ratio!r}. "
            f"Supported options are: {', '.join(SUPPORTED_ASPECT_RATIOS)}"
        )

    # 4. crop_style
    if crop_style not in SUPPORTED_CROP_STYLES:
        raise ValidationError(
            f"Unsupported crop_style: {crop_style!r}. "
            f"Supported options are: {', '.join(SUPPORTED_CROP_STYLES)}"
        )

    # 5. type_mode
    if type_mode not in SUPPORTED_TYPES:
        raise ValidationError(
            f"Unsupported type: {type_mode!r}. "
            f"Supported options are: {', '.join(SUPPORTED_TYPES)}"
        )

    # 6. mode
    if mode not in SUPPORTED_MODES:
        raise ValidationError(
            f"Unsupported mode: {mode!r}. "
            f"Supported options are: {', '.join(SUPPORTED_MODES)}"
        )

    # 7. Type-specific constraints
    if type_mode == "sports":
        if aspect_ratio != "9:16":
            raise ValidationError(
                f"Sports mode currently only supports aspect_ratio='9:16' (requested: {aspect_ratio!r})"
            )
        if crop_style != "blur":
            raise ValidationError(
                f"Sports mode currently only supports crop_style='blur' (requested: {crop_style!r}). "
                f"Face-tracking cannot follow wide-angle sports action."
            )

    # 8. out_dir writability
    if out_dir:
        try:
            os.makedirs(out_dir, exist_ok=True)
            test_file = os.path.join(out_dir, f".write_test_{os.getpid()}")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            raise ValidationError(
                f"Output directory {out_dir!r} is not writable or cannot be created: {e}"
            )


def is_remote_url(source: str) -> bool:
    """Check if the string is an HTTP/HTTPS remote URL."""
    try:
        parsed = urlparse(source.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def resolve_media_path(source: str) -> Tuple[Optional[str], bool]:
    """Resolve local path or determine if remote URL.

    Returns:
        (local_path_or_none, is_remote)
    """
    source = (source or "").strip()
    if not source:
        raise ValidationError("Source video URL or file path cannot be empty.")

    if is_remote_url(source):
        return None, True

    from .local.downloader import _resolve_local_path
    try:
        local_path = _resolve_local_path(source)
    except RuntimeError as e:
        raise ValidationError(str(e))

    if local_path and os.path.exists(local_path):
        return local_path, False

    candidate = os.path.abspath(os.path.expanduser(source))
    if os.path.exists(candidate):
        return candidate, False

    raise ValidationError(f"Source video file does not exist: {source!r}")


def probe_media_file(file_path: str, need_audio: bool = False) -> Dict[str, Any]:
    """Run ffprobe on local file to ensure it has valid video (and audio) streams.

    Raises:
        ValidationError: If the file is not a valid video or lacks required streams.
    """
    if not os.path.isfile(file_path):
        raise ValidationError(f"Source path is not a file: {file_path!r}")

    size = os.path.getsize(file_path)
    if size < 1024:
        raise ValidationError(
            f"Source video file is empty or corrupted (< 1KB, size={size} bytes): {file_path!r}"
        )

    if not shutil.which("ffprobe"):
        return {"file_path": file_path, "size": size}

    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_type,width,height,duration",
        "-show_entries", "format=duration",
        "-of", "json",
        file_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        info = json.loads(res.stdout)
    except Exception as e:
        raise ValidationError(f"Failed to probe source media with ffprobe: {e} ({file_path!r})")

    streams = info.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    if not video_streams:
        raise ValidationError(f"Source file {file_path!r} contains no video stream.")

    v_stream = video_streams[0]
    width = v_stream.get("width", 0)
    height = v_stream.get("height", 0)
    if not width or not height or width <= 0 or height <= 0:
        raise ValidationError(f"Source file {file_path!r} has invalid video dimensions ({width}x{height}).")

    fmt_duration = info.get("format", {}).get("duration")
    duration = None
    if fmt_duration:
        try:
            duration = float(fmt_duration)
        except (ValueError, TypeError):
            pass
    if duration is None:
        v_dur = v_stream.get("duration")
        if v_dur:
            try:
                duration = float(v_dur)
            except (ValueError, TypeError):
                pass

    if duration is not None and duration <= 0:
        raise ValidationError(f"Source video {file_path!r} has invalid duration ({duration}s).")

    if need_audio and not audio_streams:
        raise ValidationError(
            f"Source file {file_path!r} has no audio stream. "
            f"Audio is required to analyze highlights (speech or audio energy peaks)."
        )

    return {
        "file_path": file_path,
        "size": size,
        "width": width,
        "height": height,
        "duration": duration or 0.0,
        "has_audio": bool(audio_streams),
        "has_video": True,
    }


def validate_source_media(source: str, need_audio: bool = False) -> Dict[str, Any]:
    """Validate source URL or local path.

    Raises:
        ValidationError: If input is invalid, missing, unreadable, or missing required streams.
    """
    local_path, is_remote = resolve_media_path(source)
    if is_remote:
        return {"is_remote": True, "source": source}

    meta = probe_media_file(local_path, need_audio=need_audio)
    meta["is_remote"] = False
    meta["source"] = local_path
    return meta
