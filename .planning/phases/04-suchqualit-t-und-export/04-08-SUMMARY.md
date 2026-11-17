---
phase: 04-suchqualit-t-und-export
plan: 08
subsystem: export
tags: [subtitles, srt, vtt, txt, exp-02, exp-04, tdd, messung]

# Dependency graph
requires:
  - phase: 04-suchqualit-t-und-export (plan 04-07)
    provides: "subtitles/cues.py: Cue, build_cues, count_overruns; Fuzz-Generator und NORMAL/FAST-Fixtures"
  - phase: 04-suchqualit-t-und-export (plan 04-04)
    provides: "unabhängige Prüfer tests/subtitle_checkers.py (webvtt-py 0.8.0, srt 3.5.3, ffmpeg)"
provides:
  - "subtitles/formats.py: to_srt(cues), to_vtt(cues), to_txt(words), TXT_PARAGRAPH_PAUSE_MS=2000"
  - "Prüfer-Beweis über alle 300 Fuzz-Fälle plus NORMAL/FAST: webvtt-py, srt und ffmpeg lesen jede Ausgabe, exakter Text und exakte Zeiten je Cue"
  - "Messung 100 000 Wörter (12,6 h): Zeit und Größe je Format, Bemessung für EXPORT_TIMEOUT_SECONDS und EXPORT_MAX_BODY_BYTES"
affects: [04-09 (Container-Route und Abgleichtest), 04-10 (PHP-Konstanten), 04-14]

# Tech tracking
tech-stack:
  added: []
  patterns: "Writer ohne Untertitel-Bibliothek (ca. 60 Zeilen); VTT-Maskierung & < > nur im Cue-Text; ffmpeg-Zählung berücksichtigt Pfeil-Textzeilen"

key-files:
  created:
    - backend/src/audio_video_search_backend/subtitles/formats.py
    - backend/tests/test_subtitles_formats.py
    - scripts/research/phase4/measure_export.py
  modified:
    - backend/src/audio_video_search_backend/subtitles/cues.py
    - backend/tests/test_subtitles_cues.py

key-decisions:
  - "ffmpeg-Erwartungswert = len(cues) + Textzeilen mit eigenem Pfeil: check_ffmpeg zählt Pfeilzeilen der zurückcodierten SRT-Ausgabe, ffmpeg schreibt Textzeilen wörtlich zurück (SRT) bzw. entmaskiert (VTT), gemessen mit ffmpeg 8.1.1"
  - "Negativer Wortstart wird in build_cues auf 0 geklemmt (SRT/VTT kennen keine negative Zeit), Fuzz-Fund beim Prüfer-Beweis"
  - "Messbefund: EXPORT_MAX_BODY_BYTES nach Formel 8 MiB statt der 16 MiB aus 04-10, deutlich markiert für 04-09"

patterns-established:
  - "Steuerzeichen-Behandlung hat genau eine Definition: formats.to_txt nutzt das _CONTROL-Muster aus cues.py (T-04-20)"

requirements-completed: [EXP-02, EXP-01 (Anteil Formate), EXP-04 (Anteil Writer)]

# Metrics
duration: 45min
completed: 2026-11-16
---

# Phase 4 Plan 08: Format-Writer SRT, VTT, TXT Summary

**to_srt/to_vtt/to_txt formen Cues und Wörter in die drei Exportformate, bewiesen durch drei fremde Prüfer (webvtt-py, srt, ffmpeg) über alle Fuzz-Fälle mit exaktem Text und exakten Zeiten; die 100 000-Wörter-Messung bemisst Timeout (30 s bleibt) und Größengrenze (Formel ergibt 8 MiB, 04-10 trägt 16 MiB, deutlich markiert).**

## Performance

- **Duration:** ca. 45 min Arbeitszeit (Usage-Limit-Pause zwischen Start und Fortsetzung nicht gezählt)
- **Started:** 2026-11-16T09:02:59Z
- **Completed:** 2026-11-16T13:55:00Z
- **Tasks:** 2 (Task 1 TDD: RED, GREEN; Task 2 Messung)
- **Files modified:** 5

## Accomplishments

