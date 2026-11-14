"""The preview jobs in the store (plan 03-09, D-03-05 to D-03-09, D-03-12, D-03-13, D-03-17, TRANS-07).

Every change of a preview job is one checked transaction: the claim in the
order of D-03-05, the commit of one piece with its words, its index revision
and its outbox row (D-03-07), the verdicts with their reason codes, the way
back to the queue on an interruption and after a restart, and the way back of
too long files when the admin raises the limit (D-03-09).

The tests read the database with their own SQL, never with the statements of
the implementation, and every expected order is written out by hand.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.store.repo import (
    PREVIEW_REASONS,
    PREVIEW_STATES,
    ChunkCounters,
    IntakeItem,
    PreviewJob,
    Store,
)

NOW = 1_800_000_000
HEAD = "9" * 64
MODEL = "d" * 64
SHA = {1: "1" * 64, 2: "2" * 64, 3: "3" * 64, 4: "4" * 64}
NO_COUNT = ChunkCounters(kept_words=0, drop_script=0, drop_language=0, drop_conf=0, speech_ms=0)


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


def _keyed(store: Store, file_id: int, sha256: str, **fields: Any) -> int:
    """Take a file in, claim it and key it, the way the capture does; the job is seeded with it."""
    store.apply_intake([_item(file_id, **fields)])
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert claimed.file_id == file_id
    media_id = store.mark_keyed(claimed, sha256, HEAD, NOW)
    assert media_id is not None
    return media_id


def _sql(path: Path, statement: str, values: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    with closing(sqlite3.connect(path)) as conn, conn:
        return conn.execute(statement, values).fetchall()


def _job_row(path: Path, media_id: int) -> dict[str, Any] | None:
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM preview_job WHERE media_id = ?", (media_id,)).fetchone()
    return None if row is None else dict(row)


def _prov(sha256: str, epoch: int = 0) -> Provenance:
    return Provenance(
        engine="parakeet",
        model_sha256=MODEL,
        config_version=1,
        profile="balanced",
        level=Level.PREVIEW,
        epoch=epoch,
        language="und",
        input_file_sha256=sha256,
    )


def _w(surface: str, start: int) -> Word:
    return Word(start_ms=start, end_ms=start + 300, surface=surface, norm=surface.casefold(), conf=0.8, src="machine")


def _counters(kept: int, script: int = 0, language: int = 0, conf: int = 0, speech: int = 0) -> ChunkCounters:
    return ChunkCounters(kept_words=kept, drop_script=script, drop_language=language, drop_conf=conf, speech_ms=speech)


def _claim(store: Store, now: int = NOW) -> PreviewJob:
    job = store.next_preview(now)
    assert job is not None
    return job


def _three_jobs(store: Store) -> dict[str, int]:
    """crawl with mtime 300, event with mtime 100, crawl with mtime 500."""
    return {
        "crawl300": _keyed(store, 11, SHA[1], mtime=300),
        "event100": _keyed(store, 12, SHA[2], mtime=100, origin="event"),
        "crawl500": _keyed(store, 13, SHA[3], mtime=500),
    }


# -- closed lists ------------------------------------------------------------------


def test_the_closed_lists_of_the_preview_job() -> None:
    assert frozenset({"queued", "running", "waiting", "complete", "skipped"}) == PREVIEW_STATES
    assert (
        frozenset(
            {
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
        )
        == PREVIEW_REASONS
    )


def test_every_reason_of_the_probe_and_of_the_file_verdict_is_a_preview_reason() -> None:
    from audio_video_search_backend.engine import catch
    from audio_video_search_backend.media import probe

    assert probe.MEDIA_REASONS <= PREVIEW_REASONS
    assert {catch.NO_SPEECH, catch.UNSUPPORTED_LANGUAGE} <= PREVIEW_REASONS


def test_the_schema_knows_every_state_of_the_list(path: Path, store: Store) -> None:
    media_id = _keyed(store, 11, SHA[1])
    for state in sorted(PREVIEW_STATES):
        _sql(path, "UPDATE preview_job SET state = ? WHERE media_id = ?", (state, media_id))
    with pytest.raises(sqlite3.IntegrityError):
        _sql(path, "UPDATE preview_job SET state = 'paused' WHERE media_id = ?", (media_id,))


# -- the claim (D-03-05) -----------------------------------------------------------


def test_event_comes_before_crawl_and_then_the_newest_first(store: Store, path: Path) -> None:
    media = _three_jobs(store)

    order = [_claim(store).media_id for _ in range(3)]

    assert order == [media["event100"], media["crawl500"], media["crawl300"]]
    assert store.next_preview(NOW) is None


def test_the_claimed_job_is_running_with_all_its_columns(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1], mtime=300, origin="event")

    job = _claim(store, NOW + 5)

    assert job.media_id == media_id
    assert (job.state, job.origin, job.sort_mtime, job.epoch) == ("running", "event", 300, 0)
    assert (job.next_start_ms, job.chunks_done, job.version_id, job.attempts) == (0, 0, None, 0)
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["updated_at"]) == ("running", NOW + 5)


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE file_ref SET reader_uid = NULL WHERE file_id = 11",
        "UPDATE file_ref SET state = 'unreadable' WHERE file_id = 11",
        "UPDATE file_ref SET state = 'vanished' WHERE file_id = 11",
        "UPDATE file_ref SET state = 'trashed' WHERE file_id = 11",
        "UPDATE file_ref SET stage = 'probing' WHERE file_id = 11",
    ],
)
def test_a_job_without_an_active_keyed_reference_with_a_reader_never_comes(
    store: Store, path: Path, change: str
) -> None:
    _keyed(store, 11, SHA[1])
    _sql(path, change)

    assert store.next_preview(NOW) is None


def test_a_second_copy_with_a_reader_makes_the_job_claimable_again(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    _sql(path, "UPDATE file_ref SET reader_uid = NULL WHERE file_id = 11")
    assert store.next_preview(NOW) is None
    _keyed(store, 12, SHA[1])

    assert _claim(store).media_id == media_id


def test_a_waiting_job_comes_only_once_its_time_has_come(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.defer_preview(job, "disk_full", retry_at=NOW + 600, now=NOW)

    assert store.next_preview(NOW + 599) is None
    again = _claim(store, NOW + 600)
    assert again.media_id == media_id
    assert (again.state, again.reason) == ("running", None)


@pytest.mark.parametrize("state", ["running", "complete", "skipped"])
def test_settled_and_running_jobs_are_never_claimed(store: Store, path: Path, state: str) -> None:
    media_id = _keyed(store, 11, SHA[1])
    _sql(path, "UPDATE preview_job SET state = ? WHERE media_id = ?", (state, media_id))

    assert store.next_preview(NOW) is None


# -- the source of a job -----------------------------------------------------------


def test_the_source_is_the_active_keyed_reference_with_the_smallest_file_id(store: Store, path: Path) -> None:
    media_id = _keyed(store, 20, SHA[1], size=1000, reader_uid="ben")
    _keyed(store, 15, SHA[1], size=1000, reader_uid="cem")

    assert store.preview_source(media_id) == (15, "cem", 1000)

    _sql(path, "UPDATE file_ref SET state = 'trashed' WHERE file_id = 15")
    assert store.preview_source(media_id) == (20, "ben", 1000)


def test_no_source_without_an_active_keyed_reference_with_a_reader(store: Store, path: Path) -> None:
    media_id = _keyed(store, 20, SHA[1])
    _sql(path, "UPDATE file_ref SET reader_uid = NULL WHERE file_id = 20")

    assert store.preview_source(media_id) is None
    assert store.preview_source(media_id + 1000) is None


# -- the commit of one piece (D-03-07, TRANS-07) -----------------------------------


def _transcripts(path: Path, media_id: int) -> list[tuple[Any, ...]]:
    return _sql(path, "SELECT version_id, engine, level FROM transcript WHERE media_id = ?", (media_id,))


def _words(path: Path, version_id: int) -> list[tuple[Any, ...]]:
    return _sql(path, "SELECT idx, surface, start_ms FROM word WHERE version_id = ? ORDER BY idx", (version_id,))


def _outbox(path: Path, media_id: int) -> list[int]:
    return [r[0] for r in _sql(path, "SELECT index_rev FROM index_outbox WHERE media_id = ? ORDER BY 1", (media_id,))]


def test_the_first_piece_makes_the_preview_version_current(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)

    done = store.commit_chunk(
        job,
        prov=_prov(SHA[1]),
        words=[_w("eins", 0), _w("zwei", 400), _w("drei", 800)],
        next_start_ms=600_000,
        counters=_counters(3, script=1, language=2, conf=4, speech=5000),
    )

    assert done is True
    transcripts = _transcripts(path, media_id)
    assert len(transcripts) == 1
    version_id, engine, level = transcripts[0]
    assert (engine, level) == ("parakeet", int(Level.PREVIEW))
    current = _sql(path, "SELECT version_id, level, index_rev FROM current WHERE media_id = ?", (media_id,))
    assert current == [(version_id, int(Level.PREVIEW), 1)]
    assert _outbox(path, media_id) == [1]
    assert _words(path, version_id) == [(0, "eins", 0), (1, "zwei", 400), (2, "drei", 800)]
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["next_start_ms"], row["chunks_done"], row["version_id"]) == (
        "running",
        600_000,
        1,
        version_id,
    )
    assert (row["kept_words"], row["drop_script"], row["drop_language"], row["drop_conf"], row["speech_ms"]) == (
        3,
        1,
        2,
        4,
        5000,
    )


def test_a_further_piece_appends_to_the_same_version_and_raises_the_revision(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    first = [_w("eins", 0), _w("zwei", 400), _w("drei", 800)]
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=first, next_start_ms=600_000, counters=_counters(3))

    # The worker goes on with the job it claimed; the store knows the version.
    second = [_w("vier", 600_100), _w("fünf", 600_500)]
    assert store.commit_chunk(
        job, prov=_prov(SHA[1]), words=second, next_start_ms=1_200_000, counters=_counters(2, conf=1)
    )

    transcripts = _transcripts(path, media_id)
    assert len(transcripts) == 1
    version_id = transcripts[0][0]
    assert _words(path, version_id) == [
        (0, "eins", 0),
        (1, "zwei", 400),
        (2, "drei", 800),
        (3, "vier", 600_100),
        (4, "fünf", 600_500),
    ]
    assert _sql(path, "SELECT index_rev FROM current WHERE media_id = ?", (media_id,)) == [(2,)]
    assert _outbox(path, media_id) == [1, 2]
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["next_start_ms"], row["chunks_done"], row["version_id"], row["kept_words"], row["drop_conf"]) == (
        1_200_000,
        2,
        version_id,
        5,
        1,
    )


def test_a_piece_without_words_before_the_first_word_writes_no_version(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)

    assert store.commit_chunk(
        job, prov=_prov(SHA[1]), words=[], next_start_ms=600_000, counters=_counters(0, script=7, speech=900)
    )

    assert _transcripts(path, media_id) == []
    assert _sql(path, "SELECT COUNT(*) FROM current WHERE media_id = ?", (media_id,)) == [(0,)]
    assert _outbox(path, media_id) == []
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["next_start_ms"], row["chunks_done"], row["version_id"], row["drop_script"], row["speech_ms"]) == (
        600_000,
        1,
        None,
        7,
        900,
    )


def test_the_first_words_after_an_empty_piece_make_the_version(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[], next_start_ms=600_000, counters=NO_COUNT)

    assert store.commit_chunk(
        job, prov=_prov(SHA[1]), words=[_w("eins", 600_100)], next_start_ms=1_200_000, counters=_counters(1)
    )

    transcripts = _transcripts(path, media_id)
    assert len(transcripts) == 1
    assert _words(path, transcripts[0][0]) == [(0, "eins", 600_100)]
    assert _outbox(path, media_id) == [1]
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["chunks_done"], row["version_id"]) == (2, transcripts[0][0])


def test_an_empty_piece_after_the_version_raises_no_revision(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT)

    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[], next_start_ms=1_200_000, counters=NO_COUNT)

    assert _sql(path, "SELECT index_rev FROM current WHERE media_id = ?", (media_id,)) == [(1,)]
    assert _outbox(path, media_id) == [1]


def test_a_piece_of_an_old_epoch_writes_nothing(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    store.bump_epoch(media_id)

    done = store.commit_chunk(
        job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=_counters(1)
    )

    assert done is False
    assert _transcripts(path, media_id) == []
    assert _sql(path, "SELECT COUNT(*) FROM word") == [(0,)]
    assert _outbox(path, media_id) == []
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["next_start_ms"], row["chunks_done"], row["kept_words"]) == (0, 0, 0)


def test_a_further_piece_after_a_new_epoch_writes_nothing(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT)
    store.bump_epoch(media_id)

    done = store.commit_chunk(
        job, prov=_prov(SHA[1]), words=[_w("zwei", 600_100)], next_start_ms=1_200_000, counters=_counters(1)
    )

    assert done is False
    version_id = _transcripts(path, media_id)[0][0]
    assert _words(path, version_id) == [(0, "eins", 0)]
    assert _outbox(path, media_id) == [1]
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["next_start_ms"], row["chunks_done"], row["kept_words"]) == (600_000, 1, 0)


def test_a_piece_whose_provenance_names_an_old_epoch_writes_nothing(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    store.bump_epoch(media_id)
    _sql(path, "UPDATE preview_job SET epoch = 1 WHERE media_id = ?", (media_id,))
    job = _claim(store)

    done = store.commit_chunk(
        job, prov=_prov(SHA[1], epoch=0), words=[_w("eins", 0)], next_start_ms=600_000, counters=_counters(1)
    )

    assert done is False
    assert _transcripts(path, media_id) == []


@pytest.mark.parametrize("piece", ["first", "further"])
def test_a_piece_whose_provenance_names_a_newer_epoch_writes_nothing(store: Store, path: Path, piece: str) -> None:
    _keyed(store, 11, SHA[1])
    job = _claim(store)
    if piece == "further":
        assert store.commit_chunk(
            job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT
        )

    done = store.commit_chunk(
        job, prov=_prov(SHA[1], epoch=1), words=[_w("zwei", 600_100)], next_start_ms=1_200_000, counters=NO_COUNT
    )

    assert done is False
    assert _sql(path, "SELECT COUNT(*) FROM word WHERE surface = 'zwei'") == [(0,)]
    assert _sql(path, "SELECT COUNT(*) FROM transcript WHERE epoch = 1") == [(0,)]


def test_a_piece_after_another_version_became_current_writes_nothing(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT)
    preview_version = _transcripts(path, media_id)[0][0]
    refined = Provenance(
        engine="whisper-turbo",
        model_sha256=MODEL,
        config_version=1,
        profile="balanced",
        level=Level.REFINED,
        epoch=0,
        language="de",
        input_file_sha256=SHA[1],
    )
    assert store.publish_version(media_id, refined, [_w("Eins", 0)]).published

    done = store.commit_chunk(
        job, prov=_prov(SHA[1]), words=[_w("zwei", 600_100)], next_start_ms=1_200_000, counters=NO_COUNT
    )

    assert done is False
    assert _words(path, preview_version) == [(0, "eins", 0)]
    assert _outbox(path, media_id) == [1, 2]
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["next_start_ms"], row["chunks_done"]) == (600_000, 1)


def test_a_piece_for_other_bytes_writes_nothing(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)

    done = store.commit_chunk(
        job, prov=_prov(SHA[2]), words=[_w("eins", 0)], next_start_ms=600_000, counters=_counters(1)
    )

    assert done is False
    assert _transcripts(path, media_id) == []
    row = _job_row(path, media_id)
    assert row is not None
    assert row["chunks_done"] == 0


@pytest.mark.parametrize("state", ["queued", "complete", "skipped", "waiting"])
def test_a_piece_of_a_job_that_no_longer_runs_writes_nothing(store: Store, path: Path, state: str) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    _sql(path, "UPDATE preview_job SET state = ? WHERE media_id = ?", (state, media_id))

    done = store.commit_chunk(
        job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=_counters(1)
    )

    assert done is False
    assert _transcripts(path, media_id) == []


def test_a_piece_of_a_forgotten_content_writes_nothing(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    store.apply_intake([_item(11, "exclude")])

    done = store.commit_chunk(
        job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=_counters(1)
    )

    assert done is False
    assert _sql(path, "SELECT COUNT(*) FROM transcript") == [(0,)]
    assert _job_row(path, media_id) is None


def test_a_piece_never_goes_back_in_time(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT)

    done = store.commit_chunk(
        job, prov=_prov(SHA[1]), words=[_w("zwei", 100)], next_start_ms=500_000, counters=_counters(1)
    )

    assert done is False
    version_id = _transcripts(path, media_id)[0][0]
    assert _words(path, version_id) == [(0, "eins", 0)]
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["next_start_ms"], row["chunks_done"]) == (600_000, 1)


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("next_start_ms", {"next_start_ms": -1}),
        (
            "counters",
            {"counters": ChunkCounters(kept_words=-1, drop_script=0, drop_language=0, drop_conf=0, speech_ms=0)},
        ),
        (
            "counters",
            {"counters": ChunkCounters(kept_words=0, drop_script=0, drop_language=0, drop_conf=0, speech_ms=True)},
        ),  # type: ignore[arg-type]
    ],
)
def test_invalid_fields_of_a_piece_are_refused_by_name(
    store: Store, path: Path, field: str, values: dict[str, Any]
) -> None:
    _keyed(store, 11, SHA[1])
    job = _claim(store)
    arguments: dict[str, Any] = {"prov": _prov(SHA[1]), "words": [], "next_start_ms": 1, "counters": NO_COUNT}
    arguments.update(values)

    with pytest.raises(ValueError, match=f"invalid preview field: {field}"):
        store.commit_chunk(job, **arguments)


class _FailingConnection:
    """The connection of the store, failing on the first write to the job after the words."""

    def __init__(self, inner: sqlite3.Connection) -> None:
        self._inner = inner

    def execute(self, sql: str, *args: Any) -> sqlite3.Cursor:
        if sql.lstrip().upper().startswith("UPDATE PREVIEW_JOB"):
            words = self._inner.execute("SELECT COUNT(*) FROM word").fetchone()[0]
            assert words > 0, "the job was written before the words"
            raise sqlite3.OperationalError("injected")
        return self._inner.execute(sql, *args)

    def executemany(self, sql: str, *args: Any) -> sqlite3.Cursor:
        return self._inner.executemany(sql, *args)


def test_a_failure_between_the_words_and_the_job_leaves_nothing_behind(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    inner = store._conn
    store._conn = _FailingConnection(inner)  # type: ignore[assignment]

    with pytest.raises(sqlite3.OperationalError, match="injected"):
        store.commit_chunk(
            job, prov=_prov(SHA[1]), words=[_w("eins", 0), _w("zwei", 400)], next_start_ms=600_000, counters=NO_COUNT
        )
    store._conn = inner

    assert _sql(path, "SELECT COUNT(*) FROM word") == [(0,)]
    assert _transcripts(path, media_id) == []
    assert _outbox(path, media_id) == []
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["next_start_ms"], row["chunks_done"], row["version_id"]) == ("running", 0, 0, None)


def test_a_failure_in_a_further_piece_keeps_the_first_piece(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT)
    inner = store._conn
    store._conn = _FailingConnection(inner)  # type: ignore[assignment]

    with pytest.raises(sqlite3.OperationalError, match="injected"):
        store.commit_chunk(
            job, prov=_prov(SHA[1]), words=[_w("zwei", 600_100)], next_start_ms=1_200_000, counters=NO_COUNT
        )
    store._conn = inner

    version_id = _transcripts(path, media_id)[0][0]
    assert _words(path, version_id) == [(0, "eins", 0)]
    assert _sql(path, "SELECT index_rev FROM current WHERE media_id = ?", (media_id,)) == [(1,)]
    assert _outbox(path, media_id) == [1]
    row = _job_row(path, media_id)
    assert row is not None
    assert (row["next_start_ms"], row["chunks_done"]) == (600_000, 1)


# -- verdicts and reasons (MEDIA-04, D-03-12, D-03-13, D-03-17) ---------------------


def test_the_verdict_transcript_completes_the_job(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT)

    assert store.finish_preview(job, "transcript")

    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["reason"]) == ("complete", None)


@pytest.mark.parametrize("verdict", ["no_speech", "unsupported_language"])
def test_a_verdict_without_text_skips_with_its_reason_and_leaves_current_alone(
    store: Store, path: Path, verdict: str
) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)

    assert store.finish_preview(job, verdict)

    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["reason"]) == ("skipped", verdict)
    assert _sql(path, "SELECT COUNT(*) FROM current") == [(0,)]


def test_an_unknown_verdict_is_refused_without_its_value(store: Store, path: Path) -> None:
    _keyed(store, 11, SHA[1])
    job = _claim(store)

    with pytest.raises(ValueError, match="invalid preview field: verdict") as raised:
        store.finish_preview(job, "Sitzung.mp4")

    assert "Sitzung.mp4" not in str(raised.value)


@pytest.mark.parametrize(
    "reason", ["no_audio", "damaged", "protected", "format_unsupported", "too_long", "engine_failed"]
)
def test_a_skip_keeps_its_reason_and_the_duration(store: Store, path: Path, reason: str) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)

    assert store.skip_preview(job, reason, duration_ms=50_000_000)

    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["reason"], row["duration_ms"]) == ("skipped", reason, 50_000_000)


def test_a_skip_without_a_known_duration_is_possible(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)

    assert store.skip_preview(job, "damaged", duration_ms=None)

    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["reason"], row["duration_ms"]) == ("skipped", "damaged", None)


@pytest.mark.parametrize("reason", ["Sitzung.mp4", "disk_full", "no_speech", "", "read_denied"])
def test_a_skip_with_a_reason_outside_its_list_is_refused_by_name(store: Store, path: Path, reason: str) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)

    with pytest.raises(ValueError, match="invalid preview field: reason") as raised:
        store.skip_preview(job, reason, duration_ms=1)

    assert reason == "" or reason not in str(raised.value).removeprefix("invalid preview field: reason")
    row = _job_row(path, media_id)
    assert row is not None
    assert row["state"] == "running"


def test_a_defer_waits_with_its_reason_and_keeps_the_progress(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT)

    assert store.defer_preview(job, "disk_full", retry_at=NOW + 3600, now=NOW)

    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["reason"], row["next_try_at"], row["next_start_ms"]) == (
        "waiting",
        "disk_full",
        NOW + 3600,
        600_000,
    )


@pytest.mark.parametrize("reason", ["too_long", "damaged", "Sitzung.mp4"])
def test_a_defer_takes_only_a_reason_to_wait_for(store: Store, path: Path, reason: str) -> None:
    _keyed(store, 11, SHA[1])
    job = _claim(store)

    with pytest.raises(ValueError, match="invalid preview field: reason"):
        store.defer_preview(job, reason, retry_at=NOW, now=NOW)


@pytest.mark.parametrize(("count", "attempts"), [(True, 1), (False, 0)])
def test_a_retry_waits_without_a_reason_and_counts_on_request(
    store: Store, path: Path, count: bool, attempts: int
) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT)

    assert store.retry_preview(job, retry_at=NOW + 60, count=count, now=NOW)

    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["reason"], row["next_try_at"], row["attempts"], row["next_start_ms"]) == (
        "waiting",
        None,
        NOW + 60,
        attempts,
        600_000,
    )
    assert store.next_preview(NOW + 59) is None
    again = _claim(store, NOW + 60)
    assert (again.media_id, again.next_start_ms, again.attempts) == (media_id, 600_000, attempts)


def test_retries_add_up(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    for moment in (NOW, NOW + 100, NOW + 200):
        job = _claim(store, moment)
        assert store.retry_preview(job, retry_at=moment + 60, count=True, now=moment)

    row = _job_row(path, media_id)
    assert row is not None
    assert row["attempts"] == 3


@pytest.mark.parametrize("job_too", [True, False], ids=["job-moved-on", "only-the-content-moved-on"])
@pytest.mark.parametrize("operation", ["finish", "skip", "defer", "retry", "yield"])
def test_a_verdict_for_a_job_of_an_old_epoch_writes_nothing(
    store: Store, path: Path, operation: str, job_too: bool
) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    store.bump_epoch(media_id)
    if job_too:
        _sql(path, "UPDATE preview_job SET epoch = 1 WHERE media_id = ?", (media_id,))
    before = _job_row(path, media_id)

    calls = {
        "finish": lambda: store.finish_preview(job, "no_speech"),
        "skip": lambda: store.skip_preview(job, "damaged", duration_ms=1),
        "defer": lambda: store.defer_preview(job, "disk_full", retry_at=NOW, now=NOW),
        "retry": lambda: store.retry_preview(job, retry_at=NOW, count=True, now=NOW),
        "yield": lambda: store.yield_preview(job, now=NOW),
    }

    assert calls[operation]() is False
    assert _job_row(path, media_id) == before


# -- interruption and restart (D-03-06, TRANS-07) -----------------------------------


def test_yielding_puts_a_running_job_back_with_its_progress(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT)

    assert store.yield_preview(job, now=NOW)

    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["next_start_ms"], row["chunks_done"]) == ("queued", 600_000, 1)
    again = _claim(store)
    assert (again.media_id, again.next_start_ms, again.chunks_done) == (media_id, 600_000, 1)


def test_a_restart_puts_every_running_job_back_and_counts_them(store: Store, path: Path) -> None:
    media = _three_jobs(store)
    first = _claim(store)
    second = _claim(store)
    assert store.commit_chunk(
        first, prov=_prov(SHA[2]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT
    )

    assert store.reset_running() == 2

    states = dict(_sql(path, "SELECT media_id, state FROM preview_job"))
    assert states == {media["event100"]: "queued", media["crawl500"]: "queued", media["crawl300"]: "queued"}
    row = _job_row(path, first.media_id)
    assert row is not None
    assert (row["next_start_ms"], row["chunks_done"]) == (600_000, 1)
    assert second.media_id == media["crawl500"]
    assert store.reset_running() == 0


def test_an_event_waits_only_when_it_could_be_claimed(store: Store, path: Path) -> None:
    _keyed(store, 11, SHA[1], mtime=500)
    assert store.has_waiting_event() is False
    _claim(store)
    _keyed(store, 12, SHA[2], origin="event")
    assert store.has_waiting_event() is True

    _sql(path, "UPDATE file_ref SET reader_uid = NULL WHERE file_id = 12")
    assert store.has_waiting_event() is False


def test_a_running_or_settled_event_does_not_wait(store: Store, path: Path) -> None:
    media_id = _keyed(store, 12, SHA[2], origin="event")
    _claim(store)
    assert store.has_waiting_event() is False
    _sql(path, "UPDATE preview_job SET state = 'complete' WHERE media_id = ?", (media_id,))
    assert store.has_waiting_event() is False


# -- the limit of the duration (D-03-08, D-03-09) ------------------------------------


def test_the_limit_is_twelve_hours_until_set(store: Store) -> None:
    assert store.max_duration_hours() == 12


def test_setting_the_limit_answers_the_old_value(store: Store, path: Path) -> None:
    assert store.set_max_duration_hours(24) == 12
    assert store.max_duration_hours() == 24
    assert store.set_max_duration_hours(6) == 24
    assert _sql(path, "SELECT value FROM meta WHERE key = 'max_duration_hours'") == [("6",)]


@pytest.mark.parametrize("hours", [0, -1, True])
def test_a_limit_below_one_hour_is_refused_by_name(store: Store, hours: int) -> None:
    with pytest.raises(ValueError, match="invalid preview field: max_duration_hours"):
        store.set_max_duration_hours(hours)


def test_a_broken_stored_limit_reads_as_the_default(store: Store, path: Path) -> None:
    _sql(path, "INSERT INTO meta (key, value) VALUES ('max_duration_hours', 'zwölf')")
    assert store.max_duration_hours() == 12


def test_raising_the_limit_brings_back_what_fits(store: Store, path: Path) -> None:
    hour = 3_600_000
    fits = _keyed(store, 11, SHA[1])
    unknown = _keyed(store, 12, SHA[2])
    longer = _keyed(store, 13, SHA[3])
    damaged = _keyed(store, 14, SHA[4])
    for media_id, reason, duration in (
        (fits, "too_long", 20 * hour),
        (unknown, "too_long", None),
        (longer, "too_long", 30 * hour),
        (damaged, "damaged", 1 * hour),
    ):
        _sql(
            path,
            "UPDATE preview_job SET state = 'skipped', reason = ?, duration_ms = ?, next_start_ms = 5, "
            "chunks_done = 2 WHERE media_id = ?",
            (reason, duration, media_id),
        )

    assert store.requeue_too_long(24 * hour) == 2

    rows = {
        r[0]: r[1:] for r in _sql(path, "SELECT media_id, state, reason, next_start_ms, chunks_done FROM preview_job")
    }
    assert rows[fits] == ("queued", None, 0, 0)
    assert rows[unknown] == ("queued", None, 0, 0)
    assert rows[longer] == ("skipped", "too_long", 5, 2)
    assert rows[damaged] == ("skipped", "damaged", 5, 2)


def test_the_limit_itself_still_fits(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    _sql(
        path,
        "UPDATE preview_job SET state = 'skipped', reason = 'too_long', duration_ms = 1000 WHERE media_id = ?",
        (media_id,),
    )

    assert store.requeue_too_long(999) == 0
    assert store.requeue_too_long(1000) == 1


# -- what the play page may learn (D-03-13, D-02-15c) --------------------------------


def test_the_view_of_an_active_reference(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[_w("eins", 0)], next_start_ms=600_000, counters=NO_COUNT)

    view = store.preview_view(11)

    assert view is not None
    assert (view.state, view.reason, view.chunks_done, view.next_start_ms, view.level) == (
        "running",
        None,
        1,
        600_000,
        int(Level.PREVIEW),
    )
    assert store.skip_preview(job, "engine_failed", duration_ms=None)
    skipped = store.preview_view(11)
    assert skipped is not None
    assert (skipped.state, skipped.reason) == ("skipped", "engine_failed")
    assert media_id > 0


def test_the_view_of_a_job_without_a_version_has_no_level(store: Store, path: Path) -> None:
    _keyed(store, 11, SHA[1])

    view = store.preview_view(11)

    assert view is not None
    assert (view.state, view.reason, view.chunks_done, view.next_start_ms, view.level) == ("queued", None, 0, 0, None)


@pytest.mark.parametrize("state", ["unreadable", "vanished", "trashed"])
def test_no_reference_but_an_active_one_tells_anything(store: Store, path: Path, state: str) -> None:
    media_id = _keyed(store, 11, SHA[1])
    _keyed(store, 12, SHA[1])
    job = _claim(store)
    assert store.skip_preview(job, "too_long", duration_ms=99 * 3_600_000)
    _sql(path, "UPDATE file_ref SET state = ? WHERE file_id = 11", (state,))

    hidden = store.preview_view(11)
    unknown = store.preview_view(999)

    assert hidden is None
    assert unknown is None
    assert repr(hidden) == repr(unknown)
    assert store.preview_view(12) is not None
    assert media_id > 0


def test_a_sample_tells_nothing_about_a_job(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    store.put_sample(50, media_id)

    assert store.preview_view(50) is None


# -- a job for every way back to an active keyed reference (03-03 open points) -------


def _drop_job(path: Path, media_id: int) -> None:
    """A content whose job the migration did not seed: all its references lay elsewhere then."""
    _sql(path, "DELETE FROM preview_job WHERE media_id = ?", (media_id,))


def test_a_restore_from_the_trash_seeds_a_missing_job(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1], mtime=700)
    store.apply_intake([_item(11, "trash")])
    _drop_job(path, media_id)

    store.apply_intake([_item(11, "restore", mtime=700, origin="event")])

    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["origin"], row["sort_mtime"]) == ("queued", "event", 700)


def test_a_restore_that_owes_its_proof_seeds_no_job_yet(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1], prefilter_key="a" * 64)
    store.apply_intake([_item(11, "trash", prefilter_key="a" * 64)])
    _drop_job(path, media_id)

    store.apply_intake([_item(11, "restore", prefilter_key="a" * 64)])

    assert _job_row(path, media_id) is None


def test_a_passed_renewed_proof_seeds_a_missing_job(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1], prefilter_key="a" * 64)
    store.apply_intake([_item(11, "trash", prefilter_key="a" * 64)])
    _drop_job(path, media_id)
    store.apply_intake([_item(11, "restore", prefilter_key="a" * 64)])
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert claimed.file_id == 11

    assert store.confirm_proof(11, claimed.etag, NOW)

    row = _job_row(path, media_id)
    assert row is not None
    assert row["state"] == "queued"


def test_a_storage_back_in_the_list_seeds_a_missing_job(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    store.mark_vanished([3], NOW)
    _drop_job(path, media_id)

    assert store.mark_present([3], [], NOW) == 1

    row = _job_row(path, media_id)
    assert row is not None
    assert row["state"] == "queued"


def test_a_storage_back_that_owes_its_proof_seeds_no_job_yet(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    store.mark_vanished([3], NOW)
    _drop_job(path, media_id)

    assert store.mark_present([3], [3], NOW) == 1

    assert _job_row(path, media_id) is None


def test_a_way_back_does_not_reopen_a_settled_job(store: Store, path: Path) -> None:
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert store.finish_preview(job, "no_speech")
    store.apply_intake([_item(11, "trash")])

    store.apply_intake([_item(11, "restore")])

    row = _job_row(path, media_id)
    assert row is not None
    assert (row["state"], row["reason"]) == ("skipped", "no_speech")
