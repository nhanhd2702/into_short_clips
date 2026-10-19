"""Sports and Action Highlight Generator.

Detects high-energy moments (cheers, shouts, smashes, points) via audio volume peaks,
and formats wide-angle sports footage into vertical 9:16 Shorts using Pillarbox Blur
(entire court/field visible in center, aesthetic blurred background top/bottom).
"""
import math
import os
import subprocess
import tempfile
import wave
from typing import Dict, List, Optional
import numpy as np

from .config import LOCAL_OUTPUT_DIR


def _has_audio_stream(media_path: str) -> bool:
    """Check if the source file has at least one audio stream."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            media_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return bool(res.stdout.strip())
    except Exception:
        return False


def _verify_video_file(file_path: str) -> bool:
    """Ensure output file exists, is non-empty, and has a readable video stream."""
    if not os.path.isfile(file_path) or os.path.getsize(file_path) < 1024:
        return False
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            file_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return bool(res.stdout.strip())
    except Exception:
        return False


def _clips_overlap(s1: float, e1: float, s2: float, e2: float, max_overlap_ratio: float = 0.35) -> bool:
    """Check if two time intervals overlap significantly."""
    overlap = max(0.0, min(e1, e2) - max(s1, s2))
    min_dur = max(1.0, min(e1 - s1, e2 - s2))
    return (overlap / min_dur) > max_overlap_ratio


def extract_audio_peaks(
    source_path: str,
    num_clips: int = 5,
    clip_duration: float = 45.0,
    out_dir: Optional[str] = None,
) -> List[Dict]:
    """Find the top `num_clips` audio energy peaks in a sports video.
    
    Guarantees every clip interval [start, end] firmly contains the peak event.
    """
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    if not _has_audio_stream(source_path):
        raise ValueError(
            f"Cannot analyze audio peaks: video '{source_path}' does not contain any audio stream."
        )

    if num_clips <= 0:
        raise ValueError(f"num_clips must be positive (received: {num_clips})")
    if clip_duration <= 0 or not math.isfinite(clip_duration):
        raise ValueError(f"clip_duration must be a finite positive number (received: {clip_duration})")

    temp_dir = out_dir or LOCAL_OUTPUT_DIR
    os.makedirs(temp_dir, exist_ok=True)
    temp_fd, temp_wav = tempfile.mkstemp(prefix="sports_audio_", suffix=".wav", dir=temp_dir)
    os.close(temp_fd)

    print(f"[sports] Analyzing audio waveform for {source_path}...", flush=True)
    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", source_path,
            "-vn", "-ac", "1", "-ar", "8000",
            temp_wav
        ], check=True)

        with wave.open(temp_wav, "rb") as wf:
            rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass

    if len(audio) == 0 or rate == 0:
        raise ValueError(f"Audio stream in '{source_path}' is empty or unreadable.")

    total_seconds = len(audio) / rate
    win = int(2.0 * rate)   # 2-second window
    step = int(1.0 * rate)  # 1-second step

    energies = []
    timestamps = []
    for i in range(0, max(1, len(audio) - win), step):
        chunk = audio[i : i + win]
        if len(chunk) == 0:
            continue
        rms = float(np.sqrt(np.mean(chunk**2)))
        energies.append(rms)
        timestamps.append(i / rate)

    if not energies:
        return []

    energies_arr = np.array(energies)
    timestamps_arr = np.array(timestamps)
    max_rms = float(np.max(energies_arr))
    min_rms = float(np.min(energies_arr))
    rms_range = max_rms - min_rms

    # Sort descending by RMS energy
    sorted_idx = np.argsort(energies_arr)[::-1]
    
    # Calculate dynamic lead-in based on clip duration (70% lead-in, 30% follow-through)
    lead_in = clip_duration * 0.7

    selected_intervals: List[Dict] = []
    for idx in sorted_idx:
        t = float(timestamps_arr[idx])
        rms = float(energies_arr[idx])

        # Clamp interval within source boundaries
        if total_seconds <= clip_duration:
            start = 0.0
            end = total_seconds
        else:
            max_start = max(0.0, total_seconds - clip_duration)
            start = max(0.0, min(t - lead_in, max_start))
            end = min(total_seconds, start + clip_duration)

        # Verify peak is strictly contained in [start, end]
        # (With a tiny tolerance of 0.05s for float rounding)
        if not (start - 0.05 <= t <= end + 0.05):
            continue

        # Overlap check on actual candidate intervals
        overlaps = False
        for existing in selected_intervals:
            if _clips_overlap(start, end, existing["start_time"], existing["end_time"]):
                overlaps = True
                break
        if overlaps:
            continue

        # Calculate normalized heuristic RMS score
        norm_score = int(round(((rms - min_rms) / (rms_range + 1e-6)) * 100)) if rms_range > 0 else 80

        selected_intervals.append({
            "start_time": start,
            "end_time": end,
            "peak_time": t,
            "duration": end - start,
            "score": norm_score,
            "heuristic_score": norm_score,
            "score_type": "normalized_audio_rms",
            "peak_rms": round(rms, 2),
        })

        if len(selected_intervals) >= num_clips:
            break

    # Sort chronologically for output
    selected_intervals.sort(key=lambda x: x["start_time"])
    for i, item in enumerate(selected_intervals, 1):
        m, s = int(item["peak_time"] // 60), int(item["peak_time"] % 60)
        item["index"] = i
        item["title"] = f"Sports Highlight #{i:02d} (Peak at {m:02d}:{s:02d})"

    return selected_intervals


def render_sports_clip_916(
    source_path: str,
    start_time: float,
    duration: float,
    out_path: str,
) -> str:
    """Render a 9:16 vertical short with pillarbox blur."""
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:10,eq=brightness=-0.05:contrast=0.95[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=0:(H-h)/2"
    )

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start_time:.3f}",
        "-t", f"{duration:.3f}",
        "-i", source_path,
        "-filter_complex", filter_complex,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "faster",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-threads", "0",
        out_path
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass
        raise RuntimeError(f"FFmpeg render failed with exit code {e.returncode}") from e

    if not _verify_video_file(out_path):
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass
        raise RuntimeError(f"Rendered file {out_path} is invalid, corrupt, or missing video stream.")

    return out_path


def generate_sports_shorts(
    source_path: str,
    num_clips: int = 5,
    clip_duration: float = 45.0,
    aspect_ratio: str = "9:16",
    crop_style: str = "blur",
    out_dir: Optional[str] = None,
    overwrite: bool = False,
) -> Dict:
    """End-to-end sports highlight extraction and rendering with robust status tracking and run isolation."""
    from .validation import validate_common_args, validate_source_media
    from .run_context import create_run_directory, save_manifest
    import datetime

    validate_common_args(
        num_clips=num_clips,
        duration=clip_duration,
        aspect_ratio=aspect_ratio,
        crop_style=crop_style,
        type_mode="sports",
        out_dir=out_dir,
    )
    validate_source_media(source_path, need_audio=True)

    run_dir, run_id = create_run_directory(
        source=source_path,
        base_out_dir=out_dir,
        overwrite=overwrite,
    )

    from .local.downloader import download_youtube_local
    resolved_source = download_youtube_local(source_path, out_dir=run_dir)
    if not _has_audio_stream(resolved_source):
        from .validation import ValidationError
        raise ValidationError(
            f"Source video {resolved_source!r} has no audio stream. "
            f"Sports highlight detection requires audio to detect cheers and energy peaks."
        )

    highlights = extract_audio_peaks(
        resolved_source,
        num_clips=num_clips,
        clip_duration=clip_duration,
        out_dir=run_dir,
    )

    selected_count = len(highlights)
    print(f"\n[sports] Found {selected_count} peak moments (requested {num_clips}). Rendering 9:16 clips to {run_dir}...", flush=True)

    rendered_shorts = []
    for h in highlights:
        out_name = f"sports_short_{h['index']:02d}.mp4"
        out_path = os.path.join(run_dir, out_name)
        print(f"[sports] Rendering #{h['index']:02d}: {h['title']} ({h['duration']:.1f}s) -> {out_name}", flush=True)
        try:
            render_sports_clip_916(
                source_path=resolved_source,
                start_time=h["start_time"],
                duration=h["duration"],
                out_path=out_path,
            )
            rendered_shorts.append({**h, "clip_url": out_path, "status": "success"})
        except Exception as e:
            print(f"[sports] Failed #{h['index']:02d}: {e}", flush=True)
            rendered_shorts.append({**h, "clip_url": None, "error": str(e), "status": "failed"})

    succeeded = sum(1 for s in rendered_shorts if s.get("clip_url"))
    failed = len(rendered_shorts) - succeeded

    if selected_count == 0:
        overall_status = "failure"
    elif succeeded == selected_count and succeeded > 0:
        overall_status = "success"
    elif succeeded > 0:
        overall_status = "partial_success"
    else:
        overall_status = "failure"

    result_data = {
        "run_id": run_id,
        "out_dir": run_dir,
        "mode": "sports_local",
        "status": overall_status,
        "requested": num_clips,
        "selected": selected_count,
        "succeeded": succeeded,
        "failed": failed,
        "source_video_url": resolved_source,
        "highlights": highlights,
        "shorts": rendered_shorts,
    }

    manifest = {
        **result_data,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config": {
            "num_clips": num_clips,
            "duration": clip_duration,
            "aspect_ratio": aspect_ratio,
            "crop_style": crop_style,
        },
    }
    save_manifest(run_dir, manifest)

    return result_data
