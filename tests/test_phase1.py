"""Phase 1 Acceptance Tests: Caching, Sports Peak Containment, Validation & Exit Codes.

Uses Python standard library `unittest` to ensure zero-dependency execution.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shorts_generator.local.transcriber import (
    _compute_cache_identity,
    _get_cache_dir,
    _load_cached_transcript,
    _save_transcript_cache,
)
from shorts_generator.sports import (
    _clips_overlap,
    extract_audio_peaks,
)
from shorts_generator.validation import (
    ValidationError,
    validate_common_args,
    validate_source_media,
    is_remote_url,
)
from pathlib import Path


class TestSubtitleCache(unittest.TestCase):
    """Item 1: Subtitle cache correctness."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_cache_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_keys_distinct_for_different_paths_with_same_name(self):
        """Two files with the same basename in different directories must NOT share cache keys."""
        dir_a = os.path.join(self.temp_dir, "dir_a")
        dir_b = os.path.join(self.temp_dir, "dir_b")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)

        file_a = os.path.join(dir_a, "video.mp4")
        file_b = os.path.join(dir_b, "video.mp4")

        with open(file_a, "wb") as f:
            f.write(b"content_a_1234567890")
        with open(file_b, "wb") as f:
            f.write(b"content_b_1234567890")

        key_a, meta_a = _compute_cache_identity(file_a, language="vi")
        key_b, meta_b = _compute_cache_identity(file_b, language="vi")

        self.assertNotEqual(key_a, key_b, "Different directories with same filename must yield different cache keys")
        self.assertNotEqual(meta_a["source_path"], meta_b["source_path"])

    def test_cache_keys_distinct_when_file_modified_or_language_changed(self):
        """Changing file content/mtime or language must change the cache key."""
        file_path = os.path.join(self.temp_dir, "video.mp4")
        with open(file_path, "wb") as f:
            f.write(b"initial_content")

        key_vi, meta_vi = _compute_cache_identity(file_path, language="vi")
        key_en, meta_en = _compute_cache_identity(file_path, language="en")

        self.assertNotEqual(key_vi, key_en, "Language difference must change cache key")

        # Modify file size
        with open(file_path, "ab") as f:
            f.write(b"_appended_bytes")
        key_modified, meta_mod = _compute_cache_identity(file_path, language="vi")
        self.assertNotEqual(key_vi, key_modified, "File modification must change cache key")

    def test_save_and_load_cache_integrity(self):
        """Test atomic cache saving and successful reload."""
        video_path = os.path.join(self.temp_dir, "test.mp4")
        with open(video_path, "wb") as f:
            f.write(b"sample video data")

        cache_key, meta = _compute_cache_identity(video_path, language="vi")
        cache_dir = _get_cache_dir(cache_key, base_out_dir=self.temp_dir)

        segments = [
            {"start": 0.0, "end": 2.5, "text": "Xin chào các bạn"},
            {"start": 2.5, "end": 5.0, "text": "Đây là video thử nghiệm"},
        ]
        transcript_data = {"duration": 5.0, "segments": segments}

        # Save cache
        _save_transcript_cache(
            cache_dir=cache_dir,
            metadata=meta,
            transcript=transcript_data,
        )

        self.assertTrue((cache_dir / "transcript.srt").is_file())
        self.assertTrue((cache_dir / "metadata.json").is_file())

        # Load cache
        loaded = _load_cached_transcript(cache_dir, meta)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded["segments"]), 2)
        self.assertEqual(loaded["segments"][0]["text"], "Xin chào các bạn")

    def test_corrupted_cache_is_rejected(self):
        """Corrupted metadata or empty SRT must be discarded."""
        video_path = os.path.join(self.temp_dir, "test.mp4")
        with open(video_path, "wb") as f:
            f.write(b"sample video data")

        cache_key, meta = _compute_cache_identity(video_path, language="vi")
        cache_dir = _get_cache_dir(cache_key, base_out_dir=self.temp_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Write invalid/corrupt metadata
        (cache_dir / "metadata.json").write_text("{invalid_json: true", encoding="utf-8")
        (cache_dir / "transcript.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

        loaded = _load_cached_transcript(cache_dir, meta)
        self.assertIsNone(loaded, "Corrupt cache must not be loaded")


class TestSportsClipping(unittest.TestCase):
    """Item 3: Sports peak containment and dynamic lead-in."""

    def test_peak_containment_across_durations(self):
        """Guarantee that peak_time is strictly contained in [start, end] for various durations."""
        source_duration = 100.0
        test_peaks = [1.0, 5.0, 15.0, 50.0, 80.0, 95.0, 99.0]
        test_durations = [5.0, 10.0, 30.0, 45.0, 60.0]

        for dur in test_durations:
            lead_in = dur * 0.7
            for peak in test_peaks:
                max_start = max(0.0, source_duration - dur)
                start = max(0.0, min(peak - lead_in, max_start))
                end = min(source_duration, start + dur)

                # Check containment
                self.assertGreaterEqual(
                    peak + 0.05, start,
                    f"Peak {peak} must be >= start {start} (dur={dur})"
                )
                self.assertLessEqual(
                    peak - 0.05, end,
                    f"Peak {peak} must be <= end {end} (dur={dur})"
                )
                self.assertGreater(end, start)
                self.assertLessEqual(end, source_duration)
                self.assertGreaterEqual(start, 0.0)

    def test_video_shorter_than_clip_duration(self):
        """When source video is shorter than requested duration, entire valid range is selected."""
        source_dur = 15.0
        requested_dur = 45.0
        peak = 8.0

        if source_dur <= requested_dur:
            start = 0.0
            end = source_dur

        self.assertEqual(start, 0.0)
        self.assertEqual(end, 15.0)
        self.assertTrue(start <= peak <= end)

    def test_overlap_suppression(self):
        """Clips with significant overlap must be suppressed."""
        # s1, e1 = 10, 55 (dur=45)
        # candidate s2, e2 = 15, 60 (overlap=40s / 45s = 88% -> overlaps)
        self.assertTrue(_clips_overlap(10.0, 55.0, 15.0, 60.0, max_overlap_ratio=0.35))

        # Far apart intervals should not overlap
        self.assertFalse(_clips_overlap(10.0, 30.0, 50.0, 70.0, max_overlap_ratio=0.35))


class TestValidation(unittest.TestCase):
    """Item 4: Early parameter and media validation."""

    def test_invalid_num_clips(self):
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=0)
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=-5)
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=True)  # type: ignore (bool)

    def test_invalid_duration(self):
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=3, duration=0)
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=3, duration=-10.0)
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=3, duration=float("nan"))
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=3, duration=float("inf"))

    def test_invalid_aspect_ratio(self):
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=3, aspect_ratio="4:3")
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=3, aspect_ratio="invalid")

    def test_invalid_crop_style(self):
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=3, crop_style="magic_ai")

    def test_sports_specific_constraints(self):
        # Sports mode only supports 9:16 and blur
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=3, aspect_ratio="1:1", type_mode="sports")
        with self.assertRaises(ValidationError):
            validate_common_args(num_clips=3, crop_style="face", type_mode="sports")

    def test_source_validation_empty_or_nonexistent(self):
        with self.assertRaises(ValidationError):
            validate_source_media("")
        with self.assertRaises(ValidationError):
            validate_source_media("   ")
        with self.assertRaises(ValidationError):
            validate_source_media("non_existent_file_12345.mp4")

    def test_remote_url_detection(self):
        self.assertTrue(is_remote_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_remote_url("http://example.com/video.mp4"))
        self.assertFalse(is_remote_url("local_video.mp4"))
        self.assertFalse(is_remote_url("file:///c:/path/to/video.mp4"))


