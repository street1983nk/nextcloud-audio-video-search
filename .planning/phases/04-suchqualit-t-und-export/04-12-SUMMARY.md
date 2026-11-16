---
phase: 04-suchqualit-t-und-export
plan: 12
subsystem: php-export
tags: [export, sidecar, vtt, exp-03, srch-04, csrf, lock, gate-regel-20]
requires:
  - "04-10 (ExportController mit resolve, DownloadPolicy::allowsExport, downloadName, withNote, Gate-Regel 19)"
provides:
  - "SidecarWriter::write(Folder, name, content): CREATED/EXISTS/BUSY/NOT_WRITABLE, nodeExists vor newFile unter LOCK_EXCLUSIVE avs-sidecar/<storageId>/<sha1(Zielpfad)>"
  - "ExportController::sidecar: POST /sidecar/{fileId} mit CSRF, UserRateLimit 10/60, Antworten 201/409 {name}, 403 {reason: blocked|not_writable}, 400 {reason: name_too_long}, 404/503 {}"
  - "Gate-Regel 20 (newFile nur im SidecarWriter, Sperre vor nodeExists vor newFile, sidecar ohne NoCSRFRequired); Regeln 14 und 19 auf sidecar erweitert"
affects: [04-11, 04-13, 04-14, 04-17]
tech-stack:
  added: []
  patterns:
    - "Eigene Existenzprüfung unter App-Sperre statt Folder::newFile (überschreibt still) und statt getNonExistingName (D-04-05)"
    - "isCreatable und newFile innerhalb ReaderContext::actAs als Nutzer (Quota, Team-Folder-ACL, files_accesscontrol)"
key-files:
  created:
    - php/lib/Service/SidecarWriter.php
    - php/tests/Unit/SidecarTest.php
  modified:
    - php/lib/Controller/ExportController.php
    - php/tests/Unit/ExportControllerTest.php
    - backend/tests/test_php_gates.py
decisions:
  - "BUSY (Sperre belegt) antwortet wie EXISTS mit 409 und Namen: dieselbe Wahrheit, nichts wurde geschrieben"
  - "isCreatable, das selbst wirft, zählt als nein (fail closed, 403 not_writable); jede andere Ausnahme beim Schreiben (Elternordner weg, Speicherfehler, Backslash im Mediennamen) wird 503 {} (E7), Log nur fileId und class"
  - "Die 255-Byte-Grenze steht als SidecarWriter::MAX_NAME_BYTES an einer Stelle; der Controller antwortet 400 vor dem Schreiben, der Writer wirft bei Verletzung (Programmierfehler)"
metrics:
  duration: "ca. 40 min (inkl. abgebrochenem Vorgänger)"
  completed: 2026-11-16
---

# Phase 4 Plan 12: Nebendatei ablegen, nie überschreiben Summary

POST /sidecar/{fileId} legt `<Name>.<de|en|fr>.vtt` als Nutzer neben das Medium; eine eigene exklusive Sperre umschließt Existenzprüfung und Anlegen, sodass `Folder::newFile` nie für einen vorhandenen Namen gerufen wird; Download-Sperre (auch unentscheidbar) gibt 403 blocked vor Ausschluss und Container.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | SidecarWriter schreibt nie über eine vorhandene Datei | c182451 |
| 2 | POST /sidecar/{fileId} mit allen Prüfungen und Gate-Regel 20 | b93f5f3 |

## Ergebnisse

