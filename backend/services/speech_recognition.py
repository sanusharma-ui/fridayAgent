"""Local English speech-to-text using the compact Whisper tiny.en checkpoint."""

import json
from pathlib import Path
import re
import subprocess
import sys
import threading

import numpy as np


_WORKER = Path(__file__).with_name("whisper_worker.py")
WAKE_WORD = "hey sunday"
WAKE_CHECK_DURATION = 2


def wake_word_matches(text):
    """Return whether a transcript contains the configured wake phrase."""
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return WAKE_WORD in normalized


def wake_word_loop(stop_event, paused_event, on_wake, on_error):
    """Continuously transcribe short microphone windows until stopped."""
    while not stop_event.is_set():
        if paused_event.wait(0.1):
            continue
        try:
            transcript = listen_command(WAKE_CHECK_DURATION)
        except RuntimeError as exc:
            on_error(str(exc))
            stop_event.wait(5)
            continue
        if wake_word_matches(transcript):
            paused_event.set()
            on_wake(transcript)


def _transcribe_audio(audio):
    """Run CTranslate2 outside the Qt process; its native thread pool can abort under Qt."""
    root = _WORKER.parents[2]
    try:
        result = subprocess.run(
            [sys.executable, str(_WORKER)],
            input=np.asarray(audio, dtype="<f4").tobytes(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=root,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Whisper took too long to transcribe this recording. Please try again.") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the isolated Whisper worker: {exc}") from exc

    try:
        response = json.loads(result.stdout.decode("utf-8").strip().splitlines()[-1])
    except (UnicodeDecodeError, json.JSONDecodeError, IndexError) as exc:
        detail = result.stderr.decode("utf-8", errors="replace")[-1200:].strip()
        raise RuntimeError(
            "Whisper worker stopped unexpectedly"
            + (f" (exit {result.returncode})" if result.returncode else "")
            + (f": {detail}" if detail else ".")
        ) from exc
    if result.returncode or "error" in response:
        raise RuntimeError(response.get("error") or "Whisper worker exited unexpectedly.")
    return response.get("text", "")


def _record_audio(duration):
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("Voice input needs sounddevice. Run: python -m pip install -r requirements.txt") from exc

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

    mono = np.asarray(audio).reshape(-1)
    if native_rate != 16000 and mono.size:
        source_positions = np.arange(mono.size, dtype=np.float64) / native_rate
        output_count = int(round(mono.size * 16000 / native_rate))
        output_positions = np.arange(output_count, dtype=np.float64) / 16000
        mono = np.interp(output_positions, source_positions, mono).astype(np.float32)
    else:
        mono = mono.astype(np.float32)
    mono /= 32768.0
    return mono


def listen_command(duration=6):
    """Record one short utterance and transcribe it locally in English."""
    if not 0 < duration <= 15:
        raise ValueError("Voice recording duration must be between 0 and 15 seconds.")

    audio = _record_audio(duration)
    if not audio.size or float(np.max(np.abs(audio))) < 0.003:
        return ""

    return _transcribe_audio(audio)
