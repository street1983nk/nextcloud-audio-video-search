---
phase: 02-erfassung-aller-dateien
plan: 03
subsystem: php-erfassung
tags: [queue, claim, mountmenge, migration, disc-01, disc-04]
requires: []
provides:
  - "Migration Version000200Date20261107000000: oc_avs_queue (id, kind, file_id NULL, storage_id, enqueued_at, locked_at NULL, lock_token, dirty, attempts; eindeutig kind+file_id+storage_id), oc_avs_crawl (storage_id, root_id, last_file_id, generation, started_at, finished_at), oc_avs_storage (capturable Standard 0)"
  - "QueueMapper: KINDS (exclude_storage, exclude, delete, trash, restore, content, metadata), LOCK_TIMEOUT 900, MAX_BATCH 256, enqueue(kind, ?fileId, storageId), claim(limit, token), rowsOfToken, acknowledge(token, ids), unlock(token, ids), drop(token, ids), openByKind()"
  - "CrawlMapper: upsert, advance, finish, reset, find"
  - "StorageService: HOME_MOUNT_PROVIDERS, providers(), getMounts(), mountRoots(), inMountSet(), mountRelativePath(), getFileSlice(storageId, rootId, afterFileId, limit): list<ICacheEntry>, allowedMimeIds()"
  - "QueueService: ITEM_KEYS (neun), admissible(storageId, mimeId, mountRelativePath), enqueue, claim, acknowledge, unlock, describe(token, rows), readerUid(storageId, fileId), stats()"
  - "QueueController: POST /ocs/v2.php/apps/audio_video_search/queues/media/claim|ack|unlock"
affects: [02-05, 02-06, 02-07, 02-11, 02-12, 02-14, 02-16, 02-19]
tech-stack:
  added: []
  patterns:
    - "Claim per bedingtem UPDATE mit einem Token je Claim über alle Kinds, Reihenfolge der Kinds als Vorrang"
    - "content und delete derselben file_id ersetzen einander (letztes Wort gewinnt), trash und restore ebenso"
    - "Mapper-Tests gegen die echte SQLite der Wegwerfinstanz; php.yml aktiviert die App vor der Suite"
    - "describe prüft admissible ein zweites Mal und löscht Verworfenes unter dem Claim-Token"
key-files:
  created:
    - php/lib/Migration/Version000200Date20261107000000.php
    - php/lib/Db/QueueMapper.php
    - php/lib/Db/CrawlMapper.php
    - php/lib/Service/StorageService.php
    - php/lib/Service/QueueService.php
    - php/lib/Controller/QueueController.php
    - php/tests/Unit/QueueMapperTest.php
    - php/tests/Unit/CrawlMapperTest.php
    - php/tests/Unit/StorageServiceTest.php
    - php/tests/Unit/QueueServiceTest.php
    - php/tests/Unit/QueueControllerTest.php
  modified:
    - .github/workflows/php.yml
decisions:
  - "avs_crawl.root_id ist die Laufwurzel (overridden_root aus getDistinctMounts, bei Homes der files-Ordner)"
  - "Spalte last_file_id statt cursor, weil cursor in MySQL/MariaDB reserviert ist"
  - "admissible verlangt zusätzlich einen Pfad unter der Laufwurzel (Papierkorb und Versionen liegen auf dem Home-Speicher, aber außerhalb)"
  - "Lösch- und Ausschluss-Kinds werden ohne Dateiabfrage ausgegeben; nur content, metadata und restore brauchen eine zulässige Datei"
  - "Leer- und Übergröße-Listen bei ack/unlock sind 400"
metrics:
  duration: "ca. 70 min"
  completed: 2026-11-07
  tasks: 2
  files: 12
---

# Phase 2 Plan 03: PHP-Warteschlange, Mountmenge und Queue-Routen Summary

Die PHP-App hat jetzt ihre drei Erfassungstabellen, eine Warteschlange mit bedingtem Claim, fester Sperrfrist von 900 s, dirty-Markierung und Kind-Vorrang, die Mountmenge aus Homes und Gruppenordnern mit Datei-Scheiben und audio/video-Filter, und die drei Queue-Routen, die bei der Ausgabe ein zweites Mal prüfen und genau neun Schlüssel ohne Pfade liefern.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Migration, Mapper und StorageService | 9a19937 | Migration, QueueMapper, CrawlMapper, StorageService, drei Tests, php.yml |
| 2 | QueueService und QueueController | f408af3 | QueueService, QueueController, zwei Tests |

## Prüfungen

- Lokal kein PHP: phpunit und `php -l` laufen erst in CI (php.yml, Push in Plan 11).
- test_php_gates.py 23 grün (Regel 1 Guard als erste Anweisung in claim, ack, unlock; Regel 4 getFirstNodeById nur in FileAccess; Regel 6 keine Pfade in Logs; Regel 7/8 Kopf und keine Gedankenstriche).
- Volle Python-Gates seriell grün: ruff, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 439 grün.
- OCP-Signaturen gegen stable33 per gh geprüft: IFileAccess (getDistinctMounts, getByAncestorInStorage, getByFileId, getByFileIdInStorage), ICacheEntry, ICachedMountInfo::getMountProvider, IUserMountCache::getMountsForStorageId, IDBConnection::insertIgnoreConflict.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Mapper-Tests brauchen die Tabellen**
- **Found during:** Task 1
- **Issue:** Ein Claim per bedingtem UPDATE lässt sich mit Query-Builder-Mocks nicht belegen; die Tests laufen gegen die echte SQLite der Wegwerfinstanz, deren Tabellen erst die Migration anlegt.
- **Fix:** php.yml aktiviert die App vor der Suite (`occ app:enable audio_video_search`) und prüft, dass oc_avs_queue existiert; die Tests brechen sonst mit klarer Meldung ab. Der Lauf belegt damit auch die Migration selbst.
- **Files modified:** .github/workflows/php.yml
- **Commit:** 9a19937

**2. [Rule 1] Spaltenname cursor reserviert**
- `cursor` ist in MySQL/MariaDB ein reserviertes Wort; die Spalte heißt `last_file_id`, die Methode `advance()` bleibt. Commit 9a19937.

**3. Zusätzliche Testdatei**
- CrawlMapperTest.php ist neu (nicht in der Dateiliste des Plans), weil CrawlMapper sonst ungeprüft bliebe.

## Known Stubs

- `describe` liefert `prefilterKey` immer null; den Freigabe-Schlüssel bildet Plan 12. Ohne Schlüssel gruppiert der Container keine Kopien: korrekt, nur ein Hash je Kopie mehr.
- `admissible` kennt noch keine Erfassbarkeit (Plan 12) und keine Ausschlüsse (Plan 16); `mountRelativePath` ist der Pfadraum dafür.
- avs_storage wird angelegt, aber erst in Plan 12 beschrieben.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new-route | php/lib/Controller/QueueController.php | drei neue ExApp-Routen; abgedeckt durch T-02-08 bis T-02-11 (ExAppRequired, EX-APP-ID-Vergleich, Token, Grenzen) |

## Self-Check: PASSED

- FOUND: alle elf neuen PHP-Dateien
- FOUND: 9a19937, f408af3
