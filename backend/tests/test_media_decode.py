"""MEDIA-01: the ten common formats decode from a local file to 16 kHz mono f32.

Every file is made at run time (tests/media_fixtures.py). The large MP4 and M4A
keep their index (moov) at the end, the default of the mp4 muxer: read through
a pipe they break off (RESEARCH M-3), read as a local file they decode whole.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from audio_video_search_backend.media import decode, probe
from audio_video_search_backend.media.decode import DEMUXERS, SAMPLE_RATE, decode_chunk
from audio_video_search_backend.media.probe import MEDIA_REASONS, ProbeResult, pick_audio_stream
from tests import media_fixtures as media

TWENTY_SECONDS_MS = 20000
LENGTH_TOLERANCE_S = 0.030
TEN_MIB = 10 * 1024 * 1024


@pytest.fixture(scope="module")
def twenty_seconds(ffmpeg_bin: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return media.tone(ffmpeg_bin, tmp_path_factory.mktemp("source") / "tone20.wav", 20)


@pytest.mark.parametrize("name", media.FORMAT_NAMES)
def test_every_format_decodes_to_twenty_seconds_of_mono_f32(
    name: str,
    ffmpeg_bin: Path,
    ffprobe_bin: Path,
    encoders: frozenset[str],
    twenty_seconds: Path,
    tmp_path: Path,
) -> None:
    path = media.encode(ffmpeg_bin, encoders, twenty_seconds, tmp_path, name)

    probed = probe.probe(path, ffprobe=ffprobe_bin)
    assert probed.reason is None, name
    assert probed.stream_index is not None
    assert probed.duration_ms is not None
    assert abs(probed.duration_ms - TWENTY_SECONDS_MS) < 100, (name, probed.duration_ms)

    result = decode_chunk(
        path, probed.stream_index, 0, TWENTY_SECONDS_MS + 5000, expected_ms=TWENTY_SECONDS_MS, ffmpeg=ffmpeg_bin
    )
    assert result.reason is None, name
    assert len(result.pcm) % 4 == 0
    assert abs(media.seconds_of(result.pcm) - 20.0) <= LENGTH_TOLERANCE_S, (name, media.seconds_of(result.pcm))
    # The tone is there, not silence of the right length.
    assert media.peak(result.pcm) > 0.2
    assert abs(media.dominant_hz(result.pcm) - 440) < 5


def test_the_format_list_holds_ten_formats_audio_and_video() -> None:
    assert media.FORMAT_NAMES == ("mp3", "m4a", "wav", "ogg", "opus", "flac", "mp4", "mov", "mkv", "webm")
    assert {spec.name for spec in media.FORMATS if spec.video} == {"mp4", "mov", "mkv", "webm"}


def large_m4a(ffmpeg: Path, encoders: frozenset[str], out: Path) -> Path:
    # Two independent noise channels in ALAC hardly compress: 60 s are > 10 MiB.
    codec = media.pick_encoder(encoders, "alac")
    source = "aevalsrc='random(0)-0.5|random(1)-0.5':s=48000:d=60"
    media.run_ffmpeg(ffmpeg, "-f", "lavfi", "-i", source, "-c:a", codec, str(out))
    return out


def large_mp4(ffmpeg: Path, encoders: frozenset[str], tone: Path, out: Path) -> Path:
    video = media.pick_encoder(encoders, "mpeg4")
    audio = media.pick_encoder(encoders, "aac")
    picture = "nullsrc=s=320x240:r=25:d=20,geq=lum=random(1)*255:cb=128:cr=128"
    media.run_ffmpeg(
        ffmpeg,
        "-f",
        "lavfi",
        "-i",
        picture,
        "-i",
        str(tone),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        video,
        "-q:v",
        "1",
        "-c:a",
        audio,
        str(out),
    )
    return out


def index_is_at_the_end(path: Path) -> bool:
    data = path.read_bytes()
    return 0 <= data.find(b"mdat") < data.rfind(b"moov")


@pytest.mark.parametrize("kind", ["m4a", "mp4"])
def test_a_large_file_with_the_index_at_the_end_decodes_whole(
    kind: str,
    ffmpeg_bin: Path,
    ffprobe_bin: Path,
    encoders: frozenset[str],
    twenty_seconds: Path,
    tmp_path: Path,
) -> None:
    if kind == "m4a":
        path, seconds = large_m4a(ffmpeg_bin, encoders, tmp_path / "large.m4a"), 60.0
    else:
        path, seconds = large_mp4(ffmpeg_bin, encoders, twenty_seconds, tmp_path / "large.mp4"), 20.0
    # The premise of the test: big and without faststart.
    assert path.stat().st_size > TEN_MIB, path.stat().st_size
    assert index_is_at_the_end(path)

    probed = probe.probe(path, ffprobe=ffprobe_bin)
    assert probed.reason is None
    assert probed.stream_index is not None
    result = decode_chunk(
        path, probed.stream_index, 0, int(seconds * 1000) + 5000, expected_ms=int(seconds * 1000), ffmpeg=ffmpeg_bin
    )

    assert result.reason is None
    assert abs(media.seconds_of(result.pcm) - seconds) <= LENGTH_TOLERANCE_S


def test_the_index_rule_of_the_large_file_test_sees_a_faststart_file(
    ffmpeg_bin: Path, encoders: frozenset[str], twenty_seconds: Path, tmp_path: Path
) -> None:
    # Positive control: the same encode with +faststart puts moov first, and
    # the premise check above would refuse it.
    audio = media.pick_encoder(encoders, "aac")
    out = tmp_path / "fast.m4a"
    media.run_ffmpeg(ffmpeg_bin, "-i", str(twenty_seconds), "-c:a", audio, "-movflags", "+faststart", str(out))

    assert not index_is_at_the_end(out)


def test_a_chunk_never_carries_more_than_its_byte_limit(
    ffmpeg_bin: Path, ffprobe_bin: Path, twenty_seconds: Path
) -> None:
    probed = probe.probe(twenty_seconds, ffprobe=ffprobe_bin)
    assert probed.stream_index is not None

    result = decode_chunk(twenty_seconds, probed.stream_index, 3000, 2000, expected_ms=2000, ffmpeg=ffmpeg_bin)

    assert result.reason is None
    assert abs(media.seconds_of(result.pcm) - 2.0) <= LENGTH_TOLERANCE_S
    assert len(result.pcm) <= (2 + 1) * SAMPLE_RATE * 4


def test_the_constants_of_the_decoder() -> None:
    assert DEMUXERS == "mov,mp3,wav,w64,ogg,flac,matroska,aac,asf,avi,amr,aiff,caf,mpegts,mpeg"
    assert SAMPLE_RATE == 16000
    assert decode.DECODE_WALL_SECONDS == 300
    assert decode.MIN_SAMPLE_SHARE == 0.5
    assert Path("/usr/local/bin/ffmpeg") == decode.FFMPEG
    assert Path("/usr/local/bin/ffprobe") == probe.FFPROBE
    assert probe.PROBE_WALL_SECONDS == 60
    assert frozenset({"no_audio", "damaged", "protected", "format_unsupported"}) == MEDIA_REASONS


def test_too_few_samples_for_the_expected_length_are_damaged(
    ffmpeg_bin: Path, ffprobe_bin: Path, twenty_seconds: Path
) -> None:
    # The file holds 20 s; a caller that expects 60 s from 0 gets a third.
    result = decode_chunk(twenty_seconds, 0, 0, 60000, expected_ms=60000, ffmpeg=ffmpeg_bin)
    assert result.reason == "damaged"
    assert result.pcm == b""

    # Without an expectation the same call is fine: the end of a file is no damage.
    plain = decode_chunk(twenty_seconds, 0, 0, 60000, expected_ms=None, ffmpeg=ffmpeg_bin)
    assert plain.reason is None
    assert abs(media.seconds_of(plain.pcm) - 20.0) <= LENGTH_TOLERANCE_S


def test_probe_result_is_a_frozen_value() -> None:
    result = ProbeResult(stream_index=1, duration_ms=2, reason=None)

    with pytest.raises(AttributeError):
        result.reason = "damaged"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ({"streams": [{"index": 0, "codec_type": "video"}, {"index": 1, "codec_type": "audio"}]}, 1),
        (
            {
                "streams": [
                    {"index": 1, "codec_type": "audio", "disposition": {"default": 0}},
                    {"index": 2, "codec_type": "audio", "disposition": {"default": 1}},
                ]
            },
            2,
        ),
        ({"streams": [{"index": 0, "codec_type": "video"}]}, None),
        ({}, None),
        ({"streams": "not a list"}, None),
        ({"streams": [None, 7, {"codec_type": "audio"}, {"index": "3", "codec_type": "audio"}]}, None),
        ({"streams": [{"index": True, "codec_type": "audio"}, {"index": 4, "codec_type": "audio"}]}, 4),
        ({"streams": [{"index": 5, "codec_type": "audio", "disposition": "yes"}]}, 5),
    ],
)
def test_pick_audio_stream_is_defensive(document: dict[str, object], expected: int | None) -> None:
    assert pick_audio_stream(document) == expected
