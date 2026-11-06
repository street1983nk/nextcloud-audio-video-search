-- The operating state of the backend: $APP_PERSISTENT_STORAGE/state.db
--
-- SQLite is the source of truth. The Tantivy index is derived from it and can be
-- rebuilt from it at any time. This file is an artifact on purpose (Findling
-- pattern): a schema gets read, diffed and quoted in bug reports. Every
-- statement is IF NOT EXISTS, so applying it on every start is a no-op.
--
-- Connection pragmas (WAL, busy_timeout, foreign_keys, query_only) are per
-- connection and live in repo.py.
--
-- All times are whole milliseconds of audio time, INTEGER (pitfall 8).

-- Version marks: schema_version, index_generation. Open names, so a later mark
-- needs no migration.
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- One media item per distinct content. Transcripts hang at media_id, never at a
-- file id: two copies of the same recording share one transcript, while access
-- rights stay per file_id. epoch rises only when an admin asks for a recompute
-- or a faulty model is recalled; a result of an older epoch is stale.
CREATE TABLE IF NOT EXISTS media (
    media_id   INTEGER PRIMARY KEY,
    epoch      INTEGER NOT NULL DEFAULT 0 CHECK (epoch >= 0),
    created_at INTEGER NOT NULL
);

-- Content keys pointing at a media item (decision 3). Phase 1 writes only
-- kind = 'file_sha256'; a second kind can point at an existing media_id later
-- without a migration.
CREATE TABLE IF NOT EXISTS media_key (
    kind     TEXT    NOT NULL,
    value    TEXT    NOT NULL,
    media_id INTEGER NOT NULL REFERENCES media (media_id),
    PRIMARY KEY (kind, value)
);

-- One row per Nextcloud file that has been seen. reason is a code from the
-- closed list STATE_REASONS in repo.py, never free text.
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

-- Every transcript version with its full provenance (decision 5).
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

-- The machine words of one version.
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

-- The pointer to the current version of a media item. Written only through the
-- conditional UPSERT in repo.py: (epoch, level, config_version) must rise.
-- index_rev rises with every change the index has to see (new version or new
-- correction).
CREATE TABLE IF NOT EXISTS current (
    media_id       INTEGER PRIMARY KEY REFERENCES media (media_id),
    version_id     INTEGER NOT NULL REFERENCES transcript (version_id),
    epoch          INTEGER NOT NULL,
    level          INTEGER NOT NULL,
    config_version INTEGER NOT NULL,
    index_rev      INTEGER NOT NULL
);

-- User corrections anchored at audio time of a media item (decision 4). Active
-- text corrections of one media item never overlap; a new one sets
-- superseded_by of the old ones, so the history stays (BITV-04).
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

-- Index work committed together with the change that caused it. The index
-- worker publishes the revision and then calls mark_indexed.
CREATE TABLE IF NOT EXISTS index_outbox (
    media_id  INTEGER NOT NULL,
    index_rev INTEGER NOT NULL,
    PRIMARY KEY (media_id, index_rev)
);
