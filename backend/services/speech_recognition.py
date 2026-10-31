"""Short, push-to-talk transcription with the bundled offline Vosk model."""

import json
from pathlib import Path

import numpy as np


MODEL_DIR = Path(__file__).resolve().parents[2] / "vosk-model-small-en-us-0.15" / "vosk-model-small-en-us-0.15"
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
        device = sd.default.device[0]
        if device is None or device < 0:
            raise RuntimeError("Windows has no default microphone selected.")
        info = sd.query_devices(device, "input")
        native_rate = int(info["default_samplerate"])
        if info["max_input_channels"] < 1:
            raise RuntimeError("The selected default audio device has no microphone input.")
        audio = sd.rec(int(duration * native_rate), samplerate=native_rate,
                       device=device, channels=1, dtype="int16")
        sd.wait()
    except Exception as exc:
        raise RuntimeError(
            f"Microphone unavailable: {exc}. Check Windows Settings > Privacy & security > Microphone, "
            "allow desktop apps to access the microphone, and select a working input in Sound settings."
        ) from exc

    recognizer = KaldiRecognizer(_model, sample_rate)
    segments = []
    mono = np.asarray(audio).reshape(-1)
    if native_rate != sample_rate and mono.size:
        source_positions = np.arange(mono.size, dtype=np.float64) / native_rate
        output_count = int(round(mono.size * sample_rate / native_rate))
        output_positions = np.arange(output_count, dtype=np.float64) / sample_rate
        mono = np.interp(output_positions, source_positions, mono).astype(np.int16)
    raw = mono.astype(np.int16, copy=False).tobytes()
    for offset in range(0, len(raw), 8000):
        if recognizer.AcceptWaveform(raw[offset:offset + 8000]):
            segments.append(json.loads(recognizer.Result()).get("text", ""))
    segments.append(json.loads(recognizer.FinalResult()).get("text", ""))
    return " ".join(segment for segment in segments if segment).strip()
