# Phase 3: Vorschau-Transkripte in der Suche - Context

**Gathered:** 2026-11-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Erfasste Audio- und Videodateien (Arbeitsvorrat aus Phase 2) werden gehärtet dekodiert und mit Parakeet-TDT-0.6B-v3 int8 (Schluck-Wächter, VAD immer an, Abfangregel) zu einem Vorschau-Transkript gerechnet. Der gesprochene Text ist über die bestehende Unified-Search-Anbindung findbar: Zeitmarke, Ausschnitt, mehrere Stellen je Datei, Kennzeichen "vorläufig", wortgenauer Sprung auf der Abspielseite, Rechteprüfung zur Abfragezeit. Anforderungen: MEDIA-01 bis 04, TRANS-01, 02, 03, 07, 08, SRCH-01 bis 03.

Nicht in dieser Phase: besseres Transkript (turbo/large-v3, ROVER, Profile), Sprachwechsel-Nachrechnen, Wortformen/Komposita/Filter (Phase 4), Export, voller cgroup-Wächter (Phase 5), Admin-Oberfläche (Phase 9).

</domain>

<decisions>
## Implementation Decisions

### Trefferbild in der Suche
- **D-03-01:** Eine Ergebniszeile je Stelle (wie der bestehende Provider): jede Zeile mit eigener Zeitmarke, eigenem Ausschnitt und eigenem Sprung-Link. Keine Zusammenfassung je Datei.
- **D-03-02:** Höchstens 3 Stellen je Datei pro Ergebnisseite, danach kommt die nächste Datei; weitere Stellen über die Paginierung der Unified Search ("Mehr laden"), ohne Dubletten und ohne Lücken über Seiten hinweg.
- **D-03-03:** Kennzeichen "vorläufig" als Wort im Untertitel, gleiche Form wie das bestehende "Test result": `1:23 · Vorläufig · Ausschnitt` (DE/EN/FR, l10n). Das Dateityp-Icon bleibt.
- **D-03-04:** Die Abspielseite zeigt bei einem Vorschau-Transkript einen kurzen Hinweis (sinngemäß "Vorläufiges Transkript, wird automatisch verbessert"), dreisprachig. Nachtrag Owner 14.11.2026 (UI-Vertrag): T2 lautet "Vorläufiges Transkript. Es kann Fehler enthalten." ohne Verbesserungsversprechen; maßgeblich sind die freigegebenen Texte T1 bis T11 in 03-UI-SPEC.md.

### Reihenfolge der Arbeit
- **D-03-05:** Neue und geänderte Dateien (Ereignisweg) zuerst, danach der Altbestand nach Änderungsdatum, neueste zuerst.
- **D-03-06:** Ein neuer Upload darf eine lange Datei unterbrechen, aber nur an der Stückgrenze: das laufende ca. 10-min-Stück wird fertig gerechnet und gesichert, dann kommt der neue Upload dran, danach geht die lange Datei am nächsten Stück weiter (gleicher Mechanismus wie das Fortsetzen nach Neustart, TRANS-07).
- **D-03-07:** Teile einer langen Datei sind je fertigem Stück findbar (als vorläufig), nicht erst nach der ganzen Datei. Die Rechte- und Zustandsregeln aus Phase 2 gelten für Teiltreffer unverändert.

### Grenzen und Spurwahl
- **D-03-08:** Höchstdauer 12 Stunden Spieldauer; länger wird mit Grund "überlang" übersprungen (nicht still).
- **D-03-09:** Die Höchstdauer ist eine Admin-Einstellung (Standard 12 h). Wird sie erhöht, kommen zuvor wegen Überlänge übersprungene Dateien zurück in den Arbeitsvorrat. In Phase 3 über den bestehenden Einstellungsweg (deklarative Einstellung bzw. occ), die eigentliche Admin-Oberfläche bleibt Phase 9.
- **D-03-10:** Tonspur: die im Container als Standard (default disposition) markierte Audiospur, sonst die erste Audiospur. Fest, ohne Erkennungslauf. Zeitachse muss auch bei Edit-Lists stimmen (MEDIA-02).

