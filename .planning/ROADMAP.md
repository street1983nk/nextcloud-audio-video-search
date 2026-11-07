# Roadmap: Audio & Video Search

## Overview

Zuerst wird das größte Plattformrisiko ausgeräumt: zwei Apps (PHP-Begleit-App `audio_video_search` und ExApp `audio_video_search_backend`) beweisen im Lockstep auf NC 33 bis 35, dass ein Treffer in der Unified Search erscheint und eine minimale Abspielansicht an der Zeitstelle startet. In Phase 1 werden auch die teuersten Entscheide festgelegt: Inhalts-Schlüssel, Herkunft (Provenienz) und ein Transkript-Schema, das Nutzerkorrekturen über spätere Neuberechnungen hinweg trägt. Danach liefert jede Phase ein lauffähiges Inkrement: Erfassung aller Dateien, Vorschau-Transkripte in der echten Suche (Kernwert), Suchqualität und Export, Ressourcen-Wächter und Profile, Veredelung, Sprachwechsel, Lebenszyklus und DSGVO, ehrliche Admin-Zustände, der BITV-Weg mit Korrektur-Editor und zum Schluss Release-Gate, Messung auf Pi 5 und N100 und der große Volltest.

Projektmodus: mvp, Owner-Regel "erst Risiko, dann vertikal". 11 Phasen bei Granularität standard; begründet durch den Umfang (69 Anforderungen, zwei Apps, drei Engines, BITV-Weg in v1) und durch zwei Phasen mit offenem Messbedarf (Sprachwechsel, Release-Messung), die nicht mit sicheren Phasen vermischt werden sollen.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Zwei-App-Gerüst und Integrationsbeweis** - PHP-App und ExApp im Lockstep, Dummy-Treffer in der Unified Search, Abspielansicht ab `#t=`, Schlüssel/Provenienz/Schema festgelegt
 (completed 2026-11-07)
- [ ] **Phase 2: Erfassung aller Dateien** - Arbeitsvorrat, Ereignisse, Crawl inkl. Gruppenordner und externer Speicher, Ausschlüsse, Inhalts-Dedupe
- [ ] **Phase 3: Vorschau-Transkripte in der Suche** - Gehärteter Medien-Eingang, Parakeet-Vorschau mit Wächter und Abfangregel, echte Treffer mit Rechteprüfung zur Abfragezeit
- [ ] **Phase 4: Suchqualität und Export** - Wortformen/Komposita/Zahlen, Filter-Verträglichkeit, Download-Sperre, SRT/VTT/TXT und Nebendatei als Untertitel-Entwurf
- [ ] **Phase 5: Ressourcen, Profile und Modellbezug** - cgroup-RAM-Wächter, OOM-Isolation, Profilvorwahl, Reihenfolge, Rechenfenster, Modell-Download mit sha256, Lizenzen
- [ ] **Phase 6: Veredelung** - Schnell/Ausgewogen/Qualität mit turbo, large-v3 und ROVER, atomarer Ersatz ohne Textverlust, Schnell-Gate je Build
- [ ] **Phase 7: Sprachen und Sprachwechsel** - Instanz-Sprachen einstellbar, Sprachwechsel in einer Datei erkannt und je Fenster nachgerechnet
- [ ] **Phase 8: Lebenszyklus und DSGVO** - Löschen, Papierkorb, Versionen, Waisen-Abgleich, alle Transkripte löschen, Temp-Dateien nach Absturz
- [ ] **Phase 9: Ehrliche Admin-Zustände und Dreisprachigkeit** - Fortschritt, Gründe ohne Dateinamen, Pause, Wiederholung, Sprach-Gate DE/EN/FR
- [ ] **Phase 10: BITV-Weg** - Korrektur-Editor neben dem Player, Sprecher- und Geräusch-Marken, Status "geprüft", Export ohne Entwurf-Kennzeichen
- [ ] **Phase 11: Release-Gate, Hardware-Messung und Volltest** - 8,2-h-Gate, Pi 5/N100, Härtungstests, Volltest DE/EN/FR mit Owner-Abnahme

## Phase Details

