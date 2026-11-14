---
phase: 02-erfassung-aller-dateien
plan: 21
subsystem: release-upgrade-doku
tags: [version, lockstep, upgrade, positive-control, docs, trilingual, changelog]
requires: [02-18, 02-19, 02-20]
provides:
  - "Version 0.2.0 im Lockstep (beide info.xml, Image-Tag, pyproject, uv.lock, Playwright admin.spec)"
  - "deploy-harp.yml Job upgrade: prev/ per git worktree aus 82f1655 (Release 0.1.0), Positivkontrolle vorher, Prüfung der Migration nachher"
  - "Gate real_prev_findings in test_workflows.py, Gate _playwright_findings in test_lockstep_versions.py"
  - "Abschnitt Erfassung in docs/install.md, install.en.md, install.fr.md; README-Status 0.2.0; CHANGELOG 0.2.0"
affects: [02-22]
tech-stack:
  added: []
  patterns:
    - "Upgrade-Beweis vom echten Release-Commit, nicht von einer umbenannten Kopie des eigenen Commits"
    - "Positivkontrolle liest Dateien direkt (stdlib sqlite3), nicht über die App; Gegenprobe oc_appconfig gegen leere oder falsche Datei"
key-files:
  created: []
  modified:
    - php/appinfo/info.xml
    - backend/appinfo/info.xml
    - backend/pyproject.toml
    - backend/uv.lock
    - .github/workflows/deploy-harp.yml
    - backend/tests/test_workflows.py
    - backend/tests/test_lockstep_versions.py
    - ci/playwright/admin.spec.ts
    - docs/install.md
    - docs/install.en.md
    - docs/install.fr.md
    - README.md
    - README.en.md
    - README.fr.md
    - CHANGELOG.md
    - .planning/debug/discovery-push9-exclude-after.md
decisions:
  - "Nach dem Update steht die Probe in sample_ref (D-02-15, migrate.py), nicht in file_ref mit storage_id 0; der Job prüft sample_ref mit Transkript und dass keine Zeile in file_ref state sample oder eine nicht ganzzahlige storage_id hat"
  - "FR-Bezeichnung der files_external-Option wie in nextcloud/server fr.json: Identifiants de connexion, sauvegarder dans la base de données"
metrics:
  duration: "ca. 90 min (mit Checkpoint)"
  completed: 2026-11-14
  tasks: "3 von 3"
---

# Phase 2 Plan 21: Version 0.2.0, Upgrade-Beweis vom echten 0.1.0, Doku DE/EN/FR Summary

Lockstep 0.2.0, ein Upgrade-Job, der das echte 0.1.0 aus Commit 82f1655 per git worktree baut und vor dem Update positiv prüft (schema_version 1, Probe in file_ref mit storage_id '', keine oc_avs_-Tabelle), danach Schema 2, sample_ref mit Transkript, die drei oc_avs_-Tabellen und `occ status --json`; dazu die vom Owner freigegebene Erfassungs-Doku in drei Sprachen.

## Commits

| Task | Commit | Inhalt |
|------|--------|--------|
| Vorab | f61cb37 | Debug-Notiz Push 9 resolved (Lauf 43565101302, 20/20) |
| 1 RED | ea12c5d | Gate real_prev_findings plus 3 Selbsttests, 8 rot |
| 1 GREEN | f06d519 | 0.2.0, Upgrade-Job vom echten 0.1.0, admin.spec 0.2.0, CHANGELOG-Überschrift |
| 2 | (Checkpoint) | Owner-Freigabe 14.11.2026 "Freigegeben (Empfohlen)" |
| 3 | b1463f5 | Erfassung DE/EN/FR, README-Status, CHANGELOG 0.2.0 |
| Zusatz RED | 9c0e2fa | Lockstep-Gate admin.spec.ts, 3 Selbsttests rot |
| Zusatz GREEN | 621fce6 | Regel umgesetzt, Gegenprobe mit 0.1.0 in admin.spec rot |

## Belege

- ruff, ruff format (76), pyright 0, vulture 0, pytest `-p no:xdist` 1023 bestanden
- trilingual, public_texts, public_artifacts: 32 bestanden
- Container-Snippets des Jobs lokal gegen einen v1-Store aus dem Schema von 82f1655, vor und nach migrate_v1_to_v2: Positiv- und Negativfälle wie erwartet
- YAML lädt, `bash -n` auf jeden run-Block des Jobs upgrade grün
- Gedankenstriche im Diff: 0, Positivkontrolle 1
- Kein Docker gestartet: an PHP nur die Version in info.xml geändert, XML parst

## Deviations from Plan

1. [Regel 1] Plan: "nachher Probe storage_id 0". Der Code verschiebt Proben bei der Migration nach sample_ref (ohne storage_id). Geprüft wird darum sample_ref mit Transkript und keine alte Zeile in file_ref.
2. [Regel 3] ci/playwright/admin.spec.ts hatte `VERSION = '0.1.0'` fest; auf 0.2.0 gesetzt, sonst wäre der Hauptlauf von deploy-harp rot. Auf Wunsch des Owners dazu das Lockstep-Gate (9c0e2fa, 621fce6).
3. [Regel 3] test_store_metadata verlangt `## 0.2.0` im CHANGELOG; in Task 1 nur die Überschrift, Einträge nach der Freigabe in Task 3.
4. Nextcloud-Datenbank per python3 statt sqlite3-CLI gelesen, mit oc_appconfig als Gegenprobe. `git -C app-src worktree add --detach "${GITHUB_WORKSPACE}/prev"` statt wörtlich `git worktree add prev`.
5. FR-Text: freigegeben war "Identifiants de connexion, enregistrés dans la base de données"; nextcloud/server apps/files_external/l10n/fr.json (stable33, stable34, stable35, master) sagt "Identifiants de connexion, sauvegarder dans la base de données". Eingespielt ist die echte Bezeichnung.

## Offene Punkte

- DE-Bezeichnung: freigegeben und eingespielt ist "Anmeldedaten, in Datenbank speichern". files_external sagt in `de` "Anmeldedaten in Datenbank speichern" (ohne Komma), in `de_DE` "Anmeldedaten des Benutzers (in Datenbank gespeichert)". Owner-Entscheid, ob angleichen.
- Der Upgrade-Job läuft erst in Plan 22 (CI): Build des 0.1.0-Images heute und gleiche Probetreffer nach der Migration sind lokal nicht belegt.

## Self-Check: PASSED

Commits f61cb37, ea12c5d, f06d519, b1463f5, 9c0e2fa, 621fce6 vorhanden; alle geänderten Dateien vorhanden.
