"""Phase-4-Research: Suchzeit und Beifang der Präfix-Klausel messen (Plan 04-06, D-04-14).

Aufruf aus backend/:

    uv run python ../scripts/research/phase4/measure_prefix.py --docs 100000 --queries 200 --threshold-ms 250

Das Skript baut in einem Temp-Verzeichnis einen Index aus synthetischen
Segmenten (deterministischer Zufall, fester Seed, 40 Wörter je Segment) und
misst für zehn typische Begriffe die Suchzeit p50/p95 mit Bestandsweg
(parse_query wie Phase 1 bis 3) und mit Präfix-Klausel (SearchIndex.search,
Plan 04-06). Die Bestandteilliste enthält nur die Fugen, damit Komposita ganz
bleiben: so trägt das Term-Wörterbuch die meisten eigenen Einträge je Präfix,
der ungünstigste Fall für die Regex-Klausel. Mit --wordlist zählt es je Begriff
die Einträge der Liste, die mit dem gefalteten Stamm beginnen
(Beifang-Obergrenze gegen ngerman). Ausgabe ist JSON mit Zahlen; Exitcode 1,
wenn p95 mit Präfix über --threshold-ms liegt.
"""

import argparse
import json
import statistics
import sys
import tempfile
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path

import numpy as np

from audio_video_search_backend.index.analyzer import german_analyzer, normalize
from audio_video_search_backend.index.publish import _WORD, SearchIndex, Segment
from audio_video_search_backend.index.schema import BODY_FIELDS
from audio_video_search_backend.index.wordlist import FUGEN

SEED = 40601
WORDS_PER_SEGMENT = 40
SEGMENTS_PER_MEDIA = 1000
SEARCH_LIMIT = 20
VOCABULARY_SIZE = 4000

# Typische Verwaltungs-Begriffe (Plan 04-06); nie Wörter aus Nutzerdaten.
TERMS = (
    "Haushalt",
    "Sitzung",
    "Beratung",
    "Vertrag",
    "Verwaltung",
    "Gemeinderat",
    "Bebauung",
    "Schule",
    "Feuerwehr",
    "Antrag",
)
# Nachsilben, die aus jedem Begriff Komposita für das Wörterbuch machen.
TAILS = ("splanberatung", "svorlage", "sverfahren", "sausschuss")
SYLLABLES = (
    "ab",
    "be",
    "da",
    "ge",
    "hal",
    "ken",
    "lung",
    "mar",
    "nis",
    "or",
    "pla",
    "rat",
    "schu",
    "ter",
    "ung",
    "ver",
    "wal",
    "zen",
)


def fold(text: str) -> str:
    """Kleinbuchstaben, flache Umlaute, ss statt scharfem s (wie index/numbers)."""
    lowered = unicodedata.normalize("NFC", text).lower().replace("ß", "ss")
    return "".join(c for c in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(c))


def build_pool(rng: np.random.Generator) -> list[str]:
    """Füllwörter plus Zielwörter plus abgeleitete Komposita, mehrfach gewichtet."""
    filler: set[str] = set()
    while len(filler) < VOCABULARY_SIZE:
        count = int(rng.integers(2, 5))
        filler.add("".join(SYLLABLES[int(i)] for i in rng.integers(0, len(SYLLABLES), count)))
    compounds = [fold(term) + tail for term in TERMS for tail in TAILS]
    return sorted(filler) + [fold(term) for term in TERMS] * 10 + compounds * 5


def build_index(root: Path, docs: int, rng: np.random.Generator) -> SearchIndex:
    pool = np.array(build_pool(rng))
    picks = rng.integers(0, len(pool), size=(docs, WORDS_PER_SEGMENT))
    opened = SearchIndex.open(root / "idx", constituents=sorted(FUGEN))
    for media_id in range(0, docs, SEGMENTS_PER_MEDIA):
        rows = picks[media_id : media_id + SEGMENTS_PER_MEDIA]
        segments = [
            Segment(seg_idx=i, start_ms=i * 1000, end_ms=i * 1000 + 900, text=" ".join(pool[row]))
            for i, row in enumerate(rows)
        ]
        opened.publish(media_id // SEGMENTS_PER_MEDIA + 1, 1, segments)
    return opened


def quantile_ms(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, round(share * (len(ordered) - 1)))], 3)