### Phase 1: Zwei-App-Gerüst und Integrationsbeweis
**Goal**: Der Admin installiert beide Apps, und ein Nutzer sieht einen (Dummy-)Treffer in der normalen Nextcloud-Suche, dessen Klick eine Abspielansicht genau an der Zeitstelle startet; die schwer umkehrbaren Datenentscheide sind getroffen und durch Tests belegt.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: PLAT-01, PLAT-02, PLAT-03, PLAY-01, PLAY-02, TRANS-06
**Success Criteria** (what must be TRUE):
  1. Admin installiert `audio_video_search` (PHP) und `audio_video_search_backend` (ExApp) auf NC 33, 34 und 35 (amd64 und arm64); CI belegt Lockstep-Version und ein Upgrade beider Apps; der Zertifikatsantrag für `audio_video_search_backend` ist gestellt.
  2. Fehlt die Gegen-App, ist sie nicht erreichbar oder hat sie eine andere Version, sieht der Admin eine klare Meldung statt eines stillen Ausfalls.
  3. Ein Nutzer sucht ein Dummy-Wort und bekommt in der Unified Search einen Treffer mit Dateiname, Zeitmarke und Ausschnitt; der Klick öffnet die Abspielansicht, die per Range-Seek über WebDAV an der Zeitstelle startet (NC 33 bis 35, hell/dunkel, drei Breiten, Playwright).
  4. Ein Test-Transkript trägt Herkunft (Engine, Modell-sha256, Konfigurationsversion, Profilstufe) und Inhalts-Schlüssel; ein Schreibversuch mit älterer Herkunft wird abgewiesen.
  5. Das Transkript-Schema hält Nutzerkorrekturen als eigene Schicht über den Maschinen-Stufen; ein Test zeigt, dass eine Korrektur einen simulierten Ersatz durch ein besseres Maschinen-Transkript übersteht (Vorbedingung für BITV-01).
**Plans**: 13 plans (8 Wellen)
Plans:
- [x] 01-01-PLAN.md: (W1) Gerüst beider Apps (backend/ + php/), Paket-Freigabe, Workflows, Lockstep-Build-Gate, php.yml
- [x] 01-02-PLAN.md: (W2) Datenkern SQLite mit Inhalts-Schlüssel, Provenienz, bedingtem Schreiben, Korrektur-Schicht, remove_sample (TRANS-06)
- [x] 01-03-PLAN.md: (W2) PHP-Suchtreffer: ExAppService, Rechte-Recheck, Provider mit Zeitmarke, Gateway, occ-Saat mit --remove
- [x] 01-04-PLAN.md: (W2) Kataloge DE/EN/FR mit Gate und fehlschlagender Playwright-Kernweg
- [x] 01-12-PLAN.md: (W3) Owner: früher Push auf Branch phase-01, php.yml/phpunit in CI, Korrekturschleife
- [x] 01-05-PLAN.md: (W4) Container-Hälfte: Tantivy-Index, /sample mit sha256 im Strom, /sample/remove, /search, /excerpt
- [x] 01-06-PLAN.md: (W4) Abspielansicht mit Range-Seek über WebDAV und allen Zuständen
- [x] 01-07-PLAN.md: (W5) Admin-Sektion mit Gegen-App-Zustand, Erneut prüfen, Debug-Schalter (PLAT-02)
- [x] 01-08-PLAN.md: (W5) Handshake: Container erkennt fehlende PHP-App, erweiterter /status
- [x] 01-09-PLAN.md: (W6) CI-Integrationsbeweis auf sechs Beinen mit Playwright und Screenshots
- [x] 01-13-PLAN.md: (W6) Doku DE/EN/FR, DESIGN.md, PRODUCT.md, CHANGELOG
- [x] 01-10-PLAN.md: (W7) Upgrade 0.0.1 nach 0.1.0, Drift-Schritte, zwei Store-Archive
- [x] 01-11-PLAN.md: (W8) Owner: Push-Freigabe main oder phase-01, CI mit Korrekturschleife, gemeinsame UI-Abnahme
**UI hint**: yes
**Research flag**: Range-Seek über WebDAV mit Sitzungs-Cookie, Mobil-Apps, Verhalten NC 33/34/35, Store-Ablauf mit zwei Apps. Vor dem Plan klären: viewer#2176/#3226 (Startzeit im Viewer, Folge in jedem Fall eigene Route), Suchindex Tantivy vs. FTS5 (Empfehlung Tantivy, SQLite als Wahrheit), Inhalts-Schlüssel Datei-Hash vs. PCM-Fingerabdruck (Datei-Hash als Vorfilter, PCM-Fingerabdruck als Schlüssel prüfen), Verankerung von Korrekturen an Zeit- und Wortpositionen.

