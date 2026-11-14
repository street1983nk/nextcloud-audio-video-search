"""The intake of the PHP work stock (plan 02-05).

A row of oc_avs_queue becomes a reference in state.db in one transaction and is
acknowledged only after it: a container that dies before the ack gets the row
again once the 900 s lock of PHP ran out, and writing it again ends in the
same state.

Plan 02-15 writes every kind: an exclusion removes references and forgets a
content with its last one, a deleted file only marks it orphaned, the trash
sets a reference aside, and a restore brings it back without a download. No
kind goes back unlocked any more.
"""

import logging
import sqlite3
from collections.abc import Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast, get_args

import httpx
import pytest
from pydantic import ValidationError

from audio_video_search_backend import companion, nc, nc_queue
from audio_video_search_backend.api import Services
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.nc_queue import ClaimAnswer, ClaimItem, QueueClient
from audio_video_search_backend.store import coverage as cov
from audio_video_search_backend.store import repo
from audio_video_search_backend.store.repo import IntakeItem, Store
from audio_video_search_backend.worker.intake import Intake

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
        "origin": "crawl",
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


def test_every_kind_of_the_queue_is_written_and_returned(store: Store) -> None:
    rows = [item(queue_id=i, kind=kind, file_id=20 + i) for i, kind in enumerate(nc_queue.KINDS, start=1)]

    applied = store.apply_intake(rows)

    assert frozenset(nc_queue.KINDS) == repo.INTAKE_KINDS
    assert applied == [1, 2, 3, 4, 5, 6, 7]
    assert store.file_ref(21) is None  # exclude_storage
    assert store.file_ref(23) is None  # delete
    assert store.file_ref(24) is None  # trash of a file never seen
    assert store.file_ref(25) is not None  # restore of a file never seen: taken in like content
    assert store.file_ref(26) is not None


def test_a_kind_outside_the_list_is_neither_written_nor_returned(store: Store) -> None:
    assert store.apply_intake([item(kind="ocr"), item(queue_id=2, file_id=11)]) == [2]
    assert store.file_ref(10) is None


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


def test_a_file_with_a_sample_gets_a_real_reference_on_its_first_content_row(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA_B)
    store.put_sample(10, media_id)

    store.apply_intake([item()])

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id, ref.storage_id) == ("active", "pending", None, 3)


# -- the contract of the claim answer ------------------------------------------------


def answer(*items: dict[str, Any], **stats: Any) -> dict[str, Any]:
    return {"claimToken": TOKEN, "items": list(items), "stats": {"ok": True, "open": {"content": 0}} | stats}


