---
phase: 02-erfassung-aller-dateien
plan: 20
subsystem: container-abgleich
tags: [reconcile, sweep, walk, requeue, reproof, vanished]
requires: [02-15, 02-17, 02-19]
provides:
  - "Reconciler.run_once(reprove, force): Sweep vor dem Tor, Lesebeweis-Planung, Walk"
  - "nc_files.FileClient: Vertrag der vier Abgleich-Routen, nc.reconcile_request"
  - "Store.mark_vanished, mark_present, mark_reproof_due, remove_storages, reconcile_rows, mark_missing"
  - "POST /reconcile/run (ADMIN) für occ audio_video_search:reconcile [--reprove]"
  - "Gate: nur worker/intake.py ruft Store.apply_intake"
affects: [02-22]
tech-stack:
  added: []
  patterns:
    - "Abweichungen gehen über PHP requeue durch admissible, der Container trägt nie selbst ein"
    - "Löschen nur aus einer Mountliste, die ok und nicht leer ist, und nur nach classify"
key-files:
  created:
    - backend/src/audio_video_search_backend/nc_files.py
    - backend/src/audio_video_search_backend/worker/reconcile.py
    - backend/src/audio_video_search_backend/api/reconcile.py
    - backend/tests/test_reconcile_sweep.py
    - backend/tests/test_reconcile_walk.py
  modified:
    - backend/src/audio_video_search_backend/nc.py
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/worker/intake.py
    - backend/src/audio_video_search_backend/api/__init__.py
    - backend/src/audio_video_search_backend/main.py
    - backend/appinfo/info.xml
    - backend/tests/conftest.py
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
decisions:
  - "Speicher zurück in der Liste: mit Inhalt auf SMB/SFTP oder ohne bestandenen Beweis unreadable und probing (kein Treffer bis zum Beweis), wie nach dem Papierkorb; keyed ohne Beweispflicht active ohne Download"
  - "Ordner im Papierkorb: Verweise eines ganz durchlaufenen Speichers, die keine Scheibe trägt und seit Walk-Beginn unberührt sind, werden trashed; Rückkehr über requeue und _restore"
  - "Sweep zusätzlich sofort fällig, wenn ein Speicher die Liste verlässt oder zurückkommt (lokale Abfrage je Takt), sonst 24 h mit Stundenregel"
  - "Warteschlangen-Zustand für den Walk: stats.ok der letzten beantworteten Claim-Runde (intake.last_queue_ok), None ist kein Tor"
  - "Body von /reconcile/run wie alle Container-Routen mit extra=ignore, reprove StrictBool"
metrics:
  duration: "ca. 75 min"
  completed: 2026-11-14
  tasks: "2 von 2"
---

# Phase 2 Plan 20: Container-Abgleich Summary

Der Container gleicht alle 300 s seinen Stand mit der Mountliste der PHP-App ab: ein Sweep unter eigenem Stempel vor dem Walk (auch wenn der Walk blockiert ist), die Planung des erneuten Lesebeweises für SMB/SFTP und ein Walk über Mounts mit fertigem Erst-Crawl, der jede Abweichung über `POST reconcile/requeue` an die eine Vorprüfung zurückgibt. `POST /reconcile/run` macht das sofort, damit läuft jetzt `occ audio_video_search:reconcile [--reprove]` aus 02-19. Alles lokal, nichts gepusht.

## Task 1: Sweep vor dem Tor und Re-Proof-Planung

- `nc.py`: `reconcile_url` (nur vier Routen, Speicher-ID nur Ziffern), `reconcile_request` (GET/POST, nie Ausnahme beim Transport, Logs nur Routenart, Status, Fehlertyp), `new_reconcile_client` (keine Umleitungen).
- `nc_files.py`: strikte Modelle mit `extra="forbid"` (MountEntry, MountList, SliceFile, Slice, Classification, RequeueAnswer); `FileClient` mit classify und requeue in Bändern zu 256; jede Antwort außerhalb des Vertrags ist None.
- `worker/reconcile.py`: `Reconciler.run_once(reprove, force)`. Mountliste nicht ok, leer oder verworfen: nichts gelöscht, kein Stempel, kein Walk (`mounts_unavailable`, `mounts_empty`). Sweep: `mark_present` für gelistete Speicher, classify für fehlende; gone -> `remove_storages(cause gone)` (Verweise weg, Inhalt nur vorgemerkt), deselected -> `mark_vanished`, `vanished_since` älter als 30 Tage -> `remove_storages(cause vanished_expired)`; classify ohne Antwort: nichts gelöscht, kein Stempel (`classify_unavailable`). Stempel `storage_sweep_at`, `_cadence_due` aus Findling (24 h, Stunde 3, Ausweg bei 48 h).
- Lesebeweis-Planung jeden Takt: `mark_reproof_due` für active/keyed auf groupable Speichern mit `proved_at` älter als 7 Tage, `reprove` sofort für alle.
- `intake.last_queue_ok()`: stats.ok der letzten beantworteten Claim-Runde.