### Phase 2: Erfassung aller Dateien
**Goal**: Ohne Konfiguration kennt das System alle Audio- und Videodateien der Instanz, inklusive Gruppenordner und externer Speicher, respektiert Ausschlüsse von Anfang an und rechnet gleichen Inhalt nur einmal.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: DISC-01, DISC-02, DISC-03, DISC-04, DISC-05, DISC-06
**Success Criteria** (what must be TRUE):
  1. Nach der Installation listet `occ` alle Audio- und Videodateien aller Nutzer und Gruppenordner im Arbeitsvorrat; externe Speicher (SMB, S3) erscheinen, bis der Admin sie per Schalter ausschließt.
  2. Ausgeschlossene Nutzer, Gruppen und Ordner landen nie im Arbeitsvorrat, auch wenn der Ausschluss vor dem ersten Durchlauf gesetzt wurde; ein nachträglicher Ausschluss entfernt vorhandene Einträge und Transkripte.
  3. Eine neu hochgeladene oder geänderte Datei steht innerhalb weniger Minuten im Arbeitsvorrat; eine außerhalb von Nextcloud geänderte Datei auf externem Speicher wird spätestens beim periodischen Abgleich erkannt.
  4. Kopie, Verschieben, Umbenennen, Taggen und dieselbe externe Freigabe bei mehreren Nutzern erzeugen keinen zweiten Rechenauftrag (Inhalts-Schlüssel).
**Plans**: 22 plans (11 Wellen)
Plans:
- [x] 02-01-PLAN.md: (W1) Abnahme D-02-07 Teil 1: Workflow, Samba/S3/Freigabe-Topologie, Kontrollbein leak-control
- [x] 02-02-PLAN.md: (W1) Container: Schema v2 mit Migration
- [x] 02-03-PLAN.md: (W1) PHP: Tabellen, Warteschlange, Mountmenge, Queue-Routen
- [x] 02-04-PLAN.md: (W2) Abnahme Teil 2: unabhängige Wahrheit, Ledger, Vergleich, Positivkontrollen
- [x] 02-05-PLAN.md: (W2) Container: Intake mit Ack nach Eintrag
- [x] 02-06-PLAN.md: (W2) PHP: Erst-Crawl nach Handshake, Gate-Regeln 12/13
- [x] 02-07-PLAN.md: (W2) PHP: Node- und Cache-Ereignisse
- [x] 02-08-PLAN.md: (W3) Container: Erfassung per Temp-Download mit Längenprüfung
- [ ] 02-09-PLAN.md: (W3) Container: Zählung nach Inhalten, /workstock, /coverage
- [ ] 02-10-PLAN.md: (W3) PHP: Gateway access_control/locked, Kopf-Route, occ :files/:status
- [ ] 02-11-PLAN.md: (W4) Owner: Push 1 auf phase-02 hinter Freigabedatei, prüfbare CI
- [ ] 02-12-PLAN.md: (W5) PHP: externe Speicher, Klassifikation, Vorfilter-Schlüssel, Leser
- [ ] 02-13-PLAN.md: (W5) Container: Lesebeweis und erneuter Beweis, Gate ohne Abschaltweg, CI-Patch
- [ ] 02-14-PLAN.md: (W6) PHP: ExternalRescanJob und occ :rescan
- [ ] 02-15-PLAN.md: (W6) Container: Ausschluss vergisst, Löschen und Papierkorb merken vor
- [ ] 02-16-PLAN.md: (W7) PHP: Ausschlüsse vor dem ersten Durchlauf, dreifach geprüft
- [ ] 02-17-PLAN.md: (W8) Owner: Push 2, Sicherheitsteil in CI
- [ ] 02-18-PLAN.md: (W9) PHP: rückwirkender Ausschluss, Gruppen, Papierkorb-Ereignisse
- [ ] 02-19-PLAN.md: (W9) PHP: Abgleich-Routen mit requeue, occ :reconcile
- [ ] 02-20-PLAN.md: (W9) Container: Abgleich mit Sweep vor dem Tor und erneutem Lesebeweis
- [ ] 02-21-PLAN.md: (W10) Owner: Version 0.2.0, Upgrade vom echten 0.1.0, Doku nach Textfreigabe
- [ ] 02-22-PLAN.md: (W11) Owner: Push 3, Abnahme auf sechs Beinen
**Research flag**: Sperrfrist für lange Vorschauen, SMB/S3-Timeouts, Sitzungs-Anmeldedaten bei externen Speichern, `files_accesscontrol`, Crawl-Flag-Tor für den Abgleich.