def test_a_claim_answer_with_the_ten_keys_is_accepted() -> None:
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
        "origin",
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
        wire(origin="push"),
        wire(origin=None),
        wire(origin=1),
        {key: value for key, value in wire().items() if key != "origin"},
    ],
    ids=[
        "path",
        "kind",
        "bool size",
        "file id 0",
        "upper hex",
        "long uid",
        "long etag",
        "content no etag",
        "no reader key",
        "unknown origin",
        "null origin",
        "number origin",
        "no origin key",
    ],
)
def test_an_answer_outside_the_contract_is_refused(broken: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ClaimAnswer.model_validate(answer(wire(queue_id=5), broken))


@pytest.mark.parametrize("origin", ["event", "crawl"])
def test_the_origin_of_the_claim_reaches_the_intake_item(origin: str) -> None:
    parsed = ClaimAnswer.model_validate(answer(wire(origin=origin)))

    assert parsed.items[0].origin == origin
    assert parsed.items[0].to_intake().origin == origin


def test_the_container_knows_the_same_two_origins_as_the_store() -> None:
    assert nc_queue.ORIGINS == repo.ORIGINS == frozenset({"event", "crawl"})
    # The field type of the claim allows exactly the values of the list.
    assert frozenset(get_args(nc_queue.Origin.__value__)) == nc_queue.ORIGINS


async def test_a_claim_with_an_unknown_origin_is_dropped_whole_and_counted() -> None:
    """Today's rule for every row outside the contract: the whole band goes, the valid row with it."""
    seen: list[tuple[str, Any]] = []
    answers = {"claim": answer(wire(origin="event"), wire(queue_id=2, file_id=11, origin="push"))}
    async with httpx.AsyncClient(transport=transport(answers, seen)) as client:
        outcome = await QueueClient(client).claim(10)

    assert outcome.answer is None
    assert (outcome.reachable, outcome.malformed) == (True, 2)
    assert [action for action, _ in seen] == ["claim"]


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


# -- the intake round: commit first, ack second -------------------------------------


class FakeQueue(QueueClient):
    """Hands out prepared bands and records every ack and unlock."""

    def __init__(self, *bands: dict[str, Any] | None) -> None:
        self.bands = list(bands)
        self.claims = 0
        self.acks: list[list[int]] = []
        self.unlocks: list[list[int]] = []
        self.ack_crashes = 0

    async def claim(self, limit: int) -> nc_queue.ClaimOutcome:
        self.claims += 1
        data = self.bands.pop(0) if self.bands else answer()
        if data is None:
            return nc_queue.ClaimOutcome(answer=None, reachable=False, malformed=0)
        return nc_queue.ClaimOutcome(answer=ClaimAnswer.model_validate(data), reachable=True, malformed=0)

    async def ack(self, token: str, queue_ids: Sequence[int]) -> bool:
        if self.ack_crashes:
            self.ack_crashes -= 1
            raise RuntimeError("the container died before the ack")
        self.acks.append(list(queue_ids))
        return True

    async def unlock(self, token: str, queue_ids: Sequence[int]) -> bool:
        self.unlocks.append(list(queue_ids))
        return True


@pytest.fixture
def companion_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(companion, "current", lambda: companion.CompanionState(companion.OK, "0.2.0", 0.0))


def services_of(store: Store) -> Services:
    return Services(store=store, index=cast("SearchIndex", None))


def bare(queue_id: int, kind: str, file_id: int | None = 10, **fields: Any) -> dict[str, Any]:
    """A row of a kind that describes no file version: PHP sends etag, size and mtime as null."""
    return wire(queue_id=queue_id, kind=kind, file_id=file_id, etag=None, size=None, mtime=None, **fields)


async def test_every_kind_is_acknowledged_and_none_is_unlocked(store: Store) -> None:
    band = answer(
        bare(1, "exclude_storage", None, storageId=9),
        bare(2, "exclude", 30),
        bare(3, "delete", 31),
        bare(4, "trash", 32),
        wire(queue_id=5, kind="restore", file_id=33),
        wire(queue_id=6),
        wire(queue_id=7, kind="metadata", file_id=34),
    )
    queue = FakeQueue(band)

    result = await Intake(services_of(store), queue).run_once()

    assert queue.acks == [[1, 2, 3, 4, 5, 6, 7]]
    assert queue.unlocks == []
    assert (result.claimed, result.applied, result.acked, result.unlocked) == (7, 7, 7, 0)
    assert store.file_ref(10) is not None


@pytest.mark.parametrize("origin", ["event", "crawl"])
async def test_the_origin_of_the_claim_lands_in_the_reference(store: Store, origin: str) -> None:
    queue = FakeQueue(answer(wire(origin=origin)))

    result = await Intake(services_of(store), queue).run_once()

    assert queue.acks == [[1]]
    assert result.applied == 1
    assert store.file_ref(10) is not None
    assert store._conn.execute("SELECT origin FROM file_ref WHERE file_id = 10").fetchone()[0] == origin


async def test_a_failed_commit_acknowledges_nothing_and_unlocks_the_band(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_items: object) -> list[int]:
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(store, "apply_intake", broken)
    queue = FakeQueue(answer(wire(), wire(queue_id=2, file_id=11)))

    result = await Intake(services_of(store), queue).run_once()

    assert queue.acks == []
    assert queue.unlocks == [[1, 2]]
    assert (result.applied, result.acked, result.unlocked) == (0, 0, 2)


async def test_a_crash_between_commit_and_ack_ends_in_the_same_state(store: Store) -> None:
    band = answer(wire(prefilterKey=PREFILTER), wire(queue_id=2, file_id=11))
    queue = FakeQueue(band, band)
    queue.ack_crashes = 1
    intake = Intake(services_of(store), queue)

    with pytest.raises(RuntimeError):
        await intake.run_once()
    first = [store.file_ref(10), store.file_ref(11)]
    await intake.run_once()
    second = [store.file_ref(10), store.file_ref(11)]

    assert queue.acks == [[1, 2]]
    assert None not in first + second
    assert [replace(ref, updated_at=0) for ref in first if ref] == [replace(ref, updated_at=0) for ref in second if ref]


async def test_an_unreadable_queue_writes_nothing(store: Store) -> None:
    queue = FakeQueue(answer(wire(), ok=False))

    result = await Intake(services_of(store), queue).run_once()

    assert result.queue_ok is False
    assert result.applied == 0
    assert queue.acks == []
    assert queue.unlocks == [[1]]
    assert store.file_ref(10) is None


async def test_a_band_outside_the_contract_is_neither_written_nor_acknowledged(store: Store) -> None:
    class Malformed(FakeQueue):
        async def claim(self, limit: int) -> nc_queue.ClaimOutcome:
            return nc_queue.ClaimOutcome(answer=None, reachable=True, malformed=3)

    queue = Malformed()

    result = await Intake(services_of(store), queue).run_once()

    assert (result.malformed, result.applied, result.queue_ok) == (3, 0, False)
    assert queue.acks == []
    assert queue.unlocks == []


@pytest.mark.usefixtures("companion_ok")
async def test_a_full_written_band_is_followed_by_the_next_claim_at_once(store: Store) -> None:
    queue = FakeQueue(answer(wire(), wire(queue_id=2, file_id=11)), answer())
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    await Intake(services_of(store), queue, batch=2).run_forever(sleep=sleep, rounds=2)

    assert queue.claims == 2
    assert sleeps == [30.0]


@pytest.mark.usefixtures("companion_ok")
async def test_a_full_band_of_deletes_is_written_and_followed_by_the_next_claim(store: Store) -> None:
    queue = FakeQueue(answer(bare(1, "delete", 10), bare(2, "delete", 11)), answer(bare(3, "trash", 12)))
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    await Intake(services_of(store), queue, batch=2).run_forever(sleep=sleep, rounds=2)

    assert queue.claims == 2
    assert sleeps == [30.0]
    assert queue.acks == [[1, 2], [3]]
    assert queue.unlocks == []


async def test_no_claim_before_the_php_app_answered(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(companion, "current", lambda: companion.CompanionState(companion.UNKNOWN, None, None))
    queue = FakeQueue(answer(wire()))
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    await Intake(services_of(store), queue).run_forever(sleep=sleep, rounds=2)

    assert queue.claims == 0
    assert sleeps == [30.0, 30.0]


@pytest.mark.usefixtures("companion_ok")
async def test_a_failing_round_does_not_end_the_loop(store: Store) -> None:
    class Exploding(FakeQueue):
        async def claim(self, limit: int) -> nc_queue.ClaimOutcome:
            self.claims += 1
            raise RuntimeError("boom")

    queue = Exploding()
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    await Intake(services_of(store), queue).run_forever(sleep=sleep, rounds=2)

    assert queue.claims == 2
    assert sleeps == [30.0, 30.0]


# -- plan 02-15: exclusion, deletion, trash and restore --------------------------------

NOW = 1_800_000_000
MODEL = "c" * 64


def transcribed(store: Store, media_id: int, sha256: str) -> None:
    """A transcript and a correction by hand at the content."""
    prov = Provenance(
        engine="parakeet",
        model_sha256=MODEL,
        config_version=1,
        profile="balanced",
        level=Level.PREVIEW,
        epoch=0,
        language="de",
        input_file_sha256=sha256,
    )
    words = [Word(i * 400, i * 400 + 350, w, w.lower(), 0.9, "machine") for i, w in enumerate(["Der", "Haushalt"])]
    assert store.publish_version(media_id, prov, words).published
    store.add_correction(
        media_id, 400, 750, "text", "Haushaltsplan", author_uid="ana", base_version_id=None, base_text=None
    )


def known(store: Store, media_id: int) -> tuple[int, int, int]:
    """(media rows, transcripts, corrections) of a content."""
    conn = store.reading_connection()
    return (
        int(conn.execute("SELECT COUNT(*) FROM media WHERE media_id = ?", (media_id,)).fetchone()[0]),
        int(conn.execute("SELECT COUNT(*) FROM transcript WHERE media_id = ?", (media_id,)).fetchone()[0]),
        int(conn.execute("SELECT COUNT(*) FROM correction WHERE media_id = ?", (media_id,)).fetchone()[0]),
    )


def two_copies(store: Store, **fields: Any) -> int:
    """Files 10 and 11 keyed at one content with a transcript and a correction."""
    store.apply_intake([item(**fields), item(queue_id=2, file_id=11, **fields)])
    media_id = keyed(store, 10, SHA_A)
    assert keyed(store, 11, SHA_A) == media_id
    transcribed(store, media_id, SHA_A)
    return media_id


def one_copy(store: Store, **fields: Any) -> int:
    store.apply_intake([item(**fields)])
    media_id = keyed(store, 10, SHA_A)
    transcribed(store, media_id, SHA_A)
    return media_id


def gone(queue_id: int, kind: str, file_id: int | None = 10, storage_id: int = 3) -> IntakeItem:
    """A row the way PHP sends an exclusion, a deletion or the trash: no etag, size or mtime."""
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


def counted(store: Store) -> tuple[int, int, int]:
    found = cov.coverage(store.reading_connection(), NOW)
    return found.contents, found.transcribed, found.files


def test_an_exclusion_removes_the_reference_and_forgets_with_the_last_one(store: Store) -> None:
    media_id = two_copies(store)

    assert store.apply_intake([gone(5, "exclude", 10)]) == [5]

    assert store.file_ref(10) is None
    assert store.file_ids_for_media(media_id) == [11]
    assert known(store, media_id) == (1, 1, 1)

    assert store.apply_intake([gone(6, "exclude", 11)]) == [6]

    assert known(store, media_id) == (0, 0, 0)
    assert store.retired_media() == [media_id]


def test_an_excluded_storage_loses_every_reference_on_it(store: Store) -> None:
    store.apply_intake([item(storage_id=7), item(queue_id=2, file_id=11, storage_id=7), item(queue_id=3, file_id=12)])
    media_id = keyed(store, 10, SHA_A)
    transcribed(store, media_id, SHA_A)
    other = keyed(store, 12, SHA_B)

    assert store.apply_intake([gone(5, "exclude_storage", None, storage_id=7)]) == [5]

    assert (store.file_ref(10), store.file_ref(11)) == (None, None)
    assert known(store, media_id) == (0, 0, 0)
    assert store.file_ids_for_media(other) == [12]


def test_a_deleted_file_only_marks_its_content(store: Store) -> None:
    media_id = one_copy(store)

    assert store.apply_intake([gone(5, "delete")]) == [5]

    assert store.file_ref(10) is None
    assert known(store, media_id) == (1, 1, 1)
    assert orphaned_at(store, media_id) is not None
    assert store.file_ids_for_media(media_id) == []
    assert counted(store) == (0, 0, 0)
    assert store.retired_media() == []


def test_the_trash_sets_the_reference_aside_and_marks_the_content(store: Store) -> None:
    media_id = one_copy(store)

    assert store.apply_intake([gone(5, "trash")]) == [5]

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id) == ("trashed", "keyed", media_id)
    assert orphaned_at(store, media_id) is not None
    assert known(store, media_id) == (1, 1, 1)
    # Not findable, not counted, never fetched.
    assert store.file_ids_for_media(media_id) == []
    assert counted(store) == (0, 0, 0)
    assert store.next_capture(NOW) is None


def test_the_trash_does_not_mark_a_content_another_active_copy_holds(store: Store) -> None:
    media_id = two_copies(store)

    store.apply_intake([gone(5, "trash", 10)])

    assert orphaned_at(store, media_id) is None
    assert store.file_ids_for_media(media_id) == [11]
    assert counted(store) == (1, 1, 1)


def test_the_trash_of_a_file_never_seen_is_written_as_nothing(store: Store) -> None:
    assert store.apply_intake([gone(5, "trash", 99)]) == [5]
    assert store.file_ref(99) is None


@pytest.mark.parametrize("kind", ["restore", "content"])
def test_a_restore_with_the_same_values_is_active_again_without_a_download(store: Store, kind: str) -> None:
    media_id = one_copy(store)
    store.apply_intake([gone(5, "trash")])

    assert store.apply_intake([item(queue_id=6, kind=kind)]) == [6]

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id, ref.proved_at) == ("active", "keyed", media_id, 1)
    assert (ref.reason, ref.attempts, ref.next_try_at) == (None, 0, None)
    assert orphaned_at(store, media_id) is None
    assert store.file_ids_for_media(media_id) == [10]
    assert known(store, media_id) == (1, 1, 1)
    assert counted(store) == (1, 1, 1)
    # Nothing for the capture: no download and, without a prefilter key, no proof.
    assert store.next_capture(NOW) is None


