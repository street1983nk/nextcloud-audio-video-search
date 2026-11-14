---
phase: 03-vorschau-transkripte-in-der-suche
plan: 14
subsystem: api
tags: [excerpt, leck-regel, preview_job, occ, tdd]
requires: ["03-09"]
provides:
  - "POST /excerpt: {known, excerpt, stage, partial, pendingHere, reason} für einen aktiven Verweis, limitHours nur bei too_long"
  - "POST /excerpt: genau {\"known\":false} für nicht aktive Verweise, Ausschluss, unbekannte Datei und aktiven Verweis ohne Job und ohne Version"
  - "occ audio_video_search:status: Zeile 'Preview:' nach 'By stage:', --json mit byPreview"
affects: [03-16, 03-17, 03-20]
tech-stack:
  added: []
  patterns:
    - "Zwei Pforten der Leck-Regel nebeneinander: preview_view (Job) und media_for_file (Text); known nur, wenn eine von beiden etwas nennt"
    - "Ausgehende Grundcodes nur aus repo.PREVIEW_REASONS, auch wenn die Datenbank etwas anderes enthält"
key-files:
  created:
    - php/tests/Unit/StatusCommandTest.php
  modified:
    - backend/src/audio_video_search_backend/api/excerpt.py
    - backend/tests/test_excerpt_states.py
    - backend/tests/test_sample_real_transcript.py
    - backend/tests/test_api_routes.py
    - php/lib/Command/StatusCommand.php
decisions:
  - "Offener Punkt aus 03-09 entschieden: aktiver Verweis mit current, aber ohne Job, liefert seinen Text wie bisher (partial false, reason null). Begründung: Die Pforte der Leck-Regel für Text ist media_for_file und lässt genau diesen Verweis durch; preview_view None heißt hier nur 'kein Job', nicht 'nicht erlaubt'. Ohne current und ohne Job: {\"known\":false} wie bisher."
  - "partial = Job in queued, running oder waiting und chunks_done > 0; ein skipped-Job nach einem Stück ist nicht mehr partial, sein Text bleibt"
  - "pendingHere = partial und atMs >= next_start_ms; dann excerpt null (kein Text von einer anderen Stelle)"
  - "stage beschreibt die current-Version (auch bei pendingHere), null ohne current"
  - "Ein Grundcode außerhalb von PREVIEW_REASONS (nur durch Handeingriff möglich) geht als reason null hinaus, nie roh"
  - "occ-Zeile listet wie By state/By stage auch Nullen, in der Reihenfolge, die ExAppService::coverage über PREVIEW_NAMES festlegt"
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-14
  tasks: 2
  files: 6
---

# Phase 3 Plan 14: Ausschnitt-Zustände und Preview-Zähler Summary

/excerpt nennt für einen aktiven Verweis Stufe, Teilstand (partial, pendingHere), Grundcode und bei too_long die eingestellte Höchstdauer; jeder andere Fall antwortet byte-gleich `{"known":false}`. occ status zeigt die Vorschau-Jobs je Grund oder Zustand in einer Zeile `Preview:`.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 RED | 6bf455b | test(03-14): Ausschnitt-Zustände unter der Leck-Regel als Vertrag |
| 1 GREEN | c8268d1 | feat(03-14): Ausschnitt mit Stufe, Teilstand und Grund |
| 2 | 040f27f | feat(03-14): Vorschau-Zähler im occ-Status |

Alle Commits lokal, Autor und Committer street1983nk <k.cherif@outlook.de>, nichts gepusht.

## Was gebaut wurde

- **api/excerpt.py**: `preview_view(file_id)` und `media_for_file(file_id)` nebeneinander. Keiner nennt etwas (bzw. keine current-Version): `{"known": False}` ohne weitere Schlüssel. Sonst `known, excerpt, stage, partial, pendingHere, reason`, dazu `limitHours = store.max_duration_hours()` nur bei `reason == "too_long"`. `stage_of` wird aus api/search.py importiert (Test prüft Identität). Grundcode nur, wenn er in `repo.PREVIEW_REASONS` steht.
- **Zustände A1 bis A13 ableitbar**: A1 (complete, Text, preview), A2 (partial true), A4 (pendingHere true, excerpt null), A5 (queued oder running ohne Stück: known true ohne Text und Grund; nicht erlaubt: known false), A6 bis A11 (reason, PHP ordnet no_audio, format_unsupported, engine_failed A11 zu, Plan 03-16), A10 (too_long + limitHours), A13 (disk_full, auch mit Teiltext).
- **StatusCommand.php**: `'Preview: ' . self::listed($coverage['byPreview'] ?? [])` direkt nach `By stage:`; `--json` trägt byPreview über `$coverage +`. Kopfkommentar ergänzt.
- **StatusCommandTest.php** (neu): Zeile von Hand ausgeschrieben, Lage zwischen By stage und Queue, genau eine Preview-Zeile, gleiche Ausgabe bei zwei Läufen, Form nur `code zahl`, kein `/`, JSON-Schlüsselreihenfolge mit byPreview, im JSON-Modus keine Textzeile.

## Tests und Gates

