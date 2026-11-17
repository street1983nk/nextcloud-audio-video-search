"""Counting by content (plan 02-09, D-02-06, pitfall 4).

The property test compares store/coverage.py with a model written here in
plain Python, over 500 random work stocks with a fixed seed. The model is not
the SQL of the implementation: it walks the rows itself.
"""

import random
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from audio_video_search_backend import nc
from audio_video_search_backend.store import coverage as cov
from audio_video_search_backend.store.repo import PREVIEW_REASONS, PREVIEW_STATES, STAGES, STATES, IntakeItem, Store

NOW = 1_800_000_000
PREFILTERS = [None, "a" * 64, "b" * 64, "c" * 64]
MODEL = "d" * 64


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    opened = Store.open(tmp_path / "state.db")
    yield opened
    opened.close()


def _conn(store: Store) -> sqlite3.Connection:
    return store.reading_connection()


def _clear(conn: sqlite3.Connection) -> None:
    for table in ("current", "word", "transcript", "file_ref", "media_key", "media"):
        conn.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed table names of the test


def _media(conn: sqlite3.Connection, media_id: int, *, transcript: bool, orphaned: bool) -> None:
    conn.execute(
        "INSERT INTO media (media_id, created_at, orphaned_at) VALUES (?, 0, ?)",
        (media_id, NOW if orphaned else None),
    )
    if transcript:
        conn.execute(
            "INSERT INTO transcript (version_id, media_id, engine, model_sha256, config_version, profile, level, "
            "epoch, language, input_file_sha256, created_at) VALUES (?, ?, 'parakeet', ?, 1, 'balanced', 100, 0, "
            "'de', ?, 0)",
            (media_id, media_id, MODEL, f"{media_id:064x}"),
        )
        conn.execute(
            "INSERT INTO current (media_id, version_id, epoch, level, config_version, index_rev) "
            "VALUES (?, ?, 0, 100, 1, 1)",
            (media_id, media_id),
        )


def _ref(
    conn: sqlite3.Connection,
    file_id: int,
    *,
    media_id: int | None = None,
    prefilter: str | None = None,
    state: str = "active",
    stage: str = "pending",
    next_try_at: int | None = None,
) -> None:
    conn.execute(
        "INSERT INTO file_ref (file_id, media_id, storage_id, prefilter_key, reader_uid, etag, size, mtime, state, "
        "stage, reason, attempts, next_try_at, updated_at) VALUES (?, ?, 3, ?, 'ana', 'e', 1, 1, ?, ?, NULL, 0, ?, 0)",
        (file_id, media_id, prefilter, state, stage, next_try_at),
    )


def _model(
    refs: list[tuple[int, int | None, str | None, str]], media: dict[int, tuple[bool, bool]]
) -> tuple[int, int, int]:
    """(contents, transcribed, files) computed row by row, without SQL."""
    active = sorted((r for r in refs if r[3] == "active"), key=lambda r: r[0])
    keys: set[object] = set()
    for file_id, media_id, prefilter, _state in active:
        if media_id is not None:
            keys.add(("m", media_id))
            continue
        sibling = next(
            (s[1] for s in active if prefilter is not None and s[2] == prefilter and s[1] is not None),
            None,
        )
        if sibling is not None:
            keys.add(("m", sibling))
        elif prefilter is not None:
            keys.add(("p", prefilter))
        else:
            keys.add(("f", file_id))
    actively_used = {r[1] for r in active if r[1] is not None}
    transcribed = sum(
        1
        for media_id, (has_current, orphaned) in media.items()
        if has_current and not orphaned and media_id in actively_used
    )
    return len(keys), transcribed, len(active)


def test_500_random_work_stocks_count_like_the_model(store: Store) -> None:
    conn = _conn(store)
    rng = random.Random(20261107)  # noqa: S311 - test data, not a secret
    for _case in range(500):
        _clear(conn)
        media = {m: (rng.random() < 0.6, rng.random() < 0.2) for m in range(1, rng.randint(0, 6) + 1)}
        for media_id, (has_current, orphaned) in media.items():
            _media(conn, media_id, transcript=has_current, orphaned=orphaned)
        refs: list[tuple[int, int | None, str | None, str]] = []
        for file_id in range(1, rng.randint(0, 15) + 1):
            media_id = rng.choice([None, *media]) if media else None
            prefilter = rng.choice(PREFILTERS)
            state = rng.choice(sorted(STATES))
            stage = rng.choice(sorted(STAGES))
            _ref(conn, file_id, media_id=media_id, prefilter=prefilter, state=state, stage=stage)
            refs.append((file_id, media_id, prefilter, state))

        found = cov.coverage(conn, NOW)

        assert (found.contents, found.transcribed, found.files) == _model(refs, media)
        assert found.transcribed <= found.contents <= found.files
        assert sum(found.by_state.values()) == len(refs)
        assert sum(found.by_stage.values()) == len(refs)


