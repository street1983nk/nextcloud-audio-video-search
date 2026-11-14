"""Schema v3 of state.db and the migration from v2 (plan 03-03, T-03-07, T-03-09).

The v2 schema below is a frozen copy of store/schema.sql as phase 2 shipped it
(0.2.0), without its comments, so the migration is tested against the shape
that exists in the field, not against whatever schema.sql says today.
"""

import logging
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from audio_video_search_backend.store import migrate
from audio_video_search_backend.store.repo import SCHEMA_VERSION, Store

SCHEMA_SQL = Path(migrate.__file__).with_name("schema.sql")

V2_SCHEMA = """
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
    updated_at     INTEGER NOT NULL
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
"""

PREVIEW_COLUMNS = [
    "media_id",
    "epoch",
    "state",
    "reason",
    "origin",
    "sort_mtime",
    "duration_ms",
    "next_start_ms",
    "chunks_done",
    "version_id",
    "kept_words",
    "drop_script",
    "drop_language",
    "drop_conf",
    "speech_ms",
    "attempts",
    "next_try_at",
    "second_pass",
    "updated_at",
]

V2_REF = (
    "INSERT INTO file_ref (file_id, media_id, storage_id, etag, size, mtime, state, stage, updated_at)"
    " VALUES (?, ?, 3, 'e', 10, ?, ?, ?, 100)"
)


def _make_v2(path: Path) -> None:
    """A v2 database as phase 2 leaves it.

    Content 1 has two active keyed copies (mtime 100 and 300) and a third one in
    the trash with a later mtime; content 2 only has a copy in the trash;
    content 3 only a copy that owes its read proof (unreadable, probing);
    content 4 only a sample of the walking skeleton (D-02-15). Only content 1
    may get a preview job, and its sort time is the newest active copy.
    """
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.executescript(V2_SCHEMA)
        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            [("schema_version", "2"), ("index_generation", "4"), ("index_schema_version", "1")],
        )
        conn.executemany(
            "INSERT INTO media (media_id, epoch, created_at) VALUES (?, ?, 50)",
            [(1, 2), (2, 0), (3, 0), (4, 0)],
        )
        conn.executemany(
            V2_REF,
            [
                (10, 1, 100, "active", "keyed"),
                (11, 1, 300, "active", "keyed"),
                (12, 1, 999, "trashed", "keyed"),
                (20, 2, 500, "trashed", "keyed"),
                (30, 3, 700, "unreadable", "probing"),
                (40, None, 800, "active", "pending"),
            ],
        )
        conn.execute("INSERT INTO sample_ref (file_id, media_id, created_at) VALUES (90, 4, 100)")


def _dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as conn:
        return list(conn.iterdump())


def _tables(path: Path) -> set[str]:
    with closing(sqlite3.connect(path)) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _columns(path: Path, table: str) -> list[str]:
    with closing(sqlite3.connect(path)) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _jobs(path: Path) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(
            "SELECT media_id, epoch, state, origin, sort_mtime, next_start_ms, chunks_done, second_pass"
            " FROM preview_job ORDER BY media_id"
        ).fetchall()


def _normalized(sql: str) -> str:
    """SQL without comments, IF NOT EXISTS and differences in white space."""
    without_comments = re.sub(r"--[^\n]*", "", sql)
    flat = " ".join(without_comments.replace("IF NOT EXISTS ", "").split())
    return flat.replace("( ", "(").replace(" )", ")").rstrip(";").strip()


def _statement(name: str, keyword: str) -> str:
    """The one statement of schema.sql that creates ``name``."""
    text = SCHEMA_SQL.read_text(encoding="utf-8")
    match = re.search(rf"CREATE {keyword} IF NOT EXISTS {name}\b.*?;", text, re.DOTALL)
    assert match is not None, name
    return match.group(0)


def test_the_schema_version_is_three() -> None:
    assert SCHEMA_VERSION == 3


