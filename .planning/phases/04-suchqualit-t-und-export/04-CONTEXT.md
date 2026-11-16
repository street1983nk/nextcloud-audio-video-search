# Phase 4: Suchqualität und Export - Context

**Gathered:** 2026-11-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Nutzer finden gesprochene Inhalte auch über Wortformen, Komposita-Teile und Zahlen (als Ziffer und als Wort, DE/EN/FR), behalten die Ergebnisgruppe bei gesetzten Datums- und Personenfiltern und laden je Datei SRT, VTT und TXT herunter oder legen die Untertitel als Nebendatei `<Name>.<Sprache>.vtt` neben das Medium. Freigaben mit Download-Sperre erlauben Suche, aber keinen Export und keine Nebendatei. Ungeprüfte Exporte heißen überall "Untertitel-Entwurf", nirgends "BITV-konform". Anforderungen: SRCH-04, SRCH-05, SRCH-06, EXP-01 bis EXP-04.

Nicht in dieser Phase: besseres Transkript (turbo/large-v3, ROVER, Profile), Admin-Oberfläche (Phase 9), BITV-Prüfweg (Phase 10), eigene App-Seite (v1-Regel: nur Unified Search + Abspielseite).

</domain>

<decisions>
## Implementation Decisions

### Export-Ort und Bedienung (Owner 16.11.2026)
- **D-04-01:** Downloads NUR auf der Abspielseite (v1-Regel bestätigt, kein Files-Kontextmenü). Ein Rechte-Pfad.
- **D-04-02:** Drei sichtbare Download-Buttons (SRT, VTT, TXT) unter dem Hinweistext der Abspielseite; kein Menü.
- **D-04-03:** TXT = Fließtext ohne Zeitmarken, mit Kopfzeile (Dateiname + "Untertitel-Entwurf"-Hinweis, DE/EN/FR nach Anzeigesprache).
- **D-04-04:** Download-Dateiname folgt dem Nebendatei-Muster: `<Name>.<Sprache>.srt` / `.vtt` / `.txt` (z. B. `sitzung.de.srt`).

### Nebendatei-Ablage (Owner 16.11.2026)
- **D-04-05:** Namenskollision: klare Fehlermeldung ("Datei existiert bereits", DE/EN/FR), KEIN Ablegen, kein Alternativname, kein stilles Nichtstun. Nie überschreiben (EXP-03) bleibt hart.
- **D-04-06:** Ablegen darf, wer Schreibrecht im Ordner der Mediendatei hat (Nextcloud-Rechteprüfung in PHP). Download-Sperre blockiert Export UND Ablage (SRCH-04).
- **D-04-07:** Sprachkürzel ISO-Kurzform de/en/fr im Dateinamen (`sitzung.de.vtt`). Das Viewer-Untertitel-Schema für NC 33 bis 35 ist unbelegt und wird in der Research geprüft (Roadmap-Research-Flag); weicht der Viewer ab, Owner fragen.
- **D-04-08:** Kein Veraltungs-Hinweis: Die abgelegte Nebendatei wird nie automatisch aktualisiert; die Abspielseite vergleicht nichts. Nutzer legen bei Bedarf neu ab (nach eigenem Löschen der alten Datei).

### Filter-Semantik (Owner 16.11.2026)
- **D-04-09:** Datumsfilter = Änderungsdatum (mtime) der Mediendatei, wie die Files-Suche. Kein Aufnahmedatum aus Metadaten.
- **D-04-10:** Personenfilter nach dem Muster des Files-Providers (Dateien, die der Person gehören oder von ihr geteilt sind); die Research prüft das exakte Files-Verhalten in NC 33 bis 35 und wir ziehen gleich.

### Zahlen und Wortformen (Owner 16.11.2026)
- **D-04-11:** Zahlen-Gleichsetzung Wort <-> Ziffer je Sprache DE/EN/FR: 0 bis 100 voll, dazu runde Hunderter/Tausender (zweihundert, dreitausend) und Jahreszahlen-Muster. Kein voller Zahlenparser. Was darüber hinaus nötig ist, misst die Research am Korpus.
- **D-04-12:** Ordinalzahlen im gleichen Zahlenraum (zwölfter <-> 12., twelfth, douzième), wichtig für Datumsangaben.
- **D-04-13:** Komposita und Stemming: Findling-Analyzer-Muster 1:1 übernehmen (gleiche Analyzer-Kette, gleiche Wortlisten-Beschaffung fail-closed über Digest, an tantivy 0.26.2 gemessen). Keine Alternativ-Recherche.

