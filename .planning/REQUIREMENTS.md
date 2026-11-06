# Requirements: Audio & Video Search

**Defined:** 2026-11-06
**Core Value:** Nach der Installation werden alle Audio- und Videodateien ohne Konfiguration lokal transkribiert und sind in der Nextcloud-Suche mit Zeitmarke findbar, mit der bestmöglichen Transkriptqualität, die auf der vorhandenen Hardware sicher läuft. Kein Inhalt verlässt den Server.

Quellen: PROJECT.md, research/SUMMARY.md, Spike 3 (SPIKE3-REPORT.md). Owner-Entscheide vom 06.11.2026.

## v1 Requirements

### Plattform (PLAT)

- [ ] **PLAT-01**: Admin installiert zwei Apps aus dem Store: PHP-App `audio_video_search` und ExApp `audio_video_search_backend`; beide laufen im Lockstep (gleiche Version, Upgrade-Beweis in CI)
- [ ] **PLAT-02**: Admin sieht eine klare Meldung, wenn die Gegen-App fehlt, nicht erreichbar ist oder eine andere Version hat
- [ ] **PLAT-03**: Läuft auf Nextcloud 33, 34 und 35 mit AppAPI/HaRP, amd64 und arm64, nur CPU
- [ ] **PLAT-04**: Kein Audio, kein Text, keine Telemetrie verlässt den Server; einzige ausgehende Verbindung ist der Modell-Download von einer Host-Allowlist, abschaltbar für Offline-Instanzen

### Erfassung (DISC)

- [ ] **DISC-01**: Ohne Konfiguration werden alle Audio- und Videodateien aller Nutzer erfasst, inklusive Gruppenordner
- [ ] **DISC-02**: Externe Speicher (SMB, S3 usw.) werden erfasst; Admin kann sie per Schalter ausschließen
- [ ] **DISC-03**: Admin kann Nutzer, Gruppen und Ordner ausschließen; Ausschlüsse greifen vor dem ersten Durchlauf und wirken rückwirkend (vorhandene Transkripte werden entfernt)
- [ ] **DISC-04**: Neue und geänderte Dateien werden innerhalb weniger Minuten erkannt (Ereignisse), Änderungen außerhalb von Nextcloud über einen periodischen Abgleich
- [ ] **DISC-05**: Gleicher Inhalt wird nur einmal gerechnet (Inhalts-Schlüssel), auch bei Kopien, Verschieben, Umbenennen und je Nutzer eingebundenen externen Speichern
- [ ] **DISC-06**: Verschieben, Umbenennen oder Taggen löst keine Neuberechnung aus

### Medien-Eingang (MEDIA)

- [ ] **MEDIA-01**: Gängige Audio- und Videoformate werden dekodiert (u. a. MP3, M4A, WAV, OGG, Opus, FLAC, MP4, MOV, MKV, WebM), auch MP4 mit Index am Dateiende
- [ ] **MEDIA-02**: Bei mehreren Tonspuren wird eine Spur nach fester Regel gewählt, die Zeitachse stimmt auch bei Edit-Lists
- [ ] **MEDIA-03**: Dekodierung ist gehärtet: nur lokale Eingänge (Protokoll-Positivliste), Demuxer-Positivliste, Zeit- und Größengrenzen; defekte oder geschützte Dateien werden mit Grund übersprungen
- [ ] **MEDIA-04**: Dateien ohne Sprache (Musik, Stille, Rauschen) werden als "keine Sprache" erkannt, nicht als Fehler

### Transkription (TRANS)

