---
phase: 03-vorschau-transkripte-in-der-suche
plan: 11
subsystem: claim-vertrag, einstellungen
tags: [nc_queue, origin, settings, l10n, tdd]
requires: ["03-01", "03-03", "03-04"]
provides:
  - "nc_queue: ORIGINS, type Origin, ClaimItem.origin (zehn Schlüssel), to_intake reicht origin weiter"
  - "settings: MAX_DURATION_HOURS, DEFAULT_MAX_DURATION_HOURS (12), MAX_DURATION_CAP_HOURS (24), read_max_duration_hours(values)"
  - "test_php_gates Regel 17: QueueMapper::ORIGINS gegen nc_queue.ORIGINS und repo.ORIGINS"
affects: [03-15, 03-16b]
tech-stack:
  added: []
  patterns:
    - "Gate nimmt die Container-Listen als Parameter, damit eine abweichende Liste gegen den unveränderten PHP-Baum feuern kann"
key-files:
  created: []
  modified:
    - backend/src/audio_video_search_backend/nc_queue.py
    - backend/src/audio_video_search_backend/settings.py
    - backend/l10n/de.json
    - backend/l10n/de.js
    - backend/l10n/en.json
    - backend/l10n/en.js
    - backend/l10n/fr.json
    - backend/l10n/fr.js
    - backend/tests/test_intake.py
    - backend/tests/test_php_gates.py
    - backend/tests/test_settings.py
    - backend/tests/test_main.py
decisions:
  - "Unbekannte oder fehlende Herkunft verwirft das ganze Claim-Band, wie heute jeder Eintrag außerhalb des Vertrags (festgehalten, nicht geändert)"
  - "read_max_duration_hours nimmt nur ASCII-Ziffern; leer, 0, negativ, Bruch, Wort oder fremde Ziffern ergeben 12; mehr Stellen als der Deckel oder über 24 ergeben 24"
  - "worker/intake.py unverändert: dort werden keine Felder einzeln weitergereicht oder geloggt"
metrics:
  duration: "ca. 40 min"
  completed: 2026-11-14
---

# Phase 3 Plan 11: Herkunft im Claim und Höchstdauer statt Größengrenze Summary

Container-Hälfte des Herkunfts-Vertrags (ClaimItem.origin event/crawl bis in file_ref, Gate gegen QueueMapper::ORIGINS) und die Admin-Einstellung "Longest recording in hours" (Standard 12, Deckel 24) anstelle von "Largest file in MB".

## Vorab-Beleg (Task 2)

`grep -rIn "max_file_size\|MAX_FILE_SIZE\|Largest file" .` (ohne .venv/.git/.planning) vor dem Umbau: nur `settings.py`, `backend/l10n/*` und die Tests `test_settings.py`, `test_main.py`. `capture.py` nutzt allein `MAX_CAPTURE_BYTES` (64 GiB). Keine Rückstell-Migration für alte Größen-Verweise nötig. Nachher liefert `grep -rn "max_file_size" backend/src backend/l10n` nichts.

## Commits

| Commit | Betreff |
|--------|---------|
| fd4fc0f | test(03-11): Herkunft im Claim-Vertrag als Vertrag |
| 490c5e5 | feat(03-11): Herkunft im Claim-Vertrag |
| 4982320 | test(03-11): Höchstdauer als Admin-Einstellung als Vertrag |
| a90f07a | feat(03-11): Höchstdauer als Admin-Einstellung statt Größengrenze |
| 096da64 | test(03-11): Schlüssel und Standard der Höchstdauer gleich in Einstellung und Store |

## Prüfungen

- RED Task 1: 15 Fehlschläge in test_intake.py, test_php_gates.py bricht beim Sammeln (nc_queue.ORIGINS fehlt). GREEN: 163 bestanden (intake, php_gates, preview_seed).
- RED Task 2: 19 Fehlschläge in test_settings.py. GREEN: 79 bestanden (settings, trilingual, public_texts, main).
- Volle Suite nach Task 2: ruff check, ruff format --check (100 Dateien), pyright 0 Fehler, vulture grün, pytest 1559 bestanden. Nach dem letzten Testcommit test_settings.py 26 bestanden, ruff/pyright/vulture grün.
- Positivkontrollen:
  - Regel 17: veränderte PHP-Kopie (`['event']`, `[event, 'urgent']`) liefert je drei Befunde; abweichende Container-Listen (`push` zusätzlich, `crawl` fehlt) feuern gegen den unveränderten PHP-Baum.
  - origin in file_ref: im RED schlug der Fall `event` fehl (Standard `crawl` des IntakeItem), also prüft der Test die Weitergabe.
  - read_max_duration_hours, eigenes Mutationsskript (nicht das Testmuster): ohne ASCII-Prüfung wird `٥` zu 5, ohne Langzahl-Deckel `200` zu 200, ohne Null-Prüfung ValueError; der reine min-Deckel wird vom pytest-Fall `25` gefangen.
  - Texte: Skript liest die Tabelle aus 03-01-SUMMARY.md und vergleicht mit den Katalogen und settings.py: 0 Abweichungen; Kopie mit "Laengere" und Gedankenstrich ergibt 3 Befunde.
- `.js`-Zwillinge mit `scripts/l10n_js.py` erzeugt; php/l10n blieb unverändert; Dateien ohne CR.

## Deviations from Plan

1. **[Rule 3] test_main.py angepasst** (nicht in files_modified): die gestellte Antwort von `settings.read` nannte noch `max_file_size_mb`; auf `max_duration_hours: "12"` umgestellt, damit kein Altschlüssel in Tests überlebt. Commit 4982320.
2. **file_ref.origin im Test per SQL gelesen**: `FileRef` (repo.py) hat kein Feld origin; repo.py ist nicht Teil des Plans, deshalb liest der Test `SELECT origin FROM file_ref` wie test_preview_seed.py.
3. **Zusätzlicher Testcommit 096da64**: hält `settings.MAX_DURATION_HOURS == repo.MAX_DURATION_KEY` und gleiche Standardwerte fest (Store aus 03-09 kennt dieselbe Grenze).
4. Hinweis Verify-Befehl: `scripts/l10n_js.py --help` kennt kein `--help` und schreibt dabei alle `.js`-Zwillinge beider Wurzeln neu (hier ohne Folgen, da sie stimmten).

## Offene Punkte

- `read_max_duration_hours` wird noch nirgends im Worker gelesen; das verbindet Plan 03-15 (Store.set_max_duration_hours, requeue_too_long). `Store.max_duration_hours` selbst kennt keinen Deckel 24; der Deckel greift nur über den Einstellungsleser.
- PHP-Seite unverändert, phpunit nicht lokal gelaufen (kein PHP), nicht nötig für diesen Plan.

## Self-Check: PASSED

Alle fünf Commits vorhanden (`git log`), alle geänderten Dateien vorhanden.
