---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 08
subsystem: container-companion
tags: [handshake, companion-state, status, sample-guard, plat-02]
requires:
  - "01-03 (GatewayController mit rejectForeignCaller, /sample über das Gateway)"
  - "01-05 (Container-Routen, Services.lock, nc.py als einzige nc_py_api-Grenze)"
  - "01-07 (Admin-Sektion liest appVersion, companion, sampleCount aus GET /status)"
provides:
  - "OCS GET /ocs/v2.php/apps/audio_video_search/api/v1/handshake -> {companionVersion}, nur für EX-APP-ID audio_video_search_backend, sonst 403"
  - "nc.fetch_handshake() -> (status|None, version|None), wirft nie"
  - "companion.py: CompanionState, check_once, refresh_if_stale (30 s), run_periodic (300 s), current, reset"
  - "GET /status in api/status.py mit app_id, version, appVersion, companion, companionVersion, schemaVersion, sampleCount, settings"
  - "/sample antwortet {error: companion_missing} ohne Gateway-Aufruf"
affects: [01-09, 01-11]
tech-stack:
  added: []
  patterns:
    - "Companion-Zustand im Modul gehalten; 404 = sofort missing, Netzfehler = unknown, drei Fehlschläge in Folge = missing, Antwort ohne gültige Version = unknown"
    - "Versionsprüfung im Container mit demselben Muster wie ExAppService VERSION_PATTERN"
    - "Endlose Hintergrundaufgabe wird im Lifespan vor stop_background gezielt abgebrochen, damit der Shutdown nicht die 5-s-Frist abwartet"
    - "conftest-Autouse: PHP-App antwortet in Tests mit 200/0.1.0, Zustand je Test frisch; kein Test erreicht NEXTCLOUD_URL"
key-files:
  created:
    - php/lib/Controller/HandshakeController.php
    - php/tests/Unit/HandshakeControllerTest.php
    - backend/src/audio_video_search_backend/companion.py
    - backend/src/audio_video_search_backend/api/status.py
    - backend/tests/test_handshake.py
  modified:
    - backend/src/audio_video_search_backend/nc.py
    - backend/src/audio_video_search_backend/main.py
    - backend/src/audio_video_search_backend/api/__init__.py
    - backend/src/audio_video_search_backend/api/sample.py
    - backend/tests/conftest.py
    - backend/tests/test_main.py
decisions:
  - "Bei unknown nach der einmaligen Prüfung arbeitet /sample weiter; nur bestätigtes missing sperrt, ein nicht erreichbares Nextcloud meldet dann das Gateway (gateway_failed)"
  - "/status behält die alten Felder app_id und version neben den neuen"
  - "Warnung nur beim Wechsel nach missing, Wechsel nach ok/unknown als info; extra nur companion, reason (answered/no_version/not_found/unreachable) und status"
metrics:
  duration: "ca. 15 min"
  completed: 2026-11-06
  tasks: 2
  files: 11
---

# Phase 1 Plan 08: Handshake und Companion-Zustand im Container Summary

Der Container fragt beim Start und alle 300 s die neue OCS-Handshake-Route der PHP-App, hält ok/missing/unknown samt companionVersion, meldet das mit appVersion, schemaVersion und sampleCount in `/status` und verweigert `/sample` mit `companion_missing`, solange die PHP-App fehlt.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Handshake-Route der PHP-App | 81e9032 | HandshakeController.php, HandshakeControllerTest.php |
| 2 (RED) | Rote Tests Companion, /status, /sample | 6dd117a | test_handshake.py |
| 2 (GREEN) | Companion-Prüfung, erweiterter /status, /sample-Sperre | 786bc6f | companion.py, api/status.py, api/sample.py, nc.py, main.py, conftest.py, test_main.py |

## Verifikation

- `uv run pytest -q`: 347 passed (19 neue Tests in test_handshake.py), Abdeckung 95,87 %
- ruff check, ruff format --check, pyright (latest, basic) 0 Fehler, vulture grün
- test_php_gates.py 19 passed (Regel 1: Handshake-Methode beginnt mit dem Guard)
- test_boundary.py grün: nc_py_api nur in nc.py
- HandshakeControllerTest (5 Fälle) läuft erst in CI (kein PHP lokal)
- Keine U+2013/U+2014 in den geänderten Dateien

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Periodische Prüfung hätte den Shutdown um 5 s verzögert**
- **Gefunden bei:** Task 2
- **Problem:** `run_periodic` endet nie; `stop_background` hätte bei jedem Shutdown (und jedem TestClient) die volle Frist gewartet.
- **Fix:** Lifespan bricht die Prüfaufgabe vor `stop_background` ab; Test `test_the_lifespan_starts_the_check_and_stops_it_at_once` hält das fest.
- **Commit:** 786bc6f

**2. [Rule 2 - Kritisch] Tests hätten echte Netzaufrufe an NEXTCLOUD_URL versucht**
- **Gefunden bei:** Task 2
- **Fix:** Autouse-Fixture `companion_present` in conftest ersetzt `nc.fetch_handshake` und setzt den Companion-Zustand je Test zurück.
- **Commit:** 786bc6f

`app_client` ist mit der `/status`-Route von main.py nach api/status.py gewandert (main.py brauchte ihn nur dort).

## Beobachtung (nicht behoben, außerhalb des Plans)

- Mit `--cov` meldet der volle Lauf einmal eine ResourceWarning "unclosed database", zufällig beim ersten /status-Test (GC einer Verbindung aus einem früheren Test). Isoliert und ohne Coverage nicht reproduzierbar; Ursprung liegt nicht in den Dateien dieses Plans.

## Threat-Abdeckung

- T-01-37: `#[ExAppRequired]` plus `rejectForeignCaller()` als erste Anweisung (Gate-Regel 1 grün, phpunit-Fälle für fremde, Findling- und leere EX-APP-ID)
- T-01-39: Intervall 300 s, Timeout aus nc_py_api, `fetch_handshake` und `run_periodic` werfen nie
- T-01-40: Logzeilen nur mit Zustands- und Reason-Codes und Statuscode; kein Pfad, keine URL, kein Antwortinhalt (Test prüft das)

## Anforderungen

PLAT-02 bleibt offen: beide Richtungen sind jetzt gebaut und lokal getestet, der Beweis im echten Lauf (fehlende Gegen-App, Drift; Pläne 10, 11, 13) und phpunit in CI fehlen noch. Deshalb nicht als erledigt markiert, wie in 01-07.

## Known Stubs

Keine.

## Self-Check: PASSED

- Dateien vorhanden: HandshakeController.php, HandshakeControllerTest.php, companion.py, api/status.py, test_handshake.py
- Commits vorhanden: 81e9032, 6dd117a, 786bc6f