- [ ] **TRANS-01**: Jede Datei bekommt zuerst ein Vorschau-Transkript (Parakeet-TDT-0.6B-v3 int8 mit Schluck-Wächter, Einstellungen laut Spike 3), in Minuten durchsuchbar
- [ ] **TRANS-02**: VAD ist immer an und nicht abschaltbar
- [ ] **TRANS-03**: Halluzinations-Abfangregel je Segment: Segmente mit erkannter Sprache außerhalb der Instanz-Sprachen und Sicherheit < 0,5 sowie Segmente in fremder Schrift werden verworfen; echte Aufnahmen in nicht unterstützter Sprache werden als "Sprache nicht unterstützt" übersprungen, nicht still geleert
- [ ] **TRANS-04**: Ein besseres Transkript ersetzt das vorherige atomar; die Suche bleibt dabei durchgehend verfügbar und zeigt nie einen Mischzustand
- [ ] **TRANS-05**: Ein Ersatz verliert keinen korrekt erkannten Text der Vorschau (Abdeckungs-Wächter je Fenster)
- [ ] **TRANS-06**: Jedes Transkript führt seine Herkunft (Engine, Modell-sha256, Konfigurationsversion, Profilstufe); ein veraltetes Ergebnis überschreibt nie ein neueres
- [ ] **TRANS-07**: Lange Dateien werden in Stücken (ca. 10 min) gerechnet; nach Neustart oder Absturz geht es am letzten fertigen Stück weiter
- [ ] **TRANS-08**: Zeitstempel je Wort stimmen auf die Audiozeit (Parakeet-Wortzeiten bevorzugt)

### Profile und Veredelung (QUAL)

- [ ] **QUAL-01**: Profil "Schnell": Parakeet-Vorschau, danach selektives Nachrechnen mit Whisper large-v3-turbo für Fenster mit Konfidenz < 0,8
- [ ] **QUAL-02**: Profil "Ausgewogen" (Standard): Parakeet-Vorschau, im Leerlauf turbo ganz, Endtext = ROVER Parakeet + turbo
- [ ] **QUAL-03**: Profil "Qualität": wie Ausgewogen, für Deutsch zusätzlich large-v3, Endtext = ROVER turbo + large-v3
- [ ] **QUAL-04**: Sprachwechsel innerhalb einer Datei wird erkannt; betroffene Fenster werden mit eigener Spracherkennung nachgerechnet, das bessere Ergebnis bleibt
- [ ] **QUAL-05**: Whisper-Einstellungen laut Spike 3 fest (int8, beam 1, `condition_on_previous_text=False`, VAD 0,5 / 2000 ms, kein `initial_prompt`, keine hotwords)
- [ ] **QUAL-06**: Nach einem Profilwechsel werden vorhandene Transkripte gezielt auf das neue Zielniveau gebracht (nur die Differenz)

### Ressourcen und Modelle (RES)

- [ ] **RES-01**: Die App schlägt beim Start das beste sicher lauffähige Profil vor (RAM und CPU aus der cgroup, kurzer Eigentest); Admin kann es ändern, nicht lauffähige Profile sind mit Grund gesperrt
- [ ] **RES-02**: RAM-Wächter je Modell (Bedarf + Reserve, aus cgroup gemessen); kein Modell startet ohne genug Speicher
- [ ] **RES-03**: Erkennung läuft in Kindprozessen mit niedriger Priorität und hohem OOM-Wert, so dass bei Speichermangel nie Nextcloud oder die Datenbank getroffen wird
- [ ] **RES-04**: Reihenfolge: erst alle Vorschauen, dann Veredelung, jeweils neueste Datei zuerst
- [ ] **RES-05**: Admin kann Threads begrenzen und ein Rechenfenster (Uhrzeiten) setzen
- [ ] **RES-06**: Parakeet und Silero VAD liegen im Image; Whisper-Modelle werden mit festem Commit und sha256 geladen oder vom Admin offline abgelegt
- [ ] **RES-07**: Namensnennung CC-BY-4.0 (NVIDIA Parakeet) und alle Drittlizenzen (ffmpeg LGPL, PyAV-Codecs, Whisper MIT) sind in App, README und THIRD-PARTY.md genannt

### Suche (SRCH)

