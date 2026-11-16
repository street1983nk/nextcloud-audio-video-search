---
phase: 4
slug: suchqualit-t-und-export
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-16
---

# Phase 4 , Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (backend, .venv), phpunit 11.5.x (php/), Playwright (ci/playwright) |
| **Config file** | backend/pyproject.toml, php/phpunit.xml, ci/playwright/playwright.config.ts |
| **Quick run command** | `.venv/Scripts/python -m pytest tests/<touched area> -q` (backend) bzw. `php vendor/bin/phpunit --filter <Klasse>` (php) |
| **Full suite command** | `.venv/Scripts/python -m pytest -q` + ruff/pyright/vulture; php vendor/bin/phpunit |
| **Estimated runtime** | Backend-Vollsuite ~2-4 min lokal; PHP ~1 min |
| **Besonderheit** | Untertitel-Beweis (EXP-02) braucht einen UNABHÄNGIGEN SRT/VTT-Parser als Prüfer (webvtt-py/srt nur dev, Writer bleibt eigener Code); Gegenprobe nie mit dem Muster der Umsetzung |

---

## Sampling Rate

- **After every task commit:** Run quick command des berührten Bereichs
- **After every plan wave:** Run full suite (backend + php, je nach berührten Teilen)
- **Before `/gsd:verify-work`:** Full suite must be green (inkl. ruff --no-cache, pyright mit --pythonpath .venv/Scripts/python.exe, vulture)
- **Max feedback latency:** 240 seconds

---

## Per-Task Verification Map

> Wird vom Planner je Task gefüllt (Task-IDs entstehen erst mit den PLAN.md-Dateien).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (vom Planner zu füllen) | | | SRCH-04..06, EXP-01..04 | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Unabhängiger Untertitel-Parser als dev-Abhängigkeit prüfen und pinnen (webvtt-py, srt) , Checkpoint vor dem Einbau (Research: Pakete ungeprüft)
- [ ] Testdaten für Zahlen/Wortformen-Suchfälle (DE/EN/FR) als Fixture-Skript, keine Binärdateien im Repo

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UI-Abnahme der neuen Flächen (Buttons, Spur, Banner) | EXP-01/03, UI-SPEC | Owner-Regel: Abnahme gemeinsam per Playwright, 3 Breiten, hell/dunkel | Screenshots aus CI, Owner-Sichtung |
| Owner-Freigabe der Texte T13 bis T35 | EXP-04, UI-SPEC | Textfreigabe vor dem Bau ist Owner-Entscheid | Textliste vorlegen |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 240s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
