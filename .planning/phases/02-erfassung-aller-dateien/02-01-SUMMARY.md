---
phase: 02-erfassung-aller-dateien
plan: 01
subsystem: abnahme-ci
tags: [d-02-07, samba, leak-control, topologie, workflow-gate]
requires: []
provides:
  - "Workflow 'Discovery acceptance' (.github/workflows/discovery-e2e.yml): Job discovery (ein Bein je Push, sechs Beine mit workflow_dispatch legs=all), Job leak-control (gepatchte Kopie unter RUNNER_TEMP, nur lokale Registry)"
  - "ci/discovery/topology.sh: Unterbefehle samba, part-a, part-b, control und 17 Vorgänge (upload_new bis reattach)"
  - "ci/discovery/ids.env (nur CI): ID_<NUTZER>_<PFAD>, STORAGE_SMB_<NUTZER>, STORAGE_SMB_TEIL_ANA, M1_ID bis M5_ID, M1_MODE, TEAM_FOLDER_ID, TAG_SPERRE, TAG_HARMLOS, UPLOAD_ID/UPLOAD_AT, OVERWRITE_AT, FOREIGN_AT"
  - "backend/tests/test_discovery_workflow.py: workflow_findings, leak_findings, topology_findings mit Selbsttests"
affects: [02-04, 02-11, 02-13, 02-17, 02-22]
tech-stack:
  added: []
  patterns:
    - "Matrix per fromJSON(inputs.legs == 'all' && '<sechs>' || '<eins>'), Gate liest beide JSON-Listen"
    - "php -S direkt mit PHP_CLI_SERVER_WORKERS=8 und -d max_execution_time=120 (composer serve setzt Worker selbst und reicht keine ini-Option durch)"
    - "Patch nur per git -C \"${LEAK_ROOT}\" apply auf eine Kopie unter RUNNER_TEMP, danach git -C app-src diff --quiet"
    - "Samba-Teil (topology.sh samba) vor der Samba-Kontrolle, Nextcloud-Teil (part-a) danach, beide vor der ExApp"
key-files:
  created:
    - .github/workflows/discovery-e2e.yml
    - ci/discovery/topology.sh
    - ci/discovery/README.md
    - backend/tests/test_discovery_workflow.py
  modified:
    - .gitignore
decisions:
  - "S3-Bein gegen SeaweedFS 4.52 (chrislusf/seaweedfs per Index-Digest, amd64+arm64) statt MinIO: minio/minio ist auf Docker Hub nicht mehr vorhanden, quay.io verweigert anonymes Ziehen (geprüft 07.11.)"
  - "Samba-Aufbau als eigener Unterbefehl samba vor controls.sh samba, damit die Reihenfolge aus Plan 04 (Samba-Kontrolle vor part-a) hält"
  - "part-b = erneuter Scan und ids.env nach der Registrierung, plus Ausschlussliste in occ-exclusions.txt"
  - "Ausschluss-Fallback vor Plan 16 per occ config:app:set excluded_users|excluded_groups|excluded_folders|excluded_storages als JSON-Liste"
metrics:
  duration: "ca. 60 min"
  completed: 2026-11-07
  tasks: 2
  files: 5
---

# Phase 2 Plan 01: Abnahme-Workflow und Topologie Summary

Der Workflow "Discovery acceptance" baut auf echtem Samba eine Instanz mit unterschiedlicher Sicht je Nutzer, DENY READ (A6), Sitzungs-Mount, zweiter Konfiguration derselben Freigabe, lokalem und S3-Speicher, Gruppenordner mit ACL, Freigaben, files_accesscontrol und Ausschlüssen vor dem ersten Durchlauf; ein Kontrollbein baut das Image ohne Lesebeweis nur in die lokale Registry. Er ist erwartbar rot, bis die Erfassung steht.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Workflow-Gerüst und Workflow-Gate | 161edb7 | discovery-e2e.yml, test_discovery_workflow.py |
| 2 | Topologie und README | 2743d95 | topology.sh, README.md, test_discovery_workflow.py, .gitignore |

## Prüfungen

- `bash -n ci/discovery/topology.sh` grün; shellcheck lokal nicht vorhanden.
- `uv run pytest tests/test_discovery_workflow.py` 17 grün (davon 10 Selbsttests, die an kaputten Kopien anschlagen müssen).
- Volle Python-Gates seriell grün: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 407 grün.
- Ausführung in CI erst ab Plan 11 (Push nur nach Owner-Freigabe). Bis dahin fehlen controls.sh, compare.sh, truth.sh (Plan 04) und ci/leak-control/read-proof-off.patch (Plan 13); beide Jobs schlagen erwartbar fehl.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] MinIO-Image nicht mehr beziehbar, S3 über SeaweedFS**
- **Found during:** Task 1
- **Issue:** `minio/minio` liefert auf Docker Hub `insufficient_scope` (Repository weg), quay.io verlangt Anmeldung; ein Digest-Pin war nicht möglich.
- **Fix:** `chrislusf/seaweedfs@sha256:57877e32...ce59` (Tag 4.52, Index mit amd64 und arm64), `server -s3` mit Zugangsdaten aus Job-Variablen; Bucket legt das Nextcloud-Backend amazons3 selbst an, kein `mc` nötig. Startet der Server nicht, wird der Schritt rot.
- **Files modified:** .github/workflows/discovery-e2e.yml, ci/discovery/README.md
- **Commit:** 161edb7
- **Owner-Hinweis:** Ersatz eines Testwerkzeugs, nicht des Produkts; bitte vor dem Push in Plan 11 bestätigen.

**2. [Rule 3 - Blocking] Reihenfolge Samba-Kontrolle vor part-a**
- **Found during:** Task 2
- **Issue:** Plan 04 verlangt `controls.sh samba` vor `topology.sh part-a`, part-a sollte aber die Samba-Konten anlegen.
- **Fix:** eigener Unterbefehl `samba` (Server, Konten, Inhalt, DENY-ACE) vor der Kontrolle; part-a enthält nur die Nextcloud-Seite.
- **Commit:** 2743d95

**3. [Rule 2] ids.env in .gitignore**
- Erzeugte Datei mit Paarung Name zu file_id gehört nicht ins Repo, wie ci/fileids.env. Commit 2743d95.

## Known Stubs

- Workflow-Schritte "Wait until the work stock is complete" und "Compare the initial work stock" rufen compare.sh/truth.sh aus Plan 04; Plan 04 ersetzt sie durch Selbsttests, Zugriffslog-Kontrolle und je Phase einen Block.
- `topology.sh control` legt nur Nutzer, M1 und IDs an; kontrolle.webm samt DENY baut `controls.sh leak` (Plan 04).

## Annahmen für den ersten CI-Lauf

- `password::logincredentials` speichert bei Basic-Auth über WebDAV; sonst greift der protokollierte Rückfall auf persönliche Mounts.
- `files_external:create --user` funktioniert mit `allow_user_mounting=yes` (nur im Rückfall).
- groupfolders-ACL-Syntax `groupfolders:permissions <id> --user ben <pfad> -- +read -share` laut README stable33.

## Self-Check: PASSED

- FOUND: .github/workflows/discovery-e2e.yml, ci/discovery/topology.sh, ci/discovery/README.md, backend/tests/test_discovery_workflow.py
- FOUND: 161edb7, 2743d95
