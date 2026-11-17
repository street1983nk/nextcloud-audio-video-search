"""Truth conditions T6 and T7 of 03-UI-SPEC (plan 03-15): a replaced file comes back into the work stock.

T6 says of a damaged file "If it is replaced, transcription starts again
automatically", T7 of a protected one "An unprotected copy is transcribed
automatically". Both sentences are only true if new content, under the same or
a new file id, goes the event way of phase 2 (claim with origin event, intake,
capture, key) back to a queued preview job. These tests run that way against
the real store, the real capture and the real preview worker; only the
gateway, the probe and the engine are fakes. The counter test shows that the
promise holds for new content only: the same bytes under a new etag join the
old content, whose verdict stays, so a damaged file is never tried in a loop.

If one of these tests fails, the sentence is not true: do not change the test,
ask the owner whether the product way is fixed or the sentence goes.

The tests read the store with their own SQL, never with the statements of the
implementation.
"""

import hashlib
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from audio_video_search_backend import nc
from audio_video_search_backend.api import Services
from audio_video_search_backend.engine import child
from audio_video_search_backend.engine.parakeet import Window
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.media.decode import DecodeResult
from audio_video_search_backend.media.probe import ProbeResult
from audio_video_search_backend.models import procure
from audio_video_search_backend.nc_queue import ClaimItem
from audio_video_search_backend.store.repo import Store
from audio_video_search_backend.worker.capture import Capture, CaptureOutcome
from audio_video_search_backend.worker.preview import Preview, PreviewOutcome

NOW = 1_800_000_000
DAMAGED = "damaged"
PROTECTED = "protected"


def _bytes(label: str, size: int = 4096) -> bytes:
    seed = hashlib.sha256(label.encode()).digest()
    return (seed * (size // len(seed) + 1))[:size]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Files:
    """What Nextcloud holds right now, by file id; the capture and the preview both read it."""

    def __init__(self) -> None:
        self.bytes: dict[int, bytes] = {}
        self.downloads: list[int] = []

    async def capture_fetch(self, file_id: int, _user: str, _dir: Path, _size: int, _cap: int) -> nc.FetchResult:
        self.downloads.append(file_id)
        data = self.bytes[file_id]
        return nc.FetchResult(sha256=_sha(data), size=len(data), error=None, head_sha256=_sha(data[: nc.HEAD_BYTES]))

    def _handler(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=self.bytes[int(request.url.path.rsplit("/", 1)[1])])

    @asynccontextmanager
    async def preview_fetch(
        self, file_id: int, user_id: str, directory: Path, size: int, cap: int
    ) -> AsyncIterator[tuple[nc.FetchResult, Path | None]]:
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(self._handler)) as client,
            nc.fetch_media_file(file_id, user_id, directory, size, cap, client=client) as kept,
        ):
            yield kept


class Probe:
    """ffprobe as a table: a reason per content, a playable minute otherwise."""

    def __init__(self) -> None:
        self.reasons: dict[str, str] = {}

    def __call__(self, path: Path) -> ProbeResult:
        reason = self.reasons.get(_sha(path.read_bytes()))
        if reason is not None:
            return ProbeResult(stream_index=None, duration_ms=None, reason=reason)
        return ProbeResult(stream_index=0, duration_ms=60_000, reason=None)


class SilentEngine:
    def start(self) -> str:
        return child.OK

    def ask(self, pcm: bytes, offset_ms: int, second_pass: bool) -> tuple[str, list[Window]]:
        return child.OK, []

    def stop(self) -> None:
        return None


def _decode(path: Path, stream_index: int, start_ms: int, dur_ms: int, *, expected_ms: int | None) -> DecodeResult:
    return DecodeResult(pcm=bytes(max(0, min(dur_ms, 60_000 - start_ms)) * 64), reason=None)


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


@pytest.fixture(autouse=True)
def plenty_of_space(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: 1024**4)


@pytest.fixture(autouse=True)
def models_are_ready() -> Iterator[None]:
    procure.mark_ready(True)
    yield
    procure.mark_ready(False)


@pytest.fixture
def files() -> Files:
    return Files()


@pytest.fixture
def probe() -> Probe:
    return Probe()


@pytest.fixture
def capture(services: Services, files: Files, tmp_path: Path) -> Capture:
    async def no_head(_file_id: int, _user: str) -> nc.HeadResult:
        raise AssertionError("no read proof expected: no prefilter key")

    directory = tmp_path / "tmp"
    directory.mkdir(exist_ok=True)
    return Capture(services, directory=directory, fetch=files.capture_fetch, clock=lambda: float(NOW), head=no_head)


@pytest.fixture
def preview(services: Services, files: Files, probe: Probe, tmp_path: Path) -> Preview:
    async def unread() -> dict[str, str]:
        raise ConnectionError("not needed")

    # prepare() of run_forever creates it in the container; run_once alone does not.
    directory = tmp_path / "tmp" / "preview"
    directory.mkdir(parents=True)
    return Preview(
        services,
        directory=directory,
        models_root=tmp_path / "models",
        fetch=files.preview_fetch,
        engine_factory=lambda _root: SilentEngine(),
        probe=probe,
        decode=_decode,
        clock=lambda: float(NOW),
        read_settings=unread,
    )


_QUEUE_IDS = iter(range(1, 10_000))


