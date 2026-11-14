"""The preview worker (plan 03-13): chunks, resume, yield at the chunk boundary, reasons and the file verdict.

The worker joins the media intake, the engine and the store (TRANS-01, TRANS-07,
TRANS-08, MEDIA-01 to 04; D-03-05 to D-03-08, D-03-16, D-03-17, D-03-20). The
tests run it against a real state.db and the real nc.fetch_media_file behind an
httpx MockTransport; probe, decode and the engine are fakes driven by tables in
media time, so no model is needed. One test runs real ffprobe and ffmpeg on a
generated WAV (tests/media_fixtures.py).

The fake engine answers like the VAD would on the decoded range: every window
of its table that overlaps ``[offset_ms, offset_ms + length)`` comes back cut to
that range, with the words that start inside it. A window that the previous
chunk took therefore reappears as a fragment inside the 1 s of context, and the
worker has to drop it.

The tests read the store with their own SQL, never with the statements of the
implementation.
"""

import asyncio
import hashlib
import logging
import sqlite3
import wave
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, closing
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from audio_video_search_backend.worker.preview import (
    IDLE_SECONDS,
    MAX_ENGINE_ATTEMPTS,
    NO_ROOM_RETRY_SECONDS,
    PROFILE,
    Preview,
    PreviewOutcome,
)

from audio_video_search_backend import companion, nc
from audio_video_search_backend.api import Services
from audio_video_search_backend.engine import child
from audio_video_search_backend.engine.catch import DROP_CONFIDENCE, DROP_LANGUAGE, KEEP
from audio_video_search_backend.engine.constants import CHUNK_CONTEXT_MS, CHUNK_LOOKAHEAD_MS, CHUNK_MS
from audio_video_search_backend.engine.parakeet import EngineWord, Window
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.media import probe as probe_module
from audio_video_search_backend.media.decode import DecodeResult, decode_chunk
from audio_video_search_backend.media.probe import ProbeResult
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.models import catalog, procure
from audio_video_search_backend.store.repo import ChunkCounters, IntakeItem, Store
from audio_video_search_backend.worker import preview as preview_module
from audio_video_search_backend.worker.capture import DISK_FULL_RETRY_SECONDS

NOW = 1_800_000_000
HEAD = "9" * 64
MIN = 60_000
SPOKEN_WORD = "geheimwort"
MARK = "HIDDEN"


# -- fakes ---------------------------------------------------------------------------


def ew(text: str, at: int, length: int = 300, conf: float = 0.9) -> EngineWord:
    return EngineWord(text=text, start_ms=at, end_ms=at + length, conf=conf)


def win(
    start: int,
    end: int,
    words: tuple[EngineWord, ...] = (),
    *,
    verdict: str = KEEP,
    n_words: int | None = None,
    speech: int | None = None,
) -> Window:
    return Window(
        start_ms=start,
        end_ms=end,
        speech_ms=end - start if speech is None else speech,
        n_words=len(words) if n_words is None else n_words,
        verdict=verdict,
        words=words if verdict == KEEP else (),
    )


def spread(start: int, end: int, label: str, step: int = 4000) -> Window:
    """A kept window with one word every ``step`` ms."""
    return win(start, end, tuple(ew(f"{label}{at}", at) for at in range(start, end - 300, step)))


@dataclass
class Call:
    offset_ms: int
    length_ms: int
    second_pass: bool


@dataclass
class FakeEngine:
    """The engine behind the child boundary, answering from a table in media time."""

    first: list[Window] = field(default_factory=list)
    second: list[Window] = field(default_factory=list)
    start_code: str = child.OK
    codes: dict[int, str] = field(default_factory=dict)
    raise_at: int | None = None
    relative: bool = False
    hook: Callable[[int], None] | None = None
    calls: list[Call] = field(default_factory=list)
    starts: int = 0
    stops: int = 0

    def start(self) -> str:
        self.starts += 1
        return self.start_code

    def stop(self) -> None:
        self.stops += 1

    def ask(
        self, pcm: bytes, offset_ms: int, second_pass: bool, *, deadline: float = 900.0
    ) -> tuple[str, list[Window]]:
        index = len(self.calls)
        length = len(pcm) // 4 * 1000 // 16000
        self.calls.append(Call(offset_ms, length, second_pass))
        if self.hook is not None:
            self.hook(index)
        if self.raise_at == index:
            raise RuntimeError("engine broke")
        if index in self.codes:
            return self.codes[index], []
        table = self.second if second_pass else self.first
        if self.relative:
            # Only the first two chunks answer, so the file ends after a few empty chunks.
            table = [_shift(window, offset_ms) for window in table] if index <= 1 else []
        return child.OK, [cut for window in table if (cut := _cut(window, offset_ms, offset_ms + length))]


def _shift(window: Window, by: int) -> Window:
    words = tuple(EngineWord(w.text, w.start_ms + by, w.end_ms + by, w.conf) for w in window.words)
    return win(window.start_ms + by, window.end_ms + by, words, verdict=window.verdict, n_words=window.n_words)


def _cut(window: Window, low: int, high: int) -> Window | None:
    start, end = max(window.start_ms, low), min(window.end_ms, high)
    if start >= end:
        return None
    words = tuple(w for w in window.words if start <= w.start_ms < end)
    n_words = len(words) if window.verdict == KEEP else window.n_words
    return win(start, end, words, verdict=window.verdict, n_words=n_words, speech=min(window.speech_ms, end - start))


