---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 02
subsystem: database
tags: [sqlite, provenance, corrections, upsert, wal, tdd]
requires:
  - phase: 01-01
    provides: "backend/ mit Paket audio_video_search_backend, conftest BACKEND_ROOT/REPO_ROOT"
provides:
  - "store/schema.sql: meta, media (mit epoch), media_key, file_ref, transcript, word, current, correction, index_outbox; schema_version 1"
  - "store/repo.py: Store, PublishResult, CurrentRow, STATE_REASONS; publish_version mit bedingtem UPSERT"
  - "model/provenance.py: Level, ENGINES, PROFILES, SAMPLE_MODEL_SHA256, Provenance, validate, order_key"
  - "model/overlay.py: Word, Correction, effective_words (Mittelpunktregel, ganze ms)"
  - "conftest-Fixture store (frische DB im tmp_path)"
affects: [01-05, 01-08]
tech-stack:
  added: []
  patterns:
    - "SQL nur als Final-Konstanten mit Platzhaltern; Transaktion BEGIN IMMEDIATE / ROLLBACK / COMMIT (Findling)"
    - "Ablehnung im Store über interne Ausnahme _Rejected: Rollback, dann PublishResult mit Grund-Code"
    - "Fehlermeldungen nennen nur den Feldnamen, nie den Wert; Logs nur IDs und Zahlen per extra="
key-files:
  created:
    - backend/src/audio_video_search_backend/model/__init__.py
    - backend/src/audio_video_search_backend/model/provenance.py
    - backend/src/audio_video_search_backend/model/overlay.py
    - backend/src/audio_video_search_backend/store/__init__.py
    - backend/src/audio_video_search_backend/store/schema.sql
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/tests/test_provenance.py
    - backend/tests/test_corrections.py
    - backend/tests/test_store_schema.py
  modified:
    - backend/tests/conftest.py
key-decisions:
  - "Epoch je media_id liegt in media.epoch (Spalte mit DEFAULT 0); publish_version weist Ergebnisse mit prov.epoch < media.epoch als stale_rejected ab, damit laufende Ergebnisse alter Epoche nach bump_epoch nie mehr gewinnen"
  - "Neue Methode Store.media_epoch(media_id): Plan 05 nimmt die Epoche für den Testtreffer daraus statt aus current.epoch"
  - "file_ref.state ist ein kurzer Code [a-z_]{1,32}, reason aus der geschlossenen Liste STATE_REASONS (Phase 1: sample); leerer reason wird NULL"
  - "words_json einer Korrektur wird beim Schreiben geprüft (ganze ms, aufsteigend, innerhalb der Spanne)"
  - "rover-model_sha256 muss sortiert und mindestens zweiteilig sein; sample-model_sha256 muss SAMPLE_MODEL_SHA256 sein"
  - "remove_sample löscht media/media_key nur, wenn keine file_ref-, correction- oder transcript-Zeile mehr darauf zeigt"
patterns-established:
  - "Store-Fixture in conftest.py für alle Store-Tests"
requirements-completed: [TRANS-06]
duration: 9min
completed: 2026-11-06
---

# Phase 1 Plan 02: Datenmodell, Provenienz und Korrektur-Schicht Summary

**SQLite-Schema als Wahrheit mit media_key-Indirektion, bedingtem UPSERT auf current (epoch, level, config_version) und zeitverankerter Korrektur-Überlagerung, durch 72 Unit-Tests belegt**

## Performance

- **Duration:** ca. 9 min
- **Started:** 2026-11-06T12:44Z
- **Completed:** 2026-11-06T12:53Z
- **Tasks:** 2 (je RED und GREEN)
- **Files modified:** 10

## Accomplishments

- Erfolgskriterium 4: Jede Version trägt engine, model_sha256, config_version, profile, level, epoch, language, input_file_sha256; ungültige Provenienz schreibt nichts. Ältere Stufe mit höherer config_version und Gleichstand werden abgewiesen, ohne verwaiste transcript- oder word-Zeilen; höhere Epoche gewinnt mit Stufe SAMPLE; falscher input_file_sha256 ergibt input_mismatch.
- Erfolgskriterium 5: Korrektur [250, 900) "Haushaltsplan" übersteht den Ersatz v1 durch v2 ("der Haushaltsplan wurde beschlossen") und eine abgewiesene veraltete Veröffentlichung; Randfälle 1 bis 4 einzeln getestet.
- Schema mit schema_version 1 und index_generation in meta, alle *_ms-Spalten INTEGER, WAL aktiv, read_only-Verbindung mit query_only.
- remove_sample und count_current_at_level für Plan 05/08 bereit.

