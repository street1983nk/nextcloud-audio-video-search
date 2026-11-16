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
from audio_video_search_backend.subtitles.cues import Cue

TXT_PARAGRAPH_PAUSE_MS: Final = 2000


def to_srt(cues: Sequence[Cue]) -> str:
    """The cues as one SRT text; an empty list yields an empty string."""
    raise NotImplementedError


def to_vtt(cues: Sequence[Cue]) -> str:
    """The cues as one WebVTT text; an empty list yields only the header."""
    raise NotImplementedError


def to_txt(words: Sequence[Word]) -> str:
    """The words as flow text with paragraphs at long pauses; no time marks."""
    raise NotImplementedError
