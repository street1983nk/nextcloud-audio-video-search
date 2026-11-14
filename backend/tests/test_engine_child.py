"""The engine runs in a child process per job block, and its window logic is pure (plan 03-10).

T-03-33: a hung engine is killed at its wall time and only the child goes; a
child that runs out of memory answers OUT_OF_MEMORY instead of taking the main
process along; the memory guard refuses a start without room (NO_ROOM, no child
at all); a child is replaced after MAX_CHUNKS_PER_CHILD jobs. T-03-34: the child
holds no app secret. After every test no child is left alive.

The window logic of the engine (merging the VAD segments, word times from the
tokens, the swallow guard, the catch rule per window) is tested on an Engine
whose recognizer, VAD and language identification are replaced; the real model
runs in tests/test_engine_model.py.
"""

import math
import multiprocessing
import os
import pickle
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from audio_video_search_backend.engine import child, parakeet
from audio_video_search_backend.engine.catch import DROP_CONFIDENCE, DROP_LANGUAGE, DROP_SCRIPT, KEEP
from audio_video_search_backend.engine.child import (
    CHUNK_WALL_SECONDS,
    CRASHED,
    ENGINE_NEED_BYTES,
    ENGINE_NICE,
    ENGINE_RESERVE_BYTES,
    MAX_CHUNKS_PER_CHILD,
    NO_ROOM,
    OK,
    OUT_OF_MEMORY,
    THREAD_ENV,
    TIMEOUT,
    EngineWorker,
)
from audio_video_search_backend.engine.constants import SAMPLE_RATE
from audio_video_search_backend.engine.parakeet import Engine, EngineWord, Window, merge_segments, words_from_tokens
from tests import engine_fakes
from tests.conftest import BACKEND_ROOT

FAKE = "tests.engine_fakes:fake_engine"
ROOM = ENGINE_NEED_BYTES + ENGINE_RESERVE_BYTES
SR = SAMPLE_RATE


@pytest.fixture(autouse=True)
def no_child_survives() -> Iterator[None]:
    yield
    deadline = time.monotonic() + 10
    while multiprocessing.active_children() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert multiprocessing.active_children() == []


def _pcm(command: float = engine_fakes.NORMAL, samples: int = 16) -> bytes:
    pcm = np.zeros(samples, dtype="<f4")
    pcm[0] = command
    return pcm.tobytes()


def _worker(tmp_path: Path, *, factory: str = FAKE, room: int | None = ROOM) -> EngineWorker:
    return EngineWorker(tmp_path / "models", factory=factory, headroom=lambda: room)


def _alive(pid: int) -> bool:
    return any(process.pid == pid for process in multiprocessing.active_children())


# The child process.


