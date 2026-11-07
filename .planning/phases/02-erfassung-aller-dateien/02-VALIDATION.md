---
phase: 2
slug: erfassung-aller-dateien
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-11-07
---

# Phase 2: Validation Strategy

> Prüfvertrag je Phase für Rückmeldungen während der Ausführung. Grundlage: 02-RESEARCH.md (Validation Architecture, D-02-07-Abschnitt) und 02-CONTEXT.md (D-02-01 bis D-02-13).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.2.0 (backend), phpunit 11.5 (php, nur CI), Bash + Samba + MinIO + sqlite3 im CI-Workflow "Discovery acceptance" |
| **Config file** | `backend/pyproject.toml`, `php/phpunit.xml`, `.github/workflows/discovery-e2e.yml` |
| **Quick run command** | `cd backend && uv run pytest -q -x` |
| **Full suite command** | `cd backend && uv run ruff check . && uv run ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -q`; PHP, Integration und Abnahme in CI |
| **Estimated runtime** | ca. 40 Sekunden lokal (seriell); CI deutlich länger |

---

## Sampling Rate

- **After every task commit:** betroffene pytest-Datei, dann `cd backend && uv run pytest -q -x`
- **After every plan wave:** volle Python-Gates lokal; CI an den drei Push-Punkten (Plan 11 nach Welle 3, Plan 17 nach Welle 7, Plan 22 am Ende), jeder Push hinter der Freigabedatei je SHA
- **Before `/gsd:verify-work`:** Python gates, PHP gates, Deploy through HaRP (mit Upgrade 0.1.0 nach 0.2.0) und Discovery acceptance auf sechs Beinen grün, inklusive Samba-Kontrolle, compare-Selbsttests, access-log-Kontrolle und Kontrollbein leak-control
- **Max feedback latency:** 60 Sekunden lokal

---

## Per-Task Verification Map

| Requirement | Behavior | Test Type | Automated Command | Plan | Status |
|-------------|----------|-----------|-------------------|------|--------|
| DISC-01 | Schema v2, Migration verlustfrei | unit | `uv run pytest tests/test_store_migration_v2.py -x` | 02 | ⬜ pending |
| DISC-01 | Warteschlange, Claim, describe mit fester Schlüsselmenge | unit (php) | `php.yml` QueueMapperTest, QueueServiceTest, QueueControllerTest | 03 | ⬜ pending |
| DISC-01 | Erst-Crawl nach Handshake, eine Vergleichsstelle | unit (php) + Gate | `php.yml` StorageCrawlJobTest; `uv run pytest tests/test_php_gates.py -x` | 06 | ⬜ pending |
| DISC-01 | alle Medien aller Nutzer, Gruppenordner, Freigaben im Vorrat | e2e | Discovery acceptance, Phasen initial, shares | 01, 04 | ⬜ pending |
| DISC-02 | externe Speicher ab Werk, Sitzungs-Speicher übersprungen mit Grund | unit (php) + e2e | `php.yml` StorageClassifierTest; Phase initial (M2, M4, M5) | 12 | ⬜ pending |
| DISC-02 | Speicherschalter | e2e | Phase exclude-storage-after | 16, 18 | ⬜ pending |
| DISC-03 | Ausschluss vor erstem Durchlauf: nie im Vorrat, nie im Zugriffslog | e2e | neverFetched-Prüfung mit Selbsttest (eingespritzte Zeile) | 16 | ⬜ pending |
| DISC-03 | letzter Verweis: Ausschluss vergisst, Löschen merkt vor (D-02-04, D-02-13) | unit + e2e | `uv run pytest tests/test_exclusion_forget.py -x`; Phasen exclude-after, delete-user, reattach | 15, 18 | ⬜ pending |
| DISC-03 | Nutzer-Ausschluss nach Durchlauf, Kopien anderer bleiben (D-02-11) | unit (php) + e2e | ExclusionServiceTest; Phase exclude-user-after | 16, 18 | ⬜ pending |
| DISC-04 | Ereignisse in Minuten | e2e | Phase upload (<= 300 s) | 07 | ⬜ pending |
| DISC-04 | Fremdänderung nach erzwungenem Rescan | e2e | Phase foreign-change mit `occ audio_video_search:rescan` | 14 | ⬜ pending |
| DISC-04 | Sweep vor dem Tor, Walk über requeue | unit | `uv run pytest tests/test_reconcile_sweep.py tests/test_reconcile_walk.py -x` | 20 | ⬜ pending |
| DISC-05 | Inhalts-Schlüssel per vollständigem Download, Längenprüfung | unit | `uv run pytest tests/test_capture.py -x` | 08 | ⬜ pending |
| DISC-05 | Zähler Teilmenge des Nenners | unit (Eigenschaftstest) | `uv run pytest tests/test_coverage_count.py -x` | 09 | ⬜ pending |
| DISC-05 | Lesebeweis, erneuter Beweis, kein Abschaltweg (D-02-01a, D-02-10, D-02-12) | unit + Gate + e2e | `uv run pytest tests/test_read_proof.py tests/test_read_proof_gate.py -x`; Phasen read-proof, reprove; Kontrollbein leak-control | 13, 20 | ⬜ pending |
| DISC-05 | transcribed exakt gegen Proben-Ledger | e2e | compare.sh, Positivkontrollen vanish und delete-user | 04 | ⬜ pending |
| DISC-06 | Umbenennen, Taggen, Wiederherstellen ohne Download | e2e | Zugriffslog-Zählung, Phasen rename, tag, restore | 05, 15 | ⬜ pending |
| (Upgrade) | 0.1.0 nach 0.2.0 vom echten Commit, Vorher-Kontrolle | integration | Deploy through HaRP, Job upgrade | 21 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `.github/workflows/discovery-e2e.yml`, `ci/discovery/topology.sh`, `backend/tests/test_discovery_workflow.py` (Plan 01, Welle 1)
- [ ] `ci/discovery/truth.sh`, `ledger.sh`, `compare.sh`, `controls.sh` (Plan 04)
- [ ] `backend/tests/test_store_migration_v2.py` (Plan 02)
- [ ] `backend/tests/test_read_proof.py`, `test_read_proof_gate.py` zuerst rot (Plan 13, Task 1)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Texte DE/EN/FR vor dem Commit | I18N (Owner-Regel) | Owner-Freigabe | Plan 21 Task 2 |
| Push-Freigaben | Prozess (Owner-Regel) | Owner-Entscheid | Freigabedatei je SHA, Plan 11, 17, 22 |

Keine UI in Phase 2 (D-02-06: Anzeige per occ, Oberfläche in Phase 9).

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (Plan-Checker Runde 2)
