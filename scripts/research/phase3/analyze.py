"""Phase-3-Research: Auswertung der Messung (Kandidatenregeln für keine Sprache / nicht unterstützt).

python -I analyze.py <results_dir>
"""

import json
import pathlib
import sys

R = pathlib.Path(sys.argv[1])
INST = {"de", "en", "fr"}


def load() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(R.glob("*.json"))]


def group(name: str) -> str:
    if name.startswith("lang_"):
        code = name[5:7]
        if code in INST:
            return "speech_inst"
        return "foreign_pk" if code in {"es", "it", "pl", "nl", "ru", "el"} else "foreign_unsup"
    for pre, g in (
        ("memo3s_", "memo3s"),
        ("memo_", "memo"),
        ("ns_", "nonspeech"),
        ("music_", "music"),
        ("sing_", "sing"),
        ("mix_", "mixed"),
        ("podcast", "memo"),
    ):
        if name.startswith(pre):
            return g
    return "other"


def window_kept(w: dict, rule: str) -> bool:
    """Abfangregel-Kandidaten je Fenster (VAD-Fenster bis 25 s)."""
    if not w["nw"]:
        return False
    if w["latin"] < 0.5:
        return False
    if rule == "script":
        return True
    if rule == "lid":
        return w["lid"] in INST
    if rule == "lid_or_short":
        # sehr kurze Fenster (<3 Wörter) sind für jede Text-LID zu kurz: behalten, wenn Datei-LID Instanz ist
        return w["lid"] in INST or w["nw"] < 3
    raise ValueError(rule)


def main() -> None:
    rows = load()
    print(
        f"{'Datei':<34}{'Gruppe':<14}{'Dauer':>7}{'VAD-s':>7}{'Ant%':>6}{'Wort':>6}{'W/s':>6}{'Konf':>6}"
        f"{'lat':>5}{'LID':>5}{'p':>6}{'stop':>6}{'keep':>6}{'keep%':>6}"
    )
    for r in rows:
        g = group(r["file"])
        speech = r["speech_s"]
        share = 100 * speech / r["dur_s"] if r["dur_s"] else 0
        kept = sum(w["nw"] for w in r["windows"] if window_kept(w, "lid_or_short"))
        nw = r["n_words"]
        wps = nw / speech if speech else 0
        stop = r["stop_lang"] or "-"
        print(
            f"{r['file'][:33]:<34}{g:<14}{r['dur_s']:7.0f}{speech:7.1f}{share:6.1f}{nw:6d}{wps:6.2f}"
            f"{(r['conf_mean'] or 0):6.2f}{r['latin']:5.2f}{r['lid'][:4]:>5}{r['lid_p']:6.2f}{stop:>6}{kept:6d}"
            f"{(100 * kept / nw if nw else 0):6.0f}"
        )


if __name__ == "__main__":
    main()
