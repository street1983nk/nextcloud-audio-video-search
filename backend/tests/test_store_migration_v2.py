"""Schema v2 of state.db and the migration from v1 (plan 02-02, T-02-05, T-02-06).

The v1 schema below is a frozen copy of store/schema.sql as phase 1 shipped it
(0.1.0), so the migration is tested against the shape that exists in the field,
not against whatever schema.sql says today.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from audio_video_search_backend.store import migrate
from audio_video_search_backend.store.repo import SCHEMA_VERSION, STAGES, STATES, Store

SHA_A = "a" * 64
MODEL = "d" * 64

V1_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media (
    media_id   INTEGER PRIMARY KEY,
    epoch      INTEGER NOT NULL DEFAULT 0 CHECK (epoch >= 0),
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS media_key (
    kind     TEXT    NOT NULL,
    value    TEXT    NOT NULL,
    media_id INTEGER NOT NULL REFERENCES media (media_id),
    PRIMARY KEY (kind, value)
);
CREATE TABLE IF NOT EXISTS file_ref (
    file_id    INTEGER PRIMARY KEY,
    media_id   INTEGER REFERENCES media (media_id),
    storage_id TEXT    NOT NULL,
    etag       TEXT    NOT NULL,
    size       INTEGER NOT NULL,
    mtime      INTEGER NOT NULL,
    state      TEXT    NOT NULL,
    reason     TEXT,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS file_ref_media ON file_ref (media_id);
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

V1_REF = (
    "INSERT INTO file_ref (file_id, media_id, storage_id, etag, size, mtime, state, reason, updated_at)"
    " VALUES (?, ?, ?, ?, ?, ?, 'sample', ?, 100)"
)


def _make_v1(path: Path) -> None:
    """A v1 database with a sample, a transcript, its words, a correction and index work."""
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.executescript(V1_SCHEMA)
        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            [("schema_version", "1"), ("index_generation", "3"), ("index_schema_version", "1")],
        )
        conn.execute("INSERT INTO media (media_id, epoch, created_at) VALUES (5, 0, 100)")
        conn.execute("INSERT INTO media_key (kind, value, media_id) VALUES ('file_sha256', ?, 5)", (SHA_A,))
        conn.execute(V1_REF, (42, 5, "", "", 1234, 0, "sample"))
        conn.execute(V1_REF, (43, None, "7", "e", 10, 1, None))
        conn.execute(
            "INSERT INTO transcript (version_id, media_id, engine, model_sha256, config_version, profile, level,"
            " epoch, language, input_file_sha256, created_at)"
            " VALUES (9, 5, 'sample', ?, 1, 'debug', 1, 0, 'de', ?, 100)",
            (MODEL, SHA_A),
        )
        conn.executemany(
            "INSERT INTO word (version_id, idx, start_ms, end_ms, surface, norm, conf, src)"
            " VALUES (9, ?, ?, ?, ?, ?, 1.0, 'machine')",
            [(0, 0, 400, "Dies", "dies"), (1, 400, 750, "ist", "ist")],
        )
        conn.execute(
            "INSERT INTO current (media_id, version_id, epoch, level, config_version, index_rev)"
            " VALUES (5, 9, 0, 1, 1, 2)"
        )
        conn.execute(
            "INSERT INTO correction (correction_id, media_id, start_ms, end_ms, kind, body, author_uid, created_at)"
            " VALUES (1, 5, 0, 400, 'text', 'Das', 'alice', 100)"
        )
        conn.execute("INSERT INTO index_outbox (media_id, index_rev) VALUES (5, 2)")


KEPT = ("media_key", "transcript", "word", "current", "correction", "index_outbox")


_ALL_ROWS = {
    table: f"SELECT * FROM {table} ORDER BY 1, 2"  # noqa: S608 - fixed table names of this test
    for table in ("media", "sample_ref", *KEPT)
}


def _rows(path: Path, table: str) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(_ALL_ROWS[table]).fetchall()


def _columns(path: Path, table: str) -> list[str]:
    with closing(sqlite3.connect(path)) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as conn:
        return list(conn.iterdump())


def test_the_schema_version_is_two() -> None:
    assert SCHEMA_VERSION == 2


def test_a_v1_file_is_lifted_to_v2_without_loss(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v1(path)
    before = {table: _rows(path, table) for table in KEPT}

    store = Store.open(path)
    try:
        assert store.schema_version() == 2
        sample_ref = store.file_ref(42)
        sample_media = store.sample_media(42)
        other = store.file_ref(43)
    finally:
        store.close()

    # D-02-15: v1 knew only samples (phase 1). They move to their own layer;
    # a sample without a media item has no content and is dropped, so file_ref
    # starts empty.
    assert sample_ref is None
    assert other is None
    assert sample_media == 5
    assert _rows(path, "sample_ref") == [(42, 5, 100)]
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM file_ref").fetchone()[0] == 0
    for table in KEPT:
        assert _rows(path, table) == before[table], table
    assert _rows(path, "media") == [(5, 0, 100, None, None)]
    assert _columns(path, "media")[-2:] == ["head_sha256", "orphaned_at"]
    with closing(sqlite3.connect(path)) as conn:
        storage_type = {row[1]: row[2] for row in conn.execute("PRAGMA table_info(file_ref)")}["storage_id"]
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    assert storage_type == "INTEGER"
    assert {"file_ref_media", "file_ref_storage", "file_ref_prefilter", "file_ref_stage"} <= indexes
    assert meta == {"schema_version": "2", "index_generation": "3", "index_schema_version": "1"}


def test_the_sample_still_finds_its_file_after_the_migration(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v1(path)
    store = Store.open(path)
    try:
        assert store.file_ids_for_media(5) == [42]
        assert store.effective_words(5)[0].surface == "Das"
    finally:
        store.close()


def test_a_failure_inside_the_migration_leaves_v1_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "state.db"
    _make_v1(path)
    before = _dump(path)
    steps = list(migrate.V1_TO_V2_STEPS)
    # After the copy and the drop of the old table: the worst moment to fail.
    drop = next(i for i, step in enumerate(steps) if step.startswith("DROP TABLE file_ref"))
    steps.insert(drop + 1, "INSERT INTO no_such_table VALUES (1)")
    monkeypatch.setattr(migrate, "V1_TO_V2_STEPS", tuple(steps))

    with pytest.raises(sqlite3.OperationalError):
        Store.open(path)

    assert _dump(path) == before


def test_a_second_open_is_a_no_op(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v1(path)
    Store.open(path).close()
    after_first = _dump(path)

    Store.open(path).close()

    assert _dump(path) == after_first


def test_a_newer_schema_is_refused_with_a_clear_message(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v1(path)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("UPDATE meta SET value = '3' WHERE key = 'schema_version'")
    before = _dump(path)

    with pytest.raises(RuntimeError, match="unsupported store schema version 3"):
        Store.open(path)

    assert _dump(path) == before


def test_a_reader_never_migrates(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _make_v1(path)
    before = _dump(path)

    with pytest.raises(RuntimeError, match="unsupported store schema version 1"):
        Store.open(path, read_only=True)

    assert _dump(path) == before


def test_a_fresh_file_is_v2_at_once(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    Store.open(path).close()

    assert "proved_at" in _columns(path, "file_ref")
    assert _columns(path, "media")[-2:] == ["head_sha256", "orphaned_at"]


def test_a_fresh_file_and_a_migrated_file_have_the_same_schema(tmp_path: Path) -> None:
    fresh, migrated = tmp_path / "fresh.db", tmp_path / "migrated.db"
    Store.open(fresh).close()
    _make_v1(migrated)
    Store.open(migrated).close()

    def shape(path: Path) -> dict[str, list[tuple[object, ...]]]:
        with closing(sqlite3.connect(path)) as conn:
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            return {table: conn.execute(f"PRAGMA table_info({table})").fetchall() for table in sorted(tables)}

    def indexes(path: Path) -> set[tuple[str, str]]:
        with closing(sqlite3.connect(path)) as conn:
            return set(
                conn.execute("SELECT name, tbl_name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
            )

    assert shape(migrated) == shape(fresh)
    assert indexes(migrated) == indexes(fresh)


# -- upsert_file_ref: closed lists and bounds ------------------------------------


def _ref(store: Store, file_id: int, **changes: object) -> None:
    fields: dict[str, object] = {
        "storage_id": 3,
        "etag": "e",
        "size": 10,
        "mtime": 1,
        "state": "active",
        "stage": "pending",
        "reason": None,
    }
    fields.update(changes)
    store.upsert_file_ref(file_id, None, **fields)  # type: ignore[arg-type]


def test_the_closed_lists() -> None:
    assert frozenset({"active", "unreadable", "vanished", "trashed"}) == STATES
    assert frozenset({"pending", "probing", "fetching", "keyed", "failed"}) == STAGES


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("state", "deleted"),
        ("stage", "transcribing"),
        ("reason", "Sitzung.mp4"),
        ("prefilter_key", "A" * 64),
        ("prefilter_key", "a" * 63),
        ("reader_uid", ""),
        ("reader_uid", "u" * 65),
        ("storage_id", -1),
        ("storage_id", "7"),
        ("storage_id", True),
        ("attempts", -1),
    ],
)
def test_upsert_file_ref_refuses_a_value_outside_its_list(store: Store, field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        _ref(store, 1, **{field: value})
    assert store.file_ref(1) is None


def test_upsert_file_ref_stores_every_field(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA_A)
    store.upsert_file_ref(
        7,
        media_id,
        storage_id=12,
        etag="e7",
        size=99,
        mtime=5,
        state="unreadable",
        stage="failed",
        reason="read_denied",
        prefilter_key="b" * 64,
        reader_uid="ben",
        attempts=2,
        next_try_at=1000,
        proved_at=900,
        vanished_since=None,
    )
    ref = store.file_ref(7)
    assert ref is not None
    assert (ref.media_id, ref.storage_id, ref.etag, ref.size, ref.mtime) == (media_id, 12, "e7", 99, 5)
    assert (ref.state, ref.stage, ref.reason, ref.attempts) == ("unreadable", "failed", "read_denied", 2)
    assert (ref.prefilter_key, ref.reader_uid, ref.next_try_at, ref.proved_at) == ("b" * 64, "ben", 1000, 900)


@pytest.mark.parametrize("state", ["unreadable", "vanished", "trashed"])
def test_only_active_references_and_samples_give_hits(store: Store, state: str) -> None:
    media_id = store.media_for_file_sha256(SHA_A)
    common: dict[str, object] = {"etag": "", "size": 1, "mtime": 0, "stage": "keyed"}
    store.upsert_file_ref(1, media_id, storage_id=1, state="active", reason=None, **common)  # type: ignore[arg-type]
    store.put_sample(2, media_id)
    store.upsert_file_ref(3, media_id, storage_id=1, state=state, reason=None, **common)  # type: ignore[arg-type]

    assert store.file_ids_for_media(media_id) == [1, 2]
