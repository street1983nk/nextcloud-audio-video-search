"""Offline: the one way out of the container is shut before a client or a name lookup exists (plan 05-08).

The model download is the only request that leaves the Nextcloud (PLAT-04,
D-05-07). With the offline check registered and true, both fetch functions
answer ``offline`` as their first act. Two traps prove that nothing was even
prepared: ``nc.new_model_client`` is counted, and ``socket.getaddrinfo`` fails
the test when anything asks for an address. A control shows that the same
traps do see an attempt when the check says online.
"""

import hashlib
import logging
import socket
from pathlib import Path

import httpx
import pytest

from audio_video_search_backend import nc
from audio_video_search_backend.models import catalog, procure

URL = "https://github.com/street1983nk/nextcloud-audio-video-search/releases/download/whisper-2026-11/a.bin"
BODY = b"model bytes " * 100
OTHER = b"other bytes " * 100
PROXY_VARIABLES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class Traps:
    """Counts every client that is built and every name that is looked up."""

    def __init__(self) -> None:
        self.clients = 0
        self.lookups: list[str] = []
        self.requests: list[httpx.Request] = []

    def client(self) -> httpx.AsyncClient:
        self.clients += 1
        return httpx.AsyncClient(transport=httpx.MockTransport(self._answer), follow_redirects=False)

    def _answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, content=BODY)

    def lookup(self, host: object, *_args: object, **_kwargs: object) -> list[object]:
        self.lookups.append(str(host))
        message = "a name lookup although the model download is offline"
        raise AssertionError(message)

    def untouched(self) -> bool:
        return self.clients == 0 and self.lookups == [] and self.requests == []


@pytest.fixture
def traps(monkeypatch: pytest.MonkeyPatch) -> Traps:
    found = Traps()
    monkeypatch.setattr(nc, "new_model_client", found.client)
    monkeypatch.setattr(socket, "getaddrinfo", found.lookup)
    return found


