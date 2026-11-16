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
    # Round hundreds (plan 04-06, D-04-11)
    (["zweihundert"], 200, False),
    (["two", "hundred"], 200, False),
    (["deux", "cents"], 200, False),
    (["deux", "cent"], 200, False),
    (["neunhundert"], 900, False),
    # Thousands and grouped ten thousands
    (["tausend"], 1000, False),
    (["eintausend"], 1000, False),
    (["one", "thousand"], 1000, False),
    (["mille"], 1000, False),
    (["dreitausend"], 3000, False),
    (["three", "thousand"], 3000, False),
    (["trois", "mille"], 3000, False),
    (["zehntausend"], 10000, False),
    (["dreißigtausend"], 30000, False),
    (["thirty", "thousand"], 30000, False),
    (["trente", "mille"], 30000, False),
    (["hunderttausend"], 100000, False),
    (["cent", "mille"], 100000, False),
    # Years 1100 to 2099
    (["neunzehnhundertneunzig"], 1990, False),
    (["neunzehnhundert"], 1900, False),
    (["nineteen", "ninety"], 1990, False),
    (["nineteen", "oh", "five"], 1905, False),
    (["mille", "neuf", "cent", "quatre-vingt-dix"], 1990, False),
    (["dix-neuf", "cent", "quatre-vingt-dix"], 1990, False),
    (["zweitausendvierundzwanzig"], 2024, False),
    (["zwanzigvierundzwanzig"], 2024, False),
    (["twenty", "twenty", "four"], 2024, False),
    (["two", "thousand", "twenty", "four"], 2024, False),
    (["deux", "mille", "vingt-quatre"], 2024, False),
    # Digits of the new range, with and without thousands grouping
    (["200"], 200, False),
    (["3000"], 3000, False),
    (["30000"], 30000, False),
    (["30", "000"], 30000, False),
    (["1", "000"], 1000, False),
    (["100", "000"], 100000, False),
    (["1990"], 1990, False),
    (["2024"], 2024, False),
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
    # Plan 04-06 (D-04-11): round hundreds, thousands, grouping, years.
    (200, False, {"200", "zweihundert", '"two hundred"', '"deux cents"'}),
    (3000, False, {"3000", '"3 000"', "dreitausend", '"three thousand"', '"trois mille"'}),
    (30000, False, {"30000", '"30 000"', "dreißigtausend", '"thirty thousand"', '"trente mille"'}),
    (100000, False, {"100000", '"100 000"', "hunderttausend", '"one hundred thousand"', '"cent mille"'}),
    (1990, False, {"1990", "neunzehnhundertneunzig", '"nineteen ninety"', '"mille neuf cent quatre vingt dix"'}),
    (1990, False, {'"dix neuf cent quatre vingt dix"'}),
    (1905, False, {"1905", "neunzehnhundertfünf", '"nineteen oh five"'}),
    (2024, False, {"2024", "zweitausendvierundzwanzig", "zwanzigvierundzwanzig", '"twenty twenty four"'}),
    (2024, False, {'"two thousand twenty four"', '"deux mille vingt quatre"'}),
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
    # T-04-01: the variant count per number is fixed by the tables; since plan
    # 04-06 the bound also holds for hundreds, thousands and every year.
    values = [
        *range(101),
        *range(200, 1000, 100),
        *range(1000, 10000, 1000),
        *range(10000, 100001, 10000),
        *range(1100, 2100),
    ]
    for value in values:
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


@pytest.mark.parametrize(
    "words",
    [["234"], ["2345"], ["150"], ["12500"], ["123456"], ["neunhundertneunzig"], ["zwölftausend"]],
    ids=["234", "2345", "150", "12500", "123456", "neunhundertneunzig", "zwölftausend"],
)
def test_no_full_parser_numbers_outside_the_patterns_stay_digits_only(words: list[str]) -> None:
    # D-04-11: no full number parser. A digit outside the round values and the
    # year window, and a number word outside the tables, is no number span; the
    # search keeps it as a plain word.
    assert numbers.recognize(words) == []


def test_the_year_window_is_a_named_constant() -> None:
    assert numbers.YEAR_RANGE == (1100, 2099)


def test_1234_lies_inside_the_year_window_and_is_equated() -> None:
    # The plan names 1234 as digits-only, but 1234 lies inside YEAR_RANGE and
    # the must-have equates every year from 1100 to 2099 (D-04-11); the
    # digits-only rule holds outside the window (test above, 2345).
    assert numbers.recognize(["1234"]) == [numbers.NumberSpan(start=0, stop=1, value=1234, ordinal=False)]
    assert "zwölfhundertvierunddreißig" in numbers.variants(1234, ordinal=False)


def test_spans_inside_a_longer_query_are_greedy_and_positioned() -> None:
    words = ["am", "zwölften", "März", "um", "vingt", "et", "un", "Uhr", "12"]

    assert numbers.recognize(words) == [
        numbers.NumberSpan(start=1, stop=2, value=12, ordinal=True),
        numbers.NumberSpan(start=4, stop=7, value=21, ordinal=False),
        numbers.NumberSpan(start=8, stop=9, value=12, ordinal=False),
    ]


def test_a_span_never_reaches_beyond_seven_words() -> None:
    # Plan 04-01 needed five ("soixante et onze"); the years of plan 04-06 need
    # seven ("mille neuf cent quatre-vingt-dix-neuf" folds to seven words).
    assert numbers.MAX_SPAN_WORDS == 7
    assert numbers.recognize(["quatre", "vingt", "dix", "neuf", "chaises"]) == [
        numbers.NumberSpan(start=0, stop=4, value=99, ordinal=False)
    ]
    assert numbers.recognize(["mille", "neuf", "cent", "quatre", "vingt", "dix", "neuf", "chaises"]) == [
        numbers.NumberSpan(start=0, stop=7, value=1999, ordinal=False)
    ]
