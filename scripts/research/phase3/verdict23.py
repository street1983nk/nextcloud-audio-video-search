"""Phase 3, D-03-23: die Fenster des zweiten VAD-Durchgangs am Korpus, mit der echten Engine.

python -I verdict23.py <models_root> <out_dir> <wav> [<wav> ...]
models_root ist der Ordner, den ``procure --root`` füllt. Läuft mit der Umgebung des Backends
(``uv run --project backend``). Derselbe Ablauf wie verdict22.py: dieselbe Engine
(engine/parakeet.py, beide Durchgänge nur über ``Engine.transcribe``), dieselbe Zählung des
Workers (``take``), derselbe zweite Durchgang für Dateien bis 60 s ohne behaltenes Wort,
dasselbe Dateiurteil, dieselben JSON-Felder einschließlich ``words`` (build_short.py liest sie).

Zusätzlich je Datei ``second_windows``: je Fenster des zweiten Durchgangs Zeit, Wortzahl,
Schriftanteil, Textsprache mit p, mittlere und kleinste Wortkonfidenz (nur bei Fenstern, die
die alte Regel behielt, sonst null, weil die Engine nur dann Wörter mitgibt) und das Urteil der
alten Regel; ``second_kept`` ist die Wortzahl, die der zweite Durchgang unter der alten Regel
behielt. eval23.py bestimmt daraus die Schwelle für den zweiten Durchgang.
Kein Text verlässt den Rechner; Audio und Ergebnisse liegen nur im angegebenen Ordner.
"""

import json
import pathlib
import sys
import time
import wave

import numpy as np

from audio_video_search_backend.engine.catch import file_verdict, needs_second_pass
from audio_video_search_backend.engine.parakeet import Engine, Window
from audio_video_search_backend.worker.preview import take

SR = 16000


def read_wav(path: pathlib.Path) -> np.ndarray:
    with wave.open(str(path)) as handle:
        if handle.getframerate() != SR or handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise SystemExit(f"{path.name}: 16 kHz mono s16 expected")
        frames = handle.readframes(handle.getnframes())
    return (np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0).astype(np.float32)


def raw_words(windows: list[Window]) -> int:
    return sum(window.n_words for window in windows)


def window_row(window: Window) -> dict[str, object]:
    return {
        "start_ms": window.start_ms,
        "end_ms": window.end_ms,
        "n_words": window.n_words,
        "latin": window.latin,
        "lid": window.lid,
        "lid_p": window.lid_p,
        "conf_mean": window.conf_mean,
        "conf_min": round(min(w.conf for w in window.words), 4) if window.words else None,
        "verdict": window.verdict,
        # what take() counts as kept for this window (words with text)
        "kept_n": sum(1 for w in window.words if w.text.strip()),
        "text": " ".join(w.text for w in window.words),
    }


def measure(engine: Engine, path: pathlib.Path) -> dict[str, object]:
    pcm = read_wav(path)
    duration_ms = len(pcm) * 1000 // SR
    started = time.perf_counter()
    first = engine.transcribe(pcm, 0, second_pass=False)
    taken = take(first, 0, None)
    counters = taken.counters
    kept, script, language, conf = counters.kept_words, counters.drop_script, counters.drop_language, counters.drop_conf
    speech_ms = counters.speech_ms
    second: list[Window] = []
    second_kept = 0
    ran = needs_second_pass(kept, duration_ms, False)
    if ran:
        second = engine.transcribe(pcm, 0, second_pass=True)
        again = take(second, 0, None, count_speech=False).counters
        second_kept = again.kept_words
        kept += again.kept_words
        script += again.drop_script
        language += again.drop_language
        conf += again.drop_conf
    return {
        "file": path.stem,
        "dur_ms": duration_ms,
        "proc_s": round(time.perf_counter() - started, 2),
        "speech_ms": speech_ms,
        "share": round(speech_ms / duration_ms, 4) if duration_ms else 0.0,
        "windows": len(first),
        "raw_words": raw_words(first),
        "second_pass": ran,
        "second_speech_ms": sum(window.speech_ms for window in second),
        "second_raw_words": raw_words(second),
        "second_kept": second_kept,
        "second_windows": [window_row(window) for window in second],
        "kept": kept,
        "drop_script": script,
        "drop_language": language,
        "drop_conf": conf,
        "verdict": file_verdict(kept, script, language, conf, speech_ms, duration_ms),
        "words": [[w.surface, w.start_ms / 1000, w.end_ms / 1000, w.conf] for w in taken.words],
        "lids": sorted({f"{window.lid}:{window.lid_p}" for window in first if window.n_words}),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: python -I verdict23.py <models_root> <out_dir> <wav> [<wav> ...]", file=sys.stderr)
        return 2
    engine = Engine(pathlib.Path(argv[0]))
    out = pathlib.Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for arg in argv[2:]:
        path = pathlib.Path(arg)
        result = measure(engine, path)
        (out / f"{path.stem}.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(
            f"{result['file']:<34}{result['dur_ms']:>8}{result['speech_ms']:>8}{result['raw_words']:>5}"
            f"{result['kept']:>5}{result['second_kept']:>4} {result['verdict']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
