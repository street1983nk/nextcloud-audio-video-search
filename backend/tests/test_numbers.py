"""Numbers as digit and word in German, English and French (plan 04-01, D-04-11, D-04-12).

Both tables below are written by hand from the spelling rules of the three
languages, never generated with ``index/numbers.py``: a table computed by the
code under test would only repeat its mistakes (owner rule: the cross check
never uses the pattern of the implementation).
"""

import pytest

from audio_video_search_backend.index import numbers

# (words of the query, expected value, ordinal)
RECOGNIZED = [
    # German cardinals
    (["null"], 0, False),
    (["eins"], 1, False),
    (["sieben"], 7, False),
    (["zwölf"], 12, False),
    (["Zwölf"], 12, False),
    (["sechzehn"], 16, False),
    (["siebzehn"], 17, False),
    (["einundzwanzig"], 21, False),
    (["dreißig"], 30, False),
    (["siebzig"], 70, False),
    (["einundsiebzig"], 71, False),
    (["achtzig"], 80, False),
    (["neunzig"], 90, False),
    (["neunundneunzig"], 99, False),
    (["hundert"], 100, False),
    # German ordinals
    (["erste"], 1, True),
    (["ersten"], 1, True),
    (["zweiten"], 2, True),
    (["dritte"], 3, True),
    (["siebte"], 7, True),
    (["achten"], 8, True),
    (["zwölfter"], 12, True),
    (["zwölften"], 12, True),
    (["einundzwanzigsten"], 21, True),
    # English cardinals
    (["zero"], 0, False),
    (["one"], 1, False),
    (["seven"], 7, False),
    (["twelve"], 12, False),
    (["sixteen"], 16, False),
    (["seventeen"], 17, False),
    (["twenty", "one"], 21, False),
    (["twenty-one"], 21, False),
    (["thirty"], 30, False),
    (["seventy"], 70, False),
    (["seventy-one"], 71, False),
    (["eighty"], 80, False),
    (["ninety"], 90, False),
    (["ninety", "nine"], 99, False),
    (["one", "hundred"], 100, False),
    # English ordinals
    (["first"], 1, True),
    (["second"], 2, True),
    (["third"], 3, True),
    (["twelfth"], 12, True),
    (["twenty-first"], 21, True),
    (["twenty", "first"], 21, True),
    # French cardinals
    (["zéro"], 0, False),
    (["sept"], 7, False),
    (["douze"], 12, False),
    (["seize"], 16, False),
    (["dix-sept"], 17, False),
    (["dix", "sept"], 17, False),
    (["vingt", "et", "un"], 21, False),
    (["vingt-et-un"], 21, False),
    (["trente"], 30, False),
    (["soixante", "dix"], 70, False),
    (["soixante-dix"], 70, False),
    (["soixante", "et", "onze"], 71, False),
    (["quatre-vingts"], 80, False),
    (["quatre-vingt-dix"], 90, False),
    (["quatre", "vingt", "dix", "neuf"], 99, False),
    (["cent"], 100, False),
    # French ordinals
    (["premier"], 1, True),
    (["première"], 1, True),
    (["deuxième"], 2, True),
    (["troisième"], 3, True),
    (["douzième"], 12, True),
    (["vingt", "et", "unième"], 21, True),
    # Digits and digit ordinals
    (["0"], 0, False),
    (["12"], 12, False),
    (["100"], 100, False),
    (["12."], 12, True),
    (["1st"], 1, True),
    (["2nd"], 2, True),
    (["3rd"], 3, True),
    (["12th"], 12, True),
    (["21st"], 21, True),
    (["12e"], 12, True),
    (["12ème"], 12, True),
    (["1er"], 1, True),
    (["1re"], 1, True),
]


@pytest.mark.parametrize(
    ("words", "value", "ordinal"),
    RECOGNIZED,
    ids=[" ".join(words) for words, _, _ in RECOGNIZED],
)
def test_a_number_is_recognized_with_value_and_kind(words: list[str], value: int, ordinal: bool) -> None:
    spans = numbers.recognize(words)

    assert spans == [numbers.NumberSpan(start=0, stop=len(words), value=value, ordinal=ordinal)]


