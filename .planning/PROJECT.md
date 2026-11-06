# Audio & Video Search

## What This Is

Nextcloud-App aus zwei Teilen (PHP-App `audio_video_search` für Suche, Ereignisse, Rechte und Abspielansicht; ExApp `audio_video_search_backend` für Dekodieren, Erkennung und Index), die alle Audio- und Videodateien einer Instanz automatisch und vollständig lokal transkribiert und den gesprochenen Text über die normale Nextcloud-Suche mit Sprung auf die Zeitstelle findbar macht. Zielgruppe: Selfhoster, kleine Organisationen, Behörden und Schulen, die ihre Aufnahmen (Sitzungen, Interviews, Vorlesungen, Videos) durchsuchen wollen, ohne Inhalte an einen Cloud-Dienst zu geben. Sprachen DE, EN, FR.

## Core Value

Nach der Installation werden alle Audio- und Videodateien ohne Konfiguration lokal transkribiert und sind in der Nextcloud-Suche mit Zeitmarke findbar, mit der bestmöglichen Transkriptqualität, die auf der vorhandenen Hardware sicher läuft. Kein Inhalt verlässt den Server.

## Requirements

### Validated

- ✓ ExApp-Grundgerüst (AppAPI/HaRP, deklarative Admin-Einstellungen, l10n DE/EN/FR, Store-Metadaten, Release-/Zertifikats-Pipeline, CI): existing (gemeinsames Skeleton, e4d5941..f908a85)

### Active

- [ ] Automatische Transkription aller Audio-/Videodateien aller Nutzer inkl. Gruppenordner; Admin kann Nutzer, Gruppen, Ordner ausschließen
- [ ] Externe Speicher (SMB, S3 usw.) einbezogen, Admin-Schalter zum Ausschließen
- [ ] Vorschau-Transkript sofort: Parakeet-TDT-0.6B-v3 int8 mit Schluck-Wächter, VAD immer an (nicht abschaltbar)
- [ ] Drei Profile laut Spike 3: Schnell (Parakeet + selektives turbo-Nachrechnen bei Konfidenz < 0,8), Ausgewogen = Standard (Parakeet-Vorschau, turbo ganz im Leerlauf, ROVER), Qualität (wie Ausgewogen, DE zusätzlich large-v3 + ROVER turbo/large-v3)
- [ ] Besseres Transkript ersetzt das Vorschau-Transkript atomar, Suche bleibt dabei durchgehend verfügbar
- [ ] Profil-Vorwahl nach Hardware (RAM/Kerne), Admin kann ändern; nur Profile, die auf der Hardware sicher laufen (RAM-Wächter)
- [ ] Halluzinations-Abfangregel: erkannte Sprache außerhalb der Instanz-Sprachen mit Sicherheit < 0,5 verwerfen, Segmente in fremder Schrift verwerfen
- [ ] Sprachwechsel in einer Datei erkennen und betroffene Fenster mit eigener Spracherkennung nachrechnen, besseres Ergebnis behalten
- [ ] Unified-Search-Provider: Treffer im gesprochenen Text mit Zeitmarke, Klick öffnet Datei an der Stelle; Rechte wie die Datei (geteilt/entzogen/gelöscht wirkt sofort)
- [ ] SRT/VTT/TXT-Export je Datei als "Untertitel-Entwurf", optional als Nebendatei (nie überschreiben); Download-Sperre: Suche ja, Export nein
- [ ] PHP-Begleit-App `audio_video_search` (Suche, Ereignisse, Rechte, Abspielansicht) + ExApp `audio_video_search_backend`
- [ ] Minimale Abspielansicht, die an der Zeitstelle startet
- [ ] BITV-Weg: Korrektur-Editor, Sprecher- und Geräusch-Marken von Hand, Status "geprüft", erst dann Export ohne Entwurf-Kennzeichen
- [ ] Ehrliche Zustände: Fortschritt, übersprungene und fehlgeschlagene Dateien mit Grund sichtbar (Admin-Status)
- [ ] Release-Gate aus Spike 3 (Schnell-Gate je Build, Release-Gate vor Store-Release, sha256-geprüft; Gate-Daten per Skript erzeugt, nicht im Repo)
- [ ] amd64 + arm64, nur CPU; Pi 5 / N100 vor Release echt gemessen
- [ ] Alle Texte inkl. README dreisprachig DE/EN/FR im Gleichstand

