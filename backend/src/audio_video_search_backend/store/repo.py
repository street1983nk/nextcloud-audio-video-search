"""The SQLite operating state, the one place that writes it.

Three data decisions of phase 1 live here as code (phase research, decisions 3
to 5):

- Content keys with indirection: transcripts hang at ``media_id``; the file
  hash is one ``media_key`` pointing at it, and rights stay per ``file_id``.
- Conditional publish: a version becomes current only when its
  ``(epoch, level, config_version)`` is strictly greater than the current one.
  A stale result is rolled back completely, a result for other content
  (``input_file_sha256`` not pointing at the media item) is refused before
  anything is written.
- The correction layer: user corrections are anchored at audio time and laid
  over whatever machine version is current, see :mod:`..model.overlay`.

Every SQL statement is a ``Final`` constant with placeholders; no value is ever
formatted into SQL (T-01-05). Log lines carry ids and counts through ``extra=``
and never a word, a correction text or a path (T-01-07).
"""

import json
import logging
import re
import sqlite3
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
from typing import Final, Literal

from audio_video_search_backend.model import overlay
from audio_video_search_backend.model.overlay import Correction, Word
from audio_video_search_backend.model.provenance import Level, Provenance, validate
from audio_video_search_backend.store.migrate import migrate_v1_to_v2, migrate_v2_to_v3, stored_version

_LOG: Final = logging.getLogger(__name__)

SCHEMA_VERSION: Final = 3
_SCHEMA_FILE: Final = Path(__file__).with_name("schema.sql")
_BUSY_TIMEOUT_MS: Final = 5000

