"""The last reference of a content, by cause (plan 02-15, D-02-04, D-02-09, D-02-13).

An exclusion forgets: when the last reference of a content falls, its words,
transcripts, current pointer, corrections, keys, the media item and the index
documents go at once. Every other cause (a deleted file, a storage that is
gone) only marks the content orphaned; a copy with the same bytes that turns
up later hangs at it again and keeps transcript and corrections.

Only contents of the removed references are ever looked at (T-02-56).
"""

import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import SAMPLE_MODEL_SHA256, Level, Provenance
from audio_video_search_backend.store import coverage as cov
from audio_video_search_backend.store import repo
from audio_video_search_backend.store.repo import IntakeItem, Store
from tests.test_index_open import CONSTITUENTS

NOW = 1_800_000_000
MODEL = "c" * 64
SHA_A = "1" * 64
SHA_B = "2" * 64
SHA_C = "3" * 64
HEAD = "9" * 64
MEDIA_TABLES = ("media", "media_key", "transcript", "current", "correction", "file_ref", "sample_ref")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    opened = Store.open(tmp_path / "state.db")
    yield opened
    opened.close()


@pytest.fixture
def search_index(tmp_path: Path) -> Iterator[SearchIndex]:
    opened = SearchIndex.open(tmp_path / "idx", constituents=CONSTITUENTS)
    try:
        yield opened
    finally:
        opened.close()


def _conn(store: Store) -> sqlite3.Connection:
    return store.reading_connection()


def _content(store: Store, file_id: int, *, storage_id: int = 3, **fields: Any) -> None:
    values: dict[str, Any] = {
        "etag": "e1",
        "size": 1000,
        "mtime": 1_700_000_000,
        "prefilter_key": None,
        "reader_uid": "ana",
    }
    values.update(fields)
    store.apply_intake([IntakeItem(queue_id=file_id, kind="content", file_id=file_id, storage_id=storage_id, **values)])


def _keyed(store: Store, file_id: int, sha256: str, **fields: Any) -> int:
    """A reference the way the capture leaves it: taken in, claimed, hung at the content of its bytes."""
    _content(store, file_id, **fields)
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert claimed.file_id == file_id
    media_id = store.mark_keyed(claimed, sha256, HEAD, NOW)
    assert media_id is not None
    return media_id


def _words(text: str) -> list[Word]:
    return [Word(i * 400, i * 400 + 350, w, w.lower(), 0.9, "machine") for i, w in enumerate(text.split())]


def _transcript(store: Store, media_id: int, sha256: str, text: str = "Dies ist der Haushalt") -> int:
    prov = Provenance(
        engine="parakeet",
        model_sha256=MODEL,
        config_version=1,
        profile="balanced",
        level=Level.PREVIEW,
        epoch=store.media_epoch(media_id),
        language="de",
        input_file_sha256=sha256,
    )
    result = store.publish_version(media_id, prov, _words(text))
    assert result.published
    assert result.version_id is not None
    return result.version_id


def _correction(store: Store, media_id: int) -> int:
    return store.add_correction(
        media_id, 1200, 1550, "text", "Haushaltsplan", author_uid="ana", base_version_id=None, base_text=None
    )


def _rows(store: Store, table: str, media_id: int) -> int:
    assert table in MEDIA_TABLES
    sql = f"SELECT COUNT(*) FROM {table} WHERE media_id = ?"  # noqa: S608 - fixed table names of the test
    return int(_conn(store).execute(sql, (media_id,)).fetchone()[0])


def _word_rows(store: Store, version_id: int) -> int:
    return int(_conn(store).execute("SELECT COUNT(*) FROM word WHERE version_id = ?", (version_id,)).fetchone()[0])


def _orphaned_at(store: Store, media_id: int) -> object:
    row = _conn(store).execute("SELECT orphaned_at FROM media WHERE media_id = ?", (media_id,)).fetchone()
    assert row is not None
    return row[0]


def _two_copies(store: Store) -> tuple[int, int]:
    """Content M with the active copies 10 and 11, a transcript and a correction; returns (M, version)."""
    media_id = _keyed(store, 10, SHA_A)
    assert _keyed(store, 11, SHA_A) == media_id
    version_id = _transcript(store, media_id, SHA_A)
    _correction(store, media_id)
    return media_id, version_id


# -- exclusion forgets ----------------------------------------------------------------


