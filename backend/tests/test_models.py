"""The model catalog and the file side of the download (plan 03-07), without a network."""

import asyncio
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from audio_video_search_backend import nc
from audio_video_search_backend.models import catalog, procure
from tests.conftest import BACKEND_ROOT

# The values of 03-RESEARCH.md, written out here once more on purpose: the test
# compares the catalog against them instead of against itself.
RESEARCH_DIGESTS = {
    "encoder.int8.onnx": "acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247",
    "decoder.int8.onnx": "179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e",
    "joiner.int8.onnx": "3164c13fc2821009440d20fcb5fdc78bff28b4db2f8d0f0b329101719c0948b3",
    "tokens.txt": "d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d",
    "silero_vad.onnx": "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6",
}
COMMIT = "2bda32ec70b097a55adaa07d9a7173915b43cc78"
HEX64 = re.compile(r"[0-9a-f]{64}")


def _all_files() -> list[catalog.ModelFile]:
    return [entry for files in catalog.MODELS.values() for entry in files]


def test_the_catalog_holds_the_research_digests_and_nothing_else() -> None:
    assert {entry.name: entry.sha256 for entry in _all_files()} == RESEARCH_DIGESTS
    assert all(HEX64.fullmatch(entry.sha256) for entry in _all_files())
    assert all(entry.size > 0 for entry in _all_files())


def test_every_parakeet_url_is_pinned_to_the_commit() -> None:
    for entry in catalog.PARAKEET_FILES:
        assert entry.url == (
            f"https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/resolve/{COMMIT}/{entry.name}"
        )
    assert catalog.SILERO_FILES[0].url.endswith("/releases/download/asr-models/silero_vad.onnx")


def test_every_url_starts_on_an_allowed_host_over_https() -> None:
    for entry in _all_files():
        scheme, _, rest = entry.url.partition("://")
        assert scheme == "https"
        assert rest.split("/", 1)[0] in catalog.ASSET_HOSTS


def test_the_allowlist_has_no_pattern() -> None:
    assert catalog.ASSET_HOSTS
    for host in catalog.ASSET_HOSTS:
        assert "*" not in host
        assert re.fullmatch(r"[a-z0-9.-]+", host), host


def test_model_sha256_is_the_sha256_of_the_sorted_digests() -> None:
    joined = ",".join(sorted(RESEARCH_DIGESTS.values()))

    assert hashlib.sha256(joined.encode("ascii")).hexdigest() == catalog.MODEL_SHA256
    assert HEX64.fullmatch(catalog.MODEL_SHA256)


def test_model_dir_is_under_models_name_and_the_set_digest(tmp_path: Path) -> None:
    assert procure.model_dir(tmp_path, "parakeet") == tmp_path / "models" / "parakeet" / catalog.MODEL_SHA256


# ---------------------------------------------------------------------------
# procure() with a fetch that writes given bytes
# ---------------------------------------------------------------------------

GOOD = b"model bytes " * 100
OTHER = b"other bytes " * 100


def _entry(name: str, payload: bytes) -> catalog.ModelFile:
    return catalog.ModelFile(
        name=name,
        url=f"https://huggingface.co/x/resolve/{COMMIT}/{name}",
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
    )


@pytest.fixture
def small_model(monkeypatch: pytest.MonkeyPatch) -> catalog.ModelFile:
    entry = _entry("a.onnx", GOOD)
    monkeypatch.setitem(catalog.MODELS, "parakeet", (entry,))
    return entry


class FakeFetch:
    """Writes ``payload`` into the .part like nc.fetch_model_asset, and counts calls."""

    def __init__(self, payload: bytes, code: str = nc.MODEL_FETCHED) -> None:
        self.payload = payload
        self.code = code
        self.calls: list[str] = []
        self.hosts: list[frozenset[str]] = []

    async def __call__(
        self,
        url: str,
        dest: Path,
        *,
        expected_size: int,
        allowed_hosts: frozenset[str],
        on_chunk: Callable[[bytes], Awaitable[None]],
    ) -> str:
        del expected_size
        self.calls.append(url)
        self.hosts.append(allowed_hosts)
        if self.code != nc.MODEL_FETCHED:
            return self.code
        await asyncio.to_thread(dest.write_bytes, self.payload)
        await on_chunk(self.payload)
        return self.code