@dataclass
class Media:
    """The fake probe and decode: what each content (by its sha256) is."""

    durations: dict[str, int | None] = field(default_factory=dict)
    probe_reasons: dict[str, str] = field(default_factory=dict)
    decode_reasons: dict[str, str] = field(default_factory=dict)
    decodes: list[tuple[int, int, int | None]] = field(default_factory=list)
    probes: int = 0

    def probe(self, path: Path) -> ProbeResult:
        self.probes += 1
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha in self.probe_reasons:
            return ProbeResult(stream_index=None, duration_ms=None, reason=self.probe_reasons[sha])
        return ProbeResult(stream_index=0, duration_ms=self.durations[sha], reason=None)

    def decode(
        self, path: Path, stream_index: int, start_ms: int, dur_ms: int, *, expected_ms: int | None
    ) -> DecodeResult:
        assert stream_index == 0
        self.decodes.append((start_ms, dur_ms, expected_ms))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha in self.decode_reasons:
            return DecodeResult(pcm=b"", reason=self.decode_reasons[sha])
        duration = self.durations[sha]
        if duration is None:
            duration = 0
        length = max(0, min(dur_ms, duration - start_ms))
        return DecodeResult(pcm=bytes(length * 16 * 4), reason=None)


class Gateway:
    """The content gateway behind a MockTransport: bytes by file id, every request counted."""

    def __init__(self) -> None:
        self.files: dict[int, bytes] = {}
        self.requests = 0

    def _handler(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        file_id = int(request.url.path.rsplit("/", 1)[1])
        return httpx.Response(200, content=self.files[file_id])

    @asynccontextmanager
    async def fetch(
        self, file_id: int, user_id: str, directory: Path, size: int, cap: int
    ) -> AsyncIterator[tuple[nc.FetchResult, Path | None]]:
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(self._handler)) as client,
            nc.fetch_media_file(file_id, user_id, directory, size, cap, client=client) as kept,
        ):
            yield kept


# -- fixtures ------------------------------------------------------------------------


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


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    directory = tmp_path / MARK / "tmp"
    directory.mkdir(parents=True)
    return directory


@pytest.fixture(autouse=True)
def plenty_of_space(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: 1024**4)


@pytest.fixture(autouse=True)
def models_are_ready() -> Iterator[None]:
    procure.mark_ready(True)
    yield
    procure.mark_ready(False)


@pytest.fixture
def companion_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(companion, "current", lambda: companion.CompanionState(companion.OK, "0.2.0", 0.0))


@pytest.fixture
def gateway() -> Gateway:
    return Gateway()


@pytest.fixture
def media() -> Media:
    return Media()


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


class Clock:
    def __init__(self) -> None:
        self.now = float(NOW)

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


def _worker(
    services: Services, tmp_dir: Path, gateway: Gateway, media: Media, engine: FakeEngine, clock: Clock
) -> Preview:
    return Preview(
        services,
        directory=tmp_dir,
        models_root=tmp_dir.parent / "models",
        fetch=gateway.fetch,
        engine_factory=lambda _root: engine,
        probe=media.probe,
        decode=media.decode,
        clock=clock,
    )


@pytest.fixture
def worker(
    services: Services, tmp_dir: Path, gateway: Gateway, media: Media, engine: FakeEngine, clock: Clock
) -> Preview:
    return _worker(services, tmp_dir, gateway, media, engine, clock)


