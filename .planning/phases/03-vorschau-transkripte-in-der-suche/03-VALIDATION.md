---
phase: 3
slug: vorschau-transkripte-in-der-suche
status: draft
nyquist_compliant: false
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

Wird vom Planer je Task ausgefüllt. Zuordnung Anforderung zu Test (aus der Research):

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| MEDIA-01 | 10 Formate dekodieren, MP4 mit moov am Ende > 10 MB | unit (Medien per Test erzeugt) | `uv run pytest tests/test_media_decode.py -x` | W0 | pending |
| MEDIA-02 | Standardspur/erste Spur; Beep mit `-itsoffset 2` bei 7,0 s ± 5 ms; Stücke ± 5 ms | unit | `uv run pytest tests/test_media_timeline.py -x` | W0 | pending |
| MEDIA-03 | ffconcat-als-mp3 abgewiesen, Zufallsbytes/abgeschnitten = damaged, CENC = protected, Wandzeit-Abbruch, Plattenreserve (D-03-17) | unit | `uv run pytest tests/test_media_hardening.py -x` | W0 | pending |
| MEDIA-04 | Dateiurteil aus Zählern (Tabelle M-9), zweiter VAD-Durchgang bis 60 s (D-03-16) | unit | `uv run pytest tests/test_catch_rule.py -x` | W0 | pending |
| TRANS-01 | Spike-3-Konstanten unverändert; Engine liefert Wörter | unit + Modelltest (CI mit Modell-Cache) | `uv run pytest tests/test_engine_constants.py tests/test_engine_model.py -x` | W0 | pending |
| TRANS-02 | kein Einstellungs-/Env-/Routenweg für VAD | unit (Quelltext-Gate) | `uv run pytest tests/test_vad_gate.py -x` | W0 | pending |
| TRANS-03 | Fensterregel mit Fällen aus M-8 (D-03-19) | unit | `uv run pytest tests/test_catch_rule.py -x` | W0 | pending |
| TRANS-07 | Stückgrenze, keine Dopplung, Fortsetzen bei k+1, Unterbrechen durch Ereignis-Job (D-03-06) | unit (Engine gefälscht) | `uv run pytest tests/test_preview_worker.py -x` | W0 | pending |
| TRANS-08 | Wortzeit + Stückversatz = Medienzeit; Link rundet abwärts | unit | `uv run pytest tests/test_preview_worker.py -k timeline -x` | W0 | pending |
| SRCH-01 | Stufen-Folge, Auffüllen auf `limit` (D-03-15), offset ohne Dubletten/Lücken | unit + phpunit | `uv run pytest tests/test_search_tiers.py -x`; CI `php.yml` | W0 | pending |
| SRCH-02 | Stufe `preview`, Untertitel mit "Vorläufig"/"Preliminary"/"Provisoire" | phpunit + `test_trilingual.py` | CI `php.yml`; `uv run pytest tests/test_trilingual.py -x` | teilweise | pending |
| SRCH-03 | Paritätstest HTTP-Pfad (entzogene Freigabe, Gruppenordner-ACL, Papierkorb) | e2e (CI) | `discovery-e2e.yml`, neue Phase `search-parity` | W0 | pending |

*Status: pending, green, red, flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/media_fixtures.py`: erzeugt Beep-/Formatdateien per ffmpeg zur Laufzeit, skip mit Grund ohne ffmpeg
- [ ] ffmpeg im Python-CI-Job (BtbN-Asset mit sha256 wie im Dockerfile)
- [ ] Modell-Cache in CI (Schlüssel = sha256 der Modelle)
- [ ] Sprachdatei für e2e (FLEURS-Clip CC-BY-4.0) per Skript mit festem sha256, nicht eingecheckt
- [x] `scripts/research/phase3/` mit den Messskripten (6795ddd); lokale ffmpeg-Pfade vor Push durch Parameter ersetzen
- [ ] Korpus-Test der Abfangregel als markierter Langtest

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UI-Abnahme Suche und Abspielseite (alle Zustände aus 03-UI-SPEC.md) | SRCH-01, SRCH-02, D-03-13 | Owner-Regel: gemeinsame Abnahme | Playwright 375/768/1280, hell/dunkel, mit dem Owner |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