## Task 2: Walk über requeue, Route und Gate

- Walk nur über Mounts mit `crawlFinished` und `capturable`, Scheiben zu 1000, Vergleich mit `reconcile_rows`: unbekannt, andere (etag, size, mtime), anderer Speicher oder trashed -> requeue in Bändern zu 256; state.db bleibt unverändert. stats.ok false, eine fehlende Scheibe oder ein abgelehntes Band beenden den Walk ohne Stempel `walk_at`; der Sweep ist davon unberührt.
- Nach einem vollständigen Walk: `mark_missing` für Speicher, deren alle Mounts durchlaufen wurden (Ordner im Papierkorb, deferred items 02-18).
- `api/reconcile.py`: `POST /reconcile/run {"reprove": bool}` mit `force=True`, Antwort genau `RECONCILE_KEYS` in der Reihenfolge von ExAppService; 503 ohne Reconciler. `info.xml`: `^/reconcile/run$` POST ADMIN.
- `main.py`: Reconciler im Lifespan, `app.state.reconciler`, Task `file-reconcile`, Client beim Herunterfahren geschlossen; Schleife nur bei companion ok.
- Gate: AST-Suche im Paket, nur `worker/intake.py` ruft `apply_intake`; Selbsttest mit einem Aufruf in reconcile.py schlägt an.

## Prüfungen

Python-Gates (backend, seriell, vor jedem GREEN-Commit): `ruff check .` grün, `ruff format --check .` 76 unverändert, `pyright` (latest) 0 errors, `vulture` Exit 0, `pytest -p no:xdist -q` **1001 passed** (vorher 952); Plan-Verify `test_reconcile_sweep.py test_reconcile_walk.py test_store_metadata.py` 62 passed.

RED belegt: Task 1 Sammelfehler (Module fehlen), Task 2 17 failed / 7 passed (Gate, 401, Fälle ohne Walk).

Mutationen an HEAD (danach zurückgesetzt): Walk ohne crawlFinished-Filter -> 3 Tests rot; `mark_missing` ohne Zeitbedingung `updated_at < before` -> 11 Tests rot.

Kein PHP geändert, daher kein Container-Lauf (kein Docker gestartet).

## Commits

| Task | Commit | Inhalt |
|------|--------|--------|
| 1 RED | 4ea415b | test: Sweep, Stempel, gestörte Liste, gone/deselected/zurück, Lesebeweis, Vertrag |
| 1 GREEN | 72955be | feat(02-20): Sweep vor dem Tor und erneuter Lesebeweis im Abgleich |
| 2 RED | 37ce996 | test: Walk, Bänder, Papierkorb-Ordner, Route, Lifespan, Gate |
| 2 GREEN | 92013a7 | feat(02-20): Abgleich gibt Abweichungen an die Vorprüfung zurück |

## Deviations from Plan

**1. [Rule 2 - Datenschutz] Zurück aus vanished auf SMB/SFTP als unreadable statt active** (`Store.mark_present`): must_have 2 sagt "active, auf SMB/SFTP sofort stage probing". active plus probing gäbe Treffer bis zum Beweis und würde in `_CLAIM_CAPTURE` nicht vorgezogen. Umgesetzt wie der Owner-Entscheid vom 12.11.2026 für das Wiederherstellen (deferred items 02-15b hatte genau diese Frage an Plan 20 gestellt): unreadable und probing, Beweis zuerst. **OWNER-ENTSCHEID 14.11.2026** ("Ja, erst Beweis (Empfohlen)", AskUserQuestion der Hauptsitzung): bestätigt.

