---
phase: 02
slug: erfassung-aller-dateien
status: draft
threats_open: 0
asvs_level: 2
created: 2026-11-15
---

# Phase 02: Security

> Sicherheitsvertrag je Phase: Threat-Register, akzeptierte Risiken, Audit-Verlauf.
> Register aus den 26 `<threat_model>`-Blöcken der PLAN-Dateien 02-01 bis 02-22 (inkl. 15b, 15c, 16b, 17b; register_authored_at_plan_time: true, rückwirkend geprüft).
> Geprüfter Stand: HEAD `dc742f7` (Arbeitsbaum zusätzlich mit uncommitteter Änderung an `backend/tests/test_model_download.py`, nicht Teil des Belegs).
> Belege sind Datei:Zeile im Repo. Prozess-Threats (Owner-Tore, Pushes, ghcr/main) sind über `approvals/` und die SUMMARY-Dateien belegt; die Vorher/Nachher-Dateien wurden am 2026-11-15 per `cmp` neu verglichen. Die globalen Änderungen vom 15.11.2026 aus Phase 3 (`logs.py` ohne Exception-Text, Modell-Urteile nur im Prozess) gelten hier als vorhandene Mitigation, wo sie passen.
> `T-02-55` steht in 02-15 und 02-15b und ist hier ein Eintrag mit beiden Mitigationen.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Nextcloud-Ereignisse nach Warteschlange | Node-, Cache-, Gruppen-, Nutzer-Events | Datei-IDs, Speicher-IDs |
| Cron (Crawl, Rescan, Klassifikation) nach externem Speicher | files_external meldet sich im Namen eines Nutzers an | Metadaten, Anmeldung |
| PHP-Warteschlange nach Container (Claim/Ack/Unlock) | signierte ExApp-Routen | IDs, etag, Größe, Vorfilter-Schlüssel, Leser-UID |
| Container nach Gateway (Inhalt, Kopf) | signierte ExApp-Routen | Dateibytes, 64-KiB-Kopf |
| Container nach Reconcile-Routen | signierte ExApp-Routen | IDs, etags, Flags |
| Admin-Regeln (Ausschlüsse) nach Prüfstellen | appconfig, occ | Regeln, Präfixe |
| alte state.db / Installation 0.1.0 nach 0.2.0 | Schemawechsel v1 nach v2, Migration PHP | Zustandsdaten |
| CI-Kontrollbein nach Runner | absichtlich gepatchtes Image | Testdaten |
| lokales Repo nach GitHub, ghcr | Push auf `phase-02` | Code, Images |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (Beleg) | Status |
|-----------|----------|-----------|-------------|--------------------|--------|
| T-02-01 | Tampering | Kontroll-Image | mitigate | lokale Registry `.github/workflows/discovery-e2e.yml:65,217-221,610`, `permissions: contents: read` :605-606, Artefakt nur `logs/` :784-788; Gates `backend/tests/test_discovery_workflow.py:337,373,385,422` | closed |
| T-02-02 | Tampering | Hauptbein mit gepatchtem Code | mitigate | `git -C app-src diff --quiet -- backend/` `discovery-e2e.yml:219,681`; Gate `test_discovery_workflow.py:346,359,399` | closed |
| T-02-03 | Denial of Service | hängender SMB-Download | mitigate | `PHP_CLI_SERVER_WORKERS=8 ... max_execution_time=120` `discovery-e2e.yml:149,654`; Mount-Option `timeout=20` `ci/discovery/topology.sh:340,348` | closed |
| T-02-04 | Information Disclosure | Artefakte | accept | siehe AR-02-01 | closed |
| T-02-05 | Tampering | Migration | mitigate | `BEGIN IMMEDIATE` `backend/src/audio_video_search_backend/store/migrate.py:152-154`; Test `backend/tests/test_store_migration_v2.py:222` | closed |
| T-02-06 | Information Disclosure | Suche über nicht aktive Verweise | mitigate | `_FILE_IDS_FOR_MEDIA` nur `state = 'active'` bzw. sichtbare Probe `store/repo.py:158-166,1683-1691` | closed |
| T-02-07 | Tampering | Probe überschreibt Verweis | mitigate | eigene Schicht `sample_ref` `store/schema.sql:104-116`, `put_sample` schreibt nie file_ref `store/repo.py:1716-1721`; Tests `test_sample_layer.py:108,121`, `test_store_schema.py:257` | closed |
| T-02-08 | Elevation of Privilege | QueueController | mitigate | `#[ExAppRequired]` + `rejectForeignCaller()` `php/lib/Controller/QueueController.php:43-47,69-73,87-91,109-121`; Test `php/tests/Unit/QueueControllerTest.php:61`; Gate Regel 1 `test_php_gates.py:280` | closed |
| T-02-09 | Information Disclosure | describe | mitigate | feste Schlüsselmenge `php/lib/Service/QueueService.php:46,166`; Gate Regel 13 `test_php_gates.py:550,566` | closed |
| T-02-10 | Denial of Service | Listen | mitigate | `QueueMapper::MAX_BATCH = 256` `php/lib/Db/QueueMapper.php:93,223`; `intList` `QueueController.php:132-134`; Test `QueueControllerTest.php:84` | closed |
| T-02-11 | Tampering | Ack fremder Claims | mitigate | Token `^[0-9a-f]{32}$` `QueueController.php:123-125`; jede Änderung nur mit `lock_token` `QueueMapper.php:278,316,326,350,359,377`; Test `QueueMapperTest.php:132` | closed |
| T-02-12 | Information Disclosure | nicht klassifizierter Speicher | mitigate | `capturable` Standard 0 `php/lib/Migration/Version000200Date20261107000000.php:95`; ohne Zeile nie erfassbar `QueueService.php:100-107` | closed |
| T-02-13 | Repudiation | truth.sh | mitigate | Kopf `ci/discovery/truth.sh:5-11`; Gate ohne App-Code `test_discovery_workflow.py:615-627` | closed |
| T-02-14 | Tampering | compare.sh grün trotz Fehler | mitigate | Selbsttest `ci/discovery/compare.sh:502-556,561`; Gate `test_discovery_workflow.py:629-640` | closed |
| T-02-15 | Information Disclosure | Leck unbemerkt | mitigate | `ci/discovery/controls.sh:64-89` (Abbruch ohne Leck); Lauf 43570120264 `LEAK CONTROL SHOWED THE LEAK`, Hauptbeine ohne Leck (02-22-SUMMARY.md:58,80) | closed |
| T-02-16 | Repudiation | Zugriffslog leer | mitigate | `controls.sh:53-55` (Lauf ungültig ohne Gateway-Zeile); Reihenfolge-Gate `test_discovery_workflow.py:876` | closed |
| T-02-17 | Information Disclosure | ClaimItem | mitigate | `extra="forbid", strict=True` `backend/src/audio_video_search_backend/nc_queue.py:52,91,107`; Test `test_intake.py:495` | closed |
| T-02-18 | Tampering | apply_intake | mitigate | Commit vor Ack `worker/intake.py:9-12,106-117`; Tests `test_intake.py:195,450,466` | closed |
| T-02-19 | Denial of Service | Claim-Größe | mitigate | `items: list[ClaimItem] = Field(max_length=MAX_BATCH)` `nc_queue.py:110`, Feldgrenzen :54-62; `QUEUE_TIMEOUT` `nc.py:245,262` | closed |
| T-02-20 | Repudiation | verlorene Löschaufträge | mitigate | Seit 02-15 werden alle Kinds in derselben Transaktion umgesetzt `worker/intake.py:13-17`, `Kind` geschlossen `nc_queue.py:45`; fehlgeschlagener Commit entsperrt `intake.py:110`; Test `test_intake.py:418` | closed |
| T-02-21 | Information Disclosure | Crawl vor Ausschluss | mitigate | Crawl nur in `CRAWL_STATES` `php/lib/BackgroundJobs/SchedulerJob.php:71,104-108` | closed |
| T-02-22 | Denial of Service | großer Mount | mitigate | `MAX_FILES`, `MAX_SECONDS`, Cursor `php/lib/BackgroundJobs/StorageCrawlJob.php:43-45,83-111` | closed |
| T-02-23 | Information Disclosure | Pfade an den Container | mitigate | Gate Regel 13 `test_php_gates.py:35-38,550`; Reconcile-Antworten nur IDs/etags/Flags `php/lib/Controller/ReconcileController.php:91-98,144-149` | closed |
| T-02-24 | Denial of Service | Listener-Last | mitigate | try/catch um jede Behandlung `php/lib/Listener/FileEventListener.php:72-90`; Medientyp-Prüfung vor Speicher-/Ausschlussfragen `QueueService.php:78-83`, Mount-Wurzeln je Prozess gecacht `php/lib/Service/StorageService.php:107-120` | closed |
| T-02-25 | Tampering | Speicherwechsel-Verschieben | mitigate | Ersetzungsregeln `QueueMapper.php:74-85`; Test `php/tests/Unit/CacheEventListenerTest.php:146` | closed |
| T-02-26 | Tampering | abgeschnittener Download | mitigate | `size != expected_size` verwirft `nc.py:482,490,496`; `_validated` `worker/capture.py:157-161` | closed |
| T-02-27 | Denial of Service | Temp-Dateien | mitigate | Platzprüfung `nc.py:538` (`DISK_RESERVE_BYTES` :415), `finally` :556; Aufräumen beim Start `worker/capture.py:196-207` | closed |
| T-02-28 | Denial of Service | Dateisperre | mitigate | Strom erst vollständig in Temp-Datei `nc.py:469-498`, dann Auswertung | closed |
| T-02-29 | Tampering | falscher Inhalts-Schlüssel | mitigate | sha256 über alle Bytes `nc.py:471,489,498` | closed |
| T-02-30 | Information Disclosure | /coverage, /workstock | mitigate | ADMIN `backend/appinfo/info.xml:93-106`; feste Schlüssel `api/coverage.py:1-20`; Test `test_coverage_count.py:299,377` | closed |
| T-02-31 | Repudiation | Quote über 100 % | mitigate | Eigenschaftstest 500 Fälle `backend/tests/test_coverage_count.py:106-130` (`transcribed <= contents <= files`) | closed |
| T-02-32 | Elevation of Privilege | Kopf-Route | mitigate | `GatewayController.php:148-155` Wächter zuerst, `resolve` mit `actAs` und `readableNode` :228-241; Gates Regel 1 und 4 `test_php_gates.py:280,293` | closed |
| T-02-33 | Information Disclosure | Kopf-Route | mitigate | `HEAD_BYTES = 65536` `GatewayController.php:69,195-209`; gleiche 404 :164-166,:243-245 | closed |
| T-02-34 | Repudiation | files_accesscontrol | mitigate | `refusedByAccessControl` `php/lib/Service/FileAccess.php:91-114`; 403 access_control statt 500 `GatewayController.php:234-235,280-288` | closed |
| T-02-35 | Information Disclosure | occ | mitigate | `php/lib/Command/FilesCommand.php:90-98` (IDs, Zustand, Code), `php/lib/Command/StatusCommand.php:72-104` (Zahlen) | closed |
| T-02-36 | Spoofing | Owner-Freigabe (Push 5/6) | mitigate | Freigabedateien `approvals/push-<sha>` mit Inhalt `push-phase-02 <sha>` (10 Dateien, geprüft 2026-11-15) | closed |
| T-02-37 | Repudiation | Commit-Identität und Texte | mitigate | `git log`: nur street1983nk und dependabot, keine Session-/closes-Zeilen (geprüft 2026-11-15) | closed |
| T-02-38 | Tampering | main | mitigate | `approvals/main-before-*` (f908a85 bzw. ea97b58); Nachher per `ls-remote | cmp -` 02-11-SUMMARY.md:76; Wechsel f908a85 nach ea97b58 ist der eigene Owner-Push "docs: disclose the AI assistance" (lokale reflog) | closed |
| T-02-39 | Tampering | ghcr | mitigate | `approvals/ghcr-before-*`/`ghcr-after-*` und `ghcr-extra-*` per `cmp` identisch für 25d241b, 434a350, 80ce5c9, c1b6375, f8b28a5, ad6a32c (geprüft 2026-11-15); kein leak-control-Tag | closed |
| T-02-40 | Information Disclosure | prefilterKey | mitigate | Hash in PHP `QueueService.php:244-254`; Spalte `share_key_hash` (64) `Version000200Date20261107000000.php:92`, `StorageClassifier.php:174` | closed |
| T-02-41 | Denial of Service | Sitzungs-Speicher | mitigate | `NEVER`-Liste vorab `php/lib/Service/StorageClassifier.php:47`; Neuprüfung 24 h :64; 60 s je Lauf `SchedulerJob.php:74,121` | closed |
| T-02-42 | Information Disclosure | falscher Leser | mitigate | `QueueService.php:268-308` (Heim = Besitzer, eigener Nutzer bei Einzel-Mount, sonst `readableFile` unter `actAs`, höchstens 5 Versuche) | closed |
| T-02-43 | Tampering | unklassifizierter Speicher | mitigate | wie T-02-12: `Version000200Date20261107000000.php:95`, `QueueService.php:100-107` | closed |
| T-02-44 | Information Disclosure | occ status | mitigate | `StatusCommand.php:91-100` (mount_id, Backend-Art, Anmeldeart, Grund, Zahl) | closed |
| T-02-45 | Information Disclosure | Vorfilter-Anhängen | mitigate | Lesebeweis `worker/read_proof.py:83`, Kopf-Hash/Länge `worker/capture.py:252-300`; AST-Gate `backend/tests/test_read_proof_gate.py:758,955,1144` | closed |
| T-02-46 | Information Disclosure | Rechte nach Anhängen entzogen | mitigate | erneuter Beweis `worker/capture.py:278-300`, Fehlschlag macht unreadable `_fail_proof` :300; Beweis alle 7 Tage `worker/reconcile.py:64` | closed |
| T-02-46b | Information Disclosure | Ausschnitt ohne gültigen Beweis | mitigate | `media_for_file` nur aktiver Verweis `store/repo.py:1693-1712`; `{"known": false}` `api/excerpt.py:34,57-60`; Test `test_excerpt_states.py:132,149` | closed |
| T-02-46c | Information Disclosure | Probe mit echtem Transkript | mitigate | Probe nur bei Stufe Probe `store/repo.py:164,1700-1707`; Test `test_sample_real_transcript.py:172`, `test_exclusion_forget.py:433` | closed |
| T-02-47 | Elevation of Privilege | Abschaltweg Lesebeweis | mitigate | Regeln a bis e und Gegenprobe g `test_read_proof_gate.py:758-1022` (u. a. :804,:834,:859,:890,:920,:994,:1022) | closed |
| T-02-48 | Tampering | weitere Schreibstelle für media_id | mitigate | Regel f mit Gegenprobe `test_read_proof_gate.py:843,1062,1089,1124,1144` | closed |
| T-02-49 | Denial of Service | hängender Kopf | mitigate | Sperrkreis je Speicher `worker/read_proof.py:45-47,120-169`; Test `test_restore_proof.py:328` | closed |
| T-02-50 | Tampering | Kontroll-Image | mitigate | Regel e `test_read_proof_gate.py:1022`; Workflow-Gate wie T-02-01 | closed |
| T-02-51 | Denial of Service | großer Speicher | mitigate | `BUDGET_SECONDS = 300`, `RESCAN_SECONDS = 86400` `php/lib/Service/RescanService.php:52,55,103` | closed |
| T-02-52 | Information Disclosure | nicht erfassbarer Speicher | mitigate | nur erfassbare Speicher `RescanService.php:67,107,117`; Crawl überspringt `SchedulerJob.php:131-136` | closed |
| T-02-53 | Information Disclosure | Transkript nach Ausschluss | mitigate | Vergessen samt Index `backend/tests/test_exclusion_forget.py:148,163,277,464,499`; Rollback :356 | closed |
| T-02-54 | Information Disclosure | verwaiste media | mitigate | kein aktiver Verweis, nicht gezählt `test_exclusion_forget.py:230,383`, `test_coverage_count.py:199` | closed |
| T-02-55 | Information Disclosure | Wiederherstellen mit entzogenem Recht | mitigate | kein Treffer vor bestandenem Beweis, Beweis vorgezogen `backend/tests/test_restore_proof.py:179,192,235,294,313`; `test_intake.py:735` | closed |
| T-02-55b | Denial of Service | viele Wiederherstellungen, hängender Speicher | mitigate | `test_restore_proof.py:328,360` mit Sperrkreis `read_proof.py:45-47` | closed |
| T-02-56 | Tampering | Löschen fremder Inhalte | mitigate | nur berührte media_ids `test_exclusion_forget.py:170,371`; RETURNING-Muster `store/repo.py:503-505` | closed |
| T-02-57 | Information Disclosure | Fenster Regel bis Download | mitigate | drei Prüfstellen: Listener `FileEventListener.php:192`, describe `QueueService.php:196-199`, Gateway `GatewayController.php:113,159`; Gate Regel 14 `test_php_gates.py:707,740` | closed |
| T-02-58 | Information Disclosure | Treffer für Ausgeschlossene | mitigate | `php/lib/Search/Provider.php:170-173,268` | closed |
| T-02-58b | Information Disclosure | Ausschnitt Abspielseite für Ausgeschlossene | mitigate | `php/lib/Controller/PageController.php:313-326` (vor Container-Frage, fail-closed, Antwort "kein Transkript") | closed |
| T-02-59 | Tampering | Traversal-Präfix | mitigate | `normalise`/`validate` `php/lib/Service/ExclusionService.php:393-411,762-800` (`.` und `..` abgelehnt :789) | closed |
| T-02-59b | Tampering | Steuerzeichen am Rand | mitigate | Prüfung am unveränderten Eintrag `ExclusionService.php:770` (`[\x00-\x1F\x7F]`, UTF-8) | closed |
| T-02-60 | Information Disclosure | Logs Ausschlüsse | mitigate | nur Listenname/Klasse/Zähler `ExclusionService.php:147,192,616`, `ExclusionClearJob.php:78,103,116,124`, `GroupEventListener.php:71,85,111` | closed |
| T-02-61 | Spoofing | Owner-Freigabe (Push 7/8) | mitigate | wie T-02-36 (`approvals/push-25d241b…`, `push-c1b6375…`, `push-bf2342c…`); Owner-Entscheid push-8 02-17b-SUMMARY.md:150 | closed |
| T-02-62 | Repudiation | Commit-Identität und Texte | mitigate | wie T-02-37 | closed |
| T-02-63 | Tampering | main | mitigate | wie T-02-38 | closed |
| T-02-64 | Tampering | ghcr | mitigate | wie T-02-39 | closed |
| T-02-65 | Information Disclosure | Regel ohne Befehl gesetzt | mitigate | Fingerabdruck `SchedulerJob.php:173-179`; Provider liest Regeln von jetzt `Provider.php:161` | closed |
| T-02-66 | Information Disclosure | Gruppenbeitritt | mitigate | sofortige Neubewertung `php/lib/Listener/GroupEventListener.php:62-111` | closed |
| T-02-67 | Tampering | applied_* zu früh | mitigate | `SchedulerJob.php:229-234` erst nach allen `enqueue`/Job-Einträgen :198-227 | closed |
| T-02-68 | Repudiation | Papierkorb als Löschen | mitigate | Entscheidung am Cache-Eintrag `QueueService.php:177-179,212-230` | closed |
| T-02-69 | Information Disclosure | Abgleich am Ausschluss vorbei | mitigate | requeue über `admissible` `ReconcileController.php:211-248`; Gate Regel 16 `test_php_gates.py:1013` | closed |
| T-02-70 | Tampering | Löschen aus gestörter Liste | mitigate | `ok: false` ohne Mounts `ReconcileController.php:100-105`; `classifyAbsent` :170-197; Container `worker/reconcile.py:236`; Test `test_reconcile_sweep.py:237,258` | closed |
| T-02-71 | Elevation of Privilege | Reconcile-Routen | mitigate | `ReconcileController.php:74-78,119-123,167-171,208-212,281`; Test `php/tests/Unit/ReconcileControllerTest.php:150` | closed |
| T-02-72 | Information Disclosure | Walk am Ausschluss vorbei | mitigate | requeue über PHP `worker/reconcile.py:24-26,380`; Gate `backend/tests/test_reconcile_walk.py:452` | closed |
| T-02-73 | Information Disclosure | entzogene SMB-Rechte | mitigate | `REPROOF_AGE_SECONDS = 7 * 86_400` `worker/reconcile.py:64`; Proof-Planung je Takt `test_reconcile_sweep.py:398` | closed |
| T-02-74 | Tampering | Löschen aus leerer Liste | mitigate | `worker/reconcile.py:8-10,236`; Tests `test_reconcile_sweep.py:237,258` | closed |
| T-02-75 | Denial of Service | Sweep verhungert | mitigate | eigener Stempel `SWEEP_STAMP` `worker/reconcile.py:58,250,268`; Test über Takte `test_reconcile_sweep.py:176,211` | closed |
| T-02-76 | Tampering | Update 0.1.0 auf 0.2.0 | mitigate | Lauf 43570120498 (vier Beine grün, 02-22-SUMMARY.md:10,84-91), prev aus Commit 82f1655 (02-21-SUMMARY.md:9,48); Mechanik heute in `deploy-harp.yml:781-782,826-840` (auf 0.2.0 nach 0.3.0 weitergezogen) | closed |
| T-02-77 | Repudiation | Upgrade-Test prüft nichts | mitigate | Positivkontrolle vorher (schema 1) 02-21-SUMMARY.md:17,48; heutige Form `deploy-harp.yml:1006-1027` | closed |
| T-02-78 | Spoofing | Owner-Freigabe (Push 9 bis 11) | mitigate | `approvals/push-77359a8…`, `push-6ddfd34…`, `push-a99565a…` mit passendem Inhalt | closed |
| T-02-79 | Information Disclosure | Leck im Hauptbein | mitigate | `PHASE FAIL`-Abbruch im Workflow, Lauf 43570120264: 20/20 Phasen je 287 PASS, 0 FAIL, kein Leck im Hauptbein (02-22-SUMMARY.md:9,73,80) | closed |
| T-02-80 | Tampering | main, ghcr | mitigate | `approvals/main-after-a99565a…` = `main-before-77359a8…` (ea97b58); `ghcr-after-a99565a…` = `ghcr-before-77359a8…` per `cmp` (geprüft 2026-11-15) | closed |
| T-02-81 | Repudiation | aufgeweichte Erwartung | mitigate | Änderungen an truth.sh/compare.sh nach 02-04 nur 11db11a, 85921b8, 3ee83c3, jeweils mit Lauf-ID im Commit-Text; 85921b8 verschärft (session_shared_readers) und ist dem Owner in 02-17-SUMMARY.md:166-198,291 vorgelegt | closed |
| T-02-82 | Information Disclosure | admissibleFile nach dem Fix | mitigate | `FileEventListener.php:179-197` (Pfad nicht bestimmbar ergibt null), Umbenennen weg ergibt delete :108-113 | closed |
| T-02-83 | Denial of Service | Jobliste ohne SchedulerJob | mitigate | `php/lib/Service/JobRegistry.php:35,53-64` (`IJobList::has` vor `add`) | closed |
| T-02-84 | Elevation of Privilege | Handshake schreibt Jobliste | mitigate | `ensure()` nach `rejectForeignCaller` `HandshakeController.php:46-57`; feste Klassenliste `JobRegistry.php:35` | closed |
| T-02-85 | Information Disclosure | Logs JobRegistry/Listener | mitigate | `JobRegistry.php:64,69` (Klassenname), `FileEventListener.php:89` (Klasse) | closed |
| T-02-86 | Tampering | discovery-e2e.yml | mitigate | Diff von 1b3b842 ohne Änderung an `on:`, `permissions`, `uses:`, Registry, Secrets (geprüft 2026-11-15); 02-17b-SUMMARY.md:79 | closed |
| T-02-87 | Denial of Service | Docker neben fremder Sitzung | mitigate | 02-17b-SUMMARY.md:87-89 (RAM je Start >= 4,2 GB, nur `avs-phpcheck-*`, kein down/prune) | closed |

