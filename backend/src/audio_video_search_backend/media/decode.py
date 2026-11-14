"""ffmpeg: one chunk of one audio track as 16 kHz mono f32 PCM.

The command is the one measured in RESEARCH Pattern 1 (M-1 to M-5):

- ``-ss``/``-t`` before ``-i`` seek as input options, sample exact for every
  tested format (M-2).
- ``-map 0:<index>`` takes the track probe.py chose, never ffmpeg's own pick.
- ``aresample=async=1:first_pts=0`` keeps the time axis of the container: it
  fills the silence in front of audio that starts after the video (edit list)
  and cuts encoder priming. Without it a beep behind an edit list lands 1,98 s
  early (M-1).
- ``-protocol_whitelist file`` and ``-format_whitelist`` as in probe.py,
  ``-threads 1``, ``-fs`` for the bytes one chunk may yield, and a wall time.

A failed run, a killed run, or far fewer samples than expected make the chunk
``damaged``; a refused demuxer makes it ``format_unsupported``. The error
output is read for that one distinction and never logged.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from audio_video_search_backend.media.probe import DAMAGED, DEMUXERS, failure_reason, run_tool

LOGGER = logging.getLogger(__name__)

FFMPEG: Final = Path("/usr/local/bin/ffmpeg")
SAMPLE_RATE: Final = 16000
DECODE_WALL_SECONDS: Final = 300
# A chunk with fewer samples than half its expected length is damaged.
MIN_SAMPLE_SHARE: Final = 0.5
_BYTES_PER_SAMPLE: Final = 4

__all__ = ["DEMUXERS", "FFMPEG", "SAMPLE_RATE", "DecodeResult", "decode_chunk"]


@dataclass(frozen=True, slots=True)
class DecodeResult:
    """The PCM of a chunk (f32 little endian, 16 kHz, mono), or the reason there is none."""

    pcm: bytes
    reason: str | None


def max_bytes(dur_ms: int) -> int:
    """The output limit of one chunk: its length plus one second."""
    return (math.ceil(dur_ms / 1000) + 1) * SAMPLE_RATE * _BYTES_PER_SAMPLE


def _refused(reason: str, exit_code: int | None) -> DecodeResult:
    # A code and an exit code; never the path, never the error output.
    LOGGER.info("media decode refused", extra={"reason": reason, "exit_code": exit_code})
    return DecodeResult(pcm=b"", reason=reason)


def decode_chunk(
    path: Path,
    stream_index: int,
    start_ms: int,
    dur_ms: int,
    *,
    expected_ms: int | None,
    ffmpeg: Path = FFMPEG,
    wall_seconds: float = DECODE_WALL_SECONDS,
) -> DecodeResult:
    """Decode ``[start_ms, start_ms + dur_ms)`` of track ``stream_index`` of the local file ``path``."""
    command = [
        str(ffmpeg),
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-threads",
        "1",
        "-protocol_whitelist",
        "file",
        "-format_whitelist",
        DEMUXERS,
        "-ss",
        f"{start_ms / 1000:.3f}",
        "-t",
        f"{dur_ms / 1000:.3f}",
        "-i",
        str(path),
        "-map",
        f"0:{stream_index}",
        "-vn",
        "-sn",
        "-dn",
        "-af",
        "aresample=async=1:first_pts=0",
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-c:a",
        "pcm_f32le",
        "-f",
        "f32le",
        "-fs",
        str(max_bytes(dur_ms)),
        "pipe:1",
    ]
    completed = run_tool(command, wall_seconds)
    if completed.exit_code != 0:
        return _refused(failure_reason(completed), completed.exit_code)
    pcm = completed.stdout[: len(completed.stdout) - len(completed.stdout) % _BYTES_PER_SAMPLE]
    if expected_ms is not None:
        expected_samples = expected_ms * SAMPLE_RATE // 1000
        if len(pcm) // _BYTES_PER_SAMPLE < MIN_SAMPLE_SHARE * expected_samples:
            return _refused(DAMAGED, completed.exit_code)
    return DecodeResult(pcm=pcm, reason=None)