def _claim(store: Store, files: Files, file_id: int, data: bytes, *, etag: str, origin: str, mtime: int) -> None:
    """One content row as PHP's queue hands it out, through the contract of nc_queue (the intake way)."""
    files.bytes[file_id] = data
    item = ClaimItem(
        queueId=next(_QUEUE_IDS),
        kind="content",
        fileId=file_id,
        storageId=3,
        etag=etag,
        size=len(data),
        mtime=mtime,
        prefilterKey=None,
        readerUid="ana",
        origin=cast("Any", origin),
    )
    store.apply_intake([item.to_intake()])


def _jobs(db: Path) -> dict[int, tuple[Any, ...]]:
    with closing(sqlite3.connect(db)) as conn:
        rows = conn.execute("SELECT media_id, state, reason, origin FROM preview_job").fetchall()
    return {int(row[0]): tuple(row[1:]) for row in rows}


def _media_of(db: Path, file_id: int) -> int | None:
    with closing(sqlite3.connect(db)) as conn:
        row = conn.execute("SELECT media_id FROM file_ref WHERE file_id = ?", (file_id,)).fetchone()
    return None if row is None or row[0] is None else int(row[0])


async def _skipped_with(
    store: Store, files: Files, probe: Probe, capture: Capture, preview: Preview, db: Path, reason: str
) -> tuple[int, bytes]:
    """File 10 is captured and its preview job ends skipped with ``reason`` (the real worker)."""
    old = _bytes(f"broken-{reason}")
    probe.reasons[_sha(old)] = reason
    _claim(store, files, 10, old, etag="e1", origin="crawl", mtime=1_700_000_000)
    assert (await capture.run_once()).outcome == CaptureOutcome.KEYED
    media_id = _media_of(db, 10)
    assert media_id is not None
    step = await preview.run_once()
    assert (step.outcome, step.reason) == (PreviewOutcome.SKIPPED, reason)
    view = store.preview_view(10)
    assert view is not None
    assert (view.state, view.reason) == ("skipped", reason)
    return media_id, old


async def _replace_in_place(
    store: Store, files: Files, capture: Capture, preview: Preview, db: Path, old_media: int, reason: str
) -> None:
    new = _bytes(f"repaired-{reason}", 6000)
    _claim(store, files, 10, new, etag="e2", origin="event", mtime=1_700_000_500)
    assert (await capture.run_once()).outcome == CaptureOutcome.KEYED

    new_media = _media_of(db, 10)
    assert new_media is not None
    assert new_media != old_media
    assert _jobs(db)[new_media] == ("queued", None, "event")
    view = store.preview_view(10)
    assert view is not None
    assert view.reason != reason
    assert view.state == "queued"
    # And the worker does take it: the new content is transcribed, not skipped.
    step = await preview.run_once()
    assert step.media_id == new_media
    assert step.reason != reason


async def test_t6_a_damaged_file_replaced_with_new_content_is_queued_again(
    store: Store, files: Files, probe: Probe, capture: Capture, preview: Preview, db: Path
) -> None:
    old_media, _ = await _skipped_with(store, files, probe, capture, preview, db, DAMAGED)

    await _replace_in_place(store, files, capture, preview, db, old_media, DAMAGED)


async def test_t7_a_protected_file_replaced_with_new_content_is_queued_again(
    store: Store, files: Files, probe: Probe, capture: Capture, preview: Preview, db: Path
) -> None:
    old_media, _ = await _skipped_with(store, files, probe, capture, preview, db, PROTECTED)

    await _replace_in_place(store, files, capture, preview, db, old_media, PROTECTED)


async def test_t7_an_unprotected_copy_under_a_new_file_id_gets_its_own_queued_job(
    store: Store, files: Files, probe: Probe, capture: Capture, preview: Preview, db: Path
) -> None:
    old_media, _ = await _skipped_with(store, files, probe, capture, preview, db, PROTECTED)

    _claim(store, files, 11, _bytes("unprotected copy", 5000), etag="f1", origin="event", mtime=1_700_000_600)
    assert (await capture.run_once()).outcome == CaptureOutcome.KEYED

    copy_media = _media_of(db, 11)
    assert copy_media is not None
    assert copy_media != old_media
    jobs = _jobs(db)
    assert jobs[copy_media] == ("queued", None, "event")
    # The protected original keeps its own honest reason.
    assert jobs[old_media] == ("skipped", PROTECTED, "crawl")
    view = store.preview_view(11)
    assert view is not None
    assert (view.state, view.reason) == ("queued", None)


async def test_the_same_bytes_under_a_new_etag_keep_the_verdict_and_never_loop(
    store: Store, files: Files, probe: Probe, capture: Capture, preview: Preview, db: Path
) -> None:
    old_media, old = await _skipped_with(store, files, probe, capture, preview, db, DAMAGED)

    # Touched, not repaired: a new etag and mtime, the very same bytes.
    _claim(store, files, 10, old, etag="e2", origin="event", mtime=1_700_000_500)
    assert (await capture.run_once()).outcome == CaptureOutcome.KEYED

    assert _media_of(db, 10) == old_media
    assert _jobs(db) == {old_media: ("skipped", DAMAGED, "crawl")}
    view = store.preview_view(10)
    assert view is not None
    assert (view.state, view.reason) == ("skipped", DAMAGED)
    # Nothing to do: T6 promises a new start for new content only.
    assert (await preview.run_once()).outcome == PreviewOutcome.IDLE
    assert files.downloads == [10, 10]
