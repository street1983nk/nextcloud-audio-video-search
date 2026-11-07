"""The capture of the discovery (plan 02-08): one full download per reference.

Part 1 tests nc.fetch_to_tempfile against an httpx MockTransport: the bytes go
into a temporary file under the volume, both hashes come out of the stream, the
length has to be exactly the size of the reference, and every refusal of the
gateway is its own code, never a hash. Part 2 tests the stage itself
(worker/capture.py) with a fake fetch against a real state.db.
"""

import asyncio
import hashlib
import logging
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, BinaryIO, cast

import httpx
import pytest

from audio_video_search_backend import companion, nc
from audio_video_search_backend.api import Services
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.store.repo import FileRef, IntakeItem, Store
from audio_video_search_backend.worker import capture as capture_module
from audio_video_search_backend.worker.capture import Capture, CaptureOutcome, retry_at

KIB = 1024
USER = "alice-reader"
HIDDEN_PATH = "/very/secret/path/recording.mp4"


def _bytes(size: int) -> bytes:
    """Deterministic, not repeating within 64 KiB, so a wrong head offset changes the hash."""
    block = hashlib.sha256(b"seed").digest()
    out = bytearray()
    counter = 0
    while len(out) < size:
        out += hashlib.sha256(block + counter.to_bytes(8, "big")).digest()
        counter += 1
    return bytes(out[:size])


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


def _left(directory: Path) -> list[str]:
    """What is left in the temporary directory (a sync helper, the async tests call it)."""
    return sorted(path.name for path in directory.iterdir())


def _sizes(directory: Path) -> list[tuple[str, int]]:
    return [(path.name, path.stat().st_size) for path in directory.iterdir()]


def _split(data: bytes, step: int) -> list[bytes]:
    return [data[i : i + step] for i in range(0, len(data), step)]


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "tmp"
    directory.mkdir()
    return directory


@pytest.fixture(autouse=True)
def plenty_of_space(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: 1024**4)


async def _fetch(
    handler: Callable[[httpx.Request], httpx.Response],
    tmp_dir: Path,
    expected_size: int,
    *,
    max_bytes: int = 1024**3,
) -> nc.FetchResult:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await nc.fetch_to_tempfile(42, USER, tmp_dir, expected_size, max_bytes, client=client)


# Part 1: the download into a temporary file.


async def test_a_full_download_gives_both_hashes_and_leaves_no_file(tmp_dir: Path) -> None:
    data = _bytes(200 * KIB)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        # Odd block sizes, so the head boundary falls inside a block.
        return httpx.Response(200, content=_chunks(*_split(data, 7 * KIB + 3)))

    result = await _fetch(handler, tmp_dir, len(data))

    assert result.error is None
    assert result.sha256 == _sha(data)
    assert result.head_sha256 == _sha(data[: nc.HEAD_BYTES])
    assert result.size == len(data)
    assert _left(tmp_dir) == []
    request = seen[0]
    assert request.url.path == "/ocs/v2.php/apps/audio_video_search/files/42"
    assert request.url.params["userId"] == USER
    assert request.headers["EX-APP-ID"] == "audio_video_search_backend"
    assert "AUTHORIZATION-APP-API" in request.headers


async def test_the_bytes_are_written_to_a_part_file_under_the_volume_while_streaming(tmp_dir: Path) -> None:
    mib = nc.CHUNK_SIZE
    data = _bytes(3 * mib)
    during: list[tuple[str, int]] = []

    async def body() -> AsyncIterator[bytes]:
        yield data[:mib]
        yield data[mib : 2 * mib]
        # At least the first block is on disk by now; the stream has not ended yet.
        await asyncio.sleep(0.05)
        during.extend(_sizes(tmp_dir))
        yield data[2 * mib :]

    result = await _fetch(lambda _r: httpx.Response(200, content=body()), tmp_dir, len(data))

    assert result.sha256 == _sha(data)
    assert len(during) == 1
    name, size = during[0]
    assert name.endswith(".part")
    assert len(name) == 32 + len(".part")
    assert size >= mib
    assert _left(tmp_dir) == []


@pytest.mark.parametrize("size", [0, 10 * KIB, nc.HEAD_BYTES])
async def test_a_file_up_to_64_kib_has_the_head_hash_of_the_whole(tmp_dir: Path, size: int) -> None:
    data = _bytes(size)

    result = await _fetch(lambda _r: httpx.Response(200, content=_chunks(data)), tmp_dir, size)

    assert result.error is None
    assert result.head_sha256 == result.sha256 == _sha(data)


