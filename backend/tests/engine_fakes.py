"""Fake engines for the child process tests (plan 03-10); no model is needed.

The child imports these by the "module:function" path the worker is given, so
they live in an importable module of the test package. The first sample of the
PCM picks the behaviour: the tests drive hang, memory exhaustion and a crash
through it without a second channel into the child.
"""

import os
import sys
import time
from pathlib import Path

import numpy as np

from audio_video_search_backend.engine.catch import KEEP
from audio_video_search_backend.engine.parakeet import EngineWord, Window

NORMAL = 0.0
HANG = 1.0
EXHAUST = 2.0
CRASH = 3.0
REPORT = 4.0
RAISE = 5.0
HANG_SECONDS = 60.0
REPORTED_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "APP_SECRET", "HP_SHARED_KEY")


def _word(text: str, start_ms: int) -> EngineWord:
    return EngineWord(text=text, start_ms=start_ms, end_ms=start_ms + 80, conf=1.0)


class FakeEngine:
    """Answers like the engine, from the first sample of the PCM."""

    def __init__(self, models_root: Path) -> None:
        self.models_root = models_root

    def transcribe(self, pcm: np.ndarray, offset_ms: int, *, second_pass: bool) -> list[Window]:
        command = float(pcm[0]) if len(pcm) else NORMAL
        if command == HANG:
            time.sleep(HANG_SECONDS)
        elif command == EXHAUST:
            raise MemoryError
        elif command == CRASH:
            os._exit(3)
        elif command == RAISE:
            raise RuntimeError("engine failed")
        texts = ["second" if second_pass else "first", f"samples={len(pcm)}", f"root={self.models_root.name}"]
        if command == REPORT:
            texts += [f"{name}={os.environ.get(name, '<absent>')}" for name in REPORTED_VARIABLES]
            texts.append(f"sherpa={'sherpa_onnx' in sys.modules}")
            texts.append(f"nice={os.nice(0) if sys.platform != 'win32' else 'none'}")
        words = tuple(_word(text, offset_ms + 100 * index) for index, text in enumerate(texts))
        return [
            Window(
                start_ms=offset_ms,
                end_ms=offset_ms + 1000,
                speech_ms=800,
                n_words=len(words),
                verdict=KEEP,
                words=words,
            )
        ]


def fake_engine(models_root: Path) -> FakeEngine:
    return FakeEngine(models_root)


def exhausted_engine(models_root: Path) -> FakeEngine:
    raise MemoryError(str(models_root))


def broken_engine(models_root: Path) -> FakeEngine:
    raise FileNotFoundError(str(models_root))
