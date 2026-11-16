# Phase 4: Suchqualität und Export - Research

**Researched:** 2026-11-16
**Domain:** Tantivy-Abfrageerweiterung (Zahlen, Komposita), Unified-Search-Filter (IFilteringProvider), Untertitel-Bildung aus Wortzeiten, Datei-Export und Nebendatei-Ablage in einer Nextcloud-PHP-App (NC 33 bis 35)
**Confidence:** HIGH für Viewer-, Filter- und Download-Sperre-Befunde (Quellcode der Zweige stable33/34/35 gelesen) und für das Analyzer-Verhalten (am echten Code mit tantivy 0.26.2 und wngerman 20161207-15 gemessen); MEDIUM für den Untertitel-Algorithmus (Regeln belegt, Grenzfälle am Korpus noch zu messen).

## Summary

Vier Befunde verändern den Plan, zwei davon brauchen einen Owner-Entscheid vor dem Bau:

1. **Erfolgskriterium 1 scheitert mit dem 1:1 übernommenen Findling-Analyzer (D-04-13).** Gemessen: `Haushaltsplanberatung` wird zu `['haushaltsplan', 'berat']` zerlegt, weil `haushaltsplan` (13 Zeichen) selbst in der Wortliste steht und der Splitter leftmost-longest arbeitet. Die Suche "Haushalt" findet die Datei deshalb **nicht** (Probe: leere Trefferliste). Findling dokumentiert genau diese Grenze ("Mietvertrag ist nicht über Vertrag findbar"). "Häuser" findet "Haus" dagegen schon heute (beide Stamm `haus`). Eine Rezeptänderung (zerlegbare Einträge streichen) habe ich gemessen: sie behebt "Haushalt", zerlegt aber `Verbraucher` in `verb|rauch`, `Feuerwehr` in `feu|wehr`, `Unternehmen` in `nehm` und macht `Grundstücksverkehrsgenehmigung` unzerlegbar, also schlechter. Ein abfrageseitiger Präfix-Zusatz auf `body_de` (`Query.regex_query(..., "haushalt.*")`) findet "Haushaltsplanberatung" ohne Neuindex, bringt aber Beifang (`Haushälterin`) und hilft nur für den Kopf eines Kompositums. **Owner-Frage F1** (siehe Open Questions).
2. **Zahlen gehören auf die Abfrageseite, nicht in den Index.** tantivy-py 0.26.2 hat keinen Synonym-Filter; die Ketten zerlegen Zahlwörter aber vorhersagbar (gemessen, Tabelle unten). Eine Abfrage-Erweiterung (Ziffer und Zahlwort in DE/EN/FR als `Occur.Should`-Gruppe, jede Variante durch dieselbe `parse_query`-Kette) findet "zwölf" über "12" und umgekehrt, braucht **keinen Neuindex** und lässt `ANALYZER_VERSION` unverändert. Gemessen: Erweiterung von "12" trifft Dokumente mit "12", "zwölf", "twelve", "soixante dix"-Phrase (Probe).
3. **Der Viewer in NC 33 bis 35 zeigt keine Untertitel-Nebendateien.** In `nextcloud/viewer` stable33, stable34 und stable35 gibt es keinen Code, der `.vtt`/`.srt` neben einem Video sucht (nur das Plyr-Bedienelement "captions"). Erst die Bibliothek `@nextcloud/viewer` (2.0.0-beta.21, im Server erst ab `master` = NC 36) erkennt `film.vtt`, `film.de.vtt`, `film.pt-BR.srt` neben `film.mp4`. Das Namensschema dort ist **Name ohne Medien-Endung** + `.<Sprache>.vtt` und passt zu D-04-07 (`sitzung.de.vtt` neben `sitzung.mp4`). Kein Schema-Widerspruch, aber kein sichtbarer Nutzen der Nebendatei im Viewer vor NC 36.
4. **Die Sprache im Dateinamen gibt es heute nicht.** Jede Vorschau-Version wird mit `language = "und"` gespeichert (`worker/preview.py:115`, Parakeet nennt keine Sprache). `sitzung.und.vtt` wäre falsch und würde vom NC-36-Viewer **nicht** als Untertitel erkannt (`canonicalLanguage` liefert für `und` nichts, `subtitleOf` gibt dann `undefined`). Die Sprache muss neu bestimmt werden. **Owner-Frage F2.**

Der Rest ist belegte Handwerksarbeit: Der Personenfilter der Files-Suche ist in 33, 34 und 35 identisch und **nicht** "Dateien der Person", sondern "Dateien mit einer Freigabezeile, deren `uid_owner` die Person ist, oder die der Person direkt freigegeben sind" (innerer Join auf `oc_share`). Nicht geteilte eigene Dateien fallen bei Files heraus; wir ziehen gleich (D-04-10). Die Download-Sperre prüft die App bereits richtig (`PageController::downloadAllowed`); `IShare::canDownload()` gibt es erst ab 33.0.1 bzw. 34.0.0, also beim Attribut bleiben. `Folder::newFile()` **überschreibt stillschweigend** (`file_put_contents`), das Nie-Überschreiben muss die App selbst sichern.

**Primary recommendation:** Zahlen als abfrageseitige Erweiterung im Container (`index/numbers.py` + neuer Query-Aufbau in `SearchIndex.search` und `first_match_ms`), Filter in PHP nach der Rechteprüfung, Untertitel-Writer als reine Python-Funktion im Container mit Eigenschaftstests plus zwei unabhängigen Prüfern (webvtt-py/srt als Test-Abhängigkeit, ffmpeg als sprachfremder Parser), Export und Ablage nur über PHP mit derselben Rechte- und Sperrprüfung wie die Abspielseite. Vor dem Plan F1 und F2 dem Owner vorlegen.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Export-Ort und Bedienung (Owner 16.11.2026)
- **D-04-01:** Downloads NUR auf der Abspielseite (v1-Regel bestätigt, kein Files-Kontextmenü). Ein Rechte-Pfad.
- **D-04-02:** Drei sichtbare Download-Buttons (SRT, VTT, TXT) unter dem Hinweistext der Abspielseite; kein Menü.
- **D-04-03:** TXT = Fließtext ohne Zeitmarken, mit Kopfzeile (Dateiname + "Untertitel-Entwurf"-Hinweis, DE/EN/FR nach Anzeigesprache).
- **D-04-04:** Download-Dateiname folgt dem Nebendatei-Muster: `<Name>.<Sprache>.srt` / `.vtt` / `.txt` (z. B. `sitzung.de.srt`).

#### Nebendatei-Ablage (Owner 16.11.2026)
- **D-04-05:** Namenskollision: klare Fehlermeldung ("Datei existiert bereits", DE/EN/FR), KEIN Ablegen, kein Alternativname, kein stilles Nichtstun. Nie überschreiben (EXP-03) bleibt hart.
- **D-04-06:** Ablegen darf, wer Schreibrecht im Ordner der Mediendatei hat (Nextcloud-Rechteprüfung in PHP). Download-Sperre blockiert Export UND Ablage (SRCH-04).
- **D-04-07:** Sprachkürzel ISO-Kurzform de/en/fr im Dateinamen (`sitzung.de.vtt`). Das Viewer-Untertitel-Schema für NC 33 bis 35 ist unbelegt und wird in der Research geprüft (Roadmap-Research-Flag); weicht der Viewer ab, Owner fragen.
- **D-04-08:** Kein Veraltungs-Hinweis: Die abgelegte Nebendatei wird nie automatisch aktualisiert; die Abspielseite vergleicht nichts. Nutzer legen bei Bedarf neu ab (nach eigenem Löschen der alten Datei).

#### Filter-Semantik (Owner 16.11.2026)
- **D-04-09:** Datumsfilter = Änderungsdatum (mtime) der Mediendatei, wie die Files-Suche. Kein Aufnahmedatum aus Metadaten.
- **D-04-10:** Personenfilter nach dem Muster des Files-Providers (Dateien, die der Person gehören oder von ihr geteilt sind); die Research prüft das exakte Files-Verhalten in NC 33 bis 35 und wir ziehen gleich.