async def test_one_byte_over_64_kib_has_its_own_head_hash(tmp_dir: Path) -> None:
    data = _bytes(nc.HEAD_BYTES + 1)

    result = await _fetch(lambda _r: httpx.Response(200, content=_chunks(data)), tmp_dir, len(data))

    assert result.head_sha256 == _sha(data[: nc.HEAD_BYTES])
    assert result.head_sha256 != result.sha256


@pytest.mark.parametrize("delta", [-1, 1, -100 * KIB, 5 * KIB])
async def test_a_wrong_length_is_size_mismatch_and_leaves_no_file(tmp_dir: Path, delta: int) -> None:
    expected = 200 * KIB
    data = _bytes(expected + delta)

    result = await _fetch(lambda _r: httpx.Response(200, content=_chunks(*_split(data, 4096))), tmp_dir, expected)

    assert result.error == nc.SIZE_MISMATCH
    assert result.sha256 is None
    assert result.head_sha256 is None
    assert _left(tmp_dir) == []


async def test_a_declared_length_other_than_the_size_is_refused_before_writing(tmp_dir: Path) -> None:
    data = _bytes(KIB)
    opened: list[Path] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=data)  # content= sets Content-Length

    original = nc._open_part

    def spy(part: Path) -> BinaryIO:
        opened.append(part)
        return original(part)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(nc, "_open_part", spy)
        result = await _fetch(handler, tmp_dir, KIB + 1)

    assert result.error == nc.SIZE_MISMATCH
    assert opened == []
    assert _left(tmp_dir) == []


async def test_a_stream_that_breaks_off_is_gateway_failed_and_leaves_no_file(tmp_dir: Path) -> None:
    data = _bytes(64 * KIB)

    async def body() -> AsyncIterator[bytes]:
        yield data[: 16 * KIB]
        raise httpx.RemoteProtocolError("peer closed connection")

    result = await _fetch(lambda _r: httpx.Response(200, content=body()), tmp_dir, len(data))

    assert result.error == nc.GATEWAY_FAILED
    assert result.sha256 is None
    assert _left(tmp_dir) == []


async def test_a_read_timeout_inside_the_stream_is_read_timeout(tmp_dir: Path) -> None:
    async def body() -> AsyncIterator[bytes]:
        yield b"x" * KIB
        raise httpx.ReadTimeout("silence")

    result = await _fetch(lambda _r: httpx.Response(200, content=body()), tmp_dir, 4 * KIB)

    assert result.error == nc.READ_TIMEOUT
    assert _left(tmp_dir) == []


async def test_a_trickling_answer_hits_the_overall_deadline(tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nc, "capture_deadline", lambda _size: 0.2)

    async def body() -> AsyncIterator[bytes]:
        for _ in range(100):
            yield b"x"
            await asyncio.sleep(0.05)

    result = await _fetch(lambda _r: httpx.Response(200, content=body()), tmp_dir, 100)

    assert result.error == nc.READ_TIMEOUT
    assert _left(tmp_dir) == []


def test_the_deadline_grows_with_the_size() -> None:
    assert nc.capture_deadline(0) == nc.CAPTURE_DEADLINE_BASE_SECONDS
    gib = nc.capture_deadline(1024**3)
    assert gib == pytest.approx(120 + 4096)


@pytest.mark.parametrize(
    "exception",
    [httpx.ConnectTimeout("slow"), httpx.PoolTimeout("busy")],
)
async def test_a_timeout_before_the_answer_is_read_timeout(tmp_dir: Path, exception: Exception) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise exception

    result = await _fetch(handler, tmp_dir, 10)

    assert result.error == nc.READ_TIMEOUT


async def test_a_refused_connection_is_gateway_failed(tmp_dir: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    result = await _fetch(handler, tmp_dir, 10)

    assert result.error == nc.GATEWAY_FAILED


async def test_too_little_space_is_disk_full_without_a_request(tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[httpx.Request] = []
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: nc.DISK_RESERVE_BYTES + 99)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"x" * 100)

    result = await _fetch(handler, tmp_dir, 100)

    assert result.error == nc.DISK_FULL
    assert calls == []


async def test_an_unreadable_volume_is_disk_full_without_a_request(
    tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[httpx.Request] = []

    def broken(_directory: Path) -> int:
        raise OSError("no such volume")

    monkeypatch.setattr(nc, "free_bytes", broken)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"x")

    assert (await _fetch(handler, tmp_dir, 1)).error == nc.DISK_FULL
    assert calls == []


async def test_more_than_the_cap_is_too_large_without_a_request(tmp_dir: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"x")

    result = await _fetch(handler, tmp_dir, 1001, max_bytes=1000)

    assert result.error == nc.TOO_LARGE
    assert calls == []