def timed_ms(action: Callable[[str], None], queries: int) -> list[float]:
    """Jede Abfrage einzeln gestoppt; action(term) führt genau eine Suche aus."""
    times: list[float] = []
    for i in range(queries):
        term = TERMS[i % len(TERMS)]
        started = time.perf_counter()
        action(term)
        times.append((time.perf_counter() - started) * 1000.0)
    return times


def legacy_count(opened: SearchIndex, term: str, ceiling: int) -> int:
    # Die Stubs von tantivy 0.26.2 kennen result.count nicht; die Länge der
    # Trefferliste mit Dokumenten-Obergrenze zählt genauso.
    query = opened._index.parse_query(normalize(term), list(BODY_FIELDS), conjunction_by_default=True)
    return len(opened._index.searcher().search(query, ceiling).hits)


def prefix_count(opened: SearchIndex, term: str, ceiling: int) -> int:
    query = opened._word_query(_WORD.findall(normalize(term)))
    if query is None:
        return 0
    return len(opened._index.searcher().search(query, ceiling).hits)


def wordlist_bounds(path: Path, stems: dict[str, str]) -> dict[str, int]:
    entries = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    folded = [fold(entry) for entry in entries]
    return {term: sum(1 for entry in folded if entry.startswith(stem)) for term, stem in stems.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=int, default=100000)
    parser.add_argument("--queries", type=int, default=200)
    parser.add_argument("--wordlist", type=Path, default=None, help="Pfad zu ngerman für die Beifang-Obergrenze")
    parser.add_argument("--threshold-ms", type=float, default=250.0)
    arguments = parser.parse_args()

    rng = np.random.default_rng(SEED)
    chain = german_analyzer(sorted(FUGEN))
    stems = {term: chain.analyze(term)[0] for term in TERMS}

    with tempfile.TemporaryDirectory(prefix="measure-prefix-", ignore_cleanup_errors=True) as scratch:
        opened = build_index(Path(scratch), arguments.docs, rng)
        try:

            def legacy_once(term: str) -> None:
                query = opened._index.parse_query(normalize(term), list(BODY_FIELDS), conjunction_by_default=True)
                opened._index.searcher().search(query, SEARCH_LIMIT)

            def prefix_once(term: str) -> None:
                opened.search(term, SEARCH_LIMIT)

            legacy_times = timed_ms(legacy_once, arguments.queries)
            prefix_times = timed_ms(prefix_once, arguments.queries)
            per_term: dict[str, dict[str, int | None]] = {
                term: {
                    "legacy_hits": legacy_count(opened, term, arguments.docs),
                    "prefix_hits": prefix_count(opened, term, arguments.docs),
                    "wordlist_prefix_entries": None,
                }
                for term in TERMS
            }
        finally:
            opened.close()

    if arguments.wordlist is not None:
        for term, bound in wordlist_bounds(arguments.wordlist, stems).items():
            per_term[term]["wordlist_prefix_entries"] = bound

    p95_prefix = quantile_ms(prefix_times, 0.95)
    report = {
        "docs": arguments.docs,
        "queries": arguments.queries,
        "threshold_ms": arguments.threshold_ms,
        "legacy_ms": {
            "p50": quantile_ms(legacy_times, 0.50),
            "p95": quantile_ms(legacy_times, 0.95),
            "mean": round(statistics.mean(legacy_times), 3),
        },
        "prefix_ms": {
            "p50": quantile_ms(prefix_times, 0.50),
            "p95": p95_prefix,
            "mean": round(statistics.mean(prefix_times), 3),
        },
        "terms": per_term,
        "within_threshold": p95_prefix <= arguments.threshold_ms,
    }
    print(json.dumps(report, indent=2))
    return 0 if p95_prefix <= arguments.threshold_ms else 1


if __name__ == "__main__":
    sys.exit(main())