#### Zahlen und Wortformen (Owner 16.11.2026)
- **D-04-11:** Zahlen-Gleichsetzung Wort <-> Ziffer je Sprache DE/EN/FR: 0 bis 100 voll, dazu runde Hunderter/Tausender (zweihundert, dreitausend) und Jahreszahlen-Muster. Kein voller Zahlenparser. Was darüber hinaus nötig ist, misst die Research am Korpus.
- **D-04-12:** Ordinalzahlen im gleichen Zahlenraum (zwölfter <-> 12., twelfth, douzième), wichtig für Datumsangaben.
- **D-04-13:** Komposita und Stemming: Findling-Analyzer-Muster 1:1 übernehmen (gleiche Analyzer-Kette, gleiche Wortlisten-Beschaffung fail-closed über Digest, an tantivy 0.26.2 gemessen). Keine Alternativ-Recherche.

#### Übernommen aus früheren Entscheiden (nicht neu verhandelt)
- Treffer und Ausschnitt nur über Verweise mit state active (D-02-01a, D-02-15c); Ausschluss D-02-04/08/16; Probe-Regeln D-02-15/15a.
- Trefferbild der Suche aus Phase 3 (D-03-01 bis D-03-03, D-03-15) bleibt unverändert; Phase 4 ändert Findbarkeit, nicht das Trefferbild.
- "Vorläufig"-Kennzeichen und freigegebene Texte T1 bis T11 aus 03-UI-SPEC.md gelten weiter; neue nutzersichtbare Texte (Buttons, Fehlermeldung, TXT-Kopf) dem Owner vor dem Bau zeigen (UI-Abnahme-Regel).
- Kein Inhalt verlässt den Server; keine neuen ausgehenden Verbindungen.

### Claude's Discretion
- Untertitel-Segmentierung aus Wortzeiten (42 Zeichen, 2 Zeilen, 1-7 s, 20 Zeichen/s, ca. 80 ms Abstand, EXP-02): Algorithmus und Umbruchregeln; unabhängiger Parser für den Beweis.
- Technische Umsetzung der Zahlen-Normalisierung (Index-Zeit vs. Abfrage-Zeit, Token-Erweiterung) nach Research-Befund.
- Ablage-Mechanik der Nebendatei (PHP schreibt über Nextcloud-Filesystem-API; Pfad- und Namens-Härtung NFC wie PII-Muster).
- Reindex-Strategie, falls der Analyzer-Umbau den Bestand betrifft (Schema-Version nach Findling-Muster, kein stiller Leerlauf der Suche).

### Deferred Ideas (OUT OF SCOPE)
None , discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRCH-04 | Freigaben mit Download-Sperre: Suche ja, Export nein | Bestehende Prüfung `PageController::downloadAllowed` (Attribut `permissions/download` am `ISharedStorage`) ist korrekt und deckt sich mit `ViewOnly::checkFileInfo` des Servers; in einen Dienst ziehen und in Export- und Ablage-Route vor jedem Container-Aufruf anwenden. `canDownload()` erst ab 33.0.1/34.0.0, nicht nutzen. Abschnitt "Download-Sperre" |
| SRCH-05 | Wortformen, Komposita-Teile, Zahlen als Ziffer und Wort (DE/EN/FR) | Stemming belegt (Häuser/Haus, maisons/maison, houses/house); Kompositum-Grenze gemessen (F1); Zahlen über Abfrage-Erweiterung, Token-Tabelle gemessen. Abschnitte "Zahlen" und "Komposita" |
| SRCH-06 | Ergebnisgruppe bleibt bei Datums-/Personenfilter sichtbar | Web-Client 33/34/35 zeigt Anbieter ohne `since`+`until` bzw. `person` in `getSupportedFilters()` nur unter "Partial matches"/unfiltered; Files-Semantik aus Quellcode. Abschnitt "Filter" |
| EXP-01 | SRT, VTT, TXT je Datei herunterladen | `DataDownloadResponse` (seit 8.0, Content-Disposition mit UTF-8 und ASCII-Fallback über Symfony `HeaderUtils`), neue Container-Route `/export`. Abschnitt "Export" |
| EXP-02 | Untertitel aus Wortzeiten unter den Grenzen, unabhängiger Parser | Algorithmus unten, Eigenschaftstests, Prüfer webvtt-py 0.8.0 + srt 3.5.3 (nur dev) und ffmpeg als sprachfremder Parser |
| EXP-03 | Nebendatei `<Name>.<Sprache>.vtt`, nie überschreiben | Viewer-Schema (NC 36) belegt; `newFile` überschreibt, deshalb eigene Prüfung plus Sperre; Sprache F2 |
| EXP-04 | "Untertitel-Entwurf", nie "BITV-konform" | Text-Gate (bestehende Text-/l10n-Gates erweitern: verbotenes Wort in allen Katalogen, README, Store-Text, Dateiinhalten) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Kein Inhalt, kein Text, keine Telemetrie verlässt den Server; keine neuen ausgehenden Verbindungen.
- Qualität vor Speed; Qualitätsentscheidungen mit Messung belegen.
- Nextcloud 33 bis 35, AppAPI mit HaRP, amd64 + arm64, nur CPU.
- Tantivy 0.26.2 bleibt gepinnt (Findling-Code 1:1); Schema-/Analyzer-Marken in `meta`, sonst stumme leere Suche nach Upgrade.
- **What NOT to Use:** `webvtt-py`, `srt`, `pysubs2` **als Writer**; eigener Writer von ca. 100 Zeilen mit Tests. (Als reine Test-Prüfer sind sie mit dieser Regel vereinbar, siehe Standard Stack.)
- Keine eigene App-Seite mit Medienübersicht in v1; nur Unified Search + Abspielroute.
- Alle nutzersichtbaren Texte DE/EN/FR im Gleichstand, Deutsch zuerst, echte Umlaute, keine Gedankenstriche, keine Emojis.
- Qualitäts-Gates: ruff-Vollsatz, pyright basic, vulture lokal grün (ruff lokal mit `--no-cache`); Commits nur als street1983nk, ohne "closes #N".
- Vor jedem Push, Merge oder Kommentar den Owner fragen; UI-Abnahme gemeinsam per Playwright (3 Breiten, hell/dunkel).
- Agenten: nie `python -`/`python -c`, nur Skriptdateien; GitHub-API sparsam.
- Security hat höchste Priorität: secure-phase zum Phasenabschluss, offene Threats blockieren.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Zahlen-/Wortform-Findbarkeit | Container (Python, Tantivy-Abfrage) | , | Index und Analyzer leben nur im Container |
| Datums-/Personenfilter | PHP-Provider (nach `readableFile`) | , | Rechte, mtime aus dem Node, `oc_share` nur in PHP sichtbar; Container kennt keine Rechte |
| Untertitel-Cues, SRT/VTT/TXT-Text | Container (reine Funktion über `effective_words`) | PHP (Kopfzeile/NOTE in Anzeigesprache) | Wortzeiten nur in SQLite des Containers; Lokalisierung der Kopfzeile über IL10N in PHP |
| Download-Antwort, Dateiname | PHP-Controller | , | Sitzung, Rechte, Download-Sperre, Content-Disposition |
| Nebendatei schreiben | PHP-Controller als Nutzer (`ReaderContext::actAs`) | , | Schreibrecht, Quota, files_accesscontrol, Versionen, Gruppenordner-ACL gelten nur über die Nutzer-Sicht |
| Download-Sperre-Erkennung | PHP-Dienst | Browser (Buttons ausblenden) | Server entscheidet; UI nur Spiegel |
| Dateisprache für den Namen | Container (Worker oder Export-Route) | , | Text-Sprachkennung py3langid läuft dort (F2) |

## Standard Stack

