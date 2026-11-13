"""What an exclusion leaves behind in the container: nothing (plan 02-16, D-02-04, D-02-15a).

Two gaps noted for plan 16 in deferred-items.md of phase 2:

- the capture meets an excluded file before the exclude row of the queue does
  (the gateway answers 403 excluded): the reference was deleted and its
  content only marked orphaned. The exclude row that followed found no
  reference any more, so transcript and corrections stayed until phase 8,
  instead of going at once with the last reference (D-02-04);
- the sample (occ :sample) of an excluded file stayed, and with it a test hit
  for a file the admin had excluded (D-02-15a).

Every other cause (a deleted file, a storage that is gone) still only marks a
content and never touches a sample.
"""

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from audio_video_search_backend import nc
from audio_video_search_backend.api import Services
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.store import repo
from audio_video_search_backend.store.repo import FileRef, IntakeItem, RemoveCause, Store
from audio_video_search_backend.worker import capture as capture_module
from audio_video_search_backend.worker.capture import Capture, CaptureOutcome
from tests.test_exclusion_forget import (
    NOW,
    SHA_A,
    SHA_B,
    _correction,
    _keyed,
    _orphaned_at,
    _rows,
    _sample,
    _transcript,
)
from tests.test_index_open import CONSTITUENTS

SAMPLE_WORD = "Testtreffer"


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


def _claimable(store: Store, file_id: int, media_id: int | None, *, storage_id: int = 3) -> None:
    """A reference the capture takes next, hanging at ``media_id`` or at nothing."""
    store.upsert_file_ref(
        file_id,
        media_id,
        storage_id=storage_id,
        etag="e1",
        size=1000,
        mtime=1_700_000_000,
        state="active",
        stage="pending",
        reason=None,
        reader_uid="ana",
    )


def _claim(store: Store, file_id: int) -> FileRef:
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert claimed.file_id == file_id
    return claimed


def _gone(queue_id: int, kind: str, file_id: int | None, storage_id: int = 3) -> IntakeItem:
    return IntakeItem(
        queue_id=queue_id,
        kind=kind,
        file_id=file_id,
        storage_id=storage_id,
        etag=None,
        size=None,
        mtime=None,
        prefilter_key=None,
        reader_uid=None,
    )


def _known(store: Store, media_id: int) -> tuple[int, int, int, int]:
    """Rows of a content: media item, keys, transcripts, corrections."""
    return (
        _rows(store, "media", media_id),
        _rows(store, "media_key", media_id),
        _rows(store, "transcript", media_id),
        _rows(store, "correction", media_id),
    )


# -- the sample of an excluded file (D-02-15a) ---------------------------------------


def test_the_sample_of_an_excluded_file_goes_with_the_exclusion(store: Store) -> None:
    media_id = _sample(store, 10, SHA_A)
    assert store.file_ids_for_media(media_id) == [10]

    assert store.remove_refs(file_ids=[10], cause="exclude", now=NOW) == [media_id]

    assert store.sample_media(10) is None
    assert store.file_ids_for_media(media_id) == []
    assert store.media_for_file(10) is None
    assert _known(store, media_id) == (0, 0, 0, 0)
    assert store.current(media_id) is None
    assert store.retired_media() == [media_id]


def test_no_sample_hit_is_left_in_the_index_for_an_excluded_file(store: Store, search_index: SearchIndex) -> None:
    media_id = _sample(store, 10, SHA_A)
    search_index.reconcile(store)
    assert [h.media_id for h in search_index.search(SAMPLE_WORD, 10)] == [media_id]

    store.remove_refs(file_ids=[10], cause="exclude", now=NOW)
    assert search_index.retire_forgotten(store) == 1

    assert search_index.search(SAMPLE_WORD, 10) == []
    assert store.retired_media() == []


def test_the_sample_goes_also_when_the_discovery_holds_the_excluded_file(store: Store) -> None:
    media_id = _sample(store, 10, SHA_A)
    assert _keyed(store, 10, SHA_A) == media_id
    _transcript(store, media_id, SHA_A)
    _correction(store, media_id)

    assert store.remove_refs(file_ids=[10], cause="exclude", now=NOW) == [media_id]

    assert store.sample_media(10) is None
    assert store.file_ref(10) is None
    assert _known(store, media_id) == (0, 0, 0, 0)
    assert store.retired_media() == [media_id]


