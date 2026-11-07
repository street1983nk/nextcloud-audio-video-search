"""The SQLite schema as source of truth: tables, types, keys, indirection, sample removal."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

import pytest

from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import SAMPLE_MODEL_SHA256, Level, Provenance
from audio_video_search_backend.store.repo import STATE_REASONS, Store

TABLES = {"meta", "media", "media_key", "file_ref", "transcript", "word", "current", "correction", "index_outbox"}
SHA_A = "a" * 64
SHA_B = "b" * 64
MODEL = "d" * 64


@contextmanager
def _raw(store_path: Path) -> Iterator[sqlite3.Connection]:
    """A raw connection that commits like sqlite3's own context manager and is closed afterwards."""
    with closing(sqlite3.connect(store_path)) as conn, conn:
        yield conn


def _words() -> list[Word]:
    return [
        Word(start_ms=0, end_ms=400, surface="Audiosuche", norm="audiosuche", conf=1.0, src="machine"),
        Word(start_ms=450, end_ms=900, surface="funktioniert", norm="funktioniert", conf=1.0, src="machine"),
    ]


def _sample_prov(sha: str, epoch: int = 0) -> Provenance:
    return Provenance(
        engine="sample",
        model_sha256=SAMPLE_MODEL_SHA256,
        config_version=1,
        profile="debug",
        level=Level.SAMPLE,
        epoch=epoch,
        language="de",
        input_file_sha256=sha,
    )


def _real_prov(sha: str) -> Provenance:
    return Provenance(
        engine="parakeet",
        model_sha256=MODEL,
        config_version=1,
        profile="balanced",
        level=Level.PREVIEW,
        epoch=0,
        language="de",
        input_file_sha256=sha,
    )


def _seed(store: Store, file_id: int, sha: str) -> int:
    media_id = store.media_for_file_sha256(sha)
    store.upsert_file_ref(
        file_id, media_id, storage_id=0, etag="", size=10, mtime=0, state="sample", stage="keyed", reason="sample"
    )
    assert store.publish_version(media_id, _sample_prov(sha), _words()).published
    return media_id


def _count(path: Path, table: str, media_id: int) -> int:
    queries = {
        "transcript": "SELECT COUNT(*) FROM transcript WHERE media_id = ?",
        "word": "SELECT COUNT(*) FROM word JOIN transcript USING (version_id) WHERE media_id = ?",
        "current": "SELECT COUNT(*) FROM current WHERE media_id = ?",
        "file_ref": "SELECT COUNT(*) FROM file_ref WHERE media_id = ?",
        "index_outbox": "SELECT COUNT(*) FROM index_outbox WHERE media_id = ?",
        "media": "SELECT COUNT(*) FROM media WHERE media_id = ?",
        "media_key": "SELECT COUNT(*) FROM media_key WHERE media_id = ?",
    }
    with _raw(path) as conn:
        return conn.execute(queries[table], (media_id,)).fetchone()[0]


def test_fresh_database_has_meta_marks(store: Store, tmp_path: Path) -> None:
    assert store.schema_version() == 2
    with _raw(tmp_path / "state.db") as conn:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    assert meta["schema_version"] == "2"
    assert "index_generation" in meta


def test_all_nine_tables_exist(store: Store, tmp_path: Path) -> None:
    del store
    with _raw(tmp_path / "state.db") as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert names >= TABLES


def test_every_ms_column_is_integer(store: Store, tmp_path: Path) -> None:
    del store
    seen = 0
    with _raw(tmp_path / "state.db") as conn:
        for table in sorted(TABLES):
            for _cid, name, col_type, *_rest in conn.execute(f"PRAGMA table_info({table})"):
                if name.endswith("_ms"):
                    seen += 1
                    assert col_type == "INTEGER", (table, name)
    assert seen >= 4


def test_keys(store: Store, tmp_path: Path) -> None:
    del store
    with _raw(tmp_path / "state.db") as conn:
        file_ref = {row[1]: row[5] for row in conn.execute("PRAGMA table_info(file_ref)")}
        assert file_ref["file_id"] == 1
        conn.execute("INSERT INTO media (media_id, created_at) VALUES (1, 0)")
        conn.execute("INSERT INTO media_key (kind, value, media_id) VALUES ('file_sha256', 'x', 1)")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO media_key (kind, value, media_id) VALUES ('file_sha256', 'x', 1)")


def test_open_twice_is_idempotent(tmp_path: Path) -> None:
    first = Store.open(tmp_path / "state.db")
    media_id = first.media_for_file_sha256(SHA_A)
    first.close()
    second = Store.open(tmp_path / "state.db")
    try:
        assert second.schema_version() == 2
        assert second.media_for_file_sha256(SHA_A) == media_id
    finally:
        second.close()


def test_wal_is_active(store: Store, tmp_path: Path) -> None:
    del store
    with _raw(tmp_path / "state.db") as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_read_only_store_refuses_writes(store: Store, tmp_path: Path) -> None:
    del store
    reader = Store.open(tmp_path / "state.db", read_only=True)
    try:
        assert reader.schema_version() == 2
        with pytest.raises(sqlite3.OperationalError):
            reader.media_for_file_sha256(SHA_A)
    finally:
        reader.close()


