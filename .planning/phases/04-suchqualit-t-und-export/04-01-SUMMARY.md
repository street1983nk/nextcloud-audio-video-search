---
phase: 04-suchqualit-t-und-export
plan: 01
subsystem: backend/index
tags: [SRCH-05, zahlen, ordinalia, tantivy, abfrage]
requires: []
provides:
  - "index/numbers.py: NumberSpan(start, stop, value, ordinal), recognize(words), variants(value, ordinal), MAX_SPAN_WORDS = 5, MAX_VALUE = 100"
  - "SearchIndex.search: Wortweg _word_query für Begriffe mit Zahl oder Syntaxfehler; first_match_ms kennt alle Schreibweisen einer Zahl"
affects: [04-06]
tech-stack:
  added: []
  patterns: ["abfrageseitige Erweiterung ohne Neuindex: je Zahl eine Occur.Should-Gruppe der Schreibweisen, zwischen Wörtern Occur.Must", "Bestandsweg bleibt für Begriffe ohne Zahl und ohne Syntaxfehler"]
key-files:
  created:
    - backend/src/audio_video_search_backend/index/numbers.py
    - backend/tests/test_numbers.py
    - backend/tests/test_search_numbers.py
  modified:
    - backend/src/audio_video_search_backend/index/publish.py
decisions:
  - "Im Wortweg fällt ein Wort heraus, das in irgendeiner der drei Ketten ein Stoppwort ist (nicht erst bei leerer Ausgabe in allen drei): derselbe Text steht in allen drei Feldern, deshalb landet das deutsche 'ein' sonst als Term im englischen Feld und leert 'ein 12'"
  - "Die Gruppe einer Zahl enthält immer auch die Wörter, wie sie getippt wurden; damit ist der Wortweg für eine Zahl nie enger als der Bestandsweg"
  - "Ein Punkt hinter Ziffern bleibt als deutsche Ordinalmarke, außer es folgt ein Buchstabe oder eine Ziffer ('1.000'); Ziffern mit führender Null und über 100 sind keine Zahl in diesem Plan"
  - "Wörter gehen klein geschrieben an parse_query, damit AND, OR und NOT im Wortweg normale Wörter bleiben; gleiche Gruppen werden nur einmal gebaut (T-04-01)"
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-16
  tasks: 2
  files: 4
---

# Phase 4 Plan 01: Zahlen als Ziffer und Wort finden Summary

Abfrageseitige Zahlensuche ohne Neuindex: `index/numbers.py` erkennt Ziffern, Zahlwörter und Ordinalia DE/EN/FR von 0 bis 100 und liefert alle Schreibweisen, `SearchIndex.search` baut daraus je Zahl eine Should-Gruppe; "zwölf" findet "12", "twelve", "douze", "zwölften", "12th", "12e", und "12:30" endet nicht mehr leer.

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | numbers.py mit handgeschriebener Erwartungstabelle | f8fd81e (RED), e8d2815 (GREEN) | index/numbers.py, tests/test_numbers.py |
| 2 | Wortweg in search und first_match_ms, 12:30 ohne Fehler | 002e409 (RED), c3d45a1 (GREEN) | index/publish.py, tests/test_search_numbers.py |

## Ergebnis

- `recognize` sucht gierig die längste Folge bis fünf Wörter: "vingt et un", "quatre vingt dix neuf", "twenty-first" als ein Wort oder getrennt. Artikel `ein/eine/un/une` sind allein nie eine Zahl, und 1 erweitert nie auf sie.
- `variants` liefert je Zahl eine feste, kleine Menge Schreibweisen, für 100 von Hand gezählt 15. Der Test verlangt höchstens 24 und keine Dubletten für alle Werte von 0 bis 100. Mehrteilige Schreibweisen kommen als Phrase in Anführungszeichen. Kardinal- und Ordinal-Abfrage enthalten dieselben Formen (Datumsfall D-04-12), nur die Reihenfolge unterscheidet sich.
- Index-Proben: "zwölf", "12", "twelve", "douze", "zwölften", "twelfth", "douzième", "12th" und "12e" finden alle neun 12er-Segmente. "12 Personen" findet nur eins, "zwölften März" und "am 12. März" finden beide Datumssegmente, "70 personnes" findet "soixante-dix personnes", "12:30" findet "um 12 Uhr 30", "ein 12" verhält sich wie "12".
- Ohne Zahl: "Häuser" und "Markt" liefern dieselben Treffer und Scores wie eine direkte tantivy-Abfrage über den Weg von Phase 1 bis 3, in der notierten Reihenfolge.
- `first_match_ms("zwölf", "Es waren 12 Personen")` zeigt auf das Wort "12".
- analyzer.py, schema.py und open.py sind unverändert, ANALYZER_VERSION bleibt 1, es gibt keinen Neuindex.
- Gates: ruff `--no-cache` (check und format) grün, pyright 0 Fehler, vulture grün, volle Suite: 2095 bestanden, 15 übersprungen, 4 xfailed.

