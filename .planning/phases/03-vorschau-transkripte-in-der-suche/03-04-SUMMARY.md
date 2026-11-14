---
phase: 03-vorschau-transkripte-in-der-suche
plan: 04
subsystem: php-queue
tags: [php, migration, avs_queue, origin, claim-vertrag, gates]
requires: []
provides:
  - "Migration Version000300Date20261114000000: Spalte avs_queue.origin (STRING 8, notnull, Standard crawl)"
  - "QueueMapper::ORIGIN_EVENT, ORIGIN_CRAWL, ORIGINS; enqueue(kind, fileId, storageId, origin = crawl)"
  - "claim/rowsOfToken liefern origin je Zeile"
  - "QueueService::ITEM_KEYS mit origin (zehn Schlüssel), describeRow verwirft unbekannte Herkunft"
  - "Gates 17 und 18 in backend/tests/test_php_gates.py"
affects: [03-11, 03-20]
tech-stack:
  added: []
  patterns:
    - "Gate als Funktion eines Quellbaums, Probe auf veränderter Kopie in tmp_path"
    - "assertPostConditions in den Listener-Suiten: jede content-Zeile jedes Falls trägt event"
key-files:
  created:
    - php/lib/Migration/Version000300Date20261114000000.php
  modified:
    - php/lib/Db/QueueMapper.php
    - php/lib/Service/QueueService.php
    - php/lib/Controller/QueueController.php
    - php/lib/Listener/FileEventListener.php
    - php/lib/Listener/CacheEventListener.php
    - php/lib/BackgroundJobs/StorageCrawlJob.php
    - php/lib/Controller/ReconcileController.php
    - php/tests/Unit/QueueMapperTest.php
    - php/tests/Unit/QueueServiceTest.php
    - php/tests/Unit/QueueControllerTest.php
    - php/tests/Unit/FileEventListenerTest.php
    - php/tests/Unit/CacheEventListenerTest.php
    - php/tests/Unit/StorageCrawlJobTest.php
    - php/tests/Unit/ReconcileControllerTest.php
    - backend/tests/test_php_gates.py
decisions:
  - "Ein Ereignis hebt auch eine geclaimte crawl-Zeile auf event (Abweichung vom Plan, siehe unten)"
  - "Die Spalte heißt origin; Sperrspalten sind locked_at/lock_token (der Plan nannte claim_token)"
  - "Andere Arten als content behalten den Standard crawl; der Container wertet ihre Herkunft nicht aus"
metrics:
  duration: "ca. 50 min"
  completed: 2026-11-14
  tasks: 2
  files: 16
---

# Phase 3 Plan 04: Herkunft event/crawl in avs_queue Summary

Die PHP-Warteschlange weiß jetzt, wer eine Zeile schrieb: Datei- und Cache-Ereignisse schreiben `event`, Erst-Crawl und Abgleich `crawl`; ein Ereignis hebt eine vorhandene crawl-Zeile auf `event`, nie umgekehrt, und der Claim gibt `origin` als zehnten Schlüssel an den Container.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 | fa7330d | feat(03-04): Herkunft event/crawl in der Warteschlange |
| 2 | db23966 | feat(03-04): Ereignisse und Crawl setzen ihre Herkunft |

Alle Commits lokal, Autor und Committer street1983nk <k.cherif@outlook.de>, nichts gepusht.

## Was gebaut wurde

- **Migration 0.3.0:** `hasTable`/`hasColumn`-Wächter, `origin` STRING(8), notnull, Standard `crawl`; vorhandene Zeilen werden crawl (niemand weiß mehr, ob ein Ereignis sie schrieb).
- **QueueMapper:** `ORIGINS = [ORIGIN_EVENT, ORIGIN_CRAWL]`, unbekannte Herkunft wirft `InvalidArgumentException('unknown queue origin')` vor jedem Schreibzugriff; Einfügen mit `origin`; im Konfliktzweig `liftToEvent` (`UPDATE ... SET origin = 'event' WHERE` gleicher Schlüssel `AND origin = 'crawl'`), nur wenn die neue Herkunft event ist; `rowsOfToken` liest origin mit.
- **QueueService:** `enqueue(..., origin = crawl)` reicht weiter; `ITEM_KEYS` zehn Schlüssel; `describeRow` setzt `origin` und verwirft eine Zeile mit Herkunft außerhalb von `ORIGINS` (landet in `dropped`, T-03-11).
- **Aufrufer:** FileEventListener (2 content-Aufrufe) und CacheEventListener (1) mit `ORIGIN_EVENT`, StorageCrawlJob und ReconcileController::requeue mit `ORIGIN_CRAWL`. delete, trash, restore, metadata, exclude bleiben beim Standard.

## Tests und Gates

