---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
verified: 2026-11-07T09:30:00Z
status: human_needed
score: 4/5 Erfolgskriterien verifiziert, 1 mit Owner-Entscheid (SC2 Gegenrichtung)
overrides_applied: 1
overrides:
  - must_have: "Fehlt die Gegen-App, ist sie nicht erreichbar oder hat sie eine andere Version, sieht der Admin eine klare Meldung statt eines stillen Ausfalls."
    reason: "Richtung Backend ohne PHP-App: statischer Pflichthinweis in ExApp-Beschreibung und Einstellungen, Container verweigert Arbeit (companion_missing); laut UI-SPEC so entschieden. Owner 07.11.: Hinweis umformuliert (settings.py, l10n de/en/fr), er stimmt jetzt auch ohne PHP-App: ohne die App aus dem App Store findet die Suche nichts, die Seite Verwaltung, Audio & Video Search wird erst für den Fall 'beide Apps installiert' genannt"
    accepted_by: "street1983nk"
    accepted_at: "2026-11-07T00:00:00Z"
gaps: []
deferred:
  - truth: "PLAT-01 'aus dem Store': signiertes Store-Archiv des Backends"
    addressed_in: "Phase 11 (Store-Release) und extern app-certificate-requests PR 1417"
    evidence: "Phase-11-Ziel: 'Vor dem Store-Release ist belegt ...'; release.yml:57 BACKEND_CERT_PUBKEY_SHA256 pending-certificate, release.yml:230 stoppt die Backend-Hälfte bewusst"
  - truth: "aktive Admin-Benachrichtigung bei companion_missing (Backend aktiv, PHP-App fehlt)"
    addressed_in: "Phase 9 (Ehrliche Admin-Zustände und Dreisprachigkeit)"
    evidence: "Owner-Entscheid 07.11.: in Phase 1 bleibt der statische Hinweis; der dynamische Zustand steht heute nur in /status und im Container-Log"
human_verification:
  - test: "PHP-App audio_video_search deaktivieren, Backend bleibt aktiv; als Admin die Einstellungsseite der ExApp audio_video_search_backend und die App-Verwaltung öffnen"
    expected: "Der Admin erkennt ohne Logblick, dass die PHP-App fehlt. Heute sieht er nur den statischen Satz 'braucht die App Audio & Video Search' (settings.py:39-42, info.xml summary/description); der dynamische Zustand companion=missing steht nur in /status und als Warnung im Container-Log"
    why_human: "Ob ein statischer Pflichthinweis als 'klare Meldung statt stiller Ausfall' (SC2, PLAT-02) genügt, ist ein Produktentscheid. UI-SPEC Z. 226 sieht ihn so vor, RESEARCH Z. 219 hielt eine Admin-Benachrichtigung als offen [ASSUMED]. Die ExApp-Einstellungsseite war nicht Teil der Screenshot-Abnahme vom 07.11."
---

# Phase 1: Zwei-App-Gerüst und Integrationsbeweis, Verifikationsbericht

**Phasenziel:** Der Admin installiert beide Apps, und ein Nutzer sieht einen (Dummy-)Treffer in der normalen Nextcloud-Suche, dessen Klick eine Abspielansicht genau an der Zeitstelle startet; die schwer umkehrbaren Datenentscheide sind getroffen und durch Tests belegt.
**Verifiziert:** 2026-11-07
**Status:** human_needed
**Re-Verifikation:** Nein, erste Verifikation
**Geprüfter Stand:** lokal 706eb46 = remote phase-01 bedbc13 plus nur 01-11-SUMMARY.md (git diff --stat geprüft)

Hinweis MVP-Modus: Die Phase trägt `mode: mvp`, das Ziel ist aber keine User Story im Format "As a ..., I want to ..., so that ..." (`gsd-sdk query user-story.validate`: valid=false). Auf ausdrücklichen Auftrag wurde trotzdem goal-backward gegen die fünf Roadmap-Kriterien geprüft; die Nutzerfluss-Tabelle unten ersetzt die MVP-Coverage.

## Nutzerfluss-Abdeckung

| Schritt | Erwartet | Beleg | Status |
|---------|----------|-------|--------|
| Admin installiert beide Apps | PHP-App per occ, ExApp über HaRP, NC 33/34/35, amd64/arm64 | Lauf 42347921936: 6/6 deploy-harp grün | VERIFIED |
| Nutzer sucht Dummy-Wort | Treffer in Unified Search mit Name, Zeitmarke, Ausschnitt | OCS-Schritt deploy-harp.yml:291-316 (subline "0:44 · ", t=44.4), Screenshot search-hit-w1280-dark (NC 33) | VERIFIED |
| Klick öffnet Abspielansicht | Route /play/{id}?t=44.4, WebDAV 206, Medium bei 44,4 s +- Toleranz | play.spec.ts:137-159, helpers.ts:204-217, 132 passed je Bein | VERIFIED |
| Ausschnitt in der Abspielansicht | Transkript-Ausschnitt sichtbar | templates/play.php:181-189, Screenshot play-w1280-light zeigt "Dies ist ein Testtreffer für die Audiosuche in Audio und Video" | VERIFIED (nur Bildbeleg, kein Assert) |