- Writer ohne Bibliothek: SRT (Nummer ab 1, Komma-Millisekunden, Text roh), VTT (WEBVTT-Kopf, Punkt-Millisekunden, `&` `<` `>` im Cue-Text maskiert, T-04-21), TXT (Fließtext ohne Zeitmarken, Absatz bei Pause über 2 s). Stunden zweistellig, über 99 h dreistellig; nur LF, kein BOM; kein Kopf-/NOTE-Text im Container (D-04-03, Gate-Regel 13).
- Drei-Prüfer-Beweis über alle 300 Fuzz-Fälle aus 04-07 (gleicher Generator, fester Seed) plus NORMAL/FAST: check_vtt und check_srt werfen nicht, webvtt-py (nach Entmaskierung) und srt lesen je Cue exakt `"\n".join(cue.lines)` und exakt die Cue-Zeiten in ms; ffmpeg dekodiert jede Datei ohne stderr mit der erwarteten Cue-Zahl (rund 590 Aufrufe je Format-Paar, lokal ffmpeg 8.1.1 im PATH, kein Skip).
- Maskierungs-Literal: `a --> b <i>x</i> & y` steht in VTT als `a --&gt; b &lt;i&gt;x&lt;/i&gt; &amp; y` und kommt über webvtt-py identisch zurück; in SRT roh und von srt unverändert gelesen.
- Text-Gate EXP-04: zeilenweise Gleichheit beweist, dass kein Wort (also auch kein "BITV") aus dem Writer stammt (T-04-23); to_txt-Tokens sind wortgleich zu den sichtbaren Tokens der Eingabe.

## Task Commits

1. **Task 1 RED: Prüfer-Tests + Skelett** - `101888e` (test)
2. **Task 1 GREEN: Writer-Implementierung + Zeit-Klemmung** - `b3c2542` (feat)
3. **Task 2: Messskript Export-Zeit und -Größe** - `edece04` (chore)

_REFACTOR entfiel: Implementierung bestand alle Gates ohne Nacharbeit._

## Files Created/Modified

- `backend/src/audio_video_search_backend/subtitles/formats.py` - to_srt, to_vtt, to_txt, TXT_PARAGRAPH_PAUSE_MS, _clock, _escape_vtt
- `backend/tests/test_subtitles_formats.py` - Prüfer-Beweis (check_vtt, check_srt, check_ffmpeg) über Fuzz + Fixtures, Literal- und TXT-Tests
- `backend/src/audio_video_search_backend/subtitles/cues.py` - Fix: negativer Wortstart wird 0
- `backend/tests/test_subtitles_cues.py` - Fuzz-Eigenschaft ergänzt: Cue-Zeiten nie negativ
- `scripts/research/phase4/measure_export.py` - Messung Zeit/Größe/JSON-Hülle, argparse --words/--runs, JSON-Ausgabe

## Messwerte (T-04-19, T-04-22; 5 Läufe, Windows-Laptop, Python 3.13)

100 000 Wörter im NORMAL-Tempo = 12,61 h Rede, 11 244 Cues.

| Format | Median Sekunden (inkl. build_cues bei SRT/VTT) | Bytes (UTF-8) | Bytes JSON-Hülle `{"known": true, "body": ...}` |
|---|---|---|---|
| build_cues allein | 0,432 | - | - |
| SRT | 0,453 | 1 042 202 | 1 096 702 |
| VTT | 0,460 | 985 852 | 1 029 110 |
| TXT | 0,090 | 637 281 | 637 309 |

**Abgeleitete Vorgaben für Plan 04-09 (Abgleichtest) und 04-10 (PHP-Konstanten):**

- `EXPORT_TIMEOUT_SECONDS = 30.0` bestätigt: max(30, 8 x 0,46 s) = 30; selbst mit Faktor 8 für Pi 5/arm64 liegt das teuerste Format bei rund 3,7 s, Reserve über 8x.
- **ABWEICHUNG, deutlich markiert:** `EXPORT_MAX_BODY_BYTES` nach Planformel = **8 MiB (8 388 608)**, nicht 16 MiB: größte JSON-Hülle bei 24 h Text = 2 x 1 096 702 = 2 193 404 Bytes, mal 2 = 4 386 808, nächste Zweierpotenz = 8 MiB. Die in 04-10 bereits umgesetzten 16 MiB liegen eine Zweierpotenz darüber (Faktor ~7,6 über der 24-h-Schätzung) und sind damit sicher, aber nicht die gemessene Bemessung. Entscheidung (16 MiB behalten oder auf 8 MiB senken) gehört in den Abgleichtest von Plan 04-09; dort bitte beide Zahlen gegenhalten.

