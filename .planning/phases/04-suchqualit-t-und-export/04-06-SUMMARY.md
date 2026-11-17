---
phase: 04-suchqualit-t-und-export
plan: 06
subsystem: backend/index
tags: [SRCH-05, komposita, praefix, zahlen, jahreszahlen, tantivy, messung]
requires:
  - "04-01: numbers.recognize/variants, Wortweg in SearchIndex.search und first_match_ms"
provides:
  - "publish.py: PREFIX_MIN_CHARS = 5, _prefix_pattern(stem), je Wort ab 5 Zeichen ohne Ziffer eine Query.regex_query-Klausel je deutschem Stamm auf body_de (D-04-14)"
  - "numbers.py: YEAR_RANGE = (1100, 2099), MAX_GROUPED = 100000, MAX_SPAN_WORDS = 7; Hunderter, Tausender, gruppierte Tausender und Jahre DE/EN/FR (D-04-11)"
  - "scripts/research/phase4/measure_prefix.py: p50/p95 mit und ohne Präfix, Beifang-Zählung, Exit 1 über Schwelle"
affects: [04-14]
tech-stack:
  added: []
  patterns: ["Präfix-Klausel nur abfrageseitig: Occur.Should aus parse_query(wort) plus regex_query(re.escape(stamm) + \".*\") auf body_de, kein Neuindex", "Jahres- und Skalenwörter als Surface-Tabellen, Erzeugung je Wert, Varianten gedeckelt"]
key-files:
  created:
    - backend/tests/test_compounds.py
    - scripts/research/phase4/measure_prefix.py
  modified:
    - backend/src/audio_video_search_backend/index/publish.py
    - backend/src/audio_video_search_backend/index/numbers.py
    - backend/tests/test_numbers.py
    - backend/tests/test_search_numbers.py
decisions:
  - "Präfix-Berechtigung hängt am Abfragewort (ab 5 Zeichen, ohne Ziffer), das Muster am Stamm der de-Kette: nur so findet Miete (Stamm miet, 4 Zeichen) den Mietvertrag; Haus (4 Zeichen) bekommt keine Klausel"
  - "Phase-3-Gleichheit (Reihenfolge und Scores wie parse_query) gilt seit diesem Plan nur noch für Begriffe aus Wörtern unter 5 Zeichen; längere Wörter nehmen den Wortweg mit Präfix"
  - "Ziffern-Gruppierung nur für die Wortfolge d plus 000 (30.000, 30,000, 30 000); beliebige Paare wie 3 100 bleiben zwei Zahlen, damit getrennte Angaben nicht zu einer Phrase verschmelzen"
  - "MAX_SPAN_WORDS von 5 auf 7: mille neuf cent quatre-vingt-dix-neuf faltet zu sieben Wörtern"
metrics:
  duration: "ca. 35 min"
  completed: 2026-11-16
  tasks: 2
  files: 6
---

# Phase 4 Plan 06: Komposita-Köpfe und voller Zahlenraum Summary

"Haushalt" findet "Haushaltsplanberatung" über eine abfrageseitige Präfix-Klausel auf body_de ohne Neuindex (D-04-14, gemessen p95 1,136 ms bei 100000 Dokumenten), und runde Hunderter/Tausender, gruppierte Tausender (30.000/30,000/30 000) sowie Jahreszahlen 1100 bis 2099 sind in DE/EN/FR den Ziffern gleichgesetzt (D-04-11). SRCH-05 ist damit im lokalen Index vollständig; der Container-Beleg mit echter Wortliste folgt in Plan 04-14.

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | Präfix-Klausel für Komposita-Köpfe, Messung Beifang und Suchzeit | 63e5bab (RED), e82ba4a (GREEN) | index/publish.py, tests/test_compounds.py, scripts/research/phase4/measure_prefix.py |
| 2 | Zahlenraum Hunderter, Tausender, gruppierte Tausender, Jahreszahlen | 1856c29 (RED), 75bdad4 (GREEN) | index/numbers.py, tests/test_numbers.py, tests/test_search_numbers.py |

## Ergebnis

