"""The read proof of a further copy and the renewed proof (plan 02-13, D-02-01a, D-02-10, D-02-12).

A copy with the prefilter key of a keyed reference may hang at that content
only after its OWN read proof: the first 64 KiB through its own file id and its
own reader, within a time limit, with exactly ``min(65536, size)`` bytes and the
sha256 of the head of the content. Findling measurement A6 is the reason: an
SMB server lists a file it denies, ``isReadable()`` says yes, only the read
fails or hangs.

Part 1 tests nc.fetch_head against an httpx MockTransport, part 2 the verdict
(read_proof.prove_read), part 3 the circuit per storage, part 4 the stage
(worker/capture.py) against a real state.db. Nearly all of it is negative
tests; POSITIVE CONTROL B at the end shows that the same denied copy attaches
as soon as the verdict is replaced, so the negative tests can see the leak.
"""

import asyncio
import hashlib
import logging
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from audio_video_search_backend import nc
from audio_video_search_backend.api import Services
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.store.repo import FileRef, IntakeItem, Store
from audio_video_search_backend.worker import capture as capture_module
from audio_video_search_backend.worker import read_proof
from audio_video_search_backend.worker.capture import Capture, CaptureOutcome
from audio_video_search_backend.worker.read_proof import ProofOutcome, StorageBreaker, prove_read

KIB = 1024
NOW = 1_800_000_000
PREFILTER = "c" * 64
OTHER_PREFILTER = "e" * 64
HIDDEN_PATH = "/very/secret/path/recording.mp4"
# Every user has a storage of their own for the same share.
STORAGE_ANA = 3
STORAGE_BEN = 4
STORAGE_CEM = 5


def _bytes(size: int, seed: bytes = b"seed") -> bytes:
    block = hashlib.sha256(seed).digest()
    out = bytearray()
    counter = 0
    while len(out) < size:
        out += hashlib.sha256(block + counter.to_bytes(8, "big")).digest()
        counter += 1
    return bytes(out[:size])


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _head(data: bytes) -> str:
    return _sha(data[: nc.HEAD_BYTES])


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "tmp"
    directory.mkdir()
    return directory


@pytest.fixture(autouse=True)
def plenty_of_space(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: 1024**4)


# Part 1: the head of a file through the gateway.


async def _fetch_head(handler: Callable[[httpx.Request], Any], file_id: int = 42, user: str = "ben") -> nc.HeadResult:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await nc.fetch_head(file_id, user, client=client)


async def test_the_head_is_hashed_and_counted_and_asked_as_the_reader() -> None:
    data = _bytes(200 * KIB)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=data[: nc.HEAD_BYTES])

    result = await _fetch_head(handler)

    assert result == nc.HeadResult(sha256=_head(data), length=nc.HEAD_BYTES, error=None, status=200)
    request = seen[0]
    assert request.url.path == "/ocs/v2.php/apps/audio_video_search/files/42/head"
    assert request.url.params["userId"] == "ben"
    assert request.headers["EX-APP-ID"] == "audio_video_search_backend"
    assert "AUTHORIZATION-APP-API" in request.headers


@pytest.mark.parametrize("size", [0, 1, 10 * KIB, nc.HEAD_BYTES - 1])
async def test_a_short_file_has_a_short_head(size: int) -> None:
    data = _bytes(size)

    result = await _fetch_head(lambda _request: httpx.Response(200, content=data))

    assert (result.sha256, result.length, result.error) == (_sha(data), size, None)


async def test_one_byte_more_than_the_head_is_refused_by_its_declared_length() -> None:
    data = _bytes(nc.HEAD_BYTES + 1)

    result = await _fetch_head(lambda _request: httpx.Response(200, content=data))

    assert (result.sha256, result.error) == (None, nc.HEAD_TOO_LONG)


async def test_one_byte_more_than_the_head_is_refused_in_a_stream_without_a_length() -> None:
    data = _bytes(nc.HEAD_BYTES + 1)

    async def body() -> AsyncIterator[bytes]:
        yield data[: 40 * KIB]
        yield data[40 * KIB :]

    result = await _fetch_head(lambda _request: httpx.Response(200, content=body()))

    assert (result.sha256, result.error) == (None, nc.HEAD_TOO_LONG)


@pytest.mark.parametrize(
    ("status", "reason", "error"),
    [
        (403, None, nc.READ_DENIED),
        (403, "access_control", nc.ACCESS_CONTROL),
        (403, "excluded", nc.EXCLUDED),
        (422, None, nc.READ_DENIED),
        (423, "locked", nc.LOCKED),
        (404, None, nc.NOT_FOUND),
        (404, "access_control", nc.NOT_FOUND),
        (500, None, nc.GATEWAY_FAILED),
        (401, None, nc.GATEWAY_FAILED),
        (302, None, nc.GATEWAY_FAILED),
        (204, None, nc.GATEWAY_FAILED),
        (206, None, nc.GATEWAY_FAILED),
    ],
)
async def test_every_answer_of_the_head_route_other_than_200_is_a_code_and_never_a_hash(
    status: int, reason: str | None, error: str, caplog: pytest.LogCaptureFixture
) -> None:
    headers = {} if reason is None else {nc.REASON_HEADER: reason}

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers=headers | {"Location": HIDDEN_PATH}, content=b"x" * 10)

    with caplog.at_level(logging.DEBUG):
        result = await _fetch_head(handler, user="geheime-leserin")

    assert (result.sha256, result.error, result.status) == (None, error, status)
    own = [record for record in caplog.records if record.name.startswith("audio_video_search_backend")]
    assert own
    for record in own:
        line = repr(vars(record))
        assert "geheime-leserin" not in line
        assert HIDDEN_PATH not in line