### Phase 3: Vorschau-Transkripte in der Suche
**Goal**: Nutzer finden gesprochenen Text ihrer Aufnahmen in Minuten über die normale Nextcloud-Suche, als vorläufig gekennzeichnet und nur in Dateien, die sie lesen dürfen (Kernwert in Vorschau-Qualität).
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: MEDIA-01, MEDIA-02, MEDIA-03, MEDIA-04, TRANS-01, TRANS-02, TRANS-03, TRANS-07, TRANS-08, SRCH-01, SRCH-02, SRCH-03
**Success Criteria** (what must be TRUE):
  1. Ein Nutzer lädt eine Aufnahme hoch (MP3, M4A, WAV, OGG, Opus, FLAC, MP4 auch mit Index am Dateiende, MOV, MKV, WebM) und findet wenige Minuten später ein gesprochenes Wort in der Unified Search mit Zeitmarke, Ausschnitt, mehreren Stellen je Datei und dem Kennzeichen "vorläufig"; der Klick springt wortgenau an die Stelle.
  2. Musik, Stille oder Rauschen erscheinen als "keine Sprache", defekte, geschützte oder überlange Dateien als übersprungen mit Grund, eine echte Aufnahme in nicht unterstützter Sprache als "Sprache nicht unterstützt"; nichts wird still geleert, fremde Schrift und Halluzinationen tauchen nicht im Index auf.
  3. Ein Nutzer ohne Leserecht (entzogene Freigabe, Gruppenordner-ACL `+read -share`, Papierkorb) sieht keinen Treffer aus der Datei; der Rechte-Paritätstest läuft im HTTP-Pfad in CI.
  4. Wird der Container während einer langen Datei beendet, setzt die Vorschau nach dem Neustart am letzten fertigen Stück fort; VAD lässt sich nirgends abschalten.
**Plans**: TBD
**Research flag**: Standardmuster (Spike-Code vorhanden, Findling-Rechteprüfung). Medienkorpus für Fuzz/Formate anlegen; Gesang/Musik für "keine Sprache" und Sprachen außerhalb DE/EN/FR sind ungemessen. Hinweis: Parakeet läuft hier schon als Kindprozess; der vollständige cgroup-Wächter folgt in Phase 5.

### Phase 4: Suchqualität und Export
**Goal**: Nutzer finden gesprochene Inhalte auch über Wortformen, Komposita-Teile und Zahlen, behalten die Treffer bei gesetzten Filtern und laden je Datei Untertitel-Entwürfe und Transkripte herunter oder legen sie neben das Medium.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: SRCH-04, SRCH-05, SRCH-06, EXP-01, EXP-02, EXP-03, EXP-04
**Success Criteria** (what must be TRUE):
  1. Die Suche nach "Haushalt" findet "Haushaltsplanberatung", "Häuser" findet "Haus", "zwölf" findet "12" und umgekehrt, in DE, EN und FR.
  2. Setzt ein Nutzer einen Datums- oder Personenfilter, bleibt die Ergebnisgruppe sichtbar.
  3. Ein Nutzer lädt je Datei SRT, VTT und TXT herunter; die Untertitel halten die Grenzen (42 Zeichen, 2 Zeilen, 1 bis 7 s, 20 Zeichen/s, ca. 80 ms Abstand), bestehen einen unabhängigen Parser und heißen überall "Untertitel-Entwurf", nirgends "BITV-konform".
  4. Ein Nutzer legt `<Name>.<Sprache>.vtt` neben das Medium; eine vorhandene Datei gleichen Namens wird nie überschrieben.
  5. Über eine Freigabe mit Download-Sperre findet der Empfänger Treffer, bekommt aber keinen Export und keine Nebendatei.
