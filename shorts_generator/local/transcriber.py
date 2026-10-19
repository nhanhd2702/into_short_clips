"""Local transcription via faster-whisper.

Reads a local media file and returns the same shape the highlight generator
expects: {duration, segments[start, end, text]}.
Includes robust metadata-validated, atomic caching in `output/cache/transcripts/<hash>/`.
"""
import datetime
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

from ..config import (
    LOCAL_OUTPUT_DIR,
    LOCAL_WHISPER_DEVICE,
    LOCAL_WHISPER_MODEL,
    LOCAL_WHISPER_VAD_FILTER,
    LOCAL_WHISPER_VAD_PARAMETERS,
)


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _parse_srt_timestamp(value: str) -> float:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", value.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {value!r}")
    hours, minutes, seconds, millis = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + (millis / 1000.0)


def _compute_cache_identity(media_path: str, language: Optional[str] = None) -> Tuple[str, Dict]:
    """Generate a unique cache key based on absolute path, file size, mtime_ns, model, and language."""
    norm_path = os.path.abspath(os.path.realpath(media_path))
    if not os.path.exists(norm_path):
        raise FileNotFoundError(f"Source media file not found: {media_path}")

    stat = os.stat(norm_path)
    file_size = stat.st_size
    mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9))
    lang = (language or "auto").strip().lower()
    vad_sig = f"{LOCAL_WHISPER_VAD_FILTER}_{json.dumps(LOCAL_WHISPER_VAD_PARAMETERS, sort_keys=True)}"

    identity_str = f"{norm_path}|{file_size}|{mtime_ns}|{LOCAL_WHISPER_MODEL}|{lang}|{vad_sig}"
    cache_key = hashlib.sha256(identity_str.encode("utf-8")).hexdigest()[:20]

    metadata = {
        "cache_key": cache_key,
        "source_path": norm_path,
        "file_size": file_size,
        "mtime_ns": mtime_ns,
        "whisper_model": LOCAL_WHISPER_MODEL,
        "language": lang,
        "vad_filter": LOCAL_WHISPER_VAD_FILTER,
    }
    return cache_key, metadata


def _get_cache_dir(cache_key: str, base_out_dir: Optional[str] = None) -> Path:
    base = Path(base_out_dir or LOCAL_OUTPUT_DIR)
    return base / "cache" / "transcripts" / cache_key


def _load_srt_content(content: str) -> Dict:
    content = content.strip()
    if not content:
        return {"duration": 0.0, "segments": []}

    segments = []
    for block in re.split(r"\n\s*\n", content):
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if "-->" not in lines[0] and len(lines) > 1 and "-->" in lines[1]:
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue
        start_raw, end_raw = [part.strip() for part in lines[0].split("-->", 1)]
        text = "\n".join(lines[1:]).strip()
        segments.append(
            {
                "start": _parse_srt_timestamp(start_raw),
                "end": _parse_srt_timestamp(end_raw),
                "text": text,
            }
        )

    duration = segments[-1]["end"] if segments else 0.0
    return {"duration": duration, "segments": segments}


def _load_cached_transcript(cache_dir: Path, expected_meta: Dict) -> Optional[Dict]:
    """Verify metadata and content before reusing cached transcript."""
    meta_path = cache_dir / "metadata.json"
    srt_path = cache_dir / "transcript.srt"

    if not meta_path.is_file() or not srt_path.is_file():
        return None

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            stored_meta = json.load(f)

        # Verify all essential fields match exactly
        for field in ("source_path", "file_size", "mtime_ns", "whisper_model", "language"):
            if stored_meta.get(field) != expected_meta.get(field):
                print(
                    f"[transcribe/local] Cache metadata mismatch for {field}: "
                    f"stored={stored_meta.get(field)!r} vs current={expected_meta.get(field)!r}",
                    flush=True,
                )
                return None

        content = srt_path.read_text(encoding="utf-8-sig")
        cached = _load_srt_content(content)
        if not cached["segments"] or cached["duration"] <= 0.0:
            print(f"[transcribe/local] Cache file {srt_path} is empty or contains no valid segments", flush=True)
            return None

        return cached
    except Exception as e:
        print(f"[transcribe/local] Failed to read cache {cache_dir}: {e}", flush=True)
        return None