### Core (unverändert, schon im Projekt)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tantivy (tantivy-py) | 0.26.2 | Index, `parse_query`, `Query.boolean_query`, `Query.regex_query` | Findling-Pin; alle Query-Bausteine in 0.26.2 vorhanden [VERIFIED: `dir(Query)` im Projekt-venv: `boolean_query`, `phrase_query`, `regex_query`, `term_set_query`, `disjunction_max_query` ...] |
| Nextcloud OCP | 33 bis 35 | `IFilteringProvider`, `IFilter::BUILTIN_SINCE/UNTIL/PERSON`, `DataDownloadResponse`, `Folder::newFile`, `ISharedStorage` | Öffentliche API, in allen drei Zweigen geprüft [VERIFIED: nextcloud/server stable33/34/35 Quellen] |
| py3langid | 0.4.0 | Text-Sprachkennung (bereits Laufzeitabhängigkeit, D-03-18), Kandidat für F2 | schon gepinnt, nur im Kindprozess geladen [VERIFIED: backend/pyproject.toml, engine/parakeet.py:148] |
| ffmpeg (LGPL-Build) | im Image | sprachfremder Zweit-Parser für SRT/VTT im Test | schon vorhanden; lokal ffmpeg 8.1.1 im PATH [VERIFIED: PATH] |

### Supporting (neu, nur Test/Dev)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| webvtt-py | 0.8.0 (08.11.2026, MIT) | Unabhängiger VTT-**Prüfer** in pytest | Nur `dependency-groups.dev`, nie im Image, nie als Writer [VERIFIED: pypi.org JSON; ASSUMED legitim, slopcheck nicht lauffähig] |
| srt | 3.5.3 (28.03.2023, MIT) | Unabhängiger SRT-**Prüfer** in pytest (`srt.parse` wirft `SRTParseError`) | Nur dev [VERIFIED: pypi.org JSON; ASSUMED legitim] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Abfrageseitige Zahlen-Erweiterung | Index-Zeit-Normalisierung (Zahlwort zu Ziffer vor `add_text`) | `body_de` ist gespeichert und liefert den Ausschnitt der Suche; Umschreiben würde den Ausschnitt verfälschen oder ein viertes Feld plus Neuindex verlangen. Nur sinnvoll, wenn die Abfrage-Erweiterung messbar zu langsam wird |
| Eigener Zahlwort-Generator mit Tabellentest | `num2words` 0.5.14 (LGPL, Dez. 2024) | Würde Laufzeitabhängigkeit für einen begrenzten Zahlenraum; Gegenprobe soll unabhängig sein (Owner-Regel), also handgeschriebene Erwartungstabelle statt zweiter Generator |
| webvtt-py als Prüfer | pysubs2 | pysubs2 ist tolerant beim Lesen und deshalb ein schwacher Prüfer [ASSUMED] |

**Installation (dev only):**
```bash
cd backend && uv add --group dev webvtt-py==0.8.0 srt==3.5.3
```

## Package Legitimacy Audit

slopcheck konnte in dieser Sitzung nicht installiert werden (Installationsaufruf vom Berechtigungssystem abgelehnt). Nach Protokoll gelten alle neuen Pakete als `[ASSUMED]`; der Planer setzt vor dem `uv add` einen `checkpoint:human-verify`.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| webvtt-py | PyPI | Projekt seit Jahren, Release 0.8.0 vom 08.11.2026 | nicht geprüft | github.com/glut23/webvtt-py | nicht gelaufen | Flagged: nur dev, Checkpoint; sehr frisches Release, Changelog vor Pin lesen |
| srt | PyPI | letzter Release 03/2023 | nicht geprüft | github.com/cdown/srt | nicht gelaufen | Flagged: nur dev, Checkpoint |

**Packages removed due to slopcheck [SLOP] verdict:** keine
**Packages flagged as suspicious [SUS]:** keine bewertet; beide wegen fehlender Prüfung hinter Checkpoint
Beide Namen stehen bereits in der Projekt-Stackrecherche (CLAUDE.md "What NOT to Use"), sind also keine Neuerfindung dieser Sitzung.

## Architecture Patterns

### System Architecture Diagram

```
Suche mit Filtern
  Browser (Unified Search, since/until/person)
     │ OCS /search/providers/audio_video_search/search?term&since&until&person
     ▼
  PHP Provider.search ──(term, limit*4, offset)──► Container POST /search
     │                                               │ numbers.expand(term) ─► Should-Gruppen
     │                                               │ parse_query je Variante (de/en/fr-Ketten)
     │                                               │ Must über Begriffe ─► Kandidaten ─► tiered
     │ ◄──────────── fileId, startMs, excerpt ────────┘
     ▼
  Ausschluss ─► readableFile (actAs) ─► FilterCheck(mtime, oc_share) ─► Eintrag
                                          (nur wenn Filter gesetzt)

Export / Ablage
  Abspielseite (play.php, Buttons SRT|VTT|TXT, "Neben das Medium legen")
     │ GET  /export/{fileId}/{format}            POST /sidecar/{fileId} (CSRF)
     ▼
  PHP ExportController
     resolve (actAs, readableFile) ─► Ausschluss ─► DownloadPolicy.allowed?  ──nein──► 403 + Text
     │ ja
     ▼
  Container POST /export {fileId, format} ─► effective_words ─► cues ─► srt|vtt|txt-Body + language
     │
     ├─ Download: DataDownloadResponse(<Name>.<lang>.<ext>), Kopf/NOTE aus IL10N
     └─ Ablage:   Parent.isCreatable? ─► Lock ─► nodeExists(name)? ──ja──► 409 "existiert bereits"
                                                    │ nein
                                                    ▼
                                         Parent.newFile(name, vtt) als Nutzer
```

### Recommended Project Structure
```
backend/src/audio_video_search_backend/
├── index/numbers.py        # Zahlwort-Tabellen DE/EN/FR, expand(term) -> Gruppen von Varianten
├── index/publish.py        # search(): Query aus Gruppen; first_match_ms(): Varianten
├── subtitles/cues.py       # Wörter -> Cues (Grenzen EXP-02), reine Funktion
├── subtitles/formats.py    # to_srt, to_vtt, to_txt (Body ohne lokalisierte Kopfzeile)
└── api/export.py           # POST /export {fileId, format} -> {language, body} unter Leck-Regel
php/lib/
├── Controller/ExportController.php   # GET export, POST sidecar
├── Service/DownloadPolicy.php        # aus PageController::downloadAllowed herausgezogen
├── Service/SearchFilters.php         # since/until/person je Datei (oc_share-Abfrage)
└── Search/Provider.php               # getSupportedFilters + Filteranwendung
```

### Pattern 1: Zahlen als abfrageseitige Erweiterung
**What:** Der Suchbegriff wird in Wörter zerlegt (gleiche Grenze wie `Tokenizer.simple`: alles nicht Alphanumerische trennt). Erkannte Zahlen (Ziffernfolge, Zahlwort oder Zahlwortfolge in DE/EN/FR, Ordinalform) werden zu einer kanonischen Zahl plus Ordinal-Flag. Für diese Zahl erzeugt `numbers.py` alle Schreibweisen; jede läuft durch `index.parse_query(variante, BODY_FIELDS)`, mehrteilige als Phrase (`"soixante dix"`). Pro Zahl eine `Occur.Should`-Gruppe, zwischen den Begriffen `Occur.Must` (entspricht `conjunction_by_default=True`).
**When to use:** nur wenn der Begriff mindestens eine Zahl enthält; sonst bleibt der bisherige Weg (`parse_query(text)`) unverändert, damit Phase-3-Verhalten und -Tests stehen bleiben.
**Warum hier:** keine Indexänderung, kein Neuindex, `ANALYZER_VERSION` bleibt 1; Index-Ketten und Abfrage-Ketten können nicht auseinanderlaufen, weil jede Variante durch dieselben Ketten geht.

Gemessene Token der bestehenden Ketten (tantivy 0.26.2, wngerman 20161207-15, `scratchpad/scripts/probe_analyzer.py`):