- Volle Backend-Suite: **1692 passed** (vor dem Plan 1682 im eigenen GREEN-Lauf; Zuwachs auch durch den parallelen Plan 03-07b).
- test_excerpt_states.py: 163 Fälle (24 Antwortfälle, 90 Leck-Fälle = 6 Job-Zustände x 15 nicht aktive Zustand/Stufe-Paare, Ausschluss, roher Code, Grenzfälle ohne Job, Grenze bei atMs = next_start_ms).
- Plan-Verify Task 1 (excerpt_states, sample_layer, sample_real_transcript, api_routes): 238 passed. Task 2: test_php_gates.py 43 passed, grep byPreview und Datei vorhanden.
- ruff check, ruff format --check (100 Dateien), pyright latest (0 Fehler), vulture: grün.
- RED-Lauf: 139 failed, 22 passed, jeweils aus dem erwarteten Grund (fehlende Felder, `excerpt: null` im unbekannten Fall, Positivkontrolle der Leck-Fälle ohne Text known false, `stage_of` fehlt in excerpt.py).
- Positivkontrollen:
  - 13 Mutationsproben gegen excerpt.py und repo.py (Filter PREVIEW_REASONS entfernt, limitHours bei jedem Grund, `>` statt `>=`, ohne chunks_done, `!= "complete"` statt Arbeitszustände, alte Antwortform, Text trotz pendingHere, zwei andere Pforten-Bedingungen, eigene stage-Abbildung, stage fest, `_PREVIEW_VIEW` ohne `state = 'active'`, Text über file_ref ohne active-Prüfung): alle rot. Eine Probe (`!= "complete"`) überlebte zuerst und führte zum Fall "Stück, dann engine_failed".
  - Das PHP-Gate rule10 schlug beim Hilfsnamen `run` bzw. `status` (final in TestCase) an und wurde mit `statusText` grün; damit ist das Gate selbst positiv belegt.
  - Gedankenstrich-Prüfung über alle geänderten Dateien: 0 Treffer; Prüfer an einer Probedatei mit U+2014 positiv (1 Treffer).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Nachbartests auf die neue Antwortform gezogen**
- **Found during:** Task 1 GREEN
- **Issue:** test_api_routes.py (2 Stellen) und test_sample_real_transcript.py (6 Stellen) verglichen die alte Form `{"known": ..., "excerpt": ...}`.
- **Fix:** unbekannt jetzt `{"known": False}`, echte Antwort mit allen Feldern (`REAL_ANSWER`, Probe mit stage "sample"). Nicht in files_modified des Plans, aber nötig.
- **Commit:** c8268d1

**2. [Rule 2] Roher Grundcode aus der Datenbank wird nicht weitergegeben**
- preview_job.reason hat keine CHECK-Bedingung im Schema; der Store prüft beim Schreiben. excerpt.py lässt zusätzlich nur Codes aus PREVIEW_REASONS hinaus (T-03-49), Test mit Handeingriff.
- **Commit:** c8268d1

**3. Zusätzliche Fälle über den Plan hinaus**
- Grenze atMs = next_start_ms (pendingHere true) und next_start_ms - 1 (false); Job nach yield (queued mit Fortschritt); disk_full mit Teiltext; Stück dann engine_failed; aktiver Verweis ohne Job mit und ohne Version; Ausschluss über die Intake-Art exclude.

## Offene Punkte

- **PHP nur in CI prüfbar:** StatusCommand.php und StatusCommandTest.php sind lokal weder mit `php -l` noch mit phpunit gelaufen (kein PHP, kein Docker). Beim nächsten Push `php.yml` beobachten.
- **FilesCommandTest::coverage()** hat kein byPreview; dank `?? []` bleibt der Test grün, die Zeile lautet dort `Preview: `. In der Praxis liefert ExAppService::coverage byPreview immer (sonst null).
- **PHP-Seite der Zustände** (Typprüfung von stage, partial, pendingHere, reason, limitHours; Positivliste; A11) folgt in Plan 03-16; ExAppService::excerpt verträgt die neue Antwort heute schon (fehlendes excerpt wird null, Zusatzfelder werden ignoriert).
- Während der Ausführung lief parallel Plan 03-07b im selben Arbeitsbaum; ein Lauf der vollen Suite hatte deshalb einen Ausreißer in test_read_proof_gate.py (vergleicht eine Kopie mit dem Arbeitsbaum, während fremde Dateien sich änderten). Einzeln dreimal grün, der folgende volle Lauf 1692 passed.

## Threat Flags

Keine neue Oberfläche außerhalb des Bedrohungsmodells. T-03-48 (Grund nur über aktiven Verweis, byte-gleich sonst, 90 Fälle plus Ausschluss), T-03-49 (nur Code aus geschlossener Liste und Instanz-Einstellung limitHours), T-03-50 (occ nur Codes und Zahlen, Test) umgesetzt.

## Known Stubs

Keine.

## TDD Gate Compliance

test(03-14) 6bf455b vor feat(03-14) c8268d1. Task 2 ist kein TDD-Task (PHP lokal nicht ausführbar).

## Self-Check: PASSED

- Dateien vorhanden: php/tests/Unit/StatusCommandTest.php, 03-14-SUMMARY.md.
- Commits vorhanden: 6bf455b, c8268d1, 040f27f.