@pytest.fixture(autouse=True)
def check_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check is module state: every test starts and ends with the one the module came with."""
    monkeypatch.setattr(nc, "_OFFLINE_CHECK", vars(nc)["_OFFLINE_CHECK"])


def _keep(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


# ---------------------------------------------------------------------------
# The two fetch functions
# ---------------------------------------------------------------------------


async def test_offline_answers_before_a_client_or_a_lookup_exists(tmp_path: Path, traps: Traps) -> None:
    nc.set_models_offline(lambda: True)
    dest = tmp_path / "a.bin.part"

    code = await nc.fetch_model_asset(URL, dest, expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS)

    assert code == nc.MODEL_OFFLINE
    assert traps.untouched()
    assert not dest.exists()


async def test_offline_answers_for_a_part_and_leaves_the_file_as_it_is(tmp_path: Path, traps: Traps) -> None:
    nc.set_models_offline(lambda: True)
    path = tmp_path / "model.bin.part"
    # More bytes than the start: an offline answer does not even cut the file.
    _keep(path, b"kept bytes and a rest")

    with path.open("r+b") as handle:
        code = await nc.fetch_model_part(
            URL, handle, start=10, expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS
        )

    assert code == nc.MODEL_OFFLINE
    assert traps.untouched()
    assert path.read_bytes() == b"kept bytes and a rest"


async def test_offline_does_not_use_a_client_the_caller_brought(tmp_path: Path, traps: Traps) -> None:
    nc.set_models_offline(lambda: True)
    path = tmp_path / "model.bin.part"
    _keep(path, b"")

    async with traps.client() as client:
        traps.clients = 0
        asset = await nc.fetch_model_asset(
            URL, tmp_path / "a.part", expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS, client=client
        )
        with path.open("r+b") as handle:
            part = await nc.fetch_model_part(
                URL, handle, start=0, expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS, client=client
            )

    assert (asset, part) == (nc.MODEL_OFFLINE, nc.MODEL_OFFLINE)
    assert traps.requests == []


async def test_the_traps_see_an_attempt_when_the_check_says_online(tmp_path: Path, traps: Traps) -> None:
    # Positive control, same traps, same calls: online builds one client per
    # call and the requests go out (to the mock transport of the trap).
    nc.set_models_offline(lambda: False)
    path = tmp_path / "model.bin.part"
    _keep(path, b"")

    asset = await nc.fetch_model_asset(
        URL, tmp_path / "a.part", expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS
    )
    with path.open("r+b") as handle:
        part = await nc.fetch_model_part(
            URL, handle, start=0, expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS
        )

    assert (asset, part) == (nc.MODEL_FETCHED, nc.MODEL_FETCHED)
    assert traps.clients == 2
    assert len(traps.requests) == 2


async def test_the_lookup_trap_fires_for_the_real_client_when_online(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Positive control of the lookup trap: the real client, online, asks for the
    # address of the release host first. The trap answers like a resolver that
    # is down, so no packet leaves this machine and the outcome is "network".
    for name in PROXY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    lookups: list[str] = []

    def down(host: object, *_args: object, **_kwargs: object) -> list[object]:
        lookups.append(host.decode() if isinstance(host, bytes) else str(host))
        raise socket.gaierror(socket.EAI_NONAME, "resolver is down in this test")

    monkeypatch.setattr(socket, "getaddrinfo", down)

    code = await nc.fetch_model_asset(
        URL, tmp_path / "a.part", expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS
    )

    assert code == nc.MODEL_NETWORK
    assert lookups
    assert set(lookups) == {"github.com"}

    # And the same call offline never reaches the resolver.
    lookups.clear()
    nc.set_models_offline(lambda: True)
    assert (
        await nc.fetch_model_asset(URL, tmp_path / "a.part", expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS)
        == nc.MODEL_OFFLINE
    )
    assert lookups == []


async def test_the_check_is_read_anew_on_every_call(tmp_path: Path, traps: Traps) -> None:
    state = {"offline": True, "asked": 0}

    def check() -> bool:
        state["asked"] += 1
        return bool(state["offline"])

    nc.set_models_offline(check)
    dest = tmp_path / "a.part"

    async def fetch() -> str:
        return await nc.fetch_model_asset(URL, dest, expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS)

    assert await fetch() == nc.MODEL_OFFLINE
    assert traps.untouched()
    state["offline"] = False
    assert await fetch() == nc.MODEL_FETCHED
    assert traps.clients == 1
    state["offline"] = True
    assert await fetch() == nc.MODEL_OFFLINE
    assert traps.clients == 1
    assert state["asked"] == 3


async def test_without_a_registered_check_the_download_is_online(tmp_path: Path, traps: Traps) -> None:
    # The state every other test file runs in (tests/test_model_download.py).
    code = await nc.fetch_model_asset(
        URL, tmp_path / "a.part", expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS
    )

    assert code == nc.MODEL_FETCHED
    assert traps.clients == 1


async def test_a_check_that_fails_counts_as_offline(
    tmp_path: Path, traps: Traps, caplog: pytest.LogCaptureFixture
) -> None:
    # Not knowing is not a licence to connect (T-05-18): the lock fails closed.
    def broken() -> bool:
        message = "state.db is locked"
        raise RuntimeError(message)

    nc.set_models_offline(broken)

    with caplog.at_level(logging.INFO, logger=nc.LOGGER.name):
        code = await nc.fetch_model_asset(
            URL, tmp_path / "a.part", expected_size=len(BODY), allowed_hosts=catalog.ASSET_HOSTS
        )

    assert code == nc.MODEL_OFFLINE
    assert traps.untouched()
    assert [getattr(record, "error_type", None) for record in caplog.records] == ["RuntimeError"]
    assert "state.db" not in caplog.text


async def test_the_offline_log_names_the_outcome_and_no_url(
    tmp_path: Path, traps: Traps, caplog: pytest.LogCaptureFixture
) -> None:
    del traps
    nc.set_models_offline(lambda: True)

    with caplog.at_level(logging.INFO, logger=nc.LOGGER.name):
        await nc.fetch_model_asset(URL, tmp_path / "a.part", expected_size=1, allowed_hosts=catalog.ASSET_HOSTS)

    assert [getattr(record, "outcome", None) for record in caplog.records] == [nc.MODEL_OFFLINE]
    for record in caplog.records:
        assert "github" not in record.getMessage()
        assert "whisper" not in record.getMessage()
        assert URL not in str(record.__dict__)


def test_offline_is_an_outcome_of_the_fetch_and_of_procure_but_never_ready() -> None:
    assert nc.MODEL_OFFLINE == "offline"
    assert nc.MODEL_OFFLINE in nc.MODEL_FETCH_OUTCOMES
    assert procure.OFFLINE == "offline"
    assert procure.OFFLINE in procure.PROCURE_OUTCOMES
    assert procure.OFFLINE not in procure.READY_OUTCOMES
    assert {procure.PROCURED, procure.PRESENT} == procure.READY_OUTCOMES


# ---------------------------------------------------------------------------
# procure with the real fetch functions
# ---------------------------------------------------------------------------

MODEL = "whisper-turbo"
PART_BYTES = (b"a1b2" * 500, b"c3d4" * 300)


def _whole_file() -> catalog.ModelFile:
    return catalog.ModelFile(name="a.bin", url=URL, sha256=_sha(BODY), size=len(BODY))


def _parted_file() -> catalog.PartedFile:
    whole = b"".join(PART_BYTES)
    return catalog.PartedFile(
        name="model.bin",
        sha256=_sha(whole),
        size=len(whole),
        parts=tuple(
            catalog.Part(url=f"{URL}.{index:03d}", sha256=_sha(payload), size=len(payload))
            for index, payload in enumerate(PART_BYTES, start=1)
        ),
    )


def _files(root: Path) -> list[str]:
    directory = procure.model_dir(root, MODEL)
    return sorted(path.name for path in directory.iterdir()) if directory.exists() else []


def _place(root: Path, name: str, payload: bytes) -> Path:
    directory = procure.model_dir(root, MODEL)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(payload)
    return path


async def test_procure_offline_with_a_missing_file_is_offline_without_a_request(
    tmp_path: Path, traps: Traps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(catalog.MODELS, MODEL, (_whole_file(),))
    nc.set_models_offline(lambda: True)

    assert await procure.procure(tmp_path, MODEL, fetch=nc.fetch_model_asset) == procure.OFFLINE
    assert traps.untouched()
    assert _files(tmp_path) == []


async def test_procure_offline_with_a_missing_parted_file_is_offline_without_a_request(
    tmp_path: Path, traps: Traps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(catalog.MODELS, MODEL, (_parted_file(),))
    nc.set_models_offline(lambda: True)

    assert await procure.procure(tmp_path, MODEL) == procure.OFFLINE
    assert traps.untouched()
    assert _files(tmp_path) == []


async def test_procure_offline_keeps_the_verified_parts_of_an_earlier_run(
    tmp_path: Path, traps: Traps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(catalog.MODELS, MODEL, (_parted_file(),))
    part = _place(tmp_path, "model.bin.part", PART_BYTES[0])
    nc.set_models_offline(lambda: True)

    assert await procure.procure(tmp_path, MODEL) == procure.OFFLINE
    assert traps.untouched()
    assert part.read_bytes() == PART_BYTES[0]


async def test_procure_offline_takes_a_right_file_the_admin_placed(
    tmp_path: Path, traps: Traps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(catalog.MODELS, MODEL, (_whole_file(), _parted_file()))
    _place(tmp_path, "a.bin", BODY)
    _place(tmp_path, "model.bin", b"".join(PART_BYTES))
    nc.set_models_offline(lambda: True)

    assert await procure.procure(tmp_path, MODEL, fetch=nc.fetch_model_asset) == procure.PRESENT
    assert traps.untouched()


@pytest.mark.parametrize("wrong", ["a.bin", "model.bin"])
async def test_procure_offline_refuses_a_wrong_file_the_admin_placed_and_keeps_it(
    tmp_path: Path, traps: Traps, monkeypatch: pytest.MonkeyPatch, wrong: str
) -> None:
    monkeypatch.setitem(catalog.MODELS, MODEL, (_whole_file(), _parted_file()))
    payloads = {"a.bin": BODY, "model.bin": b"".join(PART_BYTES)}
    forged = b"\0" * len(payloads[wrong])
    payloads[wrong] = forged
    for name, payload in payloads.items():
        _place(tmp_path, name, payload)
    nc.set_models_offline(lambda: True)

    assert await procure.procure(tmp_path, MODEL, fetch=nc.fetch_model_asset) == procure.WRONG_DIGEST
    assert traps.untouched()
    assert (procure.model_dir(tmp_path, MODEL) / wrong).read_bytes() == forged
    assert _files(tmp_path) == ["a.bin", "model.bin"]


async def test_procure_fetches_again_as_soon_as_the_check_says_online(
    tmp_path: Path, traps: Traps, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Positive control of the procure tests above: the same call, online.
    monkeypatch.setitem(catalog.MODELS, MODEL, (_whole_file(),))
    state = {"offline": True}
    nc.set_models_offline(lambda: state["offline"])

    assert await procure.procure(tmp_path, MODEL) == procure.OFFLINE
    state["offline"] = False
    assert await procure.procure(tmp_path, MODEL) == procure.PROCURED
    assert traps.clients == 1
    assert _files(tmp_path) == ["a.bin"]


def test_the_command_line_names_offline_and_fails(
    tmp_path: Path, traps: Traps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    small = catalog.ModelFile(name="a.bin", url=URL, sha256=_sha(OTHER), size=len(OTHER))
    monkeypatch.setitem(catalog.MODELS, "silero", (small,))
    monkeypatch.setitem(catalog.MODELS, "parakeet", (_whole_file(),))
    nc.set_models_offline(lambda: True)

    assert procure.cli(["--root", str(tmp_path)]) == 1
    assert capsys.readouterr().out.splitlines() == ["silero offline", "parakeet offline"]
    assert traps.untouched()
