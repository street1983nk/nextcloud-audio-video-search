"""Subtitle cues from word times (EXP-02, D-04-16).

Limits, each a constant with a value test: at most MAX_LINE characters per
line and MAX_LINES lines per cue, duration MIN_MS to MAX_MS, at most MAX_CPS
characters per second, at least GAP_MS between cues, a pause above
PAUSE_CUT_MS closes the open cue. Sources: .planning/research/FEATURES.md
(Netflix German TTSG: 42 characters, 2 lines, 20 cps for same-language SDH;
ARD standing time 1 s; BITV 7.1.2 synchronicity, so word start times are
never shifted, only the cue end stretches into pauses).

Decision D-04-16: the limits are best effort and the text is NEVER changed.
Unavoidable overruns (fast speech, verbatim text) are minimized by stretching
the timing, counted by ``count_overruns`` and gated in the tests. A word above
MAX_LINE characters stays unbroken alone on its line.

Control characters and line breaks inside a surface would break the SRT/VTT
formats; each run of them becomes one space (T-04-20), everything else stays
byte for byte. The input is walked once and backtracking never reaches past
the words of the open cue, so long inputs stay linear (T-04-19, measured at
100 000 words in plan 04-08).

Nothing here logs: the words are content and never belong in a log line.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from audio_video_search_backend.model.overlay import Word

MAX_LINE: Final = 42
MAX_LINES: Final = 2
MIN_MS: Final = 1000
MAX_MS: Final = 7000
MAX_CPS: Final = 20
GAP_MS: Final = 80
PAUSE_CUT_MS: Final = 700


@dataclass(frozen=True, slots=True)
class Cue:
    """One subtitle cue: times in whole milliseconds, lines already broken."""

    start_ms: int
    end_ms: int
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Overruns:
    """Counted soft-limit overruns (D-04-16): named and gated, never fixed by changing text."""

    cps: int
    short: int
    gap: int
    long_word: int
    total: int


def build_cues(words: Sequence[Word]) -> list[Cue]:
    """Cues from word times under the EXP-02 limits; the text is never changed."""
    raise NotImplementedError(f"build_cues over {len(words)} words")


def count_overruns(cues: Sequence[Cue]) -> Overruns:
    """How many cues overrun each soft limit: cps, standing time, gap, long word."""
    raise NotImplementedError(f"count_overruns over {len(cues)} cues")