@pytest.mark.parametrize(
    ("status", "reason", "error"),
    [
        (403, None, nc.READ_DENIED),
        (403, "access_control", nc.ACCESS_CONTROL),
        (403, "excluded", nc.EXCLUDED),
        (403, "Access_Control ", nc.ACCESS_CONTROL),
        (403, "locked", nc.READ_DENIED),
        (403, "something else", nc.READ_DENIED),
        (422, None, nc.READ_DENIED),
        (422, "excluded", nc.READ_DENIED),
        (423, None, nc.LOCKED),
        (423, "locked", nc.LOCKED),
        (404, None, nc.NOT_FOUND),
        (404, "excluded", nc.NOT_FOUND),
        (500, None, nc.GATEWAY_FAILED),
        (503, None, nc.GATEWAY_FAILED),
        (401, None, nc.GATEWAY_FAILED),
        (412, None, nc.GATEWAY_FAILED),
        (302, None, nc.GATEWAY_FAILED),
        (204, None, nc.GATEWAY_FAILED),
        (206, None, nc.GATEWAY_FAILED),
    ],
)
async def test_every_answer_other_than_200_is_its_own_code_and_never_a_hash(
    tmp_dir: Path, status: int, reason: str | None, error: str, caplog: pytest.LogCaptureFixture
) -> None:
    headers = {} if reason is None else {nc.REASON_HEADER: reason}
    data = b"x" * 10  # exactly the expected size: the status alone must refuse

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers=headers | {"Location": HIDDEN_PATH}, content=data)

    with caplog.at_level(logging.DEBUG):
        result = await _fetch(handler, tmp_dir, len(data))

    assert result.error == error
    assert result.status == status
    assert result.sha256 is None
    assert result.head_sha256 is None
    assert _left(tmp_dir) == []
    # The client loggers stand on WARNING outside debug (logs.py); our own lines never carry them.
    own = [record for record in caplog.records if record.name.startswith("audio_video_search_backend")]
    assert own
    for record in own:
        line = repr(vars(record))
        assert USER not in line
        assert HIDDEN_PATH not in line


def test_every_code_is_in_the_closed_list_of_the_store() -> None:
    from audio_video_search_backend.store.repo import STATE_REASONS

    assert nc.FETCH_ERRORS - {nc.EXCLUDED} <= STATE_REASONS


def test_the_capture_client_follows_no_redirect() -> None:
    client = nc.new_capture_client()
    try:
        assert client.follow_redirects is False
        assert client.timeout.connect == 10.0
        assert client.timeout.read == 30.0
    finally:
        asyncio.run(client.aclose())


def test_stale_part_files_are_removed_and_nothing_else(tmp_dir: Path) -> None:
    (tmp_dir / "a.part").write_bytes(b"x")
    (tmp_dir / "b.part").write_bytes(b"y")
    keep = tmp_dir / "keep.txt"
    keep.write_bytes(b"z")

    assert nc.remove_stale_parts(tmp_dir) == 2
    assert sorted(path.name for path in tmp_dir.iterdir()) == ["keep.txt"]
    assert nc.remove_stale_parts(tmp_dir / "missing") == 0


# Part 2: the stage, against a real state.db.

NOW = 1_800_000_000
PREFILTER = "c" * 64
MODEL = "d" * 64


class Clock:
    def __init__(self, now: int = NOW) -> None:
        self.now = now

    def __call__(self) -> float:
        return float(self.now)


class FakeFetch:
    """The gateway as the capture sees it: bytes per file id, or scripted results first."""

    def __init__(self) -> None:
        self.contents: dict[int, bytes] = {}
        self.results: dict[int, list[nc.FetchResult]] = {}
        self.calls: list[tuple[int, str, Path, int, int]] = []

    async def __call__(self, file_id: int, user_id: str, directory: Path, size: int, cap: int) -> nc.FetchResult:
        self.calls.append((file_id, user_id, directory, size, cap))
        scripted = self.results.get(file_id)
        if scripted:
            return scripted.pop(0)
        data = self.contents[file_id]
        return nc.FetchResult(sha256=_sha(data), size=len(data), error=None, head_sha256=_sha(data[: nc.HEAD_BYTES]))

    def failing(self, file_id: int, error: str, times: int = 1) -> None:
        self.results.setdefault(file_id, []).extend(
            nc.FetchResult(sha256=None, size=0, error=error) for _ in range(times)
        )


def _services(store: Store) -> Services:
    return Services(store=store, index=cast("SearchIndex", None))


def _intake(
    store: Store, file_id: int, size: int, *, etag: str = "e1", reader: str | None = "ana", **extra: Any
) -> None:
    values: dict[str, Any] = {
        "storage_id": 3,
        "etag": etag,
        "size": size,
        "mtime": 1_700_000_000,
        "prefilter_key": None,
        "reader_uid": reader,
    }
    values.update(extra)
    store.apply_intake([IntakeItem(queue_id=file_id, kind="content", file_id=file_id, **values)])


