"""Independent subtitle checkers for the SRT and WebVTT export (EXP-02, plan 04-04).

The writer is our own code; these checkers are not. Each one reads a subtitle
text with a parser that shares nothing with the writer, so a test that passes
here is a cross check and never the writer agreeing with itself:

* ``check_vtt``: webvtt-py in strict mode plus its own ``validate()`` errors.
* ``check_srt``: ``srt.parse``, which raises ``srt.SRTParseError`` on any
  text it cannot read as a whole.
* ``check_ffmpeg``: the ffmpeg subtitle demuxer and decoder, found only
  through ``media_fixtures.find_tool`` (skip with reason locally, failure
  under CI=true).

Known limits, held as strict xfail in test_subtitle_checkers.py: neither
srt nor ffmpeg notices a missing blank line between two SRT cues (both
recover the two cues), and ffmpeg reads a WebVTT file without its header and
a cue that ends before it starts without a word. So a caller also compares
the exact text it expects, not only "no exception".

Both libraries are owner approved dev pins (webvtt-py 0.8.0, srt 3.5.3) and
never reach the image. Plans 04-08, 04-09 and 04-14 import from here.
"""

from __future__ import annotations

import html
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import srt
import webvtt
from webvtt.errors import WebVTTError

from tests.media_fixtures import find_tool

_MILLISECOND = timedelta(milliseconds=1)


@dataclass(frozen=True)
class Cue:
    """One cue as an independent parser read it: times in milliseconds, plain text."""

    start_ms: int
    end_ms: int
    text: str


class SubtitleCheckError(AssertionError):
    """A checker found the subtitle text invalid."""


def _read_vtt(text: str) -> webvtt.WebVTT:
    try:
        document = webvtt.WebVTT.from_string(text, strict=True)
    except (WebVTTError, ValueError) as error:
        raise SubtitleCheckError(f"webvtt-py: {error}") from error
    errors = [issue for issue in document.validate() if issue.severity == "error"]
    if errors:
        raise SubtitleCheckError(f"webvtt-py: {errors}")
    if not document.captions:
        raise SubtitleCheckError("webvtt-py: no caption read")
    return document


def check_vtt(text: str) -> None:
    """Raise SubtitleCheckError unless webvtt-py reads the text as valid WebVTT."""
    _read_vtt(text)


def read_vtt_captions(text: str) -> list[Cue]:
    """The cues of a valid WebVTT text, read by webvtt-py (check first, then read).

    webvtt-py keeps character references as written (``&amp;`` stays
    ``&amp;``), so the text is unescaped once here to compare it with what a
    viewer shows.
    """
    return [
        Cue(caption.start_in_milliseconds, caption.end_in_milliseconds, html.unescape(caption.text))
        for caption in _read_vtt(text).captions
    ]


def _read_srt(text: str) -> list[srt.Subtitle]:
    try:
        subtitles = list(srt.parse(text))
    except srt.SRTParseError as error:
        raise SubtitleCheckError(f"srt: {error}") from error
    if not subtitles:
        raise SubtitleCheckError("srt: no subtitle read")
    for subtitle in subtitles:
        if subtitle.end <= subtitle.start:
            raise SubtitleCheckError(f"srt: subtitle {subtitle.index} ends before it starts")
        # srt keeps anything after the timing as proprietary cue settings; plain
        # SRT has none, so text there is a cue line that slipped onto the timing.
        if subtitle.proprietary.strip():
            raise SubtitleCheckError(f"srt: subtitle {subtitle.index} has text on its timing line")
    return subtitles


def check_srt(text: str) -> None:
    """Raise SubtitleCheckError unless srt.parse reads the whole text."""
    _read_srt(text)


def read_srt_subtitles(text: str) -> list[Cue]:
    """The subtitles of a valid SRT text, read by srt (check first, then read)."""
    return [
        Cue(
            subtitle.start // _MILLISECOND,
            subtitle.end // _MILLISECOND,
            subtitle.content,
        )
        for subtitle in _read_srt(text)
    ]


def check_ffmpeg(text: str, suffix: str, expected_cues: int | None = None) -> None:
    """Raise SubtitleCheckError unless ffmpeg demuxes and decodes every cue silently.

    ``suffix`` is ".vtt" or ".srt"; ffmpeg picks its demuxer from it and from
    the content. The file goes into a fresh temporary directory, ffmpeg runs
    with an argument list (never a shell), decodes the first subtitle stream
    and re-encodes it as SRT on stdout. It fails on a non zero exit, on any
    word on stderr, on zero decoded cues, and, when ``expected_cues`` is
    given, on a cue count other than the one the caller wrote: ffmpeg skips a
    cue it cannot read without a message, so only the count shows the loss.
    """
    ffmpeg = find_tool("AVS_FFMPEG", "ffmpeg")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"subtitle{suffix}"
        path.write_text(text, encoding="utf-8", newline="")
        result = subprocess.run(  # noqa: S603 - an argument list, never a shell
            [
                str(ffmpeg),
                *("-hide_banner", "-nostdin", "-v", "error", "-i", str(path)),
                *("-map", "0:s:0", "-c:s", "srt", "-f", "srt", "pipe:1"),
            ],
            capture_output=True,
            check=False,
            timeout=60,
        )
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode != 0 or stderr:
        raise SubtitleCheckError(f"ffmpeg rc={result.returncode}: {stderr}")
    decoded = result.stdout.decode("utf-8", errors="replace")
    cues = sum(1 for line in decoded.splitlines() if "-->" in line)
    if cues == 0:
        raise SubtitleCheckError("ffmpeg: no cue decoded")
    if expected_cues is not None and cues != expected_cues:
        raise SubtitleCheckError(f"ffmpeg: decoded {cues} cues, expected {expected_cues}")