## Zielerreichung

### Beobachtbare Wahrheiten (Roadmap-Erfolgskriterien)

| # | Wahrheit | Status | Beleg |
|---|----------|--------|-------|
| 1 | Installation auf NC 33/34/35, amd64/arm64; CI belegt Lockstep und Upgrade beider Apps; Zertifikatsantrag gestellt | VERIFIED | `gh run view 42347921936`: deploy-harp stable33/34/35 x ubuntu-24.04/-arm alle success; upgrade stable33, stable34, stable35 (amd64), stable35-arm success (0.0.1 nach 0.1.0, state.db-Inode und Volume gleich, deploy-harp.yml Upgrade-Job Z. 846-864). Lockstep: test_lockstep_versions.py (info.xml beider Apps, image-tag, pyproject = 0.1.0, lokal grün). PR nextcloud/app-certificate-requests#1417 "Add certificate request for audio_video_search_backend", OPEN seit 06.11. |
| 2 | Fehlt die Gegen-App, ist sie nicht erreichbar oder anders versioniert: klare Meldung statt stillem Ausfall | UNCERTAIN (Teil Gegenrichtung) | PHP-Seite VERIFIED: ExAppService-Zustände, Playwright @disabled/@unreachable/@drift/@patch/@missing grün auf 6 Beinen, Screenshots admin-version_drift, admin-backend_missing usw. Gegenrichtung (PHP-App fehlt): Container erkennt es (companion.py:95-101, /status companion=missing, /sample antwortet companion_missing, CI Drift 4 deploy-harp.yml:483-512), der Admin sieht aber nur den statischen Pflichthinweis der ExApp (settings.py:39-42). Dieser verweist auf "Verwaltung, Audio & Video Search", eine Seite, die es ohne PHP-App gar nicht gibt. Owner-Entscheid nötig. |
| 3 | Dummy-Treffer mit Dateiname, Zeitmarke, Ausschnitt; Klick startet Abspielansicht per Range-Seek über WebDAV an der Zeitstelle (NC 33 bis 35, hell/dunkel, drei Breiten, Playwright) | VERIFIED | Provider.php entry(): Name, clock(startMs), Ausschnitt (max 120 Zeichen), Route mit t. playwright.config.ts: 375/768/1280 x light/dark plus HC und DE/FR. CI: 132 passed je Bein, keine skipped/failed. Owner-Abnahme 07.11. ("Approved", 01-11-SUMMARY). |
| 4 | Test-Transkript trägt Herkunft (Engine, Modell-sha256, Konfigurationsversion, Profilstufe) und Inhalts-Schlüssel; ältere Herkunft wird abgewiesen | VERIFIED | schema.sql transcript-Spalten engine, model_sha256, config_version, profile, level, epoch, input_file_sha256; media_key (file_sha256). repo.py:92-101 bedingtes UPSERT mit Zeilenwertvergleich (epoch, level, config_version). api/sample.py:77-95 schreibt die Herkunft auf dem echten Weg mit sha256 aus dem Strom. Tests test_provenance.py:154 (ältere Stufe mit höherer Config abgewiesen, keine Waisenzeilen), :167 (Gleichstand stale), :179 (Epoche). |
| 5 | Nutzerkorrekturen als eigene Schicht; Korrektur übersteht Ersatz durch besseres Maschinen-Transkript | VERIFIED | schema.sql Tabelle correction (an media_id und Audiozeit verankert, superseded_by); model/overlay.py; test_corrections.py:163 test_store_correction_survives_v2 ("der Haushaltsplan wurde beschlossen" nach V2), :181 übersteht auch eine stale-Abweisung. |

**Score:** 4/5 verifiziert, 1 wartet auf Owner-Entscheid

### Zurückgestellte Punkte

| # | Punkt | Zuständig | Beleg |
|---|-------|-----------|-------|
| 1 | Store-Veröffentlichung des Backends (Pin, Secret BACKEND_PRIVATE_KEY) | Phase 11 / PR 1417 | release.yml:57 `pending-certificate`, release.yml:230 bricht die Backend-Hälfte gezielt ab |
| 2 | reconcile über Terms-Aggregation, Sperre beim Neuaufbau | Phase 6 | deferred-items.md "Aus Plan 01-05" |

### Erforderliche Artefakte (Stichprobe der Kernstücke)