| Eingabe | Kette | Token |
|---|---|---|
| zwölf / zwölften / zwölfter | de | `zwolf` / `zwolft` / `zwolft` |
| 12. / am 12. März | de | `12` / `12`, `marz` |
| einundzwanzig / einundzwanzigsten | de | `einundzwanz` (bleibt ganz) |
| neunzehnhundertneunzig | de | `neunzehn`, `hundert`, `neunzig` (Splitter zerlegt) |
| zweitausendvierundzwanzig | de | `zweitaus`, `vierundzwanz` |
| ein, eine | de | `[]` (Stoppwort) |
| eins | de | `ein` |
| 1.000 / 1,5 / 12:30 | de | `1`,`000` / `1`,`5` / `12`,`30` |
| twelve / twelfth / twenty-one | en | `twelv` / `twelfth` / `twenti`,`one` |
| 1st / 12th | en | `1st` / `12th` (ein Token, nicht `12`) |
| douze / douzième / soixante-dix | fr | `douz` / `douziem` / `soix`,`dix` |
| un, une / vingt et un | fr | `[]` / `vingt` (Stoppwörter) |
| 12e / 1er | fr | `12e` / `1er` (ein Token) |

Folgerungen für den Generator:
- Varianten immer als **Oberflächenform** erzeugen und durch `parse_query` schicken, nie Stämme von Hand schreiben.
- Ziffern-Ordinalia der Sprachen EN/FR als eigene Varianten: `12th`, `12e`, `12ème`, `1st/2nd/3rd`, `1er/1re`.
- Tausender mit Gruppierung: Variante `"30 000"` als Phrase deckt `30.000` (DE), `30,000` (EN) und `30 000` (FR) im Index (der Tokenizer trennt am Punkt/Komma). Parakeet schreibt solche Zahlen tatsächlich so (Spike-2-Transkript FLEURS DE: "30.000 gepflegte Hirsche", "1963", "400", "20%", "Am 15. August 1940", "siebzig messerscharfen Zähnen") [VERIFIED: spike2/results/pk_fl_pipe_t4.json]. Beide Formen kommen also im selben Transkript vor; die Gleichsetzung ist nötig.
- Jahreszahlen: DE `neunzehnhundertneunzig`, `zweitausendvierundzwanzig`, `zwanzigvierundzwanzig`; EN `nineteen ninety`, `two thousand twenty four`, `twenty twenty four`; FR `mille neuf cent quatre-vingt-dix`, `dix-neuf cent quatre-vingt-dix`, `deux mille vingt-quatre`. Bereich 1100 bis 2099 als Muster, kein voller Parser (D-04-11).
- **Grenze 1:** `ein/eine/un/une` sind Stoppwörter und Artikel; "1" darf nicht auf sie erweitert werden (wäre ohnehin wirkungslos). `eins`, `one`, `premier/première`, `erste` gehen.
- **Grenze 2:** FR `vingt et un` wird zu `vingt`, weil `et` und `un` Stoppwörter sind; die Phrase `"vingt et un"` trifft dann jedes `vingt` (Beifang bei 21/31/41/.../71). Messen und als bekannte Grenze notieren.
- Ordinalwort-Abfrage (`zwölften`) erweitert auf Ziffer (`12`) und Ordinalwörter; Ziffern-Abfrage `12` erweitert auf Kardinal- **und** Ordinalwörter (Datumsfall "am zwölften März" muss über "12. März" finden und umgekehrt, D-04-12).

**Example:**
```python
# Source: im Projekt-venv gemessen (tantivy 0.26.2), probe_analyzer.py
parts = [index.parse_query(v, list(BODY_FIELDS)) for v in ["12", "zwölf", "twelve", "douze", '"soixante dix"']]
number = Query.boolean_query([(Occur.Should, p) for p in parts])
query = Query.boolean_query([(Occur.Must, number), (Occur.Must, index.parse_query("Personen", list(BODY_FIELDS)))])
# Probe: trifft "Es waren 12 Personen" und "soixante-dix personnes", nicht die übrigen
```

### Pattern 2: Filter im Provider nach der Rechteprüfung
**What:** `getSupportedFilters()` meldet `term`, `since`, `until`, `person` (Konstanten `IFilter::BUILTIN_*`). Im Rundenlauf wird nach `readableFile` je Datei geprüft:
- `since`: `$file->getMTime() >= $query->getFilter('since')->get()->getTimestamp()`; `until`: `<=` (gleiche Vergleiche wie Files: `COMPARE_GREATER_THAN_EQUAL`/`LESS_THAN_EQUAL` auf `mtime`).
- `person` als `UserFilter` (`->get()` ist `IUser`): Datei zählt, wenn es in `oc_share` eine Zeile mit `file_source = fileId` gibt und (`uid_owner = uid`) oder (`share_with = uid` und `share_type = 0`). Als `GroupFilter` (`person=group/<gid>` über `FilterFactory::getPerson`): `share_with = gid` und `share_type = 1`.
**Warum genau so:** Files baut daraus `SearchComparison('owner', ...)`, und `SearchBuilder` übersetzt `owner` in `uid_owner` der **Share**-Tabelle; `QuerySearchHelper::equipQueryForShares` macht einen **inneren** Join `file.fileid = s.file_source` [VERIFIED: stable33/34/35 identisch]. Folgen, die wir mitkopieren: (a) eine nie geteilte Datei der Person erscheint nicht; (b) nur die Datei selbst zählt, nicht eine geteilte Elternmappe; (c) jede Freigabeart zählt für `uid_owner` (auch Link-Freigaben).
**Abfrage:** eine Query je Runde für alle Kandidaten (`file_source IN (...)`), mit `IDBConnection`/`IQueryBuilder`, nicht je Treffer.
**Web-Client:** 33/34 (`UnifiedSearchModal.vue`) und 35 schicken `since`/`until` nur, wenn der Anbieter **beide** meldet, `person` nur bei `person`; ein Anbieter ohne Unterstützung landet unter "Partial matches" [VERIFIED: core/src/components/UnifiedSearch/UnifiedSearchModal.vue, stable34 Zeilen 383 bis 425 und 528 bis 556; stable35 Zeilen 541 bis 604, 1076 bis 1094]. In 35 kommen Datumswerte als ISO-String.

### Pattern 3: Export über PHP, Text aus dem Container
**What:** `GET /apps/audio_video_search/export/{fileId}/{format}` mit `format ∈ {srt, vtt, txt}` (Route-Requirement als Regex), `NoAdminRequired`. Ablauf wie `PageController::play`: `resolve` (actAs + `readableFile`), Ausschlussprüfung (Ausschluss = Antwort "kein Transkript"), `DownloadPolicy::allowed($file)` (false = 403 ohne Container-Aufruf, unabhängig von `shareapi_allow_view_without_download`), dann Container `/export`. Antwort `new DataDownloadResponse($body, $name, $mime)`; `DownloadResponse` setzt `Content-Disposition` per `HeaderUtils::makeDisposition` mit ASCII-Fallback und ersetzt `/` und `\` [VERIFIED: stable33/34/35].
MIME: `text/vtt; charset=utf-8`, `application/x-subrip; charset=utf-8`, `text/plain; charset=utf-8`.
**Timeout:** Die Nutzer-Routen nutzen 1,5 s (`REQUEST_TIMEOUT_SECONDS`); eine 12-h-Datei hat grob 100 000 Wörter. Eigene Konstante (z. B. 15 s) und Messung im Plan.
**Container-Route** in `backend/appinfo/info.xml` mit `access_level USER` eintragen (Gate aus 02-09 verlangt jede Route dort).

### Pattern 4: Nebendatei sicher ablegen
**What:** `POST /apps/audio_video_search/sidecar/{fileId}` (CSRF-Token Pflicht, kein `NoCSRFRequired`), `#[UserRateLimit]`.
1. resolve als Nutzer, Ausschluss, `DownloadPolicy` (Sperre = 403).
2. `$parent = $file->getParent()`; `$parent->isCreatable()` sonst 403 mit Text.
3. Name = Dateiname ohne letzte Endung + `.` + Sprache + `.vtt` (NFC-normalisiert, `\Normalizer::normalize`). Ohne Endung: ganzer Name. Länge in Bytes prüfen (Dateinamen-Grenze 255 Bytes), sonst Fehlertext.
4. Sperre: `ILockingProvider` bzw. `$parent->lock()` nicht nutzen (sperrt den ganzen Ordner gegen andere Schreiber); stattdessen eigener Schlüssel über `ILockingProvider::acquireLock('avs-sidecar/'.$storageId.'/'.$internalPath, LOCK_EXCLUSIVE)` für die Prüf-und-Schreib-Sequenz der App [ASSUMED: Muster, vor Bau an `OCP\Lock\ILockingProvider` stable33 prüfen].
5. `if ($parent->nodeExists($name))` dann 409 "existiert bereits" mit Namen (D-04-05).
6. `$parent->newFile($name, $vtt)`.
**Warum:** `Folder::newFile` ruft bei vorhandenem Inhalt `view->file_put_contents` und **überschreibt** eine bestehende Datei ohne Rückfrage [VERIFIED: lib/private/Files/Node/Folder.php stable34 Zeilen 171 bis 194]. Restrisiko: ein fremder Client legt zwischen 5 und 6 eine gleichnamige Datei an; die Lücke ist Millisekunden groß, im SECURITY.md als akzeptiertes Restrisiko führen.

