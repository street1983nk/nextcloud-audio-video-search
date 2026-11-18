"""The real model behind the real child process, on the pinned FLEURS clips (plan 03-10).

TRANS-01 and TRANS-08 on real output: the German clip gives its expected word
with a media time inside the clip, the same clip at a chunk offset of 10 min
gives the same word 600 000 ms later, five seconds of silence give no word, and
the Turkish clip keeps no window (TRANS-03, the catch rule on real output).
D-03-22: the file verdict, counted the way the preview worker counts (worker/preview.take,
the second pass for files up to 60 s), is "transcript" for the German clip and
"unsupported_language" for the Spanish clip (Parakeet transcribes it, the text
language drops it) and for the Turkish clip (Parakeet gives almost no word).
Plan 05-07: the real child runs with the standard thread count and reports a
memory peak of the size the measurement of plan 05-01 found (Linux).

Needs the pinned models (AVS_TEST_MODELS, the root ``procure --root`` filled)
and the clips of ci/media/fetch_speech.py (AVS_TEST_SPEECH, AVS_TEST_SPEECH_TR,
AVS_TEST_SPEECH_ES, AVS_TEST_WORD; the S7 clips of plan 04-14 lie next to
AVS_TEST_SPEECH). Without them every test skips with its reason; under CI=true it
fails instead, because CI fetches both through its cache and the coverage floor
counts on these tests. Serial by nature: one child, one model in memory.
"""

import asyncio
import ctypes
import importlib.util
import os
import sys
import wave
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest

from audio_video_search_backend import hardware, measured, memory_guard
from audio_video_search_backend.engine.catch import (
    DROP_LANGUAGE,
    KEEP,
    TRANSCRIPT,
    UNSUPPORTED_LANGUAGE,
    file_verdict,
    needs_second_pass,
)
from audio_video_search_backend.engine.child import OK, EngineWorker
from audio_video_search_backend.engine.constants import SAMPLE_RATE
from audio_video_search_backend.engine.parakeet import Window
from audio_video_search_backend.models import procure
from audio_video_search_backend.worker.preview import take
from tests.conftest import REPO_ROOT
from tests.media_fixtures import missing

pytestmark = pytest.mark.model

FETCH_SPEECH = REPO_ROOT / "ci" / "media" / "fetch_speech.py"
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


def test_the_real_child_runs_with_the_standard_threads_and_reports_its_peak(worker: EngineWorker) -> None:
    pcm, _ = _pcm(_path("AVS_TEST_SPEECH"))

    assert worker.start() == OK
    assert worker.threads == hardware.default_threads(hardware.usable_cpus())
    code, _ = worker.ask(pcm, 0, False)

    assert code == OK
    peak = worker.last_peak_bytes
    if sys.platform.startswith("linux"):
        # The model alone is 0.67 GB; a short clip stays below the peak of a 10 min chunk
        # with room to spare. A wrong unit of ru_maxrss is off by a factor of 1024.
        assert peak is not None
        assert 300 * 1024**2 < peak < 2 * max(measured.PARAKEET_PEAK_BYTES.values())
    else:
        assert peak is None


def _file_verdict(worker: EngineWorker, pcm: bytes, clip_ms: int) -> str:
    """The verdict of the clip as one file, counted like worker/preview.py."""
    code, first = worker.ask(pcm, 0, False)
    assert code == OK
    counters = take(first, 0, None).counters
    kept, script, language, conf = counters.kept_words, counters.drop_script, counters.drop_language, counters.drop_conf
    if needs_second_pass(kept, clip_ms, False):
        code, second = worker.ask(pcm, 0, True)
        assert code == OK
        again = take(second, 0, None, count_speech=False).counters
        kept += again.kept_words
        script += again.drop_script
        language += again.drop_language
        conf += again.drop_conf
    return file_verdict(kept, script, language, conf, counters.speech_ms, clip_ms)


def test_the_german_clip_is_a_transcript(worker: EngineWorker) -> None:
    pcm, clip_ms = _pcm(_path("AVS_TEST_SPEECH"))

    assert _file_verdict(worker, pcm, clip_ms) == TRANSCRIPT


def test_the_spanish_clip_is_transcribed_and_dropped_by_its_text_language(worker: EngineWorker) -> None:
    pcm, clip_ms = _pcm(_path("AVS_TEST_SPEECH_ES"))

    code, windows = worker.ask(pcm, 0, False)

    assert code == OK
    # Parakeet knows Spanish: the windows carry words, and the catch rule drops them by language.
    assert sum(window.n_words for window in windows) >= 10
    assert all(window.verdict == DROP_LANGUAGE for window in windows if window.n_words)
    assert all(window.lid == "es" for window in windows if window.n_words)
    assert _file_verdict(worker, pcm, clip_ms) == UNSUPPORTED_LANGUAGE


def test_the_turkish_clip_is_unsupported_language(worker: EngineWorker) -> None:
    """D-03-22: much speech by the VAD, no or almost no word from Parakeet."""
    pcm, clip_ms = _pcm(_path("AVS_TEST_SPEECH_TR"))

    assert _file_verdict(worker, pcm, clip_ms) == UNSUPPORTED_LANGUAGE


def _fetch_speech() -> ModuleType:
    """ci/media/fetch_speech.py as a module, without bytecode next to it."""
    spec = importlib.util.spec_from_file_location("fetch_speech_for_model_tests", FETCH_SPEECH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        # dataclasses looks the module up in sys.modules while the class is built
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
        sys.modules.pop(spec.name, None)
    return module


S7_CLIPS = _fetch_speech().S7_CLIPS


def _s7_clip_path(name: str) -> Path:
    """The S7 clip lies next to AVS_TEST_SPEECH: python.yml fetches every clip of CLIPS into one folder."""
    path = _path("AVS_TEST_SPEECH").parent / name
    if not path.exists():
        missing(f"{name} is not next to AVS_TEST_SPEECH")
    return path


@pytest.mark.parametrize("clip", S7_CLIPS, ids=[clip.name for clip in S7_CLIPS])
def test_the_s7_clips_give_the_measured_target_forms(worker: EngineWorker, clip: Any) -> None:
    """Plan 04-14: the E2E search spec counts on these forms, so they must come out of Parakeet as measured.

    Tokens of the kept windows are compared folded, so punctuation and case do
    not matter; the full text is not compared.
    """
    pcm, _ = _pcm(_s7_clip_path(clip.name))

    code, windows = worker.ask(pcm, 0, False)

    assert code == OK
    tokens = {_norm(item.text) for window in windows if window.verdict == KEEP for item in window.words}
    targets = clip.s7
    wanted = list(dict.fromkeys([clip.expected_word, targets.number_word, targets.compound]))
    if targets.plural:
        wanted.append(targets.plural)
    absent = [form for form in wanted if _norm(form) not in tokens]
    assert not absent, f"{clip.name}: measured target forms missing from the transcript: {absent}"