async def test_a_head_that_hangs_ends_at_the_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nc, "HEAD_DEADLINE_SECONDS", 0.2)

    async def handler(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(30)
        return httpx.Response(200, content=b"x")

    started = time.monotonic()
    result = await _fetch_head(handler)

    assert (result.sha256, result.error) == (None, nc.READ_TIMEOUT)
    assert time.monotonic() - started < 5


async def test_a_head_that_trickles_ends_at_the_deadline_too(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nc, "HEAD_DEADLINE_SECONDS", 0.2)

    async def body() -> AsyncIterator[bytes]:
        for _ in range(200):
            yield b"x"
            await asyncio.sleep(0.05)

    result = await _fetch_head(lambda _request: httpx.Response(200, content=body()))

    assert (result.sha256, result.error) == (None, nc.READ_TIMEOUT)


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (httpx.ReadTimeout("silence"), nc.READ_TIMEOUT),
        (httpx.ConnectTimeout("slow"), nc.READ_TIMEOUT),
        (httpx.ConnectError("refused"), nc.GATEWAY_FAILED),
        (httpx.RemoteProtocolError("closed"), nc.GATEWAY_FAILED),
    ],
)
async def test_a_network_error_of_the_head_is_a_code(exception: Exception, error: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise exception

    result = await _fetch_head(handler)

    assert (result.sha256, result.error) == (None, error)


def test_the_time_limits_of_the_head() -> None:
    assert nc.HEAD_TIMEOUT.connect == 10.0
    assert nc.HEAD_TIMEOUT.read == 30.0
    assert nc.HEAD_DEADLINE_SECONDS == 45.0
    assert nc.HEAD_BYTES == 65536


# Part 2: the verdict.


def _reference(size: int = 200 * KIB, *, file_id: int = 11, reader: str | None = "ben") -> FileRef:
    return FileRef(
        file_id=file_id,
        media_id=None,
        storage_id=STORAGE_BEN,
        prefilter_key=PREFILTER,
        reader_uid=reader,
        etag="e1",
        size=size,
        mtime=1_700_000_000,
        state="active",
        stage="fetching",
        reason=None,
        attempts=0,
        next_try_at=None,
        proved_at=None,
        vanished_since=None,
        updated_at=NOW,
    )


class FakeHead:
    """The head route as the capture sees it: the head of the bytes per file id, or scripted results first."""

    def __init__(self) -> None:
        self.contents: dict[int, bytes] = {}
        self.results: dict[int, list[nc.HeadResult]] = {}
        self.calls: list[tuple[int, str]] = []

    async def __call__(self, file_id: int, user_id: str) -> nc.HeadResult:
        self.calls.append((file_id, user_id))
        scripted = self.results.get(file_id)
        if scripted:
            return scripted.pop(0)
        head = self.contents[file_id][: nc.HEAD_BYTES]
        return nc.HeadResult(sha256=_sha(head), length=len(head), error=None, status=200)

    def failing(self, file_id: int, error: str, times: int = 1) -> None:
        self.results.setdefault(file_id, []).extend(
            nc.HeadResult(sha256=None, length=0, error=error) for _ in range(times)
        )

    def answering(self, file_id: int, sha256: str | None, length: int) -> None:
        self.results.setdefault(file_id, []).append(nc.HeadResult(sha256=sha256, length=length, error=None, status=200))


async def test_the_same_head_with_the_right_length_is_ok_and_asked_as_the_copy() -> None:
    data = _bytes(200 * KIB)
    head = FakeHead()
    head.contents[11] = data

    outcome = await prove_read(_reference(), _head(data), nc.HEAD_BYTES, head)

    assert outcome is ProofOutcome.OK
    # The file id and the reader of THE COPY, never those of the sibling.
    assert head.calls == [(11, "ben")]


async def test_a_file_below_64_kib_is_proved_with_its_whole_length() -> None:
    data = _bytes(10 * KIB)
    head = FakeHead()
    head.contents[11] = data

    assert await prove_read(_reference(len(data)), _sha(data), len(data), head) is ProofOutcome.OK


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        (nc.READ_DENIED, ProofOutcome.READ_DENIED),
        (nc.NOT_FOUND, ProofOutcome.READ_DENIED),
        (nc.EXCLUDED, ProofOutcome.READ_DENIED),
        (nc.ACCESS_CONTROL, ProofOutcome.ACCESS_CONTROL),
        (nc.LOCKED, ProofOutcome.LOCKED),
        (nc.READ_TIMEOUT, ProofOutcome.READ_TIMEOUT),
        (nc.GATEWAY_FAILED, ProofOutcome.GATEWAY_FAILED),
        (nc.HEAD_TOO_LONG, ProofOutcome.GATEWAY_FAILED),
        (nc.SIZE_MISMATCH, ProofOutcome.GATEWAY_FAILED),
        ("something_new", ProofOutcome.GATEWAY_FAILED),
        ("ok", ProofOutcome.GATEWAY_FAILED),
    ],
)
async def test_every_refusal_of_the_head_is_its_outcome_and_never_ok(error: str, outcome: ProofOutcome) -> None:
    data = _bytes(200 * KIB)
    head = FakeHead()
    # Even with the right hash beside the error: an error is never a proof.
    head.results[11] = [nc.HeadResult(sha256=_head(data), length=nc.HEAD_BYTES, error=error, status=403)]

    assert await prove_read(_reference(), _head(data), nc.HEAD_BYTES, head) is outcome


async def test_other_bytes_are_a_head_mismatch() -> None:
    data = _bytes(200 * KIB)
    head = FakeHead()
    head.contents[11] = _bytes(200 * KIB, b"other")

    assert await prove_read(_reference(), _head(data), nc.HEAD_BYTES, head) is ProofOutcome.HEAD_MISMATCH


@pytest.mark.parametrize(
    ("size", "length"),
    [
        (200 * KIB, nc.HEAD_BYTES - 1),
        (200 * KIB, nc.HEAD_BYTES + 1),
        (200 * KIB, 0),
        (100, 99),
        (100, 101),
        (100, nc.HEAD_BYTES),
    ],
)
async def test_a_head_of_another_length_is_gateway_failed_even_with_the_right_hash(size: int, length: int) -> None:
    data = _bytes(size)
    head = FakeHead()
    head.answering(11, _head(data), length)

    outcome = await prove_read(_reference(size), _head(data), min(nc.HEAD_BYTES, size), head)

    assert outcome is ProofOutcome.GATEWAY_FAILED


async def test_an_expected_length_other_than_the_one_of_the_reference_is_gateway_failed() -> None:
    data = _bytes(200 * KIB)
    head = FakeHead()
    # The caller asks for 100 bytes and the answer has 100 bytes: still no proof,
    # the head of this reference is min(65536, size) long.
    head.answering(11, _sha(data[:100]), 100)

    assert await prove_read(_reference(), _sha(data[:100]), 100, head) is ProofOutcome.GATEWAY_FAILED


@pytest.mark.parametrize("sha", [None, "", "A" * 64, "a" * 63, "g" * 64])
async def test_an_answer_without_a_valid_hash_is_gateway_failed(sha: str | None) -> None:
    head = FakeHead()
    head.answering(11, sha, nc.HEAD_BYTES)

    assert await prove_read(_reference(), "a" * 64, nc.HEAD_BYTES, head) is ProofOutcome.GATEWAY_FAILED


