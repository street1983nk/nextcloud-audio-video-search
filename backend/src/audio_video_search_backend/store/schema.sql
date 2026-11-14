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
--
-- Schema version 2 (phase 2). A file of version 1 is lifted by
-- store/migrate.py in one transaction before this script runs.
--
-- Schema version 3 (phase 3): the table preview_job (one row per content) and
-- the column file_ref.origin. A file of version 2 is lifted by store/migrate.py
-- in one transaction, a file of version 1 runs through both steps; this script
-- describes version 3 for a new file.

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
--
-- head_sha256 is the sha256 of the first 64 KiB of the content: every further
-- copy has to read the same head through its own file id and its own reader
-- before it may attach (read proof, D-02-01a). orphaned_at is set when the last
-- reference went away (trash, deleted user, D-02-09 and D-02-13); the content is
-- forgotten later, so a copy that turns up again keeps its transcript.
CREATE TABLE IF NOT EXISTS media (
    media_id    INTEGER PRIMARY KEY,
    epoch       INTEGER NOT NULL DEFAULT 0 CHECK (epoch >= 0),
    created_at  INTEGER NOT NULL,
    head_sha256 TEXT,
    orphaned_at INTEGER
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

-- One row per Nextcloud file that has been seen: the work stock of the
-- discovery. Rights stay per file_id; only a reference in state active ever
-- gives a hit. The test results of the walking skeleton live in sample_ref,
-- never here (D-02-15).
--
-- storage_id is the numeric Nextcloud storage id (oc_storages.numeric_id); the
-- string id is cut to an md5 above 64 characters, so the container never keys
-- on it. prefilter_key is a sha256 the PHP app computes from share, path in the
-- share, size and mtime (D-02-01); the container never sees a path. reader_uid
-- is the user the gateway reads the file as. stage is the place in the
-- discovery (pending, probing, fetching, keyed, failed) with its own attempts
-- and retry time, so a long download needs no lock in the PHP queue.
-- proved_at is the time of the last successful read proof of this copy: the
-- reconcile renews it at least every 7 days on SMB and SFTP (D-02-12).
-- vanished_since is set when the storage of the reference is no longer mounted;
-- such a reference neither counts nor gives hits, and comes back without a
-- download. state, stage and reason are codes from the closed lists in repo.py,
-- never free text.
--
-- origin (schema v3, D-03-05) says how the PHP app came to the file: event (an
-- upload or a change a user made) or crawl (the walk over a storage). event
-- always wins over crawl and never the other way round; a file changed by a
-- user is an event even when the crawl saw it first. The column is the last
-- one because the migration adds it with ALTER TABLE.
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

-- The test results of occ :sample (D-02-15, Owner 07.11.): a layer of its own,
-- so a sample and the reference of the discovery for the same file never
-- overwrite each other. The intake and the orphan rule never write here; the
-- sample removal never writes file_ref. A sample gives a hit for its file
-- unless the discovery holds a reference of that file that gives none
-- (unreadable, vanished, trashed). media_id is the content of the bytes the
-- sample read through the gateway.
CREATE TABLE IF NOT EXISTS sample_ref (
    file_id    INTEGER PRIMARY KEY,
    media_id   INTEGER NOT NULL REFERENCES media (media_id),
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sample_ref_media ON sample_ref (media_id);

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

-- The preview of a content (schema v3, phase 3): one row per media_id, never
-- per file_id, so two copies of the same recording are transcribed once.
-- Written only by repo.py; the capture seeds a row in the same commit that keys
-- a reference (mark_keyed, attach_by_proof), the migration seeds the stock.
--
-- state is where the preview stands:
--   queued   waits for the worker;
--   running  is being computed piece by piece;
--   waiting  waits for disk space (reason disk_full) until next_try_at;
--   complete the whole content is transcribed (the end mark for phase 6);
--   skipped  will not be transcribed, with a reason.
-- reason is a code from the closed list in repo.py (too_long, no_audio,
-- damaged, protected, format_unsupported, no_speech, unsupported_language,
-- disk_full), never free text, so no CHECK here.
--
-- origin (D-03-05) is event or crawl; event always wins, and the order of the
-- work is event before crawl, then the newest file first (sort_mtime, the
-- largest mtime of the active references). epoch is media.epoch when the row
-- was seeded; a result of an older epoch is stale.
--
-- duration_ms is the length of the content once known; a too_long row comes
-- back when the admin raises the limit (D-03-09). next_start_ms is the audio
-- time where the next piece begins; it is written in the same commit as the
-- words of a piece, so a restart goes on from there (TRANS-07). chunks_done
-- counts the committed pieces, version_id is the preview version the pieces
-- hang at (D-03-07). kept_words and the drop_* counters say how many words
-- were kept or dropped and why (script, language, confidence), speech_ms how
-- much speech the VAD found. attempts and next_try_at belong to retries;
-- second_pass is 1 once the second VAD pass is done (D-03-16).
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
