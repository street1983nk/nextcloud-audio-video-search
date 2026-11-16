"""Numbers as digit and as word in German, English and French, on the query side only.

A transcript writes "12" in one place and "zwölf" in another; Parakeet and
Whisper both do it within one file. The index keeps what was said, and this
module widens a number in the query to every spelling of it (plan 04-01,
D-04-11, D-04-12, 04-RESEARCH Pattern 1). Nothing changes in the index, so
ANALYZER_VERSION stays and no rebuild runs: every spelling goes through the
same chains as before, through ``Index.parse_query``.

The range of this plan is 0 to 100 with the ordinals; hundreds, thousands and
years follow in plan 04-06.

Two limits, measured in 04-RESEARCH:

1. ``ein``, ``eine``, ``un`` and ``une`` are articles and stop words. A lone one
   is never taken for 1, and 1 never widens to them; ``eins``, ``one``,
   ``premier``, ``première`` and ``erste`` do.
2. French ``vingt et un`` leaves only ``vingt`` after the stop words, so the
   phrase also meets every other ``vingt``. That catch is accepted.

The tables are written once and turned into a reverse lookup at import. Keys are
folded: lower case, accents and umlauts flattened, sharp s as ss, a hyphen as a
space. Multi word spellings come back as a phrase in double quotes.

Nothing here logs a token or a word: this path sees user content.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

MAX_VALUE: Final = 100
# A number spells with at most five words ("soixante et onze", "quatre vingt dix neuf").
MAX_SPAN_WORDS: Final = 5

# German: 0 to 19, the tens, the unit prefixes of the compounds (einundzwanzig).
_DE_UNITS: Final = (
    "null",
    "eins",
    "zwei",
    "drei",
    "vier",
    "fünf",
    "sechs",
    "sieben",
    "acht",
    "neun",
    "zehn",
    "elf",
    "zwölf",
    "dreizehn",
    "vierzehn",
    "fünfzehn",
    "sechzehn",
    "siebzehn",
    "achtzehn",
    "neunzehn",
)
_DE_TENS: Final = ("", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig", "neunzig")
_DE_COMPOUND_UNITS: Final = ("", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun")
_DE_HUNDRED: Final = ("hundert", "einhundert")
# Ordinal stems that do not follow "cardinal + t" (below 20) or "cardinal + st".
_DE_ORDINAL_STEMS: Final = {1: "erst", 3: "dritt", 7: "siebt", 8: "acht"}
# All endings are recognized; the variants carry three, the German stemmer
# strips the rest to the same stem.
_DE_ORDINAL_ENDINGS: Final = ("e", "en", "er", "es", "em")
_DE_VARIANT_ENDINGS: Final = ("e", "en", "er")

# English.
_EN_UNITS: Final = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_EN_TENS: Final = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_EN_HUNDRED: Final = ("hundred", "one hundred")
_EN_ORDINAL_WORDS: Final = {
    1: "first",
    2: "second",
    3: "third",
    5: "fifth",
    8: "eighth",
    9: "ninth",
    12: "twelfth",
}

# French: 0 to 16 as one word, the tens up to 60; 70 to 99 are built.
_FR_UNITS: Final = (
    "zéro",
    "un",
    "deux",
    "trois",
    "quatre",
    "cinq",
    "six",
    "sept",
    "huit",
    "neuf",
    "dix",
    "onze",
    "douze",
    "treize",
    "quatorze",
    "quinze",
    "seize",
)
_FR_TENS: Final = ("", "", "vingt", "trente", "quarante", "cinquante", "soixante")
_FR_HUNDRED: Final = "cent"
# The last word of a cardinal that changes before "-ième".
_FR_ORDINAL_LAST: Final = {"un": "unième", "cinq": "cinquième", "neuf": "neuvième", "vingts": "vingtième"}
_FR_FIRST: Final = ("premier", "première")
_FR_SECOND: Final = ("second", "seconde")

# Articles: never a number on their own (limit 1).
_ARTICLES: Final = frozenset({"ein", "eine", "un", "une"})

# A digit, optionally with an ordinal mark: "12." (German), 1st/2nd/3rd/12th,
# 12e/12ème/1er/1re/1ère (French). Matched against the folded word.
_DIGITS: Final = re.compile(r"(\d{1,3})(\.|st|nd|rd|th|e|eme|er|re|ere)?")


@dataclass(frozen=True, slots=True)
class NumberSpan:
    """A number found in a word sequence; ``start`` and ``stop`` are word indices."""

    start: int
    stop: int
    value: int
    ordinal: bool


def _fold(text: str) -> str:
    """The lookup key of a spelling: lower case, flat letters, hyphen as space."""
    lowered = unicodedata.normalize("NFC", text).lower().replace("ß", "ss").replace("-", " ")
    flat = "".join(c for c in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(c))
    return " ".join(flat.split())


def _de_cardinals(value: int) -> tuple[str, ...]:
    if value < 20:
        return (_DE_UNITS[value],)
    if value == MAX_VALUE:
        return _DE_HUNDRED
    tens, unit = divmod(value, 10)
    if unit == 0:
        return (_DE_TENS[tens],)
    return (f"{_DE_COMPOUND_UNITS[unit]}und{_DE_TENS[tens]}",)


def _de_ordinal_stem(value: int) -> str:
    if value in _DE_ORDINAL_STEMS:
        return _DE_ORDINAL_STEMS[value]
    if value < 20:
        return _DE_UNITS[value] + "t"
    return _de_cardinals(value)[0] + "st"


def _en_cardinals(value: int) -> tuple[str, ...]:
    if value < 20:
        return (_EN_UNITS[value],)
    if value == MAX_VALUE:
        return _EN_HUNDRED
    tens, unit = divmod(value, 10)
    if unit == 0:
        return (_EN_TENS[tens],)
    return (f"{_EN_TENS[tens]} {_EN_UNITS[unit]}",)


def _en_ordinal_word(value: int) -> str:
    if value in _EN_ORDINAL_WORDS:
        return _EN_ORDINAL_WORDS[value]
    if value < 20:
        return _EN_UNITS[value] + "th"
    tens, unit = divmod(value, 10)
    if unit == 0:
        return _EN_TENS[tens][:-1] + "ieth"
    return f"{_EN_TENS[tens]} {_en_ordinal_word(unit)}"


def _en_ordinals(value: int) -> tuple[str, ...]:
    if value == MAX_VALUE:
        return ("hundredth", "one hundredth")
    return (_en_ordinal_word(value),)


def _fr_cardinal(value: int) -> str:
    if value <= 16:
        return _FR_UNITS[value]
    if value < 20:
        return f"dix {_FR_UNITS[value - 10]}"
    if value < 70:
        tens, unit = divmod(value, 10)
        if unit == 0:
            return _FR_TENS[tens]
        if unit == 1:
            return f"{_FR_TENS[tens]} et un"
        return f"{_FR_TENS[tens]} {_FR_UNITS[unit]}"
    if value < 80:
        return "soixante et onze" if value == 71 else f"soixante {_fr_cardinal(value - 60)}"
    if value == 80:
        return "quatre vingts"
    if value < MAX_VALUE:
        return f"quatre vingt {_fr_cardinal(value - 80)}"
    return _FR_HUNDRED


def _fr_ordinals(value: int) -> tuple[str, ...]:
    if value == 0:
        return ()
    if value == 1:
        return _FR_FIRST
    *head, last = _fr_cardinal(value).split(" ")
    if last in _FR_ORDINAL_LAST:
        tail = _FR_ORDINAL_LAST[last]
    elif last.endswith("e"):
        tail = last[:-1] + "ième"
    else:
        tail = last + "ième"
    word = " ".join([*head, tail])
    return ("deuxième", *_FR_SECOND) if value == 2 else (word,)


def _digit_ordinals(value: int) -> tuple[str, ...]:
    english = "th" if value % 100 in (11, 12, 13) else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    french = (f"{value}er", f"{value}re") if value == 1 else (f"{value}e", f"{value}ème")
    return (f"{value}{english}", *french)


def _cardinal_words(value: int) -> tuple[str, ...]:
    french = () if value == 1 else (_fr_cardinal(value),)
    return (*_de_cardinals(value), *_en_cardinals(value), *french)


def _ordinal_words(value: int) -> tuple[str, ...]:
    stem = _de_ordinal_stem(value)
    german = tuple(stem + ending for ending in _DE_VARIANT_ENDINGS)
    return (*german, *_en_ordinals(value), *_fr_ordinals(value))


def _build_surface() -> dict[str, tuple[int, bool]]:
    surface: dict[str, tuple[int, bool]] = {}

    def put(spelling: str, value: int, ordinal: bool) -> None:
        key = _fold(spelling)
        if key in _ARTICLES:
            return
        known = surface.setdefault(key, (value, ordinal))
        if known != (value, ordinal):
            raise RuntimeError(f"number spelling {key!r} is ambiguous")

    for value in range(MAX_VALUE + 1):
        for word in _cardinal_words(value):
            put(word, value, False)
        stem = _de_ordinal_stem(value)
        for ending in _DE_ORDINAL_ENDINGS:
            put(stem + ending, value, True)
        for word in (*_en_ordinals(value), *_fr_ordinals(value)):
            put(word, value, True)
    # Spellings that only the lookup needs: French feminine and singular forms.
    for tens in range(2, 7):
        put(f"{_FR_TENS[tens]} et une", tens * 10 + 1, False)
    put("quatre vingt", 80, False)
    return surface


_SURFACE: Final[dict[str, tuple[int, bool]]] = _build_surface()


def _digit_value(word: str) -> tuple[int, bool] | None:
    match = _DIGITS.fullmatch(word)
    if match is None:
        return None
    digits = match.group(1)
    if len(digits) > 1 and digits.startswith("0"):
        return None
    value = int(digits)
    if value > MAX_VALUE:
        return None
    return value, match.group(2) is not None


def _lookup(words: Sequence[str]) -> tuple[int, bool] | None:
    keys = [_fold(word) for word in words]
    if any(not key for key in keys):
        return None
    if len(keys) == 1:
        digit = _digit_value(keys[0])
        if digit is not None:
            return digit
    return _SURFACE.get(" ".join(keys))


def recognize(words: Sequence[str]) -> list[NumberSpan]:
    """Every number in the words, left to right, the longest spelling first."""
    spans: list[NumberSpan] = []
    start = 0
    while start < len(words):
        for length in range(min(MAX_SPAN_WORDS, len(words) - start), 0, -1):
            found = _lookup(words[start : start + length])
            if found is not None:
                spans.append(NumberSpan(start=start, stop=start + length, value=found[0], ordinal=found[1]))
                start += length
                break
        else:
            start += 1
    return spans


def _quoted(spelling: str) -> str:
    return f'"{spelling}"' if " " in spelling else spelling


def variants(value: int, ordinal: bool) -> tuple[str, ...]:
    """Every spelling of a number as input for ``parse_query``, without duplicates.

    A cardinal widens to the ordinals too and an ordinal to the cardinals: a
    date said as "am zwölften März" must meet "am 12. März" (D-04-12). The
    ordinal flag only decides which come first.
    """
    if not 0 <= value <= MAX_VALUE:
        return (str(value),)
    cardinal = _cardinal_words(value)
    ordinal_forms = (*_ordinal_words(value), *_digit_ordinals(value))
    ordered = (str(value), *ordinal_forms, *cardinal) if ordinal else (str(value), *cardinal, *ordinal_forms)
    return tuple(dict.fromkeys(_quoted(spelling) for spelling in ordered))
