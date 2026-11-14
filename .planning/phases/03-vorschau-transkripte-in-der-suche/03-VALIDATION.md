---
phase: 3
slug: vorschau-transkripte-in-der-suche
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-11-14
---

# Phase 3: Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Quelle: 03-RESEARCH.md, Abschnitt "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 (backend), phpunit 11.5 (php, CI), Bash + curl im CI-Workflow "Discovery acceptance" |
| **Config file** | `backend/pyproject.toml`, `php/phpunit.xml`, `.github/workflows/discovery-e2e.yml` |
| **Quick run command** | `cd backend && uv run pytest -q -x` |
| **Full suite command** | `cd backend && uv run ruff check . && uv run ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -q` (PHP und e2e in CI) |
| **Estimated runtime** | ca. 120 Sekunden lokal ohne Modelltests |

---

## Sampling Rate

- **After every task commit:** betroffene pytest-Datei, dann `cd backend && uv run pytest -q -x`
- **After every plan wave:** Full suite command
- **Before `/gsd:verify-work`:** Full suite grün plus CI (php.yml, discovery-e2e inkl. search-parity)
- **Max feedback latency:** 180 Sekunden

---

## Per-Task Verification Map

Aus den Plänen 03-01 bis 03-21 (inkl. 03-07b, 03-13b, 03-16b, 03-18b) erzeugt. Jede Aufgabe hat einen `<automated>`-Befehl; Checkpoints prüfen mit einem schnellen Gate, die eigentliche Prüfung ist die Owner-Antwort. PHP- und Container-Belege (phpunit, Docker, Playwright, search-parity) kommen aus CI in Plan 03-20.