### Pattern 5: Untertitel-Cues aus Wortzeiten (EXP-02)
**Grenzen als Konstanten mit Test:** `MAX_LINE = 42`, `MAX_LINES = 2`, `MIN_MS = 1000`, `MAX_MS = 7000`, `MAX_CPS = 20`, `GAP_MS = 80`.
**Algorithmus (gierig mit Rückgriff auf den letzten guten Schnitt):**
1. Eingabe: `effective_words(media_id)` (Korrekturen schon überlagert), sortiert, `surface` mit Satzzeichen.
2. Wörter in einen offenen Cue aufnehmen, solange (a) der Text sich in höchstens 2 Zeilen zu je höchstens 42 Zeichen umbrechen lässt, (b) `last.end - first.start <= 7000`, (c) keine Pause > ca. 700 ms davor liegt, (d) kein Satzende (`.?!`) vorher kam und der Cue schon die halbe Länge hat.
3. Passt das nächste Wort nicht, am **letzten guten Schnitt** schließen: Rangfolge Satzende > Pause > Komma/Semikolon/Doppelpunkt > vor Konjunktion (und, oder, aber, dass / and, but, or / et, ou, mais, que) > beliebige Wortgrenze.
4. Zeilenumbruch im Cue: die Bruchstelle, die beide Zeilen <= 42 hält und den Längenunterschied minimiert, bevorzugt nach Satzzeichen; einzeilig, wenn <= 42.
5. Zeiten: `start = erstes Wort.start`; `end = max(letztes Wort.end, start + 1000, start + ceil(len(text)/20*1000))`, gedeckelt auf `start + 7000` und auf `nächster.start - 80`. Kommt der Folge-Cue zu früh, zuerst das Ende in die Pause schieben, dann den Folge-Start nicht verschieben (Synchronität BITV 7.1.2: höchstens 100 ms Versatz, FEATURES.md).
6. Ist `cps > 20` nach Schritt 5 nicht erreichbar (schnelle Rede, wortgetreu, kein Kürzen), Cue an einem früheren Schnitt teilen hilft **nicht** (Rate bleibt). Deshalb: Ende bis zur nächsten Pause verlängern (bis 7 s); bleibt es darüber, Cue behalten und zählen. Ob die Anforderung "höchstens 20 Z/s" als harte Eigenschaft oder als "gezählt und benannt" gilt, ist **Owner-Frage F3**.
7. Ein Wort > 42 Zeichen (Kompositum) bekommt eine eigene Zeile und wird hart bei 41 Zeichen mit `-` getrennt [Entscheid offen, Teil von F3].
8. Kurzer Einzel-Cue unter 1 s, dessen Verlängerung mit dem Nachbarn kollidiert: mit dem vorigen Cue zusammenlegen, wenn die Grenzen das erlauben.

**Formate:**
- VTT: `WEBVTT` + Leerzeile, optional `NOTE`-Block mit "Untertitel-Entwurf, automatisch erstellt" (lokalisiert, kein `-->` im Text), Zeit `HH:MM:SS.mmm --> HH:MM:SS.mmm`, Text mit `&` `<` `>` als `&amp;` `&lt;` `&gt;` maskiert, UTF-8 ohne BOM, LF.
- SRT: fortlaufende Nummer ab 1, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, Text, Leerzeile; keine Leerzeile innerhalb eines Cues; kein Kommentar-Mechanismus, die Kennzeichnung trägt nur der Dateiname/die UI.
- TXT (D-04-03): Kopfzeile (Dateiname + "Untertitel-Entwurf"-Hinweis, Anzeigesprache), Leerzeile, Fließtext; Absatz bei Pause > 2 s (Vorschlag).

### Anti-Patterns to Avoid
- **Zahlen in den gespeicherten Text schreiben:** `body_de` ist das gespeicherte Feld und liefert den Ausschnitt jedes Treffers (`IndexHit.text`); Umschreiben zeigt Nutzern "30000" statt "30.000".
- **Benutzereingabe als Query-Syntax weiterreichen, wenn Zahlen erweitert werden:** gemessen wirft `parse_query("12:30")` "Field does not exist: '12'" und die Suche liefert still nichts; `"open`, `(x`, `-zwölf` werfen ebenfalls. Der Zahlenweg baut die Query aus Einzelwörtern.
- **`Folder::newFile` ohne eigene Existenzprüfung:** überschreibt.
- **`IShare::canDownload()`** benutzen: fehlt in 33.0.0 (`@since 33.0.1` im Zweig stable33, `@since 34.0.0` in stable34/35).
- **Filter im Container:** Container kennt weder Rechte noch `oc_share`; mtime im Container ist der Stand der Erfassung.
- **Viewer-Integration versprechen:** README und UI dürfen für NC 33 bis 35 nicht sagen, dass der Viewer die Nebendatei anzeigt.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Content-Disposition mit Umlauten | eigene Header-Kodierung | `DataDownloadResponse` | RFC 6266 `filename*` + ASCII-Fallback schon drin |
| Rechte zum Schreiben | eigene Prüfung von Permissions-Bits | `Folder::isCreatable()` + `newFile` als Nutzer (actAs) | Quota, ACL, files_accesscontrol, Versionen greifen nur so |
| Download-Sperre | neue Logik | bestehende `downloadAllowed` als Dienst | entspricht `ViewOnly::checkFileInfo` des Servers |
| Personenfilter-Semantik | eigene Deutung | exakte Files-Bedingung (oben) | D-04-10 "gleichziehen" |
| SRT/VTT-Prüfung im Test | eigener Parser als Gegenprobe | webvtt-py, srt, ffmpeg | Gegenprobe nie mit dem Muster der Umsetzung (Owner-Regel) |
| Analyse der Varianten | Stämme von Hand | `parse_query` je Variante | gleiche Kette wie der Index |

**Key insight:** Alle drei Risikoflächen (Index-Konsistenz, Rechte, Dateiformate) haben fertige, geprüfte Mechanismen im Bestand oder im Server; die neue Logik beschränkt sich auf Zahlwort-Tabellen, Cue-Bildung und das Zusammenstecken.

## Komposita (D-04-13, SRCH-05, Erfolgskriterium 1): Messbefund

Am echten Projektcode gemessen (`scratchpad/scripts/probe_analyzer.py`, `probe_prune.py`, `probe_prefix.py`):

| Fall | Rezept A (Bestand) | Rezept A ohne zerlegbare Einträge |
|---|---|---|
| Haushaltsplanberatung | `haushaltsplan`, `berat` ("Haushalt" findet NICHT) | `haus`, `halt`, `plan`, `berat` |
| Haushaltssatzung | `haushalt`, `satzung` | `haus`, `halt`, `satzung` |
| Grundstücksverkehrsgenehmigung | `grundstuck`, `verkehr`, `genehm` | `grundstucksverkehrsgenehm` (schlechter) |
| Verbraucher | `verbrauch` | `verb`, `rauch` (falsch) |
| Feuerwehr / Unternehmen | ganz | `feu`,`wehr` / `nehm` (falsch) |
| Arbeitsvertrag / Bebauungsplan | ganz | `arbeit`,`vertrag` / `bebau`,`plan` (besser) |

