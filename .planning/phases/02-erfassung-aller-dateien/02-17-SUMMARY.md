---
phase: 02-erfassung-aller-dateien
plan: 17
subsystem: ci-abnahme
tags: [disc-02, disc-03, disc-05, d-02-10, d-02-01a, push, discovery-acceptance, leak-control]
requires: [02-12, 02-13, 02-14, 02-15, 02-15b, 02-15c, 02-16, 02-16b]
provides:
  - "Push 6: c1b6375 auf origin/phase-02, PHP gates, Python gates und Deploy through HaRP grün"
  - "Erster CI-Beleg der PHP-Seite von 02-13 bis 02-16b: PHPUnit 569 Tests, 7416 Assertions, php -l 59 Dateien"
  - "Befund und lokale Korrektur für das Kontrollbein leak-control und für compare.sh wait (ungepusht)"
affects: [02-18, 02-19, 02-20, 02-22]
tech-stack:
  added: []
  patterns:
    - "Sauberkeitsprüfung des Checkouts in CI nur über backend/, weil die PHP-App vor dem Bau herausbewegt wird"
    - "Die Abnahme wartet auf den ersten geplanten Crawl, bevor sie einen Arbeitsvorrat als fertig wertet"
key-files:
  created: []
  modified:
    - .github/workflows/discovery-e2e.yml
    - ci/discovery/compare.sh
    - ci/discovery/truth.sh
    - ci/discovery/common.sh
    - ci/discovery/README.md
    - backend/tests/test_discovery_workflow.py
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
decisions:
  - "02-17: Owner-Entscheid 13.11.2026 push-phase-02 ('Go', über die Hauptsitzung übermittelt) für genau einen Push von c1b6375 auf phase-02"
  - "02-17: Zweiter Checkpoint offen: die Korrektur 11db11a liegt lokal, Push nur nach neuer Owner-Wahl (push-fix, stop)"
  - "02-17: compare.sh wait gilt erst mit mindestens einem Erst-Crawl (fertig oder offen) als fertig; die Erwartungen der Phasen sind unverändert"
metrics:
  duration: "ca. 25 min"
  completed: 2026-11-13
---

# Phase 2 Plan 17: Zweiter Zwischen-Push nach Welle 7 Summary

Push 6 (c1b6375 auf phase-02) ist durch das Tor gegangen: die drei Pflicht-Workflows sind grün und die PHP-Seite von 02-13 bis 02-16b ist zum ersten Mal in CI belegt; Discovery acceptance ist rot, weil das Kontrollbein an einer Sauberkeitsprüfung über den ganzen Checkout scheitert und die Abnahme vier Phasen vor dem ersten Crawl beurteilt. Beide Ursachen sind lokal korrigiert und nicht gepusht. Der Plan ist damit NICHT erfüllt, der zweite Checkpoint wartet auf den Owner.

## Freigabe und Tor

- Owner-Entscheid 13.11.2026: `push-phase-02`, wörtlich "Go" auf die Frage der Hauptsitzung, ob der Zwischen-Push von 02-17 freigegeben wird; über die Hauptsitzung übermittelt. Gilt für genau einen Push.
- HEAD vor dem Push: c1b6375e6269755d8f37f6da5a9f7733c604476c, Arbeitsbaum sauber, origin/phase-02 (fa3af22) ist Vorfahr von HEAD, 39 Commits, kein Merge-Commit.
- origin/main liegt 2 Commits vor dem lokalen main (ea97b58, 88f4f08). Das berührt diesen Push nicht: Ziel ist nur phase-02, kein Merge, kein Rebase, kein force.
- Freigabedatei `approvals/push-c1b6375…` mit Inhalt `push-phase-02 c1b6375…`; `approvals/` steht in `.git/info/exclude` (`git check-ignore` bestätigt).
- Push: `git push origin HEAD:phase-02`, Fast-Forward fa3af22..c1b6375 um 03:33:13Z. Genau ein Push.