| Task-ID | Plan | Welle | Requirement | Threat-Ref | Testtyp | Automatischer Befehl | Datei | Status |
|---|---|---|---|---|---|---|---|---|
| 03-01-T1 | 03-01 | 1 | TRANS-01, TRANS-03, MEDIA-03 | T-03-01, T-03-02, T-03-SC | checkpoint | `curl -fsS https://pypi.org/pypi/py3langid/0.4.0/json \| python -c "import json,sys; d=json.load(sys.stdin); ...` | vorhanden | pending |
| 03-01-T2 | 03-01 | 1 | TRANS-01, TRANS-03, MEDIA-03 | T-03-01, T-03-02, T-03-SC | checkpoint | `cd backend && uv run pytest tests/test_trilingual.py -x -q` | vorhanden | pending |
| 03-01-T3 | 03-01 | 1 | TRANS-01, TRANS-03, MEDIA-03 | T-03-01, T-03-02, T-03-SC | auto | `F=.planning/phases/03-vorschau-transkripte-in-der-suche/03-UI-SPEC.md && grep -q "A13" "$F" && grep -q "dis...` | vorhanden | pending |
| 03-02-T1 | 03-02 | 1 | MEDIA-04, TRANS-03, SRCH-01, SRCH-02 | T-03-03 bis T-03-06 | auto | `cd backend && uv run pytest tests/test_research_scripts.py -x -q && uv run ruff check ../scripts` | W0 (Plan legt an) | pending |
| 03-02-T2 | 03-02 | 1 | MEDIA-04, TRANS-03, SRCH-01, SRCH-02 | T-03-03 bis T-03-06 | auto | `cd backend && uv run pytest tests/test_fetch_speech.py -x -q` | W0 (Plan legt an) | pending |
| 03-02-T3 | 03-02 | 1 | MEDIA-04, TRANS-03, SRCH-01, SRCH-02 | T-03-03 bis T-03-06 | auto | `cd ci/playwright && npx playwright test --list --grep @preview` | vorhanden | pending |
| 03-03-T1 | 03-03 | 1 | TRANS-01, TRANS-07 | T-03-07 bis T-03-10 | tdd | `cd backend && uv run pytest tests/test_store_migration_v3.py tests/test_store_migration_v2.py tests/test_st...` | W0 (Plan legt an) | pending |
| 03-03-T2 | 03-03 | 1 | TRANS-01, TRANS-07 | T-03-07 bis T-03-10 | tdd | `cd backend && uv run pytest tests/test_preview_seed.py tests/test_intake.py tests/test_capture.py -x -q` | W0 (Plan legt an) | pending |
| 03-04-T1 | 03-04 | 1 | TRANS-01 | T-03-11, T-03-12, T-03-13 | auto | `cd backend && uv run pytest tests/test_php_gates.py -x -q && grep -q "ORIGINS" ../php/lib/Db/QueueMapper.ph...` | vorhanden | pending |
| 03-04-T2 | 03-04 | 1 | TRANS-01 | T-03-11, T-03-12, T-03-13 | auto | `cd backend && uv run pytest tests/test_php_gates.py -x -q && test "$(grep -c "ORIGIN_EVENT" ../php/lib/List...` | vorhanden | pending |
| 03-05-T1 | 03-05 | 1 | MEDIA-01, MEDIA-02, MEDIA-03 | T-03-14 bis T-03-18 | auto | `cd backend && uv run pytest tests/test_dockerfile.py tests/test_workflow_pins.py tests/test_workflows.py -x...` | vorhanden | pending |
| 03-05-T2 | 03-05 | 1 | MEDIA-01, MEDIA-02, MEDIA-03 | T-03-14 bis T-03-18 | tdd | `cd backend && uv run pytest tests/test_media_decode.py tests/test_media_timeline.py tests/test_media_harden...` | W0 (Plan legt an) | pending |
| 03-06-T1 | 03-06 | 1 | TRANS-02, TRANS-03, MEDIA-04 | T-03-19, T-03-20, T-03-21 | tdd | `cd backend && uv run pytest tests/test_catch_rule.py tests/test_engine_constants.py -x -q` | W0 (Plan legt an) | pending |
| 03-06-T2 | 03-06 | 1 | TRANS-02, TRANS-03, MEDIA-04 | T-03-19, T-03-20, T-03-21 | tdd | `cd backend && uv run pytest tests/test_vad_gate.py -x -q` | W0 (Plan legt an) | pending |
| 03-07-T1 | 03-07 | 2 | TRANS-01 | T-03-22 bis T-03-25 | auto | `cd backend && uv run pytest tests/test_models.py tests/test_model_download.py tests/test_boundary.py -x -q` | W0 (Plan legt an) | pending |
| 03-07-T2 | 03-07 | 2 | TRANS-01 | T-03-22 bis T-03-25 | auto | `cd backend && uv run pytest tests/test_main.py tests/test_models.py tests/test_boundary.py -x -q` | W0 (Plan legt an) | pending |
| 03-07b-T1 | 03-07b | 3 | TRANS-01 | T-03-74 bis T-03-79 | checkpoint | `gh release view models-2026-11 --repo street1983nk/nextcloud-audio-video-search --json isDraft,tagName,assets ...` | vorhanden | pending |
| 03-07b-T2 | 03-07b | 3 | TRANS-01 | T-03-74 bis T-03-79 | tdd | `cd backend && uv run pytest tests/test_models.py tests/test_model_download.py tests/test_dockerfile.py tests/test_boundary.py tests/test_main.py ...` | vorhanden | pending |
| 03-08-T1 | 03-08 | 1 | SRCH-01, SRCH-02 | T-03-26, T-03-27, T-03-28 | tdd | `cd backend && uv run pytest tests/test_search_tiers.py tests/test_api_routes.py tests/test_excerpt_states.p...` | W0 (Plan legt an) | pending |
| 03-09-T1 | 03-09 | 2 | TRANS-07, TRANS-03, MEDIA-04 | T-03-29 bis T-03-32 | tdd | `cd backend && uv run pytest tests/test_preview_store.py tests/test_corrections.py tests/test_provenance.py ...` | W0 (Plan legt an) | pending |
| 03-09-T2 | 03-09 | 2 | TRANS-07, TRANS-03, MEDIA-04 | T-03-29 bis T-03-32 | tdd | `cd backend && uv run pytest tests/test_coverage_count.py tests/test_preview_store.py tests/test_exclusion_f...` | W0 (Plan legt an) | pending |
| 03-10-T1 | 03-10 | 3 | TRANS-01, TRANS-02, TRANS-08 | T-03-33 bis T-03-SC | auto | `cd backend && uv sync --frozen && uv run pytest tests/test_lock_wheels.py tests/test_memory_guard.py -x -q ...` | W0 (Plan legt an) | pending |
| 03-10-T2 | 03-10 | 3 | TRANS-01, TRANS-02, TRANS-08 | T-03-33 bis T-03-SC | tdd | `cd backend && uv run pytest tests/test_engine_child.py tests/test_vad_gate.py tests/test_catch_rule.py -x -q` | W0 (Plan legt an) | pending |
| 03-10-T3 | 03-10 | 3 | TRANS-01, TRANS-02, TRANS-08 | T-03-33 bis T-03-SC | auto | `cd backend && uv run pytest tests/test_engine_model.py tests/test_workflow_pins.py -x -q -rs` | W0 (Plan legt an) | pending |
| 03-11-T1 | 03-11 | 2 | TRANS-01, MEDIA-03 | T-03-36, T-03-37, T-03-38 | tdd | `cd backend && uv run pytest tests/test_intake.py tests/test_php_gates.py tests/test_preview_seed.py -x -q` | W0 (Plan legt an) | pending |
| 03-11-T2 | 03-11 | 2 | TRANS-01, MEDIA-03 | T-03-36, T-03-37, T-03-38 | tdd | `cd backend && uv run pytest tests/test_settings.py tests/test_trilingual.py tests/test_public_texts.py -x -...` | vorhanden | pending |
| 03-12-T1 | 03-12 | 2 | SRCH-01, SRCH-02, SRCH-03 | T-03-39 bis T-03-42 | auto | `cd backend && uv run pytest tests/test_php_gates.py -x -q && grep -q "int \$offset" ../php/lib/Service/ExAp...` | vorhanden | pending |
| 03-12-T2 | 03-12 | 2 | SRCH-01, SRCH-02, SRCH-03 | T-03-39 bis T-03-42 | auto | `cd backend && uv run pytest tests/test_php_gates.py tests/test_trilingual.py tests/test_public_texts.py -x ...` | vorhanden | pending |
| 03-13-T1 | 03-13 | 4 | alle 12 | T-03-43 bis T-03-47 | tdd | `cd backend && uv run pytest tests/test_fetch_keep.py tests/test_capture.py tests/test_boundary.py -x -q` | W0 (Plan legt an) | pending |
| 03-13-T2 | 03-13 | 4 | alle 12 | T-03-43 bis T-03-47 | tdd | `cd backend && uv run pytest tests/test_preview_worker.py -x -q` | W0 (Plan legt an) | pending |
| 03-13-T3 | 03-13 | 4 | alle 12 | T-03-43 bis T-03-47 | auto | `cd backend && uv run pytest tests/test_preview_index_load.py -x -q -s` | W0 (Plan legt an) | pending |
| 03-13b-T1 | 03-13b | 5 | TRANS-03, MEDIA-04 | T-03-82 bis T-03-84 | auto | `cd backend && uv run pytest tests/test_research_scripts.py -x -q && uv run ruff check ../scripts && uv run ruff format --check ../scripts` (Messung mit echter Engine im Scratch, Tabelle im SUMMARY; mehrdeutig: Owner-Checkpoint) | vorhanden | pending |
| 03-13b-T2 | 03-13b | 5 | TRANS-03, MEDIA-04 | T-03-80, T-03-81 | tdd | `cd backend && uv run pytest tests/test_catch_rule.py tests/test_engine_constants.py tests/test_engine_child.py tests/test_vad_gate.py tests/test_preview_worker.py tests/test_research_scripts.py -x -q` | vorhanden | pending |
| 03-14-T1 | 03-14 | 3 | SRCH-02, SRCH-03, MEDIA-04 | T-03-48, T-03-49, T-03-50 | tdd | `cd backend && uv run pytest tests/test_excerpt_states.py tests/test_sample_layer.py tests/test_sample_real_...` | vorhanden | pending |
| 03-14-T2 | 03-14 | 3 | SRCH-02, SRCH-03, MEDIA-04 | T-03-48, T-03-49, T-03-50 | auto | `cd backend && uv run pytest tests/test_php_gates.py -x -q && grep -q "byPreview" ../php/lib/Command/StatusC...` | vorhanden | pending |
| 03-15-T1 | 03-15 | 5 | TRANS-01, MEDIA-03, MEDIA-04 | T-03-51, T-03-52, T-03-53 | tdd | `cd backend && uv run pytest tests/test_main.py tests/test_preview_settings.py tests/test_preview_worker.py ...` | W0 (Plan legt an) | pending |
| 03-15-T2 | 03-15 | 5 | TRANS-01, MEDIA-03, MEDIA-04 | T-03-51, T-03-52, T-03-53 | tdd | `cd backend && uv run pytest tests/test_replaced_file.py -x -q` | W0 (Plan legt an) | pending |
| 03-15-T3 | 03-15 | 5 | TRANS-01, MEDIA-03, MEDIA-04 | T-03-51, T-03-52, T-03-53 | auto | `cd backend && uv run pytest tests/test_preview_corpus.py -x -q -rs -s` | W0 (Plan legt an) | pending |
| 03-16-T1 | 03-16 | 4 | SRCH-02, SRCH-03, MEDIA-04 | T-03-54, T-03-55, T-03-56 | auto | `cd backend && uv run pytest tests/test_php_gates.py -x -q && grep -q "EXCERPT_PENDING_HERE" ../php/lib/Cont...` | vorhanden | pending |
| 03-16b-T1 | 03-16b | 5 | SRCH-02, MEDIA-04 | T-03-72, T-03-73 | auto | `cd backend && uv run pytest tests/test_ui_assets.py tests/test_trilingual.py tests/test_public_texts.py tes...` | vorhanden | pending |
| 03-17-T1 | 03-17 | 6 | SRCH-03, SRCH-01 | T-03-57, T-03-58, T-03-59 | auto | `cd backend && uv run pytest tests/test_discovery_workflow.py tests/test_workflow_pins.py -x -q` | vorhanden | pending |
| 03-17-T2 | 03-17 | 6 | SRCH-03, SRCH-01 | T-03-57, T-03-58, T-03-59 | auto | `cd backend && uv run pytest tests/test_discovery_workflow.py -x -q && bash -n ../ci/discovery/parity.sh && ...` | vorhanden | pending |
| 03-18-T1 | 03-18 | 6 | alle 12 | T-03-60, T-03-61, T-03-62 | auto | `bash -n ci/make-testmedia.sh && bash -n ci/seed.sh && cd backend && uv run pytest tests/test_workflows.py t...` | vorhanden | pending |
| 03-18-T2 | 03-18 | 6 | alle 12 | T-03-60, T-03-61, T-03-62 | auto | `cd ci/playwright && npx playwright test --list --grep @preview` | vorhanden | pending |
| 03-18b-T1 | 03-18b | 7 | SRCH-02, SRCH-03 | T-03-85 bis T-03-88 | checkpoint | `cd backend && uv run pytest tests/test_discovery_workflow.py -x -q` (Owner OC-1: Bildbeleg P12) | vorhanden | pending |
| 03-18b-T2 | 03-18b | 7 | SRCH-02, SRCH-03 | T-03-85 bis T-03-88 | auto | `bash -n ci/discovery/playpage.sh && bash ci/discovery/playpage.sh --self-test` (offline, muss PLAY SELF-TEST PASSED zeigen) | W0 (Plan legt an) | pending |
| 03-18b-T3 | 03-18b | 7 | SRCH-02, SRCH-03 | T-03-85 bis T-03-88 | auto | `cd backend && uv run pytest tests/test_discovery_workflow.py tests/test_workflow_pins.py tests/test_workflows.py -q` | vorhanden | pending |
| 03-19-T1 | 03-19 | 8 | alle 12 | T-03-63, T-03-64, T-03-65 | auto | `cd backend && uv run pytest tests/test_lockstep_versions.py tests/test_workflows.py tests/test_store_metada...` | vorhanden | pending |
| 03-19-T2 | 03-19 | 8 | alle 12 | T-03-63, T-03-64, T-03-65 | checkpoint | `cd backend && uv run pytest tests/test_trilingual.py -x -q` | vorhanden | pending |
| 03-19-T3 | 03-19 | 8 | alle 12 | T-03-63, T-03-64, T-03-65 | auto | `cd backend && uv run pytest tests/test_trilingual.py tests/test_public_texts.py tests/test_public_artifacts...` | vorhanden | pending |
| 03-20-T1 | 03-20 | 9 | alle 12 | T-03-66 bis T-03-69 | checkpoint | `BASE=origin/main && test -z "$(git log --format='%an <%ae>' "$BASE"..HEAD \| grep -vx 'street1983nk <k.cheri...` | vorhanden | pending |
| 03-20-T2 | 03-20 | 9 | alle 12 | T-03-66 bis T-03-69 | auto | `SHA=$(git rev-parse HEAD) && A=.planning/phases/03-vorschau-transkripte-in-der-suche/approvals && gh run li...` | vorhanden | pending |
| 03-20-T3 | 03-20 | 9 | alle 12 | T-03-66 bis T-03-69 | checkpoint | `cd backend && uv run pytest -q && uv run ruff check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright...` | vorhanden | pending |
| 03-21-T1 | 03-21 | 10 | SRCH-01, SRCH-02, SRCH-03, MEDIA-04 | T-03-70, T-03-71 | auto | `python -c "import sys,pathlib; bad=[p for p in sys.argv[1:] if any(c in pathlib.Path(p).read_text(encoding=...` | vorhanden | pending |
| 03-21-T2 | 03-21 | 10 | SRCH-01, SRCH-02, SRCH-03, MEDIA-04 | T-03-70, T-03-71 | checkpoint | `cd backend && uv run pytest tests/test_trilingual.py tests/test_ui_assets.py -x -q` | vorhanden | pending |