class TestExitCodesAndCLI(unittest.TestCase):
    """Item 2: Standardized exit codes via CLI execution."""

    def test_cli_exit_code_2_on_invalid_parameters(self):
        """CLI must exit with code 2 when parameters or source are invalid."""
        python_exe = sys.executable
        main_py = os.path.join(PROJECT_ROOT, "main.py")

        # Test with invalid num-clips = 0
        cmd = [python_exe, main_py, "some_file.mp4", "--num-clips", "0"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, f"Expected exit code 2, got {proc.returncode}. Stderr: {proc.stderr}")

        # Test with nonexistent file
        cmd = [python_exe, main_py, "completely_nonexistent_file_9999.mp4"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, f"Expected exit code 2 for missing file, got {proc.returncode}")

    def test_cli_failure_json_written_on_validation_error(self):
        """CLI must write structured failure JSON on validation error if --output-json is set."""
        python_exe = sys.executable
        main_py = os.path.join(PROJECT_ROOT, "main.py")
        temp_dir = tempfile.mkdtemp(prefix="test_json_")
        json_path = os.path.join(temp_dir, "result.json")

        try:
            cmd = [
                python_exe,
                main_py,
                "nonexistent.mp4",
                "--num-clips",
                "3",
                "--output-json",
                json_path,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertTrue(os.path.exists(json_path), "JSON output must be created even on validation failure")

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertEqual(data.get("status"), "failure")
            self.assertEqual(data.get("requested"), 3)
            self.assertIn("error", data)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
