"""Short, push-to-talk transcription with the bundled offline Vosk model."""

import json
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1] / "vosk-model-small-en-us-0.15" / "vosk-model-small-en-us-0.15"
_model = None


def listen_command(duration=6):
    global _model
    try:
        import sounddevice as sd
        from vosk import KaldiRecognizer, Model
    except ImportError as exc:
        raise RuntimeError("Voice input needs vosk and sounddevice. Install requirements.txt.") from exc

    if not MODEL_DIR.is_dir():
        raise RuntimeError(f"Vosk model is missing: {MODEL_DIR}")
    if _model is None:
        _model = Model(str(MODEL_DIR))

    sample_rate = 16000
    try:
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
                       channels=1, dtype="int16")
        sd.wait()
    except Exception as exc:
        raise RuntimeError(f"Microphone unavailable: {exc}") from exc

    recognizer = KaldiRecognizer(_model, sample_rate)
    segments = []
    raw = audio.tobytes()
    for offset in range(0, len(raw), 8000):
        if recognizer.AcceptWaveform(raw[offset:offset + 8000]):
            segments.append(json.loads(recognizer.Result()).get("text", ""))
    segments.append(json.loads(recognizer.FinalResult()).get("text", ""))
    return " ".join(segment for segment in segments if segment).strip()
