"""MEDIA-03: a hostile file reads nothing, blocks nothing and leaks nothing.

Every refusal here has a counter check that shows the test can see the thing
it refuses: the concat playlist does read the foreign file once the positive
lists are gone, the CENC file is an ordinary M4A without its encryption, the
slow decode succeeds without its tiny wall time, and ffmpeg's own error output
does carry the path the logs must not carry.
"""

from __future__ import annotations

import logging
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from audio_video_search_backend.logs import JsonFormatter
from audio_video_search_backend.media.decode import decode_chunk
from audio_video_search_backend.media.probe import has_protection_boxes, probe, run_tool
from tests import media_fixtures as media

KEY = "00112233445566778899aabbccddeeff"
KID = "ffeeddccbbaa99887766554433221100"
MARKER = "HIDDEN-7f3a"


def random_bytes(path: Path, size: int = 200_000) -> Path:
    path.write_bytes(random.Random(20261114).randbytes(size))  # noqa: S311 - test data, not a secret
    return path


@pytest.fixture
def secret_and_playlist(ffmpeg_bin: Path, tmp_path: Path) -> Path:
    media.tone(ffmpeg_bin, tmp_path / "secret.wav", 5, hz=440)
    evil = tmp_path / "evil_concat.mp3"
    evil.write_text("ffconcat version 1.0\nfile 'secret.wav'\n", encoding="ascii")
    return evil


def test_a_concat_playlist_named_mp3_reads_no_foreign_file(
    ffmpeg_bin: Path, ffprobe_bin: Path, secret_and_playlist: Path
) -> None:
    probed = probe(secret_and_playlist, ffprobe=ffprobe_bin)
    assert probed.reason == "format_unsupported"
    assert probed.stream_index is None

    result = decode_chunk(secret_and_playlist, 0, 0, 5000, expected_ms=None, ffmpeg=ffmpeg_bin)
    assert result.reason == "format_unsupported"
    assert media.peak(result.pcm) < 0.01


def test_without_the_positive_lists_the_playlist_does_read_the_secret(
    ffmpeg_bin: Path, secret_and_playlist: Path
) -> None:
    # Counter check: the same decode without -protocol_whitelist and
    # -format_whitelist, in an ffmpeg call of its own. ffmpeg opens the .mp3 as
    # a concat playlist and returns the 440 Hz of secret.wav, so the test above
    # would see the leak if the lists were missing.
    leaked = subprocess.run(  # noqa: S603 - an argument list, never a shell
        [
            str(ffmpeg_bin),
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(secret_and_playlist),
            "-map",
            "0:0",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_f32le",
            "-f",
            "f32le",
            "pipe:1",
        ],
        capture_output=True,
        check=False,
    ).stdout

    assert media.peak(leaked) > 0.2
    assert abs(media.dominant_hz(leaked) - 440) < 5


@pytest.mark.parametrize("suffix", [".m4a", ".wav", ".ogg", ".mkv"])
def test_random_bytes_are_damaged(suffix: str, ffmpeg_bin: Path, ffprobe_bin: Path, tmp_path: Path) -> None:
    path = random_bytes(tmp_path / f"noise{suffix}")

    assert probe(path, ffprobe=ffprobe_bin).reason == "damaged"
    assert decode_chunk(path, 0, 0, 5000, expected_ms=5000, ffmpeg=ffmpeg_bin).reason == "damaged"


def test_random_bytes_named_mp3_pass_the_probe_and_fail_the_decode(
    ffmpeg_bin: Path, ffprobe_bin: Path, tmp_path: Path
) -> None:
    # Measured: the mp3 demuxer takes the file on its suffix alone and ffprobe
    # names an audio track without a length. The decode yields no sample
    # (ffmpeg exit 69), so the intake still ends in damaged.
    path = random_bytes(tmp_path / "noise.mp3")

    probed = probe(path, ffprobe=ffprobe_bin)
    assert probed.reason is None
    assert probed.duration_ms is None
    assert probed.stream_index == 0
    assert decode_chunk(path, 0, 0, 5000, expected_ms=5000, ffmpeg=ffmpeg_bin).reason == "damaged"
    # Even without an expected length: a failed run is damaged.
    assert decode_chunk(path, 0, 0, 5000, expected_ms=None, ffmpeg=ffmpeg_bin).reason == "damaged"