def _files(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir()) if directory.exists() else []


async def test_a_matching_download_is_installed(tmp_path: Path, small_model: catalog.ModelFile) -> None:
    fetch = FakeFetch(GOOD)
    seen: list[int] = []

    async def progress(done: int) -> None:
        seen.append(done)

    outcome = await procure.procure(tmp_path, "parakeet", fetch=fetch, progress=progress)

    directory = procure.model_dir(tmp_path, "parakeet")
    assert outcome == procure.PROCURED
    assert (directory / "a.onnx").read_bytes() == GOOD
    assert _files(directory) == ["a.onnx", "a.onnx.verified.json"]
    assert fetch.calls == [small_model.url]
    assert fetch.hosts == [catalog.ASSET_HOSTS]
    assert seen[-1] == len(GOOD)


async def test_a_download_with_the_wrong_digest_leaves_nothing(tmp_path: Path, small_model: catalog.ModelFile) -> None:
    assert len(OTHER) == small_model.size  # same length, other bytes: only the hash can tell

    outcome = await procure.procure(tmp_path, "parakeet", fetch=FakeFetch(OTHER))

    assert outcome == procure.WRONG_DIGEST
    assert _files(procure.model_dir(tmp_path, "parakeet")) == []


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (nc.MODEL_FOREIGN_HOST, procure.UNAVAILABLE),
        (nc.MODEL_HTTP_ERROR, procure.UNAVAILABLE),
        (nc.MODEL_NETWORK, procure.UNAVAILABLE),
        (nc.MODEL_TOO_LARGE, procure.WRONG_DIGEST),
    ],
)
async def test_a_refused_fetch_is_an_outcome_without_a_file(
    tmp_path: Path, small_model: catalog.ModelFile, code: str, expected: str
) -> None:
    del small_model
    outcome = await procure.procure(tmp_path, "parakeet", fetch=FakeFetch(GOOD, code=code))

    assert outcome == expected
    assert _files(procure.model_dir(tmp_path, "parakeet")) == []


async def test_no_room_asks_nothing(
    tmp_path: Path, small_model: catalog.ModelFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: small_model.size + nc.DISK_RESERVE_BYTES - 1)
    fetch = FakeFetch(GOOD)

    outcome = await procure.procure(tmp_path, "parakeet", fetch=fetch)

    assert outcome == procure.NO_ROOM
    assert fetch.calls == []
    assert _files(procure.model_dir(tmp_path, "parakeet")) == []


async def test_exactly_enough_room_is_enough(
    tmp_path: Path, small_model: catalog.ModelFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Positive control of the test above: the same check one byte higher passes.
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: small_model.size + nc.DISK_RESERVE_BYTES)

    assert await procure.procure(tmp_path, "parakeet", fetch=FakeFetch(GOOD)) == procure.PROCURED


async def test_a_file_the_admin_placed_counts_without_a_request(tmp_path: Path, small_model: catalog.ModelFile) -> None:
    directory = procure.model_dir(tmp_path, "parakeet")
    directory.mkdir(parents=True)
    (directory / small_model.name).write_bytes(GOOD)
    fetch = FakeFetch(GOOD)

    assert await procure.procure(tmp_path, "parakeet", fetch=fetch) == procure.PRESENT
    assert fetch.calls == []
    # Also in the mode without any fetch (the air gap check).
    assert await procure.procure(tmp_path, "parakeet", fetch=None) == procure.PRESENT


async def test_a_wrong_file_the_admin_placed_is_refused_and_kept(
    tmp_path: Path, small_model: catalog.ModelFile
) -> None:
    directory = procure.model_dir(tmp_path, "parakeet")
    directory.mkdir(parents=True)
    (directory / small_model.name).write_bytes(OTHER)
    fetch = FakeFetch(GOOD)

    assert await procure.procure(tmp_path, "parakeet", fetch=fetch) == procure.WRONG_DIGEST
    assert fetch.calls == []
    assert (directory / small_model.name).read_bytes() == OTHER
    assert _files(directory) == [small_model.name]


