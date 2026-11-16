---
phase: 4
slug: suchqualit-t-und-export
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-11-16
---

# Phase 4 , Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (backend, .venv), phpunit 11.5.x (php/, nur CI), Playwright (ci/playwright, nur CI) |
| **Config file** | backend/pyproject.toml, php/phpunit.xml, ci/playwright/playwright.config.ts |
| **Quick run command** | `cd backend && uv run pytest tests/<berührte Datei> -x -q`; PHP lokal nur über die Python-Gates `tests/test_php_gates.py tests/test_trilingual.py tests/test_public_texts.py tests/test_ui_assets.py` (kein PHP lokal) |
| **Full suite command** | `cd backend && uv run ruff check --no-cache . && uv run ruff format --check --no-cache . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright --pythonpath .venv/Scripts/python.exe && uv run vulture && uv run pytest -q`; PHPUnit und Playwright in CI (Plan 04-15) |
| **Estimated runtime** | Backend-Vollsuite ca. 2 bis 4 min lokal; PHP ca. 1 min in CI |
| **Besonderheit** | Untertitel-Beweis (EXP-02) über drei UNABHÄNGIGE Prüfer (webvtt-py, srt nur dev; ffmpeg), Writer bleibt eigener Code; Gegenprobe nie mit dem Muster der Umsetzung (handgeschriebene Tabellen in test_numbers.py) |

---

## Sampling Rate

