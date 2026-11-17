---
phase: 04-suchqualit-t-und-export
plan: 05
subsystem: backend/store+worker
tags: [EXP-03, EXP-01, D-04-15, D-04-17, schema-v4, file-language]
requires: []
provides:
  - "store/migrate.py: V3_TO_V4_STEPS und migrate_v3_to_v4 (eine Transaktion, Rollback lässt die Datei auf v3)"
  - "store/repo.py: SCHEMA_VERSION = 4, FILE_LANGUAGES, Store.file_language(media_id), Store.set_file_language(media_id, language)"
  - "preview_job.words_de/en/fr und media.language (CHECK nur de/en/fr oder NULL)"
  - "worker/preview.py take(): Sprachzählung je KEEP-Fenster über window.lid"
  - "file_language.detect(words) -> de|en|fr|None, py3langid auf drei Sprachen beschränkt, lazy geladen"
affects: [04-09]
tech-stack:
  added: []
  patterns:
    - "Migration als Modulkonstanten-Schritte in BEGIN IMMEDIATE, Test schiebt einen Fehlschritt dazwischen"
    - "Mehrheit mit Gleichstands-Reihenfolge als SQL-CASE in derselben Transaktion wie das Urteil"
key-files:
  created:
    - backend/src/audio_video_search_backend/file_language.py
    - backend/tests/test_store_migration_v4.py
    - backend/tests/test_file_language.py
    - backend/tests/file_language_probe.py
  modified:
    - backend/src/audio_video_search_backend/store/schema.sql
    - backend/src/audio_video_search_backend/store/migrate.py
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/worker/preview.py
    - backend/tests/test_store_migration_v2.py
    - backend/tests/test_store_migration_v3.py
    - backend/tests/test_store_schema.py
    - backend/tests/test_preview_worker.py
    - backend/tests/test_index_open.py
    - backend/tests/test_handshake.py
    - backend/tests/test_main.py
decisions:
  - "finish_preview mit Urteil transcript überschreibt eine früher per set_file_language gespeicherte Rückfall-Sprache: das fertige Transkript kennt die ganze Datei (Test test_the_verdict_overwrites_an_earlier_fallback)"
  - "set_file_language loggt nur die media_id, nie die Sprache (T-04-15)"
  - "Der v3-Konstanten-Vergleich in test_store_migration_v3.py ist jetzt ein Präfix-Vergleich: schema.sql beschreibt v4, PREVIEW_JOB_V3 fährt weiter die 2-nach-3-Migration"
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-16
  tasks: 2
  files: 15
---

# Phase 4 Plan 05: Mehrheitssprache je Datei, Store v4, Nachbestimmung für Altbestand Summary

Store v4 trägt je Vorschau-Job die behaltenen Wörter nach Text-Sprache (words_de/en/fr) und je Inhalt die Mehrheitssprache (media.language, CHECK nur de/en/fr oder NULL); der Worker zählt beim Stück-Schreiben über window.lid, das Urteil transcript speichert die Mehrheit (Gleichstand de vor en vor fr) in derselben Transaktion, und file_language.detect bestimmt für den Altbestand die Sprache aus dem Transkripttext, nur aus de/en/fr; "und" kann an keiner Stelle als Dateisprache herauskommen (D-04-15).

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | Store v4 mit Sprachzählern und Dateisprache | f4f508b (RED), ddbebfb (GREEN) | schema.sql, migrate.py, repo.py, test_store_migration_v4/v3/v2.py, test_store_schema.py |
| 2 | Worker zählt Sprachen, file_language.detect für Altbestand | 79eba69 (RED), 5761d3c (GREEN) | worker/preview.py, file_language.py, test_file_language.py, file_language_probe.py, test_preview_worker.py |

## Ergebnis

- `migrate_v3_to_v4` hebt eine v3-Datei in einer Transaktion (BEGIN IMMEDIATE) auf v4; ein erzwungener Fehlschritt lässt die Datei byte-gleich auf Version 3, Fehlerlog nur mit from/to (T-04-12). Eine v2-Datei läuft 2 nach 3 nach 4 im selben Open, eine v1-Datei durch alle drei Schritte; ein Leser migriert nie, Version 5 wird abgelehnt.
- Frische und migrierte Dateien haben spaltengleiche Schemata (PRAGMA-Vergleich); die neuen Spalten stehen am Tabellenende, weil ALTER TABLE anhängt.
- `commit_chunk` addiert words_de/en/fr zusammen mit den übrigen Zählern in einer Transaktion und prüft sie wie diese (negative Werte = ValueError); der Weg zurück eines zu langen Jobs (`requeue_too_long`) setzt sie mit next_start_ms und chunks_done auf 0.
- `finish_preview(job, "transcript")` speichert die Mehrheit der Zähler als media.language in derselben Transaktion wie das Urteil: Gleichstand de vor en vor fr (SQL-CASE), Summe 0 speichert nichts, andere Urteile und ein stales Urteil lassen die Sprache unverändert.
- `Store.file_language(media_id)`: gespeicherte Sprache, sonst Mehrheit der laufenden Zähler (Teiltranskript, D-04-17), sonst None. `Store.set_file_language` wirft ValueError für alles außer de/en/fr (auch "und"), setzt nur bei NULL (erste Bestimmung gewinnt) und loggt nur die media_id.
- `take()` zählt jedes behaltene Wort nach `window.lid` in de/en/fr; Fenster außerhalb der drei Sprachen behalten ihre Wörter, zählen aber für keine Sprache; Kontextwörter vor start_ms zählen nicht. `PREVIEW_LANGUAGE = "und"` bleibt die Provenienz der Version.
- `file_language.detect`: py3langid wie in engine/parakeet.py geladen (nur Modul langid), per `set_languages(["de", "en", "fr"])` beschränkt, `functools.cache`; höchstens `LANGUAGE_SAMPLE_WORDS = 3000` Wörter (Test mit Giftobjekt hinter der Grenze); türkischer Text bleibt in den drei Sprachen, leerer Text ist None. Der Import lädt py3langid nicht (Probe-Datei in frischem Interpreter, nie `python -c`).
- Gates nach jedem GREEN-Commit: ruff check + format `--no-cache` grün, pyright (PYRIGHT_PYTHON_FORCE_VERSION=latest, --pythonpath .venv/Scripts/python.exe) 0 Fehler, vulture grün, volle Suite zuletzt 2137 bestanden, 15 übersprungen, 4 xfailed.
- Plan-Greps alle erfüllt: migrate_v3_to_v4/V3_TO_V4_STEPS, SCHEMA_VERSION: Final = 4, kein `schema_version() == 3`/`== "3"`/`is_three` mehr in test_store_migration_v2.py und test_store_schema.py, words_de in take und _add, set_languages/LANGUAGE_SAMPLE_WORDS/functools.cache vorhanden, kein Modul-Import von py3langid in file_language.py.