def test_media_indirection(store: Store, tmp_path: Path) -> None:
    first = store.media_for_file_sha256(SHA_A)
    assert store.media_for_file_sha256(SHA_A) == first
    other = store.media_for_file_sha256(SHA_B)
    assert other != first
    with _raw(tmp_path / "state.db") as conn:
        conn.execute(
            "INSERT INTO media_key (kind, value, media_id) VALUES ('audio_pkt_sha256', ?, ?)", ("e" * 64, first)
        )
        rows = conn.execute("SELECT kind FROM media_key WHERE media_id = ? ORDER BY kind", (first,)).fetchall()
    assert [r[0] for r in rows] == ["audio_pkt_sha256", "file_sha256"]


def test_media_for_file_sha256_rejects_non_hex(store: Store) -> None:
    with pytest.raises(ValueError, match="sha256"):
        store.media_for_file_sha256("nope")


def test_file_ref_roundtrip(store: Store) -> None:
    media_id = store.media_for_file_sha256(SHA_A)
    store.upsert_file_ref(
        42, media_id, storage_id=11, etag="e1", size=5, mtime=1, state="sample", stage="keyed", reason=""
    )
    store.upsert_file_ref(
        43, media_id, storage_id=12, etag="e2", size=5, mtime=1, state="sample", stage="keyed", reason=None
    )
    assert store.media_for_file(42) == media_id
    assert store.media_for_file(99) is None
    assert store.file_ids_for_media(media_id) == [42, 43]
    store.upsert_file_ref(
        43, None, storage_id=12, etag="e3", size=5, mtime=2, state="sample", stage="pending", reason=None
    )
    assert store.file_ids_for_media(media_id) == [42]
    assert store.media_for_file(43) is None


def test_file_ref_reason_is_a_closed_list(store: Store) -> None:
    assert "sample" in STATE_REASONS
    with pytest.raises(ValueError, match="reason"):
        store.upsert_file_ref(
            1, None, storage_id=0, etag="", size=0, mtime=0, state="sample", stage="keyed", reason="Sitzung.mp4"
        )
    with pytest.raises(ValueError, match="state"):
        store.upsert_file_ref(
            1, None, storage_id=0, etag="", size=0, mtime=0, state="Sitzung.mp4", stage="keyed", reason=None
        )


def test_count_current_at_level(store: Store) -> None:
    assert store.count_current_at_level(Level.SAMPLE) == 0
    _seed(store, 1, SHA_A)
    _seed(store, 2, SHA_B)
    assert store.count_current_at_level(Level.SAMPLE) == 2
    assert store.count_current_at_level(Level.PREVIEW) == 0


def test_remove_sample(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    media_id = _seed(store, 7, SHA_A)
    assert store.remove_sample(7) == ("removed", media_id)
    for table in ("transcript", "word", "current", "file_ref", "index_outbox", "media", "media_key"):
        assert _count(path, table, media_id) == 0, table
    assert store.remove_sample(7) == ("not_found", None)


def test_remove_sample_never_touches_real_transcripts(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    media_id = _seed(store, 7, SHA_A)
    assert store.publish_version(media_id, _real_prov(SHA_A), _words()).published
    assert store.remove_sample(7) == ("not_sample", media_id)
    for table in ("transcript", "word", "current", "file_ref", "media"):
        assert _count(path, table, media_id) > 0, table


def test_remove_sample_keeps_media_with_corrections(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    media_id = _seed(store, 7, SHA_A)
    store.add_correction(
        media_id, 0, 400, "text", "Audiosuche", author_uid="alice", base_version_id=None, base_text=None
    )
    assert store.remove_sample(7) == ("removed", media_id)
    assert _count(path, "current", media_id) == 0
    assert _count(path, "transcript", media_id) == 0
    assert _count(path, "media", media_id) == 1
    assert _count(path, "media_key", media_id) == 1


def test_remove_sample_keeps_media_shared_with_another_file(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    media_id = _seed(store, 7, SHA_A)
    store.upsert_file_ref(
        8, media_id, storage_id=0, etag="", size=10, mtime=0, state="sample", stage="keyed", reason="sample"
    )
    assert store.remove_sample(7) == ("removed", media_id)
    assert store.file_ids_for_media(media_id) == [8]
    assert _count(path, "media", media_id) == 1


def test_remove_sample_keeps_a_reference_of_the_discovery(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    media_id = store.media_for_file_sha256(SHA_A)
    store.upsert_file_ref(
        7, media_id, storage_id=4, etag="e", size=10, mtime=1, state="active", stage="keyed", reason=None, proved_at=3
    )
    before = store.file_ref(7)
    assert store.publish_version(media_id, _sample_prov(SHA_A), _words()).published

    assert store.remove_sample(7) == ("removed", media_id)

    assert store.file_ref(7) == before
    assert _count(path, "current", media_id) == 0
    assert _count(path, "transcript", media_id) == 0
    assert _count(path, "media", media_id) == 1
