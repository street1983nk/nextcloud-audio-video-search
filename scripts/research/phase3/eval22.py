"""Phase 3, D-03-22: die Ergebnisse von verdict22.py je Gruppe mit dem Dateiurteil von engine/catch.py auswerten.

python -I eval22.py <result_dir> [<result_dir> ...]
Läuft mit der Umgebung des Backends (``uv run --project backend``). Das Urteil wird aus den
gespeicherten Zählern neu berechnet, damit eine geänderte Regel ohne neuen Modelllauf geprüft
werden kann. Ausgabe je Gruppe: Urteile, und für Dateien ohne behaltenes Wort die Spanne der
VAD-Sprache und ihres Anteils; danach jede Datei, deren Urteil nicht das erwartete ist.

Gruppen nach dem Dateinamen (Korpus aus fetch_corpus.py, build_corpus.py, build_extra.py,
build_short.py und den Clips aus ci/media/fetch_speech.py):
- instance: Sprache in DE/EN/FR (erwartet transcript; Kurzmemos ohne Sprache dürfen no_speech sein)
- nonspeech: Stille, Rauschen, Instrumentalmusik, Kunstgesang (erwartet no_speech)
- sung: gesungenes Englisch mit verständlichem Text (erwartet transcript, M-7)
- foreign: von Parakeet erkannte Fremdsprachen ES, IT, NL, PL, RU, EL (erwartet unsupported_language)
- unsupported: von Parakeet nicht unterstützte Sprachen (erwartet unsupported_language)
"""

import json
import pathlib
import sys
from collections import Counter

from audio_video_search_backend.engine.catch import NO_SPEECH, TRANSCRIPT, UNSUPPORTED_LANGUAGE, file_verdict

FOREIGN = ("es_419", "it_it", "nl_nl", "pl_pl", "ru_ru", "el_gr")
UNSUPPORTED = ("tr_tr", "ar_eg", "cmn_hans_cn", "ja_jp", "hi_in", "vi_vn", "sw_ke")
SUNG = ("music_band_rock", "sing_en_bowlly_guilty", "sing_en_california")


def group(name: str) -> str:
    if name.startswith(SUNG):
        return "sung"
    if name.startswith(("ns_", "music_", "sing_")):
        return "nonspeech"
    if name == "speech_es" or any(f"_{code}" in name for code in FOREIGN):
        return "foreign"
    if name == "speech_tr" or any(f"_{code}" in name for code in UNSUPPORTED):
        return "unsupported"
    return "instance"


EXPECTED = {
    "instance": TRANSCRIPT,
    "nonspeech": NO_SPEECH,
    "sung": TRANSCRIPT,
    "foreign": UNSUPPORTED_LANGUAGE,
    "unsupported": UNSUPPORTED_LANGUAGE,
}


def verdict(r: dict[str, int]) -> str:
    return file_verdict(r["kept"], r["drop_script"], r["drop_language"], r["drop_conf"], r["speech_ms"], r["dur_ms"])


def main(argv: list[str]) -> int:
    rows = [json.loads(p.read_text(encoding="utf-8")) for d in argv for p in sorted(pathlib.Path(d).glob("*.json"))]
    if not rows:
        print("usage: python -I eval22.py <result_dir> [<result_dir> ...]", file=sys.stderr)
        return 2
    misses = []
    for name in EXPECTED:
        members = [r for r in rows if group(r["file"]) == name]
        counts = Counter(verdict(r) for r in members)
        silent = [r for r in members if r["kept"] == 0]
        span = ""
        if silent:
            speech = [r["speech_ms"] / 1000 for r in silent]
            share = [r["share"] for r in silent]
            span = (
                f"  ohne behaltenes Wort {len(silent)}: Sprache {min(speech):.1f} bis {max(speech):.1f} s,"
                f" Anteil {min(share):.0%} bis {max(share):.0%}"
            )
        print(f"{name:<12}{len(members):4d}  {dict(sorted(counts.items()))}{span}")
        misses += [(name, r) for r in members if verdict(r) != EXPECTED[name]]
    print("\nabweichend vom erwarteten Urteil:")
    for name, r in misses:
        print(
            f"  {name:<12}{r['file']:<32}{r['speech_ms'] / 1000:6.1f} s {r['share']:5.0%}"
            f"  roh {r['raw_words']:3d}  behalten {r['kept']:3d}  -> {verdict(r)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
