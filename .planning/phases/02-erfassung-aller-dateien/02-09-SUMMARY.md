---
phase: 02-erfassung-aller-dateien
plan: 09
subsystem: backend-zaehlung
tags: [zaehlung, coverage, workstock, admin-routen, disc-05, d-02-06]
requires: [02-02, 02-08]
provides:
  - "store/coverage.py (nur lesend): coverage(conn, now) -> Coverage(contents, transcribed, files, by_state, by_stage, due_work).as_wire(), workstock(conn, state, after, limit) -> WorkstockPage(files, next).as_wire(), WORKSTOCK_MAX_LIMIT 1000"
  - "Store.reading_connection() für die lesenden Abfragen"
  - "GET /coverage -> {contents, transcribed, files, byState, byStage, dueWork}"
  - "GET /workstock?state=&after=&limit= -> {files: [{fileId, mediaId, storageId, state, stage, reason}], next}"
  - "backend/appinfo/info.xml: ^/workstock$ und ^/coverage$, GET, ADMIN"
  - "pytest-Marker timing"
affects: [02-10, 02-04, 02-11, 02-17, 02-22]
tech-stack:
  added: []
  patterns:
    - "Zähler und Nenner aus derselben Menge aktiver Verweise; Zähler Teilmenge per Konstruktion"
    - "byState/byStage nennen jeden Code der geschlossenen Liste (0, wenn leer), nie einen fremden"
    - "Alle Zahlen in einer Lesetransaktion"
    - "Eigenschaftstest gegen ein Python-Modell, das die Zeilen selbst abläuft (nicht die SQL der Umsetzung)"
key-files:
  created:
    - backend/src/audio_video_search_backend/store/coverage.py
    - backend/src/audio_video_search_backend/api/coverage.py
    - backend/src/audio_video_search_backend/api/workstock.py
    - backend/tests/test_coverage_count.py
  modified:
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/api/__init__.py
    - backend/appinfo/info.xml
    - backend/pyproject.toml
    - backend/tests/test_api_routes.py
    - backend/tests/test_store_metadata.py
decisions:
  - "dueWork zählt nur Verweise in state active oder unreadable (die die Erfassung lädt); ein pending Verweis auf vanished/trashed/sample würde die Abnahme sonst ewig warten lassen"
  - "transcribed verlangt zusätzlich media.orphaned_at IS NULL"
  - "Geschwister für den Schlüssel nur aktive mit media_id, das erste nach file_id"
  - "workstock: next = letzte file_id einer vollen Seite, sonst null; limit Standard 1000"
metrics:
  duration: "ca. 40 min"
  completed: 2026-11-07
  tasks: 2
  files: 10
---

# Phase 2 Plan 09: Zählung nach Inhalten, /workstock, /coverage Summary

Die Zahl "X von Y Inhalten (N Dateien)" kommt jetzt aus einem nur lesenden Modul, in dem Zähler und Nenner dieselbe Menge aktiver Verweise zählen, und occ (Plan 10) sowie die Abnahme lesen Arbeitsvorrat und Zahlen über zwei ADMIN-Routen mit fester Feldmenge.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Zählung als Eigenschaftstest | cbbf89e | store/coverage.py, store/repo.py, test_coverage_count.py, pyproject.toml |
| 2 | ADMIN-Routen /workstock und /coverage | a9b7b2d | api/workstock.py, api/coverage.py, api/__init__.py, info.xml, test_api_routes.py, test_store_metadata.py |

Zusätzlich: e2ebf56 `docs(02)` D-02-14 (SeaweedFS statt MinIO, Owner-Bestätigung 07.11.) in 02-CONTEXT.md.

## Prüfungen

- test_coverage_count.py 19 grün: 500 Zufallsfälle (Seed 20261107) gegen das Python-Modell, transcribed <= contents <= files; keyed Kopie plus pending Geschwister = ein Inhalt; zwei pending mit einem Vorfilter = ein Inhalt; vanished, trashed, unreadable, sample zählen nicht; unreadable Kopie wird nicht über das keyed Geschwister gezählt, und ein unreadable keyed Geschwister schlüsselt keine pending Kopie; media mit current, aber nur vanished Verweis oder orphaned_at nicht transcribed; dueWork-Fälle (pending ohne Zeit ja, locked in der Zukunft nein, failed mit Wiederholung nein, fälliges probing ja, fetching ja, vanished nein); Ende-zu-Ende mit der Erfassung aus Plan 08 (eine Kopie keyed, Geschwister 403): contents 1, files 1, unreadable 1, dueWork 0; workstock-Seiten und Grenzwerte; 140.000 Verweise unter 2 s (Marker timing).
- test_api_routes.py: feste Schlüssel beider Antworten, Seiten, state-Filter, 422 für limit 0/1001/"x", fremden oder großgeschriebenen state, after -1; 401 ohne Signatur.
- test_store_metadata.py: beide Routen GET/ADMIN; neues Gate, dass jede Container-Route mit Verb in info.xml steht (Positivkontrolle: umbenannte Route in info.xml -> 2 rot).
- Positivkontrollen per Mutation an coverage.py (danach zurückgesetzt): Geschwister ohne state-Bedingung -> 1 rot; Zähler ohne aktiven Verweis -> 7 rot; ohne orphaned_at-Bedingung -> 2 rot; dueWork ohne state-Bedingung -> 1 rot.
- Volle Python-Gates seriell grün: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 605 grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1] dueWork nur für ladbare Verweise**
- **Found during:** Task 1
- **Issue:** Mit der wörtlichen Definition zählte ein pending Verweis auf einem vanished oder trashed Zustand ewig als fällige Arbeit, obwohl die Erfassung ihn nie lädt; compare.sh wait hätte nie geendet.
- **Fix:** zusätzlich `state IN ('active', 'unreadable')`, genau die Auswahl von Store.next_capture. Test.
- **Commit:** cbbf89e

**2. [Rule 2] Gate Route gegen info.xml**
- HaRP lässt nur deklarierte Routen durch; ein Test prüft jetzt jede Route des Routers mit Verb gegen info.xml. Commit a9b7b2d.

**3. Store.reading_connection()**
- coverage.py braucht die Verbindung des Stores, ohne dass repo.py das Modul importiert (Zyklus); eine dokumentierte Lesemethode statt Zugriff auf `_conn`.

**4. pytest-Marker timing in pyproject.toml** (nicht in der Dateiliste), damit der markierte Hinweis-Test keine Warnung für einen unbekannten Marker erzeugt.

## Known Stubs

- skippedStorages fehlt in den Zahlen (Plan 12, liegt in PHP).
- Die Admin-Oberfläche liest die Zahlen erst in Phase 9 (D-02-06).

## Threat Flags

Keine neue Oberfläche über das Threat-Register hinaus (T-02-30: ADMIN, feste Feldmenge, nur IDs und Zahlen; T-02-31: Eigenschaftstest Zähler Teilmenge).

## Self-Check: PASSED

- FOUND: store/coverage.py, api/coverage.py, api/workstock.py, test_coverage_count.py
- FOUND: cbbf89e, a9b7b2d, e2ebf56
