# Walking Skeleton: Audio & Video Search

**Phase:** 1
**Generated:** 2026-11-06

## Capability Proven End-to-End

Ein Admin installiert die PHP-App `audio_video_search` und die ExApp `audio_video_search_backend` auf NC 33, 34 oder 35 (amd64 oder arm64), legt per `occ audio_video_search:sample <fileId>` einen Testtreffer über den echten Weg an (Gateway, sha256 im Strom, SQLite, Tantivy), und ein Nutzer findet das Testwort "Audiosuche" in der normalen Nextcloud-Suche; der Klick öffnet `/apps/audio_video_search/play/{fileId}?t=42.0`, und das Medium steht per Range-Seek über WebDAV an der Zeitstelle.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| App-Aufteilung | PHP-App `audio_video_search` (Suche, Rechte, Abspielansicht, Admin, Gateway, Handshake) + ExApp `audio_video_search_backend` (SQLite, Tantivy, später Dekodieren und Erkennung) | Nur PHP kann `registerSearchProvider`; Rechenarbeit gehört in den Container (RESEARCH Architekturkarte) |
| Repo-Layout | `php/` (Findling-Layout, Namespace `OCA\AudioVideoSearch`), `backend/` (Python-Paket `audio_video_search_backend`, `backend/tests/` enthält alle Python-Gates inkl. Repo-weiter Prüfungen), `ci/playwright/` (nur CI), `scripts/` (Repo-Werkzeuge) | Findling-Muster, Lockstep-Test liest `php/appinfo/info.xml` und `backend/appinfo/info.xml` |
| Lockstep | Eine Versionsnummer in `php/appinfo/info.xml`, `backend/appinfo/info.xml` (`<version>` und `<image-tag>`), `backend/pyproject.toml`, Git-Tag; Build-Gate exakt; Laufzeit Major.Minor ungleich = Fehler, Patch ungleich = Hinweis | Owner 06.11. |
| Gegen-App-Zustand | `ExAppService::backendState()` mit `no_app_api`, `backend_missing`, `backend_disabled`, `backend_unreachable`, `version_drift`, `version_patch_differs`, `ok` über `PublicFunctions::getExApp()` + `/status`; Gegenrichtung Container ruft `GET /ocs/v2.php/apps/audio_video_search/api/v1/handshake` | PLAT-02, RESEARCH Entscheid 6 |
| Daten-Wahrheit | SQLite WAL `$APP_PERSISTENT_STORAGE/state.db`, Tabellen `meta`, `media`, `media_key`, `file_ref`, `transcript`, `word`, `current`, `correction`, `index_outbox`; `meta.schema_version = 1` | RESEARCH Entscheid 2 bis 5 |
| Inhalts-Schlüssel | `media_key(kind='file_sha256', value)` auf Ersatzschlüssel `media_id`; sha256 der Dateibytes im Gateway-Strom; Vorfilter `(file_id, etag, size)` in `file_ref`; kein PCM-Fingerabdruck | FATE-Toleranzen, RESEARCH Entscheid 3 |
| Provenienz | Pflichtfelder `engine`, `model_sha256`, `config_version`, `profile`, `level`, `epoch`, `language`, `input_file_sha256`; Ordnung `(epoch, level, config_version)`; bedingter UPSERT auf `current`, `changes() = 0` heißt `stale_rejected` | TRANS-06, RESEARCH Entscheid 5 |
| Korrektur-Schicht | Tabelle `correction` an `media_id` und Audiozeit `[start_ms, end_ms)` in ganzen ms; Überlagerung beim Lesen per Mittelpunktregel (`model/overlay.py::effective_words`) | Vorbedingung BITV-01, RESEARCH Entscheid 4 |
| Suchindex | Tantivy 0.26.2, abgeleitet und jederzeit aus SQLite neu baubar; Felder `media_id`, `index_rev`, `seg_idx`, `start_ms`, `body_de`, `body_en`, `body_fr`; nur `index/open.py` öffnet; Suche übernimmt nur Treffer mit `index_rev` gleich `current.index_rev` oder `current.index_rev - 1` (je `media_id` die höchste), `index_outbox` + Anlauf-Abgleich | RESEARCH Entscheid 2, Pattern 3; Planer-Festlegung des Tauschfensters |
| Abspielansicht | PHP-Template `play.php` mit nativem `<video>`/`<audio>` auf `/remote.php/dav/files/{uid}/{pfad}#t={s}`; `resourceUrl` trägt `?t=`; kein eigener Stream-Controller, kein Autoplay, kein Bundler | RESEARCH Entscheid 1, UI-SPEC Fläche 2 |
| Suchtreffer | Provider-ID `audio_video_search`, Gruppenname "Audio und Video", `subline` = `m:ss · Ausschnitt`, Attribute `fileId` + `path` (Mobil nativ ab 0:00), Rechte-Recheck je fileId zur Abfragezeit | RESEARCH Entscheid 7, Owner 06.11. |
| Testtreffer | `occ audio_video_search:sample <fileId> [--at=<s>]` zum Anlegen und `--remove` zum Entfernen (nur per occ, UI-SPEC Entscheid 6), beides nur mit `config.php` `debug => true`; Stufe `sample` (level 1) wird von jeder echten Stufe verdrängt; Schalter `sample_visible` in IAppConfig | Owner 06.11. |
| Auth | Nextcloud-Sitzung für Seite und WebDAV (GET ohne CSRF); PHP nach Container nur signiert über `PublicFunctions::exAppRequest`; Container nach PHP nur `#[ExAppRequired]` + `EX-APP-ID`-Prüfung | ASVS V2/V4 |
| Env-Präfix Container | `AVS_` (z. B. `AVS_LOG_LEVEL`) | Planer-Festlegung (RESEARCH Runtime State) |
| Deployment / Lauf | Kein lokaler Stack (RAM). Voller Lauf in CI: `deploy-harp.yml` mit HaRP, Matrix NC 33/34/35 x amd64/arm64, beide Apps, Testmedien per ffmpeg im Runner, Playwright `ci/playwright/`; Push nur nach Owner-Freigabe; früher Push auf Branch `phase-01` nach Welle 2 für phpunit (Owner 06.11.) | Owner-Regeln |

