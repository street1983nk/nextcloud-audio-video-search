---
phase: 02-erfassung-aller-dateien
plan: 08
subsystem: backend-erfassung
tags: [erfassung, temp-download, zustandsmaschine, disc-05, disc-06, d-02-13]
requires: [02-02, 02-05]
provides:
  - "nc.fetch_to_tempfile(file_id, user_id, tmp_dir, expected_size, max_bytes, *, client) -> FetchResult(sha256, size, error, head_sha256, status)"
  - "nc: FETCH_ERRORS (read_denied, access_control, excluded, locked, not_found, read_timeout, gateway_failed, size_mismatch, disk_full, too_large), HEAD_BYTES 65536, REASON_HEADER 'X-AVS-Reason', refusal_code(status, header), CAPTURE_TIMEOUT (connect 10 s, read 30 s), capture_deadline(size), free_bytes, remove_stale_parts"
  - "Store.next_capture(now), reset_fetching(), mark_keyed(claimed, sha256, head_sha256, now) -> media_id|None, mark_failed(claimed, reason, *, retry_at, bump, state, now), defer_capture(claimed, reason, *, retry_at, now), delete_ref(claimed, now)"
  - "worker/capture.py: Capture(services, *, directory, fetch, clock, max_bytes).prepare()/run_once()/run_forever(), CaptureOutcome, CaptureStep, retry_at(now, attempts_before, reason), tmp_dir(), MAX_ATTEMPTS 5, MAX_CAPTURE_BYTES 64 GiB"
  - "main.py: Hintergrundaufgabe capture im Lifespan; conftest no_capture"
affects: [02-09, 02-10, 02-13, 02-15, 02-16, 02-20]
tech-stack:
  added: []
  patterns:
    - "Claim per stage fetching; jedes Schreiben nach dem Download nennt etag, size, mtime des Claims, sonst stale ohne Schreiben"
    - "Grund eines 403/423 im Antwort-Header X-AVS-Reason, unabhängig vom OCS-Format (XML oder JSON)"
    - "Nur 200 mit exakt ref.size Bytes und gültigem Hex ist ein Erfolg; alles andere ist ein Code"
    - "Gesamtfrist je Download (120 s + Größe / 256 KiB/s) neben der Lesezeitgrenze"
key-files:
  created:
    - backend/src/audio_video_search_backend/worker/capture.py
    - backend/tests/test_capture.py
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
  modified:
    - backend/src/audio_video_search_backend/nc.py
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/main.py
    - backend/tests/conftest.py
    - backend/tests/test_main.py
decisions:
  - "Vertrag mit Plan 10/16: PHP nennt den Grund eines 403 (access_control, excluded) im Header X-AVS-Reason; 423 ist locked; 403 ohne bekannten Grund und 422 sind read_denied"
  - "mark_keyed nimmt den sha256 und legt media in derselben Transaktion an (statt media_id von außen), damit keine media ohne Verweis entsteht"
  - "Wartezeit nach Fehler: min(2^attempts_vorher * 60 s, 6 h), also 60/120/240/480 s, fünfter Fehlschlag ohne next_try_at; access_control fest 300 s"
  - "disk_full wie locked: zurück auf pending ohne Urteil (300 s); too_large: failed, state active, keine Wiederholung"
  - "Neue Verweise vor fälligen Wiederholungen (ORDER BY COALESCE(next_try_at, 0), file_id)"
  - "Jede andere Antwort als 200 (auch 3xx, 204, 206, 401, 412) ist gateway_failed, nie Inhalt"
metrics:
  duration: "ca. 70 min"
  completed: 2026-11-07
  tasks: 2
  files: 8
---

# Phase 2 Plan 08: Erfassung per Temp-Download mit Längenprüfung Summary

Jeder offene Verweis wird jetzt einmal über die eigene file_id und den eigenen Leser vollständig in eine Zufallsdatei unter `$APP_PERSISTENT_STORAGE/tmp` geladen, sha256 und Kopf-sha256 entstehen im Strom, und nur bei exakt `ref.size` Bytes hängt er an `media_key(file_sha256)`; jeder Lesefehler macht ihn sofort unreadable mit begrenzten Wiederholungen.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Temp-Download mit Hash und Längenprüfung | 0e14839 | nc.py, test_capture.py |
| 2 | Erfassungsstufe und Schleife | 8d2980e | worker/capture.py, store/repo.py, main.py, conftest.py, test_capture.py, test_main.py |

## Prüfungen