@pytest.mark.parametrize("kind", ["restore", "content"])
def test_a_restore_on_smb_or_sftp_asks_for_the_read_proof_again(store: Store, kind: str) -> None:
    media_id = one_copy(store, prefilter_key=PREFILTER)
    store.apply_intake([gone(5, "trash")])

    store.apply_intake([item(queue_id=6, kind=kind, prefilter_key=PREFILTER)])

    ref = store.file_ref(10)
    assert ref is not None
    # No hit before its own proof passed (plan 02-15b): unreadable, and the content keeps its mark.
    assert (ref.state, ref.stage, ref.media_id, ref.next_try_at) == ("unreadable", "probing", media_id, None)
    assert (ref.reason, ref.attempts) == (None, 0)
    assert orphaned_at(store, media_id) is not None
    assert store.file_ids_for_media(media_id) == []
    # Due at once, and as a proof: the reference still hangs at its content.
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert (claimed.file_id, claimed.media_id) == (10, media_id)


def test_a_restore_takes_the_prefilter_key_of_its_own_row(store: Store) -> None:
    # The storage was classified as SMB while the file lay in the trash.
    media_id = one_copy(store)
    store.apply_intake([gone(5, "trash")])

    store.apply_intake([item(queue_id=6, kind="restore", prefilter_key=PREFILTER, reader_uid="ben")])

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.stage, ref.prefilter_key, ref.reader_uid, ref.media_id) == ("probing", PREFILTER, "ben", media_id)