- Jedes Abfragewort ab 5 Zeichen ohne Ziffer erhält in seiner Should-Gruppe je deutschem Stamm eine `Query.regex_query(schema, body_de, re.escape(stamm) + ".*")`-Klausel; der Stamm kommt aus derselben de-Kette wie der Index, nur [a-z]-Stämme werden Muster, gekappt auf MAX_TOKEN_CHARS (T-04-16). Analyzer, Schema, open.py und wordlist.py sind unverändert (`git diff` leer), ANALYZER_VERSION bleibt 1, kein Neuindex.
- Proben am kleinen ngerman-nachgestellten Index: "Haushalt" findet Haushaltsplanberatung und Haushaltssatzung; "Häuser" findet "Haus"; "Miete" findet "Mietvertrag"; "Haus" und "Plan" (unter 5 Zeichen) erzeugen keine Klausel; `first_match_ms("Haushalt", ...)` zeigt auf "Haushaltsplanberatung".
- Zahlen: zweihundert/two hundred/deux cents, tausend bis hunderttausend, dreißigtausend = 30000 = "30 000"-Phrase (deckt 30.000, 30,000, 30 000), Jahre 1100 bis 2099 (neunzehnhundertneunzig, nineteen ninety, nineteen oh five, mille neuf cent quatre-vingt-dix, dix-neuf cent ..., zweitausendvierundzwanzig, zwanzigvierundzwanzig, twenty twenty four, deux mille vingt-quatre). Index-Proben: "dreißigtausend Hirsche" findet "30.000 gepflegte Hirsche"; "1940" findet "neunzehnhundertvierzig"; "1963" findet "nineteen sixty three".
- Kein voller Zahlenparser: 234, 2345, 150, 12500, 123456, neunhundertneunzig, zwölftausend bleiben nur Ziffern beziehungsweise normale Wörter (Test). Variantenzahl je Wert bleibt unter 24 für alle Werte inklusive aller Jahre.
- Gates: ruff `--no-cache` (check und format) grün, pyright 0 Fehler, vulture grün, volle Suite: 2211 bestanden, 15 übersprungen, 4 xfailed.

## Messwerte (measure_prefix.py, 100000 Dokumente, 200 Abfragen, Seed fest, Exit 0)

Suchzeit je Abfrage (ms), zehn typische Begriffe im Wechsel:

| Weg | p50 | p95 | Mittel |
|-----|-----|-----|--------|
| Bestandsweg (parse_query) | 0,171 | 0,199 | 0,177 |
| Mit Präfix-Klausel (search) | 0,907 | 1,136 | 0,947 |

Schwelle 250 ms klar eingehalten (Faktor ca. 220 Luft); die Klausel verfünffacht die Zeit, bleibt aber im Mikro-Bereich. Beifang: Treffer im synthetischen Index (legacy gegen Präfix) und Obergrenze gegen die echte ngerman-Liste (356010 Einträge, wngerman_20161207-15, sha256 911f25d2695a44331c7c1d352cb760c4b472128840a1799d6bb10bcc832727dc, nur im Scratchpad):

| Begriff | Treffer Bestandsweg | Treffer mit Präfix | ngerman-Einträge mit Stamm-Präfix |
|---------|--------------------:|-------------------:|----------------------------------:|
| Haushalt | 8890 | 24326 | 126 |
| Sitzung | 8757 | 24473 | 12 |
| Beratung | 9766 | 35742 | 94 |
| Vertrag | 8839 | 24402 | 146 |
| Verwaltung | 8829 | 24213 | 83 |
| Gemeinderat | 9032 | 24399 | 9 |
| Bebauung | 8880 | 24307 | 28 |
| Schule | 8783 | 32429 | 453 |
| Feuerwehr | 8801 | 24227 | 6 |
| Antrag | 9027 | 24707 | 39 |

Die synthetischen Mehr-Treffer stammen aus absichtlich eingestreuten Komposita (ungünstigster Fall: Bestandteilliste nur Fugen, nichts wird zerlegt). Die ngerman-Spalte ist die ehrliche Obergrenze echter Wörter je Präfix (Beispiel Haushalt: 126 Einträge, darunter Haushälterin). T-04-17 (Beifang) bleibt akzeptiert: Treffer liegen nur in Dateien, die der Nutzer lesen darf.

## Bekannte Grenzen

1. **Beifang des Kopf-Präfixes:** "Haushalt" trifft auch "Haushälterin" (benannter Test, akzeptiert in D-04-14/T-04-17).
2. **Nur der Kopf:** "Plan" findet "Bebauungsplan" nicht; der Präfix hilft nie für den Schwanz eines Kompositums (benannter Test).
3. **"vingt et un"** trifft weiter jedes "vingt" (Stoppwörter et/un), jetzt auch als Index-Probe benannt ("vingt-deux" wird gefunden).
4. **Jahres-Zweiteiler als Beifang:** "twelve thirty" gilt als Jahr 1230; eine gesprochene Uhrzeit in dieser Form trifft mit.
5. **Asymmetrie der Gruppierung:** "30.500" findet "30500" (Wortfolge 30/500 trifft beide Gruppen), aber "30500" als ein Wort bleibt nur Ziffer (nicht rund, kein Jahr).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Plan-Widerspruch] Präfix-Berechtigung am Wort, Muster am Stamm**
- **Found during:** Task 1
- **Issue:** Der Plan sagt an einer Stelle "nur für Stämme ab 5 Zeichen", verlangt aber als Pflicht-Verhalten "Miete findet Mietvertrag". Der Stamm von "Miete" ist "miet" (4 Zeichen); mit Stamm-Regel wäre das Verhalten unerfüllbar.
- **Fix:** Berechtigung = Abfragewort ab PREFIX_MIN_CHARS ohne Ziffer; Muster = Stamm. Das Plan-Beispiel "Haus" (4 Zeichen) bleibt wie gefordert ohne Klausel.
- **Commit:** e82ba4a