- `SidecarWriter` (neu): Name nur geprüft (nicht leer, kein `.`/`..`, kein `/` oder `\`, höchstens 255 Bytes), sonst `InvalidArgumentException`. `acquireLock(LOCK_EXCLUSIVE)` -> `nodeExists` -> ggf. `newFile` -> `releaseLock` in `finally`. `LockedException` -> BUSY, `NotPermittedException` aus newFile -> NOT_WRITABLE. Sperrschlüssel ohne lesbaren Pfad (sha1), Log nur `class`.
- `ExportController::sidecar`: Reihenfolge resolve (404 {}) -> allowsExport (403 blocked) -> reload + isExcludedUser/isExcludedFile, Fehler = ausgeschlossen (404 {}) -> isCreatable des Elternordners in actAs (403 not_writable) -> searchAllowed (503 {}) -> export(uid, fileId, 'vtt') (null 503 {}, known false 404 {}) -> downloadName (> 255 Bytes 400 name_too_long) -> withNote(body, noteSafe([T35, ggf. T15])) -> write in actAs: CREATED 201 {name}, EXISTS/BUSY 409 {name}, NOT_WRITABLE 403 not_writable. Kein NoCSRFRequired. Keine Aktualisierung, kein Vergleich, kein Veraltungs-Hinweis (D-04-08).
- PHPUnit (`ExportControllerTest`, läuft in CI): 201 mit vollständigem Inhaltsbeleg (`WEBVTT\n\nNOTE\n` + T35 + T15 + Cues), zweiter Aufruf 409 mit demselben Namen und sha256 unverändert (newFile genau einmal), fremde Datei gleichen Namens 409 byte-gleich (newFile nie), BUSY 409 ohne Schreiben, gesperrt 403 blocked ohne Container, Kombifall gesperrt+ausgeschlossen byte-gleich zu gesperrt mit Ausschlüssen nie gefragt, unlesbares Attribut ebenso, isCreatable false 403 not_writable ohne Container, NotPermitted tief im Speicher 403 not_writable, 400 bei 259 Bytes mit Positivkontrolle bei genau 255 Bytes, 404 byte-gleich für ausgeschlossen, unbekannt und unlesbar, 503 byte-gleich für Drift und stillen Container, Attribut-Test der Route (POST, `\d+`, 10/60, kein NoCSRFRequired/PublicPage/ExAppRequired).
- Gate-Regel 20 mit Selbsttest (zweiter Ersteller, Aufruf im Kommentar zählt nicht, fehlende Prüfung, fehlende Sperre, kein Anlegen, NoCSRFRequired); Regeln 14 und 19 samt Selbsttests auf `sidecar` erweitert.

## Signatur-Befund (OCP, raw.githubusercontent.com nextcloud/server)

- `ILockingProvider` stable33 und stable34 identisch: `LOCK_EXCLUSIVE = 2`, `acquireLock(string $path, int $type, ?string $readablePath = null): void`, `releaseLock(string $path, int $type): void`; entspricht dem Plan.
- stable34: `LockedException::__construct(string $path, ?\Exception $previous = null, ...)`, `DataResponse::__construct(mixed $data = [], int $statusCode = Http::STATUS_OK, array $headers = [])`, `Folder::nodeExists($path)`, `Folder::newFile($path, $content = null)`, `Folder::isCreatable()`, `Node::getParent()`, `Node::getInternalPath()`, `ICache::getNumericStorageId()`.

## Verifikation

- `uv run pytest tests/test_php_gates.py` 49 passed; volle Backend-Suite 2249 passed, 15 skipped, 4 xfailed (vorher 2247 + 2 neue Regel-20-Tests).
- ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture grün.
- `grep -rn -- "->newFile(" php/lib` trifft nur `SidecarWriter.php`; `test_rule20` und `test_self_rule20` vorhanden; Route und `UserRateLimit(limit: 10, period: 60)` per grep belegt.
- PHPUnit läuft erst in CI (kein lokales PHP).

## Deviations from Plan

Keine inhaltlichen. Task 2 stammte aus dem Arbeitsbaum eines abgebrochenen Vorgänger-Executors; er wurde gegen Behavior und Acceptance Criteria geprüft, ohne Lücke befunden und unverändert committet. Ergänzungen über den Plan hinaus, alle im Sinn von Rule 2:

- **[Rule 2] isCreatable-Ausnahme fail closed:** wirft die Frage selbst, antwortet die Route 403 not_writable statt einer unbehandelten Ausnahme.
- **[Rule 2] Restausnahmen beim Schreiben:** alles außerhalb der vier Writer-Ergebnisse (z. B. Backslash im Mediennamen, der in Nextcloud erlaubt ist, aber kein Nebendatei-Name) wird 503 {} (E7), Log nur fileId und class.

## Threat Flags

Keine neuen Flächen außerhalb des Threat-Registers (T-04-36 bis T-04-43); T-04-42 (Wettlauf mit fremdem Client) bleibt akzeptiert und wird in Plan 04-13 in SECURITY.md geführt.

## Known Stubs

Keine. Der Knopf auf der Abspielseite wird in Plan 04-11 freigeschaltet.

## Self-Check: PASSED

- FOUND: php/lib/Service/SidecarWriter.php, php/tests/Unit/SidecarTest.php, php/lib/Controller/ExportController.php
- FOUND: c182451, b93f5f3
