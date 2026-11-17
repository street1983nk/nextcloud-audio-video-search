"""Where a transcript version came from, and which one wins.

Every version carries the full provenance (decision 5 of the phase research).
The order is lexicographic over ``(epoch, level, config_version)``:

- a higher level always wins over a lower one in the same epoch;
- on the same level the higher config version wins, so a model update can
  recompute on purpose;
- a tie is stale and gets rejected, which makes publishing idempotent;
- the epoch of a media item only rises when an admin asks for a recompute or a
  faulty model is recalled. That is the one way back to a lower level.

``validate`` raises ``ValueError`` naming the field, never the value: a value
could be anything a caller passed, and these messages can end up in a log.
"""

import hashlib
import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Final, Protocol


class Level(IntEnum):
    """Quality levels with gaps, so a later stage fits in between."""

    SAMPLE = 1
    PREVIEW = 100
    SELECTIVE = 150
    REFINED = 200
    REFINED_L3 = 300


ENGINES: Final = frozenset({"sample", "parakeet", "whisper-turbo", "whisper-large-v3", "rover"})
PROFILES: Final = frozenset({"fast", "balanced", "quality", "debug"})
LANGUAGES: Final = frozenset({"de", "en", "fr", "und"})

# The sample transcript of the walking skeleton has no model; its fixed mark is
# the hash of a fixed text, so the field keeps its 64-hex shape everywhere.
SAMPLE_MODEL_SHA256: Final = hashlib.sha256(b"audio_video_search_backend sample v1").hexdigest()

_HEX64: Final = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class Provenance:
    """The mandatory fields of one transcript version."""

    engine: str
    model_sha256: str
    config_version: int
    profile: str
    level: Level
    epoch: int
    language: str
    input_file_sha256: str


class _Ordered(Protocol):
    @property
    def epoch(self) -> int: ...
    @property
    def level(self) -> int: ...
    @property
    def config_version(self) -> int: ...


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _model_ok(engine: str, value: object) -> bool:
    if not isinstance(value, str):
        return False
    if engine == "sample":
        return value == SAMPLE_MODEL_SHA256
    if engine == "rover":
        parts = value.split(",")
        return len(parts) >= 2 and all(_is_hex64(p) for p in parts) and parts == sorted(parts)
    return _is_hex64(value)


def validate(p: Provenance) -> None:
    """Raise ``ValueError`` with the name of the first invalid field."""
    if p.engine not in ENGINES:
        raise ValueError("invalid provenance field: engine")
    if not _model_ok(p.engine, p.model_sha256):
        raise ValueError("invalid provenance field: model_sha256")
    if not _is_int(p.config_version) or p.config_version < 1:
        raise ValueError("invalid provenance field: config_version")
    if p.profile not in PROFILES:
        raise ValueError("invalid provenance field: profile")
    if not _is_int(p.level) or p.level not in set(Level):
        raise ValueError("invalid provenance field: level")
    if not _is_int(p.epoch) or p.epoch < 0:
        raise ValueError("invalid provenance field: epoch")
    if p.language not in LANGUAGES:
        raise ValueError("invalid provenance field: language")
    if not _is_hex64(p.input_file_sha256):
        raise ValueError("invalid provenance field: input_file_sha256")


def order_key(p_or_row: _Ordered) -> tuple[int, int, int]:
    """The order of versions: ``(epoch, level, config_version)``."""
    return (int(p_or_row.epoch), int(p_or_row.level), int(p_or_row.config_version))
