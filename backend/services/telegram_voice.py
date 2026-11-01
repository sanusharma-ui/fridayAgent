"""Local multilingual transcription for bounded Telegram voice recordings."""

import io
import json
import subprocess
import sys
from pathlib import Path


class VoiceTranscriber:
    def __init__(self, model="base", language=""):
        self.model_name = model or "base"
        self.language = language or None
        self._model = None

    def transcribe(self, path):
        """Keep native audio/Whisper failures outside the Qt application."""
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), str(Path(path).resolve()),
                 self.model_name, self.language or ""],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Voice transcription timed out. The first model download needs internet; try a shorter note or send text.") from None
        except OSError:
            raise RuntimeError("Could not start the Telegram speech worker. Check your Python installation.") from None
        if result.returncode:
            raise RuntimeError("Telegram speech worker stopped unexpectedly. The app is still running; try again or send text.")
        try:
            data = json.loads(result.stdout.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError()
            if isinstance(data.get("error"), str):
                raise RuntimeError(data["error"])
            if not isinstance(data.get("text"), str):
                raise ValueError()
            return data["text"]
        except (ValueError, UnicodeDecodeError):
            raise RuntimeError("Telegram speech worker returned an invalid response. Try again or send text.") from None

    def _transcribe_local(self, path):
        try:
            import av
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("Voice notes need the optional packages: python -m pip install -r requirements-telegram.txt") from None

        # Decode at most 65 seconds even if the message's metadata is misleading.
        # PyAV bundles FFmpeg: no external ffmpeg.exe or shell command is needed.
        import numpy as np
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        pcm = io.BytesIO()
        try:
            with av.open(str(path)) as container:
                for frame in container.decode(audio=0):
                    for converted in resampler.resample(frame):
                        pcm.write(converted.to_ndarray().tobytes())
                        if pcm.tell() > 65 * 16000 * 2:
                            raise ValueError("Voice notes must be 60 seconds or shorter.")
                for converted in resampler.resample(None):
                    pcm.write(converted.to_ndarray().tobytes())
        except ValueError:
            raise
        except Exception:
            raise RuntimeError("This voice recording could not be decoded. Please record a new voice note.") from None
        if not pcm.tell():
            return ""
        if pcm.tell() > 65 * 16000 * 2:
            raise ValueError("Voice notes must be 60 seconds or shorter.")
        try:
            if self._model is None:
                self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            audio = np.frombuffer(pcm.getvalue(), dtype=np.int16).astype(np.float32) / 32768.0
            segments, _ = self._model.transcribe(audio, language=self.language, beam_size=3, vad_filter=True)
            return " ".join(segment.text.strip() for segment in segments).strip()
        except Exception:
            raise RuntimeError("Voice transcription failed. Check the model/language setting and internet access for the first model download.") from None


if __name__ == "__main__":
    import contextlib
    try:
        with contextlib.redirect_stdout(sys.stderr):
            text = VoiceTranscriber(sys.argv[2], sys.argv[3])._transcribe_local(sys.argv[1])
        result = {"text": text}
    except (RuntimeError, ValueError) as exc:
        result = {"error": str(exc)}
    except Exception:
        result = {"error": "Voice transcription failed. Check your voice dependencies and try again."}
    print(json.dumps(result, ensure_ascii=True), flush=True)
