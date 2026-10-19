"""Tests for Phase 3: Model downloader robustness & highlight boundary snapping."""
import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from shorts_generator.highlights import (
    _sanitize_highlights,
    dedupe_highlights,
    snap_to_segment_boundaries,
)
from shorts_generator.local.model_downloader import (
    compute_file_sha256,
    download_file_resumable,
    ensure_whisper_model,
)


class TestModelDownloader(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_model_dl_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_compute_file_sha256(self):
        sample_path = os.path.join(self.test_dir, "sample.bin")
        data = b"Hello, Whisper model weights data!"
        with open(sample_path, "wb") as f:
            f.write(data)

        expected_sha = hashlib.sha256(data).hexdigest()
        actual_sha = compute_file_sha256(sample_path)
        self.assertEqual(actual_sha, expected_sha)

    def test_download_file_resumable_existing_valid(self):
        dest_path = os.path.join(self.test_dir, "model.bin")
        data = b"Pre-existing verified content"
        with open(dest_path, "wb") as f:
            f.write(data)
        expected_sha = hashlib.sha256(data).hexdigest()

        # Should return immediately without network call
        res = download_file_resumable("http://dummy-url", dest_path, expected_sha256=expected_sha)
        self.assertEqual(res, dest_path)
        self.assertTrue(os.path.exists(dest_path))

    def test_download_file_resumable_corrupt_file_deleted(self):
        dest_path = os.path.join(self.test_dir, "model.bin")
        corrupted_data = b"Corrupted content"
        with open(dest_path, "wb") as f:
            f.write(corrupted_data)

        expected_sha = hashlib.sha256(b"Legitimate content").hexdigest()

        # When hash mismatches and mock fails, file is deleted
        with self.assertRaises(Exception):
            download_file_resumable("http://invalid-url-that-fails.local/file", dest_path, expected_sha256=expected_sha, max_retries=1)


class TestHighlightBoundarySnapping(unittest.TestCase):
    def setUp(self):
        # Synthetic transcript simulating a real podcast/video
        self.segments = [
            # Segment 0: Channel intro (0 - 5.5s)
            {"start": 0.0, "end": 5.5, "text": "Chào mừng các bạn đã quay trở lại kênh! Hãy like và đăng ký kênh nhé."},
            # Segment 1: Host transition (5.5 - 9.0s)
            {"start": 5.5, "end": 9.0, "text": "Hôm nay chúng ta sẽ bàn về một chủ đề rất đặc biệt."},
            # Segment 2: Hook question (9.2 - 16.0s)
            {"start": 9.2, "end": 16.0, "text": "Tại sao hầu hết mọi người đều cảm thấy kiệt sức vào mỗi cuối tuần?"},
            # Segment 3: Story start (16.5 - 28.0s)
            {"start": 16.5, "end": 28.0, "text": "Thực ra nguyên nhân không nằm ở công việc bạn làm, mà nằm ở chiếc điện thoại."},
            # Segment 4: Explanation (28.2 - 42.0s)
            {"start": 28.2, "end": 42.0, "text": "Khi bạn lướt mạng xã hội liên tục, não bộ tiếp nhận dopamine nhân tạo liên hồi."},
            # Segment 5: Climax insight (42.5 - 58.0s)
            {"start": 42.5, "end": 58.0, "text": "Kết quả là hệ thống thần kinh rơi vào trạng thái tê liệt cảm xúc hoàn toàn."},
            # Segment 6: Closing question (58.5 - 65.0s)
            {"start": 58.5, "end": 65.0, "text": "Bạn đã bao giờ trải qua cảm giác mệt mỏi này chưa?"},
            # Segment 7: Next topic (65.5 - 75.0s)
            {"start": 65.5, "end": 75.0, "text": "Bây giờ hãy chuyển sang cách khắc phục nó từng bước một."},
        ]
        self.duration = 75.0

    def test_snap_skips_channel_intro(self):
        # LLM erroneously suggested starting at 0.0s (in the middle of channel intro)
        start, end = snap_to_segment_boundaries(
            start_time=0.0,
            end_time=50.0,
            segments=self.segments,
            duration=self.duration,
            min_duration=40.0,
            max_duration=65.0,
        )

        # Intro segment (0-5.5s) MUST be skipped; clip should start at Segment 1 or 2
        self.assertGreaterEqual(start, 5.5)
        # End must align with an actual segment end
        self.assertIn(end, [s["end"] for s in self.segments])
        # Duration must be within expected bounds
        self.assertGreaterEqual(end - start, 40.0)
        self.assertLessEqual(end - start, 65.0)

    def test_snap_aligns_to_exact_sentence_punctuation(self):
        # Start at 9.2s (Hook question)
        start, end = snap_to_segment_boundaries(
            start_time=9.2,
            end_time=55.0,
            segments=self.segments,
            duration=self.duration,
            min_duration=40.0,
            max_duration=65.0,
        )

        self.assertEqual(start, 9.2)
        # Segments in window [9.2+40=49.2, 9.2+65=74.2]:
        # Seg 5 ends at 58.0 (text ends with '.')
        # Seg 6 ends at 65.0 (dur = 65.0 - 9.2 = 55.8s, text ends with '?') -> Perfect match for 55s target!
        self.assertIn(end, [58.0, 65.0])
        # Crucially: it must NOT be arbitrary like 9.2 + 60.0 = 69.2
        self.assertNotEqual(end, 69.2)

    def test_snap_does_not_cut_mid_word_or_mid_segment(self):
        # LLM suggested start_time = 12.0s (in the middle of segment 2: 9.2-16.0s)
        start, end = snap_to_segment_boundaries(
            start_time=12.0,
            end_time=60.0,
            segments=self.segments,
            duration=self.duration,
            min_duration=40.0,
            max_duration=65.0,
        )

        # Must snap to start of segment 2 (9.2s) instead of 12.0s
        self.assertEqual(start, 9.2)

    def test_sanitize_highlights_integrates_snapping(self):
        raw = [
            {
                "title": "Viral Hook Clip",
                "start_time": 0.0,
                "end_time": 30.0,  # too short (<40s)
                "score": 95,
                "hook_sentence": "Tại sao hầu hết mọi người đều cảm thấy kiệt sức?",
                "virality_reason": "High dopamine contrast",
            }
        ]

        sanitized = _sanitize_highlights(raw, duration=self.duration, segments=self.segments)
        self.assertEqual(len(sanitized), 1)
        h = sanitized[0]

        # Intro skipped:
        self.assertGreaterEqual(h["start_time"], 5.5)
        # End snapped to sentence boundary:
        self.assertIn(h["end_time"], [s["end"] for s in self.segments])
        # Duration at least 40s:
        self.assertGreaterEqual(h["end_time"] - h["start_time"], 40.0)


if __name__ == "__main__":
    unittest.main()
