"""The derived index behind one narrow interface: publish, retire, search, rebuild.

SQLite is the source of truth; this index is derived and can be rebuilt from it
at any time (phase research, decision 2 and pattern 3). The order of one change,
fixed by the planner:

1. SQLite commits the new version together with an ``index_outbox`` row
   (store/repo.py), so ``current.index_rev`` rises.
2. ``publish``: documents of ``(media_id, index_rev)`` are added and committed.
3. ``retire``: documents of the same media_id with another revision are deleted
   and committed.
4. ``store.mark_indexed`` removes the outbox row.

Between 2 and 3 both revisions stand; the search route keeps per media item the
highest revision that ``current`` admits (api/search.py). A crash anywhere leaves
an outbox row or a stale document, and ``reconcile`` at the next start repairs
both. ``reconcile`` and ``rebuild_from_store`` read SQLite only through the
Store interface.

The keys are unsigned columns. A Python int handed to ``delete_documents_by_term``
becomes an I64 term that never matches a U64 column and deletes nothing (Findling
``writer.py``, measured on tantivy 0.26), so deletion always goes through
``Query.term_query``, which takes the type from the schema. Documents are built
with ``add_unsigned`` for the same reason.

Nothing here logs a word, a term or a path; only ids and counts.
"""

import logging
import shutil
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from tantivy import Document, Index, IndexWriter, Occur, Query

from audio_video_search_backend.index.analyzer import (
    cached_german_analyzer,
    english_analyzer,
    french_analyzer,
    normalize,
)
from audio_video_search_backend.index.open import expected_marks, open_index, open_reader
from audio_video_search_backend.index.schema import (
    BODY_FIELDS,
    FIELD_BODY_DE,
    FIELD_BODY_EN,
    FIELD_BODY_FR,
    FIELD_INDEX_REV,
    FIELD_MEDIA_ID,
    FIELD_SEG_IDX,
    FIELD_START_MS,
)
from audio_video_search_backend.index.wordlist import load_constituents, wordlist_hash
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.store.repo import Store

_LOG: Final = logging.getLogger(__name__)

MAX_TERM_CHARS: Final = 200
# tantivy needs at least 15 MB per writer thread; one thread, a little above.
WRITER_HEAP_BYTES: Final = 20_000_000
GENERATION_PREFIX: Final = "gen-"
# Upper bound for the key listing of reconcile; far above what phase 1 holds.
_MAX_KEYS: Final = 1_000_000


@dataclass(frozen=True, slots=True)
class Segment:
    """A run of words that becomes one index document; times in whole ms."""

    seg_idx: int
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True, slots=True)
class IndexHit:
    """One candidate from the index; the search route checks it against SQLite."""

    media_id: int
    index_rev: int
    seg_idx: int
    start_ms: int
    score: float
    text: str


def segments_from_words(words: Sequence[Word], *, max_gap_ms: int = 1500, max_words: int = 40) -> list[Segment]:
    """Cut words into segments at a pause above ``max_gap_ms`` or after ``max_words``."""
    segments: list[Segment] = []
    run: list[Word] = []

    def close() -> None:
        if run:
            text = " ".join(w.surface for w in run)
            segments.append(Segment(len(segments), int(run[0].start_ms), int(run[-1].end_ms), text))
            run.clear()

    for word in words:
        if run and (len(run) >= max_words or word.start_ms - run[-1].end_ms > max_gap_ms):
            close()
        run.append(word)
    close()
    return segments


def _unsigned(document: Document, field: str) -> int:
    value = document.get_first(field)
    if not isinstance(value, int):
        raise RuntimeError(f"index document without {field}")
    return value


