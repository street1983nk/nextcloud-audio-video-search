# Project Research Summary

**Project:** Audio & Video Search
**Domain:** Nextcloud-Integration für lokale Transkription und Volltextsuche in Audio und Video (CPU, amd64 + arm64, DE/EN/FR)
**Researched:** 2026-11-06
**Confidence:** MEDIUM bis HIGH

## Executive Summary

Das Produkt transkribiert alle Audio- und Videodateien einer Nextcloud automatisch und lokal und macht den Text über die normale Suche mit Zeitmarke findbar; kein Inhalt verlässt den Server. Alle vier Recherchen kommen unabhängig zum selben Kernbefund: **Eine reine Python-ExApp kann in NC 33 bis 35 keinen Unified-Search-Provider registrieren und keine zuverlässigen Datei-Ereignisse empfangen** (AppAPI-Event-Listener ab stable32 entfernt, webhook_listeners ab Werk aus, bis 5 min Verzug, ohne Share-/Gruppen-Events). Gebaut wird deshalb nach dem Findling-Muster in zwei Teilen: eine schlanke PHP-Begleit-App (Suchprovider, Listener, Crawl, Rechteprüfung, Gateway, Export- und Abspielroute) und der Python-Container (ffmpeg, Parakeet, Whisper, ROVER, Index). Die Sicherheitsgrenze liegt in PHP: Rechte werden zur Abfragezeit je Treffer geprüft, der Index kennt nie Nutzerrechte.

Die Pipeline ist eine Folge veröffentlichter Stufen je Inhalt: Parakeet mit Schluck-Wächter liefert in Minuten die durchsuchbare Vorschau, danach ersetzt im Leerlauf ein besseres Transkript (turbo + ROVER, in Qualität für DE large-v3 + ROVER) atomar das vorherige. Nacharbeit ist keine zweite Warteschlange, sondern die Abfrage "erreichtes Niveau kleiner Zielniveau". Modelle, Profile und Einstellungen sind durch Spike 3 fest. Jedes Modell läuft in einem eigenen Kindprozess hinter einem cgroup-basierten RAM-Wächter, lange Dateien in Stücken von ca. 10 Minuten.

Größte Risiken: (1) Plattformlücken: der Viewer hat keinen Startzeit-Parameter, "Klick öffnet an der Stelle" braucht eine eigene minimale Abspielroute; (2) Rechte, Lebenszyklus, DSGVO (Gruppenordner-ACL, externe Speicher, Löschen, Papierkorb), wo Findling schon teure Erfahrung hat; (3) Ressourcen auf schwacher Hardware (RAM-Wächter, OOM-Isolation, arm64-Tempo ungemessen); (4) BITV-Überversprechen, da automatische Untertitel ohne Prüfung die Konformität nicht erfüllen. Empfehlung: Risiko zuerst (Zwei-App-Gerüst mit Integrationsbeweis inkl. Zeitsprung), Inhalts-Schlüssel und Provenienz von Anfang an festlegen, Kernwert früh mit Vorschau-Qualität ausliefern, danach Profile, Veredelung, Sprachwechsel.

## Owner-Entscheidungen (06.11.2026)

1. **App-IDs:** PHP-App = `audio_video_search` (vorhandenes Zertifikat), ExApp = `audio_video_search_backend`, neues Zertifikat früh beantragen. Berührt `info.xml`, Image-Name, `release.yml`, Layout `backend/` + `php/`.
2. **Zeitsprung:** minimale Abspielansicht der PHP-App (HTML5-Player ab `#t=`, Transkript-Ausschnitt), keine Medienübersicht (bleibt v2).
3. **Export:** SRT/VTT + TXT-Transkript (WCAG 1.2.1 für reine Audiodateien); als "Untertitel-Entwurf" benannt; zusätzlich Ablage als Nebendatei neben dem Medium (`<Name>.<Sprache>.vtt`, ab NC 36 vom Viewer automatisch angezeigt), vorhandene Dateien nie überschreiben.
4. **Freigaben mit Download-Sperre:** Suche ja, Export nein.
5. Offen: Dateinamen im Admin-Fehlerstatus; BITV-Weg (Owner-Frage, siehe Gaps).

