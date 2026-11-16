---
phase: 04-suchqualit-t-und-export
plan: 10
subsystem: php-export
tags: [export, srt, vtt, txt, srch-04, exp-01, exp-04, download-policy, gate-regel-19]
requires:
  - "04-03 (Katalogschluessel T13 bis T35 in de, de_DE, en, fr)"
provides:
  - "DownloadPolicy: decide/allowsPlayback (fail-open wie Bestand) / allowsExport (fail-closed, UNKNOWN sperrt)"
  - "ExportController: GET /export/{fileId}/{format} (SRT/VTT/TXT, Name <Name>.<de|en|fr>.<ext>) und GET /track/{fileId} (text/vtt ohne Content-Disposition)"
  - "export_error.php: Fehlerseite D2 im App-Rahmen (T29, Grundtext je Fall, T30), nie JSON"
  - "ExAppService::export/exportMeta gegen den 04-09-Vertrag, EXPORT_TIMEOUT_SECONDS=30, EXPORT_MAX_BODY_BYTES=16 MiB"
  - "Gate-Regel 14 erweitert (download/track fragen Ausschluesse vor dem Container), neue Gate-Regel 19 (Sperre vor Ausschluss und Container, kein canDownload)"
affects: [04-09, 04-11, 04-12, 04-17]
tech-stack:
  added: []
  patterns:
    - "Sperre VOR Ausschluss: 403 T24 byte-gleich, gleich ob ausgeschlossen (kein Ausschluss-Orakel, T-04-29a)"
    - "call() mit maxBytes-Parameter: eigene Antwortgrenze je Route, Bestandsaufrufer unveraendert"
key-files:
  created:
    - php/lib/Service/DownloadPolicy.php
    - php/lib/Controller/ExportController.php
    - php/templates/export_error.php
    - php/tests/Unit/DownloadPolicyTest.php
    - php/tests/Unit/ExportControllerTest.php
  modified:
    - php/lib/Controller/PageController.php
    - php/lib/Service/ExAppService.php
    - php/tests/Unit/PlayControllerTest.php
    - php/tests/Unit/ExAppServiceTest.php
    - backend/tests/test_php_gates.py
decisions:
  - "UNKNOWN-Freigabe-Attribut sperrt den Export fail-closed mit derselben 403-T24-Seite wie BLOCKED (Plan-Vorgabe; die Abspielseite bleibt fail-open, weil WebDAV dort nachprueft)"
  - "track entfernt den Content-Disposition-Header, den DataDisplayResponse selbst setzt (inline), per addHeader(null): die Spur traegt gar keinen (D-04-18)"
  - "ExportController::resolve liefert [File, uid] statt [Folder, File, uid]: der Nutzerordner wird hier nicht gebraucht (Ablage kommt in 04-11/04-12)"
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-16
---

# Phase 4 Plan 10: PHP-Export mit Rechte-Pfad Summary

Export- und Spur-Routen mit Download-Sperre als eigenem Dienst: allowsExport wird vor den Ausschluessen und vor jedem Container-Aufruf gefragt (403 T24, fail-closed bei unentscheidbarem Attribut), Downloads heissen <Name>.<de|en|fr>.<ext> mit MIME laut Research, TXT-Kopf und VTT-NOTE tragen T35 und bei Teiltranskript T15, Fehler sind eine Seite im App-Rahmen statt JSON.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | DownloadPolicy herausziehen, Export fail-closed | 4fab54b |
| 2 | ExAppService::export und exportMeta mit eigenem Budget | 9087f1d |
| 3 | ExportController mit Download, Spur, Fehlerseite und Gate-Regeln | f2ca3f4 |

## Ergebnisse

- `DownloadPolicy` (neu): Inhalt von `PageController::downloadAllowed` verschoben, drei Konstanten ALLOWED/BLOCKED/UNKNOWN, Log nur fileId und class. PageController nutzt `allowsPlayback`, Bestandsverhalten unveraendert (PlayControllerTest-Faelle stehen).
- `ExAppService`: `export()` ruft `/export` mit `EXPORT_TIMEOUT_SECONDS = 30.0` und `maxBytes: EXPORT_MAX_BODY_BYTES = 16777216`; `exportMeta()` ruft `/export/meta` mit Suchbudget. Feldpruefung nach excerpt-Muster: known false verwirft alles; partial bool, untilMs >= 0, language nur de/en/fr, body String; Format ausserhalb srt/vtt/txt ohne Aufruf.
- `ExportController`: Pruefkette resolve -> allowsExport -> Ausschluesse (reload, Fehler = ausgeschlossen) -> searchAllowed -> export, identisch in download und track. 403 fuer gesperrt und gesperrt+ausgeschlossen byte-gleich (PHPUnit vergleicht Params UND gerenderte Seite); ausgeschlossen und known false byte-gleiche 404; nicht lesbar eigene 404 "This file is not available". `UserRateLimit(limit: 30, period: 60)` auf beiden Routen.
- Dateiinhalte: TXT Zeile 1 Dateiname (Steuerzeichen -> Leerzeichen), Zeile 2 T35, bei partial Zeile 3 T15 mit `Provider::clock(untilMs)`, Leerzeile, Text. VTT: `WEBVTT\n\nNOTE\n` + T35 [+ T15], NOTE-Zeilen mit `-->` oder Zeilenumbruch werden weggelassen und mit fileId geloggt. SRT byte-gleich zum Container.
- `export_error.php`: play.php-Kopf (`addStyle`), ein Banner `avs-banner--error` mit Icon `error`, Titel T29, Grundtext je Fall (geschlossene Liste im Template, alles ueber `$l->t()` aus den freigegebenen Katalogen), Aktion T30 auf die Abspielroute mit fileId und `?t=` (nur bei gueltigem startMs > 0). Keine neuen Katalogschluessel noetig.
- Gates: Regel 14 um `ExportController::download/track` erweitert (EXCLUSION_CHECKS + HIT_CHECKS, Selbsttest `test_self_rule14_fires_when_an_export_route_skips_the_exclusions_or_asks_them_late`); neue Regel 19 `test_rule19_the_export_path_asks_the_download_policy_before_the_exclusions_and_the_container` mit Selbsttests `test_self_rule19_fires_when_the_exclusions_come_first` und `test_self_rule19_fires_when_the_container_comes_first`; `canDownload(` kommt unter php/lib nicht vor (Kommentare nennen den Helfer ohne Klammer).

