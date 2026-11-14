"""The model files on the volume: fetch, verify, install (plan 03-07, after Findling ``embed/weights.py``).

Every file lives under ``<volume>/models/<model>/<MODEL_SHA256>/<file>`` and has
exactly the identity of :mod:`catalog`. Three rules carry the design:

* A download is written to ``<file>.part``, hashed and counted while it
  streams, fsynced, and only renamed to ``<file>`` with ``os.replace`` after
  length and digest match. Anything else removes the ``.part``.
* Every failure is a value out of :data:`PROCURE_OUTCOMES`, never an exception
  the caller has to know, and no failure leaves a file behind.
* A file the admin placed by hand (air gap) is verified against the same digest
  and length before it counts, without a single request. The verdict is kept
  in a small JSON file next to it, keyed on size and modification time, so the
  next start costs one stat instead of hashing 650 MB again.

The bytes arrive only through ``nc.fetch_model_asset`` (tests/test_boundary.py).
Logs carry the model name, an outcome and an error type, never a path or a URL.

Command line for CI and admins::

    python -m audio_video_search_backend.models.procure --root PATH [--verify-only]

fetches (or only checks) both models and ends with exit 0 only when both are
present or procured.
"""

import argparse
import asyncio
import errno
import hashlib
import json
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Final

from audio_video_search_backend import nc
from audio_video_search_backend.models import catalog

LOGGER = logging.getLogger(__name__)

PROCURED: Final = "procured"
PRESENT: Final = "present"
UNAVAILABLE: Final = "unavailable"
WRONG_DIGEST: Final = "wrong_digest"
NO_ROOM: Final = "no_room"
PROCURE_OUTCOMES: Final = frozenset({PROCURED, PRESENT, UNAVAILABLE, WRONG_DIGEST, NO_ROOM})
READY_OUTCOMES: Final = frozenset({PROCURED, PRESENT})

PART_SUFFIX: Final = ".part"
VERDICT_SUFFIX: Final = ".verified.json"
# The order of the command line and of /init: the small model first.
MODEL_ORDER: Final = ("silero", "parakeet")

# The shape of nc.fetch_model_asset.
FetchModel = Callable[..., Awaitable[str]]
Progress = Callable[[int], Awaitable[None]]

_HASH_CHUNK: Final = 1024 * 1024
# How often this process hashed a whole file; makes the verdict cache checkable.
_HASH_COUNT = 0
# Whether both models were found or fetched and verified in this process.
_READY = False


def models_ready() -> bool:
    """True once both models are verified on the volume in this process."""
    return _READY


def mark_ready(ready: bool = True) -> None:
    """Set the answer of :func:`models_ready` (``/init`` and the start check do this)."""
    global _READY
    _READY = ready


def hash_count() -> int:
    """How often this process has hashed a whole model file."""
    return _HASH_COUNT


def model_dir(root: Path, name: str) -> Path:
    """Where the files of one model live on the volume."""
    return root / "models" / name / catalog.MODEL_SHA256


def _file_digest(path: Path) -> str:
    global _HASH_COUNT
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(_HASH_CHUNK):
            digest.update(block)
    _HASH_COUNT += 1
    return digest.hexdigest()


def _verdict_path(target: Path) -> Path:
    return target.with_name(target.name + VERDICT_SUFFIX)


def _remember(target: Path, entry: catalog.ModelFile) -> None:
    """Write the verdict for a file that matched, keyed on its size and mtime."""
    status = target.stat()
    record = {"sha256": entry.sha256, "size": status.st_size, "mtime_ns": status.st_mtime_ns}
    verdict = _verdict_path(target)
    temporary = verdict.with_name(verdict.name + ".tmp")
    temporary.write_text(json.dumps(record), encoding="utf-8")
    os.replace(temporary, verdict)


def _remembered(target: Path, entry: catalog.ModelFile, status: os.stat_result) -> bool:
    try:
        record = json.loads(_verdict_path(target).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(record, dict) and record == {
        "sha256": entry.sha256,
        "size": status.st_size,
        "mtime_ns": status.st_mtime_ns,
    }


def verify_file(target: Path, entry: catalog.ModelFile) -> bool | None:
    """The verdict on a file on the volume: True matches, False does not, None is missing.

    Synchronous on purpose (the first look hashes up to 650 MB); an async
    caller runs it in a thread. A file of the wrong length is False without a
    hash; an unchanged file with a remembered verdict costs one stat.
    """
    try:
        status = target.stat()
    except FileNotFoundError:
        return None
    if status.st_size != entry.size:
        return False
    if _remembered(target, entry, status):
        return True
    if _file_digest(target) != entry.sha256:
        return False
    try:
        _remember(target, entry)
    except OSError as error:
        # Only the cache is lost; the file itself matched.
        LOGGER.warning("model verdict not stored", extra={"error_type": type(error).__name__})
    return True


def _fsync(path: Path) -> None:
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())


