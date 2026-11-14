"""MEDIA-02: the fixed track rule and the time axis, edit lists included.

The edit list case is the one of RESEARCH M-1: a 10 s WAV with a beep at
exactly 5,000 s goes into an MP4 next to a 12 s video, shifted by
``-itsoffset 2``. A player plays the beep at 7,0 s. Raw PCM loses the time
stamps, so without ``aresample=async=1:first_pts=0`` sample 0 is the first
audio packet and the beep lands at about 5,02 s; the test shows both, the
second one with an ffmpeg call of its own.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from audio_video_search_backend.media.decode import decode_chunk
from audio_video_search_backend.media.probe import probe

from tests import media_fixtures as media

TOLERANCE_S = 0.005
CHUNK_FORMATS = ("wav", "m4a", "opus", "mkv")


def test_a_beep_in_a_wav_lies_where_it_was_put(ffmpeg_bin: Path, ffprobe_bin: Path, tmp_path: Path) -> None:
    wav = media.beeps(ffmpeg_bin, tmp_path / "beep.wav", 10, "between(t,5,5.05)")
    probed = probe(wav, ffprobe=ffprobe_bin)
    assert probed.stream_index is not None

    result = decode_chunk(wav, probed.stream_index, 0, 10000, expected_ms=10000, ffmpeg=ffmpeg_bin)

    assert result.reason is None
    found = media.onsets(result.pcm)
    assert len(found) == 1
    assert abs(found[0] - 5.0) <= TOLERANCE_S, found


def edit_list_mp4(ffmpeg: Path, encoders: frozenset[str], tmp_path: Path) -> Path:
    wav = media.beeps(ffmpeg, tmp_path / "beep10.wav", 10, "between(t,5,5.05)")
    video = media.pick_encoder(encoders, "mpeg4")
    audio = media.pick_encoder(encoders, "aac")
    out = tmp_path / "editlist.mp4"
    media.run_ffmpeg(
        ffmpeg,
        *media.video_input(12),
        "-itsoffset",
        "2",
        "-i",
        str(wav),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        video,
        "-c:a",
        audio,
        str(out),
    )
    return out


def test_a_beep_behind_an_edit_list_lies_where_the_player_plays_it(
    ffmpeg_bin: Path, ffprobe_bin: Path, encoders: frozenset[str], tmp_path: Path
) -> None:
    path = edit_list_mp4(ffmpeg_bin, encoders, tmp_path)
    # The premise: the file has an edit list.
    assert b"elst" in path.read_bytes()
    probed = probe(path, ffprobe=ffprobe_bin)
    assert probed.reason is None
    assert probed.stream_index == 1

    result = decode_chunk(path, probed.stream_index, 0, 13000, expected_ms=12000, ffmpeg=ffmpeg_bin)

    assert result.reason is None
    found = media.onsets(result.pcm)
    assert len(found) == 1
    assert abs(found[0] - 7.0) <= TOLERANCE_S, found
    # The silence in front of the shifted audio is part of the axis.
    assert abs(media.seconds_of(result.pcm) - 12.0) <= 0.030


def test_without_the_filter_the_same_file_puts_the_beep_two_seconds_early(
    ffmpeg_bin: Path, encoders: frozenset[str], tmp_path: Path
) -> None:
    # Counter check with an ffmpeg call of its own, not decode_chunk: the plain
    # decode the filter exists for.
    path = edit_list_mp4(ffmpeg_bin, encoders, tmp_path)
    plain = subprocess.run(  # noqa: S603 - an argument list, never a shell
        [
            str(ffmpeg_bin),
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
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
        check=True,
    ).stdout

    found = media.onsets(plain)
    assert len(found) == 1
    assert 4.95 <= found[0] <= 5.10, found


@pytest.fixture(scope="module")
def twelve_minutes(ffmpeg_bin: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    # A 50 ms beep at n * 60 + 7,25 s, as in RESEARCH M-2.
    out = tmp_path_factory.mktemp("long") / "beeps12.wav"
    return media.beeps(ffmpeg_bin, out, 720, "between(mod(t,60),7.25,7.30)")


@pytest.mark.parametrize("name", CHUNK_FORMATS)
def test_a_chunk_from_ten_minutes_on_finds_its_beeps_on_its_own_clock(
    name: str,
    ffmpeg_bin: Path,
    ffprobe_bin: Path,
    encoders: frozenset[str],
    twelve_minutes: Path,
    tmp_path: Path,
) -> None:
    path = twelve_minutes if name == "wav" else media.encode(ffmpeg_bin, encoders, twelve_minutes, tmp_path, name)
    probed = probe(path, ffprobe=ffprobe_bin)
    assert probed.reason is None
    assert probed.stream_index is not None

    result = decode_chunk(path, probed.stream_index, 600000, 120000, expected_ms=120000, ffmpeg=ffmpeg_bin)

    assert result.reason is None, name
    found = media.onsets(result.pcm)
    assert len(found) == 2, (name, found)
    assert abs(found[0] - 7.25) <= TOLERANCE_S, (name, found)
    assert abs(found[1] - 67.25) <= TOLERANCE_S, (name, found)


def two_track_mkv(ffmpeg: Path, encoders: frozenset[str], tmp_path: Path, *, default_second: bool) -> Path:
    low = media.tone(ffmpeg, tmp_path / "low.wav", 3, hz=300)
    high = media.tone(ffmpeg, tmp_path / "high.wav", 3, hz=900)
    video = media.pick_encoder(encoders, "mpeg4")
    audio = media.pick_encoder(encoders, "aac")
    flags = ["-disposition:a:0", "0", "-disposition:a:1", "default" if default_second else "0"]
    out = tmp_path / f"two-{default_second}.mkv"
    media.run_ffmpeg(
        ffmpeg,
        *media.video_input(3),
        "-i",
        str(low),
        "-i",
        str(high),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-map",
        "2:a",
        "-c:v",
        video,
        "-c:a",
        audio,
        *flags,
        # Without this the matroska muxer marks the first track default on its own.
        "-default_mode",
        "passthrough",
        str(out),
    )
    return out


def test_the_track_marked_default_wins(
    ffmpeg_bin: Path, ffprobe_bin: Path, encoders: frozenset[str], tmp_path: Path
) -> None:
    path = two_track_mkv(ffmpeg_bin, encoders, tmp_path, default_second=True)

    probed = probe(path, ffprobe=ffprobe_bin)

    assert probed.stream_index == 2
    result = decode_chunk(path, 2, 0, 3000, expected_ms=3000, ffmpeg=ffmpeg_bin)
    # The 900 Hz track, not the 300 Hz one: -map really takes the chosen index.
    assert abs(media.dominant_hz(result.pcm) - 900) < 10


def test_without_a_default_mark_the_first_audio_track_wins(
    ffmpeg_bin: Path, ffprobe_bin: Path, encoders: frozenset[str], tmp_path: Path
) -> None:
    path = two_track_mkv(ffmpeg_bin, encoders, tmp_path, default_second=False)

    probed = probe(path, ffprobe=ffprobe_bin)

    assert probed.stream_index == 1
    result = decode_chunk(path, 1, 0, 3000, expected_ms=3000, ffmpeg=ffmpeg_bin)
    assert abs(media.dominant_hz(result.pcm) - 300) < 10


def test_a_file_without_audio_has_no_audio(
    ffmpeg_bin: Path, ffprobe_bin: Path, encoders: frozenset[str], tmp_path: Path
) -> None:
    video = media.pick_encoder(encoders, "mpeg4")
    out = tmp_path / "silent.mp4"
    media.run_ffmpeg(ffmpeg_bin, *media.video_input(2), "-c:v", video, str(out))

    probed = probe(out, ffprobe=ffprobe_bin)

    assert probed.reason == "no_audio"
    assert probed.stream_index is None
