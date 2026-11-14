"""Phase-3-Research: Abfangregel-Kandidaten gegen den Korpus auswerten.

python -I evalrule.py <C> <P> <results_dir> [<results_dir> ...]
Fensterregel: behalten, wenn Schrift >= 50 % lateinisch, mittlere Wortkonfidenz >= C und nicht
(Text-Sprache außerhalb DE/EN/FR mit p >= P und mind. 3 Wörter).
"""

import json
import pathlib
import sys

INST = {"de", "en", "fr"}
C = float(sys.argv[1])
P = float(sys.argv[2])


def verdict(w: dict) -> str:
    if not w["nw"]:
        return "empty"
    if w["latin"] < 0.5:
        return "script"
    if w["conf_mean"] < C:
        return "conf"
    if w["lid"] not in INST and w["lid_p"] >= P and w["nw"] >= 3:
        return "lid"
    return "keep"


rows = []
for d in sys.argv[3:]:
    for p in sorted(pathlib.Path(d).glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        tally = {"keep": 0, "script": 0, "conf": 0, "lid": 0, "empty": 0}
        for w in r["windows"]:
            tally[verdict(w)] += w["nw"]
        sp = r["speech_s"]
        rows.append((r["file"], r["dur_s"], sp, r["n_words"], tally))
print(f"C={C} P={P}")
print(f"{'Datei':<30}{'Dauer':>7}{'VAD-s':>7}{'Wort':>6}{'keep':>6}{'conf':>6}{'lid':>5}{'skr':>5}{'W/VADs':>8}")
for f, du, sp, nw, t in rows:
    print(
        f"{f[:29]:<30}{du:7.0f}{sp:7.1f}{nw:6d}{t['keep']:6d}{t['conf']:6d}{t['lid']:5d}{t['script']:5d}"
        f"{(nw / sp if sp else 0):8.2f}"
    )
