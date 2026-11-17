"""The intake: claim a band of the PHP work stock, write it, then acknowledge it.

The order is the whole point (RESEARCH Pattern 1, Findling T-03-503): the PHP
queue carries only the discovery, and a row is acknowledged as soon as its
reference is durable in state.db, seconds after the claim. Fetching, hashing
and later the transcription run in the stages of the container with their own
retries, so the lock of PHP stays a fixed 900 s however long a medium is.

- Commit first, ack second. A crash between the two delivers the band again
  after the lock ran out; ``Store.apply_intake`` writes it again to the same
  state.
- A failed commit acknowledges nothing and unlocks the whole band at once.
- Every kind is written in that one transaction (plan 02-15): content,
  metadata and restore as references, trash as a reference set aside, delete
  as a removed reference whose content is only marked, exclude and
  exclude_storage as removed references whose content is forgotten with its
  last one. No kind is unlocked any more.
- A forgotten content leaves a retirement mark in the outbox of the index,
  committed with the deletion. Its documents are deleted right after the
  commit, under the same lock and before the ack. If the index fails there,
  the rows are acknowledged all the same: SQLite is the truth, no search
  answer comes from a content without a current version, and the mark stays
  for the next round and for the reconcile at start.
- stats.ok false means PHP could not read its own table: nothing is written
  and the band is unlocked.

Logs carry counts only.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final

from audio_video_search_backend import companion
from audio_video_search_backend.api import Services, run_locked
from audio_video_search_backend.nc_queue import QueueClient
from audio_video_search_backend.store.repo import IntakeItem

LOGGER = logging.getLogger(__name__)

# Rows per claim; a full band with written rows is followed by the next claim at once.
BATCH: Final = 100
INTERVAL_SECONDS: Final = 30.0


@dataclass(frozen=True, slots=True)
class IntakeResult:
    """What one round did; ``claimed`` is the size of the band PHP handed out."""

    claimed: int
    applied: int
    acked: int
    unlocked: int
    malformed: int
    queue_ok: bool
    retired: int = 0


_NOTHING: Final = IntakeResult(claimed=0, applied=0, acked=0, unlocked=0, malformed=0, queue_ok=False)


@dataclass(slots=True)
class _QueueHealth:
    """Whether PHP could read its own work stock at the last answered claim; None before the first one."""

    ok: bool | None = None


_HEALTH: Final = _QueueHealth()


def last_queue_ok() -> bool | None:
    """stats.ok of the last answered claim; the walk of the reconcile stops on False (plan 02-20)."""
    return _HEALTH.ok


class Intake:
    """One claim, one transaction, one ack per round."""

    def __init__(self, services: Services, queue: QueueClient, *, batch: int = BATCH) -> None:
        self._services = services
        self._queue = queue
        self._batch = batch

    async def run_once(self) -> IntakeResult:
        outcome = await self._queue.claim(self._batch)
        if outcome.answer is None:
            if outcome.malformed:
                LOGGER.warning("claim band dropped", extra={"malformed": outcome.malformed})
            return IntakeResult(
                claimed=outcome.malformed, applied=0, acked=0, unlocked=0, malformed=outcome.malformed, queue_ok=False
            )
        answer = outcome.answer
        _HEALTH.ok = answer.stats.ok
        token = answer.claimToken
        ids = [entry.queueId for entry in answer.items]
        if not answer.stats.ok:
            unlocked = len(ids) if ids and await self._queue.unlock(token, ids) else 0
            LOGGER.warning("queue_unreadable", extra={"claimed": len(ids), "unlocked": unlocked})
            return IntakeResult(claimed=len(ids), applied=0, acked=0, unlocked=unlocked, malformed=0, queue_ok=False)
        if not ids:
            return IntakeResult(claimed=0, applied=0, acked=0, unlocked=0, malformed=0, queue_ok=True)

        items = [entry.to_intake() for entry in answer.items]
        try:
            applied, retired = await run_locked(self._services, lambda: self._write(items))
        except Exception as exc:
            unlocked = len(ids) if await self._queue.unlock(token, ids) else 0
            LOGGER.exception(
                "intake not written",
                extra={"claimed": len(ids), "unlocked": unlocked, "error_type": type(exc).__name__},
            )
            return IntakeResult(claimed=len(ids), applied=0, acked=0, unlocked=unlocked, malformed=0, queue_ok=True)

        acked = len(applied) if applied and await self._queue.ack(token, applied) else 0
        result = IntakeResult(
            claimed=len(ids), applied=len(applied), acked=acked, unlocked=0, malformed=0, queue_ok=True, retired=retired
        )
        LOGGER.info(
            "intake round",
            extra={"claimed": result.claimed, "applied": result.applied, "acked": acked, "retired": retired},
        )
        return result

    def _write(self, items: Sequence[IntakeItem]) -> tuple[list[int], int]:
        """Under the services lock: the transaction of the band, then the index lets go of forgotten contents."""
        store = self._services.store
        applied = store.apply_intake(items)
        retired = 0
        try:
            if store.retired_media():
                retired = self._services.index.retire_forgotten(store)
        except Exception as exc:  # the commit stands; the mark in the outbox is worked off later
            LOGGER.exception("index retirement failed", extra={"error_type": type(exc).__name__})
        return applied, retired

    def full_band_written(self, result: IntakeResult) -> bool:
        """Claim again at once: the band was full and at least one row of it was written."""
        return result.claimed >= self._batch and result.applied > 0

    async def run_forever(
        self,
        *,
        interval: float = INTERVAL_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rounds: int | None = None,
    ) -> None:
        """Claim while the PHP app is there; a full written band at once, otherwise every ``interval`` seconds.

        A band of which nothing was written (a failed commit, an unreadable
        queue) waits for the normal interval as well, so the same rows are not
        claimed in a tight loop. ``rounds`` ends the loop for tests.
        """
        done = 0
        while rounds is None or done < rounds:
            done += 1
            result = _NOTHING
            # AppAPI answers 412 while it has not enabled this container, and
            # the companion check reads that as unknown: no claim before ok.
            if companion.current().state == companion.OK:
                try:
                    result = await self.run_once()
                except Exception as exc:  # the loop must outlive any single round
                    LOGGER.exception("intake round failed", extra={"error_type": type(exc).__name__})
            if not self.full_band_written(result):
                await sleep(interval)


async def run_forever(services: Services) -> None:
    """The background task of main.py: one queue client for the life of the process."""
    queue = QueueClient()
    try:
        await Intake(services, queue).run_forever()
    finally:
        await queue.aclose()
