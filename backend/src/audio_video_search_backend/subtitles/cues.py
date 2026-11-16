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

import re
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

# A run of whitespace or C0/C1 control characters inside a surface becomes one
# space (T-04-20); \s alone misses the non-space controls like NUL or BEL.
_CONTROL: Final = re.compile(r"[\s\u0000-\u001f\u007f-\u009f]+")
# Closing quotes and brackets that may trail the punctuation of a token.
_TRAILING: Final = "\"'»«’“”)]"  # noqa: RUF001 - typographic quotes on purpose, never confusables
_SENTENCE_END: Final = ".?!"
_CLAUSE_END: Final = ",;:"
_BREAK_PUNCT: Final = ".?!,;:"
# Cut rank 2 (04-RESEARCH pattern 5): never break right before these words.
_CONJUNCTIONS: Final = frozenset({"und", "oder", "aber", "dass", "and", "but", "or", "et", "ou", "mais", "que"})
# A gap this long reads as a breath and ranks as a cut; longer than
# PAUSE_CUT_MS never occurs inside an open cue, that pause closed it already.
_PAUSE_RANK_MS: Final = 300


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


@dataclass(frozen=True, slots=True)
class _Token:
    """One visible token with the time of the word it came from."""

    start_ms: int
    end_ms: int
    text: str


def build_cues(words: Sequence[Word]) -> list[Cue]:
    """Cues from word times under the EXP-02 limits; the text is never changed.

    The input is sorted by ``(start_ms, end_ms)`` first; a word whose end lies
    before its start keeps its text and gets ``end = start`` for the timing.
    """
    tokens = _tokens(words)
    if not tokens:
        return []
    groups = _grouped(tokens)
    cues = _timed(groups)
    joined = _joined(groups, cues)
    return _timed(joined) if joined is not None else cues


def count_overruns(cues: Sequence[Cue]) -> Overruns:
    """How many cues overrun each soft limit: cps, standing time, gap, long word."""
    cps = short = gap = long_word = 0
    for index, cue in enumerate(cues):
        duration = cue.end_ms - cue.start_ms
        if len(" ".join(cue.lines)) * 1000 > MAX_CPS * duration:
            cps += 1
        if duration < MIN_MS:
            short += 1
        if index and cue.start_ms - cues[index - 1].end_ms < GAP_MS:
            gap += 1
        long_word += sum(1 for line in cue.lines if len(line) > MAX_LINE)
    return Overruns(cps=cps, short=short, gap=gap, long_word=long_word, total=cps + short + gap + long_word)


def _tokens(words: Sequence[Word]) -> list[_Token]:
    out: list[_Token] = []
    for word in sorted(words, key=lambda w: (w.start_ms, w.end_ms)):
        start = int(word.start_ms)
        end = max(int(word.end_ms), start)
        out.extend(_Token(start, end, part) for part in _CONTROL.sub(" ", word.surface).split(" ") if part)
    return out


def _bare(text: str) -> str:
    return text.rstrip(_TRAILING)


def _ends_sentence(text: str) -> bool:
    bare = _bare(text)
    return bool(bare) and bare[-1] in _SENTENCE_END


def _ends_clause(text: str) -> bool:
    bare = _bare(text)
    return bool(bare) and bare[-1] in _CLAUSE_END


def _ends_break_punct(text: str) -> bool:
    bare = _bare(text)
    return bool(bare) and bare[-1] in _BREAK_PUNCT


def _lines(texts: Sequence[str]) -> tuple[str, ...] | None:
    """At most MAX_LINES lines of at most MAX_LINE characters each, or None.

    A line may exceed MAX_LINE only as a single unbroken word (D-04-16). With
    two lines the break with both lines in bounds and the smallest length
    difference wins, a break right after punctuation is preferred.
    """
    if len(texts) == 1:
        return (texts[0],)
    whole = " ".join(texts)
    if len(whole) <= MAX_LINE:
        return (whole,)
    sizes = [len(text) + 1 for text in texts]
    total = sum(sizes) - 1
    best: tuple[int, int, int] | None = None
    best_position = 0
    left = 0
    for position in range(1, len(texts)):
        left += sizes[position - 1]
        left_length = left - 1
        right_length = total - left
        left_fits = left_length <= MAX_LINE or position == 1
        right_fits = right_length <= MAX_LINE or position == len(texts) - 1
        if not (left_fits and right_fits):
            continue
        key = (0 if _ends_break_punct(texts[position - 1]) else 1, abs(left_length - right_length), position)
        if best is None or key < best:
            best, best_position = key, position
    if best is None:
        return None
    return (" ".join(texts[:best_position]), " ".join(texts[best_position:]))


