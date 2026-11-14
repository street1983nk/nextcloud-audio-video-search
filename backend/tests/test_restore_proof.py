"""The read proof after a restore from the trash (plan 02-15b, D-02-01a second addendum, D-02-12).

A reference that comes back from the trash on a storage whose rights
Nextcloud cannot judge (SMB, SFTP: the row or the reference carries a
prefilter key) gives no hit until its OWN read proof passed, and that proof
is claimed before ordinary work. "No hit" is measured where hits are made:
api/search.py asks ``Store.file_ids_for_media`` for the files of a content.

The stage is the one of test_read_proof.py (a real state.db, a fake gateway,
a fake head route, a clock); the index is a real one.
"""

import hashlib
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from audio_video_search_backend import nc
from audio_video_search_backend.api import Services
from audio_video_search_backend.api import search as search_api
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.store.repo import IntakeItem, Store
from audio_video_search_backend.worker import read_proof
from audio_video_search_backend.worker.capture import CaptureOutcome
from tests.test_read_proof import KIB, NOW, PREFILTER, STORAGE_ANA, STORAGE_BEN, STORAGE_CEM, Stage

MODEL = "d" * 64
MTIME = 1_700_000_000


def _data(seed: bytes = b"restore", size: int = 200 * KIB) -> bytes:
    block = hashlib.sha256(seed).digest()
    return (block * (size // len(block) + 1))[:size]


DATA = _data()
OTHER = _data(b"other bytes")
SMALL = _data(b"ordinary", 50 * KIB)


@pytest.fixture(autouse=True)
def plenty_of_space(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nc, "free_bytes", lambda _directory: 1024**4)


@pytest.fixture
def search_index(tmp_path: Path) -> Iterator[SearchIndex]:
    from tests.test_index_open import CONSTITUENTS

    opened = SearchIndex.open(tmp_path / "idx", constituents=CONSTITUENTS)
    try:
        yield opened
    finally:
        opened.close()


class Scene:
    """A stage with a transcript in a real index, so that hits are asked from the search itself."""

    def __init__(self, stage: Stage, index: SearchIndex) -> None:
        self.stage = stage
        self.store = stage.store
        self.index = index

    def transcribe(self, media_id: int, data: bytes) -> None:
        prov = Provenance(
            engine="parakeet",
            model_sha256=MODEL,
            config_version=1,
            profile="balanced",
            level=Level.PREVIEW,
            epoch=0,
            language="de",
            input_file_sha256=hashlib.sha256(data).hexdigest(),
        )
        words = [Word(i * 400, i * 400 + 350, w, w.lower(), 0.9, "machine") for i, w in enumerate(["Der", "Haushalt"])]
        assert self.store.publish_version(media_id, prov, words).published
        self.index.reconcile(self.store)

    def found(self) -> list[int]:
        """The file ids POST /search hands to PHP for the word of the transcript."""
        hits, _more = search_api._search(Services(store=self.store, index=self.index), "Haushalt", 0, 50)
        return sorted(cast("int", hit["fileId"]) for hit in hits)

    async def single(self, prefilter: str | None = PREFILTER) -> int:
        """File 10 of ana, read in full, the only reference of its content."""
        self.stage.put(10, DATA)
        self.stage.intake(10, len(DATA), reader="ana", storage=STORAGE_ANA, prefilter=prefilter)
        step = await self.stage.step()
        assert step.outcome == CaptureOutcome.KEYED
        assert step.media_id is not None
        self.transcribe(step.media_id, DATA)
        assert self.found() == [10]
        return step.media_id

    async def shared(self) -> int:
        """File 10 of ana and file 12 of cem at one content; cem attached by his own proof."""
        media_id = await self.single()
        await self.attach(12, "cem", STORAGE_CEM, media_id)
        assert self.found() == [10, 12]
        return media_id

    async def attach(self, file_id: int, reader: str, storage: int, media_id: int) -> None:
        self.stage.put(file_id, DATA)
        self.stage.intake(file_id, len(DATA), reader=reader, storage=storage)
        step = await self.stage.step()
        assert (step.outcome, step.file_id, step.media_id) == (CaptureOutcome.KEYED, file_id, media_id)

    def trash(self, file_id: int, storage: int = STORAGE_CEM) -> None:
        row = IntakeItem(
            queue_id=1000 + file_id,
            kind="trash",
            file_id=file_id,
            storage_id=storage,
            etag=None,
            size=None,
            mtime=None,
            prefilter_key=None,
            reader_uid=None,
        )
        assert self.store.apply_intake([row]) == [1000 + file_id]

    def restore(
        self,
        file_id: int,
        *,
        reader: str = "cem",
        storage: int = STORAGE_CEM,
        prefilter: str | None = PREFILTER,
        kind: str = "restore",
    ) -> None:
        row = IntakeItem(
            queue_id=2000 + file_id,
            kind=kind,
            file_id=file_id,
            storage_id=storage,
            etag="e1",
            size=len(DATA),
            mtime=MTIME,
            prefilter_key=prefilter,
            reader_uid=reader,
        )
        assert self.store.apply_intake([row]) == [2000 + file_id]

    def ordinary(self, file_id: int, storage: int = STORAGE_BEN) -> None:
        """An ordinary download that waits: a new file without a prefilter key."""
        self.stage.put(file_id, SMALL)
        self.stage.intake(file_id, len(SMALL), reader="ben", storage=storage, prefilter=None)

    def orphaned_at(self, media_id: int) -> int | None:
        row = (
            self.store.reading_connection()
            .execute("SELECT orphaned_at FROM media WHERE media_id = ?", (media_id,))
            .fetchone()
        )
        return None if row[0] is None else int(row[0])

    def shape(self, file_id: int) -> tuple[str, str, int | None, str | None, int, int | None]:
        ref = self.stage.ref(file_id)
        return (ref.state, ref.stage, ref.media_id, ref.reason, ref.attempts, ref.next_try_at)


@pytest.fixture
def scene(store: Store, tmp_path: Path, search_index: SearchIndex) -> Scene:
    directory = tmp_path / "tmp"
    directory.mkdir()
    return Scene(Stage(store, directory), search_index)


# No hit before the proof.


@pytest.mark.parametrize("kind", ["restore", "content"])
async def test_a_restored_reference_on_external_storage_gives_no_hit_before_its_proof(scene: Scene, kind: str) -> None:
    media_id = await scene.shared()
    scene.trash(12)
    assert scene.found() == [10]

    scene.restore(12, kind=kind)

    # Back from the trash, but the search does not name it: its proof is due and not made yet.
    assert scene.found() == [10]
    assert scene.shape(12) == ("unreadable", "probing", media_id, None, 0, None)
    assert scene.stage.hits(media_id) == [10]


async def test_the_last_reference_restored_leaves_its_content_marked_and_unfound_until_the_proof(scene: Scene) -> None:
    media_id = await scene.single()
    scene.trash(10, STORAGE_ANA)
    marked = scene.orphaned_at(media_id)
    assert marked is not None

    scene.restore(10, reader="ana", storage=STORAGE_ANA)

    assert scene.found() == []
    assert scene.shape(10) == ("unreadable", "probing", media_id, None, 0, None)
    assert scene.orphaned_at(media_id) == marked


async def test_a_passed_proof_brings_the_hits_back_without_a_download(scene: Scene) -> None:
    media_id = await scene.single()
    scene.trash(10, STORAGE_ANA)
    scene.restore(10, reader="ana", storage=STORAGE_ANA)
    scene.stage.clock.now += 30
    downloads = list(scene.stage.fetch.calls)
    heads = list(scene.stage.head.calls)

    step = await scene.stage.step()

    assert (step.outcome, step.file_id, step.media_id) == (CaptureOutcome.KEYED, 10, media_id)
    assert scene.found() == [10]
    assert scene.shape(10) == ("active", "keyed", media_id, None, 0, None)
    assert scene.stage.ref(10).proved_at == NOW + 30
    assert scene.orphaned_at(media_id) is None
    # Proved through its own file id and its own reader, and nothing was read in full.
    assert scene.stage.head.calls == [*heads, (10, "ana")]
    assert scene.stage.fetch.calls == downloads


@pytest.mark.parametrize(
    ("error", "reason", "wait", "attempts"),
    [
        (nc.READ_DENIED, nc.READ_DENIED, 60, 1),
        (nc.READ_TIMEOUT, nc.READ_TIMEOUT, 60, 1),
        (nc.ACCESS_CONTROL, nc.ACCESS_CONTROL, 300, 1),
        (nc.GATEWAY_FAILED, nc.GATEWAY_FAILED, 60, 1),
        (nc.LOCKED, nc.LOCKED, 120, 0),
    ],
)
async def test_a_failed_proof_after_a_restore_follows_the_rules_of_the_renewed_proof_and_gives_no_hit(
    scene: Scene, error: str, reason: str, wait: int, attempts: int
) -> None:
    media_id = await scene.shared()
    scene.trash(12)
    scene.restore(12)
    # The server keeps the file from cem since it lay in the trash.
    scene.stage.head.failing(12, error)

    step = await scene.stage.step()

    assert (step.outcome, step.file_id, step.reason) == (CaptureOutcome.UNREADABLE, 12, reason)
    assert scene.shape(12) == ("unreadable", "failed", media_id, reason, attempts, NOW + wait)
    assert scene.found() == [10]

    # The right comes back: the next try is a proof again, and only it gives the hits back.
    scene.stage.clock.now += wait
    assert (await scene.stage.step()).outcome == CaptureOutcome.KEYED
    assert scene.found() == [10, 12]
    assert scene.stage.fetch.calls == [10]


async def test_other_bytes_after_a_restore_let_go_of_the_content_and_never_show_the_old_transcript(
    scene: Scene,
) -> None:
    media_id = await scene.shared()
    scene.trash(12)
    scene.restore(12)
    scene.stage.put(12, OTHER)

    step = await scene.stage.step()

    assert (step.outcome, step.file_id) == (CaptureOutcome.KEYED, 12)
    own = scene.stage.ref(12).media_id
    assert own is not None
    assert own != media_id
    assert scene.stage.fetch.calls == [10, 12]
    assert scene.found() == [10]
    assert scene.stage.hits(own) == [12]


async def test_other_bytes_after_a_restore_give_no_hit_while_the_download_waits(scene: Scene) -> None:
    media_id = await scene.shared()
    scene.trash(12)
    scene.restore(12)
    scene.stage.head.contents[12] = OTHER
    scene.stage.fetch.failing(12, nc.DISK_FULL)

    step = await scene.stage.step()

    assert (step.outcome, step.reason) == (CaptureOutcome.DEFERRED, nc.DISK_FULL)
    assert scene.stage.ref(12).media_id is None
    assert scene.found() == [10]
    assert scene.stage.hits(media_id) == [10]


# The proof of a restored reference comes first.


async def test_the_proof_of_a_restored_reference_is_claimed_before_a_download_with_a_smaller_file_id(
    scene: Scene,
) -> None:
    media_id = await scene.shared()
    scene.trash(12)
    scene.ordinary(5)
    scene.ordinary(6)
    scene.restore(12)

    first = await scene.stage.step()

    assert (first.outcome, first.file_id, first.media_id) == (CaptureOutcome.KEYED, 12, media_id)
    assert scene.stage.fetch.calls == [10]
    assert scene.found() == [10, 12]
    # The ordinary work follows in its usual order.
    assert [(await scene.stage.step()).file_id for _ in range(2)] == [5, 6]
    assert scene.stage.fetch.calls == [10, 5, 6]


async def test_the_store_hands_out_the_restored_reference_first(scene: Scene) -> None:
    await scene.shared()
    scene.ordinary(5)
    scene.trash(12)
    scene.restore(12)

    claimed = scene.store.next_capture(NOW)

    assert claimed is not None
    assert (claimed.file_id, claimed.state, claimed.stage) == (12, "unreadable", "fetching")


# Coming first must not starve ordinary work.


async def test_many_restores_on_a_storage_that_hangs_cost_three_requests_and_then_let_ordinary_work_run(
    scene: Scene,
) -> None:
    media_id = await scene.single()
    restored = [21, 22, 23, 24, 25, 26]
    for file_id in restored:
        await scene.attach(file_id, "ben", STORAGE_BEN, media_id)
    for file_id in restored:
        scene.trash(file_id, STORAGE_BEN)
    scene.ordinary(5, STORAGE_CEM)
    for file_id in restored:
        scene.restore(file_id, reader="ben", storage=STORAGE_BEN)
        scene.stage.head.failing(file_id, nc.READ_TIMEOUT)
    heads = len(scene.stage.head.calls)

    steps = [await scene.stage.step() for _ in range(7)]

    assert [step.file_id for step in steps] == [*restored, 5]
    assert [step.reason for step in steps[:6]] == [nc.READ_TIMEOUT] * 3 + [read_proof.STORAGE_PAUSED] * 3
    assert steps[6].outcome == CaptureOutcome.KEYED
    # Three requests went to the storage that hangs, not one more.
    assert len(scene.stage.head.calls) == heads + 3
    assert scene.found() == [10]
    assert all(scene.stage.ref(file_id).stage == "failed" for file_id in restored)

    # Their next tries are ordinary retries: a new download goes before them.
    scene.stage.clock.now += 60
    scene.ordinary(7, STORAGE_CEM)
    step = await scene.stage.step()
    assert (step.file_id, step.outcome) == (7, CaptureOutcome.KEYED)


async def test_a_restored_reference_comes_first_only_once(scene: Scene) -> None:
    await scene.shared()
    scene.trash(12)
    scene.restore(12)
    scene.stage.head.failing(12, nc.READ_DENIED, times=2)
    assert (await scene.stage.step()).file_id == 12
    scene.stage.clock.now += 60
    scene.ordinary(30)

    step = await scene.stage.step()

    # Its retry is due, but it waits behind the new download like every retry.
    assert (step.file_id, step.outcome) == (30, CaptureOutcome.KEYED)
    assert (await scene.stage.step()).file_id == 12


async def test_a_renewed_proof_of_an_active_reference_does_not_come_first(scene: Scene) -> None:
    media_id = await scene.shared()
    # What the reconcile of plan 20 leaves behind: active, gives hits, proof due again.
    scene.stage.renew(12, media_id, len(DATA))
    scene.ordinary(5)

    step = await scene.stage.step()

    assert step.file_id == 5


# The same state however often the restore arrives.


async def test_a_restore_delivered_twice_ends_in_the_same_state_before_and_after_the_proof(scene: Scene) -> None:
    media_id = await scene.shared()
    scene.trash(12)
    scene.restore(12)
    first = scene.stage.ref(12)

    scene.restore(12)

    assert replace(scene.stage.ref(12), updated_at=0) == replace(first, updated_at=0)
    assert scene.found() == [10]

    assert (await scene.stage.step()).outcome == CaptureOutcome.KEYED
    proved = scene.stage.ref(12)
    scene.restore(12)

    # The late copy of the row does not take the proof away again.
    assert replace(scene.stage.ref(12), updated_at=0) == replace(proved, updated_at=0)
    assert scene.shape(12) == ("active", "keyed", media_id, None, 0, None)
    assert scene.found() == [10, 12]


@pytest.mark.parametrize("prefilter", [PREFILTER, None], ids=["key", "no-key"])
async def test_trash_and_restore_twice_never_make_a_missing_proof_valid(scene: Scene, prefilter: str | None) -> None:
    media_id = await scene.shared()
    scene.trash(12)
    scene.restore(12)
    assert scene.shape(12)[:2] == ("unreadable", "probing")

    # Into the trash and back once more before the proof ran.
    scene.trash(12)
    scene.restore(12, prefilter=prefilter)

    assert scene.shape(12)[:3] == ("unreadable", "probing", media_id)
    assert scene.found() == [10]


@pytest.mark.parametrize("prefilter", [PREFILTER, None], ids=["key", "no-key"])
async def test_a_proof_that_failed_before_the_trash_stays_invalid_through_any_number_of_restores(
    scene: Scene, prefilter: str | None
) -> None:
    media_id = await scene.shared()
    scene.stage.renew(12, media_id, len(DATA))
    scene.stage.head.failing(12, nc.READ_DENIED)
    assert (await scene.stage.step()).outcome == CaptureOutcome.UNREADABLE
    assert scene.found() == [10]

    for _ in range(2):
        scene.trash(12)
        scene.restore(12, prefilter=prefilter)

        assert scene.shape(12)[:3] == ("unreadable", "probing", media_id)
        assert scene.found() == [10]


# Storages without a duty to prove.


async def test_a_restore_without_a_prefilter_key_is_active_at_once_as_before(scene: Scene) -> None:
    media_id = await scene.single(prefilter=None)
    scene.trash(10, STORAGE_ANA)
    heads = list(scene.stage.head.calls)

    scene.restore(10, reader="ana", storage=STORAGE_ANA, prefilter=None)

    assert scene.shape(10) == ("active", "keyed", media_id, None, 0, None)
    assert scene.found() == [10]
    assert scene.orphaned_at(media_id) is None
    # Nothing for the capture: no proof and no download.
    assert (await scene.stage.step()).outcome == CaptureOutcome.IDLE
    assert scene.stage.head.calls == heads


async def test_a_reference_that_had_a_prefilter_key_needs_its_proof_even_if_the_row_has_none(scene: Scene) -> None:
    media_id = await scene.single()
    scene.trash(10, STORAGE_ANA)

    # PHP sends no key, for instance while the classification of the storage is missing.
    scene.restore(10, reader="ana", storage=STORAGE_ANA, prefilter=None)

    assert scene.shape(10) == ("unreadable", "probing", media_id, None, 0, None)
    assert scene.found() == []
    assert (await scene.stage.step()).outcome == CaptureOutcome.KEYED
    assert scene.found() == [10]


# The trash while the proof that came first is running.


async def test_the_trash_during_the_running_proof_makes_its_result_stale(scene: Scene) -> None:
    media_id = await scene.shared()
    scene.trash(12)
    scene.restore(12)
    scene.ordinary(5)
    real = scene.stage.head

    async def head(file_id: int, user_id: str) -> nc.HeadResult:
        # The file goes into the trash while its head is read; the read itself succeeds.
        scene.trash(file_id)
        return await real(file_id, user_id)

    scene.stage.capture._head = head

    step = await scene.stage.step()

    assert (step.outcome, step.file_id) == (CaptureOutcome.STALE, 12)
    assert scene.shape(12)[:3] == ("trashed", "pending", media_id)
    assert scene.found() == [10]

    # Restored again: the proof that was cut off counts for nothing, and it comes first again.
    scene.stage.capture._head = real
    scene.restore(12)
    assert scene.shape(12)[:2] == ("unreadable", "probing")
    assert scene.found() == [10]

    step = await scene.stage.step()

    assert (step.outcome, step.file_id) == (CaptureOutcome.KEYED, 12)
    assert scene.found() == [10, 12]