| Artefakt | Status | Details |
|----------|--------|---------|
| php/lib/Search/Provider.php | VERIFIED | IFilteringProvider, registriert in Application.php:32, Rechte-Recheck je Treffer über ReaderContext::actAs + FileAccess::readableFile, Testtreffer nur mit debug + Schalter |
| php/lib/Controller/PageController.php + templates/play.php + js/play.js | VERIFIED | WebDAV-URL, Download-Sperre, Ausschnitt-Zustände, Seek in play.js:37-59 |
| php/lib/Service/ExAppService.php | VERIFIED | searchAllowed() sperrt bei Drift (Provider.php search()) |
| php/lib/Controller/HandshakeController.php | VERIFIED | nur für EX-APP-ID des Backends (HandshakeControllerTest) |
| backend/src/.../store/repo.py, schema.sql | VERIFIED | siehe SC4/SC5 |
| backend/src/.../api/sample.py, search.py, excerpt.py, status.py | VERIFIED | im CI-Lauf über HaRP angesprochen |
| backend/src/.../companion.py | VERIFIED | Zustand ok/missing/unknown, periodisch 300 s |
| .github/workflows/deploy-harp.yml | VERIFIED | 6 Beine + Upgrade-Job, alle grün |

### Verdrahtung

| Von | Nach | Über | Status |
|-----|------|------|--------|
| Unified Search | Provider | registerSearchProvider (Application.php:32) | WIRED |
| Provider | Container /search | ExAppService::search, Ergebnis in entries() | WIRED |
| Treffer | Abspielansicht | linkToRouteAbsolute('audio_video_search.page.play', t) | WIRED (CI-URL-Assert) |
| Abspielansicht | WebDAV | davUrl(), 206 im CI | WIRED |
| Abspielansicht | Container /excerpt | ExAppService::excerpt | WIRED (Screenshot zeigt Text) |
| Container | PHP-Handshake | companion.check_once | WIRED (CI Drift 4) |
| occ sample | Container /sample | SampleCommand, sha256 im Strom | WIRED (OCS-Treffer nach Saat) |

### Datenfluss (Level 4)

| Artefakt | Daten | Quelle | Echte Daten | Status |
|----------|-------|--------|-------------|--------|
| Suchtreffer | hits | Container-Index (Tantivy aus SQLite) nach occ-Saat | ja, OCS liefert >= 2 Einträge für alice, 0 für mallory | FLOWING |
| Ausschnitt Abspielansicht | excerpt | Container /excerpt | ja, Text im Screenshot | FLOWING |
| Admin-Zustand | state, own, backend | ExAppService + /status | ja, Drift-Schritte prüfen per jq | FLOWING |

### Verhaltensprüfungen (lokal)

