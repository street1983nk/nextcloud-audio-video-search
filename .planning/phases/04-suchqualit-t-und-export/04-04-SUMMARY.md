---
phase: 04-suchqualit-t-und-export
plan: 04
subsystem: tests/export
tags: [EXP-02, untertitel, srt, webvtt, ffmpeg, gegenprobe]
requires: []
provides:
  - "backend/tests/subtitle_checkers.py: check_vtt, check_srt, check_ffmpeg(text, suffix, expected_cues=None), read_vtt_captions, read_srt_subtitles, Cue, SubtitleCheckError"
affects: [04-08, 04-09, 04-14]
tech-stack:
  added: ["webvtt-py==0.8.0 (nur dev)", "srt==3.5.3 (nur dev, sdist)"]
  patterns: ["unabhängige Prüfer mit Positiv- und Negativkontrolle", "bekannte Prüferlücken als xfail strict mit eigener Ausnahme"]
key-files:
  created:
    - backend/tests/subtitle_checkers.py
    - backend/tests/test_subtitle_checkers.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
decisions:
  - "Owner 16.11.2026: webvtt-py 0.8.0 (Trusted-Publishing-Provenance) und srt 3.5.3 (nur sdist, Build akzeptiert) freigegeben, nur dev"
  - "check_ffmpeg dekodiert nach SRT auf stdout und zählt Cues, weil ffmpeg unlesbare Cues still verwirft; expected_cues prüft die Anzahl"
  - "check_srt lehnt Text auf der Zeitzeile ab (srt-Feld proprietary), weil reines SRT dort nichts kennt"
metrics:
  completed: 2026-11-16
  tasks: 2
  files: 4
---

# Phase 4 Plan 04: Unabhängige Untertitel-Prüfer Summary

Drei unabhängige Prüfer für SRT/VTT (webvtt-py 0.8.0 strikt plus validate, srt 3.5.3, ffmpeg-Demuxer mit Cue-Zählung) als gemeinsame Hilfen für die Export-Tests; jeder lässt eine handgeschriebene gültige Datei durch und schlägt nachweislich auf kaputten an.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Legitimität webvtt-py und srt (blocking-human) | keiner (Owner-Entscheid 16.11.2026) | keine |
| 2 | dev-Pins und Positivkontrolle der drei Prüfer | 847470f | backend/pyproject.toml, backend/uv.lock, backend/tests/subtitle_checkers.py, backend/tests/test_subtitle_checkers.py |

## Ergebnis

- Pins nur in `[dependency-groups] dev`. Die Hashes im uv.lock stimmen mit den vorgelegten Werten überein: webvtt-py-Wheel `1780a77d...8524`, srt-sdist `48843150...0cc0`.
- Prüfer erkennen:
  - webvtt-py: fehlender Kopf, Pfeil `->`, Ende vor Start, Müll.
  - srt: Text auf der Zeitzeile, Ende vor Start, Müll.
  - ffmpeg: Pfeil `->` (Cue fehlt, Anzahl stimmt nicht), Müll als VTT (0 Cues), Müll als SRT (Exit-Code ungleich 0).
- Gültige VTT (Kopf, NOTE, zwei Cues, `&amp;`, Umlaute) und gültige SRT liefern bei webvtt-py und srt genau die erwarteten Zeiten und Texte, `&amp;` wird einmal entmaskiert. ffmpeg dekodiert beide gültigen Dateien mit 2 Cues, ohne etwas auf stderr.
- ffmpeg wird nur über `find_tool("AVS_FFMPEG", "ffmpeg")` gesucht. Lokal ohne ffmpeg gibt es einen Skip mit Grund, unter `CI=true` schlagen alle 8 ffmpeg-Fälle fehl, auch die xfail-Fälle (gegengeprüft). Es gibt kein `skipif`.
- Gates: ruff `--no-cache` (check und format) grün, pyright 0 Fehler, vulture grün, volle Suite: 1964 bestanden, 15 übersprungen, 4 xfailed. test_lock_wheels und test_dockerfile bleiben unverändert grün.

## Bekannte Grenzen (xfail strict, CheckerMissedIt)

1. **SRT ohne Leerzeile zwischen zwei Cues:** srt und ffmpeg lesen beide Cues korrekt wieder ein und erkennen den Fehler nicht. Kein Text geht verloren, das belegt ein eigener Test. Die Export-Tests in 04-08 und 04-14 müssen deshalb den exakten erwarteten Text vergleichen.
2. **ffmpeg, VTT ohne `WEBVTT`-Kopf:** wird stillschweigend gelesen. webvtt-py erkennt den Fehler.
3. **ffmpeg, VTT-Cue mit Ende vor Start:** wird stillschweigend gelesen. webvtt-py erkennt den Fehler.

Die xfail-Marken akzeptieren nur `CheckerMissedIt`. Ein fehlendes ffmpeg unter CI kann deshalb nie als erwartete Lücke durchgehen.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ffmpeg mit `-f null` lehnt eine reine Untertiteldatei ab**
- **Found during:** Task 2
- **Issue:** `ffmpeg -i x.vtt -f null -` bricht mit "Output file does not contain any stream" ab. Außerdem verwirft ffmpeg kaputte Cues still, mit Exit-Code 0.
- **Fix:** Dekodieren mit `-map 0:s:0 -c:s srt -f srt pipe:1` und Cues zählen. Kein Cue ist ein Fehler. Optional prüft `expected_cues` die Anzahl, die Signatur bleibt mit dem dritten Parameter abwärtskompatibel.
- **Commit:** 847470f

**2. [Rule 2 - Korrektheit] check_srt lehnt Text auf der Zeitzeile ab**
- **Found during:** Task 2
- **Issue:** srt liest Text hinter der Zeitangabe als Positionsangabe (`proprietary`) und meldet keinen Fehler.
- **Fix:** Ist `proprietary` nicht leer, wird SubtitleCheckError geworfen. Der Writer schreibt dort nie etwas.
- **Commit:** 847470f

## Threat Flags

Keine neue Angriffsfläche. T-04-SC ist umgesetzt: blockierender Checkpoint, exakte Pins, Hashes im Lock, nur dev. T-04-11 ist umgesetzt: Positiv- und Negativkontrolle, Lücken als xfail strict benannt.

## Self-Check: PASSED

- FOUND: backend/tests/subtitle_checkers.py
- FOUND: backend/tests/test_subtitle_checkers.py
- FOUND: Commit 847470f
