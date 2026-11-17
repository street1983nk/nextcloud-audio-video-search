---
phase: 04
slug: suchqualit-t-und-export
status: open
threats_open: 2
asvs_level: 2
created: 2026-11-17
---

# Phase 04: Security

> Sicherheitsvertrag je Phase: Threat-Register, akzeptierte Risiken, Audit-Verlauf.
> Register aus den 17 `<threat_model>`-Blöcken der PLAN-Dateien 04-01 bis 04-17 (register_authored_at_plan_time: true).
> Geprüfter Stand: HEAD `e15a891` lokal; `origin/phase-04` = `f7bb9da` (CI-Belege 04-15-SUMMARY.md, 04-16-SUMMARY.md). Arbeitsbaum zusätzlich mit uncommitteter Änderung an `backend/tests/test_model_download.py` und `.planning/debug/`, nicht Teil des Belegs.
> Belege sind Datei:Zeile im Repo plus der Test, der die Mitigation beweist. Prozess-Threats (Push-Tor, CI-Läufe, Abnahme) sind über abgelegte Artefakte und Lauf-URLs belegt, nicht über Absichtserklärungen.
> Register-Hinweise: T-04-51 und T-04-52 stehen in 04-14 und 04-17 (zusammengeführt, 04-17 ist die erweiterte Fassung). T-04-58 war doppelt vergeben (04-14 Testclip, 04-16 Screenshots); seit dem Nachtrag 17.11.2026 heißt der Fall aus 04-16 im Register `T-04-61` (E-2 aufgelöst, 04-16-PLAN.md bleibt als Planstand unverändert).
> Nachtrag 17.11.2026 (Owner-Entscheide gleichen Tags): T-04-25, T-04-50 und E-1 nach Findling-Muster geschlossen (Commit `c35b5e4`), lokal belegt, CI-Beleg mit Push 5 ausstehend; T-04-SC per Gate geschlossen (Commit `b000e44`); AR-04-01, -02, -04, -05 vom Owner bestätigt.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Nutzer nach Suchprovider | Suchbegriff mit Zahlen, Satzzeichen, Abfragesyntax; Filter Person/Datum | Anfragewerte |
| Provider nach Datenbank (oc_share) | Personenfilter fragt Freigabezeilen | uid, gid, fileIds |
| PHP nach Container (`exAppRequest`) | Export- und Meta-Anfrage je fileId | fileId, Format |
| Browser nach AppAPI/HaRP nach Container (`/exapps/<app>/<route>`, `/index.php/apps/app_api/proxy/<app>/<route>`) | direkter Weg an PHP vorbei, nur durch `access_level` der Route begrenzt; seit 17.11.2026 nur ADMIN-Routen deklariert, die Routen mit Nutzerdaten gar nicht (Proxy antwortet 404) | nur Admin-Diagnose (`/status`, `/workstock`, `/coverage`, `/sample`, `/sample/remove`, `/reconcile/run`) |
| Container nach PHP | Exportkörper, Sprache, Teilstand | Transkripttext |
| PHP nach Browser | Download, Spur, Fehlerseiten, Abspielseite | Dateiname im Header, VTT/SRT/TXT |
| PHP nach Dateisystem des Nutzers | Nebendatei neben dem Medium | Dateiname, VTT |
| Freigabe-Attribut nach Export | Download-Sperre der Freigabe, auch unlesbar | Urteil ALLOWED/BLOCKED/UNKNOWN |
| PyPI nach dev-Umgebung | webvtt-py, srt (nur Prüfer) | Lieferkette |
| Hugging Face nach CI | FLEURS-Testclips | Testaudio |
| lokales Repo nach GitHub | Push auf phase-04, CI-Artefakte | Code, Screenshots, Downloads |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (Beleg) | Status |
|-----------|----------|-----------|-------------|--------------------|--------|
| T-04-01 | Denial of Service | `SearchIndex._word_query` (04-01) | mitigate | `MAX_TERM_CHARS = 200` `backend/src/audio_video_search_backend/index/publish.py:69`, Kürzung :372,:411; Test `backend/tests/test_index_publish.py:111-112`. Varianten je Zahl begrenzt: `backend/tests/test_numbers.py:207-221` (`<= 24`, alle Werte 0 bis 100, Hunderter, Tausender, Jahre 1100 bis 2099). Abweichung vom Plantext: `MAX_SPAN_WORDS` ist 7 statt 5 `index/numbers.py:42`, begründet in 04-06-SUMMARY.md:112 (Jahreszahlen FR), weiterhin feste Grenze, Test `test_numbers.py:267-274` | closed |
| T-04-02 | Information Disclosure | Logging publish.py/numbers.py | mitigate | `index/numbers.py` ohne Logger (Kommentar :29 "Nothing here logs a token or a word"); `publish.py` loggt nur Zähler/IDs :190,:244,:287,:514 | closed |
| T-04-03 | Tampering | Abfragesyntax im Begriff | mitigate | `publish.py:376-383` (ValueError des Parsers führt in den Wortweg), `_parse` fängt ValueError :290-294, Wortweg nur aus alphanumerischen Wörtern `_WORD` :78; Test `backend/tests/test_search_numbers.py:78-79` ("12:30"). Gegenprobe dieses Audits (Scratchpad, nicht im Repo): `"open`, `(x)`, `Markt "`, `AND OR (`, `Markt)`, `zwölf (`, `"12 Uhr` werfen nicht; Positivkontrolle `"Markt` und `(Markt)` finden {9,10,11}; 9 passed | closed |
| T-04-04 | Information Disclosure | `SearchFilters::sharedSubset` als Orakel | mitigate | Erst readableFile und Ausschluss `php/lib/Search/Provider.php:315-331`, dann nur bestätigte IDs an `sharedSubset` :333-346, Ergebnis nur als Ausschluss :350; DB-Fehler = leere Menge `php/lib/Service/SearchFilters.php:140-143`. Tests `php/tests/Unit/ProviderTest.php:932` (ausgeschlossen/unlesbar nie in der Abfrage), :898, `SearchFiltersTest.php:420` | closed |
| T-04-05 | Tampering | SQL über person/uid | mitigate | Nur `createNamedParameter` mit `PARAM_INT_ARRAY`/`PARAM_INT` `SearchFilters.php:132,159-168`; Tests `SearchFiltersTest.php:399,409` (Parameterbindung) | closed |
| T-04-06 | Denial of Service | Runden mit Filter | mitigate | `MAX_ROUNDS_FILTERED = 6` `Provider.php:108`, Anwendung :269; `BUDGET_SECONDS` :85,:272,:302; eine Abfrage je Runde :341; `CHUNK = 1000` `SearchFilters.php:49,125`. Tests `ProviderTest.php:968,909,919`, `SearchFiltersTest.php:385-391` (1001 IDs = Bänder 1000+1) | closed |
| T-04-07 | Information Disclosure | Logs Personenfilter | mitigate | Warnung nur mit `class` `SearchFilters.php:141`; Test `SearchFiltersTest.php:420`; Gate-Regel 6 `backend/tests/test_php_gates.py:324` mit Selbsttest :482 | closed |
| T-04-08 | Repudiation | Kataloge, README, Store-Text | mitigate | EXP-04-Gate `backend/tests/test_public_texts.py:219-243` mit Selbsttest :246-266; läuft in `.github/workflows/python.yml:161` bei jedem Push (:7-9) | closed |
| T-04-09 | Tampering | VTT-NOTE aus Katalogtexten | mitigate | `test_public_texts.py:199-203,239-241` (kein `-->`, `\n`, `\r` in T15/T35, alle Kataloge); `backend/tests/test_vtt_note_pattern.py:88,131,197`; zur Laufzeit zusätzlich `noteSafe` `php/lib/Controller/ExportController.php:436-449`, Test `ExportControllerTest.php:623` | closed |
| T-04-10 | Tampering | Icon-Pfade aus Fremdquelle | accept | siehe AR-04-01 | closed |
| T-04-SC | Tampering | uv add webvtt-py, srt (04-04) | mitigate | Owner-Freigabe 16.11.2026 04-04-SUMMARY.md:21,38; exakte Pins nur in `[dependency-groups] dev` `backend/pyproject.toml:38-48`; Hashes `backend/uv.lock:695-698,870-873`; Image `--no-dev` `backend/Dockerfile:20,22`. Gate seit 17.11.2026 (Commit `b000e44`): `uv_installs`/`dev_install_findings` `backend/tests/test_dockerfile.py:235,241`, jedes `uv sync`/`uv export` des Builds (Fortsetzungszeilen verbunden) trägt `--no-dev` und keins von `--dev`, `--all-groups`, `--only-dev`, `--group`, `--only-group`; echter Stand `test_every_uv_sync_of_the_build_leaves_the_dev_group_out` :254 (genau zwei Aufrufe, 0 Befunde). Gegenprobe :259: ohne `--no-dev` (auch über Fortsetzungszeile), `uv export` ohne `--no-dev`, `--group dev` und ein Dockerfile ohne `uv sync` feuern je mit genau einem Befund. Dazu `test_the_checkers_are_pinned_in_the_dev_group_only` :282 (webvtt-py und srt nur in `dev`, nicht in `[project] dependencies`) | closed |
| T-04-11 | Repudiation | Prüfer, die nie anschlagen | mitigate | Positiv-/Negativkontrolle je Prüfer `backend/tests/test_subtitle_checkers.py:90,100,108,118,137,150`; Lücken als `xfail(strict=True, raises=CheckerMissedIt)` :123,:165,:171,:177; fehlendes ffmpeg unter `CI=true` scheitert (04-04-SUMMARY.md:47) | closed |
| T-04-12 | Tampering | `migrate_v3_to_v4` | mitigate | `BEGIN IMMEDIATE`/`ROLLBACK` `backend/src/audio_video_search_backend/store/migrate.py:204-213`; Tests `backend/tests/test_store_migration_v4.py:390` (Fehler lässt v3), :414, :436 (neuere Version abgelehnt) | closed |
| T-04-13 | Tampering | `media.language` im Dateinamen | mitigate | CHECK `store/schema.sql:56`; `FILE_LANGUAGES` `store/repo.py:68`, `set_file_language` wirft :1963-1964; Tests `test_store_migration_v4.py:452,578`; PHP prüft erneut `php/lib/Service/ExAppService.php:97,448-450`, Test `ExAppServiceTest.php` (language `und` = null) | closed |
| T-04-14 | Denial of Service | `file_language.detect` auf 12-h-Text | mitigate | `LANGUAGE_SAMPLE_WORDS = 3000` `file_language.py:25,40`, `functools.cache` :28; Tests `backend/tests/test_file_language.py:70,86,93` | closed |
| T-04-15 | Information Disclosure | Logs Sprache | mitigate | nur `media_id` `store/repo.py:1968-1969`; `file_language.py` ohne Logzeile; Export ohne Logger (T-04-28) | closed |
| T-04-16 | Denial of Service | `Query.regex_query` (ReDoS) | mitigate | `re.escape` + Kappung + nur `.*` `index/publish.py:91-93`; nur `[a-z]+`-Stämme :88,:311; Mindestlänge `PREFIX_MIN_CHARS = 5` :84,:309, keine Ziffern :309. Tests `backend/tests/test_compounds.py:112,119,125`. Messskript endet mit Code 1 über Schwelle `scripts/research/phase4/measure_prefix.py:150,204`; gemessen p95 1,136 ms gegen 250 ms (04-06-SUMMARY.md, Threat Flags) | closed |
| T-04-17 | Information Disclosure | Präfix-Beifang | accept | siehe AR-04-02 | closed |
| T-04-18 | Information Disclosure | Messskript, Wortliste | mitigate | Index nur im `tempfile.TemporaryDirectory` `measure_prefix.py:157-158`, Wortliste nur als Argument `--wordlist` :149; `git ls-files` ohne Wortlistendatei (geprüft 2026-11-17; `index/wordlist.py` ist Code, der `/usr/share/dict/ngerman` im Image liest) | closed |
| T-04-19 | Denial of Service | `build_cues` auf 100 000 Wörtern | mitigate | Ein Durchlauf, Rückgriff nur im offenen Cue `subtitles/cues.py:18-19,84`; Messung 100 000 Wörter 04-08-SUMMARY.md:85; Zeit-Gate `backend/tests/test_export_budget.py:49,112-120` | closed |
| T-04-20 | Tampering | Steuerzeichen in Oberflächen | mitigate | `_CONTROL` `subtitles/cues.py:42`, Ersatz :120; Tests `backend/tests/test_subtitles_cues.py:193,302` (`\n`, `\t`, `-->`) | closed |
| T-04-21 | Tampering | VTT-Cue-Text mit Markup | mitigate | Maskierung `subtitles/formats.py:34,45-48`; Tests `backend/tests/test_subtitles_formats.py:71` (Rücklesen über webvtt-py, srt, ffmpeg), :86, :105 | closed |
| T-04-22 | Denial of Service | sehr große Exporte | mitigate | Messung 04-08-SUMMARY.md:50,85; Abgleich der PHP-Konstanten `test_export_budget.py:51-52,106-142` gegen `ExAppService.php:84,91` | closed |
| T-04-23 | Repudiation | Writer fügt Text hinzu | mitigate | `test_subtitles_cues.py:177`, `test_subtitles_formats.py:86,142` (wortgleich, exakte Zeiten) | closed |
| T-04-24 | Information Disclosure | `/export`, `/export/meta` | mitigate | `_NOT_KNOWN` `backend/src/audio_video_search_backend/api/export.py:56,82-99,132-156`; Test `backend/tests/test_api_export.py:305-314` (sechs Fälle inkl. ausgeschlossen, rohe Bytes gegen unbekannte ID), Positivkontrolle :319-323 | closed |
| T-04-25 | Spoofing | Aufruf am PHP vorbei | mitigate | **Fix 17.11.2026 (Owner-Entscheid, Findling-Muster, Commit `c35b5e4`):** `^/export$` und `^/export/meta$` (mit `^/search$`, `^/excerpt$`, E-1) aus `backend/appinfo/info.xml` entfernt; deklariert bleiben nur ADMIN-Routen :84-125, Begründung im Kopfkommentar :18-28. Beide Proxys antworten einer nicht deklarierten Route mit 404: HaRP v0.4.5 (= CI-Pin `HARP_IMAGE` sha256:603fdf5c…, Tag v0.4.5 auf 93afc127) `haproxy_agent.py:572-575` ("No defined route", `not_found`, `record_ip_failure`) mit `haproxy.cfg.template:50` (`return status 404`); signierte AppAPI-Anfragen überspringen die Prüfung :529-531. AppAPI `ExAppProxyController::prepareProxy` stable33/34 :272-278, stable35 :274-280 ("route does not pass the access check", `NotFoundResponse`); `PublicFunctions::exAppRequest` stable34 :29-42 geht über `AppAPIService::requestToExApp` :64-75 ohne Routenprüfung; `ExAppPost` gibt dann `NotFoundResponse` zurück stable34 :130-137 (Branch-Stände 17.11.2026: stable33 a1230aac, stable34 747c8c62, stable35 918fcc1f, wie sie die CI auscheckt). Die PHP-App ruft alle vier nur über `call()` -> `proxyRequest` -> `exAppRequest` (`php/lib/Service/ExAppService.php:234,286,374-375,414,1065`); CI, Playwright und Skripte rufen sie nirgends über `/exapps/...` (geprüft 17.11.2026: nur `/status` und `/sample`, beide ADMIN). Gate `route_findings` `backend/tests/test_store_metadata.py:145` (keine Route außer ADMIN, keine Route, deren Regex einen der vier Pfade trifft, auch `^/.*$` und Großschreibung), echter Stand :173, Gegenprobe :178 (USER, PUBLIC, jede der vier Routen, `^/.*$`, `^/EXPORT/META$`, ungültige Regex feuern; `^/searching$` als Positivkontrolle ohne Befund), gegen die info.xml von `b2430c8` 8 Befunde; `ACCESS_LEVELS` :53 nur noch ADMIN (vorher ließ :134 PUBLIC durch); Container-Routen ohne Deklaration :240, PHP ruft alle vier :205. E2E-Negativtest `.github/workflows/deploy-harp.yml:470-510` (bob POST auf alle vier über HaRP `/exapps/...` und AppAPI `/index.php/apps/app_api/proxy/...`, je 404, Container-Zugriffslog ohne neue Zeile; danach Positivkontrolle admin GET `/status` über beide Wege 200), Gate `past_php_findings` `backend/tests/test_workflows.py:966` mit Gegenprobe :996. PHP-Weg für bob weiter grün: OCS-Suche `deploy-harp.yml:450-452`, S1 bis S5 `ci/playwright/preview.spec.ts:354`, Export für einen Freigabe-Empfänger X5 `export.spec.ts:605`. **closed lokal, CI-Beleg Push 5 ausstehend.** Befund vor dem Fix: **Lücke 1 (Wirkung):** `access_level` gilt nur für den Weg Browser nach AppAPI/HaRP nach Container (Findling-Recherche VERIFIED, `nextcloud-search/.planning/milestones/v1.0-phases/04-admin-sichtbarkeit-und-diagnose/04-RESEARCH.md:638`); `USER` lässt dort jeden angemeldeten Nutzer durch. Dass der Weg besteht, zeigt die eigene CI: `.github/workflows/deploy-harp.yml:404,785` ruft `/exapps/${BACKEND_APP_ID}/status` und `/sample` direkt per Basic Auth. `/export` nimmt nur `fileId` und prüft keine Rechte `api/export.py:143-156` (Zeilen nach dem Docstring-Nachtrag). Damit kann ein angemeldeter Nutzer per `POST /exapps/audio_video_search_backend/export {"fileId": N}` den Export fremder, ausgeschlossener oder download-gesperrter Dateien abrufen; Rechteprüfung, Ausschluss und DownloadPolicy (T-04-29 bis T-04-31) liegen nur in PHP. In diesem Audit nicht live ausgeführt (kein Docker). **Lücke 2 (Gate):** Der Plan nennt ein Gate in `test_api_routes.py`; dort steht keins. `backend/tests/test_store_metadata.py:48,127-135` lässt für jede Route `PUBLIC`, `USER` oder `ADMIN` zu, ein Wechsel von `/export` auf `PUBLIC` bliebe grün | closed lokal, CI-Beleg Push 5 ausstehend |
| T-04-26 | Denial of Service | Export langer Dateien blockiert den Store | mitigate | nur Snapshot unter `run_locked` `api/export.py:134`, Sprache und Format in `asyncio.to_thread` :119,:135,:149; Tests `test_api_export.py:369,394` | closed |
| T-04-27 | Tampering | Sprache im Dateinamen | mitigate | `api/export.py:115-129` (nur `FILE_LANGUAGES`, sonst known false); Test `test_api_export.py:238-247` (kein `und`) | closed |
| T-04-28 | Information Disclosure | Logs Export | mitigate | `api/export.py` ohne Logger (Kopf :27-28); Test `test_api_export.py:412` | closed |
| T-04-29 | Information Disclosure | Export aus Freigabe mit Download-Sperre | mitigate | `allowsExport` vor Container `ExportController.php:109,169,241`; Gate-Regel 19 `test_php_gates.py:1385` mit Selbsttests :1392,:1414; PHPUnit `ExportControllerTest.php:334` (Container nie gefragt); E2E X3 `ci/playwright/export.spec.ts:471` grün in sechs Beinen (Läufe 43926051392, 43955067783) | closed |
| T-04-29a | Information Disclosure | Ausschluss-Orakel 404 vs 403 | mitigate | Sperre vor `reload`/`isExcluded*` `ExportController.php:109-125,169-185,241-257`; Gate-Regel 19 `test_php_gates.py:1392-1411`; PHPUnit `ExportControllerTest.php:357,379,391`; E2E Kombifall `export.spec.ts:492` | closed |
| T-04-30 | Information Disclosure | unentscheidbares Freigabe-Attribut | mitigate | `UNKNOWN` bei Lesefehler `php/lib/Service/DownloadPolicy.php:60-65`, Export nur bei `ALLOWED` :81-82; Tests `DownloadPolicyTest.php:115,136`, `ExportControllerTest.php:346,379` | closed |
| T-04-31 | Information Disclosure | Export fremder/ausgeschlossener Dateien per geratener fileId (PHP-Routen) | mitigate | `resolve` über `readableFile` als Nutzer `ExportController.php:458-479`; Ausschluss nach Regeln von jetzt :113-125 (Gate-Regel 14 `test_php_gates.py:914`); byte-gleiche 404 `ExportControllerTest.php:411,444,460,824`. Für die PHP-Routen belegt; der Weg an PHP vorbei ist T-04-25 | closed |
| T-04-32 | Tampering | Dateiname in Content-Disposition, TXT-Kopf, VTT-NOTE | mitigate | Name nur aus dem Node `ExportController.php:140,289`; Header-Name ohne Steuerzeichen :352-356, `DataDownloadResponse` (HeaderUtils, ASCII-Fallback, `/` `\` ersetzt, laut 04-RESEARCH.md:243 gegen stable33/34/35 VERIFIED); TXT-Kopf :386-391; NOTE :436-449; Name nie an den Container: Gate-Regel 13 `test_php_gates.py:572` mit Selbsttest :588. Tests `ExportControllerTest.php:541,582,595,623`, `SidecarTest.php:230` | closed |
| T-04-33 | Denial of Service | teure Exporte | mitigate | `UserRateLimit(30, 60)` `ExportController.php:98,159`; eigener Timeout und Grenze `ExAppService.php:84,91,374-380,1141`; Tests `ExportControllerTest.php:896`, `ExAppServiceTest.php` (Export-Budget, Körper über Grenze = null) | closed |
| T-04-34 | Elevation of Privilege | Track-Route als Umgehung | mitigate | gleiche Kette `ExportController.php:161-196`; Gate-Regel 19 prüft `track`; Tests `ExportControllerTest.php:391,658`; E2E X3 (Spur 403) | closed |
| T-04-35 | Information Disclosure | Logs Export-Routen | mitigate | nur `fileId`/`class` `ExportController.php:118-120,178-180,250-252,266-269,309-312,440-442,472-475`; Gate-Regel 6 `test_php_gates.py:324,482` | closed |
| T-04-36 | Tampering | Überschreiben fremder Untertitel | mitigate | Sperre vor `nodeExists` vor `newFile` `php/lib/Service/SidecarWriter.php:69-97`; Gate-Regel 20 `test_php_gates.py:1499` mit Selbsttest :1503; Tests `SidecarTest.php:118,143,162`, `ExportControllerTest.php:722,737`; E2E E1/E2 byte-gleich `ci/playwright/sidecar.spec.ts:261` | closed |
| T-04-37 | Tampering | Pfad-Injektion über den Namen | mitigate | Name aus Node, NFC, Sprache nur de/en/fr `ExportController.php:289,335-341,516-523`, `ExAppService.php:448-450`; Prüfung `/` `\` `.` `..` leer, 255 Byte `SidecarWriter.php:65-67,112-116`, `ExportController.php:290-292`; Tests `SidecarTest.php:133,230,243`, `ExportControllerTest.php:808` | closed |
| T-04-38 | Spoofing | CSRF-Ablage | mitigate | `sidecar` ohne `NoCSRFRequired` `ExportController.php:230-232`; Gate-Regel 20 `test_php_gates.py:1521-1527`; PHPUnit `ExportControllerTest.php:862`; `requesttoken` `php/js/play.js:95` | closed |
| T-04-39 | Elevation of Privilege | Schreiben ohne Schreibrecht | mitigate | `isCreatable` und `write` in `actAs` `ExportController.php:264,300-303`; `NotPermittedException` = not_writable `SidecarWriter.php:84-92`; Tests `ExportControllerTest.php:784,797`, `SidecarTest.php:193`; E2E E3 `sidecar.spec.ts:331` | closed |
| T-04-40 | Information Disclosure | Ablage aus Freigabe mit Download-Sperre | mitigate | `allowsExport` vor Container und Schreiben `ExportController.php:241-243`; Gate-Regel 19; Test `ExportControllerTest.php:762`; E2E E4 `sidecar.spec.ts:362` und X3 | closed |
| T-04-41 | Denial of Service | Ablage-Flut | mitigate | `UserRateLimit(10, 60)` `ExportController.php:231`; Test `ExportControllerTest.php:862`; E2E E6 `sidecar.spec.ts:596`; Kollision verhindert Mehrfachablage (T-04-36) | closed |
| T-04-42 | Tampering | Wettlauf fremder Client zwischen Prüfung und Anlegen | accept | siehe AR-04-03; öffentlich `SECURITY.md:48-53`, Code-Kommentar `SidecarWriter.php:25-30` | closed |
| T-04-43 | Information Disclosure | Logs Ablage | mitigate | `SidecarWriter.php:87-89` nur `class`, kein Sperrschlüssel; Controller :266-269,:309-312; Test `SidecarTest.php:193`; Gate-Regel 6 | closed |
| T-04-44 | Information Disclosure | Export-URLs bei Download-Sperre | mitigate | `BLOCKED` liefert Abschnitt ohne URLs `php/lib/Controller/PageController.php:407-409`, `UNKNOWN` ohne Abschnitt :410-411; Tests `PlayControllerTest.php:1049,1080,1314`; E2E X3 `export.spec.ts:471` | closed |
| T-04-45 | Information Disclosure | X4 ausgeschlossen/unbekannt | mitigate | `PageController.php:410-420`; Tests `PlayControllerTest.php:1262,1358` (Byte-Vergleich); E2E X4 `export.spec.ts:524` | closed |
| T-04-45a | Information Disclosure | Ausschluss-Orakel X3 vs X4 | mitigate | Urteil vor `$excluded` `PageController.php:150,170,407-411`; Test `PlayControllerTest.php:1063`; E2E `export.spec.ts:492` | closed |
| T-04-46 | Tampering | XSS über Dateinamen | mitigate | `play.js` nur `textContent` `php/js/play.js:18,69`; Gate `backend/tests/test_ui_assets.py:38-39,272,470-482` (kein `innerHTML`, kein unmaskierter Druck, mit Selbsttest) | closed |
| T-04-47 | Spoofing | CSRF der Ablage (Client) | mitigate | `requesttoken` `play.js:95`; Gate `test_ui_assets.py:273,455`; Server T-04-38 | closed |
| T-04-48 | Repudiation | Spur als "geprüft" missverstanden | mitigate | Label `PageController.php:449` ("%s, subtitle draft"); kein `default` `test_ui_assets.py:226-231` mit Selbsttest :290; E2E `sidecar.spec.ts:463` (Label, aus) | closed |
| T-04-49 | Repudiation | README-Behauptungen | mitigate | `README.md:42`, `README.en.md:42`, `README.fr.md:42` (NC-36-Satz); BITV-Gate `test_public_texts.py:219` mit Selbsttest :246-266 | closed |
| T-04-50 | Information Disclosure | Sicherheitsversprechen ohne Deckung | mitigate | `SECURITY.md:35-41` verspricht, Exporte und Spur gebe es "only for files the user may read and only when the share allows downloads"; PHPUnit/E2E decken die PHP-Routen (T-04-29 bis T-04-31, T-04-51). **Fix 17.11.2026 (Commit `c35b5e4`):** der direkte Containerweg ist zu (T-04-25: Routen nicht deklariert, Gate `test_store_metadata.py:145,173,178`, E2E `deploy-harp.yml:470-510`). `SECURITY.md:26-33` präzisiert: Container-Routen mit Nutzerdaten sind für AppAPI-Proxy und HaRP nicht deklariert, nur über die PHP-App erreichbar, die Leserecht, Ausschluss und Download-Sperre zuerst prüft; die übrigen Routen sind ADMIN. Docstrings, die die Zugriffsentscheidung der Container-info.xml zuschrieben, präzisiert (`api/__init__.py:3-11`, `status.py:3-7`, `coverage.py:3-5`, `reconcile.py:3-5`, `workstock.py:3-4`, `sample.py:19-20`; neu `search.py:17-20`, `excerpt.py:18-21`, `export.py:30-34`). Befund vor dem Fix: Für den direkten Containerweg fehlte jede Deckung | closed lokal, CI-Beleg Push 5 ausstehend |
| T-04-51 | Information Disclosure | Rechte-Negativtests im echten Stack | mitigate | E2E X3 `export.spec.ts:471`, Kombifall :492, X4 :524, X5 :605, E3/E4 `sidecar.spec.ts:331,362`, SRCH-04 `search-quality.spec.ts:285`; grün in sechs Beinen: Lauf 43926051392 (04-15-SUMMARY.md:63,87-93), Lauf 43955067783 (04-16-SUMMARY.md:137-157) | closed |
| T-04-52 | Tampering | Admin-Schalter/Container bleibt verändert | mitigate | `finally` `export.spec.ts:487-489,513-521`; `sidecar.spec.ts:346-357,377-388`; `withContainerStopped` `ci/playwright/helpers.ts:584,606,634` | closed |
| T-04-53 | Information Disclosure | Artefakte mit Inhalten | accept | siehe AR-04-04 | closed |
| T-04-54 | Repudiation | Commit-Autoren und -Texte | mitigate | Freigabedateien `approvals/push-269d173…`, `push-56f3627…`, `push-e5a2479…`, `push-f7bb9da…` (je `push-phase-04 <sha>`); Prüfung dieses Audits über `origin/phase-03..f7bb9da`: 89 Commits, alle `street1983nk <k.cherif@outlook.de>` als Autor und Committer, keine `Claude-Session`/`Co-Authored`/`closes|fixes|resolves #N`, kein `.planning/debug/` (2026-11-17) | closed |
| T-04-55 | Tampering | main oder ghcr verändert | mitigate | `approvals/main-before-*`/`main-after-*` und `ghcr-before-*`/`ghcr-after-*` für 269d173 und 56f3627 gleich (04-15-SUMMARY.md:110-113); für e5a2479 und f7bb9da nur `main-before-*`. Gegenprobe dieses Audits: `git ls-remote` 2026-11-17 `refs/heads/main` = `ea97b58` (= alle main-before), `phase-04` = `f7bb9da`, kein `v*`-Tag; ghcr-Veröffentlichung nur bei main/Tag (`.github/workflows/docker.yml:12-16`, `release.yml:22-25`) | closed |
| T-04-56 | Denial of Service | GitHub-API-Rate | mitigate | Prozessbeleg: "Läufe einzeln nacheinander beobachtet" 04-15-SUMMARY.md:67; ein Rerun statt Neustart 04-16-SUMMARY.md:139 | closed |
| T-04-57 | Repudiation | Abnahme ohne Bild | mitigate | Lücken benannt 04-16-SUMMARY.md:66,87,91-96 (Spurmenü T31 ohne Bild, vom Owner akzeptiert); 04-15-SUMMARY.md:146-149 | closed |
| T-04-58 | Tampering | Testclip ausgetauscht (04-14) | mitigate | `REVISION` `ci/media/fetch_speech.py:33`, `member_sha256` je Clip :81,:95,:105,:121,:144, Prüfung :263; Host-Allowlist :39-40,:187; kein extractall (Kopf :9) | closed |
| T-04-59 | Repudiation | Beweis still übersprungen | mitigate | `backend/tests/test_downloaded_subtitles.py:57,62,66` (leerer/fehlender Ordner, fehlendes Format = fail), Selbsttests :148,:153,:158,:165,:171; Workflow-Gate ohne `continue-on-error` `backend/tests/test_workflows.py:856-860`; CI "11 passed, kein skip" je Bein 04-15-SUMMARY.md:102 | closed |
| T-04-61 | Information Disclosure | Screenshots mit Testinhalten (04-16; im Plan als T-04-58 vergeben, E-2) | accept | siehe AR-04-05 | closed |
| T-04-60 | Information Disclosure | Ausschluss-Orakel über die Sperrseite | mitigate | E2E Kombifall `export.spec.ts:492-521` (Abschnitt und Sidecar-403 byte-gleich, Positivkontrolle A5); PHPUnit `PlayControllerTest.php:1063`, `ExportControllerTest.php:357` | closed |

*Status: open · closed · closed lokal, CI-Beleg Push 5 ausstehend (zählt bis zum grünen CI-Lauf als open)*
*Disposition: mitigate (Umsetzung nötig) · accept (dokumentiertes Risiko) · transfer (an andere Komponente/Dritte)*

---

## Offene Threats (BLOCKER)

Kein Threat mehr ohne Fix. Zwei warten nur noch auf den CI-Beleg:

| Threat ID | Stand | Was CI mit Push 5 belegen muss |
|-----------|-------|--------------------------------|
| T-04-25 | closed lokal (Commit `c35b5e4`): Routen mit Nutzerdaten nicht mehr deklariert, Gates grün | In allen sechs Beinen von deploy-harp.yml der Schritt "Container routes with user data are not reachable past the PHP app" grün: bob POST auf `/search`, `/excerpt`, `/export`, `/export/meta` über HaRP (`:8090/exapps/...`) und über AppAPI (`/index.php/apps/app_api/proxy/...`) je 404, Container-Zugriffslog ohne neue Zeile; danach admin GET `/status` über beide Wege 200. Dazu weiter grün: OCS-Suche für bob (Schritt davor), @preview S1 bis S5, @phase4 (X5 Export eines Freigabe-Empfängers, X3/X4), damit der PHP-Weg über `exAppRequest` ohne Deklaration nachweislich trägt |
| T-04-50 | closed lokal (Commit `c35b5e4`): Versprechen in `SECURITY.md:26-41` gedeckt, sobald T-04-25 in CI belegt ist | wie T-04-25 |

Prüfpunkt für den Lauf: Jede abgewiesene HaRP-Anfrage zählt gegen die Sperre von 127.0.0.1 (`HP_BLACKLIST_COUNT` 10 in 300 s, HaRP v0.4.5 `haproxy_agent.py:390-400`); der Schritt schickt genau vier. Wird ein Bein danach rot mit HaRP-`silent-drop`, ist das die Sperre, nicht der Fix.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-10 | Icon-Pfade sind reine Pfaddaten (`M…Z`), keine Skripte; Quelle Apache-2.0, im UI-SPEC festgehalten | Plan 04-03 (Planfreigabe); vom Owner bestätigt 17.11.2026 | 2026-11-17 |
| AR-04-02 | T-04-17 | Präfix-Beifang nur in Dateien, die der Nutzer ohnehin lesen darf; Rechteprüfung in PHP unverändert (`Provider.php:315-331`); Zahlen im 04-06-SUMMARY. Gilt mit dem T-04-25-Fix: die Rechteprüfung ist nur noch über PHP erreichbar, weil `/search` und `/excerpt` nicht mehr am Proxy deklariert sind | Plan 04-06 (Planfreigabe); vom Owner bestätigt 17.11.2026 | 2026-11-17 |
| AR-04-03 | T-04-42 | Lücke im Millisekundenbereich zwischen `nodeExists` und `newFile` gegen fremde Clients (Sync, WebDAV); App-Sperre schützt gegen eigene Parallelaufrufe; Server bietet kein create-only. Öffentlich in `SECURITY.md:48-53` | Owner | 2026-11-16 |
| AR-04-04 | T-04-53 | CI-Artefakte nur mit FLEURS-Testaudio (CC-BY-4.0) und Wegwerf-Instanz, keine Nutzerdaten | Plan 04-14 (Planfreigabe); vom Owner bestätigt 17.11.2026 | 2026-11-17 |
| AR-04-05 | T-04-61 | Screenshots nur mit synthetischen Testnutzern und Testaudio; Artefakte in CI und Scratchpad | Plan 04-16 (Planfreigabe); vom Owner bestätigt 17.11.2026 | 2026-11-17 |

*Akzeptierte Risiken tauchen in späteren Audit-Läufen nicht erneut auf.*

---

## Threat Flags aus den SUMMARY-Dateien

| Flag | Quelle | Zuordnung |
|------|--------|-----------|
| Keine neue Angriffsfläche | 04-01, 04-02, 04-04 bis 04-14, 04-17 | jeweils T-IDs des Plans (informativ) |
| `/export`, `/export/meta` hinter AppAPIAuthMiddleware mit `access_level USER` | 04-09-SUMMARY | T-04-25; die SUMMARY wertete USER als Schutz, für den Proxyweg war es keiner. Seit 17.11.2026 sind beide Routen nicht mehr deklariert |
| Player `controlslist="nodownload"` bei gesperrter oder unklarer Freigabe | 04-16-SUMMARY:82-84 | kein Threat: nur Bedien-Hürde (Owner 16./17.11., `SECURITY.md:43-46`); echte Sperre ist die DownloadPolicy fail-closed vor Export, Spur und Ablage (T-04-29, T-04-30, T-04-40, X3 in CI belegt). Belege: `PageController.php:188`, `PlayControllerTest.php:1328,1342`, Gate `test_ui_assets.py:391-408`, E2E X3/X1 (Lauf 43955067783) |
| Abschnitt "Threat Flags" nachgetragen 17.11.2026 | 04-03, 04-15, 04-16 | Formlücke geschlossen: 04-03 (T-04-08 bis T-04-10), 04-15 (T-04-54 bis T-04-56), 04-16 (nodownload, T-04-57, T-04-61); keine neue Fläche |

---

## Escalations (außerhalb des Registers)

- **E-1 (Phase 3, gleicher Weg wie T-04-25): closed lokal, CI-Beleg Push 5 ausstehend.** Befund: `/search` und `/excerpt` standen mit `access_level USER` in `backend/appinfo/info.xml` (Stand `b2430c8` :80-92); Phase 3 hat die Rechteprüfung an PHP übergeben (T-03-27 transfer), über den direkten `/exapps/...`-Weg hätte ein angemeldeter Nutzer Treffer und Ausschnitte aus allen Dateien des Index erhalten. Fix mit T-04-25 im selben Commit `c35b5e4`: beide Routen nicht mehr deklariert, gleiche Gates (`test_store_metadata.py:145,173,178`), gleicher E2E-Schritt (`deploy-harp.yml:470-510`, `/search` und `/excerpt` auf beiden Wegen 404). Versprechen `SECURITY.md:26-33` ("search results … only show files the user may read") damit gedeckt, sobald CI grün ist.
- **E-2 (Register): aufgelöst 17.11.2026.** T-04-58 war in 04-14 und 04-16 doppelt vergeben; der Fall aus 04-16 (Screenshots) heißt im Register jetzt `T-04-61` (AR-04-05, 04-16-SUMMARY Threat Flags). Die Plandatei bleibt als historischer Stand unverändert.

---

## Routen der Container-info.xml (vorher/nachher, 17.11.2026)

| Route | Verb | vorher (`b2430c8`) | nachher | Begründung |
|-------|------|--------------------|---------|------------|
| `^/status$` | GET | ADMIN | ADMIN | Admin-Diagnose (Zustand, Versionen, Einstellungen, Zähler; keine Inhalte); CI-Positivkontrolle und Rückkehr-Prüfung des Containers |
| `^/search$` | POST | USER | entfernt | Treffer mit Ausschnitt aus allen Dateien des Index; Rechte nur in PHP (E-1) |
| `^/excerpt$` | POST | USER | entfernt | Transkripttext je fileId; Rechte nur in PHP (E-1) |
| `^/export$` | POST | USER | entfernt | Untertitel/Transkript je fileId; Rechte, Ausschluss, DownloadPolicy nur in PHP (T-04-25) |
| `^/export/meta$` | POST | USER | entfernt | Zustand, Sprache, Teilstand je fileId; gleiche Begründung (T-04-25) |
| `^/workstock$` | GET | ADMIN | ADMIN | Arbeitsbestand nur mit IDs und Codes, nie Pfad oder Nutzer; occ audio_video_search:files |
| `^/coverage$` | GET | ADMIN | ADMIN | nur Zahlen; occ audio_video_search:status |
| `^/sample$` | POST | ADMIN | ADMIN | Testergebnis säen (Walking Skeleton); liest die Datei über das Content-Gateway der PHP-App als der genannte Nutzer; occ und CI-Schritt "Drift 4" als admin |
| `^/sample/remove$` | POST | ADMIN | ADMIN | Testergebnis entfernen; occ |
| `^/reconcile/run$` | POST | ADMIN | ADMIN | eine Abgleichsrunde, Antwort nur Zähler; occ audio_video_search:reconcile |

ADMIN wirkt nur auf dem Proxyweg; occ und die Admin-Seite erreichen die Routen über `exAppRequest`, dort entscheidet PHP (Konsole bzw. Controller ohne `NoAdminRequired`).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-17 | 63 (58 mitigate, 5 accept, 0 transfer) | 60 (55 mitigate, 5 accept) | 3 (T-04-25, T-04-50, T-04-SC) | gsd-security-auditor (ASVS 2, block_on open) |
| 2026-11-17 (Nachtrag nach Owner-Entscheid) | 63 (58 mitigate, 5 accept, 0 transfer) | 61 (56 mitigate, 5 accept; T-04-SC per Gate) | 2 (T-04-25, T-04-50: closed lokal, CI-Beleg Push 5 ausstehend); E-1 ebenso | gsd-executor (Fix-Lauf, lokal) |

---

## Sign-Off

- [x] Alle Threats haben eine Disposition (mitigate / accept / transfer)
- [x] Akzeptierte Risiken im Accepted Risks Log, alle fünf vom Owner bestätigt
- [ ] `threats_open: 0` bestätigt (nach grünem CI-Lauf von Push 5)
- [ ] `status: verified` im Frontmatter gesetzt (Owner, nach CI)

**Approval:** offen bis zum CI-Beleg. T-04-25, T-04-50 und E-1 sind lokal geschlossen (Routen nicht deklariert, Gates mit Gegenprobe grün), der Nachweis im echten Stack kommt mit Push 5. T-04-SC ist per Gate geschlossen. AR-04-01, AR-04-02, AR-04-04 und AR-04-05 vom Owner am 17.11.2026 bestätigt, AR-04-03 am 16.11.2026.
