"""The periodic reconcile of the container (plan 02-20, DISC-04, after Findling 1.6.3).

Events are an accelerator, never a guarantee: a mass import over occ, a folder
moved into the trash (no event for the files in it), a user deleted, a storage
an admin switched off. This round compares what state.db holds with what the
PHP app lists and turns every difference into work, in three steps per tick:

1. **The sweep**, in front of everything else and under a stamp of its own
   (``storage_sweep_at``), also while the walk is held back (Findling 1.6.3,
   issue #25). Only a mount list that is ok and not empty counts: an empty or
   disturbed list looks exactly like an instance whose storages all went away
   (T-02-74). A storage the list no longer carries is classified by PHP: gone
   loses its references at once (their contents are only marked, D-02-13),
   deselected is vanished (no hit, not counted) and goes after
   VANISHED_GRACE_SECONDS. A storage back in the list comes back without a
   download; on SMB and SFTP it owes a read proof first (D-02-12). Besides its
   cadence the sweep runs at once when a storage left the list or came back,
   which a local query sees every tick.
2. **The planning of the renewed read proof** (D-02-12), every tick, since it
   is one query on the index: every active keyed reference on a storage with a
   share key (SMB, SFTP) whose proof is older than REPROOF_AGE_SECONDS is due
   again; ``reprove`` makes it due now. The proof itself is made by the
   capture (worker/capture.py, plan 02-13).
3. **The walk**, under the stamp ``walk_at``, only over mounts whose first
   crawl is finished. The container never writes a new or changed file into
   state.db itself: it hands it back over POST reconcile/requeue, and PHP sends
   it through the one pre-check (QueueService::admissible, D-02-05) into the
   work stock, from where only the intake writes (T-02-72, gate in
   tests/test_reconcile_walk.py).

The cadence is ours: at most one sweep and one walk per MIN_INTERVAL_HOURS,
preferably in PREFERRED_HOUR, at twice the interval whatever the hour is. The
length of the work stock is no gate. POST /reconcile/run (occ
audio_video_search:reconcile) runs all three at once.

Logs carry counters and storage ids, never a file id, a path or a name.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from audio_video_search_backend import companion
from audio_video_search_backend.api import Services, run_locked
from audio_video_search_backend.nc_files import Classification, FileClient, MountEntry, MountList, RequeueAnswer, Slice
from audio_video_search_backend.worker import intake

LOGGER = logging.getLogger(__name__)

TICK_SECONDS: Final = 300.0
MIN_INTERVAL_HOURS: Final = 24
# The hour of the container clock a due sweep or walk prefers.
PREFERRED_HOUR: Final = 3
SWEEP_STAMP: Final = "storage_sweep_at"
WALK_STAMP: Final = "walk_at"
# How long a deselected storage keeps its references (Findling D-36-05). Fixed
# on purpose: a setting of zero would turn every short outage into a removal.
VANISHED_GRACE_SECONDS: Final = 30 * 86_400
# D-02-12: the read proof of a copy on SMB or SFTP is renewed at least this often.
REPROOF_AGE_SECONDS: Final = 7 * 86_400
SLICE_LIMIT: Final = 1000
# At most this many storage ids per list in a log line; the counters stay exact.
LOG_STORAGES: Final = 20
# The extra fields a log line of this module may carry.
LOG_FIELDS: Final = frozenset(
    {
        "swept",
        "vanished",
        "orphaned",
        "walked_mounts",
        "requeued",
        "rejected",
        "reproof_due",
        "skipped_reason",
        "set_aside",
        "back",
        "absent",
        "gone_storages",
        "deselected_storages",
        "expired_storages",
        "error_type",
    }
)

MOUNTS_UNAVAILABLE: Final = "mounts_unavailable"
MOUNTS_EMPTY: Final = "mounts_empty"
CLASSIFY_UNAVAILABLE: Final = "classify_unavailable"
QUEUE_UNAVAILABLE: Final = "queue_unavailable"
CRAWL_UNFINISHED: Final = "crawl_unfinished"
SLICE_UNAVAILABLE: Final = "slice_unavailable"
REQUEUE_UNAVAILABLE: Final = "requeue_unavailable"


class Files(Protocol):
    """The reconcile routes of the PHP app (nc_files.FileClient, a fake in tests)."""

    async def mounts(self) -> MountList | None: ...

    async def slice(self, storage_id: int, root_id: int, after: int, limit: int) -> Slice | None: ...

    async def classify(self, storage_ids: Sequence[int]) -> Classification | None: ...

    async def requeue(self, file_ids: Sequence[int]) -> RequeueAnswer | None: ...


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    """What one round did; the answer of POST /reconcile/run (ExAppService::RECONCILE_KEYS)."""

    swept: int
    vanished: int
    orphaned: int
    walked_mounts: int
    requeued: int
    rejected: int
    reproof_due: int
    skipped_reason: str | None

    def as_wire(self) -> dict[str, int | str | None]:
        return {
            "swept": self.swept,
            "vanished": self.vanished,
            "orphaned": self.orphaned,
            "walkedMounts": self.walked_mounts,
            "requeued": self.requeued,
            "rejected": self.rejected,
            "reproofDue": self.reproof_due,
            "skippedReason": self.skipped_reason,
        }


@dataclass(slots=True)
class _Tally:
    swept: int = 0
    vanished: int = 0
    orphaned: int = 0
    walked_mounts: int = 0
    requeued: int = 0
    rejected: int = 0
    reproof_due: int = 0
    set_aside: int = 0
    skipped_reason: str | None = None

    def skip(self, reason: str) -> None:
        if self.skipped_reason is None:
            self.skipped_reason = reason

    def result(self) -> ReconcileResult:
        return ReconcileResult(
            swept=self.swept,
            vanished=self.vanished,
            orphaned=self.orphaned,
            walked_mounts=self.walked_mounts,
            requeued=self.requeued,
            rejected=self.rejected,
            reproof_due=self.reproof_due,
            skipped_reason=self.skipped_reason,
        )


def _local_hour() -> int:
    return time.localtime().tm_hour


def _first(storage_ids: Sequence[int]) -> list[int]:
    return list(storage_ids[:LOG_STORAGES])


class Reconciler:
    """Sweep, proof planning and walk; one round at a time, also against POST /reconcile/run."""

    def __init__(
        self,
        services: Services,
        files: Files,
        *,
        clock: Callable[[], float] = time.time,
        hour_of: Callable[[], int] = _local_hour,
        queue_ok: Callable[[], bool | None] = intake.last_queue_ok,
        slice_limit: int = SLICE_LIMIT,
    ) -> None:
        self._services = services
        self._files = files
        self._clock = clock
        self._hour_of = hour_of
        self._queue_ok = queue_ok
        self._slice_limit = slice_limit
        self._lock = asyncio.Lock()

    async def run_once(self, *, reprove: bool = False, force: bool = False) -> ReconcileResult:
        """One round; ``force`` runs sweep and walk whatever their stamps say (POST /reconcile/run)."""
        async with self._lock:
            tally = _Tally()
            await self._round(tally, reprove=reprove, force=force)
        result = tally.result()
        LOGGER.info(
            "reconcile round",
            extra={
                "swept": result.swept,
                "vanished": result.vanished,
                "orphaned": result.orphaned,
                "walked_mounts": result.walked_mounts,
                "requeued": result.requeued,
                "rejected": result.rejected,
                "reproof_due": result.reproof_due,
                "set_aside": tally.set_aside,
                "skipped_reason": result.skipped_reason,
            },
        )
        return result

    async def _round(self, tally: _Tally, *, reprove: bool, force: bool) -> None:
        now = int(self._clock())
        listing = await self._files.mounts()
        if listing is None or not listing.ok:
            tally.skip(MOUNTS_UNAVAILABLE)
            return
        if not listing.mounts:
            tally.skip(MOUNTS_EMPTY)
            return
        mounts = listing.mounts
        listed = {entry.storageId for entry in mounts}
        groupable = sorted({entry.storageId for entry in mounts if entry.groupable})
        store = self._services.store

        if force or await self._sweep_due(listed):
            reason = await self._sweep(listed, groupable, now, tally)
            if reason is None:
                await run_locked(self._services, lambda: store.set_meta(SWEEP_STAMP, str(now)))
            else:
                tally.skip(reason)

        older_than = now + 1 if reprove else now - REPROOF_AGE_SECONDS
        tally.reproof_due = await run_locked(self._services, lambda: store.mark_reproof_due(groupable, older_than, now))

        if force or await self._stamp_due(WALK_STAMP):
            reason = await self._walk(mounts, now, tally)
            if reason is None:
                await run_locked(self._services, lambda: store.set_meta(WALK_STAMP, str(now)))
            else:
                tally.skip(reason)

    # -- the sweep ---------------------------------------------------------------

    async def _sweep_due(self, listed: set[int]) -> bool:
        """Due by its stamp, or because a storage left the list or came back since the last sweep."""
        if await self._stamp_due(SWEEP_STAMP):
            return True
        store = self._services.store

        def changed() -> bool:
            unmarked = store.reconcile_storages(unmarked=True)
            marked = store.vanished_storages(before=2**62)
            return any(storage_id > 0 for storage_id in unmarked - listed) or bool(marked & listed)

        return await run_locked(self._services, changed)

    async def _sweep(self, listed: set[int], groupable: Sequence[int], now: int, tally: _Tally) -> str | None:
        """Back, gone, deselected, expired; None when every step got through."""
        store = self._services.store
        back = await run_locked(self._services, lambda: store.mark_present(sorted(listed), groupable, now))
        known = await run_locked(self._services, store.reconcile_storages)
        absent = sorted(storage_id for storage_id in known - listed if storage_id > 0)
        gone: list[int] = []
        deselected: list[int] = []
        if absent:
            answer = await self._files.classify(absent)
            if answer is None:
                return CLASSIFY_UNAVAILABLE
            asked = set(absent)
            gone = sorted(asked & set(answer.gone))
            deselected = sorted((asked & set(answer.deselected)) - set(gone))

        def apply() -> list[int]:
            removed, orphaned = store.remove_storages(gone, "gone", now)
            vanished, marked = store.mark_vanished(deselected, now)
            expired = sorted(store.vanished_storages(before=now - VANISHED_GRACE_SECONDS) - listed)
            expired_removed, expired_orphaned = store.remove_storages(expired, "vanished_expired", now)
            tally.swept += removed + expired_removed
            tally.vanished += vanished
            tally.orphaned += orphaned + marked + expired_orphaned
            return expired

        expired = await run_locked(self._services, apply)
        LOGGER.info(
            "storage sweep",
            extra={
                "back": back,
                "absent": len(absent),
                "gone_storages": _first(gone),
                "deselected_storages": _first(deselected),
                "expired_storages": _first(expired),
            },
        )
        return None

    # -- the walk ----------------------------------------------------------------

    async def _walk(self, mounts: Sequence[MountEntry], now: int, tally: _Tally) -> str | None:
        """Walk the mounts whose first crawl is finished; None when the walk got through."""
        del now
        if not any(entry.crawlFinished and entry.capturable for entry in mounts):
            return CRAWL_UNFINISHED
        return None

    # -- cadence -----------------------------------------------------------------

    async def _stamp_due(self, key: str) -> bool:
        raw = await run_locked(self._services, lambda: self._services.store.meta_value(key))
        last = int(raw) if raw is not None and raw.isdigit() else None
        return self._cadence_due(last)

    def _cadence_due(self, last_at: int | None) -> bool:
        """Never run: due. Then the minimum interval, the preferred hour, and twice the interval as escape."""
        if last_at is None:
            return True
        elapsed = self._clock() - last_at
        interval = MIN_INTERVAL_HOURS * 3600.0
        if elapsed < interval:
            return False
        if self._hour_of() == PREFERRED_HOUR:
            return True
        return elapsed >= 2 * interval

    # -- the loop ----------------------------------------------------------------

    async def run_forever(
        self,
        *,
        interval: float = TICK_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rounds: int | None = None,
    ) -> None:
        """A round every ``interval`` seconds while the PHP app is there; ``rounds`` ends the loop for tests."""
        done = 0
        while rounds is None or done < rounds:
            done += 1
            if companion.current().state == companion.OK:
                try:
                    await self.run_once()
                except Exception as exc:  # the loop must outlive any single round
                    LOGGER.exception("reconcile round failed", extra={"error_type": type(exc).__name__})
            await sleep(interval)


async def run_forever(reconciler: Reconciler) -> None:
    """The background task of main.py."""
    await reconciler.run_forever()


def new_reconciler(services: Services) -> tuple[Reconciler, FileClient]:
    """The reconcile of the running container with its own client for the PHP routes."""
    files = FileClient()
    return Reconciler(services, files), files
