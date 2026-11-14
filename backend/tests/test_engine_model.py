"""The real model behind the real child process, on the pinned FLEURS clips (plan 03-10).

TRANS-01 and TRANS-08 on real output: the German clip gives its expected word
with a media time inside the clip, the same clip at a chunk offset of 10 min
gives the same word 600 000 ms later, five seconds of silence give no word, and
the Turkish clip keeps no window (TRANS-03, the catch rule on real output).

Needs the pinned models (AVS_TEST_MODELS, the root ``procure --root`` filled)
and the clips of ci/media/fetch_speech.py (AVS_TEST_SPEECH, AVS_TEST_SPEECH_TR,
AVS_TEST_WORD). Without them every test skips with its reason; under CI=true it
fails instead, because CI fetches both through its cache and the coverage floor
counts on these tests. Serial by nature: one child, one model in memory.
"""

import asyncio
import ctypes
import os
import sys
import wave
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from audio_video_search_backend import memory_guard
from audio_video_search_backend.engine.catch import KEEP
from audio_video_search_backend.engine.child import OK, EngineWorker
from audio_video_search_backend.engine.constants import SAMPLE_RATE
from audio_video_search_backend.engine.parakeet import Window
from audio_video_search_backend.models import procure
from tests.media_fixtures import missing

pytestmark = pytest.mark.model

OFFSET_MS = 600_000
SILENCE_S = 5


def _available_bytes() -> int | None:
    """The memory guard on Linux; on a Windows laptop the free physical memory instead."""
    if sys.platform != "win32":
        return memory_guard.headroom_bytes()

    class _Status(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _Status()
    status.dwLength = ctypes.sizeof(_Status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullAvailPhys)


def _path(name: str) -> Path:
    value = os.environ.get(name, "")
    if not value:
        missing(f"{name} is not set")
    path = Path(value)
    if not path.exists():
        missing(f"{name} points at nothing")
    return path


def _pcm(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path)) as handle:
        assert handle.getframerate() == SAMPLE_RATE
        assert handle.getnchannels() == 1
        frames = handle.readframes(handle.getnframes())
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    return samples.astype("<f4").tobytes(), len(samples) * 1000 // SAMPLE_RATE


def _norm(text: str) -> str:
    return "".join(char for char in text.lower() if char.isalnum())


@pytest.fixture(scope="module")
def models_root() -> Path:
    root = _path("AVS_TEST_MODELS")
    for name in procure.MODEL_ORDER:
        outcome = asyncio.run(procure.procure(root, name, fetch=None))
        if outcome != procure.PRESENT:
            missing(f"model {name} under AVS_TEST_MODELS is {outcome}, not present")
    return root


@pytest.fixture(scope="module")
def worker(models_root: Path) -> Iterator[EngineWorker]:
    engine = EngineWorker(models_root, headroom=_available_bytes)
    if engine.start() != OK:
        missing("not enough free memory for the engine child")
    yield engine
    engine.stop()


@pytest.fixture(scope="module")
def word() -> str:
    value = os.environ.get("AVS_TEST_WORD", "")
    if not value:
        missing("AVS_TEST_WORD is not set")
    return _norm(value)


def _hits(windows: list[Window], word: str) -> list[int]:
    return [item.start_ms for window in windows for item in window.words if _norm(item.text) == word]


def test_the_german_clip_gives_the_expected_word_inside_the_clip(worker: EngineWorker, word: str) -> None:
    pcm, clip_ms = _pcm(_path("AVS_TEST_SPEECH"))

    code, windows = worker.ask(pcm, 0, False)

    assert code == OK
    assert any(window.verdict == KEEP for window in windows)
    hits = _hits(windows, word)
    assert hits, "expected word not recognised"
    assert all(0 <= at <= clip_ms for at in hits)
    for window in windows:
        assert 0 <= window.start_ms <= window.end_ms <= clip_ms
        for item in window.words:
            assert item.start_ms <= item.end_ms
            assert 0.0 < item.conf <= 1.0


def test_a_chunk_offset_moves_every_word_by_the_offset(worker: EngineWorker, word: str) -> None:
    pcm, _ = _pcm(_path("AVS_TEST_SPEECH"))

    _, at_zero = worker.ask(pcm, 0, False)
    code, shifted = worker.ask(pcm, OFFSET_MS, False)

    assert code == OK
    assert _hits(at_zero, word)
    assert _hits(shifted, word) == [at + OFFSET_MS for at in _hits(at_zero, word)]
    assert [(window.start_ms, window.end_ms) for window in shifted] == [
        (window.start_ms + OFFSET_MS, window.end_ms + OFFSET_MS) for window in at_zero
    ]


@pytest.mark.parametrize("second_pass", [False, True])
def test_five_seconds_of_silence_give_no_word(worker: EngineWorker, second_pass: bool) -> None:
    silence = np.zeros(SILENCE_S * SAMPLE_RATE, dtype="<f4").tobytes()

    code, windows = worker.ask(silence, 0, second_pass)

    assert code == OK
    assert sum(window.n_words for window in windows) == 0


def test_the_turkish_clip_keeps_no_window(worker: EngineWorker) -> None:
    pcm, _ = _pcm(_path("AVS_TEST_SPEECH_TR"))

    code, windows = worker.ask(pcm, 0, False)

    assert code == OK
    # Positive control: the VAD did hear speech, so the windows were judged rather than absent.
    # Measured on 14.11.2026: Parakeet gives no token at all on this clip (also with sherpa-onnx
    # alone on the whole clip), so its windows fall by confidence with zero words, not by language.
    assert windows
    assert sum(window.speech_ms for window in windows) > 0
    assert all(window.verdict != KEEP for window in windows)
    assert all(window.words == () for window in windows)
