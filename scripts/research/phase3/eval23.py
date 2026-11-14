"""Phase 3, D-03-23: die Fenster des zweiten VAD-Durchgangs aus verdict23.py auswerten und die Schwelle bestimmen.

python -I eval23.py [--check] <result_dir> [<result_dir> ...]
Läuft mit der Umgebung des Backends (``uv run --project backend``). Die neue Regel prüft dieses
Skript selbst nach (eigene Formel, nicht aus engine/catch.py): ein Fenster des zweiten Durchgangs
bleibt, wenn die alte Regel es behielt, seine Textsprache DE, EN oder FR mit p >= 0,9 ist und
seine mittlere Wortkonfidenz mindestens T erreicht. Aus catch kommen nur file_verdict und die
Namen der Urteile; nur mit ``--check`` zusätzlich window_verdict und SECOND_PASS_CONF für die
Gegenprobe (0 Abweichungen erwartet).

P: Dateien der Gruppe instance, deren zweiter Durchgang Wörter behielt (Pflicht: die Kurzmemos
short1w bis short4w). N: Fenster des zweiten Durchgangs in nonspeech, foreign und unsupported,
die die alte Regel behielt. L = max(0,5, größtes conf_mean der N-Fenster mit sicherer
Instanzsprache), U = kleinstes conf_mean der besten Fenster der P-Dateien. Eindeutig, wenn keine
P-Datei ohne sichere Sprache ist und U - L >= 0,02; dann T = Mitte von L und U, auf zwei Stellen
abgerundet. Ausgabe als Markdown auf stdout. Kein Text verlässt den Rechner.
"""

import importlib
import json
import pathlib
import sys
from collections.abc import Iterable
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from audio_video_search_backend.engine.catch import (
    DROP_CONFIDENCE,
    DROP_LANGUAGE,
    DROP_SCRIPT,
    KEEP,
    file_verdict,
)

FOREIGN = ("es_419", "it_it", "nl_nl", "pl_pl", "ru_ru", "el_gr")
UNSUPPORTED = ("tr_tr", "ar_eg", "cmn_hans_cn", "ja_jp", "hi_in", "vi_vn", "sw_ke")
SUNG = ("music_band_rock", "sing_en_bowlly_guilty", "sing_en_california")
GROUPS = ("instance", "nonspeech", "sung", "foreign", "unsupported")
NEGATIVE = ("nonspeech", "foreign", "unsupported")
MEMOS = ("short1w", "short2w", "short3w", "short4w")
SURE_LANGUAGES = {"de", "en", "fr"}
FLOOR_CONF = Decimal("0.5")  # CONF_INSTANCE, the old lower border
MIN_GAP = Decimal("0.02")
JA = "fleurs_ja_jp_00"


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


def sure(w: dict[str, Any]) -> bool:
    """Old rule kept it and the text language is surely an instance language."""
    return w["verdict"] == KEEP and w["lid"] in SURE_LANGUAGES and w["lid_p"] >= 0.9


def stays(w: dict[str, Any], t: Decimal) -> bool:
    return sure(w) and Decimal(str(w["conf_mean"])) >= t


def expected_verdict(w: dict[str, Any], t: Decimal) -> str:
    """The verdict the new rule must give in the second pass, from the stored old verdict."""
    if w["verdict"] in (DROP_SCRIPT, DROP_LANGUAGE):
        return w["verdict"]
    return KEEP if stays(w, t) else DROP_CONFIDENCE


def counts(r: dict[str, Any], t: Decimal | None) -> tuple[int, int, int, int]:
    """kept, script, language, conf of a file; with t the rejected second-pass windows move to conf."""
    kept, conf = r["kept"], r["drop_conf"]
    if t is not None:
        for w in r.get("second_windows", []):
            if w["verdict"] == KEEP and not stays(w, t):
                kept -= w["kept_n"]
                conf += w["n_words"]
    return kept, r["drop_script"], r["drop_language"], conf