- **pytest (backend):** 1123 passed (vorher 1121; +2 Gates mit je einer Probe-Funktion: Gate 17 und 18 samt Selbsttests, 41 auf 43 Tests in test_php_gates.py).
- ruff check, ruff format --check (80 Dateien), pyright (latest, 0 Fehler), vulture: grün.
- Plan-Prüfkommandos beider Tasks grün; `grep -c origin QueueMapper.php` = 16.
- **Positivkontrollen:**
  - Gate 17 auf dem Stand vor dem Plan (Quellen aus f678a5b in einem Scratch-Baum): alle vier Befunde (kein ORIGINS, enqueue ohne Prüfung, ITEM_KEYS ohne origin, describeRow ungeprüft).
  - Gate 17 auf veränderten Kopien in tmp_path: `ORIGINS = ['event']`, `ORIGINS = [self::ORIGIN_EVENT, 'urgent']`, Prüfung in enqueue ersetzt, origin aus ITEM_KEYS entfernt, Prüfung in describeRow ersetzt, leerer Baum: jede Probe genau mit ihrem Befund.
  - Gate 18 auf dem Stand vor Task 2 (fa7330d): fünf Befunde "no origin" (2 FileEventListener, 1 CacheEventListener, 1 StorageCrawlJob, 1 ReconcileController). Selbsttest: fehlende Herkunft, falsche Richtung in beide Richtungen, andere Art und auskommentierter Aufruf ohne Befund.
  - Werkzeuge an Probedateien: ruff check Exit 1, ruff format --check Exit 1, pyright Exit 1, vulture Exit 3; Probedateien entfernt.
- **PHPUnit:** nicht lokal (kein PHP auf dem Rechner); die neuen Fälle laufen erst in CI (Plan 03-20): QueueMapperTest +7 (Herkunft gespeichert/Standard, Claim trägt origin, event hebt crawl, crawl senkt event nicht, andere Art/Speicher unberührt, geclaimte Zeile kommt als event wieder, unbekannte Herkunft wirft und schreibt nichts), QueueServiceTest: Zehn-Schlüssel-Fall mit origin erweitert, +3 (Herkunft je Zeile, unbekannte Herkunft verworfen, enqueue reicht Herkunft weiter), je ein Herkunftsfall in FileEventListenerTest, CacheEventListenerTest, StorageCrawlJobTest; ReconcileControllerTest prüft die Herkunft im Tupel.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ereignis auf geclaimter crawl-Zeile ging als crawl verloren**
- **Found during:** Task 1
- **Issue:** Der Plan wollte nur ungeclaimte Zeilen heben (`claim_token IS NULL`). Eine geclaimte Zeile wird beim Ereignis aber dirty, die Quittung gibt sie frei, und der nächste Claim gibt sie erneut aus. Mit der Plan-Bedingung käme die geänderte Datei dann als crawl, gegen D-03-05 ("geänderte Dateien zuerst").
- **Fix:** `liftToEvent` hebt jede crawl-Zeile desselben Schlüssels, geclaimt oder nicht. Der laufende Claim ist dem Container schon beschrieben, also ändert das an ihm nichts; erst die erneute Ausgabe trägt event. Test `testAnEventOnAClaimedCrawlRowIsHandedOutAgainAsAnEvent` statt "geclaimte Zeile unberührt".
- **Files modified:** php/lib/Db/QueueMapper.php, php/tests/Unit/QueueMapperTest.php
- **Commit:** fa7330d

**2. Spaltennamen:** Der Plan nannte `claim_token`; die Tabelle hat `locked_at`/`lock_token` (Migration 000200). Durch Abweichung 1 entfällt die Bedingung ohnehin.

**3. Zusätzlich angepasst (nicht in files_modified):** `QueueController.php` (Kommentar "nine" auf "ten keys"), `QueueControllerTest.php` (Beispielzeile mit origin), `ReconcileControllerTest.php` (Tupel mit Herkunft). Gate 18 kam in Task 2 dazu, damit jeder content-Aufruf maschinell geprüft wird.

**4. Abnahmekriterium `grep -rn "KIND_CONTENT," php/lib | grep -v ORIGIN_`** liefert vier Zeilen, die keine enqueue-Aufrufe sind (KINDS-Liste und REPLACES im Mapper, NEEDS_FILE im Service). Das genaue Kriterium "jeder content-enqueue nennt eine Herkunft" prüft Gate 18 (alle 5 Aufrufe, Sollliste je Datei).

## Offene Punkte

- **Lockstep:** `ClaimItem` im Container ist `extra="forbid"`; bis Plan 03-11 lehnt der Container Claims mit `origin` ab. Beide Hälften erst zusammen in Plan 03-20 nach CI.
- **Versionssprung:** Die Migration läuft bei einem Upgrade erst, wenn info.xml die Version hebt (Lockstep-Plan); bei einer Neuinstallation in CI läuft sie sofort.
- **PHPUnit und php -l** erst in CI (Plan 03-20).

## Threat Flags

Keine neue Oberfläche außerhalb des Bedrohungsmodells. T-03-11 umgesetzt (Positivliste, Exception, describeRow verwirft), T-03-12 über Gate 17 und Lockstep-Hinweis, T-03-13 akzeptiert.

## Self-Check: PASSED

- Dateien vorhanden: php/lib/Migration/Version000300Date20261114000000.php, Gates 17 und 18 in backend/tests/test_php_gates.py.
- Commits vorhanden: fa7330d, db23966.