*Status: open · closed*
*Disposition: mitigate (Umsetzung nötig) · accept (dokumentiertes Risiko) · transfer (an andere Komponente/Dritte)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-02-01 | T-02-04 | Artefakte der Abnahme stammen aus der Wegwerfinstanz mit Testmedien und Job-Passwörtern; Upload nur `logs/`, 7 Tage (`discovery-e2e.yml:784-788`) | Planfreigabe 02-01; Owner einzeln bestätigt 15.11.2026 | 2026-11-15 |

*Akzeptierte Risiken tauchen in späteren Audit-Läufen nicht erneut auf.*

---

## Threat Flags aus den SUMMARY-Dateien

| Flag | Quelle | Zuordnung |
|------|--------|-----------|
| new-route QueueController (drei ExApp-Routen) | 02-03-SUMMARY | T-02-08 bis T-02-11 (informativ) |
| new-route Kopf-Route `/files/{fileId}/head` | 02-10-SUMMARY | T-02-32, T-02-33 (informativ) |
| outbound-probe: Klassifikation setzt Mount im Cron auf, files_external kontaktiert externen Server | 02-12-SUMMARY | T-02-41 (Budget 60 s, 24 h; informativ) |
| outbound-scan: Rescan listet externen Server im Namen eines Nutzers | 02-14-SUMMARY | T-02-51, T-02-52 (informativ) |
| Container-Route `/reconcile/run` (ADMIN, signiert) | 02-20-SUMMARY | unregistered_flag: kein Threat nennt die Route; ADMIN `backend/appinfo/info.xml:121-127` und `AppAPIAuthMiddleware` `main.py:251`, PHP ruft sie nur aus `ExAppService::reconcileNow` mit 120 s Timeout (WARNING, nicht blockierend) |
| übrige Plans (05, 07, 08, 09, 13, 15, 15b, 15c, 16, 16b, 17b, 18, 19) | SUMMARY | "keine neue Oberfläche", Zuordnung zu den eigenen Threats (informativ) |

