"""The sweep of the reconcile and the planning of the renewed read proof (plan 02-20).

The sweep runs in front of the walk and under a stamp of its own, also while
the walk is held back (Findling 1.6.3, issue #25): two due ticks with a
blocked walk are two sweeps and no walk. A mount list that is not ok, empty
or outside the contract deletes nothing and writes no stamp (T-02-74).

- gone: the references go, their contents are only marked (D-02-13);
- deselected: vanished, they neither count nor give hits; after 30 days
  they go with cause vanished_expired;
- back in the list: a keyed reference on a storage without a duty to prove
  is active again without a download; on SMB and SFTP (groupable) it owes a
  read proof first and gives no hit until that proof passed (D-02-12, as
  after the trash, deferred items 02-15b);
- every active keyed reference on a groupable storage whose proof is older
  than seven days is due for a proof again; --reprove makes it due now.

The PHP routes are a fake here (FakeFiles); the contract of their answers is
tested against nc.reconcile_request at the end.
"""

import logging
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, cast

import pytest

from audio_video_search_backend import nc, nc_files
from audio_video_search_backend.api import Services
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.nc_files import (
    Classification,
    FileClient,
    MountEntry,
    MountList,
    RequeueAnswer,
    Slice,
    SliceFile,
)
from audio_video_search_backend.store.repo import Store
from audio_video_search_backend.worker import reconcile as reconcile_module
from audio_video_search_backend.worker.reconcile import Reconciler, ReconcileResult

DAY = 86_400
NOW = 1_800_000_000
SHA_A = "1" * 64
SHA_B = "2" * 64
SHA_C = "3" * 64
LOCAL = 3
SMB = 4
GONE = 8
LEFT = 9
OTHER = 7
SECRET_FILE_ID = 424_242


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    opened = Store.open(tmp_path / "state.db")
    yield opened
    opened.close()


def services(store: Store) -> Services:
    return Services(store=store, index=cast("SearchIndex", None))


def mount(storage_id: int, *, root: int | None = None, finished: bool = True, groupable: bool = False) -> MountEntry:
    return MountEntry(
        storageId=storage_id,
        rootId=root if root is not None else storage_id * 100,
        crawlFinished=finished,
        capturable=True,
        external=groupable,
        groupable=groupable,
    )


class FakeFiles:
    """The four PHP routes of plan 02-19, played from memory."""

    def __init__(
        self,
        mounts: MountList | None,
        *,
        classification: Classification | None = None,
        files: dict[tuple[int, int], list[SliceFile]] | None = None,
    ) -> None:
        self.listing = mounts
        self.classification = classification or Classification(gone=[], deselected=[], present=[])
        self.files = files or {}
        self.classified: list[list[int]] = []
        self.sliced: list[tuple[int, int, int]] = []
        self.requeued: list[list[int]] = []

    async def mounts(self) -> MountList | None:
        return self.listing

    async def classify(self, storage_ids: Sequence[int]) -> Classification | None:
        self.classified.append(list(storage_ids))
        return self.classification

    async def slice(self, storage_id: int, root_id: int, after: int, limit: int) -> Slice | None:
        self.sliced.append((storage_id, root_id, after))
        rows = [row for row in self.files.get((storage_id, root_id), []) if row.fileId > after][:limit]
        return Slice(files=rows, next=rows[-1].fileId if len(rows) == limit else None)

    async def requeue(self, file_ids: Sequence[int]) -> RequeueAnswer | None:
        self.requeued.append(list(file_ids))
        return RequeueAnswer(enqueued=len(file_ids), rejected=0)


class Clock:
    def __init__(self, at: int = NOW) -> None:
        self.at = at

    def __call__(self) -> float:
        return float(self.at)


def reconciler(store: Store, files: FakeFiles, clock: Clock, *, queue_ok: bool | None = True) -> Reconciler:
    return Reconciler(
        services(store),
        files,
        clock=clock,
        hour_of=lambda: reconcile_module.PREFERRED_HOUR,
        queue_ok=lambda: queue_ok,
    )


