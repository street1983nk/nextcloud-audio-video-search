"""The pinned speech clips for CI and model tests (plan 03-02), without network.

``ci/media/fetch_speech.py`` reads one named member of a FLEURS test archive as a
stream, checks its fixed sha256 and writes nothing of the archive to disk. The
tests below build small archives in tmp_path and prove that the right member is
taken, a wrong hash is refused, and a member ``../evil`` is never written.
"""

import hashlib
import importlib.util
import io
import json
import re
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

from audio_video_search_backend.index import numbers
from audio_video_search_backend.index.publish import PREFIX_MIN_CHARS
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


def test_clips_de_tr_es_and_the_s7_clips(fs: ModuleType) -> None:
    assert [clip.name for clip in fs.CLIPS] == [
        "speech_de.wav",
        "speech_tr.wav",
        "speech_es.wav",
        "speech_s7_de.wav",
        "speech_s7_de_digit.wav",
    ]
    assert [clip.tar_path for clip in fs.CLIPS] == [
        "data/de_de/audio/test.tar.gz",
        "data/tr_tr/audio/test.tar.gz",
        "data/es_419/audio/test.tar.gz",
        "data/de_de/audio/test.tar.gz",
        "data/de_de/audio/test.tar.gz",
    ]
    assert fs.S7_CLIPS == (fs.SPEECH_S7_DE, fs.SPEECH_S7_DE_DIGIT)
    assert len({clip.member_sha256 for clip in fs.CLIPS}) == len(fs.CLIPS)


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


@pytest.mark.parametrize("index", [3, 4])
def test_s7_clip_pins_are_well_formed(fs: ModuleType, index: int) -> None:
    clip = fs.CLIPS[index]
    assert clip in fs.S7_CLIPS
    assert HEX64.fullmatch(clip.member_sha256)
    assert HEX64.fullmatch(clip.wav_sha256)
    assert re.fullmatch(r"\d+\.wav", clip.member)
    assert 5.0 <= clip.duration_s <= 30.0
    assert fs.clip_url(clip) == (f"https://huggingface.co/datasets/google/fleurs/resolve/{fs.REVISION}/{clip.tar_path}")


def _fold(text: str) -> str:
    return "".join(char for char in text.lower() if char.isalnum())


@pytest.mark.parametrize("index", [3, 4])
def test_s7_targets_stand_in_the_measured_text(fs: ModuleType, index: int) -> None:
    """The target forms come from the measured transcript (plan 04-14), each number form names one value."""
    clip = fs.CLIPS[index]
    targets = clip.s7
    tokens = {_fold(part) for part in clip.expected_text.split()}
    assert clip.expected_word == targets.number_word
    assert _fold(targets.number_word) in tokens
    assert _fold(targets.compound) in tokens
    assert targets.plural is None or _fold(targets.plural) in tokens
    assert _fold(targets.head) not in tokens
    assert _fold(targets.compound).startswith(_fold(targets.head)[:4])
    assert len(targets.head) >= PREFIX_MIN_CHARS
    assert targets.singular is None or _fold(targets.singular) not in tokens
    values = [[span.value for span in numbers.recognize(form.split())] for form in targets.number_forms]
    assert len(targets.number_forms) == 4
    assert all(value == values[0] and len(value) == 1 for value in values)
    assert targets.number_forms[0].isdigit()


def test_only_the_three_old_clips_lack_s7_targets(fs: ModuleType) -> None:
    assert [clip.s7 is None for clip in fs.CLIPS] == [True, True, True, False, False]


def test_read_member_takes_the_named_member_without_a_pin(fs: ModuleType) -> None:
    data = fs.read_member(archive({"test/a.wav": b"aaa", "test/b.wav": b"bbb"}), "b.wav")

    assert data == b"bbb"


def test_read_member_refuses_a_path(fs: ModuleType) -> None:
    with pytest.raises(ValueError, match="plain file name"):
        fs.read_member(archive({"test/a.wav": b"aaa"}), "../a.wav")


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


def test_s7_env_names_each_clip_and_its_forms(
    fs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    """Plan 04-14: deploy-harp.yml writes these lines into GITHUB_ENV; nothing is fetched, ffmpeg is not needed."""
    monkeypatch.delenv("AVS_FFMPEG", raising=False)
    monkeypatch.setenv("PATH", "")
    for clip in fs.S7_CLIPS:
        (tmp_path / clip.name).write_bytes(b"RIFF")

    assert fs.main([str(tmp_path), "--s7-env"]) == 0

    lines = capsysbinary.readouterr().out.decode("utf-8").splitlines()
    assert lines[:2] == [
        f"AVS_SPEECH_S7_DE={tmp_path / 'speech_s7_de.wav'}",
        f"AVS_SPEECH_S7_DE_DIGIT={tmp_path / 'speech_s7_de_digit.wav'}",
    ]
    assert lines[2].startswith("AVS_S7_TARGETS=")
    assert len(lines) == 3
    targets = json.loads(lines[2].removeprefix("AVS_S7_TARGETS="))
    assert [item["key"] for item in targets] == ["S7_DE", "S7_DE_DIGIT"]
    assert targets[0]["number_forms"] == ["20", "zwanzig", "twenty", "vingt"]
    assert targets[1]["number_forms"] == ["12", "zwölf", "twelve", "douze"]
    assert targets[0]["plural"] == "Polizisten"
    assert targets[1]["plural"] is None


def test_s7_env_without_the_clips_exits_3(fs: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "speech_s7_de.wav").write_bytes(b"RIFF")
    (tmp_path / "speech_s7_de_digit.wav").write_bytes(b"")

    assert fs.main([str(tmp_path), "--s7-env"]) == 3

    captured = capsys.readouterr()
    assert "speech_s7_de_digit.wav is missing" in captured.err
    assert captured.out == ""
