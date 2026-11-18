"""Measure the Linux memory peak of the Parakeet child on one 10 min chunk (plan 05-01, D-05-09).

Runs inside the released image, never part of it (the build context is backend/):

    /app/.venv/bin/python -I /probe/peak_probe.py --models ROOT --wav PATH --out PATH

Reads a 16 kHz mono WAV, repeats it to exactly CHUNK_MS + CHUNK_LOOKAHEAD_MS of
media, starts the unchanged EngineWorker with the default factory (real
Parakeet), sends the one chunk with ask, stops the child and then reads
ru_maxrss of the waited children (Linux: KiB). While the chunk runs, a thread
samples VmHWM of the child out of /proc/<pid>/status every 0.5 s.

The output is one JSON object {arch, ru_maxrss_kib, vmhwm_kib, code, words,
seconds, threads_env}. The code has to be ok and words above zero, otherwise
exit 1: the positive control that the measurement ran on real speech. No word
of the transcript is written, only the count.
"""

import argparse
import json
import platform
import resource
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np

from audio_video_search_backend import hardware
from audio_video_search_backend.engine.child import OK, EngineWorker, thread_env
from audio_video_search_backend.engine.constants import CHUNK_LOOKAHEAD_MS, CHUNK_MS, SAMPLE_RATE

SAMPLE_SECONDS = 0.5
EXIT_FAILED = 1


def read_pcm(path: Path) -> np.ndarray:
    """The samples of a 16 kHz mono s16 WAV as float32 in [-1, 1]."""
    with wave.open(str(path), "rb") as source:
        if source.getframerate() != SAMPLE_RATE or source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise SystemExit(f"{path.name}: not 16 kHz mono s16")
        frames = source.readframes(source.getnframes())
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def one_chunk(samples: np.ndarray) -> bytes:
    """The clip repeated to exactly CHUNK_MS + CHUNK_LOOKAHEAD_MS, as f32 little endian."""
    wanted = (CHUNK_MS + CHUNK_LOOKAHEAD_MS) * SAMPLE_RATE // 1000
    repeats = -(-wanted // len(samples))
    return np.tile(samples, repeats)[:wanted].astype("<f4").tobytes()


def vmhwm_kib(pid: int) -> int | None:
    """VmHWM of a process in KiB, or None when /proc has no such line (or no such process)."""
    try:
        status = Path(f"/proc/{pid}/status").read_text(encoding="ascii")
    except (OSError, ValueError):
        return None
    for line in status.splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1])
    return None


class PeakSampler(threading.Thread):
    """Samples VmHWM of the current child until stopped and keeps the maximum."""

    def __init__(self, worker: EngineWorker) -> None:
        super().__init__(daemon=True)
        self._worker = worker
        self._done = threading.Event()
        self.peak_kib = 0

    def run(self) -> None:
        while not self._done.wait(SAMPLE_SECONDS):
            pid = self._worker.pid
            if pid is not None:
                self.peak_kib = max(self.peak_kib, vmhwm_kib(pid) or 0)

    def finish(self) -> None:
        self._done.set()
        self.join()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    pcm = one_chunk(read_pcm(args.wav))
    # The count the product takes by default, read once here so the record names it.
    threads = hardware.default_threads(hardware.usable_cpus())
    worker = EngineWorker(args.models, threads=lambda: threads)
    sampler = PeakSampler(worker)
    sampler.start()
    started = time.monotonic()
    try:
        code, windows = worker.ask(pcm, 0, False)
    finally:
        sampler.finish()
        worker.stop()
    seconds = round(time.monotonic() - started, 1)

    result = {
        "arch": platform.machine(),
        "ru_maxrss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        "vmhwm_kib": sampler.peak_kib,
        "code": code,
        "words": sum(window.n_words for window in windows),
        "seconds": seconds,
        "threads_env": thread_env(threads),
    }
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if code == OK and result["words"] > 0 else EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
