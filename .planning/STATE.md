---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Roadmap und STATE angelegt, Traceability in REQUIREMENTS.md gefüllt
last_updated: "2026-11-06T12:53:04.567Z"
last_activity: 2026-11-06
progress:
  total_phases: 11
  completed_phases: 0
  total_plans: 13
  completed_plans: 2
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-06)

**Core value:** Nach der Installation werden alle Audio- und Videodateien ohne Konfiguration lokal transkribiert und sind in der Nextcloud-Suche mit Zeitmarke findbar, mit der bestmöglichen Transkriptqualität, die auf der vorhandenen Hardware sicher läuft. Kein Inhalt verlässt den Server.
**Current focus:** Phase 01 — Zwei-App-Gerüst und Integrationsbeweis

## Current Position

Phase: 01 (Zwei-App-Gerüst und Integrationsbeweis) — EXECUTING
Plan: 3 of 13
Status: Ready to execute
Last activity: 2026-11-06

Progress: [██░░░░░░░░] 15%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P01 | 40min | 3 tasks | 50 files |
| Phase 01 P02 | 9min | 2 tasks | 10 files |

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
- [Phase 01-01]: Env-Präfix der Backend-Variablen ist AVS_ (config.ENV_PREFIX)
- [Phase 01-01]: Backend-Image ohne LICENSE-Datei: Build-Kontext backend/, Lizenz im OCI-Label (wie Findling)
- [Phase 01-01]: .planning/ vom Strich-/Emoji-Gate ausgenommen (GSD-Statuszeichen)
- [Phase 01-01]: composer.lock wird in php.yml in CI aufgelöst und auditiert, nicht im Repo
- [Phase 01-01]: Lockstep-Gate prüft php-, backend-, image-tag- und pyproject-Version sowie das Server-Fenster gegen die deploy-harp-Matrix
- [Phase ?]: 01-02: Epoche je media_id in media.epoch; publish_version weist prov.epoch < media.epoch ab; Plan 05 nimmt Epoche aus store.media_epoch

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

Last session: 2026-11-06T12:52:58.311Z
Stopped at: Roadmap und STATE angelegt, Traceability in REQUIREMENTS.md gefüllt
Resume file: None