**Plans**: TBD
**UI hint**: yes
**Research flag**: Standardmuster (Findling-Muster für Tantivy-Normalisierung). Viewer-Untertitel-Schema für NC 33 bis 35 unbelegt, Nebendatei vor dem Plan gegen den Viewer prüfen.

### Phase 5: Ressourcen, Profile und Modellbezug
**Goal**: Die App läuft auf jeder unterstützten Hardware sicher: sie schlägt das beste sicher lauffähige Profil vor, startet kein Modell ohne genug Speicher, trifft bei Speichermangel nie Nextcloud oder die Datenbank und bezieht Modelle nachprüfbar und abschaltbar.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: RES-01, RES-02, RES-03, RES-04, RES-05, RES-06, RES-07, PLAT-04
**Success Criteria** (what must be TRUE):
  1. Der Admin sieht beim Start ein vorgeschlagenes Profil (aus cgroup-RAM/CPU und kurzem Eigentest) und kann es ändern; nicht lauffähige Profile sind mit Grund gesperrt.
  2. In einem Container mit `--memory=2g` startet kein Modell ohne Bedarf plus Reserve; ein provozierter Speichermangel beendet nur einen Erkennungs-Kindprozess, nie Nextcloud oder die Datenbank.
  3. Der Admin begrenzt Threads und setzt ein Rechenfenster; außerhalb des Fensters wird nicht gerechnet; Vorschauen kommen vor Veredelung, neueste Datei zuerst.
  4. Parakeet und Silero VAD sind im Image; Whisper-Modelle werden mit festem Commit und sha256 nur von der Host-Allowlist geladen oder offline abgelegt; im Offline-Modus gibt es keinerlei ausgehende Verbindung (Netzwerkmitschnitt).
  5. Namensnennung NVIDIA Parakeet (CC-BY-4.0) und alle Drittlizenzen stehen in App, README und THIRD-PARTY.md.
**Plans**: TBD
**UI hint**: yes
**Research flag**: HF-CDN-Hosts für die Allowlist, Profilschwellen, optional int8-Vorkonvertierung von turbo, huggingface-hub 2.x im ersten Container-Build. Profilvorwahl bis Phase 11 nur RAM-basiert.

### Phase 6: Veredelung
**Goal**: Im Leerlauf ersetzt ein besseres Transkript die Vorschau atomar und ohne Textverlust, nach dem gewählten Profil; die Suche bleibt dabei durchgehend verfügbar, und jeder Build beweist per Schnell-Gate, dass die Qualität den Spike-3-Werten entspricht.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-05, QUAL-06, TRANS-04, TRANS-05, REL-01
**Success Criteria** (what must be TRUE):
  1. Mit "Ausgewogen" (Standard) verliert ein Treffer nach dem Leerlauf das Kennzeichen "vorläufig" und zeigt den ROVER-Text aus Parakeet und turbo; mit "Schnell" werden nur Fenster mit Konfidenz < 0,8 nachgerechnet; mit "Qualität" bekommen deutsche Dateien zusätzlich large-v3 und ROVER turbo + large-v3.
  2. Während eines Ersatzes liefert die Suche jederzeit entweder den alten oder den neuen Stand, nie einen Mischzustand; Snippets und Untertitel zeigen die Oberflächenform (Groß-/Kleinschreibung, Satzzeichen).
  3. Kein korrekt erkanntes Vorschau-Wort geht durch den Ersatz verloren (Abdeckungs-Wächter je Fenster, im Schnell-Gate gemessen).
  4. Nach einem Profilwechsel rechnet die App nur die Differenz zum neuen Zielniveau nach, keine Vollneuberechnung.
  5. Das Schnell-Gate (Kernsätze, Nicht-Sprache, Lücken, gepaarter Bootstrap) läuft in jedem Build und schlägt bei Rückschritt gegenüber Spike 3 fehl; die Whisper-Einstellungen sind fest (int8, beam 1, `condition_on_previous_text=False`, kein `initial_prompt`, keine hotwords).
**Plans**: TBD
**Research flag**: ROVER-Kosten auf 3-h-Dateien, Abbildung normalisierter Token auf Originalwörter (WER muss gleich bleiben), Speicherwachstum langer Dateien in Stücken.