async def test_a_short_file_the_admin_placed_is_refused(tmp_path: Path, small_model: catalog.ModelFile) -> None:
    directory = procure.model_dir(tmp_path, "parakeet")
    directory.mkdir(parents=True)
    (directory / small_model.name).write_bytes(GOOD[:-1])

    assert await procure.procure(tmp_path, "parakeet", fetch=None) == procure.WRONG_DIGEST


async def test_a_missing_file_without_fetch_is_unavailable(tmp_path: Path, small_model: catalog.ModelFile) -> None:
    del small_model
    assert await procure.procure(tmp_path, "parakeet", fetch=None) == procure.UNAVAILABLE


async def test_the_verdict_is_cached_by_size_and_mtime(tmp_path: Path, small_model: catalog.ModelFile) -> None:
    directory = procure.model_dir(tmp_path, "parakeet")
    directory.mkdir(parents=True)
    target = directory / small_model.name
    target.write_bytes(GOOD)

    before = procure.hash_count()
    assert await procure.procure(tmp_path, "parakeet", fetch=None) == procure.PRESENT
    assert procure.hash_count() == before + 1
    assert await procure.procure(tmp_path, "parakeet", fetch=None) == procure.PRESENT
    assert procure.hash_count() == before + 1  # second look: one stat, no hash

    # Same size, other bytes, other mtime: the cache must not answer.
    target.write_bytes(OTHER)
    status = target.stat()
    os.utime(target, ns=(status.st_atime_ns, status.st_mtime_ns + 1_000_000_000))
    assert await procure.procure(tmp_path, "parakeet", fetch=None) == procure.WRONG_DIGEST
    assert procure.hash_count() == before + 2


async def test_a_stale_part_is_replaced_by_a_fresh_download(tmp_path: Path, small_model: catalog.ModelFile) -> None:
    directory = procure.model_dir(tmp_path, "parakeet")
    directory.mkdir(parents=True)
    (directory / (small_model.name + procure.PART_SUFFIX)).write_bytes(b"left over")

    assert await procure.procure(tmp_path, "parakeet", fetch=FakeFetch(GOOD)) == procure.PROCURED
    assert _files(directory) == ["a.onnx", "a.onnx.verified.json"]


async def test_a_write_error_is_an_outcome(tmp_path: Path, small_model: catalog.ModelFile) -> None:
    del small_model

    async def full(url: str, dest: Path, **_kwargs: object) -> str:
        del url, dest
        raise OSError(28, "No space left on device")

    assert await procure.procure(tmp_path, "parakeet", fetch=full) == procure.NO_ROOM


def test_the_models_package_never_imports_an_http_client() -> None:
    package = BACKEND_ROOT / "src" / "audio_video_search_backend" / "models"
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import httpx" not in text, path.name
        assert "nc_py_api" not in text, path.name


def test_the_command_line_fails_on_an_empty_volume_and_names_both_models(tmp_path: Path) -> None:
    result = subprocess.run(  # noqa: S603 - an argument list, never a shell
        [sys.executable, "-m", "audio_video_search_backend.models.procure", "--root", str(tmp_path), "--verify-only"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert result.returncode == 1
    assert result.stdout.splitlines() == ["silero unavailable", "parakeet unavailable"]


def test_the_command_line_succeeds_when_both_models_are_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(catalog.MODELS, "silero", (_entry("s.onnx", OTHER),))
    monkeypatch.setitem(catalog.MODELS, "parakeet", (_entry("p.onnx", GOOD),))
    for name, filename, payload in (("silero", "s.onnx", OTHER), ("parakeet", "p.onnx", GOOD)):
        directory = procure.model_dir(tmp_path, name)
        directory.mkdir(parents=True)
        (directory / filename).write_bytes(payload)

    assert procure.cli(["--root", str(tmp_path), "--verify-only"]) == 0
    assert capsys.readouterr().out.splitlines() == ["silero present", "parakeet present"]
