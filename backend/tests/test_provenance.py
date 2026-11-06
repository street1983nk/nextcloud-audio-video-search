"""Provenance of a transcript version and the order that decides which one is current.

Decision 5 of the phase research: every version carries engine, model hash,
config version, profile, level, epoch, language and the hash of the input file.
The order is lexicographic over (epoch, level, config_version); a tie is stale.
"""

import hashlib
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import (
    ENGINES,
    PROFILES,
    SAMPLE_MODEL_SHA256,
    Level,
    Provenance,
    order_key,
    validate,
)
from audio_video_search_backend.store.repo import PublishResult, Store

HEX_A = "a" * 64
HEX_B = "b" * 64
INPUT = "c" * 64


def _prov(**changes: object) -> Provenance:
    base = Provenance(
        engine="parakeet",
        model_sha256=HEX_A,
        config_version=1,
        profile="balanced",
        level=Level.PREVIEW,
        epoch=0,
        language="de",
        input_file_sha256=INPUT,
    )
    return replace(base, **changes)  # pyright: ignore[reportArgumentType]


def test_levels_leave_room_between_them() -> None:
    assert [int(level) for level in Level] == [1, 100, 150, 200, 300]
    assert Level.REFINED_L3 > Level.REFINED > Level.SELECTIVE > Level.PREVIEW > Level.SAMPLE


def test_closed_lists() -> None:
    assert frozenset({"sample", "parakeet", "whisper-turbo", "whisper-large-v3", "rover"}) == ENGINES
    assert frozenset({"fast", "balanced", "quality", "debug"}) == PROFILES


def test_sample_model_hash_is_the_hash_of_the_fixed_text() -> None:
    assert hashlib.sha256(b"audio_video_search_backend sample v1").hexdigest() == SAMPLE_MODEL_SHA256


def test_valid_provenance_passes() -> None:
    validate(_prov())
    validate(_prov(engine="sample", model_sha256=SAMPLE_MODEL_SHA256, level=Level.SAMPLE, language="und"))
    validate(_prov(engine="rover", model_sha256=f"{HEX_A},{HEX_B}", level=Level.REFINED))


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"engine": "cloud"}, "engine"),
        ({"engine": ""}, "engine"),
        ({"model_sha256": "abc"}, "model_sha256"),
        ({"model_sha256": "A" * 64}, "model_sha256"),
        ({"model_sha256": ""}, "model_sha256"),
        ({"engine": "rover", "model_sha256": f"{HEX_B},{HEX_A}"}, "model_sha256"),
        ({"engine": "rover", "model_sha256": HEX_A}, "model_sha256"),
        ({"engine": "sample", "model_sha256": HEX_A}, "model_sha256"),
        ({"config_version": 0}, "config_version"),
        ({"profile": "turbo"}, "profile"),
        ({"level": 7}, "level"),
        ({"epoch": -1}, "epoch"),
        ({"language": "es"}, "language"),
        ({"language": ""}, "language"),
        ({"input_file_sha256": ""}, "input_file_sha256"),
        ({"input_file_sha256": "z" * 64}, "input_file_sha256"),
    ],
)
def test_invalid_provenance_names_the_field(changes: dict[str, object], field: str) -> None:
    with pytest.raises(ValueError, match=field):
        validate(_prov(**changes))


def test_error_message_never_carries_the_value() -> None:
    content = "Sitzungsprotokoll-geheim"
    with pytest.raises(ValueError, match="engine") as info:
        validate(_prov(engine=content))
    assert content not in str(info.value)


def test_order_key_is_epoch_level_config() -> None:
    assert order_key(_prov(epoch=2, level=Level.REFINED, config_version=3)) == (2, 200, 3)


def test_order_key_comparisons() -> None:
    def key(epoch: int, level: Level, config: int) -> tuple[int, int, int]:
        return order_key(_prov(epoch=epoch, level=level, config_version=config))

    # A better level wins even against a higher config version.
    assert key(0, Level.REFINED, 1) > key(0, Level.PREVIEW, 9)
    # Same level: the higher config version wins.
    assert key(0, Level.PREVIEW, 2) > key(0, Level.PREVIEW, 1)
    # A tie does not count as newer.
    assert not key(0, Level.PREVIEW, 1) > key(0, Level.PREVIEW, 1)
    # A higher epoch wins even with the lowest level.
    assert key(1, Level.SAMPLE, 1) > key(0, Level.REFINED_L3, 9)


def test_order_key_reads_rows_too() -> None:
    class Row:
        epoch = 1
        level = 150
        config_version = 4

    assert order_key(Row()) == (1, 150, 4)


# Store level: the conditional publish of decision 5.

WORDS = [Word(start_ms=0, end_ms=300, surface="Haushalt", norm="haushalt", conf=0.8, src="machine")]
ROVER = f"{HEX_A},{HEX_B}"