Abfrageseitiger Kopf-Präfix (`Query.regex_query(schema, "body_de", "<stamm>.*")` als zusätzliche Should-Gruppe für Begriffe ab ca. 5 Zeichen): "Haushalt" findet `Haushaltsplanberatung` und `Haushälterin` (Beifang); "Miete" findet `Mietvertrag`; "Plan" findet `Bebauungsplan` weiterhin nicht (Kopf-Präfix hilft nicht für den Schwanz). Kein Neuindex nötig. Regex auf dem Term-Wörterbuch kostet bei großem Index Zeit; vor Übernahme an einem großen Index messen.

**Fazit:** Mit D-04-13 wörtlich ist Erfolgskriterium 1 für "Haushalt -> Haushaltsplanberatung" nicht erfüllbar; das Beispiel ist ein Grenzfall des Findling-Rezepts. Entscheid F1.

## Runtime State Inventory

Phase 4 ist kein Umbenennungs-Umbau; relevant ist nur, ob bestehender Zustand mitwandern muss.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Tantivy-Index (gen-N) und SQLite `transcript.language = 'und'` für alle Vorschau-Versionen | Mit Abfrage-Erweiterung: kein Neuindex. Mit Analyzer-Änderung (nur F1-Option C): `ANALYZER_VERSION` erhöhen, Neubau aus SQLite beim Start. Sprache: bei F2 Variante "im Worker speichern" Datenmigration oder Lazy-Bestimmung für Altbestand |
| Live service config | keine | keine, geprüft: Routen kommen aus Attributen und info.xml im Repo |
| OS-registered state | keine | keine |
| Secrets/env vars | keine neuen | keine |
| Build artifacts | `backend/.venv` bekommt zwei dev-Pakete | `uv sync` |

## Common Pitfalls

### Pitfall 1: Kompositum steht selbst in der Liste
**What goes wrong:** "Haushalt" findet "Haushaltsplanberatung" nicht.
**Why:** leftmost-longest auf einer Liste, die `haushaltsplan` enthält.
**How to avoid:** F1 entscheiden; Testfall genau mit diesem Beispiel, dazu Findlings `COMPOUNDS`- und `UNSPLIT`-Tabellen übernehmen.
**Warning signs:** Test, der nur "irgendein Treffer" prüft.

### Pitfall 2: Neuindex ohne Not
**What goes wrong:** Analyzer-Änderung erhöht die Marke, `open_generation` baut beim Start synchron neu; die Suche antwortet in der Zeit nicht.
**How to avoid:** Zahlen und Präfix nur abfrageseitig; falls doch Index-Änderung: Dauer messen und ehrlichen Status melden.

### Pitfall 3: Sprache "und" im Dateinamen
**What goes wrong:** `sitzung.und.vtt`, vom NC-36-Viewer ignoriert, für Menschen unverständlich.
**How to avoid:** F2; Test, dass nur `de|en|fr` im Namen erscheinen kann.

### Pitfall 4: Filter senkt die Ausbeute einer Seite
**What goes wrong:** Mit Filter fallen viele Vorschläge weg; nach `MAX_ROUNDS = 3` × `OVERFETCH = 4` ist die Seite dünn und "Mehr laden" fehlt.
**How to avoid:** Verhalten im Test festhalten; bei gesetzten Filtern Runden/Overfetch moderat erhöhen, Zeitbudget 2,5 s bleibt Grenze.

### Pitfall 5: Download-Sperre nur in der UI
**What goes wrong:** Buttons ausgeblendet, Route liefert trotzdem.
**How to avoid:** Prüfung im Controller vor jedem Container-Aufruf; PHPUnit-Fall mit `ISharedStorage`-Mock und Attribut `download=false`, in E2E mit echter Freigabe.

### Pitfall 6: `newFile` überschreibt
Siehe Pattern 4. Test: vorhandene Datei, Inhalt danach byte-gleich.

### Pitfall 7: VTT-Text mit Sonderzeichen
**What goes wrong:** `-->` oder `<` im Transkript bricht Parser.
**How to avoid:** Maskierung; Fuzz-Test mit Oberflächen aus `<`, `&`, `-->`, Leerzeilen, sehr langen Wörtern, leerer Wortliste, gleichen Zeitstempeln.

### Pitfall 8: Suche nach Zahl in Uhrzeit/Dezimalzahl
**What goes wrong:** "12:30" endet heute in einem `ValueError` und leerer Suche (gemessen).
**How to avoid:** Zahlenweg baut aus Einzelwörtern; Test "12:30" findet "12 Uhr 30"? mindestens kein Fehler.

### Pitfall 9: Teiltranskript exportiert
**What goes wrong:** Während eine lange Datei noch läuft (`partial`), bekommt der Nutzer einen abgeschnittenen Untertitel ohne Hinweis.
**How to avoid:** Owner-Frage F4; mindestens Hinweis im TXT-Kopf/NOTE.

## Code Examples

### Filter lesen (PHP)
```php
// Source: nextcloud/server stable34 apps/files/lib/Search/FilesSearchProvider.php (Semantik), lib/public/Search/IFilter.php
public function getSupportedFilters(): array {
	return [IFilter::BUILTIN_TERM, IFilter::BUILTIN_SINCE, IFilter::BUILTIN_UNTIL, IFilter::BUILTIN_PERSON];
}
$since = $query->getFilter(IFilter::BUILTIN_SINCE)?->get();   // \DateTimeImmutable
$person = $query->getFilter(IFilter::BUILTIN_PERSON);         // UserFilter (get(): IUser) oder GroupFilter (get(): IGroup)
```
Hinweis: `UserFilter`/`GroupFilter` sind `OC\`-Klassen; im Provider über `$filter->get() instanceof IUser` bzw. `IGroup` unterscheiden, nicht über die private Klasse.

### Personenbedingung (gleich Files)
```php
// Files: OR( owner = uid , AND(share_with = uid, share_type = USER) ), innerer Join file.fileid = s.file_source
$qb->select('file_source')->from('share')
   ->where($qb->expr()->in('file_source', $qb->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)))
   ->andWhere($qb->expr()->orX(
       $qb->expr()->eq('uid_owner', $qb->createNamedParameter($uid)),
       $qb->expr()->andX(
           $qb->expr()->eq('share_with', $qb->createNamedParameter($uid)),
           $qb->expr()->eq('share_type', $qb->createNamedParameter(IShare::TYPE_USER, IQueryBuilder::PARAM_INT)))));
```

### Download-Antwort
```php
// Source: lib/public/AppFramework/Http/DataDownloadResponse.php (seit 8.0.0, stable33/34/35 gleich)
return new DataDownloadResponse($body, $baseName . '.' . $lang . '.srt', 'application/x-subrip; charset=utf-8');
```

### Viewer-Namensregel (NC 36, zur Gestaltung des Namens)
```ts
// Source: nextcloud-libraries/nextcloud-viewer main lib/utils/subtitleNames.ts
const name = extension === '' ? video.basename : video.basename.slice(0, -extension.length)
new RegExp(`^${escapeRegExp(name)}(?:\\.([A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*))?\\.(vtt|srt)$`, 'i')
// nur für file.mime video/*, Untertitel aus Freigaben ohne Download werden weggelassen
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Viewer-App `nextcloud/viewer` (Plyr, keine Nebendatei-Spuren) | Bibliothek `@nextcloud/viewer` 2.0.0-beta mit `useSubtitles` | gemergt 02.11.2026, im Server nur `master` (NC 36 dev, `^2.0.0-beta.20`) | Nebendatei ab NC 36 automatisch sichtbar, 33 bis 35 nicht |
| Download-Sperre nur über Attribut | `IShare::canDownload()`/`canSeeContent()` | canSeeContent 32.0.0, canDownload 33.0.1/34.0.0 | Attribut weiter nutzen, solange 33.0.0 unterstützt wird |
| Unified Search: Anbieter ohne Filter versteckt | Anbieter ohne Filter unter "Partial matches" | 33/34 bereits, 35 Modal neu geschrieben | SRCH-06: nur mit `since`+`until`+`person` bleibt die Gruppe im Hauptteil |

