---
phase: 04-suchqualit-t-und-export
plan: 18
subsystem: php/export
tags: [EXP-01, EXP-03, gap-closure, uat-04-test-5, export, sidecar, umlaut]
requires:
  - "04-10, 04-12: ExportController::downloadName, sidecar(), PageController sidecarName"
  - "04-14, 04-17: test_downloaded_subtitles.py, Playwright D1, X1, X6, E1/E2"
provides:
  - "ExportController::downloadName() schreibt ä, ö, ü, Ä, Ö, Ü, ß, U+1E9E aus (ae, oe, ue, Ae, Oe, Ue, ss, SS), auch zerlegt (Buchstabe + U+0308) und ohne intl"
  - "Download (SRT/VTT/TXT), Nebendatei und Hinweissatz/Banner der Abspielseite nennen S7-Uebung.de.*"
  - "Python-Gate: Umlaut, ß, U+1E9E und jedes U+0308 im Namen echter Downloads scheitern"
  - "helpers.ts: S7_EXPORT_BASE = 'S7-Uebung' (Literal), s7ExportName()"
affects: [04-19]
tech-stack:
  added: []
  patterns:
    - "Umlaut-Ersatz per strtr() mit fester Tabelle (komponiert + zerlegt), längster Treffer gewinnt"
    - "E2E-Erwartung als Literal, nicht aus dem Aufnahmenamen abgeleitet (Gegenprobe unabhängig vom Muster der Umsetzung)"
key-files:
  created: []
  modified:
    - php/lib/Controller/ExportController.php
    - php/tests/Unit/ExportControllerTest.php
    - php/tests/Unit/PlayControllerTest.php
    - ci/playwright/helpers.ts
    - ci/playwright/export.spec.ts
    - ci/playwright/sidecar.spec.ts
    - backend/tests/test_downloaded_subtitles.py
    - .planning/phases/04-suchqualit-t-und-export/04-UI-SPEC.md
    - README.md
    - README.en.md
    - README.fr.md
    - CHANGELOG.md
decisions:
  - "Nur Umlaute und ß werden ersetzt; é, ñ, Kyrillisch, Emoji bleiben unverändert (Owner verlangte nur Umlaute, keine eigenmächtige ASCII-Erzwingung; Rückfrage offen)"
  - "Die TXT-Kopfzeile nennt weiter den echten Namen der Aufnahme mit Umlaut (Inhalt, kein Dateiname)"
  - "Das Download-Gate lehnt jedes U+0308 im Namen ab, auch NFD-ë/-ï, die der Export nicht ersetzt (bewusst streng: echte Downloads kommen aus NFC-Namen)"
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-17
  tasks: 2
  files: 12
---

# Phase 4 Plan 18: Untertitel-Dateinamen ohne Umlaute Summary

Gap aus UAT 04 Test 5 geschlossen: `ExportController::downloadName()` ersetzt Umlaute und ß per `strtr()` (komponiert und zerlegt, auch ohne intl), damit heißen Download, Nebendatei und Hinweissatz der Abspielseite für `S7-Übung.webm` jetzt `S7-Uebung.de.srt|vtt|txt`; Playwright, Python-Download-Gate, UI-SPEC, READMEs DE/EN/FR und CHANGELOG sind nachgezogen.

## Commits

| Task | Commit | Inhalt |
|------|--------|--------|
| 1 | 5f1d608 | `fix(04-18): Untertitel-Dateinamen ohne Umlaute (ae, oe, ue, ss)`: ExportController, ExportControllerTest, PlayControllerTest |
| 2 | e4b2d90 | `fix(04-18): E2E, Download-Gate und Doku auf Uebung-Namen`: helpers.ts, export.spec.ts, sidecar.spec.ts, test_downloaded_subtitles.py, 04-UI-SPEC, README DE/EN/FR, CHANGELOG |

## Was geändert ist

- **ExportController:** private Konstante `UMLAUTS` (8 komponierte Zeichen, U+1E9E nur als Escape `"\u{1E9E}"`, plus 6 zerlegte Folgen `"a\u{0308}"` usw.); `downloadName()` wendet `strtr()` direkt nach `composed()` an. `attachmentName()`, `composed()`, TXT-Kopf, 255-Byte-Prüfungen und Kollisionslogik unverändert; PageController unverändert (ruft `downloadName()`).
- **PHPUnit (läuft nur in CI, PHP lokal nicht vorhanden):**
  - DataProvider `downloadNames()`: 'several dots' -> `Uebung.final.fr.vtt`, 'decomposed umlaut' -> `Uebung.de.srt` (bisher `Übung.de.srt`, sonst CI rot), neu 'decomposed lowercase', 'all umlauts', 'capital sharp s', 'control character stays', 'other letters stay' (é, ñ, Kyrillisch und U+1F3A4 als PHP-Escape im Test, Eingabe und Erwartung).
  - `testTheDownloadNameSpellsOutTheUmlautAndTheTxtHeadKeepsTheRealName`: alle drei Formate, Content-Disposition enthält `S7-Uebung.de.<fmt>`, kein `Übung`, kein `%C3%9C`; TXT beginnt mit `S7-Übung.webm\n`.
  - `testTheSidecarSpellsOutTheUmlautAndASecondCallIsThe409OnTheSameName`: 201 `Uebung.de.vtt`, einziger Schlüssel, zweiter Aufruf 409 mit demselben Namen, sha256 gleich, ein newFile-Aufruf.
  - `testTheLimitOf255BytesIsCheckedOnTheSpelledOutName`: 124 x ß + `.mp4` -> 201, Name genau 255 Byte (strlen geprüft); 124 x ß + `x.mp4` -> 256 Byte, 400 `name_too_long`, nichts geschrieben. ß -> ss ist byte-neutral, dieser Fall belegt also nur die Grenze 255/256.
  - `testACapitalSharpSNameFitsOnlyBecauseItIsSpelledOut`: 83 x U+1E9E + `.webm` (unersetzt 256 Byte) -> 201 mit `SS` x 83 + `.de.vtt` (173 Byte). Dieser Fall belegt, dass die Längenprüfung auf dem ersetzten Namen sitzt.
  - PlayControllerTest: `S7-Übung.webm` -> sidecarName `S7-Uebung.de.vtt`; 125 x ä bleibt `''` (Kommentar ergänzt: 250 + 7 = 257).
