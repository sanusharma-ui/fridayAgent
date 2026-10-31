import unittest
from unittest.mock import Mock, patch

import numpy as np
import sounddevice as sd

from backend.services import speech_recognition as speech


class SpeechRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.device = type("AudioDefaults", (), {"device": (1, 4)})()
        self.audio = np.full(6 * 44100, 4096, dtype=np.int16)
        self.record_patch = patch.object(sd, "rec", return_value=self.audio)
        self.patches = [
            patch.object(sd, "default", self.device),
            patch.object(sd, "query_devices", return_value={"default_samplerate": 44100, "max_input_channels": 2}),
            self.record_patch,
            patch.object(sd, "wait"),
        ]
        for item in self.patches:
            started = item.start()
            if item is self.record_patch:
                self.record = started

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def test_records_native_rate_and_passes_resampled_english_audio(self):
        transcribe = Mock(return_value="open calculator")
        with patch.object(speech, "_transcribe_audio", transcribe):
            self.assertEqual(speech.listen_command(), "open calculator")
        self.record.assert_called_once_with(6 * 44100, samplerate=44100, device=1,
                                            channels=1, dtype="int16")
        audio = transcribe.call_args.args[0]
        self.assertEqual(audio.shape, (6 * 16000,))
        self.assertAlmostEqual(float(audio.mean()), 0.125, places=3)

    def test_worker_failure_is_reported_without_affecting_backend_process(self):
        with patch.object(speech, "_record_audio", return_value=np.full(16000, 0.1, dtype=np.float32)):
            with patch.object(speech, "_transcribe_audio", side_effect=RuntimeError("worker crashed")):
                with self.assertRaisesRegex(RuntimeError, "worker crashed"):
                    speech.listen_command()

    def test_reports_windows_microphone_permission_guidance(self):
        with patch.object(sd, "rec", side_effect=RuntimeError("device busy")):
            with self.assertRaisesRegex(RuntimeError, "Privacy & security > Microphone"):
                speech.listen_command()

    def test_ignores_silence_without_loading_model(self):
        with patch.object(speech, "_record_audio", return_value=np.zeros(16000, dtype=np.float32)):
            with patch.object(speech, "_transcribe_audio") as transcribe:
                self.assertEqual(speech.listen_command(), "")
                transcribe.assert_not_called()

    def test_rejects_unbounded_recording_time(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 15"):
            speech.listen_command(100)


if __name__ == "__main__":
    unittest.main()
