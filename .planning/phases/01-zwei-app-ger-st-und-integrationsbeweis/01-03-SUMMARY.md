---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 03
subsystem: php-app
tags: [unified-search, appapi, gateway, recheck, occ, static-gates, phpunit]
requires:
  - "01-01 (PHP-Gerüst, Application::BACKEND_APP_ID, info.xml mit SampleCommand)"
provides:
  - "ExAppService: einziger AppAPI-Aufrufort, search/excerpt/sample/removeSample, Lockstep, searchAllowed"
  - "FileAccess: readableFile/readableNode/relativePath/ownerOf, einzige Stelle der Lesbarkeitsfrage"
  - "ReaderContext::actAs (Findling-Kopie)"
  - "GatewayController: OCS GET /files/{fileId}?userId= für den Container"
  - "Provider audio_video_search mit Zeitmarke, Play-Link und Testtreffer-Kennzeichen"
  - "occ audio_video_search:sample <fileId> [--at] [--user] [--remove]"
  - "backend/tests/test_php_gates.py: acht statische PHP-Regeln mit Selbsttests"
affects: [01-04, 01-05, 01-06, 01-07, 01-08, 01-11, 01-12]
tech-stack:
  added: []
  patterns:
    - "Containerantwort ist ein Vorschlag: Treffer auf fileId/startMs/excerpt/sample reduziert, Titel und Pfad nur aus dem geprüften Node"
    - "Lokaler Ersatz für fehlendes PHP: statische Gates mit Selbsttest je Regel und Anti-Vakuum-Untergrenze"
    - "Logkontext nur mit route/status/innerMs/fileId/count/exception, nie Pfad oder Name"
key-files:
  created:
    - php/lib/Service/ExAppService.php
    - php/lib/Service/ReaderContext.php
    - php/lib/Service/FileAccess.php
    - php/lib/Controller/GatewayController.php
    - php/lib/Search/Provider.php
    - php/lib/Command/SampleCommand.php
    - php/tests/Unit/ExAppServiceTest.php
    - php/tests/Unit/GatewayControllerTest.php
    - php/tests/Unit/ProviderTest.php
    - php/tests/Unit/SampleCommandTest.php
    - backend/tests/test_php_gates.py
  modified: []
key-decisions:
  - "Eigener Timeout SAMPLE_TIMEOUT_SECONDS = 120 s für /sample und /sample/remove (occ, niemand wartet; der Container liest und hasht die ganze Datei über das Gateway); Suche und Ausschnitt bleiben bei 1,5 s"
  - "Besitzerauflösung für occ als FileAccess::ownerOf, damit getFirstNodeById nur in FileAccess.php steht (Regel 4)"
  - "Logschlüssel route statt path in ExAppService, damit Regel 6 ($path nie im Logaufruf) ohne Ausnahme gilt"
  - "stale_rejected beim Anlegen ist SUCCESS mit Hinweis (kein Fehler, eine echte Stufe hat Vorrang); not_sample bei --remove ist FAILURE"
  - "Eine JSON-Liste statt eines Objekts gilt als fehlerhafte Antwort (Fall 4)"
requirements-completed: []  # PLAY-01: PHP-Hälfte steht, der Klick-Beweis auf die Zeitstelle folgt in CI (Plan 11/12)
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-06
  tasks: 2
  files: 11
---

# Phase 1 Plan 03: PHP-Hälfte des Suchtreffers Summary

Unified-Search-Provider `audio_video_search` mit Rechte-Recheck je fileId, Zeitmarke `m:ss · Ausschnitt` und Link auf `/apps/audio_video_search/play/{fileId}?t=SS.S`, dazu der einzige AppAPI-Aufrufort `ExAppService`, das Content-Gateway für den Container und der Debug-Saatbefehl `occ audio_video_search:sample` mit `--remove`.

## Ergebnis

- **Task 1:** `ExAppService` als reduzierte Findling-Kopie (vier stille Fehlerfälle, `MAX_BODY_BYTES`, `VERSION_PATTERN`, Lockstep mit `lockstep(?string): string`, `majorMinor(): ?string`, `ownVersion()`, `driftOnRecord()`, `searchAllowed()`), Vertrag `/search`, `/excerpt`, `/sample`, `/sample/remove` mit strenger Typ- und Bereichsprüfung. `ReaderContext` 1:1, `FileAccess` mit den drei statischen Methoden plus `ownerOf`. `GatewayController` mit `rejectForeignCaller()` gegen `audio_video_search_backend` als erster Anweisung, wortgleicher 404 für unbekannten Nutzer, fehlende Datei, Ordner und nicht lesbar, 422 bei `fopen`-Fehler, 500 ohne Pfad. `test_php_gates.py` mit acht Regeln, je einem Selbsttest und einer Untergrenze für den echten Baum.
- **Task 2:** `Provider` (`IFilteringProvider`, nur `BUILTIN_TERM`, Budget 2,5 s, Limit 25, Begriff auf 200 Zeichen), Testtreffer nur bei `debug => true` und `sample_visible`, Kennzeichen `Test result`, Attribute `fileId` und `path` immer zusammen. `SampleCommand` mit `--at` (0 bis 86400 s, höchstens drei Nachkommastellen, exakt in ms umgerechnet), `--user`, `--remove` (nicht mit `--at`), Debug-Pflicht für beide Wege, keine Pfade in der Ausgabe.
- phpunit-Fälle: ExAppServiceTest 21, GatewayControllerTest 10, ProviderTest 18, SampleCommandTest 15; sie laufen erst in CI (`php.yml`), lokal gibt es kein PHP.

