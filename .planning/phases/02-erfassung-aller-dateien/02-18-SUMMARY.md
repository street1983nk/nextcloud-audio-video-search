---
phase: 02-erfassung-aller-dateien
plan: 18
subsystem: php-ausschluss, php-ereignisse, hintergrundjobs
tags: [exclusion, fingerprint, clearing-job, group-events, trash, restore]
requires: [02-15, 02-16, 02-17, 02-17b]
provides:
  - "SchedulerJob: Fingerabdruck-Vergleich mit applied_exclusion_fingerprint, Löschaufträge je Änderung"
  - "ExclusionClearJob: Teilbaum-Lauf je Mount über getFileSlice in Bändern zu 500"
  - "GroupEventListener: UserAddedEvent/UserRemovedEvent"
  - "Papierkorb: trash, restore, delete; Entscheidung am Cache-Eintrag in describe"
affects: [02-19, 02-20, 02-22]
tech-stack:
  added: []
  patterns:
    - "applied_* erst nach vollständigem Einreihen schreiben"
    - "Ereignisse fremder Apps per Klassennamen registrieren, nicht hinter class_exists"
key-files:
  created:
    - php/lib/BackgroundJobs/ExclusionClearJob.php
    - php/lib/Listener/GroupEventListener.php
    - php/tests/Unit/ExclusionClearJobTest.php
  modified:
    - php/lib/BackgroundJobs/SchedulerJob.php
    - php/lib/Service/ExclusionService.php
    - php/lib/Service/QueueService.php
    - php/lib/Listener/FileEventListener.php
    - php/lib/AppInfo/Application.php
    - php/tests/Unit/SchedulerJobTest.php
    - php/tests/Unit/ExclusionServiceTest.php
    - php/tests/Unit/FileEventListenerTest.php
    - php/tests/Unit/QueueServiceTest.php
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
decisions:
  - "Trashbin-Ereignisse per Name registriert statt hinter class_exists (Coordinator lädt den Autoloader von files_trashbin erst nach audio_video_search)"
  - "Unlesbare Regeln: keine Löschaufträge, applied bleibt stehen (die drei Prüfungen schließen ohnehin alles aus)"
  - "Kein applied-Stand vorhanden: alle geltenden Regeln gelten als neu (Datenschutz zuerst)"
  - "Vergleichslogik (changesSince, storageRuleCovers, groupListed) in ExclusionService, damit Gate-Regel 14 einen Ort behält"
  - "ExclusionClearJob plant bei einem Fehler denselben Band nach 300 s neu, statt die Kette zu beenden"
metrics:
  duration: "ca. 95 min (davon ca. 55 min Warten auf freien RAM und freie Docker-Umgebung)"
  completed: 2026-11-14
  tasks: "2 von 2"
---

# Phase 2 Plan 18: Nachträglicher Ausschluss, Gruppenwechsel und Papierkorb (PHP) Summary

Jede Änderung der Ausschlussregeln wird im SchedulerJob am Fingerabdruck erkannt und in exclude_storage, ExclusionClearJobs (exclude je Datei) oder Crawl-Neustarts übersetzt; Gruppenbeitritt und -austritt wirken sofort; Papierkorb und Wiederherstellen kommen als trash und restore beim Container an, und ein delete wird beim Ausgeben als trash erkannt, wenn die Datei-ID im Papierkorb liegt. Alles lokal, nichts gepusht.

## Task 1: Fingerabdruck-Vergleich und ExclusionClearJob

- `SchedulerJob::applyExclusionChanges` (nach der Bereitschaftsprüfung des Backends, vor der Crawl-Planung): `reload()`, Vergleich `ExclusionService::fingerprint` mit `applied_exclusion_fingerprint`; bei Abweichung `changesSince(applied_exclusions)`.
  - neu Nutzer, Gruppe, Speicherschalter: `exclude_storage` je Speicher, den `storageRuleCovers(added, …)` erreicht (Eigentümer laut `storageOwner`, D-02-11; Kopien anderer Nutzer derselben Freigabe unberührt).
  - neuer Präfix: ein `ExclusionClearJob` je Mount mit Cursor 0.
  - Rücknahme: `CrawlMapper::reset` (Cursor 0, generation + 1) für betroffene Mounts mit Crawl-Zeile, nicht für als Ganzes weiter ausgeschlossene; die Crawl-Planung desselben Laufs legt die Jobs wieder an. Kein exclude.
  - `applied_exclusions` und danach der Fingerabdruck erst nach allen Aufträgen; ein Fehler mittendrin lässt den Stand stehen, der nächste Lauf wiederholt (T-02-67).
- `ExclusionClearJob` (QueuedJob): Bänder zu 500 über `StorageService::getFileSlice`, Pfad über `StorageService::mountRelativePath`, Frage `ExclusionService::isExcluded` mit den Regeln von jetzt, `exclude` je Datei; Fortsetzung mit Cursor nach 30 s; als Ganzes ausgeschlossener Speicher wird nicht gelaufen; Fehler: derselbe Band nach 300 s. Logs nur Speicher-ID und Zahlen.
- `ExclusionService`: `snapshot`, `changesSince` (Nutzer ohne Groß/klein, unbrauchbarer applied-Stand gilt als keine Regel), `storageRuleCovers` (Zweifel erreicht den Speicher), `groupListed`, `reload`.

## Task 2: Gruppen- und Papierkorb-Ereignisse