def _unlink(path: Path) -> None:
    path.unlink(missing_ok=True)


async def _download(entry: catalog.ModelFile, directory: Path, fetch: FetchModel, report: Progress) -> str:
    """Fetch one file into its ``.part``, check it, install it; returns an outcome."""
    target = directory / entry.name
    part = directory / (entry.name + PART_SUFFIX)
    try:
        free = await asyncio.to_thread(nc.free_bytes, directory)
    except OSError:
        return NO_ROOM
    if free < entry.size + nc.DISK_RESERVE_BYTES:
        return NO_ROOM

    digest = hashlib.sha256()
    received = 0

    async def observe(chunk: bytes) -> None:
        nonlocal received
        digest.update(chunk)
        received += len(chunk)
        await report(received)

    try:
        await asyncio.to_thread(_unlink, part)
        code = await fetch(
            entry.url,
            part,
            expected_size=entry.size,
            allowed_hosts=catalog.ASSET_HOSTS,
            on_chunk=observe,
        )
        if code == nc.MODEL_TOO_LARGE:
            return WRONG_DIGEST
        if code != nc.MODEL_FETCHED:
            return UNAVAILABLE
        if received != entry.size or digest.hexdigest() != entry.sha256:
            return WRONG_DIGEST
        await asyncio.to_thread(_fsync, part)
        await asyncio.to_thread(os.replace, part, target)
    except OSError as error:
        LOGGER.warning("model file not written", extra={"error_type": type(error).__name__})
        return NO_ROOM if error.errno == errno.ENOSPC else UNAVAILABLE
    finally:
        # Every way out but the rename leaves no .part, a cancellation included.
        _unlink(part)
    try:
        await asyncio.to_thread(_remember, target, entry)
    except OSError as error:
        LOGGER.warning("model verdict not stored", extra={"error_type": type(error).__name__})
    return PROCURED


async def _no_progress(_done: int) -> None:
    return None


async def procure(
    root: Path,
    name: str,
    *,
    fetch: FetchModel | None = nc.fetch_model_asset,
    progress: Progress | None = None,
) -> str:
    """Make sure every file of one model is on the volume, return one of :data:`PROCURE_OUTCOMES`.

    ``fetch=None`` only verifies (the start check after a restart, the air gap
    check of the command line): a missing file is then UNAVAILABLE without a
    request. A file that is there but does not match is WRONG_DIGEST and is left
    as it is, so an admin sees the error instead of a silent overwrite.
    ``progress`` gets the bytes of this model done so far.
    """
    report = progress if progress is not None else _no_progress
    directory = model_dir(root, name)
    fetched_any = False
    done = 0
    try:
        await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    except OSError as error:
        return _outcome(name, UNAVAILABLE, error)
    for entry in catalog.MODELS[name]:
        try:
            verdict = await asyncio.to_thread(verify_file, directory / entry.name, entry)
        except OSError as error:
            return _outcome(name, UNAVAILABLE, error)
        if verdict is False:
            return _outcome(name, WRONG_DIGEST)
        if verdict is None:
            if fetch is None:
                return _outcome(name, UNAVAILABLE)
            base = done

            async def step(received: int, base: int = base) -> None:
                await report(base + received)

            outcome = await _download(entry, directory, fetch, step)
            if outcome != PROCURED:
                return _outcome(name, outcome)
            fetched_any = True
        done += entry.size
        await report(done)
    return _outcome(name, PROCURED if fetched_any else PRESENT)


def _outcome(name: str, outcome: str, error: BaseException | None = None) -> str:
    extra: dict[str, str] = {"model": name, "outcome": outcome}
    if error is not None:
        extra["error_type"] = type(error).__name__
    LOGGER.info("model procure", extra=extra)
    return outcome


async def _run(root: Path, *, verify_only: bool) -> dict[str, str]:
    results: dict[str, str] = {}
    for name in MODEL_ORDER:
        results[name] = await procure(root, name, fetch=None if verify_only else nc.fetch_model_asset)
    return results


def cli(argv: list[str] | None = None) -> int:
    """Fetch or verify both models; exit 0 only when both are there."""
    parser = argparse.ArgumentParser(prog="audio_video_search_backend.models.procure")
    parser.add_argument("--root", type=Path, required=True, help="the persistent volume")
    parser.add_argument("--verify-only", action="store_true", help="check the files, fetch nothing")
    arguments = parser.parse_args(argv)
    results = asyncio.run(_run(arguments.root, verify_only=arguments.verify_only))
    for name, outcome in results.items():
        sys.stdout.write(f"{name} {outcome}\n")
    return 0 if all(outcome in READY_OUTCOMES for outcome in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(cli())
