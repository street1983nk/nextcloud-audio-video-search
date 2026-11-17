---
phase: 03
slug: vorschau-transkripte-in-der-suche
status: verified
threats_open: 0
asvs_level: 2
created: 2026-11-15
---

# Phase 03: Security

> Sicherheitsvertrag je Phase: Threat-Register, akzeptierte Risiken, Audit-Verlauf.
> Register aus den 25 `<threat_model>`-Blöcken der PLAN-Dateien 03-01 bis 03-21 (register_authored_at_plan_time: true).
> Geprüfter Stand: HEAD `e68d407` (Arbeitsbaum zusätzlich mit uncommitteter Änderung an `backend/tests/test_model_download.py`, nicht Teil des Belegs).
> Belege sind Datei:Zeile im Repo. Prozess-Threats (Owner-Tore, Messläufe, Release-Spiegel) sind über die abgelegten Artefakte belegt, nicht über Absichtserklärungen.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| PyPI nach Build/Laufzeit | fremder Code gelangt ins Image (sherpa-onnx, numpy, py3langid) | native Bibliotheken, Lieferkette |
| GitHub-Release / BtbN nach Image und CI | fremde Binärdateien (ffmpeg, Modelle) | Binärdaten, Integrität |
| Hugging Face / k2-fsa nach CI und Scratch | fremde Archivdaten (FLEURS, Modellquellen) | Testaudio, Modelle |
| Container nach Internet (github.com, release-assets.githubusercontent.com) | einziger ausgehender Weg, Redirect-Kette | nur Dateianfrage, keine Inhalte |
| Admin-Ablage nach Engine | Modelldatei aus unbekannter Quelle (Air Gap) | Binärdaten |
| Nutzerdatei nach ffmpeg/ffprobe | beliebige, auch bösartige Bytes | Nutzerinhalte |
| Gateway nach Temp-Datei | Datei des Nutzers, kann sich während der Vorschau ändern | Nutzerinhalte |
| Worker nach Engine-Kind | PCM hinein, Wörter heraus, isolierter Prozess | Transkripttext |
| Modellausgabe nach Index | erfundener oder fremdsprachiger Text | Transkripttext |
| PHP-Warteschlange nach Container | Claim-Vertrag mit neuem Feld origin | Datei-IDs, Herkunft |
| alte state.db / alte Installation nach neuem Code | Schemawechsel v2 nach v3, Update 0.2.0 nach 0.3.0 | Zustandsdaten |
| Nutzer nach Provider / Abspielseite | Suchbegriff, limit, Cursor, fileId, t | Anfragewerte |
| Container nach PHP / HTML | Vorschläge mit fileId, Stufe, Grund, Ausschnitt | Transkripttext, Zustandscodes |
| Admin-Einstellung nach Worker | Höchstdauer aus appconfig_ex | Zahl |
| Testharness nach Instanz | Abnahme darf nichts beschönigen | Testdaten |
| lokales Repo nach GitHub, CI-Artefakte nach Owner | Push, Abnahme auf Belegbasis | Code, Screenshots |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (Beleg) | Status |
|-----------|----------|-----------|-------------|--------------------|--------|
| T-03-SC | Tampering | sherpa-onnx, numpy, py3langid (03-01, 03-10) | mitigate | Exakte Pins `backend/pyproject.toml:26-35`; Wheel-sha256 gegen Owner-Freigabe `backend/tests/test_lock_wheels.py:18-19,84-98,110-117` (mit Negativfällen :121,:138,:160); uv.lock hält Hashes | closed |
| T-03-01 | Repudiation | T12-Satz 2, Einstellungstext | mitigate | T12: `backend/tests/test_preview_worker.py:847-852` (disk_full nach DISK_FULL_RETRY_SECONDS); Höchstdauer Satz 2: `backend/tests/test_preview_settings.py:159,235` | closed |
| T-03-02 | Information Disclosure | A13-Text | accept | siehe AR-03-01 | closed |
| T-03-03 | Tampering | fetch_speech.py | mitigate | feste Revision `ci/media/fetch_speech.py:31`; sha256 je Mitglied :59,:73,:83, Prüfung :135-137; nur `extractfile` eines benannten Mitglieds :124-131, kein extractall | closed |
| T-03-04 | Elevation of Privilege | Tar-Pfad `../` | mitigate | Namensprüfung `ci/media/fetch_speech.py:122-123`, exakter Mitgliedsname :127, Ausgabe unter festem Namen :185; Test `backend/tests/test_fetch_speech.py:118-129` | closed |
| T-03-05 | Information Disclosure | lokale Pfade in Skripten | mitigate | Pfad-Gate `backend/tests/test_research_scripts.py:57` mit Positivkontrollen :62,:80,:85 | closed |
| T-03-06 | Information Disclosure | Audiodaten im Repo | mitigate | `git ls-files` ohne .wav/.flac/.mp3/.ogg/.opus/.m4a/.mp4/.webm/.onnx (Prüfung 2026-11-15, leer); Laden nur per `ci/media/fetch_speech.py` | closed |
| T-03-07 | Tampering | migrate_v2_to_v3 | mitigate | eine Transaktion `backend/src/audio_video_search_backend/store/migrate.py:167-178`; Rollback-Test `backend/tests/test_store_migration_v3.py:342`; Schemavergleich :285 | closed |
| T-03-08 | Tampering | IntakeItem.origin | mitigate | `store/repo.py:58` ORIGINS, `:742-743` ValueError ohne Wert; CHECK `store/schema.sql:97,222`; Test `backend/tests/test_preview_seed.py:94` | closed |
| T-03-09 | Information Disclosure | Job für Probe / nicht aktiven Verweis | mitigate | Saat nur aus `file_ref` mit `state='active' AND stage='keyed'` `store/repo.py:374-378`; Test `backend/tests/test_preview_seed.py:160-164` (Probe aus sample_ref erzeugt keinen Job) | closed |
| T-03-10 | Denial of Service | Doppeljobs je Kopie | mitigate | `media_id INTEGER PRIMARY KEY` `store/schema.sql:218`; `ON CONFLICT (media_id)` `store/repo.py:378`; Test `backend/tests/test_preview_seed.py:169` | closed |
| T-03-11 | Tampering | avs_queue.origin | mitigate | `php/lib/Db/QueueMapper.php:70,121-122` (InvalidArgumentException); `php/lib/Service/QueueService.php:173-175` describeRow verwirft | closed |
| T-03-12 | Denial of Service | Claim-Band verworfen wegen fremdem Feld | mitigate | Gate gleiche Liste `backend/tests/test_php_gates.py:1058,1085-1108`; ClaimItem kennt origin `backend/src/audio_video_search_backend/nc_queue.py:46,63` | closed |
| T-03-13 | Elevation of Privilege | crawl drängt sich vor | accept | siehe AR-03-02 | closed |
| T-03-14 | Information Disclosure | concat/HLS liest lokale Dateien | mitigate | `-protocol_whitelist file`, `-format_whitelist DEMUXERS` in `media/probe.py:35,176-179` und `media/decode.py:80-83`; Test `backend/tests/test_media_hardening.py:45` | closed |
| T-03-15 | Denial of Service | Decoder-Endlosschleife, riesige Ausgabe | mitigate | Wandzeit mit Kill `media/probe.py:73-82`; `-threads 1` `media/decode.py:78`, `-fs` :105; Tests `test_media_hardening.py:226,247,259` | closed |
| T-03-16 | Tampering | ffmpeg-Binärdatei | mitigate | Monatsletzter Tag `autobuild-2026-10-31` `backend/Dockerfile:69`, sha256 je Architektur :71-72,:80, Abbruch bei `--enable-gpl` :92-93 | closed |
| T-03-17 | Information Disclosure | ffmpeg-stderr in Logs | mitigate | stderr nur für Grundcode gelesen `media/probe.py:88`, keine weitere Verwendung in `backend/src`; HIDDEN-Test `test_media_hardening.py:29,271` | closed |
| T-03-18 | Elevation of Privilege | Shell-Injektion über Dateinamen | mitigate | Argumentliste `media/probe.py:74` (einziger Unterprozess im Paket, kein shell=True); Temp-Name `secrets.token_hex(16)` `nc.py:587` | closed |
| T-03-19 | Tampering | Halluzinationen im Index | mitigate | `engine/parakeet.py:255,263` (Wörter nur bei KEEP); Schwellen `engine/catch.py:45-63,86-103`; `worker/preview.py:202` | closed |
| T-03-20 | Elevation of Privilege | Abschaltweg für VAD/Regel | mitigate | `backend/tests/test_vad_gate.py:162` mit Positivkontrollen :198-272; Schwellen als `Final`-Konstanten `engine/catch.py:45-63` | closed |
| T-03-21 | Repudiation | stille Schwellenänderung | mitigate | Fingerabdruck `backend/tests/test_engine_constants.py:174-175`, Gegenprobe :188 | closed |
| T-03-22 | Tampering | Modelldatei | mitigate | sha256 und Länge fest `models/catalog.py:45-73`; `os.replace` erst nach Treffer `models/procure.py:192-195`; Admin-Ablage gleiche Prüfung `procure.py:125-147` | closed |
| T-03-23 | Spoofing | Weiterleitung auf fremden Host | mitigate | eigene Redirect-Verfolgung `nc.py:762-797` (nur https + Allowlist, vor nächstem Request); Tests `test_model_download.py:90,100,108,118` | closed |
| T-03-24 | Information Disclosure | Anfrage-Header | mitigate | eigener Client ohne AppAPI-Header, neutraler UA `nc.py:743-759`, Cookies je Hop geleert :786; Tests `test_model_download.py:241,261,271` | closed |
| T-03-25 | Denial of Service | Platte voll durch Download | mitigate | Platzprüfung `models/procure.py:163-168` mit `nc.DISK_RESERVE_BYTES` `nc.py:415`; Abbruch über erwarteter Länge `nc.py:800-809` | closed |
| T-03-26 | Denial of Service | riesiger offset | mitigate | `api/search.py:42,46,59-60` (`le=MAX_OFFSET`, `le=50`, MAX_CANDIDATES) | closed |
| T-03-27 | Information Disclosure | Treffer aus nicht lesbarer Datei | transfer | an PHP übergeben und dort belegt: `php/lib/Search/Provider.php:265-279` (isExcludedFile, readableFile unter actAs je fileId); Container nur aktive Verweise `store/repo.py:1683-1691` | closed |
| T-03-28 | Information Disclosure | Suchbegriff im Log | mitigate | `api/search.py:183` loggt nur hits, limit, offset | closed |
| T-03-29 | Tampering | Stück-Commit | mitigate | `store/repo.py:1743` commit_chunk in `_transaction` :951-953; Rollback-Test `test_preview_store.py:596`; Epochen-Tests :395,:413,:432,:447 | closed |
| T-03-30 | Information Disclosure | preview_view für nicht aktiven Verweis | mitigate | SQL `store/repo.py:637-642` (`f.state = 'active'`), :1922-1930 None wie unbekannt; Test `test_preview_store.py:959` | closed |
| T-03-31 | Information Disclosure | occ-Zähler | mitigate | feste Namensliste `store/coverage.py:65`, `php/lib/Service/ExAppService.php:91,509` | closed |
| T-03-32 | Denial of Service | Job ohne Leser blockiert | mitigate | Claim nur mit `reader_uid IS NOT NULL` `store/repo.py:588,596,625`; Test `test_preview_store.py:198,248` | closed |
| T-03-33 | Denial of Service | Modell frisst RAM, hängt | mitigate | Speicherwächter vor Start `engine/child.py:188`; Kill der Prozessgruppe :79-93,:224,:257; Kindwechsel `MAX_CHUNKS_PER_CHILD` :57,:234 | closed |
| T-03-34 | Elevation of Privilege | Kind erbt Geheimnisse | mitigate | spawn `engine/child.py:47`; Geheimnisse geleert `SECRET_ENV` :61,:124 | closed |
| T-03-35 | Information Disclosure | Erkennungstext in Logs | mitigate | einzige Logzeilen `engine/child.py:189,206` (Code, Dauer) | closed |
| T-03-36 | Tampering | ClaimItem.origin | mitigate | `Literal["event","crawl"]` `nc_queue.py:46`, strict/forbid :52; Gate `test_php_gates.py:1085-1108` | closed |
| T-03-37 | Denial of Service | Höchstdauer 0 oder riesig | mitigate | `settings.py:86-100` (Default bei Nicht-Zahl/0, Deckel) | closed |
| T-03-38 | Repudiation | Wegfall der Größengrenze | accept | siehe AR-03-03 | closed |
| T-03-39 | Information Disclosure | Treffer aus nicht lesbarer/ausgeschlossener Datei | mitigate | `php/lib/Search/Provider.php:266-279` je fileId; Cache `$checked` nur lokal in `entries()` :227 | closed |
| T-03-40 | Denial of Service | großer Cursor, viele Runden | mitigate | `Provider.php:75,78,81,89` (2,5 s, 25, 1200, 3), Anwendung :180,:199-202,:230-231,:254 | closed |
| T-03-41 | Tampering | Stufe aus Container | mitigate | `php/lib/Service/ExAppService.php:170,1060-1080` (Typprüfung verwirft, Unbekanntes wird preview) | closed |
| T-03-42 | Information Disclosure | Ausschnitt im HTML | mitigate | `ExAppService.php:1096-1104` plainText; `Provider.php:322,365-382` shorten, kein Markup | closed |
| T-03-43 | Tampering | Datei während der Vorschau geändert | mitigate | `worker/preview.py:356-360` sha256 gegen Inhalts-Schlüssel, sonst STALE ohne Wort | closed |
| T-03-44 | Information Disclosure | Temp-Datei bleibt liegen | mitigate | Zufallsname ohne Endung `nc.py:587`, Löschen im finally :597-599; `_clear` beim Start `worker/preview.py:253-261,294-296`; Tests `test_fetch_keep.py:80,106,124`, `test_preview_worker.py:1110` | closed |
| T-03-45 | Denial of Service | Platte voll, endlose Neuversuche | mitigate | `worker/preview.py:348-349,363-375` (300 s `worker/capture.py:88`); engine_failed nach `MAX_ENGINE_ATTEMPTS = 3` `preview.py:103,411-412` | closed |
| T-03-46 | Denial of Service | lange Datei blockiert neue Uploads | mitigate | `worker/preview.py:516-517`; `store/repo.py:1881,1893`; Test `test_preview_worker.py:560` | closed |
| T-03-47 | Information Disclosure | Wörter oder Pfade in Logs | mitigate | Logzeilen `worker/preview.py:299,315,329,443,573-580` nur ids/Codes/Zähler; HIDDEN-Test `test_preview_worker.py:1171-1200` (Restpunkt siehe Escalations E-1) | closed |
| T-03-48 | Information Disclosure | Grund als Probe auf fremde Datei | mitigate | `api/excerpt.py:34,54,69` (`{"known": false}` sonst); Tests `test_excerpt_states.py:438,452,474,486` | closed |
| T-03-49 | Information Disclosure | Dateidauer, Codec im Grund | mitigate | `api/excerpt.py:69,79` nur Code aus PREVIEW_REASONS und `max_duration_hours()` | closed |
| T-03-50 | Information Disclosure | Dateinamen im occ-Status | mitigate | `php/lib/Command/StatusCommand.php:85` über `ExAppService::countsOf(..., PREVIEW_NAMES)` `ExAppService.php:509` | closed |
| T-03-51 | Repudiation | Text T6/T7 verspricht Neustart | mitigate | `backend/tests/test_replaced_file.py:253,261,269,289` | closed |
| T-03-52 | Denial of Service | Rückstellen vieler Jobs beim Anheben | accept | siehe AR-03-04 | closed |
| T-03-53 | Tampering | fremdsprachiger Text im Index | mitigate | Korpustest TR/ES ohne Wort `backend/tests/test_preview_corpus.py:182-183,333-335` mit Positivkontrolle :321-326 | closed |
| T-03-54 | Information Disclosure | Grund verrät fremde Datei | mitigate | Ausschluss vor Container-Frage `php/lib/Controller/PageController.php:313-326`; Excerpt nur nach readableFile :127-150,:230-232; Tests `php/tests/Unit/PlayControllerTest.php:712,732,775,792` | closed |
| T-03-55 | Tampering / XSS | reason, excerpt im HTML | mitigate | `PageController.php:86,360` REASON_STATES; `php/templates/play.php` nur `p()` (kein print_unescaped), Typprüfung `ExAppService.php:262-311` | closed |
| T-03-56 | Information Disclosure | Dateidauer im Text | mitigate | `PageController.php:365-370` nur limitHours; Bereich 1 bis 24 `ExAppService.php:311` | closed |
| T-03-57 | Repudiation | Paritätstest prüft nichts | mitigate | Selbsttest `ci/discovery/parity.sh:371-404` (extra-id, missing-id), Abbruch :431-433 | closed |
| T-03-58 | Information Disclosure | Rechteleck im echten Pfad | mitigate | Wahrheit per WebDAV `ci/discovery/parity.sh:99-113`, sha256 `ci/discovery/truth.sh:146,258`; Samba-Zweig per smbclient mit eigenem Selbsttest `parity.sh:143-219` (Commit 40a769f, Owner-Freigabe D-03-25) | closed |
| T-03-59 | Tampering | Modelle in CI | mitigate | Cache ohne `*.verified.json` `.github/workflows/discovery-e2e.yml:245-250,307`, `deploy-harp.yml:200-205,263`; Prüfung durch procure `models/procure.py:125-147` | closed |
| T-03-60 | Repudiation | Kontrastmessung misst falsch | mitigate | `ci/playwright/preview.spec.ts:336,350,557` | closed |
| T-03-61 | Information Disclosure | Leck über Abspielseite | mitigate | P11 `ci/playwright/preview.spec.ts:732`; Logprobe mit Positivkontrolle `.github/workflows/deploy-harp.yml:498-522` | closed |
| T-03-62 | Repudiation | stilles Auslassen von P13 | mitigate | `ci/playwright/preview.spec.ts:783` test.fixme; Unit-Beleg 03-18-SUMMARY.md:107, `test_preview_worker.py:847-852` | closed |
| T-03-63 | Tampering | Update 0.2.0 auf 0.3.0 | mitigate | `.github/workflows/deploy-harp.yml:781,829-839` (prev aus echtem Commit), Inode :999,:1121-1123, Nachher :1158-1186 | closed |
| T-03-64 | Repudiation | Upgrade-Test prüft nichts | mitigate | Positivkontrolle `deploy-harp.yml:1004-1027` (schema 2, ohne preview_job, ohne origin) | closed |
| T-03-65 | Information Disclosure | falsche Datenschutzaussage in Doku | mitigate | `docs/install.md:84`, `install.en.md:84`, `install.fr.md:84` gleich `models/catalog.py:83` | closed |
| T-03-66 | Spoofing | Owner-Freigabe | mitigate | Freigabedatei `approvals/push-4c972ea81f569aafcc22e6ca088946f295f7155f` mit Inhalt `push-phase-03 4c972ea...` (geprüft 2026-11-15) | closed |
| T-03-67 | Information Disclosure | Rechteleck in search-parity | mitigate | `ci/discovery/parity.sh:431-451` (PHASE FAIL, Abbruch); Kontrollbein zeigt Leck (03-20-SUMMARY.md:71) | closed |
| T-03-68 | Tampering | main, ghcr | mitigate | `approvals/main-before-*`/`main-after-*` und `ghcr-before-*`/`ghcr-after-*` für 4c972ea per `cmp` identisch (geprüft 2026-11-15) | closed |
| T-03-69 | Repudiation | aufgeweichte Erwartung | mitigate | `git log` truth.sh/parity.sh: keine Änderung in 03-20; letzte Änderung 40a769f mit Beleg (Lauf 43633120030) und Owner-Freigabe im Commit-Text | closed |
| T-03-70 | Repudiation | Abnahme ohne Bild | mitigate | 03-21-SUMMARY.md:50,60 (P13 ohne Bild als Abweichung 4 benannt, vom Owner akzeptiert) | closed |
| T-03-71 | Information Disclosure | Screenshots mit Testinhalten | accept | siehe AR-03-05 | closed |
| T-03-72 | Tampering / XSS | Template-Ausgabe | mitigate | `php/templates/play.php:36-49` Typprüfung, :141-157 feste Tabelle mit `$l->t`/`$l->n`, alle Ausgaben über `p()` (:164-222) | closed |
| T-03-73 | Information Disclosure | A5-Zweig verändert | mitigate | `backend/tests/test_ui_assets.py:234`; `PlayControllerTest.php:732` Byte-Vergleich | closed |
| T-03-74 | Tampering | Lieferkette beim Spiegeln | mitigate | Festwerte `models/catalog.py:45-73`, jeder Download gegen sha256+Länge `models/procure.py:192`; Digest-Tabelle vor Veröffentlichung 03-07b-SUMMARY.md:49-61 | closed |
| T-03-75 | Tampering | Release-Manipulation | mitigate | `models/procure.py:188-195` (WRONG_DIGEST, os.replace erst nach Treffer); Tag-Trigger nur `v[0-9]+.[0-9]+.[0-9]+` `.github/workflows/release.yml:22-25` | closed |
| T-03-76 | Spoofing | Host-Allowlist | mitigate | `models/catalog.py:83` genau zwei Hosts; Tests `test_model_download.py:90,100,108,118`, `test_models.py:100` | closed |
| T-03-77 | Information Disclosure | huggingface-hub, signierte URLs | mitigate | `backend/Dockerfile:144-145` im runtime-Stage; Test `backend/tests/test_dockerfile.py:117-140`; Logs ohne URL `nc.py:851,857` | closed |
| T-03-78 | Repudiation | Lizenzpflicht CC-BY-4.0 / MIT | mitigate | `README.md:59`, `README.en.md:59`, `README.fr.md:59` (NVIDIA, CC-BY-4.0, MIT); Release-Text laut 03-07b-SUMMARY.md:49 (nicht live geprüft, keine GitHub-API laut Auftrag) | closed |
| T-03-79 | Denial of Service | Release gelöscht / GitHub nicht erreichbar | accept | siehe AR-03-06 | closed |
| T-03-80 | Tampering | Wortsalat aus zweitem Durchgang | mitigate | `engine/catch.py:63,99-100`; Tests `test_catch_rule.py:53-54,61`. Abweichung vom Plantext (keine Sprachbedingung) per Owner-Entscheid Option A 14.11.2026, `catch.py:23-33`, 03-13b-SUMMARY.md:86-94 | closed |
| T-03-81 | Tampering | Schwelle zur Laufzeit verschiebbar | mitigate | `Final`-Konstante `engine/catch.py:63`; Wert/Fingerabdruck `test_engine_constants.py:174-189`; `test_vad_gate.py:162` | closed |
| T-03-82 | Information Disclosure | Korpus/Modelle/Messergebnisse im Repo | mitigate | `git ls-files` ohne .wav/.onnx und ohne FLEURS-JSON (nur l10n/Config-JSON), geprüft 2026-11-15 | closed |
| T-03-83 | Denial of Service | Messung erschöpft RAM | mitigate | Prozess-Mitigation, belegt durch RAM-Tabelle je Lauf 03-13b-SUMMARY.md:49-56 (alle > 4 GB, seriell) | closed |
| T-03-84 | Repudiation | Schwelle geraten statt gemessen | mitigate | `scripts/research/phase3/eval23.py:47,163` (MIN_GAP 0,02); Owner-Checkpoint 03-13b-SUMMARY.md:86-87 | closed |
| T-03-85 | Information Disclosure | Abspielseite für nicht aktiven Verweis | mitigate | `ci/discovery/playpage.sh:22-23,63,93-105,145` (Byte-Vergleich, UI-SPEC-Texte, kein Clip-Wort, kein T5) | closed |
| T-03-86 | Repudiation | Probe prüft anderen Fall | mitigate | `ci/discovery/playpage.sh:110-162` (ref_state aus occ und state.db, INVALID nie PASS) | closed |
| T-03-87 | Repudiation | Vergleich kann nicht scheitern | mitigate | Offline-Selbsttest `ci/discovery/playpage.sh:205-248`; Live-Kontrolle :409; Gate `test_discovery_workflow.py:1433,1455` | closed |
| T-03-88 | Tampering | Probe verändert Instanz | mitigate | Verbotsliste `backend/tests/test_discovery_workflow.py:1449,1463-1469`; Kopf `playpage.sh:37` | closed |

