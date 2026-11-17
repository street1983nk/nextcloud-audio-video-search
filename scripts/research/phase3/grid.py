"""Raster über die Abfangregel: C (Konfidenz allgemein), C2 (Konfidenz bei sicherer Instanz-Sprache), P (LID).

Fensterregel: verwerfen bei Schrift < 50 % lateinisch; verwerfen bei fremder Text-Sprache mit p >= P und >= 3 Wörtern;
sonst behalten, wenn conf >= C oder (Text-Sprache in DE/EN/FR mit p >= P und conf >= C2).
python -I grid.py <dir> [<dir> ...]
"""

import json
import pathlib
import sys

INST = {"de", "en", "fr"}


def group(name: str) -> str | None:
    if name.startswith(("lang_de", "lang_en", "lang_fr", "memo", "short", "podcast")):
        return "inst_clean"
    if name.startswith(("deg_pink", "deg_tel")):
        return "inst_noisy"
    if name.startswith(("lang_ar", "lang_cmn", "lang_hi", "lang_ja", "lang_sw", "lang_tr", "lang_vi")):
        return "unsupported"
    if name.startswith(("lang_es", "lang_it", "lang_nl", "lang_pl", "lang_ru", "lang_el")):
        return "foreign_pk"
    if name.startswith(("sing_", "music_")):
        return "music_sing"
    return None


wins = []
for d in sys.argv[1:]:
    for p in pathlib.Path(d).glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        g = group(r["file"])
        if g:
            wins += [(g, w) for w in r["windows"] if w["nw"]]


def keep(w: dict, c: float, c2: float, pp: float) -> bool:
    if w["latin"] < 0.5:
        return False
    if w["lid"] not in INST and w["lid_p"] >= pp and w["nw"] >= 3:
        return False
    if w["conf_mean"] >= c:
        return True
    return w["lid"] in INST and w["lid_p"] >= pp and w["conf_mean"] >= c2


print(f"{'C':>5}{'C2':>5}{'P':>5} | kept words: inst_clean inst_noisy | unsupported foreign_pk music_sing")
tot = {}
for g, w in wins:
    tot[g] = tot.get(g, 0) + w["nw"]
for c in (0.5, 0.55, 0.6, 0.65):
    for c2 in (0.4, 0.45, 0.5, c):
        if c2 > c:
            continue
        for pp in (0.8, 0.9):
            k = {}
            for g, w in wins:
                if keep(w, c, c2, pp):
                    k[g] = k.get(g, 0) + w["nw"]
            print(
                f"{c:5.2f}{c2:5.2f}{pp:5.2f} | {k.get('inst_clean', 0):5d}/{tot['inst_clean']} "
                f"{k.get('inst_noisy', 0):5d}/{tot['inst_noisy']} | {k.get('unsupported', 0):4d}/{tot['unsupported']} "
                f"{k.get('foreign_pk', 0):4d}/{tot['foreign_pk']} {k.get('music_sing', 0):4d}/{tot['music_sing']}"
            )
