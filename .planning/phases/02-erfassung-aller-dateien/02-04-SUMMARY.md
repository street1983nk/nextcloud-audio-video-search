---
phase: 02-erfassung-aller-dateien
plan: 04
subsystem: abnahme-ci
tags: [d-02-07, wahrheit, ledger, selbsttest, positivkontrolle]
requires: [02-01]
provides:
  - "ci/discovery/truth.sh <phase>: truth-<phase>.json mit files, unreadable, N_active, Y, neverFetched, sha (file_id -> sha256), unmapped"
  - "ci/discovery/ledger.sh add|sample|drop-where-gone|expected (Proben des Tests, erwartetes transcribed)"
  - "ci/discovery/compare.sh wait|--self-test|prepare <phase>|mark <phase>|appear <id> <since> <limit>|<phase>"
  - "ci/discovery/controls.sh samba|access-log|leak"
  - "ci/discovery/common.sh: PHASES (zwanzig Phasen in Reihenfolge), reached, gateway_lines, search_ids, password_of"
  - "Workflow-Schritte: Self tests of the comparison, Wait, Access log positive control, Run the phases, The verdict of all phases"
affects: [02-11, 02-13, 02-17, 02-22]
tech-stack:
  added: []
  patterns:
    - "file_id je Pfad über oc_mounts (user_id, mount_point) -> storage_id und root_id -> Pfad der Wurzel -> oc_filecache (storage, path)"
    - "S3-Wahrheit über curl --aws-sigv4 direkt gegen die S3-API, nicht über Nextcloud"
    - "Selbsttest: Erwartung aus der echten Ausgabe, Verschiebung um 1 muss genau die eine Prüfung neu rot machen (Differenz zur Grundlinie)"
    - "Je Phase: prepare (Proben, Kontrollen), mark (Log-Offset, Vorrat, Status), Vorgang, wait, truth, compare"
key-files:
  created:
    - ci/discovery/common.sh
    - ci/discovery/truth.sh
    - ci/discovery/ledger.sh
    - ci/discovery/compare.sh
    - ci/discovery/controls.sh
  modified:
    - .github/workflows/discovery-e2e.yml
    - backend/tests/test_discovery_workflow.py
    - ci/discovery/README.md
decisions:
  - "Gemeinsame Hilfen in ci/discovery/common.sh; truth.sh bindet sie ein, darum gilt das Gate ohne App-Code auch für common.sh"
  - "ledger.sh drop-where-gone nur nach den drei Ausschluss-Phasen (Transkript vergessen); gelöschter Nutzer und Papierkorb verwaisen nur, der Eintrag bleibt für reattach"
  - "Die Korrektur auf z schreibt compare.sh prepare exclude-after per docker exec python3 mit stdlib sqlite3; state.db-Prüfungen lesen eine Kopie (Datei, -wal, -shm) mit sqlite3 des Runners"
  - "Die 300-s-Grenze beim Upload misst compare.sh appear direkt nach dem Vorgang, vor dem Warten"
  - "Neue file_ids nach Umbenennen, Verschieben und Wiederherstellen kommen aus ids.env (topology.sh record), die Schnappschüsse aus mark"
metrics:
  duration: "ca. 75 min"
  completed: 2026-11-07
  tasks: 3
  files: 8
---

# Phase 2 Plan 04: Unabhängige Wahrheit, Vergleich und Positivkontrollen Summary

Die Abnahme D-02-07 hat jetzt ihr Urteil: truth.sh baut die Wahrheit je Phase ohne eine Zeile App-Code (find, smbclient, S3-API, sqlite3 auf owncloud.db, sha256sum), ledger.sh kennt die eigenen Proben, compare.sh vergleicht zwanzig Phasen exakt und prüft sich vorher selbst, controls.sh hält die Samba-, Zugriffslog- und Leck-Kontrolle.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Wahrheit und Ledger | e256a1a | common.sh, truth.sh, ledger.sh |
| 2 | Vergleich mit Selbsttests und Warten | 43b310c | compare.sh |
| 3 | Kontrollen, Workflow-Schritte und Gate | e6ecdbe | controls.sh, discovery-e2e.yml, test_discovery_workflow.py, README.md |

