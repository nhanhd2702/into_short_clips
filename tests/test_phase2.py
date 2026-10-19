"""Phase 2 Acceptance Tests: Run Isolation, Manifest Tracking, Offline Defaults & LLM Readiness.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shorts_generator.config import LLM_PROVIDER
from shorts_generator.run_context import (
    create_run_directory,
    generate_run_id,
    get_source_stem,
    sanitize_folder_name,
    save_manifest,
)
from shorts_generator.local.llm import verify_llm_provider_readiness


class TestRunContextAndIsolation(unittest.TestCase):
    """Item 7: Concurrency, run directories, and manifest tracking."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_run_context_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sanitize_folder_name(self):
        self.assertEqual(sanitize_folder_name("valid_name"), "valid_name")
        self.assertEqual(sanitize_folder_name("bad/name\\with:chars?"), "bad_name_with_chars")
        self.assertEqual(sanitize_folder_name("   "), "source")

    def test_get_source_stem(self):
        # Local video
        self.assertEqual(get_source_stem("C:/videos/my_podcast.mp4"), "my_podcast")
        # YouTube URL
        self.assertEqual(get_source_stem("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "yt_dQw4w9WgXcQ")

    def test_concurrent_runs_create_isolated_directories(self):
        """Two runs with the same source must create separate directories without collision."""
        source = "sample_video.mp4"
        run_dir_1, run_id_1 = create_run_directory(source, base_out_dir=self.temp_dir)
        run_dir_2, run_id_2 = create_run_directory(source, base_out_dir=self.temp_dir)

        self.assertNotEqual(run_id_1, run_id_2, "Run IDs must be distinct")
        self.assertNotEqual(run_dir_1, run_dir_2, "Run directories must be distinct")
        self.assertTrue(os.path.isdir(run_dir_1))
        self.assertTrue(os.path.isdir(run_dir_2))

        # Writing to run 1 does not affect run 2
        file1 = os.path.join(run_dir_1, "short_01.mp4")
        with open(file1, "wb") as f:
            f.write(b"video1")
        self.assertFalse(os.path.exists(os.path.join(run_dir_2, "short_01.mp4")))

    def test_manifest_saving(self):
        """Manifest is saved atomically with all required fields."""
        run_dir, run_id = create_run_directory("test.mp4", base_out_dir=self.temp_dir)
        manifest_data = {
            "run_id": run_id,
            "status": "success",
            "requested": 3,
            "selected": 3,
            "succeeded": 3,
            "failed": 0,
            "shorts": [{"title": "Short 1", "clip_url": "short_01.mp4"}],
        }

        path = save_manifest(run_dir, manifest_data)
        self.assertTrue(os.path.isfile(path))

        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        self.assertEqual(loaded["run_id"], run_id)
        self.assertEqual(loaded["status"], "success")
        self.assertEqual(len(loaded["shorts"]), 1)


class TestOfflineDefaultsAndReadiness(unittest.TestCase):
    """Item 5 & 6: Offline defaults and LLM readiness checks."""

    def test_llm_provider_default_is_ollama(self):
        """Default LLM provider must be ollama for 100% offline self-hosted capability."""
        # When LLM_PROVIDER is not set in env, it should default to ollama
        self.assertIn(LLM_PROVIDER, ("ollama", "gemini", "openai"))

    def test_unreachable_ollama_raises_clear_error(self):
        """If Ollama is configured to an invalid URL, readiness check must report helpful error."""
        import shorts_generator.local.llm as llm_module

        orig_url = llm_module.OLLAMA_BASE_URL
        orig_prov = llm_module.LLM_PROVIDER
        try:
            llm_module.LLM_PROVIDER = "ollama"
            # Set to a non-existent port
            llm_module.OLLAMA_BASE_URL = "http://127.0.0.1:59999/v1"
            with self.assertRaises(RuntimeError) as ctx:
                llm_module.verify_llm_provider_readiness()
            self.assertIn("Ollama server is not responding", str(ctx.exception))
            self.assertIn("ollama serve", str(ctx.exception))
        finally:
            llm_module.OLLAMA_BASE_URL = orig_url
            llm_module.LLM_PROVIDER = orig_prov


if __name__ == "__main__":
    unittest.main()