### Phase 7: Sprachen und Sprachwechsel
**Goal**: Der Admin legt die Instanz-Sprachen fest, und Aufnahmen mit Sprachwechsel innerhalb einer Datei werden je Fenster in der richtigen Sprache nachgerechnet, so dass das bessere Ergebnis in der Suche steht.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: QUAL-04, ADM-05
**Success Criteria** (what must be TRUE):
  1. Der Admin stellt die Instanz-Sprachen ein (Standard DE/EN/FR); die Abfangregel und die Spracherkennung richten sich danach.
  2. In einer gemischt deutsch-englischen oder französisch-englischen Aufnahme findet ein Nutzer Wörter beider Sprachen korrekt geschrieben; die WER auf dem mixlang-Satz sinkt messbar (Spike-3-Vollweg: 70 % auf 35 %).
  3. Bei einsprachigen Dateien kostet die Sprachwechsel-Prüfung keine messbare Qualität und nur begrenzt Rechenzeit (Auslöser gemessen, nicht Vollweg für jede Datei).
**Plans**: TBD
**Research flag**: Komplett offen, Messung Pflicht: nur der Vollweg ist gemessen (69,8 % auf 34,9 %, RTF 1,39); Auslöser, Fensterprüfung und Kosten erst messen, dann bauen.

### Phase 8: Lebenszyklus und DSGVO
**Goal**: Transkripte folgen dem Leben ihrer Dateien: Gelöschtes verschwindet sofort aus der Suche und nach kurzer Karenz aus dem Speicher, endgültig Gelöschtes hinterlässt nichts, und der Admin kann alles löschen.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: LIFE-01, LIFE-02, LIFE-03, LIFE-04
**Success Criteria** (what must be TRUE):
  1. Ein Nutzer löscht eine Datei: der Treffer ist sofort weg; stellt er sie aus dem Papierkorb wieder her, ist sie ohne Neuberechnung wieder findbar.
  2. Nach Leeren oder Ablauf des Papierkorbs bleibt kein Transkript zurück; der periodische Abgleich meldet 0 Waisen.
  3. Eine wiederhergestellte ältere Version oder ein geänderter Inhalt wird neu bewertet und zeigt danach den passenden Text.
  4. Der Admin löscht alle Transkripte mit einer Aktion; nach einem provozierten Absturz liegen keine Temp-Dateien mehr herum.
**Plans**: TBD
**Research flag**: Papierkorb ohne Löschereignis, Ereignislage bei Versionswiederherstellung je NC-Version.

### Phase 9: Ehrliche Admin-Zustände und Dreisprachigkeit
**Goal**: Der Admin sieht jederzeit ehrlich, wo die Instanz steht, kann pausieren und Fehlgeschlagenes neu anstoßen, und alle Texte sind in DE, EN und FR im Gleichstand.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: ADM-01, ADM-02, ADM-03, ADM-04, I18N-01, I18N-02
**Success Criteria** (what must be TRUE):
  1. Der Admin sieht Zähler für erfasst, Vorschau fertig, veredelt, übersprungen und fehlgeschlagen samt Restzeit-Schätzung; übersprungene und fehlgeschlagene Dateien erscheinen nur als Zähler mit Grund, ohne Dateinamen; Details liefert `occ`.
  2. Der Admin pausiert und setzt fort, in der Oberfläche und per `occ`; während der Pause startet keine neue Erkennung.
  3. Eine dauerhaft fehlerhafte Datei wird höchstens dreimal zugestellt und steht dann als `failed` mit Grund; der Admin kann sie neu anstoßen.
  4. Das Sprach-Gate in CI schlägt fehl, sobald ein nutzersichtbarer Text, Store-Text oder README-Abschnitt in DE, EN oder FR fehlt; `de_DE` greift als Rückfall; das Umlaut-Audit findet keine ASCII-Ersatzumlaute, Gedankenstriche oder Emojis.
**Plans**: TBD
**UI hint**: yes
**Research flag**: Standardmuster (Findling-Kataloge und Gates); Zustände als Schlüssel, PHP übersetzt.