def ref(
    store: Store,
    file_id: int,
    storage_id: int,
    *,
    sha: str | None = None,
    stage: str = "keyed",
    state: str = "active",
    proved_at: int | None = NOW - DAY,
) -> int | None:
    media_id = store.media_for_file_sha256(sha) if sha is not None else None
    store.upsert_file_ref(
        file_id,
        media_id,
        storage_id=storage_id,
        etag=f"etag-{file_id}",
        size=1000 + file_id,
        mtime=1_700_000_000 + file_id,
        state=state,
        stage=stage if media_id is not None else "pending",
        reason=None,
        reader_uid="ana",
        proved_at=proved_at if media_id is not None else None,
    )
    return media_id


def row(store: Store, file_id: int) -> tuple[Any, ...] | None:
    found = store.file_ref(file_id)
    return None if found is None else (found.state, found.stage, found.vanished_since)


def orphaned_at(store: Store, media_id: int | None) -> object:
    found = store._conn.execute("SELECT orphaned_at FROM media WHERE media_id = ?", (media_id,)).fetchone()
    return None if found is None else found[0]


def media_exists(store: Store, media_id: int | None) -> bool:
    return store._conn.execute("SELECT 1 FROM media WHERE media_id = ?", (media_id,)).fetchone() is not None


# -- the stamp of the sweep and the blocked walk ---------------------------------------


async def test_a_blocked_walk_still_sweeps_on_every_due_tick(store: Store) -> None:
    ref(store, 10, LOCAL, sha=SHA_A)
    ref(store, 20, LEFT, sha=SHA_B)
    files = FakeFiles(
        MountList(ok=True, mounts=[mount(LOCAL, finished=False)]),
        classification=Classification(gone=[], deselected=[], present=[LEFT]),
    )
    clock = Clock()
    rounds = reconciler(store, files, clock)

    first = await rounds.run_once()
    clock.at += DAY + 3600
    second = await rounds.run_once()

    assert files.classified == [[LEFT], [LEFT]]
    assert files.sliced == []
    assert store.meta_value("storage_sweep_at") == str(NOW + DAY + 3600)
    assert store.meta_value("walk_at") is None
    assert first.skipped_reason == second.skipped_reason == "crawl_unfinished"
    assert first.walked_mounts == second.walked_mounts == 0


async def test_a_sweep_is_not_due_again_within_a_day(store: Store) -> None:
    ref(store, 10, LOCAL, sha=SHA_A)
    files = FakeFiles(MountList(ok=True, mounts=[mount(LOCAL, finished=False)]))
    clock = Clock()
    rounds = reconciler(store, files, clock)

    await rounds.run_once()
    clock.at += 3600
    await rounds.run_once()

    assert store.meta_value("storage_sweep_at") == str(NOW)


async def test_a_storage_that_leaves_the_list_is_swept_at_the_next_tick(store: Store) -> None:
    ref(store, 10, LOCAL, sha=SHA_A)
    ref(store, 20, LEFT, sha=SHA_B)
    files = FakeFiles(MountList(ok=True, mounts=[mount(LOCAL, finished=False), mount(LEFT, finished=False)]))
    clock = Clock()
    rounds = reconciler(store, files, clock)
    await rounds.run_once()
    files.listing = MountList(ok=True, mounts=[mount(LOCAL, finished=False)])
    files.classification = Classification(gone=[], deselected=[LEFT], present=[])
    clock.at += 300

    result = await rounds.run_once()

    assert files.classified == [[LEFT]]
    assert result.vanished == 1
    assert row(store, 20) == ("vanished", "keyed", NOW + 300)


@pytest.mark.parametrize(
    ("listing", "reason"),
    [
        (MountList(ok=False, mounts=[]), "mounts_unavailable"),
        (MountList(ok=True, mounts=[]), "mounts_empty"),
        (None, "mounts_unavailable"),
    ],
)
async def test_a_disturbed_mount_list_deletes_nothing_and_writes_no_stamp(
    store: Store, listing: MountList | None, reason: str
) -> None:
    media_id = ref(store, 20, GONE, sha=SHA_B)
    ref(store, 30, SMB, sha=SHA_C, proved_at=NOW - 30 * DAY)
    files = FakeFiles(listing, classification=Classification(gone=[GONE], deselected=[], present=[]))

    result = await reconciler(store, files, Clock()).run_once(reprove=True)

    assert files.classified == []
    assert files.sliced == []
    assert row(store, 20) == ("active", "keyed", None)
    assert row(store, 30) == ("active", "keyed", None)
    assert orphaned_at(store, media_id) is None
    assert store.meta_value("storage_sweep_at") is None
    assert store.meta_value("walk_at") is None
    assert result == ReconcileResult(
        swept=0, vanished=0, orphaned=0, walked_mounts=0, requeued=0, rejected=0, reproof_due=0, skipped_reason=reason
    )


