"""The origin of a reference and the preview job of its content (plan 03-03, D-03-05, T-03-08 to T-03-10).

A reference carries where the PHP app found it: event (a user uploaded or
changed it) or crawl (the walk over a storage). event always wins, never the
other way round. Keying a reference seeds the preview job of its content in
the same commit; a copy of the same content never makes a second job.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from audio_video_search_backend.store.repo import ORIGINS, IntakeItem, Store

NOW = 1_800_000_000
SHA_A = "1" * 64
SHA_B = "2" * 64
HEAD = "9" * 64
PREFILTER = "a" * 64


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state.db"


@pytest.fixture
def store(path: Path) -> Iterator[Store]:
    opened = Store.open(path)
    yield opened
    opened.close()


def _item(file_id: int, kind: str = "content", **fields: Any) -> IntakeItem:
    values: dict[str, Any] = {
        "storage_id": 3,
        "etag": "e1",
        "size": 1000,
        "mtime": 1_700_000_000,
        "prefilter_key": None,
        "reader_uid": "ana",
    }
    values.update(fields)
    return IntakeItem(queue_id=file_id, kind=kind, file_id=file_id, **values)


def _origin(path: Path, file_id: int) -> str:
    with closing(sqlite3.connect(path)) as conn:
        row = conn.execute("SELECT origin FROM file_ref WHERE file_id = ?", (file_id,)).fetchone()
    assert row is not None
    return str(row[0])


def _jobs(path: Path) -> list[tuple[Any, ...]]:
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(
            "SELECT media_id, epoch, state, origin, sort_mtime, updated_at FROM preview_job ORDER BY media_id"
        ).fetchall()


def _write(path: Path, statement: str, values: tuple[Any, ...]) -> None:
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(statement, values)


def _keyed(store: Store, file_id: int, sha256: str, now: int = NOW, **fields: Any) -> int:
    """Take a file in, claim it and hang it at the content of ``sha256``, the way the capture does."""
    store.apply_intake([_item(file_id, **fields)])
    claimed = store.next_capture(now)
    assert claimed is not None
    assert claimed.file_id == file_id
    media_id = store.mark_keyed(claimed, sha256, HEAD, now)
    assert media_id is not None
    return media_id


# -- origin in the intake ----------------------------------------------------------


def test_the_closed_list_of_origins() -> None:
    assert frozenset({"event", "crawl"}) == ORIGINS


def test_an_intake_row_is_crawl_unless_it_says_otherwise() -> None:
    assert _item(1).origin == "crawl"


@pytest.mark.parametrize("kind", ["content", "metadata", "restore", "trash", "delete", "exclude"])
def test_an_origin_outside_the_list_is_refused_without_its_value(store: Store, path: Path, kind: str) -> None:
    with pytest.raises(ValueError, match="invalid intake field: origin") as raised:
        store.apply_intake([_item(10, kind, origin="Upload.mp4")])

    assert "Upload.mp4" not in str(raised.value)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM file_ref").fetchone()[0] == 0


@pytest.mark.parametrize("origin", ["event", "crawl"])
def test_a_new_reference_takes_the_origin_of_its_row(store: Store, path: Path, origin: str) -> None:
    store.apply_intake([_item(10, origin=origin)])

    assert _origin(path, 10) == origin


# The same row as before (content, same bytes), a new metadata row, and a
# change of the bytes: each one is a separate way through apply_intake.
SECOND_ROWS = {
    "same": {"kind": "content"},
    "metadata": {"kind": "metadata"},
    "changed": {"kind": "content", "etag": "e2", "mtime": 1_700_000_100},
}


@pytest.mark.parametrize("second", sorted(SECOND_ROWS))
def test_an_event_turns_a_crawl_reference_into_an_event(store: Store, path: Path, second: str) -> None:
    store.apply_intake([_item(10, origin="crawl")])
    assert _origin(path, 10) == "crawl"

    store.apply_intake([_item(10, origin="event", **SECOND_ROWS[second])])

    assert _origin(path, 10) == "event"


@pytest.mark.parametrize("second", sorted(SECOND_ROWS))
def test_crawl_never_overwrites_event(store: Store, path: Path, second: str) -> None:
    store.apply_intake([_item(10, origin="event")])

    store.apply_intake([_item(10, origin="crawl", **SECOND_ROWS[second])])

    assert _origin(path, 10) == "event"


def test_a_restore_from_the_trash_carries_the_event(store: Store, path: Path) -> None:
    _keyed(store, 10, SHA_A, origin="crawl")
    store.apply_intake([_item(10, "trash")])

    store.apply_intake([_item(10, "restore", origin="event")])

    assert _origin(path, 10) == "event"


# -- the preview job of a keyed content -------------------------------------------


def test_keying_seeds_one_queued_job_with_the_origin_and_mtime_of_the_reference(store: Store, path: Path) -> None:
    media_id = store.media_for_file_sha256(SHA_A)
    store.bump_epoch(media_id)
    store.bump_epoch(media_id)

    assert _keyed(store, 10, SHA_A, origin="event", mtime=1_700_000_500) == media_id

    assert _jobs(path) == [(media_id, 2, "queued", "event", 1_700_000_500, NOW)]


def test_nothing_but_keying_seeds_a_job(store: Store, path: Path) -> None:
    # A reference that is only taken in, and a sample of the walking skeleton
    # (D-02-15), give no job (T-03-09).
    store.apply_intake([_item(10, origin="event")])
    store.put_sample(20, store.media_for_file_sha256(SHA_B))

    assert _jobs(path) == []


def test_a_copy_makes_no_second_job(store: Store, path: Path) -> None:
    media_id = _keyed(store, 10, SHA_A, origin="crawl", mtime=1_700_000_100)

    assert _keyed(store, 11, SHA_A, NOW + 5, origin="crawl", mtime=1_700_000_050) == media_id

    assert _jobs(path) == [(media_id, 0, "queued", "crawl", 1_700_000_100, NOW + 5)]


def test_an_event_copy_turns_the_queued_job_into_an_event_with_the_newest_mtime(store: Store, path: Path) -> None:
    media_id = _keyed(store, 10, SHA_A, origin="crawl", mtime=1_700_000_100)

    _keyed(store, 11, SHA_A, NOW + 5, origin="event", mtime=1_700_000_900)

    assert _jobs(path) == [(media_id, 0, "queued", "event", 1_700_000_900, NOW + 5)]


def test_a_crawl_copy_does_not_overwrite_the_event_of_the_job(store: Store, path: Path) -> None:
    media_id = _keyed(store, 10, SHA_A, origin="event", mtime=1_700_000_100)

    _keyed(store, 11, SHA_A, NOW + 5, origin="crawl", mtime=1_700_000_900)

    assert _jobs(path) == [(media_id, 0, "queued", "event", 1_700_000_900, NOW + 5)]


def test_a_waiting_job_still_takes_a_copy(store: Store, path: Path) -> None:
    # Positive control for the next test: waiting is open like queued.
    media_id = _keyed(store, 10, SHA_A, origin="crawl", mtime=1_700_000_100)
    _write(path, "UPDATE preview_job SET state = 'waiting', reason = 'disk_full' WHERE media_id = ?", (media_id,))

    _keyed(store, 11, SHA_A, NOW + 5, origin="event", mtime=1_700_000_900)

    assert _jobs(path) == [(media_id, 0, "waiting", "event", 1_700_000_900, NOW + 5)]


@pytest.mark.parametrize("state", ["complete", "skipped", "running"])
def test_a_settled_or_running_job_is_not_touched_by_a_copy(store: Store, path: Path, state: str) -> None:
    media_id = _keyed(store, 10, SHA_A, origin="crawl", mtime=1_700_000_100)
    _write(path, "UPDATE preview_job SET state = ? WHERE media_id = ?", (state, media_id))
    before = _jobs(path)

    _keyed(store, 11, SHA_A, NOW + 5, origin="event", mtime=1_700_000_900)

    assert _jobs(path) == before
    assert before[0][2:5] == (state, "crawl", 1_700_000_100)


def test_a_stale_key_seeds_no_job(store: Store, path: Path) -> None:
    store.apply_intake([_item(10, origin="event")])
    claimed = store.next_capture(NOW)
    assert claimed is not None
    # The file changed while it was downloaded.
    store.apply_intake([_item(10, origin="event", etag="e2")])

    assert store.mark_keyed(claimed, SHA_A, HEAD, NOW) is None

    assert _jobs(path) == []


def test_a_failed_capture_seeds_no_job(store: Store, path: Path) -> None:
    store.apply_intake([_item(10, origin="event")])
    claimed = store.next_capture(NOW)
    assert claimed is not None

    assert store.mark_failed(claimed, "read_denied", retry_at=NOW + 60, now=NOW)

    assert _jobs(path) == []


def _attach_setup(store: Store) -> tuple[int, int]:
    """A keyed crawl copy with a prefilter key, and a claimed event copy with the same key."""
    media_id = _keyed(store, 10, SHA_A, origin="crawl", mtime=1_700_000_100, prefilter_key=PREFILTER)
    store.apply_intake([_item(11, origin="event", mtime=1_700_000_700, prefilter_key=PREFILTER, reader_uid="ben")])
    claimed = store.next_capture(NOW + 5)
    assert claimed is not None
    assert claimed.file_id == 11
    return media_id, claimed.file_id


def test_a_copy_attached_by_proof_joins_the_job_of_its_content(store: Store, path: Path) -> None:
    media_id, file_id = _attach_setup(store)

    assert store.attach_by_proof(file_id, media_id, "e1", NOW + 5) is True

    assert _jobs(path) == [(media_id, 0, "queued", "event", 1_700_000_700, NOW + 5)]


def test_a_refused_attach_leaves_the_job_alone(store: Store, path: Path) -> None:
    media_id, file_id = _attach_setup(store)
    before = _jobs(path)

    assert store.attach_by_proof(file_id, media_id, "other-etag", NOW + 5) is False

    assert _jobs(path) == before


# -- the job goes with its content -----------------------------------------------------


def test_an_exclusion_forgets_the_job_with_its_content(store: Store, path: Path) -> None:
    media_id = _keyed(store, 10, SHA_A, origin="event")

    store.apply_intake([_item(10, "exclude")])

    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM media WHERE media_id = ?", (media_id,)).fetchone()[0] == 0
    assert _jobs(path) == []


def test_a_deleted_file_keeps_the_job_of_its_orphaned_content(store: Store, path: Path) -> None:
    # Positive control for the test above: an orphan is only marked (D-02-13),
    # so a copy that turns up again keeps its place in the work.
    media_id = _keyed(store, 10, SHA_A, origin="event")

    store.apply_intake([_item(10, "delete")])

    assert [row[0] for row in _jobs(path)] == [media_id]


def test_forgetting_an_orphan_takes_its_job(store: Store, path: Path) -> None:
    media_id = _keyed(store, 10, SHA_A, origin="event")
    store.apply_intake([_item(10, "delete")])

    assert store.forget_media(media_id) is True

    assert _jobs(path) == []


def test_removing_the_last_sample_of_an_orphan_with_a_job_does_not_fail(store: Store, path: Path) -> None:
    media_id = _keyed(store, 10, SHA_A, origin="event")
    store.put_sample(20, media_id)
    store.apply_intake([_item(10, "delete")])

    assert store.remove_sample(20) == ("removed", media_id)

    assert _jobs(path) == []
