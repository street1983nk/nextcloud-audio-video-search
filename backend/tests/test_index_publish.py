"""The derived index: revisions, retirement, reconcile and rebuild from SQLite."""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from audio_video_search_backend.index.publish import SearchIndex, Segment, segments_from_words
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import SAMPLE_MODEL_SHA256, Level, Provenance
from audio_video_search_backend.store.repo import Store
from tests.test_index_open import CONSTITUENTS

SHA_A = "a" * 64
SHA_B = "b" * 64


@pytest.fixture
def search_index(tmp_path: Path) -> Iterator[SearchIndex]:
    opened = SearchIndex.open(tmp_path / "idx", constituents=CONSTITUENTS)
    try:
        yield opened
    finally:
        opened.close()


def _segment(text: str, start_ms: int = 2000, seg_idx: int = 0) -> Segment:
    return Segment(seg_idx=seg_idx, start_ms=start_ms, end_ms=start_ms + 1000, text=text)


def _words(text: str, start_ms: int = 0) -> list[Word]:
    return [
        Word(start_ms + i * 400, start_ms + i * 400 + 350, w, w.lower(), 1.0, "machine")
        for i, w in enumerate(text.split())
    ]


def _publish(store: Store, sha: str, text: str, *, file_id: int, level: Level = Level.SAMPLE) -> tuple[int, int]:
    media_id = store.media_for_file_sha256(sha)
    store.upsert_file_ref(
        file_id, media_id, storage_id=0, etag="", size=1, mtime=0, state="sample", stage="keyed", reason="sample"
    )
    prov = Provenance(
        engine="sample" if level == Level.SAMPLE else "parakeet",
        model_sha256=SAMPLE_MODEL_SHA256 if level == Level.SAMPLE else "c" * 64,
        config_version=1,
        profile="debug" if level == Level.SAMPLE else "fast",
        level=level,
        epoch=store.media_epoch(media_id),
        language="de",
        input_file_sha256=sha,
    )
    result = store.publish_version(media_id, prov, _words(text))
    assert result.published
    assert result.index_rev is not None
    return media_id, result.index_rev


def test_a_published_segment_is_found_with_its_revision_and_time(search_index: SearchIndex) -> None:
    search_index.publish(4, 1, [_segment("Hier beginnt die Audiosuche im Video")])

    hits = search_index.search("Audiosuche", 10)

    assert [(h.media_id, h.index_rev, h.seg_idx, h.start_ms) for h in hits] == [(4, 1, 0, 2000)]
    assert "Audiosuche" in hits[0].text
    assert hits[0].score > 0


def test_a_new_revision_replaces_the_old_one_after_retire(search_index: SearchIndex) -> None:
    search_index.publish(4, 1, [_segment("alter Wortlaut Audiosuche")])
    search_index.publish(4, 2, [_segment("neuer Wortlaut Testtreffer")])
    search_index.retire(4, keep_rev=2)

    assert search_index.search("Audiosuche", 10) == []
    assert [h.index_rev for h in search_index.search("Testtreffer", 10)] == [2]


def test_both_revisions_stand_until_retire(search_index: SearchIndex) -> None:
    # A crash between add and delete leaves both; the search route keeps the
    # highest admissible one (tests/test_api_routes.py).
    search_index.publish(4, 1, [_segment("Audiosuche eins")])
    search_index.publish(4, 2, [_segment("Audiosuche zwei")])

    assert sorted(h.index_rev for h in search_index.search("Audiosuche", 10)) == [1, 2]


def test_publishing_the_same_revision_twice_does_not_duplicate(search_index: SearchIndex) -> None:
    search_index.publish(4, 1, [_segment("Audiosuche")])
    search_index.publish(4, 1, [_segment("Audiosuche")])

    assert len(search_index.search("Audiosuche", 10)) == 1


def test_retire_with_keep_rev_zero_removes_every_document(search_index: SearchIndex) -> None:
    search_index.publish(4, 1, [_segment("Audiosuche")])
    search_index.publish(5, 1, [_segment("Audiosuche")])
    search_index.retire(4, keep_rev=0)

    assert [h.media_id for h in search_index.search("Audiosuche", 10)] == [5]


@pytest.mark.parametrize("term", ["", "   ", 'field:"', "AND", "(((", "body_de:"])
def test_an_empty_or_broken_query_is_an_empty_list(search_index: SearchIndex, term: str) -> None:
    search_index.publish(4, 1, [_segment("Audiosuche")])

    assert search_index.search(term, 10) == []


def test_a_long_term_is_cut_to_two_hundred_characters(search_index: SearchIndex) -> None:
    search_index.publish(4, 1, [_segment("Audiosuche")])

    assert search_index.search("Audiosuche " + "x" * 400, 10) != []
    assert search_index.search("x" * 199 + " Audiosuche", 10) == []


def test_the_first_matching_word_carries_the_time(search_index: SearchIndex) -> None:
    words = _words("Dies ist die Audiosuche heute", start_ms=1000)

    assert search_index.first_match_ms("audiosuchen", words) == 1000 + 3 * 400
    assert search_index.first_match_ms("nichts", words) is None