def test_random_bytes_without_a_media_suffix_are_refused_as_a_format(ffprobe_bin: Path, tmp_path: Path) -> None:
    # Measured: without a media suffix (the temporary file of plan 03-13 ends
    # in .bin) ffmpeg's "bin" demuxer claims random bytes, and the positive
    # list refuses it. A real recording under .bin is recognised by its
    # content (all ten formats checked by hand), so only junk lands here.
    path = random_bytes(tmp_path / "noise.bin")

    assert probe(path, ffprobe=ffprobe_bin).reason == "format_unsupported"


def test_an_m4a_without_its_index_is_damaged(
    ffmpeg_bin: Path, ffprobe_bin: Path, encoders: frozenset[str], tmp_path: Path
) -> None:
    tone = media.tone(ffmpeg_bin, tmp_path / "tone.wav", 10)
    whole = tmp_path / "whole.m4a"
    media.run_ffmpeg(ffmpeg_bin, "-i", str(tone), "-c:a", media.pick_encoder(encoders, "aac"), str(whole))
    data = whole.read_bytes()
    moov = data.rfind(b"moov") - 4
    assert moov > data.find(b"mdat")
    cut = tmp_path / "cut.m4a"
    cut.write_bytes(data[:moov])

    # Counter check: the uncut file is fine.
    assert probe(whole, ffprobe=ffprobe_bin).reason is None
    assert probe(cut, ffprobe=ffprobe_bin).reason == "damaged"
    assert decode_chunk(cut, 0, 0, 10000, expected_ms=10000, ffmpeg=ffmpeg_bin).reason == "damaged"


def m4a(ffmpeg: Path, encoders: frozenset[str], tmp_path: Path, name: str, *extra: str) -> Path:
    tone = media.tone(ffmpeg, tmp_path / f"{name}.wav", 5)
    out = tmp_path / f"{name}.m4a"
    media.run_ffmpeg(ffmpeg, "-i", str(tone), "-c:a", media.pick_encoder(encoders, "aac"), *extra, str(out))
    return out


def test_a_cenc_encrypted_m4a_is_protected(
    ffmpeg_bin: Path, ffprobe_bin: Path, encoders: frozenset[str], tmp_path: Path
) -> None:
    locked = m4a(
        ffmpeg_bin,
        encoders,
        tmp_path,
        "locked",
        "-encryption_scheme",
        "cenc-aes-ctr",
        "-encryption_key",
        KEY,
        "-encryption_kid",
        KID,
    )
    plain = m4a(ffmpeg_bin, encoders, tmp_path, "plain")

    assert probe(locked, ffprobe=ffprobe_bin).reason == "protected"
    assert has_protection_boxes(locked)
    # Counter check: the same file without encryption is an ordinary M4A.
    assert probe(plain, ffprobe=ffprobe_bin).reason is None
    assert not has_protection_boxes(plain)
    # Decoding without the key yields nothing usable (RESEARCH M-5: exit 69).
    assert decode_chunk(locked, 0, 0, 5000, expected_ms=5000, ffmpeg=ffmpeg_bin).reason == "damaged"


def box(kind: bytes, payload: bytes) -> bytes:
    return (8 + len(payload)).to_bytes(4, "big") + kind + payload


def large_box(kind: bytes, payload: bytes) -> bytes:
    return (1).to_bytes(4, "big") + kind + (16 + len(payload)).to_bytes(8, "big") + payload


@pytest.mark.parametrize("marker", [b"enca", b"sinf", b"schm", b"tenc", b"drms", b"aavd"])
def test_every_protection_mark_inside_moov_is_found(marker: bytes, tmp_path: Path) -> None:
    path = tmp_path / "boxes.mp4"
    path.write_bytes(box(b"ftyp", b"M4A \x00\x00\x00\x00") + large_box(b"mdat", b"\x00" * 64) + box(b"moov", marker))

    assert has_protection_boxes(path)


def test_a_mark_outside_moov_and_broken_box_sizes_are_no_protection(tmp_path: Path) -> None:
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(box(b"ftyp", b"M4A ") + box(b"mdat", b"sinf tenc enca") + box(b"moov", b"trak"))
    broken = tmp_path / "broken.mp4"
    broken.write_bytes((3).to_bytes(4, "big") + b"moov" + b"sinf")
    to_end = tmp_path / "to_end.mp4"
    to_end.write_bytes(box(b"ftyp", b"M4A ") + (0).to_bytes(4, "big") + b"moov" + b"trak schm")
    short = tmp_path / "short.mp4"
    short.write_bytes(b"\x00\x00")

    assert not has_protection_boxes(outside)
    assert not has_protection_boxes(broken)
    assert has_protection_boxes(to_end)
    assert not has_protection_boxes(short)
    assert not has_protection_boxes(tmp_path / "missing.mp4")