## Key Findings

### Recommended Stack

Python 3.13 (`python:3.13-slim-trixie`, Digest gepinnt), nc-py-api 0.30.3, FastAPI 0.162.0; sherpa-onnx 2.0.1 (Parakeet-TDT-0.6B-v3 int8 greedy, Silero VAD); faster-whisper 1.2.1 festgenagelt + CTranslate2 4.8.5 (int8, arm64 über Ruy); onnxruntime 1.31.1, av 19.0.2, numpy 2.5.4; ffmpeg LGPL (BtbN Monatsend-Autobuild, sha256 je Arch); jiwer 4.0.0 als Laufzeitabhängigkeit (ROVER-Alignment); Tantivy 0.26.2 + SQLite WAL als Wahrheit; PHP-Companion (PHP >= 8.2, `IFilteringProvider`, `exAppRequest`); eigener Modell-Downloader (Commit-Pin, Host-Allowlist, sha256, `HF_HUB_OFFLINE=1`). Alle nativen Pakete haben Wheels für cp313 manylinux x86_64 und aarch64.

**Nie:** Cloud-STT, beide Engines in einem Prozess (zwei ORT-Bibliotheken), `RLIMIT_AS`, BtbN `latest`, Celery/Redis, `fetch_models_task` (nur ETag). PyAV enthält GPL-Codecs: AGPL-vereinbar, in `THIRD-PARTY.md`. Details: STACK.md

### Expected Features

**Must have (table stakes):**
- Treffer mit Zeitmarke, Snippet (nur Klartext), mehreren Stellen, Kennzeichen "vorläufig"; unterstützte Filter melden, sonst blendet die Suche die Gruppe aus
- Sprung an die Stelle (eigene Route)
- Rechte-Recheck zur Abfragezeit inkl. Gruppenordner-ACL, Papierkorb, Download-Sperre
- Admin-Status mit Zählern, Gründen, Restzeit, `occ`; Pause; rückwirkende Ausschlüsse vor dem ersten Walk; Profilwahl mit gesperrten Profilen samt Grund; Instanz-Sprachen; Dauer-/Thread-Grenze; "alle löschen"
- Fehlerklassen, Wiederholung, Wiederaufnahme je Stück, atomarer Ersatz
- SRT/VTT aus Wortzeiten (höchstens 42 Zeichen je Zeile, 2 Zeilen, 1 bis 7 s, höchstens 20 Zeichen/s, ca. 80 ms Abstand), als Entwurf gekennzeichnet
- Erkennung "keine Sprache"

**Differentiators:** vollautomatisch ohne Konfiguration; Minuten bis durchsuchbar, später beste Qualität; arm64; korrekte `files_accesscontrol`/ACL; Reihenfolge "erst alle Vorschauen, dann Endfassungen, neueste zuerst"; Rechenfenster; Inhalts-Dedupe; Teilwort-Suche für Komposita.

**Defer (v2+):** Medienseite, Diarisierung, Korrektur-Editor, Geräuschmarken, STT-Provider, GPU, Findling-Anbindung, Opt-out je Ordner für Nutzer (v1.x, Personalrat). **Nie:** "BITV-konform" bewerben. Details: FEATURES.md

### Architecture Approach

Zwei Apps, Abhol-Prinzip: PHP führt einen Arbeitsvorrat, der Container claimt mit Lease, das Gateway liefert Inhalte nur per file_id. Der Hauptprozess ist einziger SQL-Schreiber, Engines laufen als Kindprozesse mit `oom_score_adj`, JSON über Pipe. Pipeline-Logik als reine Funktionen (Schnell-Gate ohne Modell testbar). Suche zweistufig: Container liefert Kandidaten, PHP prüft Rechte, dann Snippets.