def test_reconcile_publishes_pending_work_and_marks_it(search_index: SearchIndex, store: Store) -> None:
    media_id, rev = _publish(store, SHA_A, "Dies ist die Audiosuche", file_id=7)
    assert store.pending_index_work() == [(media_id, rev)]

    assert search_index.reconcile(store) == 1

    assert store.pending_index_work() == []
    assert [(h.media_id, h.index_rev) for h in search_index.search("Audiosuche", 10)] == [(media_id, rev)]


def test_reconcile_publishes_the_effective_words(search_index: SearchIndex, store: Store) -> None:
    media_id, _ = _publish(store, SHA_A, "Dies ist die Audiosuche", file_id=7)
    search_index.reconcile(store)
    store.add_correction(
        media_id, 1200, 1600, "text", "Videosuche", author_uid="alice", base_version_id=None, base_text=None
    )

    search_index.reconcile(store)

    assert search_index.search("Audiosuche", 10) == []
    assert [h.index_rev for h in search_index.search("Videosuche", 10)] == [2]


def test_reconcile_deletes_documents_without_a_current_version(search_index: SearchIndex, store: Store) -> None:
    search_index.publish(99, 3, [_segment("Audiosuche verwaist")])
    media_id, rev = _publish(store, SHA_A, "Testtreffer", file_id=7)
    search_index.publish(media_id, rev, segments_from_words(store.effective_words(media_id)))
    store.mark_indexed(media_id, rev)
    # A stale revision of a live media item goes as well.
    search_index.publish(media_id, rev + 5, [_segment("Testtreffer alt")])

    assert search_index.reconcile(store) == 2

    assert search_index.search("Audiosuche", 10) == []
    assert [(h.media_id, h.index_rev) for h in search_index.search("Testtreffer", 10)] == [(media_id, rev)]


def test_reconcile_fills_a_current_version_missing_from_the_index(search_index: SearchIndex, store: Store) -> None:
    media_id, rev = _publish(store, SHA_A, "Testtreffer", file_id=7)
    store.mark_indexed(media_id, rev)  # outbox lost, index empty

    assert search_index.reconcile(store) == 1
    assert [h.media_id for h in search_index.search("Testtreffer", 10)] == [media_id]


def test_reconcile_retires_a_removed_sample_still_in_the_outbox(search_index: SearchIndex, store: Store) -> None:
    media_id, rev = _publish(store, SHA_A, "Testtreffer", file_id=7)
    search_index.publish(media_id, rev, segments_from_words(store.effective_words(media_id)))
    store.remove_sample(7)

    search_index.reconcile(store)

    assert search_index.search("Testtreffer", 10) == []


def test_rebuild_from_store_after_the_directory_is_gone(tmp_path: Path, store: Store) -> None:
    media_a, _ = _publish(store, SHA_A, "Dies ist die Audiosuche", file_id=7)
    media_b, _ = _publish(store, SHA_B, "Ein echter Testtreffer", file_id=8, level=Level.PREVIEW)
    store.add_correction(media_a, 0, 400, "text", "Das", author_uid="alice", base_version_id=None, base_text=None)
    directory = tmp_path / "idx"
    SearchIndex.open(directory, constituents=CONSTITUENTS).close()
    shutil.rmtree(directory)

    rebuilt = SearchIndex.open(directory, constituents=CONSTITUENTS)
    try:
        assert rebuilt.rebuild_from_store(store) == 2
        assert [h.media_id for h in rebuilt.search("Audiosuche", 10)] == [media_a]
        assert [h.media_id for h in rebuilt.search("Testtreffer", 10)] == [media_b]
        # effective_words: the correction is in, the replaced machine word is out.
        assert "Das ist" in rebuilt.search("Audiosuche", 10)[0].text
        assert store.pending_index_work() == []
    finally:
        rebuilt.close()


def test_segments_split_at_a_gap_and_after_forty_words() -> None:
    words = _words(" ".join(f"w{i}" for i in range(45)))
    gap = Word(60_000, 60_350, "spaeter", "spaeter", 1.0, "machine")

    segments = segments_from_words([*words, gap])

    assert [len(s.text.split()) for s in segments] == [40, 5, 1]
    assert [s.seg_idx for s in segments] == [0, 1, 2]
    assert segments[0].start_ms == 0
    assert segments[0].end_ms == 39 * 400 + 350
    assert segments[1].start_ms == 40 * 400
    assert segments[2].start_ms == 60_000
    assert all(isinstance(s.start_ms, int) and isinstance(s.end_ms, int) for s in segments)


def test_a_gap_of_exactly_the_limit_stays_in_one_segment() -> None:
    first = Word(0, 100, "a", "a", 1.0, "machine")
    second = Word(1600, 1700, "b", "b", 1.0, "machine")
    third = Word(3201, 3300, "c", "c", 1.0, "machine")

    assert [s.text for s in segments_from_words([first, second, third])] == ["a b", "c"]
    assert segments_from_words([]) == []