def test_an_exclusion_keeps_everything_while_an_active_copy_remains(store: Store) -> None:
    media_id, version_id = _two_copies(store)

    assert store.remove_refs(file_ids=[10], cause="exclude", now=NOW) == []

    assert store.file_ref(10) is None
    assert store.file_ids_for_media(media_id) == [11]
    assert _orphaned_at(store, media_id) is None
    assert (_rows(store, "transcript", media_id), _rows(store, "correction", media_id)) == (1, 1)
    assert _word_rows(store, version_id) == 4
    assert store.current(media_id) is not None


def test_an_exclusion_of_the_last_copy_forgets_the_content(store: Store) -> None:
    media_id, version_id = _two_copies(store)
    store.remove_refs(file_ids=[10], cause="exclude", now=NOW)

    assert store.remove_refs(file_ids=[11], cause="exclude", now=NOW) == [media_id]

    for table in ("file_ref", "correction", "current", "transcript", "media_key", "media"):
        assert _rows(store, table, media_id) == 0, table
    assert _word_rows(store, version_id) == 0
    assert store.current(media_id) is None
    # The index learns it through the outbox: revision 0 is the retirement mark.
    assert store.pending_index_work() == [(media_id, repo.RETIRED_REV)]
    assert store.retired_media() == [media_id]


def test_both_copies_excluded_at_once_forget_the_content(store: Store) -> None:
    media_id, _ = _two_copies(store)

    assert store.remove_refs(file_ids=[11, 10, 10], cause="exclude", now=NOW) == [media_id]
    assert _rows(store, "media", media_id) == 0


def test_an_exclusion_leaves_other_contents_alone(store: Store) -> None:
    media_id, _ = _two_copies(store)
    # A content without any reference, marked long ago: not touched by this removal (T-02-56).
    lonely = _keyed(store, 20, SHA_B)
    version = _transcript(store, lonely, SHA_B)
    store.remove_refs(file_ids=[20], cause="delete", now=NOW - 50)
    # And one that is in use.
    used = _keyed(store, 30, SHA_C)
    _transcript(store, used, SHA_C)

    assert store.remove_refs(file_ids=[10, 11], cause="exclude", now=NOW) == [media_id]

    assert _orphaned_at(store, lonely) == NOW - 50
    assert (_rows(store, "transcript", lonely), _word_rows(store, version)) == (1, 4)
    assert _orphaned_at(store, used) is None
    assert store.file_ids_for_media(used) == [30]


def test_an_exclusion_does_not_forget_while_a_trashed_copy_holds_the_content(store: Store) -> None:
    media_id, _ = _two_copies(store)
    _conn(store).execute("UPDATE file_ref SET state = 'trashed' WHERE file_id = 11")

    assert store.remove_refs(file_ids=[10], cause="exclude", now=NOW) == []

    # Not forgotten (the copy in the trash may come back), but without an active copy: marked.
    assert _rows(store, "transcript", media_id) == 1
    assert _orphaned_at(store, media_id) == NOW
    assert store.file_ids_for_media(media_id) == []


def test_a_reference_without_a_content_is_just_removed(store: Store) -> None:
    _content(store, 10)

    assert store.remove_refs(file_ids=[10], cause="exclude", now=NOW) == []
    assert store.file_ref(10) is None
    assert store.pending_index_work() == []


def test_unknown_ids_are_no_error_and_change_nothing(store: Store) -> None:
    media_id, _ = _two_copies(store)

    assert store.remove_refs(file_ids=[98, 99], cause="exclude", now=NOW) == []
    assert store.remove_refs(storage_ids=[77], cause="exclude", now=NOW) == []
    assert store.remove_refs(file_ids=[], cause="exclude", now=NOW) == []
    assert store.file_ids_for_media(media_id) == [10, 11]


def test_work_of_the_index_for_a_forgotten_content_is_replaced_by_the_mark(store: Store) -> None:
    media_id, _ = _two_copies(store)
    assert store.pending_index_work() == [(media_id, 1), (media_id, 2)]

    store.remove_refs(file_ids=[10, 11], cause="exclude", now=NOW)

    assert store.pending_index_work() == [(media_id, 0)]


# -- every other cause only marks -----------------------------------------------------


