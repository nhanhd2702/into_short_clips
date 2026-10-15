"""Sports and Action Highlight Generator.

Detects high-energy moments (cheers, shouts, smashes, points) via audio volume peaks,
and formats wide-angle sports footage into vertical 9:16 Shorts using Pillarbox Blur
(entire court/field visible in center, aesthetic blurred background top/bottom).
"""
import os
import subprocess
import wave
import numpy as np
from typing import Dict, List, Optional

from .config import LOCAL_OUTPUT_DIR


def extract_audio_peaks(
    source_path: str,
    num_clips: int = 5,
    min_distance_seconds: float = 60.0,
    clip_duration: float = 45.0,
    lead_in_seconds: float = 35.0,
) -> List[Dict]:
    """Find the top `num_clips` audio energy peaks in a sports video."""
    temp_wav = os.path.join(LOCAL_OUTPUT_DIR, "_temp_analysis.wav")
    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)

    print(f"[sports] Analyzing audio waveform for {source_path}...", flush=True)
    subprocess.run([
        "ffmpeg", "-y", "-i", source_path,
        "-vn", "-ac", "1", "-ar", "8000",
        temp_wav
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        with wave.open(temp_wav, "rb") as wf:
            rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    finally:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

    total_seconds = len(audio) / rate
    win = int(2.0 * rate)   # 2-second window
    step = int(1.0 * rate)  # 1-second step

    energies = []
    timestamps = []
    for i in range(0, len(audio) - win, step):
        chunk = audio[i : i + win]
        rms = float(np.sqrt(np.mean(chunk**2)))
        energies.append(rms)
        timestamps.append(i / rate)

    energies_arr = np.array(energies)
    timestamps_arr = np.array(timestamps)

    # Sort descending by RMS energy
    sorted_idx = np.argsort(energies_arr)[::-1]
    picked = []
    for idx in sorted_idx:
        t = float(timestamps_arr[idx])
        if all(abs(t - p) >= min_distance_seconds for p in picked):
            picked.append(t)
        if len(picked) >= num_clips:
            break

    picked.sort()
    clips = []
    for i, t in enumerate(picked, 1):
        start = max(0.0, t - lead_in_seconds)
        end = min(total_seconds, start + clip_duration)
        dur = end - start
        m, s = int(t // 60), int(t % 60)
        clips.append({
            "index": i,
            "title": f"Highlight #{i:02d} (Peak at {m:02d}:{s:02d})",
            "start_time": start,
            "end_time": end,
            "peak_time": t,
            "duration": dur,
            "score": 90 - (i * 2),
        })

    return clips


def render_sports_clip_916(
    source_path: str,
    start_time: float,
    duration: float,
    out_path: str,
) -> str:
    """Render a 9:16 vertical short with pillarbox blur."""
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
        "[0:v]scale=1080:-1[fg];"
        "[bg][fg]overlay=0:(H-h)/2"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_time:.3f}",
        "-t", f"{duration:.3f}",
        "-i", source_path,
        "-filter_complex", filter_complex,
        "-c:v", "libx264",
        "-preset", "faster",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "128k",
        "-threads", "0",
        out_path
    ]
    subprocess.run(cmd, check=True)
    return out_path


def generate_sports_shorts(
    source_path: str,
    num_clips: int = 5,
    clip_duration: float = 45.0,
    out_dir: Optional[str] = None,
) -> Dict:
    """End-to-end sports highlight extraction and rendering."""
    out_dir = out_dir or LOCAL_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    highlights = extract_audio_peaks(
        source_path,
        num_clips=num_clips,
        clip_duration=clip_duration,
    )

    print(f"\n[sports] Found {len(highlights)} peak moments. Rendering 9:16 clips...", flush=True)
    rendered_shorts = []
    for h in highlights:
        out_name = f"sports_short_{h['index']:02d}.mp4"
        out_path = os.path.join(out_dir, out_name)
        print(f"[sports] Rendering #{h['index']:02d}: {h['title']} ({h['duration']:.1f}s) -> {out_name}", flush=True)
        try:
            render_sports_clip_916(
                source_path=source_path,
                start_time=h["start_time"],
                duration=h["duration"],
                out_path=out_path,
            )
            rendered_shorts.append({**h, "clip_url": out_path})
        except Exception as e:
            print(f"[sports] Failed #{h['index']:02d}: {e}", flush=True)
            rendered_shorts.append({**h, "clip_url": None, "error": str(e)})

    return {
        "mode": "sports_local",
        "source_video_url": source_path,
        "highlights": highlights,
        "shorts": rendered_shorts,
    }