def _capture(store: Store, fetch: Any, tmp_dir: Path, clock: Clock, **kwargs: Any) -> Capture:
    return Capture(_services(store), directory=tmp_dir, fetch=fetch, clock=clock, **kwargs)


def _gateway_fetch(handler: Callable[[httpx.Request], httpx.Response]) -> Any:
    """The real nc.fetch_to_tempfile behind a MockTransport, as the fetch of the capture."""

    async def fetch(file_id: int, user_id: str, directory: Path, size: int, cap: int) -> nc.FetchResult:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await nc.fetch_to_tempfile(file_id, user_id, directory, size, cap, client=client)

    return fetch


def _ref(store: Store, file_id: int) -> FileRef:
    ref = store.file_ref(file_id)
    assert ref is not None
    return ref


def _media_row(store: Store, media_id: int) -> tuple[str | None, int | None]:
    row = store._conn.execute("SELECT head_sha256, orphaned_at FROM media WHERE media_id = ?", (media_id,)).fetchone()
    return row[0], row[1]


def _active_count(store: Store) -> int:
    """Independent of the coverage module: the plain number of references that may count."""
    return int(store._conn.execute("SELECT COUNT(*) FROM file_ref WHERE state = 'active'").fetchone()[0])


async def test_a_pending_reference_is_downloaded_and_keyed(store: Store, tmp_dir: Path) -> None:
    data = _bytes(200 * KIB)
    fetch = FakeFetch()
    fetch.contents[10] = data
    _intake(store, 10, len(data))

    step = await _capture(store, fetch, tmp_dir, Clock()).run_once()

    assert step.outcome == CaptureOutcome.KEYED
    ref = _ref(store, 10)
    assert (ref.state, ref.stage, ref.reason, ref.attempts, ref.next_try_at) == ("active", "keyed", None, 0, None)
    assert ref.proved_at == NOW
    media_id = ref.media_id
    assert media_id is not None
    assert media_id == step.media_id
    assert media_id == store.media_for_file_sha256(_sha(data))
    assert _media_row(store, media_id) == (_sha(data[: nc.HEAD_BYTES]), None)
    assert fetch.calls == [(10, "ana", tmp_dir, len(data), capture_module.MAX_CAPTURE_BYTES)]
    assert store.file_ids_for_media(media_id) == [10]


async def test_nothing_due_is_idle_without_a_request(store: Store, tmp_dir: Path) -> None:
    fetch = FakeFetch()

    step = await _capture(store, fetch, tmp_dir, Clock()).run_once()

    assert step.outcome == CaptureOutcome.IDLE
    assert fetch.calls == []


async def test_two_copies_of_the_same_bytes_are_downloaded_twice_and_share_one_media(
    store: Store, tmp_dir: Path
) -> None:
    data = _bytes(70 * KIB)
    fetch = FakeFetch()
    fetch.contents[10] = fetch.contents[11] = data
    # Same prefilter key as well: this plan never attaches by it.
    _intake(store, 10, len(data), prefilter_key=PREFILTER)
    _intake(store, 11, len(data), prefilter_key=PREFILTER, reader="ben")
    capture = _capture(store, fetch, tmp_dir, Clock())

    first = await capture.run_once()
    second = await capture.run_once()

    assert [call[0] for call in fetch.calls] == [10, 11]
    assert [call[1] for call in fetch.calls] == ["ana", "ben"]
    assert first.media_id == second.media_id
    assert store.file_ids_for_media(_ref(store, 10).media_id or 0) == [10, 11]


async def test_a_copy_of_an_orphaned_content_keeps_transcript_and_correction(store: Store, tmp_dir: Path) -> None:
    data = _bytes(100 * KIB)
    fetch = FakeFetch()
    fetch.contents[10] = data
    _intake(store, 10, len(data))
    capture = _capture(store, fetch, tmp_dir, Clock())
    media_id = (await capture.run_once()).media_id
    assert media_id is not None
    words = [Word(start_ms=0, end_ms=400, surface="Haushalt", norm="haushalt", conf=0.9, src="machine")]
    prov = Provenance(
        engine="parakeet",
        model_sha256=MODEL,
        config_version=1,
        profile="balanced",
        level=Level.PREVIEW,
        epoch=0,
        language="de",
        input_file_sha256=_sha(data),
    )
    assert store.publish_version(media_id, prov, words).published
    correction = store.add_correction(
        media_id, 0, 400, "text", "Haushaltsplan", author_uid="ana", base_version_id=None, base_text=None
    )
    before = store.current(media_id)
    # The only copy changes: the content is orphaned (D-02-13).
    other = _bytes(100 * KIB + 1)
    fetch.contents[10] = other
    _intake(store, 10, len(other), etag="e2")
    assert _media_row(store, media_id)[1] is not None
    await capture.run_once()
    assert _ref(store, 10).media_id != media_id

    # A new copy with the old bytes turns up and hangs at the old content.
    fetch.contents[20] = data
    _intake(store, 20, len(data), reader="ben")
    step = await capture.run_once()

    assert step.media_id == media_id
    assert _media_row(store, media_id) == (_sha(data[: nc.HEAD_BYTES]), None)
    assert store.current(media_id) == before
    assert [c.correction_id for c in store.active_corrections(media_id)] == [correction]
    assert store.file_ids_for_media(media_id) == [20]


