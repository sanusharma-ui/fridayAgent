import json
import sys
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np
import sounddevice as sd

from backend.services import speech_recognition as speech


class SpeechRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.recognizer = Mock()
        self.recognizer.AcceptWaveform.return_value = False
        self.recognizer.FinalResult.return_value = json.dumps({"text": "open calculator"})
        self.vosk = types.ModuleType("vosk")
        self.vosk.KaldiRecognizer = Mock(return_value=self.recognizer)
        self.vosk.Model = Mock()
        self.device = types.SimpleNamespace(device=(1, 4))
        self.audio = np.zeros(6 * 44100, dtype=np.int16)
        self.record = patch.object(sd, "rec", return_value=self.audio)
        self.patches = [
            patch.dict(sys.modules, {"vosk": self.vosk}),
            patch.object(speech, "_model", object()),
            patch.object(sd, "default", self.device),
            patch.object(sd, "query_devices", return_value={"default_samplerate": 44100, "max_input_channels": 2}),
            self.record,
            patch.object(sd, "wait"),
        ]
        for item in self.patches:
            started = item.start()
            if item is self.record:
                self.record = started

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def test_uses_supported_device_rate_and_resamples_for_vosk(self):
        self.assertEqual(speech.listen_command(), "open calculator")
        self.record.assert_called_once_with(6 * 44100, samplerate=44100, device=1,
                                            channels=1, dtype="int16")
        samples = b"".join(call.args[0] for call in self.recognizer.AcceptWaveform.call_args_list)
        self.assertEqual(len(samples), 6 * 16000 * 2)

    def test_reports_windows_microphone_permission_guidance(self):
        with patch.object(sd, "rec", side_effect=RuntimeError("device busy")):
            with self.assertRaisesRegex(RuntimeError, "Privacy & security > Microphone"):
                speech.listen_command()


if __name__ == "__main__":
    unittest.main()