async def test_a_fetch_that_raises_is_gateway_failed() -> None:
    async def broken(_file_id: int, _user_id: str) -> nc.HeadResult:
        raise RuntimeError("bug")

    assert await prove_read(_reference(), "a" * 64, nc.HEAD_BYTES, broken) is ProofOutcome.GATEWAY_FAILED


async def test_without_a_reader_there_is_no_proof_and_no_request() -> None:
    head = FakeHead()
    head.contents[11] = _bytes(200 * KIB)

    outcome = await prove_read(_reference(reader=None), _head(head.contents[11]), nc.HEAD_BYTES, head)

    assert outcome is ProofOutcome.READ_DENIED
    assert head.calls == []


@pytest.mark.parametrize("media_head", ["", "A" * 64, "a" * 63])
async def test_a_content_without_a_valid_head_cannot_be_proved_against(media_head: str) -> None:
    head = FakeHead()
    head.contents[11] = _bytes(200 * KIB)

    assert await prove_read(_reference(), media_head, nc.HEAD_BYTES, head) is ProofOutcome.HEAD_MISMATCH
    assert head.calls == []


def test_the_head_length_of_a_reference() -> None:
    assert read_proof.head_length(0) == 0
    assert read_proof.head_length(100) == 100
    assert read_proof.head_length(nc.HEAD_BYTES) == nc.HEAD_BYTES
    assert read_proof.head_length(nc.HEAD_BYTES + 1) == nc.HEAD_BYTES


def test_the_outcomes_are_the_closed_list_of_the_plan() -> None:
    assert {outcome.value for outcome in ProofOutcome} == {
        "ok",
        "read_denied",
        "read_timeout",
        "access_control",
        "locked",
        "gateway_failed",
        "head_mismatch",
    }


# Part 3: the circuit per storage.


def test_three_timeouts_in_a_row_open_a_storage_for_an_hour() -> None:
    breaker = StorageBreaker()

    breaker.record(STORAGE_BEN, timed_out=True, now=NOW)
    breaker.record(STORAGE_BEN, timed_out=True, now=NOW + 10)
    assert breaker.closes_at(STORAGE_BEN, NOW + 10) is None
    breaker.record(STORAGE_BEN, timed_out=True, now=NOW + 20)

    assert breaker.closes_at(STORAGE_BEN, NOW + 20) == NOW + 20 + 3600
    assert breaker.closes_at(STORAGE_BEN, NOW + 20 + 3599) == NOW + 20 + 3600
    # Another storage keeps running.
    assert breaker.closes_at(STORAGE_ANA, NOW + 20) is None
    # At the closing time it is asked again, and three new timeouts are needed.
    assert breaker.closes_at(STORAGE_BEN, NOW + 20 + 3600) is None
    breaker.record(STORAGE_BEN, timed_out=True, now=NOW + 4000)
    breaker.record(STORAGE_BEN, timed_out=True, now=NOW + 4001)
    assert breaker.closes_at(STORAGE_BEN, NOW + 4001) is None


def test_an_answer_between_two_timeouts_starts_the_count_again() -> None:
    breaker = StorageBreaker()

    breaker.record(STORAGE_BEN, timed_out=True, now=NOW)
    breaker.record(STORAGE_BEN, timed_out=True, now=NOW)
    breaker.record(STORAGE_BEN, timed_out=False, now=NOW)
    breaker.record(STORAGE_BEN, timed_out=True, now=NOW)
    breaker.record(STORAGE_BEN, timed_out=True, now=NOW)

    assert breaker.closes_at(STORAGE_BEN, NOW) is None
    # Timeouts of two storages are counted apart.
    breaker.record(STORAGE_CEM, timed_out=True, now=NOW)
    assert breaker.closes_at(STORAGE_BEN, NOW) is None
    assert breaker.closes_at(STORAGE_CEM, NOW) is None


# Part 4: the stage, against a real state.db.


class Clock:
    def __init__(self, now: int = NOW) -> None:
        self.now = now

    def __call__(self) -> float:
        return float(self.now)


class FakeFetch:
    """The full download: bytes per file id, or scripted results first."""

    def __init__(self) -> None:
        self.contents: dict[int, bytes] = {}
        self.results: dict[int, list[nc.FetchResult]] = {}
        self.calls: list[int] = []
        self.readers: list[str] = []

    async def __call__(self, file_id: int, user_id: str, _directory: Path, _size: int, _cap: int) -> nc.FetchResult:
        self.calls.append(file_id)
        self.readers.append(user_id)
        scripted = self.results.get(file_id)
        if scripted:
            return scripted.pop(0)
        data = self.contents[file_id]
        return nc.FetchResult(sha256=_sha(data), size=len(data), error=None, head_sha256=_head(data))

    def failing(self, file_id: int, error: str, times: int = 1) -> None:
        self.results.setdefault(file_id, []).extend(
            nc.FetchResult(sha256=None, size=0, error=error) for _ in range(times)
        )


class Stage:
    """One capture over one state.db with a fake gateway, a fake head route and a clock."""

    def __init__(self, store: Store, directory: Path) -> None:
        self.store = store
        self.fetch = FakeFetch()
        self.head = FakeHead()
        self.clock = Clock()
        self.breaker = StorageBreaker()
        self.capture = Capture(
            Services(store=store, index=cast("SearchIndex", None)),
            directory=directory,
            fetch=self.fetch,
            head=self.head,
            clock=self.clock,
            breaker=self.breaker,
        )

    def put(self, file_id: int, data: bytes) -> None:
        """The bytes the gateway and the head route serve for a file id."""
        self.fetch.contents[file_id] = data
        self.head.contents[file_id] = data

    def intake(
        self,
        file_id: int,
        size: int,
        *,
        reader: str | None,
        storage: int,
        prefilter: str | None = PREFILTER,
        etag: str = "e1",
    ) -> None:
        item = IntakeItem(
            queue_id=file_id,
            kind="content",
            file_id=file_id,
            storage_id=storage,
            etag=etag,
            size=size,
            mtime=1_700_000_000,
            prefilter_key=prefilter,
            reader_uid=reader,
        )
        self.store.apply_intake([item])

    async def step(self) -> capture_module.CaptureStep:
        return await self.capture.run_once()

    def ref(self, file_id: int) -> FileRef:
        ref = self.store.file_ref(file_id)
        assert ref is not None
        return ref

    def hits(self, media_id: int | None) -> list[int]:
        assert media_id is not None
        return self.store.file_ids_for_media(media_id)

    async def keyed_sibling(self, data: bytes, file_id: int = 10) -> int:
        """Ana's copy, downloaded in full and keyed; returns its content."""
        self.put(file_id, data)
        self.intake(file_id, len(data), reader="ana", storage=STORAGE_ANA)
        step = await self.step()
        assert step.outcome == CaptureOutcome.KEYED
        assert step.media_id is not None
        return step.media_id

    def renew(
        self, file_id: int, media_id: int, size: int, *, reader: str | None = "cem", storage: int = STORAGE_CEM
    ) -> None:
        """What plan 15 and plan 20 leave behind: an attached reference whose proof is due again."""
        self.store.upsert_file_ref(
            file_id,
            media_id,
            storage_id=storage,
            prefilter_key=PREFILTER,
            reader_uid=reader,
            etag="e1",
            size=size,
            mtime=1_700_000_000,
            state="active",
            stage="probing",
            reason=None,
            proved_at=NOW - 8 * 86400,
        )