**Deprecated/outdated:**
- Annahme aus `ARCHITECTURE.md` (Anti-Pattern 6), Viewer-PR #907 könne Nebendateien laden: im Code von stable33 bis 35 nicht vorhanden [VERIFIED].
- Phase-1-Kommentar in `Provider::getSupportedFilters` ("Only the term in phase 1") wird ersetzt.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | webvtt-py 0.8.0 und srt 3.5.3 sind legitime Pakete (slopcheck nicht gelaufen) | Standard Stack | Lieferkette; Checkpoint vor `uv add` |
| A2 | pysubs2 ist als Prüfer zu tolerant | Alternatives | gering, nur Werkzeugwahl |
| A3 | Eigener Sperrschlüssel über `ILockingProvider` ist das passende Muster gegen Doppelablage | Pattern 4 | Restrisiko Doppelablage; Signatur vor Bau prüfen |
| A4 | Export einer 12-h-Datei passt in ca. 15 s Timeout | Pattern 3 | Abbruch bei langen Dateien; messen |
| A5 | Regex-Präfixabfrage bleibt auf großen Indexen schnell genug | Komposita | Suchzeit über Budget 2,5 s; nur relevant bei F1 Option B |
| A6 | Pausenschwelle ca. 700 ms als Cue-Schnitt, Absatz bei 2 s im TXT | Pattern 5 | nur Lesbarkeit; am Korpus prüfen |

## Open Questions (RESOLVED)

1. **F1 (Owner, blockiert SRCH-05/Kriterium 1): Wie soll "Haushalt" "Haushaltsplanberatung" finden?**
   - What we know: Rezept A (D-04-13) liefert `haushaltsplan|berat`; gemessen findet "Haushalt" nichts. Prune-Rezept gemessen schlechter. Kopf-Präfix gemessen wirksam mit Beifang.
   - Optionen: (A) Kriterium-Beispiel als bekannte Grenze dokumentieren (z. B. auf "Haushaltssatzung" ändern), D-04-13 unverändert; (B) zusätzliche abfrageseitige Kopf-Präfix-Gruppe auf `body_de` (kein Neuindex, Beifang wie "Haushälterin", nur Kopfteile); (C) Rezept ändern (widerspricht D-04-13, gemessene Variante schlechter, Neuindex).
   - Recommendation: (B), mit Messung von Beifang und Zeit an einem großen Index; Findling-Tabellen als Regressionsschutz.
   - RESOLVED: D-04-14 (Option B, Präfix-Klausel zur Abfragezeit, kein Neuindex, Wortliste unverändert; umgesetzt in Plan 04-06, Container-Beleg in Plan 04-14)
2. **F2 (Owner, blockiert EXP-03/D-04-04): Woher kommt die Sprache im Dateinamen?**
   - What we know: alle Vorschau-Versionen tragen `und`; py3langid läuft je Fenster im Kindprozess, das Ergebnis wird nicht gespeichert.
   - Optionen: (a) Worker speichert die Dateisprache (Wortgewichtete Mehrheit der behaltenen Fenster mit Sprache de/en/fr) in `transcript.language`, Altbestand wird beim Export einmal nachbestimmt; (b) Export-Route bestimmt sie jedes Mal per py3langid (auf de/en/fr beschränkt) über den Text; (c) Nutzer wählt die Sprache auf der Abspielseite. Unentscheidbar oder gemischt: ohne Sprachteil (`sitzung.vtt`, vom NC-36-Viewer akzeptiert) oder Mehrheitssprache.
   - Recommendation: (a) plus Rückfall (b) für Altbestand; bei Mischsprache die Mehrheitssprache; nie `und`.
   - RESOLVED: D-04-15 (Option a plus Rückfall b, nie `und`; Plan 04-05 und 04-09)
3. **F3 (Owner): 20 Zeichen/s hart oder gezählt?** Wortgetreue Untertitel schneller Rede können die Grenze ohne Kürzen oder Zeitversatz nicht immer halten. Recommendation: Grenze halten, wo Pausen es erlauben; Rest zählen, im NOTE-Block nennen, Anteil am Korpus messen und im Plan belegen. Dazu: Wörter > 42 Zeichen hart trennen?
   - RESOLVED: D-04-16 (Best-Effort plus Zählung mit Schwelle als Gate, überlange Wörter ungetrennt auf eigener Zeile, Text nie verändert; Plan 04-07)
4. **F4 (Owner): Export während die Datei noch transkribiert wird?** Recommendation: erlauben mit Hinweis "Teiltranskript" in TXT-Kopf und VTT-NOTE, oder Buttons erst nach fertigem Transkript; Owner wählt.
   - RESOLVED: D-04-17 (Export erlaubt mit Hinweis T15 "Transkript bis mm:ss"; Plan 04-09, 04-10, 04-11)
5. **F5 (Owner, Info zu D-04-07): Viewer zeigt die Nebendatei erst ab NC 36.** Schema passt; soll die eigene Abspielseite auf 33 bis 35 die erzeugte VTT als `<track>` zeigen? Recommendation: nicht in Phase 4 (kein Requirement), README ehrlich formulieren.
   - RESOLVED: D-04-18 (Owner abweichend von der Empfehlung: Spur am Player IN Phase 4, README nennt NC 36; Plan 04-10, 04-11, 04-13)
6. **Neue Texte (UI-Abnahme-Regel):** Button-Beschriftungen, "Neben das Medium legen", Kollisionsfehler mit Dateiname, Sperr-Hinweis, fehlendes Schreibrecht, Kopfzeile TXT/NOTE. Entwurf DE/EN/FR vor dem Bau zeigen (UI-Phase empfohlen, `workflow.ui_phase: true`).
   - RESOLVED: Plan 04-03 (Owner-Freigabe der Texte T13 bis T35 und Kataloge vor dem Bau)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Projekt-venv mit tantivy 0.26.2, py3langid 0.4.0 | Messungen, pytest | ✓ | wie gepinnt | , |
| ngerman (wngerman 20161207-15) lokal | Analyzer-Messungen | ✓ (nur im Scratchpad entpackt, sha256 deb `911f25d2...27dc`) | 20161207-15 | im Image ohnehin vorhanden |
| ffmpeg | Zweit-Parser im Test | ✓ lokal 8.1.1; im Image | 8.1.1 / BtbN | nur webvtt-py/srt |
| Docker | deploy-harp/E2E lokal | Daemon lief nicht | , | CI (deploy-harp.yml, discovery-e2e.yml) |
| slopcheck | Paketprüfung | ✗ | , | Checkpoint human-verify |

