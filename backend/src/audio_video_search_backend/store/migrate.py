"""Schema migrations of state.db, as code and in one transaction each.

v1 to v2 (phase 2, plan 02-02): ``file_ref`` becomes the work stock of the
discovery. SQLite cannot change the type of a column, so the table is built
anew, the rows are copied, the old table is dropped and the new one renamed.
``storage_id`` was TEXT and carries ``''`` for the samples of phase 1
(api/sample.py); v2 keeps the numeric Nextcloud storage id and gives a sample
0. A row with a media item is ``keyed`` (its content key is known), one
without is ``pending``. The samples of phase 1 move to their own layer
``sample_ref`` (D-02-15); a sample row without a media item has no content and
is dropped. ``media`` gains ``head_sha256`` (the first 64 KiB, for
the read proof) and ``orphaned_at`` (the last reference went away).

v2 to v3 (phase 3, plan 03-03): the table ``preview_job`` with its order
index, and ``file_ref.origin`` (event or crawl, D-03-05). Every content with
at least one active, keyed reference gets one job in state ``queued`` with
origin ``crawl`` (the stock was found by the crawl or by events nobody can
tell apart any more), ``sort_mtime`` the newest mtime of its active
references and ``epoch`` the one of its media item. References in the trash,
unreadable ones and samples (D-02-15) give no job (T-03-09).

Every statement runs inside ``BEGIN IMMEDIATE``; any failure rolls the whole
file back to the version it had, so an interrupted update never leaves a half
migrated store (T-02-05, T-03-07). The steps are module constants on purpose:
the tests insert a failing statement between them.
"""

import logging
import sqlite3
import time
from typing import Final

_LOG: Final = logging.getLogger(__name__)

# Must stay identical to the file_ref definition in schema.sql; the test
# compares a migrated file with a fresh one column by column.
FILE_REF_V2: Final = """
CREATE TABLE file_ref_v2 (
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
)
"""

# Must stay identical to the sample_ref definition in schema.sql.
SAMPLE_REF_V2: Final = """
CREATE TABLE sample_ref (
    file_id    INTEGER PRIMARY KEY,
    media_id   INTEGER NOT NULL REFERENCES media (media_id),
    created_at INTEGER NOT NULL
)
"""

V1_TO_V2_STEPS: tuple[str, ...] = (
    FILE_REF_V2,
    SAMPLE_REF_V2,
    """
    INSERT INTO sample_ref (file_id, media_id, created_at)
    SELECT file_id, media_id, updated_at FROM file_ref WHERE state = 'sample' AND media_id IS NOT NULL
    """,
    """
    INSERT INTO file_ref_v2 (file_id, media_id, storage_id, prefilter_key, reader_uid, etag, size, mtime,
                             state, stage, reason, attempts, next_try_at, proved_at, vanished_since, updated_at)
    SELECT file_id, media_id, COALESCE(CAST(NULLIF(storage_id, '') AS INTEGER), 0), NULL, NULL, etag, size,
           mtime, state, CASE WHEN media_id IS NULL THEN 'pending' ELSE 'keyed' END, reason, 0, NULL, NULL,
           NULL, updated_at
    FROM file_ref WHERE state <> 'sample'
    """,
    "DROP TABLE file_ref",
    "ALTER TABLE file_ref_v2 RENAME TO file_ref",
    "CREATE INDEX file_ref_media ON file_ref (media_id)",
    "CREATE INDEX file_ref_storage ON file_ref (storage_id)",
    "CREATE INDEX file_ref_prefilter ON file_ref (prefilter_key) WHERE prefilter_key IS NOT NULL",
    "CREATE INDEX file_ref_stage ON file_ref (stage, next_try_at) WHERE stage <> 'keyed'",
    "CREATE INDEX sample_ref_media ON sample_ref (media_id)",
    "ALTER TABLE media ADD COLUMN head_sha256 TEXT",
    "ALTER TABLE media ADD COLUMN orphaned_at INTEGER",
    "UPDATE meta SET value = '2' WHERE key = 'schema_version'",
)

# Must stay identical to the preview_job definition and its index in schema.sql
# (without IF NOT EXISTS); tests/test_store_migration_v3.py compares both.
PREVIEW_JOB_V3: Final = """
CREATE TABLE preview_job (
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
)
"""
PREVIEW_JOB_ORDER_V3: Final = """
CREATE INDEX preview_job_order
    ON preview_job (state, CASE origin WHEN 'event' THEN 0 ELSE 1 END, sort_mtime DESC, media_id)
"""
# The column definition of file_ref.origin, the last column in schema.sql.
FILE_REF_ORIGIN_V3: Final = "origin TEXT NOT NULL DEFAULT 'crawl' CHECK (origin IN ('event', 'crawl'))"

V2_TO_V3_STEPS: tuple[str, ...] = (
    PREVIEW_JOB_V3,
    PREVIEW_JOB_ORDER_V3,
    f"ALTER TABLE file_ref ADD COLUMN {FILE_REF_ORIGIN_V3}",
    """
    INSERT INTO preview_job (media_id, epoch, state, origin, sort_mtime, updated_at)
    SELECT m.media_id, m.epoch, 'queued', 'crawl', MAX(f.mtime), :now
    FROM media m JOIN file_ref f ON f.media_id = m.media_id
    WHERE f.state = 'active' AND f.stage = 'keyed'
    GROUP BY m.media_id
    """,
    "UPDATE meta SET value = '3' WHERE key = 'schema_version'",
)

_GET_VERSION: Final = "SELECT value FROM meta WHERE key = 'schema_version'"
_HAS_META: Final = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'meta'"


def stored_version(connection: sqlite3.Connection) -> int:
    """The schema version a file carries; 0 for a new, empty file."""
    if connection.execute(_HAS_META).fetchone() is None:
        return 0
    row = connection.execute(_GET_VERSION).fetchone()
    return int(row[0]) if row else 0


def migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    """Lift a v1 file to v2 in one transaction; on any error the file stays v1."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        rows = int(connection.execute("SELECT COUNT(*) FROM file_ref").fetchone()[0])
        for step in V1_TO_V2_STEPS:
            connection.execute(step)
    except BaseException:
        connection.execute("ROLLBACK")
        _LOG.error("store migration failed, the file stays at version 1", extra={"from": 1, "to": 2})
        raise
    connection.execute("COMMIT")
    _LOG.info("store migrated", extra={"from": 1, "to": 2, "file_refs": rows})


def migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    """Lift a v2 file to v3 in one transaction; on any error the file stays v2."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        for step in V2_TO_V3_STEPS:
            connection.execute(step, {"now": int(time.time())})
        jobs = int(connection.execute("SELECT COUNT(*) FROM preview_job").fetchone()[0])
    except BaseException:
        connection.execute("ROLLBACK")
        _LOG.error("store migration failed, the file stays at version 2", extra={"from": 2, "to": 3})
        raise
    connection.execute("COMMIT")
    _LOG.info("store migrated", extra={"from": 2, "to": 3, "preview_jobs": jobs})