## Gate-Ergebnisse (lokal)

- pytest test_php_gates + test_trilingual + test_public_texts + test_ui_assets: 119 passed
- volle pytest-Suite: 2236 passed, 15 skipped, 4 xfailed (145 s, kein tantivy-Flake)
- ruff Vollsatz: All checks passed; ruff format: 128 files formatted; vulture: keine Funde
- pyright basic (PYRIGHT_PYTHON_FORCE_VERSION=latest): 0 errors, 0 warnings

## Verifikation PHP

- Kein `php` im PATH: `php -l` auf DownloadPolicy.php, ExportController.php und export_error.php konnte lokal nicht laufen; Syntax und PHPUnit laufen erst in CI (php.yml) beim naechsten freigegebenen Push.
- OCP-Signaturen gegen nextcloud/server stable34 (raw.githubusercontent) verifiziert: `DataDownloadResponse(string $data, string $filename, string $contentType, ...)`, `DataDisplayResponse(string $data = '', int $statusCode = 200, array $headers = [])` (setzt selbst `Content-Disposition: inline`), `DownloadResponse` (HeaderUtils::makeDisposition, ASCII-Fallback, / und \\ ersetzt), `UserRateLimit extends ARateLimit(int $limit, int $period)`, `Response::addHeader($name, null)` entfernt einen Header.

## Deviations from Plan

### Auto-fixed / Zusaetze

**1. [Rule 2] UTF-8-Pruefung des Export-body**
- **Found during:** Task 2
- **Issue:** Der Container ist ausserhalb der Vertrauensgrenze; ein body, der kein UTF-8 ist, wuerde in den Download durchgereicht.
- **Fix:** `ExAppService::export` prueft `mb_check_encoding($body, 'UTF-8')`, sonst null (Defense in depth zu T-04-32).
- **Files modified:** php/lib/Service/ExAppService.php
- **Commit:** 9087f1d

**2. [Rule 1] Content-Disposition der Spur**
- **Found during:** Task 3 (Signatur-Verifikation gegen stable34)
- **Issue:** `DataDisplayResponse` setzt im Konstruktor selbst `Content-Disposition: inline; filename=""`; der Plan verlangt die Spur ohne Content-Disposition.
- **Fix:** `addHeader('Content-Disposition', null)` nach der Konstruktion (entfernt den Header, stable34 verifiziert); PHPUnit prueft `assertArrayNotHasKey`.
- **Files modified:** php/lib/Controller/ExportController.php
- **Commit:** f2ca3f4

**3. Kleinere Formabweichung:** `ExportController::resolve` liefert `[File, uid]` statt des PageController-Tripels `[Folder, File, uid]`, weil der Nutzerordner in diesem Plan ungenutzt waere (Ablage folgt in 04-11/04-12). Pruefweg identisch (ReaderContext::actAs + FileAccess::readableFile, Gate-Regel 4).

## TDD Gate Compliance

Die Tasks tragen `tdd="true"`, lokal laeuft aber kein PHP: RED/GREEN kann nicht lokal ausgefuehrt werden. Tests und Umsetzung wurden je Task gemeinsam in dem einen Commit abgeschlossen, den der Plan in `<done>` vorgibt (refactor/feat/feat); der rote/gruene Nachweis der PHPUnit-Faelle faellt in CI beim naechsten freigegebenen Push an. Die Python-Gates (Regel 14/19 inkl. Selbsttests, die auf mutierten Quellen anschlagen) liefen lokal rot-auf-Mutation/gruen-auf-Bestand.

## Known Stubs

Keine. Die Abspielseite verlinkt die neuen Routen noch nicht (section.avs-export, track-Element): das ist der geplante Schnitt von 04-11/04-12, keine Luecke dieses Plans. Die Routen antworten bis zum Container-Plan 04-09 mit der 503-Seite T25 (searchAllowed/export null), was dem Vertragsverhalten entspricht.

## Threat Flags

Keine neuen Flaechen ausserhalb des Threat-Models: beide neuen Routen sind T-04-29 bis T-04-35 zugeordnet (Sperre vor Container, byte-gleiche Antworten, UserRateLimit, Logs nur fileId/class, Name nie an den Container).

## Offene Punkte

- PHPUnit und php -l erst in CI (kein lokales PHP); Push wartet auf Owner-Freigabe.
- EXPORT_TIMEOUT_SECONDS/EXPORT_MAX_BODY_BYTES sind Ausgangswerte; Plan 04-08 misst, Plan 04-09 gleicht per Test ab.

## Self-Check: PASSED

- Dateien vorhanden: DownloadPolicy.php, ExportController.php, export_error.php, DownloadPolicyTest.php, ExportControllerTest.php
- Commits vorhanden: 4fab54b, 9087f1d, f2ca3f4