@pytest.mark.parametrize("kind", ["restore", "content"])
@pytest.mark.parametrize(
    "change", [{"etag": "etag-2"}, {"size": 1001}, {"mtime": 1_700_000_001}], ids=["etag", "size", "mtime"]
)
def test_a_restore_with_other_values_is_a_new_version(store: Store, kind: str, change: dict[str, Any]) -> None:
    media_id = one_copy(store)
    store.apply_intake([gone(5, "trash")])
    marked = orphaned_at(store, media_id)

    store.apply_intake([item(queue_id=6, kind=kind, **change)])

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id, ref.proved_at) == ("active", "pending", None, None)
    # The old content keeps its mark and everything known of it (D-02-13).
    assert marked is not None
    assert orphaned_at(store, media_id) == marked
    assert known(store, media_id) == (1, 1, 1)
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert (claimed.file_id, claimed.media_id) == (10, None)


def test_a_restore_with_other_values_leaves_a_content_another_copy_holds_unmarked(store: Store) -> None:
    media_id = two_copies(store)
    store.apply_intake([gone(5, "trash", 10)])

    store.apply_intake([item(queue_id=6, kind="restore", etag="etag-2")])

    assert orphaned_at(store, media_id) is None
    assert store.file_ids_for_media(media_id) == [11]


