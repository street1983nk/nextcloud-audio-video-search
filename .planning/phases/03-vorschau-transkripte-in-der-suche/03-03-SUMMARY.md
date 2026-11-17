---
phase: 03-vorschau-transkripte-in-der-suche
plan: 03
subsystem: store
tags: [sqlite, schema-v3, migration, preview_job, origin, tdd]
requires: []
provides:
  - "state.db Schema 3: Tabelle preview_job (eine Zeile je media_id) mit Index preview_job_order, Spalte file_ref.origin"
  - "store/migrate.py: migrate_v2_to_v3, V2_TO_V3_STEPS, PREVIEW_JOB_V3, PREVIEW_JOB_ORDER_V3, FILE_REF_ORIGIN_V3"
  - "repo.ORIGINS, IntakeItem.origin (Standard crawl), event gewinnt in apply_intake"
  - "repo._SEED_PREVIEW_JOB in mark_keyed und attach_by_proof, im selben Commit wie das Schlüsseln"
affects: [03-04, 03-05, 03-06, 03-08, 03-19]
tech-stack:
  added: []
  patterns:
    - "Migration als Konstanten-Schritte in einer Transaktion, Rollback-Test mit eingeschobenem Fehler"
    - "eingefrorenes Vorgänger-Schema als Teststring, spaltenweiser Vergleich frisch gegen migriert (table_info, index_xinfo)"
    - "UPSERT ON CONFLICT(media_id) DO UPDATE ... WHERE state IN ('queued','waiting')"
key-files:
  created:
    - backend/tests/test_store_migration_v3.py
    - backend/tests/test_preview_seed.py
  modified:
    - backend/src/audio_video_search_backend/store/schema.sql
    - backend/src/audio_video_search_backend/store/migrate.py
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/tests/test_store_migration_v2.py
    - backend/tests/test_store_schema.py
    - backend/tests/test_handshake.py
    - backend/tests/test_main.py
    - backend/tests/test_index_open.py
decisions:
  - "file_ref.origin ist die letzte Spalte, weil ALTER TABLE sie hinten anhängt; nur so gleicht die migrierte Datei der frischen spaltenweise"
  - "Saat als INSERT ... SELECT aus file_ref JOIN media mit der Bedingung active und keyed in SQL, statt VALUES mit Python-Werten"
  - "Ein Job wird beim Vergessen des Inhalts und beim Entfernen der letzten Probe vor der media-Zeile gelöscht (Fremdschlüssel)"
  - "running wird wie complete und skipped von einer weiteren Kopie nicht verändert; nur queued und waiting nehmen Herkunft und mtime auf"
metrics:
  duration: "ca. 75 min"
  completed: 2026-11-14
  tasks: 2
  files: 10
---

# Phase 3 Plan 03: Store v3 mit Vorschau-Job und Herkunft Summary

state.db Schema 3: Tabelle `preview_job` je Inhalt mit geschlossenen Zuständen und Reihenfolge-Index, `file_ref.origin` (event gewinnt immer gegen crawl), Migration v2 nach v3 in einer Transaktion mit Saat für den Bestand, und ein Vorschau-Job, der im selben Commit wie das Schlüsseln eines Verweises entsteht.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 RED | 0450426 | test(03-03): Schema v3 und Migration v2 nach v3 als Vertrag |
| 1 GREEN | 8336c61 | feat(03-03): Schema v3 mit preview_job und file_ref.origin |
| 2 RED | 879fd68 | test(03-03): Herkunft im Intake und Vorschau-Job beim Erfassen als Vertrag |
| 2 GREEN | 5cc8e7c | feat(03-03): Herkunft im Intake und Vorschau-Job beim Erfassen |
| 2 Nachtrag | 49044b9 | test(03-03): Bedingung der Saat direkt an der Anweisung geprüft |

Alle Commits lokal, Autor und Committer street1983nk <k.cherif@outlook.de>, nichts gepusht.

## Was gebaut wurde

- **schema.sql v3:** `preview_job` (19 Spalten laut Plan inkl. `second_pass`), CHECK für state (queued, running, waiting, complete, skipped), origin (event, crawl), `next_start_ms >= 0`, `chunks_done >= 0`; `reason` ohne CHECK. Index `preview_job_order` wörtlich aus RESEARCH. `file_ref.origin TEXT NOT NULL DEFAULT 'crawl' CHECK (...)` als letzte Spalte. Kommentar je Spalte (TRANS-07: `next_start_ms` im selben Commit wie die Wörter).
- **migrate.py:** `V2_TO_V3_STEPS` = Tabelle, Index, ALTER, Saat (`MAX(f.mtime)` aktiver keyed-Verweise, `epoch = media.epoch`, origin crawl, Zeit als Parameter), Versionsmarke 3. `migrate_v2_to_v3` mit BEGIN IMMEDIATE und ROLLBACK, Log nur `from`, `to`, `preview_jobs`.
- **repo.py:** `SCHEMA_VERSION = 3`; `Store.open` hebt v1 über v2 bis v3, v2 direkt (jeder Schritt eigene Transaktion). `ORIGINS`, `IntakeItem.origin = "crawl"`, Prüfung `ValueError("invalid intake field: origin")` für jede Art. `_INTAKE_NEW` schreibt origin; `_INTAKE_METADATA`, `_INTAKE_CHANGED`, `_INTAKE_RESTORE` mit "event gewinnt". `_SEED_PREVIEW_JOB` in `mark_keyed` und `attach_by_proof` innerhalb derselben Transaktion.

