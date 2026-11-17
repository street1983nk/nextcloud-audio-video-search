---
phase: 1
slug: zwei-app-ger-st-und-integrationsbeweis
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-11-06
---

# Phase 1: Validation Strategy

> Prüfvertrag je Phase für Rückmeldungen während der Ausführung. Grundlage: 01-RESEARCH.md, Abschnitt "Validation Architecture", und 01-UI-SPEC.md.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 (backend), phpunit 11.5 (php, CI), Playwright (CI-Job `ci/playwright/`, Abspielseite und Admin), GitHub Actions mit HaRP |
| **Config file** | `backend/pyproject.toml`, `php/phpunit.xml` (Wave 0) |
| **Quick run command** | `cd backend && uv run pytest -q -x` |
| **Full suite command** | `cd backend && uv run ruff check . && uv run ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -q`; PHP, Integration und Playwright in CI |
| **Estimated runtime** | ca. 30 Sekunden lokal (Python); CI-Matrix deutlich länger |

---

## Sampling Rate

- **After every task commit:** `cd backend && uv run pytest -q -x`
- **After every plan wave:** volle Python-Gates lokal, dann CI (`python.yml`, `php.yml`, `deploy-harp.yml`)
- **Before `/gsd:verify-work`:** alles grün auf 6 Matrix-Beinen (NC 33/34/35 x amd64/arm64), danach gemeinsame Playwright-Abnahme mit dem Owner (375/768/1280 px, hell/dunkel)
- **Max feedback latency:** 60 Sekunden lokal

---

## Per-Task Verification Map

Die Task-IDs trägt der Planer ein. Zuordnung Anforderung zu Test:

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| PLAT-01 | drei Versionswerte + pyproject + Matrix stimmen (Build exakt) | unit | `uv run pytest tests/test_lockstep_versions.py -x` | ❌ W0 | ⬜ pending |
| PLAT-01 | Upgrade 0.0.1 nach 0.1.0 beider Apps, Daten bleiben | integration | `deploy-harp.yml` Schritt "Upgrade" | ❌ W0 | ⬜ pending |
| PLAT-02 | fünf Zustände + Patch-Hinweis (Major.Minor Fehler, Patch Hinweis) | unit (php) | `composer run test -- --filter BackendStateTest` | ❌ W0 | ⬜ pending |
| PLAT-02 | Drift in beide Richtungen, Suche leer statt Fehler | integration | `deploy-harp.yml` "Drift 1/2/3" | ❌ W0 | ⬜ pending |
| PLAT-02 | Container meldet `companion: missing` | unit + integration | `uv run pytest tests/test_handshake.py -x` | ❌ W0 | ⬜ pending |
| PLAT-03 | Matrix deckt 33/34/35 x amd64/arm64 | unit | `uv run pytest tests/test_workflows.py -x` | ✅ erweitern | ⬜ pending |
| PLAT-03 | Installation + Suche auf 6 Beinen | integration | `deploy-harp.yml` | ✅ teilweise | ⬜ pending |
| PLAY-01 | Eintrag mit Titel, `mm:ss · Ausschnitt`, play-URL mit `?t=`, Kennzeichen "Testtreffer", Mobil-Attribute `fileId` + `path` | unit (php) | `composer run test -- --filter ProviderTest` | ❌ W0 | ⬜ pending |
| PLAY-01 | Klick öffnet Abspielseite, Ausschnitt sichtbar | e2e | Playwright `play.spec.ts` | ❌ W0 | ⬜ pending |
| PLAY-02 | 206-Antwort, `currentTime` ca. t, Home + Gruppenordner + Freigabe | e2e | Playwright `play.spec.ts` | ❌ W0 | ⬜ pending |
| PLAY-02 | 404 ohne Dateinamen bei fehlender Datei oder fehlenden Rechten | e2e + unit (php) | Playwright + `--filter PlayControllerTest` | ❌ W0 | ⬜ pending |
| PLAY-02 | Download-Sperre mit view_without_download aus: Hinweis statt Fehler | e2e | Playwright | ❌ W0 | ⬜ pending |
| TRANS-06 | Provenienz-Pflichtfelder, ältere/gleiche Herkunft abgewiesen, epoch gewinnt | unit | `uv run pytest tests/test_provenance.py -x` | ❌ W0 | ⬜ pending |
| TRANS-06 | Korrektur übersteht Ersatz der Maschinen-Version (Randfälle aus Entscheid 4) | unit | `uv run pytest tests/test_corrections.py -x` | ❌ W0 | ⬜ pending |
| TRANS-06 | Schema-Version, `media_key`-Indirektion, Zeiten als INTEGER ms | unit | `uv run pytest tests/test_store_schema.py -x` | ❌ W0 | ⬜ pending |
| (Index) | Versionsfilter, Anlauf-Abgleich, Analyzer beim Öffnen | unit | `uv run pytest tests/test_index_publish.py tests/test_index_open.py -x` | ❌ W0 | ⬜ pending |
| (Sprache) | DE/EN/FR im Gleichstand, U+00A0 vor `: ; ? !` in FR, keine U+2013/U+2014, keine Emojis | unit | `uv run pytest tests/test_trilingual.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Repo-Umbau `backend/` + `php/`, Pfade in allen Workflows und Tests
- [ ] `php/composer.json`, `php/phpunit.xml`, `php/tests/bootstrap.php` (Findling-Kopie)
- [ ] `backend/tests/test_lockstep_versions.py` (Findling, angepasst auf zwei IDs)
- [ ] `backend/tests/test_trilingual.py`
- [ ] Testmedien `testdata/tone-90s.webm`, `testdata/tone-90s.ogg` (generiert, freie Lizenz)
- [ ] Playwright-Gerüst im CI-Job (`ci/playwright/`, nur CI)
- [ ] Matrix 33/34/35 x amd64/arm64 in `deploy-harp.yml`, PHP-App-Installation im Setup

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Optische Abnahme Abspielansicht, Admin-Sektion, Suchtreffer | PLAY-01, PLAY-02, PLAT-02 | Owner-Regel: UI-Abnahme gemeinsam | Playwright-Screens 375/768/1280 px, hell/dunkel, gemeinsam mit dem Owner ansehen |
| Mobil-App öffnet Treffer nativ ab 0:00 | PLAY-01 | Mobil-Apps nicht in CI | Treffer in Android-/iOS-App antippen, Datei öffnet nativ |
| Zertifikatsantrag `audio_video_search_backend` gestellt | PLAT-01 | externer Vorgang (PR #1417) | PR-Status prüfen |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-11-06 (Plan-Checker Runde 2)