**2. [Rule 2] Ordner im Papierkorb: fehlende Verweise werden beiseitegelegt** (`Store.mark_missing`). Der Plan sagt "file_id in state.db, aber nicht in der Scheibe -> nichts"; das gilt weiter je Scheibe (Test `a_known_file_missing_from_one_slice_is_no_finding`). Der Auftrag der Hauptsitzung und deferred items 02-18/02-19 verlangen das Wegräumen im Container: nur Speicher, deren alle Mounts fertig gecrawlt und vollständig durchlaufen sind, nur active/unreadable, nur seit Walk-Beginn unberührt, als trashed (Inhalt vorgemerkt, kein Vergessen). Rückkehr über Scheibe, requeue, admissible und `_restore` ohne Download.

**3. Sweep zusätzlich ereignisnah fällig**: neben dem 24-h-Stempel läuft der Sweep im nächsten Takt, sobald ein Speicher mit Verweisen die Liste verlässt oder ein vanished Speicher zurückkommt (lokale Abfrage). Sonst bliebe ein gelöschter Nutzer bis zu 48 h stehen.

**4. Body von /reconcile/run mit `extra="ignore"`** wie alle Container-Routen (AppAPI-Muster); `reprove` StrictBool, fehlend oder kein bool -> 422. Den Fall "Zusatzfeld -> 422" im eigenen RED-Test vor GREEN auf `{"reprove": 1}` geändert.

**5. Warteschlangen-Zustand**: es gibt keine Stats-Route; der Walk liest stats.ok der letzten Claim-Antwort der Erfassung (`intake.last_queue_ok`). None (noch keine Antwort) ist kein Tor.

**6. Zusatzdateien** außerhalb files_modified: `nc.py` (einzige Datei mit HTTP-Client, test_boundary), `worker/intake.py`, `tests/conftest.py` (Schleife in Tests aus), deferred-items.md.

## Nachtrag 14.11.2026: Workflow (Owner-Entscheid "Ja, vor Push 9 (Empfohlen)")

- 29ce322 test(02-20): Gate-Regel in `test_discovery_workflow.py` (`RECONCILE_AFTER`): reprove, vanish und delete-user rufen direkt nach ihrer Operation `occ audio_video_search:reconcile` (reprove mit `--reprove`); Selbsttest je Phase. RED: 6 rot (Regel und Selbsttests).
- 7f323ec ci(02-20): `discovery-e2e.yml` ruft nach `vanish_cem` und `delete_dan` `./occ audio_video_search:reconcile`. Nicht lokal ausgeführt.
- Gates danach: ruff, ruff format (76), pyright 0, vulture 0, pytest **1004 passed**.

## Known Stubs

Keine. Die Lücke aus 02-19 (occ :reconcile ohne Container-Route) ist geschlossen.

## Offene Punkte

- CI: reprove sollte mit dem nächsten Push grün werden (occ :reconcile --reprove hat jetzt die Route). vanish und delete-user: Workflow ruft jetzt direkt nach der Operation `occ audio_video_search:reconcile` (siehe Nachtrag); Beleg folgt mit Push 9.
- POST /reconcile/run läuft den ganzen Walk in der Anfrage, Timeout von PHP 120 s (neue Zeile in deferred-items).
- STATE.md/ROADMAP.md nicht per gsd-sdk fortgeschrieben (Auftrag der Hauptsitzung).

## Threat Flags

Keine neue Fläche außerhalb des Threat-Modells. T-02-72 (requeue über PHP, Gate apply_intake mit Selbsttest), T-02-73 (Beweis alle 7 Tage und bei Rückkehr aus vanished), T-02-74 (ok false, leer, verworfen, classify ohne Antwort: nichts gelöscht, kein Stempel), T-02-75 (eigener Stempel, Test über zwei Takte) umgesetzt. Neue Container-Route `/reconcile/run` ist ADMIN in info.xml und hinter AppAPIAuthMiddleware.

## Self-Check: PASSED

- Dateien vorhanden: nc_files.py, worker/reconcile.py, api/reconcile.py, test_reconcile_sweep.py, test_reconcile_walk.py.
- Commits vorhanden: 4ea415b, 72955be, 37ce996, 92013a7.
