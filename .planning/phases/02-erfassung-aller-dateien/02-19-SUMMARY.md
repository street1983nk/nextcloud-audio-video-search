---
phase: 02-erfassung-aller-dateien
plan: 19
subsystem: php-abgleich, occ
tags: [reconcile, classify-absent, requeue, admissible, occ]
requires: [02-16, 02-17]
provides:
  - "GET /reconcile/mounts mit crawlFinished, capturable, external, groupable; ok false bei gestörter Liste"
  - "GET /reconcile/mounts/{storageId}/slice?root=&after=&limit= nur an Wanderwurzeln"
  - "POST /reconcile/storages/classify über StorageService::classifyAbsent"
  - "POST /reconcile/requeue durch QueueService::admissible und enqueue content"
  - "occ audio_video_search:reconcile [--reprove] über ExAppService::reconcileNow"
affects: [02-20, 02-22]
tech-stack:
  added: []
  patterns:
    - "Der Container trägt nie selbst ein: jede Abweichung geht über requeue durch die eine Vorprüfung"
    - "Speicher, Medientyp und Pfad kommen aus dem Cache-Eintrag, nie vom Aufrufer"
key-files:
  created:
    - php/lib/Controller/ReconcileController.php
    - php/lib/Command/ReconcileCommand.php
    - php/tests/Unit/ReconcileControllerTest.php
    - php/tests/Unit/ClassifyAbsentTest.php
  modified:
    - php/lib/Service/StorageService.php
    - php/lib/Service/ExAppService.php
    - php/appinfo/info.xml
    - php/tests/Unit/ExAppServiceTest.php
    - backend/tests/test_php_gates.py
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
decisions:
  - "classifyAbsent bekommt die Erfassbarkeit als Closure (QueueService::storageCapturable), weil StorageService den avs_storage-Stand nicht kennt; die Frage geht nur an Speicher der Mount-Menge"
  - "Scheibe nur an einer Wanderwurzel des Speichers (sonst 404), damit keine Scheibe in Papierkorb oder Versionen reicht"
  - "mounts bei jedem Lesefehler (Liste oder Flag) ok false mit leerer Liste und HTTP 200"
  - "requeue: Lesefehler je Datei = rejected; Fehler beim Einreihen = 500, damit der Container im nächsten Takt neu fragt"
  - "Gate-Regel 16 in test_php_gates.py hält requeue an admissible vor enqueue, nur content, kein enqueue außerhalb"
metrics:
  duration: "ca. 45 min (davon ca. 4 min Container)"
  completed: 2026-11-14
  tasks: "2 von 2"
---

# Phase 2 Plan 19: PHP-Routen des Abgleichs Summary

Vier ExApp-Routen geben dem Container Mountliste mit Flags, Scheiben (fileId, etag, size, mtime), eine Klassifikation gone/deselected/present aus oc_storages und eine Rückgabe abweichender Dateien, die je Datei-ID den Cache-Eintrag lädt, `QueueService::admissible` fragt und nur dann content einreiht; `occ audio_video_search:reconcile [--reprove]` löst einen Takt über `ExAppService::reconcileNow` aus. Alles lokal, nichts gepusht.

## Task 1: Mounts, Scheiben, Klassifikation, Requeue

- `ReconcileController` (final, OCS, Routen per Attribut, je Route `ExAppRequired` plus EX-APP-ID-Vergleich als erste Anweisung):
  - `mounts`: je Mount `storageId`, `rootId` (overridden_root, wie der Crawl), `crawlFinished` (CrawlMapper), `capturable` (QueueService), `external`, `groupable` (share_key_hash in avs_storage). Fehler beim Lesen: `{"ok": false, "mounts": []}`, Log nur Klasse.
  - `slice`: storageId, root, after, limit (1 bis 1000, Standard 500) streng geprüft (400); root muss Wanderwurzel des Speichers sein (404); `next` = letzte fileId einer vollen Scheibe, sonst null; mtime = storage mtime wie in describe; Lesefehler 500 ohne Detail.
  - `classify`: 1 bis 256 positive IDs (400 sonst), Antwort nur gone, deselected, present.
  - `requeue`: 1 bis 256 positive IDs; Cache-Eintrag, Medientyp-ID, Pfad unter der Wanderwurzel; unbekannt, außerhalb (Papierkorb), anderer Typ oder ausgeschlossen: rejected; zulässig: `enqueue(KIND_CONTENT, fileId, storageId des Eintrags)`.
- `StorageService::classifyAbsent(array, Closure)`: Bänder zu `ABSENT_LOOKUP_BAND` 200 über oc_storages; ohne Zeile gone, nicht in der Mount-Menge oder nicht erfassbar deselected, sonst present; nur positive, gefragte IDs, einmal, aufsteigend.
- Gate-Regel 16 (`test_php_gates.py`) mit Selbsttest an vier Mutationen.

## Task 2: occ :reconcile

- `ReconcileCommand`: `audio_video_search:reconcile [--reprove]`, ruft `reconcileNow(false|true)`, gibt `Reconcile skipped: <code>` (falls gesetzt) und je Zähler eine Zeile `key: n` aus; keine Antwort: `Backend not reachable.` und FAILURE. Texte englisch (occ).
- `ExAppService::reconcileNow(bool)`: POST `/reconcile/run` als erster Admin, `RECONCILE_TIMEOUT_SECONDS` 120; Antwort genau `RECONCILE_KEYS` (Vertrag aus Plan 20: swept, vanished, orphaned, walkedMounts, requeued, rejected, reproofDue, skippedReason), Zahlen >= 0, skippedReason null oder Grundcode, sonst null.
- `info.xml`: Befehl in `<commands>`.

