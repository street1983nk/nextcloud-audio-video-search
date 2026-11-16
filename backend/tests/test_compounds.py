"""Compound heads in the search: "Haushalt" finds "Haushaltsplanberatung" (plan 04-06, D-04-14).

The constituent list of this module re-enacts ngerman: compounds that stand in
the Debian list themselves (haushaltsplan, bebauungsplan) are entries here too,
because the splitter matches leftmost-longest and an entry is never split
(04-RESEARCH, measured). The widening comes from a prefix clause on body_de at
query time; the analyzer chain, the word list recipe and the index are the ones
of phase 1 (D-04-13, no rebuild).

Known limits are named tests: the prefix helps only for the head of a compound
("Plan" does not find "Bebauungsplan"), and it brings catch ("Haushalt" also
meets "Haushälterin").
"""

from collections.abc import Iterator

import pytest

from audio_video_search_backend.index import wordlist
from audio_video_search_backend.index.analyzer import MAX_TOKEN_CHARS
from audio_video_search_backend.index.publish import PREFIX_MIN_CHARS, SearchIndex, Segment, _prefix_pattern
from audio_video_search_backend.index.schema import BODY_FIELDS
from audio_video_search_backend.model.overlay import Word

# Re-enacting ngerman: "haushaltsplan" and "bebauungsplan" are entries of the
# Debian list themselves (4 to 14 letters), so "Haushaltsplanberatung" splits
# into haushaltsplan|beratung and "Bebauungsplan" stays one term.
CONSTITUENTS = sorted(
    {
        "haushalt",
        "haushaltsplan",
        "plan",
        "beratung",
        "miete",
        "vertrag",
        "haus",
        "bebauung",
        "bebauungsplan",
        *wordlist.FUGEN,
    }
)

SEGMENTS = {
    1: "Die Haushaltsplanberatung beginnt",
    2: "Die Haushaltssatzung gilt weiter",
    3: "Die Haushälterin kommt morgen",
    4: "Das Haus steht offen",
    5: "Der Mietvertrag endet im Mai",
    6: "Der Bebauungsplan liegt aus",
    7: "Die Hausaufgabe ist fertig",
    8: "Projekt42 startet bald",
}


@pytest.fixture(scope="module")
def search_index(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SearchIndex]:
    # One index for the module: the tests only read (same reason as in
    # tests/test_search_numbers.py, tantivy renames fail now and then on
    # Windows when every test commits).
    opened = SearchIndex.open(tmp_path_factory.mktemp("compounds") / "idx", constituents=CONSTITUENTS)
    try:
        for media_id, text in SEGMENTS.items():
            opened.publish(
                media_id, 1, [Segment(seg_idx=0, start_ms=1000 * media_id, end_ms=1000 * media_id + 900, text=text)]
            )
        yield opened
    finally:
        opened.close()


def _ids(index: SearchIndex, term: str) -> set[int]:
    return {hit.media_id for hit in index.search(term, 50)}


def _words(text: str, start_ms: int = 0) -> list[Word]:
    return [
        Word(start_ms + i * 400, start_ms + i * 400 + 350, w, w.lower(), 1.0, "machine")
        for i, w in enumerate(text.split())
    ]


def test_haushalt_finds_the_compound_heads(search_index: SearchIndex) -> None:
    # Success criterion 1 (D-04-14): the prefix clause reaches
    # "Haushaltsplanberatung" (split as haushaltsplan|beratung) and
    # "Haushaltssatzung" (stays whole here); 3 is the named catch below.
    assert _ids(search_index, "Haushalt") == {1, 2, 3}


def test_known_limit_haushalt_also_meets_haushalterin(search_index: SearchIndex) -> None:
    # Catch accepted in D-04-14 and T-04-17: the folded stem of "Haushälterin"
    # begins with "haushalt", and a prefix cannot tell the two apart.
    assert 3 in _ids(search_index, "Haushalt")


def test_haeuser_finds_haus(search_index: SearchIndex) -> None:
    # Stemming of phase 1 already does this; it must survive the new way.
    assert 4 in _ids(search_index, "Häuser")


def test_miete_finds_mietvertrag(search_index: SearchIndex) -> None:
    # "mietvertrag" stays one term (an ngerman entry); only the prefix of the
    # stem "miet" reaches it.
    assert _ids(search_index, "Miete") == {5}


def test_known_limit_plan_does_not_find_bebauungsplan(search_index: SearchIndex) -> None:
    # The head prefix never helps for the tail of a compound (04-RESEARCH):
    # "bebauungsplan" is one term and "Plan" is below the prefix floor.
    assert _ids(search_index, "Plan") == set()


def test_haus_below_the_floor_adds_no_prefix(search_index: SearchIndex) -> None:
    # "Haus" has four letters: no regex clause, so "Hausaufgabe" (unsplit, no
    # list entry covers "aufgabe") stays unfound and only the plain term hits.
    assert PREFIX_MIN_CHARS == 5
    assert _ids(search_index, "Haus") == {4}


def test_a_word_with_a_digit_gets_no_prefix(search_index: SearchIndex) -> None:
    # Digits stay exact: "Projekt4" must not reach "Projekt42" over a prefix.
    assert _ids(search_index, "Projekt42") == {8}
    assert _ids(search_index, "Projekt4") == set()


def test_prefix_pattern_escapes_metacharacters_and_caps_the_stem() -> None:
    # T-04-16: the pattern is a plain anchored prefix, never user regex, and
    # never longer than a token of the chain can be.
    assert _prefix_pattern("haus(halt") == r"haus\(halt.*"
    assert _prefix_pattern("a" * 100) == "a" * MAX_TOKEN_CHARS + ".*"


def test_the_jump_lands_on_the_prefix_hit(search_index: SearchIndex) -> None:
    words = _words("die Haushaltsplanberatung beginnt", start_ms=2000)

    assert search_index.first_match_ms("Haushalt", words) == 2000 + 1 * 400


def test_a_short_term_keeps_the_legacy_way_scores(search_index: SearchIndex) -> None:
    # A term made only of words below the floor, without a number and without a
    # syntax error, still goes through parse_query as in phases 1 to 3. The
    # reference is tantivy itself, not a second call of the new code.
    reference_query = search_index._index.parse_query("Haus", list(BODY_FIELDS), conjunction_by_default=True)
    searcher = search_index._index.searcher()
    reference = [
        (searcher.doc(address).get_first("media_id"), float(score))
        for score, address in searcher.search(reference_query, 50).hits
    ]

    hits = search_index.search("Haus", 50)

    assert [(hit.media_id, hit.score) for hit in hits] == reference
    assert [hit.media_id for hit in hits] == [4]