async def test_an_unanswered_classification_deletes_nothing_and_writes_no_stamp(store: Store) -> None:
    ref(store, 20, GONE, sha=SHA_B)
    files = FakeFiles(MountList(ok=True, mounts=[mount(LOCAL, finished=False)]))

    async def unanswered(_ids: Sequence[int]) -> Classification | None:
        return None

    files.classify = unanswered  # type: ignore[method-assign]
    result = await reconciler(store, files, Clock()).run_once()

    assert row(store, 20) == ("active", "keyed", None)
    assert store.meta_value("storage_sweep_at") is None
    assert result.skipped_reason == "classify_unavailable"


# -- gone, deselected, back ----------------------------------------------------------


async def test_a_gone_storage_loses_its_references_and_its_content_is_only_marked(store: Store) -> None:
    media_id = ref(store, 20, GONE, sha=SHA_B)
    ref(store, 21, GONE)
    files = FakeFiles(
        MountList(ok=True, mounts=[mount(LOCAL, finished=False)]),
        classification=Classification(gone=[GONE], deselected=[], present=[]),
    )

    result = await reconciler(store, files, Clock()).run_once()

    assert store.file_ref(20) is None
    assert store.file_ref(21) is None
    assert media_exists(store, media_id)
    assert orphaned_at(store, media_id) is not None
    assert (result.swept, result.orphaned) == (2, 1)
    assert store.meta_value("storage_sweep_at") == str(NOW)


async def test_a_listed_storage_is_never_classified_or_swept(store: Store) -> None:
    ref(store, 10, LOCAL, sha=SHA_A)
    files = FakeFiles(
        MountList(ok=True, mounts=[mount(LOCAL, finished=False)]),
        classification=Classification(gone=[LOCAL], deselected=[], present=[]),
    )

    await reconciler(store, files, Clock()).run_once()

    assert files.classified == []
    assert row(store, 10) == ("active", "keyed", None)


async def test_a_deselected_storage_vanishes_and_goes_after_thirty_days(store: Store) -> None:
    media_id = ref(store, 20, LEFT, sha=SHA_B)
    files = FakeFiles(
        MountList(ok=True, mounts=[mount(LOCAL, finished=False)]),
        classification=Classification(gone=[], deselected=[LEFT], present=[]),
    )
    clock = Clock()
    rounds = reconciler(store, files, clock)

    first = await rounds.run_once()
    assert row(store, 20) == ("vanished", "keyed", NOW)
    assert first.vanished == 1
    assert orphaned_at(store, media_id) is not None

    clock.at = NOW + 29 * DAY
    await rounds.run_once()
    assert row(store, 20) == ("vanished", "keyed", NOW)

    clock.at = NOW + 31 * DAY
    last = await rounds.run_once()
    assert store.file_ref(20) is None
    assert media_exists(store, media_id)
    assert last.swept == 1


async def test_a_vanished_reference_neither_counts_nor_is_fetched(store: Store) -> None:
    from audio_video_search_backend.store import coverage

    ref(store, 20, LEFT, sha=SHA_B)
    ref(store, 21, LEFT)
    files = FakeFiles(
        MountList(ok=True, mounts=[mount(LOCAL, finished=False)]),
        classification=Classification(gone=[], deselected=[LEFT], present=[]),
    )

    await reconciler(store, files, Clock()).run_once()

    counts = coverage.coverage(store.reading_connection())
    assert counts.files == 0
    assert store.next_capture() is None


