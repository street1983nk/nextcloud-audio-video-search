---
phase: 04-suchqualit-t-und-export
plan: 19
subsystem: ci
tags: [ci, harp, export, untertitel, umlaute]
requires: [04-18]
provides: [CI-Beleg Push 6 für ee6bd68]
key-files:
  created: [.planning/phases/04-suchqualit-t-und-export/04-19-SUMMARY.md]
  modified: []
decisions:
  - "Owner-Entscheid 17.11.: Nur Umlaute und ß werden im Untertitel-Namen ersetzt; andere Nicht-ASCII-Zeichen (é, ñ, Kyrillisch, Emoji) bleiben UNVERÄNDERT. Die offene Frage aus 04-18-SUMMARY ist damit entschieden."
status: Task 1, 2 und 3 fertig (UAT Test 5 vom Owner am 17.11.2026 erneut bestanden)
---

# Phase 04 Plan 19: CI-Beleg für die Untertitel-Namen ohne Umlaute

Push 6 (phase-04 = ee6bd680fc1256f5bac427684d648bdcef31a107, 7d9b6c3..ee6bd68) ist in allen vier Workflows grün; D1 lädt in jedem Bein S7-Uebung.de.srt/.vtt/.txt, und das Download-Gate prüft die echten Dateien.

## Task 1: Push-Freigabe

Freigabe durch den Owner, Push durch den Orchestrator. Belege: `approvals/push-ee6bd68…`, `approvals/main-before-ee6bd68…`. Nur Push-Läufe, kein Dispatch (Owner).

## Task 2: CI-Beleg Push 6

| Workflow | Lauf | Ergebnis |
|---|---|---|
| PHP gates | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/44019004788 | success |
| Python gates | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/44019004814 | success |
| Deploy through HaRP | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/44019004773 | success (10 Jobs) |
| discovery-e2e | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/44019005157 | success (leak-control, discovery stable33) |

**PHP gates:** PHPUnit `OK (933 tests, 11570 assertions)`; php -l und composer validate/audit grün. Neue Fälle aus 04-18 darin enthalten:
- ExportControllerTest, DataProvider `downloadNames()`: 'several dots', 'control character stays', 'decomposed umlaut', 'decomposed lowercase', 'all umlauts', 'capital sharp s', 'other letters stay'
- ExportControllerTest: `testTheDownloadNameSpellsOutTheUmlautAndTheTxtHeadKeepsTheRealName`, `testTheSidecarSpellsOutTheUmlautAndASecondCallIsThe409OnTheSameName`, `testTheLimitOf255BytesIsCheckedOnTheSpelledOutName`, `testACapitalSharpSNameFitsOnlyBecauseItIsSpelledOut`
- PlayControllerTest: `testTheSidecarNameOnThePageSpellsOutTheUmlaut`

**HaRP, alle sechs deploy-harp-Beine** (stable33/34/35 je ubuntu-24.04 und ubuntu-24.04-arm) plus drei upgrade-Beine success:

| Bein | Phase-4-Playwright | D1/X1/X6/E1/E2 | Parser-Schritt (Umlaut-Gate) | Container-Routen-Negativschritt |
|---|---|---|---|---|
| stable33 amd64 | 50 passed | PASS | 16 passed | grün |
| stable33 arm64 | 50 passed | PASS | 16 passed | grün |
| stable34 amd64 | 50 passed | PASS | 16 passed | grün |
| stable34 arm64 | 50 passed | PASS | 16 passed | grün |
| stable35 amd64 | 50 passed | PASS | 16 passed | grün |
| stable35 arm64 | 50 passed | PASS | 16 passed | grün |

- Je Bein 13 grüne Einträge für X1 (Video, alle Breiten/Sprachen), X6, D1, E1 und E2, E2 (Hochkontrast, Französisch); keine Fehlschläge. X1/X6/E1/E2 nutzen `S7_EXPORT_BASE = 'S7-Uebung'` (`ci/playwright/helpers.ts:719`), also `S7-Uebung.de.vtt`.
- Parser-Schritt "The parsers on the real downloads of phase 4": `uv run pytest tests/test_downloaded_subtitles.py -q -rs` auf `AVS_DOWNLOADS_DIR` = `16 passed` in jedem Bein, darin die Umlaut-, ß- und U+0308-Prüfung.
- Artefakt `phase4-screens-stable35-ubuntu-24.04` geladen, Downloads darin:
  - `S7-Uebung.de.srt`, `S7-Uebung.de.txt`, `S7-Uebung.de.vtt`
  - `s7-ziffer.de.srt`, `s7-ziffer.de.txt`, `s7-ziffer.de.vtt`
- main unverändert: `git ls-remote origin refs/heads/main` gleich `approvals/main-before-ee6bd68…` (cmp ohne Unterschied).
- ghcr: Für ee6bd68 gibt es keine `ghcr-before`-Datei; der ghcr-Vergleich wurde in diesem Beobachterlauf nicht gemacht.

## Task 3: UAT Test 5 mit dem Owner

Erledigt 17.11.2026: Der Owner hat Test 5 nach dem Gap-Schluss erneut geprüft und bestätigt, dass die Dateinamen keine Umlaute mehr tragen (`S7-Uebung.de.srt`, `.vtt`, `.txt` aus Lauf 44019004773, CI-Beleg Push 6 auf ee6bd68). `04-UAT.md` steht damit auf `status: complete`, 14 von 14 bestanden, Gap Test 5 `status: resolved` (Commit 18bc093).

## Deviations from Plan

- `discovery-e2e.yml -f legs=all` nicht per Dispatch gestartet: Owner-Vorgabe "nur Push-Läufe". Der Push-Lauf von discovery-e2e ist grün.

## Self-Check: PASSED