def _forbidden(reason: str | None = None) -> Callable[[httpx.Request], httpx.Response]:
    headers = {} if reason is None else {nc.REASON_HEADER: reason}
    return lambda _request: httpx.Response(403, headers=headers, content=b"x")


def _status(status: int) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _request: httpx.Response(status, content=b"x")


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("silence", request=request)


def _short(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=_chunks(b"x" * 99))


def _long(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=_chunks(b"x" * 101))


@pytest.mark.parametrize(
    ("handler", "reason", "first_wait"),
    [
        (_forbidden(), nc.READ_DENIED, 60),
        (_status(422), nc.READ_DENIED, 60),
        (_status(404), nc.NOT_FOUND, 60),
        (_timeout, nc.READ_TIMEOUT, 60),
        (_status(500), nc.GATEWAY_FAILED, 60),
        (_status(302), nc.GATEWAY_FAILED, 60),
        (_forbidden("access_control"), nc.ACCESS_CONTROL, 300),
        (_short, nc.SIZE_MISMATCH, 60),
        (_long, nc.SIZE_MISMATCH, 60),
    ],
    ids=["403", "422", "404", "timeout", "500", "302", "access_control", "short", "long"],
)
async def test_every_read_failure_of_the_own_reader_is_unreadable_at_once(
    store: Store,
    tmp_dir: Path,
    handler: Callable[[httpx.Request], httpx.Response],
    reason: str,
    first_wait: int,
) -> None:
    # A keyed sibling with the same prefilter key and the same bytes size.
    sibling = b"x" * 100
    fake = FakeFetch()
    fake.contents[10] = sibling
    _intake(store, 10, 100, prefilter_key=PREFILTER)
    await _capture(store, fake, tmp_dir, Clock()).run_once()
    media_id = _ref(store, 10).media_id
    assert media_id is not None
    _intake(store, 11, 100, prefilter_key=PREFILTER, reader="ben")

    step = await _capture(store, _gateway_fetch(handler), tmp_dir, Clock()).run_once()

    assert step.outcome == CaptureOutcome.UNREADABLE
    assert step.reason == reason
    ref = _ref(store, 11)
    assert (ref.state, ref.stage, ref.reason, ref.attempts) == ("unreadable", "failed", reason, 1)
    assert ref.next_try_at == NOW + first_wait
    assert ref.media_id is None
    assert ref.proved_at is None
    # Never counted, never a hit, not even through the keyed sibling.
    assert store.file_ids_for_media(media_id) == [10]
    assert _active_count(store) == 1
    assert _left(tmp_dir) == []


async def test_a_reference_without_a_reader_is_not_found_without_a_request(store: Store, tmp_dir: Path) -> None:
    fetch = FakeFetch()
    _intake(store, 10, 100, reader=None)

    step = await _capture(store, fetch, tmp_dir, Clock()).run_once()

    assert (step.outcome, step.reason) == (CaptureOutcome.UNREADABLE, nc.NOT_FOUND)
    assert fetch.calls == []
    assert _ref(store, 10).state == "unreadable"


@pytest.mark.parametrize(
    "result",
    [
        nc.FetchResult(sha256=None, size=0, error=None),
        nc.FetchResult(sha256="a" * 64, size=100, error=None, head_sha256=None),
        nc.FetchResult(sha256="A" * 64, size=100, error=None, head_sha256="a" * 64),
        nc.FetchResult(sha256="a" * 64, size=99, error=None, head_sha256="a" * 64),
        nc.FetchResult(sha256="a" * 64, size=100, error="something_new", head_sha256="a" * 64),
    ],
    ids=["no-hash", "no-head", "upper-hex", "wrong-size", "unknown-code"],
)
async def test_anything_but_a_validated_success_is_never_keyed(
    store: Store, tmp_dir: Path, result: nc.FetchResult
) -> None:
    fetch = FakeFetch()
    fetch.results[10] = [result]
    _intake(store, 10, 100)

    step = await _capture(store, fetch, tmp_dir, Clock()).run_once()

    assert step.outcome == CaptureOutcome.UNREADABLE
    ref = _ref(store, 10)
    assert (ref.state, ref.stage, ref.media_id) == ("unreadable", "failed", None)
    assert ref.reason in (nc.GATEWAY_FAILED, nc.SIZE_MISMATCH)


