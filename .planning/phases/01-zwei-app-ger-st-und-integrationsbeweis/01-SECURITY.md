---
phase: 01
slug: zwei-app-ger-st-und-integrationsbeweis
status: verified
threats_open: 0
asvs_level: 2
created: 2026-11-15
---

# Phase 01: Security

> Sicherheitsvertrag je Phase: Threat-Register, akzeptierte Risiken, Audit-Verlauf.
> Register aus den 13 `<threat_model>`-Blöcken der PLAN-Dateien 01-01 bis 01-13 (register_authored_at_plan_time: true, rückwirkend geprüft).
> Geprüfter Stand: HEAD `dc742f7` (Arbeitsbaum zusätzlich mit uncommitteter Änderung an `backend/tests/test_model_download.py`, nicht Teil des Belegs).
> Belege sind Datei:Zeile im Repo. Prozess-Threats (Owner-Tore, Pushes) sind über SUMMARY-Dateien und die lokale Git-Historie belegt, nicht über Absichtserklärungen. Die globalen Änderungen vom 15.11.2026 aus Phase 3 (`logs.py` schreibt nie Exception-Text, `models/procure.py` hält Modell-Urteile nur im Prozess) gelten hier als vorhandene Mitigation, wo sie passen.
> `T-01-SC` steht in vier Plänen (01, 04, 05, 09) und ist hier ein Eintrag.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Nutzer nach Provider (Unified Search) | Suchbegriff, limit, Cursor | Anfragewerte |
| Nutzer nach Abspielseite `/play/{fileId}?t=` | Datei-ID, Zeitmarke, Sitzung | Anfragewerte |
| Admin nach `/admin/state`, `/admin/sample` | Admin-Sitzung, requesttoken | Schalterwert |
| Container nach PHP-Gateway, Handshake | signierte AppAPI-Anfrage mit EX-APP-ID | Datei-ID, Nutzer-ID, Dateibytes |
| PHP nach Container (`/search`, `/excerpt`, `/sample`, `/status`) | signierte AppAPI-Anfrage | Begriff, Datei-IDs, Ausschnitte |
| Container-Antwort nach HTML/Initial-State | Ausschnitt, Versionen, Zähler | Transkripttext, Zustandscodes |
| Nutzerdatei nach WebDAV-Player | Medienstrom, Freigabe-Attribute | Nutzerinhalte |
| Lieferkette nach Build/CI | tantivy, @playwright/test, phpunit, Actions | fremder Code |
| CI-Wegwerfinstanz nach Artefakte | Screenshots, Logs | Testdaten, Job-Passwörter |
| Release-Workflow nach Store | Signaturschlüssel, Archive | Schlüsselmaterial, Code |
| lokales Repo nach GitHub | Push auf `phase-01` | Code, Commit-Identität |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (Beleg) | Status |
|-----------|----------|-----------|-------------|--------------------|--------|
| T-01-SC | Tampering | tantivy, @playwright/test, phpunit, npm in CI | mitigate | Exakte Pins `backend/pyproject.toml:21` (tantivy==0.26.2), `php/composer.json:15` (phpunit 11.5.57), `ci/playwright/package.json:10` (1.65.0); package-lock mit Integrity; `npm ci --ignore-scripts` `.github/workflows/deploy-harp.yml:464-469` | closed |
| T-01-01 | Tampering | Workflow-Actions | mitigate | Alle `uses:` per 40-stelligem SHA (grep ohne Treffer für ungepinnte Zeilen, 2026-11-15); Gate `backend/tests/test_workflow_pins.py:265,283,289,295` mit Selbsttests :336,:350 | closed |
| T-01-02 | Elevation of Privilege | php.yml, docker.yml | mitigate | `permissions: contents: read` `.github/workflows/php.yml:27-28`, `docker.yml:23-24`; keine `secrets.` in php.yml | closed |
| T-01-03 | Information Disclosure | Geheimnis-Scan | mitigate | `backend/tests/test_public_artifacts.py:15,37,43-48` über REPO_ROOT, Selbsttest :63; läuft in CI `.github/workflows/python.yml:161` | closed |
| T-01-04 | Spoofing | Lockstep-Versionen | accept | siehe AR-01-01 | closed |
| T-01-05 | Tampering | store/repo.py SQL | mitigate | SQL als `Final`-Konstanten mit `?`/`:name` (z. B. `store/repo.py:508-557`); ruff-Regelsatz `S` (enthält S608) `backend/pyproject.toml:75`; einziges f-String-SQL ist ein Pragma mit Konstante `store/repo.py:855` | closed |
| T-01-06 | Tampering | publish_version | mitigate | `store/repo.py:1941-2000`: input_file_sha256 gegen media_key :1971-1973, Epoche :1974-1976, bedingter UPSERT mit Zeilenwertvergleich :520-529 und `changes()`-Prüfung :1999-2000, alles in `_transaction` (BEGIN IMMEDIATE :953) | closed |
| T-01-07 | Information Disclosure | Logs aus repo.py | mitigate | nur IDs/Zahlen per `extra=` `store/repo.py:1954-1962`; `logs.py` ohne Exception-Text (Phase-3-Fix 15.11.), Tests `backend/tests/test_logs.py:41,60` | closed |
| T-01-08 | Repudiation | correction | mitigate | `author_uid`, `created_at`, `superseded_by` `store/schema.sql:162-178`; Pflichtprüfung author_uid `store/repo.py:2053-2054` | closed |
| T-01-09 | Denial of Service | Korrektur-Spannen | mitigate | CHECK `end_ms > start_ms` `store/schema.sql:167`; Überlappung per `_SUPERSEDE_TEXT` `store/repo.py:549-553` | closed |
| T-01-10 | Information Disclosure | Provider | mitigate | Recheck je fileId `php/lib/Search/Provider.php:265-279` (`FileAccess::readableFile` unter `ReaderContext::actAs`); Titel/Pfad nur aus geprüftem Node :315-341 | closed |
| T-01-11 | Elevation of Privilege | GatewayController | mitigate | `#[ExAppRequired]` + `rejectForeignCaller()` als erste Anweisung `php/lib/Controller/GatewayController.php:102-109,148-155,320-332`; Gate Regel 1 `backend/tests/test_php_gates.py:280` | closed |
| T-01-12 | Information Disclosure | Gateway-Fehler | mitigate | Wortgleiche 404 für nicht sichtbar, nicht lesbar, kein File, unbekannter Nutzer `GatewayController.php:118-122,243-245,273-278`; Logzeilen der Ablehnungen nur fileId/Grund :252,:263,:281,:291 (Restpunkt 500-Zweig siehe E-01-1) | closed |
| T-01-13 | Tampering | subline/XSS | mitigate | Typprüfung der Container-Felder `php/lib/Service/ExAppService.php:202-233`; Ausschnitt gekürzt, reiner Text `Provider.php:322,365-382` | closed |
| T-01-14 | Tampering | SampleCommand | mitigate | nur mit `debug => true` `php/lib/Command/SampleCommand.php:82-83`; Provider zeigt Probe nur mit debug und Schalter `Provider.php:222-223,261` | closed |
| T-01-15 | Denial of Service | Provider | mitigate | Begriff 200 Zeichen `Provider.php:93,162`, limit 25 :78,:180, Budget 2,5 s :75,:231,:254; Timeout 1,5 s `ExAppService.php:65,213` | closed |
| T-01-16 | Spoofing | appVersion aus Antwort | accept | siehe AR-01-02 | closed |
| T-01-17 | Tampering | Kataloge in Templates | mitigate | Ausgabe nur über `p()` (keine `echo`/`print_unescaped` in `php/templates/*.php`); Gate `backend/tests/test_ui_assets.py:136,309` | closed |
| T-01-18 | Information Disclosure | Playwright-Artefakte | mitigate | Passwörter nur als Job-Variablen der Wegwerfinstanz (z. B. `deploy-harp.yml:68`), keine `secrets.` in deploy-harp.yml | closed |
| T-01-19 | Spoofing | /search, /excerpt, /sample | mitigate | `APP.add_middleware(AppAPIAuthMiddleware)` `backend/src/audio_video_search_backend/main.py:251`; Routenblock `^/<name>$` mit ADMIN für /sample `backend/appinfo/info.xml:71-128` | closed |
| T-01-20 | Tampering | Eingaben der Routen | mitigate | `api/excerpt.py:40-41` (fileId > 0, atMs 0 bis 86400000 `api/__init__.py:25`); `api/search.py:58-60,179` (limit 1 bis 50, Begriff auf `MAX_TERM_CHARS = 200` `index/publish.py:66` gekürzt); Query-Fehler leer `index/publish.py:270-275` | closed |
| T-01-21 | Information Disclosure | Logs Container | mitigate | `api/search.py:183` nur hits/limit/offset; caplog-Test `backend/tests/test_api_routes.py:407-416`; `logs.py` ohne Exception-Text (`test_logs.py:41,60`) | closed |
| T-01-22 | Information Disclosure | Rechte | mitigate | Container liefert nur fileId/Zeit/Text `api/search.py:165-173`; Recheck in PHP `Provider.php:265-279` | closed |
| T-01-23 | Denial of Service | Gateway-Strom | mitigate | 8 GiB `api/sample.py:43,119`; Abbruch über max_bytes `nc.py:187`; Timeouts und `follow_redirects=False` `nc.py:112,165` | closed |
| T-01-24 | Tampering | veraltete Index-Dokumente | mitigate | index_rev-Filter `api/search.py:63-72`; Outbox und reconcile beim Start `main.py:183-211` | closed |
| T-01-25 | Information Disclosure | play/{fileId} (IDOR) | mitigate | `php/lib/Controller/PageController.php:223-245` (`readableFile` unter `actAs`), gleiche Antwort für fehlend und verboten :127-130 | closed |
| T-01-26 | Tampering | Pfad in DAV-Adresse | mitigate | `PageController.php:283-288` Pfad aus dem Node, `rawurlencode` je Segment und für die UID | closed |
| T-01-27 | Tampering | XSS Dateiname/Ausschnitt | mitigate | nur `p()` in `php/templates/play.php`; JS ohne innerHTML/insertAdjacentHTML (grep leer); Gates `test_ui_assets.py:136,145,149` mit Selbsttests :309,:321 | closed |
| T-01-28 | Tampering | t-Parameter | mitigate | Muster `PageController.php:57`, Grenze 86400 :55, Auswertung :175-187 (sonst 0) | closed |
| T-01-29 | Elevation of Privilege | Download-Sperre | mitigate | kein eigener Stream, nur WebDAV-Adresse `PageController.php:147,283-288`; Hinweis aus Freigabe-Attribut :253-275 | closed |
| T-01-30 | Tampering | CSP | mitigate | keine `ContentSecurityPolicy`-Änderung in `php/lib` (grep leer), keine `blob:`/createObjectURL in `php/js` (grep leer); Gate `test_ui_assets.py:128` | closed |
| T-01-31 | Spoofing | Seite ohne Sitzung | mitigate | kein `PublicPage` in `php/lib` (grep leer, Gate Regel 2 `test_php_gates.py:14`); Route nur `NoAdminRequired`/`NoCSRFRequired` `PageController.php:122-124` | closed |
| T-01-32 | Elevation of Privilege | /admin/state, /admin/sample | mitigate | keine Lockerungsattribute `php/lib/Controller/SettingsController.php:53,77` (Admin + CSRF durch Nextcloud-Standard); Test `php/tests/Unit/SettingsControllerTest.php:183` | closed |
| T-01-33 | Tampering | Debug-Schalter | mitigate | 403 ohne debug `SettingsController.php:79-83`; Provider ignoriert Schalter ohne debug `Provider.php:222-223` | closed |
| T-01-34 | Information Disclosure | Banner/Initial-State | mitigate | `php/lib/Settings/Admin.php:44-58` (Zustand, Versionen, Zähler, debug-Flag), Fallback :84-89 | closed |
| T-01-35 | Tampering | /status-Werte im Template | mitigate | `VERSION_PATTERN` `ExAppService.php:152,900-903`; Ausgabe mit `p()` `php/templates/admin.php:107-113` | closed |
| T-01-36 | Spoofing | appVersion fremder Container | accept | siehe AR-01-03 | closed |
| T-01-37 | Elevation of Privilege | HandshakeController | mitigate | `php/lib/Controller/HandshakeController.php:42-49,67-79`; Gate Regel 1 `test_php_gates.py:280` | closed |
| T-01-38 | Information Disclosure | Handshake-Antwort | accept | siehe AR-01-04 | closed |
| T-01-39 | Denial of Service | periodische Prüfung | mitigate | `CHECK_INTERVAL_SECONDS = 300` `backend/src/audio_video_search_backend/companion.py:38,126`; Fehler gefangen :132; Test `backend/tests/test_handshake.py:265` | closed |
| T-01-40 | Information Disclosure | Logs Handshake | mitigate | `companion.py:114` nur Zustand/Grund/Status; Test `test_handshake.py:137-148` | closed |
| T-01-41 | Information Disclosure | CI-Artefakte | mitigate | Wegwerfinstanz, synthetische Medien `ci/make-testmedia.sh`, Passwörter als Job-Variablen `deploy-harp.yml:68`; keine Repo-Secrets in deploy-harp.yml | closed |
| T-01-42 | Information Disclosure | Logs (Testdateinamen) | mitigate | Abschlussprüfung `deploy-harp.yml:702-703` (grep der Testdateinamen in nextcloud.log und Container-Log) | closed |
| T-01-43 | Tampering | Workflow-Actions | mitigate | wie T-01-01: `test_workflow_pins.py:283` | closed |
| T-01-44 | Information Disclosure | Rechte-Parität | mitigate | mallory in OCS `deploy-harp.yml:443-444`, Playwright `ci/playwright/play.spec.ts:112,212` | closed |
| T-01-45 | Spoofing | Archiv-Signatur | mitigate | Pin `CERT_PUBKEY_SHA256` `.github/workflows/release.yml:56`, Prüfung :167-170,:242-245; Backend fail-closed `pending-certificate` :57,:230-232; Abbruch ohne Secret :191-193 | closed |
| T-01-46 | Information Disclosure | private Schlüssel | mitigate | Schlüssel nur über env und Datei mit umask 077 `release.yml`, kein xtrace, Löschen per shred, Repo-Prüfung; seit 15.11.2026 verlangt der erste Schritt für JEDES Ereignis einen Ref `refs/tags/vMAJOR.MINOR.PATCH` (Regex-Gate), ein workflow_dispatch von einem Branch-Ref bricht ab, bevor ein Secret angefasst wird | closed |
| T-01-47 | Tampering | Archivinhalt | mitigate | Einschlussliste und cmp `scripts/release/store-archive.sh`; Gates `backend/tests/test_release_archives.py:169,180,254,267` | closed |
| T-01-48 | Denial of Service | Upgrade-Datenverlust | mitigate | Gate gegen `--rm-data` `backend/tests/test_workflows.py:407-408,451-453`; Vorher/Nachher-Prüfung state.db `deploy-harp.yml:999,1006-1027` | closed |
| T-01-49 | Spoofing | Drift-Container | accept | siehe AR-01-05 | closed |
| T-01-50 | Information Disclosure | Push | mitigate | Owner-Freigabe je Push 01-11-SUMMARY.md:40,70; Geheimnis-Scan läuft in jeder CI `python.yml:161` (Läufe 01-11-SUMMARY.md:49,56 grün) | closed |
| T-01-51 | Repudiation | Commit-Identität | mitigate | `git log` über die ganze Historie: 396 Commits street1983nk <k.cherif@outlook.de>, 2 dependabot, keine Session-/closes-Zeilen (geprüft 2026-11-15) | closed |
| T-01-52 | Tampering | heruntergeladene Artefakte | accept | siehe AR-01-06 | closed |
| T-01-53 | Information Disclosure | Push auf phase-01 | mitigate | 01-12-SUMMARY.md:23,27 (Owner-Freigabe, Prüfung vor Push, 221 Tests grün inkl. `test_public_artifacts.py`) | closed |
| T-01-54 | Repudiation | Commit-Identität | mitigate | wie T-01-51; 01-12-SUMMARY.md:27 | closed |
| T-01-55 | Tampering | main | mitigate | `origin/main` (lokale Ref) hat 6 Commits ohne Phase-01-Arbeit, `bedbc13` ist kein Vorfahr von origin/main (geprüft 2026-11-15); 01-11-SUMMARY.md:40 | closed |
| T-01-56 | Tampering | Testtreffer in Produktion | mitigate | `docs/install.md:37,57`, `docs/install.en.md:34-40,57-60`, `docs/install.fr.md:37,57` (debug Pflicht, `--remove` einziger Löschweg) | closed |
| T-01-57 | Information Disclosure | Beispiele in der Doku | mitigate | nur Platzhalter `<fileId>` in `docs/install*.md:57`; Scan `test_public_artifacts.py:43-48` | closed |