## Container-Prüfung (PHP)

Vorprüfung 04:57Z: 4,85 GB frei, keine fremden Container; zweiter Lauf 05:00Z: 4,41 GB frei, keine fremden Container. Container `avs-phpcheck-19` zweimal gestartet und jeweils mit `docker rm -f avs-phpcheck-19` entfernt; `docker ps -a --filter name=avs-phpcheck-` danach leer. Kein fremder Container berührt, kein down, kein prune.

Umgebung: php:8.2-cli (PHP 8.2.33), nextcloud/server stable34 Commit 7f24f37e (34.0.6.2), 3rdparty 8e50d96, PHPUnit 11.5.57.

| Lauf | Stand | Ergebnis |
|------|-------|----------|
| a | bbddb9e (Task 1 RED) | 668 Tests, 41 Errors: ReconcileController fehlt (34), classifyAbsent fehlt (7); Bestand grün |
| b | 05120c4 (Task 2 RED) | 682 Tests, 14 Errors: reconcileNow fehlt (9), ReconcileCommand fehlt (5); Bestand grün |
| erster HEAD-Lauf | 8168544 | 682 Tests, 1 Failure: Testhelfer baute die erwartete Antwort in anderer Reihenfolge (assertSame); Fix 3787461 |
| Mutation | HEAD, requeue ohne admissible (`if (false)`) | 4 Failures: excluded, unbekannt/Typ/Papierkorb, gemischte Liste, Speicher aus dem Cache-Eintrag |
| HEAD | 3787461 | **OK (682 tests, 8121 assertions)** |
| php -l | HEAD, 68 Dateien | fails=0; Positivkontrolle Exit 255 |

Python-Gates (backend, seriell): `ruff check .` grün, `ruff format --check .` 71 unverändert, `pyright` (latest) 0 errors, `vulture` Exit 0, `pytest -p no:xdist -q` **952 passed**; `test_php_gates.py` + `test_store_metadata.py` 50 passed.

## Commits

| Task | Commit | Inhalt |
|------|--------|--------|
| 1 RED | bbddb9e | test: ReconcileControllerTest, ClassifyAbsentTest, Gate-Regel 16 |
| 1 GREEN | d206f63 | feat(02-19): Abgleich-Routen mit Rückgabe an die Vorprüfung |
| 2 RED | 05120c4 | test: ReconcileCommand, reconcileNow |
| 2 GREEN | 8168544 | feat(02-19): Abgleich per occ auslösbar |
| Testfix | 3787461 | test: Reihenfolge der Antwort im Testhelfer |

## Deviations from Plan

**1. [Rule 2] Gate-Regel 16 in `backend/tests/test_php_gates.py`** (nicht in files_modified): hält den key_link requeue -> admissible statisch fest (T-02-69), lokal ohne PHP prüfbar, mit Selbsttest.

**2. [Rule 3] `ExAppServiceTest.php` erweitert** (nicht in files_modified): Tests für `reconcileNow` gehören zur Klasse des Dienstes; die Befehlstests stehen wie geplant in ReconcileControllerTest.

**3. [Rule 1] Testhelfer korrigiert** (3787461): `$override + [...]` stellte skippedReason nach vorn, `assertSame` vergleicht die Reihenfolge; jetzt `array_replace`. Produktcode unverändert.

**4. classifyAbsent mit Closure-Parameter**: der Plan nennt "nicht capturable deselected" in classifyAbsent; StorageService kennt avs_storage nicht, QueueService soll nicht geändert werden. Der Controller reicht `QueueService::storageCapturable` als Closure hinein.

## Known Stubs

- `occ audio_video_search:reconcile` ruft `/reconcile/run` des Containers; die Route baut Plan 20. Bis dahin antwortet der Container 404 und der Befehl meldet `Backend not reachable.` (FAILURE). Gewollt, Plan 20 schließt das.

## Offene Punkte

- Ordner in Papierkorb/Wiederherstellen (deferred-items, Zeile 02-18): PHP-Seite steht (Scheiben nur an Wanderwurzeln, Rückgabe über requeue); Wegräumen und Zurückgeben im Container baut Plan 20. Zeile ergänzt.
- Regeln einmal je Prozess (deferred-items, 02-18): Web-Anfragen sind je Anfrage ein Prozess, die Abgleich-Routen sehen also immer die Regeln von jetzt.
- CI-Beleg (Instanz, E2E) folgt mit Plan 22 und einem freigegebenen Push.
- STATE.md/ROADMAP.md nicht per gsd-sdk fortgeschrieben (Auftrag der Hauptsitzung).

## Threat Flags

Keine neue Fläche außerhalb des Threat-Modells. T-02-69 (requeue über admissible, Gate-Regel 16, Mutationsbeleg), T-02-70 (ok false, classifyAbsent), T-02-71 (ExAppRequired plus EX-APP-ID an allen vier Routen, Test 403) umgesetzt.

## Self-Check: PASSED

- Dateien vorhanden: ReconcileController.php, ReconcileCommand.php, ReconcileControllerTest.php, ClassifyAbsentTest.php.
- Commits vorhanden: bbddb9e, d206f63, 05120c4, 8168544, 3787461.
