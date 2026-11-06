# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-06)

**Core value:** Nach der Installation werden alle Audio- und Videodateien ohne Konfiguration lokal transkribiert und sind in der Nextcloud-Suche mit Zeitmarke findbar, mit der bestmöglichen Transkriptqualität, die auf der vorhandenen Hardware sicher läuft. Kein Inhalt verlässt den Server.
**Current focus:** Phase 1: Zwei-App-Gerüst und Integrationsbeweis

## Current Position

Phase: 1 of 11 (Zwei-App-Gerüst und Integrationsbeweis)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-11-06: Roadmap erstellt (11 Phasen, 69/69 Anforderungen zugeordnet)

Progress: [░░░░░░░░░░] 0%

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

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Projektmodus mvp, "erst Risiko, dann vertikal"; Phase 1 = Zwei-App-Gerüst mit Dummy-Treffer und Abspielansicht ab `#t=`
- [Roadmap]: BITV-Weg (BITV-01 bis 06) in v1 als Phase 10, nach Suche/Export und Veredelung
- [Phase 1]: Transkript-Schema muss Nutzerkorrekturen als eigene Schicht tragen, die Veredelung und Neuberechnung übersteht (Vorbedingung BITV-01)
- [Phase 1]: Inhalts-Schlüssel, Provenienz und bedingtes Schreiben von Anfang an (teuerste Recovery)

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

Last session: 2026-11-06
Stopped at: Roadmap und STATE angelegt, Traceability in REQUIREMENTS.md gefüllt
Resume file: None
