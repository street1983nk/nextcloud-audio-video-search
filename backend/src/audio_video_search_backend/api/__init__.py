"""The container routes of the contract with the PHP app (plan 01-03).

Every route sits behind ``AppAPIAuthMiddleware`` (main.py): a request without a
valid AppAPI signature is answered with 401 before it reaches a handler. The
routes block in appinfo/info.xml limits unsigned direct access on top.

Store and index are opened once in the lifespan and live in ``app.state``. The
SQLite connection is shared between threads, and a transaction on it must not
interleave with another one, so every piece of store and index work runs in a
worker thread under one lock (:func:`run_locked`).
"""

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

from fastapi import APIRouter, HTTPException, Request

from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.store.repo import Store

# The upper end of a time stamp: one day of audio, in whole milliseconds.
MAX_AT_MS: Final = 86_400_000
MAX_UID_LENGTH: Final = 64


@dataclass
class Services:
    """What the routes work on; one per running application."""

    store: Store
    index: SearchIndex
    lock: threading.Lock = field(default_factory=threading.Lock)

    def close(self) -> None:
        with self.lock:
            self.index.close()
            self.store.close()


def services(request: Request) -> Services:
    """The services of the running application; 503 while the lifespan has not opened them."""
    opened = getattr(request.app.state, "services", None)
    if not isinstance(opened, Services):
        raise HTTPException(status_code=503, detail="not ready")
    return opened


async def run_locked[T](opened: Services, work: Callable[[], T]) -> T:
    """Run blocking store and index work in a thread, one piece at a time."""

    def locked() -> T:
        with opened.lock:
            return work()

    return await asyncio.to_thread(locked)


def build_router() -> APIRouter:
    """All container routes in one router for main.py."""
    from audio_video_search_backend.api import coverage, excerpt, reconcile, sample, search, status, workstock

    router = APIRouter()
    router.include_router(search.router)
    router.include_router(excerpt.router)
    router.include_router(sample.router)
    router.include_router(status.router)
    router.include_router(workstock.router)
    router.include_router(coverage.router)
    router.include_router(reconcile.router)
    return router
