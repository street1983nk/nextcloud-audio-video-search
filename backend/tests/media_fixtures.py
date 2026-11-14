"""Test media made at run time by ffmpeg; no media file is ever checked in.

The tests find ffmpeg and ffprobe through AVS_FFMPEG / AVS_FFPROBE (python.yml
sets both to the pinned BtbN build of the image) or on PATH, never through a
fixed path. Without them a media test skips with its reason; under CI=true it
fails instead, so a runner that lost its ffmpeg cannot turn the media gates
into a row of silent skips. The same holds for a missing encoder: the LGPL
build has no libx264, so video is MPEG-4 part 2 (mpeg4) or VP8/VP9 (libvpx),
and every encoder is picked from what ``ffmpeg -encoders`` really lists.

Signals are pure tones and beeps from the lavfi sources, measured back with
the standard library only (the backend has no numpy): a beep onset is the
first sample above half its amplitude after a quiet stretch.
"""

from __future__ import annotations

import array
import itertools
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

SAMPLE_RATE = 16000
BEEP_AMPLITUDE = 0.5
BEEP_HZ = 1000


def in_ci() -> bool:
    return os.environ.get("CI", "").strip().lower() == "true"


def missing(reason: str) -> None:
    """Skip with the reason, or fail under CI=true: no media case may vanish there."""
    if in_ci():
        pytest.fail(f"{reason} (CI=true: a media test must not skip)")
    pytest.skip(reason)


def find_tool(env: str, name: str) -> Path:
    configured = os.environ.get(env, "").strip()
    if configured:
        path = Path(configured)
        if not path.is_file():
            missing(f"{env} points at no file")
        return path
    found = shutil.which(name)
    if found is None:
        missing(f"{name} not available")
        raise AssertionError  # unreachable, pytest.skip and pytest.fail raise
    return Path(found)


@pytest.fixture(scope="session")
def ffmpeg_bin() -> Path:
    return find_tool("AVS_FFMPEG", "ffmpeg")


@pytest.fixture(scope="session")
def ffprobe_bin() -> Path:
    return find_tool("AVS_FFPROBE", "ffprobe")


@pytest.fixture(scope="session")
def encoders(ffmpeg_bin: Path) -> frozenset[str]:
    return list_encoders(ffmpeg_bin)


def list_encoders(ffmpeg: Path) -> frozenset[str]:
    listing = subprocess.run(  # noqa: S603 - an argument list, never a shell
        [str(ffmpeg), "-hide_banner", "-encoders"], capture_output=True, text=True, check=True
    ).stdout
    names: set[str] = set()
    started = False
    for line in listing.splitlines():
        if line.strip().startswith("------"):
            started = True
            continue
        parts = line.split()
        if started and len(parts) >= 2:
            names.add(parts[1])
    return frozenset(names)


def pick_encoder(available: frozenset[str], *candidates: str) -> str:
    for name in candidates:
        if name in available:
            return name
    missing(f"no encoder of {', '.join(candidates)} in this ffmpeg")
    raise AssertionError  # unreachable


