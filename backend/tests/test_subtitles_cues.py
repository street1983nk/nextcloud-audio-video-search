"""Properties of the cue builder (EXP-02, D-04-16, plan 04-07).

Fixtures and expectations are independent test code: the NORMAL and FAST
generators, the token cleaning and the SRT serialization here never call into
cues.py, and the round trip check parses with tests.subtitle_checkers
(the srt library), which shares nothing with the implementation (owner rule:
the cross check never uses the pattern of the implementation).
"""

import itertools
import random
import unicodedata
from collections.abc import Sequence
from typing import Final

from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.subtitles.cues import (
    GAP_MS,
    MAX_CPS,
    MAX_LINE,
    MAX_LINES,
    MAX_MS,
    MIN_MS,
    PAUSE_CUT_MS,
    Cue,
    Overruns,
    build_cues,
    count_overruns,
)
from tests.subtitle_checkers import read_srt_subtitles

# Schwelle für die FAST-Fixture (D-04-16): wortgetreuer Text bei 4,5 Wörtern/s
# ohne Pausen braucht rund 28 Zeichen/s, eine Dehnung ist physisch unmöglich;
# nur der letzte Cue kann sich frei dehnen. Gemessen am 2026-11-16: 0,9762
# (41 von 42 Cues über 20 Zeichen/s). Der 5-%-Schritt des Plans wäre 1,00 und
# damit kein Gate mehr; deshalb auf den nächsten 1-%-Schritt aufgerundet, so
# schlägt der Test an, sobald auch der letzte Cue die Rate reißt.
FAST_SPEECH_MAX_OVER_CPS_SHARE: Final = 0.98

_LETTERS: Final = "abcdefghijklmnopqrstuvwxyz"
_SEED: Final = 20261116
# Wortlängen 3 bis 12, kurze Wörter häufig: mittlere Länge 5,3 Zeichen.
_LENGTH_WEIGHTS: Final = [26, 20, 16, 12, 9, 7, 4, 3, 2, 1]


def _word(start_ms: int, end_ms: int, surface: str) -> Word:
    return Word(start_ms, end_ms, surface, surface.casefold(), 1.0, "machine")


def _spoken(surfaces: Sequence[str], *, char_ms: int = 61, pause_after: dict[int, int] | None = None) -> list[Word]:
    """Words laid out like speech: one character takes ``char_ms``, one space between words."""
    words: list[Word] = []
    cursor = 0
    for index, surface in enumerate(surfaces):
        end = cursor + len(surface) * char_ms
        words.append(_word(cursor, end, surface))
        cursor = end + char_ms + (pause_after or {}).get(index, 0)
    return words


def _visible_tokens(words: Sequence[Word]) -> list[str]:
    """What a reader may see: every control or whitespace character of a surface as a space (T-04-20)."""
    tokens: list[str] = []
    for word in sorted(words, key=lambda w: (w.start_ms, w.end_ms)):
        cleaned = "".join(" " if ch.isspace() or unicodedata.category(ch) == "Cc" else ch for ch in word.surface)
        tokens.extend(cleaned.split())
    return tokens


def _cue_tokens(cues: Sequence[Cue]) -> list[str]:
    """The exact formula of the plan: all lines of all cues joined with spaces, split again."""
    joined = " ".join(line for cue in cues for line in cue.lines)
    return joined.split(" ") if joined else []


def _speech(rng: random.Random, count: int, char_ms: int, pause_range: tuple[int, int] | None) -> list[Word]:
    """Deterministic speech: sentences of 8 to 15 words, word lengths 3 to 12."""
    surfaces: list[str] = []
    pause_after: dict[int, int] = {}
    left = rng.randint(8, 15)
    for index in range(count):
        length = rng.choices(range(3, 13), weights=_LENGTH_WEIGHTS)[0]
        surface = "".join(rng.choice(_LETTERS) for _ in range(length))
        left -= 1
        if left == 0:
            surface += "."
            left = rng.randint(8, 15)
            if pause_range is not None:
                pause_after[index] = rng.randint(*pause_range)
        surfaces.append(surface)
    return _spoken(surfaces, char_ms=char_ms, pause_after=pause_after)


def _normal_words() -> list[Word]:
    # 2,6 Wörter/s: mittlere Oberfläche 5,3 Zeichen plus Leerzeichen bei 61 ms
    # je Zeichen; Satzenden alle 8 bis 15 Wörter, Pausen 300 bis 1200 ms.
    return _speech(random.Random(_SEED), 400, 61, (300, 1200))  # noqa: S311 - test data, not a secret


def _fast_words() -> list[Word]:
    # 4,5 Wörter/s: 35 ms je Zeichen, keine Pausen.
    return _speech(random.Random(_SEED + 1), 400, 35, None)  # noqa: S311 - test data, not a secret