**2. [Rule 1 - Testerwartung] Phase-3-Gleichheit nur noch für kurze Wörter**
- **Found during:** Task 1
- **Issue:** Der Bestandstest verlangte Score-Gleichheit mit parse_query für "Häuser" und "Markt"; beide Wörter haben 5 und mehr Zeichen und nehmen laut Plan jetzt den Präfix-Weg (konstanter Score-Anteil der regex-Klausel).
- **Fix:** Gleichheitstest auf kurze Wörter ("März", "jour") umgestellt, wie im Plan-Verhalten beschrieben; neuer Test hält fest, dass "Häuser"/"Markt" ihre Treffer und Reihenfolge behalten. Bei "März" zusätzlich Score-Gleichstand der beiden Dokumente: Mengen- statt Reihenfolge-Erwartung (Reihenfolge bei Gleichstand nicht baustabil), die Referenzgleichheit bleibt der Beweis.
- **Commit:** e82ba4a, 1856c29

**3. [Rule 1 - Planbeispiel] 1234 liegt im Jahresfenster**
- **Found during:** Task 2
- **Issue:** Das Akzeptanzkriterium nennt "1234 nur als Ziffer", die Pflicht-Wahrheit setzt aber alle Jahre 1100 bis 2099 den Ziffern gleich; 1234 liegt in diesem Fenster.
- **Fix:** Pflicht-Wahrheit umgesetzt (1234 wird als Jahr erkannt, Test `test_1234_lies_inside_the_year_window_and_is_equated` benennt es); der Kein-Parser-Test nutzt Werte außerhalb der Muster (234, 2345, 12500, 123456).
- **Commit:** 75bdad4

**4. [Rule 3 - Schnittstelle] MAX_SPAN_WORDS von 5 auf 7**
- **Found during:** Task 2
- **Issue:** "mille neuf cent quatre-vingt-dix-neuf" (1999) faltet zu sieben Wörtern; mit der 04-01-Grenze 5 wäre kein französisches Jahr erkennbar.
- **Fix:** Konstante auf 7, Test umbenannt und erweitert; die 04-01-Fälle bleiben unverändert grün.
- **Commit:** 75bdad4

**5. [Rule 3 - Werkzeug] tantivy-Stubs kennen SearchResult.count nicht**
- **Found during:** Task 1 (pyright-Gate)
- **Issue:** Das Messskript sollte Trefferzahlen über `result.count` lesen; die Stubs von tantivy 0.26.2 führen das Attribut nicht, pyright schlug fehl.
- **Fix:** Zählung über die Länge der Trefferliste mit Dokumenten-Obergrenze; Ergebnis identisch.
- **Commit:** e82ba4a

### Anmerkungen ohne Code-Abweichung

- Die Testliste in test_compounds.py enthält zusätzlich den Eintrag `bebauungsplan`, weil ngerman das Wort selbst führt und ein Eintrag nie zerlegt wird; nur so stellt der kleine Index das echte Verhalten ("Plan findet Bebauungsplan nicht") nach.
- Einmalig traten beim gemeinsamen Lauf dreier Testdateien 26 Fixture-Fehler auf (bekannter Windows-tantivy-Umbenennungsfehler os error 5 aus 04-01); nicht reproduzierbar, alle Folgeläufe und die volle Suite grün.
- Wortliste beschafft wie geplant: wngerman_20161207-15_all.deb von deb.debian.org, sha256 geprüft (voller Wert oben), per eigener Skriptdatei entpackt, nur im Scratchpad; die Beifang-Zählung ist damit NICHT "offen, Plan 04-14", sondern mit Zahlen belegt. Plan 04-14 ergänzt den Beleg im Container.

## TDD Gate Compliance

Task 1: RED 63e5bab, GREEN e82ba4a. Task 2: RED 1856c29, GREEN 75bdad4. REFACTOR-Commits waren nicht nötig.

## Threat Flags

Keine neue Angriffsfläche über das Threat-Register des Plans hinaus.
- T-04-16 (ReDoS/teure Automaten) mitigiert: Muster nur aus gefaltetem Analyzer-Stamm, re.escape, nur Suffix ".*", Kappung auf MAX_TOKEN_CHARS, Wort-Mindestlänge 5, keine Ziffern; p95 gemessen 1,136 ms gegen Schwelle 250 ms, Skript endet sonst mit Code 1.
- T-04-17 (Beifang) akzeptiert und oben mit Zahlen benannt; Rechteprüfung in PHP unverändert.
- T-04-18 (Wortliste/Messdaten) mitigiert: nur synthetische Daten im Index, Wortliste nur im Scratchpad, JSON enthält Zahlen und die zehn festen Begriffe, keine Nutzerdaten.

## Known Stubs

Keine.

## Self-Check: PASSED

- FOUND: backend/tests/test_compounds.py
- FOUND: scripts/research/phase4/measure_prefix.py
- FOUND: backend/src/audio_video_search_backend/index/publish.py (PREFIX_MIN_CHARS, regex_query, re.escape)
- FOUND: backend/src/audio_video_search_backend/index/numbers.py (YEAR_RANGE)
- FOUND: Commits 63e5bab, e82ba4a, 1856c29, 75bdad4
