---
phase: 02-erfassung-aller-dateien
plan: 11
subsystem: ci-push
tags: [push-1, phase-02, ci, discovery-acceptance, ghcr, disc-01, disc-04]
requires: [02-01, 02-02, 02-03, 02-04, 02-05, 02-06, 02-07, 02-08, 02-09, 02-10]
provides:
  - "Branch phase-02 auf origin mit Spitze ad6a32c (43 Commits seit origin/phase-01 82f1655)"
  - "Erster CI-Beleg für PHP (PHPUnit 272 Tests) und Python (606 Tests) von Phase 2"
  - "Lokal, nicht gepusht: fix(02-01) 6e02526 für die ungültige Workflow-Datei discovery-e2e.yml, mit neuem Gate"
affects: [02-12, 02-13, 02-17, 02-22]
tech-stack:
  added: []
  patterns:
    - "Gate: kein Workflow liest den runner-Kontext im env von Workflow oder Job (GitHub verwirft sonst die ganze Datei)"
key-files:
  created: []
  modified:
    - .github/workflows/discovery-e2e.yml
    - backend/tests/test_discovery_workflow.py
    - .planning/phases/02-erfassung-aller-dateien/02-17-PLAN.md
    - .planning/phases/02-erfassung-aller-dateien/02-22-PLAN.md
decisions:
  - "Push 1 nur für ad6a32c (Owner 07.11.: 'Ja, pushen'); die lokale Korrektur 6e02526 braucht eine neue Owner-Freigabe"
  - "ghcr-Abfrage in Plan 17 und 22 mit --paginate und per_page=100"
metrics:
  duration: "ca. 60 min"
  completed: 2026-11-07
---

# Phase 2 Plan 11: Push 1 auf phase-02 Summary

Push 1 von ad6a32c auf phase-02 lief durch das Tor; Python gates und PHP gates sind grün, Discovery acceptance startete nie, weil GitHub die Workflow-Datei ablehnt (runner.temp im Job-env, Zeile 414); die Korrektur liegt lokal als 6e02526 und wartet auf eine neue Owner-Freigabe.

## Freigabe und Tor