def test_a_restore_of_a_file_never_seen_is_taken_in_like_content(store: Store) -> None:
    assert store.apply_intake([item(queue_id=6, kind="restore", prefilter_key=PREFILTER)]) == [6]

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id, ref.prefilter_key) == ("active", "pending", None, PREFILTER)


def test_a_restore_of_a_reference_that_is_not_in_the_trash_changes_no_stage(store: Store) -> None:
    media_id = one_copy(store, prefilter_key=PREFILTER)

    store.apply_intake([item(queue_id=6, kind="restore", prefilter_key=PREFILTER)])

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id, ref.proved_at) == ("active", "keyed", media_id, 1)


def test_a_restore_delivered_twice_ends_in_the_same_state(store: Store) -> None:
    one_copy(store, prefilter_key=PREFILTER)
    band = [gone(5, "trash"), item(queue_id=6, kind="restore", prefilter_key=PREFILTER)]
    store.apply_intake(band)
    first = store.file_ref(10)

    store.apply_intake([band[1]])

    second = store.file_ref(10)
    assert first is not None
    assert second is not None
    assert replace(first, updated_at=0) == replace(second, updated_at=0)


def test_a_restore_without_a_content_starts_the_capture_anew(store: Store) -> None:
    store.apply_intake([item()])
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert store.mark_failed(claimed, "read_denied", retry_at=NOW + 3600, now=NOW)
    store.apply_intake([gone(5, "trash")])

    store.apply_intake([item(queue_id=6, kind="restore")])

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id) == ("active", "pending", None)
    assert (ref.reason, ref.attempts, ref.next_try_at) == (None, 0, None)


