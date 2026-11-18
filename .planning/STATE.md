---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: "Welle 1: 05-02/03/04/05/06 fertig (05-02: d200a5d, a7508a8, d5720c0, nur lokal); 05-01 Task 3 wartet auf die CI-Messung, dafür ist eine Owner-Freigabe für den Push nötig"
last_updated: "2026-11-18T12:25:00.000Z"
last_activity: 2026-11-18
progress:
  total_phases: 11
  completed_phases: 4
  total_plans: 106
  completed_plans: 88
  percent: 36
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-17)

**Core value:** Nach der Installation werden alle Audio- und Videodateien ohne Konfiguration lokal transkribiert und sind in der Nextcloud-Suche mit Zeitmarke findbar, mit der bestmöglichen Transkriptqualität, die auf der vorhandenen Hardware sicher läuft. Kein Inhalt verlässt den Server.
**Current focus:** Phase 5, Ressourcen, Profile und Modellbezug (Welle 1 in Ausführung)

## Current Position

Phase: 5 (Ressourcen, Profile und Modellbezug)
Plan: 05-02, 05-03, 05-04, 05-05, 05-06 fertig (Welle 1); 05-01 Task 3 offen (CI-Messung)
Status: Executing Phase 5
Last activity: 2026-11-18

Progress: [████████░░] 83%

## Performance Metrics

**Velocity:**

