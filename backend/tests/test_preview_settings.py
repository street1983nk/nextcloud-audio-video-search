"""The duration limit of the admin settings in the preview worker (plan 03-15, D-03-08, D-03-09).

The worker reads the setting at its start and every SETTINGS_REFRESH_SECONDS,
stores it, and only when the limit went up brings the jobs that were skipped as
too long back into the work stock (Store.requeue_too_long). A lower limit
touches no job, a failed read keeps the stored limit. The reader runs outside
the services lock; only the store calls take it.

The tests read the store with their own SQL, never with the statements of the
implementation.
"""

import hashlib
import logging
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Any, cast

import pytest

from audio_video_search_backend import nc, settings
from audio_video_search_backend.api import Services
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.store.repo import IntakeItem, Store
from audio_video_search_backend.worker import preview as preview_module
from audio_video_search_backend.worker.preview import (
    SETTINGS_REFRESH_SECONDS,
    Preview,
    PreviewOutcome,
    PreviewStep,
    read_admin_settings,
)

NOW = 1_800_000_000
HOUR = 3_600_000
HEAD = "9" * 64
# Captured at import, before the conftest fixture replaces the module attribute.
REAL_READER = read_admin_settings


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "state.db"


@pytest.fixture
def store(db: Path) -> Iterator[Store]:
    opened = Store.open(db)
    yield opened
    opened.close()


@pytest.fixture
def services(store: Store) -> Services:
    return Services(store=store, index=cast("SearchIndex", None))


class Clock:
    def __init__(self) -> None:
        self.now = float(NOW)

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def worker(services: Services, tmp_path: Path, clock: Clock) -> Preview:
    return Preview(services, directory=tmp_path / "tmp" / "preview", models_root=tmp_path / "models", clock=clock)


def _keyed(store: Store, file_id: int) -> int:
    """A file the capture has keyed; its preview job is seeded with it (queued)."""
    sha = hashlib.sha256(f"file-{file_id}".encode()).hexdigest()
    store.apply_intake(
        [
            IntakeItem(
                queue_id=file_id,
                kind="content",
                file_id=file_id,
                storage_id=3,
                etag="e1",
                size=4096,
                mtime=1_700_000_000 + file_id,
                prefilter_key=None,
                reader_uid="ana",
                origin="crawl",
            )
        ]
    )
    claimed = store.next_capture(NOW)
    assert claimed is not None
    media_id = store.mark_keyed(claimed, sha, HEAD, NOW)
    assert media_id is not None
    return media_id


def _too_long(store: Store, file_id: int, duration_ms: int | None) -> int:
    """A keyed file whose job the worker skipped as too long, through the store's own way."""
    media_id = _keyed(store, file_id)
    job = store.next_preview(NOW)
    assert job is not None
    assert job.media_id == media_id
    assert store.skip_preview(job, "too_long", duration_ms)
    return media_id


def _job(db: Path, media_id: int) -> tuple[Any, ...]:
    with closing(sqlite3.connect(db)) as conn:
        row = conn.execute("SELECT state, reason FROM preview_job WHERE media_id = ?", (media_id,)).fetchone()
    assert row is not None
    return tuple(row)


def _limit(db: Path) -> str | None:
    with closing(sqlite3.connect(db)) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = 'max_duration_hours'").fetchone()
    return None if row is None else str(row[0])


def _reader(value: str, calls: list[str] | None = None, services: Services | None = None) -> Any:
    async def read() -> dict[str, str]:
        if calls is not None:
            calls.append("read")
        if services is not None:
            # The reader talks to Nextcloud; it must never hold the store lock meanwhile.
            assert not services.lock.locked()
        return {settings.PROCESSING_ENABLED: "1", settings.MAX_DURATION_HOURS: value}

    return read


class _Spy:
    def __init__(self, store: Store) -> None:
        self.calls: list[int] = []
        self._real = store.requeue_too_long

    def __call__(self, max_ms: int) -> int:
        self.calls.append(max_ms)
        return self._real(max_ms)


@pytest.fixture
def requeue(store: Store, monkeypatch: pytest.MonkeyPatch) -> _Spy:
    spy = _Spy(store)
    monkeypatch.setattr(store, "requeue_too_long", spy)
    return spy


# -- raising, lowering, failing ------------------------------------------------------


async def test_raising_the_limit_brings_back_the_too_long_jobs_that_fit(
    worker: Preview, store: Store, services: Services, db: Path, requeue: _Spy
) -> None:
    store.set_max_duration_hours(12)
    fits = _too_long(store, 11, 20 * HOUR)
    longer = _too_long(store, 12, 30 * HOUR)

    await worker.sync_limits(_reader("24", services=services))

    assert requeue.calls == [24 * HOUR]
    assert _job(db, fits) == ("queued", None)
    assert _job(db, longer) == ("skipped", "too_long")
    assert _limit(db) == "24"


