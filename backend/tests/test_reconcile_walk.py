"""The walk of the reconcile, its route and the gate of the intake (plan 02-20).

The walk reads the slices of every mount whose first crawl is finished and
compares them with state.db. A file it does not know, or knows with another
(etag, size, mtime), another storage or set aside, goes back to PHP over
POST reconcile/requeue in bands of 256, and PHP sends it through the one
pre-check (D-02-05). The walk never writes such a file into state.db itself
(T-02-72): only worker/intake.py calls Store.apply_intake, and the gate at the
end of this file holds that by the AST.

A reference of a storage whose every mount was walked to its end, which no
slice carried and which nothing touched since the walk began, lies outside
every walk root: a folder in the trash raises no event for the files in it
(deferred items 02-18). It is set aside like a file in the trash and comes
back through the walk and the pre-check when the folder is restored.

stats.ok false of the work stock ends the walk, not the sweep; the length of
the work stock is no gate.
"""

import ast
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend import companion
from audio_video_search_backend.api import Services
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.nc_files import (
    Classification,
    MountEntry,
    MountList,
    RequeueAnswer,
    Slice,
    SliceFile,
)
from audio_video_search_backend.store.repo import Store
from audio_video_search_backend.worker import reconcile as reconcile_module
from audio_video_search_backend.worker.reconcile import Reconciler
from tests.conftest import BACKEND_ROOT, signed_headers

DAY = 86_400
FUTURE = 1_900_000_000
SHA_A = "1" * 64
SHA_B = "2" * 64
HOME = 3
TEAM = 5
SMB = 4
PACKAGE = BACKEND_ROOT / "src" / "audio_video_search_backend"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    opened = Store.open(tmp_path / "state.db")
    yield opened
    opened.close()


def mount(storage_id: int, root: int, *, finished: bool = True, capturable: bool = True) -> MountEntry:
    return MountEntry(
        storageId=storage_id,
        rootId=root,
        crawlFinished=finished,
        capturable=capturable,
        external=False,
        groupable=False,
    )


def file(file_id: int, *, etag: str | None = None, size: int | None = None, mtime: int | None = None) -> SliceFile:
    return SliceFile(
        fileId=file_id,
        etag=etag if etag is not None else f"etag-{file_id}",
        size=size if size is not None else 1000 + file_id,
        mtime=mtime if mtime is not None else 1_700_000_000 + file_id,
    )


class FakeFiles:
    def __init__(self, mounts: list[MountEntry], files: dict[tuple[int, int], list[SliceFile]]) -> None:
        self.listing: MountList | None = MountList(ok=True, mounts=mounts)
        self.files = files
        self.sliced: list[tuple[int, int, int]] = []
        self.requeued: list[list[int]] = []
        self.slice_fails = False
        self.requeue_fails = False

    async def mounts(self) -> MountList | None:
        return self.listing

    async def classify(self, storage_ids: Sequence[int]) -> Classification | None:
        return Classification(gone=[], deselected=[], present=list(storage_ids))

    async def slice(self, storage_id: int, root_id: int, after: int, limit: int) -> Slice | None:
        self.sliced.append((storage_id, root_id, after))
        if self.slice_fails:
            return None
        rows = [row for row in self.files.get((storage_id, root_id), []) if row.fileId > after][:limit]
        return Slice(files=rows, next=rows[-1].fileId if len(rows) == limit else None)

    async def requeue(self, file_ids: Sequence[int]) -> RequeueAnswer | None:
        if self.requeue_fails:
            return None
        self.requeued.append(list(file_ids))
        return RequeueAnswer(enqueued=len(file_ids) - 1, rejected=1)


class Clock:
    def __init__(self, at: int = FUTURE) -> None:
        self.at = at

    def __call__(self) -> float:
        return float(self.at)


def reconciler(
    store: Store, files: FakeFiles, clock: Clock | None = None, *, queue_ok: bool | None = True, limit: int = 1000
) -> Reconciler:
    return Reconciler(
        Services(store=store, index=cast("SearchIndex", None)),
        files,
        clock=clock or Clock(),
        hour_of=lambda: reconcile_module.PREFERRED_HOUR,
        queue_ok=lambda: queue_ok,
        slice_limit=limit,
    )


