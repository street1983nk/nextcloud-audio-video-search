"""The intake of the PHP work stock (plan 02-05).

A row of oc_avs_queue becomes a reference in state.db in one transaction and is
acknowledged only after it: a container that dies before the ack gets the row
again once the 900 s lock of PHP ran out, and writing it again ends in the
same state. Kinds this plan does not handle yet go back unlocked, never lost.
"""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from audio_video_search_backend import nc, nc_queue
from audio_video_search_backend.nc_queue import ClaimAnswer, ClaimItem, QueueClient
from audio_video_search_backend.store.repo import IntakeItem, Store

TOKEN = "0123456789abcdef0123456789abcdef"  # noqa: S105 - a claim token of the test, not a secret
PREFILTER = "a" * 64
OTHER_PREFILTER = "b" * 64
SHA_A = "1" * 64
SHA_B = "2" * 64


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    opened = Store.open(tmp_path / "state.db")
    yield opened
    opened.close()


def item(queue_id: int = 1, kind: str = "content", file_id: int = 10, **fields: Any) -> IntakeItem:
    values: dict[str, Any] = {
        "storage_id": 3,
        "etag": "etag-1",
        "size": 1000,
        "mtime": 1_700_000_000,
        "prefilter_key": None,
        "reader_uid": "ana",
    }
    values.update(fields)
    return IntakeItem(queue_id=queue_id, kind=kind, file_id=file_id, **values)


def wire(queue_id: int = 1, kind: str = "content", file_id: int | None = 10, **fields: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "queueId": queue_id,
        "kind": kind,
        "fileId": file_id,
        "storageId": 3,
        "etag": "etag-1",
        "size": 1000,
        "mtime": 1_700_000_000,
        "prefilterKey": None,
        "readerUid": "ana",
    }
    values.update(fields)
    return values


def keyed(store: Store, file_id: int, sha256: str) -> int:
    """Give a reference a media item, as the capture of plan 08 will."""
    media_id = store.media_for_file_sha256(sha256)
    ref = store.file_ref(file_id)
    assert ref is not None
    store.upsert_file_ref(
        file_id,
        media_id,
        storage_id=ref.storage_id,
        etag=ref.etag,
        size=ref.size,
        mtime=ref.mtime,
        state="active",
        stage="keyed",
        reason=None,
        prefilter_key=ref.prefilter_key,
        reader_uid=ref.reader_uid,
        proved_at=1,
    )
    return media_id


def orphaned_at(store: Store, media_id: int) -> object:
    return store._conn.execute("SELECT orphaned_at FROM media WHERE media_id = ?", (media_id,)).fetchone()[0]


# -- apply_intake ---------------------------------------------------------------------


def test_a_new_file_becomes_an_active_pending_reference(store: Store) -> None:
    assert store.apply_intake([item(prefilter_key=PREFILTER)]) == [1]

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.attempts, ref.media_id) == ("active", "pending", 0, None)
    assert (ref.storage_id, ref.etag, ref.size, ref.mtime) == (3, "etag-1", 1000, 1_700_000_000)
    assert (ref.prefilter_key, ref.reader_uid) == (PREFILTER, "ana")


def test_unchanged_content_with_a_media_item_stays_keyed(store: Store) -> None:
    store.apply_intake([item()])
    media_id = keyed(store, 10, SHA_A)
    before = store.file_ref(10)

    assert store.apply_intake([item(queue_id=2)]) == [2]

    after = store.file_ref(10)
    assert before is not None
    assert after is not None
    assert (after.state, after.stage, after.media_id, after.proved_at) == ("active", "keyed", media_id, 1)
    assert (after.etag, after.size, after.mtime) == (before.etag, before.size, before.mtime)


@pytest.mark.parametrize(
    "change", [{"etag": "etag-2"}, {"size": 1001}, {"mtime": 1_700_000_001}], ids=["etag", "size", "mtime"]
)
def test_any_difference_makes_the_content_unknown_and_orphans_the_old_media(
    store: Store, change: dict[str, Any]
) -> None:
    store.apply_intake([item()])
    media_id = keyed(store, 10, SHA_A)

    assert store.apply_intake([item(queue_id=2, **change)]) == [2]

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id, ref.attempts, ref.proved_at) == ("active", "pending", None, 0, None)
    assert orphaned_at(store, media_id) is not None


def test_the_old_media_is_not_orphaned_while_another_active_copy_points_at_it(store: Store) -> None:
    store.apply_intake([item(), item(queue_id=2, file_id=11)])
    media_id = keyed(store, 10, SHA_A)
    assert keyed(store, 11, SHA_A) == media_id

    store.apply_intake([item(queue_id=3, etag="etag-2")])

    assert orphaned_at(store, media_id) is None
    assert store.file_ids_for_media(media_id) == [11]


def test_metadata_changes_only_the_prefilter_key_and_the_reader(store: Store) -> None:
    store.apply_intake([item(prefilter_key=PREFILTER)])
    media_id = keyed(store, 10, SHA_A)

    applied = store.apply_intake(
        [item(queue_id=2, kind="metadata", etag="etag-9", size=5, prefilter_key=OTHER_PREFILTER, reader_uid="ben")]
    )

    assert applied == [2]
    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.prefilter_key, ref.reader_uid) == (OTHER_PREFILTER, "ben")
    assert (ref.etag, ref.size, ref.stage, ref.media_id) == ("etag-1", 1000, "keyed", media_id)