def test_a_restore_never_gives_hits_to_a_reference_whose_last_proof_failed(store: Store) -> None:
    media_id = one_copy(store, prefilter_key=PREFILTER)
    store.reading_connection().execute("UPDATE file_ref SET stage = 'probing' WHERE file_id = 10")
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert store.fail_proof(claimed, "read_denied", retry_at=NOW + 3600, now=NOW)
    assert store.file_ids_for_media(media_id) == []
    store.apply_intake([gone(5, "trash")])

    store.apply_intake([item(queue_id=6, kind="restore", prefilter_key=PREFILTER)])

    ref = store.file_ref(10)
    assert ref is not None
    # Back from the trash, but unreadable until its own proof says ok; the proof is due at once.
    assert (ref.state, ref.stage, ref.media_id, ref.next_try_at, ref.attempts) == (
        "unreadable",
        "probing",
        media_id,
        None,
        0,
    )
    assert store.file_ids_for_media(media_id) == []
    assert orphaned_at(store, media_id) is not None
    again = store.next_capture(NOW)
    assert again is not None
    assert (again.file_id, again.media_id) == (10, media_id)


def test_the_trash_takes_the_claim_of_a_running_download(store: Store) -> None:
    store.apply_intake([item()])
    claimed = store.next_capture(NOW)
    assert claimed is not None

    store.apply_intake([gone(5, "trash")])

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage) == ("trashed", "pending")
    # The download that was running comes back stale and writes nothing.
    assert store.mark_keyed(claimed, SHA_A, SHA_B, NOW) is None
    after = store.file_ref(10)
    assert after is not None
    assert (after.state, after.stage, after.media_id) == ("trashed", "pending", None)