### Phase 10: BITV-Weg
**Goal**: Nutzer mit Schreibrecht machen aus einem automatischen Transkript geprüfte, barrierefreie Untertitel: Text und Zeiten korrigieren, Sprecher und Geräusche markieren, als "geprüft" freigeben und erst dann ohne Entwurf-Kennzeichen exportieren.
**Mode:** mvp
**Depends on**: Phase 4, Phase 6, Phase 7
**Requirements**: BITV-01, BITV-02, BITV-03, BITV-04, BITV-05, BITV-06
**Success Criteria** (what must be TRUE):
  1. Ein Nutzer korrigiert neben dem Player Text und Zeitgrenzen; nach einer späteren Veredelung oder Neuberechnung sind seine Korrekturen noch da.
  2. Ein Nutzer setzt Sprecher-Marken, benennt Sprecher und fügt Geräusch-Marken wie "[Applaus]" ein; Suche und Export zeigen sie.
  3. Erst nach "geprüft" exportiert die App Untertitel ohne Entwurf-Kennzeichen, mit Sprecher- und Geräuschangaben nach BITV 9.1.2.2 / WCAG 1.2.2; ungeprüfte Exporte bleiben "Untertitel-Entwurf".
  4. Ein Nutzer mit nur Leserecht kann weder korrigieren noch prüfen (Negativtest); jede Änderung zeigt Nutzer und Zeit.
  5. Der Editor ist vollständig per Tastatur und Screenreader bedienbar und besteht eine WCAG-2.1-AA-Prüfung (axe plus manueller Durchgang, hell/dunkel, drei Breiten).
**Plans**: TBD
**UI hint**: yes
**Research flag**: Editor-Muster für zeitgebundene Transkripte in Nextcloud-Vue, Konfliktfall Korrektur gegen Neuberechnung (Verankerung aus Phase 1), BITV 9.1.2.2 Prüfschritte im Detail.

### Phase 11: Release-Gate, Hardware-Messung und Volltest
**Goal**: Vor dem Store-Release ist belegt, dass Qualität, Robustheit und Tempo auf echter Zielhardware stimmen und alle Funktionen und Meldungen in DE, EN und FR fehlerfrei sind.
**Mode:** mvp
**Depends on**: Phase 8, Phase 9, Phase 10
**Requirements**: REL-02, REL-03, REL-04, REL-05
**Success Criteria** (what must be TRUE):
  1. Das Release-Gate (46 Sätze, 8,2 h, sha256-geprüft, Daten per Skript erzeugt, nicht im Repo) ist grün, inklusive "verlorene korrekte Vorschau-Wörter" und Negativsatz fremder Sprachen (FLEURS tr/ar/uk).
  2. Auf Pi 5 und N100 sind RTF und RAM je Profil gemessen; die Profilvorwahl nutzt diese echten Werte.
  3. OOM-, Offline-, Fuzz-Medien-, 50-Dateien-Dauer- und Rechte-Negativtests laufen ohne Datenverlust, ohne ausgehende Verbindung und ohne Rechteleck.
  4. Der große Volltest aller Funktionen und Meldungen in DE/EN/FR ist gemeinsam mit dem Owner per Playwright abgenommen (drei Breiten, hell/dunkel); der Store-Text behauptet nirgends "BITV-konform" für ungeprüfte Untertitel.
**Plans**: TBD
**UI hint**: yes
**Research flag**: arm64-Tempo, Pi 5 und N100 ungemessen; Cassini-Stand vor Release prüfen.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11. Phase 5 und Phase 8 hängen nur an Phase 3 bzw. 4 und können bei Bedarf vorgezogen werden.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Zwei-App-Gerüst und Integrationsbeweis | 13/13 | Complete    | 2026-11-07 |
| 2. Erfassung aller Dateien | 8/22 | In Progress|  |
| 3. Vorschau-Transkripte in der Suche | 0/TBD | Not started | - |
| 4. Suchqualität und Export | 0/TBD | Not started | - |
| 5. Ressourcen, Profile und Modellbezug | 0/TBD | Not started | - |
| 6. Veredelung | 0/TBD | Not started | - |
| 7. Sprachen und Sprachwechsel | 0/TBD | Not started | - |
| 8. Lebenszyklus und DSGVO | 0/TBD | Not started | - |
| 9. Ehrliche Admin-Zustände und Dreisprachigkeit | 0/TBD | Not started | - |
| 10. BITV-Weg | 0/TBD | Not started | - |
| 11. Release-Gate, Hardware-Messung und Volltest | 0/TBD | Not started | - |

---
*Roadmap created: 2026-11-06*
