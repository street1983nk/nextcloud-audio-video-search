---
phase: 04-suchqualit-t-und-export
plan: 07
subsystem: export
tags: [subtitles, cues, exp-02, tdd, srt, vtt]

# Dependency graph
requires:
  - phase: 04-suchqualit-t-und-export (plan 04-04)
    provides: "unabhängige Untertitel-Prüfer tests/subtitle_checkers.py (srt, webvtt-py, ffmpeg) als Gegenprobe"
  - phase: 01-fundament
    provides: "model/overlay.py Word (start_ms, end_ms, surface) als Eingabetyp"
provides:
  - "subtitles/cues.py: Cue, Overruns, build_cues(words), count_overruns(cues) mit MAX_LINE=42, MAX_LINES=2, MIN_MS=1000, MAX_MS=7000, MAX_CPS=20, GAP_MS=80, PAUSE_CUT_MS=700"
  - "Eigenschaftstests mit Fuzz (300 Fälle), NORMAL/FAST-Sprechtempo-Fixtures und Zähl-Gate FAST_SPEECH_MAX_OVER_CPS_SHARE"
affects: [04-08 (SRT/VTT-Writer), 04-09, 04-14 (Export-Routen und Beweise)]

# Tech tracking
tech-stack:
  added: []
  patterns: "Cue-Bildung als reine Funktion über Sequence[Word]; weiche Grenzen gezählt statt Text geändert (D-04-16)"

key-files:
  created:
    - backend/src/audio_video_search_backend/subtitles/__init__.py
    - backend/src/audio_video_search_backend/subtitles/cues.py
    - backend/tests/test_subtitles_cues.py
  modified: []

key-decisions:
  - "Schnitt bei Rang-Gleichstand nach Balance (kleinster Längenunterschied) statt nur letzter Wortgrenze: verhindert Mini-Rest-Cues unter 1 s vor Pausen"
  - "FAST-Gate 0,98 statt 5-%-Schritt 1,00: gemessen 0,9762, der 5-%-Schritt wäre kein Gate mehr"
  - "Steuerzeichen-Ersatz je Lauf ein Leerzeichen, inkl. aller Whitespace-Läufe: hält die Textgleichheits-Formel des Plans exakt"

patterns-established:
  - "Gegenprobe über tests/subtitle_checkers (unabhängiger srt-Parser), nie über die eigene Logik"
  - "Messwerte in Assert-Meldungen statt Prints: f-String nennt gemessenen Anteil und Cue-Zahl"

requirements-completed: [EXP-02]

# Metrics
duration: 35min
completed: 2026-11-16
---

# Phase 4 Plan 07: Cue-Bildung aus Wortzeiten Summary

**build_cues formt Wortzeiten in Untertitel-Cues unter den EXP-02-Grenzen (42 Zeichen, 2 Zeilen, 1 bis 7 s, 20 Zeichen/s, 80 ms Abstand), ohne je ein Zeichen Text zu ändern; count_overruns zählt unvermeidbare Überschreitungen, die Tests setzen Schwellen als Gate.**

## Performance

- **Duration:** ca. 35 min
- **Started:** 2026-11-16T08:19:38Z
- **Completed:** 2026-11-16T08:55:00Z
- **Tasks:** 1 (TDD: RED, GREEN, Messung)
- **Files modified:** 3

## Accomplishments
- Gieriger Cue-Aufbau mit Rückgriff auf den letzten guten Schnitt (Satzende > Pause > Komma/Semikolon/Doppelpunkt > vor Konjunktion > Wortgrenze), Zeilenumbruch mit kleinstem Längenunterschied und Vorrang für Satzzeichen, überlange Wörter ungetrennt allein auf der Zeile.
- Harte Eigenschaften über 300 Fuzz-Fälle bewiesen (leere Liste, gleiche Zeitstempel, end < start, Überlappungen, "<", "&", "-->", Zeilenumbrüche, Tabs, NUL/BEL, Wörter bis 90 Zeichen): Textgleichheit, Zeilen- und Zeitgrenzen, Monotonie ohne Überlappung.
- Weiche Grenzen gezählt: NORMAL-Fixture (2,6 Wörter/s, Pausen 300 bis 1200 ms) ergibt 48 Cues mit Overruns(cps=0, short=0, gap=0, long_word=0, total=0); FAST-Fixture (4,5 Wörter/s, keine Pausen) ergibt 42 Cues mit cps-Anteil 0,9762 (41 von 42), Gate 0,98.
- Gegenprobe: alle NORMAL-Cues laufen als minimales SRT durch den unabhängigen Parser aus tests/subtitle_checkers (Anzahl, exakter Text, exakte Zeiten).

## Task Commits

1. **Task 1 RED: Cue-Eigenschaften EXP-02** - `89aebf8` (test)
2. **Task 1 GREEN: Untertitel-Cues aus Wortzeiten** - `87b66f0` (feat)
3. **Task 1 Messung: FAST-Schwelle auf den Messwert gesetzt** - `702c2d7` (test)

