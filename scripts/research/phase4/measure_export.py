"""Phase-4-Research: Export-Zeit und -Größe für 100 000 Wörter messen (Plan 04-08, T-04-19, T-04-22).

Aufruf aus backend/:

    uv run python ../scripts/research/phase4/measure_export.py --words 100000 --runs 5

Erzeugt deterministisch Wörter im NORMAL-Sprechtempo aus Plan 04-07 (61 ms je
Zeichen, Sätze zu 8 bis 15 Wörtern, Pausen 300 bis 1200 ms; 100 000 Wörter
ergeben rund 12 h) und misst je Lauf build_cues, to_srt, to_vtt und to_txt
einzeln mit time.perf_counter. Ausgabe ist JSON: Median-Sekunden je Format
(SRT und VTT enthalten build_cues, TXT arbeitet auf den Wörtern), Bytes je
Format (UTF-8) und Bytes der JSON-Hülle {"known": true, "body": ...}
(json.dumps mit ensure_ascii=False). Abgeleitet für Plan 04-09 und 04-10:
EXPORT_TIMEOUT_SECONDS = max(30, 8 x Median des teuersten Formats; Faktor 8
für Pi 5/arm64) und EXPORT_MAX_BODY_BYTES = nächste Zweierpotenz über
2 x größter JSON-Hülle bei 24 h Text (24 h = 2 x 12 h; alle Größen sind
linear in der Wortzahl, build_cues ist linear, T-04-19).
"""

import argparse
import json
import random
import statistics
import sys
import time

from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.subtitles.cues import build_cues
from audio_video_search_backend.subtitles.formats import to_srt, to_txt, to_vtt

SEED = 40801
CHAR_MS = 61
LETTERS = "abcdefghijklmnopqrstuvwxyz"
# Wortlängen 3 bis 12, kurze häufig: mittlere Länge 5,3 Zeichen (wie Plan 04-07).
LENGTH_WEIGHTS = [26, 20, 16, 12, 9, 7, 4, 3, 2, 1]
FORMATS = ("srt", "vtt", "txt")


def speech(count: int) -> list[Word]:
    """Deterministische Rede im NORMAL-Tempo: Sätze zu 8 bis 15 Wörtern, Pausen 300 bis 1200 ms."""
    rng = random.Random(SEED)  # noqa: S311 - Messdaten, kein Geheimnis
    words: list[Word] = []
    cursor = 0
    left = rng.randint(8, 15)
    for _ in range(count):
        length = rng.choices(range(3, 13), weights=LENGTH_WEIGHTS)[0]
        surface = "".join(rng.choice(LETTERS) for _ in range(length))
        left -= 1
        pause = 0
        if left == 0:
            surface += "."
            left = rng.randint(8, 15)
            pause = rng.randint(300, 1200)
        end = cursor + len(surface) * CHAR_MS
        words.append(Word(cursor, end, surface, surface.casefold(), 1.0, "machine"))
        cursor = end + CHAR_MS + pause
    return words


def envelope_bytes(body: str) -> int:
    """Bytes der JSON-Hülle, die Plan 04-09/04-10 über die Route schicken."""
    return len(json.dumps({"known": True, "body": body}, ensure_ascii=False).encode("utf-8"))


def next_power_of_two(value: float) -> int:
    """Die kleinste Zweierpotenz strikt über value."""
    power = 1
    while power <= value:
        power *= 2
    return power


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", type=int, default=100000)
    parser.add_argument("--runs", type=int, default=5)
    arguments = parser.parse_args()

    words = speech(arguments.words)
    timings: dict[str, list[float]] = {"build_cues": [], "srt": [], "vtt": [], "txt": []}
    outputs: dict[str, str] = {}
    cue_count = 0
    for _ in range(arguments.runs):
        started = time.perf_counter()
        cues = build_cues(words)
        built = time.perf_counter() - started
        cue_count = len(cues)
        timings["build_cues"].append(built)
        for name, produce in (
            ("srt", lambda: to_srt(cues)),  # noqa: B023 - sofort aufgerufen, nie aufbewahrt
            ("vtt", lambda: to_vtt(cues)),  # noqa: B023
            ("txt", lambda: to_txt(words)),
        ):
            started = time.perf_counter()
            outputs[name] = produce()
            elapsed = time.perf_counter() - started
            # SRT und VTT brauchen die Cues, TXT nur die Wörter.
            timings[name].append(elapsed + (built if name != "txt" else 0.0))

    seconds = {name: round(statistics.median(timings[name]), 3) for name in timings}
    sizes = {name: len(outputs[name].encode("utf-8")) for name in FORMATS}
    json_sizes = {name: envelope_bytes(outputs[name]) for name in FORMATS}

    worst_format_seconds = max(seconds[name] for name in FORMATS)
    json_bytes_24h = 2 * max(json_sizes.values())
    body_limit = next_power_of_two(2 * json_bytes_24h)
    report = {
        "words": arguments.words,
        "runs": arguments.runs,
        "span_hours": round(words[-1].end_ms / 3_600_000, 2),
        "cues": cue_count,
        "seconds": seconds,
        "bytes": sizes,
        "json_bytes": json_sizes,
        "derived": {
            "export_timeout_seconds": max(30.0, round(8 * worst_format_seconds, 1)),
            "export_max_body_bytes": body_limit,
            "export_max_body_mib": body_limit / 1_048_576,
            "json_bytes_24h_estimate": json_bytes_24h,
        },
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