def test_a_fresh_file_has_the_preview_job_table_and_its_order(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    Store.open(path).close()

    assert _columns(path, "preview_job") == PREVIEW_COLUMNS
    assert _columns(path, "file_ref")[-1] == "origin"
    with closing(sqlite3.connect(path)) as conn:
        order = conn.execute(
            "SELECT tbl_name FROM sqlite_master WHERE type = 'index' AND name = 'preview_job_order'"
        ).fetchone()
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    assert order == ("preview_job",)
    assert meta["schema_version"] == "3"


def test_the_migration_constants_are_the_statements_of_schema_sql() -> None:
    assert _normalized(migrate.PREVIEW_JOB_V3) == _normalized(_statement("preview_job", "TABLE"))
    assert _normalized(migrate.PREVIEW_JOB_ORDER_V3) == _normalized(_statement("preview_job_order", "INDEX"))
    assert _normalized(migrate.FILE_REF_ORIGIN_V3) in _normalized(_statement("file_ref", "TABLE"))


def test_a_v2_file_is_lifted_to_v3_and_seeds_one_job_per_active_content(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v2(path)

    store = Store.open(path)
    try:
        assert store.schema_version() == 3
    finally:
        store.close()

    # Only content 1: its copies in the trash, the owed proof, the pending copy
    # without a content and the sample give no job (T-03-09). Sort time is the
    # newest active copy, never the copy in the trash.
    jobs = _jobs(path)
    assert jobs == [(1, 2, "queued", "crawl", 300, 0, 0, 0)]
    with closing(sqlite3.connect(path)) as conn:
        origins = conn.execute("SELECT DISTINCT origin FROM file_ref").fetchall()
        refs = conn.execute("SELECT COUNT(*) FROM file_ref").fetchone()[0]
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        updated = conn.execute("SELECT updated_at FROM preview_job").fetchone()[0]
    assert origins == [("crawl",)]
    assert refs == 6
    assert meta == {"schema_version": "3", "index_generation": "4", "index_schema_version": "1"}
    assert updated > 0


def test_the_migration_logs_counts_only(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = tmp_path / "state.db"
    _make_v2(path)

    with caplog.at_level(logging.INFO, logger=migrate.__name__):
        Store.open(path).close()

    done = [record for record in caplog.records if record.getMessage() == "store migrated"]
    assert len(done) == 1
    assert (done[0].__dict__["from"], done[0].__dict__["to"], done[0].__dict__["preview_jobs"]) == (2, 3, 1)


def test_a_fresh_file_and_a_migrated_v2_file_have_the_same_schema(tmp_path: Path) -> None:
    fresh, migrated = tmp_path / "fresh.db", tmp_path / "migrated.db"
    Store.open(fresh).close()
    _make_v2(migrated)
    Store.open(migrated).close()

    def shape(path: Path) -> dict[str, list[tuple[object, ...]]]:
        with closing(sqlite3.connect(path)) as conn:
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            return {table: conn.execute(f"PRAGMA table_info({table})").fetchall() for table in sorted(tables)}

    def indexes(path: Path) -> dict[str, list[tuple[object, ...]]]:
        with closing(sqlite3.connect(path)) as conn:
            names = [
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
            ]
            return {name: conn.execute(f"PRAGMA index_xinfo({name})").fetchall() for name in sorted(names)}

    assert shape(migrated) == shape(fresh)
    assert indexes(migrated) == indexes(fresh)
    assert "preview_job_order" in indexes(migrated)


@pytest.mark.parametrize(
    ("statement", "values"),
    [
        ("UPDATE file_ref SET origin = ? WHERE file_id = 10", ("upload",)),
        ("UPDATE preview_job SET state = ? WHERE media_id = 1", ("done",)),
        ("UPDATE preview_job SET origin = ? WHERE media_id = 1", ("upload",)),
        ("UPDATE preview_job SET next_start_ms = ? WHERE media_id = 1", (-1,)),
        ("UPDATE preview_job SET chunks_done = ? WHERE media_id = 1", (-1,)),
    ],
)
def test_the_migrated_file_keeps_the_closed_lists(tmp_path: Path, statement: str, values: tuple[object]) -> None:
    path = tmp_path / "state.db"
    _make_v2(path)
    Store.open(path).close()

    with closing(sqlite3.connect(path)) as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute(statement, values)


def test_the_migrated_file_takes_every_state_of_the_list(tmp_path: Path) -> None:
    # Positive control for the CHECK above: the five states and both origins pass.
    path = tmp_path / "state.db"
    _make_v2(path)
    Store.open(path).close()

    with closing(sqlite3.connect(path)) as conn, conn:
        for state in ("queued", "running", "waiting", "complete", "skipped"):
            conn.execute("UPDATE preview_job SET state = ? WHERE media_id = 1", (state,))
        for origin in ("event", "crawl"):
            conn.execute("UPDATE preview_job SET origin = ? WHERE media_id = 1", (origin,))
            conn.execute("UPDATE file_ref SET origin = ? WHERE file_id = 10", (origin,))


def test_a_failure_inside_the_migration_leaves_v2_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "state.db"
    _make_v2(path)
    before = _dump(path)
    steps = list(migrate.V2_TO_V3_STEPS)
    # After the table, its index and the new column: every change of the
    # schema is made, the seed and the version mark are not.
    steps.insert(3, "INSERT INTO no_such_table VALUES (1)")
    monkeypatch.setattr(migrate, "V2_TO_V3_STEPS", tuple(steps))

    with pytest.raises(sqlite3.OperationalError):
        Store.open(path)

    assert _dump(path) == before
    assert "preview_job" not in _tables(path)
    assert "origin" not in _columns(path, "file_ref")
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone() == ("2",)


def test_the_failure_step_lands_after_the_schema_changes() -> None:
    # Positive control for the test above: the inserted failure really comes
    # after the three schema steps, not before the first one.
    steps = migrate.V2_TO_V3_STEPS
    assert steps[0].lstrip().startswith("CREATE TABLE preview_job")
    assert steps[1].lstrip().startswith("CREATE INDEX preview_job_order")
    assert steps[2].lstrip().startswith("ALTER TABLE file_ref ADD COLUMN origin")
    assert "INSERT INTO preview_job" in steps[3]
    assert steps[-1].strip() == "UPDATE meta SET value = '3' WHERE key = 'schema_version'"


def test_a_second_open_is_a_no_op(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v2(path)
    Store.open(path).close()
    after_first = _dump(path)

    Store.open(path).close()

    assert _dump(path) == after_first


def test_a_reader_never_migrates_a_v2_file(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v2(path)
    before = _dump(path)

    with pytest.raises(RuntimeError, match="unsupported store schema version 2"):
        Store.open(path, read_only=True)

    assert _dump(path) == before


def test_a_newer_schema_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v2(path)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("UPDATE meta SET value = '4' WHERE key = 'schema_version'")
    before = _dump(path)

    with pytest.raises(RuntimeError, match="unsupported store schema version 4"):
        Store.open(path)

    assert _dump(path) == before