- test_capture.py 85 grün. Teil 1 (MockTransport): 200 KiB mit krummen Blockgrößen, Datei während des Stroms als `<32 hex>.part` unter tmp/ und danach weg, Kopf-Hash bei 0, 10 KiB, 64 KiB und 64 KiB + 1, zu kurz/zu lang/abweichende Content-Length (ohne Datei anzulegen), Abbruch im Strom, ReadTimeout, Gesamtfrist, Connect-/Pool-Timeout, Verbindungsfehler, Platzprüfung und Größendeckel ohne Request, 19 Status/Header-Kombinationen (403 mit/ohne Grund, 422, 423, 404, 500, 503, 401, 412, 302, 204, 206), keine Leser-ID und kein Pfad in eigenen Logzeilen.
- Teil 2 (echte state.db): pending nach keyed mit head_sha256 und proved_at; zwei Kopien gleicher Bytes mit gleichem Vorfilter-Schlüssel = zwei Downloads, eine media_id; verwaiste media nach Wiederanhängen ohne orphaned_at, Transkript (current) und Korrektur unverändert (D-02-13); 403, 422, 404, Timeout, 500, 302, access_control, zu kurz, zu lang über den echten fetch_to_tempfile: sofort unreadable/failed, attempts 1, next_try_at 60 bzw. 300 s, nicht in file_ids_for_media und nicht unter den aktiven Verweisen, obwohl ein Vorfilter-Geschwister keyed ist; fünf ungültige Erfolge (kein Hash, kein Kopf, Großbuchstaben-Hex, falsche Größe, unbekannter Code) nie keyed; Fetch-Ausnahme = gateway_failed; fällige Wiederholung mit Erfolg = active/keyed; fünf Fehlschläge 60/120/240/480/None, danach auch nach einem Jahr kein Versuch; Änderung danach startet neu; excluded löscht; locked auf unreadable-Verweis und auf neuem Verweis (pending, attempts gleich, +120 s); disk_full ohne Request (+300 s); too_large ohne Request; Änderung während des Downloads (stale) bei Erfolg und bei Fehler ohne Schreiben; vanished/trashed/sample nie geladen; neue vor fälligen; prepare löscht .part und setzt Claims zurück; drei gleichzeitige Schritte mit Höchstparallelität 1; Schleife nur bei companion ok, Fehler beendet sie nicht; keine Leser-ID in Logs.
- Positivkontrollen (Mutation, danach zurückgesetzt): Identitätsprüfung des Claims entfernt -> 2 rot; Größenprüfung in capture entfernt -> 1 rot; Längenprüfung in nc entfernt -> 2 rot; unreadable durch active ersetzt -> 17 rot; Grund-Header ignoriert -> 5 rot.
- Volle Python-Gates seriell grün: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 573 grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Sicherheit] Schreiben nur auf den unveränderten Claim**
- **Found during:** Task 2
- **Issue:** Ändert die Intake einen Verweis während des Downloads (neue Version), hätte das Ergebnis der alten Bytes den neuen Stand überschrieben (falscher Inhalts-Schlüssel, T-02-29) oder ihn fälschlich unreadable gemacht.
- **Fix:** next_capture setzt stage fetching; mark_keyed, mark_failed, defer_capture und delete_ref schreiben nur bei stage fetching und gleichem etag, size, mtime, sonst Ergebnis stale. Zwei Tests.
- **Commit:** 8d2980e

**2. [Rule 2] Gesamtfrist je Download**
- Eine Antwort, die alle 29 s ein Byte liefert, hätte den einzigen Erfassungsplatz unbegrenzt belegt (Lesezeitgrenze allein reicht nicht). Frist 120 s + Größe / 256 KiB/s, dann read_timeout. Commit 0e14839.

**3. [Rule 1] Nur 200 ist Inhalt**
- Der Phase-1-Strom wertet alles unter 400 als Inhalt; für die Erfassung gilt nur 200 (Umleitung, 204, 206 sind gateway_failed). Der alte Probe-Weg ist in deferred-items.md notiert, nicht geändert. Commit 0e14839.

**4. Schnittstelle mark_keyed**
- Plan nennt `mark_keyed(file_id, media_id, head_sha256)`; umgesetzt als `mark_keyed(claimed, sha256, head_sha256)`, damit Suchen/Anlegen der media und das Setzen am Verweis in einer Transaktion liegen. media_id wird weiter nur hier gesetzt (und in Plan 13 in attach_by_proof). Dazu die Hilfen reset_fetching und defer_capture.

**5. Vertrag Grund-Header**
- Der Plan sagt nicht, wie der Container "403 access_control" von "403 excluded" unterscheidet. Festgelegt: Header `X-AVS-Reason` (OCS übernimmt Header der DataResponse, BaseResponse stable33 per gh geprüft). Plan 10 setzt ihn für access_control und locked, Plan 16 für excluded.

## Known Stubs

- Der Inhalt wird nach dem Hashen gelöscht (wie geplant); die Temp-Datei für das Dekodieren behält erst Phase 3.
- Kein Anhängen über den Vorfilter, kein Lesebeweis, kein Sperrkreis je Speicher: Plan 13.
- Zählung (files/contents) für unreadable Verweise belegt Plan 09 mit coverage(); hier nur über file_ids_for_media und die Zahl aktiver Zeilen geprüft.
- REQUIREMENTS DISC-05/06 nicht abgehakt: erst nach Lesebeweis (Plan 13) und Abnahme (Plan 17/22), wie in den Plänen davor.

## Threat Flags

Keine neue Oberfläche über das Threat-Register hinaus (T-02-26 Länge == ref.size; T-02-27 Platzprüfung, finally, Aufräumen beim Start; T-02-28 erst vollständig laden; T-02-29 sha256 über alle Bytes, kein Vorfilter, Claim-Identität).

## Self-Check: PASSED

- FOUND: backend/src/audio_video_search_backend/worker/capture.py, backend/tests/test_capture.py
- FOUND: 0e14839, 8d2980e