def test_a_job_comes_back_with_windows_at_its_offset(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    try:
        assert worker.start() == OK
        code, windows = worker.ask(_pcm(samples=32), 600_000, False)
        second_code, second = worker.ask(_pcm(), 0, True)
    finally:
        worker.stop()

    assert code == OK
    assert [word.text for word in windows[0].words] == ["first", "samples=32", "root=models"]
    assert windows[0].start_ms == 600_000
    assert windows[0].words[0].start_ms == 600_000
    assert second_code == OK
    assert second[0].words[0].text == "second"


def test_ask_starts_a_child_when_none_runs(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    try:
        assert worker.pid is None
        code, _ = worker.ask(_pcm(), 0, False)
        assert code == OK
        assert worker.pid is not None
    finally:
        worker.stop()


def test_a_child_over_its_deadline_is_killed_and_the_next_job_gets_a_new_one(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    try:
        assert worker.start() == OK
        first_pid = worker.pid
        assert first_pid is not None
        started = time.monotonic()
        code, windows = worker.ask(_pcm(engine_fakes.HANG), 0, False, deadline=1.0)
        waited = time.monotonic() - started

        assert (code, windows) == (TIMEOUT, [])
        assert waited < engine_fakes.HANG_SECONDS / 2
        assert worker.pid is None
        assert not _alive(first_pid)

        code, windows = worker.ask(_pcm(), 0, False)
        assert code == OK
        assert worker.pid not in {None, first_pid}
    finally:
        worker.stop()


def test_a_memory_error_in_the_child_is_out_of_memory_and_replaces_the_child(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    try:
        worker.start()
        first_pid = worker.pid
        assert worker.ask(_pcm(engine_fakes.EXHAUST), 0, False) == (OUT_OF_MEMORY, [])
        assert worker.pid is None

        code, _ = worker.ask(_pcm(), 0, False)
        assert code == OK
        assert worker.pid != first_pid
    finally:
        worker.stop()


def test_a_dying_child_is_crashed_not_a_crash_of_the_caller(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    try:
        worker.start()
        assert worker.ask(_pcm(engine_fakes.CRASH), 0, False) == (CRASHED, [])
        assert worker.pid is None
        assert worker.ask(_pcm(), 0, False)[0] == OK
    finally:
        worker.stop()


def test_an_engine_exception_is_crashed_and_the_child_is_replaced(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    try:
        worker.start()
        assert worker.ask(_pcm(engine_fakes.RAISE), 0, False) == (CRASHED, [])
        assert worker.pid is None
    finally:
        worker.stop()


@pytest.mark.parametrize(
    ("factory", "code"),
    [("tests.engine_fakes:exhausted_engine", OUT_OF_MEMORY), ("tests.engine_fakes:broken_engine", CRASHED)],
)
def test_an_engine_that_cannot_be_built_answers_with_a_code(tmp_path: Path, factory: str, code: str) -> None:
    worker = _worker(tmp_path, factory=factory)
    try:
        assert worker.start() == OK
        assert worker.ask(_pcm(), 0, False) == (code, [])
        assert worker.pid is None
    finally:
        worker.stop()


@pytest.mark.parametrize("room", [None, 0, ENGINE_NEED_BYTES, ROOM - 1])
def test_without_room_no_child_is_started(tmp_path: Path, room: int | None) -> None:
    worker = _worker(tmp_path, room=room)
    try:
        assert worker.start() == NO_ROOM
        assert worker.pid is None
        assert multiprocessing.active_children() == []
        assert worker.ask(_pcm(), 0, False) == (NO_ROOM, [])
        assert multiprocessing.active_children() == []
    finally:
        worker.stop()


def test_room_of_exactly_need_plus_reserve_is_admitted(tmp_path: Path) -> None:
    worker = _worker(tmp_path, room=ROOM)
    try:
        assert worker.start() == OK
        assert worker.pid is not None
    finally:
        worker.stop()


def test_the_real_guard_is_the_default_reader(tmp_path: Path) -> None:
    worker = EngineWorker(tmp_path / "models", factory=FAKE)
    expected = OK if child.memory_guard.admits(child.memory_guard.headroom_bytes(), need=ROOM) else NO_ROOM
    try:
        assert worker.start() == expected
    finally:
        worker.stop()


def test_the_child_is_replaced_after_max_chunks(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    try:
        worker.start()
        first_pid = worker.pid
        for _ in range(MAX_CHUNKS_PER_CHILD):
            assert worker.pid in {None, first_pid}
            assert worker.ask(_pcm(), 0, False)[0] == OK
        assert worker.pid is None
        assert first_pid is not None
        assert not _alive(first_pid)

        assert worker.ask(_pcm(), 0, False)[0] == OK
        assert worker.pid not in {None, first_pid}
    finally:
        worker.stop()


def test_stop_leaves_no_process_and_is_repeatable(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    worker.start()
    pid = worker.pid
    assert pid is not None
    worker.stop()
    worker.stop()

    assert worker.pid is None
    assert not _alive(pid)


def test_the_child_pins_its_threads_and_holds_no_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HP_SHARED_KEY", "harp-key-not-real")
    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    worker = _worker(tmp_path)
    try:
        code, windows = worker.ask(_pcm(engine_fakes.REPORT), 0, False)
    finally:
        worker.stop()

    assert code == OK
    seen = dict(word.text.split("=", 1) for word in windows[0].words[1:])
    for name, value in THREAD_ENV.items():
        assert seen[name] == value
    assert seen["APP_SECRET"] == ""
    assert seen["HP_SHARED_KEY"] == ""
    # The engine module was imported, sherpa_onnx was not: it loads only when an Engine is built.
    assert seen["sherpa"] == "False"
    if sys.platform.startswith("linux"):
        assert seen["nice"] == str(ENGINE_NICE)
    # The parent keeps its own environment.
    assert os.environ["HP_SHARED_KEY"] == "harp-key-not-real"
    assert "OMP_NUM_THREADS" not in os.environ


def test_a_factory_must_name_module_and_function(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="module:function"):
        EngineWorker(tmp_path, factory="tests.engine_fakes.fake_engine")


def test_the_constants_are_the_planned_ones() -> None:
    assert ENGINE_NEED_BYTES == 1_700 * 1024**2
    assert ENGINE_RESERVE_BYTES == 512 * 1024**2
    assert CHUNK_WALL_SECONDS == 900
    assert MAX_CHUNKS_PER_CHILD == 12
    assert ENGINE_NICE == 10
    assert THREAD_ENV == {"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    assert child.SPAWN_CONTEXT.get_start_method() == "spawn"


def test_the_child_source_logs_no_text_and_limits_no_address_space() -> None:
    source = (BACKEND_ROOT / "src/audio_video_search_backend/engine/child.py").read_text(encoding="utf-8")
    assert "setrlimit" not in source
    assert "RLIMIT_AS" not in source
    for line in source.splitlines():
        if "LOGGER." in line:
            assert "text" not in line
            assert "words" not in line


def _fresh_python(code: str) -> str:
    completed = subprocess.run(  # noqa: S603 - the interpreter of this test run with a fixed program
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=BACKEND_ROOT
    )
    return completed.stdout.strip()


def test_the_parent_never_loads_sherpa_onnx() -> None:
    out = _fresh_python(
        "import sys\n"
        "import audio_video_search_backend.engine.child\n"
        "import audio_video_search_backend.engine.parakeet\n"
        "print(sorted(m for m in sys.modules if m.split('.')[0] in {'sherpa_onnx', 'py3langid', 'onnxruntime'}))"
    )
    assert out == "[]"


def test_py3langid_server_is_never_imported() -> None:
    out = _fresh_python(
        "import sys\n"
        "from audio_video_search_backend.engine import parakeet\n"
        "identifier = parakeet.language_identifier()\n"
        "print(identifier.classify('Das ist ein ganz normaler deutscher Satz')[0])\n"
        "print(sorted(m for m in sys.modules if m.startswith('py3langid')))"
    )
    language, modules = out.splitlines()
    assert language == "de"
    assert "py3langid.langid" in modules
    assert "py3langid.server" not in modules
    # Positive control: the same check sees the module once it is imported.
    control = _fresh_python("import sys, py3langid.server\nprint('py3langid.server' in sys.modules)")
    assert control == "True"
    package = BACKEND_ROOT / "src/audio_video_search_backend"
    for path in package.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "py3langid.server" not in text
        assert "import server" not in text


# The window logic.


def test_segments_merge_while_the_gap_is_at_most_2_s_and_the_window_at_most_25_s() -> None:
    assert merge_segments([]) == []
    assert merge_segments([(0, SR), (3 * SR, SR)]) == [(0, 4 * SR, [(0, SR), (3 * SR, SR)])]
    # A gap of 2 s plus one sample splits.
    assert merge_segments([(0, SR), (3 * SR + 1, SR)]) == [
        (0, SR, [(0, SR)]),
        (3 * SR + 1, 4 * SR + 1, [(3 * SR + 1, SR)]),
    ]
    # 25 s exactly still merges, one sample more splits.
    assert merge_segments([(0, 10 * SR), (11 * SR, 14 * SR)]) == [(0, 25 * SR, [(0, 10 * SR), (11 * SR, 14 * SR)])]
    assert len(merge_segments([(0, 10 * SR), (11 * SR, 14 * SR + 1)])) == 2
    # A merged window is measured from its first start.
    three = merge_segments([(0, SR), (2 * SR, SR), (4 * SR, SR)])
    assert three == [(0, 5 * SR, [(0, SR), (2 * SR, SR), (4 * SR, SR)])]


def test_words_take_media_time_from_offset_token_time_and_padding() -> None:
    words = words_from_tokens(
        [" Hal", "lo", " Welt", " "],
        [0.5, 0.58, 0.9, 1.2],
        [-0.1, -0.5, -0.2, -0.3],
        span_offset_s=1.6,
        offset_ms=600_000,
    )

    assert [word.text for word in words] == ["Hallo", "Welt"]
    assert words[0].start_ms == 600_000 + 2100
    assert words[0].end_ms == 600_000 + round((0.58 + 1.6 + 0.08) * 1000)
    assert words[0].conf == round(math.exp(-0.5), 4)
    assert words[1].start_ms == 600_000 + 2500
    assert words[1].conf == round(math.exp(-0.2), 4)


def test_without_matching_log_probs_the_confidence_is_one() -> None:
    words = words_from_tokens([" ja"], [0.0], [], span_offset_s=-0.5, offset_ms=0)
    assert words == [EngineWord(text="ja", start_ms=-500, end_ms=-420, conf=1.0)]


def test_the_vad_values_of_the_second_pass() -> None:
    assert parakeet.vad_values(second_pass=False) == (0.5, 0.25)
    assert parakeet.vad_values(second_pass=True) == (0.3, 0.1)


class ScriptedEngine(Engine):
    """The pipeline of Engine with a scripted VAD, recognizer and language identification."""

    def __init__(self, segments: list[tuple[int, int]], decodes: dict[int, list[tuple[str, float]]]) -> None:
        self.segments = segments
        self.decodes = decodes
        self.calls: list[int] = []
        self.vad_calls: list[bool] = []

    def _segments(self, pcm: np.ndarray, *, second_pass: bool) -> list[tuple[int, int]]:
        self.vad_calls.append(second_pass)
        return self.segments

    def _decode(self, samples: np.ndarray) -> tuple[list[str], list[float], list[float]]:
        self.calls.append(len(samples))
        script = self.decodes.get(len(samples), [])
        return [token for token, _ in script], [time for _, time in script], [-0.05] * len(script)

    def _language(self, text: str) -> tuple[str, float]:
        if text.startswith("Bu"):
            return "tr", 0.99
        return ("de", 0.95) if text else ("", 0.0)


def _span_len(start: int, end: int) -> int:
    """The length of a decoded span: context, at least half a second, padding on both sides."""
    s0 = max(0, start - int(0.4 * SR))
    body = min(end + int(0.4 * SR), 60 * SR) - s0
    return max(body, SR // 2) + SR


def test_a_kept_window_carries_words_at_media_time() -> None:
    span = _span_len(SR, 2 * SR)
    engine = ScriptedEngine([(SR, SR)], {span: [(" Hallo", 0.9), (" Welt", 1.2)]})

    windows = engine.transcribe(np.zeros(60 * SR, dtype=np.float32), 1_000, second_pass=False)

    assert len(windows) == 1
    window = windows[0]
    assert (window.start_ms, window.end_ms, window.speech_ms) == (2_000, 3_000, 1_000)
    assert window.verdict == KEEP
    assert window.n_words == 2
    # span offset: (1.0 s - 0.4 s context) - 0.5 s padding = 0.1 s
    assert [(word.text, word.start_ms) for word in window.words] == [("Hallo", 1_000 + 1_000), ("Welt", 1_000 + 1_300)]
    assert (window.lid, window.lid_p) == ("de", 0.95)
    assert engine.vad_calls == [False]


def test_a_dropped_window_carries_no_words_but_its_counts() -> None:
    span = _span_len(SR, 2 * SR)
    engine = ScriptedEngine([(SR, SR)], {span: [(" Bu", 0.9), (" bir", 1.0), (" test", 1.1)]})

    windows = engine.transcribe(np.zeros(60 * SR, dtype=np.float32), 0, second_pass=True)

    assert windows[0].verdict == DROP_LANGUAGE
    assert windows[0].words == ()
    assert windows[0].n_words == 3
    assert windows[0].speech_ms == 1_000
    assert engine.vad_calls == [True]


def test_a_window_in_another_script_is_dropped() -> None:
    span = _span_len(SR, 2 * SR)
    engine = ScriptedEngine([(SR, SR)], {span: [(" Привет", 0.9)]})

    windows = engine.transcribe(np.zeros(60 * SR, dtype=np.float32), 0, second_pass=False)

    assert windows[0].verdict == DROP_SCRIPT
    assert windows[0].words == ()


def test_a_window_without_words_counts_nothing() -> None:
    engine = ScriptedEngine([(SR, SR)], {})

    windows = engine.transcribe(np.zeros(60 * SR, dtype=np.float32), 0, second_pass=False)

    assert windows[0].n_words == 0
    assert windows[0].verdict == DROP_CONFIDENCE
    assert windows[0].words == ()


def test_the_swallow_guard_decodes_a_quiet_part_again_and_keeps_the_richer_result() -> None:
    # Two segments of 2 s, merged into one window; the window decode puts three
    # words into the first segment and none into the second, so the second (2 s,
    # below 1 word per second) is decoded again on its own and gives two words.
    segments = [(0, 2 * SR), (3 * SR, 2 * SR)]
    window_span = _span_len(0, 5 * SR)
    second_span = _span_len(3 * SR, 5 * SR)
    engine = ScriptedEngine(
        segments,
        {
            window_span: [(" eins", 0.6), (" zwei", 0.9), (" drei", 1.2)],
            # The first part alone (2 s, 3 words) is never decoded again.
            second_span: [(" vier", 0.5), (" fünf", 1.0)],
        },
    )

    windows = engine.transcribe(np.zeros(60 * SR, dtype=np.float32), 0, second_pass=False)

    assert [word.text for word in windows[0].words] == ["eins", "zwei", "drei", "vier", "fünf"]
    assert [word.start_ms for word in windows[0].words] == sorted(word.start_ms for word in windows[0].words)
    assert len(engine.calls) == 2
    assert windows[0].n_words == 5


def test_the_guard_keeps_the_window_result_when_the_part_gives_no_more() -> None:
    segments = [(0, 2 * SR), (3 * SR, 2 * SR)]
    window_span = _span_len(0, 5 * SR)
    engine = ScriptedEngine(segments, {window_span: [(" eins", 0.6), (" zwei", 0.9), (" drei", 1.2)]})

    windows = engine.transcribe(np.zeros(60 * SR, dtype=np.float32), 0, second_pass=False)

    assert [word.text for word in windows[0].words] == ["eins", "zwei", "drei"]
    assert len(engine.calls) == 2


def test_windows_and_words_cross_the_pipe() -> None:
    window = Window(start_ms=1, end_ms=2, speech_ms=1, n_words=1, verdict=KEEP, words=(EngineWord("a", 1, 2, 0.5),))
    assert pickle.loads(pickle.dumps(window)) == window  # noqa: S301 - our own bytes, just written


def test_a_child_that_dies_while_it_builds_the_engine_is_crashed_at_once(tmp_path: Path) -> None:
    worker = _worker(tmp_path, factory="tests.engine_fakes:dying_engine")
    try:
        started = time.monotonic()
        assert worker.ask(_pcm(), 0, False, deadline=30.0) == (CRASHED, [])
        assert time.monotonic() - started < 15.0
        assert worker.pid is None
    finally:
        worker.stop()


class _Pipe:
    def __init__(self, ready_after: int | None) -> None:
        self.ready_after = ready_after
        self.polls: list[float] = []

    def poll(self, timeout: float) -> bool:
        self.polls.append(timeout)
        return self.ready_after is not None and len(self.polls) > self.ready_after


class _Process:
    def __init__(self, alive: bool) -> None:
        self.alive = alive

    def is_alive(self) -> bool:
        return self.alive


def test_waiting_stops_early_when_the_child_is_gone() -> None:
    """A child that died before it held its pipe end does not wake the poll on Windows (measured)."""
    pipe = _Pipe(ready_after=None)
    started = time.monotonic()

    assert child._answered(_Process(alive=False), pipe, 30.0) is False  # type: ignore[arg-type]

    assert time.monotonic() - started < 5.0
    assert pipe.polls[-1] == 0


def test_waiting_returns_the_answer_and_honours_the_deadline() -> None:
    assert child._answered(_Process(alive=True), _Pipe(ready_after=2), 30.0) is True  # type: ignore[arg-type]
    slow = _Pipe(ready_after=None)
    started = time.monotonic()
    assert child._answered(_Process(alive=True), slow, 0.3) is False  # type: ignore[arg-type]
    assert time.monotonic() - started < 2.0
    assert all(timeout <= child._POLL_SLICE_SECONDS for timeout in slow.polls)