def test_kinds_this_plan_does_not_handle_are_neither_written_nor_returned(store: Store) -> None:
    rows = [item(queue_id=i, kind=kind, file_id=20 + i) for i, kind in enumerate(nc_queue.KINDS, start=1)]

    applied = store.apply_intake(rows)

    assert applied == [6, 7]
    assert store.file_ref(21) is None  # exclude_storage
    assert store.file_ref(23) is None  # delete
    assert store.file_ref(26) is not None


def test_writing_the_same_band_twice_ends_in_the_same_state(store: Store) -> None:
    band = [item(), item(queue_id=2, file_id=11, prefilter_key=PREFILTER)]
    store.apply_intake(band)
    first = [store.file_ref(10), store.file_ref(11)]

    store.apply_intake(band)

    second = [store.file_ref(10), store.file_ref(11)]
    assert None not in first + second
    assert [replace(ref, updated_at=0) for ref in first if ref] == [replace(ref, updated_at=0) for ref in second if ref]


def test_an_invalid_row_rolls_back_the_whole_band(store: Store) -> None:
    with pytest.raises(ValueError, match="prefilter_key"):
        store.apply_intake([item(), item(queue_id=2, file_id=11, prefilter_key="not-hex")])

    assert store.file_ref(10) is None


def test_a_sample_reference_becomes_a_real_one_on_its_first_content_row(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA_B)
    store.upsert_file_ref(
        10, media_id, storage_id=0, etag="", size=1000, mtime=0, state="sample", stage="keyed", reason="sample"
    )

    store.apply_intake([item()])

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id, ref.storage_id) == ("active", "pending", None, 3)


# -- the contract of the claim answer ------------------------------------------------


def answer(*items: dict[str, Any], **stats: Any) -> dict[str, Any]:
    return {"claimToken": TOKEN, "items": list(items), "stats": {"ok": True, "open": {"content": 0}} | stats}


def test_a_claim_answer_with_the_nine_keys_is_accepted() -> None:
    delete = wire(queue_id=2, kind="delete", etag=None, size=None, mtime=None)
    parsed = ClaimAnswer.model_validate(answer(wire(), delete))

    assert [entry.queueId for entry in parsed.items] == [1, 2]
    assert set(ClaimItem.model_fields) == {
        "queueId",
        "kind",
        "fileId",
        "storageId",
        "etag",
        "size",
        "mtime",
        "prefilterKey",
        "readerUid",
    }


@pytest.mark.parametrize(
    "broken",
    [
        wire(path="/ana/files/x.webm"),
        wire(kind="ocr"),
        wire(size=True),
        wire(fileId=0),
        wire(prefilterKey="A" * 64),
        wire(readerUid="x" * 65),
        wire(etag="e" * 65),
        wire(etag=None),
        {key: value for key, value in wire().items() if key != "readerUid"},
    ],
    ids=["path", "kind", "bool size", "file id 0", "upper hex", "long uid", "long etag", "content no etag", "8 keys"],
)
def test_an_answer_outside_the_contract_is_refused(broken: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ClaimAnswer.model_validate(answer(wire(queue_id=5), broken))


def test_an_empty_php_array_of_open_kinds_is_no_error() -> None:
    parsed = ClaimAnswer.model_validate({"claimToken": TOKEN, "items": [], "stats": {"ok": False, "open": []}})

    assert parsed.stats.open == {}
    assert parsed.stats.ok is False


def test_the_queue_timeouts_are_connect_10_and_read_30() -> None:
    assert nc.QUEUE_TIMEOUT.connect == 10.0
    assert nc.QUEUE_TIMEOUT.read == 30.0


def transport(answers: dict[str, Any], seen: list[tuple[str, Any]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        action = request.url.path.rsplit("/", 1)[-1]
        seen.append((action, request.read()))
        assert request.headers["EX-APP-ID"]
        return httpx.Response(200, json={"ocs": {"meta": {"status": "ok"}, "data": answers[action]}})

    return httpx.MockTransport(handler)


async def test_a_claim_with_a_path_field_is_dropped_whole_and_counted() -> None:
    seen: list[tuple[str, Any]] = []
    answers = {"claim": answer(wire(), wire(queue_id=2, path="/secret.webm"))}
    async with httpx.AsyncClient(transport=transport(answers, seen)) as client:
        outcome = await QueueClient(client).claim(10)

    assert outcome.answer is None
    assert (outcome.reachable, outcome.malformed) == (True, 2)
    assert [action for action, _ in seen] == ["claim"]


async def test_ack_and_unlock_send_bands_of_at_most_256_ids() -> None:
    seen: list[tuple[str, Any]] = []
    answers = {"ack": {"acknowledged": 1}, "unlock": {"unlocked": 1}}
    async with httpx.AsyncClient(transport=transport(answers, seen)) as client:
        queue = QueueClient(client)
        assert await queue.ack(TOKEN, list(range(1, 300)))
        assert await queue.unlock(TOKEN, [7])

    assert [action for action, _ in seen] == ["ack", "ack", "unlock"]


async def test_an_unreachable_queue_is_a_result_not_an_exception() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as client:
        queue = QueueClient(client)
        outcome = await queue.claim(10)
        acked = await queue.ack(TOKEN, [1])

    assert (outcome.answer, outcome.reachable, outcome.malformed) == (None, False, 0)
    assert acked is False
