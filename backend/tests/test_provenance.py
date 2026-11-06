"""Provenance of a transcript version and the order that decides which one is current.

Decision 5 of the phase research: every version carries engine, model hash,
config version, profile, level, epoch, language and the hash of the input file.
The order is lexicographic over (epoch, level, config_version); a tie is stale.
"""

import hashlib
from dataclasses import replace

import pytest

from audio_video_search_backend.model.provenance import (
    ENGINES,
    PROFILES,
    SAMPLE_MODEL_SHA256,
    Level,
    Provenance,
    order_key,
    validate,
)

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
    secret = "Sitzungsprotokoll-geheim"
    with pytest.raises(ValueError, match="engine") as info:
        validate(_prov(engine=secret))
    assert secret not in str(info.value)


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