- Owner-Freigabe 07.11. (Claude-Code-Terminal, Antwort auf "Darf ich Push 1 von AV Phase 2 ausführen (Plan 02-11, 43 Commits nur auf den Branch phase-02, nicht main)?"): "Ja, pushen". Gilt für genau einen Push.
- Freigabedatei `approvals/push-ad6a32c413d0a6d5890251f7c91c4928cddd9fca` mit Inhalt `push-phase-02 ad6a32c413d0a6d5890251f7c91c4928cddd9fca`; `approvals/` per `.git/info/exclude` (Muster `.planning/phases/02-erfassung-aller-dateien/approvals/`) ausgeschlossen, `git check-ignore` bestätigt.
- Autoren- und Textprüfung über `origin/phase-01..HEAD` (43 Commits, alle Autor und Committer `street1983nk <k.cherif@outlook.de>`, kein Claude-Session, kein closes/fixes/resolves #N): grün.
- Lokale Gates vor dem Push: ruff check, ruff format --check (62 Dateien), pyright latest 0 Fehler, vulture, pytest 606 grün.
- Push 12:38:03Z: `git push origin HEAD:phase-02` -> `* [new branch] HEAD -> phase-02`, genau einmal, kein --force, kein PR.

## CI-Ergebnis für ad6a32c

| Workflow | Lauf | Ergebnis |
|---|---|---|
| Python gates | [42373357005](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42373357005) | success (606 passed, Lint und shellcheck grün) |
| PHP gates | [42373356995](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42373356995) | success (php -l, composer validate/audit, PHPUnit OK 272 Tests, 5203 Assertions); lief direkt per Push, kein workflow_dispatch nötig |
| Deploy through HaRP | [42373357012](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42373357012) | success (10 Jobs: upgrade stable33/34/35 amd64 und stable35 arm64, deploy-harp stable33/34/35 auf amd64 und arm64) |
| Discovery acceptance | [42373356051](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42373356051) | failure ohne Jobs: "Invalid workflow file" |

Befund Discovery acceptance (Seite des Laufs, `gh run view` meldet "This run likely failed because of a workflow file issue"):

```
Invalid workflow file
(Line: 414, Col: 18): Unrecognized named-value: 'runner'. Located at position 1 within expression: runner.temp
```

Zeile 414 ist `LEAK_ROOT: ${{ runner.temp }}/leak-backend` im `env` des Jobs `leak-control`. Der runner-Kontext ist im env von Workflow und Job nicht erlaubt, nur in Schritten. Folge: kein Job lief, auch das Bein `discovery` nicht; es gibt keine PASS/FAIL-Zeilen, keine Samba-, Selbsttest- oder access-log-Kontrolle. Der Lauf trägt als workflowName den Dateipfad `.github/workflows/discovery-e2e.yml` statt "Discovery acceptance".

Das Workflow-Gate aus 02-01 (`leak_findings`) verlangte genau diesen Text (`"LEAK_ROOT: ${{ runner.temp }}/" in leak`) und konnte den Fehler darum nicht finden.

### Zuordnung der Discovery-Prüfungen

| Prüfung | Ergebnis | Zuordnung |
|---|---|---|
| Samba-Kontrolle | nicht gelaufen | Fehler 02-01 (Workflow-Datei), Korrektur 6e02526 lokal |
| Selbsttest des Vergleichs | nicht gelaufen | dito |
| access-log-Kontrolle | nicht gelaufen | dito |
| initial (Homes, Gruppenordner), upload, overwrite, copy, rename, tag | nicht gelaufen | dito |
| übrige Phasen | nicht gelaufen | dito (erwartet rot bis Plan 12 bis 20) |
| leak-control | nicht gelaufen | dito; Patch fehlt ohnehin bis Plan 13 |

## main und ghcr

- main vorher (`approvals/main-before-<sha>`): `f908a858402c4cae5a16c3cd3fe9b116f9ea0350 refs/heads/main`; nachher per `git ls-remote origin refs/heads/main | cmp -` identisch.
- ghcr `audio_video_search_backend` vorher: Exit 1, `{"message":"Package not found.", ... "status":"404"}` / `gh: Package not found. (HTTP 404)` -> Datei `STATE 404 Package not found`; nachher dieselbe Antwort (Exit 1, gleicher 404-Körper, Fehlerausgabe `gh: Package not found. (HTTP 404)`) -> `approvals/ghcr-after-<sha>` `STATE 404 Package not found`; `cmp` vorher/nachher gleich, kein `leak-control`. Hinweis: gh schreibt den 404-JSON-Körper auf stdout, die Meldung `HTTP 404` auf stderr.
- Scope: Token mit `read:packages` (gh auth status).
- Positivkontrolle: `gh api "users/street1983nk/packages?package_type=container"` nennt findling_backend, mcp_connector, gameworld, pdf_accessibility, audio_video_search, pii_redaction. `gh api --paginate "users/street1983nk/packages/container/findling_backend/versions?per_page=100" --jq '.[].metadata.container.tags[]'` Exit 0, 352 Tags, enthält `1.6.2`. Die Positivkontrolle setzt voraus, dass `findling_backend:1.6.2` existiert; fehlt es, nennt der Owner einen anderen bekannten Tag, und der Plan wird mit diesem Tag wiederholt.
- Zusatzbeleg: Es gibt ein öffentliches Paket `audio_video_search` (nicht `_backend`, angelegt 05.11. aus main-Läufen des Gerüsts, Tags `dev`, Commit-SHAs, `buildcache-*`). Vorher-Stand in `approvals/ghcr-extra-before-<sha>`; nachher `approvals/ghcr-extra-after-<sha>` identisch, kein `leak-control`.

## Deviations from Plan

**1. [Koordinator-Befund] ghcr-Abfrage mit per_page=100**
- Der Koordinator meldete, dass die erste Seite der findling_backend-Versionen `1.6.2` nicht enthält. Gemessen: ohne `--paginate` fehlt 1.6.2; die Plan-Abfrage mit `--paginate` (ohne per_page) fand 1.6.2 ebenfalls (352 Zeilen). Ausgeführt wurde die Form `gh api --paginate "...versions?per_page=100"`; Plan 17 und 22 auf diese Form umgestellt.
- Commit: a412bb6 (lokal)

**2. [Rule 1 - Bug] Workflow-Datei discovery-e2e.yml ungültig (Task 3, nur lokal)**
- Gefunden: Push 1, Lauf 42373356051.
- Fix: LEAK_ROOT aus dem env des Jobs in das env des Schritts "Build the control image out of a patched copy"; neues Gate `runner_env_findings` über alle Workflows mit Selbsttest. Positivkontrolle: am gepushten Stand meldet die Regel genau `old:414 reads the runner context in a job env`, also dieselbe Zeile wie GitHub.
- Gates lokal: ruff, format, pyright 0, vulture, pytest 608 grün.
- Commit: 6e02526 (lokal, NICHT gepusht; Push nur nach neuer Owner-Freigabe).

## Offen für den Owner

- Freigabe für Push 2 (Korrektur): neuer SHA ist HEAD nach dem docs-Commit dieses SUMMARY; Inhalt seit ad6a32c: a412bb6 (docs Plan 17/22), 6e02526 (fix 02-01), docs(02-11).
</content>

## Prüfung aus verify (mit festem SHA ad6a32c, weil HEAD lokal weitergewandert ist)

- Pflicht-Workflows success: 3 von 3 (Python gates, PHP gates, Deploy through HaRP).
- main unverändert (`cmp` grün), phase-02 = ad6a32c.
- ghcr-before und ghcr-after vorhanden, gleich, kein leak-control; Positivkontrolle findling_backend 1.6.2 grün.
- Discovery acceptance: rot wegen ungültiger Workflow-Datei, die Muss-Wahrheit "läuft auf einem Bein, Kontrollen grün" ist damit NICHT erfüllt. Plan 11 bleibt offen bis Push 2 (neue Owner-Freigabe) und ein Lauf mit Jobs.

## Self-Check: PASSED

- Commits a412bb6, 6e02526 vorhanden; Freigabe-, main- und ghcr-Dateien unter approvals/ vorhanden (nicht committet).

## Push 2 (Korrektur), 434a350

- Owner-Freigabe 07.11. (Claude-Code-Terminal, Antwort auf "Darf ich einen Korrektur-Push auf phase-02 machen (3 Commits)?"): "Ja, Korrektur pushen". Genau ein Push von 434a350.
- HEAD vor dem Push = 434a3509e7c22f8846ceae82ae5cab7875ccf808; Autoren-, Committer- und Textprüfung über origin/phase-01..HEAD (46 Commits) grün; lokale Gates grün (pytest 608); Freigabedatei `approvals/push-434a350…`; Fast-Forward ad6a32c..434a350 um 13:01:12Z.
- PHP gates startete per Push nicht (keine Änderung unter php/); nach fünf Minuten wie im Plan `gh workflow run php.yml --ref phase-02`.

| Workflow | Lauf | Ergebnis |
|---|---|---|
| Python gates | 42375022210 | success |
| PHP gates (workflow_dispatch) | 42375439100 | success |
| Deploy through HaRP | 42375022170 | **failure**: deploy-harp stable34 arm64 und stable35 arm64 im Schritt "The OCS search honours read access"; die übrigen 8 Jobs success |
| Discovery acceptance | 42375022218 | failure: discovery stable33 amd64 cancelled (Job-Zeitgrenze 120 min), leak-control failure |

Der Produktcode ist zwischen ad6a32c (Push 1, Deploy 10/10 grün) und 434a350 gleich (Diff außerhalb .planning nur discovery-e2e.yml und test_discovery_workflow.py).

### Befund 1: Deploy arm64, Probe gegen Erfassung (zeitabhängig)

- stable35 arm64: `intake written new 4` um 13:03:30 VOR den Proben; danach `sample answered file_id 52 published`, aber search-alice.json enthält nur 51, nicht 52 -> `jq` false.
- stable34 arm64: Proben zuerst (51, 52, 54 published; 53 und 55 `stale_rejected` auf media 1), danach `intake written ... changed 4, orphaned 2` um 13:03:31; search-carol.json `entries: []` (Gruppenordner-Datei 53 fehlt), danach bob false.
- Deutung: Erst-Crawl/Intake (02-03 bis 02-06) und der Probe-Weg aus Phase 1 laufen auf denselben file_ids; je nach Reihenfolge überschreibt das Intake die Probe-Verweise (und verwaist media) oder die Probe greift nicht, weil schon ein echter Verweis da ist (02-02: Probe lässt echte Verweise unberührt). Auf amd64 und in Push 1 kam das Intake offenbar erst nach der Suche. Kein Fix in diesem Plan; Owner-Entscheid.

### Befund 2: Discovery, S3-Server kollidiert mit Nextcloud auf Port 8080

```
Start Seaweed volume server 30GB 4.52 984eac6a7 at 10.1.0.134:8080
F1107 13:02:38.726514 volume.go:705 Volume server listener error:listen tcp 10.1.0.134:8080: bind: address already in use
```

`weed server` mit `--net host` startet den Volume-Server auf seinem Standardport 8080, auf dem schon `php -S` von Nextcloud läuft (02-01). Dadurch übersprungen: Testmedien, Samba, Samba-Kontrolle, Topologie, Registry, HaRP, ExApp, Selbsttests, Warten, access-log-Kontrolle.

### Befund 3: "Run the phases" läuft nach gescheitertem Aufbau zwei Stunden

`if: ${{ !cancelled() }}` startet die Phasen auch ohne Aufbau; jede Phase wartet 15 min (`compare.sh wait`), nach 7 Phasen und dem Anfang von rename bricht die Job-Grenze 120 min ab. Zeilen (results.txt):

```
FAIL initial:wait / FAIL initial:truth / PHASE FAIL initial
FAIL read-proof:wait / FAIL read-proof:truth / PHASE FAIL read-proof
FAIL shares:wait / FAIL shares:truth / PHASE FAIL shares
FAIL access-control:operation / :wait / :truth / PHASE FAIL access-control
FAIL upload:operation / :wait / :truth / PHASE FAIL upload
FAIL overwrite:operation / :wait / :truth / PHASE FAIL overwrite
FAIL copy:operation / :wait / :truth / PHASE FAIL copy
FAIL rename:operation (danach Abbruch)
```

Alle Zeilen sind Folge von Befund 2 (`truth.sh <phase> has not run`, `ledger sample takes a numeric file id`, `occ audio_video_search:files failed`), keine ist einem späteren Plan zuzuordnen. Samba-, Selbsttest- und access-log-Kontrolle liefen nicht.

### Befund 4: leak-control

```
error: can't open patch '.../app-src/ci/leak-control/read-proof-off.patch': No such file or directory
```

Erwartet: der Patch kommt mit Plan 13.

### Befund 5: Name des Discovery-Laufs in gh run list

Auch der gültige Lauf trägt in `gh run list` den workflowName `.github/workflows/discovery-e2e.yml` (`gh run view` nennt "Discovery acceptance"). Die verify-Zeile von Plan 22 (`unique|length == 4` und `select(.workflowName=="Discovery acceptance" ...)`) würde daran scheitern; offen für den Owner.

### main und ghcr nach Push 2

main unverändert (`cmp` grün); audio_video_search_backend vorher und nachher `STATE 404 Package not found`, gleich, kein leak-control; Positivkontrolle findling_backend 1.6.2 grün; Paket audio_video_search unverändert.

## Stand

Plan 11 bleibt offen: Deploy through HaRP rot (Befund 1), Discovery ohne Kontrollen (Befund 2, 3). Jeder weitere Push braucht eine neue Owner-Freigabe.

## 02-11a: D-02-15 und Workflow-Korrekturen (Owner 07.11.)

Owner-Entscheide 07.11.: Befund 1 "Getrennte Schichten (Empfohlen)", Workflow-Korrekturen, Push 3 "Ja, nach den Fixes pushen".

| Commit | Inhalt |
|---|---|
| 654bb86 | docs: STATE completed_plans zurück auf 23 |
| 40fff64 | test (RED): beide Reihenfolgen Intake/Probe aus Push 2, 7 von 8 rot (`assert [] == [52]`, `assert [] == [51, 53]`, ...) |
| d86cb22 | docs: D-02-15 in 02-CONTEXT.md |
| ffd38e1 | fix (GREEN): Tabelle `sample_ref`, Probe schreibt nie `file_ref`, `file_ref` ohne Zustand sample (Python STATES und PHP WORK_STATES), Suche = aktive Verweise plus Proben (Probe nur ohne Verweis, der keine Treffer gibt), Intake und Verwaist-Regel lassen sample_ref unberührt, remove_sample schreibt nie file_ref, Migration v1 nach v2 legt Proben in sample_ref |
| 73d4d73 | fix(02-01): `-volume.port` 8380 für weed server; Run the phases nur nach `steps.setup.outcome == 'success'`, WAIT_LIMIT 300 s, Schritt 90 min; Gates mit Selbsttest (Positivkontrolle: am alten Stand melden beide Regeln die Lücke) |
| f8b28a5 | docs: Plan 22 erkennt den Discovery-Lauf auch am Dateipfad (GitHub nimmt den Namen vom Standardzweig) |

Entscheid innerhalb D-02-15: Die Verwaist-Marke richtet sich nur nach echten Verweisen; eine Probe schützt eine media nicht vor der Marke (sonst wären die Prüfungen old_media_orphaned, x_forgotten der Abnahme nicht mehr erreichbar, weil das Ledger dort Proben setzt). Die Marke versteckt keinen Probetreffer. Offen für Plan 16 und Phase 8: Ausschluss und Vergessen müssen die Probe der Datei mit entfernen.

Gates lokal: ruff, format, pyright 0, vulture, pytest 620 grün. PHP lokal nicht prüfbar, in CI grün.

## Push 3, f8b28a5

- Autoren-, Committer- und Textprüfung grün, Freigabedatei `approvals/push-f8b28a5…`, Fast-Forward 434a350..f8b28a5 um 15:20:12Z.

| Workflow | Lauf | Ergebnis |
|---|---|---|
| Python gates | 42385881719 | success |
| PHP gates (Push, php/ geändert) | 42385881816 | success, OK (272 Tests, 5203 Assertions) |
| Deploy through HaRP | 42385881969 | success, 10 von 10 Jobs (auch beide arm64-Beine, Befund 1 behoben) |
| Discovery acceptance | 42385881743 | failure |

Discovery: S3-Server, Testmedien, Samba und Samba-Kontrolle grün (`samba positive control: ana reads gesperrt.webm, ben gets NT_STATUS_ACCESS_DENIED`). Danach rot in "Topology part A":

```
first login of cem: HTTP 207
Error: in prepare, no such table: oc_credentials
```

Die Tabelle heißt `oc_storages_credentials` (CredentialsManager::DB_TABLE, stable33); das Topologie-Gate aus 02-01 verlangte den falschen Namen. Durch den neuen Schutz liefen die Phasen nicht (skipped statt zwei Stunden Warten), das Urteil ist rot. Es gibt darum noch keine PASS/FAIL-Zeilen der Phasen, keinen Selbsttest und keine access-log-Kontrolle. leak-control: `can't open patch .../read-proof-off.patch` (erwartet bis Plan 13).

Korrektur lokal, nicht gepusht: e05dbf9 fix(02-01) `oc_storages_credentials` in topology.sh und im Gate. Push 4 braucht eine neue Owner-Freigabe.

main unverändert (`cmp` grün), audio_video_search_backend vorher und nachher `STATE 404 Package not found`, kein leak-control, Positivkontrolle findling_backend 1.6.2 grün, Paket audio_video_search unverändert.

## Push 4, 80ce5c9

- Owner-Freigabe 07.11. ("Ja, Push 4"); genau e05dbf9 und 80ce5c9 vor origin/phase-02 geprüft; Autoren-, Committer- und Textprüfung grün; Gates lokal grün (pytest 620); Fast-Forward f8b28a5..80ce5c9 um 15:42:59Z.
- D-02-15a (Owner "Ja, so lassen") danach lokal: bc9a1b0 (02-CONTEXT.md, deferred-items.md für Plan 16 und Phase 8).

| Workflow | Lauf | Ergebnis |
|---|---|---|
| Python gates | 42387720591 | success |
| PHP gates (workflow_dispatch, Pfadfilter ohne php/) | 42388136823 | success |
| Deploy through HaRP | 42387720598 | success, 10 von 10 |
| Discovery acceptance | 42387720556 | discovery: Aufbau komplett grün, Urteil rot; leak-control rot (Patch fehlt, Plan 13) |

Kontrollen alle grün: Samba (`ana reads gesperrt.webm, ben gets NT_STATUS_ACCESS_DENIED`), Selbsttest (jede verschobene Erwartung schlägt an: files_count, contents, transcribed, never_in_log), Warten auf den Arbeitsvorrat (30 s), access-log (`1 gateway line(s) for file 74`). Run the phases lief in 60 min durch (alle 20 Phasen).

### Erster Schnitt (Homes und Gruppenordner): Vorgangsprüfungen grün

- initial: shared_once_ben, shared_once_cem, shared_once_dan, transcribed, unmapped PASS
- upload: upload_within_300s, upload_active PASS
- overwrite: overwrite_active, overwrite_new_media, overwrite_downloaded, old_media_orphaned PASS (bestätigt D-02-15a)
- copy: copy_active, copy_same_media, copy_at_most_one_download PASS
- rename: rename_same_file_id, rename_same_media, rename_no_gateway_line PASS
- tag: tag_same_media, tag_no_gateway_line PASS

### FAIL-Zeilen und Zuordnung (results.txt, je Phase gleiche Muster)

| FAIL | Ursache | Plan |
|---|---|---|
| active_set / files_count / contents in allen Phasen (fehlt 41, 44, 55, 63, 66, 72, 73, 105 bis 137: SMB-, S3- und lokale externe Speicher) | externe Speicher noch ohne Crawl | 12 |
| unreadable_set / unreadable_count (fehlt 52 = BEN SMB gesperrt, später 66) | SMB-Rechteleck, Lesebeweis | 12, 13 |
| initial:skipped_session_mount, local_captured, s3_captured | Klassifikation externer Speicher | 12 |
| transcribed in read-proof bis foreign-change zu klein | Proben des Ledgers liegen auf SMB-Dateien ohne aktiven Verweis | 12 (Folge) |
| zuviel / never_in_stock / never_in_log 83, 91, 95 (ANA privat P, EVA, FRITZ) | Ausschlüsse fehlen (`occ audio_video_search:exclude is missing`), ausgeschlossene Dateien wurden geladen | 16 |
| never_in_log zusätzlich 41, 44, 107, 113, 114 | Gateway-Zeilen der Ledger-Proben (occ :sample) auf SMB-Dateien, die noch nicht im Vorrat sind | 12 (Folge) |
| shares:eva_finds_nothing, exclude-user-after:ben_finds_nothing | keine Treffer für Ausgeschlossene | 16, 18 |
| exclude-user-after:ana_storage_refs_stay, exclude-storage-after:files_fewer, exclude-after:z_kept, z_correction_kept | rückwirkender Ausschluss | 15, 18 |
| trash:trashed_not_active (75 bleibt active), restore | Papierkorb-Kinds | 15, 18 |
| delete-user:dan_ref_gone, dan_media_orphaned, transcribed_minus_one | Löschen eines Nutzers | 15 |
| reprove:cem_finds_before, operation, reprove_unreadable | erneuter Lesebeweis auf SMB | 13, 20 |
| vanish:cem_refs_vanished, transcribed_minus_one | Sweep verschwundener Speicher | 20 (12) |
| reattach:transcribed_plus_one | Wiederanhängen, SMB | 13, 15 |
| foreign-change:operation, foreign_new_hash | Fremdänderung auf externem Speicher, Rescan | 12, 14 |
| :wait ab move-cross (WAIT_LIMIT 300 s) | Arbeitsvorrat wird nicht fertig, solange externe Vorgänge fehlen | 12, 14, 15 |
| **access-control:reason_77, sperre_reason (erwartet access_control, gefunden not_found), in allen Folgephasen** | **echter Befund in 02-10**: nach dem Tag der files_accesscontrol-Regel antwortet das Gateway 404, nicht 403 access_control (`[404]: GET /ocs/v2.php/apps/audio_video_search/files/77?userId=ana`, vorher 200). Die Annahme "files_accesscontrol wirft ForbiddenException bei fopen" stimmt auf stable33 nicht; der Knoten wird offenbar schon beim Auflösen verweigert. Folge: falscher Grund und Wiederholung nach 60 s statt 300 s; kein Treffer-Leck. | Owner-Entscheid (02-10 korrigieren oder in Plan 13/16 einplanen) |

main unverändert (`cmp` grün), audio_video_search_backend vorher und nachher `STATE 404 Package not found`, kein leak-control, Positivkontrolle findling_backend 1.6.2 grün, Paket audio_video_search unverändert.

Stand: Pflicht-Workflows grün, Kontrollen grün, Vorgangsprüfungen des ersten Schnitts grün; alle übrigen FAIL-Zeilen einem späteren Plan zugeordnet, eine (reason_77) als echter Befund. Plan 11 kann nach Owner-Entscheid zu reason_77 abgeschlossen werden. Jeder weitere Push braucht eine neue Freigabe.