*Status: open · closed*
*Disposition: mitigate (Umsetzung nötig) · accept (dokumentiertes Risiko) · transfer (an andere Komponente/Dritte)*

### Offene Threats (Schweregrad, nicht blockierend bei block_on high)

- **T-01-46 (niedrig):** Die Signaturschlüssel sind nicht an Tag-Läufe gebunden: `release.yml` nimmt auch `workflow_dispatch` von jedem Ref an (`.github/workflows/release.yml:26`, Prüfung :102 lässt `workflow_dispatch:*` durch) und signiert dann mit `APP_PRIVATE_KEY`. Voraussetzung ist Schreibrecht auf das Repo, das ohnehin einen Tag setzen könnte; Log-Schutz ist gleichwertig umgesetzt (env statt Kommandozeile, umask 077, kein `set -x`, Maskierung durch GitHub, `shred`). Vorschlag: Dispatch auf `refs/tags/v*` beschränken oder als akzeptiertes Risiko eintragen.
- **T-01-52 (niedrig):** Prozess-Mitigation ohne Artefakt-Beleg. Vorschlag: als akzeptiertes Risiko eintragen (Artefakte enthalten nur Screenshots und HTML-Report der Wegwerfinstanz) oder Ablage künftig in der SUMMARY nennen.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01-01 | T-01-04 | Lockstep der Versionen ist keine Authentisierung; Schutz über signierte AppAPI-Aufrufe (Findling T-05-25) | Planfreigabe 01-01; Owner einzeln bestätigt 15.11.2026 | 2026-11-15 |
| AR-01-02 | T-01-16 | appVersion aus der `/search`-Antwort steuert nur den Drift-Hinweis; der Pfad ist signiert | Planfreigabe 01-03; Owner einzeln bestätigt 15.11.2026 | 2026-11-15 |
| AR-01-03 | T-01-36 | appVersion eines fremden Containers: Lockstep ist keine Authentisierung, Pfad signiert | Planfreigabe 01-07; Owner einzeln bestätigt 15.11.2026 | 2026-11-15 |
| AR-01-04 | T-01-38 | Handshake-Antwort liefert nur `companionVersion` (`HandshakeController.php:59`), kein Personenbezug | Planfreigabe 01-08; Owner einzeln bestätigt 15.11.2026 | 2026-11-15 |
| AR-01-05 | T-01-49 | Drift-Container sind Wegwerf-Images der CI | Planfreigabe 01-10; Owner einzeln bestätigt 15.11.2026 | 2026-11-15 |
| AR-01-06 | T-01-52 | Prozessregel: heruntergeladene CI-Artefakte gehen nur ins Scratchpad und werden nie ausgeführt; Artefakte enthalten nur Screenshots und HTML-Report der Wegwerfinstanz | Owner akzeptiert 15.11.2026 | 2026-11-15 |

