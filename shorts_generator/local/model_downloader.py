"""Robust Resumable Whisper Model Downloader with SHA-256 Verification.

Features:
- Resumable chunked HTTP downloads (HTTP Range header) with .part temporary files.
- SHA-256 checksum verification of model weights to prevent corrupted caches.
- Downloads directly to a clean local directory and loads 100% offline.
"""
import hashlib
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Dict, Optional

# Verified SHA-256 checksums for Systran faster-whisper model.bin files
KNOWN_MODEL_SHA256: Dict[str, str] = {
    "tiny": "dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1",
    "base": "d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9",
    "small": "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
}

# Required files for faster-whisper CTranslate2 model
WHISPER_FILES = [
    "config.json",
    "tokenizer.json",
    "vocabulary.txt",
    "model.bin",
]


def compute_file_sha256(file_path: str, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


def download_file_resumable(
    url: str,
    dest_path: str,
    expected_sha256: Optional[str] = None,
    chunk_size: int = 1024 * 1024,
    max_retries: int = 5,
) -> str:
    """Download a file with HTTP Range support (resumable) and SHA-256 verification."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part_path = dest.with_name(dest.name + ".part")

    # If destination already exists and verified, return
    if dest.is_file() and dest.stat().st_size > 0:
        if expected_sha256:
            actual = compute_file_sha256(str(dest))
            if actual == expected_sha256.lower():
                return str(dest)
            # Corrupted existing file, delete and re-download
            dest.unlink(missing_ok=True)
        else:
            return str(dest)

    for attempt in range(1, max_retries + 1):
        existing_size = part_path.stat().st_size if part_path.is_file() else 0
        headers = {"User-Agent": "into_short_clips/1.0"}
        if existing_size > 0:
            headers["Range"] = f"bytes={existing_size}-"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                total_header = resp.headers.get("Content-Length")
                total_bytes = int(total_header) + existing_size if total_header else None

                mode = "ab" if status == 206 and existing_size > 0 else "wb"
                if mode == "wb":
                    existing_size = 0

                fname = dest.name
                with open(part_path, mode) as f:
                    downloaded = existing_size
                    while True:
                        buf = resp.read(chunk_size)
                        if not buf:
                            break
                        f.write(buf)
                        downloaded += len(buf)
                        if total_bytes:
                            pct = (downloaded / total_bytes) * 100
                            mb = downloaded / (1024 * 1024)
                            total_mb = total_bytes / (1024 * 1024)
                            print(f"\r[whisper-download] {fname}: {pct:.1f}% ({mb:.1f}MB/{total_mb:.1f}MB)", end="", flush=True)

            print()  # Newline after download completes

            # Verify SHA-256 if expected
            if expected_sha256:
                print(f"[whisper-download] Verifying SHA-256 for {fname}...", flush=True)
                actual_sha = compute_file_sha256(str(part_path))
                if actual_sha != expected_sha256.lower():
                    print(
                        f"[whisper-download] Checksum mismatch! Expected {expected_sha256[:12]}..., got {actual_sha[:12]}...",
                        flush=True,
                    )
                    part_path.unlink(missing_ok=True)
                    if attempt < max_retries:
                        continue
                    raise RuntimeError(f"SHA-256 checksum mismatch for {url}")

            # Atomically rename .part to destination
            if dest.is_file():
                dest.unlink(missing_ok=True)
            part_path.rename(dest)
            return str(dest)

        except Exception as e:
            print(f"\n[whisper-download] Attempt {attempt}/{max_retries} failed for {dest.name}: {e}", flush=True)
            if attempt == max_retries:
                raise RuntimeError(f"Failed to download {url} after {max_retries} attempts: {e}") from e

    raise RuntimeError(f"Failed to download {url}")


def ensure_whisper_model(model_name: str, cache_dir: Optional[str] = None) -> str:
    """Ensure faster-whisper model files are downloaded, verified, and ready on disk.

    Returns the directory path containing the verified model files.
    """
    model_name = (model_name or "base").strip().lower()
    root = Path(cache_dir or "output") / "models" / "whisper" / model_name
    root.mkdir(parents=True, exist_ok=True)

    # Check if all files exist and model.bin passes SHA-256
    model_bin = root / "model.bin"
    expected_sha = KNOWN_MODEL_SHA256.get(model_name)
    all_exist = all((root / f).is_file() for f in WHISPER_FILES)

    if all_exist:
        if expected_sha:
            actual = compute_file_sha256(str(model_bin))
            if actual == expected_sha.lower():
                return str(root)
            print(f"[whisper-model] Corrupted {model_bin.name} detected, re-downloading...", flush=True)
        else:
            return str(root)

    print(f"\n[whisper-model] Ensuring model '{model_name}' weights with resumable download & SHA-256...", flush=True)

    base_url = f"https://huggingface.co/Systran/faster-whisper-{model_name}/resolve/main"

    for fname in WHISPER_FILES:
        file_url = f"{base_url}/{fname}"
        dest_file = root / fname
        sha = expected_sha if fname == "model.bin" else None
        download_file_resumable(file_url, str(dest_file), expected_sha256=sha)

    print(f"[whisper-model] Model '{model_name}' verified and ready at: {root}\n", flush=True)
    return str(root)
