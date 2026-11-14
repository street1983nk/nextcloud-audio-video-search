"""The download of the preview (plan 03-13): the temporary file stays for ffmpeg until the block ends.

nc.fetch_media_file is the sibling of nc.fetch_to_tempfile: the same checks
(free space first, the gateway's refusal codes, exactly the expected size, the
deadline), but the finished file is handed to the caller under a random name
without an extension and removed when the ``async with`` block is left, on every
way out (T-03-44). Tested against an httpx MockTransport like tests/test_capture.py.
"""

import asyncio
import hashlib
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from audio_video_search_backend import nc

USER = "alice-reader"
NAME = re.compile(r"[0-9a-f]{32}")
GIB = 1024**3

type Handler = Callable[[httpx.Request], httpx.Response]


def _data(size: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < size:
        out += hashlib.sha256(counter.to_bytes(8, "big")).digest()
        counter += 1
    return bytes(out[:size])


def _left(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "tmp"
    directory.mkdir()
    return directory


@pytest.fixture(autouse=True)
def plenty_of_space(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: 1024**4)


def _answer(status: int = 200, body: bytes = b"", headers: dict[str, str] | None = None) -> Handler:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers=headers or {})

    return handler


def _streamed(body: Callable[[], AsyncIterator[bytes]]) -> Handler:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body())

    return handler


@asynccontextmanager
async def _kept(
    handler: Handler, directory: Path, size: int, cap: int = GIB
) -> AsyncIterator[tuple[nc.FetchResult, Path | None]]:
    """One fetch_media_file against a mock gateway; the block of the caller runs inside it."""
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client,
        nc.fetch_media_file(42, USER, directory, size, cap, client=client) as kept,
    ):
        yield kept


async def test_the_file_stays_inside_the_block_with_a_random_name_and_is_gone_after(tmp_dir: Path) -> None:
    data = _data(150_000)
    async with _kept(_answer(body=data), tmp_dir, len(data)) as (result, path):
        assert result.error is None
        assert result.sha256 == hashlib.sha256(data).hexdigest()
        assert result.size == len(data)
        assert path is not None
        assert path.parent == tmp_dir
        # A random name without an extension: the demuxer is chosen by the content alone.
        assert NAME.fullmatch(path.name) is not None
        assert path.suffix == ""
        assert path.read_bytes() == data
        assert _left(tmp_dir) == [path.name]
    assert _left(tmp_dir) == []


async def test_two_downloads_get_two_names(tmp_dir: Path) -> None:
    data = _data(1000)
    names: list[str] = []
    for _ in range(2):
        async with _kept(_answer(body=data), tmp_dir, len(data)) as (_result, path):
            assert path is not None
            names.append(path.name)
    assert names[0] != names[1]


async def test_the_file_is_gone_after_an_exception_in_the_block(tmp_dir: Path) -> None:
    data = _data(5000)
    seen: list[Path] = []

    async def fail_inside() -> None:
        async with _kept(_answer(body=data), tmp_dir, len(data)) as (_result, path):
            assert path is not None
            seen.append(path)
            assert path.exists()
            raise RuntimeError("inside the block")

    with pytest.raises(RuntimeError, match="inside the block"):
        await fail_inside()
    assert seen
    assert not seen[0].exists()
    assert _left(tmp_dir) == []


async def test_the_file_is_gone_after_a_cancellation_in_the_block(tmp_dir: Path) -> None:
    data = _data(5000)
    entered = asyncio.Event()

    async def hold() -> None:
        async with _kept(_answer(body=data), tmp_dir, len(data)) as (_result, path):
            assert path is not None
            entered.set()
            await asyncio.sleep(60)

    task = asyncio.create_task(hold())
    await asyncio.wait_for(entered.wait(), 5)
    assert len(_left(tmp_dir)) == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert _left(tmp_dir) == []