class SearchIndex:
    """One open index directory with its single writer."""

    def __init__(self, index: Index, writer: IndexWriter, constituents: Sequence[str]) -> None:
        self._index = index
        self._schema = index.schema
        self._writer: IndexWriter | None = writer
        self._lock = threading.RLock()
        # The query side of the chains, for the word that carries the hit time.
        # German comes from the process cache that open_index filled.
        self._chains = (
            cached_german_analyzer(wordlist_hash(constituents), constituents),
            english_analyzer(),
            french_analyzer(),
        )
        open_reader(index)

    @classmethod
    def open(cls, path: Path, *, constituents: Sequence[str] | None = None) -> "SearchIndex":
        """Open (or create) the directory as it is, without comparing marks."""
        entries = load_constituents() if constituents is None else constituents
        index = open_index(path, entries)
        return cls(index, index.writer(heap_size=WRITER_HEAP_BYTES, num_threads=1), entries)

    @classmethod
    def open_generation(cls, root: Path, store: Store, *, constituents: Sequence[str] | None = None) -> "SearchIndex":
        """Open the current generation under ``root``; rebuild from SQLite when the marks differ.

        A missing directory or a mark that differs from :func:`expected_marks`
        (schema, analyzer with the word list digest, tantivy format) raises the
        generation, builds a fresh directory from SQLite, writes the marks and
        removes older generation directories.
        """
        entries = load_constituents() if constituents is None else constituents
        marks = expected_marks(wordlist_hash(entries))
        stale = any(store.meta_value(key) != value for key, value in marks.items())
        generation = store.index_generation()
        directory = root / f"{GENERATION_PREFIX}{generation}"
        if stale or not directory.is_dir():
            generation = store.bump_index_generation()
            directory = root / f"{GENERATION_PREFIX}{generation}"
            shutil.rmtree(directory, ignore_errors=True)
            opened = cls.open(directory, constituents=entries)
            count = opened.rebuild_from_store(store)
            for key, value in marks.items():
                store.set_meta(key, value)
            _LOG.info("index rebuilt from sqlite", extra={"generation": generation, "media": count})
            for old in root.glob(f"{GENERATION_PREFIX}*"):
                if old != directory:
                    # Windows keeps memory maps of a closed index a little longer;
                    # a leftover is removed at a later start.
                    shutil.rmtree(old, ignore_errors=True)
            return opened
        return cls.open(directory, constituents=entries)

    def close(self) -> None:
        with self._lock:
            writer, self._writer = self._writer, None
            if writer is not None:
                writer.wait_merging_threads()

    def _require_writer(self) -> IndexWriter:
        if self._writer is None:
            raise RuntimeError("the search index is closed")
        return self._writer

    def _term(self, field: str, value: int) -> Query:
        return Query.term_query(self._schema, field, value)

    def _add(self, writer: IndexWriter, media_id: int, index_rev: int, segments: Sequence[Segment]) -> None:
        writer.delete_documents_by_query(
            Query.boolean_query(
                [
                    (Occur.Must, self._term(FIELD_MEDIA_ID, media_id)),
                    (Occur.Must, self._term(FIELD_INDEX_REV, index_rev)),
                ]
            )
        )
        for segment in segments:
            text = normalize(segment.text)
            document = Document()
            document.add_unsigned(FIELD_MEDIA_ID, media_id)
            document.add_unsigned(FIELD_INDEX_REV, index_rev)
            document.add_unsigned(FIELD_SEG_IDX, segment.seg_idx)
            document.add_unsigned(FIELD_START_MS, segment.start_ms)
            document.add_text(FIELD_BODY_DE, text)
            document.add_text(FIELD_BODY_EN, text)
            document.add_text(FIELD_BODY_FR, text)
            writer.add_document(document)

    def _commit(self, writer: IndexWriter) -> None:
        writer.commit()
        self._index.reload()

    def publish(self, media_id: int, index_rev: int, segments: Sequence[Segment]) -> None:
        """Add the documents of one revision and commit; the same revision twice stays single."""
        with self._lock:
            writer = self._require_writer()
            self._add(writer, media_id, index_rev, segments)
            self._commit(writer)
        _LOG.info("index revision published", extra={"media_id": media_id, "index_rev": index_rev})

    def retire(self, media_id: int, keep_rev: int) -> None:
        """Delete every document of the media item with a revision other than ``keep_rev``.

        ``keep_rev=0`` deletes all of them, revisions start at 1.
        """
        with self._lock:
            writer = self._require_writer()
            writer.delete_documents_by_query(
                Query.boolean_query(
                    [
                        (Occur.Must, self._term(FIELD_MEDIA_ID, media_id)),
                        (Occur.MustNot, self._term(FIELD_INDEX_REV, keep_rev)),
                    ]
                )
            )
            self._commit(writer)

    def search(self, term: str, limit: int) -> list[IndexHit]:
        """Candidates for a term over the three body fields; a broken query is an empty list."""
        text = normalize(term[:MAX_TERM_CHARS]).strip()
        if not text or limit <= 0:
            return []
        try:
            query = self._index.parse_query(text, list(BODY_FIELDS), conjunction_by_default=True)
        except ValueError:
            return []
        searcher = self._index.searcher()
        hits: list[IndexHit] = []
        for score, address in searcher.search(query, limit).hits:
            document = searcher.doc(address)
            hits.append(
                IndexHit(
                    media_id=_unsigned(document, FIELD_MEDIA_ID),
                    index_rev=_unsigned(document, FIELD_INDEX_REV),
                    seg_idx=_unsigned(document, FIELD_SEG_IDX),
                    start_ms=_unsigned(document, FIELD_START_MS),
                    score=float(score),
                    text=str(document.get_first(FIELD_BODY_DE) or ""),
                )
            )
        return hits

    def first_match_ms(self, term: str, words: Sequence[Word]) -> int | None:
        """The start of the first word that shares a token with the term in any chain."""
        text = normalize(term[:MAX_TERM_CHARS])
        wanted = [set(chain.analyze(text)) for chain in self._chains]
        if not any(wanted):
            return None
        for word in words:
            surface = normalize(word.surface)
            for chain, tokens in zip(self._chains, wanted, strict=True):
                if tokens and tokens.intersection(chain.analyze(surface)):
                    return int(word.start_ms)
        return None

    def _keys(self) -> dict[int, set[int]]:
        """Every (media_id, index_rev) pair in the index, through a terms aggregation."""
        searcher = self._index.searcher()
        if searcher.num_docs == 0:
            return {}
        answer = searcher.aggregate(
            Query.all_query(),
            {
                "media": {
                    "terms": {"field": FIELD_MEDIA_ID, "size": _MAX_KEYS},
                    "aggs": {"revs": {"terms": {"field": FIELD_INDEX_REV, "size": _MAX_KEYS}}},
                }
            },
        )
        keys: dict[int, set[int]] = {}
        for bucket in answer["media"]["buckets"]:
            keys[int(bucket["key"])] = {int(rev["key"]) for rev in bucket["revs"]["buckets"]}
        return keys

    def _index_current(self, store: Store, media_id: int) -> None:
        """Publish the current revision of one media item from SQLite and retire the rest."""
        current = store.current(media_id)
        if current is None:
            self.retire(media_id, keep_rev=0)
            return
        self.publish(media_id, current.index_rev, segments_from_words(store.effective_words(media_id)))
        self.retire(media_id, keep_rev=current.index_rev)
        store.mark_indexed(media_id, current.index_rev)

    def reconcile(self, store: Store) -> int:
        """Bring the index in line with SQLite; returns how many media items were touched.

        Pending outbox rows are published (or retired when the media item has no
        current version any more). Documents of a media item without a current
        version, or with a revision other than the current one, are deleted; a
        current version missing from the index is added.
        """
        touched: set[int] = set()
        for media_id, index_rev in store.pending_index_work():
            current = store.current(media_id)
            if current is None:
                self.retire(media_id, keep_rev=0)
                store.mark_indexed(media_id, index_rev)
            else:
                self._index_current(store, media_id)
            touched.add(media_id)

        keys = self._keys()
        for media_id, revs in keys.items():
            if media_id in touched:
                continue
            current = store.current(media_id)
            if current is None or revs != {current.index_rev}:
                self._index_current(store, media_id)
                touched.add(media_id)
        for media_id in store.current_media_ids():
            if media_id not in keys and media_id not in touched:
                self._index_current(store, media_id)
                touched.add(media_id)
        if touched:
            _LOG.info("index reconciled", extra={"media": len(touched)})
        return len(touched)

    def rebuild_from_store(self, store: Store) -> int:
        """Drop every document and write all current versions from SQLite; returns the count."""
        media_ids = store.current_media_ids()
        revisions: list[tuple[int, int]] = []
        with self._lock:
            writer = self._require_writer()
            writer.delete_all_documents()
            for media_id in media_ids:
                current = store.current(media_id)
                if current is None:
                    continue
                self._add(writer, media_id, current.index_rev, segments_from_words(store.effective_words(media_id)))
                revisions.append((media_id, current.index_rev))
            self._commit(writer)
        for media_id, index_rev in revisions:
            store.mark_indexed(media_id, index_rev)
        for media_id, index_rev in store.pending_index_work():
            if store.current(media_id) is None:
                store.mark_indexed(media_id, index_rev)
        return len(revisions)