*Akzeptierte Risiken tauchen in späteren Audit-Läufen nicht erneut auf.*

---

## Threat Flags aus den SUMMARY-Dateien

| Flag | Quelle | Zuordnung |
|------|--------|-----------|
| Gateway, Provider, SampleCommand | 01-03-SUMMARY | T-01-10 bis T-01-15 (informativ) |
| Gateway-Strom, Eingabegrenzen, Logs, index_rev, Routenblock | 01-05-SUMMARY | T-01-19 bis T-01-24 (informativ) |
| Abspielseite | 01-06-SUMMARY | T-01-25 bis T-01-31 (informativ) |
| Admin-Routen | 01-07-SUMMARY | T-01-32 bis T-01-36 (informativ) |
| Handshake (Abschnitt "Threat-Abdeckung") | 01-08-SUMMARY | T-01-37, T-01-39, T-01-40 (informativ) |
| CI-Artefakte, Log-Prüfung, Pins, mallory, npm | 01-09-SUMMARY | T-01-41 bis T-01-44, T-01-SC (informativ) |
| `ci/admin-state.sh` holt App-Passwort der Wegwerfinstanz, maskiert per `::add-mask::` | 01-10-SUMMARY | unregistered_flag: kein Threat nennt das App-Passwort; nur Wegwerfinstanz, maskiert, keine Repo-Secrets (WARNING, nicht blockierend) |