### Ohne Sprache / fremde Sprache
- **D-03-11:** Schwelle für "keine Sprache" wird nicht geraten, sondern in der Research am Medienkorpus (Musik, Gesang, Stille, Rauschen, kurze Sprachmemos) gemessen (z. B. VAD-Sprachanteil und Wortzahl nach Abfangregel) und dann festgelegt. Ein kurzes echtes Sprachmemo darf nicht als "keine Sprache" enden; Messung als Beleg im Plan.
- **D-03-12:** Gemischte Dateien: Teiltranskript behalten. Segmente in Instanz-Sprachen bleiben findbar, fremde Segmente fallen durch die Abfangregel (TRANS-03) weg. "Sprache nicht unterstützt" nur, wenn praktisch nichts übrig bleibt (Schwelle ebenfalls messen).
- **D-03-13:** Gründe (keine Sprache, übersprungen mit Grund, Sprache nicht unterstützt, überlang) sieht der Admin per occ (Admin-Status ohne Dateinamen, Entscheid 06.11.), der Nutzer auf der Abspielseite seiner Datei statt "kein Transkript". Die Abspielseite zeigt den Grund nur unter denselben Rechte- und Ausschlussregeln wie bisher (D-02-15c, D-02-16): für jeden nicht erlaubten Verweis antwortet sie wie für eine Datei ohne Transkript.
- **D-03-14:** Instanz-Sprachen für die Abfangregel in Phase 3 fest DE/EN/FR. Admin-Einschränkung erst später zusammen mit den Profilen.

### Übernommen aus früheren Entscheiden (nicht neu verhandelt)
- VAD immer an, kein Abschaltweg; Spike-3-Standardwerte Abschnitt 11 als Konstanten mit Test.
- Treffer und Ausschnitt nur über Verweise mit state active (D-02-01a, D-02-15c), Probe-Regeln D-02-15/15a/Nachtrag, Ausschluss D-02-04/08/16, Lesebeweis ohne Abschaltweg D-02-10.
- Kein Inhalt verlässt den Server; Parakeet und Silero über eigenen Downloader mit festem sha256.

### Owner-Entscheide nach der Research (14.11.2026)
- **D-03-15:** "Mehr laden": Gibt es zu wenig Treffer-Dateien, wird die Seite mit weiteren Stellen derselben Datei aufgefüllt (Stufen zu je 3 Stellen je Datei, PHP füllt auf genau `limit` auf), damit "Mehr laden" erscheint und keine Stelle unerreichbar bleibt. Präzisiert D-03-02.
- **D-03-16:** Zweiter VAD-Durchgang mit Schwelle 0,3 (Mindestsprache 0,1 s) nur für Dateien bis 60 s, die im ersten Durchgang kein behaltenes Wort hatten. VAD bleibt immer an; die Schwelle ist eine feste Konstante mit Test, kein Schalter.
- **D-03-17:** Keine eigene Größengrenze mehr (der alte Standard 100 MB entfällt); maßgeblich ist die Höchstdauer 12 h (D-03-08). Vor dem Ablegen der Temp-Datei wird freier Plattenplatz geprüft; reicht er nicht, wird mit Grund "zu wenig Speicherplatz" übersprungen und später erneut versucht. Dieser Grund braucht einen neuen Text (DE/EN/FR) auf der Abspielseite: dem Owner vor dem Bau zeigen und in 03-UI-SPEC.md nachtragen.
- **D-03-18:** Neue Laufzeitabhängigkeit py3langid 0.4.0 (BSD-3, nur numpy) für die Text-Sprachkennung der Abfangregel; Herkunft, Lizenz und Wheels für amd64/arm64 vor dem Einbau prüfen, exakt pinnen.
- **D-03-19:** TRANS-03 gilt mit der gemessenen Parakeet-Regel aus 03-RESEARCH.md (Schrift unter 50 % lateinisch, Text-Sprache außerhalb DE/EN/FR mit p >= 0,9 und mindestens 3 Wörtern, Wortkonfidenz-Schwellen 0,6 bzw. 0,5) und dem Dateiurteil aus der Research; Anforderungstext angepasst.
- Die Messskripte liegen unter `scripts/research/phase3/` (ohne Audiodaten); lokale Pfade (ffmpeg) vor jedem Push durch Parameter ersetzen.