- **After every task commit:** Quick run des berührten Bereichs
- **After every plan wave:** Full suite (Backend) plus Python-Gates der PHP-Seite
- **Before `/gsd:verify-work`:** Full suite grün, CI-Läufe aus Plan 04-15 grün, Owner-Abnahme Plan 04-16
- **Max feedback latency:** 240 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | SRCH-05 | T-04-01 | begrenzte Variantenzahl | unit | `cd backend && uv run pytest tests/test_numbers.py -x -q` | ❌ W0 (RED im Task) | ⬜ pending |
| 04-01-02 | 01 | 1 | SRCH-05 | T-04-03 | 12:30 ohne ValueError, Wortweg | integration | `cd backend && uv run pytest tests/test_search_numbers.py tests/test_index_publish.py tests/test_search_tiers.py -x -q` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | SRCH-06 | T-04-04, T-04-05 | Freigabe-Abfrage gebunden, fail-closed | unit (CI) + gate | `cd backend && uv run pytest tests/test_php_gates.py -x -q` | ❌ W0 (SearchFiltersTest.php) | ⬜ pending |
| 04-02-02 | 02 | 1 | SRCH-06, SRCH-04 | T-04-04, T-04-06 | Filter nur nach readableFile | unit (CI) + gate | `cd backend && uv run pytest tests/test_php_gates.py -x -q` + grep BUILTIN_* | ✅ ProviderTest erweitern | ⬜ pending |
| 04-03-01 | 03 | 1 | EXP-04 | T-04-10 | Icon-Pfade geprüft | doc | `grep -q "Owner-Freigabe Phase 4" 04-UI-SPEC.md` | ✅ | ⬜ pending |
| 04-03-02 | 03 | 1 | EXP-04 | , | Owner-Freigabe Texte | checkpoint | `grep -q "Owner-Freigabe Phase 4" 04-UI-SPEC.md` | ✅ | ⬜ pending |
| 04-03-03 | 03 | 1 | EXP-04 | T-04-08, T-04-09 | Gate gegen BITV-Behauptung, NOTE ohne --> | gate | `cd backend && uv run pytest tests/test_trilingual.py tests/test_public_texts.py -x -q` | ✅ erweitern | ⬜ pending |
| 04-04-01 | 04 | 1 | EXP-02 | T-04-SC | Legitimitätsprüfung vor Install | checkpoint (blocking-human) | `cd backend && ! grep -q "webvtt-py\|srt==" pyproject.toml` | ✅ | ⬜ pending |
| 04-04-02 | 04 | 1 | EXP-02 | T-04-SC, T-04-11 | Prüfer schlagen an (Positivkontrolle) | unit | `cd backend && uv run pytest tests/test_subtitle_checkers.py tests/test_lock_wheels.py tests/test_dockerfile.py -x -q` | ❌ W0 | ⬜ pending |
| 04-05-01 | 05 | 1 | EXP-03, EXP-01 | T-04-12, T-04-13 | Migration transaktional, CHECK de/en/fr | unit | `cd backend && uv run pytest tests/test_store_migration_v4.py tests/test_store_migration_v3.py tests/test_store_migration_v2.py tests/test_store_schema.py tests/test_preview_store.py -x -q` | ❌ W0 | ⬜ pending |
| 04-05-02 | 05 | 1 | EXP-03 | T-04-14, T-04-15 | nie und, Stichprobe 3000 Wörter | unit | `cd backend && uv run pytest tests/test_file_language.py tests/test_preview_worker.py tests/test_preview_index_load.py -x -q` | ❌ W0 | ⬜ pending |
| 04-06-01 | 06 | 2 | SRCH-05 | T-04-16, T-04-17 | Regex maskiert, p95 <= 250 ms | integration + Messung | `cd backend && uv run pytest tests/test_compounds.py tests/test_search_numbers.py tests/test_index_publish.py -x -q && uv run python ../scripts/research/phase4/measure_prefix.py --docs 100000 --queries 200 --threshold-ms 250` | ❌ W0 | ⬜ pending |
| 04-06-02 | 06 | 2 | SRCH-05 | T-04-01 | Zahlenraum begrenzt | unit + integration | `cd backend && uv run pytest tests/test_numbers.py tests/test_search_numbers.py tests/test_compounds.py -x -q` | ✅ (aus 04-01) | ⬜ pending |
| 04-07-01 | 07 | 2 | EXP-02 | T-04-19, T-04-20 | Fuzz ohne Absturz, Text unverändert | unit (property) | `cd backend && uv run pytest tests/test_subtitles_cues.py -x -q` | ❌ W0 | ⬜ pending |
| 04-08-01 | 08 | 3 | EXP-02, EXP-04 | T-04-21, T-04-23 | VTT maskiert, drei Prüfer | unit (property) | `cd backend && uv run pytest tests/test_subtitles_formats.py tests/test_subtitles_cues.py tests/test_subtitle_checkers.py -x -q` | ❌ W0 | ⬜ pending |
| 04-08-02 | 08 | 3 | EXP-01 | T-04-22 | Budget gemessen | Messung | `cd backend && uv run python ../scripts/research/phase4/measure_export.py --words 100000 --runs 3` | ❌ W0 | ⬜ pending |
| 04-09-01 | 09 | 4 | EXP-01, EXP-02, EXP-03 | T-04-24 bis T-04-28 | Leck-Regel byte-gleich, Lock frei | integration (TestClient) | `cd backend && uv run pytest tests/test_api_export.py tests/test_api_routes.py tests/test_excerpt_states.py -x -q` | ❌ W0 | ⬜ pending |
| 04-09-02 | 09 | 4 | EXP-01 | T-04-26 | PHP-Grenzen passen zur Messung | unit | `cd backend && uv run pytest tests/test_export_budget.py -x -q` | ❌ W0 | ⬜ pending |
| 04-10-01 | 10 | 2 | SRCH-04 | T-04-30 | Export fail-closed, kein canDownload | unit (CI) + gate | `cd backend && uv run pytest tests/test_php_gates.py -x -q` + grep allowsExport | ❌ W0 (DownloadPolicyTest.php) | ⬜ pending |
| 04-10-02 | 10 | 2 | EXP-01 | T-04-33 | Antwortprüfung, eigenes Budget | unit (CI) + gate | `cd backend && uv run pytest tests/test_php_gates.py -x -q` + grep EXPORT_* | ✅ ExAppServiceTest erweitern | ⬜ pending |
| 04-10-03 | 10 | 2 | SRCH-04, EXP-01, EXP-04 | T-04-29, T-04-31, T-04-32, T-04-34 | 403 vor Container, 404 byte-gleich, Regel 19 | unit (CI) + gate | `cd backend && uv run pytest tests/test_php_gates.py tests/test_trilingual.py tests/test_public_texts.py tests/test_ui_assets.py -x -q` | ❌ W0 (ExportControllerTest.php) | ⬜ pending |
| 04-11-01 | 11 | 4 | SRCH-04, EXP-01 | T-04-44, T-04-45 | X3 ohne URLs, X4 byte-gleich | unit (CI) + gate | `cd backend && uv run pytest tests/test_php_gates.py -x -q` + grep EXPORT_BLOCKED | ✅ PlayControllerTest erweitern | ⬜ pending |
| 04-11-02 | 11 | 4 | EXP-01, EXP-04 | T-04-46, T-04-48 | nur p(), Spur ohne default | gate | `cd backend && uv run pytest tests/test_ui_assets.py tests/test_php_gates.py tests/test_trilingual.py tests/test_public_texts.py -x -q` | ✅ erweitern | ⬜ pending |
| 04-11-03 | 11 | 4 | EXP-03 | T-04-46, T-04-47 | textContent, requesttoken | gate | `cd backend && uv run pytest tests/test_ui_assets.py -x -q` | ✅ erweitern | ⬜ pending |
| 04-12-01 | 12 | 3 | EXP-03 | T-04-36, T-04-37 | nodeExists unter Sperre, nie newFile auf Bestand | unit (CI) + gate | `cd backend && uv run pytest tests/test_php_gates.py -x -q` + grep acquireLock/nodeExists | ❌ W0 (SidecarTest.php) | ⬜ pending |
| 04-12-02 | 12 | 3 | EXP-03, SRCH-04 | T-04-38 bis T-04-41 | CSRF, Rate-Limit, 403 vor Container, Regel 20 | unit (CI) + gate | `cd backend && uv run pytest tests/test_php_gates.py -x -q` | ✅ ExportControllerTest erweitern | ⬜ pending |
| 04-13-01 | 13 | 5 | EXP-04, EXP-03 | T-04-49 | ehrliche README, NC 36 | gate | `cd backend && uv run pytest tests/test_trilingual.py tests/test_public_texts.py -x -q` | ✅ | ⬜ pending |
| 04-13-02 | 13 | 5 | EXP-04 | T-04-50 | Versprechen gedeckt | gate | `cd backend && uv run pytest tests/test_public_texts.py -x -q` | ✅ | ⬜ pending |
| 04-14-01 | 14 | 5 | SRCH-05 | T-04-58 | S7-Sätze gepinnt und vorab gemessen | model (CI python.yml) | `cd backend && uv run pytest tests/test_engine_model.py -k s7 -x -q` | ✅ erweitern | ⬜ pending |
| 04-14-02 | 14 | 5 | SRCH-05, SRCH-06, SRCH-04 | T-04-51 | Treffer bei Sperre, Filter-Gruppe, Vorbedingung S7 | e2e (CI) | `cd ci/playwright && npx playwright test --list --grep @phase4` | ❌ W0 | ⬜ pending |
| 04-14-03 | 14 | 5 | EXP-02, EXP-04, SRCH-05 | T-04-53, T-04-59 | Prüfer auf echten Downloads, leerer Ordner scheitert, Beifang verbindlich | gate + e2e | `cd backend && uv run pytest tests/test_workflows.py tests/test_workflow_pins.py tests/test_downloaded_subtitles.py -x -q` | ❌ W0 | ⬜ pending |
| 04-17-01 | 17 | 6 | EXP-01, EXP-02, SRCH-04 | T-04-51, T-04-52, T-04-60 | 403 auf export/track/sidecar, Kombifall gesperrt und ausgeschlossen = X3, X2 kontrolliert | e2e (CI) | `cd ci/playwright && npx playwright test --list --grep @phase4` | ❌ W0 | ⬜ pending |
| 04-17-02 | 17 | 6 | EXP-03, EXP-04 | T-04-51, T-04-52 | sha256 gleich, E3/E4 nach Seitenaufbau, Spur, Kontrast, axe | e2e (CI) | `cd ci/playwright && npx playwright test --list --grep @phase4` | ❌ W0 | ⬜ pending |
| 04-15-01 | 15 | 7 | alle | T-04-54 | Autoren-/Text-/debug-Prüfung | checkpoint | Autoren- und Textprüfung + `uv run pytest -q` | ✅ | ⬜ pending |
| 04-15-02 | 15 | 7 | alle | T-04-55, T-04-56 | main/ghcr unverändert, ein Beobachter | CI | `gh run list --branch phase-04 --commit "$SHA" ...` (siehe Plan) | ✅ | ⬜ pending |
| 04-16-01 | 16 | 8 | EXP-01, EXP-03, EXP-04, SRCH-04, SRCH-06 | T-04-57 | Lücken markiert | gate | `cd backend && uv run pytest tests/test_trilingual.py tests/test_public_texts.py tests/test_ui_assets.py -x -q` | ✅ | ⬜ pending |
| 04-16-02 | 16 | 8 | wie oben | T-04-57, T-04-58 | Owner-Abnahme | checkpoint | `cd backend && uv run pytest tests/test_trilingual.py tests/test_ui_assets.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Unabhängiger Untertitel-Prüfer als dev-Abhängigkeit prüfen und pinnen (webvtt-py, srt), Checkpoint vor dem Einbau: Plan 04-04 Task 1 (blocking-human), danach Positivkontrolle Task 2
- [ ] Testdaten für Zahlen/Wortformen-Suchfälle (DE/EN/FR) als handgeschriebene Tabellen und Index-Fixtures im Test, keine Binärdateien im Repo: Plan 04-01, 04-06
- [ ] Neue Testdateien entstehen jeweils im RED-Schritt ihrer TDD-Aufgabe (test_numbers, test_search_numbers, test_compounds, test_subtitles_cues, test_subtitles_formats, test_subtitle_checkers, test_store_migration_v4, test_file_language, test_api_export, test_export_budget, test_downloaded_subtitles; PHP: SearchFiltersTest, DownloadPolicyTest, ExportControllerTest, SidecarTest)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UI-Abnahme der neuen Flächen (Knöpfe, Spur, Banner) | EXP-01/03, UI-SPEC | Owner-Regel: Abnahme gemeinsam per Playwright, 3 Breiten, hell/dunkel | Plan 04-16, Screenshots aus CI (Artefakt phase4-screens) |
| Owner-Freigabe der Texte T13 bis T35 | EXP-04, UI-SPEC | Textfreigabe vor dem Bau ist Owner-Entscheid | Plan 04-03 Task 2 |
| Legitimität webvtt-py/srt | EXP-02 | slopcheck lief nicht; Package Legitimacy Gate | Plan 04-04 Task 1 |
| Push-Freigabe | alle | Owner-Regel vor jedem Push | Plan 04-15 Task 1 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 240s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
