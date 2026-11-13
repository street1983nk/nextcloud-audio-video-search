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
| never_in_stock, never_in_log in sieben Phasen | Befund 3 | Fehler der Erwartung, offen |

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

## Deviations from Plan

### Auto-fixed Issues

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

- Zweiter Checkpoint: Push von HEAD nach diesem SUMMARY-Commit auf phase-02 (vier Korrektur-Commits plus dieser docs-Commit) braucht eine neue Owner-Wahl und eine neue Freigabedatei für den neuen SHA.
- Befund 3 (neverFetched und M2): Owner-Entscheid zur Erwartung der Abnahme. Ohne ihn bleiben upload, copy und tag auch nach der Korrektur rot, sobald M2 beim Lesen der Wahrheit in oc_mounts steht; die vier vom Plan verlangten Phasen hatten in diesem Lauf 3 Einträge und wären davon nicht betroffen, sicher ist das nicht.
- Takt des SchedulerJob (bis zu fünf Minuten bis zum Erst-Crawl nach bereitem Backend): Owner-Entscheid, ob das Produkt das ändern soll; steht in deferred-items.md.
- DISC-02, DISC-03, DISC-05: nicht abgehakt; die Abnahme der externen Speicher, des Lesebeweises und der Ausschlüsse vor dem ersten Durchlauf ist in CI erst mit einem grünen Lauf von initial, read-proof, shares, access-control und dem Kontrollbein belegt.
- Beobachtung ohne Wertung: nextcloud.log des Laufs nennt `QueueController::claim executed 289 queries` (Hinweis des Servers im Debug-Modus).

## Self-Check: PASSED

- Commits vorhanden: 1862b53, 00928f7, 9b59082, 11db11a.
- Dateien vorhanden (lokal, nicht committet): approvals/push-c1b6375…, main-before, ghcr-before, ghcr-after, ghcr-extra-before, ghcr-extra-after, discovery-c1b6375….log.
- origin/phase-02 = c1b6375, origin/main = ea97b58 (unverändert).
