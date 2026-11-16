"""Schema v4 of state.db and the migration from v3 (plan 04-05, D-04-15, T-04-12, T-04-13).

The v3 schema below is a frozen copy of store/schema.sql as phase 3 shipped it
(0.3.0), without its comments, so the migration is tested against the shape
that exists in the field, not against whatever schema.sql says today.

v4 adds the kept words per text language to preview_job (words_de/en/fr) and
the majority language of a file to media (language, only de/en/fr or NULL,
never "und"). The rules around the new columns live here as well: the chunk
write adds the counters, the way back of a too long job clears them, the
verdict transcript stores the majority (ties go de before en before fr),
file_language falls back to the counters of a running preview (D-04-17) and
set_file_language takes only the three languages, once.
"""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.store import migrate
from audio_video_search_backend.store.repo import (
    FILE_LANGUAGES,
    SCHEMA_VERSION,
    ChunkCounters,
    IntakeItem,
    PreviewJob,
    Store,
)
from tests.test_store_migration_v3 import V2_REF, V2_SCHEMA, _normalized, _statement

NOW = 1_800_000_000
HEAD = "9" * 64
MODEL = "d" * 64
SHA = {1: "1" * 64, 2: "2" * 64, 3: "3" * 64}

V3_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media (
    media_id    INTEGER PRIMARY KEY,
    epoch       INTEGER NOT NULL DEFAULT 0 CHECK (epoch >= 0),
    created_at  INTEGER NOT NULL,
    head_sha256 TEXT,
    orphaned_at INTEGER
);
CREATE TABLE IF NOT EXISTS media_key (
    kind     TEXT    NOT NULL,
    value    TEXT    NOT NULL,
    media_id INTEGER NOT NULL REFERENCES media (media_id),
    PRIMARY KEY (kind, value)
);
CREATE TABLE IF NOT EXISTS file_ref (
    file_id        INTEGER PRIMARY KEY,
    media_id       INTEGER REFERENCES media (media_id),
    storage_id     INTEGER NOT NULL,
    prefilter_key  TEXT,
    reader_uid     TEXT,
    etag           TEXT    NOT NULL,
    size           INTEGER NOT NULL,
    mtime          INTEGER NOT NULL,
    state          TEXT    NOT NULL,
    stage          TEXT    NOT NULL,
    reason         TEXT,
    attempts       INTEGER NOT NULL DEFAULT 0,
    next_try_at    INTEGER,
    proved_at      INTEGER,
    vanished_since INTEGER,
    updated_at     INTEGER NOT NULL,
    origin         TEXT    NOT NULL DEFAULT 'crawl' CHECK (origin IN ('event', 'crawl'))
);
CREATE INDEX IF NOT EXISTS file_ref_media ON file_ref (media_id);
CREATE INDEX IF NOT EXISTS file_ref_storage ON file_ref (storage_id);
CREATE INDEX IF NOT EXISTS file_ref_prefilter ON file_ref (prefilter_key) WHERE prefilter_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS file_ref_stage ON file_ref (stage, next_try_at) WHERE stage <> 'keyed';
CREATE TABLE IF NOT EXISTS sample_ref (
    file_id    INTEGER PRIMARY KEY,
    media_id   INTEGER NOT NULL REFERENCES media (media_id),
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sample_ref_media ON sample_ref (media_id);
CREATE TABLE IF NOT EXISTS transcript (
    version_id        INTEGER PRIMARY KEY,
    media_id          INTEGER NOT NULL REFERENCES media (media_id),
    engine            TEXT    NOT NULL,
    model_sha256      TEXT    NOT NULL,
    config_version    INTEGER NOT NULL CHECK (config_version >= 1),
    profile           TEXT    NOT NULL,
    level             INTEGER NOT NULL CHECK (level > 0),
    epoch             INTEGER NOT NULL CHECK (epoch >= 0),
    language          TEXT    NOT NULL,
    input_file_sha256 TEXT    NOT NULL,
    created_at        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS transcript_media ON transcript (media_id);
CREATE TABLE IF NOT EXISTS word (
    version_id INTEGER NOT NULL REFERENCES transcript (version_id),
    idx        INTEGER NOT NULL,
    start_ms   INTEGER NOT NULL,
    end_ms     INTEGER NOT NULL CHECK (end_ms >= start_ms),
    surface    TEXT    NOT NULL,
    norm       TEXT    NOT NULL,
    conf       REAL    NOT NULL,
    src        TEXT    NOT NULL CHECK (src IN ('machine', 'user')),
    PRIMARY KEY (version_id, idx)
);
CREATE TABLE IF NOT EXISTS current (
    media_id       INTEGER PRIMARY KEY REFERENCES media (media_id),
    version_id     INTEGER NOT NULL REFERENCES transcript (version_id),
    epoch          INTEGER NOT NULL,
    level          INTEGER NOT NULL,
    config_version INTEGER NOT NULL,
    index_rev      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS correction (
    correction_id   INTEGER PRIMARY KEY,
    media_id        INTEGER NOT NULL REFERENCES media (media_id),
    start_ms        INTEGER NOT NULL,
    end_ms          INTEGER NOT NULL CHECK (end_ms > start_ms),
    kind            TEXT    NOT NULL CHECK (kind IN ('text', 'speaker', 'sound')),
    body            TEXT    NOT NULL,
    words_json      TEXT,
    base_version_id INTEGER,
    base_text       TEXT,
    author_uid      TEXT    NOT NULL,
    created_at      INTEGER NOT NULL,
    superseded_by   INTEGER REFERENCES correction (correction_id),
    reviewed_at     INTEGER
);
CREATE INDEX IF NOT EXISTS correction_media ON correction (media_id, start_ms) WHERE superseded_by IS NULL;
CREATE TABLE IF NOT EXISTS index_outbox (
    media_id  INTEGER NOT NULL,
    index_rev INTEGER NOT NULL,
    PRIMARY KEY (media_id, index_rev)
);
CREATE TABLE IF NOT EXISTS preview_job (
    media_id      INTEGER PRIMARY KEY REFERENCES media (media_id),
    epoch         INTEGER NOT NULL,
    state         TEXT    NOT NULL CHECK (state IN ('queued', 'running', 'waiting', 'complete', 'skipped')),
    reason        TEXT,
    origin        TEXT    NOT NULL CHECK (origin IN ('event', 'crawl')),
    sort_mtime    INTEGER NOT NULL,
    duration_ms   INTEGER,
    next_start_ms INTEGER NOT NULL DEFAULT 0 CHECK (next_start_ms >= 0),
    chunks_done   INTEGER NOT NULL DEFAULT 0 CHECK (chunks_done >= 0),
    version_id    INTEGER,
    kept_words    INTEGER NOT NULL DEFAULT 0,
    drop_script   INTEGER NOT NULL DEFAULT 0,
    drop_language INTEGER NOT NULL DEFAULT 0,
    drop_conf     INTEGER NOT NULL DEFAULT 0,
    speech_ms     INTEGER NOT NULL DEFAULT 0,
    attempts      INTEGER NOT NULL DEFAULT 0,
    next_try_at   INTEGER,
    second_pass   INTEGER NOT NULL DEFAULT 0,
    updated_at    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS preview_job_order
    ON preview_job (state, CASE origin WHEN 'event' THEN 0 ELSE 1 END, sort_mtime DESC, media_id);
"""

V3_REF = (
    "INSERT INTO file_ref (file_id, media_id, storage_id, reader_uid, etag, size, mtime, state, stage,"
    " updated_at, origin) VALUES (?, ?, 3, ?, 'e', 10, ?, ?, ?, 100, 'crawl')"
)
V3_JOB = (
    "INSERT INTO preview_job (media_id, epoch, state, origin, sort_mtime, duration_ms, next_start_ms,"
    " chunks_done, kept_words, drop_script, drop_language, drop_conf, speech_ms, second_pass, updated_at)"
    " VALUES (?, ?, ?, 'crawl', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 100)"
)


def _make_v3(path: Path) -> None:
    """A v3 database as phase 3 leaves it: one finished preview with counters, one queued job."""
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.executescript(V3_SCHEMA)
        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            [("schema_version", "3"), ("index_generation", "4"), ("index_schema_version", "1")],
        )
        conn.executemany(
            "INSERT INTO media (media_id, epoch, created_at) VALUES (?, ?, 50)",
            [(1, 2), (2, 0)],
        )
        conn.executemany(
            V3_REF,
            [(10, 1, "ana", 300, "active", "keyed"), (20, 2, "ben", 500, "active", "keyed")],
        )
        conn.execute(V3_JOB, (1, 2, "complete", 300, 60_000, 60_000, 2, 7, 1, 2, 3, 1000, 1))
        conn.execute(V3_JOB, (2, 0, "queued", 500, None, 0, 0, 0, 0, 0, 0, 0, 0))


def _dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as conn:
        return list(conn.iterdump())


def _columns(path: Path, table: str) -> list[str]:
    with closing(sqlite3.connect(path)) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _sql(path: Path, statement: str, values: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    with closing(sqlite3.connect(path)) as conn, conn:
        return conn.execute(statement, values).fetchall()


def _language(path: Path, media_id: int) -> str | None:
    rows = _sql(path, "SELECT language FROM media WHERE media_id = ?", (media_id,))
    assert len(rows) == 1
    value = rows[0][0]
    return None if value is None else str(value)


def _job_row(path: Path, media_id: int) -> dict[str, Any]:
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM preview_job WHERE media_id = ?", (media_id,)).fetchone()
    assert row is not None
    return dict(row)


# -- helpers that seed through the public API, the way the capture does ------------


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state.db"


@pytest.fixture
def store(path: Path) -> Iterator[Store]:
    opened = Store.open(path)
    yield opened
    opened.close()


def _item(file_id: int, **fields: Any) -> IntakeItem:
    values: dict[str, Any] = {
        "storage_id": 3,
        "etag": "e1",
        "size": 1000,
        "mtime": 1_700_000_000,
        "prefilter_key": None,
        "reader_uid": "ana",
    }
    values.update(fields)
    return IntakeItem(queue_id=file_id, kind="content", file_id=file_id, **values)


def _keyed(store: Store, file_id: int, sha256: str) -> int:
    store.apply_intake([_item(file_id)])
    claimed = store.next_capture(NOW)
    assert claimed is not None
    media_id = store.mark_keyed(claimed, sha256, HEAD, NOW)
    assert media_id is not None
    return media_id


def _claim(store: Store) -> PreviewJob:
    job = store.next_preview(NOW)
    assert job is not None
    return job


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


def _counted(de: int = 0, en: int = 0, fr: int = 0) -> ChunkCounters:
    return ChunkCounters(
        kept_words=de + en + fr,
        drop_script=0,
        drop_language=0,
        drop_conf=0,
        speech_ms=0,
        words_de=de,
        words_en=en,
        words_fr=fr,
    )


def _running(store: Store, *, de: int = 0, en: int = 0, fr: int = 0, next_start: int = 600_000) -> PreviewJob:
    """One running job whose counters already hold the given words."""
    media_id = _keyed(store, 11, SHA[1])
    job = _claim(store)
    assert job.media_id == media_id
    counters = _counted(de, en, fr)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[], next_start_ms=next_start, counters=counters)
    return job


# -- the migration ------------------------------------------------------------------


def test_a_fresh_file_has_the_language_columns(path: Path) -> None:
    Store.open(path).close()

    assert _columns(path, "preview_job")[-3:] == ["words_de", "words_en", "words_fr"]
    assert _columns(path, "media")[-1] == "language"
    with closing(sqlite3.connect(path)) as conn:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    assert meta["schema_version"] == str(SCHEMA_VERSION)


def test_the_migration_constants_are_the_statements_of_schema_sql() -> None:
    preview_job = _normalized(_statement("preview_job", "TABLE"))
    for column in migrate.PREVIEW_WORDS_V4:
        assert _normalized(column) in preview_job
    assert _normalized(migrate.MEDIA_LANGUAGE_V4) in _normalized(_statement("media", "TABLE"))


def test_a_v3_file_is_lifted_to_v4_with_its_data_untouched(path: Path) -> None:
    _make_v3(path)

    store = Store.open(path)
    try:
        assert store.schema_version() == SCHEMA_VERSION
    finally:
        store.close()

    done = _job_row(path, 1)
    assert (done["state"], done["chunks_done"], done["kept_words"], done["speech_ms"]) == ("complete", 2, 7, 1000)
    assert (done["drop_script"], done["drop_language"], done["drop_conf"], done["second_pass"]) == (1, 2, 3, 1)
    assert (done["words_de"], done["words_en"], done["words_fr"]) == (0, 0, 0)
    queued = _job_row(path, 2)
    assert (queued["state"], queued["words_de"], queued["words_en"], queued["words_fr"]) == ("queued", 0, 0, 0)
    assert _language(path, 1) is None
    assert _language(path, 2) is None
    with closing(sqlite3.connect(path)) as conn:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    assert meta == {"schema_version": str(SCHEMA_VERSION), "index_generation": "4", "index_schema_version": "1"}


def test_a_v2_file_runs_through_to_v4(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.executescript(V2_SCHEMA)
        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            [("schema_version", "2"), ("index_generation", "4"), ("index_schema_version", "1")],
        )
        conn.execute("INSERT INTO media (media_id, epoch, created_at) VALUES (1, 0, 50)")
        conn.execute(V2_REF, (10, 1, 100, "active", "keyed"))

    store = Store.open(path)
    try:
        assert store.schema_version() == SCHEMA_VERSION
    finally:
        store.close()

    assert _job_row(path, 1)["words_de"] == 0
    assert _language(path, 1) is None


def test_a_fresh_file_and_a_migrated_v3_file_have_the_same_schema(tmp_path: Path) -> None:
    fresh, migrated = tmp_path / "fresh.db", tmp_path / "migrated.db"
    Store.open(fresh).close()
    _make_v3(migrated)
    Store.open(migrated).close()

    def shape(path: Path) -> dict[str, list[tuple[object, ...]]]:
        with closing(sqlite3.connect(path)) as conn:
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            return {table: conn.execute(f"PRAGMA table_info({table})").fetchall() for table in sorted(tables)}

    assert shape(migrated) == shape(fresh)


def test_a_failure_inside_the_migration_leaves_v3_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "state.db"
    _make_v3(path)
    before = _dump(path)
    steps = list(migrate.V3_TO_V4_STEPS)
    # After the four new columns: every change of the schema is made, the
    # version mark is not.
    steps.insert(4, "INSERT INTO no_such_table VALUES (1)")
    monkeypatch.setattr(migrate, "V3_TO_V4_STEPS", tuple(steps))

    with caplog.at_level(logging.ERROR, logger=migrate.__name__), pytest.raises(sqlite3.OperationalError):
        Store.open(path)

    assert _dump(path) == before
    assert "words_de" not in _columns(path, "preview_job")
    assert "language" not in _columns(path, "media")
    assert _sql(path, "SELECT value FROM meta WHERE key = 'schema_version'") == [("3",)]
    failed = [record for record in caplog.records if record.getMessage().startswith("store migration failed")]
    assert len(failed) == 1
    assert (failed[0].__dict__["from"], failed[0].__dict__["to"]) == (3, 4)


def test_the_failure_step_lands_after_the_schema_changes() -> None:
    # Positive control for the test above: the inserted failure really comes
    # after the four ALTER TABLE steps, right before the version mark.
    steps = migrate.V3_TO_V4_STEPS
    assert len(steps) == 5
    for step, column in zip(steps[:3], migrate.PREVIEW_WORDS_V4, strict=True):
        assert step.strip() == f"ALTER TABLE preview_job ADD COLUMN {column}"
    assert steps[3].strip() == f"ALTER TABLE media ADD COLUMN {migrate.MEDIA_LANGUAGE_V4}"
    assert steps[-1].strip() == "UPDATE meta SET value = '4' WHERE key = 'schema_version'"


def test_a_reader_never_migrates_a_v3_file(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v3(path)
    before = _dump(path)

    with pytest.raises(RuntimeError, match="unsupported store schema version 3"):
        Store.open(path, read_only=True)

    assert _dump(path) == before


def test_a_newer_schema_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v3(path)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("UPDATE meta SET value = '5' WHERE key = 'schema_version'")
    before = _dump(path)

    with pytest.raises(RuntimeError, match="unsupported store schema version 5"):
        Store.open(path)

    assert _dump(path) == before


# -- the closed list of the file language (T-04-13) ---------------------------------


def test_the_check_constraint_takes_only_the_three_languages(path: Path, store: Store) -> None:
    media_id = _keyed(store, 11, SHA[1])

    for wrong in ("und", "tr", ""):
        with pytest.raises(sqlite3.IntegrityError):
            _sql(path, "UPDATE media SET language = ? WHERE media_id = ?", (wrong, media_id))
    # Positive control: the three languages and NULL pass.
    for value in (*FILE_LANGUAGES, None):
        _sql(path, "UPDATE media SET language = ? WHERE media_id = ?", (value, media_id))


# -- the counters of the chunks ------------------------------------------------------


def test_a_chunk_adds_the_language_counters(path: Path, store: Store) -> None:
    job = _running(store, de=3, en=1)
    assert store.commit_chunk(job, prov=_prov(SHA[1]), words=[], next_start_ms=1_200_000, counters=_counted(de=1, fr=2))

    row = _job_row(path, job.media_id)
    assert (row["words_de"], row["words_en"], row["words_fr"]) == (4, 1, 2)
    assert row["kept_words"] == 7


def test_a_negative_language_counter_is_refused(store: Store) -> None:
    job = _running(store)
    bad = ChunkCounters(kept_words=0, drop_script=0, drop_language=0, drop_conf=0, speech_ms=0, words_de=-1)
    with pytest.raises(ValueError, match="counters"):
        store.commit_chunk(job, prov=_prov(SHA[1]), words=[], next_start_ms=1_200_000, counters=bad)


def test_the_way_back_of_a_too_long_job_clears_the_language_counters(path: Path, store: Store) -> None:
    job = _running(store, de=3, en=1)
    assert store.skip_preview(job, "too_long", 120_000)

    assert store.requeue_too_long(600_000) == 1

    row = _job_row(path, job.media_id)
    assert (row["state"], row["next_start_ms"], row["chunks_done"]) == ("queued", 0, 0)
    assert (row["words_de"], row["words_en"], row["words_fr"]) == (0, 0, 0)


# -- the majority at the verdict (D-04-15) -------------------------------------------


@pytest.mark.parametrize(
    ("de", "en", "fr", "expected"),
    [
        (3, 1, 0, "de"),
        (1, 3, 0, "en"),
        (0, 1, 3, "fr"),
        (2, 2, 0, "de"),
        (0, 2, 2, "en"),
        (1, 1, 1, "de"),
    ],
    ids=["de", "en", "fr", "tie-de-en", "tie-en-fr", "tie-all"],
)
def test_the_verdict_transcript_stores_the_majority(
    path: Path, store: Store, de: int, en: int, fr: int, expected: str
) -> None:
    job = _running(store, de=de, en=en, fr=fr)

    assert store.finish_preview(job, "transcript")

    assert _language(path, job.media_id) == expected


def test_a_sum_of_zero_leaves_the_language_null(path: Path, store: Store) -> None:
    job = _running(store)

    assert store.finish_preview(job, "transcript")

    assert _language(path, job.media_id) is None


def test_other_verdicts_leave_the_language_alone(path: Path, store: Store) -> None:
    job = _running(store, de=5)

    assert store.finish_preview(job, "no_speech")

    assert _language(path, job.media_id) is None


def test_a_stale_verdict_stores_no_language(path: Path, store: Store) -> None:
    job = _running(store, de=5)
    _sql(path, "UPDATE media SET epoch = epoch + 1 WHERE media_id = ?", (job.media_id,))

    assert not store.finish_preview(job, "transcript")

    assert _language(path, job.media_id) is None


def test_the_verdict_overwrites_an_earlier_fallback(path: Path, store: Store) -> None:
    # The finished transcript knows the whole file; it beats the fallback of
    # the export over a part of it (D-04-15, D-04-17).
    job = _running(store, de=5)
    assert store.set_file_language(job.media_id, "fr")

    assert store.finish_preview(job, "transcript")

    assert _language(path, job.media_id) == "de"


# -- file_language and set_file_language (D-04-15, D-04-17) --------------------------


def test_file_language_prefers_the_stored_language(store: Store) -> None:
    job = _running(store, en=5)
    assert store.set_file_language(job.media_id, "fr")

    assert store.file_language(job.media_id) == "fr"


def test_file_language_falls_back_to_the_running_counters(store: Store) -> None:
    job = _running(store, de=1, en=3)

    assert store.file_language(job.media_id) == "en"


def test_file_language_without_a_trace_is_none(store: Store) -> None:
    media_id = _keyed(store, 11, SHA[1])

    assert store.file_language(media_id) is None
    assert store.file_language(999) is None


@pytest.mark.parametrize("wrong", ["und", "tr", "", "DE", "deutsch"])
def test_set_file_language_refuses_everything_but_the_three(store: Store, wrong: str) -> None:
    media_id = _keyed(store, 11, SHA[1])

    with pytest.raises(ValueError, match="language"):
        store.set_file_language(media_id, wrong)

    assert store.file_language(media_id) is None


def test_the_first_determination_wins(path: Path, store: Store) -> None:
    media_id = _keyed(store, 11, SHA[1])

    assert store.set_file_language(media_id, "en")
    assert not store.set_file_language(media_id, "fr")

    assert _language(path, media_id) == "en"