- [ ] **SRCH-01**: Nutzer findet gesprochenen Text in der normalen Nextcloud-Suche; Treffer zeigen Dateiname, Zeitmarke und Textausschnitt, mehrere Stellen je Datei
- [ ] **SRCH-02**: Treffer aus einem Vorschau-Transkript sind als vorläufig gekennzeichnet
- [ ] **SRCH-03**: Nutzer sieht nur Treffer aus Dateien, die er gerade lesen darf (Prüfung zur Abfragezeit inkl. Gruppenordner-ACL, Freigaben, entzogene Rechte, Papierkorb)
- [ ] **SRCH-04**: Freigaben mit Download-Sperre: Suche ja, Export nein
- [ ] **SRCH-05**: Suche findet Wortformen und Teilwörter in Komposita (DE/EN/FR) sowie Zahlen als Ziffer und als Wort
- [ ] **SRCH-06**: Die Ergebnisgruppe bleibt sichtbar, wenn Nutzer Datums- oder Personenfilter setzen (unterstützte Filter gemeldet)

### Abspielen (PLAY)

- [ ] **PLAY-01**: Klick auf einen Treffer öffnet eine schlichte Abspielansicht, die an der Zeitstelle startet und den Transkript-Ausschnitt zeigt
- [ ] **PLAY-02**: Abspielansicht funktioniert mit Seek über WebDAV auf NC 33 bis 35, im Browser hell und dunkel, auf drei Breiten

### Export (EXP)

- [ ] **EXP-01**: Nutzer lädt je Datei SRT, VTT und TXT herunter
- [ ] **EXP-02**: Untertitel werden aus Wortzeiten gebildet (höchstens 42 Zeichen je Zeile, 2 Zeilen, 1 bis 7 s, höchstens 20 Zeichen/s, ca. 80 ms Abstand) und bestehen einen unabhängigen SRT/VTT-Parser
- [ ] **EXP-03**: Nutzer kann die Untertitel als Nebendatei neben das Medium legen (`<Name>.<Sprache>.vtt`); vorhandene Dateien werden nie überschrieben
- [ ] **EXP-04**: Ungeprüfte Exporte heißen "Untertitel-Entwurf"; nirgends wird "BITV-konform" für ungeprüfte Untertitel behauptet

### BITV-Weg (BITV)

- [ ] **BITV-01**: Nutzer korrigiert das Transkript in einem Editor neben dem Player (Text, Zeitgrenzen); Korrekturen bleiben bei späterer Veredelung oder Neuberechnung erhalten
- [ ] **BITV-02**: Nutzer setzt Sprecher-Marken von Hand und benennt Sprecher
- [ ] **BITV-03**: Nutzer fügt Geräusch-Marken ein (z. B. "[Applaus]", "[Telefon klingelt]")
- [ ] **BITV-04**: Nutzer markiert ein Transkript als "geprüft"; erst dann exportiert die App Untertitel ohne Entwurf-Kennzeichen, inkl. Sprecher- und Geräuschangaben nach BITV 9.1.2.2 / WCAG 1.2.2
- [ ] **BITV-05**: Nur Nutzer mit Schreibrecht auf die Datei dürfen korrigieren und prüfen; jede Änderung ist mit Nutzer und Zeit nachvollziehbar
- [ ] **BITV-06**: Editor ist selbst barrierefrei bedienbar (WCAG 2.1 AA, Tastatur, Screenreader)

### Lebenszyklus und DSGVO (LIFE)

- [ ] **LIFE-01**: Wird eine Datei gelöscht, verschwindet ihr Transkript aus der Suche sofort und aus dem Speicher nach kurzer Karenz (Papierkorb-Wiederherstellung bleibt möglich)
- [ ] **LIFE-02**: Endgültig gelöschte Dateien (Papierkorb geleert, abgelaufen) hinterlassen keine Transkripte; ein periodischer Abgleich findet Waisen
- [ ] **LIFE-03**: Wiederhergestellte Versionen und geänderte Inhalte werden neu bewertet
- [ ] **LIFE-04**: Admin kann alle Transkripte löschen; Temp-Dateien werden auch nach Absturz entfernt

### Admin und Zustände (ADM)

