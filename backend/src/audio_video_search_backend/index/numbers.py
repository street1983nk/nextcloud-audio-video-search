"""Numbers as digit and as word in German, English and French, on the query side only.

A transcript writes "12" in one place and "zwölf" in another; Parakeet and
Whisper both do it within one file. The index keeps what was said, and this
module widens a number in the query to every spelling of it (plan 04-01,
D-04-11, D-04-12, 04-RESEARCH Pattern 1). Nothing changes in the index, so
ANALYZER_VERSION stays and no rebuild runs: every spelling goes through the
same chains as before, through ``Index.parse_query``.

The range is 0 to 100 with the ordinals (plan 04-01), plus the round hundreds
(200 to 900), the round thousands up to 100000 with their digit grouping
(30000, "30.000", "30,000" and "30 000" are one number) and the years 1100 to
2099 as spoken in the three languages (plan 04-06, D-04-11). There is no full
number parser: a digit outside these values and a number word outside the
tables stay plain words.

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
# A number spells with at most seven words: plan 04-01 needed five ("soixante
# et onze"), the years of plan 04-06 need seven ("mille neuf cent
# quatre-vingt-dix-neuf" folds to seven words).
MAX_SPAN_WORDS: Final = 7
# The year window of D-04-11: the century part 11 to 20, the rest 0 to 99.
YEAR_RANGE: Final = (1100, 2099)
# Grouped thousands reach to here; beyond is no number of this module.
MAX_GROUPED: Final = 100_000

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
# Round hundreds 200 to 900 as one German word; the index is the hundreds digit.
_DE_HUNDREDS: Final = (
    "",
    "",
    "zweihundert",
    "dreihundert",
    "vierhundert",
    "fünfhundert",
    "sechshundert",
    "siebenhundert",
    "achthundert",
    "neunhundert",
)
# The scale words of English and French; German compounds its own forms.
_EN_SCALE: Final = ("hundred", "thousand")
_FR_SCALE: Final = ("cent", "cents", "mille")
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
# 12e/12ème/1er/1re/1ère (French). Matched against the folded word. Six digits
# reach the top of the grouped thousands (100000, plan 04-06).
_DIGITS: Final = re.compile(r"(\d{1,6})(\.|st|nd|rd|th|e|eme|er|re|ere)?")


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


def _hundreds_words(value: int) -> tuple[str, ...]:
    """The spellings of a round hundred from 200 to 900 (D-04-11)."""
    unit = value // 100
    return (
        _DE_HUNDREDS[unit],
        f"{_EN_UNITS[unit]} {_EN_SCALE[0]}",
        f"{_FR_UNITS[unit]} {_FR_SCALE[1]}",
        f"{_FR_UNITS[unit]} {_FR_SCALE[0]}",
    )


def _thousands_words(value: int) -> tuple[str, ...]:
    """The spellings of a round thousand: 1000 to 9000, the ten thousands, 100000."""
    count = value // 1000
    if count == 1:
        return ("tausend", "eintausend", f"one {_EN_SCALE[1]}", _FR_SCALE[2])
    de_counts = (_DE_COMPOUND_UNITS[count],) if count < 10 else _de_cardinals(count)
    german = tuple(f"{word}tausend" for word in de_counts)
    english = tuple(f"{word} {_EN_SCALE[1]}" for word in _en_cardinals(count))
    return (*german, *english, f"{_fr_cardinal(count)} {_FR_SCALE[2]}")


def _year_words(year: int) -> tuple[str, ...]:
    """The spoken forms of a year from 1100 to 2099 in the three languages.

    German builds century times hundred plus rest (neunzehnhundertneunzig),
    for 2000 to 2099 the thousand form (zweitausendvierundzwanzig) and the two
    part form (zwanzigvierundzwanzig). English pairs the century with the rest
    (nineteen ninety, nineteen oh five, twenty twenty four) and spells 20xx as
    two thousand (and) rest. French says mille neuf cent ... and dix-neuf cent
    ..., for 20xx deux mille ... (D-04-11).
    """
    century, rest = divmod(year, 100)
    rest_de = "" if rest == 0 else _de_cardinals(rest)[0]
    rest_en = "" if rest == 0 else _en_cardinals(rest)[0]
    if century == 20:
        forms = [f"zweitausend{rest_de}", f"deux {_FR_SCALE[2]}"]
        if rest == 0:
            forms += [f"two {_EN_SCALE[1]}"]
        else:
            forms += [f"two {_EN_SCALE[1]} {rest_en}", f"two {_EN_SCALE[1]} and {rest_en}"]
            forms[1] = f"deux {_FR_SCALE[2]} {_fr_cardinal(rest)}"
            if rest >= 10:
                forms += [f"zwanzig{rest_de}", f"twenty {rest_en}"]
            else:
                forms += [f"twenty oh {_EN_UNITS[rest]}"]
        return tuple(forms)
    century_de = _DE_UNITS[century]
    century_en = _EN_UNITS[century]
    hundreds_digit = century - 10
    mille_mid = "" if hundreds_digit == 1 else f" {_FR_UNITS[hundreds_digit]}"
    tail_fr = "" if rest == 0 else f" {_fr_cardinal(rest)}"
    forms = [
        f"{century_de}hundert{rest_de}",
        f"mille{mille_mid} {_FR_SCALE[0]}{tail_fr}",
        f"{_fr_cardinal(century)} {_FR_SCALE[0]}{tail_fr}",
    ]
    if rest == 0:
        forms += [f"{century_en} {_EN_SCALE[0]}"]
    elif rest < 10:
        forms += [f"{century_en} oh {_EN_UNITS[rest]}"]
    else:
        forms += [f"{century_en} {rest_en}"]
    return tuple(forms)


def _digit_equated(value: int) -> bool:
    """Equated beyond 0 to 100: round hundreds, round thousands, the year window."""
    if YEAR_RANGE[0] <= value <= YEAR_RANGE[1]:
        return True
    if value % 100 == 0 and 200 <= value <= 900:
        return True
    return value % 1000 == 0 and 1000 <= value <= MAX_GROUPED


def _large_words(value: int) -> tuple[str, ...]:
    words: tuple[str, ...] = ()
    if value % 100 == 0 and 200 <= value <= 900:
        words += _hundreds_words(value)
    if value % 1000 == 0 and 1000 <= value <= MAX_GROUPED and (value < 10_000 or value % 10_000 == 0):
        words += _thousands_words(value)
    if YEAR_RANGE[0] <= value <= YEAR_RANGE[1]:
        words += _year_words(value)
    return words


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
    # Plan 04-06 (D-04-11): round hundreds and thousands, the year window.
    for value in range(200, 1000, 100):
        for word in _hundreds_words(value):
            put(word, value, False)
    for value in (*range(1000, 10_000, 1000), *range(10_000, MAX_GROUPED + 1, 10_000)):
        for word in _thousands_words(value):
            put(word, value, False)
    for year in range(YEAR_RANGE[0], YEAR_RANGE[1] + 1):
        for word in _year_words(year):
            put(word, year, False)
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
    if value > MAX_VALUE and not _digit_equated(value):
        return None
    return value, match.group(2) is not None


def _grouped_value(keys: Sequence[str]) -> tuple[int, bool] | None:
    """Two words "d" and "000" are one grouped thousand: 30.000, 30,000, 30 000.

    The tokenizer of the query splits at the point, the comma and the space, so
    every written grouping arrives as this word pair (04-RESEARCH Pattern 1).
    """
    head, tail = keys
    if tail != "000" or not head.isdigit() or head.startswith("0") or len(head) > 3:
        return None
    value = int(head) * 1000
    if value > MAX_GROUPED:
        return None
    return value, False


def _lookup(words: Sequence[str]) -> tuple[int, bool] | None:
    keys = [_fold(word) for word in words]
    if any(not key for key in keys):
        return None
    if len(keys) == 1:
        digit = _digit_value(keys[0])
        if digit is not None:
            return digit
    if len(keys) == 2:
        grouped = _grouped_value(keys)
        if grouped is not None:
            return grouped
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


def _large_variants(value: int) -> tuple[str, ...]:
    """The spellings above 100: digits, the grouped phrase, the word tables.

    The grouped phrase ``"30 000"`` covers 30.000, 30,000 and 30 000 in the
    index, because the tokenizer splits at the point, the comma and the space.
    Above 100 there are no ordinal forms (D-04-12 covers 0 to 100).
    """
    if not _digit_equated(value):
        return (str(value),)
    grouped = (f"{value // 1000} {value % 1000:03d}",) if value % 1000 == 0 and value >= 1000 else ()
    ordered = (str(value), *grouped, *_large_words(value))
    return tuple(dict.fromkeys(_quoted(spelling) for spelling in ordered))


def variants(value: int, ordinal: bool) -> tuple[str, ...]:
    """Every spelling of a number as input for ``parse_query``, without duplicates.

    A cardinal widens to the ordinals too and an ordinal to the cardinals: a
    date said as "am zwölften März" must meet "am 12. März" (D-04-12). The
    ordinal flag only decides which come first.
    """
    if not 0 <= value <= MAX_VALUE:
        return _large_variants(value)
    cardinal = _cardinal_words(value)
    ordinal_forms = (*_ordinal_words(value), *_digit_ordinals(value))
    ordered = (str(value), *ordinal_forms, *cardinal) if ordinal else (str(value), *cardinal, *ordinal_forms)
    return tuple(dict.fromkeys(_quoted(spelling) for spelling in ordered))
