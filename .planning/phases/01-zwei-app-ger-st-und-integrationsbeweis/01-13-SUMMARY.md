---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 13
subsystem: docs
tags: [docs, trilingual, lockstep, occ, design]
requires: [01-07, 01-08]
provides:
  - Installationsdoku DE/EN/FR mit Reihenfolge, Zuständen des Statusbereichs und Testtreffer per occ
  - README DE/EN/FR für zwei Apps im Gleichschritt
  - DESIGN.md (Stufe 3) und PRODUCT.md ohne TODO(skeleton)
  - CHANGELOG 0.1.0
affects: [README.md, README.en.md, README.fr.md, docs/install*.md, DESIGN.md, PRODUCT.md, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md]
tech-stack:
  added: []
  patterns: [Doku Deutsch zuerst, FR mit U+00A0 vor Satzzeichen und in Guillemets]
key-files:
  created: []
  modified: [README.md, README.en.md, README.fr.md, docs/install.md, docs/install.en.md, docs/install.fr.md, DESIGN.md, PRODUCT.md, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md]
decisions:
  - "Doku nennt occ audio_video_search:sample <fileId> --remove als einzigen Löschweg; auch --remove braucht den Debug-Modus (wie SampleCommand)"
  - "Lizenzhinweis wngerman (GPL-2.0-or-later) und geplante Modelle Parakeet (NVIDIA, CC-BY-4.0) und Whisper (MIT) im README-Abschnitt Lizenz statt eigener THIRD-PARTY-Datei"
metrics:
  duration: ~25 min
  completed: 2026-11-06
requirements: [PLAT-01, PLAT-02]
---

# Phase 1 Plan 13: Doku DE/EN/FR für zwei Apps Summary

README und Installationsdoku in drei Sprachen beschreiben die zwei Apps im Gleichschritt, die Zustände des Admin-Statusbereichs und den Testtreffer, der nur im Debug-Modus per `occ audio_video_search:sample` angelegt und nur mit `--remove` entfernt wird; DESIGN.md hält Stufe 3 fest, PRODUCT.md trägt Nutzer und Core Value.

## Erledigt

- README DE/EN/FR: Stand Phase 1 ehrlich (Testtreffer, keine Transkription), Tabelle der zwei Apps, gleiche Version nötig, Mobil-Apps ab 0:00, Datenschutz, Lizenzhinweise.
- docs/install DE/EN/FR: Reihenfolge AppAPI/HaRP, ExApp, PHP-App, Statusbereich; ein Satz je Zustand (ok, Patch-Abweichung, Versionsdrift, fehlend, deaktiviert, nicht erreichbar, kein AppAPI, Neuprüfung gescheitert); Testtreffer mit `'debug' => true`, Optionen `--at`, `--user`, `--remove`; Seek-Hinweis für nicht seekbare externe Speicher.
- DESIGN.md: Stufe 3 begründet, Flächen der Phase 1, Pfad der deklarativen Einstellungen korrigiert.
- PRODUCT.md: Nutzer, Core Value, Erfolg, Fähigkeiten, Positionierung zwei Apps.
- CHANGELOG 0.1.0 als englische Faktenliste.

## Commits

| Task | Commit | Inhalt |
|---|---|---|
| 1 | 1087ae2 | README, docs/install, DESIGN, PRODUCT, CHANGELOG |
| Zusatz | 3fd2cf7 | CONTRIBUTING, SECURITY, deferred-items |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Übergabe aus deferred-items] CONTRIBUTING.md und SECURITY.md auf neue Struktur**
- **Found during:** Übergabe der Pläne 01-01 und 01-09
- **Issue:** CONTRIBUTING nannte `src/audio_video_search/` und Gates an der Wurzel; SECURITY nur eine App-ID; wngerman-Lizenzhinweis fehlte in der Repo-Doku.
- **Fix:** Pfade auf `backend/` und `php/`, Gates wie `python.yml`; SECURITY mit beiden App-IDs; wngerman-Hinweis im README-Lizenzabschnitt (DE/EN/FR); deferred-items als erledigt markiert.
- **Files modified:** CONTRIBUTING.md, SECURITY.md, deferred-items.md
- **Commit:** 3fd2cf7

## Requirements

PLAT-01 und PLAT-02 bleiben in REQUIREMENTS.md offen: PLAT-01 verlangt den Upgrade-Beweis in CI (Pläne 01-10/01-11), diese Doku liefert nur den Admin-Teil.

## Prüfungen

- `TODO(skeleton)` in DESIGN.md/PRODUCT.md: 0; `--remove` in allen drei install-Dateien; `audio_video_search_backend` in allen drei READMEs.
- Keine U+2013/U+2014 in README*, docs/*, DESIGN, PRODUCT, CHANGELOG (Skript); FR-Dateien mit U+00A0 vor `: ; ? !` und in Guillemets, kein normales Leerzeichen davor (Skript).
- backend/: ruff check, ruff format --check, pyright (latest, 0 errors), vulture, pytest 363 passed.

## Hinweise

- Im Arbeitsbaum lagen fremde Änderungen an `backend/tests/test_handshake.py` und `php/tests/Unit/BackendStateTest.php` (nicht aus diesem Plan); nicht angefasst, nicht committet.
- Nichts gepusht.

## Self-Check: PASSED