*Status: open · closed*
*Disposition: mitigate (Umsetzung nötig) · accept (dokumentiertes Risiko) · transfer (an andere Komponente/Dritte)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-03-01 | T-03-02 | A13-Text (disk_full) nennt nur den Instanzzustand, keinen Dateiinhalt, keine Größe | Owner (Plan 03-01, Planfreigabe) | 2026-11-14 |
| AR-03-02 | T-03-13 | Herkunft event/crawl steuert nur die Reihenfolge (`store/schema.sql:238-239`), keine Rechte | Owner (Plan 03-04) | 2026-11-14 |
| AR-03-03 | T-03-38 | Größengrenze entfällt zugunsten der Höchstdauer; `MAX_CAPTURE_BYTES` 64 GiB bleibt (`worker/capture.py:90`), Platzprüfung je Download (`worker/preview.py:363-368`) | Owner (Plan 03-11) | 2026-11-14 |
| AR-03-04 | T-03-52 | Anheben der Höchstdauer stellt Jobs mit einem UPDATE zurück (`worker/preview.py:320-325`), Jobs laufen seriell | Owner (Plan 03-15) | 2026-11-14 |
| AR-03-05 | T-03-71 | Screenshots zeigen nur synthetische Testnutzer und FLEURS-Clips; Artefakte bleiben in CI und Scratchpad | Owner (Plan 03-21) | 2026-11-15 |
| AR-03-06 | T-03-79 | Release gelöscht oder GitHub nicht erreichbar: UNAVAILABLE/MODELS_FAILED wie bisher, Air-Gap-Ablage bleibt; keine Hugging-Face-Ausweichquelle, weil deren Hosts nicht fest sind | Owner (Plan 03-07b) | 2026-11-14 |

