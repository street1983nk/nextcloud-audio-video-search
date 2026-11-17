"""SRT, VTT and TXT from cues and words (EXP-01, EXP-02, plan 04-08).

Format rules (04-RESEARCH "Formate", 04-UI-SPEC "Dateiinhalte"): VTT starts
with ``WEBVTT`` and a blank line, times are ``HH:MM:SS.mmm --> HH:MM:SS.mmm``
and the cue text masks ``&`` ``<`` ``>`` (T-04-21); SRT numbers its cues from
1, uses a comma before the milliseconds and carries the text raw. Hours take
two digits, three above 99 h. Everything is LF only; the caller writes UTF-8
without a BOM. No cue block ever contains a blank line.

No header, NOTE or file name is written here: the localized headers live in
PHP (D-04-03) and nothing the container receives carries a name (gate rule
13). The writers add no words of their own (T-04-23); proof over the three
independent checkers webvtt-py, srt and ffmpeg lives in the tests.

TXT is flow text without time marks: words joined by spaces, a new paragraph
after a pause above TXT_PARAGRAPH_PAUSE_MS, control character runs become one
space exactly like the cue builder (T-04-20).

Nothing here logs: the words are content and never belong in a log line.
"""

from collections.abc import Sequence
from typing import Final

from audio_video_search_backend.model.overlay import Word

# The private control-run pattern is shared on purpose: T-04-20 has exactly
# one definition, so TXT cleans a surface precisely like the cue builder.
from audio_video_search_backend.subtitles.cues import _CONTROL, Cue

TXT_PARAGRAPH_PAUSE_MS: Final = 2000

# "&" first, or the mask would escape its own ampersands (T-04-21).
_VTT_MASK: Final = (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"))


def _clock(ms: int, sep: str) -> str:
    """``HH:MM:SS<sep>mmm``, hours two digits, three above 99 h."""
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, milli = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{sep}{milli:03d}"


def _escape_vtt(text: str) -> str:
    """The cue text with ``&`` ``<`` ``>`` masked, nothing else touched."""
    for raw, masked in _VTT_MASK:
        text = text.replace(raw, masked)
    return text


def to_srt(cues: Sequence[Cue]) -> str:
    """The cues as one SRT text; an empty list yields an empty string."""
    blocks = (
        f"{number}\n{_clock(cue.start_ms, ',')} --> {_clock(cue.end_ms, ',')}\n" + "\n".join(cue.lines)
        for number, cue in enumerate(cues, start=1)
    )
    body = "\n\n".join(blocks)
    return body + "\n" if body else ""


def to_vtt(cues: Sequence[Cue]) -> str:
    """The cues as one WebVTT text; an empty list yields only the header."""
    blocks = (
        f"{_clock(cue.start_ms, '.')} --> {_clock(cue.end_ms, '.')}\n"
        + "\n".join(_escape_vtt(line) for line in cue.lines)
        for cue in cues
    )
    body = "\n\n".join(blocks)
    return "WEBVTT\n\n" + (body + "\n" if body else "")


def to_txt(words: Sequence[Word]) -> str:
    """The words as flow text with paragraphs at long pauses; no time marks."""
    parts: list[str] = []
    previous_end: int | None = None
    for word in sorted(words, key=lambda w: (w.start_ms, w.end_ms)):
        start = int(word.start_ms)
        end = max(int(word.end_ms), start)
        text = " ".join(part for part in _CONTROL.sub(" ", word.surface).split(" ") if part)
        if not text:
            continue
        if previous_end is not None:
            parts.append("\n\n" if start - previous_end > TXT_PARAGRAPH_PAUSE_MS else " ")
        parts.append(text)
        previous_end = end
    return "".join(parts) + "\n" if parts else ""
