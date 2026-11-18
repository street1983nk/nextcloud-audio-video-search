"""A model file that comes in parts: one ``.part``, a sha256 per part and for the whole (plan 05-08).

The fake server is an httpx mock transport behind ``nc.new_model_client``, so
every test runs the real ``nc.fetch_model_part`` and the real ``procure``; only
the catalog entry is a small one with three parts.
"""

import dataclasses
import hashlib
from pathlib import Path

import httpx
import pytest

from audio_video_search_backend import nc
from audio_video_search_backend.models import catalog, procure

MODEL = "whisper-turbo"
RELEASE = "https://github.com/street1983nk/nextcloud-audio-video-search/releases/download/whisper-2026-11"
CDN = "https://release-assets.githubusercontent.com/github-production-release-asset/1"
FOREIGN = "https://evil.example.org/model.bin.002"

# Three parts of different lengths and bytes; the last one is the short one.
PART_BYTES = (b"a1b2" * 1000, b"c3d4" * 1000, b"e5f6" * 375)
WHOLE = b"".join(PART_BYTES)
ASSETS = ("tiny.model.bin.001", "tiny.model.bin.002", "tiny.model.bin.003")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _parted(parts: tuple[bytes, ...] = PART_BYTES) -> catalog.PartedFile:
    whole = b"".join(parts)
    return catalog.PartedFile(
        name="model.bin",
        sha256=_sha(whole),
        size=len(whole),
        parts=tuple(
            catalog.Part(url=f"{RELEASE}/{asset}", sha256=_sha(payload), size=len(payload))
            for asset, payload in zip(ASSETS, parts, strict=True)
        ),
    )


class Server:
    """The release and its asset host: answers by asset name and keeps every request."""

    def __init__(self, bodies: dict[str, bytes], *, foreign: frozenset[str] = frozenset()) -> None:
        self.bodies = bodies
        self.foreign = foreign
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        asset = request.url.path.rsplit("/", 1)[-1]
        if request.url.host == "github.com":
            if asset in self.foreign:
                return httpx.Response(302, headers={"Location": FOREIGN})
            return httpx.Response(302, headers={"Location": f"{CDN}/{asset}?sig=x"})
        if request.url.host == "release-assets.githubusercontent.com" and asset in self.bodies:
            return httpx.Response(200, content=self.bodies[asset])
        return httpx.Response(404)

    def assets(self) -> list[str]:
        """The asset of every request that reached the asset host, in order."""
        return [
            request.url.path.rsplit("/", 1)[-1]
            for request in self.requests
            if request.url.host == "release-assets.githubusercontent.com"
        ]

    def hosts(self) -> set[str]:
        return {request.url.host for request in self.requests}


def _bodies(parts: tuple[bytes, ...] = PART_BYTES) -> dict[str, bytes]:
    return dict(zip(ASSETS, parts, strict=True))


def _serve(monkeypatch: pytest.MonkeyPatch, server: Server) -> None:
    def client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(server),
            follow_redirects=False,
            headers={"User-Agent": nc.model_user_agent(), "Accept-Encoding": "identity"},
        )

    monkeypatch.setattr(nc, "new_model_client", client)


@pytest.fixture
def entry(monkeypatch: pytest.MonkeyPatch) -> catalog.PartedFile:
    parted = _parted()
    monkeypatch.setitem(catalog.MODELS, MODEL, (parted,))
    return parted


def _directory(root: Path) -> Path:
    return procure.model_dir(root, MODEL)


def _files(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir()) if directory.exists() else []


