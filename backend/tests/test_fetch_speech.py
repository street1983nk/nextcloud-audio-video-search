"""The pinned speech clips for CI and model tests (plan 03-02), without network.

``ci/media/fetch_speech.py`` reads one named member of a FLEURS test archive as a
stream, checks its fixed sha256 and writes nothing of the archive to disk. The
tests below build small archives in tmp_path and prove that the right member is
taken, a wrong hash is refused, and a member ``../evil`` is never written.
"""

import hashlib
import importlib.util
import io
import re
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

from tests.conftest import REPO_ROOT

FETCH_SPEECH = REPO_ROOT / "ci" / "media" / "fetch_speech.py"
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fetch_speech_under_test", FETCH_SPEECH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        # dataclasses looks the module up in sys.modules while the class is built
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
        sys.modules.pop(spec.name, None)
    return module


@pytest.fixture(scope="module")
def fs() -> ModuleType:
    return load()


def archive(members: dict[str, bytes]) -> io.BytesIO:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    buffer.seek(0)
    return buffer


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_revision_is_a_commit(fs: ModuleType) -> None:
    assert HEX40.fullmatch(fs.REVISION)
    assert fs.DATASET == "google/fleurs"


def test_three_clips_de_tr_and_es(fs: ModuleType) -> None:
    assert [clip.name for clip in fs.CLIPS] == ["speech_de.wav", "speech_tr.wav", "speech_es.wav"]
    assert [clip.tar_path for clip in fs.CLIPS] == [
        "data/de_de/audio/test.tar.gz",
        "data/tr_tr/audio/test.tar.gz",
        "data/es_419/audio/test.tar.gz",
    ]


@pytest.mark.parametrize("index", [0, 1, 2])
def test_clip_pins_are_well_formed(fs: ModuleType, index: int) -> None:
    clip = fs.CLIPS[index]
    assert HEX64.fullmatch(clip.member_sha256)
    assert HEX64.fullmatch(clip.wav_sha256)
    assert "/" not in clip.member
    assert "\\" not in clip.member
    assert ".." not in clip.member
    assert clip.member.endswith(".wav")
    assert 8.0 <= clip.duration_s <= 15.0
    assert fs.clip_url(clip) == (f"https://huggingface.co/datasets/google/fleurs/resolve/{fs.REVISION}/{clip.tar_path}")


def test_expected_word_is_in_the_expected_text(fs: ModuleType) -> None:
    word = fs.EXPECTED_WORD
    assert re.fullmatch(r"[a-z]{7,}", word)
    assert word in fs.EXPECTED_TEXT.lower().split()
    assert fs.SPEECH_TR.expected_word is None
    assert fs.SPEECH_ES.expected_word is None


def test_pick_member_takes_the_named_member(fs: ModuleType) -> None:
    good = b"RIFF good member"
    tar = archive({"test": b"", "test/other.wav": b"other", "test/clip.wav": good})
    assert fs.pick_member(tar, "clip.wav", sha(good)) == good


def test_pick_member_refuses_a_wrong_hash(fs: ModuleType) -> None:
    tar = archive({"test/clip.wav": b"tampered"})
    with pytest.raises(fs.PinError, match="sha256"):
        fs.pick_member(tar, "clip.wav", sha(b"original"))


def test_pick_member_ignores_the_same_name_outside_the_folder(fs: ModuleType) -> None:
    data = b"same name, other folder"
    tar = archive({"train/clip.wav": data, "clip.wav": data})
    with pytest.raises(fs.PinError, match="not in archive"):
        fs.pick_member(tar, "clip.wav", sha(data))


def test_member_with_dot_dot_is_never_written(fs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    evil = b"evil payload"
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    tar = archive({"../evil": evil, "test/../evil": evil, "test/clip.wav": b"clip"})
    assert fs.pick_member(tar, "clip.wav", sha(b"clip")) == b"clip"
    with pytest.raises(ValueError, match="plain file name"):
        fs.pick_member(archive({"../evil": evil}), "../evil", sha(evil))
    with pytest.raises(fs.PinError):
        fs.pick_member(archive({"../evil": evil}), "evil", sha(evil))
    assert not (tmp_path / "evil").exists()
    assert list(work.iterdir()) == []


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://huggingface.co/datasets/google/fleurs/resolve/x/y", True),
        ("https://us.aws.cdn.hf.co/xet-bridge-us/abc", True),
        ("https://cas-bridge.xethub.hf.co/abc", True),
        ("http://huggingface.co/x", False),
        ("https://evil.example/hf.co", False),
        ("https://hf.co.evil.example/x", False),
    ],
)
def test_host_allowlist(fs: ModuleType, url: str, allowed: bool) -> None:
    assert fs.host_allowed(url) is allowed


def test_pin_error_exits_3_without_file(fs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(clip: object, out_dir: Path, ff: str) -> bool:
        (out_dir / "speech_de.wav").write_bytes(b"partial")
        raise fs.PinError("sha256 mismatch")

    monkeypatch.setattr(fs, "fetch", broken)
    monkeypatch.setenv("AVS_FFMPEG", sys.executable)
    assert fs.main([str(tmp_path)]) == 3
    assert not (tmp_path / "speech_de.wav").exists()


def test_missing_ffmpeg_exits_2(fs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AVS_FFMPEG", raising=False)
    with pytest.raises(SystemExit) as stop:
        fs.main([str(tmp_path), "--ffmpeg", str(tmp_path / "no-such-ffmpeg")])
    assert stop.value.code == 2