_REFACTOR entfiel: Implementierung bestand alle Gates ohne Nacharbeit._

## Files Created/Modified
- `backend/src/audio_video_search_backend/subtitles/__init__.py` - Paket für Untertitel-Entwürfe (04-07 Cues, 04-08 Writer)
- `backend/src/audio_video_search_backend/subtitles/cues.py` - Cue, Overruns, build_cues, count_overruns; Konstanten MAX_LINE/MAX_LINES/MIN_MS/MAX_MS/MAX_CPS/GAP_MS/PAUSE_CUT_MS
- `backend/tests/test_subtitles_cues.py` - Eigenschafts-, Literal- und Fixture-Tests, FAST_SPEECH_MAX_OVER_CPS_SHARE, SRT-Gegenprobe

## Messwerte (D-04-16)

| Fixture | Cues | cps über 20 | Standzeit unter 1 s | Abstand unter 80 ms | Langwort | Schwelle |
|---|---|---|---|---|---|---|
| NORMAL (2,6 Wörter/s, Pausen 300-1200 ms) | 48 | 0 | 0 | 0 | 0 | total == 0 |
| FAST (4,5 Wörter/s, keine Pausen) | 42 | 41 (Anteil 0,9762) | 0 | 0 | 0 | Anteil <= 0,98 |

## Decisions Made
- Rang-Gleichstand beim Cue-Schnitt wird nach Balance aufgelöst (kleinster Längenunterschied, dann spätester Schnitt). Das Research-Muster "letzter guter Schnitt" allein erzeugt vor Satzpausen Ein-Wort-Rest-Cues, die ihre Mindest-Standzeit physisch nicht erreichen können; Balance beseitigt sie, ohne Text oder Wortzeiten anzufassen.
- Satzende schließt den offenen Cue erst ab halber Kapazität (42 Zeichen), kurze Sätze verbinden sich davor mit dem Folgesatz (04-RESEARCH Pattern 5 Schritt 2d).
- cps-Rechnung über den sichtbaren Text (Zeilen mit Leerzeichen verbunden), identisch in Timing-Dehnung und Zählung.

## Deviations from Plan

**1. [Rule 2 - Gate-Wirksamkeit] FAST-Schwelle 0,98 statt 5-%-Aufrundung 1,00**
- **Found during:** Task 1, Messschritt
- **Issue:** Gemessener cps-Anteil 0,9762; die Planvorgabe "auf 5 % aufgerundet" ergäbe 1,00, eine Schwelle, die nie anschlagen kann (Anteil ist nie über 1). D-04-16 verlangt die Schwelle ausdrücklich "als Gate".
- **Fix:** Auf den nächsten 1-%-Schritt 0,98 aufgerundet; der Kommentar im Test nennt Messwert, Datum und Begründung. Das Gate schlägt an, sobald auch der letzte Cue (der einzige, der sich frei dehnen kann) die Rate reißt.
- **Files modified:** backend/tests/test_subtitles_cues.py
- **Verification:** Test grün mit 0,9762 <= 0,98; mit Schwelle -1 geprüft, dass die Assert-Meldung den Messwert zeigt.
- **Committed in:** 702c2d7

---

**Total deviations:** 1 (Rule 2, Gate-Wirksamkeit). Kein Scope-Creep.

## Issues Encountered
- RUF001 meldete die typografischen Anführungszeichen in der _TRAILING-Konstante; als bewusste Zeichen mit begründetem noqa markiert (echte schließende Anführungszeichen, keine Verwechsler).

## Hinweis an 04-08
- build_cues ersetzt Steuerzeichen-Läufe in Oberflächen durch je ein Leerzeichen; "-->", "<", "&" bleiben erhalten und müssen im Writer maskiert bzw. formatfest behandelt werden (T-04-20).
- Laufzeitmessung an 100 000 Wörtern steht laut Threat-Register (T-04-19) in Plan 04-08 an; der Aufbau ist linear mit Rückgriff nur auf den offenen Cue.

## Known Stubs
Keine.

## Threat Flags
Keine neuen Flächen über das Threat-Register des Plans hinaus; T-04-19 (Linearität) und T-04-20 (Steuerzeichen) sind umgesetzt bzw. getestet.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 04-08 (SRT/VTT-Writer) kann direkt auf Cue und build_cues aufsetzen; die unabhängigen Prüfer aus 04-04 sind mit expected_cues und exaktem Text bereits im Round-Trip-Test vorgeführt.

## Self-Check: PASSED

- Alle drei Quelldateien und die SUMMARY vorhanden.
- Commits 89aebf8 (test), 87b66f0 (feat), 702c2d7 (test) im Log.
- TDD-Gates: test-Commit vor feat-Commit, RED aus dem richtigen Grund (NotImplementedError), GREEN mit voller Suite grün.

---
*Phase: 04-suchqualit-t-und-export*
*Completed: 2026-11-16*
