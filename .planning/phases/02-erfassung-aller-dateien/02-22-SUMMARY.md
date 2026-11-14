---
phase: 02-erfassung-aller-dateien
plan: 22
subsystem: abnahme
tags: [acceptance, ci, discovery, upgrade, leak-control, ghcr, push-11]
requires: [02-21]
provides:
  - "Push 11 (a99565a) mit Python gates, PHP gates, Deploy through HaRP und Discovery acceptance legs=all grün"
  - "D-02-07 auf sechs Beinen (stable33, stable34, stable35 je amd64 und arm64): 20 von 20 Phasen, je 287 PASS, 0 FAIL"
  - "Upgrade-Beweis vom echten 0.1.0 (82f1655) nach 0.2.0 auf stable33, stable34, stable35 amd64 und stable35 arm64 grün"
  - "Doku zu Anmeldedaten in der Datenbank als bewusste Entscheidung (DE, EN, FR, CHANGELOG)"
affects: [03]
tech-stack:
  added: []
  patterns:
    - "Textprüfung der Commits erkennt auch fixes, fixed, Doppelpunkt und owner/repo#N"
key-files:
  created: []
  modified:
    - docs/install.md
    - docs/install.en.md
    - docs/install.fr.md
    - CHANGELOG.md
    - .planning/phases/02-erfassung-aller-dateien/02-22-PLAN.md
decisions:
  - "Owner 14.11.2026: Satz zu Anmeldedaten in der Datenbank wörtlich übernommen; EN und FR mit den echten Bezeichnungen aus files_external"
  - "Owner 14.11.2026: Textprüfung im Plan erweitert, weil fixes #N durchrutschte"
  - "Owner 14.11.2026: Push 11 und ein Dispatch legs=all; ausgeführt von der Hauptsitzung"
metrics:
  duration: "ca. 80 min (mit zwei Checkpoints und CI)"
  completed: 2026-11-14
  tasks: "3 von 3 (Task 3: Korrekturschleife nicht nötig, ein formaler Punkt offen, siehe Abweichungen)"
---

# Phase 2 Plan 22: Abnahme der Phase Summary

Push 11 auf phase-02 (6ddfd34..a99565a). Die Abnahme D-02-07 ist auf allen sechs Beinen grün: 20 von 20 Phasen, Samba-Kontrolle, Selbsttests und Zugriffslog-Kontrolle bestanden, und das Kontrollbein zeigt das Leck. Der Upgrade-Job vom echten 0.1.0 läuft auf vier Beinen grün. main und ghcr sind unverändert.

## Commits

