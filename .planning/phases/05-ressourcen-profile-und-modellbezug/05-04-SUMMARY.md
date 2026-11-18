---
phase: 05-ressourcen-profile-und-modellbezug
plan: 04
subsystem: backend/resources
tags: [RES-01, RES-05, threads, cgroup, rechenfenster, zoneinfo]
requires: []
provides:
  - "hardware.py: usable_cpus(root, affinity), default_threads(cpus), effective_threads(admin, cpus), memory_total_bytes(meminfo), Snapshot (frozen, Bytes), snapshot(*, cgroup_root, meminfo, affinity), THREAD_CAP = 4"
  - "schedule.py: parse_hhmm(raw, field), validate_window(start, end, zone) -> (time|None, time|None, zone), window_open(now_utc, start, end, zone), next_change(now_utc, start, end, zone, *, horizon=48 h), WindowError(field)"
affects: [05-07, 05-11, 05-12, 05-15, 05-16]
tech-stack:
  added: []
  patterns: ["reine stdlib-Funktionen mit injizierbarer cgroup-Wurzel und Uhr", "Fenster in IANA-Zone über zoneinfo, Minutenschritte mit Suchgrenze"]
key-files:
  created:
    - backend/src/audio_video_search_backend/hardware.py
    - backend/src/audio_video_search_backend/schedule.py
    - backend/tests/test_hardware.py
    - backend/tests/test_schedule.py
  modified: []
decisions:
  - "Snapshot: memory.max über MemTotal zählt als MemTotal, und der Headroom wird dann auf MemTotal minus anon gedeckelt (sonst stünde ein Phantom-Headroom aus der zu hohen Grenze im Snapshot)"
  - "memory.swap.max: 0 bleibt 0 (kein Swap), 'max' und Unlesbares sind None"
  - "validate_window prüft die Zone immer, auch bei None/None, damit eine gespeicherte Zone stets nutzbar ist"
  - "window_open mit unbekannter Zone wirft WindowError('window_zone'); der Rückfall auf 'offen' gehört in den Aufrufer (ComputeGate, Plan 05-15)"
  - "next_change bekommt einen Schlüsselwort-Parameter horizon (Standard 48 h) für den Grenztest"
metrics:
  duration: "ca. 35 min"
  completed: 2026-11-18
  tasks: 2
  files: 4
---

# Phase 5 Plan 04: hardware.py und schedule.py Summary

Zwei reine stdlib-Module als Grundlage für Profilrechner, Thread-Grenze und Rechenfenster: nutzbare CPUs aus Affinität und cpu.max-Quote, Thread-Standard halbe CPU mit Deckel 4 (Admin nur senken), Speicher-Snapshot in Bytes (fail closed) und ein Rechenfenster in der IANA-Zone des Admins über Mitternacht und beide Sommerzeit-Umstellungen 2026.

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | hardware.py (RED, GREEN) | 7cea8a9 (RED), 7f8c17f (GREEN) | hardware.py, tests/test_hardware.py |
| 2 | schedule.py (RED, GREEN) | 4571455 (RED), 84feb82 (GREEN) | schedule.py, tests/test_schedule.py |

REFACTOR war nicht nötig.

## Ergebnis

- `usable_cpus`: "200000 100000" bei Affinität 8 ergibt 2, "150000 100000" ergibt 1, "max 100000" die Affinität, fehlende oder kaputte Datei ("abc 100000", "100000 0", "", "-5 100000") die Affinität, nie unter 1. Ohne `os.sched_getaffinity` (Windows) gilt `os.cpu_count()`.
- `default_threads`: 1, 2, 4, 8, 64 CPUs ergeben 1, 1, 2, 4, 4. `effective_threads(9, 8)` bleibt 4, 0 und -1 sind `ValueError("threads")`.
- `snapshot()`: MemTotal, memory.max, memory.swap.max, Headroom (aus `memory_guard.headroom_bytes`), CPUs, Affinität; nichts lesbar ergibt Headroom None.
- `window_open`: 22:00 bis 06:00 Europe/Berlin offen um 22:30 CET, zu um 06:30 CET; am 29.03.2026 (05:30 CEST offen, 06:30 CEST zu) und am 25.10.2026 (02:30 CEST und 02:30 CET beide offen, 06:30 CET zu) geprüft. 08:00 bis 17:00: 07:59 zu, 08:00 offen, 17:00 zu. Naive Zeitpunkte werden abgelehnt.
- `next_change`: nächste Öffnung bzw. Schließung als aware datetime in der Zone (z. B. Schließung am 29.03.2026 um 06:00 CEST = 04:00 UTC), bei immer offen None, höchstens 48 Stunden Suche.
- Coverage beider Module 100 %. Keins der Module liest Umgebung, Einstellungen oder OMP-Variablen (Test hält das für hardware.py).

## Verification

- `uv run pytest -q tests/test_hardware.py tests/test_schedule.py`: 86 passed (35 + 51).
- Voller Lauf: 2453 passed, 18 skipped, 4 xfailed.
- ruff check, ruff format --check, pyright basic (latest), vulture: grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lokale Zeitzonendaten unter Windows**
- **Found during:** Task 2
- **Issue:** Python unter Windows hat keine IANA-Datenbank, `ZoneInfo("Europe/Berlin")` scheitert ohne das Paket `tzdata`. Im Image (`python:3.13-slim-trixie`, tzdata unter /usr/share/zoneinfo) und auf den Ubuntu-Runnern der CI ist sie vorhanden.
- **Fix:** Keine Paketinstallation (Regel: keine Installation ohne Freigabe). Lokal laufen die Tests mit `PYTHONTZPATH` auf einen vorhandenen tzdata-Ordner eines anderen lokalen venv. Ohne diese Variable schlagen die Fenster-Tests unter Windows fehl, in CI und Container nicht.
- **Offen:** Ob `tzdata` als Dev-Abhängigkeit (nur Windows) ins Projekt soll, entscheidet der Owner.

## TDD Gate Compliance

RED- und GREEN-Commits liegen für beide Tasks in der richtigen Reihenfolge vor.

## Self-Check: PASSED

- Dateien vorhanden: hardware.py, schedule.py, test_hardware.py, test_schedule.py.
- Commits vorhanden: 7cea8a9, 7f8c17f, 4571455, 84feb82.