- **D-03-20 (Owner 14.11.2026, nach Plan 03-05):** Führt Nextcloud eine Datei als Audio/Video, ffmpeg findet darin aber nichts Lesbares (auch wenn der Demuxer der Temp-Datei, z. B. "bin", von der Positivliste abgelehnt wird), lautet der Grund "damaged" (T6, beschädigt), nicht "format_unsupported". Umsetzung in Plan 03-13; der Worker muss außerdem mit duration_ms None umgehen.

- **D-03-21 (Owner 14.11.2026, nach Plan 03-07):** Modellquelle ist ein EIGENES GitHub-Release (Repo street1983nk/nextcloud-audio-video-search) mit Parakeet-Dateien (encoder, decoder, joiner, tokens; CC-BY-4.0, Namensnennung NVIDIA im Release und in der Doku) und silero_vad.onnx (MIT) als Assets, statt Hugging Face. Grund: Hugging Face leitet je nach Region auf wechselnde CDN-Hosts weiter (gemessen us.aws.cdn.hf.co), eine feste Host-Allowlist würde in anderen Regionen scheitern. Allowlist danach nur github.com und release-assets.githubusercontent.com (vor dem Bau am echten Redirect prüfen), sha256 unverändert fest. Das Anlegen des Releases und das Hochladen sind nach außen gerichtet: vorher Owner fragen. Umsetzung als Folgeplan 03-07b. Dazu: HF_HUB_OFFLINE=1 und HF_HUB_DISABLE_TELEMETRY=1 im Dockerfile setzen (offener Punkt aus 03-07).

- **D-03-22 (Owner 14.11.2026, nach Plan 03-10):** Parakeet gibt bei Sprachen, die es nicht kennt (gemessen: FLEURS Türkisch), oft gar kein Token aus; die Datei endete dann als no_speech. Neue Regel im Dateiurteil: viel Sprache laut VAD (Dauer und Anteil), aber kein oder fast kein Wort aus Parakeet = unsupported_language ("Sprache nicht unterstützt"), nicht no_speech. Die Schwellen werden am Research-Korpus GEMESSEN, nicht geraten: Musik, Gesang, Stille, Rauschen müssen weiter no_speech bleiben, echte kurze Memos weiter ein Transkript bekommen; zusätzlich die Sprachen außerhalb von Parakeet (z. B. TR, AR, UK, JA, ZH) prüfen. Dazu ein FLEURS-Clip ES (Parakeet transkribiert, Abfangregel verwirft über Text-Sprachkennung) für Modell- und Abnahmetests neben DE und TR. Umsetzung in Plan 03-13 (Dateiurteil) mit Messbeleg; Tests in 03-15/03-17/03-18 auf die neue Erwartung (TR = unsupported_language) anpassen.