def ref(store: Store, file_id: int, storage_id: int, *, sha: str | None = None, state: str = "active") -> None:
    media_id = store.media_for_file_sha256(sha) if sha is not None else None
    store.upsert_file_ref(
        file_id,
        media_id,
        storage_id=storage_id,
        etag=f"etag-{file_id}",
        size=1000 + file_id,
        mtime=1_700_000_000 + file_id,
        state=state,
        stage="keyed" if media_id is not None else "pending",
        reason=None,
        reader_uid="ana",
        proved_at=1 if media_id is not None else None,
    )


def snapshot(store: Store) -> list[tuple[Any, ...]]:
    return store._conn.execute(
        "SELECT file_id, storage_id, etag, size, mtime, state, stage, media_id FROM file_ref ORDER BY file_id"
    ).fetchall()


def state_of(store: Store, file_id: int) -> str | None:
    found = store.file_ref(file_id)
    return None if found is None else found.state


# -- the walk --------------------------------------------------------------------------


async def test_the_walk_hands_unknown_and_changed_files_back_and_writes_nothing(store: Store) -> None:
    ref(store, 502, HOME, sha=SHA_A)
    ref(store, 503, HOME, sha=SHA_B)
    ref(store, 504, HOME)
    files = FakeFiles(
        [mount(HOME, 30), mount(TEAM, 50, finished=False)],
        {
            (HOME, 30): [file(501), file(502, etag="etag-new"), file(503), file(504, size=7)],
            (TEAM, 50): [file(601)],
        },
    )
    before = snapshot(store)

    result = await reconciler(store, files).run_once()

    assert files.sliced == [(HOME, 30, 0)]
    assert files.requeued == [[501, 502, 504]]
    assert snapshot(store) == before
    assert (result.walked_mounts, result.requeued, result.rejected) == (1, 2, 1)
    assert result.skipped_reason is None
    assert store.meta_value("walk_at") == str(FUTURE)


async def test_the_walk_hands_back_in_bands_of_256_and_follows_the_slices(store: Store) -> None:
    files = FakeFiles([mount(HOME, 30)], {(HOME, 30): [file(i) for i in range(1, 601)]})

    await reconciler(store, files, limit=500).run_once()

    assert [len(band) for band in files.requeued] == [256, 244, 100]
    assert sorted(i for band in files.requeued for i in band) == list(range(1, 601))
    assert files.sliced == [(HOME, 30, 0), (HOME, 30, 500)]
    assert snapshot(store) == []


async def test_a_moved_or_set_aside_file_goes_back_through_the_pre_check(store: Store) -> None:
    ref(store, 10, HOME, sha=SHA_A)
    ref(store, 11, TEAM, sha=SHA_B, state="trashed")
    files = FakeFiles([mount(TEAM, 50)], {(TEAM, 50): [file(10), file(11)]})

    await reconciler(store, files).run_once()

    assert files.requeued == [[10, 11]]
    assert state_of(store, 11) == "trashed"


async def test_a_known_file_missing_from_one_slice_is_no_finding(store: Store) -> None:
    ref(store, 700, HOME, sha=SHA_A)
    ref(store, 701, HOME, sha=SHA_B)
    # Two walk roots of one storage, 701 lies below the second one.
    files = FakeFiles([mount(HOME, 30), mount(HOME, 31)], {(HOME, 30): [file(700)], (HOME, 31): [file(701)]})
    before = snapshot(store)

    await reconciler(store, files).run_once()

    assert files.requeued == []
    assert snapshot(store) == before


async def test_a_storage_not_walked_to_its_end_sets_nothing_aside(store: Store) -> None:
    ref(store, 700, HOME, sha=SHA_A)
    files = FakeFiles([mount(HOME, 30), mount(HOME, 31, finished=False)], {(HOME, 30): []})

    await reconciler(store, files).run_once()

    assert state_of(store, 700) == "active"