- Total plans completed: 83
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 13 | - | - |
| 2 | 26 | - | - |
| 3 | 25 | - | - |
| 4 | 19 | - | - |

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
| Phase 02 P04 | 75 min | 3 tasks | 8 files |
| Phase 02 P05 | 50 min | 2 tasks | 9 files |
| Phase 02 P06 | 45 min | 2 tasks | 7 files |
| Phase 02 P07 | 35 min | 2 tasks | 6 files |
| Phase 02 P08 | 70 min | 2 tasks | 8 files |
| Phase 02 P09 | 40 min | 2 tasks | 10 files |
| Phase 02 P10 | 50 min | 2 tasks | 11 files |
| Phase 02 P11 | 60 min | 3 tasks | 4 files |
| Phase 02 P12 | 75 min | 2 tasks | 14 files |
| Phase 04 P07 | 35min | 1 tasks | 3 files |
| Phase 04 P10 | 45 min | 3 tasks | 10 files |
| Phase 04 P08 | 45 min | 2 tasks | 5 files |
| Phase 04 P12 | 40 min | 2 tasks | 5 files |
| Phase 04 P09 | 50 min | 2 tasks | 6 files |
| Phase 04 P11 | 75 min | 3 tasks | 6 files |
| Phase 04 P13 | 35 min | 2 tasks | 5 files |
| Phase 04 P15 | 60 min | 2 tasks | 1 files |
| Phase 04 P16 | 45 min | 2 tasks | 9 files |
| Phase 04 P18 | 45min | 2 tasks | 12 files |
| Phase 05 P04 | 35 min | 2 tasks | 4 files |
| Phase 05 P05 | 60 min | 2 tasks | 17 files |
| Phase 05 P06 | 30 min | 2 tasks | 9 files |
| Phase 05 P01 | 30 min | 1 tasks | 3 files |
| Phase 05 P03 | 60 min | 2 tasks | 3 files |
| Phase 05 P02 | 150 min | 2 tasks | 14 files |

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
- [Phase 02]: 02-04: Gemeinsame Hilfen der Abnahme in ci/discovery/common.sh; Ledger vergisst Proben nur nach Ausschluss-Phasen
- [Phase 02]: 02-05: Intake quittiert nach dem Commit; HTTP der Warteschlange in nc.py, Vertrag in nc_queue.py; kein Claim vor companion ok
- [Phase 02]: 02-06: Erst-Crawl nur bei Backend ok/version_patch_differs (firstAdmin öffentlich); Cursor in avs_crawl, verlorener Crawl-Job wird vom Scheduler ersetzt
- [Phase 02]: 02-07: Cache-Ereignisse per Pfadendung vorgefiltert, Removed nur für die Mountmenge; gelöschter Nutzer nur Hinweis sweep_hint_at für den Sweep
- [Phase 02]: 02-08: Erfassung über eigenen Leser mit Claim-Identität (etag, size, mtime); Grund eines 403 im Header X-AVS-Reason; Wartezeit ab 60 s verdoppelt bis 6 h, fünf Versuche, access_control 300 s
- [Phase 02]: 02-09: Zählung nur lesend in store/coverage.py, Zähler und Nenner über aktive Verweise; dueWork nur active/unreadable; jede Container-Route per Gate in info.xml
- [Phase 02]: D-02-14 (Owner 07.11.): S3-Bein der Abnahme mit SeaweedFS 4.52 statt MinIO, nur CI
- [Phase 02]: 02-10: Gateway 403 access_control und 423 locked mit Header X-AVS-Reason, Kopf-Route über denselben resolve-Weg; occ :files/:status als erster Admin, feste Schlüssel, PHP-Listen per Python-Gate gleich denen des Containers
- [Phase 02]: 02-11: reason_77 (files_accesscontrol gibt 404 statt 403 access_control) in Plan 13 Task 3 (Owner 07.11.); Gateway unterscheidet, Container deutet 404 nie um
- [Phase 02]: 02-12: Klassifikationspflicht (avs_storage capturable 1) nur für ConfigAdapter-Speicher; Homes und Gruppenordner ohne Zeile zulässig
- [Phase 02]: 02-12: prefilter_key = sha256(sha256(share_key), Pfad in der Freigabe, Größe, storage_mtime); avs_storage hält nur den Hash des Freigabe-Schlüssels
- [Phase 02]: 02-12: occ :status meldet Sitzungs-Konfigurationen direkt aus oc_external_mounts, weil files_external im Hintergrund gescheiterte Mounts aus oc_mounts streicht
- [Phase 02]: 02-12: Neuprüfung neu sofort, credentials_missing und session_credentials jeden Lauf, sonst alle 24 h; 60 s Budget je SchedulerJob-Lauf
- [Phase 04]: 04-07: Cue-Schnitt bei Rang-Gleichstand nach Balance (kleinster Laengenunterschied), verhindert Rest-Cues unter 1 s
- [Phase 04]: 04-07: FAST-cps-Gate 0,98 statt 5-%-Schritt 1,00 (gemessen 0,9762), damit die Schwelle als Gate wirken kann
- [Phase 04]: 04-14: S7 auf zwei gemessenen FLEURS-DE-Clips (zwanzig/Polizisten/Polizeipräsidium; 12/Seitenverhältnis), Zielformen nur über fetch_speech.py --s7-env; Beifang-Container-Schritt entfällt, weil 04-06 die ngerman-Zählung mit Zahlen führt
- [Phase 04]: 04-13: README-Status nennt Suche und Untertitel-Entwurf als gebaut, aber unveröffentlicht; T-04-42 als Restrisiko in der öffentlichen SECURITY.md
- [Phase 04]: 04-10: UNKNOWN-Freigabe-Attribut sperrt den Export fail-closed mit derselben 403-T24-Seite wie BLOCKED; Wiedergabe bleibt fail-open
- [Phase 04]: 04-10: Spur-Route entfernt den von DataDisplayResponse gesetzten Content-Disposition-Header per addHeader(null), die Spur traegt keinen
- [Phase 04]: 04-08: ffmpeg-Erwartungswert = len(cues) + Pfeil-Textzeilen (check_ffmpeg zaehlt Pfeilzeilen der zurueckcodierten Ausgabe, ffmpeg schreibt Textzeilen woertlich zurueck); negativer Wortstart wird in build_cues auf 0 geklemmt
- [Phase 04]: 04-08: Messung 100k Woerter (12,6 h): Timeout 30 s bestaetigt; EXPORT_MAX_BODY_BYTES nach Formel 8 MiB statt 16 MiB aus 04-10, Entscheidung im Abgleichtest 04-09
- [Phase 04]: 04-12: BUSY (Sperre belegt) antwortet wie EXISTS mit 409 und Namen; isCreatable-Ausnahme zählt als nein (403 not_writable), sonstige Schreibausnahmen 503 {} (E7)
- [Phase 04]: 04-09: EXPORT_MAX_BODY_BYTES bleibt 16 MiB (24 h schnelle Rede mit Umlauten: Hülle 3,59 MB, x2 = 7,17 MB, 8 MiB nur 1,17x darüber); Timeout 30 s bleibt (100k Wörter VTT 0,45 s x8 = 3,6 s)
- [Phase 04]: 04-09: Wörter ohne sichtbares Zeichen zählen als ohne Wörter, /export und /export/meta antworten known false; to_vtt([]) erreicht die Route nie
- [Phase 04]: 04-11: exportState wertet die Download-Sperre vor dem Ausschluss aus (BLOCKED = X3 auch bei Ausschluss, UNKNOWN = X4); ein decide-Aufruf je Seite, Ausschluss-Befund aus excerpt() einmal gefragt
- [Phase 04]: 04-11: sidecarAllowed nur in X1/X2 gefragt (X4 byte-gleich); Zielname über 255 Bytes ergibt T20b und beim Klick E5
- [Phase 04]: 04-17: Seed mit Video S7-Übung.webm (S7_DE-Sprache, an review) und Ordner Ablage an carol (Rechte 15) für X5/E3/E4, weil eine Datei-Freigabe im Home der Empfängerin immer anlegen darf; X2 mit lang-40min-x2.ogg (eigene Bytes gegen Dedup)
- [Phase 04]: 04-17: E5 im Stack unerreichbar (Dateiname max. 250 Bytes, Nebendateiname max. 3 Bytes länger), Seitenteil per page.route; Kombifall/X4 über Nutzer-Regel, occ hat keine Datei-Regel
- [Phase 04]: 04-17 (Owner 16.11.): axe über @axe-core/playwright 4.14.0 exakt gepinnt (axe-core 4.14.0 im Lockfile, --before=2026-11-01, weil axe-core 4.14.1 erst am 16.11. erschien), Bereich #app-content.avs-play, WCAG 2.x A/AA, Filter serious/critical, Selbsttest
- [Phase 04]: 04-17 (Owner 16.11.): Export-Links tragen ?t= aus dem geprüften startMs (seconds(), unter 0,1 s keins), D2 prüft den Rückweg über den Link echt
- [Phase 04]: 04-17 (Owner 16.11.): Nebendatei bei Datei-Freigabe landet weiter im Home der Empfängerin
- [Phase 4]: 04-15: Push 2 (56f3627) auf phase-04 in allen vier Workflows grün, Discovery legs=all 6 x 22/22; debug-Prüfung gegen origin/phase-03
- [Phase 04]: 04-16 (Owner 16.11.): alle Prüfpunkte abgenommen (Lauf 43942105866); Spurmenü T31 ohne Bild akzeptiert; S7-Vertrag auf Polizei/Seite nachgezogen; X6-Hinweis und Bannerbreiten bleiben; Trefferzeilen-Ausschnitt S6/S7 ist Backlog
- [Phase 04]: 04-16 (Owner 16.11.): X3 setzt controlslist=nodownload am Medium, fail-closed wie der Export (jedes Urteil außer ALLOWED); nur Bedien-Hürde, keine technische Sperre
- [Phase 04]: 04-18 (Owner 17.11.): Untertitel-Dateinamen schreiben nur Umlaute und ß aus (auch NFD), andere Nicht-ASCII-Zeichen bleiben; Owner-Rückfrage am 17.11. entschieden (04-19-SUMMARY)
- [Phase 4, 17.11.]: Phase 4 abgeschlossen: 19/19 Pläne, UAT 14/14 (Gap Test 5 nach 04-18/04-19 geschlossen), 04-SECURITY.md verified mit threats_open 0, CI-Beleg Push 6 auf phase-04 ee6bd68 in allen vier Workflows grün
- [Phase 05]: 05-03: Whisper-Teile gemessen (turbo 2, large-v3 3 Teile zu 1 GiB), Identität in scripts/models/whisper-parts-2026-11.json; das Skript lädt nur über https von huggingface.co und Hosts unter .hf.co, die App-Allowlist bleibt ohne Hugging Face
- [Phase 05]: 05-02 (Owner 18.11.): faster-whisper 1.2.1, ctranslate2 4.8.5, onnxruntime 1.31.1 freigegeben und exakt gepinnt; Lock 53 auf 69 Pakete, alle bestehenden unverändert; Altersgrenze [tool.uv] exclude-newer 2026-11-05T00:00:00Z, einzige Ausnahme webvtt-py
- [Phase 05]: 05-02 (Owner 18.11.): httpx2-jsfetch 1.0 nur als Lock-Eintrag mit Marker emscripten, tzdata 2026.6 nur Dev unter Windows; test_lock_platforms.py hält beides
- [Phase 05]: 05-02: Netzverbot per Test: kein Import von huggingface_hub, hf_xet, httpx2, httpcore2 unter backend/src (auch nicht in engine/), WhisperModel nur mit Verzeichnis und local_files_only=True, download_model nirgends; Gegenprobe über frischen Interpreter (tests/hub_import_probe.py)
- [Phase 05]: 05-02: der TestClient von starlette läuft auf httpx2, sobald es installiert ist; Antworttyp in Tests über conftest.ClientResponse, Produktcode bleibt bei httpx in nc.py

