"""The engine in its own child process, one per job block (plan 03-10, plan 05-07).

Built after Findling 1.6.4 ``findling/extract/sandbox.py`` (SPAWN_CONTEXT, the
nice level, the group kill, the child loop with its pipe, the ask with a
deadline). Why a child at all: the model memory of ONNX Runtime goes back to
the system only with the process, and a crash or a hang of native code must
never take the main process along (T-03-33).

- Before every start the memory guard reads the headroom; below the need of
  the model that is to run plus a reserve no child is started and the answer
  is NO_ROOM (phase 5, RES-02).
- The child makes itself a session leader, writes the highest OOM score
  adjustment for itself and runs at nice 10 (Linux), all before anything else:
  when memory runs out the kernel takes this child first, not the main
  process and, without a memory limit on the container, not Nextcloud or the
  database either (phase 5, RES-03, T-05-14). Raising the score needs no
  privilege. Then it takes the app secrets out of its environment (Findling
  ``_shed_secrets``, T-03-34) and pins the thread pools before sherpa_onnx is
  imported; it builds the engine once.
- One thread count N for the child, its environment and the library (phase 5,
  RES-05, T-05-16): the worker reads N once per child, the child sets
  OMP_NUM_THREADS=N and hands N to the factory, which gives it to the
  recognizer. OMP_THREAD_LIMIT is never set and is taken out of an inherited
  environment: a limit below what the library plans hung arm64 (PII 02-16,
  18 November 2026). A changed N reaches the next child, never a running one.
- A job is (pcm, offset_ms, second_pass) over the pipe; the answer is a code,
  the windows and the memory peak of the child in bytes (ru_maxrss, Linux
  only). Over the wall time the whole child is killed (TIMEOUT); a
  MemoryError is OUT_OF_MEMORY, any other failure CRASHED; after both the
  child is replaced, and after MAX_CHUNKS_PER_CHILD jobs as well.
- A child that dies is OUT_OF_MEMORY when the oom_kill counter of
  memory.events rose between the sending of the job and the death, or when
  it was ended by a SIGKILL the worker did not send; otherwise CRASHED
  (T-05-15). The main process lives on either way.
- No address space limit: ONNX Runtime reserves far more virtual memory than
  it uses (STACK.md "What NOT to Use").
- Logs carry the code and the duration, never a word of the recognition.
"""

import importlib
import logging
import multiprocessing as mp
import os
import sys
import time
from collections.abc import Callable
from multiprocessing.context import SpawnProcess
from pathlib import Path
from typing import Any, Final

import numpy as np

from audio_video_search_backend import hardware, memory_guard
from audio_video_search_backend.engine.parakeet import Window

if sys.platform == "win32":  # the two platforms name the same thing differently
    from multiprocessing.connection import PipeConnection as PipeEnd
else:
    from multiprocessing.connection import Connection as PipeEnd

LOGGER = logging.getLogger(__name__)

# Not fork: the parent runs an event loop, threads and open sockets.
SPAWN_CONTEXT: Final = mp.get_context("spawn")

# The nice level of the child; the main process answers the search and never lowers itself.
ENGINE_NICE: Final = 10
# The highest value the kernel takes: when memory runs out, this child goes first (RES-03).
OOM_SCORE_ADJ: Final = 1000
OOM_SCORE_PATH: Final = Path("/proc/self/oom_score_adj")
# The model a worker runs unless it is told another one.
DEFAULT_MODEL: Final = "parakeet"
# Parakeet peaks at 1.2 to 1.7 GB (Spike 3); the reserve keeps the rest of the box alive.
# Plan 05-12 hands the need per model in from resources.py; until then this is it.
ENGINE_NEED_BYTES: Final = 1_700 * 1024**2
ENGINE_RESERVE_BYTES: Final = 512 * 1024**2
# One chunk of 10 min (plus lookahead) must be done within this wall time.
CHUNK_WALL_SECONDS: Final = 900
# A child serves this many chunks, then a fresh one takes over (leaks stay bounded).
MAX_CHUNKS_PER_CHILD: Final = 12
# The child never talks to Nextcloud: the AppAPI credentials are blanked in it (T-03-34).
SECRET_ENV: Final = {"APP_SECRET": "", "HP_SHARED_KEY": "", "NEXTCLOUD_URL": "", "AA_VERSION": ""}

OK: Final = "ok"
TIMEOUT: Final = "timeout"
OUT_OF_MEMORY: Final = "out_of_memory"
CRASHED: Final = "crashed"
NO_ROOM: Final = "no_room"

DEFAULT_FACTORY: Final = "audio_video_search_backend.engine.parakeet:Engine"

_JOB: Final = "transcribe"
_STOP: Final = "stop"
# A kill takes effect at once; the grace only keeps a wedged join from becoming a hang.
_JOIN_GRACE_SECONDS: Final = 5.0
# How often a waiting ask looks whether the child is still there.
_POLL_SLICE_SECONDS: Final = 1.0
# The exit code multiprocessing gives a child that was ended by SIGKILL.
_KILLED_EXIT: Final = -9
# ru_maxrss of Linux counts in KiB (getrusage(2); assumption A12, held by a test).
_KIB: Final = 1024