Zuordnung Anforderung zu Testdatei (aus der Research, unverändert gültig):

| Requirement | Testdatei(en) | Plan |
|-------------|---------------|------|
| MEDIA-01 | test_media_decode.py | 03-05 |
| MEDIA-02 | test_media_timeline.py | 03-05 |
| MEDIA-03 | test_media_hardening.py, test_fetch_keep.py | 03-05, 03-13 |
| MEDIA-04 | test_catch_rule.py, test_preview_worker.py, test_preview_corpus.py | 03-06, 03-13, 03-13b, 03-15 |
| TRANS-01 | test_engine_constants.py, test_engine_model.py, test_models.py, test_model_download.py, test_dockerfile.py | 03-06, 03-10, 03-07, 03-07b |
| TRANS-02 | test_vad_gate.py | 03-06 |
| TRANS-03 | test_catch_rule.py, test_engine_child.py, test_engine_model.py | 03-06, 03-10, 03-13b |
| TRANS-07 | test_preview_store.py, test_preview_worker.py | 03-09, 03-13 |
| TRANS-08 | test_preview_worker.py -k timeline, test_engine_model.py | 03-13, 03-10 |
| SRCH-01 | test_search_tiers.py, ProviderTest.php (CI) | 03-08, 03-12 |
| SRCH-02 | ProviderTest.php, PlayControllerTest.php (CI), test_trilingual.py | 03-12, 03-16, 03-16b |
| SRCH-03 | test_excerpt_states.py, PlayControllerTest.php, search-parity und play-leak (CI) | 03-14, 03-16, 03-17, 03-18b |