def _takes(open_: list[_Token], token: _Token) -> bool:
    """Whether the open cue can take the next token and still break into lines in time."""
    span = max(max(t.end_ms for t in open_), token.end_ms) - open_[0].start_ms
    if span > MAX_MS:
        return False
    return _lines([t.text for t in open_] + [token.text]) is not None


def _cut(open_: list[_Token], incoming: _Token) -> int:
    """The best close position 1..len(open_): rank first, then balance, then the latest.

    Rank (04-RESEARCH pattern 5): sentence end, pause, clause punctuation,
    before a conjunction, any word boundary. Balance keeps the tail cue from
    ending up a lone word that cannot reach its minimum standing time.
    """
    sizes = [len(t.text) + 1 for t in open_] + [len(incoming.text) + 1]
    total = sum(sizes) - 1
    best: tuple[int, int, int] | None = None
    best_position = len(open_)
    left = 0
    for position in range(1, len(open_) + 1):
        left += sizes[position - 1]
        before = open_[position - 1]
        after = open_[position] if position < len(open_) else incoming
        if _ends_sentence(before.text):
            rank = 5
        elif after.start_ms - before.end_ms >= _PAUSE_RANK_MS:
            rank = 4
        elif _ends_clause(before.text):
            rank = 3
        elif after.text.casefold() in _CONJUNCTIONS:
            rank = 2
        else:
            rank = 1
        key = (-rank, abs((left - 1) - (total - left)), -position)
        if best is None or key < best:
            best, best_position = key, position
    return best_position


def _grouped(tokens: Sequence[_Token]) -> list[list[_Token]]:
    """Greedy grouping with a bounded step back to the best cut (T-04-19)."""
    groups: list[list[_Token]] = []
    open_: list[_Token] = []
    for token in tokens:
        if open_ and token.start_ms - open_[-1].end_ms > PAUSE_CUT_MS:
            groups.append(open_)
            open_ = []
        while open_ and not _takes(open_, token):
            cut = _cut(open_, token)
            groups.append(open_[:cut])
            open_ = open_[cut:]
        open_.append(token)
        if _ends_sentence(token.text) and len(" ".join(t.text for t in open_)) >= MAX_LINE:
            groups.append(open_)
            open_ = []
    if open_:
        groups.append(open_)
    return groups


def _reading_ms(chars: int) -> int:
    """The standing time MAX_CPS allows for this many characters, rounded up."""
    return -(-chars * 1000 // MAX_CPS)


def _timed(groups: Sequence[list[_Token]]) -> list[Cue]:
    """Times per group: start at the first word, the end stretched into the pause.

    ``end = max(last word end, start + MIN_MS, start + reading time)``, capped
    at ``start + MAX_MS`` and at ``next start - GAP_MS``. A following start is
    never moved later than monotony demands, at most to the word time
    (BITV 7.1.2 synchronicity).
    """
    cues: list[Cue] = []
    previous_end: int | None = None
    for index, group in enumerate(groups):
        lines = _lines([t.text for t in group])
        if lines is None:  # pragma: no cover - a group only closes while it still breaks
            raise AssertionError("a closed group no longer breaks into lines")
        start = group[0].start_ms if previous_end is None else max(group[0].start_ms, previous_end)
        raw_end = max(t.end_ms for t in group)
        desired = max(raw_end, start + MIN_MS, start + _reading_ms(len(" ".join(lines))))
        end = min(desired, start + MAX_MS)
        if index + 1 < len(groups):
            limit = groups[index + 1][0].start_ms - GAP_MS
            end = min(end, limit) if limit > start else start + 1
        cues.append(Cue(start_ms=start, end_ms=end, lines=lines))
        previous_end = end
    return cues


def _joined(groups: list[list[_Token]], cues: list[Cue]) -> list[list[_Token]] | None:
    """Short colliding cues joined into their left neighbour where the limits allow.

    Returns the new groups, or None when nothing changed. Only a cue whose
    stretching collided with its follower can be short; the last cue always
    reaches MIN_MS.
    """
    out: list[list[_Token]] = []
    changed = False
    for group, cue in zip(groups, cues, strict=True):
        if out and cue.end_ms - cue.start_ms < MIN_MS and _may_join(out[-1], group):
            out[-1] = out[-1] + group
            changed = True
        else:
            out.append(group)
    return out if changed else None


def _may_join(left: list[_Token], right: list[_Token]) -> bool:
    if right[0].start_ms - left[-1].end_ms > PAUSE_CUT_MS:
        return False
    both = left + right
    if max(t.end_ms for t in both) - both[0].start_ms > MAX_MS:
        return False
    return _lines([t.text for t in both]) is not None