- [ ] **ADM-01**: Admin sieht Fortschritt: erfasst, Vorschau fertig, veredelt, übersprungen, fehlgeschlagen, mit Restzeit-Schätzung
- [ ] **ADM-02**: Übersprungene und fehlgeschlagene Dateien werden als Zähler mit Grund gezeigt, ohne Dateinamen; Details per `occ`
- [ ] **ADM-03**: Admin kann pausieren und fortsetzen (Oberfläche und `occ`)
- [ ] **ADM-04**: Fehlgeschlagene Dateien werden begrenzt wiederholt (3 Zustellungen, dann `failed` mit Grund), Admin kann neu anstoßen
- [ ] **ADM-05**: Admin legt die Instanz-Sprachen fest (Standard DE/EN/FR)

### Sprache und Texte (I18N)

- [ ] **I18N-01**: Alle nutzersichtbaren Texte, Store-Texte und README in DE, EN, FR im Gleichstand (Gate), Deutsch zuerst, `de_DE` als Rückfall
- [ ] **I18N-02**: Echte Umlaute, keine Gedankenstriche, keine Emojis (Umlaut-Audit vor jeder Abnahme)

### Release (REL)

- [ ] **REL-01**: Schnell-Gate je Build (Kernsätze, Nicht-Sprache, Lücken) gegen Spike-3-Werte, gepaarter Bootstrap
- [ ] **REL-02**: Release-Gate vor jedem Store-Release (46 Sätze, 8,2 h, sha256-geprüft) inkl. Kennzahl "verlorene korrekte Vorschau-Wörter" und Negativsatz fremder Sprachen (FLEURS tr/ar/uk); Gate-Daten per Skript erzeugt, nicht im Repo
- [ ] **REL-03**: Messung auf Pi 5 und N100 vor Release; Profilvorwahl auf Basis echter Werte
- [ ] **REL-04**: Großer Volltest aller Funktionen und Meldungen in DE/EN/FR, Playwright-Abnahme gemeinsam mit dem Owner (3 Breiten, hell/dunkel)
- [ ] **REL-05**: Sicherheits- und Robustheitstests: OOM, Offline, Fuzz-Medien, 50-Dateien-Dauertest, Rechte-Negativtests

## v2 Requirements

### Erweiterungen

- **V2-01**: Eigene Medien-Seite mit Übersicht, Status je Datei und Player
- **V2-02**: Automatische Sprechertrennung (Diarisierung), nach eigenem CPU-Spike DE/EN/FR
- **V2-03**: Automatische Geräusch-Erkennung
- **V2-04**: STT-Provider für Assistant/Talk (TaskProcessing)
- **V2-05**: Findling-Anbindung (Findling indexiert fertige Transkripte)
- **V2-06**: GPU (CUDA/OpenVINO)
- **V2-07**: Instanz-Vokabular je Ordner als turbo-hotwords (nur für Sitzungsreihen)
- **V2-08**: Opt-out je Ordner für Nutzer (Mitbestimmung)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Cloud-STT, externe Embeddings | Owner-Regel: nichts verlässt den Server |
| VAD abschaltbar | Spike 3: ohne VAD 20 bis 72 Halluzinationswörter je Datei |
| Whisper `condition_on_previous_text=True`, Beam 5, `initial_prompt` | Spike 3 signifikant schlechter |
| Parakeet-Beam-Search / Parakeet-hotwords | Spike 3: AMI 25 % auf 53 % |
| Canary-1B-v2 | Spike 2: kein gesicherter Vorsprung, keine Wortzeiten |
| "BITV-konform" für ungeprüfte Untertitel | W3C WAI: automatische Untertitel erst nach Bestätigung konform |
| Dateinamen im Admin-Fehlerstatus | Owner 06.11.: können personenbezogen sein, Details nur per occ |

## Traceability

Wird bei der Roadmap-Erstellung gefüllt.

| Requirement | Phase | Status |
|-------------|-------|--------|

**Coverage:**
- v1 requirements: 69 total
- Mapped to phases: 0
- Unmapped: 69

---
*Requirements defined: 2026-11-06*
*Last updated: 2026-11-06 after initial definition*
