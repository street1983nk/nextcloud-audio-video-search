---
phase: 5
slug: ressourcen-profile-und-modellbezug
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-11-18
---

# Phase 5: Validation Strategy

> Prüfvertrag je Aufgabe für die Ausführung. Grundlage: 05-RESEARCH.md Abschnitt "Validation Architecture", 05-CONTEXT.md D-05-01 bis D-05-15, 05-UI-SPEC.md (Prüfvertrag für die Abnahme).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 + pytest-asyncio (Backend), phpunit 11.5 (PHP), Playwright (Admin-UI), Shell-Schritte in `.github/workflows/docker.yml` (Container auf amd64 und arm64) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]`, `php/tests/bootstrap.php`, `ci/playwright/playwright.config.ts` |
| **Quick run command** | `cd backend && uv run pytest -q -x tests/test_memory_guard.py tests/test_engine_child.py tests/test_models.py` |
| **Full suite command** | `cd backend && uv run pytest -q -rs --cov=src/audio_video_search_backend --cov-report=term` |
| **Estimated runtime** | ca. 240 Sekunden (Backend voll), Container-Nachweise nur in der CI |

---

## Sampling Rate

- **Nach jedem Task-Commit:** Quick run command plus die neue Testdatei des Tasks.
- **Nach jeder Welle:** Full suite, `uv run ruff check --no-cache .`, `uv run ruff format --check --no-cache .`, `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`, `uv run vulture`; PHP-Tests laufen in `php.yml` (CI).
- **Vor `/gsd:verify-work`:** Full suite grün; `docker.yml` auf beiden Architekturen grün (Wave-0-Messung, OOM, Wächter, Threads, Whisper-Spitzen, Offline-Mitschnitt, jeweils mit Positivkontrolle); Playwright-Admin 3 Breiten hell/dunkel; danach secure-phase (offene Threats mit Severity high blockieren).
- **Max feedback latency:** 240 Sekunden lokal.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | RES-01, RES-02 | T-05-01 | Sonde nur unter `ci/`, nie im Image | unit + Workflow-Struktur | `cd backend && uv run pytest -q tests/test_peak_measurement.py` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | RES-02 | T-05-02 | Push nur nach Owner-Freigabe | checkpoint | Freigabedatei `approvals/push-<sha>` | n/a | ⬜ pending |
| 05-01-03 | 01 | 1 | RES-01, RES-02 | T-05-03 | Messwert aus CI-Artefakt beider Arches, kein Schätzwert | unit | `cd backend && uv run pytest -q tests/test_peak_measurement.py` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | RES-06 | T-05-SC | Owner-Legitimitätsprüfung vor Installation | checkpoint (blocking-human) | `cd backend && ! grep -q "faster-whisper==" pyproject.toml` (vorher) | n/a | ⬜ pending |
| 05-02-02 | 02 | 1 | RES-06, RES-07 | T-05-SC, T-05-05 | exakte Pins 1.2.1/4.8.5/1.31.1, kein Modul importiert `av` | unit | `cd backend && uv run pytest -q tests/test_lock_wheels.py tests/test_boundary.py` | ✅ | ⬜ pending |
| 05-03-01 | 03 | 1 | RES-06 | T-05-06 | Teile aus HF am festen Commit, Gesamt-sha256 = HF-LFS | unit | `cd backend && uv run pytest -q tests/test_whisper_parts_script.py` | ❌ W0 | ⬜ pending |
| 05-03-02 | 03 | 1 | RES-06 | T-05-06 | Teil-sha256 je Teil im JSON, Summe = Größe | unit | `cd backend && uv run pytest -q tests/test_whisper_parts_script.py` | ❌ W0 | ⬜ pending |
| 05-04-01 | 04 | 1 | RES-01, RES-05 | T-05-08 | cpu.max/Affinität fail-safe, Threads nur senken | unit (TDD) | `cd backend && uv run pytest -q tests/test_hardware.py` | ❌ W0 | ⬜ pending |
| 05-04-02 | 04 | 1 | RES-05 | T-05-09 | Fenster über Mitternacht, Zone, Sommerzeit, start==end abgelehnt | unit (TDD) | `cd backend && uv run pytest -q tests/test_schedule.py` | ❌ W0 | ⬜ pending |
| 05-05-01 | 05 | 1 | RES-01, RES-05, PLAT-04 | T-05-10, T-05-11 | Admin-Pflicht + CSRF, strenge Validierung, 409 durchgereicht | phpunit | `cd php && vendor/bin/phpunit --filter 'SettingsController|ResourceFormat'` (CI php.yml) | ✅ erweitern | ⬜ pending |
| 05-05-02 | 05 | 1 | RES-06 | T-05-12 | occ ruft nur ADMIN-Route, kein Pfad in Ausgabe | phpunit | `cd php && vendor/bin/phpunit --filter ModelsCommand` (CI) | ❌ W0 | ⬜ pending |
| 05-06-01 | 06 | 1 | RES-07, RES-01 | T-05-13 | Kataloge DE/de_DE/EN/FR gleich, keine Zahl für Mindest-RAM im Text | unit | `cd backend && uv run pytest -q tests/test_l10n_phase5.py tests/test_trilingual.py` | ❌ W0 | ⬜ pending |
| 05-07-01 | 07 | 2 | RES-02, RES-03 | T-05-14, T-05-15 | oom_score_adj 1000, nice, Wächter je Modell, OOM-Code über memory.events | unit (TDD) | `cd backend && uv run pytest -q tests/test_engine_child.py` | ✅ erweitern | ⬜ pending |
| 05-07-02 | 07 | 2 | RES-05 | T-05-16 | eine Zahl für Env und Bibliothek, kein OMP_THREAD_LIMIT | unit (TDD) | `cd backend && uv run pytest -q tests/test_engine_child.py tests/test_engine_model.py` | ✅ erweitern | ⬜ pending |
| 05-08-01 | 08 | 2 | RES-06 | T-05-17 | Teil falsch: WRONG_DIGEST, .part auf Teilanfang gekürzt | unit (TDD) | `cd backend && uv run pytest -q tests/test_model_parts.py` | ❌ W0 | ⬜ pending |
| 05-08-02 | 08 | 2 | PLAT-04 | T-05-18 | Offline: kein Client, kein DNS | unit | `cd backend && uv run pytest -q tests/test_model_offline.py` | ❌ W0 | ⬜ pending |
| 05-09-01 | 09 | 2 | RES-01, RES-05, RES-07 | T-05-19 | kein Pfad, keine URL im DOM, kein Markup aus Strings | unit + phpunit | `cd backend && uv run pytest -q tests/test_admin_phase5_assets.py` | ❌ W0 | ⬜ pending |
| 05-09-02 | 09 | 2 | RES-01, RES-06 | T-05-19 | Polling nur bei M4 bis M6, Stopp nach 3 Fehlern | unit | `cd backend && uv run pytest -q tests/test_admin_phase5_assets.py` | ❌ W0 | ⬜ pending |
| 05-10-01 | 10 | 2 | RES-06 | T-05-20 | Upload nur nach Owner-Ok | checkpoint (human-action) | n/a | n/a | ⬜ pending |
| 05-10-02 | 10 | 2 | RES-06 | T-05-20 | API-Digest je Asset = Katalog | Skript | `uv run --project backend python -I scripts/models/check_release_digests.py` | ❌ W0 | ⬜ pending |
| 05-11-01 | 11 | 3 | RES-05 | T-05-21 | Thread-Zahl in Herkunft, Store v5 transaktional | unit (TDD) | `cd backend && uv run pytest -q tests/test_provenance.py tests/test_store_migration_v5.py` | ❌ W0 | ⬜ pending |
| 05-12-01 | 12 | 3 | RES-01, RES-02 | T-05-22 | Sperre mit Zahlen, Rückfall, kein Erzwingen | unit (TDD) | `cd backend && uv run pytest -q tests/test_resources.py` | ❌ W0 | ⬜ pending |
| 05-12-02 | 12 | 3 | RES-05, PLAT-04 | T-05-23 | Einstellungen strikt validiert, Offline-Wert vor jedem Versuch | unit | `cd backend && uv run pytest -q tests/test_resources_settings.py` | ❌ W0 | ⬜ pending |
| 05-13-01 | 13 | 4 | RES-06, PLAT-04 | T-05-24, T-05-25 | Backoff, wrong_digest nie geladen, Offline ohne Versuch | unit | `cd backend && uv run pytest -q tests/test_model_worker.py` | ❌ W0 | ⬜ pending |
| 05-14-01 | 14 | 3 | RES-06 | T-05-26 | Image-Stage mit sha256sum -c, 0444, Hash = Katalog | unit | `cd backend && uv run pytest -q tests/test_dockerfile.py` | ✅ erweitern | ⬜ pending |
| 05-14-02 | 14 | 3 | RES-06 | T-05-27 | Volume-Kopie nur bei gleichem Image-sha256 gelöscht; Test-Schalter nie im Release-Image | unit | `cd backend && uv run pytest -q tests/test_image_models.py tests/test_dockerfile.py` | ❌ W0 | ⬜ pending |
| 05-15-01 | 15 | 4 | RES-04, RES-05 | T-05-28 | Fenster-Gate vor Claim, Pause an Stückgrenze, capture ungebremst | unit | `cd backend && uv run pytest -q tests/test_preview_window.py` | ❌ W0 | ⬜ pending |
| 05-15-02 | 15 | 4 | RES-04 | T-05-28 | Vorschau vor Veredelung, neueste zuerst | unit | `cd backend && uv run pytest -q tests/test_compute_order.py` | ❌ W0 | ⬜ pending |
| 05-16-01 | 16 | 5 | RES-01, RES-05, PLAT-04 | T-05-29, T-05-30 | ADMIN-Routen, pydantic strict, 409 profile_locked | unit | `cd backend && uv run pytest -q tests/test_api_resources.py` | ❌ W0 | ⬜ pending |
| 05-16-02 | 16 | 5 | RES-01 | T-05-31 | Eigentest nur über Mindest-RAM, Fixture nur mit Marker | unit | `cd backend && uv run pytest -q tests/test_api_resources.py tests/test_selftest.py` | ❌ W0 | ⬜ pending |
| 05-17-01 | 17 | 4 | RES-07 | T-05-32 | jedes Laufzeitpaket aus uv.lock in THIRD-PARTY.md | unit | `cd backend && uv run pytest -q tests/test_third_party.py` | ❌ W0 | ⬜ pending |
| 05-17-02 | 17 | 4 | RES-07, RES-01 | T-05-32 | README DE/EN/FR gleich, Mindest-RAM = resources.minimum_bytes | unit | `cd backend && uv run pytest -q tests/test_third_party.py tests/test_public_texts.py` | ✅ erweitern | ⬜ pending |
| 05-18-01 | 18 | 6 | RES-02, RES-03 | T-05-33 | `--memory=2g --memory-swap=2g`: OOM trifft nur Kind, Heartbeat lebt | Container | `docker.yml` Job resources-proof (CI) | ❌ W0 | ⬜ pending |
| 05-18-02 | 18 | 6 | RES-02 | T-05-33 | 2 GiB: Start nur mit Bedarf+Reserve; 4 GiB Start (Positivkontrolle) | Container | `docker.yml` (CI) | ❌ W0 | ⬜ pending |
| 05-19-01 | 19 | 6 | RES-01, RES-05, RES-06, RES-07 | T-05-34 | Fixture-Zustände nur im CI-Image | e2e | `npx playwright test admin.spec.ts --grep @phase5` (CI) | ✅ erweitern | ⬜ pending |
| 05-20-01 | 20 | 7 | RES-05 | T-05-35 | CPU-Quote ≤ N+0,5, kein Hängen, gleiche Zahl Env/Bibliothek, amd64+arm64 | Container | `docker.yml` Job threads-proof (CI) | ❌ W0 | ⬜ pending |
| 05-20-02 | 20 | 7 | RES-02 | T-05-35 | turbo/large-v3-Spitze ≤ Katalogbedarf | Container | `docker.yml` (CI) | ❌ W0 | ⬜ pending |
| 05-21-01 | 21 | 8 | PLAT-04 | T-05-36 | Offline: null Pakete nach außen; ohne Offline sichtbar | Container | `docker.yml` Job offline-capture (CI) | ❌ W0 | ⬜ pending |
| 05-21-02 | 21 | 8 | RES-06 | T-05-37 | echter Teil-Download turbo endet `procured` | Container | `docker.yml` (CI) | ❌ W0 | ⬜ pending |
| 05-22-01 | 22 | 9 | alle | T-05-38 | Push nur nach Freigabe | checkpoint | Freigabedatei | n/a | ⬜ pending |
| 05-23-01 | 23 | 10 | RES-01, RES-05, RES-06, RES-07 | T-05-39 | gemeinsame Abnahme | checkpoint (human-verify) | Playwright-Lauf mit Screenshots | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Linux-Spitze von Parakeet (`ru_maxrss` der Kinder, `VmHWM`) in `docker.yml` auf amd64 und arm64 messen (Plan 05-01); erst daraus folgen Parakeet-Bedarf und Mindest-RAM (D-05-09). `minimumBytes` steht nie als Zahl in einem Katalogtext.
- [ ] `backend/tests/test_peak_measurement.py` (Plan 05-01)
- [ ] `backend/tests/test_hardware.py`, `test_schedule.py` (Plan 05-04)
- [ ] `backend/tests/test_resources.py`, `test_resources_settings.py` (Plan 05-12)
- [ ] `backend/tests/test_model_parts.py`, `test_model_offline.py` (Plan 05-08; `test_model_download.py` bleibt unberührt)
- [ ] `ci/oom/` Sonde und Fresser (Plan 05-18), `ci/threads/` (Plan 05-20), `ci/netcap/` (Plan 05-21), nur unter `ci/`, nie im Build-Kontext `backend/`
- [ ] Sprachclip in `docker.yml` (Muster "Fetch the speech clips" aus `python.yml`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Paket-Legitimität faster-whisper 1.2.1, ctranslate2 4.8.5, onnxruntime 1.31.1 | RES-06 | slopcheck lief nicht; Owner-Regel | Plan 05-02 Task 1 |
| Upload der Whisper-Teile in `whisper-2026-11` | RES-06 | nach außen gerichtet, Owner-Regel | Plan 05-10 Task 1 |
| Jeder Push | alle | Owner-Regel | Plan 05-01 Task 2, Plan 05-22 Task 1 |
| Gemeinsame UI-Abnahme (375/768/1280, hell/dunkel) | RES-01, RES-05, RES-06, RES-07 | Owner-Regel gemeinsame Abnahme | Plan 05-23 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 240s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