def _fuzz_surface(rng: random.Random) -> str:
    kind = rng.randrange(10)
    if kind <= 4:
        return "".join(rng.choice(_LETTERS) for _ in range(rng.randint(1, 12)))
    if kind == 5:
        return "".join(rng.choice(_LETTERS) for _ in range(rng.randint(1, 10))) + rng.choice(".?!,;:")
    if kind == 6:
        return rng.choice(["<", "&", "-->", "<i>kursiv</i>", "A&B", "a<b"])
    if kind == 7:
        return rng.choice(["zwei\nzeilig", "mit\ttab", "\n", " \t ", "wagen\rlauf", "nu\x00ll", "\x07ton"])
    if kind == 8:
        return rng.choice(_LETTERS) * rng.randint(43, 90)
    return rng.choice(["und", "oder", "aber", "dass", "and", "but", "or", "et", "ou", "mais", "que"])


def _fuzz_case(rng: random.Random) -> list[Word]:
    words: list[Word] = []
    cursor = 0
    for _ in range(rng.randint(0, 30)):
        start = cursor + rng.randint(-400, 1500)
        end = start if rng.randrange(5) == 0 else start + rng.randint(-300, 9000)
        words.append(_word(start, end, _fuzz_surface(rng)))
        cursor = max(cursor, start, end) + rng.randint(0, 400)
    return words


def _fuzz_cases() -> list[list[Word]]:
    rng = random.Random(_SEED)  # noqa: S311 - test data, not a secret
    fixed: list[list[Word]] = [
        [],
        [_word(0, 0, "gleich"), _word(0, 0, "auf"), _word(0, 0, "gleich")],
        [_word(900, 100, "ende"), _word(880, 100, "vor"), _word(860, 100, "anfang")],
        [_word(0, 500, " \n\t ")],
        [_word(0, 5000, "wort"), _word(100, 200, "mitten"), _word(150, 9000, "drin")],
    ]
    return fixed + [_fuzz_case(rng) for _ in range(len(fixed), 300)]


_FUZZ: Final = _fuzz_cases()


def _timestamp(ms: int) -> str:
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, milli = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milli:03d}"


def _as_srt(cues: Sequence[Cue]) -> str:
    """A minimal SRT serialization for the round trip; the real writer comes in plan 04-08."""
    blocks = [
        f"{number}\n{_timestamp(cue.start_ms)} --> {_timestamp(cue.end_ms)}\n" + "\n".join(cue.lines)
        for number, cue in enumerate(cues, start=1)
    ]
    return "\n\n".join(blocks) + "\n"


def test_constants_hold_the_agreed_limits() -> None:
    assert MAX_LINE == 42
    assert MAX_LINES == 2
    assert MIN_MS == 1000
    assert MAX_MS == 7000
    assert MAX_CPS == 20
    assert GAP_MS == 80
    assert PAUSE_CUT_MS == 700


def test_empty_input_yields_no_cue_and_no_overrun() -> None:
    assert build_cues([]) == []
    assert count_overruns([]) == Overruns(0, 0, 0, 0, 0)


def test_fuzz_text_stays_wordwise_identical() -> None:
    for words in _FUZZ:
        assert _cue_tokens(build_cues(words)) == _visible_tokens(words)


def test_fuzz_lines_hold_width_and_count() -> None:
    for words in _FUZZ:
        for cue in build_cues(words):
            assert 1 <= len(cue.lines) <= MAX_LINES
            for line in cue.lines:
                assert line
                assert line == line.strip()
                assert "  " not in line
                assert len(line) <= MAX_LINE or " " not in line


def test_fuzz_lines_carry_no_control_characters() -> None:
    for words in _FUZZ:
        for cue in build_cues(words):
            for line in cue.lines:
                for ch in line:
                    assert ch == " " or not ch.isspace()
                    assert unicodedata.category(ch) != "Cc"


def test_fuzz_times_are_monotone_and_bounded() -> None:
    for words in _FUZZ:
        cues = build_cues(words)
        for cue in cues:
            assert cue.start_ms >= 0, "SRT und VTT kennen keine negative Zeit (Fix 04-08)"
            assert cue.start_ms < cue.end_ms
            assert cue.end_ms - cue.start_ms <= MAX_MS
        for left, right in itertools.pairwise(cues):
            assert left.end_ms <= right.start_ms
            assert left.start_ms <= right.start_ms


def test_overruns_total_is_the_sum_of_the_counters() -> None:
    for words in _FUZZ:
        overruns = count_overruns(build_cues(words))
        assert overruns.total == overruns.cps + overruns.short + overruns.gap + overruns.long_word


def test_a_single_short_word_is_shown_at_least_the_minimum_time() -> None:
    assert build_cues([_word(0, 300, "Hallo.")]) == [Cue(0, 1000, ("Hallo.",))]


def test_extension_stops_a_gap_before_the_next_cue_and_the_rest_is_counted() -> None:
    cues = build_cues([_word(0, 200, "Kurz."), _word(950, 1500, "Weiter")])

    assert cues == [Cue(0, 870, ("Kurz.",)), Cue(950, 1950, ("Weiter",))]
    assert count_overruns(cues) == Overruns(0, 1, 0, 0, 1)


