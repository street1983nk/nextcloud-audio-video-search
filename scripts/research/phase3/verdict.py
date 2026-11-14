"""Endregel der Research: Fensterregel + Dateiurteil, je Datei ausgegeben.

Fenster: verwerfen bei Schrift < 0,5 lateinisch ("script"); verwerfen bei Text-Sprache außerhalb DE/EN/FR mit
p >= 0,9 und >= 3 Wörtern ("language"); behalten bei conf >= 0,6 oder (Text-Sprache DE/EN/FR mit p >= 0,9 und
conf >= 0,5); sonst verwerfen ("confidence").
Datei: behalten >= 1 Wort -> "transcript"; sonst "unsupported", wenn (script+language) >= 5 Wörter oder
(confidence >= 10 Wörter und VAD-Sprache >= 10 s und VAD-Anteil >= 30 %); sonst "no_speech".
python -I verdict.py <dir> [<dir> ...]
"""

import json
import pathlib
import sys

INST = {"de", "en", "fr"}


def window(w: dict) -> str:
    if w["latin"] < 0.5:
        return "script"
    if w["lid"] not in INST and w["lid_p"] >= 0.9 and w["nw"] >= 3:
        return "language"
    if w["conf_mean"] >= 0.6 or (w["lid"] in INST and w["lid_p"] >= 0.9 and w["conf_mean"] >= 0.5):
        return "keep"
    return "confidence"


for d in sys.argv[1:]:
    for p in sorted(pathlib.Path(d).glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        t = {"keep": 0, "script": 0, "language": 0, "confidence": 0}
        for w in r["windows"]:
            if w["nw"]:
                t[window(w)] += w["nw"]
        share = r["speech_s"] / r["dur_s"] if r["dur_s"] else 0
        if t["keep"] >= 1:
            v = "transcript"
        elif t["script"] + t["language"] >= 5 or (t["confidence"] >= 10 and r["speech_s"] >= 10 and share >= 0.3):
            v = "unsupported"
        else:
            v = "no_speech"
        print(
            f"{r['file'][:30]:<31}{r['dur_s']:7.0f}{r['speech_s']:7.1f}{100 * share:5.0f}%{r['n_words']:5d}"
            f"  keep {t['keep']:4d} conf {t['confidence']:4d} lang {t['language']:4d} script {t['script']:4d}  -> {v}"
        )