**Missing dependencies with no fallback:** keine.
**Missing dependencies with fallback:** Docker lokal (CI), slopcheck (Checkpoint).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 (Backend), PHPUnit 11.5 gegen stable34 (PHP), Playwright in deploy-harp (UI) |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]`, `php/phpunit.xml`, `.github/workflows/*.yml` |
| Quick run command | `cd backend && uv run pytest -q tests/test_numbers.py tests/test_subtitles.py -x` |
| Full suite command | `cd backend && uv run pytest -q` ; PHP in CI (`php.yml`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRCH-05 | Zahlwort <-> Ziffer DE/EN/FR, Ordinalia, Jahre, Tausender (handgeschriebene Erwartungstabelle) | unit | `uv run pytest tests/test_numbers.py -x` | ❌ Wave 0 |
| SRCH-05 | Index-Probe: "zwölf"/"12"/"twelve"/"douze", "12:30" ohne Fehler, Häuser/Haus, Haushalt (je F1) | integration (tantivy im Temp-Verzeichnis, echte ngerman nur im Image/CI) | `uv run pytest tests/test_search_numbers.py -x` | ❌ Wave 0 |
| SRCH-05 | Kompositum-Regression (Findling COMPOUNDS/UNSPLIT) im Container mit wngerman | smoke (deploy-harp) | Workflow-Schritt analog "frist in Kündigungsfrist" | teilweise |
| SRCH-06 | `getSupportedFilters` meldet since/until/person; mtime-Grenzen inklusiv; Person/Gruppe wie Files | unit (PHPUnit) | `vendor/bin/phpunit --filter ProviderTest` | ✅ erweitern |
| SRCH-06 | Gruppe bleibt im Hauptteil bei Datumsfilter | e2e (Playwright) | deploy-harp | ❌ |
| SRCH-04 | Gesperrte Freigabe: Treffer ja, Export 403, Ablage 403, Buttons fehlen | unit + e2e | `phpunit --filter ExportControllerTest`; discovery-e2e | ❌ Wave 0 |
| EXP-01 | drei Formate, Dateiname `<Name>.<lang>.<ext>`, MIME | unit + e2e | `phpunit --filter ExportControllerTest`; `pytest tests/test_api_export.py` | ❌ |
| EXP-02 | Eigenschaften aller Cues (<=42, <=2 Zeilen, 1 bis 7 s, cps-Regel je F3, Abstand >= 80 ms, monoton) über Korpus- und Fuzz-Eingaben; Parser webvtt-py, srt und `ffmpeg -i x.vtt -f null -` ohne Fehler | unit (property) | `uv run pytest tests/test_subtitles.py -x` | ❌ Wave 0 |
| EXP-03 | Nie überschreiben (Byte-Vergleich), Kollision 409 mit Namen, kein Schreibrecht 403, Name NFC und ohne `und` | unit + e2e | `phpunit --filter SidecarTest` | ❌ |
| EXP-04 | Kein "BITV-konform" in l10n, README*, Store-Text, Exportinhalten; "Untertitel-Entwurf"/"Subtitle draft"/"Brouillon de sous-titres" vorhanden | gate | `uv run pytest tests/test_public_texts.py -x` | ✅ erweitern |

### Sampling Rate
- **Per task commit:** Quick run oben plus betroffene PHPUnit-Datei.
- **Per wave merge:** volle pytest-Suite, ruff `--no-cache`, pyright, vulture.
- **Phase gate:** Vollsuite grün, deploy-harp mit Filter- und Export-Schritten, Playwright 3 Breiten hell/dunkel, secure-phase.

### Wave 0 Gaps
- [ ] `backend/tests/test_numbers.py`: Erwartungstabelle von Hand (nicht aus dem Generator)
- [ ] `backend/tests/test_search_numbers.py`: Index-Proben inkl. "12:30"
- [ ] `backend/tests/test_subtitles.py`: Eigenschaften + unabhängige Parser
- [ ] `backend/tests/test_api_export.py`: Leck-Regel (`{"known": false}` für nicht aktive/ausgeschlossene Dateien)
- [ ] `php/tests/Unit/ExportControllerTest.php`, `SidecarTest.php`, `SearchFiltersTest.php`
- [ ] dev-Pakete: `uv add --group dev webvtt-py==0.8.0 srt==3.5.3` (nach Checkpoint)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein (Sitzung von Nextcloud) | `NoAdminRequired`, angemeldete Sitzung |
| V3 Session Management | ja (CSRF für Ablage) | AppFramework-CSRF auf POST, kein `NoCSRFRequired` für `sidecar` |
| V4 Access Control | ja | `readableFile` als Nutzer, `DownloadPolicy`, `isCreatable`, Ausschlussregeln, Leck-Regel im Container |
| V5 Input Validation | ja | `fileId` `\d+`, `format` aus fester Liste, Name nur aus dem Node abgeleitet, NFC, Bytelänge, Suchbegriff 200 Zeichen |
| V6 Cryptography | nein | , |
| V12 Files and Resources | ja | Schreiben nur über Nutzer-Sicht, nie überschreiben, Rate-Limit |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Export einer Datei aus einer Freigabe mit Download-Sperre | Information Disclosure | Sperrprüfung im Controller vor Container-Aufruf, 403 |
| Export einer nicht lesbaren / ausgeschlossenen Datei per geratener fileId | Information Disclosure | `readableFile` + Ausschluss + Container-Leck-Regel (gleiche Antwort wie "unbekannt") |
| Überschreiben fremder Untertitel | Tampering | `nodeExists` unter Sperre, nie `newFile` auf bestehenden Namen |
| Pfad-Injektion über Dateinamen | Tampering | Name aus Node, `/` und `\` unmöglich bzw. ersetzt, keine Nutzereingabe im Namen |
| CSRF-Ablage in fremdem Ordner | Tampering | CSRF-Token, nur POST |
| Ablage-Flut (Sync-Last) | Denial of Service | `#[UserRateLimit]`, Kollision verhindert Mehrfachablage |
| Personenfilter als Orakel für fremde Freigaben | Information Disclosure | Filter nur auf bereits als lesbar bestätigte Dateien; liefert nichts, was Files nicht auch zeigt |
| Log-Leck | Information Disclosure | keine Namen, Pfade, Begriffe in Logs (bestehende Regel) |
| Regex-DoS über Suchbegriff (nur F1-B) | Denial of Service | Präfix aus normalisiertem Stamm, Regex-Metazeichen maskieren (`re.escape`-Äquivalent), Mindestlänge |

## Sources

### Primary (HIGH confidence)
- nextcloud/server stable33/34/35/master: `apps/files/lib/Search/FilesSearchProvider.php`, `lib/private/Files/Cache/SearchBuilder.php`, `QuerySearchHelper.php` (`equipQueryForShares`), `lib/public/Search/IFilter.php`, `lib/private/Search/FilterFactory.php`, `Filter/UserFilter.php`, `SearchComposer.php`, `core/src/components/UnifiedSearch/UnifiedSearchModal.vue`, `apps/dav/lib/DAV/ViewOnlyPlugin.php`, `apps/files_sharing/lib/ViewOnly.php`, `lib/public/Share/IShare.php`, `lib/private/Share20/Share.php`, `lib/private/Files/Node/Folder.php`, `lib/public/AppFramework/Http/DownloadResponse.php`, `DataDownloadResponse.php`, `package.json` (raw.githubusercontent.com, 16.11.2026)
- nextcloud/viewer stable33/34/35 Quellbäume (codeload-Tarballs, vollständig durchsucht nach vtt/subtitle/track/caption)
- nextcloud-libraries/nextcloud-viewer main: `lib/utils/subtitleNames.ts`, `lib/composables/useSubtitles.ts`, `lib/utils/canDownload.ts`, `package.json` (2.0.0-beta.21)
- Messungen im Projekt-venv (tantivy 0.26.2) mit wngerman 20161207-15 aus deb.debian.org: Scratchpad `scripts/probe_analyzer.py`, `probe_prune.py`, `probe_prefix.py`
- Projektcode: `backend/src/audio_video_search_backend/index/*.py`, `api/search.py`, `api/excerpt.py`, `worker/preview.py`, `engine/catch.py`, `php/lib/Search/Provider.php`, `php/lib/Controller/PageController.php`
- Findling: `backend/src/findling/index/wordlist.py` (Rezepte A bis D), `backend/tests/test_analyzer.py` (COMPOUNDS, UNSPLIT)

### Secondary (MEDIUM confidence)
- pypi.org JSON: webvtt-py 0.8.0, srt 3.5.3, num2words 0.5.14
- Spike 2 Transkript `spike2/results/pk_fl_pipe_t4.json` (Zahlenschreibweisen von Parakeet)
- `.planning/research/FEATURES.md` (Untertitel-Regeln ARD/Netflix, BITV 7.1.2)

### Tertiary (LOW confidence)
- keine

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, alles im Bestand; die zwei dev-Pakete mangels slopcheck ASSUMED
- Architecture: HIGH für Filter, Sperre, Download, Viewer (Quellcode); MEDIUM für Sperrmuster der Ablage
- Pitfalls: HIGH, die zentralen (Kompositum, `und`, `newFile`, `12:30`) am Code gemessen

**Research date:** 2026-11-16
**Valid until:** 2026-12-16 (Viewer-Bibliothek und NC 36 bewegen sich schneller; Viewer-Befund bei NC-35-Patchreleases erneut prüfen)