| Verhalten | Befehl | Ergebnis | Status |
|-----------|--------|----------|--------|
| Python-Tests | `uv run pytest -q` (backend/) | 389 passed | PASS |
| Coverage wie CI | `uv run pytest -q -rs --cov=...` | 95,88 % (Grenze 90 %), 29 ResourceWarnings | PASS mit Warnung |
| ruff check + format | `uv run ruff check . && uv run ruff format --check .` | grün | PASS |
| pyright | `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | 0 errors | PASS |
| vulture | `uv run vulture` | Exit 0 | PASS |
| REUSE | `uvx reuse lint` | 185/185 Dateien, konform | PASS |
| PHPUnit (CI) | Lauf 42347921902 | OK (136 tests, 670 assertions) | PASS |
| Playwright (CI) | Lauf 42347921936 | 132 passed je Bein plus Zustandsläufe, 0 skipped/failed | PASS |

### Probe-Ausführung

Keine `scripts/*/tests/probe-*.sh` vorhanden und keine in PLAN/SUMMARY deklariert. Übersprungen.

### Anforderungsabdeckung

| Anforderung | Beschreibung | Status | Beleg |
|-------------|--------------|--------|-------|
| PLAT-01 | Zwei Apps aus dem Store, Lockstep, Upgrade-Beweis in CI | SATISFIED (Store-Veröffentlichung deferred) | SC1 |
| PLAT-02 | Klare Meldung bei fehlender/unerreichbarer/anders versionierter Gegen-App | NEEDS HUMAN (Gegenrichtung) | SC2 |
| PLAT-03 | NC 33/34/35, AppAPI/HaRP, amd64/arm64, nur CPU | SATISFIED | 6/6 Beine |
| PLAY-01 | Abspielansicht startet an Zeitstelle, zeigt Ausschnitt | SATISFIED | SC3, Screenshot |
| PLAY-02 | Seek über WebDAV, NC 33 bis 35, hell/dunkel, drei Breiten | SATISFIED | SC3, Owner-Abnahme 07.11. |
| TRANS-06 | Herkunft je Transkript, veraltet überschreibt nie neuer | SATISFIED (bereits Complete) | SC4 |

Keine verwaisten Anforderungen: REQUIREMENTS.md ordnet Phase 1 genau diese sechs IDs zu.

### Gefundene Auffälligkeiten

| Datei | Zeile | Muster | Schwere | Wirkung |
|-------|-------|--------|---------|---------|
| php/templates/admin.php, php/templates/play.php | 34, 28 | MDI-Pfaddaten unter Apache-2.0, aber REUSE.toml:8-12 deklariert alles als AGPL-3.0-or-later, LICENSES/ enthält kein Apache-2.0.txt, README nennt MDI nicht | WARNING | Lizenzhinweis für Drittbestandteil fehlt; vor Store-Release nachziehen |
| REUSE.toml | 16 | Override-Pfad `docker/start.sh` existiert nicht (Datei liegt unter backend/docker/start.sh) | INFO | wirkungslos; start.sh trägt den Nextcloud-Copyright selbst im Kopf (reuse spdx geprüft) |
| backend/tests/test_store_schema.py | 18-19 | `_raw()` gibt sqlite3-Verbindungen zurück, die per `with` nie geschlossen werden (sqlite3-Kontextmanager committet nur) | WARNING (nur Tests) | Quelle der ResourceWarnings "unclosed database"; eingegrenzt: nur test_store_schema/test_provenance/test_corrections erzeugen sie, der Rest läuft ohne Warnung |
| backend/tests/test_provenance.py | 133 | dto. `with sqlite3.connect(path)` | WARNING (nur Tests) | dto. |
| backend/tests/test_corrections.py | 210 | dto. | WARNING (nur Tests) | dto. |
| backend/src/audio_video_search_backend/settings.py | 39-42 | Beschreibung verweist auf "Verwaltung, Audio & Video Search", die ohne PHP-App nicht existiert | WARNING | Teil des Owner-Entscheids SC2 |
| ci/playwright/play.spec.ts | 137-159 | Kein Assert auf den Ausschnitt-Text der Abspielansicht | INFO | nur per Screenshot und PlayControllerTest belegt |
| .github/workflows/security.yml | 5-10 | REUSE/CodeQL laufen nur auf main und PR, nicht auf phase-01 | INFO | lokal nachgeprüft, konform |
| php/tests/Unit/.gitkeep | - | überflüssig, Ordner hat Tests | INFO | keine |

Keine TBD/FIXME/XXX in getrackten Dateien außerhalb .planning (`git grep`).

### Menschliche Prüfung nötig

#### 1. Meldung bei fehlender PHP-App

**Test:** PHP-App `audio_video_search` deaktivieren, Backend aktiv lassen; als Admin die Einstellungsseite der ExApp und die App-Verwaltung ansehen.
**Erwartet:** Der Admin erkennt, dass die PHP-App fehlt und die Suche deshalb nichts tut.
**Ist-Stand:** Nur statischer Pflichthinweis (settings.py:39-42); dynamischer Zustand nur in /status und Container-Log.
**Warum menschlich:** Produktentscheid, ob das genügt (UI-SPEC Z. 226 so vorgesehen) oder ob ein dynamischer Hinweis bzw. eine Admin-Benachrichtigung nachgezogen wird. Wird es akzeptiert, als Override eintragen:

```yaml
overrides:
  - must_have: "Fehlt die Gegen-App, ist sie nicht erreichbar oder hat sie eine andere Version, sieht der Admin eine klare Meldung statt eines stillen Ausfalls."
    reason: "Richtung Backend ohne PHP-App: statischer Pflichthinweis in ExApp-Beschreibung und Einstellungen, Container verweigert Arbeit (companion_missing); laut UI-SPEC so entschieden"
    accepted_by: "street1983nk"
    accepted_at: "2026-11-07T00:00:00Z"
```

### Zusammenfassung

Das Phasenziel ist im Code erreicht: beide Apps installieren sich auf sechs Beinen, ein Dummy-Treffer läuft über den echten Weg (occ-Saat, Container-Index, Provider mit Rechte-Recheck) in die Unified Search, der Klick startet die Abspielansicht per WebDAV-Range an 0:44, und die Datenentscheide (Inhalts-Schlüssel, Herkunft mit bedingtem Schreiben, Korrektur-Schicht) sind durch Tests belegt. Kein Blocker. Offen ist ein Owner-Entscheid zur Gegenrichtung von PLAT-02 sowie zwei kleine Lizenz-/Testhygiene-Punkte (MDI-Apache-2.0-Hinweis, ungeschlossene sqlite3-Verbindungen in drei Testdateien).

---

_Verifiziert: 2026-11-07_
_Verifier: Claude (gsd-verifier)_
