"""The capture: read every open reference once, completely, and hang it at its content key.

One reference per step, one step at a time (parallelism 1): a hanging read on
an SMB storage holds a PHP worker until max_execution_time (RESEARCH A6), so
the container never opens a second one beside it. There is no prefilter here:
every reference is downloaded through its own file id and its own reader;
attaching a further copy by the prefilter key comes only with the read proof
(plan 13).

The state machine of a reference (also the contract of plan 13):

- success (200, exactly ``ref.size`` bytes): ``Store.mark_keyed`` finds or
  creates the media item of the sha256, writes its head and clears its orphan
  mark (D-02-13); state active, stage keyed, proved now.
- every read failure of the own reader (read_denied for 403 and 422,
  access_control, not_found, read_timeout, gateway_failed, size_mismatch, and
  not_found for a reference without a reader) is AT ONCE state unreadable,
  stage failed, attempts + 1, next try after min(2^attempts * 60 s, 6 h), or
  300 s for access_control. An unreadable reference never counts and never
  gives a hit. After five attempts it stays failed without a next try until
  etag, size or mtime change or the reconcile asks again.
- locked (423): stage pending again, next try in 120 s, state and attempts
  unchanged; disk_full the same with 300 s. Neither is a verdict on the file.
- excluded (403 with that reason): the reference is deleted.
- too_large: stage failed without a next try; the file stays active and counts,
  it is honestly not transcribed.

Every outcome other than a validated success is a failure: an unknown error
code, a missing hash or a byte count other than ``ref.size`` is treated like
gateway_failed or size_mismatch, never as keyed. The content is not kept after
hashing (the temporary file is deleted in nc.fetch_to_tempfile).

Logs carry file ids, codes and counts only.
"""

import asyncio
import enum
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from audio_video_search_backend import companion, config, nc
from audio_video_search_backend.api import Services, run_locked
from audio_video_search_backend.store.repo import FileRef

LOGGER = logging.getLogger(__name__)

# Pause when there is nothing due; with work the next step follows at once.
IDLE_SECONDS: Final = 15.0
MAX_ATTEMPTS: Final = 5
RETRY_BASE_SECONDS: Final = 60
RETRY_CAP_SECONDS: Final = 6 * 3600
ACCESS_CONTROL_RETRY_SECONDS: Final = 300
LOCKED_RETRY_SECONDS: Final = 120
DISK_FULL_RETRY_SECONDS: Final = 300
# Larger files are not read at all; far above any recording, below a runaway.
MAX_CAPTURE_BYTES: Final = 64 * 1024**3
TMP_DIRNAME: Final = "tmp"

# The read failures of the own reader: each one is unreadable at once.
UNREADABLE_REASONS: Final = frozenset(
    {nc.READ_DENIED, nc.ACCESS_CONTROL, nc.NOT_FOUND, nc.READ_TIMEOUT, nc.GATEWAY_FAILED, nc.SIZE_MISMATCH}
)
_HEX64: Final = re.compile(r"[0-9a-f]{64}")

type Fetch = Callable[[int, str, Path, int, int], Awaitable[nc.FetchResult]]


class CaptureOutcome(enum.StrEnum):
    """What one step did with one reference."""

    IDLE = "idle"
    KEYED = "keyed"
    UNREADABLE = "unreadable"
    FAILED = "failed"
    DEFERRED = "deferred"
    DELETED = "deleted"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class CaptureStep:
    outcome: CaptureOutcome
    file_id: int | None = None
    reason: str | None = None
    media_id: int | None = None


_IDLE: Final = CaptureStep(CaptureOutcome.IDLE)


def retry_at(now: int, attempts_before: int, reason: str) -> int | None:
    """The time of the next try after a read failure, None after the last attempt."""
    if attempts_before + 1 >= MAX_ATTEMPTS:
        return None
    if reason == nc.ACCESS_CONTROL:
        return now + ACCESS_CONTROL_RETRY_SECONDS
    return now + min(2**attempts_before * RETRY_BASE_SECONDS, RETRY_CAP_SECONDS)


def tmp_dir() -> Path:
    """$APP_PERSISTENT_STORAGE/tmp, where a download lives until it is hashed."""
    return config.storage_root() / TMP_DIRNAME


async def _default_fetch(file_id: int, user_id: str, directory: Path, expected_size: int, cap: int) -> nc.FetchResult:
    return await nc.fetch_to_tempfile(file_id, user_id, directory, expected_size, cap)


def _validated(ref: FileRef, result: nc.FetchResult) -> tuple[str, str] | str:
    """(sha256, head_sha256) of a real success, otherwise the error code to judge the reference by."""
    if result.error is not None:
        return result.error if result.error in nc.FETCH_ERRORS else nc.GATEWAY_FAILED
    if result.size != ref.size:
        return nc.SIZE_MISMATCH
    sha, head = result.sha256, result.head_sha256
    if sha is None or head is None or _HEX64.fullmatch(sha) is None or _HEX64.fullmatch(head) is None:
        return nc.GATEWAY_FAILED
    return sha, head