def test_trash_and_restore_in_one_band_end_active(store: Store) -> None:
    media_id = one_copy(store)

    assert store.apply_intake([gone(5, "trash"), item(queue_id=6, kind="restore")]) == [5, 6]

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id) == ("active", "keyed", media_id)
    assert orphaned_at(store, media_id) is None


def test_metadata_for_a_reference_in_the_trash_leaves_it_there(store: Store) -> None:
    one_copy(store)
    store.apply_intake([gone(5, "trash")])

    store.apply_intake([item(queue_id=6, kind="metadata", prefilter_key=PREFILTER)])

    ref = store.file_ref(10)
    assert ref is not None
    assert (ref.state, ref.stage, ref.prefilter_key) == ("trashed", "keyed", PREFILTER)


@pytest.mark.parametrize("kind", ["exclude", "delete", "trash"])
def test_a_row_about_a_file_without_a_file_id_rolls_back_the_band(store: Store, kind: str) -> None:
    with pytest.raises(ValueError, match="file_id"):
        store.apply_intake([item(), gone(5, kind, None)])

    assert store.file_ref(10) is None


def test_a_mixed_band_is_one_transaction(store: Store) -> None:
    store.apply_intake(
        [
            item(queue_id=1, file_id=20, storage_id=9),
            item(queue_id=2, file_id=21),
            item(queue_id=3, file_id=22),
            item(queue_id=4, file_id=23),
            item(queue_id=5, file_id=24),
        ]
    )
    excluded = keyed(store, 21, SHA_A)
    transcribed(store, excluded, SHA_A)
    keyed(store, 24, SHA_B)
    store.apply_intake([gone(6, "trash", 24)])
    statements: list[str] = []
    conn = store.reading_connection()
    conn.set_trace_callback(statements.append)

    applied = store.apply_intake(
        [
            gone(11, "exclude_storage", None, storage_id=9),
            gone(12, "exclude", 21),
            gone(13, "delete", 22),
            gone(14, "trash", 23),
            item(queue_id=15, kind="restore", file_id=24),
            item(queue_id=16, file_id=25),
            item(queue_id=17, kind="metadata", file_id=25, reader_uid="ben"),
        ]
    )

    conn.set_trace_callback(None)
    assert applied == [11, 12, 13, 14, 15, 16, 17]
    assert [s for s in statements if s.startswith(("BEGIN", "COMMIT", "ROLLBACK"))] == ["BEGIN IMMEDIATE", "COMMIT"]
    assert [store.file_ref(f) for f in (20, 21, 22)] == [None, None, None]
    assert known(store, excluded) == (0, 0, 0)
    states = {f: ref.state for f in (23, 24, 25) if (ref := store.file_ref(f)) is not None}
    assert states == {23: "trashed", 24: "active", 25: "active"}
    restored = store.file_ref(25)
    assert restored is not None
    assert restored.reader_uid == "ben"