### Pending Todos

- Zertifikat für `audio_video_search_backend` früh beantragen (Phase 1)
- Vor Phase 1 prüfen: viewer#2176/#3226, Tantivy vs. FTS5, Datei-Hash vs. PCM-Fingerabdruck

### Blockers/Concerns

- [Phase 4] requeue_too_long setzt kept_words, drop_*, speech_ms und version_id nicht zurück (deferred-items 04-05): vor Phase 6 (Veredelung) prüfen und entscheiden
- [Phase 4] Wortform-Lücke "Fischart" findet "Fischarten" nicht (deferred-items 04-14): noch nicht bewertet, bekannte Grenze benennen oder Analyzer mit Messung nachziehen
- [Phase 4] Backlog (Owner 16.11.): Trefferzeilen-Ausschnitt S6/S7 um den ersten Treffer zentrieren, Phase offen
- [Phase 4] phase-04 noch nicht nach main gemergt; Merge und Dependabot-PRs #3/#4 danach nur mit Owner-Freigabe
- [Phase 5] Push für Wave 0 offen: c796f4f hatte ein rotes lokales Gate (ruff I001, test_schedule.py); Owner entscheidet über den neuen SHA
- [Phase 5] 05-02: drei Commits nur lokal (d200a5d, a7508a8, d5720c0); der erste Linux-Bau mit der Whisper-Laufzeit und pip-audit laufen erst nach einem vom Owner freigegebenen Push
- [Phase 5] 05-02: exclude-newer 2026-11-05 bleibt im Projekt und bremst spätere Updates (auch Dependabot), bis der Owner die Grenze verschiebt
- [Phase 5] RES-06 und RES-07 stehen im Kopf von 05-02, sind aber erst mit 05-08/05-10 und 05-17 erfüllt; nicht abgehakt
- Sprachwechsel (Phase 7): Auslöser ungemessen, Messung vor Bau Pflicht
- arm64/Pi 5/N100 ungemessen: Profilvorwahl bis Phase 11 nur RAM-basiert
- Testrechner oft nur 4,5 bis 7 GB frei: Messungen seriell

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-11-18T12:25:00.000Z
Stopped at: Welle 1: 05-02/03/04/05/06 fertig (05-02: d200a5d, a7508a8, d5720c0, nur lokal); 05-01 Task 3 wartet auf die CI-Messung, dafür ist eine Owner-Freigabe für den Push nötig
Resume file: None