async def test_a_fetch_that_raises_is_gateway_failed_and_leaves_no_claim(store: Store, tmp_dir: Path) -> None:
    async def broken(*_args: object) -> nc.FetchResult:
        raise RuntimeError("bug")

    _intake(store, 10, 100)

    step = await _capture(store, broken, tmp_dir, Clock()).run_once()

    assert (step.outcome, step.reason) == (CaptureOutcome.UNREADABLE, nc.GATEWAY_FAILED)
    assert _ref(store, 10).stage == "failed"


async def test_a_due_retry_that_succeeds_becomes_active_and_keyed(store: Store, tmp_dir: Path) -> None:
    data = b"y" * 100
    fetch = FakeFetch()
    fetch.failing(10, nc.READ_TIMEOUT)
    fetch.contents[10] = data
    _intake(store, 10, 100)
    clock = Clock()
    capture = _capture(store, fetch, tmp_dir, clock)
    assert (await capture.run_once()).outcome == CaptureOutcome.UNREADABLE

    clock.now += 59
    assert (await capture.run_once()).outcome == CaptureOutcome.IDLE
    clock.now += 1
    step = await capture.run_once()

    assert step.outcome == CaptureOutcome.KEYED
    ref = _ref(store, 10)
    assert (ref.state, ref.stage, ref.reason, ref.attempts, ref.next_try_at) == ("active", "keyed", None, 0, None)
    assert len(fetch.calls) == 2


async def test_five_failures_leave_the_reference_failed_without_a_next_try(store: Store, tmp_dir: Path) -> None:
    fetch = FakeFetch()
    fetch.failing(10, nc.READ_DENIED, times=6)
    _intake(store, 10, 100)
    clock = Clock()
    capture = _capture(store, fetch, tmp_dir, clock)
    waits = []
    for _ in range(5):
        before = clock.now
        assert (await capture.run_once()).outcome == CaptureOutcome.UNREADABLE
        ref = _ref(store, 10)
        waits.append(None if ref.next_try_at is None else ref.next_try_at - before)
        clock.now = ref.next_try_at or clock.now

    assert waits == [60, 120, 240, 480, None]
    ref = _ref(store, 10)
    assert (ref.state, ref.stage, ref.attempts) == ("unreadable", "failed", 5)
    clock.now += 365 * 86400
    assert (await capture.run_once()).outcome == CaptureOutcome.IDLE
    assert len(fetch.calls) == 5


async def test_a_change_after_the_last_attempt_starts_over(store: Store, tmp_dir: Path) -> None:
    fetch = FakeFetch()
    fetch.failing(10, nc.READ_DENIED, times=5)
    _intake(store, 10, 100)
    clock = Clock()
    capture = _capture(store, fetch, tmp_dir, clock)
    for _ in range(5):
        await capture.run_once()
        clock.now += 7 * 3600
    fetch.contents[10] = b"z" * 101
    _intake(store, 10, 101, etag="e2")

    step = await capture.run_once()

    assert step.outcome == CaptureOutcome.KEYED
    assert _ref(store, 10).state == "active"


def test_the_backoff_doubles_and_stops_at_six_hours() -> None:
    assert [retry_at(0, n, nc.READ_DENIED) for n in range(5)] == [60, 120, 240, 480, None]
    assert retry_at(0, 0, nc.ACCESS_CONTROL) == 300
    assert retry_at(0, 3, nc.ACCESS_CONTROL) == 300
    assert retry_at(0, 4, nc.ACCESS_CONTROL) is None
    # The cap holds for a larger attempt limit as well.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(capture_module, "MAX_ATTEMPTS", 20)
        assert capture_module.retry_at(0, 12, nc.GATEWAY_FAILED) == 6 * 3600


async def test_excluded_deletes_the_reference(store: Store, tmp_dir: Path) -> None:
    _intake(store, 10, 100)

    step = await _capture(store, _gateway_fetch(_forbidden("excluded")), tmp_dir, Clock()).run_once()

    assert step.outcome == CaptureOutcome.DELETED
    assert store.file_ref(10) is None