@pytest.fixture
def stage(store: Store, tmp_dir: Path) -> Stage:
    return Stage(store, tmp_dir)


def _orphaned_at(store: Store, media_id: int) -> int | None:
    return store._conn.execute("SELECT orphaned_at FROM media WHERE media_id = ?", (media_id,)).fetchone()[0]


def _gateway_head(handler: Callable[[httpx.Request], Any]) -> Any:
    """The real nc.fetch_head behind a MockTransport, as the head route of the capture."""

    async def head(file_id: int, user_id: str) -> nc.HeadResult:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await nc.fetch_head(file_id, user_id, client=client)

    return head


async def test_a_copy_attaches_after_its_own_proof_without_a_download(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.put(11, data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)
    stage.clock.now += 5

    step = await stage.step()

    assert (step.outcome, step.file_id, step.media_id) == (CaptureOutcome.KEYED, 11, media_id)
    assert stage.fetch.calls == [10]
    assert stage.head.calls == [(11, "ben")]
    ref = stage.ref(11)
    assert (ref.media_id, ref.state, ref.stage, ref.reason, ref.attempts, ref.next_try_at) == (
        media_id,
        "active",
        "keyed",
        None,
        0,
        None,
    )
    assert ref.proved_at == NOW + 5
    assert stage.hits(media_id) == [10, 11]


async def test_a_copy_below_64_kib_attaches_after_its_proof(stage: Stage) -> None:
    data = _bytes(10 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.put(11, data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)

    assert (await stage.step()).outcome == CaptureOutcome.KEYED
    assert stage.fetch.calls == [10]
    assert stage.hits(media_id) == [10, 11]


def _forbidden(reason: str | None = None) -> Callable[[httpx.Request], httpx.Response]:
    headers = {} if reason is None else {nc.REASON_HEADER: reason}
    return lambda _request: httpx.Response(403, headers=headers, content=b"x")


def _status(status: int) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _request: httpx.Response(status, content=b"x")


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("silence", request=request)


def _too_long(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=b"x" * (nc.HEAD_BYTES + 1))


def _one_byte_short(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=_bytes(nc.HEAD_BYTES - 1))


@pytest.mark.parametrize(
    ("handler", "reason", "wait"),
    [
        (_forbidden(), nc.READ_DENIED, 60),
        (_status(422), nc.READ_DENIED, 60),
        (_status(404), nc.READ_DENIED, 60),
        (_forbidden("access_control"), nc.ACCESS_CONTROL, 300),
        (_status(500), nc.GATEWAY_FAILED, 60),
        (_status(302), nc.GATEWAY_FAILED, 60),
        (_timeout, nc.READ_TIMEOUT, 60),
        (_too_long, nc.GATEWAY_FAILED, 60),
        (_one_byte_short, nc.GATEWAY_FAILED, 60),
    ],
    ids=["403", "422", "404", "access_control", "500", "302", "timeout", "65537", "short"],
)
async def test_a_copy_whose_proof_fails_is_unreadable_and_never_attached(
    stage: Stage, handler: Callable[[httpx.Request], httpx.Response], reason: str, wait: int
) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    # The listing says ben has the same file; only his own read tells the truth (A6).
    stage.put(11, data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)
    stage.capture._head = _gateway_head(handler)

    step = await stage.step()

    assert (step.outcome, step.reason) == (CaptureOutcome.UNREADABLE, reason)
    ref = stage.ref(11)
    assert (ref.state, ref.stage, ref.reason, ref.attempts) == ("unreadable", "failed", reason, 1)
    assert ref.next_try_at == NOW + wait
    assert ref.media_id is None
    assert ref.proved_at is None
    assert stage.hits(media_id) == [10]
    # No download either: the copy is judged by its proof.
    assert stage.fetch.calls == [10]


async def test_a_copy_whose_head_hangs_is_read_timeout_within_the_deadline(
    stage: Stage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(nc, "HEAD_DEADLINE_SECONDS", 0.2)
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)

    async def hang(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(30)
        return httpx.Response(200, content=data[: nc.HEAD_BYTES])

    stage.capture._head = _gateway_head(hang)
    started = time.monotonic()

    step = await stage.step()

    assert time.monotonic() - started < 5
    assert (step.outcome, step.reason) == (CaptureOutcome.UNREADABLE, nc.READ_TIMEOUT)
    assert stage.ref(11).media_id is None
    assert stage.hits(media_id) == [10]


async def test_a_locked_head_waits_without_a_verdict_and_without_attaching(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)
    stage.head.failing(11, nc.LOCKED)

    step = await stage.step()

    assert (step.outcome, step.reason) == (CaptureOutcome.DEFERRED, nc.LOCKED)
    ref = stage.ref(11)
    assert (ref.state, ref.stage, ref.attempts, ref.next_try_at, ref.media_id) == (
        "active",
        "pending",
        0,
        NOW + 120,
        None,
    )
    assert stage.hits(media_id) == [10]


async def test_other_bytes_behind_the_same_prefilter_key_get_their_own_download(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    other = _bytes(200 * KIB, b"other")
    stage.put(11, other)
    stage.intake(11, len(other), reader="ben", storage=STORAGE_BEN)

    step = await stage.step()

    assert step.outcome == CaptureOutcome.KEYED
    assert stage.head.calls == [(11, "ben")]
    assert stage.fetch.calls == [10, 11]
    assert stage.fetch.readers == ["ana", "ben"]
    own = stage.ref(11).media_id
    assert own is not None
    assert own != media_id
    assert own == stage.store.media_for_file_sha256(_sha(other))
    assert stage.hits(media_id) == [10]
    assert stage.hits(own) == [11]


async def test_a_mismatch_whose_download_fails_is_unreadable(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.head.contents[11] = _bytes(200 * KIB, b"other")
    stage.fetch.failing(11, nc.READ_DENIED)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)

    step = await stage.step()

    assert (step.outcome, step.reason) == (CaptureOutcome.UNREADABLE, nc.READ_DENIED)
    assert stage.ref(11).media_id is None
    assert stage.hits(media_id) == [10]


@pytest.mark.parametrize("state", ["unreadable", "vanished", "trashed"])
async def test_a_sibling_that_is_not_active_is_no_sibling(stage: Stage, state: str) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.store.upsert_file_ref(
        10,
        media_id,
        storage_id=STORAGE_ANA,
        prefilter_key=PREFILTER,
        reader_uid="ana",
        etag="e1",
        size=len(data),
        mtime=1_700_000_000,
        state=state,
        stage="keyed",
        reason=None,
    )
    stage.put(11, data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)

    step = await stage.step()

    # No proof against a content nobody is proved to read: the copy is read in full.
    assert step.outcome == CaptureOutcome.KEYED
    assert stage.head.calls == []
    assert stage.fetch.calls == [10, 11]


@pytest.mark.parametrize("sibling_stage", ["pending", "probing", "failed"])
async def test_a_sibling_that_is_not_keyed_is_no_sibling(stage: Stage, sibling_stage: str) -> None:
    data = _bytes(200 * KIB)
    media_id = stage.store.media_for_file_sha256(_sha(data))
    stage.store._conn.execute("UPDATE media SET head_sha256 = ? WHERE media_id = ?", (_head(data), media_id))
    stage.store.upsert_file_ref(
        10,
        media_id,
        storage_id=STORAGE_ANA,
        prefilter_key=PREFILTER,
        reader_uid="ana",
        etag="e1",
        size=len(data),
        mtime=1_700_000_000,
        state="active",
        stage=sibling_stage,
        reason=None,
        next_try_at=NOW + 10_000,
    )
    stage.put(11, data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)

    step = await stage.step()

    assert (step.outcome, step.file_id) == (CaptureOutcome.KEYED, 11)
    assert stage.head.calls == []
    assert stage.fetch.calls == [11]


async def test_a_sibling_whose_content_has_no_head_is_no_sibling(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = stage.store.media_for_file_sha256(_sha(data))
    stage.store.upsert_file_ref(
        10,
        media_id,
        storage_id=STORAGE_ANA,
        prefilter_key=PREFILTER,
        reader_uid="ana",
        etag="e1",
        size=len(data),
        mtime=1_700_000_000,
        state="active",
        stage="keyed",
        reason=None,
    )
    stage.put(11, data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)

    step = await stage.step()

    assert step.outcome == CaptureOutcome.KEYED
    assert stage.head.calls == []
    assert stage.fetch.calls == [11]


async def test_a_copy_with_another_prefilter_key_or_none_is_read_in_full(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    await stage.keyed_sibling(data)
    stage.put(11, data)
    stage.put(12, data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN, prefilter=OTHER_PREFILTER)
    stage.intake(12, len(data), reader="cem", storage=STORAGE_CEM, prefilter=None)

    await stage.step()
    await stage.step()

    assert stage.head.calls == []
    assert stage.fetch.calls == [10, 11, 12]


async def test_a_copy_without_a_reader_gets_no_proof_and_no_request(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.put(11, data)
    stage.intake(11, len(data), reader=None, storage=STORAGE_BEN)

    step = await stage.step()

    assert step.outcome == CaptureOutcome.UNREADABLE
    assert stage.head.calls == []
    assert stage.fetch.calls == [10]
    assert (stage.ref(11).state, stage.ref(11).media_id) == ("unreadable", None)
    assert stage.hits(media_id) == [10]


async def test_a_failed_proof_is_tried_again_and_then_attaches(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.put(11, data)
    stage.head.failing(11, nc.READ_TIMEOUT)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)
    assert (await stage.step()).outcome == CaptureOutcome.UNREADABLE

    stage.clock.now += 59
    assert (await stage.step()).outcome == CaptureOutcome.IDLE
    stage.clock.now += 1
    step = await stage.step()

    assert step.outcome == CaptureOutcome.KEYED
    assert stage.fetch.calls == [10]
    assert stage.head.calls == [(11, "ben"), (11, "ben")]
    assert stage.hits(media_id) == [10, 11]


async def test_five_failed_proofs_leave_the_copy_unreadable_without_a_next_try(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.head.failing(11, nc.READ_DENIED, times=6)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)
    waits = []
    for _ in range(5):
        before = stage.clock.now
        assert (await stage.step()).outcome == CaptureOutcome.UNREADABLE
        ref = stage.ref(11)
        waits.append(None if ref.next_try_at is None else ref.next_try_at - before)
        stage.clock.now = ref.next_try_at or stage.clock.now

    assert waits == [60, 120, 240, 480, None]
    stage.clock.now += 365 * 86400
    assert (await stage.step()).outcome == CaptureOutcome.IDLE
    assert len(stage.head.calls) == 5
    assert stage.hits(media_id) == [10]


async def test_there_are_never_two_proofs_at_once(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    await stage.keyed_sibling(data)
    running = 0
    peak = 0

    async def slow(_file_id: int, _user_id: str) -> nc.HeadResult:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1
        return nc.HeadResult(sha256=_head(data), length=nc.HEAD_BYTES, error=None, status=200)

    stage.capture._head = slow
    for file_id, storage in ((11, STORAGE_BEN), (12, STORAGE_CEM), (13, 6)):
        stage.intake(file_id, len(data), reader="x", storage=storage)

    steps = await asyncio.gather(stage.step(), stage.step(), stage.step())

    assert peak == 1
    assert sorted(step.file_id or 0 for step in steps) == [11, 12, 13]
    assert all(step.outcome == CaptureOutcome.KEYED for step in steps)


async def test_a_changed_etag_after_attaching_starts_over_and_follows_the_orphan_rule(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.put(11, data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)
    assert (await stage.step()).outcome == CaptureOutcome.KEYED

    # Ben's copy changes: its content key is unknown again, ana's copy keeps the content alive.
    changed = _bytes(210 * KIB, b"changed")
    stage.put(11, changed)
    stage.intake(11, len(changed), reader="ben", storage=STORAGE_BEN, prefilter=OTHER_PREFILTER, etag="e2")
    ref = stage.ref(11)
    assert (ref.media_id, ref.stage, ref.proved_at) == (None, "pending", None)
    assert stage.hits(media_id) == [10]
    assert _orphaned_at(stage.store, media_id) is None

    step = await stage.step()
    assert step.outcome == CaptureOutcome.KEYED
    assert step.media_id != media_id
    assert stage.fetch.calls == [10, 11]

    # Ana's copy changes too: the old content has no active reference left.
    stage.intake(10, len(changed), reader="ana", storage=STORAGE_ANA, prefilter=OTHER_PREFILTER, etag="e2")
    assert _orphaned_at(stage.store, media_id) is not None


async def test_a_waiting_sibling_is_due_at_once_after_a_full_download(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    stage.put(11, data)
    stage.fetch.failing(11, nc.LOCKED)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)
    assert (await stage.step()).outcome == CaptureOutcome.DEFERRED
    assert stage.ref(11).next_try_at == NOW + 120
    # A copy that failed its own read waits as well, but for its own verdict.
    stage.fetch.failing(12, nc.READ_DENIED)
    stage.intake(12, len(data), reader="cem", storage=STORAGE_CEM)
    assert (await stage.step()).outcome == CaptureOutcome.UNREADABLE
    failed_until = stage.ref(12).next_try_at

    media_id = await stage.keyed_sibling(data)

    assert stage.ref(11).next_try_at is None
    assert stage.ref(12).next_try_at == failed_until
    step = await stage.step()
    assert (step.outcome, step.file_id, step.media_id) == (CaptureOutcome.KEYED, 11, media_id)
    assert stage.head.calls == [(11, "ben")]
    assert stage.fetch.calls == [11, 12, 10]


async def test_a_sibling_that_goes_away_during_the_proof_leaves_the_copy_to_its_own_download(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.put(11, data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)

    async def head(file_id: int, _user_id: str) -> nc.HeadResult:
        # While ben's head is on the way, ana's copy gets a new version.
        stage.intake(10, len(data) + 1, reader="ana", storage=STORAGE_ANA, prefilter=OTHER_PREFILTER, etag="e2")
        return nc.HeadResult(sha256=_head(data), length=nc.HEAD_BYTES, error=None, status=200)

    stage.capture._head = head

    step = await stage.step()

    # Ben read the bytes himself, so he hangs at their content, by his own download.
    assert (step.outcome, step.file_id) == (CaptureOutcome.KEYED, 11)
    assert stage.fetch.calls == [10, 11]
    assert stage.ref(11).media_id == media_id
    assert stage.hits(media_id) == [11]


async def test_a_copy_that_changes_during_the_proof_is_not_attached(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.put(11, data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)

    async def head(file_id: int, _user_id: str) -> nc.HeadResult:
        stage.intake(file_id, len(data) + 5, reader="ben", storage=STORAGE_BEN, prefilter=OTHER_PREFILTER, etag="e2")
        return nc.HeadResult(sha256=_head(data), length=nc.HEAD_BYTES, error=None, status=200)

    stage.capture._head = head

    step = await stage.step()

    assert step.outcome == CaptureOutcome.STALE
    ref = stage.ref(11)
    assert (ref.media_id, ref.stage, ref.etag) == (None, "pending", "e2")
    assert stage.hits(media_id) == [10]
    assert stage.fetch.calls == [10]


async def test_attach_by_proof_is_conditional(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    store = stage.store
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)

    # Not claimed by the capture: nothing is written.
    assert store.attach_by_proof(11, media_id, "e1", NOW) is False
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert claimed.file_id == 11
    # Another etag than the one the proof was made for.
    assert store.attach_by_proof(11, media_id, "e2", NOW) is False
    # A content no keyed sibling with the same prefilter key holds.
    foreign = store.media_for_file_sha256("f" * 64)
    assert store.attach_by_proof(11, foreign, "e1", NOW) is False
    assert stage.ref(11).media_id is None

    assert store.attach_by_proof(11, media_id, "e1", NOW) is True
    # A second attach finds a content already.
    assert store.attach_by_proof(11, media_id, "e1", NOW) is False
    assert stage.hits(media_id) == [10, 11]


async def test_attach_by_proof_never_follows_the_prefilter_key_alone(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    store = stage.store
    # Same content, but ben's copy has another prefilter key: the proof was not made against a sibling.
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN, prefilter=OTHER_PREFILTER)
    stage.intake(12, len(data), reader="cem", storage=STORAGE_CEM, prefilter=None)
    assert store.next_capture(NOW) is not None
    assert store.next_capture(NOW) is not None

    assert store.attach_by_proof(11, media_id, "e1", NOW) is False
    assert store.attach_by_proof(12, media_id, "e1", NOW) is False
    assert stage.hits(media_id) == [10]


# The circuit: a storage that hangs is left alone for an hour, without a single request.


async def test_three_timeouts_pause_every_due_reference_of_the_storage_without_a_request(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    # Three copies on ben's storage S, each head hangs.
    for file_id in (11, 12, 13):
        stage.put(file_id, data)
        stage.head.failing(file_id, nc.READ_TIMEOUT)
        stage.intake(file_id, len(data), reader="ben", storage=STORAGE_BEN)
    for _ in range(3):
        step = await stage.step()
        assert (step.outcome, step.reason) == (CaptureOutcome.UNREADABLE, nc.READ_TIMEOUT)
        stage.clock.now += 1
    opened = stage.clock.now - 1
    closes = opened + 3600
    assert stage.breaker.closes_at(STORAGE_BEN, stage.clock.now) == closes

    # Due on S now: a new proof (14), a renewed proof (15, gives hits so far) and a download (16).
    stage.put(14, data)
    stage.intake(14, len(data), reader="ben", storage=STORAGE_BEN)
    stage.put(15, data)
    stage.renew(15, media_id, len(data), reader="ben", storage=STORAGE_BEN)
    other = _bytes(50 * KIB, b"single")
    stage.put(16, other)
    stage.intake(16, len(other), reader="ben", storage=STORAGE_BEN, prefilter=None)
    # And one on another storage T.
    stage.put(20, other)
    stage.intake(20, len(other), reader="cem", storage=STORAGE_CEM, prefilter=None)
    assert stage.hits(media_id) == [10, 15]
    head_calls = list(stage.head.calls)
    fetch_calls = list(stage.fetch.calls)

    steps = [await stage.step() for _ in range(4)]

    paused = [step.file_id or 0 for step in steps if step.reason == read_proof.STORAGE_PAUSED]
    assert sorted(paused) == [14, 15, 16]
    for file_id in (14, 15, 16):
        ref = stage.ref(file_id)
        assert (ref.state, ref.stage, ref.reason, ref.next_try_at, ref.attempts) == (
            "unreadable",
            "failed",
            "storage_paused",
            closes,
            0,
        )
    # Not one request went to S; T keeps running.
    assert stage.head.calls == head_calls
    assert stage.fetch.calls == [*fetch_calls, 20]
    assert stage.ref(20).stage == "keyed"
    # The hits of the paused renewed proof are gone at once.
    assert stage.hits(media_id) == [10]

    # The three that timed out come due after their 60 s and are paused as well.
    stage.clock.now = opened + 120
    for _ in range(3):
        step = await stage.step()
        assert (step.outcome, step.reason) == (CaptureOutcome.UNREADABLE, read_proof.STORAGE_PAUSED)
    assert (await stage.step()).outcome == CaptureOutcome.IDLE
    assert stage.head.calls == head_calls
    assert [stage.ref(file_id).attempts for file_id in (11, 12, 13)] == [1, 1, 1]

    # One second before the closing time nothing on S is due.
    stage.clock.now = closes - 1
    assert (await stage.step()).outcome == CaptureOutcome.IDLE

    # At the closing time every one of them is checked again.
    stage.clock.now = closes
    outcomes = {}
    for _ in range(6):
        step = await stage.step()
        outcomes[step.file_id] = step.outcome
    assert outcomes == dict.fromkeys((11, 12, 13, 14, 15, 16), CaptureOutcome.KEYED)
    assert stage.hits(media_id) == [10, 11, 12, 13, 14, 15]
    assert stage.ref(15).proved_at == closes
    assert stage.fetch.calls == [*fetch_calls, 20, 16]


async def test_timeouts_of_a_download_count_for_the_circuit_too(stage: Stage) -> None:
    for file_id in (11, 12, 13):
        stage.fetch.failing(file_id, nc.READ_TIMEOUT)
        stage.intake(file_id, 100, reader="ben", storage=STORAGE_BEN, prefilter=None)
    for _ in range(3):
        await stage.step()
    stage.intake(14, 100, reader="ben", storage=STORAGE_BEN, prefilter=None)

    step = await stage.step()

    assert (step.outcome, step.reason) == (CaptureOutcome.UNREADABLE, read_proof.STORAGE_PAUSED)
    assert stage.fetch.calls == [11, 12, 13]


async def test_an_answer_of_the_storage_keeps_the_circuit_closed(stage: Stage) -> None:
    data = _bytes(100)
    for file_id in (11, 12):
        stage.fetch.failing(file_id, nc.READ_TIMEOUT)
        stage.intake(file_id, 100, reader="ben", storage=STORAGE_BEN, prefilter=None)
    stage.fetch.failing(13, nc.READ_DENIED)
    stage.intake(13, 100, reader="ben", storage=STORAGE_BEN, prefilter=None)
    stage.fetch.failing(14, nc.READ_TIMEOUT)
    stage.intake(14, 100, reader="ben", storage=STORAGE_BEN, prefilter=None)
    stage.put(15, data)
    stage.intake(15, 100, reader="ben", storage=STORAGE_BEN, prefilter=None)

    outcomes = [(await stage.step()).outcome for _ in range(5)]

    assert outcomes[-1] == CaptureOutcome.KEYED
    assert stage.fetch.calls == [11, 12, 13, 14, 15]


async def test_no_space_on_the_volume_says_nothing_about_the_storage(stage: Stage) -> None:
    for file_id in (11, 12):
        stage.fetch.failing(file_id, nc.READ_TIMEOUT)
        stage.intake(file_id, 100, reader="ben", storage=STORAGE_BEN, prefilter=None)
    # No request went out for this one, so it neither counts nor clears the count.
    stage.fetch.failing(13, nc.DISK_FULL)
    stage.intake(13, 100, reader="ben", storage=STORAGE_BEN, prefilter=None)
    stage.fetch.failing(14, nc.READ_TIMEOUT)
    stage.intake(14, 100, reader="ben", storage=STORAGE_BEN, prefilter=None)

    for _ in range(4):
        await stage.step()

    assert stage.breaker.closes_at(STORAGE_BEN, NOW) == NOW + 3600


# The renewed proof (D-02-12).


async def test_a_renewed_proof_that_succeeds_confirms_the_reference(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.put(12, data)
    stage.renew(12, media_id, len(data))
    stage.clock.now += 100

    step = await stage.step()

    assert (step.outcome, step.file_id, step.media_id) == (CaptureOutcome.KEYED, 12, media_id)
    ref = stage.ref(12)
    assert (ref.state, ref.stage, ref.media_id, ref.reason, ref.attempts, ref.next_try_at) == (
        "active",
        "keyed",
        media_id,
        None,
        0,
        None,
    )
    assert ref.proved_at == NOW + 100
    assert stage.head.calls == [(12, "cem")]
    assert stage.fetch.calls == [10]
    assert stage.hits(media_id) == [10, 12]


@pytest.mark.parametrize(
    ("error", "reason", "wait", "attempts"),
    [
        (nc.READ_DENIED, nc.READ_DENIED, 60, 1),
        (nc.NOT_FOUND, nc.READ_DENIED, 60, 1),
        (nc.READ_TIMEOUT, nc.READ_TIMEOUT, 60, 1),
        (nc.ACCESS_CONTROL, nc.ACCESS_CONTROL, 300, 1),
        (nc.GATEWAY_FAILED, nc.GATEWAY_FAILED, 60, 1),
        (nc.HEAD_TOO_LONG, nc.GATEWAY_FAILED, 60, 1),
        (nc.LOCKED, nc.LOCKED, 120, 0),
    ],
)
async def test_a_renewed_proof_that_fails_takes_the_hits_away_at_once(
    stage: Stage, error: str, reason: str, wait: int, attempts: int
) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.put(12, data)
    stage.renew(12, media_id, len(data))
    assert stage.hits(media_id) == [10, 12]
    # Samba denies cem the file from now on.
    stage.head.failing(12, error)

    step = await stage.step()

    assert (step.outcome, step.reason) == (CaptureOutcome.UNREADABLE, reason)
    ref = stage.ref(12)
    assert (ref.state, ref.stage, ref.reason, ref.attempts, ref.next_try_at) == (
        "unreadable",
        "failed",
        reason,
        attempts,
        NOW + wait,
    )
    assert stage.hits(media_id) == [10]
    assert stage.fetch.calls == [10]


async def test_a_renewed_proof_that_fails_on_the_last_reference_orphans_the_content_until_it_succeeds(
    stage: Stage,
) -> None:
    data = _bytes(200 * KIB)
    media_id = stage.store.media_for_file_sha256(_sha(data))
    stage.store._conn.execute("UPDATE media SET head_sha256 = ? WHERE media_id = ?", (_head(data), media_id))
    stage.put(12, data)
    stage.renew(12, media_id, len(data))
    stage.head.failing(12, nc.READ_DENIED)

    assert (await stage.step()).outcome == CaptureOutcome.UNREADABLE
    assert stage.hits(media_id) == []
    assert _orphaned_at(stage.store, media_id) == NOW

    # The right comes back: the next try proves again, without a download.
    stage.clock.now += 60
    step = await stage.step()

    assert step.outcome == CaptureOutcome.KEYED
    assert stage.fetch.calls == []
    assert stage.head.calls == [(12, "cem"), (12, "cem")]
    assert stage.hits(media_id) == [12]
    assert _orphaned_at(stage.store, media_id) is None
    assert stage.ref(12).proved_at == NOW + 60


async def test_a_renewed_proof_with_other_bytes_lets_go_of_the_content_and_reads_in_full(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    other = _bytes(200 * KIB, b"other")
    stage.put(12, other)
    stage.renew(12, media_id, len(other))

    step = await stage.step()

    assert step.outcome == CaptureOutcome.KEYED
    own = stage.ref(12).media_id
    assert own is not None
    assert own != media_id
    assert stage.hits(media_id) == [10]
    assert stage.hits(own) == [12]
    assert stage.fetch.calls == [10, 12]


async def test_a_renewed_proof_with_other_bytes_gives_no_hit_while_its_download_waits(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.head.contents[12] = _bytes(200 * KIB, b"other")
    stage.fetch.failing(12, nc.DISK_FULL)
    stage.renew(12, media_id, len(data))

    step = await stage.step()

    assert (step.outcome, step.reason) == (CaptureOutcome.DEFERRED, nc.DISK_FULL)
    assert stage.ref(12).media_id is None
    assert stage.hits(media_id) == [10]


async def test_a_renewed_proof_without_a_reader_fails_without_a_request(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.renew(12, media_id, len(data), reader=None)

    step = await stage.step()

    assert step.outcome == CaptureOutcome.UNREADABLE
    assert stage.head.calls == []
    assert stage.hits(media_id) == [10]


async def test_a_renewed_proof_of_a_changed_reference_is_not_confirmed(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.renew(12, media_id, len(data))

    async def head(file_id: int, _user_id: str) -> nc.HeadResult:
        stage.intake(file_id, len(data) + 5, reader="cem", storage=STORAGE_CEM, prefilter=OTHER_PREFILTER, etag="e2")
        return nc.HeadResult(sha256=_head(data), length=nc.HEAD_BYTES, error=None, status=200)

    stage.capture._head = head

    step = await stage.step()

    assert step.outcome == CaptureOutcome.STALE
    ref = stage.ref(12)
    assert (ref.media_id, ref.stage, ref.proved_at) == (None, "pending", None)
    assert stage.hits(media_id) == [10]


async def test_confirm_proof_is_conditional(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    store = stage.store
    stage.renew(12, media_id, len(data))

    assert store.confirm_proof(12, "e1", NOW) is False  # not claimed
    assert store.next_capture(NOW) is not None
    assert store.confirm_proof(12, "e2", NOW) is False  # another etag
    assert stage.ref(12).stage == "fetching"
    assert store.confirm_proof(12, "e1", NOW) is True
    assert stage.ref(12).stage == "keyed"
    # A reference without a content has nothing to confirm.
    stage.intake(13, 100, reader="cem", storage=STORAGE_CEM)
    assert store.next_capture(NOW) is not None
    assert store.confirm_proof(13, "e1", NOW) is False


async def test_a_probing_reference_without_a_content_is_not_claimed(stage: Stage) -> None:
    stage.store.upsert_file_ref(
        12, None, storage_id=STORAGE_CEM, etag="e1", size=100, mtime=1, state="active", stage="probing", reason=None
    )

    assert (await stage.step()).outcome == CaptureOutcome.IDLE


@pytest.mark.parametrize("state", ["vanished", "trashed"])
async def test_a_renewed_proof_is_not_due_for_a_reference_that_may_not_count(stage: Stage, state: str) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.renew(12, media_id, len(data))
    stage.store._conn.execute("UPDATE file_ref SET state = ? WHERE file_id = 12", (state,))

    assert (await stage.step()).outcome == CaptureOutcome.IDLE
    assert stage.head.calls == []


async def test_the_proof_logs_never_name_the_reader(stage: Stage, caplog: pytest.LogCaptureFixture) -> None:
    data = _bytes(200 * KIB)
    await stage.keyed_sibling(data)
    stage.put(11, data)
    stage.intake(11, len(data), reader="geheime-leserin", storage=STORAGE_BEN)
    stage.intake(12, len(data), reader="geheime-leserin", storage=STORAGE_CEM)
    stage.head.failing(12, nc.READ_DENIED)

    with caplog.at_level(logging.DEBUG):
        await stage.step()
        await stage.step()

    own = [record for record in caplog.records if record.name.startswith("audio_video_search_backend")]
    assert own
    assert all("geheime-leserin" not in repr(vars(record)) for record in own)


# POSITIVE CONTROL B (D-02-01a, D-02-10): the negative tests above can see the leak.


async def test_positive_control_b_without_the_verdict_the_denied_copy_attaches(
    stage: Stage, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)
    stage.capture._head = _gateway_head(_forbidden())

    async def always_ok(*_args: object) -> ProofOutcome:
        return ProofOutcome.OK

    # The product has no switch for this (gate in test_read_proof_gate.py); a test replaces the function.
    monkeypatch.setattr(read_proof, "prove_read", always_ok)

    step = await stage.step()

    # The same 403 copy as in the negative test now hangs at ana's content: that is the leak.
    assert (step.outcome, step.media_id) == (CaptureOutcome.KEYED, media_id)
    assert stage.ref(11).media_id == media_id
    assert stage.hits(media_id) == [10, 11]


async def test_positive_control_b_the_same_copy_stays_out_with_the_real_verdict(stage: Stage) -> None:
    data = _bytes(200 * KIB)
    media_id = await stage.keyed_sibling(data)
    stage.intake(11, len(data), reader="ben", storage=STORAGE_BEN)
    stage.capture._head = _gateway_head(_forbidden())

    step = await stage.step()

    assert (step.outcome, step.reason) == (CaptureOutcome.UNREADABLE, nc.READ_DENIED)
    assert stage.hits(media_id) == [10]