def test_a_keyed_copy_and_its_pending_sibling_are_one_content(store: Store) -> None:
    conn = _conn(store)
    _media(conn, 1, transcript=True, orphaned=False)
    _ref(conn, 10, media_id=1, prefilter=PREFILTERS[1], stage="keyed")
    _ref(conn, 11, prefilter=PREFILTERS[1])

    found = cov.coverage(conn, NOW)

    assert (found.contents, found.transcribed, found.files) == (1, 1, 2)


def test_two_pending_copies_with_one_prefilter_key_are_one_content(store: Store) -> None:
    conn = _conn(store)
    _ref(conn, 10, prefilter=PREFILTERS[1])
    _ref(conn, 11, prefilter=PREFILTERS[1])
    _ref(conn, 12)

    assert cov.coverage(conn, NOW).contents == 2


@pytest.mark.parametrize("state", ["vanished", "trashed", "unreadable"])
def test_references_that_may_not_count_are_neither_files_nor_contents(store: Store, state: str) -> None:
    conn = _conn(store)
    _media(conn, 1, transcript=True, orphaned=False)
    _ref(conn, 10, media_id=1, state=state, stage="keyed")
    _ref(conn, 11, prefilter=PREFILTERS[2], state=state)

    found = cov.coverage(conn, NOW)

    assert (found.contents, found.transcribed, found.files) == (0, 0, 0)
    assert found.by_state[state] == 2


def test_a_sample_counts_in_neither_and_has_no_state(store: Store) -> None:
    conn = _conn(store)
    _media(conn, 1, transcript=True, orphaned=False)
    store.put_sample(10, 1)  # D-02-15: the sample layer is no reference

    found = cov.coverage(conn, NOW)

    assert (found.contents, found.transcribed, found.files) == (0, 0, 0)
    assert "sample" not in found.by_state


def test_an_unreadable_copy_is_not_pulled_in_by_its_keyed_sibling(store: Store) -> None:
    conn = _conn(store)
    _media(conn, 1, transcript=True, orphaned=False)
    _ref(conn, 10, media_id=1, prefilter=PREFILTERS[1], stage="keyed")
    _ref(conn, 11, prefilter=PREFILTERS[1], state="unreadable", stage="failed")

    found = cov.coverage(conn, NOW)

    assert (found.contents, found.transcribed, found.files) == (1, 1, 1)
    assert found.by_state["unreadable"] == 1


def test_an_unreadable_keyed_sibling_does_not_key_a_pending_copy(store: Store) -> None:
    conn = _conn(store)
    _media(conn, 1, transcript=True, orphaned=False)
    _ref(conn, 10, media_id=1, prefilter=PREFILTERS[1], state="unreadable", stage="failed")
    _ref(conn, 11, prefilter=PREFILTERS[1])

    found = cov.coverage(conn, NOW)

    # One content (the pending copy by its prefilter key), and it is not transcribed.
    assert (found.contents, found.transcribed, found.files) == (1, 0, 1)


def test_media_with_a_transcript_but_no_active_reference_is_not_transcribed(store: Store) -> None:
    conn = _conn(store)
    _media(conn, 1, transcript=True, orphaned=False)
    _media(conn, 2, transcript=True, orphaned=True)
    _media(conn, 3, transcript=True, orphaned=True)
    _ref(conn, 10, media_id=1, state="vanished", stage="keyed")
    _ref(conn, 11, media_id=3, stage="keyed")

    found = cov.coverage(conn, NOW)

    # Media 3 is orphaned although an active reference points at it: still not transcribed.
    assert (found.contents, found.transcribed, found.files) == (1, 0, 1)


def test_by_state_and_by_stage_name_every_code_of_the_closed_lists(store: Store) -> None:
    found = cov.coverage(_conn(store), NOW)

    assert set(found.by_state) == STATES
    assert set(found.by_stage) == STAGES
    assert set(found.by_state.values()) == {0}


