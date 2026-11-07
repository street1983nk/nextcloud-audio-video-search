"""D-02-15 (Owner 07.11.): the test result of occ :sample and the reference of
the discovery are two layers that never overwrite each other.

Push 2 of phase 2 showed both orders on arm64 (deploy-harp, run 42375022170):

- intake first: the discovery wrote an active, pending reference without a
  media item, the sample published, and the search gave no hit for the file;
- sample first: the intake took the sample row for a changed file, set it to
  pending without a media item and marked the media item orphaned, and the
  hits of the sample were gone.

Both orders have to end in the same hits. The sample stays behind the debug
switch of the PHP app (the hit carries sample true); removing it never touches
the reference of the discovery, and the intake never touches a sample.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend.store.repo import IntakeItem, Store
from tests.test_api_routes import (  # noqa: F401  (pytest fixtures)
    SHA,
    _hit_ids,
    _post,
    _search,
    _seed,
    _services,
    api,
    fetched,
)


def _content(file_id: int, queue_id: int = 1) -> IntakeItem:
    return IntakeItem(
        queue_id=queue_id,
        kind="content",
        file_id=file_id,
        storage_id=3,
        etag="etag-1",
        size=2200,
        mtime=1_700_000_000,
        prefilter_key=None,
        reader_uid="ana",
    )


def _orphaned_at(store: Store, media_id: int) -> object:
    return store.reading_connection().execute("SELECT orphaned_at FROM media WHERE media_id = ?", (media_id,)).fetchone()[0]


def test_intake_before_the_sample_still_gives_the_sample_hit(api: TestClient) -> None:
    store, _index = _services(api)
    store.apply_intake([_content(52)])

    answer = _seed(api, 52)

    assert answer["result"] == "published"
    assert _hit_ids(api) == [52]
    ref = store.file_ref(52)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id) == ("active", "pending", None)


def test_sample_before_the_intake_keeps_the_sample_hit(api: TestClient) -> None:
    store, _index = _services(api)
    _seed(api, 51)
    _seed(api, 53)  # same bytes as 51: stale, but linked to the same content
    media_id = store.media_for_file_sha256(SHA)

    store.apply_intake([_content(51), _content(53, queue_id=2)])

    assert sorted(_hit_ids(api)) == [51, 53]  # type: ignore[type-var]
    assert _orphaned_at(store, media_id) is None
    for file_id in (51, 53):
        ref = store.file_ref(file_id)
        assert ref is not None
        assert (ref.state, ref.stage, ref.media_id, ref.storage_id) == ("active", "pending", None, 3)


def test_both_orders_end_in_the_same_hits(api: TestClient) -> None:
    store, _index = _services(api)
    store.apply_intake([_content(61)])
    _seed(api, 61)
    _seed(api, 62)
    store.apply_intake([_content(62, queue_id=2)])

    assert sorted(_hit_ids(api)) == [61, 62]  # type: ignore[type-var]
    first, second = store.file_ref(61), store.file_ref(62)
    assert first is not None and second is not None
    assert (first.state, first.stage) == (second.state, second.stage) == ("active", "pending")


def test_the_sample_hit_carries_the_debug_mark(api: TestClient) -> None:
    store, _index = _services(api)
    store.apply_intake([_content(52)])
    _seed(api, 52)

    hits = _search(api, "Audiosuche")["hits"]

    assert [h["sample"] for h in hits] == [True]  # type: ignore[union-attr]


def test_removing_the_sample_leaves_the_reference_of_the_discovery(api: TestClient) -> None:
    store, _index = _services(api)
    store.apply_intake([_content(52)])
    before = store.file_ref(52)
    _seed(api, 52)

    response = _post(api, "/sample/remove", {"fileId": 52})

    assert response.json()["result"] == "removed"
    assert store.file_ref(52) == before
    assert _hit_ids(api) == []


def test_the_intake_never_writes_the_sample_layer(api: TestClient) -> None:
    store, _index = _services(api)
    _seed(api, 51)
    media_id = store.media_for_file_sha256(SHA)

    store.apply_intake([_content(51)])

    assert store.sample_media(51) == media_id


def test_a_sample_on_a_reference_that_gives_no_hit_stays_hidden(api: TestClient) -> None:
    store, _index = _services(api)
    _seed(api, 51)
    store.upsert_file_ref(
        51, None, storage_id=3, etag="e", size=1, mtime=1, state="unreadable", stage="failed", reason="read_denied"
    )

    assert _hit_ids(api) == []


@pytest.fixture
def plain(tmp_path: Path) -> Iterator[Store]:
    store = Store.open(tmp_path / "state.db")
    yield store
    store.close()


def test_the_file_ref_states_no_longer_know_sample(plain: Store) -> None:
    with pytest.raises(ValueError, match="state"):
        plain.upsert_file_ref(1, None, storage_id=0, etag="", size=0, mtime=0, state="sample", stage="keyed", reason=None)