### Out of Scope

- Inhalte an externe Dienste schicken (Cloud-STT, externe Embeddings): Owner-Regel Datenschutz zuerst
- Eigene Medien-Seite mit Übersicht: v2; v1 hat nur die minimale Abspielansicht und den Editor
- Findling-Anbindung: später (Findling indexiert dann fertige Transkripte, ca. 3-5 PT)
- STT-Provider für Assistant/Talk (TaskProcessing): v2
- Automatische Sprecher-Trennung (Diarisierung): v2, erst eigener CPU-Spike; in v1 Sprecher-Marken von Hand
- GPU (CUDA/OpenVINO): v2
- Instanz-Vokabular (hotwords) im Standard: Spike 3: nur bei wiederkehrenden Begriffen hilfreich, sonst neutral bis schädlich; höchstens später als Option je Ordner
- Whisper `condition_on_previous_text=True`, Beam 5, `initial_prompt`, Parakeet-Beam-Search: Spike 3 signifikant schlechter
- Canary-1B-v2: Spike 2: kein gesicherter Vorsprung, keine Wortzeiten im ONNX-Weg
- VAD abschaltbar: ohne VAD 20 bis 72 Halluzinationswörter je Datei

## Context

- Spikes 1 bis 3 (04. bis 06.11.2026) unter `C:/Users/Student/audio-video-spike-2026-11-04/` (SPIKE-REPORT.md, SPIKE2-REPORT.md, SPIKE3-REPORT.md, Skripte `spike3/scripts/`, Release-Gate `spike3/release-gate-2026-11-06.json`, sha256 101fa929...). Spike 3 ist die maßgebliche Quelle für Modelle, Einstellungen und Profile.
- Gemessene Kennzahlen (i5-1335U, 2 Threads): Parakeet+Wächter RTF 0,11, 1,2 GB; turbo RTF 0,47, 1,9 GB (3,4 GB bei 41-min-Datei ohne Stückelung); large-v3 RTF 0,83, 3,3 bis 4,5 GB. Lange Dateien in Stücken (ca. 10 min) an faster-whisper geben.
- Feste Standard-Einstellungen aus Spike 3 Abschnitt 11 (Parakeet greedy, Silero VAD 0,5 / 0,3 s / max 25 s, Fenster bis 25 s + 0,4 s Kontext + 0,5 s Polster, Segmente < 0,1 s auffüllen/verwerfen; faster-whisper int8, beam 1, VAD 0,5 / 2000 ms, word_timestamps; ROVER-Parameter 0,15 / 0,2 / 0,6).
- Bekannte Schwächen: Parakeet verschluckt Passagen (Wächter nötig) und wechselt in französischer Spontansprache ins Englische; Whisper lässt ganze Sätze aus und versagt bei Sprachwechsel (70 % WER); Café-Lärm 19 bis 61 % WER bei allen Modellen; Raummikrofon-Meetings 34 bis 38 %.
- Markt: keine Store-App macht Audio/Video automatisch lokal durchsuchbar (stt_whisper2/Assistant nur auf Anfrage, nur x86; Context Chat indexiert kein Audio/Video). Nächster Konkurrent Cassini (nur Talk-Aufnahmen).
- Schwester-Apps: Findling (nextcloud-search, Datei-Walk, Rechte-Abgleich, Reconcile, Pause; Muster übernehmen), MCP-Connector, Gameworld. Gemeinsames Skeleton `C:/Users/Student/nextcloud-exapp-skeleton`.
- Zertifikat erteilt (PR #1409, jetzt für die PHP-App); Backend-Zertifikat beantragt (PR #1417, 06.11.), Repo auf GitHub `street1983nk/nextcloud-audio-video-search`.
- Testrechner hat 15,7 GB RAM, oft nur 4,5 bis 7 GB frei: Messungen seriell, RAM-Wächter.

## Constraints

- **Datenschutz**: Kein Audio, kein Text, keine Telemetrie verlässt den Server; Modelle werden einmal aus öffentlichen Quellen geladen oder ins Image gelegt: Owner-Regel
- **Qualität vor Speed**: Standard nach Qualität; Entwicklungsaufwand ist kein Grund, eine messbar bessere Lösung wegzulassen; jede Qualitätsentscheidung mit WER-Messung belegen: Owner 04./06.11.
- **Tech stack**: Python-ExApp (FastAPI, nc_py_api) aus dem Skeleton, sherpa-onnx (Parakeet, Silero VAD), faster-whisper/CTranslate2, ffmpeg LGPL-Build: Spike 1 bis 3
- **Kompatibilität**: Nextcloud 33 bis 35, AppAPI mit HaRP, amd64 + arm64, nur CPU
- **Ressourcen**: RAM-Wächter für jedes Modell; Profil darf nie mehr RAM brauchen, als die Hardware sicher hat
- **Lizenzen**: Parakeet CC-BY-4.0 (Namensnennung NVIDIA Pflicht), Whisper MIT, ffmpeg LGPL; Gate-Daten nicht ins Repo (Metamorphosis-Referenz nicht gemeinfrei, ns_music ungeprüft)
- **Sprache**: Alle nutzersichtbaren Texte und README DE/EN/FR im Gleichstand, Deutsch zuerst, echte Umlaute, keine Gedankenstriche, keine Emojis
- **Qualitäts-Gates**: ruff-Vollsatz, pyright basic, vulture lokal grün; Commits nur als street1983nk <k.cherif@outlook.de>, ohne "closes #N"
- **Prozess**: Vor jedem Push, Merge oder Kommentar den Owner fragen; UI-Abnahme gemeinsam per Playwright (3 Breiten, hell/dunkel); vor Store-Release großer Volltest DE/EN/FR

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Eigene App statt Findling-Track | Eigener Store-Eintrag, Findling später nur Konsument der Transkripte | Offen |
| Name "Audio & Video Search", ID `audio_video_search` | Owner 04.11., schlicht, Store frei | ✓ Good |
| Kombinierte Pipeline: Parakeet-Vorschau zuerst, besseres Transkript im Leerlauf ersetzt | Owner 05.11., in Minuten durchsuchbar und trotzdem beste Qualität | Offen |
| Drei Profile Schnell/Ausgewogen/Qualität, Standard Ausgewogen, Vorwahl nach Hardware | Spike 3 Abschnitt 11, Owner 06.11. | Offen |
| VAD immer an, nicht abschaltbar | Spike 3: ohne VAD massive Halluzinationen | ✓ Good |
| Instanz-Vokabular nicht im Standard | Spike 3 Option 3 | ✓ Good |
| Sprachwechsel: erkennen + je Fenster nachrechnen | Owner 06.11. (mixlang 70 % auf 35 %) | Offen |
| v1-Suche nur über Unified Search, keine eigene App-Seite | Owner 06.11. | Offen |
| v1 mit SRT/VTT-Export | Owner 06.11., BITV-Argument | Offen |
| Alle Dateien automatisch, Admin schränkt ein; externe Speicher mit Admin-Schalter | Owner 06.11., Null-Konfiguration | Offen |
| amd64 + arm64, nur CPU | Owner 06.11. | Offen |
| Zwei Apps: PHP `audio_video_search` + ExApp `audio_video_search_backend` | Reine ExApp kann keinen Suchprovider registrieren (alle 4 Recherchen) | Offen |
| BITV-Weg (Editor, Marken, geprüft) schon in v1 | Owner 06.11.; automatische Untertitel allein nicht BITV-konform | Offen |
| Admin-Fehlerstatus ohne Dateinamen | Owner 06.11., Details per occ | Offen |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check: still the right priority?
3. Audit Out of Scope: reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-06 after initialization*