# Closed lists for file_ref (schema v2). These values reach an admin page
# later, and a free field is the shortest path to a file name where no file
# name may appear. An empty reason is stored as NULL.
#
# state: whether the reference counts and gives hits. Only active does;
# unreadable (the read proof or the download failed, or a proof is owed after
# a restore from the trash, plan 02-15b), vanished (the storage is no longer
# mounted) and trashed never give a hit (T-02-06, _FILE_IDS_FOR_MEDIA).
# The samples of the walking skeleton are not a state here: they live in
# sample_ref (D-02-15).
STATES: Final = frozenset({"active", "unreadable", "vanished", "trashed"})
# origin (schema v3, D-03-05): how the PHP app came to the file, an event of a
# user or the crawl over a storage. event always wins over crawl, at the
# reference and at the preview job of its content, never the other way round.
ORIGINS: Final = frozenset({"event", "crawl"})
# stage: where the discovery of this file stands.
STAGES: Final = frozenset({"pending", "probing", "fetching", "keyed", "failed"})
STATE_REASONS: Final = frozenset(
    {
        "read_denied",
        "read_timeout",
        "access_control",
        "locked",
        "gateway_failed",
        "not_found",
        "storage_paused",
        "too_large",
        "disk_full",
        "excluded",
        "size_mismatch",
    }
)
# Closed lists for preview_job (schema v3, plan 03-09). state: see schema.sql.
# reason: why a job waits (disk_full, D-03-17) or is skipped. The four codes
# of the probe (media/probe.py MEDIA_REASONS, D-03-20), too_long (D-03-08),
# the two verdicts of a file without text (engine/catch.py, D-03-12) and
# engine_failed after the last attempt. A code reaches the play page and occ,
# never a free text (D-03-13).
PREVIEW_STATES: Final = frozenset({"queued", "running", "waiting", "complete", "skipped"})
PREVIEW_REASONS: Final = frozenset(
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
# Which call may write which code, each a part of PREVIEW_REASONS: a verdict
# of the file after its last piece, a wait for room on the disk, and every
# other code as a skip by the worker.
_TEXTLESS_VERDICTS: Final = frozenset({"no_speech", "unsupported_language"}) & PREVIEW_REASONS
_DEFER_REASONS: Final = frozenset({"disk_full"}) & PREVIEW_REASONS
_SKIP_REASONS: Final = PREVIEW_REASONS - _TEXTLESS_VERDICTS - _DEFER_REASONS
_TRANSCRIPT_VERDICT: Final = "transcript"
# The admin limit of the duration (D-03-08, D-03-09), kept in meta.
MAX_DURATION_KEY: Final = "max_duration_hours"
DEFAULT_MAX_DURATION_HOURS: Final = 12
_HEX64: Final = re.compile(r"[0-9a-f]{64}")
CORRECTION_KINDS: Final = frozenset({"text", "speaker", "sound"})
_MAX_UID_LENGTH: Final = 64
_MAX_ETAG_LENGTH: Final = 64

_SET_META_DEFAULT: Final = "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)"
_GET_META: Final = "SELECT value FROM meta WHERE key = ?"
_SET_META: Final = "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value"
_BUMP_GENERATION: Final = """
UPDATE meta SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) WHERE key = 'index_generation' RETURNING value
"""
# The store's own mark is written by open() alone; set_meta refuses it.
_OWN_META_KEYS: Final = frozenset({"schema_version", "index_generation"})
_META_KEY: Final = re.compile(r"[a-z][a-z_]{0,63}")

_MEDIA_FOR_KEY: Final = "SELECT media_id FROM media_key WHERE kind = 'file_sha256' AND value = ?"
# A media id is never handed out again while the index still has work for it:
# the documents of a forgotten content carry its id until the retirement mark
# in index_outbox is worked off (plan 02-15), and SQLite alone would give the
# highest id to the next content.
_INSERT_MEDIA: Final = """
INSERT INTO media (media_id, created_at)
VALUES (MAX((SELECT COALESCE(MAX(media_id), 0) FROM media),
            (SELECT COALESCE(MAX(media_id), 0) FROM index_outbox)) + 1, ?)
"""
_INSERT_MEDIA_KEY: Final = "INSERT INTO media_key (kind, value, media_id) VALUES ('file_sha256', ?, ?)"
_MEDIA_EPOCH: Final = "SELECT epoch FROM media WHERE media_id = ?"
_BUMP_EPOCH: Final = "UPDATE media SET epoch = epoch + 1 WHERE media_id = ? RETURNING epoch"

_UPSERT_FILE_REF: Final = """
INSERT INTO file_ref (file_id, media_id, storage_id, prefilter_key, reader_uid, etag, size, mtime, state, stage,
                      reason, attempts, next_try_at, proved_at, vanished_since, updated_at)
VALUES (:file_id, :media_id, :storage_id, :prefilter_key, :reader_uid, :etag, :size, :mtime, :state, :stage,
        :reason, :attempts, :next_try_at, :proved_at, :vanished_since, :now)
ON CONFLICT (file_id) DO UPDATE SET
    media_id = excluded.media_id, storage_id = excluded.storage_id, prefilter_key = excluded.prefilter_key,
    reader_uid = excluded.reader_uid, etag = excluded.etag, size = excluded.size, mtime = excluded.mtime,
    state = excluded.state, stage = excluded.stage, reason = excluded.reason, attempts = excluded.attempts,
    next_try_at = excluded.next_try_at, proved_at = excluded.proved_at, vanished_since = excluded.vanished_since,
    updated_at = excluded.updated_at
"""
# Only a file that may give a hit: an active reference of the discovery, or a
# sample (D-02-15) of a file whose reference, if the discovery has one, is
# active. unreadable, vanished and trashed never reach the search, also not
# through a sample.
#
# A sample counts only while its content stands at the sample level (plan
# 02-16b, owner 13.11.2026): the sample read its bytes as the user the admin
# named, so once the content has a real transcript, text goes out through an
# active reference of the discovery and through nothing else. :sample is
# Level.SAMPLE; a content without a current version has no text to give. The
# same condition stands in _SAMPLE_VISIBLE for the excerpt.
_FILE_IDS_FOR_MEDIA: Final = """
SELECT file_id FROM file_ref WHERE media_id = :m AND state = 'active'
UNION
SELECT s.file_id FROM sample_ref s
WHERE s.media_id = :m
  AND NOT EXISTS (SELECT 1 FROM file_ref r WHERE r.file_id = s.file_id AND r.state <> 'active')
  AND NOT EXISTS (SELECT 1 FROM current c WHERE c.media_id = s.media_id AND c.level <> :sample)
ORDER BY 1
"""
# The sample layer (D-02-15), written only by api/sample.py and remove_sample;
# an exclusion deletes the sample of an excluded file (_REMOVE_SAMPLES, D-02-15a).
_PUT_SAMPLE: Final = """
INSERT INTO sample_ref (file_id, media_id, created_at) VALUES (:file_id, :media_id, :now)
ON CONFLICT (file_id) DO UPDATE SET media_id = excluded.media_id, created_at = excluded.created_at
"""
_SAMPLE_MEDIA: Final = "SELECT media_id FROM sample_ref WHERE file_id = ?"
_SAMPLE_VISIBLE: Final = """
SELECT s.media_id FROM sample_ref s
WHERE s.file_id = :f AND NOT EXISTS (SELECT 1 FROM file_ref r WHERE r.file_id = :f AND r.state <> 'active')
  AND NOT EXISTS (SELECT 1 FROM current c WHERE c.media_id = s.media_id AND c.level <> :sample)
"""
_HAS_CURRENT: Final = "SELECT 1 FROM current WHERE media_id = ?"
_FILE_REF_ROW: Final = """
SELECT file_id, media_id, storage_id, prefilter_key, reader_uid, etag, size, mtime, state, stage, reason,
       attempts, next_try_at, proved_at, vanished_since, updated_at
FROM file_ref WHERE file_id = ?
"""
_FILE_REF: Final = "SELECT media_id, state FROM file_ref WHERE file_id = ?"

# The intake of the PHP work stock (plan 02-05, every kind since plan 02-15).
INTAKE_KINDS: Final = frozenset({"exclude_storage", "exclude", "delete", "trash", "restore", "content", "metadata"})
# Kinds that describe a version of a file: etag, size and mtime are mandatory.
_VERSION_KINDS: Final = frozenset({"content", "metadata", "restore"})
_INTAKE_ROW: Final = "SELECT media_id, etag, size, mtime, state, stage, prefilter_key FROM file_ref WHERE file_id = ?"
_INTAKE_NEW: Final = """
INSERT INTO file_ref (file_id, media_id, storage_id, prefilter_key, reader_uid, etag, size, mtime, state, stage,
                      reason, attempts, next_try_at, proved_at, vanished_since, updated_at, origin)
VALUES (:file_id, NULL, :storage_id, :prefilter_key, :reader_uid, :etag, :size, :mtime, 'active', 'pending',
        NULL, 0, NULL, NULL, NULL, :now, :origin)
"""
# Every update of a version row below (metadata, changed, restore) carries the
# origin of the row: event wins (D-03-05), a crawl row never turns an event
# back into crawl.
#
# Same bytes as far as the cache can tell: the keyed state stays as it is.
_INTAKE_METADATA: Final = """
UPDATE file_ref SET prefilter_key = :prefilter_key, reader_uid = :reader_uid,
    origin = CASE WHEN :origin = 'event' OR file_ref.origin = 'event' THEN 'event' ELSE 'crawl' END,
    updated_at = :now
WHERE file_id = :file_id
"""
# Any change of etag, size or mtime: the content key is unknown again (D-02-01).
_INTAKE_CHANGED: Final = """
UPDATE file_ref SET media_id = NULL, storage_id = :storage_id, prefilter_key = :prefilter_key,
    reader_uid = :reader_uid, etag = :etag, size = :size, mtime = :mtime, state = 'active', stage = 'pending',
    reason = NULL, attempts = 0, next_try_at = NULL, proved_at = NULL, vanished_since = NULL,
    origin = CASE WHEN :origin = 'event' OR file_ref.origin = 'event' THEN 'event' ELSE 'crawl' END,
    updated_at = :now
WHERE file_id = :file_id
"""
# The trash (D-02-09): the reference stays with its content but gives no hit,
# does not count and is never fetched. A download or proof that runs for it
# loses its claim, so its result is stale and cannot make the reference active.
# A reference that owed its proof after an earlier restore (unreadable,
# probing) goes in as failed: probing in the trash means "the last proof held",
# and a second round through the trash must not turn an owed proof into that.
_INTAKE_TRASH: Final = """
UPDATE file_ref SET state = 'trashed',
    stage = CASE WHEN stage = 'fetching' THEN 'pending'
                 WHEN stage = 'probing' AND state <> 'active' THEN 'failed'
                 ELSE stage END,
    updated_at = :now
WHERE file_id = :file_id AND state <> 'trashed'
RETURNING media_id
"""
# Back from the trash with the same (etag, size, mtime): no download. Which
# state and stage it comes back to is decided in apply_intake; the condition
# is on the file id and the trash alone.
_INTAKE_RESTORE: Final = """
UPDATE file_ref SET state = :state, stage = :stage, storage_id = :storage_id, prefilter_key = :prefilter_key,
    reader_uid = :reader_uid, reason = CASE WHEN :keep_reason THEN reason ELSE NULL END, attempts = 0,
    next_try_at = NULL,
    origin = CASE WHEN :origin = 'event' OR file_ref.origin = 'event' THEN 'event' ELSE 'crawl' END,
    updated_at = :now
WHERE file_id = :file_id AND state = 'trashed'
"""
# The orphan rule (D-02-09, D-02-13): a content without an active reference
# is only marked; it is forgotten later, so a copy that turns up again keeps
# its transcript and corrections. The rule looks at the references of the
# discovery only (D-02-15): a sample neither keeps a content from the mark nor
# is it ever written here; the mark does not hide a sample hit.
_MARK_ORPHANED: Final = """
UPDATE media SET orphaned_at = :now
WHERE media_id = :m AND orphaned_at IS NULL
  AND NOT EXISTS (SELECT 1 FROM file_ref WHERE media_id = :m AND state = 'active')
"""

# The capture (plan 02-08). A reference is claimed by setting stage fetching;
# every write after the download names the claimed (etag, size, mtime) and
# stage fetching, so a reference the intake changed in the meantime (pending
# again with new values) is never overwritten with the result of old bytes.
#
# Due work: a new or deferred reference (pending, next_try_at empty or past),
# a failed one whose retry time has come, and an attached one whose read proof
# is due again (probing with a media_id, set by restore and by the reconcile,
# D-02-12). vanished and trashed references are never fetched; a sample is no
# reference (D-02-15). New references come before retries.
#
# First of all comes the proof a restore from the trash owes (plan 02-15b):
# unreadable, probing, with a content. Such a reference gives no hit until
# that proof passed, so it does not wait behind downloads. Only _restore
# writes this combination, and every verdict of the capture leaves it (keyed,
# failed or pending), so a reference comes first once per restore; its retries
# wait in the ordinary order, and a storage that hangs is passed over by the
# circuit of the capture after three timeouts.
_CLAIM_CAPTURE: Final = """
UPDATE file_ref SET stage = 'fetching', updated_at = :now
WHERE file_id = (
    SELECT file_id FROM file_ref
    WHERE state IN ('active', 'unreadable')
      AND ((stage = 'pending' AND (next_try_at IS NULL OR next_try_at <= :now))
        OR (stage = 'probing' AND media_id IS NOT NULL AND (next_try_at IS NULL OR next_try_at <= :now))
        OR (stage = 'failed' AND next_try_at IS NOT NULL AND next_try_at <= :now))
    ORDER BY CASE WHEN state = 'unreadable' AND stage = 'probing' AND media_id IS NOT NULL THEN 0 ELSE 1 END,
             COALESCE(next_try_at, 0), file_id
    LIMIT 1)
RETURNING file_id, media_id, storage_id, prefilter_key, reader_uid, etag, size, mtime, state, stage, reason,
          attempts, next_try_at, proved_at, vanished_since, updated_at
"""
# A process that stopped during a download left its claim behind.
_RESET_FETCHING: Final = "UPDATE file_ref SET stage = 'pending', updated_at = :now WHERE stage = 'fetching'"
_CLAIMED: Final = """
SELECT media_id FROM file_ref
WHERE file_id = :file_id AND stage = 'fetching' AND etag = :etag AND size = :size AND mtime = :mtime
"""
# The one place besides attach_by_proof (plan 02-13) that gives a reference its media_id.
_KEY_REF: Final = """
UPDATE file_ref SET media_id = :media_id, state = 'active', stage = 'keyed', reason = NULL, attempts = 0,
    next_try_at = NULL, proved_at = :now, updated_at = :now
WHERE file_id = :file_id AND stage = 'fetching' AND etag = :etag AND size = :size AND mtime = :mtime
"""
# D-02-13: a content that comes back keeps transcript and corrections; only the
# orphan mark goes. The head is written once, it is a function of the bytes.
_KEY_MEDIA: Final = """
UPDATE media SET head_sha256 = COALESCE(head_sha256, :head), orphaned_at = NULL WHERE media_id = :media_id
"""
_FAIL_REF: Final = """
UPDATE file_ref SET state = :state, stage = 'failed', reason = :reason, attempts = attempts + :bump,
    next_try_at = :retry_at, updated_at = :now
WHERE file_id = :file_id AND stage = 'fetching' AND etag = :etag AND size = :size AND mtime = :mtime
"""
_DEFER_REF: Final = """
UPDATE file_ref SET stage = 'pending', reason = :reason, next_try_at = :retry_at, updated_at = :now
WHERE file_id = :file_id AND stage = 'fetching' AND etag = :etag AND size = :size AND mtime = :mtime
"""
_DELETE_CLAIMED: Final = """
DELETE FROM file_ref
WHERE file_id = :file_id AND stage = 'fetching' AND etag = :etag AND size = :size AND mtime = :mtime
"""
# After a full download the copies with the same prefilter key that only wait
# (deferred, not failed) are due at once: their read proof has a content to be
# made against now. They are found by the key and written by their file id.
_WAITING_SIBLINGS: Final = """
SELECT s.file_id FROM file_ref s
WHERE s.prefilter_key = (SELECT prefilter_key FROM file_ref WHERE file_id = :file_id)
  AND s.file_id <> :file_id AND s.media_id IS NULL AND s.stage = 'pending' AND s.next_try_at > :now
"""
_MAKE_DUE: Final = """
UPDATE file_ref SET next_try_at = NULL, updated_at = :now
WHERE file_id = :file_id AND media_id IS NULL AND stage = 'pending'
"""

# The read proof (plan 02-13, D-02-01a). A sibling is a reference with the same
# prefilter key that gives hits and hangs at a content with a head: only
# against such a one a further copy may prove that it reads the same bytes.
_PREFILTER_SIBLING: Final = """
SELECT s.media_id, m.head_sha256 FROM file_ref s JOIN media m ON m.media_id = s.media_id
WHERE s.prefilter_key = :prefilter_key AND s.state = 'active' AND s.stage = 'keyed'
  AND m.head_sha256 IS NOT NULL
ORDER BY s.file_id LIMIT 1
"""
_MEDIA_HEAD: Final = "SELECT head_sha256 FROM media WHERE media_id = ?"
# Asked again inside the transaction of the attach: the content the proof was
# made against is still held by a keyed sibling of this very copy.
_SIBLING_HOLDS: Final = """
SELECT 1 FROM file_ref s JOIN media m ON m.media_id = s.media_id
WHERE s.media_id = :media_id AND s.file_id <> :file_id AND s.state = 'active' AND s.stage = 'keyed'
  AND m.head_sha256 IS NOT NULL
  AND s.prefilter_key = (SELECT prefilter_key FROM file_ref WHERE file_id = :file_id)
"""
# The one place besides mark_keyed that gives a reference its media_id. It is
# conditional: the claimed reference, the etag the proof was made for, and no
# content yet. Never by the prefilter key (tests/test_read_proof_gate.py).
_ATTACH_REF: Final = """
UPDATE file_ref SET media_id = :media_id, state = 'active', stage = 'keyed', reason = NULL, attempts = 0,
    next_try_at = NULL, proved_at = :now, updated_at = :now
WHERE file_id = :file_id AND etag = :etag AND media_id IS NULL AND stage = 'fetching'
"""
# The renewed proof (D-02-12) of a reference that hangs at a content already.
_CONFIRM_REF: Final = """
UPDATE file_ref SET state = 'active', stage = 'keyed', reason = NULL, attempts = 0, next_try_at = NULL,
    proved_at = :now, updated_at = :now
WHERE file_id = :file_id AND etag = :etag AND media_id IS NOT NULL AND stage = 'fetching'
RETURNING media_id
"""
_CLEAR_ORPHAN: Final = "UPDATE media SET orphaned_at = NULL WHERE media_id = ?"
# The preview job of a content (schema v3), seeded in the same commit that keys
# a reference (mark_keyed) or attaches a copy (attach_by_proof), and on every
# way back to an active keyed reference (a restore from the trash, a renewed
# proof that passed, a storage back in the list; plan 03-09): a content whose
# references all lay elsewhere when the migration seeded gets its job there.
# One row per media_id, never per file. Only an active, keyed reference seeds; a sample
# never does (D-02-15, T-03-09). A copy of a content that has its job already
# only carries its origin (event wins) and its mtime (the newest wins) into a
# job that still waits; a running, complete or skipped job stays as it is.
_SEED_PREVIEW_JOB: Final = """
INSERT INTO preview_job (media_id, epoch, state, origin, sort_mtime, updated_at)
SELECT f.media_id, m.epoch, 'queued', f.origin, f.mtime, :now
FROM file_ref f JOIN media m ON m.media_id = f.media_id
WHERE f.file_id = :file_id AND f.state = 'active' AND f.stage = 'keyed'
ON CONFLICT (media_id) DO UPDATE SET
    origin = CASE WHEN excluded.origin = 'event' THEN 'event' ELSE preview_job.origin END,
    sort_mtime = MAX(preview_job.sort_mtime, excluded.sort_mtime),
    updated_at = excluded.updated_at
WHERE preview_job.state IN ('queued', 'waiting')
"""
# A renewed proof read other bytes than the content has: the reference lets go
# of it and is read in full like a new one.
_RELEASE_REF: Final = """
UPDATE file_ref SET media_id = NULL, proved_at = NULL, updated_at = :now
WHERE file_id = :file_id AND stage = 'fetching' AND etag = :etag AND size = :size AND mtime = :mtime
"""

# Removing references (plan 02-15). The ids travel as one JSON text, so a band
# of any size is one statement; what the statement hands back are the contents
# of the removed references, the only ones looked at afterwards (T-02-56).
RemoveCause = Literal["exclude", "delete", "gone", "vanished_expired"]
REMOVE_CAUSES: Final = frozenset({"exclude", "delete", "gone", "vanished_expired"})
_REMOVE_BY_FILE: Final = """
DELETE FROM file_ref WHERE file_id IN (SELECT value FROM json_each(?)) RETURNING media_id, file_id
"""
_REMOVE_BY_STORAGE: Final = """
DELETE FROM file_ref WHERE storage_id IN (SELECT value FROM json_each(?)) RETURNING media_id, file_id
"""
# An exclusion takes the sample of the file with it (D-02-15a): no test hit
# stays for a file the admin left out. Only an exclusion writes sample_ref here.
_REMOVE_SAMPLES: Final = """
DELETE FROM sample_ref WHERE file_id IN (SELECT value FROM json_each(?)) RETURNING media_id
"""
# Forgetting a content (D-02-04), in the order of the foreign keys: corrections,
# the current pointer, words, transcripts, keys, the media item. :everything is
# 0 while a sample (D-02-15) points at the content: then the rows of the sample
# and the media item stay, they go only through remove_sample.
_MEDIA_HAS_REF: Final = "SELECT 1 FROM file_ref WHERE media_id = ? LIMIT 1"
_MEDIA_HAS_SAMPLE: Final = "SELECT 1 FROM sample_ref WHERE media_id = ? LIMIT 1"
_FORGET_CORRECTIONS: Final = "DELETE FROM correction WHERE media_id = ?"
# The preview job hangs at the media item by a foreign key: it goes before it,
# also while a sample keeps the media item, since no reference is left to work for.
_FORGET_PREVIEW_JOB: Final = "DELETE FROM preview_job WHERE media_id = ?"
_FORGET_CURRENT: Final = """
DELETE FROM current WHERE media_id = :m AND version_id IN (
    SELECT version_id FROM transcript WHERE media_id = :m AND (:everything OR engine <> 'sample'))
"""
_FORGET_WORDS: Final = """
DELETE FROM word WHERE version_id IN (
    SELECT version_id FROM transcript WHERE media_id = :m AND (:everything OR engine <> 'sample'))
"""
_FORGET_TRANSCRIPTS: Final = "DELETE FROM transcript WHERE media_id = :m AND (:everything OR engine <> 'sample')"
# The retirement mark: revisions of the index start at 1, so a row with
# revision 0 in index_outbox says "delete every document of this content".
RETIRED_REV: Final = 0
_RETIRED_MEDIA: Final = "SELECT media_id FROM index_outbox WHERE index_rev = 0 ORDER BY media_id"
_CLEAR_RETIRED: Final = """
DELETE FROM index_outbox WHERE index_rev = 0 AND media_id IN (SELECT value FROM json_each(?))
"""

# The reconcile (plan 02-20). Storage and file ids travel as one JSON text.
#
# A storage the mount list no longer carries and PHP calls deselected is
# vanished (D-02-12): its references neither count nor give hits and are never
# fetched; a download that ran for one loses its claim. A reference in the
# trash stays trashed and only carries the time, so the grace of the storage
# runs for it as well. vanished_since is written once, on the first absence.
_STORAGES_WITH_REFS: Final = "SELECT DISTINCT storage_id FROM file_ref"
_UNMARKED_STORAGES: Final = "SELECT DISTINCT storage_id FROM file_ref WHERE vanished_since IS NULL"
_MARKED_STORAGES: Final = """
SELECT storage_id FROM file_ref WHERE vanished_since IS NOT NULL
GROUP BY storage_id HAVING MIN(vanished_since) <= :before
"""
_MARK_VANISHED: Final = """
UPDATE file_ref SET state = CASE WHEN state = 'trashed' THEN 'trashed' ELSE 'vanished' END,
    stage = CASE WHEN stage = 'fetching' THEN 'pending' ELSE stage END,
    vanished_since = :now, updated_at = :now
WHERE storage_id IN (SELECT value FROM json_each(:ids)) AND vanished_since IS NULL
RETURNING media_id, state
"""
# Back in the list. Never a download: a reference without a content goes on
# where it stood; a keyed one on a storage without a duty to prove is active
# again. Every other one with a content (SMB and SFTP, or a proof that had
# not passed) is unreadable and probing: no hit until its own read proof
# passed, and the capture takes that proof first, exactly like a restore from
# the trash (D-02-12, plan 02-15b). Every CASE reads the values before the
# update.
_MARK_PRESENT: Final = """
UPDATE file_ref SET
    state = CASE WHEN state <> 'vanished' THEN state
                 WHEN media_id IS NULL THEN 'active'
                 WHEN stage = 'keyed' AND storage_id NOT IN (SELECT value FROM json_each(:groupable)) THEN 'active'
                 ELSE 'unreadable' END,
    stage = CASE WHEN state <> 'vanished' OR media_id IS NULL THEN stage
                 WHEN stage = 'keyed' AND storage_id NOT IN (SELECT value FROM json_each(:groupable)) THEN 'keyed'
                 ELSE 'probing' END,
    next_try_at = CASE WHEN state <> 'vanished' OR media_id IS NULL THEN next_try_at
                       WHEN stage = 'keyed' AND storage_id NOT IN (SELECT value FROM json_each(:groupable))
                       THEN next_try_at
                       ELSE NULL END,
    vanished_since = NULL, updated_at = :now
WHERE storage_id IN (SELECT value FROM json_each(:ids)) AND vanished_since IS NOT NULL
RETURNING media_id, state, file_id
"""
# The renewed read proof (D-02-12): an active keyed reference on SMB or SFTP
# whose last proof is older than the limit is due again. The capture proves it
# like a further copy, confirm_proof or fail_proof decide.
_MARK_REPROOF_DUE: Final = """
UPDATE file_ref SET stage = 'probing', next_try_at = NULL, updated_at = :now
WHERE storage_id IN (SELECT value FROM json_each(:ids)) AND state = 'active' AND stage = 'keyed'
  AND media_id IS NOT NULL AND (proved_at IS NULL OR proved_at < :older_than)
"""
# What the walk compares a slice with.
_RECONCILE_ROWS: Final = """
SELECT file_id, storage_id, etag, size, mtime, state FROM file_ref
WHERE file_id IN (SELECT value FROM json_each(?))
"""
# A reference of a fully walked storage that no slice carried any more and
# that nothing touched since the walk began lies outside every walk root: a
# folder in the trash (no event for the files in it, deferred items 02-18) or
# a file removed behind Nextcloud's back. It is set aside like a file in the
# trash (D-02-09): no hit, not counted, its content marked; a restore brings
# it back without a download, through the walk and the pre-check of PHP.
_MARK_MISSING: Final = """
UPDATE file_ref SET state = 'trashed',
    stage = CASE WHEN stage = 'fetching' THEN 'pending'
                 WHEN stage = 'probing' AND state <> 'active' THEN 'failed'
                 ELSE stage END,
    updated_at = :now
WHERE storage_id IN (SELECT value FROM json_each(:storages)) AND state IN ('active', 'unreadable')
  AND updated_at < :before AND file_id NOT IN (SELECT value FROM json_each(:seen))
RETURNING media_id
"""

_INSERT_TRANSCRIPT: Final = """
INSERT INTO transcript (media_id, engine, model_sha256, config_version, profile, level, epoch, language,
                        input_file_sha256, created_at)
VALUES (:media_id, :engine, :model_sha256, :config_version, :profile, :level, :epoch, :language,
        :input_file_sha256, :now)
"""
_INSERT_WORD: Final = """
INSERT INTO word (version_id, idx, start_ms, end_ms, surface, norm, conf, src)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""
# Decision 5, checked against SQLite 3.45: row value comparison (3.15+) in the
# WHERE of an UPSERT (3.24+). A tie is not greater and therefore stale.
_UPSERT_CURRENT: Final = """
INSERT INTO current (media_id, version_id, epoch, level, config_version, index_rev)
VALUES (:m, :v, :e, :l, :c, 1)
ON CONFLICT (media_id) DO UPDATE SET
    version_id = excluded.version_id, epoch = excluded.epoch,
    level = excluded.level, config_version = excluded.config_version,
    index_rev = current.index_rev + 1
WHERE (excluded.epoch, excluded.level, excluded.config_version)
    > (current.epoch, current.level, current.config_version)
"""
_CHANGES: Final = "SELECT changes()"
_CURRENT: Final = "SELECT version_id, epoch, level, config_version, index_rev FROM current WHERE media_id = ?"
_BUMP_INDEX_REV: Final = "UPDATE current SET index_rev = index_rev + 1 WHERE media_id = ? RETURNING index_rev"
_COUNT_AT_LEVEL: Final = "SELECT COUNT(*) FROM current WHERE level = ?"
_CURRENT_MEDIA_IDS: Final = "SELECT media_id FROM current ORDER BY media_id"
_MACHINE_WORDS: Final = """
SELECT start_ms, end_ms, surface, norm, conf, src FROM word WHERE version_id = ? ORDER BY idx
"""

_INSERT_OUTBOX: Final = "INSERT OR IGNORE INTO index_outbox (media_id, index_rev) VALUES (?, ?)"
_PENDING_OUTBOX: Final = "SELECT media_id, index_rev FROM index_outbox ORDER BY media_id, index_rev"
_MARK_INDEXED: Final = "DELETE FROM index_outbox WHERE media_id = ? AND index_rev <= ?"

_INSERT_CORRECTION: Final = """
INSERT INTO correction (media_id, start_ms, end_ms, kind, body, words_json, base_version_id, base_text,
                        author_uid, created_at)
VALUES (:media_id, :start_ms, :end_ms, :kind, :body, :words_json, :base_version_id, :base_text,
        :author_uid, :now)
"""
_SUPERSEDE_TEXT: Final = """
UPDATE correction SET superseded_by = :new
WHERE media_id = :media_id AND kind = 'text' AND superseded_by IS NULL AND correction_id != :new
  AND start_ms < :end_ms AND end_ms > :start_ms
"""
_ACTIVE_CORRECTIONS: Final = """
SELECT correction_id, media_id, start_ms, end_ms, kind, body, words_json FROM correction
WHERE media_id = ? AND superseded_by IS NULL ORDER BY start_ms, correction_id
"""

# remove_sample: only the sample's own rows, in dependency order.
_DELETE_CURRENT: Final = "DELETE FROM current WHERE media_id = ?"
_DELETE_SAMPLE_WORDS: Final = """
DELETE FROM word WHERE version_id IN (SELECT version_id FROM transcript WHERE media_id = ? AND engine = 'sample')
"""
_DELETE_SAMPLE_TRANSCRIPTS: Final = "DELETE FROM transcript WHERE media_id = ? AND engine = 'sample'"
_DELETE_OUTBOX: Final = "DELETE FROM index_outbox WHERE media_id = ?"
_DELETE_SAMPLE_REF: Final = "DELETE FROM sample_ref WHERE file_id = ?"
_MEDIA_STILL_USED: Final = """
SELECT EXISTS (SELECT 1 FROM file_ref WHERE media_id = :m)
    OR EXISTS (SELECT 1 FROM sample_ref WHERE media_id = :m)
    OR EXISTS (SELECT 1 FROM correction WHERE media_id = :m)
    OR EXISTS (SELECT 1 FROM transcript WHERE media_id = :m)
"""
_DELETE_MEDIA_KEYS: Final = "DELETE FROM media_key WHERE media_id = ?"
_DELETE_MEDIA: Final = "DELETE FROM media WHERE media_id = ?"

# The preview jobs (plan 03-09). A job is worked only for a content that has
# an active, keyed reference with a reader: the gateway reads the bytes as
# that user, and a job nobody can read never blocks the queue (T-03-32).
# D-03-05: event before crawl, then the newest file first. A waiting job comes
# back once its time has come; the claim clears its reason, so a running job
# never counts under the reason it waited for.
_CLAIM_PREVIEW: Final = """
UPDATE preview_job SET state = 'running', reason = NULL, updated_at = :now
WHERE media_id = (
    SELECT media_id FROM preview_job
    WHERE (state = 'queued' OR (state = 'waiting' AND next_try_at <= :now))
      AND EXISTS (SELECT 1 FROM file_ref f WHERE f.media_id = preview_job.media_id AND f.state = 'active'
                  AND f.stage = 'keyed' AND f.reader_uid IS NOT NULL)
    ORDER BY CASE origin WHEN 'event' THEN 0 ELSE 1 END, sort_mtime DESC, media_id
    LIMIT 1)
RETURNING media_id, epoch, state, reason, origin, sort_mtime, duration_ms, next_start_ms, chunks_done, version_id,
          kept_words, drop_script, drop_language, drop_conf, speech_ms, attempts, next_try_at, second_pass, updated_at
"""
_PREVIEW_SOURCE: Final = """
SELECT file_id, reader_uid, size FROM file_ref
WHERE media_id = ? AND state = 'active' AND stage = 'keyed' AND reader_uid IS NOT NULL
ORDER BY file_id LIMIT 1
"""
# Every write after the claim names the claimed job: still running, the epoch
# it was claimed in, and the content still in that epoch. Otherwise it is
# stale and nothing is written.
_RUNNING_JOB: Final = """
SELECT p.version_id, p.next_start_ms FROM preview_job p JOIN media m ON m.media_id = p.media_id
WHERE p.media_id = :m AND p.state = 'running' AND p.epoch = :e AND m.epoch = :e
"""
_NEXT_WORD_IDX: Final = "SELECT COALESCE(MAX(idx) + 1, 0) FROM word WHERE version_id = ?"
_CHUNK_JOB: Final = """
UPDATE preview_job SET next_start_ms = :next, chunks_done = chunks_done + 1, version_id = :v,
    kept_words = kept_words + :kept, drop_script = drop_script + :script,
    drop_language = drop_language + :language, drop_conf = drop_conf + :conf,
    speech_ms = speech_ms + :speech, updated_at = :now
WHERE media_id = :m AND state = 'running' AND epoch = :e
"""
_SETTLE_JOB: Final = """
UPDATE preview_job SET state = :state, reason = :reason, duration_ms = COALESCE(:duration, duration_ms),
    next_try_at = :retry_at, attempts = attempts + :bump, updated_at = :now
WHERE media_id = :m AND state = 'running' AND epoch = :e
  AND epoch = (SELECT epoch FROM media WHERE media_id = :m)
"""
_RESET_RUNNING: Final = "UPDATE preview_job SET state = 'queued', updated_at = :now WHERE state = 'running'"
_WAITING_EVENT: Final = """
SELECT 1 FROM preview_job
WHERE state = 'queued' AND origin = 'event'
  AND EXISTS (SELECT 1 FROM file_ref f WHERE f.media_id = preview_job.media_id AND f.state = 'active'
              AND f.stage = 'keyed' AND f.reader_uid IS NOT NULL)
LIMIT 1
"""
# D-03-09: a raised limit brings back what fits now; a duration not known is
# given the chance as well. A job that comes back starts at the beginning.
_REQUEUE_TOO_LONG: Final = """
UPDATE preview_job SET state = 'queued', reason = NULL, next_start_ms = 0, chunks_done = 0, attempts = 0,
    next_try_at = NULL, updated_at = :now
WHERE state = 'skipped' AND reason = 'too_long' AND (duration_ms IS NULL OR duration_ms <= :max_ms)
"""
# What the play page may learn of a file (D-03-13): only through an active
# reference, exactly like media_for_file; every other file is not known.
_PREVIEW_VIEW: Final = """
SELECT p.state, p.reason, p.chunks_done, p.next_start_ms, c.level
FROM file_ref f JOIN preview_job p ON p.media_id = f.media_id
LEFT JOIN current c ON c.media_id = f.media_id
WHERE f.file_id = ? AND f.state = 'active'
"""


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Outcome of :meth:`Store.publish_version`; ``reason`` is a code, never text."""

    published: bool
    version_id: int | None
    index_rev: int | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class FileRef:
    """One row of file_ref, the work stock of the discovery (schema v2)."""

    file_id: int
    media_id: int | None
    storage_id: int
    prefilter_key: str | None
    reader_uid: str | None
    etag: str
    size: int
    mtime: int
    state: str
    stage: str
    reason: str | None
    attempts: int
    next_try_at: int | None
    proved_at: int | None
    vanished_since: int | None
    updated_at: int


@dataclass(frozen=True, slots=True)
class IntakeItem:
    """One row of the PHP work stock as the intake writes it (nc_queue.ClaimItem without the wire names)."""

    queue_id: int
    kind: str
    file_id: int | None
    storage_id: int
    etag: str | None
    size: int | None
    mtime: int | None
    prefilter_key: str | None
    reader_uid: str | None
    origin: str = "crawl"


@dataclass(slots=True)
class _Removal:
    """What one removal did, counted for the log line after the commit."""

    references: int = 0
    forgotten: list[int] = field(default_factory=list)
    orphaned: int = 0
    transcripts: int = 0
    words: int = 0
    corrections: int = 0
    samples: int = 0


def _id_list(ids: Sequence[int], minimum: int, name: str) -> list[int]:
    """The ids of a removal as a list, each a whole number of at least ``minimum``."""
    checked = list(ids)
    if any(not _is_count(value) or value < minimum for value in checked):
        raise ValueError(f"invalid removal field: {name}")
    return checked


def _log_removal(tally: _Removal, cause: str) -> None:
    """Counts and the cause, never an id of a file."""
    if tally.forgotten:
        _LOG.info(
            "media forgotten",
            extra={
                "media": len(tally.forgotten),
                "references": tally.references,
                "cause": cause,
                "transcripts": tally.transcripts,
                "words": tally.words,
                "corrections": tally.corrections,
            },
        )
    if tally.orphaned:
        _LOG.info("media orphaned", extra={"media": tally.orphaned, "references": tally.references, "cause": cause})
    if tally.references and not tally.forgotten and not tally.orphaned:
        _LOG.info("references removed", extra={"references": tally.references, "cause": cause})
    if tally.samples:
        _LOG.info("samples removed", extra={"samples": tally.samples, "cause": cause})


def _check_intake(item: IntakeItem) -> None:
    """The fields of one row, checked before the transaction.

    A whole storage (exclude_storage) needs its storage id, every other kind
    a file id; a kind that describes a version of a file needs all the rest.
    """
    if item.origin not in ORIGINS:
        raise ValueError("invalid intake field: origin")
    if not _is_count(item.storage_id):
        raise ValueError("invalid intake field: storage_id")
    if item.kind == "exclude_storage":
        return
    if item.file_id is None or not _is_count(item.file_id) or item.file_id == 0:
        raise ValueError("invalid intake field: file_id")
    if item.kind not in _VERSION_KINDS:
        return
    if item.etag is None or len(item.etag) > _MAX_ETAG_LENGTH:
        raise ValueError("invalid intake field: etag")
    if not _is_count(item.size) or not _is_count(item.mtime):
        raise ValueError("invalid intake field: size or mtime")
    if item.prefilter_key is not None:
        _require_hex64(item.prefilter_key, "prefilter_key")
    if item.reader_uid is not None and not 0 < len(item.reader_uid) <= _MAX_UID_LENGTH:
        raise ValueError("invalid intake field: reader_uid")


@dataclass(frozen=True, slots=True)
class CurrentRow:
    """The pointer to the current version of one media item."""

    version_id: int
    epoch: int
    level: int
    config_version: int
    index_rev: int


@dataclass(frozen=True, slots=True)
class PreviewJob:
    """One row of preview_job as the claim handed it out (schema v3, plan 03-09)."""

    media_id: int
    epoch: int
    state: str
    reason: str | None
    origin: str
    sort_mtime: int
    duration_ms: int | None
    next_start_ms: int
    chunks_done: int
    version_id: int | None
    kept_words: int
    drop_script: int
    drop_language: int
    drop_conf: int
    speech_ms: int
    attempts: int
    next_try_at: int | None
    second_pass: int
    updated_at: int


@dataclass(frozen=True, slots=True)
class ChunkCounters:
    """What one piece kept and dropped (TRANS-03), added to the job with its words."""

    kept_words: int
    drop_script: int
    drop_language: int
    drop_conf: int
    speech_ms: int


@dataclass(frozen=True, slots=True)
class PreviewView:
    """What the play page may learn of the job of a file with an active reference (D-03-13)."""

    state: str
    reason: str | None
    chunks_done: int
    next_start_ms: int
    level: int | None


class _Rejected(Exception):
    """Internal: leave the transaction with a rollback and a reason code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _row_id(cursor: sqlite3.Cursor) -> int:
    """The id of the row an INSERT just wrote."""
    if cursor.lastrowid is None:
        raise RuntimeError("INSERT returned no row id")
    return int(cursor.lastrowid)


def _now() -> int:
    return int(time.time())


def _enable_wal(connection: sqlite3.Connection) -> str:
    """Ask for WAL and return the mode the database actually took.

    WAL needs shared memory; some file systems fall back to DELETE without an
    error. That costs concurrency only, so it is a warning, not a refusal.
    """
    row = connection.execute("PRAGMA journal_mode = WAL").fetchone()
    mode = str(row[0]).lower() if row else "unknown"
    if mode != "wal":
        _LOG.warning("journal_mode is not wal; reads and writes will block each other", extra={"mode": mode})
    return mode


def _connect(path: Path, *, read_only: bool) -> sqlite3.Connection:
    """One connection with the pragmas of this database (Findling pattern)."""
    connection = sqlite3.connect(path, autocommit=True, check_same_thread=False)
    connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys = ON")
    if read_only:
        connection.execute("PRAGMA query_only = 1")
    else:
        connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def _is_count(value: object) -> bool:
    """A whole number of zero or more; a bool is not one."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _require_hex64(value: object, field: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise ValueError(f"invalid field: {field}")
    return value


def _check_words_json(words_json: str, start_ms: int, end_ms: int) -> None:
    """Editor word times must be whole ms, ascending and inside the span."""
    try:
        items = json.loads(words_json)
    except ValueError:
        raise ValueError("invalid correction field: words_json") from None
    if not isinstance(items, list) or not items:
        raise ValueError("invalid correction field: words_json")
    previous = start_ms
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("invalid correction field: words_json")
        s, e, surface = item.get("start_ms"), item.get("end_ms"), item.get("surface")
        if (
            not isinstance(s, int)
            or not isinstance(e, int)
            or isinstance(s, bool)
            or isinstance(e, bool)
            or not isinstance(surface, str)
            or not surface.strip()
            or not previous <= s <= e <= end_ms
        ):
            raise ValueError("invalid correction field: words_json")
        previous = s


class Store:
    """The operating state of one backend container."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    @classmethod
    def open(cls, path: Path, *, read_only: bool = False) -> "Store":
        """Open the database; the writer migrates, applies the schema and the version marks.

        A file of version 2 is lifted to version 3 in one transaction before
        the schema script runs, a file of version 1 first to version 2 and then
        on to 3, each step in a transaction of its own (store/migrate.py): a
        failure in the second step leaves a file of version 2, which the next
        start lifts again. A reader never migrates, and
        a version this code does not know is refused before anything is
        written.
        """
        connection = _connect(path, read_only=read_only)
        try:
            if not read_only:
                _enable_wal(connection)
                found = stored_version(connection)
                if found == 1:
                    migrate_v1_to_v2(connection)
                    found = 2
                if found == 2:
                    migrate_v2_to_v3(connection)
                elif found not in (0, SCHEMA_VERSION):
                    raise RuntimeError(f"unsupported store schema version {found}")
                connection.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
                connection.execute(_SET_META_DEFAULT, ("schema_version", str(SCHEMA_VERSION)))
                connection.execute(_SET_META_DEFAULT, ("index_generation", "0"))
            store = cls(connection)
            found = store.schema_version()
            if found != SCHEMA_VERSION:
                raise RuntimeError(f"unsupported store schema version {found}")
        except BaseException:
            connection.close()
            raise
        return store

    def close(self) -> None:
        self._conn.close()

    def reading_connection(self) -> sqlite3.Connection:
        """The connection for the read only queries of store/coverage.py; nothing else writes through it."""
        return self._conn

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        """One explicit transaction. Validation belongs before it, never inside."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    def schema_version(self) -> int:
        row = self._conn.execute(_GET_META, ("schema_version",)).fetchone()
        return int(row[0]) if row else 0

    # Version marks of the derived index.

    def meta_value(self, key: str) -> str | None:
        """One value of the meta table, None when the key is not set."""
        row = self._conn.execute(_GET_META, (key,)).fetchone()
        return None if row is None else str(row[0])

    def set_meta(self, key: str, value: str) -> None:
        """Write a mark of the derived index; the store's own marks are refused."""
        if _META_KEY.fullmatch(key) is None or key in _OWN_META_KEYS:
            raise ValueError("invalid meta field: key")
        with self._transaction():
            self._conn.execute(_SET_META, (key, value))

    def index_generation(self) -> int:
        """The generation of the index directory; a new one means a rebuild from SQLite."""
        value = self.meta_value("index_generation")
        return int(value) if value is not None and value.isdigit() else 0

    def bump_index_generation(self) -> int:
        """Raise the index generation and return the new value."""
        with self._transaction():
            row = self._conn.execute(_BUMP_GENERATION).fetchone()
        if row is None:
            raise RuntimeError("meta row index_generation is missing")
        _LOG.info("index generation raised", extra={"generation": int(row[0])})
        return int(row[0])

    # Content keys and files.

    def media_for_file_sha256(self, sha256: str) -> int:
        """The media item of a file hash; created on first sight."""
        _require_hex64(sha256, "sha256")
        with self._transaction():
            row = self._conn.execute(_MEDIA_FOR_KEY, (sha256,)).fetchone()
            if row is not None:
                return int(row[0])
            media_id = _row_id(self._conn.execute(_INSERT_MEDIA, (_now(),)))
            self._conn.execute(_INSERT_MEDIA_KEY, (sha256, media_id))
        return int(media_id)

    def media_epoch(self, media_id: int) -> int:
        """The epoch a new result for this media item has to carry (0 if unknown)."""
        row = self._conn.execute(_MEDIA_EPOCH, (media_id,)).fetchone()
        return int(row[0]) if row else 0

    def bump_epoch(self, media_id: int) -> int:
        """Raise the epoch of a media item; every in-flight older result becomes stale."""
        with self._transaction():
            row = self._conn.execute(_BUMP_EPOCH, (media_id,)).fetchone()
        if row is None:
            raise ValueError("invalid field: media_id")
        _LOG.info("epoch raised", extra={"media_id": media_id, "epoch": int(row[0])})
        return int(row[0])

    def upsert_file_ref(
        self,
        file_id: int,
        media_id: int | None,
        *,
        storage_id: int,
        etag: str,
        size: int,
        mtime: int,
        state: str,
        stage: str,
        reason: str | None,
        prefilter_key: str | None = None,
        reader_uid: str | None = None,
        attempts: int = 0,
        next_try_at: int | None = None,
        proved_at: int | None = None,
        vanished_since: int | None = None,
    ) -> None:
        """Write one reference completely; every code is checked against its closed list first."""
        if state not in STATES:
            raise ValueError("invalid file_ref field: state")
        if stage not in STAGES:
            raise ValueError("invalid file_ref field: stage")
        if reason == "":
            reason = None
        if reason is not None and reason not in STATE_REASONS:
            raise ValueError("invalid file_ref field: reason")
        if not _is_count(storage_id):
            raise ValueError("invalid file_ref field: storage_id")
        if prefilter_key is not None:
            _require_hex64(prefilter_key, "prefilter_key")
        if reader_uid is not None and not 0 < len(reader_uid) <= _MAX_UID_LENGTH:
            raise ValueError("invalid file_ref field: reader_uid")
        if not _is_count(attempts):
            raise ValueError("invalid file_ref field: attempts")
        for name, value in (("next_try_at", next_try_at), ("proved_at", proved_at), ("vanished_since", vanished_since)):
            if value is not None and not _is_count(value):
                raise ValueError(f"invalid file_ref field: {name}")
        with self._transaction():
            self._conn.execute(
                _UPSERT_FILE_REF,
                {
                    "file_id": file_id,
                    "media_id": media_id,
                    "storage_id": storage_id,
                    "prefilter_key": prefilter_key,
                    "reader_uid": reader_uid,
                    "etag": etag,
                    "size": size,
                    "mtime": mtime,
                    "state": state,
                    "stage": stage,
                    "reason": reason,
                    "attempts": attempts,
                    "next_try_at": next_try_at,
                    "proved_at": proved_at,
                    "vanished_since": vanished_since,
                    "now": _now(),
                },
            )

    def apply_intake(self, items: Sequence[IntakeItem]) -> list[int]:
        """Write the rows of one claimed band in one transaction, in the order of the band.

        Returns the queue ids that are written and may be acknowledged; a row
        of a kind outside INTAKE_KINDS is not written and not returned.
        Writing the same band twice ends in the same state (a crash between
        commit and ack delivers it again).

        - new file (content, metadata, restore): active, pending, attempts 0;
        - content or restore with the same (etag, size, mtime): stage, state
          and media stay, only the prefilter key and the reader are refreshed;
          a reference in the trash comes back, see :meth:`_restore`: where a
          read proof is required it gives no hit until that proof passed;
        - content or restore with any difference: pending again without a
          media item, and the previous media item is marked orphaned when no
          active reference points at it any more (D-02-13);
        - metadata: only the prefilter key and the reader (DISC-06);
        - exclude, exclude_storage: the references go, and a content that
          loses its last one is forgotten (D-02-04);
        - delete: the reference goes, its content is only marked (D-02-13);
        - trash: the reference is set aside, its content marked when no
          active reference is left (D-02-09).

        Samples are neither read nor written here (D-02-15). Called only from
        worker/intake.py (gate in plan 02-20), which lets the index retire the
        documents of forgotten contents after the commit.
        """
        usable = [item for item in items if item.kind in INTAKE_KINDS]
        for item in usable:
            _check_intake(item)
        applied: list[int] = []
        counts = {"new": 0, "unchanged": 0, "changed": 0, "metadata": 0, "restored": 0}
        tallies = {"exclude": _Removal(), "delete": _Removal(), "trash": _Removal(), "content": _Removal()}
        now = _now()
        with self._transaction():
            for kind, run in groupby(usable, key=lambda entry: entry.kind):
                band = list(run)
                if kind == "exclude_storage":
                    ids = [entry.storage_id for entry in band]
                    self._remove(_REMOVE_BY_STORAGE, ids, "exclude", now, tallies["exclude"])
                elif kind in ("exclude", "delete"):
                    ids = [entry.file_id for entry in band if entry.file_id is not None]
                    self._remove(_REMOVE_BY_FILE, ids, kind, now, tallies[kind])
                elif kind == "trash":
                    for entry in band:
                        self._trash(entry, now, tallies["trash"])
                else:
                    for entry in band:
                        self._write_version(entry, now, counts, tallies["content"])
                applied.extend(entry.queue_id for entry in band)
        for cause, tally in tallies.items():
            if cause != "content":
                _log_removal(tally, cause)
        _LOG.info(
            "intake written",
            extra=counts
            | {
                "items": len(items),
                "applied": len(applied),
                "removed": tallies["exclude"].references + tallies["delete"].references,
                "trashed": tallies["trash"].references,
                "forgotten": len(tallies["exclude"].forgotten),
                "orphaned": sum(tally.orphaned for tally in tallies.values()),
            },
        )
        return applied

    def _trash(self, item: IntakeItem, now: int, tally: _Removal) -> None:
        """Inside the transaction of the intake: one reference into the trash."""
        row = self._conn.execute(_INTAKE_TRASH, {"file_id": item.file_id, "now": now}).fetchone()
        if row is None:
            return
        tally.references += 1
        if row[0] is not None:
            tally.orphaned += self._conn.execute(_MARK_ORPHANED, {"m": int(row[0]), "now": now}).rowcount

    def _write_version(self, item: IntakeItem, now: int, counts: dict[str, int], tally: _Removal) -> None:
        """Inside the transaction of the intake: one content, metadata or restore row."""
        values = {
            "file_id": item.file_id,
            "storage_id": item.storage_id,
            "prefilter_key": item.prefilter_key,
            "reader_uid": item.reader_uid,
            "etag": item.etag,
            "size": item.size,
            "mtime": item.mtime,
            "origin": item.origin,
            "now": now,
        }
        row = self._conn.execute(_INTAKE_ROW, (item.file_id,)).fetchone()
        if row is None:
            self._conn.execute(_INTAKE_NEW, values)
            counts["new"] += 1
        elif item.kind == "metadata":
            self._conn.execute(_INTAKE_METADATA, values)
            counts["metadata"] += 1
        elif (str(row[1]), int(row[2]), int(row[3])) != (item.etag, item.size, item.mtime):
            self._conn.execute(_INTAKE_CHANGED, values)
            counts["changed"] += 1
            if row[0] is not None:
                tally.orphaned += self._conn.execute(_MARK_ORPHANED, {"m": int(row[0]), "now": now}).rowcount
        elif str(row[4]) == "trashed":
            self._restore(values, None if row[0] is None else int(row[0]), str(row[5]), had_key=row[6] is not None)
            counts["restored"] += 1
        else:
            self._conn.execute(_INTAKE_METADATA, values)
            counts["unchanged"] += 1

    def _restore(self, values: dict[str, object], media_id: int | None, stage: str, *, had_key: bool) -> None:
        """Inside the transaction of the intake: a reference comes back from the trash, same bytes.

        Never a download (D-02-09):

        - it hung at its content with a valid proof (keyed, or a renewed
          proof was only due) on a storage without a duty to prove (no
          prefilter key, neither in the row nor at the reference): active
          again, keyed, and the content loses its orphan mark;
        - the same on a storage with that duty (SMB, SFTP): unreadable and
          probing. It gives no hit until its own read proof passed, and the
          capture takes that proof first (D-02-01a second addendum, D-02-12,
          T-02-55, plan 02-15b). Only confirm_proof makes it active again and
          clears the orphan mark;
        - it hangs at a content, but its last proof failed, was cut off by
          the trash or was still owed: unreadable and probing as well, with
          its reason kept. The trash must not turn a failed proof into a
          valid one;
        - it has no content yet: the capture starts anew.
        """
        proved = stage in ("keyed", "probing")
        if media_id is None:
            fields = {"state": "active", "stage": "pending", "keep_reason": 0}
        elif proved and values["prefilter_key"] is None and not had_key:
            fields = {"state": "active", "stage": "keyed", "keep_reason": 0}
        else:
            fields = {"state": "unreadable", "stage": "probing", "keep_reason": 0 if proved else 1}
        self._conn.execute(_INTAKE_RESTORE, values | fields)
        if media_id is not None and fields["state"] == "active":
            self._conn.execute(_CLEAR_ORPHAN, (media_id,))
            self._conn.execute(_SEED_PREVIEW_JOB, values)

    # The capture (plan 02-08), called only from worker/capture.py.

    def next_capture(self, now: int | None = None) -> FileRef | None:
        """Claim the next due reference for a download (stage fetching) and return it, or None."""
        moment = _now() if now is None else now
        with self._transaction():
            row = self._conn.execute(_CLAIM_CAPTURE, {"now": moment}).fetchone()
        return None if row is None else FileRef(*row)

    def reset_fetching(self) -> int:
        """Hand the claims of a stopped process back as pending; returns how many."""
        with self._transaction():
            reset = self._conn.execute(_RESET_FETCHING, {"now": _now()}).rowcount
        if reset:
            _LOG.info("capture claims reset", extra={"references": reset})
        return reset

    @staticmethod
    def _claim_values(claimed: FileRef) -> dict[str, object]:
        return {"file_id": claimed.file_id, "etag": claimed.etag, "size": claimed.size, "mtime": claimed.mtime}

    def mark_keyed(self, claimed: FileRef, sha256: str, head_sha256: str, now: int | None = None) -> int | None:
        """Hang a claimed reference at the content of its bytes; returns the media_id, None when stale.

        In one transaction: find or create the media item of ``sha256``, write
        its head when it has none, clear its orphan mark (D-02-13), and set the
        reference active, keyed, proved now; the preview job of the content is
        seeded in the same commit (one per content, plan 03-03). Stale means
        the intake changed the reference while it was downloaded; then nothing
        is written, also no job.
        """
        _require_hex64(sha256, "sha256")
        _require_hex64(head_sha256, "head_sha256")
        moment = _now() if now is None else now
        values = self._claim_values(claimed) | {"now": moment, "head": head_sha256}
        with self._transaction():
            row = self._conn.execute(_CLAIMED, values).fetchone()
            if row is None:
                return None
            previous = None if row[0] is None else int(row[0])
            found = self._conn.execute(_MEDIA_FOR_KEY, (sha256,)).fetchone()
            if found is None:
                media_id = _row_id(self._conn.execute(_INSERT_MEDIA, (moment,)))
                self._conn.execute(_INSERT_MEDIA_KEY, (sha256, media_id))
            else:
                media_id = int(found[0])
            values["media_id"] = media_id
            self._conn.execute(_KEY_MEDIA, values)
            self._conn.execute(_KEY_REF, values)
            self._conn.execute(_SEED_PREVIEW_JOB, {"file_id": claimed.file_id, "now": moment})
            if previous is not None and previous != media_id:
                self._conn.execute(_MARK_ORPHANED, {"m": previous, "now": moment})
            waiting = self._conn.execute(_WAITING_SIBLINGS, values).fetchall()
            for (sibling,) in waiting:
                self._conn.execute(_MAKE_DUE, {"file_id": int(sibling), "now": moment})
        _LOG.info("reference keyed", extra={"file_id": claimed.file_id, "media_id": media_id})
        return media_id

    def mark_failed(
        self,
        claimed: FileRef,
        reason: str,
        *,
        retry_at: int | None,
        bump: bool = True,
        state: str = "unreadable",
        now: int | None = None,
    ) -> bool:
        """Set a claimed reference to stage failed with a reason and the time of its next try.

        ``state`` is unreadable for every read failure of the own reader (such a
        reference never counts and never gives a hit) and active only for a
        verdict that is not about reading (too_large). A media item that loses
        its last active reference this way is marked orphaned. False when stale.
        """
        if reason not in STATE_REASONS:
            raise ValueError("invalid file_ref field: reason")
        if state not in ("unreadable", "active"):
            raise ValueError("invalid file_ref field: state")
        if retry_at is not None and not _is_count(retry_at):
            raise ValueError("invalid file_ref field: next_try_at")
        moment = _now() if now is None else now
        values = self._claim_values(claimed) | {
            "now": moment,
            "state": state,
            "reason": reason,
            "bump": 1 if bump else 0,
            "retry_at": retry_at,
        }
        with self._transaction():
            row = self._conn.execute(_CLAIMED, values).fetchone()
            if row is None:
                return False
            self._conn.execute(_FAIL_REF, values)
            if row[0] is not None:
                self._conn.execute(_MARK_ORPHANED, {"m": int(row[0]), "now": moment})
        _LOG.info("reference failed", extra={"file_id": claimed.file_id, "reason": reason, "state": state})
        return True

    def defer_capture(self, claimed: FileRef, reason: str, *, retry_at: int, now: int | None = None) -> bool:
        """Put a claimed reference back to pending until ``retry_at``; state and attempts stay. False when stale."""
        if reason not in STATE_REASONS:
            raise ValueError("invalid file_ref field: reason")
        if not _is_count(retry_at):
            raise ValueError("invalid file_ref field: next_try_at")
        values = self._claim_values(claimed) | {
            "now": _now() if now is None else now,
            "reason": reason,
            "retry_at": retry_at,
        }
        with self._transaction():
            changed = self._conn.execute(_DEFER_REF, values).rowcount
        return changed == 1

    def delete_ref(self, claimed: FileRef, now: int | None = None) -> bool:
        """Delete a claimed reference (the gateway says excluded); False when stale.

        The capture met the exclusion before the exclude row of the queue did,
        so the rule of that row holds here as well (D-02-04, plan 02-16): the
        sample of the file goes, and a content that loses its last reference
        is forgotten at once, not only marked. The exclude row that follows
        finds nothing left to do.
        """
        moment = _now() if now is None else now
        values = self._claim_values(claimed)
        tally = _Removal()
        with self._transaction():
            row = self._conn.execute(_CLAIMED, values).fetchone()
            if row is None:
                return False
            tally.references += self._conn.execute(_DELETE_CLAIMED, values).rowcount
            held = set() if row[0] is None else {int(row[0])}
            self._judge_excluded(held, [claimed.file_id], moment, tally)
        _LOG.info("reference deleted", extra={"file_id": claimed.file_id, "reason": "excluded"})
        _log_removal(tally, "exclude")
        return True

    # The read proof (plan 02-13), called only from worker/capture.py.

    def prefilter_sibling(self, prefilter_key: str) -> tuple[int, str] | None:
        """(media_id, head_sha256) of a keyed, active reference with this prefilter key, or None.

        Only what a read proof can be made against: the sibling gives hits and
        its content has a head. Finding one attaches nothing.
        """
        _require_hex64(prefilter_key, "prefilter_key")
        row = self._conn.execute(_PREFILTER_SIBLING, {"prefilter_key": prefilter_key}).fetchone()
        return None if row is None else (int(row[0]), str(row[1]))

    def media_head(self, media_id: int) -> str | None:
        """The sha256 of the first 64 KiB of a content, None when it has none."""
        row = self._conn.execute(_MEDIA_HEAD, (media_id,)).fetchone()
        return None if row is None or row[0] is None else str(row[0])

    def attach_by_proof(self, file_id: int, media_id: int, expected_etag: str, now: int | None = None) -> bool:
        """Hang a claimed copy at the content of its sibling, after its own read proof said ok.

        Conditional: the reference is claimed, still has the etag the proof was
        made for and no content yet, and a keyed, active sibling with its
        prefilter key still holds ``media_id``. Otherwise nothing is written
        and the answer is False. Sets proved_at; the copy carries its origin
        and mtime into the preview job of the content (plan 03-03).
        """
        moment = _now() if now is None else now
        values = {"file_id": file_id, "media_id": media_id, "etag": expected_etag, "now": moment}
        with self._transaction():
            if self._conn.execute(_SIBLING_HOLDS, values).fetchone() is None:
                return False
            attached = self._conn.execute(_ATTACH_REF, values).rowcount == 1
            if attached:
                self._conn.execute(_SEED_PREVIEW_JOB, values)
        if attached:
            _LOG.info("reference attached by proof", extra={"file_id": file_id, "media_id": media_id})
        return attached

    def confirm_proof(self, file_id: int, expected_etag: str, now: int | None = None) -> bool:
        """Note a renewed read proof that said ok: active, keyed, proved now (D-02-12).

        Conditional on the claim, the etag and a content; the orphan mark of
        that content goes, since it has an active reference again. False when
        the reference changed in the meantime.
        """
        moment = _now() if now is None else now
        values = {"file_id": file_id, "etag": expected_etag, "now": moment}
        with self._transaction():
            row = self._conn.execute(_CONFIRM_REF, values).fetchone()
            if row is None:
                return False
            self._conn.execute(_CLEAR_ORPHAN, (int(row[0]),))
            self._conn.execute(_SEED_PREVIEW_JOB, values)
        _LOG.info("read proof confirmed", extra={"file_id": file_id, "media_id": int(row[0])})
        return True

    def fail_proof(
        self, claimed: FileRef, reason: str, *, retry_at: int | None, bump: bool = True, now: int | None = None
    ) -> bool:
        """Note a renewed read proof that failed: unreadable at once, so its hits are gone (D-02-12).

        The reference keeps its content, so the next try is a proof again and
        not a download; the content is marked orphaned when this was its last
        active reference. False when stale.
        """
        return self.mark_failed(claimed, reason, retry_at=retry_at, bump=bump, state="unreadable", now=now)

    def release_media(self, claimed: FileRef, now: int | None = None) -> bool:
        """Let a claimed reference go of its content, because its own bytes are other ones. False when stale."""
        moment = _now() if now is None else now
        values = self._claim_values(claimed) | {"now": moment}
        with self._transaction():
            row = self._conn.execute(_CLAIMED, values).fetchone()
            if row is None:
                return False
            self._conn.execute(_RELEASE_REF, values)
            if row[0] is not None:
                self._conn.execute(_MARK_ORPHANED, {"m": int(row[0]), "now": moment})
        _LOG.info("reference released", extra={"file_id": claimed.file_id})
        return True

    # Removing references, forgetting and marking contents (plan 02-15).

    def _forget(self, media_id: int, now: int, tally: _Removal) -> bool:
        """Inside a transaction: delete what is known about a content no reference points at.

        False, and nothing deleted, while any reference of the discovery still
        holds the content, also one that gives no hit (a copy in the trash may
        come back). While a sample points at the content its media item, its
        keys and the rows of the sample stay (D-02-15); everything real goes.
        The index learns of it through the retirement mark in the outbox,
        committed with the deletion.
        """
        if self._conn.execute(_MEDIA_HAS_REF, (media_id,)).fetchone() is not None:
            return False
        sampled = self._conn.execute(_MEDIA_HAS_SAMPLE, (media_id,)).fetchone() is not None
        values = {"m": media_id, "everything": 0 if sampled else 1}
        corrections = self._conn.execute(_FORGET_CORRECTIONS, (media_id,)).rowcount
        self._conn.execute(_FORGET_PREVIEW_JOB, (media_id,))
        self._conn.execute(_FORGET_CURRENT, values)
        words = self._conn.execute(_FORGET_WORDS, values).rowcount
        transcripts = self._conn.execute(_FORGET_TRANSCRIPTS, values).rowcount
        gone = 0
        if sampled:
            self._conn.execute(_MARK_ORPHANED, {"m": media_id, "now": now})
        else:
            self._conn.execute(_DELETE_MEDIA_KEYS, (media_id,))
            gone = self._conn.execute(_DELETE_MEDIA, (media_id,)).rowcount
        if self._conn.execute(_HAS_CURRENT, (media_id,)).fetchone() is None:
            # Nothing of this content may be published any more; with a
            # transcript there may be documents, and they have to go.
            self._conn.execute(_DELETE_OUTBOX, (media_id,))
            if transcripts:
                self._conn.execute(_INSERT_OUTBOX, (media_id, RETIRED_REV))
        if not (corrections or transcripts or gone):
            return False
        tally.forgotten.append(media_id)
        tally.transcripts += transcripts
        tally.words += words
        tally.corrections += corrections
        return True

    def _judge_excluded(self, media_ids: set[int], file_ids: Sequence[int], now: int, tally: _Removal) -> None:
        """Inside a transaction: what an exclusion does once the references of ``file_ids`` are deleted.

        The samples of these files go first (D-02-15a), so a content only a
        sample of an excluded file pointed at is forgotten like any other.
        Then every content that lost a reference or a sample is forgotten when
        nothing holds it any more, and marked orphaned otherwise (D-02-04).
        """
        samples = self._conn.execute(_REMOVE_SAMPLES, (json.dumps(list(file_ids)),)).fetchall()
        tally.samples += len(samples)
        for media_id in sorted(media_ids | {int(row[0]) for row in samples}):
            if not self._forget(media_id, now, tally):
                tally.orphaned += self._conn.execute(_MARK_ORPHANED, {"m": media_id, "now": now}).rowcount

    def _remove(self, statement: str, ids: Sequence[int], cause: str, now: int, tally: _Removal) -> None:
        """Inside a transaction: delete the references and judge only the contents they pointed at."""
        rows = self._conn.execute(statement, (json.dumps(ids),)).fetchall()
        tally.references += len(rows)
        media_ids = {int(row[0]) for row in rows if row[0] is not None}
        if cause == "exclude":
            # By file the named files lose their samples, also one the
            # discovery never saw; by storage the files of the deleted rows.
            files = ids if statement is _REMOVE_BY_FILE else [int(row[1]) for row in rows]
            self._judge_excluded(media_ids, files, now, tally)
            return
        for media_id in sorted(media_ids):
            tally.orphaned += self._conn.execute(_MARK_ORPHANED, {"m": media_id, "now": now}).rowcount

    def remove_refs(
        self,
        *,
        file_ids: Sequence[int] | None = None,
        storage_ids: Sequence[int] | None = None,
        cause: RemoveCause,
        now: int | None = None,
    ) -> list[int]:
        """Remove references by file id or by storage id; returns the media ids that were forgotten.

        The cause decides what happens to a content that loses its last
        reference this way:

        - ``exclude`` (D-02-04): it is forgotten at once, with words,
          transcripts, corrections, keys and, through the retirement mark, its
          index documents. While any reference still holds it, nothing of it
          is deleted;
        - every other cause (D-02-09, D-02-13): it is only marked orphaned,
          when no active reference is left; forgetting it later is phase 8.

        One transaction, the ids as one JSON text. Only contents of the
        removed references are looked at (T-02-56).
        """
        return self._remove_refs(file_ids, storage_ids, cause, now).forgotten

    def _remove_refs(
        self, file_ids: Sequence[int] | None, storage_ids: Sequence[int] | None, cause: str, now: int | None
    ) -> _Removal:
        if cause not in REMOVE_CAUSES:
            raise ValueError("invalid removal field: cause")
        if (file_ids is None) == (storage_ids is None):
            raise ValueError("invalid removal field: file_ids or storage_ids")
        if file_ids is not None:
            statement, ids = _REMOVE_BY_FILE, _id_list(file_ids, 1, "file_ids")
        else:
            statement, ids = _REMOVE_BY_STORAGE, _id_list(storage_ids or (), 0, "storage_ids")
        moment = _now() if now is None else now
        tally = _Removal()
        with self._transaction():
            self._remove(statement, ids, cause, moment, tally)
        _log_removal(tally, cause)
        return tally

    # The reconcile (plan 02-20), called only from worker/reconcile.py.

    def remove_storages(
        self, storage_ids: Sequence[int], cause: RemoveCause, now: int | None = None
    ) -> tuple[int, int]:
        """remove_refs by storage for the sweep; returns (references removed, contents marked orphaned)."""
        if not storage_ids:
            return 0, 0
        tally = self._remove_refs(None, storage_ids, cause, now)
        return tally.references, tally.orphaned

    def reconcile_storages(self, *, unmarked: bool = False) -> set[int]:
        """The storages that hold references; with ``unmarked`` only those with a reference not vanished yet."""
        statement = _UNMARKED_STORAGES if unmarked else _STORAGES_WITH_REFS
        return {int(row[0]) for row in self._conn.execute(statement)}

    def vanished_storages(self, before: int) -> set[int]:
        """The storages whose first absence lies at or before ``before``."""
        return {int(row[0]) for row in self._conn.execute(_MARKED_STORAGES, {"before": before})}

    def mark_vanished(self, storage_ids: Sequence[int], now: int | None = None) -> tuple[int, int]:
        """Set the references of deselected storages aside as vanished; returns (vanished, contents marked)."""
        ids = _id_list(storage_ids, 0, "storage_ids")
        if not ids:
            return 0, 0
        moment = _now() if now is None else now
        with self._transaction():
            rows = self._conn.execute(_MARK_VANISHED, {"ids": json.dumps(ids), "now": moment}).fetchall()
            orphaned = sum(
                self._conn.execute(_MARK_ORPHANED, {"m": media_id, "now": moment}).rowcount
                for media_id in sorted({int(row[0]) for row in rows if row[0] is not None})
            )
        vanished = sum(1 for row in rows if row[1] == "vanished")
        if rows:
            _LOG.info("references vanished", extra={"references": vanished, "orphaned": orphaned})
        return vanished, orphaned

    def mark_present(self, storage_ids: Sequence[int], groupable: Sequence[int], now: int | None = None) -> int:
        """Bring the references of storages back in the list back, never with a download; returns how many."""
        ids = _id_list(storage_ids, 0, "storage_ids")
        group = _id_list(groupable, 0, "groupable")
        if not ids:
            return 0
        moment = _now() if now is None else now
        values = {"ids": json.dumps(ids), "groupable": json.dumps(group), "now": moment}
        with self._transaction():
            rows = self._conn.execute(_MARK_PRESENT, values).fetchall()
            for media_id in sorted({int(row[0]) for row in rows if row[0] is not None and row[1] == "active"}):
                self._conn.execute(_CLEAR_ORPHAN, (media_id,))
            for row in rows:
                if row[0] is not None and row[1] == "active":
                    self._conn.execute(_SEED_PREVIEW_JOB, {"file_id": int(row[2]), "now": moment})
        if rows:
            _LOG.info("references back", extra={"references": len(rows)})
        return len(rows)

    def mark_reproof_due(self, storage_ids: Sequence[int], older_than: int, now: int | None = None) -> int:
        """Make the read proof of active keyed references on these storages due when older than ``older_than``."""
        ids = _id_list(storage_ids, 0, "storage_ids")
        if not ids:
            return 0
        moment = _now() if now is None else now
        with self._transaction():
            due = self._conn.execute(
                _MARK_REPROOF_DUE, {"ids": json.dumps(ids), "older_than": older_than, "now": moment}
            ).rowcount
        if due:
            _LOG.info("read proofs due", extra={"references": due})
        return due

    def reconcile_rows(self, file_ids: Sequence[int]) -> dict[int, tuple[int, str, int, int, str]]:
        """storage_id, etag, size, mtime and state of the known files among ``file_ids``."""
        rows = self._conn.execute(_RECONCILE_ROWS, (json.dumps(list(file_ids)),))
        return {int(r[0]): (int(r[1]), str(r[2]), int(r[3]), int(r[4]), str(r[5])) for r in rows}

    def mark_missing(
        self, storage_ids: Sequence[int], seen: Sequence[int], before: int, now: int | None = None
    ) -> tuple[int, int]:
        """Set aside the references of fully walked storages no slice carried; returns (set aside, marked)."""
        ids = _id_list(storage_ids, 0, "storage_ids")
        if not ids:
            return 0, 0
        moment = _now() if now is None else now
        values = {"storages": json.dumps(ids), "seen": json.dumps(list(seen)), "before": before, "now": moment}
        with self._transaction():
            rows = self._conn.execute(_MARK_MISSING, values).fetchall()
            orphaned = sum(
                self._conn.execute(_MARK_ORPHANED, {"m": media_id, "now": moment}).rowcount
                for media_id in sorted({int(row[0]) for row in rows if row[0] is not None})
            )
        if rows:
            _LOG.info("references set aside", extra={"references": len(rows), "orphaned": orphaned, "cause": "missing"})
        return len(rows), orphaned

    def forget_media(self, media_id: int) -> bool:
        """Forget one content no reference points at any more; False when one does or nothing is known of it."""
        tally = _Removal()
        with self._transaction():
            forgotten = self._forget(media_id, _now(), tally)
        _log_removal(tally, "forget")
        return forgotten

    def orphan_media(self, media_id: int, now: int | None = None) -> bool:
        """Mark a content orphaned when it has no active reference and no mark yet; True when it was marked."""
        moment = _now() if now is None else now
        with self._transaction():
            marked = self._conn.execute(_MARK_ORPHANED, {"m": media_id, "now": moment}).rowcount == 1
        if marked:
            _LOG.info("media orphaned", extra={"media": 1, "references": 0, "cause": "orphan"})
        return marked

    def retired_media(self) -> list[int]:
        """The forgotten contents whose documents the index still has to delete."""
        return [int(row[0]) for row in self._conn.execute(_RETIRED_MEDIA)]

    def mark_retired(self, media_ids: Sequence[int]) -> None:
        """The index deleted the documents of these contents: their retirement marks go."""
        with self._transaction():
            self._conn.execute(_CLEAR_RETIRED, (json.dumps(list(media_ids)),))

    def file_ref(self, file_id: int) -> FileRef | None:
        """The reference of one file, None when the file has never been seen."""
        row = self._conn.execute(_FILE_REF_ROW, (file_id,)).fetchone()
        return None if row is None else FileRef(*row)

    def file_ids_for_media(self, media_id: int) -> list[int]:
        """The files that may give a hit for this content: active references and visible samples.

        A sample is visible only while the content stands at the sample level
        (plan 02-16b): for a content with a real transcript only the active
        references of the discovery are named.
        """
        values = {"m": media_id, "sample": int(Level.SAMPLE)}
        return [int(r[0]) for r in self._conn.execute(_FILE_IDS_FOR_MEDIA, values)]

    def media_for_file(self, file_id: int) -> int | None:
        """The content of a file for its excerpt: the one with a transcript first, the discovery before the sample.

        Only what may give a hit (plan 02-15c, D-02-01a): the content of the
        reference counts while that reference is active, exactly like in
        _FILE_IDS_FOR_MEDIA. An unreadable, vanished or trashed reference
        names no content, so its file is answered like one never seen; the
        sample of such a file is hidden as well (_SAMPLE_VISIBLE). A sample
        names its content only while that content stands at the sample level
        (plan 02-16b), so it never opens the text of a real transcript.
        """
        row = self._conn.execute(_FILE_REF, (file_id,)).fetchone()
        real = None if row is None or row[0] is None or str(row[1]) != "active" else int(row[0])
        visible = self._conn.execute(_SAMPLE_VISIBLE, {"f": file_id, "sample": int(Level.SAMPLE)}).fetchone()
        sample = None if visible is None else int(visible[0])
        candidates = [m for m in (real, sample) if m is not None]
        for media_id in candidates:
            if self._conn.execute(_HAS_CURRENT, (media_id,)).fetchone() is not None:
                return media_id
        return candidates[0] if candidates else None

    # The sample layer (D-02-15), called only from api/sample.py.

    def put_sample(self, file_id: int, media_id: int) -> None:
        """Point the sample of a file at a content; file_ref is never written here."""
        if not _is_count(file_id) or file_id == 0 or not _is_count(media_id):
            raise ValueError("invalid sample_ref field")
        with self._transaction():
            self._conn.execute(_PUT_SAMPLE, {"file_id": file_id, "media_id": media_id, "now": _now()})

    def sample_media(self, file_id: int) -> int | None:
        """The content the sample of a file points at, None without a sample."""
        row = self._conn.execute(_SAMPLE_MEDIA, (file_id,)).fetchone()
        return None if row is None else int(row[0])

    # The preview jobs (plan 03-09), written only by worker/preview.py and the
    # settings sync; read by api/excerpt.py (preview_view) and occ (coverage).

    def next_preview(self, now: int | None = None) -> PreviewJob | None:
        """Claim the next preview job in the order of D-03-05 (state running) and return it, or None."""
        moment = _now() if now is None else now
        with self._transaction():
            row = self._conn.execute(_CLAIM_PREVIEW, {"now": moment}).fetchone()
        return None if row is None else PreviewJob(*row)

    def preview_source(self, media_id: int) -> tuple[int, str, int] | None:
        """(file_id, reader_uid, size) of the active keyed reference with a reader and the smallest file id."""
        row = self._conn.execute(_PREVIEW_SOURCE, (media_id,)).fetchone()
        return None if row is None else (int(row[0]), str(row[1]), int(row[2]))

    def commit_chunk(
        self,
        job: PreviewJob,
        *,
        prov: Provenance,
        words: Sequence[Word],
        next_start_ms: int,
        counters: ChunkCounters,
    ) -> bool:
        """Commit one piece of a running job in one transaction (D-03-07, TRANS-07); False when stale.

        The words, the index revision with its outbox row, next_start_ms,
        chunks_done and the counters go in together or not at all. The first
        piece with words writes the preview version and makes it current
        (the path of publish_version); every further piece appends its words
        to that version and raises the index revision, like a correction.
        Stale, with nothing written: the job no longer runs, its content left
        the epoch it was claimed in, the provenance names another epoch or
        other bytes, the current version is not the job's, or the piece would
        go back in time.
        """
        validate(prov)
        if not _is_count(next_start_ms):
            raise ValueError("invalid preview field: next_start_ms")
        tally = (
            counters.kept_words,
            counters.drop_script,
            counters.drop_language,
            counters.drop_conf,
            counters.speech_ms,
        )
        if not all(_is_count(value) for value in tally):
            raise ValueError("invalid preview field: counters")
        values = {"m": job.media_id, "e": job.epoch}
        try:
            with self._transaction():
                row = self._conn.execute(_RUNNING_JOB, values).fetchone()
                if row is None or prov.epoch != job.epoch or next_start_ms < int(row[1]):
                    raise _Rejected("stale_rejected")
                version_id = None if row[0] is None else int(row[0])
                if version_id is None and words:
                    version_id, _ = self._publish(job.media_id, prov, words)
                elif words and version_id is not None:
                    current = self._conn.execute(_CURRENT, (job.media_id,)).fetchone()
                    if current is None or int(current[0]) != version_id:
                        raise _Rejected("stale_rejected")
                    first = int(self._conn.execute(_NEXT_WORD_IDX, (version_id,)).fetchone()[0])
                    self._insert_words(version_id, first, words)
                    bumped = self._conn.execute(_BUMP_INDEX_REV, (job.media_id,)).fetchone()
                    self._conn.execute(_INSERT_OUTBOX, (job.media_id, int(bumped[0])))
                self._conn.execute(
                    _CHUNK_JOB,
                    values
                    | {
                        "next": next_start_ms,
                        "v": version_id,
                        "kept": counters.kept_words,
                        "script": counters.drop_script,
                        "language": counters.drop_language,
                        "conf": counters.drop_conf,
                        "speech": counters.speech_ms,
                        "now": _now(),
                    },
                )
        except _Rejected as rejected:
            _LOG.info("preview piece not committed", extra={"media_id": job.media_id, "reason": rejected.reason})
            return False
        _LOG.info(
            "preview piece committed",
            extra={"media_id": job.media_id, "words": len(words), "next_start_ms": next_start_ms},
        )
        return True

    def _settle(
        self,
        job: PreviewJob,
        state: str,
        *,
        reason: str | None = None,
        duration_ms: int | None = None,
        retry_at: int | None = None,
        bump: bool = False,
        now: int | None = None,
    ) -> bool:
        """Move a running job of its epoch to ``state``; False when stale."""
        values = {
            "m": job.media_id,
            "e": job.epoch,
            "state": state,
            "reason": reason,
            "duration": duration_ms,
            "retry_at": retry_at,
            "bump": 1 if bump else 0,
            "now": _now() if now is None else now,
        }
        with self._transaction():
            changed = self._conn.execute(_SETTLE_JOB, values).rowcount == 1
        if changed:
            _LOG.info("preview job settled", extra={"media_id": job.media_id, "state": state, "reason": reason})
        return changed

    def finish_preview(self, job: PreviewJob, verdict: str, now: int | None = None) -> bool:
        """The verdict of a file after its last piece (engine/catch.py file_verdict); False when stale.

        transcript completes the job; no_speech and unsupported_language skip
        it with that reason and leave the current version alone.
        """
        if verdict == _TRANSCRIPT_VERDICT:
            return self._settle(job, "complete", now=now)
        if verdict not in _TEXTLESS_VERDICTS:
            raise ValueError("invalid preview field: verdict")
        return self._settle(job, "skipped", reason=verdict, now=now)

    def skip_preview(self, job: PreviewJob, reason: str, duration_ms: int | None, now: int | None = None) -> bool:
        """Skip a running job with a reason of the probe, too_long or engine_failed; False when stale."""
        if reason not in _SKIP_REASONS:
            raise ValueError("invalid preview field: reason")
        if duration_ms is not None and not _is_count(duration_ms):
            raise ValueError("invalid preview field: duration_ms")
        return self._settle(job, "skipped", reason=reason, duration_ms=duration_ms, now=now)

    def defer_preview(self, job: PreviewJob, reason: str, *, retry_at: int, now: int | None = None) -> bool:
        """Let a running job wait with its reason until ``retry_at`` (D-03-17); its progress stays. False when stale."""
        if reason not in _DEFER_REASONS:
            raise ValueError("invalid preview field: reason")
        if not _is_count(retry_at):
            raise ValueError("invalid preview field: next_try_at")
        return self._settle(job, "waiting", reason=reason, retry_at=retry_at, now=now)

    def retry_preview(self, job: PreviewJob, *, retry_at: int, count: bool, now: int | None = None) -> bool:
        """Let a running job wait without a reason until ``retry_at``; ``count`` adds an attempt. False when stale."""
        if not _is_count(retry_at):
            raise ValueError("invalid preview field: next_try_at")
        return self._settle(job, "waiting", retry_at=retry_at, bump=count, now=now)

    def yield_preview(self, job: PreviewJob, now: int | None = None) -> bool:
        """Put a running job back in the queue at its piece boundary (D-03-06); its progress stays."""
        return self._settle(job, "queued", now=now)

    def reset_running(self) -> int:
        """Hand the running jobs of a stopped process back to the queue with their progress; returns how many."""
        with self._transaction():
            reset = self._conn.execute(_RESET_RUNNING, {"now": _now()}).rowcount
        if reset:
            _LOG.info("preview jobs reset", extra={"jobs": reset})
        return reset

    def has_waiting_event(self) -> bool:
        """True when a queued job of an event could be claimed now, the cue for a long crawl job to yield."""
        return self._conn.execute(_WAITING_EVENT).fetchone() is not None

    def requeue_too_long(self, max_ms: int) -> int:
        """Bring the too_long jobs that fit ``max_ms`` (or have no known duration) back from the start (D-03-09)."""
        if not _is_count(max_ms):
            raise ValueError("invalid preview field: max_ms")
        with self._transaction():
            back = self._conn.execute(_REQUEUE_TOO_LONG, {"max_ms": max_ms, "now": _now()}).rowcount
        if back:
            _LOG.info("too long jobs back", extra={"jobs": back, "max_ms": max_ms})
        return back

    def max_duration_hours(self) -> int:
        """The limit of the duration in hours (D-03-08); the default when unset or not a whole number above 0."""
        value = self.meta_value(MAX_DURATION_KEY)
        if value is None or not value.isdigit() or int(value) < 1:
            return DEFAULT_MAX_DURATION_HOURS
        return int(value)

    def set_max_duration_hours(self, hours: int) -> int:
        """Store the limit of the duration and return the one before."""
        if not _is_count(hours) or hours < 1:
            raise ValueError("invalid preview field: max_duration_hours")
        previous = self.max_duration_hours()
        self.set_meta(MAX_DURATION_KEY, str(hours))
        return previous

    def preview_view(self, file_id: int) -> PreviewView | None:
        """The job of a file for its play page, only through an active reference (D-03-13, D-02-15c).

        An unreadable, vanished or trashed reference, a sample and a file never
        seen all answer None alike, so the answer tells nothing about them.
        """
        row = self._conn.execute(_PREVIEW_VIEW, (file_id,)).fetchone()
        if row is None:
            return None
        return PreviewView(
            state=str(row[0]),
            reason=None if row[1] is None else str(row[1]),
            chunks_done=int(row[2]),
            next_start_ms=int(row[3]),
            level=None if row[4] is None else int(row[4]),
        )

    # Versions.

    def publish_version(self, media_id: int, prov: Provenance, words: Sequence[Word]) -> PublishResult:
        """Write a version and make it current, if and only if it is newer.

        Raises ``ValueError`` for an invalid provenance before anything is
        written. Returns ``input_mismatch`` when the input hash does not point
        at this media item and ``stale_rejected`` when the version is not
        strictly newer; in both cases nothing stays behind.
        """
        validate(prov)
        try:
            with self._transaction():
                version_id, index_rev = self._publish(media_id, prov, words)
        except _Rejected as rejected:
            _LOG.info(
                "version not published",
                extra={"media_id": media_id, "reason": rejected.reason, "level": int(prov.level)},
            )
            return PublishResult(False, None, None, rejected.reason)
        _LOG.info(
            "version published",
            extra={"media_id": media_id, "version_id": version_id, "index_rev": index_rev, "words": len(words)},
        )
        return PublishResult(True, int(version_id), index_rev, None)

    def _publish(self, media_id: int, prov: Provenance, words: Sequence[Word]) -> tuple[int, int]:
        """Inside a transaction: write a version with its words and make it current; (version_id, index_rev).

        Raises _Rejected for other bytes than the content's and for a version
        that is not strictly newer; the caller's transaction rolls back.
        """
        key = self._conn.execute(_MEDIA_FOR_KEY, (prov.input_file_sha256,)).fetchone()
        if key is None or int(key[0]) != media_id:
            raise _Rejected("input_mismatch")
        epoch = self._conn.execute(_MEDIA_EPOCH, (media_id,)).fetchone()
        if epoch is None or prov.epoch < int(epoch[0]):
            raise _Rejected("stale_rejected")
        version_id = _row_id(
            self._conn.execute(
                _INSERT_TRANSCRIPT,
                {
                    "media_id": media_id,
                    "engine": prov.engine,
                    "model_sha256": prov.model_sha256,
                    "config_version": prov.config_version,
                    "profile": prov.profile,
                    "level": int(prov.level),
                    "epoch": prov.epoch,
                    "language": prov.language,
                    "input_file_sha256": prov.input_file_sha256,
                    "now": _now(),
                },
            )
        )
        self._insert_words(version_id, 0, words)
        self._conn.execute(
            _UPSERT_CURRENT,
            {"m": media_id, "v": version_id, "e": prov.epoch, "l": int(prov.level), "c": prov.config_version},
        )
        if self._conn.execute(_CHANGES).fetchone()[0] == 0:
            raise _Rejected("stale_rejected")
        index_rev = int(self._conn.execute(_CURRENT, (media_id,)).fetchone()[4])
        self._conn.execute(_INSERT_OUTBOX, (media_id, index_rev))
        return version_id, index_rev

    def _insert_words(self, version_id: int, first_idx: int, words: Sequence[Word]) -> None:
        self._conn.executemany(
            _INSERT_WORD,
            (
                (version_id, first_idx + i, w.start_ms, w.end_ms, w.surface, w.norm, w.conf, w.src)
                for i, w in enumerate(words)
            ),
        )

    def current(self, media_id: int) -> CurrentRow | None:
        row = self._conn.execute(_CURRENT, (media_id,)).fetchone()
        return None if row is None else CurrentRow(*(int(v) for v in row))

    def current_media_ids(self) -> list[int]:
        """Every media item with a current version, what a rebuild of the index reads."""
        return [int(r[0]) for r in self._conn.execute(_CURRENT_MEDIA_IDS)]

    def count_current_at_level(self, level: int) -> int:
        return int(self._conn.execute(_COUNT_AT_LEVEL, (int(level),)).fetchone()[0])

    def machine_words(self, version_id: int) -> list[Word]:
        return [
            Word(start_ms=int(s), end_ms=int(e), surface=str(surface), norm=str(norm), conf=float(conf), src=str(src))
            for s, e, surface, norm, conf, src in self._conn.execute(_MACHINE_WORDS, (version_id,))
        ]

    # Corrections.

    def add_correction(
        self,
        media_id: int,
        start_ms: int,
        end_ms: int,
        kind: str,
        body: str,
        *,
        author_uid: str,
        base_version_id: int | None,
        base_text: str | None,
        words_json: str | None = None,
    ) -> int:
        """Store a correction; an overlapping active text correction is superseded."""
        if kind not in CORRECTION_KINDS:
            raise ValueError("invalid correction field: kind")
        if not isinstance(start_ms, int) or isinstance(start_ms, bool) or start_ms < 0:
            raise ValueError("invalid correction field: start_ms")
        if not isinstance(end_ms, int) or isinstance(end_ms, bool) or end_ms <= start_ms:
            raise ValueError("invalid correction field: end_ms")
        if not author_uid or len(author_uid) > _MAX_UID_LENGTH:
            raise ValueError("invalid correction field: author_uid")
        if words_json is not None:
            _check_words_json(words_json, start_ms, end_ms)
        with self._transaction():
            correction_id = _row_id(
                self._conn.execute(
                    _INSERT_CORRECTION,
                    {
                        "media_id": media_id,
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "kind": kind,
                        "body": body,
                        "words_json": words_json,
                        "base_version_id": base_version_id,
                        "base_text": base_text,
                        "author_uid": author_uid,
                        "now": _now(),
                    },
                )
            )
            superseded = 0
            if kind == "text":
                superseded = self._conn.execute(
                    _SUPERSEDE_TEXT,
                    {"new": correction_id, "media_id": media_id, "start_ms": start_ms, "end_ms": end_ms},
                ).rowcount
            row = self._conn.execute(_BUMP_INDEX_REV, (media_id,)).fetchone()
            if row is not None:
                self._conn.execute(_INSERT_OUTBOX, (media_id, int(row[0])))
        _LOG.info(
            "correction stored",
            extra={"media_id": media_id, "correction_id": correction_id, "superseded": superseded},
        )
        return int(correction_id)

    def active_corrections(self, media_id: int) -> list[Correction]:
        return [
            Correction(
                correction_id=int(cid),
                media_id=int(mid),
                start_ms=int(s),
                end_ms=int(e),
                kind=str(kind),
                body=str(body),
                words_json=None if wj is None else str(wj),
            )
            for cid, mid, s, e, kind, body, wj in self._conn.execute(_ACTIVE_CORRECTIONS, (media_id,))
        ]

    def effective_words(self, media_id: int) -> list[Word]:
        """What index and export read: the current machine words with corrections laid over."""
        current = self.current(media_id)
        machine = self.machine_words(current.version_id) if current is not None else []
        return overlay.effective_words(machine, self.active_corrections(media_id))

    # Index outbox.

    def pending_index_work(self) -> list[tuple[int, int]]:
        return [(int(m), int(r)) for m, r in self._conn.execute(_PENDING_OUTBOX)]

    def mark_indexed(self, media_id: int, index_rev: int) -> None:
        with self._transaction():
            self._conn.execute(_MARK_INDEXED, (media_id, index_rev))

    # Walking-skeleton sample.

    def remove_sample(self, file_id: int) -> tuple[str, int | None]:
        """Remove a seeded sample hit; real transcripts (level > 1) and file_ref are never touched (D-02-15)."""
        with self._transaction():
            sample = self._conn.execute(_SAMPLE_MEDIA, (file_id,)).fetchone()
            if sample is None:
                ref = self._conn.execute(_FILE_REF, (file_id,)).fetchone()
                if ref is None:
                    return ("not_found", None)
                return ("not_sample", None if ref[0] is None else int(ref[0]))
            media_id = int(sample[0])
            current = self.current(media_id)
            if current is not None and current.level != Level.SAMPLE:
                return ("not_sample", media_id)
            self._conn.execute(_DELETE_CURRENT, (media_id,))
            self._conn.execute(_DELETE_SAMPLE_WORDS, (media_id,))
            self._conn.execute(_DELETE_SAMPLE_TRANSCRIPTS, (media_id,))
            self._conn.execute(_DELETE_OUTBOX, (media_id,))
            self._conn.execute(_DELETE_SAMPLE_REF, (file_id,))
            if not self._conn.execute(_MEDIA_STILL_USED, {"m": media_id}).fetchone()[0]:
                self._conn.execute(_FORGET_PREVIEW_JOB, (media_id,))
                self._conn.execute(_DELETE_MEDIA_KEYS, (media_id,))
                self._conn.execute(_DELETE_MEDIA, (media_id,))
        _LOG.info("sample removed", extra={"file_id": file_id, "media_id": media_id})
        return ("removed", media_id)
