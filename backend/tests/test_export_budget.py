"""The export limits of the PHP app hold for what the container measurably delivers (plan 04-09, T-04-22, T-04-26).

php/lib/Service/ExAppService.php gives the export call its own budget
(plan 04-10): EXPORT_TIMEOUT_SECONDS for the answer, EXPORT_MAX_BODY_BYTES for
its size. Both are read here from the PHP source, never copied, and held
against a run of the real cue builder and writers:

* Time: build_cues plus to_vtt for 100 000 words (12.6 h of speech, the
  NORMAL tempo of plan 04-07; VTT is the most expensive format in plan 04-08,
  0.46 s on the measuring laptop). Times 8 for a Pi 5 / arm64 (plan 04-08)
  it must stay under the timeout.
* Size: the JSON hull ``{"known": true, ..., "body": ...}`` of 24 h of speech
  (MAX_DURATION_CAP_HOURS, the longest file the instance may transcribe) in
  the largest format, SRT. With a reserve of 2 (plan 04-08 formula) it must
  stay under the ceiling, for the NORMAL tempo (200 000 words) and for fast
  speech with long words and umlauts.

When this test fails, the PHP constant is re-measured in ExAppService.php
(the measured value times 8 rounded up, or the 24 h hull with reserve), never
the factor lowered here; the ExAppServiceTest case "above 1 MiB, below
EXPORT_MAX_BODY_BYTES" has to hold afterwards.

The generator is the one of scripts/research/phase4/measure_export.py, written
out here so the test depends on nothing outside the backend.
"""

import json
import random
import re
import time
from typing import Final

from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.settings import MAX_DURATION_CAP_HOURS
from audio_video_search_backend.subtitles.cues import build_cues
from audio_video_search_backend.subtitles.formats import to_srt, to_vtt
from tests.conftest import REPO_ROOT

EXAPP_SERVICE: Final = REPO_ROOT / "php" / "lib" / "Service" / "ExAppService.php"
# A Pi 5 / arm64 runs the writers up to this many times slower than the measuring laptop (plan 04-08).
ARM_FACTOR: Final = 8
# The reserve over the measured 24 h hull (plan 04-08 formula).
SIZE_RESERVE: Final = 2

SEED: Final = 40801
CHAR_MS: Final = 61
LETTERS: Final = "abcdefghijklmnopqrstuvwxyz"
LENGTH_WEIGHTS: Final = [26, 20, 16, 12, 9, 7, 4, 3, 2, 1]
TIME_WORDS: Final = 100_000

_TIMEOUT = re.compile(r"public\s+const\s+EXPORT_TIMEOUT_SECONDS\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*;")
_MAX_BODY = re.compile(r"private\s+const\s+EXPORT_MAX_BODY_BYTES\s*=\s*([0-9_]+)\s*;")


def _constant(pattern: re.Pattern[str]) -> str:
    found = pattern.findall(EXAPP_SERVICE.read_text(encoding="utf-8"))
    assert len(found) == 1, f"{pattern.pattern} must match exactly once in {EXAPP_SERVICE.name}"
    return found[0]


def _timeout_seconds() -> float:
    return float(_constant(_TIMEOUT))


def _max_body_bytes() -> int:
    return int(_constant(_MAX_BODY).replace("_", ""))


def _speech(
    count: int, *, letters: str = LETTERS, char_ms: int = CHAR_MS, pause: tuple[int, int] = (300, 1200)
) -> list[Word]:
    """Deterministic speech: sentences of 8 to 15 words, a pause after each (measure_export.py)."""
    rng = random.Random(SEED)  # noqa: S311 - measuring data, no secret
    words: list[Word] = []
    cursor = 0
    left = rng.randint(8, 15)
    for _ in range(count):
        length = rng.choices(range(3, 13), weights=LENGTH_WEIGHTS)[0]
        surface = "".join(rng.choice(letters) for _ in range(length))
        left -= 1
        gap = 0
        if left == 0:
            surface += "."
            left = rng.randint(8, 15)
            gap = rng.randint(*pause)
        end = cursor + len(surface) * char_ms
        words.append(Word(cursor, end, surface, surface.casefold(), 1.0, "machine"))
        cursor = end + char_ms + gap
    return words


def _day_of(words: list[Word]) -> list[Word]:
    """The words of MAX_DURATION_CAP_HOURS of speech."""
    limit = MAX_DURATION_CAP_HOURS * 3_600_000
    day = [word for word in words if word.end_ms <= limit]
    assert len(day) < len(words), "the generator must reach past the cap"
    return day


def _hull(body: str) -> int:
    """Bytes of the container answer as FastAPI sends it (UTF-8, no ASCII escapes)."""
    answer = {"known": True, "partial": True, "untilMs": 86_400_000, "language": "de", "body": body}
    return len(json.dumps(answer, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def test_the_constants_are_read_from_the_php_source() -> None:
    assert _timeout_seconds() > 0
    # Above the 1 MiB search ceiling, or a long transcript would never fit.
    assert _max_body_bytes() > 1_048_576


def test_the_slowest_format_fits_the_timeout_on_a_pi() -> None:
    words = _speech(TIME_WORDS)
    started = time.perf_counter()
    body = to_vtt(build_cues(words))
    measured = time.perf_counter() - started

    assert body.startswith("WEBVTT\n\n")
    assert ARM_FACTOR * measured < _timeout_seconds(), (
        f"{TIME_WORDS} words took {measured:.2f} s; re-measure EXPORT_TIMEOUT_SECONDS in ExAppService.php"
    )


def test_a_day_of_normal_speech_fits_the_body_ceiling_with_reserve() -> None:
    day = _day_of(_speech(220_000))
    # 24 h in the NORMAL tempo are about 190 000 words (100 000 words = 12.6 h).
    assert len(day) > 180_000
    hull = _hull(to_srt(build_cues(day)))

    assert SIZE_RESERVE * hull < _max_body_bytes(), (
        f"24 h hull {hull} bytes; re-measure EXPORT_MAX_BODY_BYTES in ExAppService.php"
    )


def test_a_day_of_fast_speech_with_umlauts_fits_the_body_ceiling_with_reserve() -> None:
    # Fast speech (40 ms per character, short pauses) with two byte umlauts:
    # about 12 700 words per hour, the densest text a day can carry.
    day = _day_of(_speech(360_000, letters=LETTERS + "äöüß", char_ms=40, pause=(150, 500)))
    hull = _hull(to_srt(build_cues(day)))

    assert SIZE_RESERVE * hull < _max_body_bytes(), (
        f"24 h fast hull {hull} bytes; re-measure EXPORT_MAX_BODY_BYTES in ExAppService.php"
    )