## Bekannte Grenzen

1. **Noch nicht verdrahtet:** `file_language`, `set_file_language` und `detect` werden erst in Plan 04-09 von der Export-Route benutzt; bis dahin belegen nur die Tests die Verträge (laut Plan-Objective so vorgesehen).
2. **Teiltranskript-Mehrheit kann sich ändern:** Die Rückfall-Antwort aus laufenden Zählern (D-04-17) kann sich mit weiteren Stücken verschieben; das fertige Urteil überschreibt sie bewusst.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blockierend] Weitere feste Versions-Annahmen außerhalb der Planliste**
- **Found during:** Task 1 (volle Suite)
- **Issue:** `test_handshake.py` und `test_main.py` erwarten `"schemaVersion": 3` in der Status-Antwort, `test_index_open.py` prüft `schema_version() == 3`; alle drei Dateien nennt der Plan nicht.
- **Fix:** Auf `SCHEMA_VERSION` (Status-Tests) bzw. `STORE_SCHEMA_VERSION`-Alias (test_index_open.py, dort ist SCHEMA_VERSION die Index-Schema-Version) umgestellt.
- **Files modified:** backend/tests/test_handshake.py, backend/tests/test_main.py, backend/tests/test_index_open.py
- **Commit:** f4f508b (index_open), ddbebfb (handshake, main)

**2. [Rule 1 - Testfolge] Migrations-Log-Test zählt jetzt zwei Hebungen**
- **Found during:** Task 1
- **Issue:** `test_the_migration_logs_counts_only` nahm genau einen "store migrated"-Eintrag an; eine v2-Datei läuft jetzt 2 nach 3 nach 4 und loggt zweimal.
- **Fix:** Erwartung auf die Folge (2,3) dann (3,4), preview_jobs weiter nur am 2-nach-3-Schritt.
- **Files modified:** backend/tests/test_store_migration_v3.py
- **Commit:** f4f508b

Sonst keine Abweichungen: Spalten, Schritte, Mehrheitsregel, Zähl- und Rückfallverhalten folgen wörtlich dem Plan. Nebenbefund am Bestand (requeue_too_long lässt kept_words/version_id stehen) nicht angefasst, sondern in deferred-items.md festgehalten.

## TDD Gate Compliance

RED f4f508b und 79eba69, danach GREEN ddbebfb und 5761d3c (5761d3c ist die nachgebesserte Commit-Botschaft des ursprünglichen GREEN-Commits c41fa26, nur Text geändert, lokal vor jedem Push zulässig). Ein REFACTOR-Commit war nicht nötig. Beide RED-Läufe schlugen vor der Implementierung aus den richtigen Gründen fehl (fehlende Konstanten/Methoden bzw. Zähler gleich 0).

## Requirements

EXP-01 und EXP-03 bleiben in REQUIREMENTS.md offen: Dieser Plan liefert den Sprach-Schnitt für den Dateinamen `<Name>.<Sprache>.<ext>`; Download-Routen und Nebendatei-Ablage entstehen erst in den Plänen 04-06 ff. und 04-09.

## Threat Flags

Keine neue Angriffsfläche über das Threat Model des Plans hinaus.
- T-04-12: eine Transaktion, Rollback-Test mit erzwungenem Fehler bleibt v3, unbekannte Version abgelehnt (Version 5 getestet).
- T-04-13: CHECK-Constraint de/en/fr in SQLite (negativ "und"/"tr"/"" und positiv de/en/fr/NULL getestet), set_file_language wirft für alles andere, detect auf drei Sprachen beschränkt.
- T-04-14: LANGUAGE_SAMPLE_WORDS = 3000 hart getestet (Giftobjekt hinter der Grenze), Identifier einmal geladen und gecacht.
- T-04-15: kein Text, keine Sprache mit Namen im Log; set_file_language loggt nur media_id, detect loggt nichts.

## Self-Check: PASSED

- FOUND: backend/src/audio_video_search_backend/file_language.py
- FOUND: backend/tests/test_store_migration_v4.py
- FOUND: backend/tests/test_file_language.py
- FOUND: backend/tests/file_language_probe.py
- FOUND: backend/src/audio_video_search_backend/store/migrate.py (migrate_v3_to_v4)
- FOUND: Commits f4f508b, ddbebfb, 79eba69, 5761d3c