- **D-03-23 (Owner 14.11.2026, nach Plan 03-13):** Der zweite VAD-Durchgang (D-03-16) brachte bei FLEURS ja_jp_00 2 Wortsalat-Wörter in den Index. Wörter aus dem zweiten Durchgang werden nur behalten, wenn die Textsprache sicher DE/EN/FR ist (p >= 0,9) und die Wortkonfidenz hoch ist; die genaue Konfidenzschwelle wird am Korpus GEMESSEN: kurze echte DE/EN/FR-Memos (1 bis 4 Wörter) sollen weiter zurückgeholt werden, der JA-Clip und alle Fremd- und Nicht-Sprach-Dateien dürfen kein Wort aus dem zweiten Durchgang behalten. Umsetzung als Folgeplan 03-13b mit Messbeleg; ist die Messung mehrdeutig, Owner fragen. NACHTRAG (Owner 14.11.2026 nach Messung 03-13b, Option A): Die Sprachbedingung p >= 0,9 trennte nicht (zwei echte FR-2-Wort-Memos mit unsicherer Sprachkennung). Regel stattdessen: Fenster aus dem zweiten Durchgang nur bei mittlerer Wortkonfidenz >= 0,68 (SECOND_PASS_CONF). Folge: JA-Kauderwelsch (0,658) raus, FR "Tout bien." (0,7034) und EN-Memos bleiben, FR "Il ajoute." (0,6098) verliert sein Transkript. Abstand knapp, kleine Stichprobe; bei mehr Daten (Phase 11 Release-Gate) nachmessen.

### Claude's Discretion
- Fortsetzen nach Neustart: Granularität und Ablage der Stück-Zustände (SQLite-Stufen-Tabelle nach Findling-Muster).
- Wortgenauer Sprung: Parakeet-Wortzeiten bevorzugt (TRANS-08), Rundung wie bestehende `clock()`-Regel (nie vor dem Wort).
- Konkrete Demuxer- und Protokoll-Positivliste, Zeit- und Größengrenzen von ffmpeg, Umgang mit DRM/defekten Dateien (MEDIA-03).
- Medienkorpus für Formate/Fuzz per Skript erzeugt, nicht im Repo (Lizenzregel).
- Parakeet als Kindprozess je Job-Block; voller cgroup-Wächter erst Phase 5.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/ROADMAP.md` Phase 3 (Ziel, Erfolgskriterien, Research flag)
- `.planning/REQUIREMENTS.md` MEDIA-01 bis 04, TRANS-01/02/03/07/08, SRCH-01 bis 03
- `.planning/PROJECT.md` (Constraints, Key Decisions)
- `.planning/research/STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md`, `FEATURES.md`, `SUMMARY.md`
- `.planning/phases/01-zwei-app-ger-st-und-integrationsbeweis/01-RESEARCH.md` und `01-UI-SPEC.md` (Suchprovider-Vertrag, Untertitel, Ausschnittlänge 120)
- `.planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md` (alle D-02-Entscheide zu Rechten, Lesebeweis, Proben, Ausschluss)
- `php/lib/Search/Provider.php`, `php/lib/Controller/PageController.php`, `php/lib/Controller/GatewayController.php`, `php/lib/Service/ExclusionService.php`
- `backend/src/audio_video_search_backend/` (worker/, index/, store/, nc_queue.py)
- Spike 3: `C:/Users/Student/audio-video-spike-2026-11-04/SPIKE3-REPORT.md` (Abschnitt 11 Einstellungen), `spike3/scripts/`
- Findling: `C:/Users/Student/nextcloud-search/backend/src/findling/memory_guard.py`, `worker/`, `index/`

</canonical_refs>

<code_context>
## Existing Code Insights

- Suchprovider (`IFilteringProvider`) existiert: SEARCH_LIMIT 25, Budget 2,5 s, eine Zeile je Treffer, Untertitel `Zeitmarke · [Test result] · Ausschnitt`, Link auf `audio_video_search.page.play` mit `t`, Attribute fileId + path, Ausschlussprüfung je Vorschlag.
- Abspielseite (PageController) und Gateway (Content-Stream je file_id) existieren aus Phase 1/2.
- Arbeitsvorrat, Lesebeweis, Abgleich, Ausschlüsse und Proben (`sample_ref`) sind aus Phase 2 fertig.

</code_context>

<deferred>
## Deferred Ideas

- Instanz-Sprachen durch den Admin einschränken (mit den Profilen).
- Mehrere Tonspuren transkribieren bzw. Spurwahl nach Sprach-Tag.

</deferred>

---

*Phase: 03-vorschau-transkripte-in-der-suche*
*Context gathered: 2026-11-14*
