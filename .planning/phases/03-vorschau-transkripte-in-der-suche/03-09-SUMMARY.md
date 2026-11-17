---
phase: 03-vorschau-transkripte-in-der-suche
plan: 09
subsystem: store
tags: [sqlite, preview_job, claim, stueck-commit, coverage, tdd]
requires: ["03-03"]
provides:
  - "repo: PREVIEW_STATES, PREVIEW_REASONS, MAX_DURATION_KEY, DEFAULT_MAX_DURATION_HOURS"
  - "repo: PreviewJob, ChunkCounters, PreviewView"
  - "Store: next_preview, preview_source, commit_chunk, finish_preview, skip_preview, defer_preview, retry_preview, yield_preview, reset_running, has_waiting_event, requeue_too_long, max_duration_hours, set_max_duration_hours, preview_view"
  - "Store._publish: gemeinsamer Helfer von publish_version und commit_chunk"
  - "coverage: byPreview (fester Namensliste), /coverage trägt byPreview"
  - "php ExAppService::coverage nimmt byPreview an (PREVIEW_NAMES, COVERAGE_KEYS)"
  - "Job-Saat auch bei Wiederherstellung aus dem Papierkorb, bestätigter Leseprobe und zurückgekehrtem Speicher"
affects: [03-13, 03-14, 03-15]
tech-stack:
  added: []
  patterns:
    - "Claim als UPDATE ... WHERE media_id = (SELECT ... ORDER BY ... LIMIT 1) RETURNING"
    - "jeder Schreibweg nach dem Claim nennt den laufenden Job und seine Epoche (Job und media), sonst stale"
    - "Rollback-Test über eine eingeschobene Verbindung, die beim ersten UPDATE preview_job wirft und vorher prüft, dass Wörter schon geschrieben sind"
key-files:
  created:
    - backend/tests/test_preview_store.py
  modified:
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/store/coverage.py
    - backend/src/audio_video_search_backend/api/coverage.py
    - backend/tests/test_coverage_count.py
    - backend/tests/test_api_routes.py
    - php/lib/Service/ExAppService.php
    - php/tests/Unit/ExAppServiceTest.php
decisions:
  - "commit_chunk nimmt version_id und next_start_ms aus der Datenbank, nicht aus dem PreviewJob-Objekt: der Worker kann mit dem einmal geholten Job weiterarbeiten; ein Stück darf next_start_ms nie zurücksetzen"
  - "Ein Folgestück ist stale, wenn current nicht mehr auf die Vorschau-Version zeigt (z. B. ein Endtext wurde veröffentlicht)"
  - "Der Claim löscht reason, damit ein laufender Job in byPreview nie unter disk_full zählt"
  - "has_waiting_event verlangt dieselbe Lesbarkeit wie der Claim (aktiver, erfasster Verweis mit Leser); sonst würde ein langer Job für ein Ereignis weichen, das niemand holen kann"
  - "Saat auch in _restore (aktiv und erfasst), confirm_proof und mark_present (offener Punkt aus 03-03); Wiederherstellung mit Beweispflicht sät erst bei bestandener Probe"
  - "byPreview wird auch in PHP geprüft (Gleichschritt-Test), sonst lehnt ExAppService::coverage die Antwort ab"
metrics:
  duration: "ca. 110 min"
  completed: 2026-11-14
  tasks: 2
  files: 8
---

# Phase 3 Plan 09: Vorschau-Jobs im Store Summary

Store-Methoden der Vorschau: Claim in der Reihenfolge event vor crawl und neueste zuerst, nur mit aktivem Leser; Stück-Commit in genau einer Transaktion (Wörter, index_rev, Outbox, next_start_ms, Zähler) mit Teiltreffern an einer Vorschau-Version; Urteile, Gründe, Rückstellen, Unterbrechen und Neustart; Höchstdauer in meta; preview_view nur über aktive Verweise; occ-Zähler byPreview in Python und PHP.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 RED | 12311c7 | test(03-09): Vorschau-Jobs im Store als Vertrag |
| 1 GREEN | 7f3d2f2 | feat(03-09): Vorschau-Jobs im Store: Claim, Stück-Commit, Urteile, Rückstellen |
| 1 Nachtrag | 6a3e3b4 | test(03-09): Epochen- und current-Wechsel beim Folgestück als Fälle |
| 2 RED | c48c192 | test(03-09): occ-Zähler byPreview und Vergessen des Jobs als Vertrag |
| 2 RED (PHP-Gleichschritt) | ac9e61d | test(03-09): byPreview im Gleichschritt mit der PHP-Prüfung der Coverage-Antwort |
| 2 GREEN | bb771be | feat(03-09): occ-Zähler byPreview nach Grund oder Zustand |
| Refactor | 8eb9584 | refactor(03-09): Teillisten der Vorschau-Gründe aus PREVIEW_REASONS abgeleitet |

