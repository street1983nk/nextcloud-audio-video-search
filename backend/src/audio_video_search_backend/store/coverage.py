"""Counting by content and the work stock list, read only (plan 02-09, D-02-06).

The admin number is "X of Y contents transcribed (N files)". Both X and Y come
from the SAME set of references, the active ones (Findling #25, pitfall 4):

- Y (``contents``) counts distinct keys over active references. The key of a
  reference is its media_id; without one, the media_id of an active sibling
  with the same prefilter key (one copy hashed, the other not yet, still one
  content); without that, the prefilter key itself; without that, the file.
- X (``transcribed``) counts media items with a current version that have an
  active reference and no orphan mark. Every such media item is the key of
  that active reference, so X is a subset of Y by construction and the rate
  never goes above 100 %.

unreadable, vanished and trashed references count in neither, a sample
(sample_ref, D-02-15) is no reference at all, and an
unreadable copy is never pulled in through a keyed sibling: the sibling counts
for itself, the unreadable copy adds nothing.

``dueWork`` is what the capture still has to do now: stage pending, probing or
fetching with no retry time or one that has come, on a reference the capture
may fetch (active or unreadable). A failed reference waiting for its planned
retry is not due, so the acceptance test does not wait for a retry hours
away.

``byPreview`` counts the preview jobs (plan 03-09, D-03-13): a job with a
reason under its reason code (skipped, or waiting for disk space), every other
one under its state, so a retry that waits without a reason counts as waiting.
The names are the closed lists of repo.py; a value outside them is never
reported, and no file id or name is part of it (T-03-31).

Only ids, codes and numbers leave this module. Every statement is a constant
with placeholders and runs on any connection, also a read only one.
"""

import sqlite3
import time
from dataclasses import dataclass
from typing import Final

from audio_video_search_backend.store.repo import PREVIEW_REASONS, PREVIEW_STATES, STAGES, STATES

WORKSTOCK_MAX_LIMIT: Final = 1000

_CONTENTS: Final = """
SELECT COUNT(DISTINCT key) FROM (
  SELECT COALESCE(
           r.media_id,
           (SELECT s.media_id FROM file_ref s
             WHERE s.prefilter_key = r.prefilter_key AND s.media_id IS NOT NULL AND s.state = 'active'
             ORDER BY s.file_id LIMIT 1),
           r.prefilter_key,
           'f' || r.file_id) AS key
  FROM file_ref r WHERE r.state = 'active')
"""
_TRANSCRIBED: Final = """
SELECT COUNT(*) FROM current c JOIN media m ON m.media_id = c.media_id
WHERE m.orphaned_at IS NULL
  AND EXISTS (SELECT 1 FROM file_ref r WHERE r.media_id = c.media_id AND r.state = 'active')
"""
_FILES: Final = "SELECT COUNT(*) FROM file_ref WHERE state = 'active'"
_BY_STATE: Final = "SELECT state, COUNT(*) FROM file_ref GROUP BY state"
_BY_STAGE: Final = "SELECT stage, COUNT(*) FROM file_ref GROUP BY stage"
_BY_PREVIEW: Final = "SELECT COALESCE(reason, state), COUNT(*) FROM preview_job GROUP BY 1"
_PREVIEW_NAMES: Final = PREVIEW_STATES | PREVIEW_REASONS
_DUE_WORK: Final = """
SELECT COUNT(*) FROM file_ref
WHERE stage IN ('pending', 'probing', 'fetching') AND state IN ('active', 'unreadable')
  AND (next_try_at IS NULL OR next_try_at <= :now)
"""
_WORKSTOCK: Final = """
SELECT file_id, media_id, storage_id, state, stage, reason FROM file_ref
WHERE file_id > :after AND (:state IS NULL OR state = :state)
ORDER BY file_id LIMIT :limit
"""


@dataclass(frozen=True, slots=True)
class Coverage:
    contents: int
    transcribed: int
    files: int
    by_state: dict[str, int]
    by_stage: dict[str, int]
    due_work: int
    by_preview: dict[str, int]

    def as_wire(self) -> dict[str, object]:
        """The answer of GET /coverage, a fixed set of keys."""
        return {
            "contents": self.contents,
            "transcribed": self.transcribed,
            "files": self.files,
            "byState": self.by_state,
            "byStage": self.by_stage,
            "dueWork": self.due_work,
            "byPreview": self.by_preview,
        }


def _one(conn: sqlite3.Connection, sql: str, params: dict[str, object] | None = None) -> int:
    return int(conn.execute(sql, params or {}).fetchone()[0])


def _grouped(conn: sqlite3.Connection, sql: str, names: frozenset[str]) -> dict[str, int]:
    """Every name of the closed list, zero when absent; a value outside the list is never reported."""
    counts = dict.fromkeys(sorted(names), 0)
    for name, count in conn.execute(sql):
        if name in counts:
            counts[name] = int(count)
    return counts


def coverage(conn: sqlite3.Connection, now: int | None = None) -> Coverage:
    """The numbers of D-02-06 in one read transaction, so all of them describe one state."""
    moment = int(time.time()) if now is None else now
    own_transaction = not conn.in_transaction
    if own_transaction:
        conn.execute("BEGIN")
    try:
        return Coverage(
            contents=_one(conn, _CONTENTS),
            transcribed=_one(conn, _TRANSCRIBED),
            files=_one(conn, _FILES),
            by_state=_grouped(conn, _BY_STATE, STATES),
            by_stage=_grouped(conn, _BY_STAGE, STAGES),
            due_work=_one(conn, _DUE_WORK, {"now": moment}),
            by_preview=_grouped(conn, _BY_PREVIEW, _PREVIEW_NAMES),
        )
    finally:
        if own_transaction:
            conn.execute("COMMIT")


@dataclass(frozen=True, slots=True)
class WorkstockPage:
    files: list[dict[str, object]]
    next: int | None

    def as_wire(self) -> dict[str, object]:
        return {"files": self.files, "next": self.next}


def workstock(conn: sqlite3.Connection, state: str | None, after: int, limit: int) -> WorkstockPage:
    """One page of the work stock by file id; ``next`` is the ``after`` of the following page."""
    if state is not None and state not in STATES:
        raise ValueError("invalid workstock field: state")
    if not 1 <= limit <= WORKSTOCK_MAX_LIMIT:
        raise ValueError("invalid workstock field: limit")
    if after < 0:
        raise ValueError("invalid workstock field: after")
    rows = conn.execute(_WORKSTOCK, {"after": after, "state": state, "limit": limit}).fetchall()
    files: list[dict[str, object]] = [
        {
            "fileId": int(file_id),
            "mediaId": None if media_id is None else int(media_id),
            "storageId": int(storage_id),
            "state": str(row_state),
            "stage": str(stage),
            "reason": None if reason is None else str(reason),
        }
        for file_id, media_id, storage_id, row_state, stage, reason in rows
    ]
    following = int(rows[-1][0]) if len(rows) == limit else None
    return WorkstockPage(files=files, next=following)