- `GroupEventListener`: UserAdded in ausgeschlossene Gruppe: `exclude_storage` für die eigenen Speicher des Nutzers (Mount-Cache des Nutzers, `storageOwner`, nur Speicher der Mount-Menge). UserRemoved, nicht anders ausgeschlossen: Crawl-Neustart seiner Speicher (nur vorhandene Crawls, nicht als Ganzes ausgeschlossene) plus StorageCrawlJob. Fehler: nur Klasse im Log.
- `FileEventListener`: `MoveToTrashEvent` -> trash, `NodeRestoredEvent` -> restore (nicht zulässiges Ziel -> delete), `NodeDeletedEvent` bleibt delete. Kommentar zu Phase 8 (D-02-13).
- `QueueService::describeRow`: delete mit Datei-ID, deren Cache-Eintrag in einem Speicher der Mount-Menge außerhalb jeder Wanderwurzel liegt (files_trashbin, Papierkorb eines Gruppenordners), geht als trash hinaus (T-02-68); Eintrag weg, fremder Speicher oder Cache-Fehler: delete.
- `Application`: beide Trashbin-Ereignisse und UserAdded/UserRemoved registriert.

## Container-Prüfung (PHP)

Vorprüfung: 03:44Z 4,06 GB frei, fremde Container `nc35-*`, `nc_app_mcp_connector`, `nc-mcp-exapp-*` liefen (nicht angefasst). Neuprüfung alle 5 Minuten bis 04:40Z: 4,63 GB, keine fremden Container (danach 4,66 GB, `docker ps` leer). Start `avs-phpcheck-18`, danach `docker rm -f avs-phpcheck-18`; `docker ps -a --filter name=avs-phpcheck-` leer. Kein fremder Container berührt, kein down, kein prune.

Umgebung: php:8.2-cli (PHP 8.2.33), nextcloud/server stable34 Commit 7f24f37e7eee08a108b8356958a73ac09008f12c (34.0.6.2), 3rdparty 8e50d96, PHPUnit 11.5.57.

| Lauf | Stand | Ergebnis |
|------|-------|----------|
| a | 58cc5a9 (Task 1 RED) | 613 Tests, 44 Errors: ExclusionClearJob fehlt (8), neue ExclusionService-Methoden fehlen (12), SchedulerJobTest 24 (Konstante APPLIED_FINGERPRINT_KEY fehlt; setUp nutzt sie, darum auch die 10 Bestandstests rot) |
| b | f66145d (Task 2 RED) | 627 Tests, 6 Errors (GroupEventListener fehlt) und 6 Failures, genau die 12 neuen Tests; Bestand grün |
| Mutation | HEAD mit QueueService.php von f66145d | 627 Tests, 1 Failure: `testADeletionWhoseFileLiesInTheTrashBinIsHandedOutAsTrash` |
| HEAD | bcbe4c9 | **OK (627 tests, 7909 assertions)** |
| php -l | HEAD, 64 Dateien | fails=0; Positivkontrolle Exit 255 |

Python-Gates (backend, seriell): `ruff check .` grün, `ruff format --check .` 71 unverändert, `pyright` (latest) 0 errors, `vulture` Exit 0, `pytest -p no:xdist -q` **950 passed**; `test_php_gates.py` 35 passed.

## Commits

| Task | Commit | Inhalt |
|------|--------|--------|
| 1 RED | 58cc5a9 | test: SchedulerJob, ExclusionClearJob, ExclusionService |
| 1 GREEN | 3d42f95 | feat(02-18): Nachträglicher Ausschluss räumt den Arbeitsvorrat auf |
| 2 RED | f66145d | test: Gruppen, Papierkorb, describe, Registrierung |
| 2 GREEN | bcbe4c9 | feat(02-18): Gruppenwechsel und Papierkorb im Ereignisweg |

## Deviations from Plan

**1. [Rule 1 - Bug] Registrierung ohne class_exists**
- Plan: Trashbin-Ereignisse mit `class_exists`-Prüfung registrieren. stable34 `Coordinator::registerApps` registriert den Autoloader jeder App erst unmittelbar vor ihrem `register()`; files_trashbin kommt nach audio_video_search, `class_exists` wäre in `register()` immer false und beide Ereignisse fielen weg.
- Fix: per `::class`-Name registriert (lädt nichts, wie Findling), `instanceof` im Listener lädt ebenfalls nichts. Test `testTheApplicationListensToTheTrashBinAndToGroupChanges`.

**2. [Rule 3] ExclusionService erweitert** (nicht in files_modified): Gate-Regel 14 erlaubt Regelvergleiche nur dort; `storageFacts` (Mount-IDs) ist privat. Neue Methoden plus 12 Tests in ExclusionServiceTest.

**3. QueueServiceTest angepasst** (nicht in files_modified): Bestandstest "Removals are handed out without looking the file up" nimmt statt delete jetzt exclude (delete wird seit diesem Plan nachgeschlagen); zwei neue Tests für die Entscheidung am Cache-Eintrag.

**4. Gruppentests in FileEventListenerTest** (wie im Plan genannt), nicht in eigener Datei.

## Offene Punkte

- CI-Beleg fehlt: restore_no_download und exclude-*-after laufen erst mit einem freigegebenen Push und der Abnahme in Plan 22.
- Neue Zeilen in deferred-items.md: Ordner in Papierkorb/Wiederherstellen wirken nicht auf die Medien darin (Abgleich 19/20); Regeln einmal je Instanz in langlebigen Prozessen; zurückgenommener Präfix startet alle Crawls neu.
- STATE.md/ROADMAP.md nicht per gsd-sdk fortgeschrieben (Auftrag der Hauptsitzung).

## Threat Flags

Keine neue Fläche außerhalb des Threat-Modells. T-02-65 bis T-02-68 umgesetzt wie geplant.

## Self-Check: PASSED

- Dateien vorhanden: ExclusionClearJob.php, GroupEventListener.php, ExclusionClearJobTest.php.
- Commits vorhanden: 58cc5a9, 3d42f95, f66145d, bcbe4c9.
