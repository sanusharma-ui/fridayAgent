import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.services.telegram_voice import VoiceTranscriber


class TelegramVoiceTests(unittest.TestCase):
    @patch("backend.services.telegram_voice.subprocess.run")
    def test_worker_receives_model_language_and_absolute_path(self, run):
        run.return_value = Mock(returncode=0, stdout=json.dumps({"text": "open youtube"}).encode())
        self.assertEqual(VoiceTranscriber("base", "hi").transcribe("voice.ogg"), "open youtube")
        args = run.call_args.args[0]
        self.assertEqual(args[-2:], ["base", "hi"])
        self.assertTrue(Path(args[-3]).is_absolute())
        self.assertEqual(run.call_args.kwargs["timeout"], 300)

    @patch("backend.services.telegram_voice.subprocess.run")
    def test_native_crash_is_reported_without_exposing_stderr(self, run):
        run.return_value = Mock(returncode=-1, stdout=b"", stderr=b"private crash details")
        with self.assertRaisesRegex(RuntimeError, "app is still running"):
            VoiceTranscriber().transcribe("voice.ogg")

    @patch("backend.services.telegram_voice.subprocess.run")
    def test_timeout_and_launch_failure(self, run):
        for error, message in [(subprocess.TimeoutExpired("worker", 300), "timed out"),
                               (OSError("failed"), "Could not start")]:
            run.side_effect = error
            with self.assertRaisesRegex(RuntimeError, message):
                VoiceTranscriber().transcribe("voice.ogg")

    @patch("backend.services.telegram_voice.subprocess.run")
    def test_bad_worker_responses_and_dependency_error(self, run):
        for output in (b"not json", b"[]", b'{"text": 42}', b"\xff"):
            run.return_value = Mock(returncode=0, stdout=output)
            with self.assertRaisesRegex(RuntimeError, "invalid response"):
                VoiceTranscriber().transcribe("voice.ogg")
        run.return_value = Mock(returncode=0, stdout=b'{"error": "Install voice dependencies"}')
        with self.assertRaisesRegex(RuntimeError, "Install voice dependencies"):
            VoiceTranscriber().transcribe("voice.ogg")


if __name__ == "__main__":
    unittest.main()