Gates in `backend/`: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture leer, pytest 208 passed (davon 17 in test_php_gates.py). RED-Nachweis: test_php_gates.py war vor Task 1 rot (Anti-Vakuum: ExAppService.php fehlte).

## Task Commits

1. **Task 1 RED:** `b4c18f3` (test) statische PHP-Gates, ExAppServiceTest, GatewayControllerTest
2. **Task 1 GREEN:** `6293625` (feat) ExAppService, ReaderContext, FileAccess, GatewayController
3. **Task 2 RED:** `8089d37` (test) ProviderTest, SampleCommandTest
4. **Task 2 GREEN:** `39f2c76` (feat) Provider, SampleCommand

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 1,5 s Timeout hätte jeden echten Saataufruf abgebrochen**
- **Found during:** Task 1
- **Issue:** Der Vertrag nennt 1,5 s für alle Aufrufe; `/sample` lässt den Container die ganze Datei über das Gateway lesen und hashen, das dauert bei echten Aufnahmen viel länger.
- **Fix:** `SAMPLE_TIMEOUT_SECONDS = 120.0` nur für `/sample` und `/sample/remove` (occ, kein Suchdialog wartet). Suche und Ausschnitt bleiben bei `REQUEST_TIMEOUT_SECONDS = 1.5`. Plan 05 sollte den Container-Endpunkt entsprechend bemessen.
- **Commit:** 6293625

**2. [Rule 3 - Blocking] Widerspruch Regel 4 gegen SampleCommand-Vorgabe**
- **Issue:** Der Plan verlangt `IRootFolder::getFirstNodeById` im SampleCommand, Regel 4 erlaubt den Aufruf nur in `FileAccess.php`.
- **Fix:** `FileAccess::ownerOf(IRootFolder, int): ?string`; der Befehl fragt danach trotzdem `readableFile` im Ordner des Nutzers.
- **Commit:** 6293625

**3. [Rule 3 - Blocking] Logschlüssel `path` gegen Regel 6**
- **Issue:** Findling loggt `'path' => $path` (Container-Route). Regel 6 verbietet `$path` in Logaufrufen.
- **Fix:** Variable und Schlüssel heißen in ExAppService `route`.
- **Commit:** 6293625

**4. [Rule 1 - Bug] Write-Werkzeug schrieb `U+2013`-Escapes als echte Zeichen**
- **Issue:** In test_php_gates.py landeten echte U+2013/U+2014 statt Escapes (ruff RUF001, hätte auch das Strich-Gate verletzt).
- **Fix:** per Skript auf `U+2013`, `U+2014`, `·`, `…` zurückgesetzt, vor dem Commit von Task 1.
- **Commit:** 6293625

Weitere kleine Ergänzungen: `FileAccess::readableFile` lehnt `fileId <= 0` ohne Lookup ab; Provider lässt mehrere Zeitstellen einer Datei als eigene Einträge stehen (eigenes `t`, Web-Client dedupliziert über `resourceUrl`); Gateway-Test für den Findling-Backend-Namen als fremden Aufrufer.

## Known Stubs

- Die Route `audio_video_search.page.play` entsteht erst mit dem PageController (Plan 04). Bis dahin würde `linkToRouteAbsolute` in einer echten Instanz scheitern; die Unit-Tests doublen den URL-Generator. Der Provider-Name und `Test result` haben noch keine DE/FR-Übersetzung, die kommt mit `php/l10n/` in Plan 04.

## Threat Flags

Keine neue Fläche außerhalb des Bedrohungsmodells: Gateway (T-01-11/12), Provider (T-01-10/13/15) und SampleCommand (T-01-14) sind dort erfasst und umgesetzt.

## Next Phase Readiness

- Plan 05 implementiert die Container-Gegenseite exakt nach dem Vertrag in `ExAppService` (Kopfkommentar), inklusive `appVersion` in `/search`.
- Plan 07 erweitert `searchAllowed()`.
- phpunit-Lauf in CI ist der erste echte PHP-Syntax- und Verhaltensbeweis für diesen Plan.

## Self-Check: PASSED

- Dateien vorhanden: alle elf unter key-files.created
- Commits vorhanden: b4c18f3, 6293625, 8089d37, 39f2c76