# The preview jobs for occ (plan 03-09, D-03-13, T-03-31): a fixed list of
# names, the states and the reason codes, and nothing else.
PREVIEW_NAMES = {
    "queued",
    "running",
    "waiting",
    "complete",
    "skipped",
    "too_long",
    "no_audio",
    "damaged",
    "protected",
    "format_unsupported",
    "no_speech",
    "unsupported_language",
    "disk_full",
    "engine_failed",
}


def _job(conn: sqlite3.Connection, media_id: int, state: str, reason: str | None = None) -> None:
    conn.execute("INSERT INTO media (media_id, created_at) VALUES (?, 0)", (media_id,))
    conn.execute(
        "INSERT INTO preview_job (media_id, epoch, state, reason, origin, sort_mtime, updated_at) "
        "VALUES (?, 0, ?, ?, 'crawl', 0, 0)",
        (media_id, state, reason),
    )


def test_by_preview_names_every_state_and_reason_of_the_closed_lists(store: Store) -> None:
    found = cov.coverage(_conn(store), NOW)

    assert set(found.by_preview) == PREVIEW_NAMES
    assert PREVIEW_NAMES == PREVIEW_STATES | PREVIEW_REASONS
    assert set(found.by_preview.values()) == {0}


def test_by_preview_counts_each_job_once_under_its_reason_or_its_state(store: Store) -> None:
    conn = _conn(store)
    _job(conn, 1, "queued")
    _job(conn, 2, "running")
    _job(conn, 3, "complete")
    _job(conn, 4, "skipped", "no_speech")
    _job(conn, 5, "skipped", "too_long")
    _job(conn, 6, "waiting", "disk_full")

    found = cov.coverage(conn, NOW).by_preview

    expected = dict.fromkeys(PREVIEW_NAMES, 0) | {
        "queued": 1,
        "running": 1,
        "complete": 1,
        "no_speech": 1,
        "too_long": 1,
        "disk_full": 1,
    }
    assert found == expected
    assert sum(found.values()) == 6


def test_a_retry_without_a_reason_counts_as_waiting(store: Store) -> None:
    conn = _conn(store)
    _job(conn, 1, "waiting")
    _job(conn, 2, "waiting")

    assert cov.coverage(conn, NOW).by_preview["waiting"] == 2


def test_a_reason_outside_the_list_is_never_reported(store: Store) -> None:
    conn = _conn(store)
    _job(conn, 1, "skipped", "Sitzung 2026-11-14.mp4")

    found = cov.coverage(conn, NOW).by_preview

    assert set(found) == PREVIEW_NAMES
    assert sum(found.values()) == 0


def test_the_wire_carries_by_preview_with_codes_and_numbers_only(store: Store) -> None:
    conn = _conn(store)
    for media_id in (1, 2, 3):
        _job(conn, 4000 + media_id, "skipped", "damaged")
        _ref(conn, 7000 + media_id, media_id=4000 + media_id, stage="keyed")

    wire = cov.coverage(conn, NOW).as_wire()

    assert set(wire) == {"contents", "transcribed", "files", "byState", "byStage", "dueWork", "byPreview"}
    by_preview = wire["byPreview"]
    assert isinstance(by_preview, dict)
    assert set(by_preview) == PREVIEW_NAMES
    assert all(isinstance(count, int) and not isinstance(count, bool) for count in by_preview.values())
    assert by_preview["damaged"] == 3
    text = repr(by_preview)
    for number in ("4001", "4002", "4003", "7001", "7002", "7003", "/"):
        assert number not in text


def test_due_work_counts_only_what_the_capture_has_to_do_now(store: Store) -> None:
    conn = _conn(store)
    _ref(conn, 1)  # pending, no retry time
    _ref(conn, 2, next_try_at=NOW + 120)  # locked: pending later
    _ref(conn, 3, stage="failed", state="unreadable", next_try_at=NOW - 10)  # failed with a retry: not counted
    _ref(conn, 4, stage="probing", next_try_at=NOW)  # due probing
    _ref(conn, 5, stage="fetching")  # in work
    _ref(conn, 6, stage="keyed")
    _ref(conn, 7, stage="failed", state="unreadable")  # no next try
    _ref(conn, 8, state="vanished")  # pending, but never fetched
    _ref(conn, 9, state="unreadable", next_try_at=NOW - 1)  # unreadable deferred again, due

    assert cov.coverage(conn, NOW).due_work == 4