**Major components:**
1. PHP-Listener, Crawl, Arbeitsvorrat
2. Search Provider + Abspiel- und Export-Route
3. Discovery-Client + Reconcile
4. Scheduler + Pipeline-Planer (Niveau statt Warteschlange)
5. Engine-Hosts + RAM-Wächter + Profil
6. Transkript-Store mit atomarem Tausch, Untertitel-Formatierer

ROVER arbeitet auf normalisierten Tokens; für Snippets und Untertitel muss die Oberflächenform mitgeführt werden. Details: ARCHITECTURE.md

### Critical Pitfalls

1. **Search/Events aus reiner ExApp unmöglich:** PHP-Companion im ersten Tor festschreiben, Lockstep + Upgrade-Beweis in CI.
2. **RAM-Wächter misst Host, OOM trifft DB:** cgroup v2 (`memory.max`, `cpu.max`), Zulassung je Modell (Bedarf + 1 GB), `oom_score_adj=1000`, `nice 19`, Test mit `--memory=2g`.
3. **Rechte im Index / Gruppenordner-ACL im falschen Lesepfad:** Index nur file_id, Recheck im Nutzerkontext, Findling-#14-Fix, CI-Fall `+read -share` im HTTP-Pfad.
4. **Falscher Ergebnis-Schlüssel, keine Provenienz:** Datei-ID allein führt zu N-fach-Rechnen (Findling #25) und Neuberechnungs-Stürmen; Inhalts-Schlüssel, Rechte je file_id, Provenienz (Engine, Modell-sha256, Konfigversion) je Version, bedingtes Schreiben. Recovery teuer, daher Phase 1.
5. **Textverlust beim Ersetzen; Abfangregel löscht echte Fremdsprache:** ROVER + Abdeckungs-Wächter je Fenster, Gate-Kennzahl "verlorene korrekte Vorschau-Wörter"; Regel nur je Segment, nicht unterstützte Sprache = `skipped` mit Grund; FLEURS tr/ar/uk ins Gate.
6. **Weitere:** ffmpeg-Härtung (`-protocol_whitelist file,pipe`, Demuxer-Positivliste, MP4 mit moov am Ende nicht per Pipe, Spurwahl, Edit-Lists), DSGVO-Löschung (Ereignis + Abgleich + Karenz, Temp-Dateien nach OOM), Speicherwachstum langer Dateien, Offline-Modelle und CC-BY-Namensnennung, BITV nicht überbehaupten.

## Implications for Roadmap

### Phase 1: Zwei-App-Gerüst und Integrationsbeweis
**Rationale:** Plattformrisiko und Zertifikat-Vorlauf zuerst; teuerste Recovery-Entscheide (Schlüssel, Provenienz, Schema).
**Delivers:** Repo `backend/` + `php/`, Dummy-Treffer in Unified Search, Abspielroute `#t=`, Schlüssel/Provenienz/Schema.
**Avoids:** P1, P4, P6, P11, P12, P24, P27

### Phase 2: Discovery
**Delivers:** Arbeitsvorrat, Listener, Crawl (Gruppenordner, externe Speicher mit Schalter), rückwirkende Ausschlüsse vor erstem Job, Reconcile mit Crawl-Flag-Tor, Gateway mit Range, Zustell-Zähler.
**Avoids:** P3, P5, P6, P12, P26, P28

### Phase 3: Medien-Eingang, Store, Vorschau-Pipeline
**Delivers:** ffprobe/ffmpeg gehärtet + Medienkorpus, VAD-Fenster, Parakeet + Schluck-Wächter, Abfangregel je Segment, publish(preview), Kill-Resume, "keine Sprache".
**Avoids:** P3, P8, P9, P15, P16

### Phase 4: Suche und Export Ende zu Ende
**Delivers:** `/search` + `/snippets`, PHP-Recheck, Rechte-Paritätstest, Zahl-/Schreibweisen-Normalisierung, SRT/VTT/TXT mit unabhängigem Parser, Nebendatei. Kernwert in Vorschau-Qualität.
**Avoids:** P4, P17, P18, P23

### Phase 5: Ressourcen, Hardware, Profile, Scheduler, Modellbezug
**Delivers:** cgroup-Wächter, OOM-Deckel, Profilvorwahl mit gesperrten Profilen, Eigentest/RTF, Prioritäten, Kindprozess-Recycling, Downloader + Offline-Ablage, Namensnennung.
**Avoids:** P2, P10, P14, P19, P20, P21

### Phase 6: Veredelung
**Delivers:** turbo gestückelt, selektiv (Schnell), ROVER mit Oberflächenform, Dateisprache, atomarer Tausch, large-v3 nur DE, Abdeckungs-Wächter, Schnell-Gate komplett.
**Avoids:** P7, P10, P11, P15

### Phase 7: Sprachwechsel
**Delivers:** Auslöser messen, Fensterprüfung, Nachrechnen, besseres Ergebnis behalten.
**Avoids:** P22

### Phase 8: Lebenszyklus und DSGVO
**Delivers:** Löschen/Papierkorb/Version/Verschieben mit Karenz, periodischer Abgleich, Waisen-Zähler 0, rückwirkendes Löschen bei Ausschluss.
**Avoids:** P12, P13, P26

### Phase 9: Admin-Status, Pause, ehrliche Zustände, Dreisprachigkeit
**Delivers:** parallel ab Phase 4, Abschluss nach 7; Zustände als Schlüssel (PHP übersetzt), Kataloge DE/de_DE/EN/FR mit Gates.
**Avoids:** P25

### Phase 10: Release-Gate, arm64, Härtung, Store
**Delivers:** 8,2-h-Gate, Kennzahl "verlorene korrekte Wörter", Pi 5/N100, 50-Dateien-Dauertest, OOM/Offline/Fuzz, Volltest DE/EN/FR, Playwright, Umlaut-Audit, Store-Text ohne "BITV-konform".

### Phase Ordering Rationale

- Plattformrisiko und Zertifikat zuerst; Schlüsselentscheidungen in Phase 1 wegen teuerster Recovery
- Discovery vor Pipeline; Suche direkt nach Vorschau (Kernwert früh)
- Wächter (5) vor Veredelung (6) wegen OOM auf 4-GB-Boxen
- Sprachwechsel nach Veredelung; Lebenszyklus als eigene Phase mit Negativtests

### Research Flags

Phasen mit Recherchebedarf:
- **Phase 1:** Range-Seek über WebDAV mit Sitzungs-Cookie, Mobil-Apps, NC 33/34/35, Store-Ablauf mit zwei Apps
- **Phase 2:** Sperrfrist lange Vorschauen, SMB/S3-Timeouts, Sitzungs-Anmeldedaten, `files_accesscontrol`
- **Phase 5:** HF-CDN-Hosts für Allowlist, Profilschwellen, optional int8-Vorkonvertierung turbo
- **Phase 6:** ROVER-Kosten auf 3-h-Dateien, Token-zu-Originalwort-Abbildung
- **Phase 7:** komplett offen, Messung Pflicht
- **Phase 8:** Papierkorb ohne Löschereignis, Versionswiederherstellung
- **Phase 10:** arm64, Pi 5, N100

Standardmuster: Phase 3 (Spike-Code vorhanden), Phase 4 (Findling-Muster), Phase 9 (Findling-Kataloge/Gates).

## Widersprüche zwischen den Recherchen

| Punkt | Aussagen | Empfehlung |
|---|---|---|
| viewer#2176 | ARCHITECTURE "offen"; STACK/FEATURES am 25.10.2026 not_planned geschlossen (plus #3226) | Vor Phase 1 prüfen; Folge identisch, eigene Route nötig |
| Suchindex | STACK Tantivy 0.26.2; ARCHITECTURE FTS5 im state.db | Tantivy (Stemming, Komposita, Findling-Code); SQLite bleibt Wahrheit; in Phase 1/3 bestätigen |
| Parakeet im Image | STACK Download in `/init`; ARCHITECTURE/PITFALLS ins Image | Ins Image (offline, Vorschau sofort); Whisper per Download; Phase 5 |
| Inhalts-Schlüssel | Datei-Hash vs. Hash des dekodierten PCM | Datei-Hash als Vorfilter, PCM-Fingerabdruck als Schlüssel prüfen; Phase 1 |
| Untertitel-Nebendatei | FEATURES ja; ARCHITECTURE/STACK keine Schreibkante in v1 | Owner 06.11.: Nebendatei ja, nie überschreiben |
| Quittierung | nach Vorschau vs. Lease + Herzschlag | Kein Widerspruch: Lease-Verlängerung je Block, 3 Zustellungen dann `failed` |

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM bis HIGH | Versionen/Wheels/Pins direkt geprüft; arm64-Tempo ungemessen, faster-whisper-Pflege, PyAV-GPL |
| Features | MEDIUM | Plattformfakten HIGH, Wettbewerber MEDIUM bis LOW, ARD/BBC/FR-Normen nur Sekundärquellen |
| Architecture | HIGH (Grenzen), MEDIUM (Scheduler/Wächter) | AppAPI stable30 bis 35 und Spike-Code gelesen; Zeitsprung und Sprachwechsel-Auslöser LOW |
| Pitfalls | MEDIUM bis HIGH | Modellfallen gemessen, Rechte aus Findling-Issues; Papierkorb, ffmpeg-Interna LOW |

**Overall confidence:** MEDIUM bis HIGH

### Gaps to Address

- **BITV-Weg:** automatische Untertitel allein erfüllen BITV 9.1.2.2 nicht (Richtigkeit bestätigt, Sprecher, bedeutungstragende Geräusche). Erreichbar nur mit menschlicher Prüfung; dafür braucht es Korrektur-Editor, Sprechermarken, Geräuschmarken (bisher v2). Owner-Frage 06.11. offen.
- Zeitsprung im Player (LOW): früher Spike Phase 1, NC 33/34/35, Playwright
- arm64/Pi 5/N100 ungemessen: Profilvorwahl bis dahin RAM-basiert, Eigentest Phase 5, Messung Phase 10
- Sprachwechsel-Auslöser: nur Vollweg gemessen (69,8 % auf 34,9 %, RTF 1,39)
- ROVER auf Oberflächenform: Abbildung bauen, WER muss gleich bleiben
- Gesang/Musik für "keine Sprache" nicht gemessen; Sprache außerhalb DE/EN/FR ungemessen
- huggingface-hub 2.x auf Linux im ersten Container-Build prüfen
- Externe Speicher: Sitzungs-Anmeldedaten, Änderungen außerhalb Nextcloud nur per Reconcile
- Papierkorb-Ereignislage je Version; Cassini-Stand vor Release; Viewer-Untertitel-Schema für NC 33 bis 35 unbelegt

## Sources

### Primary (HIGH confidence)
- AppAPI-Quellbaum (main, stable30 bis 35), nc_py_api 0.30.3, Nextcloud Developer/Admin Manual
- PyPI/GitHub/Hugging Face (06.11.2026), Spike 1 bis 3 inkl. Release-Gate (sha256 101fa929...)
- Findling-Code, Retrospektive, Issues #14, #15, #18, #19, #25, #33, #36, #44, #45
- W3C WAI (WCAG 1.2.1/1.2.2), W3C WebVTT, BITV-Test 9.1.2.2, viewer#2176/#3226, @nextcloud/viewer PR #184

### Secondary (MEDIUM confidence)
- Netflix-Styleguides, ARD/ZDF/ORF/SRF über Sekundärquellen, CTranslate2-Doku, Google Drive/MS Stream, Descript, noScribe, pyav-ffmpeg Build-Skript

### Tertiary (LOW confidence)
- Cassini, Whishper, Scriberr, BBC, viewer PR #907, faster-whisper-Issues zu aarch64/Speicher, ffmpeg-/Papierkorb-Fachwissen

---
*Research completed: 2026-11-06*
*Ready for roadmap: yes*
