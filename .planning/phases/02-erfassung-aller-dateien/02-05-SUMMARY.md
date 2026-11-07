---
phase: 02-erfassung-aller-dateien
plan: 05
subsystem: backend-erfassung
tags: [intake, queue, ack-nach-commit, disc-01, disc-05, disc-06]
requires: [02-02, 02-03]
provides:
  - "nc_queue.py: KINDS, MAX_BATCH 256, ClaimItem (neun Schlüssel, strict, extra=forbid), ClaimStats (ok, open, dropped), ClaimAnswer, ClaimOutcome(answer, reachable, malformed), QueueClient(claim, ack, unlock, aclose)"
  - "nc.py: QUEUE_PATH, QUEUE_ACTIONS, QUEUE_TIMEOUT (connect 10 s, read 30 s), HttpClient, new_queue_client(), queue_post(client, action, body) -> (status, data)"
  - "store/repo.py: IntakeItem, INTAKE_KINDS {content, metadata}, Store.apply_intake(items) -> list[int]"
  - "worker/intake.py: Intake(services, queue, batch=100).run_once() -> IntakeResult(claimed, applied, acked, unlocked, malformed, queue_ok), run_forever(interval=30, sleep, rounds), Modulfunktion run_forever(services)"
  - "main.py: Hintergrundaufgabe intake im Lifespan, beim Stopp abgebrochen"
affects: [02-08, 02-09, 02-11, 02-15, 02-20]
tech-stack:
  added: []
  patterns:
    - "Commit zuerst, Ack danach; Wiederzustellung nach Sperrablauf schreibt denselben Endzustand"
    - "HTTP bleibt in nc.py (test_boundary); nc_queue.py hält nur Vertrag und Bänder"
    - "Kein Claim, solange companion.current() nicht ok ist (AppAPI antwortet 412 vor dem Aktivieren)"
    - "conftest ersetzt intake.run_forever durch einen Leerlauf, damit kein Test NEXTCLOUD_URL anfragt"
key-files:
  created:
    - backend/src/audio_video_search_backend/nc_queue.py
    - backend/src/audio_video_search_backend/worker/__init__.py
    - backend/src/audio_video_search_backend/worker/intake.py
    - backend/tests/test_intake.py
  modified:
    - backend/src/audio_video_search_backend/nc.py
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/main.py
    - backend/tests/conftest.py
    - backend/tests/test_main.py
decisions:
  - "Der Queue-Client hält einen eigenen httpx-Client, gebaut und benutzt in nc.py; nc_queue.py importiert keinen HTTP-Client (Grenze aus Phase 1)"
  - "etag, size, mtime und fileId dürfen bei delete/exclude/trash fehlen (PHP liefert dort null), sind aber für content, metadata und restore Pflicht"
  - "Unverändertes content aktualisiert nur Vorfilter-Schlüssel und Leser, Stufe, Zustand und media bleiben; metadata für eine unbekannte file_id legt den Verweis wie content an"
  - "Ein Band außerhalb des Vertrags wird weder eingetragen noch quittiert noch entsperrt; PHP liefert es nach 900 s erneut, der Zähler malformed steht im Log"
  - "Start erst bei companion ok statt eines eigenen Aktivierungsmerkers"
metrics:
  duration: "ca. 50 min"
  completed: 2026-11-07
  tasks: 2
  files: 9
---

# Phase 2 Plan 05: Intake mit Ack nach dem Eintrag Summary

Der Container holt Bänder aus der PHP-Warteschlange, prüft sie streng gegen den Neun-Schlüssel-Vertrag, schreibt content und metadata in einer Transaktion als Verweis in state.db und quittiert erst danach; alle anderen Kinds gehen entsperrt zurück, ein gescheiterter Commit entsperrt das ganze Band.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Queue-Client und apply_intake | a804cf8 | nc.py, nc_queue.py, store/repo.py, test_intake.py |
| 2 | Intake-Schleife mit Ack nach Commit | b52ebfd | worker/intake.py, worker/__init__.py, main.py, conftest.py, test_intake.py, test_main.py |

## Prüfungen

- test_intake.py 35 grün: neu, unverändert keyed, jede Abweichung (etag, size, mtime) pending ohne media mit orphaned_at, kein orphaned_at bei weiterer aktiver Kopie, metadata nur Vorfilter und Leser, fremde Kinds nicht eingetragen, Band zweimal gleich, ungültige Zeile rollt das Band zurück, Probe-Zeile wird echt; Vertrag (path, fremdes Kind, bool, file_id 0, Großbuchstaben-Hex, zu lange uid/etag, content ohne etag, acht Schlüssel), leeres PHP-Array, Zeitgrenzen, MockTransport für Claim mit path, Bänder zu 256, unerreichbare Warteschlange; Ack nur eingetragener IDs, Commit-Fehler, Absturz zwischen Commit und Ack, stats.ok false, Band außerhalb des Vertrags, volles Band sofort, Band nur entsperrter Kinds im Takt, kein Claim vor companion ok, Fehler beendet die Schleife nicht.
- test_main.py: der Lifespan startet die Intake mit den Services.
- Volle Python-Gates seriell grün: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 483 grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] HTTP-Aufrufe in nc.py statt in nc_queue.py**
- **Found during:** Task 1
- **Issue:** tests/test_boundary.py erlaubt httpx nur in nc.py; ein eigener httpx.AsyncClient in nc_queue.py hätte das Gate gebrochen.
- **Fix:** nc.py baut den Client (new_queue_client, QUEUE_TIMEOUT) und schickt die Anfrage (queue_post); nc_queue.py hält Vertrag, Bänder und den Client als nc.HttpClient.
- **Commit:** a804cf8

**2. [Rule 1] Dateifelder bei Lösch-Kinds optional**
- QueueService::describe liefert etag, size, mtime für delete/exclude/trash als null; ein Modell mit Pflichtfeldern hätte jedes solche Band verworfen. Pflicht nur für content, metadata, restore (Modell-Validator), Test mit delete-Zeile. Commit a804cf8.

**3. [Rule 1] stats.open als leeres PHP-Array**
- json_encode([]) ist eine Liste; der Validator macht daraus {}. Commit a804cf8.

**4. [Rule 3] Kein Claim in Tests**
- Der Lifespan startet die Intake; conftest ersetzt sie durch einen Leerlauf, sonst fragte jeder Lifespan-Test NEXTCLOUD_URL an. Commit b52ebfd.

## Known Stubs

- delete, trash, restore, exclude und exclude_storage werden entsperrt und kommen nach jedem Takt wieder (Plan 15 setzt sie um). Sie blockieren nichts, belegen aber bis dahin Claim-Plätze.
- Verweise bleiben auf stage pending; Laden, Lesebeweis und Hash baut Plan 08.

## Threat Flags

Keine neue Oberfläche über das Threat-Register hinaus (T-02-17 bis T-02-20 umgesetzt: extra=forbid mit path-Test, eine Transaktion mit Ack danach und Idempotenztest, Grenzen und Zeitgrenzen, fremde Kinds entsperrt).

## Self-Check: PASSED

- FOUND: nc_queue.py, worker/intake.py, worker/__init__.py, test_intake.py
- FOUND: a804cf8, b52ebfd