def _content(label: str, size: int = 4096) -> bytes:
    seed = hashlib.sha256(label.encode()).digest()
    return (seed * (size // len(seed) + 1))[:size]


def _add(
    store: Store,
    gateway: Gateway,
    media: Media,
    file_id: int,
    *,
    duration_ms: int | None,
    origin: str = "crawl",
    mtime: int = 1_700_000_000,
    data: bytes | None = None,
) -> int:
    """A file the capture has keyed: active, keyed, with a reader; its preview job is seeded with it."""
    body = _content(f"file-{file_id}") if data is None else data
    sha = hashlib.sha256(body).hexdigest()
    gateway.files[file_id] = body
    media.durations[sha] = duration_ms
    store.apply_intake(
        [
            IntakeItem(
                queue_id=file_id,
                kind="content",
                file_id=file_id,
                storage_id=3,
                etag="e1",
                size=len(body),
                mtime=mtime,
                prefilter_key=None,
                reader_uid="ana",
                origin=origin,
            )
        ]
    )
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert claimed.file_id == file_id
    media_id = store.mark_keyed(claimed, sha, HEAD, NOW)
    assert media_id is not None
    return media_id


def _sha_of(gateway: Gateway, file_id: int) -> str:
    return hashlib.sha256(gateway.files[file_id]).hexdigest()


def _sql(db: Path, statement: str, values: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    with closing(sqlite3.connect(db)) as conn, conn:
        return conn.execute(statement, values).fetchall()


def _job(db: Path, media_id: int) -> dict[str, Any]:
    with closing(sqlite3.connect(db)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM preview_job WHERE media_id = ?", (media_id,)).fetchone()
    assert row is not None
    return dict(row)


def _words(db: Path, media_id: int) -> list[tuple[int, int, str]]:
    return [
        (int(s), int(e), str(t))
        for s, e, t in _sql(
            db,
            "SELECT w.start_ms, w.end_ms, w.surface FROM word w JOIN current c ON c.version_id = w.version_id "
            "WHERE c.media_id = ? ORDER BY w.idx",
            (media_id,),
        )
    ]


def _table_words(windows: list[Window]) -> list[tuple[int, int, str]]:
    return sorted((w.start_ms, w.end_ms, w.text) for window in windows for w in window.words)


def _left(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


# -- store helpers the worker needs --------------------------------------------------


def test_the_store_names_the_media_of_a_file_hash_without_creating_one(
    store: Store, gateway: Gateway, media: Media, db: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    before = _sql(db, "SELECT COUNT(*) FROM media")

    assert store.media_of_file_sha256(_sha_of(gateway, 11)) == media_id
    assert store.media_of_file_sha256("e" * 64) is None
    assert _sql(db, "SELECT COUNT(*) FROM media") == before


def _prov(sha: str, epoch: int = 0, level: Level = Level.PREVIEW) -> Provenance:
    return Provenance(
        engine="parakeet",
        model_sha256=catalog.MODEL_SHA256,
        config_version=1,
        profile=PROFILE,
        level=level,
        epoch=epoch,
        language="und",
        input_file_sha256=sha,
    )


def test_a_piece_of_the_second_pass_marks_the_job(store: Store, gateway: Gateway, media: Media, db: Path) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    job = store.next_preview(NOW)
    assert job is not None
    word = Word(start_ms=10, end_ms=20, surface="a", norm="a", conf=0.9, src="machine")
    counters = ChunkCounters(kept_words=1, drop_script=0, drop_language=0, drop_conf=0, speech_ms=0)

    assert store.commit_chunk(job, prov=_prov(_sha_of(gateway, 11)), words=[word], next_start_ms=0, counters=counters)
    assert _job(db, media_id)["second_pass"] == 0
    assert store.commit_chunk(
        job, prov=_prov(_sha_of(gateway, 11)), words=[], next_start_ms=0, counters=counters, second_pass=True
    )
    assert _job(db, media_id)["second_pass"] == 1


# -- order ---------------------------------------------------------------------------


async def test_the_event_job_is_worked_before_the_newer_crawl_job(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    crawl = _add(store, gateway, media, 11, duration_ms=MIN, mtime=1_700_000_500)
    event = _add(store, gateway, media, 12, duration_ms=MIN, origin="event", mtime=1_700_000_100)
    engine.first = [spread(1000, 9000, "w")]

    step = await worker.run_once()

    assert step.media_id == event
    assert step.outcome == PreviewOutcome.COMPLETE
    assert _job(db, event)["state"] == "complete"
    assert _job(db, crawl)["state"] == "queued"
    step = await worker.run_once()
    assert step.media_id == crawl


# -- chunks --------------------------------------------------------------------------


def _long_table() -> list[Window]:
    """25 min of speech windows; one reaches over 10:00 and one over 20:00."""
    return [
        spread(5_000, 20_000, "a"),
        spread(300_000, 320_000, "b"),
        spread(590_000, 607_000, "c"),  # begins before 10:00, ends after it
        spread(900_000, 915_000, "d"),
        spread(1_195_000, 1_212_000, "e"),  # begins before 20:00 after chunk 2 began at 10:07
        spread(1_400_000, 1_420_000, "f"),
        spread(1_490_000, 1_499_000, "g"),
    ]


async def test_a_25_minute_file_is_worked_in_three_chunks_without_double_or_gap(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path, tmp_dir: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=25 * MIN)
    engine.first = _long_table()

    step = await worker.run_once()

    assert step.outcome == PreviewOutcome.COMPLETE
    assert step.chunks == 3
    # Chunk 1 from 0; chunk 2 at the end of the window over 10:00, with 1 s of context in front.
    second = 607_000
    third = 1_212_000
    assert [call.offset_ms for call in engine.calls] == [0, second - CHUNK_CONTEXT_MS, third - CHUNK_CONTEXT_MS]
    assert [call.second_pass for call in engine.calls] == [False, False, False]
    starts = [d[0] for d in media.decodes]
    assert starts == [0, second - CHUNK_CONTEXT_MS, third - CHUNK_CONTEXT_MS]
    # Every decode reaches 10 min plus 60 s of lookahead past the chunk start, cut at the end of the file.
    assert media.decodes[0][1] == CHUNK_MS + CHUNK_LOOKAHEAD_MS
    assert media.decodes[1][1] == CHUNK_MS + CHUNK_LOOKAHEAD_MS + CHUNK_CONTEXT_MS
    assert media.decodes[2][2] == 25 * MIN - (third - CHUNK_CONTEXT_MS)
    # The union of the stored words is the table: no word twice, none missing.
    assert _words(db, media_id) == _table_words(engine.first)
    job = _job(db, media_id)
    assert (job["state"], job["chunks_done"], job["reason"]) == ("complete", 3, None)
    assert job["kept_words"] == len(_table_words(engine.first))
    assert engine.stops >= 1
    assert _left(tmp_dir) == []


async def test_a_window_that_begins_inside_the_context_and_reaches_on_keeps_only_its_new_words(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    """The VAD of chunk 2 may merge the tail it hears in the context with the speech that follows."""
    media_id = _add(store, gateway, media, 11, duration_ms=15 * MIN)
    tail = ew("tail", 606_500)
    after = ew("after", 608_000)
    # Chunk 1 sees the window up to 10:07 and takes it; chunk 2 sees one merged window from 10:06.
    engine.first = [win(598_000, 607_000, (ew("before", 599_000), tail)), win(640_000, 650_000, (ew("late", 641_000),))]

    def merge_in_chunk_two(index: int) -> None:
        if index == 1:
            engine.first = [win(606_000, 609_000, (tail, after)), win(640_000, 650_000, (ew("late", 641_000),))]

    engine.hook = merge_in_chunk_two

    await worker.run_once()

    assert [w[2] for w in _words(db, media_id)] == ["before", "tail", "after", "late"]


async def test_resume_after_a_failure_goes_on_at_the_saved_chunk(
    services: Services,
    tmp_dir: Path,
    gateway: Gateway,
    media: Media,
    clock: Clock,
    store: Store,
    db: Path,
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=25 * MIN)
    broken = FakeEngine(first=_long_table(), raise_at=1)
    first = _worker(services, tmp_dir, gateway, media, broken, clock)

    with pytest.raises(RuntimeError, match="engine broke"):
        await first.run_once()

    assert broken.stops == 1
    assert _left(tmp_dir) == []
    job = _job(db, media_id)
    assert (job["state"], job["chunks_done"], job["next_start_ms"]) == ("running", 1, 607_000)

    fresh = FakeEngine(first=_long_table())
    second = _worker(services, tmp_dir, gateway, media, fresh, clock)
    await second.prepare()
    step = await second.run_once()

    assert step.outcome == PreviewOutcome.COMPLETE
    # Chunk 1 is not computed again.
    assert [call.offset_ms for call in fresh.calls] == [607_000 - CHUNK_CONTEXT_MS, 1_212_000 - CHUNK_CONTEXT_MS]
    assert _words(db, media_id) == _table_words(_long_table())
    assert _job(db, media_id)["chunks_done"] == 3


async def test_a_crawl_job_yields_to_an_event_at_the_chunk_boundary_and_goes_on_later(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path, services: Services
) -> None:
    long_one = _add(store, gateway, media, 11, duration_ms=25 * MIN)
    engine.first = _long_table()
    added: list[int] = []

    def upload_during_chunk_one(index: int) -> None:
        if index == 0:
            with services.lock:
                added.append(_add(store, gateway, media, 12, duration_ms=MIN, origin="event"))

    engine.hook = upload_during_chunk_one

    step = await worker.run_once()

    assert step.outcome == PreviewOutcome.YIELDED
    assert step.media_id == long_one
    assert step.chunks == 1
    job = _job(db, long_one)
    assert (job["state"], job["chunks_done"], job["next_start_ms"]) == ("queued", 1, 607_000)
    # The chunk was finished, never cut: its words are stored.
    assert [w[2] for w in _words(db, long_one)] == [t[2] for t in _table_words(engine.first) if t[0] < 607_000]

    engine.hook = None
    step = await worker.run_once()
    assert step.media_id == added[0]
    assert step.outcome == PreviewOutcome.COMPLETE

    calls_before = len(engine.calls)
    step = await worker.run_once()
    assert step.media_id == long_one
    assert step.outcome == PreviewOutcome.COMPLETE
    assert [c.offset_ms for c in engine.calls[calls_before:]] == [
        607_000 - CHUNK_CONTEXT_MS,
        1_212_000 - CHUNK_CONTEXT_MS,
    ]
    assert _words(db, long_one) == _table_words(_long_table())


async def test_an_event_job_does_not_yield_to_another_event(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, services: Services
) -> None:
    _add(store, gateway, media, 11, duration_ms=25 * MIN, origin="event")
    engine.first = _long_table()

    def upload(index: int) -> None:
        if index == 0:
            with services.lock:
                _add(store, gateway, media, 12, duration_ms=MIN, origin="event")

    engine.hook = upload

    step = await worker.run_once()

    assert step.outcome == PreviewOutcome.COMPLETE
    assert step.chunks == 3


async def test_after_the_first_chunk_the_media_is_findable_as_a_preview(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=25 * MIN)
    engine.first = _long_table()
    seen: list[tuple[Any, ...]] = []

    def look(index: int) -> None:
        if index == 1:
            seen.extend(_sql(db, "SELECT level FROM current WHERE media_id = ?", (media_id,)))
            seen.extend(_sql(db, "SELECT 'outbox', index_rev FROM index_outbox WHERE media_id = ?", (media_id,)))

    engine.hook = look

    await worker.run_once()

    assert seen[0] == (int(Level.PREVIEW),)
    assert seen[1][0] == "outbox"
    prov = _sql(
        db,
        "SELECT t.engine, t.model_sha256, t.profile, t.level, t.language, t.input_file_sha256, t.config_version "
        "FROM transcript t JOIN current c ON c.version_id = t.version_id WHERE c.media_id = ?",
        (media_id,),
    )
    assert prov == [("parakeet", catalog.MODEL_SHA256, "balanced", int(Level.PREVIEW), "und", _sha_of(gateway, 11), 1)]


# -- time axis (TRANS-08) -------------------------------------------------------------


async def test_timeline_a_word_of_chunk_two_lands_at_offset_plus_its_window_time(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=15 * MIN)
    # Relative to the decoded range: a word at 2,0 s, and a window in the 1 s of context only.
    engine.relative = True
    engine.first = [win(100, 900, (ew("context", 200),)), win(1800, 2600, (ew("zwei", 2000),))]

    await worker.run_once()

    offsets = [call.offset_ms for call in engine.calls]
    assert offsets[0] == 0
    # Chunk 1 took its last window at 2,6 s; chunk 2 begins there and decodes from 1 s earlier.
    assert offsets[1] == 2600 - CHUNK_CONTEXT_MS
    words = _words(db, media_id)
    assert (2000, 2300, "zwei") in words
    assert (offsets[1] + 2000, offsets[1] + 2300, "zwei") in words
    # The window inside the context of chunk 2 began before next_start_ms and is dropped.
    assert (offsets[1] + 200, offsets[1] + 500, "context") not in words
    assert words == sorted(words)


# -- reasons -------------------------------------------------------------------------


@pytest.mark.parametrize("reason", ["damaged", "protected", "no_audio", "format_unsupported"])
async def test_a_probe_reason_skips_the_job_with_that_reason(
    worker: Preview,
    store: Store,
    gateway: Gateway,
    media: Media,
    engine: FakeEngine,
    db: Path,
    tmp_dir: Path,
    reason: str,
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    media.probe_reasons[_sha_of(gateway, 11)] = reason

    step = await worker.run_once()

    assert (step.outcome, step.reason) == (PreviewOutcome.SKIPPED, reason)
    job = _job(db, media_id)
    assert (job["state"], job["reason"]) == ("skipped", reason)
    assert engine.calls == []
    assert engine.starts == 0
    assert _left(tmp_dir) == []


@pytest.mark.parametrize("reason", ["damaged", "format_unsupported"])
async def test_a_decode_reason_skips_the_job_with_that_reason(
    worker: Preview,
    store: Store,
    gateway: Gateway,
    media: Media,
    engine: FakeEngine,
    db: Path,
    tmp_dir: Path,
    reason: str,
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    media.decode_reasons[_sha_of(gateway, 11)] = reason

    step = await worker.run_once()

    assert (step.outcome, step.reason) == (PreviewOutcome.SKIPPED, reason)
    job = _job(db, media_id)
    assert (job["state"], job["reason"], job["duration_ms"]) == ("skipped", reason, MIN)
    assert engine.calls == []
    assert _left(tmp_dir) == []


async def test_without_a_known_duration_a_file_without_samples_is_damaged(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    """D-03-20: probe accepts it without a duration (garbage named .mp3), decode yields nothing."""
    media_id = _add(store, gateway, media, 11, duration_ms=None)

    step = await worker.run_once()

    assert (step.outcome, step.reason) == (PreviewOutcome.SKIPPED, "damaged")
    job = _job(db, media_id)
    assert (job["state"], job["reason"], job["duration_ms"]) == ("skipped", "damaged", None)
    assert engine.calls == []


async def test_garbage_bytes_are_damaged_with_the_real_ffprobe(
    services: Services,
    tmp_dir: Path,
    gateway: Gateway,
    engine: FakeEngine,
    clock: Clock,
    store: Store,
    db: Path,
    ffprobe_bin: Path,
    ffmpeg_bin: Path,
) -> None:
    """D-03-20: the temporary file has no extension, so no demuxer is picked by a name like .bin."""
    noise = bytes(hashlib.sha256(i.to_bytes(4, "big")).digest()[0] for i in range(200_000))
    media_id = _add(store, gateway, Media(), 11, duration_ms=None, data=noise)
    worker = Preview(
        services,
        directory=tmp_dir,
        models_root=tmp_dir,
        fetch=gateway.fetch,
        engine_factory=lambda _root: engine,
        probe=partial(probe_module.probe, ffprobe=ffprobe_bin),
        decode=partial(decode_chunk, ffmpeg=ffmpeg_bin),
        clock=clock,
    )

    step = await worker.run_once()

    assert (step.outcome, step.reason) == (PreviewOutcome.SKIPPED, "damaged")
    assert _job(db, media_id)["reason"] == "damaged"
    assert _left(tmp_dir) == []


async def test_longer_than_the_limit_is_too_long_with_its_duration(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path, tmp_dir: Path
) -> None:
    store.set_max_duration_hours(2)
    over = _add(store, gateway, media, 11, duration_ms=2 * 3_600_000 + 1)

    step = await worker.run_once()

    assert (step.outcome, step.reason) == (PreviewOutcome.SKIPPED, "too_long")
    job = _job(db, over)
    assert (job["state"], job["reason"], job["duration_ms"]) == ("skipped", "too_long", 2 * 3_600_000 + 1)
    assert engine.calls == []
    assert _left(tmp_dir) == []


async def test_exactly_the_limit_is_worked(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    store.set_max_duration_hours(1)
    media_id = _add(store, gateway, media, 11, duration_ms=3_600_000)
    engine.first = [spread(1000, 9000, "w")]

    step = await worker.run_once()

    assert step.outcome == PreviewOutcome.COMPLETE
    assert _job(db, media_id)["state"] == "complete"


async def test_not_enough_space_defers_with_disk_full_and_no_download(
    worker: Preview,
    store: Store,
    gateway: Gateway,
    media: Media,
    engine: FakeEngine,
    db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    size = len(gateway.files[11])
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: size + nc.DISK_RESERVE_BYTES - 1)

    step = await worker.run_once()

    assert (step.outcome, step.reason) == (PreviewOutcome.DEFERRED, "disk_full")
    job = _job(db, media_id)
    assert (job["state"], job["reason"], job["next_try_at"]) == ("waiting", "disk_full", NOW + DISK_FULL_RETRY_SECONDS)
    assert gateway.requests == 0
    assert engine.calls == []
    # UI-SPEC T12: disk_full is tried again after DISK_FULL_RETRY_SECONDS.
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: 1024**4)
    assert await worker.run_once() == preview_module.PreviewStep(PreviewOutcome.IDLE)


async def test_disk_full_is_tried_again_after_its_wait(
    worker: Preview,
    store: Store,
    gateway: Gateway,
    media: Media,
    engine: FakeEngine,
    db: Path,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    engine.first = [spread(1000, 9000, "w")]
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: 0)
    await worker.run_once()
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: 1024**4)

    clock.now = NOW + DISK_FULL_RETRY_SECONDS
    step = await worker.run_once()

    assert step.outcome == PreviewOutcome.COMPLETE
    assert _job(db, media_id)["state"] == "complete"


async def test_exactly_enough_space_downloads(
    worker: Preview,
    store: Store,
    gateway: Gateway,
    media: Media,
    engine: FakeEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _add(store, gateway, media, 11, duration_ms=MIN)
    size = len(gateway.files[11])
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: size + nc.DISK_RESERVE_BYTES)

    step = await worker.run_once()

    assert step.outcome != PreviewOutcome.DEFERRED
    assert gateway.requests == 1


async def test_other_bytes_than_the_content_key_are_stale_without_a_word(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path, tmp_dir: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    changed = _content("changed since the capture", len(gateway.files[11]))
    gateway.files[11] = changed
    media.durations[hashlib.sha256(changed).hexdigest()] = MIN
    engine.first = [spread(1000, 9000, "w")]

    step = await worker.run_once()

    assert step.outcome == PreviewOutcome.STALE
    assert engine.calls == []
    assert media.probes == 0
    assert _words(db, media_id) == []
    assert _sql(db, "SELECT COUNT(*) FROM word") == [(0,)]
    job = _job(db, media_id)
    # Not claimed again at once (no loop of downloads), not counted as an attempt.
    assert job["state"] != "running"
    assert job["attempts"] == 0
    assert await worker.run_once() == preview_module.PreviewStep(PreviewOutcome.IDLE)
    assert _left(tmp_dir) == []


async def test_a_refused_download_waits_without_an_attempt(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path, tmp_dir: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    gateway.files[11] = b""  # 0 bytes for a file of 4096: size_mismatch

    step = await worker.run_once()

    assert (step.outcome, step.reason) == (PreviewOutcome.DEFERRED, nc.SIZE_MISMATCH)
    job = _job(db, media_id)
    assert (job["state"], job["attempts"]) == ("waiting", 0)
    assert job["next_try_at"] > NOW
    assert engine.calls == []
    assert _left(tmp_dir) == []


@pytest.mark.parametrize("code", [child.TIMEOUT, child.OUT_OF_MEMORY, child.CRASHED])
async def test_an_engine_failure_is_tried_three_times_then_engine_failed(
    worker: Preview,
    store: Store,
    gateway: Gateway,
    media: Media,
    engine: FakeEngine,
    db: Path,
    clock: Clock,
    tmp_dir: Path,
    code: str,
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    engine.codes = dict.fromkeys(range(10), code)

    outcomes = []
    for attempt in range(MAX_ENGINE_ATTEMPTS):
        clock.now = NOW + attempt * 1000
        step = await worker.run_once()
        outcomes.append(step.outcome)
        job = _job(db, media_id)
        if attempt < MAX_ENGINE_ATTEMPTS - 1:
            assert (job["state"], job["attempts"]) == ("waiting", attempt + 1)
            assert job["next_try_at"] == int(clock.now) + NO_ROOM_RETRY_SECONDS

    assert outcomes == [PreviewOutcome.FAILED_ATTEMPT] * (MAX_ENGINE_ATTEMPTS - 1) + [PreviewOutcome.SKIPPED]
    job = _job(db, media_id)
    assert (job["state"], job["reason"]) == ("skipped", "engine_failed")
    assert engine.stops >= MAX_ENGINE_ATTEMPTS
    assert _left(tmp_dir) == []


async def test_no_room_for_the_engine_waits_60_s_without_an_attempt(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path, tmp_dir: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    engine.start_code = child.NO_ROOM

    step = await worker.run_once()

    assert step.outcome == PreviewOutcome.DEFERRED
    job = _job(db, media_id)
    assert (job["state"], job["attempts"], job["next_try_at"]) == ("waiting", 0, NOW + 60)
    assert NO_ROOM_RETRY_SECONDS == 60
    assert engine.calls == []
    assert _left(tmp_dir) == []


async def test_no_room_in_the_middle_of_a_job_waits_without_an_attempt(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=25 * MIN)
    engine.first = _long_table()
    engine.codes = {1: child.NO_ROOM}

    step = await worker.run_once()

    assert step.outcome == PreviewOutcome.DEFERRED
    job = _job(db, media_id)
    assert (job["state"], job["attempts"], job["chunks_done"]) == ("waiting", 0, 1)


async def test_a_foreign_current_version_ends_the_job_without_another_try(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path, services: Services
) -> None:
    """03-09: a later piece after a foreign current version is stale; the job ends, no retry."""
    media_id = _add(store, gateway, media, 11, duration_ms=25 * MIN)
    engine.first = _long_table()
    sha = _sha_of(gateway, 11)

    def refine(index: int) -> None:
        if index == 1:
            word = Word(start_ms=0, end_ms=10, surface="x", norm="x", conf=1.0, src="machine")
            with services.lock:
                assert store.publish_version(media_id, _prov(sha, level=Level.REFINED), [word]).published

    engine.hook = refine

    step = await worker.run_once()

    assert step.outcome == PreviewOutcome.STALE
    assert len(engine.calls) == 2
    job = _job(db, media_id)
    assert job["state"] == "complete"
    assert job["chunks_done"] == 1
    assert await worker.run_once() == preview_module.PreviewStep(PreviewOutcome.IDLE)


# -- verdict (D-03-11, D-03-12, D-03-16) ------------------------------------------------


async def test_a_short_file_without_a_kept_word_gets_one_second_pass(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=40_000)
    engine.first = [win(1000, 3000, verdict=DROP_CONFIDENCE, n_words=0)]
    engine.second = [win(900, 3100, (ew("tout", 1000), ew("bien", 1500)))]

    step = await worker.run_once()

    assert [call.second_pass for call in engine.calls] == [False, True]
    assert engine.calls[1].offset_ms == 0
    assert engine.calls[1].length_ms == 40_000
    assert step.outcome == PreviewOutcome.COMPLETE
    job = _job(db, media_id)
    assert (job["state"], job["second_pass"]) == ("complete", 1)
    assert [w[2] for w in _words(db, media_id)] == ["tout", "bien"]


async def test_a_short_file_without_speech_in_both_passes_is_no_speech_after_one_second_pass(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=40_000)

    step = await worker.run_once()

    assert [call.second_pass for call in engine.calls] == [False, True]
    assert (step.outcome, step.reason) == (PreviewOutcome.SKIPPED, "no_speech")
    job = _job(db, media_id)
    assert (job["state"], job["reason"], job["second_pass"]) == ("skipped", "no_speech", 1)


async def test_the_second_pass_is_not_repeated_after_a_restart(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path, services: Services
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=40_000)
    with services.lock:
        job = store.next_preview(NOW)
        assert job is not None
        empty = ChunkCounters(kept_words=0, drop_script=0, drop_language=0, drop_conf=0, speech_ms=0)
        sha = _sha_of(gateway, 11)
        assert store.commit_chunk(job, prov=_prov(sha), words=[], next_start_ms=40_000, counters=empty)
        assert store.commit_chunk(
            job, prov=_prov(sha), words=[], next_start_ms=40_000, counters=empty, second_pass=True
        )
        store.reset_running()

    step = await worker.run_once()

    assert engine.calls == []
    assert (step.outcome, step.reason) == (PreviewOutcome.SKIPPED, "no_speech")
    assert _job(db, media_id)["state"] == "skipped"


async def test_a_file_over_60_s_without_a_word_gets_no_second_pass(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=90_000)

    step = await worker.run_once()

    assert [call.second_pass for call in engine.calls] == [False]
    assert (step.outcome, step.reason) == (PreviewOutcome.SKIPPED, "no_speech")
    assert _job(db, media_id)["second_pass"] == 0


async def test_dropped_language_without_a_kept_word_is_unsupported_language(
    worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=90_000)
    engine.first = [win(1000, 9000, verdict=DROP_LANGUAGE, n_words=6, speech=5000)]

    step = await worker.run_once()

    assert (step.outcome, step.reason) == (PreviewOutcome.SKIPPED, "unsupported_language")
    job = _job(db, media_id)
    assert (job["state"], job["reason"], job["drop_language"]) == ("skipped", "unsupported_language", 6)


# -- temporary file and logs ---------------------------------------------------------------


async def test_the_temporary_directory_is_empty_after_every_way_out(
    worker: Preview,
    store: Store,
    gateway: Gateway,
    media: Media,
    engine: FakeEngine,
    tmp_dir: Path,
    services: Services,
) -> None:
    seen_during: list[list[str]] = []
    engine.first = _long_table()

    def look(_index: int) -> None:
        seen_during.append(_left(tmp_dir))

    engine.hook = look
    # success
    _add(store, gateway, media, 11, duration_ms=MIN)
    await worker.run_once()
    assert _left(tmp_dir) == []
    # yield
    _add(store, gateway, media, 12, duration_ms=25 * MIN)

    def upload_then_look(index: int) -> None:
        look(index)
        with services.lock:
            _add(store, gateway, media, 13, duration_ms=MIN, origin="event")

    engine.hook = upload_then_look
    assert (await worker.run_once()).outcome == PreviewOutcome.YIELDED
    assert _left(tmp_dir) == []
    engine.hook = look
    # reason
    media.probe_reasons[_sha_of(gateway, 13)] = "protected"
    assert (await worker.run_once()).reason == "protected"
    assert _left(tmp_dir) == []
    # exception
    engine.raise_at = len(engine.calls)
    with pytest.raises(RuntimeError):
        await worker.run_once()
    assert _left(tmp_dir) == []
    # Positive control: while the engine worked, the file was there under a name without extension.
    assert seen_during
    assert all(len(names) == 1 and "." not in names[0] for names in seen_during)


async def test_prepare_removes_left_over_files_of_a_stopped_process(
    worker: Preview, store: Store, gateway: Gateway, media: Media, tmp_dir: Path, db: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    assert store.next_preview(NOW) is not None
    (tmp_dir / ("a" * 32)).write_bytes(b"left over media")
    (tmp_dir / ("b" * 32 + nc.PART_SUFFIX)).write_bytes(b"left over part")

    await worker.prepare()

    assert _left(tmp_dir) == []
    assert _job(db, media_id)["state"] == "queued"


async def test_logs_carry_no_path_and_no_word(
    companion_ok: None,
    worker: Preview,
    store: Store,
    gateway: Gateway,
    media: Media,
    engine: FakeEngine,
    tmp_dir: Path,
    db: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=25 * MIN)
    engine.first = [*_long_table(), win(700_000, 705_000, (ew(SPOKEN_WORD, 701_000),))]
    other = _add(store, gateway, media, 12, duration_ms=MIN)
    media.probe_reasons[_sha_of(gateway, 12)] = "damaged"

    with caplog.at_level(logging.DEBUG):
        await worker.run_once()
        await worker.run_once()
        await worker.run_forever(idle=0.0, sleep=_no_sleep, rounds=2)

    # Positive control: the word and the marker were really there to leak.
    assert SPOKEN_WORD in [w[2] for w in _words(db, media_id)]
    assert MARK in str(tmp_dir)
    assert _job(db, other)["reason"] == "damaged"
    own = [r for r in caplog.records if r.name.startswith("audio_video_search_backend")]
    assert any(r.name == preview_module.__name__ for r in own)
    for record in own:
        line = record.getMessage() + " " + str(record.__dict__)
        assert MARK not in line
        assert SPOKEN_WORD not in line


async def _no_sleep(_seconds: float) -> None:
    await asyncio.sleep(0)


# -- run_forever ---------------------------------------------------------------------


async def test_without_ready_models_no_job_is_taken(
    companion_ok: None, worker: Preview, store: Store, gateway: Gateway, media: Media, engine: FakeEngine, db: Path
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    procure.mark_ready(False)
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    await worker.run_forever(sleep=sleep, rounds=2)

    assert _job(db, media_id)["state"] == "queued"
    assert gateway.requests == 0
    assert slept == [IDLE_SECONDS, IDLE_SECONDS]

    # Positive control: with the models ready the same loop works the job.
    procure.mark_ready(True)
    await worker.run_forever(sleep=sleep, rounds=1)
    assert _job(db, media_id)["state"] == "complete"


async def test_without_the_php_app_no_job_is_taken(
    worker: Preview, store: Store, gateway: Gateway, media: Media, db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    monkeypatch.setattr(companion, "current", lambda: companion.CompanionState(companion.MISSING, None, 0.0))

    await worker.run_forever(sleep=_no_sleep, rounds=2)

    assert _job(db, media_id)["state"] == "queued"
    assert gateway.requests == 0


async def test_the_loop_outlives_a_failing_step(
    companion_ok: None,
    services: Services,
    tmp_dir: Path,
    gateway: Gateway,
    media: Media,
    clock: Clock,
    store: Store,
    db: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    media_id = _add(store, gateway, media, 11, duration_ms=MIN)
    broken = FakeEngine(raise_at=0)
    worker = _worker(services, tmp_dir, gateway, media, broken, clock)

    with caplog.at_level(logging.ERROR):
        await worker.run_forever(sleep=_no_sleep, rounds=2)

    failed = [r for r in caplog.records if r.name == preview_module.__name__ and r.levelno >= logging.ERROR]
    assert failed
    assert failed[0].__dict__["error_type"] == "RuntimeError"
    # prepare() at the start of the loop hands the broken running job back; the job stays workable.
    assert _job(db, media_id)["state"] in {"running", "queued"}


# -- real ffmpeg -----------------------------------------------------------------------


def _silent_wav(path: Path, seconds: int) -> bytes:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        block = bytes(2 * 16000 * 60)
        for _ in range(seconds // 60):
            handle.writeframes(block)
        handle.writeframes(bytes(2 * 16000 * (seconds % 60)))
    return path.read_bytes()


async def test_a_25_minute_wav_through_real_ffprobe_and_ffmpeg(
    services: Services,
    tmp_path: Path,
    tmp_dir: Path,
    gateway: Gateway,
    clock: Clock,
    store: Store,
    db: Path,
    ffprobe_bin: Path,
    ffmpeg_bin: Path,
) -> None:
    data = _silent_wav(tmp_path / "source.wav", 25 * 60)
    media_id = _add(store, gateway, Media(), 11, duration_ms=None, data=data)
    engine = FakeEngine(first=_long_table())
    worker = Preview(
        services,
        directory=tmp_dir,
        models_root=tmp_dir,
        fetch=gateway.fetch,
        engine_factory=lambda _root: engine,
        probe=partial(probe_module.probe, ffprobe=ffprobe_bin),
        decode=partial(decode_chunk, ffmpeg=ffmpeg_bin),
        clock=clock,
    )

    step = await worker.run_once()

    assert step.outcome == PreviewOutcome.COMPLETE
    assert [c.offset_ms for c in engine.calls] == [0, 607_000 - CHUNK_CONTEXT_MS, 1_212_000 - CHUNK_CONTEXT_MS]
    # Real PCM lengths: 11 min, 11 min plus the context, and the rest of the file.
    lengths = [c.length_ms for c in engine.calls]
    assert lengths[0] == CHUNK_MS + CHUNK_LOOKAHEAD_MS
    assert lengths[1] == CHUNK_MS + CHUNK_LOOKAHEAD_MS + CHUNK_CONTEXT_MS
    assert abs(lengths[2] - (25 * MIN - (1_212_000 - CHUNK_CONTEXT_MS))) <= 1
    assert _words(db, media_id) == _table_words(_long_table())
    assert _left(tmp_dir) == []