def _save_transcript_cache(cache_dir: Path, metadata: Dict, transcript: Dict) -> Path:
    """Atomically write metadata.json and transcript.srt."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    srt_lines = []
    for idx, segment in enumerate(transcript.get("segments", []), start=1):
        start = _format_srt_timestamp(float(segment["start"]))
        end = _format_srt_timestamp(float(segment["end"]))
        text = str(segment.get("text", "")).strip().replace("\r", "").replace("\n", " ")
        srt_lines.append(str(idx))
        srt_lines.append(f"{start} --> {end}")
        srt_lines.append(text)
        srt_lines.append("")

    srt_content = "\n".join(srt_lines)
    full_meta = {
        **metadata,
        "duration": transcript.get("duration", 0.0),
        "num_segments": len(transcript.get("segments", [])),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # Atomic write to temporary files then rename
    tmp_srt = cache_dir / "transcript.srt.tmp"
    tmp_meta = cache_dir / "metadata.json.tmp"
    final_srt = cache_dir / "transcript.srt"
    final_meta = cache_dir / "metadata.json"

    tmp_srt.write_text(srt_content, encoding="utf-8")
    tmp_meta.write_text(json.dumps(full_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    os.replace(str(tmp_srt), str(final_srt))
    os.replace(str(tmp_meta), str(final_meta))
    return final_srt


def _resolve_device() -> str:
    if LOCAL_WHISPER_DEVICE != "auto":
        return LOCAL_WHISPER_DEVICE
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            torch.zeros(1, device="cuda")
            return "cuda"
    except (ImportError, OSError, RuntimeError):
        pass
    return "cpu"


def transcribe_local(
    media_path: str,
    language: Optional[str] = None,
    out_dir: Optional[str] = None,
    export_user_srt: bool = True,
    cache_root: Optional[str] = None,
) -> Dict:
    """Run faster-whisper on a local file path with validated atomic caching."""
    cache_key, meta = _compute_cache_identity(media_path, language=language)
    cache_dir = _get_cache_dir(cache_key, base_out_dir=cache_root)

    cached = _load_cached_transcript(cache_dir, meta)
    if cached is not None:
        print(
            f"[transcribe/local] Reusing validated cache [{cache_key}]: "
            f"{len(cached['segments'])} segments, {cached['duration']:.1f}s",
            flush=True,
        )
        # Optional: export user-facing srt in output directory if requested
        if export_user_srt and out_dir:
            user_srt_dir = Path(out_dir)
            user_srt_dir.mkdir(parents=True, exist_ok=True)
            user_srt_path = user_srt_dir / f"{Path(media_path).stem}.srt"
            if not user_srt_path.exists():
                try:
                    user_srt_path.write_text(
                        (cache_dir / "transcript.srt").read_text(encoding="utf-8"),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
        return cached

    # Cache miss or invalid -> Run Whisper transcription
    print(f"[transcribe/local] Cache miss or invalidated. Running Whisper on: {media_path}", flush=True)

    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper is required for --mode local. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    device = _resolve_device()
    compute_type = "float16" if device == "cuda" else "int8"
    print(f"[transcribe/local] faster-whisper model={LOCAL_WHISPER_MODEL} device={device}", flush=True)

    model = WhisperModel(LOCAL_WHISPER_MODEL, device=device, compute_type=compute_type)

    transcribe_kwargs = {
        "audio": media_path,
        "language": language,
        "beam_size": 5,
        "condition_on_previous_text": False,
    }
    if LOCAL_WHISPER_VAD_FILTER:
        transcribe_kwargs["vad_filter"] = True
        transcribe_kwargs["vad_parameters"] = LOCAL_WHISPER_VAD_PARAMETERS
    else:
        transcribe_kwargs["vad_filter"] = False

    segments_iter, info = model.transcribe(**transcribe_kwargs)

    segments = []
    for s in segments_iter:
        segments.append({
            "start": float(s.start),
            "end": float(s.end),
            "text": (s.text or "").strip(),
        })

    duration = float(getattr(info, "duration", 0.0)) or (segments[-1]["end"] if segments else 0.0)
    print(f"[transcribe/local] Transcribed {len(segments)} segments, {duration:.1f}s of audio", flush=True)
    transcript = {"duration": duration, "segments": segments}

    _save_transcript_cache(cache_dir, meta, transcript)
    print(f"[transcribe/local] Saved verified cache to: {cache_dir}", flush=True)

    # Optional export for user
    if export_user_srt and out_dir:
        user_srt_dir = Path(out_dir)
        user_srt_dir.mkdir(parents=True, exist_ok=True)
        user_srt_path = user_srt_dir / f"{Path(media_path).stem}.srt"
        try:
            user_srt_path.write_text(
                (cache_dir / "transcript.srt").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        except Exception:
            pass

    return transcript