def verdict(r: dict[str, Any], t: Decimal | None) -> str:
    kept, script, language, conf = counts(r, t)
    return file_verdict(kept, script, language, conf, r["speech_ms"], r["dur_ms"])


def span(values: Iterable[float], fmt: str = "{:.3f}") -> str:
    items = list(values)
    if not items:
        return "-"
    return f"{fmt.format(min(items))} bis {fmt.format(max(items))}"


def threshold(low: Decimal, high: Decimal) -> Decimal:
    mid = (low + high) / 2
    for step in (Decimal("0.01"), Decimal("0.001")):
        t = mid.quantize(step, rounding=ROUND_FLOOR)
        if low < t <= high:
            return t
    return high


def check(rows: list[dict[str, Any]]) -> int:
    catch = importlib.import_module("audio_video_search_backend.engine.catch")
    measured = getattr(catch, "SECOND_PASS_CONF", None)
    if measured is None:
        print("catch.SECOND_PASS_CONF fehlt: --check erst nach der Umsetzung (Task 2)", file=sys.stderr)
        return 2
    t = Decimal(str(measured))
    windows = [w for r in rows for w in r.get("second_windows", [])]
    off = 0
    for w in windows:
        got = catch.window_verdict(w["latin"], w["lid"], w["lid_p"], w["n_words"], w["conf_mean"], second_pass=True)
        if got != expected_verdict(w, t):
            off += 1
            print(f"Abweichung: {w} -> catch {got}, Messformel {expected_verdict(w, t)}")
    print(f"\n## Gegenprobe --check\n\nSECOND_PASS_CONF = {t}; {len(windows)} Fenster geprüft, {off} Abweichungen")
    return 1 if off else 0


