# Feature Research

**Domain:** Lokale, automatische Transkription und Volltextsuche für Audio- und Videodateien in Nextcloud (ExApp mit Unified-Search-Anbindung, SRT/VTT-Export)
**Researched:** 2026-11-06
**Confidence:** MEDIUM (Nextcloud-Plattformfakten HIGH, da im Quellcode geprüft; Wettbewerber-Funktionen MEDIUM bis LOW, meist aus Herstellerseiten oder Sekundärquellen)

Der v1-Umfang steht (PROJECT.md, Active und Out of Scope). Diese Datei schärft, was Nutzer und Admins innerhalb dieses Umfangs erwarten, und benennt vier Plattformbefunde, die die Anforderungen direkt verändern.

## Vier Befunde, die die Anforderungen verändern

1. **Kein Sprung auf die Zeitstelle im Nextcloud-Viewer.** [HIGH, Quellcode geprüft] Der Viewer in NC 33 bis 35 (Plyr, `nextcloud/viewer` stable35) kennt keinen Startzeitpunkt. Die Feature-Requests [viewer#2176](https://github.com/nextcloud/viewer/issues/2176) ("Navigate to specific timestamps in video urls") und [viewer#3226](https://github.com/nextcloud/viewer/issues/3226) ("Starting an audio at a specific timestamp") wurden am 25.10.2026 als `not_planned` geschlossen, weil der Viewer in die Bibliothek `@nextcloud/viewer` umzieht. Auch diese Bibliothek (v2.0.0-beta.20, nur im Server-`master` = NC 36 dev) hat keine Startzeit; `currentTime` wird nur auf 0 gesetzt. Folge: "Klick öffnet Datei an der Stelle" ist mit dem Viewer nicht machbar. v1 braucht eine **eigene, minimale Abspielansicht für genau einen Treffer** (HTML5-`<video>`/`<audio>` mit WebDAV-Quelle und Media Fragment `#t=`), ausgeliefert über die PHP-Begleit-App. Das ist keine Medienübersicht (bleibt v2), muss aber als Owner-Entscheid festgehalten werden, weil PROJECT.md "keine eigene App-Seite" sagt.
2. **AppAPI kann keinen Unified-Search-Provider registrieren.** [HIGH] Die AppAPI-API-Liste ([ExApp API](https://docs.nextcloud.com/server/stable/developer_manual/exapp_development/tech_details/api/index.html)) enthält Routen, File Actions, Top-Menü, deklarative Einstellungen, Benachrichtigungen, Events, OCC, Talk-Bots, aber keine Suche. Findling hat das verifiziert und löst es mit einer PHP-Begleit-App (`OCP\Search\IFilteringProvider`, nicht `IExternalProvider`, Proxy über `PublicFunctions::exAppRequest()`, 2,5 s Budget). Dasselbe Muster gilt hier. Die Subline der Suchergebnisse wird als Klartext gerendert (kein HTML, also keine Hervorhebung per Markup).
3. **Automatische Untertitel erfüllen WCAG 1.2.2 / BITV 9.1.2.2 nicht von selbst.** [HIGH] W3C WAI: "Automatically-generated captions do not meet user needs or accessibility requirements" unless "confirmed to be fully accurate" ([W3C Captions/Subtitles](https://www.w3.org/WAI/media/av/captions/)). BITV-Prüfschritt 9.1.2.2 verlangt alle Informationen der Tonspur, "wer spricht" und "bedeutungstragende Tonereignisse" ([bitvtest 9.1.2.2](https://bitvtest.de/pruefschritt/bitv-20-web/bitv-20-web-9-1-2-2-aufgezeichnete-videos-mit-untertiteln)). Ohne Diarisierung (v2) und ohne Korrektur (v2) liefert v1 einen **prüffähigen Untertitel-Entwurf**, keine Konformität. Store-Text und README müssen das so sagen. Für reine Audiodateien verlangt WCAG 1.2.1 ein Text-Transkript, keine Untertitel.
4. **Der neue Viewer zeigt Untertitel-Nebendateien automatisch.** [HIGH für die Bibliothek, MEDIUM für den Zeitpunkt der Auslieferung] `@nextcloud/viewer` PR #184 (gemergt 02.11.2026) blendet `film.vtt`, `film.de.vtt`, `film.pt-BR.srt` neben `film.mp4` als Spur ein, SRT wird clientseitig nach VTT gewandelt, Freigaben mit Download-Sperre werden ausgelassen ([useSubtitles.ts](https://github.com/nextcloud-libraries/nextcloud-viewer/blob/main/lib/composables/useSubtitles.ts), [subtitleNames.ts](https://github.com/nextcloud-libraries/nextcloud-viewer/blob/main/lib/utils/subtitleNames.ts)). Ein Export als `<Name>.<Sprache>.vtt` neben die Datei wird damit ab NC 36 ohne jede eigene Oberfläche im Player sichtbar. NC 33 bis 35 zeigen sie nicht.

## Feature Landscape

### Table Stakes (Users Expect These)

#### A. Suche und Trefferdarstellung

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Treffer im gesprochenen Text in der normalen Nextcloud-Suche | Kern des Produkts; Google Drive und Microsoft 365 suchen seit 2025 im Transkript mit ([Google Workspace Updates](https://workspaceupdates.googleblog.com/2025/02/google-drive-video-transcripts.html), [Stream-Blog](https://techcommunity.microsoft.com/blog/streamblog/transcripts-and-captions-coming-to-stream-on-sharepoint/2681316)) | MEDIUM | PHP-Begleit-App mit `IFilteringProvider` (Befund 2). `getOrder()` nie `null`, sonst ist der Provider unsichtbar (Findling-Befund). |
| Zeitmarke im Treffer sichtbar ("12:34") | Ohne Zeitmarke ist ein Treffer in einer 2-h-Aufnahme wertlos; Stream, Drive, Otter, Scriberr zeigen alle die Stelle | LOW | Format `m:ss` unter 1 h, `h:mm:ss` darüber; als Teil der Subline (Klartext). |
| Textausschnitt um das Suchwort | Nutzer müssen ohne Abspielen entscheiden, ob der Treffer passt | LOW | Klartext-Snippet, ca. 8 bis 12 Wörter um den Treffer, Wortgrenzen nicht zerschneiden; keine HTML-Hervorhebung möglich (Subline ist `{{ subline }}`). |
| Klick springt an die Stelle | Stream und Drive: Klick auf Satz springt zur Stelle ([Google](https://workspaceupdates.googleblog.com/2025/02/google-drive-video-transcripts.html), [UT Dallas KB](https://atlas.utdallas.edu/TDClient/30/Portal/KB/Article/943/Transcriptions-in-Stream-On-SharePoint)) | MEDIUM | Viewer kann es nicht (Befund 1). Minimale Abspielansicht mit `#t=<Sekunden>`; Start 1 bis 2 s vor dem Treffer bzw. am Satz-/Cue-Anfang, damit der Kontext hörbar ist. |
| Mehrere Fundstellen je Datei | Ein Begriff fällt in einer Sitzung oft mehrfach; Stream und Otter listen alle Vorkommen | MEDIUM | Unified Search kennt nur flache Einträge: je Datei die besten 2 bis 3 Stellen als eigene Einträge, Rest über "Mehr laden" (Cursor). Nah beieinanderliegende Treffer (unter ca. 30 s) zu einem zusammenfassen. |
| Vorschaubild bzw. Dateityp-Icon | Sieht aus wie die Dateisuche | LOW | Video-Vorschau braucht den Movie-Preview-Provider (ffmpeg im Server, nicht Standard); sonst MIME-Icon. Nie leeres Bild. |
| Unterstützte Filter deklarieren (`term`, `since`, `until`, `person`) | Nutzt jemand in der Suche einen Datums- oder Personenfilter, den der Provider nicht deklariert, bekommt der Provider die Anfrage gar nicht und die Gruppe verschwindet still ([Search-Doku](https://docs.nextcloud.com/server/stable/developer_manual/digging_deeper/search.html)) | LOW | `since`/`until` auf Datei-Änderungsdatum, `person` auf Besitzer. Muster aus Findling übernehmen. |
| Schnelle Antwort, auch wenn der Container hängt | Unified Search wartet je Gruppe; ein hängender Provider zeigt eine ewig drehende Gruppe | LOW | Hartes Timeout (Findling: 2,5 s), bei gestopptem Backend leere Gruppe ohne Fehlerkaskade. |
| Groß-/Kleinschreibung und Umlaute egal, Wortanfang reicht | Nutzer tippen "haushalt" und erwarten "Haushaltsplan"; ASR schreibt Komposita mal getrennt, mal zusammen | MEDIUM | Normalisierung NFC + casefold, Präfixsuche. Volle Teilwort-Suche (Trigramme) siehe Differenzierer. |
| Kennzeichnung "vorläufig" bei Vorschau-Transkript | Produktprinzip "Ehrliche Zustände"; Parakeet-Vorschau hat in FR-Spontansprache 32 bis 80 % WER (Spike 3) | LOW | Kurzer Zusatz in der Subline, z. B. "vorläufiges Transkript". Verschwindet beim atomaren Ersatz. |

#### B. Status und Fortschritt (Admin)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Zähler: gefunden, in Warteschlange, Vorschau fertig, Endfassung fertig, übersprungen, fehlgeschlagen | Context Chat zeigt Statistiken in den Admin-Einstellungen und per `occ context_chat:stats` ([Context-Chat-Doku](https://docs.nextcloud.com/server/latest/admin_manual/ai/app_context_chat.html)); Findling hat dasselbe Muster | MEDIUM | Deklarative Einstellungen können keine dynamische Statusanzeige; Statusblock gehört in die PHP-Begleit-App (Admin-Abschnitt) oder als Nur-Lese-Felder. Dependency auf Befund 2. |
| Übersprungen und Fehlgeschlagen **mit Grund** | Produktprinzip 3, PROJECT.md Active | MEDIUM | Feste Grundliste, dreisprachig: keine Tonspur, keine Sprache erkannt, Format nicht lesbar, Datei beschädigt, Ende-zu-Ende-verschlüsselt, externer Speicher nicht erreichbar, zu lang (Admin-Grenze), RAM reicht nicht für Profil, ausgeschlossen (Nutzer/Gruppe/Ordner/Speicher). Keine Rohfehlertexte aus ffmpeg im UI. |
| Restzeit-Schätzung | Bei 8,2 h Audio und RTF 0,47 (turbo) dauert der erste Lauf Stunden bis Tage; ohne Schätzung wirkt die App kaputt | LOW | Aus gemessener RTF des laufenden Rechners und Restdauer der Warteschlange; getrennt "bis alles durchsuchbar" (Vorschau) und "bis Endfassung". |
| Status per `occ` | Admins großer Instanzen arbeiten auf der Kommandozeile; Context Chat macht es so | LOW | AppAPI kann OCC-Befehle registrieren (verifiziert in der API-Liste). |
| Admin-Benachrichtigung nur bei systemischen Fehlern | Admin muss merken, wenn nichts mehr läuft (Modell fehlt, RAM-Wächter blockiert alles, Speicher voll) | LOW | AppAPI-Notifications. Nie je Datei benachrichtigen. |
| Init-Fortschritt beim ersten Start (Modell-Download) | Modelle sind 0,6 bis 3 GB; AppAPI zeigt "init progress" | LOW | `set init progress` aus der ExApp-API; Modell-sha256 prüfen (Release-Gate-Werte). |

#### C. Admin-Steuerung

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Pause / Fortsetzen | Jeder Indexer hat das (Findling, Context Chat-Warteschlange); Admin braucht CPU bei Updates oder Last | LOW | Pause stoppt neue Jobs sofort, laufender Job wird an der nächsten Stückgrenze (ca. 10 min Audio) beendet, nicht weggeworfen. |
| Ausschlüsse: Nutzer, Gruppen, Ordner, externe Speicher | PROJECT.md Active; Behörden müssen z. B. Personalakten-Ordner ausnehmen | MEDIUM | Ausschluss wirkt **rückwirkend**: vorhandene Transkripte im ausgeschlossenen Bereich werden gelöscht, nicht nur nicht mehr erzeugt. Sonst Datenschutzproblem. |
| Profilwahl Schnell / Ausgewogen / Qualität mit Hardware-Vorwahl | PROJECT.md Active, Spike 3 Abschnitt 11 | MEDIUM | Profile, die auf der Hardware nicht sicher laufen, sichtbar, aber gesperrt mit Grund ("braucht 4,5 GB frei, verfügbar 3,1 GB"). Nicht einfach ausblenden. |
| Profilwechsel mit klarer Folge | Admin muss wissen, ob bestehende Dateien neu gerechnet werden | LOW | Auswahl: "nur neue Dateien" oder "alle im Leerlauf neu rechnen"; Standard nur neue, mit Hinweis auf Dauer. |
| Instanz-Sprachen (Standard DE/EN/FR) | Die Halluzinations-Abfangregel braucht die Liste (Spike 3 Abschnitt 5) | LOW | Mehrfachauswahl; nicht gewählte Sprachen werden als Halluzination behandelt. |
| Obergrenze Dauer / Größe | Context Chat lehnt Dateien über 100 MB ab; Videos sind oft mehrere GB, Aufzeichnungen bis 8 h | LOW | Standard großzügig (z. B. 6 h Audio), Datei wird mit Grund "zu lang" übersprungen, nicht still ignoriert. |
| Thread-/CPU-Begrenzung | stt_whisper2 nutzt standardmäßig alle Kerne und empfiehlt eine eigene Maschine ([stt_whisper2-Doku](https://docs.nextcloud.com/server/latest/admin_manual/ai/app_stt_whisper2.html)); auf einem N100 würde das Nextcloud selbst lähmen | LOW | Standard 2 Threads (Spike-Messbasis), Admin kann erhöhen. |
| Transkripte löschen / bei Deinstallation entfernen | Löschkonzept (DSGVO Art. 17) für Behörden Pflicht | LOW | Knopf "Alle Transkripte löschen" mit Bestätigung; Deinstallation entfernt Daten (AppAPI-Volume). |

#### D. Fehlerbehandlung und Neu-Transkription

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Vorübergehende von dauerhaften Fehlern trennen | Externer SMB-Speicher offline ist kein Dateifehler | MEDIUM | Vorübergehend: Wiederholung mit Backoff; dauerhaft (beschädigt, keine Tonspur): einmal markieren, erst bei Dateiänderung neu versuchen. Nach N Fehlversuchen "fehlgeschlagen". |
| "Fehlgeschlagene erneut versuchen" (Admin) | Nach Behebung (mehr RAM, Speicher wieder da) muss der Admin nicht jede Datei anfassen | LOW | Ein Knopf, plus `occ`. |
| Wiederaufnahme langer Dateien | Container-Neustart mitten in einer 3-h-Aufnahme darf nicht 1,5 h Rechenzeit vernichten | MEDIUM | Ergebnis je Stück (ca. 10 min) zwischenspeichern; Fortsetzen ab letztem fertigen Stück. Dependency auf Stückelung (Spike 3 Abschnitt 6). |
| Neu-Transkription bei Inhaltsänderung | Neue Dateiversion = neuer Inhalt | MEDIUM | Auslöser: etag/Größe/mtime geändert. **Nicht** bei Umbenennen oder Verschieben innerhalb des Speichers (fileId bleibt). Alte Fassung bleibt durchsuchbar, bis die neue Vorschau fertig ist. |
| Löschen, Papierkorb, Rechteentzug wirkt sofort | PROJECT.md Active; Treffer aus gelöschter Datei wären ein Datenleck | MEDIUM | Prüfung zur Abfragezeit (Findling-Muster: Overfetch, Recheck je Treffer), nicht nur per Event. Dateien im Papierkorb nie liefern. |
| Atomarer Ersatz Vorschau zu Endfassung | PROJECT.md Active; Suche darf nie "leer" werden | MEDIUM | Neue Fassung vollständig schreiben, dann in einer Transaktion umschalten. |
| Keine Inhalte in Logs | Owner-Regel Datenschutz; Transkripttext im Nextcloud-Log ist ein zweiter Datenspeicher ohne Löschkonzept | LOW | Logs nur mit fileId, Dauer, Fehlerklasse. |

#### E. SRT/VTT-Export

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Export je Datei als SRT und VTT über das Dateimenü | Alle Vergleichsprodukte exportieren SRT/VTT (Descript, Whishper, Scriberr, Happy Scribe); ohne eigene App-Seite ist das Dateimenü der einzige Ort | LOW bis MEDIUM | AppAPI File Actions Menu (verifiziert) für Audio-/Video-MIME-Typen. Ablage als `<Name>.<Sprache>.vtt` / `.srt` neben die Datei (Befund 4), bei fehlendem Schreibrecht als Download. |
| Bestehende Untertitel-Dateien nie überschreiben | Nutzer korrigieren den Entwurf extern (Subtitle Edit usw.); Überschreiben vernichtet Handarbeit | LOW | Existiert die Zieldatei, neuen Namen wählen (`<Name>.<Sprache>.auto-2.vtt` passt nicht ins Viewer-Namensschema, daher besser fragen bzw. Download anbieten). |
| Zeilenlänge höchstens 42 Zeichen, höchstens 2 Zeilen | Netflix DE: 42 Zeichen, 2 Zeilen ([Netflix German TTSG](https://partnerhelp.netflixstudios.com/hc/en-us/articles/217351587)); ARD/ZDF/ORF/SRF: 37 Zeichen, 2 Zeilen [MEDIUM, Sekundärquellen] | MEDIUM | Standard 42 (Bildschirm/Browser), als Admin-Option 37 (Rundfunknorm). Gilt für DE/EN/FR gleich [LOW für FR-Normen]. |
| Zeilenumbruch an Sinngrenzen | Netflix: grammatische Einheiten zusammenhalten, keine ein bis zwei kurzen Wörter allein oben, eher "Pyramide" | MEDIUM | Umbruch bevorzugt an Satzzeichen, dann vor Konjunktionen/Präpositionen; nie zwischen Artikel und Nomen. Sprachspezifische Wortlisten DE/EN/FR. |
| Cue-Dauer 1 s bis 7 s, keine Überlappung, kleiner Abstand | ARD-Standard: Mindeststandzeit 1 s [MEDIUM]; Netflix: Minimum 5/6 s ([General Requirements](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617)); übliche Obergrenze 6 bis 7 s | MEDIUM | Whisper-Segmente sind bis 30 s lang: **Cues aus Wortzeitstempeln neu bilden**, nicht aus ASR-Segmenten. Kurze Cues in Pausen hinein verlängern, Abstand zwischen Cues ca. 80 ms (2 Frames). |
| Lesegeschwindigkeit begrenzen | ARD: 13 bis 15 Zeichen/s; Netflix DE: 17 Z/s (Untertitel), 20 Z/s (SDH, gleichsprachig) | MEDIUM | Wortgetreu, also kein Kürzen: zuerst Standzeit in Pausen verlängern, dann Cue teilen. Ziel ≤ 20 Z/s (SDH-Wert, da gleichsprachig). Überschreitungen zählen und im Export-Hinweis nennen. |
| Synchronität | EN 301 549 / BITV 7.1.2: Anzeige höchstens 100 ms vom Zeitstempel ([bitvtest 7.1.2](https://bitvtest.de/pruefschritt/bitv-20-web/bitv-20-web-7-1-2-synchrone-untertitel)) | LOW | 7.1.2 betrifft den Player; unsere Pflicht ist präzise Zeitstempel. Parakeet-Wortzeiten sind präziser (Spike 2), ROVER übernimmt je Wort den Zeitstempel des gewählten Systems. |
| Formal korrekte Dateien | Viewer-Bibliothek liest VTT direkt und wandelt SRT nur per Regex (Komma zu Punkt) | LOW | UTF-8 ohne BOM, `WEBVTT`-Kopf, `hh:mm:ss.mmm` (VTT) bzw. `hh:mm:ss,mmm` (SRT), fortlaufende Nummern, LF-Zeilenenden (SRT optional CRLF). Kennzeichnung "automatisch erstellt" als `NOTE`-Block, nicht als sichtbarer Cue. |
| Text-Transkript mit Zeitmarken für Audiodateien | WCAG 1.2.1 verlangt für reine Audioaufnahmen ein Transkript, Untertitel helfen dort nicht; BITV 9.1.2.2 wertet ein Transkript neben dem Video als "teilweise erfüllt" | LOW | Gleiche File Action, Format TXT (oder Markdown) mit `[hh:mm:ss]`-Absätzen wie noScribe. Kleiner Zusatz zum v1-Export, Owner-Entscheid. |

#### F. Rechte

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Treffer nur für Nutzer mit Leserecht zur Abfragezeit | PROJECT.md Active; sonst Datenleck | MEDIUM | Findling-Muster übernehmen (Recheck gegen `oc_filecache`/Node-API je Treffer). |
| Gruppenordner inkl. erweiterter Rechte (ACL) | Behörden und Schulen arbeiten in Gruppenordnern | MEDIUM | ACL-Prüfung über die Node-API des Nutzers, nicht über eigene Rechtelogik. |
| `files_accesscontrol`-Regeln respektieren | Context Chat tut das ausdrücklich nicht ([Context-Chat-Doku](https://docs.nextcloud.com/server/latest/admin_manual/ai/app_context_chat.html)); Behörden setzen es für Zugriffsregeln ein | MEDIUM | Auch Differenzierer gegenüber Context Chat. Prüfen, ob der Node-Zugriff im Nutzerkontext die Regeln greifen lässt [LOW, ungeprüft]. |
| Freigabe mit Download-Sperre: Suche ja, Export nein | Die Viewer-Bibliothek lässt Untertitel solcher Freigaben bewusst weg ("its subtitles are its content as much as the video") | LOW | Abspielen ist erlaubt, also auch Fundstelle; Datei-Export nicht. Owner-Entscheid festhalten. |
| Ende-zu-Ende-verschlüsselte Ordner überspringen | Server sieht den Inhalt nicht | LOW | Grund "Ende-zu-Ende-verschlüsselt" im Status. Serverseitige Verschlüsselung ist lesbar und kein Ausschlussgrund. |
| Föderierte Freigaben nicht transkribieren | Datei liegt auf einem fremden Server; Transkription wäre Verarbeitung fremder Daten | LOW | Wie externer Speicher behandeln, aber Standard aus. |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Vollautomatisch und ohne Konfiguration für alle Dateien | Keine Store-App tut das lokal: stt_whisper2 nur auf Anfrage über Assistant/Talk und nur x86_64/NVIDIA; Context Chat indexiert kein Audio/Video; LinTO und Audiolog schicken Audio an externe Dienste; Cassini nur Talk-Aufnahmen | HIGH | Core Value. Datei-Walk + Events, Findling-Muster. |
| Erst in Minuten durchsuchbar, später beste Qualität | Spike 3: Vorschau ca. 7 min je Stunde Audio, Endfassung ca. 35 min; Cloud-Dienste liefern einmal | HIGH | Zwei Warteschlangen: **erst alle Vorschauen, dann Endfassungen**, jeweils neueste Datei zuerst. Sonst wartet ein frischer Upload hinter einem Archiv-Rückstand. |
| arm64 und kleine Hardware | stt_whisper2 unterstützt nur x86_64 und NVIDIA ([Doku](https://docs.nextcloud.com/server/latest/admin_manual/ai/app_stt_whisper2.html)) | HIGH | Messung Pi 5 / N100 vor Release (PROJECT.md). |
| Untertitel im Player ohne eigene Oberfläche (ab NC 36) | Befund 4: Nebendatei-Konvention des neuen Viewers | LOW | Nur Namensschema einhalten; auf NC 33 bis 35 sichtbar in der eigenen Abspielansicht als `<track>`. |
| Rechenfenster (z. B. nur nachts oder nur im Leerlauf) | Kleine Server teilen sich die CPU mit Nextcloud; Admins wollen tagsüber volle Reaktionszeit | MEDIUM | Zusätzlich zu Pause. Leerlauf-Erkennung ist für das Ausgewogen-Profil ohnehin nötig ("turbo im Leerlauf"). |
| Inhalts-Hash-Dedupe | Dieselbe Vorlesung in fünf Nutzerordnern oder kopiert nach Gruppenordner: einmal rechnen statt fünfmal | MEDIUM | Transkript je Inhalts-Hash, Rechte weiter je fileId. Spart bei Schulen viel CPU. Hash-Berechnung großer Videos kostet I/O: etag + Größe als Vorfilter. |
| Teilwort-Suche für Komposita | Deutsch: "Haushalt" findet "Kreishaushalt"; Cloud-Suchen sind dort oft schwach [LOW, nicht gemessen] | MEDIUM | z. B. SQLite FTS5 mit Trigramm-Tokenizer zusätzlich zur Wortsuche; Ranking ganze Wörter vor Teilwörtern. |
| Ehrliche Qualitätsangabe je Datei | Produktprinzip 3; kein Wettbewerber nennt erwartbare Fehlerquote | LOW | Nur "vorläufig" / "Endfassung" und ggf. "schwierige Aufnahme" bei niedriger mittlerer Konfidenz. Keine WER-Zahl je Datei erfinden. |
| `files_accesscontrol` und Gruppenordner-ACL korrekt | Context Chat hat hier eine dokumentierte Lücke | MEDIUM | Siehe Table Stakes F; als Vorteil im Store-Text nur nach eigenem Test nennen. |
| Erkennung "keine Sprache" (Musik, Stille, Bildschirmvideos ohne Ton) | Musiksammlungen würden sonst Stunden CPU verbrauchen und Liedtext-Müll erzeugen | MEDIUM | Spike 3: mit VAD 0 Wörter auf Stille/Rauschen/Klavier; **Gesang ist nicht gemessen**. Regel: Sprachanteil nach VAD unter Schwelle = "keine Sprache erkannt", Endfassung entfällt. Braucht Messung. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| "BITV-konforme Untertitel" als Werbeversprechen | Starkes Verkaufsargument bei Behörden | W3C: automatische Untertitel erfüllen die Anforderung nur nach Bestätigung; BITV 9.1.2.2 verlangt Sprecher und Geräusche, beides fehlt in v1 | "Untertitel-Entwurf für die barrierefreie Nachbearbeitung" sagen; Lücken (Sprecher, Geräusche) im README nennen. |
| Benachrichtigung an Nutzer für jede fertige Datei | Fühlt sich transparent an | Bei Erstindexierung hunderte Meldungen je Nutzer | Status "vorläufig/Endfassung" im Treffer; Admin-Meldung nur bei systemischen Fehlern. |
| Transkripte automatisch als Dateien in die Nutzerordner legen | Sichtbar, sofort im Viewer (ab NC 36) | Füllt jeden Ordner mit Nebendateien, triggert Sync-Clients, kollidiert mit Nutzerdateien, Löschen schwer | Transkripte in der ExApp-Datenbank; Nebendatei nur auf Klick (File Action). |
| Admin sieht Transkripttexte oder Dateilisten aller Nutzer | Fehlersuche | Admin sieht in Nextcloud sonst keine Nutzerinhalte; Transkript ist Inhalt | Status mit Zählern und Gründen; bei Fehlern fileId und Besitzer, Dateiname nur wenn der Owner das freigibt (offene Entscheidung). |
| Live-Transkription von Talk-Anrufen | Cassini, `live_transcription` (Vosk) machen das | Andere Architektur (Echtzeit), andere Rechtslage, Wettbewerb mit Nextcloud-eigenem Produkt | Talk-Aufnahmen landen als Dateien und werden wie jede Datei transkribiert. |
| KI-Zusammenfassungen, Chat mit Transkript | Scriberr, Audiolog, Otter haben es | Braucht LLM (lokal RAM-schwer, extern verboten), Halluzinationsrisiko, nicht Core Value | Später über Findling/Context Chat als Konsument der Transkripte. |
| VAD abschaltbar, Beam-Search, `initial_prompt`, Hotwords im Standard | "Mehr Regler = mehr Qualität" | Spike 3: alle signifikant schlechter oder halluzinieren | Keine Regler dafür; feste Werte aus Spike 3 Abschnitt 11. |
| Sprache je Datei vom Nutzer festlegen (v1) | Bei Fehlerkennung naheliegend | Spike 3: Erkennung war auf allen Sprachdateien richtig; Mischsprache wird je Fenster gelöst | Erst bei belegtem Bedarf (v1.x) als File Action "Sprache festlegen und neu rechnen". |
| Fortschrittsbalken je Datei in der Nutzer-Oberfläche | Gewohnt aus Otter/Happy Scribe | Braucht eigene Seite oder Sidebar-Tab (v2-Umfang) | Admin-Status plus Kennzeichnung im Treffer. |

## Feature Dependencies

```
PHP-Begleit-App (Search-Provider + Admin-Statusabschnitt + Abspielansicht)
    ├──requires──> ExApp-Proxy-Endpunkte (Suche, Status, Snippet)
    │                  └──requires──> Transkript-Speicher mit Wortzeiten
    │                                     └──requires──> Pipeline (Parakeet-Vorschau, VAD, Wächter)
    ├──enables──> Unified-Search-Treffer mit Zeitmarke
    │                  └──requires──> Rechte-Recheck zur Abfragezeit
    └──enables──> Sprung an die Stelle (Abspielansicht, #t=)

Datei-Walk + Events ──requires──> Ausschlüsse (vor dem ersten Job!)
Ausschlüsse ──requires──> Rückwirkendes Löschen
Stückelung (ca. 10 min) ──enables──> Wiederaufnahme, RAM-Grenze, Fortschritt/Restzeit
Wortzeitstempel (ROVER je Wort) ──requires──> SRT/VTT-Cue-Bildung (nicht ASR-Segmente)
File Action (AppAPI) ──enables──> SRT/VTT/TXT-Export ──enhances──> Viewer-Untertitel ab NC 36
Endfassung (turbo/large-v3) ──requires──> Leerlauf-Erkennung ──enhances──> Rechenfenster
Atomarer Ersatz ──requires──> Versionierte Transkripte je fileId
Inhalts-Hash-Dedupe ──conflicts──> naive "Transkript gehört fileId" (Rechte dann je fileId, Inhalt je Hash)
Automatische Nebendateien ──conflicts──> Null-Konfiguration ohne Nebenwirkung (daher nur auf Klick)
```

### Dependency Notes

- **Suche und Sprung brauchen die PHP-Begleit-App:** AppAPI kann weder Suchanbieter noch eine Abspielansicht mit Startzeit liefern, die ohne Top-Menü-Eintrag auskommt. Die Begleit-App ist deshalb Voraussetzung für das Kernversprechen und gehört in eine frühe Phase (Findling-Muster, Zertifikat für die zweite ID prüfen).
- **Ausschlüsse vor dem ersten Lauf:** Der erste Datei-Walk startet direkt nach der Installation (Null-Konfiguration). Ist der Ausschluss erst später gesetzt, wurden Personalakten bereits transkribiert. Standard-Ausschlüsse (Papierkorb, Versionen, appdata, E2EE, föderiert) müssen ab dem ersten Job gelten; Admin-Ausschlüsse greifen rückwirkend.
- **Cue-Bildung braucht Wortzeiten:** ASR-Segmente (Whisper bis 30 s) verletzen alle Untertitelregeln. Die Wortzeiten sind in der Pipeline vorhanden (`word_timestamps=True`, Parakeet-Wortzeiten); der Export ist damit ein reiner Nachbearbeitungsschritt.
- **Stückelung trägt drei Features:** RAM-Grenze bei langen Dateien (turbo 3,4 GB ohne Stückelung), Wiederaufnahme und Fortschrittsanzeige hängen an derselben Stückgrenze.
- **Dedupe kollidiert mit naiver Datenhaltung:** Wird das Transkript an die fileId gebunden, ist Dedupe später eine Migration. Entscheidung früh treffen.

## MVP Definition

### Launch With (v1)

- [ ] Unified-Search-Treffer mit Zeitmarke, Snippet, Kennzeichnung "vorläufig", mehrere Stellen je Datei: Kernversprechen
- [ ] Minimale Abspielansicht mit Sprung (`#t=`) und VTT-Spur: einzige Möglichkeit für "Klick öffnet an der Stelle" (Befund 1), Owner-Entscheid nötig
- [ ] Rechte-Recheck zur Abfragezeit inkl. Gruppenordner-ACL, Papierkorb, Download-Sperre: Datenschutz
- [ ] Admin-Status mit Zählern, Gründen, Restzeit; `occ`-Status: Produktprinzip 3
- [ ] Pause, Ausschlüsse (rückwirkend), Profilwahl mit gesperrten Profilen samt Grund, Instanz-Sprachen, Dauergrenze, Thread-Grenze, "alle löschen"
- [ ] Fehlerklassen vorübergehend/dauerhaft, Wiederholung, "Fehlgeschlagene erneut versuchen", Wiederaufnahme je Stück
- [ ] Neu-Transkription nur bei Inhaltsänderung, atomarer Ersatz
- [ ] SRT/VTT-Export per File Action, Cue-Regeln (42 Zeichen, 2 Zeilen, 1 bis 7 s, ≤ 20 Z/s, Umbruch an Sinngrenzen), nie überschreiben, ehrliche Kennzeichnung als Entwurf
- [ ] Erkennung "keine Sprache" für Musik/Stille: schützt CPU kleiner Rechner (Messung mit Gesang nötig)

### Add After Validation (v1.x)

- [ ] TXT-Transkript für Audiodateien: sobald ein Behördennutzer WCAG 1.2.1 nachfragt (oder gleich in v1, da billig)
- [ ] Rechenfenster (Uhrzeit): sobald Admins kleiner Rechner über Last klagen
- [ ] Inhalts-Hash-Dedupe: sobald Schulen/Gruppenordner mit Kopien auftauchen; Datenmodell aber schon in v1 vorbereiten
- [ ] Teilwort-Suche (Trigramme): wenn Suchanfragen mit Komposita leer bleiben
- [ ] "Sprache festlegen und neu rechnen" als File Action: bei belegten Fehlerkennungen
- [ ] Nutzer-Opt-out je Ordner: wenn Personalrat oder Datenschutzbeauftragte es fordern (Mitbestimmung bei technischen Einrichtungen, siehe PITFALLS)

### Future Consideration (v2+)

- [ ] Eigene Medienseite mit Transkriptansicht und Mitlesen: PROJECT.md v2
- [ ] Sprecher-Trennung: Voraussetzung für "wer spricht" in BITV 9.1.2.2
- [ ] Transkript-Korrektur im Browser: Voraussetzung für echte Untertitel-Konformität
- [ ] Geräusch-Kennzeichnung ([Applaus], [Musik]): BITV 9.1.2.2; VAD-Nicht-Sprache-Segmente sind eine Ausgangsbasis
- [ ] STT-Provider für Assistant/Talk, GPU, Findling-Anbindung

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Unified-Search-Treffer mit Zeitmarke und Snippet | HIGH | MEDIUM | P1 |
| Abspielansicht mit Sprung an die Stelle | HIGH | MEDIUM | P1 |
| Rechte-Recheck zur Abfragezeit | HIGH | MEDIUM | P1 |
| Admin-Status mit Gründen und Restzeit | HIGH | MEDIUM | P1 |
| Ausschlüsse rückwirkend, Pause | HIGH | MEDIUM | P1 |
| Fehlerklassen, Wiederholung, Wiederaufnahme | MEDIUM | MEDIUM | P1 |
| SRT/VTT-Export mit Cue-Regeln | HIGH | MEDIUM | P1 |
| "Keine Sprache"-Erkennung | MEDIUM | MEDIUM | P1 |
| Kennzeichnung vorläufig/Endfassung | MEDIUM | LOW | P1 |
| TXT-Transkript | MEDIUM | LOW | P2 |
| Rechenfenster | MEDIUM | MEDIUM | P2 |
| Inhalts-Hash-Dedupe | MEDIUM | MEDIUM | P2 |
| Teilwort-Suche | MEDIUM | MEDIUM | P2 |
| Nutzer-Opt-out je Ordner | MEDIUM | LOW | P2 |
| Sprache je Datei festlegen | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Nextcloud stt_whisper2 / Assistant | Context Chat | Cassini (Codemyriad) | Google Drive / MS Stream | Otter, Descript, Happy Scribe | Whishper, Scriberr, noScribe | Our Approach |
|---------|-----------------------------------|--------------|----------------------|--------------------------|-------------------------------|------------------------------|--------------|
| Auslösung | Nur auf Anfrage (Assistant, Talk) | Kein Audio/Video | Talk-Aufnahmen [LOW, Beta] | Drive: Untertitel manuell erzeugen, dann durchsuchbar; Stream: automatisch | Upload je Datei | Upload / Ordner-Watcher (Scriberr) | Alle Dateien automatisch, Admin schränkt ein |
| Lokal | Ja, x86_64/NVIDIA | Ja | Ja [LOW] | Nein | Nein | Ja | Ja, amd64 + arm64, nur CPU |
| Suche über alle Dateien | Nein | Nur Text-Dokumente | Unbekannt | Ja (Microsoft 365, Drive-Suche) | Ja, über eigene Bibliothek | Whishper: Volltextsuche nur Roadmap | Unified Search |
| Sprung an Stelle | Nein | Nein | Unbekannt | Ja, Klick auf Satz | Ja | Scriberr: Wiedergabe folgt Text | Ja, eigene Abspielansicht |
| Status/Fortschritt | Task-Status je Anfrage | Admin-Statistik + `occ` | Unbekannt | Kaum (Drive: "keine Admin-Kontrolle") | Je Datei | Je Job | Admin-Status mit Gründen, Restzeit, `occ` |
| SRT/VTT | Nein | Nein | Unbekannt | Upload eigener Spuren | Ja, mit Zeichen/Zeile, Zeilen je Cue, Sprecher (Descript) | Ja (Whishper, Scriberr: SRT/JSON/TXT) | Ja, feste Regeln nach Netflix/ARD, Entwurf-Kennzeichnung |
| Sprecher | Nein | Nein | Unbekannt | Teams-Aufnahmen ja | Ja | Scriberr, noScribe: ja (pyannote) | v2 |
| Korrektur | Nein | Nein | Unbekannt | Stream: ja | Ja | Ja (Editor) | v2 |
| Rechte | Assistant-Nutzer | Folgt Dateirechten, ignoriert `files_accesscontrol` | Talk-Raum | Folgt Dateirechten | Eigene Freigaben | Einzelnutzer | Folgt Dateirechten zur Abfragezeit inkl. ACL |

Weitere Store-Apps mit Transkription (geprüft im Store-Katalog am 06.11.2026): **LinTO** (Rechtsklick "Transcribe with LinTO", schickt Audio an eine LinTO-Studio-Instanz, Ergebnis als `.transcript`-Datei mit Sprechern und Editor, NC 31 bis 34) und **Audiolog** (Aufnahme und Transkription mit Gemini, OpenAI oder Ollama). Beide sind auf Anfrage, nicht automatisch, und nur mit Ollama bzw. eigener LinTO-Instanz lokal. Seafile, OnlyOffice und ownCloud: keine eingebaute lokale Audio-/Video-Transkription gefunden [LOW, "nicht gefunden" ist kein Beleg für "existiert nicht"].

## Sources

- Nextcloud Viewer, Feature-Requests Zeitstelle (geschlossen 25.10.2026): https://github.com/nextcloud/viewer/issues/2176, https://github.com/nextcloud/viewer/issues/3226 [HIGH]
- `@nextcloud/viewer` Untertitel-Nebendateien, PR #184 und Quellcode: https://github.com/nextcloud-libraries/nextcloud-viewer/blob/main/lib/composables/useSubtitles.ts, https://github.com/nextcloud-libraries/nextcloud-viewer/blob/main/lib/utils/subtitleNames.ts [HIGH]; Server-`master` (36.0.0 dev) nutzt `@nextcloud/viewer ^2.0.0-beta.20`, stable33 bis stable35 nicht [HIGH, package.json geprüft]
- AppAPI ExApp API-Übersicht: https://docs.nextcloud.com/server/stable/developer_manual/exapp_development/tech_details/api/index.html [HIGH]
- Unified Search Entwicklerdoku: https://docs.nextcloud.com/server/stable/developer_manual/digging_deeper/search.html [HIGH]
- Findling-Recherche (Klartext-Subline, PHP-Begleit-App, Timeout): `C:/Users/Student/nextcloud-search/.planning/milestones/v1.0-phases/01-integrationsbeweis/01-RESEARCH.md`, `php/lib/Search/Provider.php` [HIGH, im Server-Quellcode verifiziert]
- stt_whisper2: https://docs.nextcloud.com/server/latest/admin_manual/ai/app_stt_whisper2.html [HIGH]
- Context Chat: https://docs.nextcloud.com/server/latest/admin_manual/ai/app_context_chat.html [HIGH]
- W3C WAI Captions/Subtitles: https://www.w3.org/WAI/media/av/captions/ [HIGH]; WCAG Understanding 1.2.2: https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html [HIGH]
- BITV-Test 9.1.2.2 und 7.1.2: https://bitvtest.de/pruefschritt/bitv-20-web/bitv-20-web-9-1-2-2-aufgezeichnete-videos-mit-untertiteln, https://bitvtest.de/pruefschritt/bitv-20-web/bitv-20-web-7-1-2-synchrone-untertitel [HIGH]
- EN 301 549 Kapitel 7: https://accessible.canada.ca/node/382 [MEDIUM]
- Netflix German Timed Text Style Guide: https://partnerhelp.netflixstudios.com/hc/en-us/articles/217351587; General Requirements: https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617 [HIGH für Netflix-Werte]
- ARD/ZDF/ORF/SRF-Untertitelstandards (37 Zeichen, 2 Zeilen, 13 bis 15 Z/s, 1 s): Sekundärquellen, Original-PDF nicht abrufbar (404): https://www.fernuni-hagen.de/zli/docs/feu-untertitelrichtlinien.pdf, https://eldorado.tu-dortmund.de/bitstream/2003/42535/1/Leitfaden%20zur%20Erstellung%20von%20Untertiteln_Kurth%20Mai%202024.pdf [MEDIUM]
- BBC (37 Zeichen, 160 bis 180 Wörter/min): nur Sekundärquellen, bbc.co.uk nicht abrufbar [LOW]
- Google Drive Transkripte: https://workspaceupdates.googleblog.com/2025/02/google-drive-video-transcripts.html, https://www.techspot.com/news/106910-google-adds-searchable-transcripts-videos-uploaded-drive.html [MEDIUM]
- Microsoft Stream: https://techcommunity.microsoft.com/blog/streamblog/transcripts-and-captions-coming-to-stream-on-sharepoint/2681316, https://atlas.utdallas.edu/TDClient/30/Portal/KB/Article/943/Transcriptions-in-Stream-On-SharePoint [MEDIUM, ältere Beiträge]
- Descript Export: https://help.descript.com/export-and-share/subtitles.md [MEDIUM]
- Whishper: https://github.com/cross-zijie/whishper, https://netactuate.com/docs/platform/marketplace/appliances/whishper [LOW bis MEDIUM]
- Scriberr: https://github.com/yb235/Scriberr (Spiegel), https://selfhostyourself.com/services/scriberr [LOW bis MEDIUM]
- noScribe: https://github.com/kaixxx/noScribe, https://wiki.projecttracks.be/index.php/Translations:Spraak-naar-tekst_transcriptie_met_noScribe/60/en [MEDIUM]
- Cassini: nur LinkedIn-Beitrag, nicht im Store-Katalog NC 33/35 gefunden: https://pt.linkedin.com/in/chris-de-sousa [LOW]
- Store-Katalog NC 33 und NC 35 (LinTO, Audiolog): https://apps.nextcloud.com/api/v1/platform/33.0.0/apps.json [HIGH, abgerufen 06.11.2026]
- Spike 3: `C:/Users/Student/audio-video-spike-2026-11-04/SPIKE3-REPORT.md` [gemessen]

---
*Feature research for: lokale Audio-/Video-Transkription und Suche in Nextcloud*
*Researched: 2026-11-06*
