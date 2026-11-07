---
phase: 02-erfassung-aller-dateien
plan: 10
subsystem: php-gateway-occ
tags: [gateway, kopf-route, access-control, locked, occ, disc-01, disc-04, d-02-06]
requires: [02-03, 02-06, 02-08, 02-09]
provides:
  - "GatewayController: 403 access_control (OCP\\Files\\ForbiddenException), 423 locked (OCP\\Lock\\LockedException), Grund im Header X-AVS-Reason und im Feld code; HEAD_BYTES 65536, REASON_HEADER, REASON_ACCESS_CONTROL, REASON_LOCKED"
  - "GET /ocs/v2.php/apps/audio_video_search/files/{fileId}/head?userId= -> genau min(65536, Größe) Bytes, application/octet-stream, gleiche 404/422/403/423/500"
  - "ExAppService::workstock(array $query): ?array (GET /workstock), coverage(): ?array (GET /coverage), ADMIN_TIMEOUT_SECONDS 10, WORK_STATES, WORK_STAGES, WORKSTOCK_KEYS, COVERAGE_KEYS"
  - "CrawlMapper::progress(): {finished, open}"
  - "occ audio_video_search:files [--state] [--all] [--json] -> {files, next}"
  - "occ audio_video_search:status [--json] -> coverage-Felder + queue {ok, open} + crawl {finished, open}"
affects: [02-11, 02-12, 02-13, 02-16, 02-17, 02-21, 02-22]
tech-stack:
  added: []
  patterns:
    - "Ein privater Weg zur Datei (resolve mit actAs und readableFile) und eine Übersetzung der Fehler (failure) für Gateway und Kopf-Route"
    - "Ausnahmen mit Pfad in der Nachricht (Forbidden, Locked) nur als file_id plus Grund geloggt"
    - "Container-Antworten mit fester Schlüsselmenge (Reihenfolge egal) und geschlossenen Listen; ein Fehler verwirft die ganze Seite"
    - "Python-Gate liest die PHP-Konstanten und vergleicht sie mit repo.STATES/STAGES und den Wire-Schlüsseln"
key-files:
  created:
    - php/lib/Command/FilesCommand.php
    - php/lib/Command/StatusCommand.php
    - php/tests/Unit/FilesCommandTest.php
  modified:
    - php/lib/Controller/GatewayController.php
    - php/lib/Service/ExAppService.php
    - php/lib/Db/CrawlMapper.php
    - php/appinfo/info.xml
    - php/tests/Unit/GatewayControllerTest.php
    - php/tests/Unit/ExAppServiceTest.php
    - php/tests/Unit/CrawlMapperTest.php
    - backend/tests/test_api_routes.py
decisions:
  - "Der gemeinsame Auflöse-Helfer liegt privat im GatewayController (resolve), FileAccess bleibt unverändert die einzige Knotensuche"
  - "occ fragt den Container als erster aktiver Admin (ExAppService::firstAdmin), wie der Scheduler"
  - "files --json gibt {files, next} aus; mit --all alle Seiten in einer Liste und next null"
  - "Ein Lesefehler im Kopf (fread false oder Strom endet nie) ist 422 wie fopen false"
metrics:
  duration: "ca. 50 min"
  completed: 2026-11-07
  tasks: 2
  files: 11
---

# Phase 2 Plan 10: Gateway access_control/locked, Kopf-Route, occ :files/:status Summary

Das Gateway nennt files_accesscontrol und Dateisperren jetzt als eigene Codes (403 access_control, 423 locked im Header X-AVS-Reason, den der Container aus Plan 08 liest), die neue Kopf-Route liefert über denselben Rechteweg genau die ersten 64 KiB für den Lesebeweis, und `occ audio_video_search:files` sowie `:status` zeigen Arbeitsvorrat und "X of Y contents transcribed (N files)" in der Form, die compare.sh erwartet.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Gateway-Fehlercodes und Kopf-Route | 3969218 | GatewayController.php, GatewayControllerTest.php |
| 2 | occ :files und :status | a0d24d1 | FilesCommand.php, StatusCommand.php, ExAppService.php, CrawlMapper.php, info.xml, FilesCommandTest.php, ExAppServiceTest.php, CrawlMapperTest.php, test_api_routes.py |

