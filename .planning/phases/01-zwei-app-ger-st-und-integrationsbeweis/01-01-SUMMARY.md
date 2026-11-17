---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 01
subsystem: infra
tags: [scaffold, exapp, php-app, lockstep, ci, phpunit, dependabot]
requires: []
provides:
  - "backend/ mit ExApp audio_video_search_backend (Paket, Dockerfile, appinfo, l10n, Tests)"
  - "php/ mit PHP-App audio_video_search (info.xml, routes.php, Application.php, composer, phpunit, bootstrap)"
  - "Lockstep-Gate backend/tests/test_lockstep_versions.py (4 Versionen + Server-Fenster gegen deploy-harp-Matrix)"
  - ".github/workflows/php.yml (lint, composer-hygiene, phpunit gegen stable34)"
  - "conftest BACKEND_ROOT/REPO_ROOT, scripts/l10n_js.py --root"
affects: [01-02, 01-03, 01-04, 01-05, 01-07, 01-09, 01-10, 01-12, 01-13]
tech-stack:
  added: ["phpunit/phpunit 11.5.57 (require-dev, nur CI)"]
  patterns:
    - "Zwei-App-Muster wie Findling: php/ + backend/, eine Versionsnummer"
    - "Tests trennen BACKEND_ROOT (Paket, Dockerfile, appinfo, l10n, pyproject) und REPO_ROOT (Workflows, Doku)"
    - "Env-Präfix AVS_ als config.ENV_PREFIX"