async def test_a_file_outside_every_walk_root_is_set_aside_and_comes_back(store: Store) -> None:
    # A folder went into the trash: no event for the files in it.
    ref(store, 800, HOME, sha=SHA_A)
    ref(store, 801, HOME)
    ref(store, 802, TEAM, sha=SHA_B)
    files = FakeFiles([mount(HOME, 30), mount(TEAM, 50, finished=False)], {(HOME, 30): []})
    clock = Clock()
    rounds = reconciler(store, files, clock)

    await rounds.run_once()

    assert state_of(store, 800) == "trashed"
    assert state_of(store, 801) == "trashed"
    assert state_of(store, 802) == "active"
    media = store._conn.execute("SELECT orphaned_at FROM media WHERE media_id = 1").fetchone()
    assert media[0] is not None
    assert store.next_capture() is None

    # Restored: the files are back below the root and go through the pre-check.
    files.files[(HOME, 30)] = [file(800), file(801)]
    clock.at += 2 * DAY
    await rounds.run_once()

    assert files.requeued == [[800, 801]]


async def test_a_reference_touched_after_the_walk_began_is_not_set_aside(store: Store) -> None:
    ref(store, 900, HOME, sha=SHA_A)
    files = FakeFiles([mount(HOME, 30)], {(HOME, 30): []})

    await reconciler(store, files, Clock(int(time.time()) - 60)).run_once()

    assert state_of(store, 900) == "active"


async def test_a_mount_that_is_not_capturable_is_not_walked(store: Store) -> None:
    ref(store, 10, HOME, sha=SHA_A)
    files = FakeFiles([mount(HOME, 30, capturable=False)], {(HOME, 30): [file(11)]})

    result = await reconciler(store, files).run_once()

    assert files.sliced == []
    assert state_of(store, 10) == "active"
    assert result.skipped_reason == "crawl_unfinished"


async def test_an_unreadable_work_stock_ends_the_walk_not_the_sweep(store: Store) -> None:
    ref(store, 10, HOME, sha=SHA_A)
    files = FakeFiles([mount(HOME, 30)], {(HOME, 30): [file(11)]})

    result = await reconciler(store, files, queue_ok=False).run_once()

    assert files.sliced == []
    assert files.requeued == []
    assert store.meta_value("storage_sweep_at") == str(FUTURE)
    assert store.meta_value("walk_at") is None
    assert result.skipped_reason == "queue_unavailable"


async def test_a_work_stock_not_asked_yet_is_no_gate(store: Store) -> None:
    files = FakeFiles([mount(HOME, 30)], {(HOME, 30): [file(11)]})

    await reconciler(store, files, queue_ok=None).run_once()

    assert files.requeued == [[11]]


@pytest.mark.parametrize("failing", ["slice", "requeue"])
async def test_a_failed_slice_or_hand_back_ends_the_walk_without_a_stamp(store: Store, failing: str) -> None:
    ref(store, 10, HOME, sha=SHA_A)
    files = FakeFiles([mount(HOME, 30)], {(HOME, 30): [file(11)]})
    files.slice_fails = failing == "slice"
    files.requeue_fails = failing == "requeue"

    result = await reconciler(store, files).run_once()

    assert store.meta_value("walk_at") is None
    assert state_of(store, 10) == "active"
    assert result.skipped_reason == f"{failing}_unavailable"
    assert result.walked_mounts == 0


async def test_the_walk_is_due_once_a_day_and_forced_at_once(store: Store) -> None:
    files = FakeFiles([mount(HOME, 30)], {(HOME, 30): [file(11)]})
    clock = Clock()
    rounds = reconciler(store, files, clock)
    await rounds.run_once()
    clock.at += 3600

    await rounds.run_once()
    assert len(files.sliced) == 1

    await rounds.run_once(force=True)
    assert len(files.sliced) == 2
    assert store.meta_value("walk_at") == str(FUTURE + 3600)


