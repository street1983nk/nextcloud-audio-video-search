"""User corrections laid over the current machine words (decision 4).

A correction is anchored at audio time ``[start_ms, end_ms)`` of a media item,
never at word indices: indices change with every machine version, the audio
time of the same content does not. A machine word whose midpoint
``(start_ms + end_ms) // 2`` lies in the half-open span is replaced by the words
of the correction; everything outside comes from the current machine version.

All times are whole milliseconds. Floats would drift in exactly the comparisons
this module is made of (pitfall 8).

Only ``kind == "text"`` changes the word sequence. The kinds ``speaker`` and
``sound`` leave it unchanged in phase 1; how they are shown comes in phase 10.

Nothing here logs: the words are content and never belong in a log line.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass

_EDGE_PUNCTUATION = "".join(
    [
        ".,;:!?",
        "\"'`()[]{}<>",
        "\u00ab\u00bb\u2018\u2019\u201a\u201c\u201d\u201e\u2039\u203a",
        "-/\\*_\u2026",
    ]
)


@dataclass(frozen=True, slots=True)
class Word:
    """One word with its audio time in whole milliseconds."""

    start_ms: int
    end_ms: int
    surface: str
    norm: str
    conf: float
    src: str


@dataclass(frozen=True, slots=True)
class Correction:
    """One active user correction of a media item."""

    correction_id: int
    media_id: int
    start_ms: int
    end_ms: int
    kind: str
    body: str
    words_json: str | None


def normalize(surface: str) -> str:
    """Casefold and strip punctuation at both edges."""
    return surface.casefold().strip(_EDGE_PUNCTUATION)


def _mid(w: Word) -> int:
    return (w.start_ms + w.end_ms) // 2


def _user_word(start_ms: int, end_ms: int, surface: str) -> Word:
    return Word(start_ms=start_ms, end_ms=end_ms, surface=surface, norm=normalize(surface), conf=1.0, src="user")


def _correction_words(c: Correction) -> list[Word]:
    if c.words_json is not None:
        items = json.loads(c.words_json)
        return [_user_word(int(i["start_ms"]), int(i["end_ms"]), str(i["surface"])) for i in items]
    surfaces = c.body.split()
    if not surfaces:
        return []
    span = c.end_ms - c.start_ms
    n = len(surfaces)
    # Integer arithmetic only: slot k covers [start + span*k//n, start + span*(k+1)//n].
    return [_user_word(c.start_ms + span * k // n, c.start_ms + span * (k + 1) // n, s) for k, s in enumerate(surfaces)]


def effective_words(machine: Sequence[Word], corrections: Sequence[Correction]) -> list[Word]:
    """The word sequence a reader sees: machine words with corrections laid over."""
    spans = sorted((c for c in corrections if c.kind == "text"), key=lambda c: c.start_ms)
    out: list[Word] = []
    i = 0
    for c in spans:
        while i < len(machine) and _mid(machine[i]) < c.start_ms:
            out.append(machine[i])
            i += 1
        while i < len(machine) and _mid(machine[i]) < c.end_ms:
            i += 1
        out.extend(_correction_words(c))
    out.extend(machine[i:])
    return out