*Akzeptierte Risiken tauchen in späteren Audit-Läufen nicht erneut auf.*

---

## Threat Flags aus den SUMMARY-Dateien

| Flag | Quelle | Zuordnung |
|------|--------|-----------|
| `fetch_model_asset` als einzige neue ausgehende Verbindung | 03-07-SUMMARY | T-03-23, T-03-24 (informativ) |
| ffmpeg-Download zur Build-/CI-Zeit | 03-05-SUMMARY | T-03-16 (informativ) |
| `actions/cache` (SHA-gepinnt) für Modelle in CI | 03-10/03-17/03-18-SUMMARY | T-03-59 (informativ) |
| `actions/cache` für Sprach-Clips (`avs-speech`) | 03-17/03-18-SUMMARY | unregistered_flag: kein Threat deckt die erneute Prüfung gecachter Test-Clips ab; nur Testdaten, kein Produktpfad (WARNING, nicht blockierend) |
| Lesen der eigenen appconfig_ex über nc_py_api | 03-15-SUMMARY | unregistered_flag: neuer interner Weg Container nach Nextcloud, ohne Threat-ID; Wert wird geklemmt (T-03-37), Fehler nur als error_type geloggt (`worker/preview.py:312-316`) (WARNING, nicht blockierend) |
| Login-POST der Testnutzer in playpage.sh | 03-18b-SUMMARY | T-03-88 (informativ) |