Alle Commits lokal, Autor und Committer street1983nk <k.cherif@outlook.de>, nichts gepusht.

## Was gebaut wurde

- **Claim** `next_preview(now)`: `queued` oder `waiting` mit fälligem `next_try_at`, nur mit aktivem, erfasstem Verweis samt `reader_uid` (T-03-32); Reihenfolge `CASE origin WHEN 'event' THEN 0 ELSE 1 END, sort_mtime DESC, media_id`; setzt `running` und löscht `reason`.
- **Quelle** `preview_source(media_id)`: (file_id, reader_uid, size) des aktiven, erfassten Verweises mit Leser und kleinster file_id.
- **Stück-Commit** `commit_chunk(job, *, prov, words, next_start_ms, counters) -> bool`: eine Transaktion. Prüft Job `running`, Job-Epoche gleich media-Epoche gleich `prov.epoch`, `next_start_ms` nicht kleiner als gespeichert. Erstes Stück mit Wörtern über `_publish` (gemeinsamer Helfer mit `publish_version`: Eingabe-sha256, Transkript, Wörter, bedingtes `current`, Outbox); weitere Stücke hängen Wörter ab `MAX(idx)+1` an dieselbe Version, `_BUMP_INDEX_REV` + `_INSERT_OUTBOX`, nur wenn `current` noch auf diese Version zeigt. Danach `next_start_ms`, `chunks_done + 1`, `version_id`, Zähler addiert.
- **Urteile**: `finish_preview` (transcript: complete; no_speech, unsupported_language: skipped mit Grund, current unberührt), `skip_preview` (no_audio, damaged, protected, format_unsupported, too_long, engine_failed; duration_ms darf None sein, D-03-20), `defer_preview` (nur disk_full), `retry_preview` (waiting ohne Grund, `count` erhöht attempts), `yield_preview` (zurück auf queued, Fortschritt bleibt). Alle nur für den laufenden Job seiner Epoche; unbekannte Codes `ValueError("invalid preview field: reason|verdict")` ohne Wert.
- **Neustart** `reset_running() -> int`; **Ereignis wartet** `has_waiting_event()`.
- **Höchstdauer**: `max_duration_hours()` (meta, Standard 12, kaputter Wert gibt 12), `set_max_duration_hours(h) -> alter Wert` (h >= 1), `requeue_too_long(max_ms)` (duration_ms <= max_ms oder NULL zurück auf queued, Start bei 0).
- **preview_view(file_id)**: (state, reason, chunks_done, next_start_ms, level oder None) nur über einen aktiven Verweis; unreadable, vanished, trashed, Probe und unbekannte Datei geben gleichermaßen None (D-02-15c unverändert).
- **coverage**: `_BY_PREVIEW = "SELECT COALESCE(reason, state), COUNT(*) FROM preview_job GROUP BY 1"` gegen `PREVIEW_STATES | PREVIEW_REASONS`, Feld `byPreview` in `as_wire` (der Plan nennt `to_json`; die Methode heißt im Bestand `as_wire`).
- **Löschen**: `_forget` und `remove_sample` löschten den Job schon seit 03-03 vor der media-Zeile; neu getestet mit Job samt Stücken und mit einer Quellprüfung jeder `_DELETE_MEDIA`-Stelle.

## Tests und Gates

- Volle Suite: **1528 passed** (nach Task 1: 1521; test_preview_store.py 99 Fälle, test_coverage_count.py +5).
- ruff check, ruff format --check (100 Dateien), pyright (latest, 0 Fehler), vulture: grün.
- RED-Läufe: Task 1 ImportError (`PREVIEW_REASONS` fehlte); Task 2 6 Fehlschläge (5 coverage, 1 /coverage-Schlüssel); PHP-Gleichschritt-Commit rot durch die neue Coverage-Arität.
- Positivkontrollen:
  - 28 Mutationsproben gegen repo.py (Reihenfolge ASC, event zuletzt, ohne Leser, ohne Stufe keyed, waiting ohne Zeit, Claim behält Grund, ohne media-Epoche, ohne running, Rückwärtsstück, ohne prov-Epoche, idx ab 0, ohne Revision, ohne current-Prüfung, chunks_done fest, Zähler überschrieben, Urteil ohne media-Epoche, Versuch nicht gezählt, Neustart setzt Fortschritt zurück, Ereignis ohne Leser, `<` statt `<=`, NULL nicht zurück, preview_view ohne active, Skip-Liste zu weit, je eine Saat entfernt in _restore, confirm_proof, mark_present, Standard der Höchstdauer, Job beim Vergessen behalten): alle rot. Drei Proben überlebten zuerst und führten zu neuen Fällen in 6a3e3b4.
  - 4 Mutationsproben gegen coverage.py (COALESCE vertauscht, nur Zustände, Feld nicht auf dem Draht, ungefilterte Zählung): alle rot.
  - Gate-Werkzeuge an einer Fehlerdatei: ruff check Exit 1, ruff format --check Exit 1, pyright Exit 1, vulture Exit 3; Probedatei danach entfernt.
  - Gedankenstrich-Prüfung über alle geänderten Dateien: 0 Treffer (Prüfer an einem Beispiel mit U+2014 positiv).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] PHP lehnt die Coverage-Antwort mit byPreview ab**