| Task | Commit | Inhalt |
|------|--------|--------|
| 1 Vorlauf | cf122c4 | Anmeldedaten in der Datenbank als bewusste Entscheidung (install DE, EN, FR, CHANGELOG 0.2.0) |
| 1 Vorlauf | a99565a | Textprüfung im Plan erweitert (fixes, fixed, Doppelpunkt, owner/repo#N) |
| 1 | (Checkpoint) | Owner 14.11.2026 "Ja, push und Abnahme starten (Empfohlen)" |
| 2 | (Hauptsitzung) | Push 6ddfd34..a99565a nach phase-02, ein Dispatch discovery-e2e legs=all |

## Läufe für a99565a2243f5c1e11adfb71fc2909a1b6c88fe8

| Lauf | Workflow | Ereignis | Ergebnis |
|------|----------|----------|----------|
| [43570120264](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43570120264) | Discovery acceptance | workflow_dispatch (legs=all) | success, 7 Jobs success |
| [43570120704](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43570120704) | Discovery acceptance | push | cancelled (Concurrency, vom Dispatch abgelöst) |
| [43570120498](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43570120498) | Deploy through HaRP | push | success, 10 Jobs success |
| [43570120510](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43570120510) | Python gates | push | success |
| [43570120508](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43570120508) | PHP gates | push | success |

Prüfung aus verify: 4 Workflow-Namen, genau 1 Dispatch-Lauf, 6 Beine success, leak-control success, PHASE PASS initial, read-proof, shares und access-control, LEAK CONTROL SHOWED THE LEAK. Die Prüfung "kein Lauf ungleich success" ergibt 1 (der abgebrochene Push-Lauf), siehe Abweichungen.

## PASS/FAIL je Bein (Schritt "Run the phases", Lauf 43570120264)

| Bein | Prüfungen PASS | FAIL | PHASE PASS | Urteil |
|------|----------------|------|------------|--------|
| stable33 ubuntu-24.04 | 287 | 0 | 20 | 20 of 20 phases passed |
| stable33 ubuntu-24.04-arm | 287 | 0 | 20 | 20 of 20 phases passed |
| stable34 ubuntu-24.04 | 287 | 0 | 20 | 20 of 20 phases passed |
| stable34 ubuntu-24.04-arm | 287 | 0 | 20 | 20 of 20 phases passed |
| stable35 ubuntu-24.04 | 287 | 0 | 20 | 20 of 20 phases passed |
| stable35 ubuntu-24.04-arm | 287 | 0 | 20 | 20 of 20 phases passed |

Phasen, jede auf allen sechs Beinen PASS: initial, read-proof, shares, access-control, upload, overwrite, copy, rename, move-cross, tag, foreign-change, trash, restore, exclude-user-after, exclude-storage-after, exclude-after, reprove, vanish, delete-user, reattach.

Die einzigen FAIL-Zeilen im Log stammen aus den Selbsttests (gewollt, je Bein 5: files_count, contents, transcribed, never_in_log, session_shared_readers). Dazu kommen zwei Zeilen, in denen der Workflow sein eigenes Skript wiedergibt (`echo "PHASE FAIL ${phase}"`). Eine echte FAIL-Zeile gibt es nicht.

## Belegzeilen der Kontrollen (je Bein gleich)

- Samba: `samba positive control: ana reads gesperrt.webm, ben gets NT_STATUS_ACCESS_DENIED` (6 Beine und das Kontrollbein)
- Selbsttests: `compare self-test passed: every shifted check failed on its own` (6 Beine)
- Zugriffslog: `access log positive control: 1 gateway line(s) for file 74` (6 Beine)
- Leck: Kontrollbein `published media 10 rev 1`, `ledger: test result on file 61`, `LEAK CONTROL SHOWED THE LEAK`. Hauptbeine: read-proof `ben_finds_no_denied_copy` PASS, kein Leck.
- Das Kontroll-Image heißt `localhost:5000/audio_video_search_backend:leak-control` und liegt nur in der lokalen Registry des Runners, nicht in ghcr.
- Der Wettlauf aus 02-17b (groupfolders-Jobs) zeigt sich nicht: "failed to create instance of background job" steht weder im Lauf-Log noch in den sieben Artefakten.

## Upgrade 0.1.0 nach 0.2.0 (Lauf 43570120498, Jobs upgrade)

Auf stable33, stable34 und stable35 (ubuntu-24.04) sowie stable35 (ubuntu-24.04-arm) lauten die Zeilen gleich:
- vorher: Worktree auf `82f1655`, `previous 0.1.0, current 0.2.0`, admin state `own 0.1.0, backend 0.1.0, sampleCount 3`, `schema_version ('1',), probe ('', 'sample')`, keine oc_avs_-Tabelle
- Update: `installed_version 0.2.0`, `nc_app_audio_video_search_backend runs localhost:5000/audio_video_search_backend:0.2.0`
- nachher: state.db mit derselben Inode und dasselbe Volume, admin state `own 0.2.0, backend 0.2.0, sampleCount 3`, `hits before ["50","51","52","53","54"], after ["50","51","52","53","54"]`, `schema_version ('2',), sample_ref with transcript (1, 1), old rows left (0,)`, oc_avs_queue, oc_avs_crawl und oc_avs_storage vorhanden

Damit ist der offene Punkt aus 02-21 (Upgrade nie gelaufen) belegt.

## main und ghcr

- main: `ea97b58` vor und nach den Läufen (letzter Commit auf main am 09.11.2026), gleich `main-before-77359a8...` von Push 10 am selben Morgen; nachher gesichert in `approvals/main-after-a99565a...`
- ghcr `audio_video_search_backend`: `STATE 404 Package not found` nach den Läufen (`approvals/ghcr-after-a99565a...`), gleich dem Zustand vor Push 10 (`ghcr-before-77359a8...`, per cmp identisch); kein Tag leak-control
- ghcr `audio_video_search` (zusätzlich): letzte Version vom 09.11.2026 mit den Tags `ea97b58...` und `dev`, gleich dem Stand nach Push 7 (cmp); kein Tag von phase-02, kein leak-control
- Positivkontrolle für Endpunkt und Scope: `findling_backend` liefert den Tag `1.6.2`. Name und Tag sind vorher über `gh api users/street1983nk/packages?package_type=container` bestätigt (Pakete: findling_backend, mcp_connector, gameworld, pdf_accessibility, audio_video_search, pii_redaction).

Die ghcr-Positivkontrolle setzt voraus, dass `findling_backend:1.6.2` existiert. Fehlt der Tag, nennt der Owner einen anderen bekannten Tag, und der Plan wird mit diesem Tag wiederholt.

## Messwerte

| Messung | Wert | Quelle |
|---------|------|--------|
| Upload bis Arbeitsvorrat (Datei 140, Phase upload) | 11 bis 27 s (amd64 27, 11, 27; arm64 17, 17, 16) | `file 140 is in the work stock after N s` |
| Erst-Vorrat vollständig nach Registrierung | 228 bis 258 s (Kontrollbein 290 s) | `work stock complete after N s`, erster Aufruf |
| Vorrat nach den Phasen | 0 bis 77 s | dieselbe Zeile je Phase |
| Rescan je 1000 Dateien | nicht messbar | Topologie hat 52 bis 54 Dateien |
| Dauer des Lesebeweises | nicht messbar | Lauf gibt keine Zeit je Beweis aus, nur das Ergebnis (read-proof PASS) |

## Annahmen A2 bis A8 (Tabelle in 02-RESEARCH.md)

| Annahme | Stand |
|---------|-------|
| A2 storage_mtime gleich für alle Mitglieder einer SMB-Freigabe | nicht messbar (Lauf gibt storage_mtime nicht aus) |
| A3 abgebrochener Scanner-Lauf setzt fort | nicht messbar |
| A4 Papierkorb im Gruppenordner ohne /files/-Mountpunkt | nicht messbar: die Phase trash legt eine Datei aus dem Home von ana in den Papierkorb, keine aus dem Gruppenordner |
| A5 hängender smbclient belegt einen php-fpm-Worker | nicht messbar (CI ohne php-fpm, keine hängende Freigabe) |
| A6 smb::kerberos ohne Ticket im Cron | nicht messbar (keine Kerberos-Topologie) |
| A7 Cache-Ereignisse feuern nicht für die Fortpflanzung | nicht direkt gemessen; die Phasen upload, overwrite, copy, rename und tag sind grün, Zählung der Listener-Aufrufe fehlt |
| A8 64-KiB-Kopf reicht als Lesebeweis bei SMB | bestätigt für DENY READ: Samba-Kontrolle `ben gets NT_STATUS_ACCESS_DENIED`, read-proof `reason_52` und `ben_finds_no_denied_copy` PASS auf sechs Beinen, Kontrollbein zeigt das Leck ohne Beweis |

## Deviations from Plan

1. **Abgebrochener Push-Lauf von Discovery acceptance (43570120704).** Die Concurrency-Gruppe des Workflows hat ihn abgebrochen, als der Dispatch-Lauf startete. Der Plan erwartet fünf Läufe mit success; es sind vier success und ein cancelled. Inhaltlich deckt der Dispatch-Lauf das Bein des Push-Laufs (stable33 ubuntu-24.04) mit ab, und es ist grün. Die strenge Prüfung aus verify (`length == 0`) ist damit rot. Das ist kein Sicherheitsbefund. Owner-Entscheid: so annehmen oder den abgebrochenen Lauf neu starten (nur mit Freigabe, Re-run ist ein Workflow-Start).
2. **Fehlende Vorher-Dateien `main-before-a99565a...` und `ghcr-before-a99565a...`.** Die Hauptsitzung hat vor dem Push keine geschrieben. Als Ersatz dienen die Dateien von Push 10 am selben Morgen (`main-before-77359a8...` und `ghcr-before-77359a8...`, per cmp gleich dem heutigen Stand) und das Datum des letzten Commits auf main (09.11.2026). Der Vergleich ist damit belegt, aber nicht mit den Dateinamen aus dem Plan.
3. **Doku und Plan vor dem Push geändert (Owner-Auftrag).** cf122c4 und a99565a; Gates: trilingual, public_texts und public_artifacts 32 grün, pytest `-p no:xdist` 1023 grün, ruff grün, Gedankenstriche 0 (Positivkontrolle 1). Die Nachricht von a99565a habe ich vor dem Push einmal lokal geändert, weil sie selbst eine Schließformel mit Nummer enthielt.
4. **Docker nicht gestartet.** Im Diff ändert sich an PHP nur die Version in info.xml; PHP gates ist in CI grün.

## Offene Punkte

- Owner-Entscheid zum abgebrochenen Push-Lauf (Abweichung 1).
- Messwerte für Rescan je 1000 Dateien und die Dauer des Lesebeweises bleiben für Phase 11 (Hardware-Messung) offen; A2 bis A7 sind in CI nicht messbar.
- Die offenen Zeilen in deferred-items.md (02-16 REASON_SWITCHED_OFF, 02-16 Probe ohne Speicher-ID, 02-17 SchedulerJob-Takt, 02-17 WAL-Kopie im Artefakt, 02-18 reload, 02-20 Dauer von reconcile/run) bleiben stehen.
- STATE.md und ROADMAP.md sind nicht fortgeschrieben (Auftrag: keine gsd-sdk-Befehle, die sie umschreiben). Phase 2 ist bereit für `/gsd:verify-work 2`.

## Self-Check: PASSED

Commits cf122c4 und a99565a sind vorhanden und liegen auf origin/phase-02. Die Läufe 43570120264, 43570120498, 43570120510 und 43570120508 sind success. Die Dateien `approvals/discovery-a99565a...log`, `approvals/deploy-harp-a99565a...log`, `approvals/ghcr-after-a99565a...`, `approvals/ghcr-extra-after-a99565a...` und `approvals/main-after-a99565a...` sind vorhanden.