async def test_a_storage_back_in_the_list_comes_back_without_a_download(store: Store) -> None:
    local_media = ref(store, 10, LOCAL, sha=SHA_A)
    smb_media = ref(store, 30, SMB, sha=SHA_C)
    ref(store, 31, SMB)
    files = FakeFiles(
        MountList(ok=True, mounts=[mount(OTHER, finished=False)]),
        classification=Classification(gone=[], deselected=[LOCAL, SMB], present=[]),
    )
    clock = Clock()
    rounds = reconciler(store, files, clock)
    await rounds.run_once()
    assert row(store, 10) == ("vanished", "keyed", NOW)

    files.listing = MountList(
        ok=True, mounts=[mount(LOCAL, finished=False), mount(SMB, finished=False, groupable=True)]
    )
    clock.at += 600
    await rounds.run_once()

    assert row(store, 10) == ("active", "keyed", None)
    assert orphaned_at(store, local_media) is None
    # SMB and SFTP: no hit until the renewed proof passed, and that proof comes first.
    assert row(store, 30) == ("unreadable", "probing", None)
    assert orphaned_at(store, smb_media) is not None
    assert row(store, 31) == ("active", "pending", None)
    claimed = store.next_capture()
    assert claimed is not None
    assert claimed.file_id == 30


# -- the renewed read proof (D-02-12) ------------------------------------------------


async def test_a_proof_older_than_seven_days_on_a_groupable_storage_is_due_again(store: Store) -> None:
    ref(store, 30, SMB, sha=SHA_A, proved_at=NOW - 8 * DAY)
    ref(store, 31, SMB, sha=SHA_B, proved_at=NOW - 6 * DAY)
    ref(store, 10, LOCAL, sha=SHA_C, proved_at=NOW - 8 * DAY)
    files = FakeFiles(
        MountList(ok=True, mounts=[mount(LOCAL, finished=False), mount(SMB, groupable=True, finished=False)])
    )

    result = await reconciler(store, files, Clock()).run_once()

    assert row(store, 30) == ("active", "probing", None)
    assert row(store, 31) == ("active", "keyed", None)
    assert row(store, 10) == ("active", "keyed", None)
    assert result.reproof_due == 1


async def test_the_proof_planning_runs_on_every_tick(store: Store) -> None:
    ref(store, 31, SMB, sha=SHA_B, proved_at=NOW - 6 * DAY)
    files = FakeFiles(MountList(ok=True, mounts=[mount(SMB, groupable=True, finished=False)]))
    clock = Clock()
    rounds = reconciler(store, files, clock)
    await rounds.run_once()
    assert row(store, 31) == ("active", "keyed", None)

    clock.at += 2 * DAY
    await rounds.run_once()

    assert row(store, 31) == ("active", "probing", None)


async def test_reprove_makes_every_active_groupable_reference_due_at_once(store: Store) -> None:
    ref(store, 30, SMB, sha=SHA_A, proved_at=NOW - 60)
    ref(store, 31, SMB, sha=SHA_B, proved_at=NOW - 6 * DAY)
    ref(store, 32, SMB, sha=SHA_C, state="unreadable", stage="failed")
    ref(store, 10, LOCAL, sha=SHA_C, proved_at=NOW - 60)
    files = FakeFiles(
        MountList(ok=True, mounts=[mount(LOCAL, finished=False), mount(SMB, groupable=True, finished=False)])
    )

    result = await reconciler(store, files, Clock()).run_once(reprove=True)

    assert row(store, 30) == ("active", "probing", None)
    assert row(store, 31) == ("active", "probing", None)
    assert row(store, 32) == ("unreadable", "failed", None)
    assert row(store, 10) == ("active", "keyed", None)
    assert result.reproof_due == 2


# -- logs ------------------------------------------------------------------------------