@pytest.mark.parametrize("cause", ["delete", "gone", "vanished_expired"])
def test_any_other_cause_only_marks_the_content_orphaned(store: Store, cause: repo.RemoveCause) -> None:
    media_id, version_id = _two_copies(store)

    assert store.remove_refs(file_ids=[10], cause=cause, now=NOW) == []
    assert _orphaned_at(store, media_id) is None
    assert store.remove_refs(file_ids=[11], cause=cause, now=NOW + 5) == []

    assert (store.file_ref(10), store.file_ref(11)) == (None, None)
    assert _orphaned_at(store, media_id) == NOW + 5
    assert (_rows(store, "transcript", media_id), _rows(store, "correction", media_id)) == (1, 1)
    assert (_rows(store, "media_key", media_id), _word_rows(store, version_id)) == (1, 4)
    assert store.current(media_id) is not None
    # Not findable and not counted (T-02-54).
    assert store.file_ids_for_media(media_id) == []
    found = cov.coverage(_conn(store), NOW)
    assert (found.contents, found.transcribed, found.files) == (0, 0, 0)
    assert store.retired_media() == []


def test_a_copy_of_an_orphaned_content_hangs_at_it_again(store: Store) -> None:
    media_id, version_id = _two_copies(store)
    store.remove_refs(file_ids=[10, 11], cause="delete", now=NOW)
    assert _orphaned_at(store, media_id) == NOW

    assert _keyed(store, 12, SHA_A) == media_id

    assert _orphaned_at(store, media_id) is None
    assert store.file_ids_for_media(media_id) == [12]
    assert (_rows(store, "transcript", media_id), _rows(store, "correction", media_id)) == (1, 1)
    assert _word_rows(store, version_id) == 4
    assert [c.body for c in store.active_corrections(media_id)] == ["Haushaltsplan"]


def test_a_copy_of_a_forgotten_content_starts_from_nothing(store: Store) -> None:
    media_id, _ = _two_copies(store)
    store.remove_refs(file_ids=[10, 11], cause="exclude", now=NOW)

    again = _keyed(store, 12, SHA_A)

    assert again != media_id  # the mark of the index still stands, the id is not handed out again
    assert store.current(again) is None
    assert store.active_corrections(again) == []


# -- by storage -----------------------------------------------------------------------


def test_an_excluded_storage_loses_its_references_and_forgets_its_contents(store: Store) -> None:
    here = _keyed(store, 10, SHA_A, storage_id=5)
    _transcript(store, here, SHA_A)
    shared = _keyed(store, 11, SHA_B, storage_id=5)
    assert _keyed(store, 12, SHA_B, storage_id=6) == shared
    _transcript(store, shared, SHA_B)
    _content(store, 13, storage_id=5)

    assert store.remove_refs(storage_ids=[5], cause="exclude", now=NOW) == [here]

    assert [store.file_ref(f) for f in (10, 11, 13)] == [None, None, None]
    assert _rows(store, "media", here) == 0
    assert store.file_ids_for_media(shared) == [12]
    assert _rows(store, "transcript", shared) == 1


def test_the_removal_by_storage_uses_the_storage_index(store: Store) -> None:
    plan = _conn(store).execute("EXPLAIN QUERY PLAN " + repo._REMOVE_BY_STORAGE, ("[5]",)).fetchall()

    assert any("file_ref_storage" in str(row[3]) for row in plan), plan


# -- size -----------------------------------------------------------------------------


def test_ten_thousand_ids_are_removed_in_one_transaction(store: Store) -> None:
    conn = _conn(store)
    conn.execute("BEGIN")
    conn.executemany("INSERT INTO media (media_id, created_at) VALUES (?, 0)", ((m,) for m in range(1, 51)))
    conn.executemany(
        "INSERT INTO file_ref (file_id, media_id, storage_id, reader_uid, etag, size, mtime, state, stage, attempts, "
        "updated_at) VALUES (?, ?, 3, 'ana', 'e', 1, 1, 'active', 'keyed', 0, 0)",
        ((f, f % 50 + 1) for f in range(1, 10_002)),
    )
    conn.execute("COMMIT")
    statements: list[str] = []
    conn.set_trace_callback(statements.append)

    forgotten = store.remove_refs(file_ids=list(range(1, 10_001)), cause="exclude", now=NOW)

    conn.set_trace_callback(None)
    # Reference 10001 holds content 2; the other 49 lost their last one.
    assert forgotten == [m for m in range(1, 51) if m != 2]
    assert int(conn.execute("SELECT COUNT(*) FROM file_ref").fetchone()[0]) == 1
    assert int(conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]) == 1
    assert [s for s in statements if s.startswith(("BEGIN", "COMMIT", "ROLLBACK"))] == ["BEGIN IMMEDIATE", "COMMIT"]
    # The ids travel as one JSON text, not as ten thousand statements.
    assert len([s for s in statements if "DELETE FROM file_ref" in s]) == 1
    assert len(statements) < 1000