## Bekannte Grenzen

1. **"vingt et un":** Nach den Stoppwörtern bleibt nur `vingt`, deshalb trifft die Phrase jedes `vingt`, also auch 20 bis 29 (Beifang, 04-RESEARCH Grenze 2). Das gilt genauso für den Sprung in `first_match_ms`.
2. **Mehrdeutige Wörter im Wortweg:** "one", "second", "achten", "cent" und "neuf" gelten als Zahl. Die Gruppe enthält immer das getippte Wort, deshalb fallen keine Treffer weg. Es kommen nur Treffer mit der Zahl in anderer Schreibweise dazu.
3. **Phrasen im Begriff:** Ein Begriff mit Zahl geht Wort für Wort. Anführungszeichen um eine Wortfolge mit Zahl wirken nicht mehr als Phrase.
4. Hunderter, Tausender, "30.000" und Jahreszahlen folgen in Plan 04-06.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stoppwort-Regel des Wortwegs**
- **Found during:** Task 2
- **Issue:** Laut Plan sollte ein Wort nur herausfallen, wenn keine der drei Ketten einen Token liefert. "ein" liefert aber im englischen und französischen Feld den Term `ein`, deshalb fand "ein 12" nichts.
- **Fix:** Jetzt fällt ein Wort heraus, sobald eine Kette es als Stoppwort entfernt (`_carries_meaning`).
- **Commit:** c3d45a1

**2. [Rule 3 - Blockierend] Index-Fixture einmal je Modul**
- **Found during:** Task 2
- **Issue:** 13 Commits je Test führten unter Windows gelegentlich zu `os error 5` beim Umbenennen durch tantivy (Setup-Fehler, nicht Produktcode).
- **Fix:** Die Fixture in `test_search_numbers.py` hat jetzt den Scope `module`. Die Tests lesen nur.
- **Commit:** c3d45a1

**3. Testerwartung "Häuser"**
- Die Erwartung "Markt Markt Häuser" führt immer galt nur für "Markt". Bei "Häuser" sind Länge und Häufigkeit gleich. Die Reihenfolge ist jetzt je Begriff als Liste notiert, vor dem RED-Commit korrigiert.

**4. Planregel zu STATE/ROADMAP**
- Der Plan sagt, STATE.md und ROADMAP.md nicht zu schreiben. Der Auftrag des Orchestrators verlangt die Fortschrittspflege, wie in 04-04. Das wurde befolgt. REQUIREMENTS.md bleibt unverändert, weil SRCH-05 nur mit dem Zahlenteil erfüllt ist.

## TDD Gate Compliance

RED f8fd81e und 002e409, danach GREEN e8d2815 und c3d45a1. Ein REFACTOR-Commit war nicht nötig.

## Threat Flags

Keine neue Angriffsfläche.
- T-04-01: Begriff auf 200 Zeichen gekürzt, MAX_SPAN_WORDS = 5, Varianten je Zahl begrenzt (Test), gleiche Gruppen nur einmal.
- T-04-02: Kein Logging von Begriff, Wort oder Variante, der Modulkommentar sagt es.
- T-04-03: Der Wortweg baut die Abfrage aus alphanumerischen Einzelwörtern. Syntaxfehler enden nicht mehr in ValueError.

## Self-Check: PASSED

- FOUND: backend/src/audio_video_search_backend/index/numbers.py
- FOUND: backend/tests/test_numbers.py
- FOUND: backend/tests/test_search_numbers.py
- FOUND: Commits f8fd81e, e8d2815, 002e409, c3d45a1