@pytest.mark.parametrize(
    ("handler", "reason", "wait"),
    [(_status(423), nc.LOCKED, 120)],
)
async def test_locked_is_pending_again_with_the_same_attempts(
    store: Store, tmp_dir: Path, handler: Callable[[httpx.Request], httpx.Response], reason: str, wait: int
) -> None:
    fetch = FakeFetch()
    fetch.failing(10, nc.READ_DENIED)
    _intake(store, 10, 100)
    clock = Clock()
    await _capture(store, fetch, tmp_dir, clock).run_once()
    clock.now = _ref(store, 10).next_try_at or 0

    step = await _capture(store, _gateway_fetch(handler), tmp_dir, clock).run_once()

    assert (step.outcome, step.reason) == (CaptureOutcome.DEFERRED, reason)
    ref = _ref(store, 10)
    # The state of the earlier failure stays; locked is no verdict on the file.
    assert (ref.state, ref.stage, ref.reason, ref.attempts) == ("unreadable", "pending", reason, 1)
    assert ref.next_try_at == clock.now + wait


async def test_locked_on_a_new_reference_keeps_it_active_and_pending(store: Store, tmp_dir: Path) -> None:
    _intake(store, 10, 100)

    step = await _capture(store, _gateway_fetch(_status(423)), tmp_dir, Clock()).run_once()

    assert step.outcome == CaptureOutcome.DEFERRED
    ref = _ref(store, 10)
    assert (ref.state, ref.stage, ref.attempts, ref.next_try_at) == ("active", "pending", 0, NOW + 120)
    assert (await _capture(store, FakeFetch(), tmp_dir, Clock(NOW + 119)).run_once()).outcome == CaptureOutcome.IDLE


async def test_disk_full_waits_without_a_request_and_without_a_verdict(
    store: Store, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: 0)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"x" * 100)

    _intake(store, 10, 100)

    step = await _capture(store, _gateway_fetch(handler), tmp_dir, Clock()).run_once()

    assert (step.outcome, step.reason) == (CaptureOutcome.DEFERRED, nc.DISK_FULL)
    ref = _ref(store, 10)
    assert (ref.state, ref.stage, ref.attempts, ref.next_try_at) == ("active", "pending", 0, NOW + 300)
    assert calls == []


async def test_too_large_is_failed_without_a_request_and_without_a_retry(store: Store, tmp_dir: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"x" * 100)

    _intake(store, 10, 100)

    step = await _capture(store, _gateway_fetch(handler), tmp_dir, Clock(), max_bytes=99).run_once()

    assert (step.outcome, step.reason) == (CaptureOutcome.FAILED, nc.TOO_LARGE)
    ref = _ref(store, 10)
    assert (ref.state, ref.stage, ref.next_try_at, ref.media_id) == ("active", "failed", None, None)
    assert calls == []


async def test_a_reference_changed_during_the_download_keeps_the_new_values(store: Store, tmp_dir: Path) -> None:
    old = b"o" * 100

    async def fetch(file_id: int, *_args: object) -> nc.FetchResult:
        # The intake writes a new version while the old bytes are on the way.
        _intake(store, file_id, 120, etag="e2")
        return nc.FetchResult(sha256=_sha(old), size=100, error=None, head_sha256=_sha(old))

    _intake(store, 10, 100)

    step = await _capture(store, fetch, tmp_dir, Clock()).run_once()

    assert step.outcome == CaptureOutcome.STALE
    ref = _ref(store, 10)
    assert (ref.stage, ref.media_id, ref.etag, ref.size) == ("pending", None, "e2", 120)
    assert store._conn.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 0


async def test_a_failure_of_a_reference_changed_meanwhile_is_not_written(store: Store, tmp_dir: Path) -> None:
    async def fetch(file_id: int, *_args: object) -> nc.FetchResult:
        _intake(store, file_id, 120, etag="e2")
        return nc.FetchResult(sha256=None, size=0, error=nc.READ_DENIED)

    _intake(store, 10, 100)

    step = await _capture(store, fetch, tmp_dir, Clock()).run_once()

    assert step.outcome == CaptureOutcome.STALE
    ref = _ref(store, 10)
    assert (ref.state, ref.stage, ref.attempts) == ("active", "pending", 0)


@pytest.mark.parametrize("state", ["vanished", "trashed"])
async def test_references_that_may_not_count_are_never_fetched(store: Store, tmp_dir: Path, state: str) -> None:
    store.upsert_file_ref(10, None, storage_id=3, etag="e", size=1, mtime=1, state=state, stage="pending", reason=None)
    fetch = FakeFetch()

    assert (await _capture(store, fetch, tmp_dir, Clock()).run_once()).outcome == CaptureOutcome.IDLE
    assert fetch.calls == []


