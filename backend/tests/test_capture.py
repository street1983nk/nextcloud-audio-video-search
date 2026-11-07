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
from typing import BinaryIO

import httpx
import pytest

from audio_video_search_backend import nc

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
