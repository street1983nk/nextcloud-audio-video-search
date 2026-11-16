"""Phase-4-Research: FLEURS-Sätze für S7 vorab messen (Plan 04-14).

Aufruf aus backend/:

    uv run python ../scripts/research/phase4/measure_s7_sentences.py \
        --candidates KANDIDATEN.json --clips-dir ORDNER --models-root WURZEL \
        [--archive-dir ORDNER] [--wordlist /usr/share/dict/ngerman] [--out ERGEBNIS.json]

KANDIDATEN.json ist eine Liste von Objekten
``{"tar_path", "member", "number_forms", "plural", "singular", "compound", "head"}``;
alles außer tar_path und member ist optional. Je Kandidat liest das Skript das
Mitglied über ``read_member`` aus ci/media/fetch_speech.py (aus dem gepinnten
FLEURS-Archiv unter derselben Host-Allowlist, oder aus einer lokalen Kopie des
Archivs unter ``--archive-dir`` mit dem Namen ``tar_path`` mit "_" statt "/"),
gibt den sha256 des Mitglieds aus, wandelt es mit ``to_wav`` (ffmpeg, bitexact)
und transkribiert es zweimal mit Parakeet hinter der Prozessgrenze, genau wie
backend/tests/test_engine_model.py (EngineWorker, Modelle unter
``--models-root`` wie ``procure --root``). Der zweite Lauf geht über einen
frischen Kindprozess. Weichen die beiden Transkripte ab, ist der Kandidat
verworfen (``stable: false``).

Für die Zielformen prüft es, ob das gefaltete Token im Transkript steht, ob
jede Zahlform zur selben Zahl gehört (numbers.recognize) und ob jede Suchform
die Datei in einem Wegwerf-Index mit dem gemessenen Transkript findet
(SearchIndex.search, mit der Bestandteilliste aus ``--wordlist``, sonst nur den
Fugen). Ausgabe ist JSON mit FLEURS-Text und Zahlen, nie Nutzerdaten.
Exitcode 0, wenn mindestens ein Kandidat stabil ist und alle seine Prüfungen
bestehen, sonst 1.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import urllib.parse
import urllib.request
import wave
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from audio_video_search_backend import memory_guard
from audio_video_search_backend.engine.catch import KEEP
from audio_video_search_backend.engine.child import OK, EngineWorker
from audio_video_search_backend.engine.constants import SAMPLE_RATE
from audio_video_search_backend.engine.parakeet import Window
from audio_video_search_backend.index import numbers
from audio_video_search_backend.index.publish import SearchIndex, Segment
from audio_video_search_backend.index.wordlist import FUGEN, load_constituents

FETCH_SPEECH = Path(__file__).resolve().parents[3] / "ci" / "media" / "fetch_speech.py"
SEARCH_LIMIT = 10
GIB = 1024**3


def load_fetch_speech() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fetch_speech_for_s7", FETCH_SPEECH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {FETCH_SPEECH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fold(text: str) -> str:
    """Wie _norm in test_engine_model.py: Kleinschreibung, nur Buchstaben und Ziffern."""
    return "".join(char for char in text.lower() if char.isalnum())


def tokens_of(text: str) -> list[str]:
    return [token for token in (fold(part) for part in text.split()) if token]


def member_bytes(fs: ModuleType, tar_path: str, member: str, archive_dir: Path | None) -> bytes:
    if archive_dir is not None:
        with (archive_dir / tar_path.replace("/", "_")).open("rb") as handle:
            return fs.read_member(handle, member)
    url = f"https://huggingface.co/datasets/{fs.DATASET}/resolve/{fs.REVISION}/{tar_path}"
    if not fs.host_allowed(url):
        raise SystemExit("host outside the allowlist")
    request = urllib.request.Request(url, headers={"User-Agent": "audio-video-search-research/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
        if not fs.host_allowed(response.geturl()):
            raise SystemExit(f"redirect outside the allowlist: {urllib.parse.urlsplit(response.geturl()).hostname}")
        return fs.read_member(response, member)


def pcm_of(path: Path) -> tuple[bytes, float]:
    with wave.open(str(path)) as handle:
        if handle.getframerate() != SAMPLE_RATE or handle.getnchannels() != 1:
            raise SystemExit(f"{path.name}: not 16 kHz mono")
        frames = handle.readframes(handle.getnframes())
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    return samples.astype("<f4").tobytes(), round(len(samples) / SAMPLE_RATE, 2)


def transcript(windows: list[Window]) -> str:
    """Die Wörter der behaltenen Fenster, wie sie in den Index gehen."""
    return " ".join(word.text for window in windows if window.verdict == KEEP for word in window.words)


def transcribe_all(models_root: Path, headroom: Callable[[], int | None], pcms: list[bytes]) -> list[str]:
    """Ein Kindprozess für alle Kandidaten; jeder Aufruf dieser Funktion startet einen frischen."""
    engine = EngineWorker(models_root, headroom=headroom)
    if engine.start() != OK:
        raise SystemExit("engine child did not start (memory or models)")
    try:
        texts = []
        for pcm in pcms:
            code, windows = engine.ask(pcm, 0, False)
            if code != OK:
                raise SystemExit(f"engine answered {code}")
            texts.append(transcript(windows))
        return texts
    finally:
        engine.stop()


def search_hits(constituents: list[str], text: str, terms: list[str]) -> dict[str, bool]:
    with tempfile.TemporaryDirectory() as scratch:
        opened = SearchIndex.open(Path(scratch) / "idx", constituents=constituents)
        try:
            opened.publish(1, 1, [Segment(seg_idx=0, start_ms=0, end_ms=1000, text=text)])
            return {term: any(hit.media_id == 1 for hit in opened.search(term, SEARCH_LIMIT)) for term in terms}
        finally:
            opened.close()


def number_values(form: str) -> list[int]:
    return [span.value for span in numbers.recognize(form.split())]


def judge(candidate: dict[str, Any], text: str, constituents: list[str]) -> dict[str, Any]:
    tokens = set(tokens_of(text))
    checks: dict[str, Any] = {}
    terms: list[str] = []
    forms = candidate.get("number_forms") or []
    if forms:
        values = {form: number_values(form) for form in forms}
        checks["number_values"] = values
        checks["number_one_value"] = len({tuple(v) for v in values.values()}) == 1 and all(
            len(v) == 1 for v in values.values()
        )
        checks["number_token_in_transcript"] = [form for form in forms if fold(form) in tokens]
        terms.extend(forms)
    for key in ("plural", "compound"):
        if candidate.get(key):
            checks[f"{key}_in_transcript"] = fold(candidate[key]) in tokens
            terms.append(candidate[key])
    for key in ("singular", "head"):
        if candidate.get(key):
            terms.append(candidate[key])
    checks["search"] = search_hits(constituents, text, terms)
    passed = all(checks["search"].values())
    if forms:
        passed = passed and checks["number_one_value"] and bool(checks["number_token_in_transcript"])
    for key in ("plural", "compound"):
        if candidate.get(key):
            passed = passed and checks[f"{key}_in_transcript"]
    checks["passed"] = passed
    return checks


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="FLEURS-Sätze für S7 vorab messen (Plan 04-14).")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--clips-dir", type=Path, required=True)
    parser.add_argument("--models-root", type=Path, required=True)
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--wordlist", type=Path)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--free-gib", type=float, default=0.0, help="nur Windows: freier Speicher, den der Wächter annehmen darf"
    )
    arguments = parser.parse_args(argv)
    fs = load_fetch_speech()
    ff = fs.ffmpeg_binary(arguments.ffmpeg)
    candidates: list[dict[str, Any]] = json.loads(arguments.candidates.read_text(encoding="utf-8"))
    arguments.clips_dir.mkdir(parents=True, exist_ok=True)
    free = int(arguments.free_gib * GIB)
    headroom = memory_guard.headroom_bytes if sys.platform != "win32" else (lambda: free)
    constituents: list[str] = load_constituents(arguments.wordlist) if arguments.wordlist else list(FUGEN)

    pcms: list[bytes] = []
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        data = member_bytes(fs, candidate["tar_path"], candidate["member"], arguments.archive_dir)
        raw = arguments.clips_dir / ("raw_" + candidate["member"])
        raw.write_bytes(data)
        wav = arguments.clips_dir / candidate["member"]
        fs.to_wav(ff, raw, wav)
        raw.unlink()
        pcm, duration = pcm_of(wav)
        pcms.append(pcm)
        results.append(
            {
                "tar_path": candidate["tar_path"],
                "member": candidate["member"],
                "member_sha256": hashlib.sha256(data).hexdigest(),
                "wav_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
                "duration_s": duration,
            }
        )
    first = transcribe_all(arguments.models_root, headroom, pcms)
    second = transcribe_all(arguments.models_root, headroom, pcms)
    for candidate, result, run_one, run_two in zip(candidates, results, first, second, strict=True):
        result["transcript_run_1"] = run_one
        result["transcript_run_2"] = run_two
        result["stable"] = run_one == run_two
        result["tokens"] = tokens_of(run_one)
        result["number_spans"] = [
            {"value": span.value, "ordinal": span.ordinal, "words": result["tokens"][span.start : span.stop]}
            for span in numbers.recognize(result["tokens"])
        ]
        result["checks"] = judge(candidate, run_one, constituents)
        result["chosen_ok"] = result["stable"] and result["checks"]["passed"]
    report = {
        "source": f"{fs.ATTRIBUTION}, {fs.DATASET}@{fs.REVISION}",
        "wordlist_entries": len(constituents),
        "candidates": results,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if arguments.out:
        arguments.out.write_text(text + "\n", encoding="utf-8")
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    return 0 if any(result["chosen_ok"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