async def test_lowering_the_limit_brings_nothing_back_and_leaves_a_running_job(
    worker: Preview, store: Store, db: Path, requeue: _Spy
) -> None:
    store.set_max_duration_hours(24)
    skipped = _too_long(store, 11, 30 * HOUR)
    running = _keyed(store, 12)
    job = store.next_preview(NOW)
    assert job is not None
    assert job.media_id == running

    await worker.sync_limits(_reader("12"))

    assert requeue.calls == []
    assert _job(db, skipped) == ("skipped", "too_long")
    assert _job(db, running) == ("running", None)
    assert _limit(db) == "12"


async def test_the_same_limit_brings_nothing_back(worker: Preview, store: Store, db: Path, requeue: _Spy) -> None:
    store.set_max_duration_hours(12)
    unknown = _too_long(store, 11, None)

    await worker.sync_limits(_reader("12"))

    assert requeue.calls == []
    # A file of unknown length that ran past the limit would otherwise come back every five minutes.
    assert _job(db, unknown) == ("skipped", "too_long")


async def test_a_failed_read_keeps_the_stored_limit(
    worker: Preview, store: Store, db: Path, requeue: _Spy, caplog: pytest.LogCaptureFixture
) -> None:
    store.set_max_duration_hours(20)
    skipped = _too_long(store, 11, 22 * HOUR)

    async def broken() -> dict[str, str]:
        raise OSError("nextcloud.secret.example unreachable")

    with caplog.at_level(logging.WARNING):
        await worker.sync_limits(broken)

    assert requeue.calls == []
    assert _limit(db) == "20"
    assert _job(db, skipped) == ("skipped", "too_long")
    warned = [r for r in caplog.records if r.name == preview_module.__name__ and r.levelno == logging.WARNING]
    assert warned
    assert warned[0].__dict__["error_type"] == "OSError"
    assert all("secret" not in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(("saved", "hours"), [("abc", 12), ("48", 24), ("", 12)])
async def test_the_saved_text_goes_through_the_settings_reader(
    worker: Preview, store: Store, db: Path, saved: str, hours: int
) -> None:
    store.set_max_duration_hours(6)

    await worker.sync_limits(_reader(saved))

    assert _limit(db) == str(hours)


async def test_a_job_skipped_without_a_known_length_comes_back_when_raised(
    worker: Preview, store: Store, db: Path
) -> None:
    store.set_max_duration_hours(12)
    unknown = _too_long(store, 11, None)

    await worker.sync_limits(_reader("13"))

    assert _job(db, unknown) == ("queued", None)


# -- in the loop -----------------------------------------------------------------------


async def test_the_loop_reads_the_settings_first_and_then_every_refresh(
    services: Services, tmp_path: Path, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    async def step() -> PreviewStep:
        events.append("step")
        return PreviewStep(PreviewOutcome.IDLE)

    async def sleep(_seconds: float) -> None:
        clock.now += SETTINGS_REFRESH_SECONDS / 2

    monkeypatch.setattr(preview_module.procure, "models_ready", lambda: True)
    monkeypatch.setattr(
        preview_module.companion,
        "current",
        lambda: preview_module.companion.CompanionState(preview_module.companion.OK, "0.2.0", 0.0),
    )
    worker = Preview(
        services,
        directory=tmp_path / "tmp" / "preview",
        models_root=tmp_path / "models",
        clock=clock,
        read_settings=_reader("12", events),
    )
    monkeypatch.setattr(worker, "run_once", step)

    await worker.run_forever(sleep=sleep, rounds=5)

    # Start, then after 300 s (two pauses of 150 s), then again after the next 300 s.
    assert events == ["read", "step", "step", "read", "step", "step", "read", "step"]
    assert SETTINGS_REFRESH_SECONDS == 300


async def test_the_preview_task_uses_the_nextcloud_reader_by_default(
    services: Services, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    client = object()

    @asynccontextmanager
    async def fake_app() -> AsyncIterator[object]:
        opened.append("open")
        yield client
        opened.append("closed")

    async def fake_read(nc_client: object) -> dict[str, str]:
        assert nc_client is client
        return {settings.MAX_DURATION_HOURS: "7"}

    monkeypatch.setattr(nc, "nc_app", fake_app)
    monkeypatch.setattr(settings, "read", fake_read)

    assert await REAL_READER() == {settings.MAX_DURATION_HOURS: "7"}
    assert opened == ["open", "closed"]

    # Without an own reader the worker takes the module's reader at construction.
    monkeypatch.setattr(preview_module, "read_admin_settings", REAL_READER)
    worker = Preview(services, directory=tmp_path / "p", models_root=tmp_path / "m")
    await worker.sync_limits(worker._read_settings)  # pyright: ignore[reportPrivateUsage]
    assert services.store.max_duration_hours() == 7