## Prüfungen

- `bash -n` grün für common.sh, truth.sh, ledger.sh, compare.sh, controls.sh; shellcheck lokal nicht vorhanden.
- compare.sh lokal gegen ein gefälschtes occ: `--self-test` meldet je Verschiebung genau files_count, contents, transcribed und never_in_log als neu rot und endet grün; ohne passende neverFetched-ID (alle schon im Log) wählt er eine freie; `compare.sh initial` mit absichtlich falschen ids.env-Werten nennt genau die falschen Prüfungen und `PHASE FAIL`.
- jq-Logik von truth.sh (Gruppierung je file_id, Y über verschiedene sha256) und ledger.sh expected lokal mit Beispieldaten geprüft.
- test_discovery_workflow.py 25 grün (8 neu, davon 6 Selbsttests an kaputten Kopien).
- Volle Python-Gates seriell grün: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 447 grün.
- Ausführung in CI erst ab Plan 11 (Push nur nach Owner-Freigabe); bis dahin fehlen occ :files/:status (Plan 10), :reconcile --reprove (Plan 20), :rescan (Plan 14) und der Patch für das Kontrollbein (Plan 13).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Gemeinsame Datei common.sh**
- **Found during:** Task 1
- **Issue:** Phasenfolge, Pfade, Passwörter und die Zugriffslog-Zählung brauchen alle vier Skripte; vierfach kopiert würden sie auseinanderlaufen.
- **Fix:** ci/discovery/common.sh, von allen vier eingebunden; das Gate prüft auch common.sh auf App-Code und die Phasenliste gegen die Liste im Test.
- **Commit:** e256a1a

**2. [Rule 2] Zusätzliche Positivkontrollen in den Phasen**
- read-proof: ana muss ihre eigene Kopie finden, bevor "ben findet nichts" etwas sagt.
- reprove: cem muss widerruf.webm vor dem Widerruf finden (prepare), sonst ist "cem findet es danach nicht" leer.
- **Commit:** 43b310c

**3. [Rule 3] Leck-Schritt braucht MEDIA_DIR und ACCESS_LOG**
- controls.sh leak baut kontrolle.webm aus dem Testton; der Workflow-Schritt bekam MEDIA_DIR und ACCESS_LOG. Commit e6ecdbe.

**4. Ledger-Befehl sample**
- Neben `add`, `drop-where-gone` und `expected` hat ledger.sh `sample <fileId> <user> <truth.json|sha256>`, damit jeder Aufruf von `occ audio_video_search:sample` über das Ledger läuft (auch im Kontrollbein, wo es keine truth.json gibt).

## Annahmen für den ersten CI-Lauf

- `occ audio_video_search:files --json --all` liefert `{"files": [...]}` oder eine Liste; compare.sh nimmt beides. Felder fileId, mediaId, storageId, state, stage, reason (Plan 09/10).
- `status.skippedStorages[]` nennt die Mount-ID von M2 in einem seiner Felder und `reason: "session_credentials"` (Plan 12).
- Externe Speicher haben in oc_filecache Pfade relativ zur Speicherwurzel, Homes `files/...`; der Gruppenordner steht für ana unter `/ana/files/Team/` in oc_mounts.
- php -S schreibt Zugriffszeilen der Form `[...] [200]: GET /ocs/v2.php/apps/audio_video_search/files/<id>?...`.
- `occ audio_video_search:sample` arbeitet synchron (Transkript veröffentlicht, wenn der Befehl zurückkehrt).

## Known Stubs

Keine im Prüfcode. Die Abnahme bleibt erwartbar rot, bis die Erfassung steht.

## Self-Check: PASSED

- FOUND: ci/discovery/common.sh, truth.sh, ledger.sh, compare.sh, controls.sh
- FOUND: e256a1a, 43b310c, e6ecdbe
