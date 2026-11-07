---
phase: 02-erfassung-aller-dateien
plan: 02
subsystem: store
tags: [schema-v2, migration, file-ref, disc-01, disc-05]
requires: []
provides:
  - "SCHEMA_VERSION 2; store/migrate.py: migrate_v1_to_v2(connection), stored_version(connection), V1_TO_V2_STEPS"
  - "file_ref v2: file_id, media_id, storage_id INTEGER, prefilter_key, reader_uid, etag, size, mtime, state, stage, reason, attempts, next_try_at, proved_at, vanished_since, updated_at; Indizes file_ref_media, file_ref_storage, file_ref_prefilter, file_ref_stage"
  - "media + head_sha256, orphaned_at"
  - "repo.STATES, STAGES, STATE_REASONS (geschlossen), FileRef-Dataclass, Store.file_ref(file_id)"
  - "Store.upsert_file_ref(file_id, media_id, *, storage_id:int, etag, size, mtime, state, stage, reason, prefilter_key=None, reader_uid=None, attempts=0, next_try_at=None, proved_at=None, vanished_since=None)"
  - "file_ids_for_media nur state active oder sample"
affects: [02-05, 02-08, 02-09, 02-10, 02-13, 02-15, 02-20, 02-21]
tech-stack:
  added: []
  patterns:
    - "Migration als Schrittliste in einer BEGIN-IMMEDIATE-Transaktion, Test spritzt einen Fehler nach dem DROP ein"
    - "Store.open: Version lesen, v1 migrieren, unbekannte Version vor jedem Schreiben ablehnen, dann Schema-Skript"
    - "Frisch angelegte und migrierte Datei werden Spalte für Spalte verglichen"
key-files:
  created:
    - backend/src/audio_video_search_backend/store/migrate.py
    - backend/tests/test_store_migration_v2.py
  modified:
    - backend/src/audio_video_search_backend/store/schema.sql
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/api/sample.py
    - backend/tests/test_store_schema.py
    - backend/tests/test_api_routes.py
    - backend/tests/test_index_open.py
    - backend/tests/test_index_publish.py
    - backend/tests/test_handshake.py
    - backend/tests/test_main.py
    - backend/tests/test_workflows.py
    - .github/workflows/deploy-harp.yml
decisions:
  - "Ein Leser (read_only) migriert nie; trifft er v1, meldet er unsupported store schema version 1"
  - "Nicht numerische alte storage_id-Texte werden 0 (in 0.1.0 gibt es nur '')"
  - "remove_sample löscht nur Zeilen mit state sample; Verweise der Erfassung bleiben"
metrics:
  duration: "ca. 40 min"
  completed: 2026-11-07
  tasks: 2
  files: 13
---

# Phase 2 Plan 02: Schema v2 und verlustfreie Migration Summary

state.db hat jetzt Schema v2: file_ref ist der Arbeitsvorrat mit numerischer storage_id, Vorfilter-Schlüssel, Leser, Stufe, Grund, Versuchen, Lesebeweis-Zeit und vanished_since, media trägt head_sha256 und orphaned_at; eine v1-Datei wird beim Start in einer Transaktion gehoben, und Proben überschreiben nie einen echten Verweis.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Schema v2 und Migration als Code | 5f7f69c | schema.sql, migrate.py, repo.py, test_store_migration_v2.py, test_store_schema.py u. a. |
| 2 | Probe überschreibt keinen echten Verweis | 69954e3 | api/sample.py, repo.py, test_api_routes.py, test_store_schema.py |

## Prüfungen

- test_store_migration_v2.py 25 grün: v1 mit Probe, Transkript, Wörtern, Korrektur und Outbox wird v2 (Probe storage_id 0, stage keyed; alle Zeilen der übrigen Tabellen gleich), Fehler nach dem DROP lässt die Datei byte-gleich im Dump, zweites Öffnen ist No-op, Version 3 und ein Leser auf v1 werden abgewiesen, frisch und migriert gleiche Spalten und Indizes, geschlossene Listen, Treffer nur active/sample.
- Volle Python-Gates seriell grün: ruff, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 439 grün.
- Positivkontrolle für den neuen remove_sample-Schutz: ohne Schutz schlägt der Test an, mit Schutz grün.
- RED vor GREEN lokal belegt (5 der 6 neuen /sample-Tests rot vor der Änderung); rote Zwischenstände nicht committet, weil die Planregel "vor jedem Commit lokal grün" gilt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Upgrade-Job prüfte schemaVersion 1**
- **Found during:** Task 1
- **Issue:** deploy-harp.yml (Job upgrade) verlangt `.schemaVersion == 1` vor und nach dem Update; mit Schema v2 wäre der Job beim Push in Plan 11 rot.
- **Fix:** beide jq-Prüfungen auf 2, Lifecycle-Gate in test_workflows.py ebenso. Den echten Upgrade-Beweis 0.1.0 nach 0.2.0 mit Vorher-Kontrolle baut Plan 21.
- **Commit:** 5f7f69c

**2. [Rule 1 - Bug] remove_sample hätte einen echten Verweis gelöscht**
- **Found during:** Task 2
- **Issue:** Probe auf eine erfasste Datei, dann `occ :sample --remove`: remove_sample löschte die file_ref-Zeile unabhängig vom Zustand.
- **Fix:** nur Zeilen mit state sample werden gelöscht; Test mit Positivkontrolle.
- **Commit:** 69954e3

**3. Testort**
- Die /sample-Verhaltenstests stehen in test_api_routes.py (echte Route mit gefälschtem Gateway) statt in test_store_schema.py; test_store_schema.py trägt den remove_sample-Fall.

## Known Stubs

Keine. Die Spalten prefilter_key, reader_uid, attempts, next_try_at, proved_at, vanished_since, head_sha256 und orphaned_at schreiben erst die Pläne 05, 08, 13, 15 und 20.

## Self-Check: PASSED

- FOUND: backend/src/audio_video_search_backend/store/migrate.py, backend/tests/test_store_migration_v2.py
- FOUND: 5f7f69c, 69954e3
