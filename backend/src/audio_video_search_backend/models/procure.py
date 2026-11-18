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
  in this process only, keyed on size and modification time, so the second
  look costs one stat instead of hashing 650 MB again.

A file the release holds in parts (``catalog.PartedFile``, the Whisper
``model.bin`` of plan 05-08) follows the same rules with one difference: its
parts are appended to ONE ``<file>.part``, so the volume needs the length of the
file once, never twice. Two digests run while it streams, one per part and one
for the whole. A part that does not match is cut off again, so the ``.part``
always ends at the border of a verified part, and the run ends with
WRONG_DIGEST. Such a ``.part`` is the one thing a failure may leave behind: the
next run continues behind it, but only when its length is a part border and
only after hashing every part in it again; anything else is removed. The file
is installed after the sha256 of the whole matched, which is also the one
verdict for a whole file the admin placed.

The bytes arrive only through ``nc.fetch_model_asset`` and
``nc.fetch_model_part`` (tests/test_boundary.py).
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
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import BinaryIO, Final, Protocol

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
# The order of the command line and of /init: the small model first.
MODEL_ORDER: Final = ("silero", "parakeet")

# The shape of nc.fetch_model_asset.
FetchModel = Callable[..., Awaitable[str]]
# The shape of nc.fetch_model_part.
FetchPart = Callable[..., Awaitable[str]]


class _Digest(Protocol):
    """What this module uses of a running sha256."""

    def update(self, data: bytes, /) -> None: ...

    def hexdigest(self) -> str: ...


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


# Verdicts live only in this process: anything that can write the volume could
# also forge a stored verdict file, so every process start hashes anew.
_VERIFIED: dict[Path, tuple[str, int, int]] = {}


def _remember(target: Path, entry: catalog.ModelFile | catalog.PartedFile) -> None:
    status = target.stat()
    _VERIFIED[target] = (entry.sha256, status.st_size, status.st_mtime_ns)


def verify_file(target: Path, entry: catalog.ModelFile | catalog.PartedFile) -> bool | None:
    """The verdict on a file on the volume: True matches, False does not, None is missing.

    Synchronous on purpose (the first look hashes up to 3 GB); an async
    caller runs it in a thread. A file of the wrong length is False without a
    hash; a file this process already hashed costs one stat. For a file the
    release holds in parts the whole file is judged, by the sha256 of the whole.
    """
    try:
        status = target.stat()
    except FileNotFoundError:
        return None
    if status.st_size != entry.size:
        return False
    if _VERIFIED.get(target) == (entry.sha256, status.st_size, status.st_mtime_ns):
        return True
    if _file_digest(target) != entry.sha256:
        return False
    _remember(target, entry)
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
        _remember(target, entry)
    except OSError as error:
        # Only the in-process cache is lost; the file itself matched.
        LOGGER.warning("model verdict not stored", extra={"error_type": type(error).__name__})
    return PROCURED


def _resume(part: Path, entry: catalog.PartedFile) -> tuple[int, _Digest]:
    """How many parts a ``.part`` of an earlier run holds, and the digest over them.

    Nothing stored is trusted: the length must be a part border and every part
    in it is hashed again. Anything else removes the ``.part`` and starts at zero.
    """
    whole = hashlib.sha256()
    try:
        length = part.stat().st_size
    except FileNotFoundError:
        return 0, whole
    borders: list[int] = []
    end = 0
    for piece in entry.parts:
        end += piece.size
        borders.append(end)
    if length not in borders:
        _unlink(part)
        return 0, whole
    held = borders.index(length) + 1
    with part.open("rb") as source:
        for piece in entry.parts[:held]:
            digest = hashlib.sha256()
            left = piece.size
            while left > 0:
                block = source.read(min(_HASH_CHUNK, left))
                if not block:
                    break
                digest.update(block)
                whole.update(block)
                left -= len(block)
            if left or digest.hexdigest() != piece.sha256:
                held = 0
                break
    if not held:
        _unlink(part)
        return 0, hashlib.sha256()
    return held, whole


def _open_append(part: Path) -> BinaryIO:
    # "r+b" keeps what is there and writes where the handle stands; "ab" would
    # write at the end whatever the handle says.
    part.touch()
    return part.open("r+b")


def _cut(handle: BinaryIO, length: int) -> None:
    handle.flush()
    handle.seek(length)
    handle.truncate()


def _close_synced(handle: BinaryIO) -> None:
    try:
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()


