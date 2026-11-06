---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 12
subsystem: ci-frueher-push
tags: [ci, push, phpunit, owner-checkpoint]
requires:
  - "01-02, 01-03, 01-04 (Welle 2 fertig)"
provides:
  - "Branch phase-01 auf GitHub, php.yml und python.yml grün auf cb7373e"
  - "Regel 9 in backend/tests/test_php_gates.py: composer.json parst und trägt beide psr-4-Namensräume"
affects: [01-05, 01-06, 01-11]
key-files:
  modified:
    - php/composer.json
    - php/tests/bootstrap.php
    - backend/tests/test_php_gates.py
duration: ca. 15 min
completed: 2026-11-06
---

# Plan 01-12: Früher Branch-Push auf phase-01

Owner-Entscheid 06.11.: Nach Welle 2 auf `phase-01` pushen (nie main), damit die PHP-Tests früh in CI laufen. Ausgeführt vom Orchestrator, jeder Push mit eigener Owner-Freigabe.

## Ablauf

1. **Task 1, Freigabe:** Vorprüfung vor dem Push: 35 Commits, alle als street1983nk, keine Session-, Co-Author- oder closes-Zeilen, kein `node_modules`, 221 Tests grün. Owner gab den Push frei.
2. **Task 2, Push 1:** `git push origin HEAD:refs/heads/phase-01` auf `a4bbc01`, `main` remote unverändert (`f908a85`).
   - Python gates: grün.
   - Deploy through HaRP (nur Information): grün auf stable33, 34, 35.
   - PHP gates: rot. `composer.json` war kein gültiges JSON (`"OCA\AudioVideoSearch\\"`), `php/tests/bootstrap.php` Zeile 31 `rtrim($serverRoot, '/\')` brach `php -l`. Ursache: Beim Umbenennen aus Findling in Plan 01-01 ging je ein Backslash verloren.
3. **Task 3, Korrekturschleife:** Fix `cb7373e` (fix(01-01)): beide Backslashes ergänzt und Regel 9 in `test_php_gates.py` mit Selbsttest. Gegenprobe: mit der alten `composer.json` wird Regel 9 rot. Lokale Gates grün (ruff, ruff format, pyright 0 Fehler, vulture, pytest 223). Owner gab Push 2 frei.
   - Push 2 `a4bbc01..cb7373e`: PHP gates grün (`php -l`, composer validate und audit, PHPUnit `OK (64 tests, 309 assertions)`), Python gates grün.

## Ergebnis

- Die 64 phpunit-Fälle aus Plan 01-03 laufen grün auf `stable34`.
- Welle 4 (01-05, 01-06) darf starten.
- Weitere Pushes auf `phase-01` nur nach Owner-Frage; `main` nur über Plan 01-11.

## Deviations

- Fix lag in Plan 01-01 (Commit-Präfix fix(01-01)); kein eigener Plan nötig.
- Neue lokale Regel 9, damit ein solcher Kopierfehler nicht erst nach einem Push auffällt.