def test_the_sample_of_another_file_on_the_same_content_stays(store: Store) -> None:
    media_id = _sample(store, 7, SHA_A)
    store.put_sample(10, media_id)
    assert store.file_ids_for_media(media_id) == [7, 10]

    assert store.remove_refs(file_ids=[10], cause="exclude", now=NOW) == []

    assert store.sample_media(10) is None
    assert store.sample_media(7) == media_id
    assert store.file_ids_for_media(media_id) == [7]
    assert store.current(media_id) is not None
    assert store.retired_media() == []


def test_an_excluded_storage_takes_the_samples_of_its_files(store: Store) -> None:
    on_it = _keyed(store, 10, SHA_A, storage_id=7)
    store.put_sample(10, on_it)
    elsewhere = _keyed(store, 20, SHA_B, storage_id=3)
    store.put_sample(20, elsewhere)

    store.remove_refs(storage_ids=[7], cause="exclude", now=NOW)

    assert store.sample_media(10) is None
    assert _rows(store, "media", on_it) == 0
    assert store.sample_media(20) == elsewhere
    assert store.file_ids_for_media(elsewhere) == [20]


@pytest.mark.parametrize("cause", ["delete", "gone", "vanished_expired"])
def test_no_other_cause_touches_a_sample(store: Store, cause: RemoveCause) -> None:
    media_id = _sample(store, 10, SHA_A)
    assert _keyed(store, 10, SHA_A) == media_id

    assert store.remove_refs(file_ids=[10], cause=cause, now=NOW) == []

    assert store.sample_media(10) == media_id
    assert store.file_ids_for_media(media_id) == [10]
    assert store.current(media_id) is not None


@pytest.mark.parametrize(
    ("item", "left"),
    [
        (_gone(1, "exclude", 10), None),
        (_gone(1, "exclude_storage", None, 7), None),
        (_gone(1, "delete", 10), "kept"),
        (_gone(1, "trash", 10), "kept"),
    ],
)
def test_the_exclude_rows_of_the_queue_take_the_sample_and_no_other_row_does(
    store: Store, item: IntakeItem, left: str | None
) -> None:
    media_id = _keyed(store, 10, SHA_A, storage_id=7)
    store.put_sample(10, media_id)

    assert store.apply_intake([item]) == [1]

    assert store.sample_media(10) == (None if left is None else media_id)


def test_the_log_of_a_removed_sample_carries_counts_only(store: Store, caplog: pytest.LogCaptureFixture) -> None:
    _sample(store, 4711, SHA_A)
    caplog.set_level(logging.INFO, logger=repo.__name__)

    store.remove_refs(file_ids=[4711], cause="exclude", now=NOW)

    lines = [record for record in caplog.records if record.getMessage() == "samples removed"]
    assert len(lines) == 1
    assert (lines[0].__dict__["samples"], lines[0].__dict__["cause"]) == (1, "exclude")
    for record in caplog.records:
        assert "4711" not in str(record.__dict__)


# -- the capture meets the exclusion first (D-02-04) ----------------------------------


def test_excluded_at_the_download_forgets_a_content_with_its_last_reference(store: Store) -> None:
    media_id = _keyed(store, 10, SHA_A)
    _transcript(store, media_id, SHA_A)
    _correction(store, media_id)
    _claimable(store, 10, media_id)

    assert store.delete_ref(_claim(store, 10), NOW) is True

    assert store.file_ref(10) is None
    assert _known(store, media_id) == (0, 0, 0, 0)
    assert store.retired_media() == [media_id]
    # The exclude row of the queue that follows finds nothing left to do.
    assert store.remove_refs(file_ids=[10], cause="exclude", now=NOW) == []


def test_excluded_at_the_download_keeps_a_content_another_copy_holds(store: Store) -> None:
    media_id = _keyed(store, 10, SHA_A)
    assert _keyed(store, 11, SHA_A) == media_id
    _transcript(store, media_id, SHA_A)
    _correction(store, media_id)
    _claimable(store, 10, media_id)

    assert store.delete_ref(_claim(store, 10), NOW) is True

    assert store.file_ref(10) is None
    assert _known(store, media_id) == (1, 1, 1, 1)
    assert store.file_ids_for_media(media_id) == [11]
    assert _orphaned_at(store, media_id) is None
    assert store.retired_media() == []