---

## Escalations (außerhalb des Registers, nicht blockierend)

- **E-01-1 (mittel), PHP-Logs mit Exception-Objekt, BEHOBEN 15.11.2026:** alle neun Stellen (Phase 1 und 2) loggen jetzt `'class' => $e::class` statt `['exception' => $e]`; Meldung und Trace einer Exception erreichen nextcloud.log nicht mehr. Ursprünglicher Befund: Nextcloud schreibt bei `['exception' => $e]` Meldung und Trace der Exception in `nextcloud.log`; Bibliotheksmeldungen tragen dort Pfade, wie der Code selbst festhält (`php/lib/Controller/GatewayController.php:302-305`). Betroffen aus Phase 1: `GatewayController.php:305` (500-Zweig des Gateways), `php/lib/Search/Provider.php:247,272` (debug), `php/lib/Controller/SettingsController.php:58,99`, `php/lib/Settings/Admin.php:81`. Gate-Regel 6 (`test_php_gates.py`) prüft nur `getPath()`/`getName()`/`$path` im Logaufruf und fängt das nicht. Der Phase-3-Fix (Frames ohne Text) gilt nur für Python. Vorschlag: wie an den übrigen Stellen nur `'class' => $e::class` loggen.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-15 | 58 | 56 (davon 5 accept) | 2 | gsd-security-auditor (ASVS 2, block_on high), rückwirkend gegen HEAD dc742f7 |

---

## Sign-Off

- [x] Alle Threats haben eine Disposition (mitigate / accept / transfer)
- [x] Akzeptierte Risiken im Accepted Risks Log (Owner-Bestätigung ausstehend)
- [x] `threats_open: 0` bestätigt
- [ ] `status: verified` im Frontmatter gesetzt

**Approval:** verified 2026-11-15. Owner-Entscheide 15.11.2026: T-01-46 gefixt (release.yml Tag-Regex-Gate), T-01-52 akzeptiert (AR-01-06), AR-01-01 bis AR-01-05 einzeln bestätigt, E-01-1 behoben ('class' => $e::class an allen neun Stellen).