# (value, ordinal, spellings that must be among the variants)
REQUIRED_VARIANTS = [
    (0, False, {"0", "null", "zero", "zéro"}),
    (1, False, {"1", "eins", "one", "erste", "first", "premier", "première", "1st", "1er"}),
    (7, False, {"7", "sieben", "seven", "sept", "siebte", "seventh", "septième"}),
    (12, False, {"12", "zwölf", "twelve", "douze", "zwölften", "twelfth", "douzième", "12th", "12e"}),
    (12, True, {"12", "zwölf", "twelve", "douze", "zwölften", "twelfth", "douzième", "12th", "12e"}),
    (16, False, {"16", "sechzehn", "sixteen", "seize"}),
    (17, False, {"17", "siebzehn", "seventeen", '"dix sept"'}),
    (21, False, {"21", "einundzwanzig", '"twenty one"', '"vingt et un"', "21st"}),
    (21, True, {"21", "einundzwanzigsten", '"twenty first"', '"vingt et unième"'}),
    (30, False, {"30", "dreißig", "thirty", "trente"}),
    (70, False, {"70", "siebzig", "seventy", '"soixante dix"'}),
    (71, False, {"71", "einundsiebzig", '"seventy one"', '"soixante et onze"'}),
    (80, False, {"80", "achtzig", "eighty", '"quatre vingts"'}),
    (90, False, {"90", "neunzig", "ninety", '"quatre vingt dix"'}),
    (99, False, {"99", "neunundneunzig", '"ninety nine"', '"quatre vingt dix neuf"'}),
    (100, False, {"100", "hundert", "cent"}),
    (2, True, {"2", "zwei", "two", "deux", "zweiten", "second", "deuxième", "2nd"}),
    (3, True, {"3", "drei", "three", "trois", "dritten", "third", "troisième", "3rd"}),
]


@pytest.mark.parametrize(
    ("value", "ordinal", "required"),
    REQUIRED_VARIANTS,
    ids=[f"{value}-{'ord' if ordinal else 'card'}" for value, ordinal, _ in REQUIRED_VARIANTS],
)
def test_the_variants_carry_every_required_spelling(value: int, ordinal: bool, required: set[str]) -> None:
    assert required <= set(numbers.variants(value, ordinal))


@pytest.mark.parametrize("ordinal", [False, True])
def test_one_never_widens_to_an_article(ordinal: bool) -> None:
    # ein, eine, un, une are stop words and articles (04-RESEARCH, limit 1).
    forms = set(numbers.variants(1, ordinal))

    assert not forms & {"ein", "eine", "un", "une"}


def test_the_variants_stay_bounded_for_every_value() -> None:
    # T-04-01: the variant count per number is fixed by the tables.
    for value in range(101):
        for ordinal in (False, True):
            forms = numbers.variants(value, ordinal)
            assert 0 < len(forms) <= 24
            assert len(set(forms)) == len(forms)


@pytest.mark.parametrize(
    "words",
    [[], ["Haus"], ["einig"], ["neunmal"], ["zwölfjährig"], ["ein"], ["eine"], ["un"], ["une"], ["101"], ["012"]],
    ids=["empty", "Haus", "einig", "neunmal", "zwölfjährig", "ein", "eine", "un", "une", "101", "012"],
)
def test_words_that_are_no_number_stay_unrecognized(words: list[str]) -> None:
    assert numbers.recognize(words) == []


def test_spans_inside_a_longer_query_are_greedy_and_positioned() -> None:
    words = ["am", "zwölften", "März", "um", "vingt", "et", "un", "Uhr", "12"]

    assert numbers.recognize(words) == [
        numbers.NumberSpan(start=1, stop=2, value=12, ordinal=True),
        numbers.NumberSpan(start=4, stop=7, value=21, ordinal=False),
        numbers.NumberSpan(start=8, stop=9, value=12, ordinal=False),
    ]


def test_a_span_never_reaches_beyond_five_words() -> None:
    assert numbers.MAX_SPAN_WORDS == 5
    # "quatre vingt dix neuf" is four words and still one number.
    assert numbers.recognize(["quatre", "vingt", "dix", "neuf", "chaises"]) == [
        numbers.NumberSpan(start=0, stop=4, value=99, ordinal=False)
    ]