*Status: pending, green, red, flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/media_fixtures.py`: erzeugt Beep-/Formatdateien per ffmpeg zur Laufzeit, skip mit Grund ohne ffmpeg (geplant: 03-05 Task 2)
- [ ] ffmpeg im Python-CI-Job (BtbN-Asset mit sha256 wie im Dockerfile) (geplant: 03-05 Task 1)
- [ ] Modell-Cache in CI (Schlüssel = sha256 der Modelle) (geplant: 03-10 Task 3, 03-17 Task 1, 03-18 Task 1)
- [ ] Sprachdatei für e2e (FLEURS-Clip CC-BY-4.0) per Skript mit festem sha256, nicht eingecheckt (geplant: 03-02 Task 2)
- [x] `scripts/research/phase3/` mit den Messskripten (6795ddd); lokale ffmpeg-Pfade vor Push durch Parameter ersetzen (geplant: 03-02 Task 1)
- [ ] Korpus-Test der Abfangregel als markierter Langtest (geplant: 03-15 Task 3)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UI-Abnahme Suche und Abspielseite (alle Zustände aus 03-UI-SPEC.md) | SRCH-01, SRCH-02, D-03-13 | Owner-Regel: gemeinsame Abnahme | Playwright 375/768/1280, hell/dunkel, mit dem Owner |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 180s (je Task-Befehl; Modell- und slow-Tests sind markiert und laufen gezielt bzw. in CI)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