def test_a_pause_at_the_threshold_stays_in_one_cue() -> None:
    cues = build_cues([_word(0, 200, "Kurz."), _word(900, 1400, "gleich")])

    assert len(cues) == 1
    assert cues[0].lines == ("Kurz. gleich",)


def test_line_break_balances_both_lines_without_punctuation() -> None:
    words = _spoken(["Wir", "sehen", "uns", "morgen", "früh", "am", "alten", "Bahnhof", "wieder"])

    assert build_cues(words) == [Cue(0, 2989, ("Wir sehen uns morgen früh", "am alten Bahnhof wieder"))]


def test_line_break_prefers_the_punctuation_cut() -> None:
    words = _spoken(["Er", "kommt", "später,", "das", "weiß", "ich", "schon", "lange", "genau."])

    assert [cue.lines for cue in build_cues(words)] == [("Er kommt später,", "das weiß ich schon lange genau.")]


def test_cue_cut_prefers_the_comma_over_the_latest_word_boundary() -> None:
    surfaces = [
        *("Der", "Gemeinderat", "beschließt", "die", "neue", "Vorlage,"),
        *("danach", "folgen", "noch", "viele", "lange", "Wortmeldungen"),
    ]

    assert [cue.lines for cue in build_cues(_spoken(surfaces))] == [
        ("Der Gemeinderat beschließt", "die neue Vorlage,"),
        ("danach folgen noch viele", "lange Wortmeldungen"),
    ]


def test_a_sentence_end_closes_the_cue_once_it_is_half_full() -> None:
    surfaces = [
        *("Die", "Mitglieder", "stimmen", "dem", "Antrag", "heute", "zu."),
        *("Danach", "folgt", "die", "Aussprache"),
    ]

    assert [cue.lines for cue in build_cues(_spoken(surfaces))] == [
        ("Die Mitglieder stimmen", "dem Antrag heute zu."),
        ("Danach folgt die Aussprache",),
    ]


def test_a_word_over_the_line_limit_stands_alone_unbroken() -> None:
    long_word = "x" * 50
    cues = build_cues(_spoken(["Der", long_word, "Rest"]))

    assert [cue.lines for cue in cues] == [("Der", long_word), ("Rest",)]
    assert count_overruns(cues) == Overruns(0, 0, 0, 1, 1)

    alone = build_cues([_word(0, 300, "y" * 90)])
    assert alone == [Cue(0, 4500, ("y" * 90,))]
    assert count_overruns(alone).long_word == 1


def test_a_short_tail_cue_joins_the_previous_cue_when_the_limits_allow() -> None:
    surfaces = [
        *("Wir", "beginnen", "die", "Sitzung", "heute", "mit", "dem", "Protokoll."),
        "Gut.",
        *("Danach", "sprechen", "wir", "über", "den", "Haushalt."),
    ]
    words = _spoken(surfaces, pause_after={7: 100, 8: 750})

    cues = build_cues(words)

    assert cues[0] == Cue(0, 3394, ("Wir beginnen die Sitzung", "heute mit dem Protokoll. Gut."))
    assert len(cues) == 2
    assert cues[1].start_ms == 4205
    assert count_overruns(cues) == Overruns(0, 0, 0, 0, 0)


def test_control_characters_inside_a_surface_become_one_space() -> None:
    cues = build_cues(_spoken(["erste\nZeile", "zwei\tTabs", "-->", "<b>", "A&B"]))

    assert [cue.lines for cue in cues] == [("erste Zeile zwei Tabs --> <b> A&B",)]


def test_backwards_times_are_repaired_into_monotone_cues() -> None:
    words = [_word(5000, 4000, "eins"), _word(1000, 900, "zwei"), _word(1000, 1000, "drei")]

    assert build_cues(words) == [Cue(1000, 2000, ("zwei drei",)), Cue(5000, 6000, ("eins",))]


def test_normal_speech_keeps_every_limit() -> None:
    cues = build_cues(_normal_words())

    assert len(cues) >= 20, f"NORMAL-Cues: {len(cues)}"
    assert count_overruns(cues) == Overruns(0, 0, 0, 0, 0)


def test_fast_speech_cps_overruns_stay_under_the_measured_gate() -> None:
    cues = build_cues(_fast_words())
    overruns = count_overruns(cues)

    share = overruns.cps / len(cues)
    assert share <= FAST_SPEECH_MAX_OVER_CPS_SHARE, f"cps-Anteil gemessen: {share:.4f} bei {len(cues)} Cues"
    assert overruns.short == 0
    assert overruns.gap == 0
    assert overruns.long_word == 0


def test_cues_round_trip_through_the_independent_srt_parser() -> None:
    cues = build_cues(_normal_words())

    parsed = read_srt_subtitles(_as_srt(cues))

    assert len(parsed) == len(cues)
    for ours, theirs in zip(cues, parsed, strict=True):
        assert theirs.start_ms == ours.start_ms
        assert theirs.end_ms == ours.end_ms
        assert theirs.text == "\n".join(ours.lines)
