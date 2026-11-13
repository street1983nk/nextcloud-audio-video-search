"""The capture: read every open reference once, completely, and hang it at its content key.

One reference per step, one step at a time (parallelism 1): a hanging read on
an SMB storage holds a PHP worker until max_execution_time (RESEARCH A6), so
the container never opens a second one beside it, neither a download nor a
read proof.

Three ways lead through a step (plan 02-13):

- a reference without a content whose prefilter key a keyed, active sibling
  shares: its own read proof (worker/read_proof.py). ok attaches it to the
  content of the sibling without a download; other bytes (head_mismatch) send
  it to its own full download; every other outcome judges it like a failed
  read below.
- a reference that hangs at a content already (its renewed proof is due,
  D-02-12, or an earlier renewed proof failed): the read proof against the head
  of its own content. ok confirms it (active, keyed, proved now); a failure
  makes it unreadable at once with its content kept, so its hits are gone and
  the next try is a proof again; other bytes let it go of the content and read
  it in full.
- every other reference: the full download through its own file id and its
  own reader. Afterwards the waiting copies with its prefilter key are due at
  once.

The circuit per storage (read_proof.StorageBreaker): after three timeouts in a
row, every due reference of that storage is set unreadable, failed,
storage_paused with the closing time as its next try, without a request, and
checked again after that hour.

The state machine of a reference:

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
- excluded (403 with that reason): the reference is deleted, the sample of the
  file with it, and a content that loses its last reference this way is
  forgotten at once, index documents included (D-02-04, D-02-15a).
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
from audio_video_search_backend.worker import read_proof
from audio_video_search_backend.worker.read_proof import ProofOutcome, StorageBreaker

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
# The two codes of a fetch that sent no request; they say nothing about the storage.
_NO_REQUEST: Final = frozenset({nc.DISK_FULL, nc.TOO_LARGE})
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


async def _default_head(file_id: int, user_id: str) -> nc.HeadResult:
    return await nc.fetch_head(file_id, user_id)


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
    """One reference per step: claim, read proof or download, then one transaction that judges it."""

    def __init__(
        self,
        services: Services,
        *,
        directory: Path | None = None,
        fetch: Fetch = _default_fetch,
        head: read_proof.HeadFetch = _default_head,
        clock: Callable[[], float] = time.time,
        max_bytes: int = MAX_CAPTURE_BYTES,
        breaker: StorageBreaker | None = None,
    ) -> None:
        self._services = services
        self._directory = tmp_dir() if directory is None else directory
        self._fetch = fetch
        self._head = head
        self._clock = clock
        self._max_bytes = max_bytes
        self._breaker = StorageBreaker() if breaker is None else breaker
        # Parallelism 1 even if two callers step at once: never two proofs or downloads side by side.
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
        closes = self._breaker.closes_at(ref.storage_id, now)
        if closes is not None:
            return await self._pause(ref, closes)
        reader = ref.reader_uid
        if reader is None:
            # Nobody to read as: no request, the verdict of a missing file.
            return await self._judge(ref, nc.NOT_FOUND)
        proved = await (self._prove_copy(ref) if ref.media_id is None else self._prove_again(ref, ref.media_id))
        if proved is not None:
            return proved
        return await self._download(ref, reader)

    async def _pause(self, ref: FileRef, closes: int) -> CaptureStep:
        """The storage hangs: no request; unreadable until the circuit closes, then checked again."""
        store = self._services.store
        now = self._now()
        done = await run_locked(
            self._services,
            lambda: store.mark_failed(
                ref, read_proof.STORAGE_PAUSED, retry_at=closes, bump=False, state="unreadable", now=now
            ),
        )
        outcome = CaptureOutcome.UNREADABLE if done else CaptureOutcome.STALE
        return CaptureStep(outcome, ref.file_id, read_proof.STORAGE_PAUSED)

    def _answered(self, ref: FileRef, *, timed_out: bool) -> None:
        self._breaker.record(ref.storage_id, timed_out=timed_out, now=self._now())

    async def _still_claimed(self, ref: FileRef) -> bool:
        store = self._services.store
        current = await run_locked(self._services, lambda: store.file_ref(ref.file_id))
        return current is not None and current.stage == "fetching" and current.etag == ref.etag

    async def _prove_copy(self, ref: FileRef) -> CaptureStep | None:
        """A copy without a content: its own read proof against a keyed sibling. None: read it in full."""
        store = self._services.store
        key = ref.prefilter_key
        if key is None:
            return None
        sibling = await run_locked(self._services, lambda: store.prefilter_sibling(key))
        if sibling is None:
            return None
        media_id, head = sibling
        outcome = await read_proof.prove_read(ref, head, read_proof.head_length(ref.size), self._head)
        self._answered(ref, timed_out=outcome is ProofOutcome.READ_TIMEOUT)
        if outcome is ProofOutcome.OK:
            attached = await run_locked(
                self._services, lambda: store.attach_by_proof(ref.file_id, media_id, ref.etag, self._now())
            )
            if attached:
                return CaptureStep(CaptureOutcome.KEYED, ref.file_id, media_id=media_id)
            if await self._still_claimed(ref):
                # The sibling went away while the head was read: this copy reads its own bytes in full.
                return None
            return CaptureStep(CaptureOutcome.STALE, ref.file_id)
        if outcome is ProofOutcome.HEAD_MISMATCH:
            return None
        return await self._judge(ref, outcome.value)

    async def _prove_again(self, ref: FileRef, media_id: int) -> CaptureStep | None:
        """A reference that hangs at a content: the read proof against that content. None: read it in full."""
        store = self._services.store
        head = await run_locked(self._services, lambda: store.media_head(media_id))
        if head is None:
            return None
        outcome = await read_proof.prove_read(ref, head, read_proof.head_length(ref.size), self._head)
        self._answered(ref, timed_out=outcome is ProofOutcome.READ_TIMEOUT)
        if outcome is ProofOutcome.OK:
            confirmed = await run_locked(
                self._services, lambda: store.confirm_proof(ref.file_id, ref.etag, self._now())
            )
            if confirmed:
                return CaptureStep(CaptureOutcome.KEYED, ref.file_id, media_id=media_id)
            return CaptureStep(CaptureOutcome.STALE, ref.file_id)
        if outcome is ProofOutcome.HEAD_MISMATCH:
            # Its own bytes are other ones than the content has: it gives no hit
            # for that content from now on and is read in full like a new copy.
            released = await run_locked(self._services, lambda: store.release_media(ref, self._now()))
            return None if released else CaptureStep(CaptureOutcome.STALE, ref.file_id)
        return await self._fail_proof(ref, outcome.value)

    async def _fail_proof(self, ref: FileRef, reason: str) -> CaptureStep:
        """A renewed proof failed: unreadable at once; the content stays, the next try proves again."""
        store = self._services.store
        now = self._now()
        if reason == nc.LOCKED:
            # No verdict on the right to read, so no attempt is used up; but no hit without a proof either.
            next_try, bump = now + LOCKED_RETRY_SECONDS, False
        else:
            next_try, bump = retry_at(now, ref.attempts, reason), True
        done = await run_locked(
            self._services, lambda: store.fail_proof(ref, reason, retry_at=next_try, bump=bump, now=now)
        )
        return CaptureStep(CaptureOutcome.UNREADABLE if done else CaptureOutcome.STALE, ref.file_id, reason)

    async def _download(self, ref: FileRef, reader: str) -> CaptureStep:
        """The full download through the own file id and the own reader, hashed on the way."""
        store = self._services.store
        try:
            result = await self._fetch(ref.file_id, reader, self._directory, ref.size, self._max_bytes)
        except Exception as exc:  # a broken fetch is a failed read, never a stuck claim
            LOGGER.exception("capture fetch raised", extra={"file_id": ref.file_id, "error_type": type(exc).__name__})
            return await self._judge(ref, nc.GATEWAY_FAILED)
        if result.error not in _NO_REQUEST:
            self._answered(ref, timed_out=result.error == nc.READ_TIMEOUT)
        checked = _validated(ref, result)
        if isinstance(checked, str):
            return await self._judge(ref, checked)
        sha, head = checked
        media_id = await run_locked(self._services, lambda: store.mark_keyed(ref, sha, head, self._now()))
        if media_id is None:
            return CaptureStep(CaptureOutcome.STALE, ref.file_id)
        return CaptureStep(CaptureOutcome.KEYED, ref.file_id, media_id=media_id)

    def _delete_excluded(self, ref: FileRef, now: int) -> bool:
        """Under the services lock: delete the reference, then the index lets go of a content that was forgotten."""
        store = self._services.store
        done = store.delete_ref(ref, now)
        try:
            if done and store.retired_media():
                self._services.index.retire_forgotten(store)
        except Exception as exc:  # the deletion stands; the mark in the outbox is worked off later
            LOGGER.exception("index retirement failed", extra={"error_type": type(exc).__name__})
        return done

    async def _judge(self, ref: FileRef, reason: str) -> CaptureStep:
        store = self._services.store
        now = self._now()
        if reason == nc.EXCLUDED:
            done = await run_locked(self._services, lambda: self._delete_excluded(ref, now))
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