def test_excluded_at_the_download_only_marks_a_content_a_copy_in_the_trash_holds(store: Store) -> None:
    media_id = _keyed(store, 10, SHA_A)
    assert _keyed(store, 11, SHA_A) == media_id
    _transcript(store, media_id, SHA_A)
    store.apply_intake([_gone(5, "trash", 11)])
    _claimable(store, 10, media_id)

    assert store.delete_ref(_claim(store, 10), NOW) is True

    # The copy in the trash belongs to somebody who is not excluded and may come back.
    assert _known(store, media_id) == (1, 1, 1, 0)
    assert _orphaned_at(store, media_id) == NOW
    assert store.retired_media() == []


def test_excluded_at_the_download_takes_the_sample_of_the_file(store: Store) -> None:
    media_id = _sample(store, 10, SHA_A)
    _claimable(store, 10, None)

    assert store.delete_ref(_claim(store, 10), NOW) is True

    assert store.sample_media(10) is None
    assert _known(store, media_id) == (0, 0, 0, 0)
    assert store.retired_media() == [media_id]


def test_a_stale_claim_deletes_nothing_and_forgets_nothing(store: Store) -> None:
    media_id = _keyed(store, 10, SHA_A)
    _transcript(store, media_id, SHA_A)
    store.put_sample(10, media_id)
    _claimable(store, 10, media_id)
    claimed = _claim(store, 10)
    # The file changed while the download ran: the claim is no longer the reference.
    stale = FileRef(**{**{name: getattr(claimed, name) for name in FileRef.__slots__}, "etag": "older"})

    assert store.delete_ref(stale, NOW) is False

    assert store.file_ref(10) is not None
    assert store.sample_media(10) == media_id
    assert _known(store, media_id) == (1, 1, 1, 0)
    assert store.retired_media() == []


class _Excluded:
    """The gateway answers 403 excluded for every file."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    async def __call__(self, file_id: int, user_id: str, directory: Path, size: int, cap: int) -> nc.FetchResult:
        self.calls.append(file_id)
        return nc.FetchResult(sha256=None, head_sha256=None, size=0, error=nc.EXCLUDED, status=403)


async def _unexpected_head(file_id: int, user_id: str) -> nc.HeadResult:
    raise AssertionError("no read proof is expected here")


def _stage(store: Store, index: SearchIndex | None, fetch: Any, tmp_path: Path) -> Capture:
    directory = tmp_path / "tmp"
    directory.mkdir(exist_ok=True)
    services = Services(store=store, index=cast("SearchIndex", index))
    return Capture(services, directory=directory, fetch=fetch, head=_unexpected_head, clock=lambda: float(NOW))


async def test_the_capture_lets_the_index_go_of_a_content_it_forgot(
    store: Store, search_index: SearchIndex, tmp_path: Path
) -> None:
    media_id = _keyed(store, 10, SHA_A)
    _transcript(store, media_id, SHA_A, "Dies ist der Haushalt")
    search_index.reconcile(store)
    assert [h.media_id for h in search_index.search("Haushalt", 10)] == [media_id]
    # A content without a head cannot be proved again, so the reference is read in full.
    store._conn.execute("UPDATE media SET head_sha256 = NULL WHERE media_id = ?", (media_id,))
    _claimable(store, 10, media_id)
    fetch = _Excluded()

    step = await _stage(store, search_index, fetch, tmp_path).run_once()

    assert (step.outcome, step.file_id, step.reason) == (CaptureOutcome.DELETED, 10, nc.EXCLUDED)
    assert fetch.calls == [10]
    assert _known(store, media_id) == (0, 0, 0, 0)
    assert search_index.search("Haushalt", 10) == []
    assert store.retired_media() == []


async def test_an_index_that_fails_keeps_the_mark_and_the_step(
    store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    media_id = _keyed(store, 10, SHA_A)
    _transcript(store, media_id, SHA_A)
    store._conn.execute("UPDATE media SET head_sha256 = NULL WHERE media_id = ?", (media_id,))
    _claimable(store, 10, media_id)
    caplog.set_level(logging.ERROR, logger=capture_module.__name__)

    # No index at all: the retirement raises, the deletion stands.
    step = await _stage(store, None, _Excluded(), tmp_path).run_once()

    assert step.outcome == CaptureOutcome.DELETED
    assert _known(store, media_id) == (0, 0, 0, 0)
    assert store.retired_media() == [media_id]
    assert [record.getMessage() for record in caplog.records] == ["index retirement failed"]