### Übernommen aus früheren Entscheiden (nicht neu verhandelt)
- Treffer und Ausschnitt nur über Verweise mit state active (D-02-01a, D-02-15c); Ausschluss D-02-04/08/16; Probe-Regeln D-02-15/15a.
- Trefferbild der Suche aus Phase 3 (D-03-01 bis D-03-03, D-03-15) bleibt unverändert; Phase 4 ändert Findbarkeit, nicht das Trefferbild.
- "Vorläufig"-Kennzeichen und freigegebene Texte T1 bis T11 aus 03-UI-SPEC.md gelten weiter; neue nutzersichtbare Texte (Buttons, Fehlermeldung, TXT-Kopf) dem Owner vor dem Bau zeigen (UI-Abnahme-Regel).
- Kein Inhalt verlässt den Server; keine neuen ausgehenden Verbindungen.

### Claude's Discretion
- Untertitel-Segmentierung aus Wortzeiten (42 Zeichen, 2 Zeilen, 1-7 s, 20 Zeichen/s, ca. 80 ms Abstand, EXP-02): Algorithmus und Umbruchregeln; unabhängiger Parser für den Beweis.
- Technische Umsetzung der Zahlen-Normalisierung (Index-Zeit vs. Abfrage-Zeit, Token-Erweiterung) nach Research-Befund.
- Ablage-Mechanik der Nebendatei (PHP schreibt über Nextcloud-Filesystem-API; Pfad- und Namens-Härtung NFC wie PII-Muster).
- Reindex-Strategie, falls der Analyzer-Umbau den Bestand betrifft (Schema-Version nach Findling-Muster, kein stiller Leerlauf der Suche).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase und Anforderungen
- `.planning/ROADMAP.md` Phase 4 (Ziel, 5 Erfolgskriterien, Research-Flag: Viewer-Untertitel-Schema NC 33-35 unbelegt, vor dem Plan gegen den Viewer prüfen)
- `.planning/REQUIREMENTS.md` SRCH-04, SRCH-05, SRCH-06, EXP-01 bis EXP-04

### Frühere Entscheide und Verträge
- `.planning/phases/03-vorschau-transkripte-in-der-suche/03-CONTEXT.md` (D-03-01 bis D-03-25, Trefferbild, Rechte-Regeln)
- `.planning/phases/03-vorschau-transkripte-in-der-suche/03-UI-SPEC.md` (freigegebene Texte T1 bis T11, Abspielseiten-Layout)
- `.planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md` (state-/Ausschluss-/Probe-Regeln)

### Wiederverwendbare Muster (Findling)
- `C:/Users/Student/nextcloud-search/backend/src/findling/index/analyzer.py`, `schema.py`, `open.py`, `rebuild.py` (Analyzer-Kette de/en/fr, Komposita, Schema-Versionierung)
- `C:/Users/Student/nextcloud-search/backend/src/findling/index/wordlist.py` und `wordlist_nl.py` (Wortlisten-Beschaffung fail-closed über Digest)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/src/audio_video_search_backend/index/` (analyzer.py, schema.py, open.py, publish.py, wordlist.py): Tantivy-Index nach Findling-Muster liegt schon, Phase 4 erweitert Analyzer (Zahlen) und prüft Komposita-Abdeckung.
- `php/lib/Search/`: bestehender Unified-Search-Provider; IFilteringProvider-Erweiterung dockt hier an.
- `php/lib/Controller/`: Abspielseiten-Controller und Gateway; Export-Endpunkte folgen dem Rechte-Muster (readableFile, state active).
- Untertitel-Grenzen (EXP-02) brauchen einen eigenen ca. 100-Zeilen-Writer mit Tests (Stack-Entscheid: keine Bibliothek).

### Established Patterns
- Rechteprüfung zur Abfragezeit in PHP, ExApp liefert nur Daten je fileId.
- Alle nutzersichtbaren Texte dreisprachig DE/EN/FR, Deutsch zuerst, echte Umlaute, l10n-Kataloge in beiden Apps.
- Security: jede Phase endet mit Threat-Audit (SECURITY.md Pflicht); Export/Ablage sind neue Angriffsflächen (Pfad-Injektion, Rechte-Umgehung über Freigaben).

### Integration Points
- Abspielseite (bestehend) bekommt den Download-Bereich; Viewer-Nebendatei-Schema gegen NC 33-35 prüfen (Research).
- Unified Search: getSupportedFilters()/IFilteringProvider im bestehenden Provider.

</code_context>

<specifics>
## Specific Ideas

- Download-Buttons unter dem bestehenden Hinweistext der Abspielseite, Reihenfolge SRT, VTT, TXT.
- TXT-Kopfzeile sinngemäß: Dateiname + "Untertitel-Entwurf, automatisch erstellt" (Wortlaut vor dem Bau dem Owner zeigen).
- Fehlermeldung bei Kollision benennt den Dateinamen, der schon existiert.

</specifics>

<deferred>
## Deferred Ideas

None , discussion stayed within phase scope.

</deferred>

---

*Phase: 04-suchqualit-t-und-export*
*Context gathered: 2026-11-16*
