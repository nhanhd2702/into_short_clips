"""Tests for Phase 3: Model downloader robustness & highlight boundary snapping."""
import hashlib
import json
import os
import shutil
import tempfile
import unittest
import urllib.error
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
    is_model_directory_valid,
    validate_downloaded_file,
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

    def test_complete_part_file_recovered_without_redownload(self):
        """P2 test: complete .part file matching expected SHA-256 is recovered immediately."""
        dest_path = os.path.join(self.test_dir, "model.bin")
        part_path = dest_path + ".part"
        full_content = b"Complete 3600-byte content for model verification" * 80
        with open(part_path, "wb") as f:
            f.write(full_content)
        expected_sha = hashlib.sha256(full_content).hexdigest()

        # Call download_file_resumable: must promote .part to dest without network call
        res = download_file_resumable("http://dummy-url-should-not-be-called", dest_path, expected_sha256=expected_sha)
        self.assertEqual(res, dest_path)
        self.assertTrue(os.path.exists(dest_path))
        self.assertFalse(os.path.exists(part_path))
        self.assertEqual(compute_file_sha256(dest_path), expected_sha)

    def test_http_416_resets_oversized_or_corrupt_part(self):
        """P2 test: HTTP 416 on oversized/corrupted part file resets part and retries cleanly."""
        dest_path = os.path.join(self.test_dir, "config.json")
        part_path = dest_path + ".part"
        # Create an oversized/corrupt part file
        with open(part_path, "wb") as f:
            f.write(b"Oversized corrupt data")

        # Mock urlopen: first attempt raises HTTPError 416, second attempt succeeds with valid JSON
        http_416 = urllib.error.HTTPError(
            url="http://dummy-url",
            code=416,
            msg="Requested Range Not Satisfiable",
            hdrs={},
            fp=None,
        )

        valid_payload = b'{"valid_model": true}\n'
        mock_resp_success = MagicMock()
        mock_resp_success.__enter__.return_value = mock_resp_success
        mock_resp_success.status = 200
        mock_resp_success.headers = {"Content-Length": str(len(valid_payload))}
        mock_resp_success.read.side_effect = [valid_payload, b""]

        with patch("urllib.request.urlopen", side_effect=[http_416, mock_resp_success]):
            res = download_file_resumable("http://dummy-url", dest_path, max_retries=2)
            self.assertEqual(res, dest_path)
            self.assertTrue(os.path.exists(dest_path))

    def test_premature_eof_rejects_truncated_file(self):
        """P2 test: server closes connection before Content-Length is reached; reject dest creation."""
        dest_path = os.path.join(self.test_dir, "config.json")

        mock_resp_truncated = MagicMock()
        mock_resp_truncated.__enter__.return_value = mock_resp_truncated
        mock_resp_truncated.status = 200
        # Claims 3600 bytes but only delivers 10 bytes before EOF
        mock_resp_truncated.headers = {"Content-Length": "3600"}
        mock_resp_truncated.read.side_effect = [b"1234567890", b""]

        with patch("urllib.request.urlopen", return_value=mock_resp_truncated):
            with self.assertRaises(Exception) as ctx:
                download_file_resumable("http://dummy-url", dest_path, max_retries=1)

            # Dest file must NOT have been created!
            self.assertFalse(os.path.exists(dest_path))
            self.assertIn("Premature EOF", str(ctx.exception))

    def test_validate_downloaded_file_rejects_corrupted_metadata(self):
        """P2 test: JSON metadata and vocabulary validations."""
        cfg_path = Path(self.test_dir) / "config.json"
        vocab_path = Path(self.test_dir) / "vocabulary.txt"

        # Truncated JSON
        cfg_path.write_text("{\"model_type\": ", encoding="utf-8")
        self.assertFalse(validate_downloaded_file(cfg_path))

        # Valid JSON
        cfg_path.write_text("{\"model_type\": \"whisper\"}", encoding="utf-8")
        self.assertTrue(validate_downloaded_file(cfg_path))

        # 10-byte vocabulary
        vocab_path.write_text("token1\ntok", encoding="utf-8")
        self.assertFalse(validate_downloaded_file(vocab_path))

        # Full vocabulary >= 100 bytes
        vocab_path.write_text("\n".join(f"token_{i}" for i in range(50)), encoding="utf-8")
        self.assertTrue(validate_downloaded_file(vocab_path))


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
        start, end = snap_to_segment_boundaries(
            start_time=0.0,
            end_time=50.0,
            segments=self.segments,
            duration=self.duration,
            min_duration=40.0,
            max_duration=65.0,
        )

        self.assertGreaterEqual(start, 5.5)
        self.assertIn(end, [s["end"] for s in self.segments])
        self.assertGreaterEqual(end - start, 40.0)
        self.assertLessEqual(end - start, 65.0)

    def test_snap_aligns_to_exact_sentence_punctuation(self):
        start, end = snap_to_segment_boundaries(
            start_time=9.2,
            end_time=55.0,
            segments=self.segments,
            duration=self.duration,
            min_duration=40.0,
            max_duration=65.0,
        )

        self.assertEqual(start, 9.2)
        self.assertIn(end, [58.0, 65.0])
        self.assertNotEqual(end, 69.2)

    def test_snap_does_not_cut_mid_word_or_mid_segment(self):
        start, end = snap_to_segment_boundaries(
            start_time=12.0,
            end_time=60.0,
            segments=self.segments,
            duration=self.duration,
            min_duration=40.0,
            max_duration=65.0,
        )
        self.assertEqual(start, 9.2)

    def test_snap_trims_non_speech_intro_montage(self):
        """P2 test: TED-style video where segment 0 has 5.8s music montage before speech begins."""
        ted_segments = [
            {
                "start": 0.0,
                "end": 22.24,
                "speech_start": 5.8,
                "text": "When I was in college, I thought I had everything figured out completely.",
                "words": [
                    {"word": "When", "start": 5.8, "end": 6.1},
                    {"word": "I", "start": 6.1, "end": 6.3},
                    {"word": "was", "start": 6.3, "end": 6.6},
                    {"word": "in", "start": 6.6, "end": 6.8},
                    {"word": "college,", "start": 6.8, "end": 7.3},
                ],
            },
            {
                "start": 22.5,
                "end": 45.0,
                "speech_start": 22.5,
                "text": "Then life tested me in ways I never could have imagined.",
            },
            {
                "start": 45.5,
                "end": 57.68,
                "speech_start": 45.5,
                "text": "That is the fundamental power of small daily changes.",
            },
        ]

        # Candidate selected 0.0s -> 60.0s (from beginning of video)
        start, end = snap_to_segment_boundaries(
            start_time=0.0,
            end_time=60.0,
            segments=ted_segments,
            duration=65.0,
            min_duration=40.0,
            max_duration=65.0,
        )

        # The 0.0 - 5.8s music montage MUST be trimmed!
        self.assertEqual(start, 5.8)
        # End must be snapped to sentence boundary
        self.assertEqual(end, 57.68)
        self.assertGreaterEqual(end - start, 40.0)

    def test_sanitize_highlights_integrates_snapping(self):
        raw = [
            {
                "title": "Viral Hook Clip",
                "start_time": 0.0,
                "end_time": 30.0,
                "score": 95,
                "hook_sentence": "Tại sao hầu hết mọi người đều cảm thấy kiệt sức?",
                "virality_reason": "High dopamine contrast",
            }
        ]

        sanitized = _sanitize_highlights(raw, duration=self.duration, segments=self.segments)
        self.assertEqual(len(sanitized), 1)
        h = sanitized[0]

        self.assertGreaterEqual(h["start_time"], 5.5)
        self.assertIn(h["end_time"], [s["end"] for s in self.segments])
        self.assertGreaterEqual(h["end_time"] - h["start_time"], 40.0)


if __name__ == "__main__":
    unittest.main()