async def test_the_log_carries_counters_and_storage_ids_only(store: Store, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    ref(store, SECRET_FILE_ID, GONE, sha=SHA_B)
    ref(store, 20, LEFT, sha=SHA_A)
    files = FakeFiles(
        MountList(ok=True, mounts=[mount(LOCAL, finished=False)]),
        classification=Classification(gone=[GONE], deselected=[LEFT], present=[]),
    )

    await reconciler(store, files, Clock()).run_once()

    lines = [record for record in caplog.records if record.name == reconcile_module.LOGGER.name]
    assert lines
    for record in lines:
        assert str(SECRET_FILE_ID) not in record.getMessage()
        extras = {key: value for key, value in vars(record).items() if key not in vars(logging.makeLogRecord({}))}
        extras.pop("message", None)
        assert str(SECRET_FILE_ID) not in repr(extras)
        assert set(extras) <= reconcile_module.LOG_FIELDS
        for value in extras.values():
            assert isinstance(value, int | str | list | type(None))


# -- the contract of the PHP answers (nc_files.py) -------------------------------------


def answering(monkeypatch: pytest.MonkeyPatch, answers: dict[str, tuple[int | None, object]]) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []

    async def request(
        _client: object,
        method: str,
        route: str,
        *,
        params: dict[str, object] | None = None,
        body: dict[str, object] | None = None,
    ) -> tuple[int | None, object]:
        del params, body
        seen.append((method, route))
        return answers.get(route, (None, None))

    monkeypatch.setattr(nc, "reconcile_request", request)
    return seen


async def test_the_mount_list_is_read_from_its_route(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = {
        "storageId": 4,
        "rootId": 40,
        "crawlFinished": True,
        "capturable": True,
        "external": True,
        "groupable": True,
    }
    seen = answering(monkeypatch, {"mounts": (200, {"ok": True, "mounts": [entry]})})

    listing = await FileClient(cast("nc.HttpClient", object())).mounts()

    assert seen == [("GET", "mounts")]
    assert listing == MountList(ok=True, mounts=[mount(SMB, root=40, groupable=True)])


@pytest.mark.parametrize(
    "data",
    [
        {
            "ok": True,
            "mounts": [
                {
                    "storageId": 4,
                    "rootId": 40,
                    "crawlFinished": True,
                    "capturable": True,
                    "external": True,
                    "groupable": True,
                    "path": "/secret",
                }
            ],
        },
        {
            "ok": True,
            "mounts": [
                {
                    "storageId": "4",
                    "rootId": 40,
                    "crawlFinished": True,
                    "capturable": True,
                    "external": True,
                    "groupable": True,
                }
            ],
        },
        {"ok": "yes", "mounts": []},
        ["not", "an", "object"],
        None,
    ],
)
async def test_a_mount_list_outside_the_contract_is_no_list(monkeypatch: pytest.MonkeyPatch, data: object) -> None:
    answering(monkeypatch, {"mounts": (200, data)})

    assert await FileClient(cast("nc.HttpClient", object())).mounts() is None


async def test_an_unreachable_instance_is_no_list(monkeypatch: pytest.MonkeyPatch) -> None:
    answering(monkeypatch, {})

    assert await FileClient(cast("nc.HttpClient", object())).mounts() is None


async def test_the_classification_asks_in_bands_and_merges_the_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    bodies: list[list[int]] = []

    async def request(
        _client: object,
        method: str,
        route: str,
        *,
        params: dict[str, object] | None = None,
        body: dict[str, object] | None = None,
    ) -> tuple[int | None, object]:
        del params
        assert (method, route) == ("POST", "storages/classify")
        assert body is not None
        ids = cast("list[int]", body["storageIds"])
        bodies.append(ids)
        return 200, {"gone": [ids[0]], "deselected": [], "present": ids[1:]}

    monkeypatch.setattr(nc, "reconcile_request", request)
    ids = list(range(1, nc_files.MAX_IDS + 11))

    answer = await FileClient(cast("nc.HttpClient", object())).classify(ids)

    assert [len(band) for band in bodies] == [nc_files.MAX_IDS, 10]
    assert answer is not None
    assert answer.gone == [1, nc_files.MAX_IDS + 1]
    assert len(answer.present) == len(ids) - 2


def test_the_reconcile_routes_have_no_free_part() -> None:
    assert nc.reconcile_url("mounts").endswith("/ocs/v2.php/apps/audio_video_search/reconcile/mounts")
    assert nc.reconcile_url("mounts/4/slice").endswith("/reconcile/mounts/4/slice")
    for route in ("mounts/../files/1", "mounts/x/slice", "requeue?x=1", "files/1", "mounts/4/slice/.."):
        with pytest.raises(ValueError, match="route"):
            nc.reconcile_url(route)