@pytest.mark.parametrize(
    ("status", "headers", "code"),
    [
        (403, {nc.REASON_HEADER: "access_control"}, nc.ACCESS_CONTROL),
        (403, {nc.REASON_HEADER: "excluded"}, nc.EXCLUDED),
        (403, {}, nc.READ_DENIED),
        (404, {}, nc.NOT_FOUND),
        (423, {}, nc.LOCKED),
        (500, {}, nc.GATEWAY_FAILED),
    ],
)
async def test_a_refusal_gives_its_code_no_path_and_no_file(
    tmp_dir: Path, status: int, headers: dict[str, str], code: str
) -> None:
    handler = _answer(status=status, body=b"<html>secret</html>", headers=headers)
    async with _kept(handler, tmp_dir, 100) as (result, path):
        assert result.error == code
        assert result.sha256 is None
        assert path is None
        assert _left(tmp_dir) == []
    assert _left(tmp_dir) == []


@pytest.mark.parametrize("actual", [999, 1001])
async def test_another_size_gives_size_mismatch_and_no_file(tmp_dir: Path, actual: int) -> None:
    async def body() -> AsyncIterator[bytes]:
        yield _data(actual)

    async with _kept(_streamed(body), tmp_dir, 1000) as (result, path):
        assert result.error == nc.SIZE_MISMATCH
        assert path is None
    assert _left(tmp_dir) == []


async def test_not_enough_space_gives_disk_full_without_a_request(
    tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: nc.DISK_RESERVE_BYTES + 99)
    asked: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        return httpx.Response(200, content=b"x" * 100)

    async with _kept(handler, tmp_dir, 100) as (result, path):
        assert result.error == nc.DISK_FULL
        assert path is None
    assert asked == []
    assert _left(tmp_dir) == []


async def test_exactly_enough_space_is_enough(tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Positive control of the border above: the file plus the reserve fit exactly.
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: nc.DISK_RESERVE_BYTES + 100)
    async with _kept(_answer(body=b"y" * 100), tmp_dir, 100) as (result, path):
        assert result.error is None
        assert path is not None


async def test_more_than_the_cap_gives_too_large_without_a_request(tmp_dir: Path) -> None:
    async with _kept(_answer(body=b"z" * 100), tmp_dir, 100, cap=99) as (result, path):
        assert result.error == nc.TOO_LARGE
        assert path is None
    assert _left(tmp_dir) == []


async def test_a_stream_that_breaks_off_leaves_nothing(tmp_dir: Path) -> None:
    async def body() -> AsyncIterator[bytes]:
        yield b"a" * 500
        raise httpx.ReadError("gone")

    async with _kept(_streamed(body), tmp_dir, 1000) as (result, path):
        assert result.error == nc.GATEWAY_FAILED
        assert path is None
    assert _left(tmp_dir) == []


async def test_a_stopped_download_leaves_at_most_a_part_file_that_the_start_removes(tmp_dir: Path) -> None:
    started = asyncio.Event()

    async def body() -> AsyncIterator[bytes]:
        yield b"b" * 500
        started.set()
        await asyncio.sleep(60)
        yield b"b" * 500

    async def run() -> None:
        async with _kept(_streamed(body), tmp_dir, 1000):
            pass

    task = asyncio.create_task(run())
    await asyncio.wait_for(started.wait(), 5)
    during = _left(tmp_dir)
    assert len(during) == 1
    assert during[0].endswith(nc.PART_SUFFIX)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # The cancelled task cleans up itself; a killed process would leave the part file,
    # which remove_stale_parts takes away at the next start.
    assert all(name.endswith(nc.PART_SUFFIX) for name in _left(tmp_dir))
    (tmp_dir / ("0" * 32 + nc.PART_SUFFIX)).write_bytes(b"left over")
    assert nc.remove_stale_parts(tmp_dir) >= 1
    assert _left(tmp_dir) == []


async def test_the_deadline_gives_read_timeout_and_no_file(tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nc, "capture_deadline", lambda _size: 0.05)

    async def body() -> AsyncIterator[bytes]:
        yield b"c" * 10
        await asyncio.sleep(5)
        yield b"c" * 90

    async with _kept(_streamed(body), tmp_dir, 100) as (result, path):
        assert result.error == nc.READ_TIMEOUT
        assert path is None
    assert _left(tmp_dir) == []