- **Found during:** Task 2
- **Issue:** `ExAppService::coverage` verlangt genau `COVERAGE_KEYS`; mit `byPreview` wäre `occ audio_video_search:status` ohne Zahlen geblieben. Der Gleichschritt-Test `test_the_php_app_checks_the_same_closed_lists_and_keys` wurde rot. Kein Plan der Phase passt `COVERAGE_KEYS` an; 03-14 setzt `$coverage['byPreview']` aber voraus.
- **Fix:** `PREVIEW_NAMES`, `COVERAGE_KEYS` + `byPreview`, Prüfung über `countsOf`, Rückgabe `byPreview`; ExAppServiceTest mit Reihenfolge und vier Fehlformen; Python-Gleichschritt-Test vergleicht `PREVIEW_NAMES` mit den Python-Listen.
- **Nicht lokal geprüft:** kein PHP und kein Docker auf dem Rechner. CI (`php -l`, phpunit) läuft erst beim nächsten Push.
- **Commits:** ac9e61d, bb771be

**2. [Rule 2] Saat auf den Rückwegen zu einem aktiven, erfassten Verweis (offener Punkt aus 03-03)**
- `_restore` (aktiv und erfasst), `confirm_proof` und `mark_present` säen den Job im selben Commit (gleiche Anweisung `_SEED_PREVIEW_JOB`, ein abgeschlossener oder laufender Job bleibt unverändert). Ohne das hätte `preview_view` für einen wiederhergestellten Inhalt ohne Job None geliefert und der Worker den Inhalt nie geholt. `_MARK_PRESENT` liefert dafür zusätzlich `file_id`.
- **Commit:** 7f3d2f2 (Tests in 12311c7)

**3. has_waiting_event mit Lesbarkeit**
- Plan: "true genau dann, wenn ein queued-Job mit origin event existiert". Umgesetzt mit derselben Bedingung wie der Claim; sonst wiche ein langer Job bei jedem Stück für ein Ereignis, das der Claim nie herausgibt.

**4. Zusätzliche Stale-Fälle in commit_chunk**
- `prov.epoch` ungleich Job-Epoche, `next_start_ms` kleiner als gespeichert, `current` zeigt nicht mehr auf die Vorschau-Version, andere Bytes (`input_mismatch`): jeweils False, nichts geschrieben.

**5. Prüfungen mit Feldnamen**
- `invalid preview field: next_start_ms|counters|verdict|reason|next_try_at|duration_ms|max_ms|max_duration_hours`, nie der Wert.

## Offene Punkte

- **PHP-Änderung nur in CI prüfbar** (siehe Abweichung 1): beim nächsten Push `php.yml` beobachten.
- **Epoche und Job:** `bump_epoch` hat noch keinen Aufrufer. Wer ihn einführt (Neuberechnung, Modellrückruf), muss den Job im selben Commit auf die neue Epoche setzen und zurückstellen; sonst bleibt ein Job alter Epoche stale und wird nach jedem Neustart erneut geholt.
- **preview_view ohne Job gibt None:** ein aktiver Verweis mit current, aber ohne Job (nur noch durch direkte Eingriffe denkbar) wirkt für 03-14 wie unbekannt. 03-14 entscheidet, ob dann `current` allein reicht.
- **Folgestück nach fremder current-Version** gibt False; der Worker (03-13) muss das als STALE behandeln und den Job beenden statt erneut zu versuchen.
- Aus 03-03 weiter offen: deploy-harp.yml prüft Schema 2 (Plan 03-19); origin von PHP (späterer Plan).

## Threat Flags

Keine neue Oberfläche außerhalb des Bedrohungsmodells. T-03-29 (eine Transaktion, Epochenprüfung, Rollback-Test), T-03-30 (preview_view nur active, alle Zustände getestet), T-03-31 (feste Namensliste, keine IDs), T-03-32 (Claim nur mit Leser) umgesetzt und getestet.

## Known Stubs

Keine.

## TDD Gate Compliance

test(03-09) 12311c7 vor feat(03-09) 7f3d2f2; test(03-09) c48c192 und ac9e61d vor feat(03-09) bb771be.

## Self-Check: PASSED

- Dateien vorhanden: backend/tests/test_preview_store.py (99 Fälle), 03-09-SUMMARY.md.
- Commits vorhanden: 12311c7, 7f3d2f2, 6a3e3b4, c48c192, ac9e61d, bb771be, 8eb9584.
