"""ffprobe: which audio track a file has, how long it is, or why it cannot be used.

The rules, all measured in RESEARCH M-4 to M-6:

- Only the ``file`` protocol and a positive list of demuxers. Without them a
  text file named ``.mp3`` opens as a concat playlist and reads any local file
  it names; with them ffprobe stops with "not on whitelist".
- The track is fixed (D-03-10): the audio track marked default, else the first
  audio track. ffmpeg's own choice weighs channels and marks together and is no
  promise, so the caller maps the index explicitly.
- A CENC encrypted MP4 looks like any AAC file to ffprobe; its protection boxes
  (``enca``, ``sinf``, ``schm``, ``tenc``, and ``drms``/``aavd`` of FairPlay
  and Audible) in ``moov`` give it away. Such a file is ``protected``.

The error output of ffprobe can carry the path and the metadata of the file. It
is read once to tell "not on whitelist" apart and never logged; a log line has
the reason and the exit code, nothing else.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

LOGGER = logging.getLogger(__name__)

FFPROBE: Final = Path("/usr/local/bin/ffprobe")
PROBE_WALL_SECONDS: Final = 60
# The demuxers a recording comes in. mov covers MP4, M4A, MOV and 3GP;
# matroska covers MKV and WebM. No concat, no HLS, no image or text format.
DEMUXERS: Final = "mov,mp3,wav,w64,ogg,flac,matroska,aac,asf,avi,amr,aiff,caf,mpegts,mpeg"

NO_AUDIO: Final = "no_audio"
DAMAGED: Final = "damaged"
PROTECTED: Final = "protected"
FORMAT_UNSUPPORTED: Final = "format_unsupported"
MEDIA_REASONS: Final = frozenset({NO_AUDIO, DAMAGED, PROTECTED, FORMAT_UNSUPPORTED})

# What ffmpeg and ffprobe print when the positive list refuses a demuxer.
NOT_ON_WHITELIST: Final = b"not on whitelist"
# The box kinds of encrypted MP4 (CENC: enca, sinf, schm, tenc; FairPlay: drms;
# Audible: aavd) and how much of moov is searched for them.
PROTECTION_MARKS: Final = (b"enca", b"sinf", b"schm", b"tenc", b"drms", b"aavd")
MOOV_SCAN_BYTES: Final = 64 * 1024 * 1024
_MAX_TOP_LEVEL_BOXES: Final = 4096
_HEADER: Final = 8
_LARGE_HEADER: Final = 16


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """The audio track to decode and the length, or the reason the file is refused."""

    stream_index: int | None
    duration_ms: int | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class Completed:
    """One finished tool run; ``exit_code`` is None when the wall time ran out."""

    exit_code: int | None
    stdout: bytes
    stderr: bytes


def run_tool(command: list[str], wall_seconds: float) -> Completed:
    """Run ffmpeg or ffprobe with a hard wall time; on overrun the process is killed and reaped."""
    process = subprocess.Popen(  # noqa: S603 - an argument list, never a shell
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        stdout, stderr = process.communicate(timeout=wall_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return Completed(exit_code=None, stdout=b"", stderr=b"")
    return Completed(exit_code=process.returncode, stdout=stdout, stderr=stderr)


def failure_reason(completed: Completed) -> str:
    """The reason of a failed run: a refused demuxer, or a damaged file (also a timeout)."""
    if completed.exit_code is not None and NOT_ON_WHITELIST in completed.stderr:
        return FORMAT_UNSUPPORTED
    return DAMAGED


def pick_audio_stream(probe_json: dict[str, object]) -> int | None:
    """The audio track marked default, else the first audio track (D-03-10); None without one."""
    streams = probe_json.get("streams")
    if not isinstance(streams, list):
        return None
    audio: list[int] = []
    default: int | None = None
    for stream in streams:
        if not isinstance(stream, dict) or stream.get("codec_type") != "audio":
            continue
        index = stream.get("index")
        if not isinstance(index, int) or isinstance(index, bool):
            continue
        audio.append(index)
        disposition = stream.get("disposition")
        if default is None and isinstance(disposition, dict) and disposition.get("default") == 1:
            default = index
    if default is not None:
        return default
    return audio[0] if audio else None


def _duration_ms(fmt: object) -> int | None:
    if not isinstance(fmt, dict):
        return None
    raw = fmt.get("duration")
    try:
        seconds = float(raw) if isinstance(raw, str | int | float) else None
    except ValueError:
        return None
    if seconds is None or seconds != seconds or seconds < 0:  # NaN or negative
        return None
    return round(seconds * 1000)


def _demuxers(fmt: object) -> list[str]:
    if not isinstance(fmt, dict):
        return []
    name = fmt.get("format_name")
    return name.split(",") if isinstance(name, str) else []


def has_protection_boxes(path: Path) -> bool:
    """Whether a top level ``moov`` box of an MP4 carries a protection box kind."""
    try:
        with path.open("rb") as handle:
            for _ in range(_MAX_TOP_LEVEL_BOXES):
                header = handle.read(_HEADER)
                if len(header) < _HEADER:
                    return False
                size = int.from_bytes(header[:4], "big")
                kind = header[4:8]
                header_size = _HEADER
                if size == 1:
                    large = handle.read(8)
                    if len(large) < 8:
                        return False
                    size = int.from_bytes(large, "big")
                    header_size = _LARGE_HEADER
                if size != 0 and size < header_size:
                    return False
                if kind == b"moov":
                    limit = MOOV_SCAN_BYTES if size == 0 else min(size - header_size, MOOV_SCAN_BYTES)
                    body = handle.read(limit)
                    return any(mark in body for mark in PROTECTION_MARKS)
                if size == 0:
                    return False
                handle.seek(size - header_size, 1)
    except OSError:
        return False
    return False


def _refused(reason: str, exit_code: int | None) -> ProbeResult:
    # A code and an exit code; never the path, never the error output.
    LOGGER.info("media probe refused", extra={"reason": reason, "exit_code": exit_code})
    return ProbeResult(stream_index=None, duration_ms=None, reason=reason)


def probe(path: Path, *, ffprobe: Path = FFPROBE, wall_seconds: float = PROBE_WALL_SECONDS) -> ProbeResult:
    """Track, length and verdict of the local file ``path``."""
    command = [
        str(ffprobe),
        "-protocol_whitelist",
        "file",
        "-format_whitelist",
        DEMUXERS,
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type:stream_disposition=default:format=duration,format_name",
        "-of",
        "json",
        str(path),
    ]
    completed = run_tool(command, wall_seconds)
    if completed.exit_code != 0:
        return _refused(failure_reason(completed), completed.exit_code)
    try:
        document = json.loads(completed.stdout)
    except ValueError:
        return _refused(DAMAGED, completed.exit_code)
    if not isinstance(document, dict):
        return _refused(DAMAGED, completed.exit_code)
    fmt = document.get("format")
    if "mov" in _demuxers(fmt) and has_protection_boxes(path):
        return _refused(PROTECTED, completed.exit_code)
    index = pick_audio_stream(document)
    if index is None:
        return _refused(NO_AUDIO, completed.exit_code)
    return ProbeResult(stream_index=index, duration_ms=_duration_ms(fmt), reason=None)
