"""Verteilung der mittleren Wortkonfidenz je VAD-Fenster nach Gruppe.  python -I confdist.py <dir> [<dir> ...]"""

import json
import pathlib
import sys


def group(name: str) -> str | None:
    if name.startswith(("lang_de", "lang_en", "lang_fr", "memo", "short", "podcast")):
        return "Instanz sauber"
    if name.startswith("deg_"):
        return "Instanz verschlechtert"
    if name.startswith(("lang_ar", "lang_cmn", "lang_hi", "lang_ja", "lang_sw", "lang_tr", "lang_vi")):
        return "nicht unterstuetzt"
    if name.startswith(("lang_es", "lang_it", "lang_nl", "lang_pl")):
        return "Fremd lateinisch (Parakeet-Sprache)"
    if name.startswith(("sing_", "music_")):
        return "Musik/Gesang"
    return None


groups: dict[str, list[tuple[float, int, str]]] = {}
for d in sys.argv[1:]:
    for p in pathlib.Path(d).glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        g = group(r["file"])
        if g is None:
            continue
        for w in r["windows"]:
            if w["nw"]:
                groups.setdefault(g, []).append((w["conf_mean"], w["nw"], r["file"]))
for g, vals in groups.items():
    cs = sorted(v[0] for v in vals)
    n = len(cs)
    below = {t: sum(v[1] for v in vals if v[0] < t) for t in (0.5, 0.6, 0.7)}
    total = sum(v[1] for v in vals)
    print(
        f"{g:<38} Fenster {n:4d} Woerter {total:5d}  min {cs[0]:.2f} p05 {cs[n // 20]:.2f} median {cs[n // 2]:.2f}"
        f" p95 {cs[min(n - 1, 19 * n // 20)]:.2f} max {cs[-1]:.2f} | Woerter unter 0,5/0,6/0,7: "
        f"{below[0.5]}/{below[0.6]}/{below[0.7]}"
    )
    low = sorted(vals)[:3]
    print("   niedrigste:", [(round(c, 2), nw, f) for c, nw, f in low])