def test_a_failure_late_in_the_band_takes_back_the_exclusion_before_it(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_id = two_copies(store)
    monkeypatch.setattr(repo, "_INTAKE_TRASH", "UPDATE no_such_table SET state = 'trashed' WHERE file_id = :file_id")

    with pytest.raises(sqlite3.OperationalError):
        store.apply_intake([gone(5, "exclude", 10), gone(6, "exclude", 11), gone(7, "trash", 12)])

    assert store.file_ids_for_media(media_id) == [10, 11]
    assert known(store, media_id) == (1, 1, 1)
    assert store.retired_media() == []


def test_the_intake_never_touches_a_sample(store: Store) -> None:
    media_id = one_copy(store)
    store.put_sample(10, media_id)
    store.put_sample(11, media_id)

    store.apply_intake([gone(5, "trash")])
    store.apply_intake([item(queue_id=6, kind="restore")])
    store.apply_intake([gone(7, "delete")])

    assert (store.sample_media(10), store.sample_media(11)) == (media_id, media_id)


def test_the_log_of_a_band_carries_counts_only(store: Store, caplog: pytest.LogCaptureFixture) -> None:
    two_copies(store)
    store.apply_intake([item(queue_id=3, file_id=12), item(queue_id=4, file_id=13)])
    keyed(store, 12, SHA_B)
    keyed(store, 13, SHA_B)
    caplog.set_level(logging.INFO, logger=repo.__name__)

    store.apply_intake([gone(5, "exclude", 10), gone(6, "exclude", 11), gone(7, "delete", 12), gone(8, "trash", 13)])

    lines = {r.getMessage(): r.__dict__ for r in caplog.records if r.name == repo.__name__}
    written = lines["intake written"]
    assert (written["removed"], written["forgotten"], written["trashed"], written["orphaned"]) == (3, 1, 1, 1)
    assert (written["items"], written["applied"]) == (4, 4)
    assert (lines["media forgotten"]["media"], lines["media forgotten"]["cause"]) == (1, "exclude")
    assert (lines["media orphaned"]["media"], lines["media orphaned"]["cause"]) == (1, "trash")


# -- the round with every kind ----------------------------------------------------------


@pytest.fixture
def search_index(tmp_path: Path) -> Iterator[SearchIndex]:
    from tests.test_index_open import CONSTITUENTS

    opened = SearchIndex.open(tmp_path / "idx", constituents=CONSTITUENTS)
    try:
        yield opened
    finally:
        opened.close()


async def test_an_exclusion_takes_the_documents_out_of_the_index_before_the_ack(
    store: Store, search_index: SearchIndex
) -> None:
    media_id = one_copy(store)
    search_index.reconcile(store)
    assert [h.media_id for h in search_index.search("Haushaltsplan", 10)] == [media_id]
    seen: list[int] = []

    class Watching(FakeQueue):
        async def ack(self, token: str, queue_ids: Sequence[int]) -> bool:
            seen.append(len(search_index.search("Haushaltsplan", 10)))
            return await super().ack(token, queue_ids)

    queue = Watching(answer(bare(5, "exclude", 10)))

    result = await Intake(Services(store=store, index=search_index), queue).run_once()

    assert seen == [0]
    assert queue.acks == [[5]]
    assert (result.applied, result.acked, result.retired) == (1, 1, 1)
    assert store.pending_index_work() == []


async def test_a_deletion_leaves_the_index_alone(store: Store, search_index: SearchIndex) -> None:
    media_id = one_copy(store)
    search_index.reconcile(store)

    result = await Intake(
        Services(store=store, index=search_index), FakeQueue(answer(bare(5, "delete", 10)))
    ).run_once()

    assert result.retired == 0
    assert [h.media_id for h in search_index.search("Haushaltsplan", 10)] == [media_id]
    assert store.file_ids_for_media(media_id) == []


async def test_an_index_that_fails_keeps_the_mark_and_the_next_round_retires(
    store: Store, search_index: SearchIndex, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_id = one_copy(store)
    store.apply_intake([item(queue_id=2, file_id=11)])
    search_index.reconcile(store)
    queue = FakeQueue(answer(bare(5, "exclude", 10)), answer(bare(6, "delete", 11)))
    intake = Intake(Services(store=store, index=search_index), queue)
    real = search_index.retire_forgotten

    def broken(_store: Store) -> int:
        raise OSError("index directory not writable")

    monkeypatch.setattr(search_index, "retire_forgotten", broken)
    first = await intake.run_once()

    # SQLite is the truth and it is committed: the row is acknowledged, the mark waits.
    assert (first.applied, first.acked, first.retired) == (1, 1, 0)
    assert queue.acks == [[5]]
    assert store.retired_media() == [media_id]
    assert store.current(media_id) is None

    monkeypatch.setattr(search_index, "retire_forgotten", real)
    second = await intake.run_once()

    assert second.retired == 1
    assert store.retired_media() == []
    assert search_index.search("Haushaltsplan", 10) == []