---

## Escalations (außerhalb des Registers, nicht blockierend)

- **E-02-1 (niedrig), Ausschlussliste aus Leerraum gilt als "keine Regel", BEHOBEN 15.11.2026:** `trim($raw, " \t\n\r")` mit fester Zeichenliste; ein Wert nur aus `\0` oder `\v` fällt jetzt in den JSON-Parse und liest sich als kaputt (fail-closed); Tests 'only a NUL byte' und 'only a vertical tab' im unreadableLists-Provider. Ursprünglicher Befund: `ExclusionService::stored()` liefert für einen gespeicherten Wert, den `trim($raw)` leer macht, eine leere Liste statt "nicht lesbar" (`php/lib/Service/ExclusionService.php:661-662`). `trim` ohne Zeichenliste entfernt auch `\0` und `\v`, ein solcher Wert (nur über `occ config:app:set` durch den Admin setzbar) schaltet die Ausschlüsse still ab statt fail-closed. Bereits in 02-16b-SUMMARY.md:224 benannt, an HEAD unverändert. Vorschlag: `trim($raw, " \t\n\r")` plus Test. Zweite Sicherung `MOUNT_ID` ohne Modifikator `D` (02-16b-SUMMARY.md:225) ist durch die Steuerzeichen-Prüfung :770 abgedeckt.
- **E-02-2 (mittel), PHP-Logs mit Exception-Objekt, BEHOBEN 15.11.2026:** zusammen mit E-01-1 gefixt, alle neun Stellen loggen `'class' => $e::class`. Ursprünglicher Befund: wie E-01-1 in Phase 1; aus Phase 2 betroffen `php/lib/Service/QueueService.php:299,320` und `php/lib/Service/StorageClassifier.php:239`. Bei files_external (SMB/SFTP) tragen Bibliotheksmeldungen Host, Freigabe oder Pfad; Nextcloud schreibt die Meldung bei `['exception' => $e]` ins Log. Gate-Regel 6 fängt das nicht. Vorschlag: `'class' => $e::class` wie an den übrigen Stellen.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-15 | 92 | 92 (davon 1 accept) | 0 | gsd-security-auditor (ASVS 2, block_on high), rückwirkend gegen HEAD dc742f7 |

---

## Sign-Off

- [x] Alle Threats haben eine Disposition (mitigate / accept / transfer)
- [x] Akzeptierte Risiken im Accepted Risks Log (Owner-Bestätigung ausstehend)
- [x] `threats_open: 0` bestätigt
- [x] `status: verified` im Frontmatter gesetzt

**Approval:** verified 2026-11-15. Owner 15.11.2026: AR-02-01 bestätigt; E-02-1 und E-02-2 behoben.
