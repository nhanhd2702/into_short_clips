"""Run context and output artifact isolation.

Creates unique isolated output directories per run:
  output/<source_stem>/<run_id>/
Saves a complete manifest.json recording inputs, configuration, environment,
and per-clip output results.
"""
import datetime
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from .config import LOCAL_OUTPUT_DIR


def sanitize_folder_name(name: str) -> str:
    """Sanitize video name or URL for use in folder path."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", name)
    cleaned = re.sub(r'[\s_]+', '_', cleaned).strip('._ ')
    return cleaned[:40] or "source"


def get_source_stem(source: str) -> str:
    """Derive a friendly folder stem from a file path or URL."""
    source_str = (source or "").strip()
    from .local.downloader import _extract_youtube_video_id
    yt_id = _extract_youtube_video_id(source_str)
    if yt_id:
        return f"yt_{yt_id}"

    parsed = urlparse(source_str)
    path_part = parsed.path if parsed.scheme in ("http", "https", "file") else source_str
    if path_part:
        base = Path(path_part).stem
        if base:
            return sanitize_folder_name(base)
    return "source"


def generate_run_id() -> str:
    """Create a sortable, unique run identifier."""
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uid = uuid.uuid4().hex[:6]
    return f"run_{now}_{short_uid}"


def create_run_directory(
    source: str,
    base_out_dir: Optional[str] = None,
    run_id: Optional[str] = None,
    overwrite: bool = False,
) -> Tuple[str, str]:
    """Create and return (run_directory, run_id).

    If base_out_dir is explicitly given by the user and overwrite=True,
    the directory is used directly. Otherwise, output/<source_stem>/<run_id>/ is created.
    """
    rid = run_id or generate_run_id()
    if base_out_dir and overwrite:
        out_dir = os.path.abspath(base_out_dir)
    elif base_out_dir:
        # User specified custom base_out_dir, nest the run inside it
        stem = get_source_stem(source)
        out_dir = os.path.abspath(os.path.join(base_out_dir, stem, rid))
    else:
        stem = get_source_stem(source)
        out_dir = os.path.abspath(os.path.join(LOCAL_OUTPUT_DIR, stem, rid))

    os.makedirs(out_dir, exist_ok=True)
    return out_dir, rid


def save_manifest(out_dir: str, manifest_data: Dict[str, Any]) -> str:
    """Save manifest.json atomically into the run directory."""
    manifest_path = os.path.join(out_dir, "manifest.json")
    tmp_path = manifest_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, manifest_path)
    return manifest_path