- **Playwright:** `S7_EXPORT_BASE = 'S7-Uebung'` als Literal, `s7ExportName()`; X1, X6, E1/E2 nutzen es; D1 mit Feld `exportBase`, Erwartung `${exportBase}.de.${format}` und `not.toMatch(/[äöüÄÖÜßẞ̈]/u)`, Titel "Name mit Sprache, Umlaut ersetzt" (@phase4 bleibt). `S7_VIDEO_NAME` bleibt (Aufnahme heißt weiter `S7-Übung.webm`, TXT-Zeile 1 in D1).
- **Python-Gate:** `UMLAUT`-Muster in `by_format()`, Docstring nennt die Strenge bei U+0308; `_complete()` jetzt `Sitzung Maerz.de.txt`; 5 neue Selbsttests (Umlaut, NFD, ß scheitern; `Café.de.srt` besteht; Positivkontrolle `S7-Uebung.de.*` besteht).

## Gates (lokal)

- ruff check + format --check, pyright (latest, 0 Fehler), vulture: grün
- volle pytest-Suite: **2367 passed**, 18 skipped, 4 xfailed (vorher 2362, +5 Selbsttests), darin test_public_texts.py und test_php_gates.py
- tsc über Scratchpad-tsconfig grün, Kontroll-tsconfig mit absichtlichem Fehler scheitert wie erwartet
- `npx playwright test --list --grep @phase4`: 207 Tests in 3 Dateien
- PHP: kein lokales php, Syntax und PHPUnit prüft CI (php.yml) mit Plan 04-19

## Was CI belegen muss (Plan 04-19)

- php.yml: ExportControllerTest (DataProvider, Download-Header über echtes DataDownloadResponse, Nebendatei, Grenze 255/256, 83 x U+1E9E) und PlayControllerTest grün
- deploy-harp.yml @phase4: D1 lädt `S7-Uebung.de.srt|vtt|txt` herunter, X1/X6/E1/E2 nennen `S7-Uebung.de.vtt`, der Parser-Schritt mit AVS_DOWNLOADS_DIR besteht das Umlaut-Gate

## Deviations from Plan

- **Testeingabe 'other letters stay':** é, ñ und die kyrillischen Buchstaben stehen als PHP-Escapes (`\u{00E9}` usw.) statt als Zeichen, damit die Literale sicher NFC sind; Inhalt gleich dem Plan.
- **Zusätzlicher DataProvider-Fall 'control character stays'** (Plan nannte `"Sitz\tung.webm"` als "wie bisher"; jetzt explizit im Provider).
- **Plantext korrigiert** (Checker-Warnung): Klammer beim Grenzfall 124 x ß sagt jetzt, dass ß -> ss byte-neutral ist und nur die Grenze 255/256 belegt; die Prüfung auf dem ersetzten Namen belegt der 83 x U+1E9E-Fall. Test-Kommentare entsprechend formuliert.
- **Gate-Werkzeug:** `npx tsc` gibt es in ci/playwright nicht (kein typescript-Paket); tsc lief über das typescript-Paket aus einem anderen lokalen Projekt mit der Scratchpad-tsconfig, inklusive Kontrolllauf.

## Offene Owner-Rückfragen (nicht umgesetzt)

1. Sollen auch andere Nicht-ASCII-Zeichen im Untertitel-Namen ersetzt werden (é, ñ, Kyrillisch, Emoji)? Heute bleiben sie unverändert.
2. Zur Kenntnis: Die TXT-Kopfzeile nennt weiter den echten Namen der Aufnahme mit Umlaut (`S7-Übung.webm`), weil sie Inhalt ist und kein Dateiname.

## Threat Flags

Keine neue Angriffsfläche. T-04-57 (Kollision auf dem ersetzten Namen, 409 und byte-gleich) und T-04-58 (Länge nach Ersatz, 255/256 und 83 x U+1E9E) mit PHPUnit-Fällen gemildert; T-04-59 unverändert (attachmentName).

## Known Stubs

Keine.

## Self-Check: PASSED

- Dateien vorhanden, Commits 5f1d608 und e4b2d90 im Log, Autor street1983nk <k.cherif@outlook.de>, keine Session-/Co-Authored-/closes-Zeilen; test_model_download.py und .planning/debug/ unberührt; nichts gepusht.
