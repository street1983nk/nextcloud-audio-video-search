"""The Whisper weights are split into parts whose identity is measured (plan 05-03).

A GitHub release asset must stay under 2 GiB and large-v3 ``model.bin`` has
3 087 284 237 bytes, so both ``model.bin`` are cut into parts of exactly 1 GiB
(D-05-13). ``scripts/models/split_whisper.py`` loads the files at a fixed
commit, checks the sha256 of the whole file before any part is written and
writes the identities as JSON. Every test here runs on small fake files or on
a fake transport; none of them touches the network.
"""

import hashlib
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from tests.conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "models" / "split_whisper.py"

# Plan 05-03 interfaces, typed here a second time on purpose: the script must
# carry the same values, a typo on one side fails the comparison.
TURBO_BIN = (1_617_884_929, "e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da")
LARGE_BIN = (3_087_284_237, "69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1")
SMALL_FILES = {
    "whisper-turbo": {
        "config.json": (2_263, "b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e"),
        "preprocessor_config.json": (340, "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711"),
        "tokenizer.json": (2_710_337, "297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd"),
        "vocabulary.json": (1_068_114, "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1"),
    },
    "whisper-large-v3": {
        "config.json": (2_394, "a9306624f5ec14270a014b647e5c316b6e03a662c369758d1b90697a7b0655b9"),
        "preprocessor_config.json": (340, "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711"),
        "tokenizer.json": (2_480_617, "6d8cbd7cd0d8d5815e478dac67b85a26bbe77c1f5e0c6d76d1ce2abc0e5f21ca"),
        "vocabulary.json": (1_068_114, "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1"),
    },
}
SOURCES = {
    "whisper-turbo": ("deepdml/faster-whisper-large-v3-turbo-ct2", "4df90f75321148c3a29a9e2351b7ddf8f5b115a8"),
    "whisper-large-v3": ("Systran/faster-whisper-large-v3", "edaa852ec7e145841d8ffdb056a99866b5f0a478"),
}


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("split_whisper_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses look their module up while the class body runs
    sys.modules[spec.name] = module
    # no __pycache__ beside the scripts
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return load_script()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pattern(length: int) -> bytes:
    """Bytes that differ from part to part, so a swapped part is seen."""
    return bytes((index * 7 + index // 5) % 251 for index in range(length))


# --- split_file ---------------------------------------------------------------


def test_parts_joined_in_order_are_the_original(script: ModuleType, tmp_path: Path) -> None:
    data = pattern(25)
    source = tmp_path / "model.bin"
    source.write_bytes(data)
    out = tmp_path / "assets"

    parts = script.split_file(source, 10, out, "whisper-x.model.bin")

    assert [name for name, _, _ in parts] == [
        "whisper-x.model.bin.001",
        "whisper-x.model.bin.002",
        "whisper-x.model.bin.003",
    ]
    assert [size for _, size, _ in parts] == [10, 10, 5]
    assert [sha for _, _, sha in parts] == [digest(data[0:10]), digest(data[10:20]), digest(data[20:25])]
    assert b"".join((out / name).read_bytes() for name, _, _ in parts) == data
    # nothing but the parts lies in the asset folder
    assert sorted(path.name for path in out.iterdir()) == [name for name, _, _ in parts]


@pytest.mark.parametrize(("length", "sizes"), [(10, [10]), (11, [10, 1]), (9, [9]), (20, [10, 10])])
def test_part_boundaries(script: ModuleType, tmp_path: Path, length: int, sizes: list[int]) -> None:
    source = tmp_path / "model.bin"
    source.write_bytes(pattern(length))

    parts = script.split_file(source, 10, tmp_path / "assets", "p")

    assert [size for _, size, _ in parts] == sizes


@pytest.mark.parametrize("part_size", [0, -1])
def test_a_part_size_below_one_is_refused(script: ModuleType, tmp_path: Path, part_size: int) -> None:
    source = tmp_path / "model.bin"
    source.write_bytes(b"abc")

    with pytest.raises(ValueError, match="part_size"):
        script.split_file(source, part_size, tmp_path / "assets", "p")


# --- the fixed table ----------------------------------------------------------


def test_part_size_is_one_gibibyte(script: ModuleType) -> None:
    assert script.PART_SIZE == 2**30 == 1_073_741_824


def test_the_table_carries_the_values_of_the_plan(script: ModuleType) -> None:
    assert sorted(script.MODELS) == ["whisper-large-v3", "whisper-turbo"]
    for key, (repo, commit) in SOURCES.items():
        model = script.MODELS[key]
        assert (model.repo, model.commit) == (repo, commit)
        files = {entry.name: (entry.size, entry.sha256) for entry in model.files}
        expected = dict(SMALL_FILES[key])
        expected["model.bin"] = TURBO_BIN if key == "whisper-turbo" else LARGE_BIN
        assert files == expected
    assert script.MODELS["whisper-turbo"].prefix == "whisper-large-v3-turbo"
    assert script.MODELS["whisper-large-v3"].prefix == "whisper-large-v3"


def test_urls_name_the_commit_and_nothing_else(script: ModuleType) -> None:
    model = script.MODELS["whisper-large-v3"]

    assert script.source_url(model, "model.bin") == (
        "https://huggingface.co/Systran/faster-whisper-large-v3/resolve/"
        "edaa852ec7e145841d8ffdb056a99866b5f0a478/model.bin"
    )


# --- run(): whole digest first, then parts, then JSON ---------------------------


def fake_models(script: ModuleType, big: bytes, small: bytes, *, wrong: bool = False) -> dict:
    big_sha = digest(big + b"x") if wrong else digest(big)
    return {
        "whisper-fake": script.Model(
            prefix="whisper-fake",
            repo="example/fake",
            commit="0" * 40,
            files=(
                script.FileSpec("model.bin", len(big), big_sha),
                script.FileSpec("config.json", len(small), digest(small)),
            ),
        )
    }


def place(work: Path, big: bytes, small: bytes) -> None:
    folder = work / "originals" / "whisper-fake"
    folder.mkdir(parents=True)
    (folder / "model.bin").write_bytes(big)
    (folder / "config.json").write_bytes(small)


def test_run_writes_parts_and_json(script: ModuleType, tmp_path: Path) -> None:
    big, small = pattern(25), b'{"a": 1}'
    work, out = tmp_path / "work", tmp_path / "parts.json"
    place(work, big, small)

    code = script.run(work, out, models=fake_models(script, big, small), part_size=10, skip_download=True)

    assert code == 0
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["tag"] == "whisper-2026-11"
    assert list(document) == ["models", "tag"]
    model = document["models"]["whisper-fake"]
    assert model["source"] == {"commit": "0" * 40, "repo": "example/fake"}
    by_name = {entry["name"]: entry for entry in model["files"]}
    assert sorted(by_name) == ["config.json", "model.bin"]
    whole = by_name["model.bin"]
    assert whole["asset"] is None
    assert (whole["size"], whole["sha256"]) == (25, digest(big))
    assert [part["asset"] for part in whole["parts"]] == [
        "whisper-fake.model.bin.001",
        "whisper-fake.model.bin.002",
        "whisper-fake.model.bin.003",
    ]
    assert sum(part["size"] for part in whole["parts"]) == whole["size"]
    assert [part["sha256"] for part in whole["parts"]] == [digest(big[0:10]), digest(big[10:20]), digest(big[20:])]
    plain = by_name["config.json"]
    assert plain["parts"] is None
    assert plain["asset"] == "whisper-fake.config.json"
    assert (plain["size"], plain["sha256"]) == (len(small), digest(small))
    assets = work / "assets"
    assert (assets / "whisper-fake.config.json").read_bytes() == small
    assert b"".join((assets / part["asset"]).read_bytes() for part in whole["parts"]) == big
    for entry in model["files"]:
        assert sorted(entry) == ["asset", "name", "parts", "sha256", "size"]


def test_json_is_stable(script: ModuleType, tmp_path: Path) -> None:
    big, small = pattern(25), b"{}"
    work = tmp_path / "work"
    place(work, big, small)
    models = fake_models(script, big, small)

    assert script.run(work, tmp_path / "a.json", models=models, part_size=10, skip_download=True) == 0
    assert script.run(work, tmp_path / "b.json", models=models, part_size=10, skip_download=True) == 0

    first = (tmp_path / "a.json").read_bytes()
    assert first == (tmp_path / "b.json").read_bytes()
    assert first.endswith(b"}\n")
    assert first == (json.dumps(json.loads(first), indent=2, sort_keys=True) + "\n").encode()


def test_a_wrong_whole_digest_stops_before_any_part(script: ModuleType, tmp_path: Path) -> None:
    big, small = pattern(25), b"{}"
    work, out = tmp_path / "work", tmp_path / "parts.json"
    place(work, big, small)

    code = script.run(work, out, models=fake_models(script, big, small, wrong=True), part_size=10, skip_download=True)

    assert code == 1
    assert not out.exists()
    assets = work / "assets"
    assert not assets.exists() or list(assets.iterdir()) == []


def test_a_wrong_length_stops_before_any_part(script: ModuleType, tmp_path: Path) -> None:
    big, small = pattern(25), b"{}"
    work, out = tmp_path / "work", tmp_path / "parts.json"
    place(work, big + b"!", small)

    code = script.run(work, out, models=fake_models(script, big, small), part_size=10, skip_download=True)

    assert code == 1
    assert not out.exists()
    assert not (work / "assets").exists() or list((work / "assets").iterdir()) == []


def test_a_missing_file_stops_with_skip_download(script: ModuleType, tmp_path: Path) -> None:
    big, small = pattern(25), b"{}"
    work, out = tmp_path / "work", tmp_path / "parts.json"
    place(work, big, small)
    (work / "originals" / "whisper-fake" / "config.json").unlink()

    code = script.run(work, out, models=fake_models(script, big, small), part_size=10, skip_download=True)

    assert code == 1
    assert not out.exists()


# --- download: hosts, redirects, digest ---------------------------------------


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://huggingface.co/a/b/resolve/c/model.bin", True),
        ("https://us.aws.cdn.hf.co/x?sig=1", True),
        ("https://cas-bridge.xethub.hf.co/x", True),
        ("http://huggingface.co/a", False),
        ("https://evilhf.co/x", False),
        ("https://huggingface.co.example.org/x", False),
        ("https://hf.co.example.org/x", False),
        ("https://example.org/huggingface.co", False),
        ("https://user@example.org@huggingface.co.example.org/x", False),
        ("ftp://huggingface.co/x", False),
        ("https:///x", False),
    ],
)
def test_only_https_hosts_of_hugging_face_are_allowed(script: ModuleType, url: str, allowed: bool) -> None:
    assert script.allowed_url(url) is allowed


Handler = Callable[[httpx.Request], httpx.Response]


def client_for(handler: Handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def body(status: int, data: bytes, headers: dict[str, str] | None = None) -> httpx.Response:
    """An unread stream, as a real server gives it; ``content=`` would be read already."""
    return httpx.Response(status, stream=httpx.ByteStream(data), headers=headers)


def test_download_follows_the_cdn_redirect_and_checks_the_digest(script: ModuleType, tmp_path: Path) -> None:
    data = pattern(3000)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.host == "huggingface.co":
            return httpx.Response(302, headers={"location": "https://us.aws.cdn.hf.co/blob?X-Signature=secret"})
        return body(200, data)

    dest = tmp_path / "model.bin"
    with client_for(handler) as client:
        script.download(client, "https://huggingface.co/r/resolve/c/model.bin", dest, len(data), digest(data))

    assert dest.read_bytes() == data
    assert seen == ["huggingface.co", "us.aws.cdn.hf.co"]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["model.bin"]


def test_download_never_asks_a_foreign_host(script: ModuleType, tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(302, headers={"location": "https://example.org/blob"})

    dest = tmp_path / "model.bin"
    with client_for(handler) as client, pytest.raises(script.FetchError, match=r"example\.org"):
        script.download(client, "https://huggingface.co/r/resolve/c/model.bin", dest, 3, digest(b"abc"))

    assert seen == ["huggingface.co"]
    assert list(tmp_path.iterdir()) == []


def test_download_gives_up_on_a_redirect_loop(script: ModuleType, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://huggingface.co/again"})

    with client_for(handler) as client, pytest.raises(script.FetchError, match="redirect"):
        script.download(client, "https://huggingface.co/x", tmp_path / "f", 3, digest(b"abc"))


def test_a_wrong_digest_leaves_no_file(script: ModuleType, tmp_path: Path) -> None:
    data = pattern(3000)
    tampered = data[:-1] + bytes([data[-1] ^ 1])

    def handler(request: httpx.Request) -> httpx.Response:
        return body(200, tampered)

    dest = tmp_path / "model.bin"
    with client_for(handler) as client, pytest.raises(script.DigestError):
        script.download(client, "https://huggingface.co/x", dest, len(data), digest(data))

    assert list(tmp_path.iterdir()) == []


def test_a_body_longer_than_the_fixed_size_is_cut_off(script: ModuleType, tmp_path: Path) -> None:
    data = pattern(3000)

    def handler(request: httpx.Request) -> httpx.Response:
        return body(200, data + b"more")

    dest = tmp_path / "model.bin"
    with client_for(handler) as client, pytest.raises(script.FetchError, match="longer"):
        script.download(client, "https://huggingface.co/x", dest, len(data), digest(data))

    assert list(tmp_path.iterdir()) == []


def test_a_short_body_is_an_error_and_never_the_final_file(script: ModuleType, tmp_path: Path) -> None:
    data = pattern(3000)

    def handler(request: httpx.Request) -> httpx.Response:
        return body(200, data[:1000])

    dest = tmp_path / "model.bin"
    with client_for(handler) as client, pytest.raises(script.FetchError, match="short"):
        script.download(client, "https://huggingface.co/x", dest, len(data), digest(data))

    assert not dest.exists()


def test_an_http_error_is_an_error(script: ModuleType, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with client_for(handler) as client, pytest.raises(script.FetchError, match="404"):
        script.download(client, "https://huggingface.co/x", tmp_path / "f", 3, digest(b"abc"))

    assert list(tmp_path.iterdir()) == []


def test_a_started_download_goes_on_with_a_range(script: ModuleType, tmp_path: Path) -> None:
    data = pattern(3000)
    dest = tmp_path / "model.bin"
    (tmp_path / "model.bin.part").write_bytes(data[:1200])
    ranges: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ranges.append(request.headers.get("range"))
        return body(206, data[1200:], {"content-range": f"bytes 1200-2999/{len(data)}"})

    with client_for(handler) as client:
        script.download(client, "https://huggingface.co/x", dest, len(data), digest(data))

    assert ranges == ["bytes=1200-"]
    assert dest.read_bytes() == data


def test_a_server_without_range_starts_again_from_zero(script: ModuleType, tmp_path: Path) -> None:
    data = pattern(3000)
    dest = tmp_path / "model.bin"
    (tmp_path / "model.bin.part").write_bytes(b"stale bytes that do not belong")

    def handler(request: httpx.Request) -> httpx.Response:
        return body(200, data)

    with client_for(handler) as client:
        script.download(client, "https://huggingface.co/x", dest, len(data), digest(data))

    assert dest.read_bytes() == data


def test_a_range_answer_for_another_offset_is_refused(script: ModuleType, tmp_path: Path) -> None:
    data = pattern(3000)
    (tmp_path / "model.bin.part").write_bytes(data[:1200])

    def handler(request: httpx.Request) -> httpx.Response:
        return body(206, data[1000:], {"content-range": f"bytes 1000-2999/{len(data)}"})

    with client_for(handler) as client, pytest.raises(script.FetchError, match="range"):
        script.download(client, "https://huggingface.co/x", tmp_path / "model.bin", len(data), digest(data))


def test_a_present_file_with_the_right_digest_is_not_loaded_again(script: ModuleType, tmp_path: Path) -> None:
    data = pattern(3000)
    dest = tmp_path / "model.bin"
    dest.write_bytes(data)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with client_for(handler) as client:
        script.download(client, "https://huggingface.co/x", dest, len(data), digest(data))

    assert dest.read_bytes() == data


def test_a_present_file_with_a_wrong_digest_is_an_error_and_stays(script: ModuleType, tmp_path: Path) -> None:
    data = pattern(3000)
    dest = tmp_path / "model.bin"
    dest.write_bytes(b"something else")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with client_for(handler) as client, pytest.raises(script.DigestError):
        script.download(client, "https://huggingface.co/x", dest, len(data), digest(data))

    assert dest.read_bytes() == b"something else"


def test_output_names_hosts_only(script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = pattern(3000)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "huggingface.co":
            return httpx.Response(302, headers={"location": "https://us.aws.cdn.hf.co/blob/abc?X-Signature=secret"})
        return body(200, data)

    with client_for(handler) as client:
        script.download(client, "https://huggingface.co/r/resolve/c/model.bin", tmp_path / "f", len(data), digest(data))

    printed = capsys.readouterr()
    text = printed.out + printed.err
    assert "us.aws.cdn.hf.co" in text
    assert "secret" not in text
    assert "X-Signature" not in text
    assert "/blob/abc" not in text


def test_the_app_never_names_hugging_face() -> None:
    """The app loads from its own release only (D-03-21); this script is a developer step."""
    source = REPO_ROOT / "backend" / "src"
    hits = [
        path.relative_to(source).as_posix()
        for path in sorted(source.rglob("*.py"))
        if "huggingface.co" in path.read_text(encoding="utf-8")
    ]
    assert hits == []