def _version_rows(path: Path) -> tuple[int, int]:
    with sqlite3.connect(path) as conn:
        transcripts = conn.execute("SELECT COUNT(*) FROM transcript").fetchone()[0]
        words = conn.execute("SELECT COUNT(*) FROM word").fetchone()[0]
    return transcripts, words


def test_publish_insert_then_better_level(store: Store) -> None:
    media_id = store.media_for_file_sha256(INPUT)
    first = store.publish_version(media_id, _prov(), WORDS)
    assert first.published
    assert first.reason is None
    assert first.index_rev == 1
    better = store.publish_version(media_id, _prov(engine="rover", model_sha256=ROVER, level=Level.REFINED), WORDS)
    assert better.published
    assert better.index_rev == 2
    current = store.current(media_id)
    assert current is not None
    assert (current.version_id, current.level, current.index_rev) == (better.version_id, 200, 2)
    assert store.pending_index_work() == [(media_id, 1), (media_id, 2)]


def test_older_level_with_higher_config_is_stale(store: Store, tmp_path: Path) -> None:
    media_id = store.media_for_file_sha256(INPUT)
    assert store.publish_version(media_id, _prov(level=Level.REFINED), WORDS).published
    before = _version_rows(tmp_path / "state.db")
    result = store.publish_version(media_id, _prov(level=Level.PREVIEW, config_version=9), WORDS)
    assert result == PublishResult(False, None, None, "stale_rejected")
    # Rollback: no orphan transcript or word rows.
    assert _version_rows(tmp_path / "state.db") == before
    current = store.current(media_id)
    assert current is not None
    assert (current.level, current.index_rev) == (200, 1)


def test_tie_is_stale(store: Store) -> None:
    media_id = store.media_for_file_sha256(INPUT)
    assert store.publish_version(media_id, _prov(), WORDS).published
    assert store.publish_version(media_id, _prov(), WORDS).reason == "stale_rejected"


def test_higher_config_on_same_level_wins(store: Store) -> None:
    media_id = store.media_for_file_sha256(INPUT)
    assert store.publish_version(media_id, _prov(), WORDS).published
    assert store.publish_version(media_id, _prov(config_version=2), WORDS).published


def test_bump_epoch_lets_a_lower_level_win(store: Store) -> None:
    media_id = store.media_for_file_sha256(INPUT)
    assert store.publish_version(media_id, _prov(level=Level.REFINED_L3), WORDS).published
    assert store.media_epoch(media_id) == 0
    assert store.bump_epoch(media_id) == 1
    assert store.media_epoch(media_id) == 1
    # An in-flight result of the old epoch is stale, even at a high level.
    stale = store.publish_version(media_id, _prov(level=Level.REFINED_L3, config_version=5), WORDS)
    assert stale.reason == "stale_rejected"
    sample = _prov(engine="sample", model_sha256=SAMPLE_MODEL_SHA256, level=Level.SAMPLE, epoch=1)
    assert store.publish_version(media_id, sample, WORDS).published
    current = store.current(media_id)
    assert current is not None
    assert (current.epoch, current.level) == (1, 1)


def test_input_mismatch(store: Store, tmp_path: Path) -> None:
    media_id = store.media_for_file_sha256(INPUT)
    store.media_for_file_sha256("e" * 64)
    before = _version_rows(tmp_path / "state.db")
    result = store.publish_version(media_id, _prov(input_file_sha256="e" * 64), WORDS)
    assert result == PublishResult(False, None, None, "input_mismatch")
    assert store.publish_version(media_id, _prov(input_file_sha256="f" * 64), WORDS).reason == "input_mismatch"
    assert _version_rows(tmp_path / "state.db") == before
    assert store.current(media_id) is None


def test_invalid_provenance_writes_nothing(store: Store, tmp_path: Path) -> None:
    media_id = store.media_for_file_sha256(INPUT)
    with pytest.raises(ValueError, match="engine"):
        store.publish_version(media_id, _prov(engine="cloud"), WORDS)
    assert _version_rows(tmp_path / "state.db") == (0, 0)


def test_machine_words_roundtrip(store: Store) -> None:
    media_id = store.media_for_file_sha256(INPUT)
    result = store.publish_version(media_id, _prov(), WORDS)
    assert result.version_id is not None
    assert store.machine_words(result.version_id) == WORDS


def test_mark_indexed_clears_the_outbox(store: Store) -> None:
    media_id = store.media_for_file_sha256(INPUT)
    store.publish_version(media_id, _prov(), WORDS)
    store.publish_version(media_id, _prov(config_version=2), WORDS)
    store.mark_indexed(media_id, 1)
    assert store.pending_index_work() == [(media_id, 2)]
    store.mark_indexed(media_id, 2)
    assert store.pending_index_work() == []