## Task Commits

1. **Task 1: Provenienz und Korrektur-Überlagerung**
   - `90ba8c4` test(01-02): rote Tests
   - `58cf5dd` feat(01-02): model/provenance.py, model/overlay.py
2. **Task 2: SQLite-Schema und Store**
   - `1564feb` test(01-02): rote Store-Tests
   - `3ab10d5` feat(01-02): store/schema.sql, store/repo.py

## Files Created/Modified

- `backend/src/audio_video_search_backend/model/provenance.py`: Level, geschlossene Listen, validate, order_key
- `backend/src/audio_video_search_backend/model/overlay.py`: Word, Correction, effective_words
- `backend/src/audio_video_search_backend/store/schema.sql`: neun Tabellen, Indizes, CHECKs
- `backend/src/audio_video_search_backend/store/repo.py`: Store nach Interface-Block des Plans
- `backend/tests/test_provenance.py`, `test_corrections.py`, `test_store_schema.py`: Funktions- und Store-Ebene
- `backend/tests/conftest.py`: Fixture `store`

## Decisions Made

Siehe key-decisions im Kopf. Wichtig für Plan 05: Epoche des Testtreffers aus `store.media_epoch(media_id)` nehmen; `current.epoch` würde nach `bump_epoch` abgewiesen.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Korrektheit] Spalte media.epoch und Methode media_epoch**
- **Found during:** Task 2
- **Issue:** Der Plan sieht `bump_epoch(media_id) -> int` vor, das Schema aber keinen Ort für die Epoche je media_id. Ohne gespeicherte Epoche kann der Test "bump_epoch und danach Stufe SAMPLE published" nicht bestehen, und ein laufendes Ergebnis alter Epoche könnte nach dem Neu-Rechnen-Wunsch noch gewinnen.
- **Fix:** `media.epoch INTEGER NOT NULL DEFAULT 0`, `bump_epoch` erhöht sie, `publish_version` weist `prov.epoch < media.epoch` als `stale_rejected` ab, `media_epoch()` liest sie.
- **Files modified:** store/schema.sql, store/repo.py
- **Commit:** 3ab10d5

**2. [Rule 2 - Sicherheit] Eingabeprüfung in add_correction und upsert_file_ref**
- **Found during:** Task 2
- **Issue:** Werte aus signierten Anfragen landen später direkt hier (Trust Boundary des Plans).
- **Fix:** kind, start_ms, end_ms, author_uid (1 bis 64 Zeichen), words_json und file_ref.state/reason werden vor der Transaktion geprüft; ValueError nennt nur das Feld.
- **Commit:** 3ab10d5

---

**Total deviations:** 2 auto-fixed (Rule 2). **Impact:** Kein Scope-Zuwachs; Interface des Plans unverändert, nur um `media_epoch` erweitert.

## Issues Encountered

- ruff RUF001 meldete typografische Anführungszeichen im Satzzeichen-Set von overlay.py; als `\u`-Escapes geschrieben.
- `assert` für lastrowid in repo.py (ruff S101) durch Helfer `_row_id` mit RuntimeError ersetzt.

## Known Stubs

Keine. `STATE_REASONS` enthält in Phase 1 bewusst nur `sample`; spätere Phasen ergänzen die Liste.

## TDD Gate Compliance

RED vor GREEN je Task: `90ba8c4` (test) vor `58cf5dd` (feat), `1564feb` (test) vor `3ab10d5` (feat).

## Next Phase Readiness

- Plan 05 kann `media_for_file_sha256`, `upsert_file_ref`, `publish_version`, `effective_words`, `pending_index_work`, `mark_indexed`, `remove_sample` direkt nutzen. `meta.index_generation` ist mit `'0'` angelegt; Lese-/Schreibmethoden dafür bringt Plan 05.
- Gates lokal grün: ruff check, ruff format --check, pyright (latest, basic), vulture, pytest (191 passed).

## Self-Check: PASSED
