"""The engine in its own child process, one per job block (plan 03-10).

Built after Findling 1.6.4 ``findling/extract/sandbox.py`` (SPAWN_CONTEXT, the
nice level, the group kill, the child loop with its pipe, the ask with a
deadline). Why a child at all: the model memory of ONNX Runtime goes back to
the system only with the process, and a crash or a hang of native code must
never take the main process along (T-03-33).

- Before every start the memory guard reads the headroom; below the need of
  the engine plus a reserve no child is started and the answer is NO_ROOM.
- The child runs at nice 10 in its own session (Linux), takes the app secrets
  out of its environment (Findling ``_shed_secrets``, T-03-34) and pins the
  thread pools before sherpa_onnx is imported; it builds the engine once.
- A job is (pcm, offset_ms, second_pass) over the pipe; the answer is a code
  and the windows. Over the wall time the whole child is killed (TIMEOUT); a
  MemoryError is OUT_OF_MEMORY, any other failure or death CRASHED; after both
  the child is replaced, and after MAX_CHUNKS_PER_CHILD jobs as well.
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

from audio_video_search_backend import memory_guard
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
# Parakeet peaks at 1.2 to 1.7 GB (Spike 3); the reserve keeps the rest of the box alive.
ENGINE_NEED_BYTES: Final = 1_700 * 1024**2
ENGINE_RESERVE_BYTES: Final = 512 * 1024**2
# One chunk of 10 min (plus lookahead) must be done within this wall time.
CHUNK_WALL_SECONDS: Final = 900
# A child serves this many chunks, then a fresh one takes over (leaks stay bounded).
MAX_CHUNKS_PER_CHILD: Final = 12
# Read by the native thread pools while they load, so set before sherpa_onnx is imported.
THREAD_ENV: Final = {"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
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


def _factory(path: str) -> Callable[[Path], Any]:
    module, _, name = path.partition(":")
    return getattr(importlib.import_module(module), name)


def _child_main(pipe: PipeEnd, models_root: str, factory: str) -> None:
    """The child: lower itself, blank the secrets, pin the pools, build the engine, answer jobs."""
    if sys.platform != "win32":
        os.setsid()
        os.nice(ENGINE_NICE)
    os.environ.update(SECRET_ENV)
    os.environ.update(THREAD_ENV)
    engine: Any = None
    failure: str | None = None
    try:
        engine = _factory(factory)(Path(models_root))
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
            pipe.send(answer)
        except (BrokenPipeError, OSError):
            return


class EngineWorker:
    """Holds at most one engine child and the rules for starting and replacing it."""

    def __init__(
        self,
        models_root: Path,
        *,
        factory: str = DEFAULT_FACTORY,
        headroom: Callable[[], int | None] = memory_guard.headroom_bytes,
    ) -> None:
        module, colon, name = factory.partition(":")
        if not (module and colon and name):
            raise ValueError("factory must be given as 'module:function'")
        self._models_root = models_root
        self._factory = factory
        self._headroom = headroom
        self._process: SpawnProcess | None = None
        self._pipe: PipeEnd | None = None
        self._chunks = 0

    @property
    def pid(self) -> int | None:
        """The process id of the current child, or None while there is none."""
        return None if self._process is None else self._process.pid

    def start(self) -> str:
        """OK when a child runs (started now or before), NO_ROOM when the guard refuses."""
        if self._process is not None and self._process.is_alive():
            return OK
        self._recycle()
        if not memory_guard.admits(self._headroom(), need=ENGINE_NEED_BYTES + ENGINE_RESERVE_BYTES):
            LOGGER.info("engine start refused", extra={"code": NO_ROOM})
            return NO_ROOM
        parent_end, child_end = SPAWN_CONTEXT.Pipe(duplex=True)
        process = SPAWN_CONTEXT.Process(
            target=_child_main, args=(child_end, str(self._models_root), self._factory), daemon=True
        )
        process.start()
        child_end.close()
        self._process, self._pipe, self._chunks = process, parent_end, 0
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
        try:
            pipe.send((_JOB, pcm, offset_ms, second_pass))
        except (BrokenPipeError, OSError):
            self._recycle()
            return CRASHED, []
        if not pipe.poll(deadline):
            _kill_child_tree(process)
            process.join(_JOIN_GRACE_SECONDS)
            self._recycle()
            return TIMEOUT, []
        try:
            code, windows = pipe.recv()
        except (EOFError, OSError):
            self._recycle()
            return CRASHED, []
        self._chunks += 1
        if code != OK or self._chunks >= MAX_CHUNKS_PER_CHILD:
            self.stop()
        return code, windows

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
        self._process, self._pipe, self._chunks = None, None, 0
        if pipe is not None:
            pipe.close()
        if process is None:
            return
        if process.is_alive():
            _kill_child_tree(process)
        process.join(_JOIN_GRACE_SECONDS)
        process.close()