def test_the_counts_agree_with_a_capture_that_made_a_copy_unreadable(store: Store, tmp_path: Path) -> None:
    """End to end with the capture of plan 08: one copy keyed, its sibling refused by the gateway."""
    import asyncio
    from typing import cast

    from audio_video_search_backend.api import Services
    from audio_video_search_backend.index.publish import SearchIndex
    from audio_video_search_backend.worker.capture import Capture

    for file_id, reader in ((10, "ana"), (11, "ben")):
        store.apply_intake(
            [
                IntakeItem(
                    queue_id=file_id,
                    kind="content",
                    file_id=file_id,
                    storage_id=3,
                    etag="e",
                    size=4,
                    mtime=1,
                    prefilter_key=PREFILTERS[1],
                    reader_uid=reader,
                )
            ]
        )

    async def fetch(file_id: int, *_args: object) -> nc.FetchResult:
        if file_id == 11:
            return nc.FetchResult(sha256=None, size=0, error=nc.READ_DENIED)
        return nc.FetchResult(sha256="e" * 64, size=4, error=None, head_sha256="e" * 64)

    services = Services(store=store, index=cast("SearchIndex", None))
    capture = Capture(services, directory=tmp_path, fetch=fetch, clock=lambda: float(NOW))

    async def two() -> None:
        await capture.run_once()
        await capture.run_once()

    asyncio.run(two())
    found = cov.coverage(_conn(store), NOW)

    assert (found.contents, found.files, found.by_state["unreadable"], found.due_work) == (1, 1, 1, 0)


def test_workstock_pages_by_file_id_with_the_fixed_fields(store: Store) -> None:
    conn = _conn(store)
    _media(conn, 1, transcript=False, orphaned=False)
    for file_id in (3, 5, 9):
        _ref(conn, file_id, media_id=1 if file_id == 5 else None, state="unreadable" if file_id == 9 else "active")

    first = cov.workstock(conn, None, 0, 2)
    second = cov.workstock(conn, None, first.next or 0, 2)
    only = cov.workstock(conn, "unreadable", 0, 10)

    assert [f["fileId"] for f in first.files] == [3, 5]
    assert first.next == 5
    assert [f["fileId"] for f in second.files] == [9]
    assert second.next is None
    assert first.files[1] == {
        "fileId": 5,
        "mediaId": 1,
        "storageId": 3,
        "state": "active",
        "stage": "pending",
        "reason": None,
    }
    assert [f["fileId"] for f in only.files] == [9]


@pytest.mark.parametrize(("state", "after", "limit"), [("nope", 0, 1), (None, 0, 0), (None, 0, 1001), (None, -1, 1)])
def test_workstock_refuses_values_outside_the_contract(store: Store, state: str | None, after: int, limit: int) -> None:
    with pytest.raises(ValueError, match="invalid workstock field"):
        cov.workstock(_conn(store), state, after, limit)


@pytest.mark.timing
def test_140000_references_are_counted_within_two_seconds(store: Store) -> None:
    """A hint test on the laptop (RESEARCH measured 0.17 s): 40,000 contents with up to six copies."""
    conn = _conn(store)
    conn.execute("BEGIN")
    conn.executemany("INSERT INTO media (media_id, created_at) VALUES (?, 0)", ((m,) for m in range(1, 40_001)))
    rows = []
    file_id = 0
    rng = random.Random(7)  # noqa: S311 - test data, not a secret
    for media_id in range(1, 40_001):
        prefilter = f"{media_id:064x}"
        for copy in range(rng.randint(1, 6)):
            file_id += 1
            keyed = copy == 0 or rng.random() < 0.5
            rows.append((file_id, media_id if keyed else None, prefilter))
            if file_id >= 140_000:
                break
        if file_id >= 140_000:
            break
    conn.executemany(
        "INSERT INTO file_ref (file_id, media_id, storage_id, prefilter_key, reader_uid, etag, size, mtime, state, "
        "stage, attempts, updated_at) VALUES (?, ?, 3, ?, 'ana', 'e', 1, 1, 'active', 'keyed', 0, 0)",
        rows,
    )
    conn.execute("COMMIT")

    started = time.perf_counter()
    found = cov.coverage(conn, NOW)
    elapsed = time.perf_counter() - started

    assert found.files == len(rows)
    assert found.contents == len({r[2] for r in rows})
    assert elapsed < 2.0, f"counting took {elapsed:.2f} s"
