---
phase: 02-erfassung-aller-dateien
plan: 06
subsystem: php-erfassung
tags: [erst-crawl, scheduler, gate-regeln, disc-01, disc-04, d-02-05]
requires: [02-03]
provides:
  - "SchedulerJob (TimedJob 300 s, in php/appinfo/info.xml <background-jobs>): CRAWL_STATES ok und version_patch_differs, je neuem Mount avs_crawl-Zeile plus StorageCrawlJob, unfertiger Crawl ohne Job bekommt ihn zurück"
  - "StorageCrawlJob (QueuedJob): BAND 500, MAX_FILES 2000, MAX_SECONDS 60, INTERVAL_SECONDS 5, argument(storageId, rootId); Cursor in avs_crawl.last_file_id, finish nur bei leerer Scheibe"
  - "ExAppService::firstAdmin() öffentlich"
  - "test_php_gates.py Regel 12 (Mount-, Datei- und Mimetyp-Aufzählung nur in StorageService.php) und Regel 13 (keine Schlüssel path, name, mountPoint, host an den Container)"
affects: [02-07, 02-11, 02-12, 02-14, 02-16, 02-20]
tech-stack:
  added: []
  patterns:
    - "Crawl-Argument nur (storage_id, root_id); der Cursor lebt in avs_crawl, damit der Scheduler einen verlorenen Job mit IJobList::has erkennt und fortsetzt"
    - "Cursor rückt erst hinter eine erledigte Datei vor; eine gesperrte Datei ist die erste des nächsten Laufs"
    - "Container-nahe PHP-Quellen = Dateien mit ExAppRequired plus QueueService.php und ExAppService.php"
key-files:
  created:
    - php/lib/BackgroundJobs/SchedulerJob.php
    - php/lib/BackgroundJobs/StorageCrawlJob.php
    - php/tests/Unit/StorageCrawlJobTest.php
    - php/tests/Unit/SchedulerJobTest.php
  modified:
    - php/appinfo/info.xml
    - php/lib/Service/ExAppService.php
    - backend/tests/test_php_gates.py
decisions:
  - "Der Scheduler prüft den Backend-Zustand als erstes aktives Mitglied der Gruppe admin (ExAppService::firstAdmin, jetzt öffentlich); ohne Admin wird nichts geplant"
  - "Walk-Wurzel eines Crawls ist overridden_root aus getDistinctMounts (bei Homes der files-Ordner), wie avs_crawl.root_id in Plan 03"
  - "LockedException und StorageNotAvailableException schieben den Cursor nur bis zur letzten erledigten Datei und planen den Nachfolger"
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-07
  tasks: 2
  files: 7
---

# Phase 2 Plan 06: Erst-Crawl nach Handshake und Gate-Regeln 12/13 Summary

Nach dem Handshake mit dem Backend (ok oder nur Patch-Abweichung) plant ein TimedJob je Mount aus Homes und Gruppenordnern einen Erst-Crawl, der in Bändern zu 500 mit 60-s- und 2000-Dateien-Budget am Cursor fortsetzt, jede Datei durch QueueService::admissible schickt und erst bei leerer Scheibe fertig ist; zwei neue Quelltext-Regeln halten die Mount-Aufzählung an einer Stelle und Pfade vom Container fern.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | SchedulerJob und StorageCrawlJob | 90d35f7 | SchedulerJob.php, StorageCrawlJob.php, info.xml, ExAppService.php, StorageCrawlJobTest.php, SchedulerJobTest.php |
| 2 | Gate-Regeln 12 und 13 | ecb4fbe | test_php_gates.py |

Zusätzlich: 41104c9 `style(02-04)` (siehe Abweichung 4).

## Prüfungen

- Lokal kein PHP: phpunit (StorageCrawlJobTest 9 Fälle, SchedulerJobTest 9 Fälle mit Datenprovidern) und `php -l` laufen erst in CI (php.yml, Push in Plan 11).
- test_php_gates.py 27 grün (Regel 12 und 13 mit je einem Selbsttest; Regel 1, 4, 6, 7, 8 decken die neuen Jobs mit ab).
- test_store_metadata.py und test_public_texts.py grün mit dem neuen `<background-jobs>`-Eintrag.
- Volle Python-Gates seriell grün: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 487 grün.
- OCP-Namen nach stable33: TimedJob::setInterval, QueuedJob, IJobList::add/has/scheduleAfter, Job::$time, OCP\Files\StorageNotAvailableException, OCP\Lock\LockedException, IMimeTypeLoader::exists/getId (wie in QueueService).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] firstAdmin öffentlich**
- **Found during:** Task 1
- **Issue:** ExAppService::backendState braucht eine uid; im Hintergrund gibt es keine Sitzung, und die Admin-Suche war privat.
- **Fix:** `firstAdmin()` öffentlich statt einer zweiten Admin-Suche im Job. Commit 90d35f7.

**2. [Rule 2] Verlorene Crawl-Jobs**
- Ein unfertiger Crawl, dessen Job fehlt (abgebrochener Cron, gelöschter Job), bekommt beim nächsten Scheduler-Lauf seinen Job zurück; ohne das bliebe der Mount ohne finished_at und der Abgleich wartete ewig. Test im SchedulerJobTest. Commit 90d35f7.

**3. [Rule 1] Cursor hinter einer gesperrten Datei**
- Erste Fassung setzte den Cursor vor dem Einreihen; eine gesperrte Datei wäre übersprungen worden. Jetzt rückt er erst nach dem Einreihen vor. Commit 90d35f7.

**4. [Rule 1] Zeilenfortsetzungen im Workflow aus Plan 04**
- Beim Einfügen des Phasen-Schritts (Plan 04) gingen die Backslash-Zeilenenden verloren; das Skript lief gleich, war aber eine überlange Zeile. Eigener Commit 41104c9.

**5. Zusätzliche Testdatei**
- SchedulerJobTest.php ist neu (nicht in der Dateiliste des Plans), weil die Handshake-Bedingung sonst ungeprüft bliebe.

## Known Stubs

- Die Mountmenge ist bis Plan 12 nur Homes und Gruppenordner; externe Speicher bekommen ihren Crawl erst mit der Klassifikation.
- admissible kennt noch keine Ausschlüsse (Plan 16); bis dahin greift der Ausschluss vor dem ersten Durchlauf nur, weil die Abnahme das Backend erst nach den Ausschlüssen registriert und Plan 16 vor dem ersten Abnahmelauf (Plan 17) kommt.

## Self-Check: PASSED

- FOUND: SchedulerJob.php, StorageCrawlJob.php, StorageCrawlJobTest.php, SchedulerJobTest.php
- FOUND: 90d35f7, ecb4fbe, 41104c9