---

## Escalations (außerhalb des Registers, nicht blockierend)

- **E-1 (T-03-47 Rest), BEHOBEN 15.11.2026:** `logs.py` schreibt bei `exc_info` nur noch `exc_type` und die Traceback-Frames (Datei, Zeile, Funktion, Quellzeile), nie den Exception-Text; auch verkettete Ursachen (`__cause__`) bleiben draußen, weil nie ein Wert formatiert wird. Tests: `test_logs.py` (HIDDEN-Marke im Exception-Text und in der Ursache erscheint nicht in der Zeile, Frames bleiben). Gilt global für jeden Logger des Backends, nicht nur `worker/preview.py:569`.
- **E-2 (Air-Gap-Ablage), BEHOBEN 15.11.2026:** Das Urteil über eine Modelldatei lebt nur noch im Prozessspeicher (`models/procure.py`, `_VERIFIED`); auf dem Volume wird keine `*.verified.json` mehr geschrieben oder gelesen, jeder Prozessstart hasht neu (Parakeet+Silero ca. 0,67 GB beim Start). Eine untergeschobene `*.verified.json` ist wirkungslos; Positivkontrolle `test_models.py::test_a_verdict_file_on_the_volume_is_never_trusted`. Die CI-Workflows löschten solche Dateien schon vorher aus dem Cache-Volume (Zeilen bleiben als Aufräumer für Altbestände).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-15 | 89 | 89 (davon 6 accept, 1 transfer) | 0 | gsd-security-auditor (ASVS 2, block_on high) |
| 2026-11-15 (Nachtrag) | 89 | 89 | 0 | Owner bestätigt AR-03-01..06; E-1 und E-2 behoben (logs.py Frames-only, procure.py Prozess-Cache), Suite 1925 passed |

---

## Sign-Off

- [x] Alle Threats haben eine Disposition (mitigate / accept / transfer)
- [x] Akzeptierte Risiken im Accepted Risks Log
- [x] `threats_open: 0` bestätigt
- [x] `status: verified` im Frontmatter gesetzt

**Approval:** verified 2026-11-15 (Auditor). Owner 15.11.2026: AR-03-01 bis AR-03-06 einzeln vorgelegt und ausdrücklich bestätigt; Escalations E-1 und E-2 auf Owner-Entscheid "Beide fixen" behoben (siehe oben); die zwei unregistered_flags (avs-speech-Cache nur Testdaten, appconfig_ex-Lesen über T-03-37 geklemmt) zur Kenntnis genommen, keine Änderung nötig.
