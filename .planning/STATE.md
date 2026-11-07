---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 02-03-PLAN.md (Welle 1 fertig)
last_updated: "2026-11-07T10:08:00.542Z"
last_activity: 2026-11-07
progress:
  total_phases: 11
  completed_phases: 1
  total_plans: 35
  completed_plans: 16
  percent: 9
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-06)

**Core value:** Nach der Installation werden alle Audio- und Videodateien ohne Konfiguration lokal transkribiert und sind in der Nextcloud-Suche mit Zeitmarke findbar, mit der bestmöglichen Transkriptqualität, die auf der vorhandenen Hardware sicher läuft. Kein Inhalt verlässt den Server.
**Current focus:** Phase 2 — erfassung aller dateien

## Current Position

Phase: 2
Plan: 3 of 22 (planned, 11 waves)
Status: Ready to execute
Last activity: 2026-11-07

Progress: [█████░░░░░] 46%

## Performance Metrics

**Velocity:**

- Total plans completed: 13
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 13 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P01 | 40min | 3 tasks | 50 files |
| Phase 01 P02 | 9min | 2 tasks | 10 files |
| Phase 01 P03 | 45 min | 2 tasks | 11 files |
| Phase 01 P04 | 35 min | 2 tasks | 18 files |
| Phase 01 P05 | 60 min | 2 tasks | 23 files |
| Phase 01 P08 | 15 min | 2 tasks | 11 files |
| Phase 01 P09 | 55 min | 4 tasks | 10 files |
| Phase 02 P01 | 60 min | 2 tasks | 5 files |
| Phase 02 P02 | 40 min | 2 tasks | 13 files |
| Phase 02 P03 | 70 min | 2 tasks | 12 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Projektmodus mvp, "erst Risiko, dann vertikal"; Phase 1 = Zwei-App-Gerüst mit Dummy-Treffer und Abspielansicht ab `#t=`
- [Roadmap]: BITV-Weg (BITV-01 bis 06) in v1 als Phase 10, nach Suche/Export und Veredelung
- [Phase 1]: Transkript-Schema muss Nutzerkorrekturen als eigene Schicht tragen, die Veredelung und Neuberechnung übersteht (Vorbedingung BITV-01)
- [Phase 1]: Inhalts-Schlüssel, Provenienz und bedingtes Schreiben von Anfang an (teuerste Recovery)
- [Phase 1, Owner 06.11.]: Mobil-Treffer öffnen nativ (Attribute fileId + path, ab 0:00, kein Zeitsprung)
- [Phase 1, Owner 06.11.]: Lockstep zur Laufzeit: Major.Minor-Abweichung = Fehler mit Admin-Meldung, Patch-Abweichung = Hinweis; Build prüft exakt
- [Phase 1, Owner 06.11.]: Dummy-Treffer über den echten Weg (occ, Gateway, sha256) hinter Debug-Schalter
- [Phase 1, Owner 06.11.]: Vor dem Plan UI-Vertrag per /gsd:ui-phase 1
- [Phase 1, Recherche]: resourceUrl trägt `?t=` (übersteht Anmeldung), am Medium `#t=`; Tantivy 0.26.2 als abgeleiteter Index, SQLite Wahrheit; Schlüssel sha256 der Dateibytes, kein PCM-Fingerabdruck; Korrekturen an Audiozeit [start_ms, end_ms) + media_id
- [Phase 1]: Kein Feature-Wunsch an nextcloud-viewer ohne Owner-Freigabe
- [Phase 1, Owner 06.11.]: UI-SPEC-Fragen 1 bis 8 wie empfohlen (kein Autoplay, eigene Admin-Sektion, Deutsch unpersönlich de = de_DE, Kennzeichen "Testtreffer", Knopf "Zur Zeitstelle springen", Debug aus = ausblenden/Löschen nur per occ, App-Name unübersetzt/Gruppe "Audio und Video", Download-Sperre als Hinweis)
- [Phase 1, Owner 06.11.]: Früher Branch-Push nach Welle 2 auf phase-01 (nicht main), damit PHP-Tests früh in CI laufen; jeder Push nur nach Owner-Frage
- [Phase 1, Owner 06.11.]: Keine alte ExApp-Installation mit ID audio_video_search vorhanden, keine Kollision
- [Phase 1, Owner 06.11.]: wngerman (deutsche Komposita-Wortliste) noch in Phase 1 ins Container-Image, mit Test und CI-Beleg (aus deferred-items 01-05); Index baut sich danach einmal neu
- [Phase 01-01]: Env-Präfix der Backend-Variablen ist AVS_ (config.ENV_PREFIX)
- [Phase 01-01]: Backend-Image ohne LICENSE-Datei: Build-Kontext backend/, Lizenz im OCI-Label (wie Findling)
- [Phase 01-01]: .planning/ vom Strich-/Emoji-Gate ausgenommen (GSD-Statuszeichen)
- [Phase 01-01]: composer.lock wird in php.yml in CI aufgelöst und auditiert, nicht im Repo
- [Phase 01-01]: Lockstep-Gate prüft php-, backend-, image-tag- und pyproject-Version sowie das Server-Fenster gegen die deploy-harp-Matrix
- [Phase 1, 01-02]: 01-02: Epoche je media_id in media.epoch; publish_version weist prov.epoch < media.epoch ab; Plan 05 nimmt Epoche aus store.media_epoch
- [Phase 01]: 01-03: SAMPLE_TIMEOUT_SECONDS 120 s für /sample und /sample/remove, Suche bleibt bei 1,5 s
- [Phase 01]: 01-03: occ-Besitzerauflösung über FileAccess::ownerOf, getFirstNodeById nur in FileAccess.php
- [Phase 01]: 01-04: l10n_js.py prüft ohne --root beide Katalogwurzeln; Gate verlangt jedes t()-Literal der PHP-App in php/l10n
- [Phase 1]: 01-05: Trefferzeit = erstes passendes Wort im Segment (SearchIndex.first_match_ms), sonst Segmentbeginn
- [Phase 1]: 01-05: Index-Marken in meta (index_schema_version, index_analyzer mit Wortlisten-Digest, index_tantivy); Abweichung baut neue Generation index/gen-N aus SQLite
- [Phase 1]: 01-05: Eine Sperre (api.Services.lock) um alle Store- und Indexarbeit; Image braucht noch wngerman für Kompositazerlegung (deferred)
- [Phase 1]: 01-06: Abspielansicht spielt direkt über WebDAV (rawurlencode je Segment und UID), kein eigener Stream-Controller
- [Phase 1]: 01-06: Download-Sperre über ISharedStorage-Attribut permissions/download plus core shareapi_allow_view_without_download, sonst HEAD 403 in play.js; PLAY-01/02 erst nach E2E (Plan 09) abhaken
- [Phase 01]: 01-08: /sample sperrt nur bei bestätigtem companion missing; unknown wird einmal geprüft, danach meldet das Gateway
- [Phase 01]: 01-08: Companion missing nach 404 sofort oder nach drei Netzfehlern in Folge; /status fragt neu, wenn älter als 30 s
- [Phase 01]: 01-09: wngerman=20161207-15 im Image (Owner 06.11. erledigt), deploy-harp prüft im Container "frist" in "Kündigungsfrist"
- [Phase 01]: 01-09: Hoher Kontrast über Prüfnutzerin dora (admin + team), Projekt hc-1280 nur @screenshot; Instanz-Umbauten (@disabled, @unreachable, @nodebug) als eigene Workflow-Schritte
- [Phase 01]: 01-09: PHP-App vor der ExApp aktiviert, Workflow verlangt companion ok im /status; PLAT-03/PLAY-01/PLAY-02 erst nach grünem Lauf in Plan 11 abhaken
- [Phase 02]: 02-01: S3-Bein der Abnahme gegen SeaweedFS 4.52 per Digest, weil MinIO kein öffentliches Image mehr hat (Owner-Bestätigung vor Plan 11)
- [Phase 02]: 02-02: state.db Schema v2, Migration v1 nach v2 in einer Transaktion; Leser migrieren nie; Treffer nur aus active/sample; remove_sample löscht nur Probe-Zeilen
- [Phase 02]: 02-03: PHP-Warteschlange avs_queue mit Claim-Token, 900 s Sperrfrist, content/delete ersetzen einander; Mapper-Tests gegen echte DB, php.yml aktiviert dafür die App; Spalte last_file_id statt cursor

### Pending Todos

- Zertifikat für `audio_video_search_backend` früh beantragen (Phase 1)
- Vor Phase 1 prüfen: viewer#2176/#3226, Tantivy vs. FTS5, Datei-Hash vs. PCM-Fingerabdruck

### Blockers/Concerns

- Sprachwechsel (Phase 7): Auslöser ungemessen, Messung vor Bau Pflicht
- arm64/Pi 5/N100 ungemessen: Profilvorwahl bis Phase 11 nur RAM-basiert
- Testrechner oft nur 4,5 bis 7 GB frei: Messungen seriell

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-11-07T10:08:00.517Z
Stopped at: Completed 02-03-PLAN.md (Welle 1 fertig)
Resume file: None
