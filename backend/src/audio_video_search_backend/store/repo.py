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
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from audio_video_search_backend.model import overlay
from audio_video_search_backend.model.overlay import Correction, Word
from audio_video_search_backend.model.provenance import Level, Provenance, validate
from audio_video_search_backend.store.migrate import migrate_v1_to_v2, stored_version

_LOG: Final = logging.getLogger(__name__)

SCHEMA_VERSION: Final = 2
_SCHEMA_FILE: Final = Path(__file__).with_name("schema.sql")
_BUSY_TIMEOUT_MS: Final = 5000

# Closed lists for file_ref (schema v2). These values reach an admin page
# later, and a free field is the shortest path to a file name where no file
# name may appear. An empty reason is stored as NULL.
#
# state: whether the reference counts and gives hits. Only active and the
# walking-skeleton sample do; unreadable (the read proof or the download
# failed), vanished (the storage is no longer mounted) and trashed never give
# a hit (T-02-06, _FILE_IDS_FOR_MEDIA).
STATES: Final = frozenset({"active", "unreadable", "vanished", "trashed", "sample"})
# stage: where the discovery of this file stands.
STAGES: Final = frozenset({"pending", "probing", "fetching", "keyed", "failed"})
STATE_REASONS: Final = frozenset(
    {
        "sample",
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
_HEX64: Final = re.compile(r"[0-9a-f]{64}")
CORRECTION_KINDS: Final = frozenset({"text", "speaker", "sound"})
_MAX_UID_LENGTH: Final = 64

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
_INSERT_MEDIA: Final = "INSERT INTO media (created_at) VALUES (?)"
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
# Only a reference that may give a hit: state active, or a sample of the
# walking skeleton. unreadable, vanished and trashed never reach the search.
_FILE_IDS_FOR_MEDIA: Final = """
SELECT file_id FROM file_ref WHERE media_id = ? AND state IN ('active', 'sample') ORDER BY file_id
"""
_FILE_REF_ROW: Final = """
SELECT file_id, media_id, storage_id, prefilter_key, reader_uid, etag, size, mtime, state, stage, reason,
       attempts, next_try_at, proved_at, vanished_since, updated_at
FROM file_ref WHERE file_id = ?
"""
_FILE_REF: Final = "SELECT media_id, state FROM file_ref WHERE file_id = ?"

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
_DELETE_FILE_REF: Final = "DELETE FROM file_ref WHERE file_id = ?"
_MEDIA_STILL_USED: Final = """
SELECT EXISTS (SELECT 1 FROM file_ref WHERE media_id = :m)
    OR EXISTS (SELECT 1 FROM correction WHERE media_id = :m)
    OR EXISTS (SELECT 1 FROM transcript WHERE media_id = :m)
"""
_DELETE_MEDIA_KEYS: Final = "DELETE FROM media_key WHERE media_id = ?"
_DELETE_MEDIA: Final = "DELETE FROM media WHERE media_id = ?"


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
class CurrentRow:
    """The pointer to the current version of one media item."""

    version_id: int
    epoch: int
    level: int
    config_version: int
    index_rev: int


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

        A file of version 1 is lifted to version 2 in one transaction before
        the schema script runs (store/migrate.py). A reader never migrates, and
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

    def file_ref(self, file_id: int) -> FileRef | None:
        """The reference of one file, None when the file has never been seen."""
        row = self._conn.execute(_FILE_REF_ROW, (file_id,)).fetchone()
        return None if row is None else FileRef(*row)

    def file_ids_for_media(self, media_id: int) -> list[int]:
        """The files that may give a hit for this content: state active or sample only."""
        return [int(r[0]) for r in self._conn.execute(_FILE_IDS_FOR_MEDIA, (media_id,))]

    def media_for_file(self, file_id: int) -> int | None:
        row = self._conn.execute(_FILE_REF, (file_id,)).fetchone()
        return None if row is None or row[0] is None else int(row[0])

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
                self._conn.executemany(
                    _INSERT_WORD,
                    (
                        (version_id, i, w.start_ms, w.end_ms, w.surface, w.norm, w.conf, w.src)
                        for i, w in enumerate(words)
                    ),
                )
                self._conn.execute(
                    _UPSERT_CURRENT,
                    {
                        "m": media_id,
                        "v": version_id,
                        "e": prov.epoch,
                        "l": int(prov.level),
                        "c": prov.config_version,
                    },
                )
                if self._conn.execute(_CHANGES).fetchone()[0] == 0:
                    raise _Rejected("stale_rejected")
                index_rev = int(self._conn.execute(_CURRENT, (media_id,)).fetchone()[4])
                self._conn.execute(_INSERT_OUTBOX, (media_id, index_rev))
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
        """Remove a seeded sample hit; real transcripts (level > 1) and real references are never touched."""
        with self._transaction():
            ref = self._conn.execute(_FILE_REF, (file_id,)).fetchone()
            if ref is None:
                return ("not_found", None)
            media_id = None if ref[0] is None else int(ref[0])
            current = self.current(media_id) if media_id is not None else None
            if current is not None and current.level != Level.SAMPLE:
                return ("not_sample", media_id)
            if current is None and ref[1] != "sample":
                return ("not_sample", media_id)
            if media_id is not None:
                self._conn.execute(_DELETE_CURRENT, (media_id,))
                self._conn.execute(_DELETE_SAMPLE_WORDS, (media_id,))
                self._conn.execute(_DELETE_SAMPLE_TRANSCRIPTS, (media_id,))
                self._conn.execute(_DELETE_OUTBOX, (media_id,))
            # A reference the discovery made stays: only the sample's own row goes.
            if ref[1] == "sample":
                self._conn.execute(_DELETE_FILE_REF, (file_id,))
            if media_id is not None and not self._conn.execute(_MEDIA_STILL_USED, {"m": media_id}).fetchone()[0]:
                self._conn.execute(_DELETE_MEDIA_KEYS, (media_id,))
                self._conn.execute(_DELETE_MEDIA, (media_id,))
        _LOG.info("sample removed", extra={"file_id": file_id, "media_id": media_id})
        return ("removed", media_id)