def run_ffmpeg(ffmpeg: Path, *args: str) -> None:
    done = subprocess.run(  # noqa: S603 - an argument list, never a shell
        [str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]


# --- signals -------------------------------------------------------------------


def tone(ffmpeg: Path, out: Path, seconds: float, hz: int = 440) -> Path:
    """A steady tone at 44.1 kHz, peak 0,4 (sine gives 1/8), so the decoded length is the whole file."""
    source = f"sine=frequency={hz}:duration={seconds}:sample_rate=44100"
    run_ffmpeg(ffmpeg, "-f", "lavfi", "-i", source, "-af", "volume=3.2", "-c:a", "pcm_s16le", str(out))
    return out


def beeps(ffmpeg: Path, out: Path, seconds: float, condition: str) -> Path:
    """Silence with a 1 kHz beep wherever ``condition`` (an ffmpeg expression in t) holds."""
    expression = f"{BEEP_AMPLITUDE}*sin(2*PI*{BEEP_HZ}*t)*({condition})"
    # Quoted: the commas of the expression would otherwise split the filter graph.
    source = f"aevalsrc='{expression}':s=44100:d={seconds}"
    run_ffmpeg(ffmpeg, "-f", "lavfi", "-i", source, "-c:a", "pcm_s16le", str(out))
    return out


def video_input(seconds: float, size: str = "64x64", rate: int = 5) -> list[str]:
    return ["-f", "lavfi", "-i", f"testsrc=size={size}:rate={rate}:duration={seconds}"]


# --- the ten formats -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Format:
    name: str
    suffix: str
    audio: tuple[str, ...]
    video: tuple[str, ...] = ()


FORMATS: tuple[Format, ...] = (
    Format("mp3", ".mp3", ("libmp3lame",)),
    Format("m4a", ".m4a", ("aac",)),
    Format("wav", ".wav", ("pcm_s16le",)),
    Format("ogg", ".ogg", ("libvorbis", "vorbis")),
    Format("opus", ".opus", ("libopus", "opus")),
    Format("flac", ".flac", ("flac",)),
    Format("mp4", ".mp4", ("aac",), ("mpeg4",)),
    Format("mov", ".mov", ("aac",), ("mpeg4",)),
    Format("mkv", ".mkv", ("aac",), ("mpeg4",)),
    Format("webm", ".webm", ("libopus", "opus"), ("libvpx", "libvpx-vp9")),
)
FORMAT_NAMES: tuple[str, ...] = tuple(spec.name for spec in FORMATS)


def format_by_name(name: str) -> Format:
    return next(spec for spec in FORMATS if spec.name == name)


def audio_codec_args(codec: str) -> list[str]:
    args = ["-c:a", codec]
    if codec in {"opus", "vorbis"}:
        # The native encoders are marked experimental.
        args += ["-strict", "-2"]
    if codec in {"opus", "libopus"}:
        args += ["-ar", "48000"]
    if codec == "libmp3lame":
        args += ["-b:a", "128k"]
    return args


def encode(ffmpeg: Path, available: frozenset[str], source: Path, out_dir: Path, name: str) -> Path:
    """Encode ``source`` (a WAV) into one of the ten formats; video formats get a test picture."""
    spec = format_by_name(name)
    audio = pick_encoder(available, *spec.audio)
    out = out_dir / f"{source.stem}{spec.suffix}"
    if not spec.video:
        run_ffmpeg(ffmpeg, "-i", str(source), *audio_codec_args(audio), str(out))
        return out
    video = pick_encoder(available, *spec.video)
    seconds = wav_seconds(source)
    run_ffmpeg(
        ffmpeg,
        *video_input(seconds),
        "-i",
        str(source),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        video,
        *audio_codec_args(audio),
        str(out),
    )
    return out


def wav_seconds(path: Path) -> float:
    import wave

    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


# --- reading PCM back ----------------------------------------------------------


def samples(pcm: bytes) -> array.array[float]:
    values = array.array("f")
    values.frombytes(pcm)
    if sys.byteorder != "little":
        values.byteswap()
    return values


def seconds_of(pcm: bytes) -> float:
    return len(pcm) / 4 / SAMPLE_RATE


def peak(pcm: bytes) -> float:
    values = samples(pcm)
    return max((abs(v) for v in values), default=0.0)


def onsets(pcm: bytes, quiet_seconds: float = 0.5) -> list[float]:
    """Seconds of every beep onset: a sample above half the beep amplitude after a quiet stretch."""
    values = samples(pcm)
    threshold = BEEP_AMPLITUDE / 2
    quiet = int(quiet_seconds * SAMPLE_RATE)
    found: list[float] = []
    last_loud = -quiet - 1
    for index, value in enumerate(values):
        if abs(value) > threshold:
            if index - last_loud > quiet:
                found.append(index / SAMPLE_RATE)
            last_loud = index
    return found


def dominant_hz(pcm: bytes, seconds: float = 1.0, start: float = 0.5) -> float:
    """Frequency of a steady tone from its zero crossings over ``seconds`` from ``start``.

    The first half second is left out: AAC in Matroska decodes the first
    ~22 ms near silent (measured; the time axis is not shifted, a beep at 5 s
    stays at 5 s), and silence has no crossings.
    """
    values = samples(pcm)[int(start * SAMPLE_RATE) : int((start + seconds) * SAMPLE_RATE)]
    crossings = sum(1 for a, b in itertools.pairwise(values) if (a < 0) != (b < 0))
    return crossings / 2 / seconds