## Prüfungen vor dem Push

| Prüfung | Ergebnis |
|---|---|
| Autor und Committer über origin/phase-02..HEAD | 39 von 39 `street1983nk <k.cherif@outlook.de>` |
| Commit-Texte (Claude-Session, Co-Authored-By, Schließwort mit Issue-Nummer) | 0 Treffer |
| Dateinamen aller Commits im Bereich (.env, *.key, *.pem, *.crt, *.p12, id_rsa, certificates, secret, token, credential, approvals/) | 0 Treffer, 58 Dateien |
| Hinzugefügte Zeilen aller Commits (private Schlüssel, Zertifikate, GitHub-, AWS-, Slack-, JWT-, Hugging-Face-Token) | 0 Treffer |
| Zuweisungen mit password, secret, token, api key | 2 Zeilen, beide gelesen: ein Parametername `token: str` in einem Test, eine Anmeldeart `password::logincredentials` in einem Test; keine Werte |
| Trigger store-submit.yml | nur workflow_dispatch |
| Trigger release.yml, docker.yml | nur Tags `v*`, bei docker.yml zusätzlich main, Zeitplan, Dispatch; phase-02 löst beide nicht aus |
| Workflows auf phase-02 | Python gates, PHP gates (Pfadfilter php/**, erfüllt), Deploy through HaRP, Discovery acceptance; alle mit `contents: read`, ohne Registry-Anmeldung |
| Image des Kontrollbeins | `localhost:5000/audio_video_search_backend:leak-control`, gebaut aus einer Kopie unter RUNNER_TEMP, nur in die Registry des Runners geschoben, kein docker save, kein Artefakt mit Image |
| Lokale Gates auf c1b6375 | ruff check und format (71 Dateien), pyright 0 Fehler, vulture Exit 0, pytest 937 grün |

Zum bekannten Punkt aus deferred-items.md (`ci/discovery/topology.sh`, Ersatzweg schreibt `excluded_storages`, der Schlüssel heißt `excluded_mounts`): am Skript bestätigt (Zeile 205 gegen `ExclusionService::LIST_MOUNTS`). Der Ersatzweg läuft nur, wenn `occ list audio_video_search` den Befehl `audio_video_search:exclude` nicht nennt; der Befehl ist in `php/appinfo/info.xml` eingetragen. Im Lauf belegt: die Zeile "is missing" kommt 0-mal vor, die Ausgaben sind die des Befehls ("Added to the excluded users.", "Added to the excluded external storages (mount ids)."). Der falsche Schlüssel ist in diesem Lauf nicht geschrieben worden.

## Läufe für c1b6375

| Workflow | Lauf | Ergebnis |
|---|---|---|
| Python gates | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43359738037 | success |
| PHP gates | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43359737942 | success: php -l 59 Dateien, PHPUnit 11.5.57 "OK (569 tests, 7416 assertions)", composer validate und audit |
| Deploy through HaRP | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43359737811 | success, 10 von 10 (sechs Beine deploy-harp, vier upgrade) |
| Discovery acceptance | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43359737879 | failure: discovery 2 von 20 Phasen, leak-control rot im Bau |

Alle vier Läufe kamen per push, keiner wurde abgebrochen, neu gestartet oder per Dispatch ausgelöst. Pflicht-Workflows mit success: 3 von 3.

main: `git ls-remote origin refs/heads/main` vorher und nachher ea97b58, `cmp` grün. ghcr: `audio_video_search_backend` vorher und nachher `STATE 404 Package not found`; Paket `audio_video_search` vorher und nachher identisch (39 Zeilen), kein Tag leak-control. Positivkontrolle: `findling_backend` steht in der Paketliste des Owners und trägt den Tag `1.6.2`, vor und nach den Läufen Exit 0. Die ghcr-Positivkontrolle setzt voraus, dass `findling_backend:1.6.2` existiert; fehlt es, nennt der Owner einen anderen bekannten Tag, und der Plan wird mit diesem Tag wiederholt.

## Discovery acceptance im Einzelnen

Kontrollen im Bein discovery (stable33, ubuntu-24.04), alle grün: Samba ("ana reads gesperrt.webm, ben gets NT_STATUS_ACCESS_DENIED"), Selbsttest (jede verschobene Erwartung schlägt an: files_count, contents, transcribed, never_in_log), access-log ("1 gateway line(s) for file 74"). Der Aufbau lief durch, alle 20 Phasen liefen, das Urteil ist rot.

### Vom Plan verlangt, nicht erreicht

| Verlangt | Ergebnis | Ursache |
|---|---|---|
| PHASE PASS initial | FAIL | Befund 2 |
| PHASE PASS read-proof | FAIL | Befund 2 |
| PHASE PASS shares | FAIL | Befund 2 |
| PHASE PASS access-control | FAIL | Befund 2 |
| leak-control success mit "LEAK CONTROL SHOWED THE LEAK" | failure, Zeile fehlt | Befund 1 |

In den vier Phasen scheitern nur die Mengenprüfungen (active_set, unreadable_set, files_count, unreadable_count, contents, transcribed, dazu initial:local_captured und s3_captured). Die benannten Prüfungen dieser Phasen sind grün: initial skipped_session_mount, shared_once_ben, shared_once_cem, shared_once_dan, never_in_stock, never_in_log; read-proof ana_finds_her_copy, ben_finds_no_denied_copy; shares ben_finds_share, cem_finds_reshare, dan_finds_smb_share, eva_finds_nothing; access-control reason_77, sperre_reason (Fix aus 02-13 bestätigt, vorher not_found).

### Befund 1: leak-control scheitert vor dem Bau

Schritt "Build the control image out of a patched copy" endet nach unter einer Sekunde ohne Ausgabe mit Exit 1. Ursache: `git -C app-src diff --quiet` prüft den ganzen Checkout, der Schritt davor bewegt aber `app-src/php` nach `apps/audio_video_search`. Lokal nachgestellt in einem frischen Klon von c1b6375: `git apply --check` und `git apply` des Patches auf die Kopie Exit 0, `git diff --quiet` Exit 1 mit 77 als gelöscht gemeldeten Dateien, `git diff --quiet -- backend/` Exit 0. In Push 5 fiel dieselbe Stelle nicht auf, weil der Patch noch fehlte und der Schritt eine Zeile früher endete. Folge: das Kontrollbein hat das Leck weder gezeigt noch widerlegt; ein Image wurde nicht gebaut.

### Befund 2: die Abnahme beurteilt vier Phasen vor dem ersten Crawl

"work stock complete after 31 s" bei `crawl {finished 0, open 0}` und 12 Dateien (nur die über Ereignisse eingereihten). Der SchedulerJob läuft im 300-s-Takt; aus den Zeiten geschlossen fiel sein erster Lauf vor die Registrierung des Backends (PHP-App aktiv 03:34:12, Backend registriert 03:35:53). `compare.sh wait` verlangt nur `crawl.open == 0` und wertet "noch gar kein Crawl" als fertig. Status je Phase: initial bis tag `crawl finished 0`, ab move-cross (03:39:25) `finished 14` und 52 Dateien. Sobald der Vorrat steht, stimmen alle Mengen mit der Wahrheit überein: PHASE PASS move-cross und PHASE PASS trash, mit Datei 52 (ben, SMB, verweigert) als unreadable. Dieselbe Lage bestand in Push 4 und 5 (dort "externe Speicher noch ohne Crawl, Plan 12" zugeordnet); mit Plan 12 ist sie nicht verschwunden.

### Befund 3: neverFetched der Wahrheit schwankt (Abnahme, kein Zugriff auf Ausgeschlossenes)

In upload, copy, tag, restore, exclude-user-after, exclude-storage-after und reattach meldet die Abnahme never_in_log bzw. never_in_stock für 41, 44, 105 bis 108, 110 bis 114. Das sind die Dateien von ana auf der SMB-Freigabe (STORAGE_SMB_ANA 4). `truth.sh` nimmt alle IDs unter `/ana/files/SMB-Sitzung/` (M2, Sitzungs-Anmeldung) in neverFetched auf; M2 und M1 (Anmeldedaten in der Datenbank) zeigen auf denselben Speicher und damit dieselben IDs (`ID_ANA_SMB_SITZUNG_GEMEINSAM_G1_WEBM` = `ID_ANA_SMB_GEMEINSAM_G1_WEBM` = 107). neverFetched hat 3 Einträge in 13 Phasen und 14 in den sieben genannten, je nachdem, ob M2 gerade in oc_mounts steht; dieselben IDs stehen in initial unter "erwartet active". Belege aus php-server.log: jeder Abruf dieser IDs lief als `userId=ana`; für die vor dem ersten Durchlauf ausgeschlossenen IDs 83, 91, 95 (ana privat, eva, fritz) gibt es 0 Gateway-Zeilen, und sie stehen in keiner Phase im Vorrat (in Push 4 und 5 waren sie geladen worden). Ich werte das als Fehler der Erwartung, nicht als Leck; die Einordnung gehört dem Owner. Nicht geändert, steht in deferred-items.md.

### Übrige FAIL-Zeilen und Zuordnung

| FAIL | Ursache | Plan |
|---|---|---|
| upload, overwrite, copy, rename, tag: active_set, unreadable_set, files_count, unreadable_count, contents, transcribed | Befund 2 (Vorrat ohne Crawl) | Fehler der Abnahme, lokal korrigiert |
| restore:restore_no_download (erwartet 0, gefunden 1) | Papierkorb, erlaubter Folgefehler laut Plan | 18 |
| exclude-user-after: active_set, unreadable_set (zuviel 52), files_count, ben_storage_refs 10 | rückwirkender Ausschluss eines Nutzers; ben_finds_nothing ist grün | 18 |
| exclude-storage-after: active_set, m3_refs 4, files_fewer | rückwirkender Ausschluss eines Speichers | 18 |
| exclude-after: active_set, contents, transcribed, x_forgotten 3 | rückwirkender Ausschluss eines Ordners, Vergessen | 18 |
| reprove:operation | `occ audio_video_search:reconcile --reprove` gibt es noch nicht | 20 |
| reprove:reprove_unreadable, cem_finds_no_revoked_copy (erwartet false, gefunden true) | nach dem Samba-Entzug fehlt der erneute Lesebeweis; wie in Push 5 | 20 (13 führt aus) |
| vanish: cem_refs_vanished, transcribed_minus_one, Mengen | Sweep verschwundener Speicher | 19, 20 |
| delete-user: dan_ref_gone, dan_media_orphaned, transcribed_minus_one, Mengen | gelöschter Nutzer, Abgleich | 19, 20 |
| reattach:transcribed_plus_one, Mengen | Folge von vanish | 19, 20 |
| foreign-change: Mengen | Folge der Phasen davor, erlaubter Folgefehler laut Plan | 20 |
| never_in_stock, never_in_log in sieben Phasen | Befund 3 | Fehler der Erwartung, lokal korrigiert (Nachtrag unten) |

Gegen Push 5 grün geworden: never_in_stock und never_in_log für 83, 91, 95 in allen Phasen (Ausschlüsse vor dem ersten Durchlauf, Plan 16), shares:eva_finds_nothing, exclude-user-after:ben_finds_nothing und ana_storage_refs_stay, access-control:reason_77 und sperre_reason, restore:wait, move-cross und trash als ganze Phasen.

Hinweis zu reprove:cem_finds_no_revoked_copy: cem findet die Kopie nach dem Entzug auf dem SMB-Server weiter, bis Plan 20 den erneuten Lesebeweis plant. Das ist der Stand vor Plan 20 und nicht veröffentlicht, aber es ist ein Treffer nach entzogenem Recht im Hauptlauf; der Plan ordnet "übrige FAIL-Zeilen" 18 bis 20 zu, die Wertung liegt beim Owner.

## Lokale Korrektur (ungepusht)

| Commit | Inhalt |
|---|---|
| 1862b53 test(02-01) | Gate: leak-control braucht `git diff --quiet -- backend/` nach dem Patch und vor dem Bau; die Prüfung über den ganzen Checkout ist ein Befund; zwei Fälle, die die Regel einzeln auslösen. RED: 9 Fälle rot |
| 00928f7 fix(02-01) | discovery-e2e.yml, Job leak-control: `git -C app-src diff --quiet -- backend/` wie im Bein discovery. Nachgestellt: Exit 0 bei herausbewegter PHP-App, Exit 1 bei Patch auf dem Checkout |
| 9b59082 test(02-04) | Gate: `compare.sh wait` verlangt mindestens einen Erst-Crawl; ein Fall, der die Regel auslöst. RED: 6 Fälle rot |
| 11db11a fix(02-04) | compare.sh `cmd_wait`: zusätzlich `(.crawl.finished + .crawl.open) > 0`. Gegen die Statusdateien des Laufs geprüft: initial und tag nicht fertig, move-cross und foreign-change fertig |

Gates auf 11db11a: ruff check und format grün, pyright 0 Fehler, vulture Exit 0, pytest 940 grün; `bash -n ci/discovery/compare.sh` grün. Kein Test wurde aufgeweicht: beide Regeln sind strenger als vorher, keine Erwartung einer Phase ist geändert.

Lokal nicht belegbar: ob initial, read-proof, shares und access-control mit dem Warten grün werden und ob das Kontrollbein das Leck zeigt. Dafür spricht, dass move-cross und trash mit vollem Vorrat grün sind; das Kontrollbein ist nach dem Bau noch nie gelaufen. Der erste Warteschritt hat 900 s Grenze, der Takt des SchedulerJob ist 300 s; die Phasen haben je 300 s und laufen erst danach. Der Lauf wird etwa fünf Minuten länger.

## Nachtrag: Befund 3 geklärt und lokal korrigiert (Zwischenauftrag der Hauptsitzung, 13.11.2026)

Nur lokal, kein Push, kein Dispatch. Der zweite Checkpoint bleibt offen.

### Beleg aus dem Artefakt des Laufs 43359737879

| Frage | Beleg |
|---|---|
| Gleicher Speicher, gleiche IDs | Der Vorrat führt auf `storageId` 4 (STORAGE_SMB_ANA) genau 11 Dateien: 41, 44, 105, 106, 107, 108, 110, 111, 112, 113, 114. Die IDs, die `truth.sh` unter `/ana/files/SMB-Sitzung/` (M2) findet, sind genau diese 11. ids.env: `ID_ANA_SMB_SITZUNG_GEMEINSAM_G1_WEBM` = `ID_ANA_SMB_GEMEINSAM_G1_WEBM` = 107, `ID_ANA_SMB_SITZUNG_GESPERRT_WEBM` = `ID_ANA_SMB_GESPERRT_WEBM` = 41 |
| Erwartung widerspricht sich selbst | In upload, copy, tag, restore, exclude-user-after und exclude-storage-after stehen alle 11 IDs zugleich in `files` (muss im Vorrat stehen) und in `neverFetched` (darf nie im Vorrat stehen), in reattach 9 davon. Kein Produkt kann beides erfüllen. neverFetched hat 14 Einträge in diesen 7 Phasen und 3 in den anderen 13, je nachdem, ob M2 beim Lesen der Wahrheit in oc_mounts steht |
| Wer hat geladen | 17 Gateway-Zeilen für die 11 IDs (GET der Datei, keine Kopf-Route), alle 200, alle `userId=ana`; kein anderer Nutzer |
| Darf ana das über M1 | Alle 11 stehen in jeder Phase ab move-cross als `active`, Stufe `keyed`, `storageId` 4 im Vorrat; `truth.sh` liest dieselben Dateien als ana per smbclient (Quelle `smb:ana`) und erwartet sie active. M1 ist `password::logincredentials` für ana |
| Über welchen Mount | Aus dem Zugriffslog nicht ablesbar: es nennt Nutzer und Datei-ID, nicht den Mount; das Gateway nimmt `getFirstNodeById`. Indizien: `SessionCredentials::manipulateStorageConfig` (stable33) wirft ohne Anmeldedaten der Sitzung, files_external macht daraus einen FailedStorage; nextcloud.log des Laufs nennt sechsmal "Undefined array key -1 at lib/private/Files/Node/Root.php#471" (ein Mount mit Root-ID -1, also ein gescheiterter Speicher, bei der Suche nach einer Datei-ID), einmal im Abruf `files/105?userId=ana` um 03:43:23, der trotzdem 200 antwortete. Ein Abruf über M2 ist nirgends belegt; ausschließen kann das Log ihn nicht. In beiden Fällen wäre der Leser ana mit den Rechten von ana auf demselben Speicher |
| Wirklich Ausgeschlossene | `truth.sh` führt als vor dem ersten Durchlauf ausgeschlossen nur 83 (ana privat), 91 (eva), 95 (fritz); über alle 20 Wahrheiten ist die Vereinigung von neverFetched genau diese 3 plus die 11. Für 83, 91, 95: 0 Gateway-Zeilen (Datei und Kopf), 0 Zeilen in allen 20 `occ :files --json --all`, also kein Verweis und damit kein Inhalt; shares:eva_finds_nothing grün |
| Grenze des Belegs | Die Kopie von state.db im Artefakt ist leer (4096 Bytes, keine Tabelle: der Schritt "Collect the logs" kopiert die WAL-Datei nicht mit). Der Zustand stammt deshalb aus `occ-files-*.json`, nicht aus state.db |

Was die Erwartung schützen soll: D-02-03 sagt "Externe Speicher mit Anmeldedaten aus der Sitzung werden übersprungen", 02-04 sagt für initial "M2 (Sitzung) fehlt, status.skippedStorages nennt M2". 02-12 hat entschieden: "Mehrere Mount-Konfigurationen auf einem Speicher: klassifiziert wird nach der ersten mit hintergrundfähiger Anmeldung". Die Zusage ist also "nichts wird über den Sitzungs-Mount geladen", nicht "diese Dateien werden nie geladen"; 02-01 hat M2 auf dieselbe Freigabe wie M1 gelegt, 02-04 hat das bei neverFetched nicht bedacht. Der Beleg trägt die Lesart "Fehler der Erwartung": die Erwartung ist in sich widersprüchlich, alle Abrufe liefen als der berechtigte Nutzer, kein Ausgeschlossener wurde geladen.

### Korrektur

| Commit | Inhalt |
|---|---|
| d62e38c test(02-04) | Gate: `truth.sh` darf die IDs des Sitzungs-Mounts nicht pauschal nach neverFetched schreiben, muss sie nach ihren anderen Wegen teilen, `sessionShared` schreiben und IDs ohne anderen Weg in neverFetched behalten; `compare.sh` prüft `session_shared_readers`, der Selbsttest verschiebt die Prüfung. Drei auslösende Fälle. RED: 9 Fälle rot |
| 85921b8 fix(02-04) | `truth.sh` `session_mount`: je ID von M2 die anderen Mounts desselben Speichers aus oc_mounts (ohne ausgeschlossene, gelöschte, verschwundene Nutzer), deren Root die Datei enthält. Gibt es einen: `sessionShared[id] = [Nutzer]`; gibt es keinen: weiter neverFetched. `compare.sh`: neue Prüfung `session_shared_readers` (jede Gateway- und Kopf-Zeile einer solchen ID nennt einen dieser Nutzer; eine Zeile ohne Nutzer zählt als Verstoß), Selbsttest mit einer fremden Zeile. `common.sh` `gateway_users`. README der Abnahme angepasst |

neverFetched ist damit nicht schwächer als nötig: 83, 91, 95 bleiben, und jede ID, die nur M2 erreicht, bleibt auch. Für die geteilten IDs kommt eine Prüfung dazu, die es vorher nicht gab. Grenze: der Mount selbst ist im Zugriffslog nicht sichtbar; `initial:skipped_session_mount` (occ :status nennt M2 als übersprungen) bleibt unverändert.

Geprüft ohne CI, mit den echten Skripten:
- `core_checks` aus `compare.sh` gegen die Dateien des Laufs (neue Wahrheit: die 11 IDs aus neverFetched nach sessionShared mit Leser ana): in allen 20 Phasen never_in_stock, never_in_log und session_shared_readers grün.
- Positivkontrollen mit gepflanzter Zeile (Phase restore): `files/83?userId=ana` macht never_in_log rot (gefunden 83), `files/91/head?userId=eva` macht never_in_log rot (91), `files/107?userId=cem` macht session_shared_readers rot (107:cem), `files/41/head?userId=dan` rot (41:dan), `files/105` ohne Nutzer rot (105:-), `files/107?userId=ana` bleibt grün.
- `compare.sh --self-test` gegen die Dateien des Laufs: alle fünf Verschiebungen schlagen einzeln an, auch "FAIL self-test:session_shared_readers erwartet= gefunden=999999998:x". Mit ausgeschalteter Leserprüfung endet der Selbsttest mit "compare self-test did not fail (foreign-reader)", Exit 1.
- `session_mount` gegen kleine Nachbauten der drei gelesenen Tabellen: M2 nicht in oc_mounts: nichts; nur M2: alle neverFetched; M1 daneben: alle sessionShared mit ana; dazu eine Freigabe an dan unter gemeinsam: dort ana und dan; anderer Mount nur mit Root gemeinsam: nur die IDs darunter geteilt (ein Ordner `gemeinsamer` nicht), der Rest neverFetched; anderer Mount nur für die ausgeschlossene eva: alle neverFetched; anderer Mount auf einem anderen Speicher: alle neverFetched.

Gates auf 85921b8: ruff check und format grün (71 Dateien), pyright 0 Fehler, vulture Exit 0, pytest 943 grün; `bash -n` für truth.sh, compare.sh, common.sh grün.

### Die sieben betroffenen Phasen mit den Daten dieses Laufs

| Phase | never_in_stock, never_in_log, session_shared_readers | Was rot bliebe | Zuordnung |
|---|---|---|---|
| upload | grün | active_set, unreadable_set, files_count, unreadable_count, contents, transcribed | Befund 2 (Vorrat ohne Crawl), lokal korrigiert in 11db11a |
| copy | grün | dieselben | Befund 2 |
| tag | grün | dieselben | Befund 2 |
| restore | grün | restore_no_download | 18 |
| exclude-user-after | grün | active_set, unreadable_set, files_count, unreadable_count, ben_storage_refs | 18 |
| exclude-storage-after | grün | active_set, unreadable_set, files_count, unreadable_count, m3_refs, files_fewer | 18 |
| reattach | grün | active_set, unreadable_set, files_count, unreadable_count, contents, transcribed, transcribed_plus_one | 19, 20 (Folge von vanish und der Ausschlüsse aus 18) |

Die anderen 13 Phasen hatten M2 nicht in oc_mounts und sind von dieser Korrektur nicht berührt. Ob upload, copy und tag mit vollem Vorrat ganz grün werden, zeigt erst ein Lauf; move-cross und trash waren es.

## Deviations from Plan

### Auto-fixed Issues

**3. [Rule 1 - Fehler] neverFetched führt Dateien, die über einen erfassbaren Mount im Vorrat stehen müssen**
- **Gefunden bei:** Task 2, Lauf 43359737879; geklärt im Zwischenauftrag der Hauptsitzung
- **Fix:** d62e38c, 85921b8 (Nachtrag oben), lokal


**1. [Rule 1 - Fehler] Kontrollbein prüft den ganzen Checkout**
- **Gefunden bei:** Task 2, Lauf 43359737879, Job leak-control
- **Fix:** 1862b53, 00928f7 (siehe oben), lokal

**2. [Rule 1 - Fehler] Warten der Abnahme endet vor dem ersten Crawl**
- **Gefunden bei:** Task 2, Lauf 43359737879, Job discovery
- **Fix:** 9b59082, 11db11a (siehe oben), lokal

### Abweichungen im Ablauf

- **Kein workflow_dispatch.** Der Plan sieht `gh workflow run php.yml` vor, falls PHP gates nicht startet; die Vorgabe der Hauptsitzung verbietet jeden Dispatch. Nicht nötig geworden: PHP gates startete per Push.
- **Autorenprüfung erweitert** um Committer und Co-Authored-By (Vorgabe der Hauptsitzung), Inhaltsprüfung auf Schlüssel und Tokens zusätzlich zum Plan.
- **ghcr-Zusatzbeleg** für das Paket `audio_video_search` wie in 02-11 (`approvals/ghcr-extra-before` und `-after`), im Plan nicht genannt.
- **Der verify-Befehl von Task 2 ist nicht grün** (vier PHASE PASS und die Leck-Zeile fehlen); der Plan gilt als rot, nicht als abgeschlossen.
- **Task 3 angehalten statt entschieden:** die Korrektur ist lokal, die Wahl push-fix oder stop liegt beim Owner; `not-needed` trifft nicht zu.
- **Lokale Gates vor dem Push** liefen nach der Owner-Wahl, nicht davor (die Wahl kam mit dem Auftrag); Ergebnis grün, erst danach wurde die Freigabedatei geschrieben.
- **Zwei Zeilen in deferred-items.md** ergänzt (Befund 3, Takt des SchedulerJob).
- STATE.md, ROADMAP.md und die Pläne 02-18 bis 02-22 nicht angefasst.

## Offene Punkte

- Zweiter Checkpoint: Push von HEAD auf phase-02 (sechs Korrektur-Commits plus die docs-Commits von 02-17) braucht eine neue Owner-Wahl und eine neue Freigabedatei für den neuen SHA.
- Befund 3 (neverFetched und M2): geklärt und lokal korrigiert (Nachtrag, d62e38c, 85921b8). Offen bleibt die Grenze, dass das Zugriffslog den Mount nicht nennt, und dass die Kopie von state.db im Artefakt leer ist (WAL-Datei fehlt); beides steht in deferred-items.md.
- Takt des SchedulerJob (bis zu fünf Minuten bis zum Erst-Crawl nach bereitem Backend): Owner-Entscheid, ob das Produkt das ändern soll; steht in deferred-items.md.
- DISC-02, DISC-03, DISC-05: nicht abgehakt; die Abnahme der externen Speicher, des Lesebeweises und der Ausschlüsse vor dem ersten Durchlauf ist in CI erst mit einem grünen Lauf von initial, read-proof, shares, access-control und dem Kontrollbein belegt.
- Beobachtung ohne Wertung: nextcloud.log des Laufs nennt `QueueController::claim executed 289 queries` (Hinweis des Servers im Debug-Modus).

## Self-Check: PASSED

- Commits vorhanden: 1862b53, 00928f7, 9b59082, 11db11a, d62e38c, 85921b8.
- Dateien vorhanden (lokal, nicht committet): approvals/push-c1b6375…, main-before, ghcr-before, ghcr-after, ghcr-extra-before, ghcr-extra-after, discovery-c1b6375….log.
- origin/phase-02 = c1b6375, origin/main = ea97b58 (unverändert).