## Prüfungen

- Lokal kein PHP (kein php im PATH): phpunit und `php -l` laufen erst in CI (php.yml, Push in Plan 11). Neue PHP-Fälle: GatewayControllerTest +16 (access_control an fopen und an der Suche mit Rücksetzen des Nutzers, locked, keine Header bei schlichter Ablehnung, Kopf: fremde EX-APP-ID ohne Suche, 200 KiB/64 KiB/10 KiB/leer exakt der Dateianfang mit Content-Type und geschlossenem Strom, Suche als Nutzer und fopen danach, gleiche 404 wie das Gateway für unlesbar/fehlt/unbekannter Nutzer, 422, 403, 423, 500 ohne Pfad, Logger sieht weder Pfad noch Nutzer); ExAppServiceTest +9 (GET als Admin mit Query und 10 s, Query außerhalb des Vertrags ohne Aufruf, kein Admin ohne Aufruf, 12 kaputte Seiten, feste Schlüssel und Listenreihenfolge, 6 kaputte coverage-Antworten inkl. transcribed > contents, unerreichbar); FilesCommandTest 10 (files und status); CrawlMapperTest +1 (progress).
- test_php_gates.py 27 grün (Regel 1: beide ExApp-Routen beginnen mit dem Guard; Regel 4, 6, 7, 8, 10, 13). Regel 10 schlug zuerst an (Helfer `run`/`status` überschatteten finale TestCase-Methoden) und ist behoben.
- Neuer Python-Vertragstest: WORK_STATES, WORK_STAGES, WORKSTOCK_KEYS und COVERAGE_KEYS aus ExAppService.php gleich repo.STATES/STAGES und Coverage.as_wire().
- OCP gegen stable33 per gh geprüft: OCP\Files\ForbiddenException($message, $retry, $previous), OCP\Lock\LockedException(string $path, ...), Http::STATUS_LOCKED 423, DataDisplayResponse($data, $status, $headers), BaseResponse übernimmt die Header der DataResponse, AppAPI hängt bei GET die Parameter als Query an.
- Volle Python-Gates seriell grün: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 606 grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] CrawlMapper::progress()**
- **Found during:** Task 2
- **Issue:** status braucht crawl {finished, open}; CrawlMapper hatte nur find je Mount.
- **Fix:** progress() mit COUNT(*) und COUNT(finished_at), Test gegen die echte DB. Datei nicht in der Plan-Liste.
- **Commit:** a0d24d1

**2. [Rule 2] Ausnahmen mit Pfad nicht loggen**
- ForbiddenException und LockedException tragen den Pfad in der Nachricht; beide werden nur mit file_id und Grund geloggt (der 500-Zweig bleibt wie in Phase 1). Commit 3969218.

**3. [Rule 2] Vertragstest PHP gegen Container**
- Die geschlossenen Listen stehen in Python und PHP; ein Python-Test liest die PHP-Konstanten, damit beide nicht auseinanderlaufen. Commit a0d24d1.

**4. [Rule 2] Seitenfolge muss vorrücken**
- files --all bricht ab, wenn next nicht wächst oder mehr als 10.000 Seiten kommen, statt endlos zu laufen. Commit a0d24d1.

**5. Testort**
- StatusCommand-Fälle stehen in FilesCommandTest.php (nur diese Testdatei nennt der Plan).

## Known Stubs

- status nennt noch keine skippedStorages (Plan 12); compare.sh liest das Feld optional.
- Die Kopf-Route nutzt erst der Lesebeweis in Plan 13; 403 excluded setzt Plan 16.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new-route | php/lib/Controller/GatewayController.php | Kopf-Route /files/{fileId}/head; abgedeckt durch T-02-32/T-02-33 (Guard als erste Anweisung, actAs, readableFile, höchstens 65536 Bytes, gleiche 404) |

## Self-Check: PASSED

- FOUND: php/lib/Command/FilesCommand.php, php/lib/Command/StatusCommand.php, php/tests/Unit/FilesCommandTest.php
- FOUND: 3969218, a0d24d1