def _kill_child_tree(process: SpawnProcess) -> None:
    """Kill the child together with everything it may have spawned (Findling sandbox.py).

    The child made itself a session leader, so its process group id is its own
    pid. Before it got that far, or on Windows, the plain kill is the answer.
    """
    if sys.platform != "win32" and process.pid is not None:
        import signal

        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass
    process.kill()


def _answered(process: SpawnProcess, pipe: PipeEnd, deadline: float) -> bool:
    """Wait for the answer up to the deadline; stop waiting early when the child is gone.

    A child that dies before it ever holds its end of the pipe (a failure while
    it boots) does not always wake a waiting poll on Windows; looking at the
    process once per slice keeps that from becoming a wait for the whole deadline.
    """
    end = time.monotonic() + deadline
    while True:
        left = end - time.monotonic()
        if left <= 0:
            return False
        if pipe.poll(min(_POLL_SLICE_SECONDS, left)):
            return True
        if not process.is_alive():
            return pipe.poll(0)


def thread_env(threads: int) -> dict[str, str]:
    """The thread variables of a child that runs with ``threads`` threads.

    Read by the native thread pools while they load, so set before the
    library is imported. Never OMP_THREAD_LIMIT (PII 02-16: arm64 hung).
    """
    if threads < 1:
        raise ValueError("threads must be at least 1")
    return {"OMP_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}


def _standard_threads() -> int:
    """Half of the usable CPUs, capped (hardware.default_threads); the other half stays with Nextcloud."""
    return hardware.default_threads(hardware.usable_cpus())


def _factory(path: str) -> Callable[[Path, int], Any]:
    module, _, name = path.partition(":")
    return getattr(importlib.import_module(module), name)


def _catalog_need(model: str) -> int:
    """The bytes a model needs at its peak; only Parakeet is on record until plan 05-12."""
    if model != DEFAULT_MODEL:
        raise ValueError(f"no memory need on record for the model {model!r}")
    return ENGINE_NEED_BYTES


def _raise_oom_score(path: Path = OOM_SCORE_PATH) -> bool:
    """Make this process the first OOM victim; False off Linux or with a read-only /proc."""
    try:
        path.write_text(f"{OOM_SCORE_ADJ}\n", encoding="ascii")
    except OSError:
        return False
    return True


def _lower_self() -> None:
    """Own session, first OOM victim, nice: the first thing the child does (Linux)."""
    if sys.platform != "win32":
        os.setsid()
        _raise_oom_score()
        os.nice(ENGINE_NICE)


def _rss_bytes(ru_maxrss: int) -> int:
    """ru_maxrss of Linux in bytes."""
    return ru_maxrss * _KIB


def _peak_bytes() -> int | None:
    """The highest resident memory of this process so far in bytes, or None off Linux."""
    if sys.platform != "linux":
        return None
    import resource

    return _rss_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def _death_code(exitcode: int | None, kills_before: int | None, kills_after: int | None) -> str:
    """Why a child died that the worker did not kill itself.

    OUT_OF_MEMORY when the oom_kill counter rose while the job ran, or when the
    child was ended by SIGKILL; a counter that cannot be read proves nothing.
    """
    if kills_before is not None and kills_after is not None and kills_after > kills_before:
        return OUT_OF_MEMORY
    if exitcode == _KILLED_EXIT:
        return OUT_OF_MEMORY
    return CRASHED


def _child_main(pipe: PipeEnd, models_root: str, factory: str, threads: int) -> None:
    """The child: lower itself, blank the secrets, pin the pools, build the engine, answer jobs."""
    _lower_self()
    os.environ.pop("OMP_THREAD_LIMIT", None)
    os.environ.update(SECRET_ENV)
    os.environ.update(thread_env(threads))
    engine: Any = None
    failure: str | None = None
    try:
        engine = _factory(factory)(Path(models_root), threads)
    except MemoryError:
        failure = OUT_OF_MEMORY
    except Exception:
        failure = CRASHED
    while True:
        try:
            job = pipe.recv()
        except EOFError:
            return
        if job[0] == _STOP:
            return
        answer: tuple[str, list[Window]]
        if failure is not None:
            answer = (failure, [])
        else:
            try:
                pcm = np.frombuffer(job[1], dtype="<f4")
                answer = (OK, engine.transcribe(pcm, job[2], second_pass=job[3]))
            except MemoryError:
                answer = (OUT_OF_MEMORY, [])
            except Exception:
                answer = (CRASHED, [])
        try:
            pipe.send((*answer, _peak_bytes()))
        except (BrokenPipeError, OSError):
            return


class EngineWorker:
    """Holds at most one engine child and the rules for starting and replacing it."""

    def __init__(
        self,
        models_root: Path,
        *,
        model: str = DEFAULT_MODEL,
        factory: str = DEFAULT_FACTORY,
        headroom: Callable[[], int | None] = memory_guard.headroom_bytes,
        threads: Callable[[], int] = _standard_threads,
        need: Callable[[str], int] = _catalog_need,
        events: Callable[[], dict[str, int] | None] = memory_guard.memory_events,
    ) -> None:
        module, colon, name = factory.partition(":")
        if not (module and colon and name):
            raise ValueError("factory must be given as 'module:function'")
        self._models_root = models_root
        self._model = model
        self._factory = factory
        self._headroom = headroom
        self._threads = threads
        self._need = need
        self._events = events
        self._process: SpawnProcess | None = None
        self._pipe: PipeEnd | None = None
        self._chunks = 0
        self._child_threads: int | None = None
        self._last_peak_bytes: int | None = None

    @property
    def pid(self) -> int | None:
        """The process id of the current child, or None while there is none."""
        return None if self._process is None else self._process.pid

    @property
    def threads(self) -> int | None:
        """The thread count the current child was started with, or None while there is none."""
        return self._child_threads

    @property
    def last_peak_bytes(self) -> int | None:
        """The memory peak a child reported with its last answer, or None (no answer yet, or off Linux)."""
        return self._last_peak_bytes

    def start(self) -> str:
        """OK when a child runs (started now or before), NO_ROOM when the guard refuses."""
        if self._process is not None and self._process.is_alive():
            return OK
        self._recycle()
        if not memory_guard.admits(self._headroom(), need=self._need(self._model) + ENGINE_RESERVE_BYTES):
            LOGGER.info("engine start refused", extra={"code": NO_ROOM})
            return NO_ROOM
        # Read once per child: a changed count reaches the next child, never this one.
        threads = self._threads()
        thread_env(threads)  # refuses a count below 1 here, not inside the child
        parent_end, child_end = SPAWN_CONTEXT.Pipe(duplex=True)
        process = SPAWN_CONTEXT.Process(
            target=_child_main, args=(child_end, str(self._models_root), self._factory, threads), daemon=True
        )
        process.start()
        child_end.close()
        self._process, self._pipe, self._chunks, self._child_threads = process, parent_end, 0, threads
        return OK

    def ask(
        self, pcm: bytes, offset_ms: int, second_pass: bool, *, deadline: float = CHUNK_WALL_SECONDS
    ) -> tuple[str, list[Window]]:
        """Transcribe one chunk (f32 little endian, 16 kHz, mono) behind the process boundary."""
        started = time.monotonic()
        code, windows = self._ask(pcm, offset_ms, second_pass, deadline)
        LOGGER.info("engine chunk", extra={"code": code, "seconds": round(time.monotonic() - started, 2)})
        return code, windows

    def _ask(self, pcm: bytes, offset_ms: int, second_pass: bool, deadline: float) -> tuple[str, list[Window]]:
        if self.start() != OK:
            return NO_ROOM, []
        process, pipe = self._process, self._pipe
        if process is None or pipe is None:  # pragma: no cover - start() set both
            return CRASHED, []
        kills_before = self._oom_kills()
        try:
            pipe.send((_JOB, pcm, offset_ms, second_pass))
        except (BrokenPipeError, OSError):
            return self._died(process, kills_before), []
        if not _answered(process, pipe, deadline):
            if not process.is_alive():
                return self._died(process, kills_before), []
            _kill_child_tree(process)
            process.join(_JOIN_GRACE_SECONDS)
            self._recycle()
            return TIMEOUT, []
        try:
            code, windows, peak_bytes = pipe.recv()
        except (EOFError, OSError):
            return self._died(process, kills_before), []
        self._last_peak_bytes = peak_bytes
        self._chunks += 1
        if code != OK or self._chunks >= MAX_CHUNKS_PER_CHILD:
            self.stop()
        return code, windows

    def _oom_kills(self) -> int | None:
        """The oom_kill counter of memory.events, or None when it cannot be read."""
        counters = self._events()
        return None if counters is None else counters.get("oom_kill")

    def _died(self, process: SpawnProcess, kills_before: int | None) -> str:
        """The code of a child that went away on its own; the child is cleared."""
        process.join(_JOIN_GRACE_SECONDS)
        code = _death_code(process.exitcode, kills_before, self._oom_kills())
        self._recycle()
        if code == OUT_OF_MEMORY:
            LOGGER.warning("engine child killed for memory", extra={"code": OUT_OF_MEMORY})
        return code

    def stop(self) -> None:
        """End the child politely, then make sure it is gone either way."""
        process, pipe = self._process, self._pipe
        if process is not None and pipe is not None and process.is_alive():
            try:
                pipe.send((_STOP,))
                process.join(_JOIN_GRACE_SECONDS)
            except (BrokenPipeError, OSError):
                pass
        self._recycle()

    def _recycle(self) -> None:
        process, pipe = self._process, self._pipe
        self._process, self._pipe, self._chunks, self._child_threads = None, None, 0, None
        if pipe is not None:
            pipe.close()
        if process is None:
            return
        if process.is_alive():
            _kill_child_tree(process)
        process.join(_JOIN_GRACE_SECONDS)
        process.close()
