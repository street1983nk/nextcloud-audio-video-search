"""Numbers in the search over a real index (plan 04-01, D-04-11, D-04-12).

Every segment is its own media item, so a hit list reads as a set of ids. The
expected ids are written by hand from the segment texts.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from audio_video_search_backend.index.publish import SearchIndex, Segment
from audio_video_search_backend.index.schema import BODY_FIELDS
from audio_video_search_backend.model.overlay import Word
from tests.test_index_open import CONSTITUENTS

SEGMENTS = {
    1: "Es waren 12 Personen da",
    2: "zwölf Stühle",
    3: "twelve chairs",
    4: "douze chaises",
    5: "am 12. März",
    6: "am zwölften März",
    7: "soixante-dix personnes",
    8: "um 12 Uhr 30",
    9: "Häuser am Markt",
    10: "Markt Markt Häuser",
    11: "Der Markt ist heute voll",
    12: "the twelfth of March",
    13: "le 12e jour",
}

TWELVE = {1, 2, 3, 4, 5, 6, 8, 12, 13}


@pytest.fixture
def search_index(tmp_path: Path) -> Iterator[SearchIndex]:
    opened = SearchIndex.open(tmp_path / "idx", constituents=CONSTITUENTS)
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


@pytest.mark.parametrize("term", ["zwölf", "12", "twelve", "douze", "zwölften", "twelfth", "douzième", "12th", "12e"])
def test_every_spelling_of_twelve_finds_every_twelve(search_index: SearchIndex, term: str) -> None:
    assert _ids(search_index, term) == TWELVE


def test_a_number_and_a_word_must_both_match(search_index: SearchIndex) -> None:
    assert _ids(search_index, "12 Personen") == {1}


def test_the_ordinal_date_finds_both_spellings_of_the_date(search_index: SearchIndex) -> None:
    assert _ids(search_index, "zwölften März") == {5, 6}
    assert _ids(search_index, "am 12. März") == {5, 6}


def test_a_french_compound_number_is_found_through_the_digit(search_index: SearchIndex) -> None:
    assert _ids(search_index, "70 personnes") == {7}
    assert _ids(search_index, "siebzig") == {7}


def test_a_time_with_a_colon_no_longer_breaks_the_query(search_index: SearchIndex) -> None:
    assert _ids(search_index, "12:30") == {8}


def test_a_stop_word_drops_out_instead_of_emptying_the_query(search_index: SearchIndex) -> None:
    assert _ids(search_index, "ein 12") == TWELVE


@pytest.mark.parametrize(("term", "expected"), [("Häuser", [9, 10]), ("Markt", [10, 9, 11])])
def test_a_term_without_a_number_keeps_hits_order_and_scores(
    search_index: SearchIndex, term: str, expected: list[int]
) -> None:
    # The reference is tantivy itself with the query of phases 1 to 3, not a
    # second call of the new code.
    reference_query = search_index._index.parse_query(term, list(BODY_FIELDS), conjunction_by_default=True)
    searcher = search_index._index.searcher()
    reference = [
        (searcher.doc(address).get_first("media_id"), float(score))
        for score, address in searcher.search(reference_query, 50).hits
    ]

    hits = search_index.search(term, 50)

    # The order as written down: "Markt Markt Häuser" holds the term twice in
    # three words and leads; at equal length and count the earlier document
    # comes first; the longest segment comes last.
    assert [hit.media_id for hit in hits] == expected
    assert [(hit.media_id, hit.score) for hit in hits] == reference


def _words(text: str, start_ms: int = 0) -> list[Word]:
    return [
        Word(start_ms + i * 400, start_ms + i * 400 + 350, w, w.lower(), 1.0, "machine")
        for i, w in enumerate(text.split())
    ]


def test_the_jump_lands_on_the_number_in_any_spelling(search_index: SearchIndex) -> None:
    words = _words("Es waren 12 Personen", start_ms=1000)

    assert search_index.first_match_ms("zwölf", words) == 1000 + 2 * 400
    assert search_index.first_match_ms("twelfth", words) == 1000 + 2 * 400
    assert search_index.first_match_ms("zwölf", _words("am zwölften März")) == 400
    assert search_index.first_match_ms("soixante-dix", _words("es waren 70 Leute")) == 2 * 400
    assert search_index.first_match_ms("dreizehn", words) is None