## Tests und Gates

- Volle Suite: **1119 passed** (vorher 1064; +17 in test_store_migration_v3.py, +38 in test_preview_seed.py).
- ruff check, ruff format --check (80 Dateien), pyright (latest, 0 Fehler), vulture: grün.
- RED-Läufe: Task 1 mit 27 Fehlschlägen über 7 Dateien, Task 2 mit ImportError (`ORIGINS` fehlte).
- Positivkontrollen:
  - Frozen V2_SCHEMA gegen schema.sql vor der Änderung: 17 von 17 Anweisungen gleich (normalisiert und zusätzlich über sqlite_master in einer Speicher-DB).
  - Mutationsproben repo.py (8 Stück: kein Vergessen des Jobs, keine Saat in mark_keyed bzw. attach_by_proof, crawl überschreibt event am Verweis bzw. am Job, abgeschlossener Job wird geändert, Papierkorb sät, origin ungeprüft): jede macht test_preview_seed.py rot.
  - Mutationsproben migrate.py (4 Stück: Saat nimmt Papierkorb, MIN statt MAX, COMMIT statt ROLLBACK, Konstante weicht von schema.sql ab): jede macht test_store_migration_v3.py rot.
  - Gate-Werkzeuge an einer Fehlerdatei: ruff check Exit 1, pyright Exit 1, ruff format --check Exit 1, vulture Exit 3 (unerreichbarer Code); Probedatei danach entfernt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fremdschlüssel beim Vergessen eines Inhalts mit Job**
- **Found during:** Task 2
- **Issue:** `preview_job.media_id REFERENCES media`, `PRAGMA foreign_keys = ON`: `_forget` (Ausschluss, `forget_media`) und `remove_sample` hätten die media-Zeile mit FOREIGN KEY constraint failed nicht löschen können.
- **Fix:** `_FORGET_PREVIEW_JOB` vor dem Löschen der media-Zeile in `_forget` (immer) und in `remove_sample`.
- **Files modified:** backend/src/audio_video_search_backend/store/repo.py
- **Commit:** 5cc8e7c (Tests in 879fd68)

**2. [Rule 3 - Blocking] Erwartungen schemaVersion 2 in weiteren Tests**
- **Found during:** Task 1
- **Issue:** test_handshake.py, test_main.py (`/status` schemaVersion), test_index_open.py und test_store_migration_v2.py (Version 2, "neuere Version 3 abgelehnt") erwarteten Version 2.
- **Fix:** auf 3 angepasst; die Ablehnungsprobe nutzt jetzt Version 4. test_store_metadata.py prüft info.xml und enthält keine Schema-Erwartung, blieb daher unverändert.
- **Commit:** 0450426

**3. Saat als INSERT ... SELECT statt VALUES**
- Die Bedingung "nur aktiver Verweis" steht in der Anweisung selbst (`f.state = 'active' AND f.stage = 'keyed'`); epoch, origin und mtime kommen aus der Datenbank. Da mark_keyed und attach_by_proof den Verweis direkt davor aktiv setzen, erreicht kein öffentlicher Weg diese Bedingung; sie ist deshalb in 49044b9 direkt an der Anweisung getestet.

**4. running wird von einer Kopie nicht verändert**
- Der Plan nennt `WHERE preview_job.state IN ('queued','waiting')`; damit bleibt auch ein laufender Job unverändert. Test parametrisiert über complete, skipped und running; waiting als Positivkontrolle.

## Offene Punkte

- **deploy-harp.yml Upgrade-Job** prüft nach dem Update noch `.schemaVersion == 2` (Zeile 882, dazu `backend/tests/test_workflows.py` Zeile 353). Lokal grün, in CI wird der Upgrade-Job ab diesem Stand rot, bis Plan 03-19 (PREV_VERSION 0.2.0, Nachher-Kontrolle Schema 3) umgesetzt ist. Bewusst nicht angefasst, weil 03-19 genau diese Stelle neu schreibt.
- **Herkunft von PHP:** `IntakeItem.origin` hat Standard crawl; `nc_queue.ClaimItem`, `to_intake` und die PHP-Warteschlange liefern origin noch nicht (laut PATTERNS ein späterer Plan, Lockstep beachten).
- **Wiederherstellen aus dem Papierkorb und erneuerte Leseprobe** (`_restore` auf active/keyed, `confirm_proof`) säen keinen Job. Ein Inhalt, der bei der Migration nur Verweise im Papierkorb hatte, bekommt also erst beim nächsten Schlüsseln einer Kopie einen Job. Plan nennt nur mark_keyed und attach_by_proof; für den Worker-Plan zu entscheiden.

## Threat Flags

Keine neue Oberfläche außerhalb des Bedrohungsmodells (T-03-07 bis T-03-10 umgesetzt und getestet).

## Self-Check: PASSED

- Dateien vorhanden: test_store_migration_v3.py, test_preview_seed.py, schema.sql mit genau einer `CREATE TABLE IF NOT EXISTS preview_job`.
- Commits vorhanden: 0450426, 8336c61, 879fd68, 5cc8e7c, 49044b9.