async def test_the_loop_runs_only_while_the_php_app_is_there(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    files = FakeFiles([mount(HOME, 30)], {(HOME, 30): []})
    rounds = reconciler(store, files)
    states = iter([companion.UNKNOWN, companion.OK])
    monkeypatch.setattr(
        companion, "current", lambda: companion.CompanionState(state=next(states), version=None, checked_at=None)
    )
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    await rounds.run_forever(sleep=sleep, rounds=2)

    assert slept == [reconcile_module.TICK_SECONDS] * 2
    assert len(files.sliced) == 1


# -- POST /reconcile/run ---------------------------------------------------------------


def test_the_route_runs_sweep_proof_planning_and_walk_at_once(client: TestClient) -> None:
    opened = client.app.state.services  # type: ignore[attr-defined]
    ref(opened.store, 10, SMB, sha=SHA_A)
    files = FakeFiles(
        [MountEntry(storageId=SMB, rootId=40, crawlFinished=True, capturable=True, external=True, groupable=True)],
        {(SMB, 40): [file(10), file(12)]},
    )
    files.requeued = []
    client.app.state.reconciler = Reconciler(opened, files)  # type: ignore[attr-defined]
    opened.store.set_meta("storage_sweep_at", str(int(time.time())))
    opened.store.set_meta("walk_at", str(int(time.time())))

    answer = client.post("/reconcile/run", json={"reprove": True}, headers=signed_headers())

    assert answer.status_code == 200
    body = answer.json()
    assert list(body) == [
        "swept",
        "vanished",
        "orphaned",
        "walkedMounts",
        "requeued",
        "rejected",
        "reproofDue",
        "skippedReason",
    ]
    assert body == {
        "swept": 0,
        "vanished": 0,
        "orphaned": 0,
        "walkedMounts": 1,
        "requeued": 0,
        "rejected": 1,
        "reproofDue": 1,
        "skippedReason": None,
    }
    assert files.requeued == [[12]]
    found = opened.store.file_ref(10)
    assert found is not None
    assert found.stage == "probing"


@pytest.mark.parametrize("body", [{}, {"reprove": "yes"}, {"reprove": 1}])
def test_the_route_takes_exactly_its_body(client: TestClient, body: dict[str, object]) -> None:
    assert client.post("/reconcile/run", json=body, headers=signed_headers()).status_code == 422


def test_the_route_needs_a_signature(client: TestClient) -> None:
    assert client.post("/reconcile/run", json={"reprove": False}).status_code == 401


def test_the_route_answers_503_without_a_reconcile(client: TestClient) -> None:
    client.app.state.reconciler = None  # type: ignore[attr-defined]

    assert client.post("/reconcile/run", json={"reprove": False}, headers=signed_headers()).status_code == 503


def test_the_lifespan_starts_the_reconcile_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from audio_video_search_backend import main

    started: list[object] = []

    async def record(reconciler: object) -> None:
        started.append(reconciler)

    monkeypatch.setattr(reconcile_module, "run_forever", record)
    with TestClient(main.APP) as running:
        assert running.app.state.reconciler is started[0]  # type: ignore[attr-defined]

    assert isinstance(started[0], Reconciler)


def test_the_route_is_admin_only_in_info_xml() -> None:
    import xml.etree.ElementTree as ET

    tree = ET.parse(BACKEND_ROOT / "appinfo" / "info.xml")  # noqa: S314 - our own file
    routes = {
        (route.findtext("url"), route.findtext("verb")): route.findtext("access_level")
        for route in tree.getroot().iter("route")
    }
    assert routes[("^/reconcile/run$", "POST")] == "ADMIN"


# -- the gate: only the intake writes the work stock into state.db ---------------------


def apply_intake_callers(sources: dict[str, str]) -> list[str]:
    """The modules whose source calls .apply_intake(...)."""
    found = []
    for name, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "apply_intake":
                found.append(name)
                break
    return sorted(found)


def package_sources() -> dict[str, str]:
    return {
        path.relative_to(PACKAGE).as_posix(): path.read_text(encoding="utf-8") for path in sorted(PACKAGE.rglob("*.py"))
    }


def test_only_the_intake_calls_apply_intake() -> None:
    sources = package_sources()

    assert "worker/reconcile.py" in sources
    assert apply_intake_callers(sources) == ["worker/intake.py"]


def test_the_gate_sees_a_call_in_the_reconcile() -> None:
    sources = package_sources()
    sources["worker/reconcile.py"] += "\n\ndef leak(store):\n    return store.apply_intake([])\n"

    assert apply_intake_callers(sources) == ["worker/intake.py", "worker/reconcile.py"]