# -- what is refused before anything is written ---------------------------------------


@pytest.mark.parametrize(
    "arguments",
    [
        {"cause": "exclude"},
        {"file_ids": [10], "storage_ids": [3], "cause": "exclude"},
        {"file_ids": [10], "cause": "trash"},
        {"file_ids": [10], "cause": ""},
        {"file_ids": [True], "cause": "exclude"},
        {"file_ids": [0], "cause": "exclude"},
        {"file_ids": [-1], "cause": "exclude"},
        {"file_ids": ["10"], "cause": "exclude"},
        {"storage_ids": [-3], "cause": "exclude"},
        {"storage_ids": [3.0], "cause": "exclude"},
    ],
    ids=["no ids", "both", "trash", "empty cause", "bool", "zero", "negative", "text", "negative storage", "float"],
)
def test_arguments_outside_the_contract_are_refused(store: Store, arguments: dict[str, Any]) -> None:
    media_id, _ = _two_copies(store)

    with pytest.raises(ValueError, match="invalid removal field"):
        store.remove_refs(**arguments)

    assert store.file_ids_for_media(media_id) == [10, 11]


def test_a_failure_in_the_middle_rolls_everything_back(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    media_id, version_id = _two_copies(store)
    monkeypatch.setattr(repo, "_DELETE_MEDIA", "DELETE FROM no_such_table WHERE media_id = ?")

    with pytest.raises(sqlite3.OperationalError):
        store.remove_refs(file_ids=[10, 11], cause="exclude", now=NOW)

    assert store.file_ids_for_media(media_id) == [10, 11]
    assert (_rows(store, "transcript", media_id), _rows(store, "correction", media_id)) == (1, 1)
    assert _word_rows(store, version_id) == 4


# -- forget_media and orphan_media on their own ---------------------------------------


def test_forget_media_refuses_a_content_that_still_has_a_reference(store: Store) -> None:
    media_id, _ = _two_copies(store)

    assert store.forget_media(media_id) is False
    assert _rows(store, "transcript", media_id) == 1

    store.remove_refs(file_ids=[10, 11], cause="delete", now=NOW)
    assert store.forget_media(media_id) is True
    assert _rows(store, "media", media_id) == 0
    assert store.forget_media(media_id) is False


def test_orphan_media_marks_only_a_content_without_an_active_reference(store: Store) -> None:
    media_id, _ = _two_copies(store)

    assert store.orphan_media(media_id, now=NOW) is False
    assert _orphaned_at(store, media_id) is None

    _conn(store).execute("UPDATE file_ref SET state = 'unreadable' WHERE media_id = ?", (media_id,))
    assert store.orphan_media(media_id, now=NOW) is True
    assert _orphaned_at(store, media_id) == NOW
    # The first mark stays: the seven days of phase 8 run from it.
    assert store.orphan_media(media_id, now=NOW + 9) is False
    assert _orphaned_at(store, media_id) == NOW


# -- the sample layer (D-02-15) -------------------------------------------------------


def _sample(store: Store, file_id: int, sha256: str) -> int:
    media_id = store.media_for_file_sha256(sha256)
    store.put_sample(file_id, media_id)
    prov = Provenance(
        engine="sample",
        model_sha256=SAMPLE_MODEL_SHA256,
        config_version=1,
        profile="debug",
        level=Level.SAMPLE,
        epoch=store.media_epoch(media_id),
        language="de",
        input_file_sha256=sha256,
    )
    assert store.publish_version(media_id, prov, _words("Hier beginnt der Testtreffer")).published
    return media_id


def test_the_content_of_a_sample_is_removed_only_by_remove_sample(store: Store) -> None:
    media_id = _sample(store, 7, SHA_A)
    assert _keyed(store, 10, SHA_A) == media_id

    assert store.remove_refs(file_ids=[10], cause="exclude", now=NOW) == []

    assert (_rows(store, "media", media_id), _rows(store, "media_key", media_id)) == (1, 1)
    assert store.sample_media(7) == media_id
    assert store.current(media_id) is not None
    assert store.file_ids_for_media(media_id) == [7]
    assert store.retired_media() == []

    assert store.remove_sample(7) == ("removed", media_id)
    assert _rows(store, "media", media_id) == 0


def test_a_real_transcript_goes_also_when_a_sample_keeps_the_media_item(store: Store) -> None:
    media_id = _sample(store, 7, SHA_A)
    _keyed(store, 10, SHA_A)
    version_id = _transcript(store, media_id, SHA_A)
    _correction(store, media_id)

    assert store.remove_refs(file_ids=[10], cause="exclude", now=NOW) == [media_id]

    engines = [str(r[0]) for r in _conn(store).execute("SELECT engine FROM transcript WHERE media_id = ?", (media_id,))]
    assert engines == ["sample"]
    assert _word_rows(store, version_id) == 0
    assert _rows(store, "correction", media_id) == 0
    assert store.current(media_id) is None  # it pointed at the real version
    assert store.sample_media(7) == media_id
    assert store.retired_media() == [media_id]


# -- the index ------------------------------------------------------------------------


def _indexed(store: Store, index: SearchIndex) -> tuple[int, int]:
    """Two contents with one copy each, both in the index; returns their media ids."""
    first = _keyed(store, 10, SHA_A)
    _transcript(store, first, SHA_A, "Dies ist der Haushalt")
    second = _keyed(store, 20, SHA_B)
    _transcript(store, second, SHA_B, "Noch ein Haushalt hier")
    assert index.reconcile(store) == 2
    assert sorted(h.media_id for h in index.search("Haushalt", 10)) == [first, second]
    return first, second


def test_the_documents_of_a_forgotten_content_leave_the_index(store: Store, search_index: SearchIndex) -> None:
    first, second = _indexed(store, search_index)
    store.remove_refs(file_ids=[10], cause="exclude", now=NOW)

    assert search_index.retire_forgotten(store) == 1

    assert [h.media_id for h in search_index.search("Haushalt", 10)] == [second]
    assert store.pending_index_work() == []
    assert store.retired_media() == []
    assert search_index.retire_forgotten(store) == 0
    assert first != second


def test_an_orphaned_content_keeps_its_documents(store: Store, search_index: SearchIndex) -> None:
    first, second = _indexed(store, search_index)
    store.remove_refs(file_ids=[10], cause="delete", now=NOW)

    assert search_index.retire_forgotten(store) == 0

    # Still in the index for the copy that may come back; no file id gives a hit for it.
    assert sorted(h.media_id for h in search_index.search("Haushalt", 10)) == [first, second]
    assert store.file_ids_for_media(first) == []


def test_a_restart_before_the_retirement_is_repaired_by_reconcile(store: Store, search_index: SearchIndex) -> None:
    first, second = _indexed(store, search_index)
    store.remove_refs(file_ids=[10], cause="exclude", now=NOW)

    assert search_index.reconcile(store) == 1

    assert [h.media_id for h in search_index.search("Haushalt", 10)] == [second]
    assert store.pending_index_work() == []
    assert first != second


def test_a_media_id_is_not_handed_out_again_before_the_index_let_go_of_it(
    store: Store, search_index: SearchIndex
) -> None:
    _first, second = _indexed(store, search_index)
    store.remove_refs(file_ids=[20], cause="exclude", now=NOW)
    # ``second`` was the highest media id; SQLite alone would hand it out again.
    fresh = store.media_for_file_sha256(SHA_C)

    assert fresh > second

    search_index.retire_forgotten(store)
    assert [h.media_id for h in search_index.search("Haushalt", 10)] == [_first]


# -- logs carry counts only -----------------------------------------------------------


def test_the_log_lines_carry_counts_and_the_cause(store: Store, caplog: pytest.LogCaptureFixture) -> None:
    _two_copies(store)
    _keyed(store, 20, SHA_B)
    caplog.set_level(logging.INFO, logger=repo.__name__)

    store.remove_refs(file_ids=[20], cause="delete", now=NOW)
    store.remove_refs(file_ids=[10, 11], cause="exclude", now=NOW)

    lines = {r.getMessage(): r for r in caplog.records if r.name == repo.__name__}
    orphaned, forgotten = lines["media orphaned"], lines["media forgotten"]
    assert (orphaned.__dict__["media"], orphaned.__dict__["references"], orphaned.__dict__["cause"]) == (1, 1, "delete")
    assert (forgotten.__dict__["media"], forgotten.__dict__["references"], forgotten.__dict__["cause"]) == (
        1,
        2,
        "exclude",
    )
    assert forgotten.__dict__["words"] == 4
    assert forgotten.__dict__["corrections"] == 1