## Stack Touched in Phase 1

- [ ] Project scaffold: `php/` mit composer/phpunit, `backend/` mit uv, ruff, pyright, vulture, pytest; CI `python.yml`, `php.yml`, `docker.yml`, `deploy-harp.yml`
- [ ] Routing: PHP `GET /apps/audio_video_search/play/{fileId}`, OCS Gateway und Handshake, Admin-Routen; Container `/status`, `/search`, `/sample`, `/excerpt`
- [ ] Database: echtes Schreiben (Saat: `media`, `media_key`, `file_ref`, `transcript`, `word`, `current`) und echtes Lesen (`/search`, `/excerpt` über `effective_words`)
- [ ] UI: Unified-Search-Treffer, Abspielansicht mit Sprungknopf, Admin-Statusbereich mit "Erneut prüfen" und Debug-Schalter
- [ ] Deployment: CI-Lauf `deploy-harp.yml` auf sechs Beinen inkl. Upgrade 0.0.1 nach 0.1.0 und Drift-Schritten

## Out of Scope (Deferred to Later Slices)

- Erfassung aller Dateien, Ereignisse, Crawl, Ausschlüsse (Phase 2)
- Echte Transkription, Medien-Eingang mit ffmpeg, Kennzeichen "vorläufig" (Phase 3)
- Suchfilter `since/until/title-only`, Export SRT/VTT/TXT, Untertitelspur (Phase 4)
- RAM-Wächter, Profile, Modell-Download (Phase 5)
- Veredelung, Lasttest "Suche während des Tauschs" (Phase 6)
- Korrektur-Editor, Status "geprüft" (Phase 10); in Phase 1 nur Schema und Überlagerung
- Medienübersicht, Navigationseintrag, Feature-Wunsch an nextcloud-viewer
- Erster Store-Upload (Phase 11)

## Subsequent Slice Plan

- Phase 2: Arbeitsvorrat kennt alle Audio- und Videodateien (schreibt `file_ref`, nutzt `media_key`)
- Phase 3: Vorschau-Transkripte (level 100) ersetzen den Testtreffer über denselben Veröffentlichungsweg
- Phase 4: Suchqualität und Export (liest `effective_words`)
- Phase 5: Ressourcen, Profile, Modellbezug
- Phase 6: Veredelung (level 200/300, bedingter UPSERT, Index-Tausch)
- Phase 7: Sprachen und Sprachwechsel
- Phase 8: Lebenszyklus und DSGVO
- Phase 9: Ehrliche Admin-Zustände (erweitert den Admin-Statusbereich)
- Phase 10: BITV-Weg (Editor schreibt `correction`)
- Phase 11: Release-Gate, Hardware-Messung, Volltest