async def test_a_file_with_only_a_sample_is_never_fetched(store: Store, tmp_dir: Path) -> None:
    store.put_sample(10, store.media_for_file_sha256("a" * 64))  # D-02-15: a sample is no reference
    fetch = FakeFetch()

    assert (await _capture(store, fetch, tmp_dir, Clock()).run_once()).outcome == CaptureOutcome.IDLE
    assert fetch.calls == []


async def test_new_references_come_before_due_retries(store: Store, tmp_dir: Path) -> None:
    fetch = FakeFetch()
    fetch.failing(5, nc.READ_DENIED)
    fetch.contents[5] = fetch.contents[10] = b"q" * 10
    _intake(store, 5, 10)
    clock = Clock()
    capture = _capture(store, fetch, tmp_dir, clock)
    await capture.run_once()
    _intake(store, 10, 10)
    clock.now += 3600

    await capture.run_once()

    assert [call[0] for call in fetch.calls] == [5, 10]


async def test_prepare_removes_part_files_and_hands_back_claims(store: Store, tmp_dir: Path) -> None:
    (tmp_dir / "0123.part").write_bytes(b"left over")
    _intake(store, 10, 100)
    assert store.next_capture(NOW) is not None
    assert _ref(store, 10).stage == "fetching"

    await _capture(store, FakeFetch(), tmp_dir, Clock()).prepare()

    assert _left(tmp_dir) == []
    assert _ref(store, 10).stage == "pending"


async def test_prepare_creates_the_temporary_directory(store: Store, tmp_path: Path) -> None:
    directory = tmp_path / "volume" / "tmp"

    await _capture(store, FakeFetch(), directory, Clock()).prepare()

    assert directory.is_dir()


def test_the_temporary_directory_lies_under_the_volume(tmp_path: Path) -> None:
    assert capture_module.tmp_dir() == tmp_path / "tmp"


async def test_two_steps_at_once_still_read_one_file_at_a_time(store: Store, tmp_dir: Path) -> None:
    running = 0
    peak = 0

    async def fetch(file_id: int, *_args: object) -> nc.FetchResult:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1
        data = b"p" * 10 + bytes([file_id])
        return nc.FetchResult(sha256=_sha(data), size=11, error=None, head_sha256=_sha(data))

    for file_id in (10, 11, 12):
        _intake(store, file_id, 11)
    capture = _capture(store, fetch, tmp_dir, Clock())

    steps = await asyncio.gather(capture.run_once(), capture.run_once(), capture.run_once())

    assert peak == 1
    assert sorted(step.file_id or 0 for step in steps) == [10, 11, 12]


async def test_the_loop_steps_only_while_the_companion_is_ok(
    store: Store, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch = FakeFetch()
    fetch.contents[10] = b"a" * 10
    _intake(store, 10, 10)
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(companion, "current", lambda: companion.CompanionState(companion.UNKNOWN, None, None))
    await _capture(store, fetch, tmp_dir, Clock()).run_forever(sleep=sleep, rounds=2)
    assert fetch.calls == []
    assert sleeps == [15.0, 15.0]

    sleeps.clear()
    monkeypatch.setattr(companion, "current", lambda: companion.CompanionState(companion.OK, "0.2.0", 0.0))
    await _capture(store, fetch, tmp_dir, Clock()).run_forever(sleep=sleep, rounds=2)
    # Work first without a pause, then nothing due and a pause.
    assert [call[0] for call in fetch.calls] == [10]
    assert sleeps == [15.0]


async def test_a_failing_step_does_not_end_the_loop(
    store: Store, tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(companion, "current", lambda: companion.CompanionState(companion.OK, "0.2.0", 0.0))
    capture = _capture(store, FakeFetch(), tmp_dir, Clock())
    calls = 0

    async def broken() -> object:
        nonlocal calls
        calls += 1
        raise RuntimeError("store gone")

    monkeypatch.setattr(capture, "run_once", broken)
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    await capture.run_forever(sleep=sleep, rounds=3)

    assert calls == 3
    assert sleeps == [15.0, 15.0, 15.0]


async def test_the_capture_logs_never_name_the_reader(
    store: Store, tmp_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _intake(store, 10, 100, reader="geheime-leserin")
    _intake(store, 11, 100, reader="geheime-leserin")
    fake = FakeFetch()
    fake.contents[11] = b"k" * 100
    with caplog.at_level(logging.DEBUG):
        await _capture(store, _gateway_fetch(_forbidden()), tmp_dir, Clock()).run_once()
        await _capture(store, fake, tmp_dir, Clock()).run_once()

    own = [record for record in caplog.records if record.name.startswith("audio_video_search_backend")]
    assert own
    assert all("geheime-leserin" not in repr(vars(record)) for record in own)
