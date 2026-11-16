"""Optional, isolated local speech recognition worker (no GTK imports).

Run as ``python -m littleshell.speech``. It serves a line protocol on stdin so
the app keeps ONE worker alive and the Whisper model warm between dictations:
send ``record`` to start capturing the microphone and ``stop`` to end it; the
worker transcribes and writes one JSON line — ``{"text": ...}`` or
``{"error": ...}`` — to stdout, then waits for the next ``record``. The model
is loaded once, on the first transcription, and reused, so only the first
dictation pays the load cost. Closing stdin exits the worker. With ``--file``
it transcribes one audio file and exits (used by tests and the CLI). A small
model is the default; override with ``--model`` or ``LISH_SPEECH_MODEL``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .env import SPEECH_MODEL, text

DEFAULT_MODEL = text(SPEECH_MODEL, "base")
SAMPLE_RATE = 16000


def transcribe(source, model_factory=None, model_name=DEFAULT_MODEL, cpu_threads=0):
    if model_factory is None:
        from faster_whisper import WhisperModel
        model_factory = WhisperModel
    # greedy decoding (beam_size=1) and every core: short dictation on a CPU
    # must feel instant, not take minutes.
    threads = cpu_threads or os.cpu_count() or 4
    model = model_factory(model_name, device="cpu", compute_type="int8", cpu_threads=threads)
    segments, _ = model.transcribe(source, beam_size=1, vad_filter=True,
                                   condition_on_previous_text=False, task="transcribe")
    return " ".join(segment.text.strip() for segment in segments if segment.text.strip())


def warm_factory():
    """A ``model_factory`` that builds the Whisper model once and reuses it."""
    cache: dict = {}

    def factory(name, **kwargs):
        if "model" not in cache:
            from faster_whisper import WhisperModel
            cache["model"] = WhisperModel(name, **kwargs)
        return cache["model"]

    return factory


def serve(model_name=DEFAULT_MODEL, stdin=None, stdout=None) -> int:
    """Read ``record``/``stop`` lines; keep the model warm across dictations."""
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        stdout.write(json.dumps({"error": "missing-deps"}) + "\n")
        stdout.flush()
        return 1
    factory = warm_factory()
    frames: list | None = None
    stream = None
    for line in stdin:
        command = line.strip()
        if command == "record":
            frames = []
            stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                    callback=lambda indata, *_: frames.append(indata.copy()))
            stream.start()
        elif command == "stop":
            if stream is not None:
                stream.stop()
                stream.close()
                stream = None
            try:
                audio = np.concatenate(frames).reshape(-1) if frames else np.zeros(0, dtype="float32")
                if audio.size and not np.isfinite(audio).all():
                    raise ValueError("O microfone retornou áudio inválido.")
                result = transcribe(audio, model_factory=factory, model_name=model_name)
                stdout.write(json.dumps({"text": result}, ensure_ascii=False) + "\n")
            except Exception as error:  # noqa: BLE001 - reported to the user as text
                stdout.write(json.dumps({"error": str(error)}) + "\n")
            stdout.flush()
            frames = None
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    if not args.file:
        return serve(args.model)
    try:
        result = transcribe(args.file, model_name=args.model)
        print(json.dumps({"text": result}, ensure_ascii=False))
        return 0
    except ImportError:
        print(json.dumps({"error": "missing-deps"}))
    except Exception as error:  # noqa: BLE001 - reported to the user as text
        print(json.dumps({"error": str(error)}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