## Decisions Made

- ffmpeg-Zählung: check_ffmpeg (04-04) zählt Pfeilzeilen der von ffmpeg zurückcodierten SRT-Ausgabe. Eine Cue-Textzeile mit eigenem "-->" zählt dadurch einmal mehr, denn ffmpeg schreibt Textzeilen wörtlich zurück (SRT) bzw. entmaskiert `--&gt;` (VTT); mit ffmpeg 8.1.1 am 2026-11-16 nachgemessen. Der Testhelfer `_ffmpeg_expected` addiert diese Zeilen, die Zählprüfung bleibt für jeden Fuzz-Fall scharf.
- VTT-Maskierung als geordnete Ersetzungsliste, `&` zuerst, sonst maskierte die Maske ihre eigenen Ampersands.
- to_txt verwendet das _CONTROL-Muster aus cues.py (ein Import, eine Definition für T-04-20) statt einer Kopie.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] build_cues reichte negative Wortzeiten durch**
- **Found during:** Task 1 GREEN (Prüfer-Beweis)
- **Issue:** Der Fuzz-Generator erzeugt Wortstarts bis -400 ms; build_cues gab Cues mit negativem start_ms aus, webvtt-py lehnte `-1:59:59.630` als ungültigen Cue ab. SRT/VTT können keine negative Zeit tragen.
- **Fix:** In cues._tokens wird der Start auf 0 geklemmt (an derselben Stelle, die schon end < start repariert); Eigenschaft `start_ms >= 0` im 04-07-Fuzz-Test verankert.
- **Files modified:** backend/src/audio_video_search_backend/subtitles/cues.py, backend/tests/test_subtitles_cues.py
- **Verification:** Alle Cue-, Prüfer- und Format-Tests grün; volle Suite grün.
- **Commit:** b3c2542

**2. [Messbefund statt Abweichung] EXPORT_MAX_BODY_BYTES-Formel ergibt 8 MiB, 04-10 trägt 16 MiB**
- Kein Code geändert: 16 MiB ist die sichere Obergrenze, die Entscheidung liegt beim Abgleichtest in Plan 04-09 (siehe Messwerte oben, deutlich markiert).

## Issues Encountered

- check_ffmpeg zählt Pfeilzeilen des dekodierten Textes; ohne den Erwartungswert-Helfer hätten Fuzz-Fälle mit "-->" im Cue-Text falsch gezählt (siehe Decisions). Kein Fehler der Prüfer, nur eine dokumentierte Eigenschaft ihrer Zählweise.
- Kein tantivy-"os error 5"-Flake in beiden vollen Suite-Läufen.

## Hinweis an 04-09

- Abgleichtest: 30 s Timeout bestätigt; Größengrenze bitte gegen die gemessenen 8 MiB (Formel) und die umgesetzten 16 MiB (04-10) gegenhalten und die Wahl dokumentieren.
- `to_vtt([])` liefert nur den Kopf `"WEBVTT\n\n"` (gültig, 0 Captions); `to_srt([])` und `to_txt([])` liefern `""`. Die Container-Route entscheidet, ob ein leeres Transkript überhaupt exportierbar ist.

## Known Stubs

Keine.

## Threat Flags

Keine neuen Flächen. T-04-21 (Maskierung + Fuzz + Rücklesen), T-04-22 (Messung bemisst Timeout/Grenze) und T-04-23 (Textgleichheit) sind umgesetzt und getestet.

## User Setup Required

None - no external service configuration required.

## Self-Check: PASSED

- Alle vier Dateien vorhanden (formats.py, test_subtitles_formats.py, measure_export.py, SUMMARY).
- Commits 101888e (test), b3c2542 (feat), edece04 (chore) im Log; test-Commit vor feat-Commit (TDD-Gates RED vor GREEN, RED aus NotImplementedError).
- Akzeptanz-Greps: to_srt/to_vtt/to_txt/TXT_PARAGRAPH_PAUSE_MS vorhanden; kein webvtt/srt/pysubs2-Import im Writer.
- Gates: ruff check + format (backend und ../scripts) grün, pyright 0 Fehler, vulture grün, volle Suite 2247 passed / 15 skipped / 4 xfailed (zweimal gelaufen, kein tantivy-Flake).

---
*Phase: 04-suchqualit-t-und-export*
*Completed: 2026-11-16*