class _Recorder:
    """Records every Popen the decoder starts, so the test can ask each one whether it ended."""

    started: list[subprocess.Popen[Any]]

    def __init__(self) -> None:
        self.started = []
        self.original = subprocess.Popen

    def __call__(self, *args: object, **kwargs: object) -> subprocess.Popen[Any]:
        process = self.original(*args, **kwargs)  # type: ignore[call-overload]
        self.started.append(process)
        return process


def test_a_wall_time_overrun_kills_ffmpeg_and_counts_as_damaged(
    ffmpeg_bin: Path, ffprobe_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    long = media.tone(ffmpeg_bin, tmp_path / "long.wav", 600)
    recorder = _Recorder()
    monkeypatch.setattr(subprocess, "Popen", recorder)

    result = decode_chunk(long, 0, 0, 600000, expected_ms=600000, ffmpeg=ffmpeg_bin, wall_seconds=0.01)

    assert result.reason == "damaged"
    assert result.pcm == b""
    assert len(recorder.started) == 1
    assert recorder.started[0].poll() is not None

    # Counter check: the same call with the normal wall time decodes all of it,
    # so the verdict above came from the deadline and not from the file.
    whole = decode_chunk(long, 0, 0, 600000, expected_ms=600000, ffmpeg=ffmpeg_bin)
    assert whole.reason is None
    assert abs(media.seconds_of(whole.pcm) - 600.0) <= 0.030


def test_a_hung_tool_is_killed_at_its_wall_time() -> None:
    # A process that would run a minute; ffmpeg on a test file ends too fast to
    # show that the kill (and not the natural end) stops it.
    started = time.monotonic()

    completed = run_tool([sys.executable, "-c", "import time; time.sleep(60)"], 0.5)

    assert completed.exit_code is None
    assert completed.stdout == b""
    assert time.monotonic() - started < 20


def test_a_probe_wall_time_overrun_counts_as_damaged(
    ffmpeg_bin: Path, ffprobe_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wav = media.tone(ffmpeg_bin, tmp_path / "t.wav", 2)
    recorder = _Recorder()
    monkeypatch.setattr(subprocess, "Popen", recorder)

    assert probe(wav, ffprobe=ffprobe_bin, wall_seconds=0.0001).reason == "damaged"
    assert all(process.poll() is not None for process in recorder.started)
    assert probe(wav, ffprobe=ffprobe_bin).reason is None


def test_no_log_line_carries_the_path_of_a_file(
    ffmpeg_bin: Path, ffprobe_bin: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    folder = tmp_path / MARKER
    folder.mkdir()
    broken = random_bytes(folder / f"{MARKER}.m4a")
    caplog.set_level(logging.DEBUG)

    assert probe(broken, ffprobe=ffprobe_bin).reason == "damaged"
    assert decode_chunk(broken, 0, 0, 5000, expected_ms=5000, ffmpeg=ffmpeg_bin).reason == "damaged"

    formatter = JsonFormatter()
    lines = [formatter.format(record) for record in caplog.records]
    # The refusals are logged, so there is something to look at ...
    assert any('"reason": "damaged"' in line for line in lines), lines
    assert any('"exit_code"' in line for line in lines), lines
    # ... and none of it names the file.
    assert [line for line in lines if MARKER in line] == []


def test_ffmpeg_itself_names_the_path_in_its_error_output(ffmpeg_bin: Path, tmp_path: Path) -> None:
    # Counter check for the test above: the error output the code reads (and
    # must not log) does carry the marker, so logging it would leak the path.
    folder = tmp_path / MARKER
    folder.mkdir()
    broken = random_bytes(folder / f"{MARKER}.m4a")

    done = subprocess.run(  # noqa: S603 - an argument list, never a shell
        [str(ffmpeg_bin), "-nostdin", "-v", "error", "-i", str(broken), "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode != 0
    assert MARKER in done.stderr


def test_the_skip_rule_fails_under_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    # Positive control against silent skips: without CI a missing encoder skips,
    # under CI=true the same call fails the test.
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(pytest.skip.Exception):
        media.pick_encoder(frozenset({"aac"}), "no-such-encoder")
    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception):
        media.pick_encoder(frozenset({"aac"}), "no-such-encoder")
    with pytest.raises(pytest.fail.Exception):
        media.find_tool("AVS_NO_SUCH_TOOL", "avs-no-such-tool")
    assert media.pick_encoder(frozenset({"aac"}), "no-such-encoder", "aac") == "aac"
