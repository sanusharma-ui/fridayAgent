"""Standalone Whisper process so CTranslate2 native threads cannot terminate the Qt host."""

import contextlib
import json
import os
import sys

import numpy as np


def transcribe(audio):
    from faster_whisper import WhisperModel

    model = WhisperModel(
        "Systran/faster-whisper-tiny.en",
        device="cpu",
        compute_type="int8",
        cpu_threads=max(1, min(os.cpu_count() or 1, 4)),
        num_workers=1,
    )
    with contextlib.redirect_stdout(sys.stderr):
        segments, _info = model.transcribe(
            audio,
            language="en",
            task="transcribe",
            beam_size=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
            initial_prompt="Open calculator, open YouTube, open Gmail, search Google, open Notepad.",
        )
        return " ".join(segment.text.strip() for segment in segments if segment.text.strip())


def main():
    try:
        raw_audio = sys.stdin.buffer.read()
        if len(raw_audio) % 4:
            raise ValueError("Invalid audio data received by Whisper worker.")
        transcript = transcribe(np.frombuffer(raw_audio, dtype="<f4"))
        result = {"text": transcript}
    except Exception as exc:
        result = {"error": f"Whisper could not transcribe this recording: {exc}"}
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
