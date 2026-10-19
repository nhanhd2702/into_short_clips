"""Robust Resumable Whisper Model Downloader with SHA-256 Verification.

Features:
- Resumable chunked HTTP downloads (HTTP Range header) with .part temporary files.
- SHA-256 checksum verification of model weights to prevent corrupted caches.
- Complete metadata integrity validation (valid JSON, minimum byte checks, premature EOF detection).
- Resilient HTTP 416 handling: validates complete .part files or resets oversized/corrupted parts.
- Downloads directly to a clean local directory and loads 100% offline.
"""
import hashlib
import json
import os
import re
import shutil
import urllib.error
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


def validate_downloaded_file(path: Path) -> bool:
    """Validate file integrity: JSON parseable, non-empty, minimum length."""
    if not path.is_file() or path.stat().st_size == 0:
        return False

    name = path.name
    # Strip .part suffix for validation if validating temporary download
    if name.endswith(".part"):
        name = name[:-5]

    if name.endswith(".json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(data, (dict, list)) and len(data) > 0
        except Exception:
            return False

    if name == "vocabulary.txt":
        return path.stat().st_size >= 100

    if name == "model.bin":
        return path.stat().st_size >= 1_000_000

    return True


def is_model_directory_valid(root: Path, model_name: str) -> bool:
    """Check that all required model files are present and uncorrupted."""
    for fname in WHISPER_FILES:
        fpath = root / fname
        if not validate_downloaded_file(fpath):
            return False
        if fname == "model.bin":
            expected_sha = KNOWN_MODEL_SHA256.get(model_name)
            if expected_sha and compute_file_sha256(str(fpath)) != expected_sha.lower():
                return False
    return True


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

    # 1. If destination already exists and verified, return immediately
    if dest.is_file() and dest.stat().st_size > 0:
        if expected_sha256:
            actual = compute_file_sha256(str(dest))
            if actual == expected_sha256.lower():
                return str(dest)
            # Corrupted existing file, delete and re-download
            dest.unlink(missing_ok=True)
        elif validate_downloaded_file(dest):
            return str(dest)
        else:
            dest.unlink(missing_ok=True)

    # 2. If .part already exists and matches expected SHA-256, promote directly (no network call)
    if part_path.is_file() and part_path.stat().st_size > 0:
        if expected_sha256:
            if compute_file_sha256(str(part_path)) == expected_sha256.lower():
                if dest.is_file():
                    dest.unlink(missing_ok=True)
                part_path.rename(dest)
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

                # Determine total bytes from Content-Range or Content-Length
                total_bytes = None
                headers = getattr(resp, "headers", None)
                if headers and hasattr(headers, "get"):
                    cr = headers.get("Content-Range")
                    if isinstance(cr, str):
                        m = re.search(r"/(\d+)$", cr)
                        if m:
                            total_bytes = int(m.group(1))
                    if total_bytes is None:
                        cl = headers.get("Content-Length")
                        if cl is not None:
                            try:
                                total_bytes = int(cl) + existing_size
                            except (ValueError, TypeError):
                                pass

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

            print()  # Newline after stream finishes

            # Check for premature EOF / truncated response
            if total_bytes is not None and downloaded < total_bytes:
                raise IOError(
                    f"Premature EOF: received {downloaded}/{total_bytes} bytes for {fname}"
                )

            # Validate content integrity (JSON valid, non-empty text, etc.)
            if not validate_downloaded_file(part_path):
                part_path.unlink(missing_ok=True)
                raise ValueError(f"Downloaded file {dest.name} failed content/format validation")

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

        except urllib.error.HTTPError as e:
            if e.code == 416:
                # HTTP 416 Range Not Satisfiable:
                # 1. Check if the part file already has the full valid content
                if expected_sha256 and part_path.is_file():
                    if compute_file_sha256(str(part_path)) == expected_sha256.lower():
                        if dest.is_file():
                            dest.unlink(missing_ok=True)
                        part_path.rename(dest)
                        return str(dest)

                # 2. Oversized or corrupted part: wipe it and retry from byte 0
                print(
                    f"\n[whisper-download] HTTP 416 Range Not Satisfiable for {dest.name}. Resetting part file and retrying from scratch...",
                    flush=True,
                )
                part_path.unlink(missing_ok=True)
                if attempt < max_retries:
                    continue
                raise RuntimeError(f"HTTP 416 on {url} after exhausting retries") from e

            print(f"\n[whisper-download] Attempt {attempt}/{max_retries} failed for {dest.name}: {e}", flush=True)
            if attempt == max_retries:
                raise RuntimeError(f"Failed to download {url} after {max_retries} attempts: {e}") from e

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

    # Check if all files exist, are uncorrupted, and model.bin passes SHA-256
    if is_model_directory_valid(root, model_name):
        return str(root)

    print(f"\n[whisper-model] Ensuring model '{model_name}' weights with resumable download & SHA-256...", flush=True)

    base_url = f"https://huggingface.co/Systran/faster-whisper-{model_name}/resolve/main"
    expected_sha = KNOWN_MODEL_SHA256.get(model_name)

    for fname in WHISPER_FILES:
        dest_file = root / fname
        # If this individual file is already valid, skip downloading it
        if validate_downloaded_file(dest_file):
            if fname != "model.bin" or (expected_sha and compute_file_sha256(str(dest_file)) == expected_sha.lower()):
                continue

        # File missing or invalid -> download it
        dest_file.unlink(missing_ok=True)
        file_url = f"{base_url}/{fname}"
        sha = expected_sha if fname == "model.bin" else None
        download_file_resumable(file_url, str(dest_file), expected_sha256=sha)

    # Final readiness verification
    if not is_model_directory_valid(root, model_name):
        raise RuntimeError(f"Model directory {root} failed final validation checks for model '{model_name}'")

    print(f"[whisper-model] Model '{model_name}' verified and ready at: {root}\n", flush=True)
    return str(root)
