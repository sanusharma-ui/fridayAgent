"""Local multilingual transcription for bounded Telegram voice recordings."""

import io


class VoiceTranscriber:
    def __init__(self, model="base", language=""):
        self.model_name = model or "base"
        self.language = language or None
        self._model = None

    def transcribe(self, path):
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