key-files:
  created:
    - backend/README.md
    - backend/tests/test_lockstep_versions.py
    - php/appinfo/info.xml
    - php/appinfo/routes.php
    - php/lib/AppInfo/Application.php
    - php/composer.json
    - php/phpunit.xml
    - php/tests/bootstrap.php
    - .github/workflows/php.yml
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
    - backend/Dockerfile
    - backend/appinfo/info.xml
    - backend/l10n/{de,en,fr}.{json,js}
    - backend/src/audio_video_search_backend/{__init__,config,main,settings}.py
    - backend/tests/*.py
    - scripts/l10n_js.py
    - .github/workflows/{python,docker,deploy-harp}.yml
    - .github/dependabot.yml
    - backend/.dockerignore
    - .gitignore
key-decisions:
  - "Env-Präfix AVS_ (AVS_LOG_LEVEL) als config.ENV_PREFIX; Store-Test prüft gegen die Konstante"
  - "Image ohne LICENSE-Datei: Build-Kontext ist backend/, Lizenz steht im OCI-Label (wie Findling)"
  - "Repo-Name im Test fest als nextcloud-audio-video-search (folgt der PHP-App, nicht dem Backend)"
  - ".planning/ vom Strich-/Emoji-Gate ausgenommen, weil GSD-Statuszeichen in VALIDATION.md/RESEARCH.md vom Tool gelesen werden"
  - "php.yml löst composer.lock in CI auf (composer update --no-install --no-scripts) und auditiert ihn dort; kein Lock im Repo"
  - "Lockstep-Gate um die pyproject-Version erweitert (Findling prüft nur drei Werte)"
requirements-completed: []  # PLAT-01 und PLAT-03 nur angelegt (Gerüst, Lockstep-Gate); Upgrade-Beweis und Läufe auf NC 33 bis 35 folgen in späteren Plänen
metrics:
  duration: "ca. 40 min"
  completed: 2026-11-06
  tasks: 3
  files: 50
---

# Phase 1 Plan 01: Zwei-App-Gerüst Summary

Skeleton in `backend/` (ExApp `audio_video_search_backend`) und `php/` (PHP-App `audio_video_search`) aufgeteilt, alle Python-Gates grün, Lockstep-Gate über vier Versionen plus Server-Fenster, und `php.yml` testet die PHP-Hälfte in CI gegen stable34.

## Ergebnis

- Task 1 (Paket-Legitimität): vom Owner am 06.11. freigegeben (tantivy 0.26.2, @playwright/test 1.65.0, phpunit 11.5.57), kein Commit.
- Task 2: 32 Dateien per `git mv` nach `backend/` (Historie erhalten), Paket, Modul, `APP_ID`, Image und Datenpfad auf `audio_video_search_backend`, Env `AVS_LOG_LEVEL`, eigene `backend/README.md`, Formularbeschreibung "Backend-Beschreibung" aus der UI-SPEC in DE/EN/FR, `l10n_js.py --root`.
- Task 3: `python.yml` mit `defaults.run.working-directory: backend` und eigenem ruff-Schritt für `../scripts`, `docker.yml` baut aus `backend/`, `deploy-harp.yml` mit `BACKEND_APP_ID`, Dependabot docker/uv auf `/backend`, `.dockerignore` nach `backend/`; neuer selbsttestender Workflow-Test.
- Task 4: PHP-Gerüst nach Findling, `img/` nach `php/img/`, `test_lockstep_versions.py` mit Anti-Vakuum- und Selbsttests (u. a. 0.1.1 in einer temporären Kopie der php-info.xml), `php.yml` mit lint, composer-hygiene, phpunit.

Gates in `backend/`: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture leer, pytest 119 passed. Gegenprobe: `php/appinfo/info.xml` kurz auf 0.1.1 gesetzt, Lockstep-Test rot, danach zurück.

## Task Commits

1. **Task 2: Backend nach backend/** - `289ff04` (refactor)
2. **Task 3: Workflows und Dependabot auf backend/** - `bae7b42` (ci)
3. **Task 4: PHP-Gerüst, Lockstep, php.yml** - `7d11d76` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Strich-/Emoji-Gate scheiterte an .planning/**
- **Found during:** Task 2
- **Issue:** `test_no_tracked_text_carries_a_dash_or_an_emoji` fand die GSD-Statuszeichen (U+2713, U+274C, U+2705, U+26A0) in `.planning/PROJECT.md`, `01-RESEARCH.md`, `01-VALIDATION.md` (schon vor diesem Plan rot, seit die Planungsdokumente eingecheckt sind).
- **Fix:** `EXEMPT_PREFIXES = (".planning/",)` mit Begründung; die Zeichen bleiben, weil GSD sie zurückliest.
- **Commit:** 289ff04

**2. [Rule 1 - Bug] Store-Test verlangte Env-Präfix = APP_ID**
- **Issue:** Mit `AVS_` statt `AUDIO_VIDEO_SEARCH_BACKEND_` scheiterte der Präfix-Test.
- **Fix:** `config.ENV_PREFIX = "AVS_"`, Test prüft gegen die Konstante und die exakte Variablenliste.
- **Commit:** 289ff04

**3. [Rule 1 - Bug] Repo-URLs aus APP_ID abgeleitet**
- **Issue:** `test_store_metadata.py` und `test_workflows.py` bildeten den Repo-Namen aus `APP_ID` und hätten nach der Umbenennung `nextcloud-audio-video-search-backend` erwartet.
- **Fix:** fester Repo-Name `nextcloud-audio-video-search`.
- **Commits:** 289ff04, bae7b42

**4. [Rule 3 - Blocking] LICENSE außerhalb des Build-Kontexts**
- **Issue:** `COPY LICENSE` im Dockerfile wäre mit Kontext `backend/` gescheitert.
- **Fix:** Zeile entfernt, Kommentar ergänzt (Findling-Form: Lizenz im OCI-Label `org.opencontainers.image.licenses`). Alternative wäre ein benannter Build-Kontext; bei Bedarf in Plan 10 nachziehen.
- **Commit:** 289ff04

**5. [Rule 2 - Owner-Regel] FR-Texte der Backend-info.xml mit U+00A0**
- **Issue:** Die übernommene FR-Beschreibung hatte normale Leerzeichen vor `:`.
- **Fix:** U+00A0 vor `: ; ? !` in der FR-Beschreibung, neue FR-Texte mit U+00A0 und « » nach UI-SPEC.
- **Commit:** 289ff04

**6. [Rule 3 - Blocking] test_workflow_pins.py hatte eigenes REPO_ROOT = parents[1]**
- **Fix:** auf `parents[2]` (Repo-Wurzel) gestellt.
- **Commit:** 289ff04

Weitere kleine Ergänzungen: `.gitignore` für `php/vendor/`, `php/.phpunit.cache/`, `php/junit.xml`; `php/tests/Unit/.gitkeep`; `php.yml` in die Pflichtliste von `test_workflows.py`; Lockstep-Gate prüft zusätzlich `backend/pyproject.toml`.

## Deferred Issues

Siehe `deferred-items.md`: `release.yml`, `store-submit.yml`, `scripts/release/store-archive.sh` noch im Wurzel-Layout (Plan 10), `CONTRIBUTING.md`/`SECURITY.md` mit alten Pfaden (Plan 13), phpunit-Job erst mit den Tests aus Plan 03 grün.

## Known Stubs

- `php/lib/AppInfo/Application.php` registriert `OCA\AudioVideoSearch\Search\Provider`, und `php/appinfo/info.xml` nennt `OCA\AudioVideoSearch\Command\SampleCommand`; beide Klassen entstehen laut Plan in 01-03 vor dem ersten Branch-Push. Bis dahin ist die PHP-App nicht aktivierbar.

## Self-Check: PASSED

- Dateien vorhanden: backend/src/audio_video_search_backend/main.py, backend/appinfo/info.xml, php/appinfo/info.xml, php/lib/AppInfo/Application.php, backend/tests/test_lockstep_versions.py, .github/workflows/php.yml
- Commits vorhanden: 289ff04, bae7b42, 7d11d76