def _place(root: Path, name: str, payload: bytes) -> Path:
    directory = _directory(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(payload)
    return path


# ---------------------------------------------------------------------------
# The whole way: parts in order into one file
# ---------------------------------------------------------------------------


async def test_three_matching_parts_are_installed_as_one_file(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = Server(_bodies())
    _serve(monkeypatch, server)
    seen: list[int] = []

    async def progress(done: int) -> None:
        seen.append(done)

    outcome = await procure.procure(tmp_path, MODEL, progress=progress)

    directory = _directory(tmp_path)
    assert outcome == procure.PROCURED
    assert (directory / "model.bin").read_bytes() == WHOLE
    assert _sha((directory / "model.bin").read_bytes()) == entry.sha256
    assert _files(directory) == ["model.bin"]
    assert server.assets() == list(ASSETS)
    assert server.hosts() == {"github.com", "release-assets.githubusercontent.com"}
    assert seen == sorted(seen)
    assert seen[-1] == len(WHOLE)


async def test_the_second_look_asks_nothing(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    server = Server(_bodies())
    _serve(monkeypatch, server)
    assert await procure.procure(tmp_path, MODEL) == procure.PROCURED
    asked = len(server.requests)

    assert await procure.procure(tmp_path, MODEL) == procure.PRESENT
    assert len(server.requests) == asked


async def test_a_wrong_second_part_cuts_the_part_file_back_to_the_first(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    forged = b"\0" * len(PART_BYTES[1])  # the right length: only the sha256 of the part can tell
    server = Server(_bodies((PART_BYTES[0], forged, PART_BYTES[2])))
    _serve(monkeypatch, server)

    outcome = await procure.procure(tmp_path, MODEL)

    directory = _directory(tmp_path)
    assert outcome == procure.WRONG_DIGEST
    assert _files(directory) == ["model.bin.part"]
    assert (directory / "model.bin.part").read_bytes() == PART_BYTES[0]
    # The run ends at the wrong part: the third one is never asked for.
    assert server.assets() == list(ASSETS[:2])


async def test_a_wrong_first_part_leaves_nothing(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    server = Server(_bodies((b"\0" * len(PART_BYTES[0]), PART_BYTES[1], PART_BYTES[2])))
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.WRONG_DIGEST
    assert _files(_directory(tmp_path)) == []
    assert server.assets() == list(ASSETS[:1])


async def test_a_longer_part_is_refused_at_the_part_start(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    server = Server(_bodies((PART_BYTES[0], PART_BYTES[1] + b"!", PART_BYTES[2])))
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.WRONG_DIGEST
    assert (_directory(tmp_path) / "model.bin.part").read_bytes() == PART_BYTES[0]
    assert _files(_directory(tmp_path)) == ["model.bin.part"]


async def test_all_parts_right_but_the_whole_wrong_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A catalog whose parts are right and whose whole is not: the last verdict is the whole.
    forged = dataclasses.replace(_parted(), sha256=_sha(b"something else"))
    monkeypatch.setitem(catalog.MODELS, MODEL, (forged,))
    server = Server(_bodies())
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.WRONG_DIGEST
    assert _files(_directory(tmp_path)) == []
    assert server.assets() == list(ASSETS)


# ---------------------------------------------------------------------------
# Resuming after a restart: only at a part border, only after hashing again
# ---------------------------------------------------------------------------


async def test_a_part_file_on_a_border_is_resumed(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    _place(tmp_path, "model.bin.part", PART_BYTES[0])
    server = Server(_bodies())
    _serve(monkeypatch, server)
    seen: list[int] = []

    async def progress(done: int) -> None:
        seen.append(done)

    assert await procure.procure(tmp_path, MODEL, progress=progress) == procure.PROCURED
    assert (_directory(tmp_path) / "model.bin").read_bytes() == WHOLE
    assert _files(_directory(tmp_path)) == ["model.bin"]
    # Only the rest was asked for, and the count starts behind what was there.
    assert server.assets() == list(ASSETS[1:])
    assert min(seen) > len(PART_BYTES[0])
    assert seen[-1] == len(WHOLE)


async def test_a_part_file_holding_every_part_is_installed_without_a_request(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    _place(tmp_path, "model.bin.part", WHOLE)
    server = Server(_bodies())
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.PROCURED
    assert (_directory(tmp_path) / "model.bin").read_bytes() == WHOLE
    assert server.requests == []


async def test_a_resumed_part_file_with_wrong_bytes_starts_anew(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The right length of two parts, the second one forged: nothing stored says
    # so, only hashing the parts again can tell.
    del entry
    _place(tmp_path, "model.bin.part", PART_BYTES[0] + b"\0" * len(PART_BYTES[1]))
    server = Server(_bodies())
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.PROCURED
    assert (_directory(tmp_path) / "model.bin").read_bytes() == WHOLE
    assert server.assets() == list(ASSETS)


@pytest.mark.parametrize(
    "length",
    [1, len(PART_BYTES[0]) - 1, len(PART_BYTES[0]) + 1, len(WHOLE) - 1, len(WHOLE) + 1],
)
async def test_a_part_file_off_a_border_starts_anew(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch, length: int
) -> None:
    del entry
    _place(tmp_path, "model.bin.part", (WHOLE + b"!")[:length])
    server = Server(_bodies())
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.PROCURED
    assert (_directory(tmp_path) / "model.bin").read_bytes() == WHOLE
    assert _files(_directory(tmp_path)) == ["model.bin"]
    assert server.assets() == list(ASSETS)


async def test_a_break_in_the_second_part_keeps_the_first_for_the_next_run(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    broken = Server({ASSETS[0]: PART_BYTES[0], ASSETS[1]: PART_BYTES[1][:-7], ASSETS[2]: PART_BYTES[2]})
    _serve(monkeypatch, broken)

    assert await procure.procure(tmp_path, MODEL) == procure.UNAVAILABLE
    assert (_directory(tmp_path) / "model.bin.part").read_bytes() == PART_BYTES[0]

    server = Server(_bodies())
    _serve(monkeypatch, server)
    assert await procure.procure(tmp_path, MODEL) == procure.PROCURED
    assert (_directory(tmp_path) / "model.bin").read_bytes() == WHOLE
    assert server.assets() == list(ASSETS[1:])


# ---------------------------------------------------------------------------
# Room on the volume, foreign hosts
# ---------------------------------------------------------------------------


async def test_no_room_for_the_whole_file_asks_nothing(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: entry.size + nc.DISK_RESERVE_BYTES - 1)
    server = Server(_bodies())
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.NO_ROOM
    assert server.requests == []
    assert _files(_directory(tmp_path)) == []


async def test_room_for_once_the_file_is_enough(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Positive control of the test above, and the proof of the single copy: the
    # parts are never collected next to the file, so once its length suffices.
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: entry.size + nc.DISK_RESERVE_BYTES)
    _serve(monkeypatch, Server(_bodies()))

    assert await procure.procure(tmp_path, MODEL) == procure.PROCURED


async def test_a_resumed_file_needs_room_for_the_rest_only(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    _place(tmp_path, "model.bin.part", PART_BYTES[0])
    rest = entry.size - len(PART_BYTES[0])
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: rest + nc.DISK_RESERVE_BYTES - 1)
    server = Server(_bodies())
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.NO_ROOM
    assert server.requests == []
    # The verified first part stays for the run that has room.
    assert (_directory(tmp_path) / "model.bin.part").read_bytes() == PART_BYTES[0]

    monkeypatch.setattr(nc, "free_bytes", lambda _directory: rest + nc.DISK_RESERVE_BYTES)
    assert await procure.procure(tmp_path, MODEL) == procure.PROCURED


async def test_a_redirect_to_a_foreign_host_asks_nothing_there(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    server = Server(_bodies(), foreign=frozenset({ASSETS[1]}))
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.UNAVAILABLE
    assert server.hosts() == {"github.com", "release-assets.githubusercontent.com"}
    assert (_directory(tmp_path) / "model.bin.part").read_bytes() == PART_BYTES[0]
    assert _files(_directory(tmp_path)) == ["model.bin.part"]


# ---------------------------------------------------------------------------
# A whole file the admin placed (air gap): the sha256 of the whole decides
# ---------------------------------------------------------------------------


async def test_a_whole_file_the_admin_placed_counts_without_a_request(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    _place(tmp_path, "model.bin", WHOLE)
    server = Server(_bodies())
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.PRESENT
    assert await procure.procure(tmp_path, MODEL, fetch=None) == procure.PRESENT
    assert server.requests == []


async def test_a_wrong_whole_file_the_admin_placed_is_refused_and_kept(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    forged = b"\0" * len(WHOLE)
    target = _place(tmp_path, "model.bin", forged)
    server = Server(_bodies())
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.WRONG_DIGEST
    assert await procure.procure(tmp_path, MODEL, fetch=None) == procure.WRONG_DIGEST
    assert target.read_bytes() == forged
    assert _files(_directory(tmp_path)) == ["model.bin"]
    assert server.requests == []


async def test_verify_only_never_asks_and_never_touches_a_part_file(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    del entry
    _place(tmp_path, "model.bin.part", PART_BYTES[0])
    server = Server(_bodies())
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL, fetch=None) == procure.UNAVAILABLE
    assert server.requests == []
    assert (_directory(tmp_path) / "model.bin.part").read_bytes() == PART_BYTES[0]


async def test_whole_files_and_a_parted_file_of_one_model_come_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = b'{"small": true}'
    small = catalog.ModelFile(
        name="config.json", url=f"{RELEASE}/tiny.config.json", sha256=_sha(config), size=len(config)
    )
    monkeypatch.setitem(catalog.MODELS, MODEL, (small, _parted()))
    server = Server({**_bodies(), "tiny.config.json": config})
    _serve(monkeypatch, server)
    seen: list[int] = []

    async def progress(done: int) -> None:
        seen.append(done)

    assert await procure.procure(tmp_path, MODEL, progress=progress) == procure.PROCURED
    directory = _directory(tmp_path)
    assert (directory / "config.json").read_bytes() == config
    assert (directory / "model.bin").read_bytes() == WHOLE
    assert _files(directory) == ["config.json", "model.bin"]
    assert seen == sorted(seen)
    assert seen[-1] == catalog.model_bytes(MODEL) == len(config) + len(WHOLE)


# ---------------------------------------------------------------------------
# nc.fetch_model_part on its own: an open file, a start, a cut on every failure
# ---------------------------------------------------------------------------

START = f"{RELEASE}/{ASSETS[1]}"
KEPT = b"kept bytes"


def _keep(path: Path) -> None:
    path.write_bytes(KEPT)


async def _fetch_part(server: Server, path: Path, *, expected_size: int = len(PART_BYTES[1])) -> tuple[str, bytes]:
    seen: list[bytes] = []

    async def observe(chunk: bytes) -> None:
        seen.append(chunk)

    _keep(path)
    transport = httpx.MockTransport(server)
    with path.open("r+b") as handle:
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            code = await nc.fetch_model_part(
                START,
                handle,
                start=len(KEPT),
                expected_size=expected_size,
                allowed_hosts=catalog.ASSET_HOSTS,
                client=client,
                on_chunk=observe,
            )
        # The file stays open and belongs to the caller.
        assert not handle.closed
    return code, b"".join(seen)


async def test_a_part_is_appended_behind_the_start(tmp_path: Path) -> None:
    path = tmp_path / "model.bin.part"

    code, seen = await _fetch_part(Server(_bodies()), path)

    assert code == nc.MODEL_FETCHED
    assert path.read_bytes() == KEPT + PART_BYTES[1]
    assert seen == PART_BYTES[1]


async def test_a_part_overwrites_what_stood_behind_the_start(tmp_path: Path) -> None:
    # Bytes behind the start are the rest of a broken run and never part of the file.
    path = tmp_path / "model.bin.part"
    path.write_bytes(KEPT + b"rest of a broken run" * 500)
    transport = httpx.MockTransport(Server(_bodies()))

    with path.open("r+b") as handle:
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            code = await nc.fetch_model_part(
                START,
                handle,
                start=len(KEPT),
                expected_size=len(PART_BYTES[1]),
                allowed_hosts=catalog.ASSET_HOSTS,
                client=client,
            )

    assert code == nc.MODEL_FETCHED
    assert path.read_bytes() == KEPT + PART_BYTES[1]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (PART_BYTES[1][:-1], nc.MODEL_NETWORK),
        (PART_BYTES[1] + b"!", nc.MODEL_TOO_LARGE),
    ],
)
async def test_a_failed_part_cuts_the_file_back_to_the_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes, expected: str
) -> None:
    path = tmp_path / "model.bin.part"
    # Small blocks and no declared length, so bytes are on the file before the
    # count can refuse the answer.
    monkeypatch.setattr(nc, "CHUNK_SIZE", 64)

    async def stream():
        yield body

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, content=stream())

    path.write_bytes(KEPT)
    with path.open("r+b") as handle:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            code = await nc.fetch_model_part(
                START,
                handle,
                start=len(KEPT),
                expected_size=len(PART_BYTES[1]),
                allowed_hosts=catalog.ASSET_HOSTS,
                client=client,
            )

    assert code == expected
    assert path.read_bytes() == KEPT


async def test_a_part_from_a_foreign_host_sends_no_request_and_keeps_the_start(tmp_path: Path) -> None:
    path = tmp_path / "model.bin.part"
    server = Server(_bodies(), foreign=frozenset({ASSETS[1]}))

    code, seen = await _fetch_part(server, path)

    assert code == nc.MODEL_FOREIGN_HOST
    assert path.read_bytes() == KEPT
    assert seen == b""
    assert server.hosts() == {"github.com"}


async def test_a_transport_error_in_a_part_is_network_and_keeps_the_start(tmp_path: Path) -> None:
    path = tmp_path / "model.bin.part"

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    path.write_bytes(KEPT)
    with path.open("r+b") as handle:
        async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as client:
            code = await nc.fetch_model_part(
                START, handle, start=len(KEPT), expected_size=1, allowed_hosts=catalog.ASSET_HOSTS, client=client
            )

    assert code == nc.MODEL_NETWORK
    assert path.read_bytes() == KEPT


async def test_no_part_request_carries_a_credential_or_a_cookie(
    tmp_path: Path, entry: catalog.PartedFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The environment holds the AppAPI secret (conftest); none of it may travel.
    del entry
    server = Server(_bodies())
    _serve(monkeypatch, server)

    assert await procure.procure(tmp_path, MODEL) == procure.PROCURED
    assert len(server.requests) == 2 * len(ASSETS)
    for request in server.requests:
        for name in ("authorization", "cookie", "authorization-app-api", "ex-app-id"):
            assert name not in request.headers
        assert request.headers["user-agent"].startswith("audio_video_search_backend/")