class Capture:
    """One reference per step: claim, download, then one transaction that judges it."""

    def __init__(
        self,
        services: Services,
        *,
        directory: Path | None = None,
        fetch: Fetch = _default_fetch,
        clock: Callable[[], float] = time.time,
        max_bytes: int = MAX_CAPTURE_BYTES,
    ) -> None:
        self._services = services
        self._directory = tmp_dir() if directory is None else directory
        self._fetch = fetch
        self._clock = clock
        self._max_bytes = max_bytes
        # Parallelism 1 even if two callers step at once.
        self._serial = asyncio.Lock()

    def _now(self) -> int:
        return int(self._clock())

    async def prepare(self) -> None:
        """At start: the temporary directory exists, left over part files and claims are gone."""
        directory = self._directory

        def tidy() -> int:
            directory.mkdir(parents=True, exist_ok=True)
            return nc.remove_stale_parts(directory)

        removed = await asyncio.to_thread(tidy)
        store = self._services.store
        reset = await run_locked(self._services, store.reset_fetching)
        LOGGER.info("capture prepared", extra={"removed_parts": removed, "reset_claims": reset})

    async def run_once(self) -> CaptureStep:
        async with self._serial:
            return await self._step()

    async def _step(self) -> CaptureStep:
        store = self._services.store
        now = self._now()
        ref = await run_locked(self._services, lambda: store.next_capture(now))
        if ref is None:
            return _IDLE
        if ref.reader_uid is None:
            # Nobody to read as: no request, the verdict of a missing file.
            return await self._judge(ref, nc.NOT_FOUND)
        try:
            result = await self._fetch(ref.file_id, ref.reader_uid, self._directory, ref.size, self._max_bytes)
        except Exception as exc:  # a broken fetch is a failed read, never a stuck claim
            LOGGER.exception("capture fetch raised", extra={"file_id": ref.file_id, "error_type": type(exc).__name__})
            return await self._judge(ref, nc.GATEWAY_FAILED)
        checked = _validated(ref, result)
        if isinstance(checked, str):
            return await self._judge(ref, checked)
        sha, head = checked
        media_id = await run_locked(self._services, lambda: store.mark_keyed(ref, sha, head, self._now()))
        if media_id is None:
            return CaptureStep(CaptureOutcome.STALE, ref.file_id)
        return CaptureStep(CaptureOutcome.KEYED, ref.file_id, media_id=media_id)

    async def _judge(self, ref: FileRef, reason: str) -> CaptureStep:
        store = self._services.store
        now = self._now()
        if reason == nc.EXCLUDED:
            done = await run_locked(self._services, lambda: store.delete_ref(ref, now))
            outcome = CaptureOutcome.DELETED
        elif reason in (nc.LOCKED, nc.DISK_FULL):
            wait = LOCKED_RETRY_SECONDS if reason == nc.LOCKED else DISK_FULL_RETRY_SECONDS
            done = await run_locked(
                self._services, lambda: store.defer_capture(ref, reason, retry_at=now + wait, now=now)
            )
            outcome = CaptureOutcome.DEFERRED
        elif reason == nc.TOO_LARGE:
            done = await run_locked(
                self._services, lambda: store.mark_failed(ref, reason, retry_at=None, state="active", now=now)
            )
            outcome = CaptureOutcome.FAILED
        else:
            # Every other code is a read failure of the own reader (an unknown
            # one was mapped to gateway_failed before): unreadable at once.
            code = reason if reason in UNREADABLE_REASONS else nc.GATEWAY_FAILED
            next_try = retry_at(now, ref.attempts, code)
            done = await run_locked(
                self._services, lambda: store.mark_failed(ref, code, retry_at=next_try, state="unreadable", now=now)
            )
            outcome, reason = CaptureOutcome.UNREADABLE, code
        if not done:
            return CaptureStep(CaptureOutcome.STALE, ref.file_id, reason)
        return CaptureStep(outcome, ref.file_id, reason)

    async def run_forever(
        self,
        *,
        idle: float = IDLE_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rounds: int | None = None,
    ) -> None:
        """Step while the PHP app is there; without work, or before ok, every ``idle`` seconds."""
        await self.prepare()
        done = 0
        while rounds is None or done < rounds:
            done += 1
            step = _IDLE
            if companion.current().state == companion.OK:
                try:
                    step = await self.run_once()
                except Exception as exc:  # the loop must outlive any single step
                    LOGGER.exception("capture step failed", extra={"error_type": type(exc).__name__})
            if step.outcome == CaptureOutcome.IDLE:
                await sleep(idle)
            else:
                LOGGER.info(
                    "capture step",
                    extra={"file_id": step.file_id, "outcome": step.outcome.value, "reason": step.reason},
                )


async def run_forever(services: Services) -> None:
    """The background task of main.py."""
    await Capture(services).run_forever()