def main(argv: list[str]) -> int:
    run_check = bool(argv) and argv[0] == "--check"
    dirs = argv[1:] if run_check else argv
    rows = [json.loads(p.read_text(encoding="utf-8")) for d in dirs for p in sorted(pathlib.Path(d).glob("*.json"))]
    if not rows:
        print("usage: python -I eval23.py [--check] <result_dir> [<result_dir> ...]", file=sys.stderr)
        return 2
    print(f"# D-03-23: zweiter VAD-Durchgang\n\nDateien gemessen: {len(rows)}\n")

    # (a) P and its best windows
    positives = [r for r in rows if group(r["file"]) == "instance" and r.get("second_kept", 0) > 0]
    best: dict[str, dict[str, Any] | None] = {}
    for r in positives:
        candidates = [w for w in r["second_windows"] if sure(w)]
        best[r["file"]] = max(candidates, key=lambda w: w["conf_mean"]) if candidates else None
    unsure = [name for name, w in best.items() if w is None]

    # (b) N
    negatives = [
        (r["file"], w)
        for r in rows
        if group(r["file"]) in NEGATIVE
        for w in r.get("second_windows", [])
        if w["verdict"] == KEEP
    ]
    sure_negatives = [w["conf_mean"] for _, w in negatives if sure(w)]

    # (c) L, U, T
    low = max([FLOOR_CONF, *(Decimal(str(c)) for c in sure_negatives)])
    found = [Decimal(str(w["conf_mean"])) for w in best.values() if w is not None]
    high = min(found) if found else None
    clear = not unsure and high is not None and high - low >= MIN_GAP
    t = threshold(low, high) if clear and high is not None else None

    print("## Gruppen\n")
    print("| Gruppe | Dateien | mit zweitem Durchgang | Fenster | davon alt behalten | lid/p (alt behalten) |", end="")
    print(" conf_mean (alt behalten) | Wörter 2. Durchgang alt | neu | Urteilswechsel |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name in GROUPS:
        members = [r for r in rows if group(r["file"]) == name]
        ran = [r for r in members if r.get("second_pass")]
        windows = [w for r in ran for w in r.get("second_windows", [])]
        held = [w for w in windows if w["verdict"] == KEEP]
        lids = sorted({f"{w['lid']} {w['lid_p']:.3f}" for w in held})
        lid_text = ", ".join(lids) if len(lids) <= 6 else f"{len(lids)} Werte, p {span(w['lid_p'] for w in held)}"
        old_words = sum(r.get("second_kept", 0) for r in members)
        new_words: int | str = "-"
        changed: int | str = "-"
        if t is not None:
            new_words = sum(w["kept_n"] for w in held if stays(w, t))
            changed = sum(1 for r in members if verdict(r, None) != verdict(r, t))
        print(
            f"| {name} | {len(members)} | {len(ran)} | {len(windows)} | {len(held)} | {lid_text or '-'} |"
            f" {span(w['conf_mean'] for w in held)} | {old_words} | {new_words} | {changed} |"
        )

    print("\n## P: instance-Dateien mit Wörtern aus dem zweiten Durchgang\n")
    print("| Datei | Pflicht-Memo | Wörter 2. Durchgang | bestes Fenster lid | p | conf_mean | conf_min | Text |")
    print("|---|---|---|---|---|---|---|---|")
    for r in sorted(positives, key=lambda r: r["file"]):
        w = best[r["file"]]
        memo = "ja" if r["file"].startswith(MEMOS) else "nein"
        if w is None:
            held = [x for x in r["second_windows"] if x["verdict"] == KEEP]
            info = "; ".join(f"{x['lid']} {x['lid_p']} conf {x['conf_mean']}" for x in held)
            print(f"| {r['file']} | {memo} | {r['second_kept']} | ohne sichere Sprache ({info}) | | | | |")
            continue
        print(
            f"| {r['file']} | {memo} | {r['second_kept']} | {w['lid']} | {w['lid_p']} | {w['conf_mean']} |"
            f" {w['conf_min']} | {w['text']} |"
        )

    print("\n## N: alt behaltene Fenster des zweiten Durchgangs in nonspeech, foreign, unsupported\n")
    print("| Datei | Gruppe | Wörter | latin | lid | p | conf_mean | conf_min | sicher | Text |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name, w in sorted(negatives, key=lambda item: item[0]):
        mark = " (JA-Befund)" if name == JA else ""
        print(
            f"| {name}{mark} | {group(name)} | {w['n_words']} | {w['latin']} | {w['lid']} | {w['lid_p']} |"
            f" {w['conf_mean']} | {w['conf_min']} | {'ja' if sure(w) else 'nein'} | {w['text']} |"
        )

    print("\n## Schwelle\n")
    print(f"- L = {low} (max aus 0,5 und {len(sure_negatives)} N-Fenstern mit sicherer Instanzsprache)")
    print(f"- U = {high if high is not None else '-'} (kleinstes bestes conf_mean von {len(found)} P-Dateien)")
    print(f"- P-Dateien ohne sichere Sprache: {', '.join(unsure) if unsure else 'keine'}")
    print(f"- eindeutig: {'ja' if clear else 'nein'}; T = {t if t is not None else '-'}")

    if t is not None:
        print("\n## Mit T\n")
        for name in GROUPS:
            members = [r for r in rows if group(r["file"]) == name]
            for r in members:
                if verdict(r, None) != verdict(r, t):
                    print(f"- Urteilswechsel {name} {r['file']}: {verdict(r, None)} -> {verdict(r, t)}")
        for r in sorted(positives, key=lambda r: r["file"]):
            lost = counts(r, None)[0] - counts(r, t)[0]
            if lost:
                print(f"- P {r['file']}: {lost} Wörter verloren, bleibt {counts(r, t)[0]}")
        kept_neg = sum(w["kept_n"] for _, w in negatives if stays(w, t))
        print(f"- N: behaltene Wörter aus dem zweiten Durchgang neu: {kept_neg} (Soll 0)")

    return check(rows) if run_check else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
