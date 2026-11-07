"""Schema migrations of state.db, as code and in one transaction each.

v1 to v2 (phase 2, plan 02-02): ``file_ref`` becomes the work stock of the
discovery. SQLite cannot change the type of a column, so the table is built
anew, the rows are copied, the old table is dropped and the new one renamed.
``storage_id`` was TEXT and carries ``''`` for the samples of phase 1
(api/sample.py); v2 keeps the numeric Nextcloud storage id and gives a sample
0. A row with a media item is ``keyed`` (its content key is known), one
without is ``pending``. ``media`` gains ``head_sha256`` (the first 64 KiB, for
the read proof) and ``orphaned_at`` (the last reference went away).

Every statement runs inside ``BEGIN IMMEDIATE``; any failure rolls the whole
file back to v1, so an interrupted update never leaves a half migrated store
(T-02-05). The steps are a module constant on purpose: the test inserts a
failing statement between them.
"""

import logging
import sqlite3
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

V1_TO_V2_STEPS: tuple[str, ...] = (
    FILE_REF_V2,
    """
    INSERT INTO file_ref_v2 (file_id, media_id, storage_id, prefilter_key, reader_uid, etag, size, mtime,
                             state, stage, reason, attempts, next_try_at, proved_at, vanished_since, updated_at)
    SELECT file_id, media_id, COALESCE(CAST(NULLIF(storage_id, '') AS INTEGER), 0), NULL, NULL, etag, size,
           mtime, state, CASE WHEN media_id IS NULL THEN 'pending' ELSE 'keyed' END, reason, 0, NULL, NULL,
           NULL, updated_at
    FROM file_ref
    """,
    "DROP TABLE file_ref",
    "ALTER TABLE file_ref_v2 RENAME TO file_ref",
    "CREATE INDEX file_ref_media ON file_ref (media_id)",
    "CREATE INDEX file_ref_storage ON file_ref (storage_id)",
    "CREATE INDEX file_ref_prefilter ON file_ref (prefilter_key) WHERE prefilter_key IS NOT NULL",
    "CREATE INDEX file_ref_stage ON file_ref (stage, next_try_at) WHERE stage <> 'keyed'",
    "ALTER TABLE media ADD COLUMN head_sha256 TEXT",
    "ALTER TABLE media ADD COLUMN orphaned_at INTEGER",
    "UPDATE meta SET value = '2' WHERE key = 'schema_version'",
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