def _drop_empty(part: Path) -> None:
    try:
        if part.stat().st_size == 0:
            part.unlink()
    except FileNotFoundError:
        return


async def _append_parts(
    entry: catalog.PartedFile,
    handle: BinaryIO,
    held: int,
    whole: _Digest,
    fetch_part: FetchPart,
    report: Progress,
) -> str:
    """Append the parts behind the first ``held`` ones; PROCURED once the whole matches."""
    offset = sum(piece.size for piece in entry.parts[:held])
    for piece in entry.parts[held:]:
        digest = hashlib.sha256()
        received = 0

        async def observe(chunk: bytes, digest: _Digest = digest, offset: int = offset) -> None:
            # Every way out but a matching part ends the run, so the digest of
            # the whole never has to forget the bytes of a part that failed.
            nonlocal received
            digest.update(chunk)
            whole.update(chunk)
            received += len(chunk)
            await report(offset + received)

        code = await fetch_part(
            piece.url,
            handle,
            start=offset,
            expected_size=piece.size,
            allowed_hosts=catalog.ASSET_HOSTS,
            on_chunk=observe,
        )
        if code == nc.MODEL_TOO_LARGE:
            return WRONG_DIGEST
        if code != nc.MODEL_FETCHED:
            return UNAVAILABLE
        if received != piece.size or digest.hexdigest() != piece.sha256:
            # The fetch counted the bytes, only the digest can refuse them here:
            # the part goes, the ones before it stay.
            await asyncio.to_thread(_cut, handle, offset)
            return WRONG_DIGEST
        offset += piece.size
    if offset != entry.size or whole.hexdigest() != entry.sha256:
        # Every part matched and the whole does not: nothing of it can be used.
        await asyncio.to_thread(_cut, handle, 0)
        return WRONG_DIGEST
    return PROCURED


async def _download_parted(entry: catalog.PartedFile, directory: Path, fetch_part: FetchPart, report: Progress) -> str:
    """Fetch a file in parts into its one ``.part``, check it, install it; returns an outcome."""
    target = directory / entry.name
    part = directory / (entry.name + PART_SUFFIX)
    try:
        held, whole = await asyncio.to_thread(_resume, part, entry)
    except OSError as error:
        LOGGER.warning("model part file not readable", extra={"error_type": type(error).__name__})
        return UNAVAILABLE
    try:
        free = await asyncio.to_thread(nc.free_bytes, directory)
    except OSError:
        return NO_ROOM
    # The parts are appended to the one file, so only what is still missing needs room.
    missing = entry.size - sum(piece.size for piece in entry.parts[:held])
    if free < missing + nc.DISK_RESERVE_BYTES:
        return NO_ROOM

    try:
        handle = await asyncio.to_thread(_open_append, part)
        try:
            outcome = await _append_parts(entry, handle, held, whole, fetch_part, report)
        finally:
            await asyncio.to_thread(_close_synced, handle)
        if outcome == PROCURED:
            await asyncio.to_thread(os.replace, part, target)
        else:
            await asyncio.to_thread(_drop_empty, part)
    except OSError as error:
        LOGGER.warning("model file not written", extra={"error_type": type(error).__name__})
        return NO_ROOM if error.errno == errno.ENOSPC else UNAVAILABLE
    if outcome != PROCURED:
        return outcome
    try:
        _remember(target, entry)
    except OSError as error:
        # Only the in-process cache is lost; the file itself matched.
        LOGGER.warning("model verdict not stored", extra={"error_type": type(error).__name__})
    return PROCURED


async def _no_progress(_done: int) -> None:
    return None


async def procure(
    root: Path,
    name: str,
    *,
    fetch: FetchModel | None = nc.fetch_model_asset,
    fetch_part: FetchPart = nc.fetch_model_part,
    progress: Progress | None = None,
) -> str:
    """Make sure every file of one model is on the volume, return one of :data:`PROCURE_OUTCOMES`.

    ``fetch=None`` only verifies (the start check after a restart, the air gap
    check of the command line): a missing file is then UNAVAILABLE without a
    request, whether it is a whole file or one in parts, and a ``.part`` of an
    earlier run is not touched. A file that is there but does not match is
    WRONG_DIGEST and is left as it is, so an admin sees the error instead of a
    silent overwrite. ``fetch`` brings whole files, ``fetch_part`` the parts of
    a file the release holds in parts. ``progress`` gets the bytes of this model
    done so far.
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

            if isinstance(entry, catalog.PartedFile):
                outcome = await _download_parted(entry, directory, fetch_part, step)
            else:
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
