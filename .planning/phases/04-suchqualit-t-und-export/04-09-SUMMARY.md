---
phase: 04-suchqualit-t-und-export
plan: 09
subsystem: export
tags: [export, srt, vtt, txt, leck-regel, exp-01, exp-02, exp-03, srch-04, d-04-15, d-04-17, tdd]

requires:
  - phase: 04-suchqualit-t-und-export (plan 04-05)
    provides: "Store.file_language, Store.set_file_language, file_language.detect"
  - phase: 04-suchqualit-t-und-export (plan 04-08)
    provides: "build_cues, to_srt, to_vtt, to_txt; Messung 100 000 Wörter"
  - phase: 04-suchqualit-t-und-export (plan 04-10)
    provides: "ExAppService::export/exportMeta (Vertrag), EXPORT_TIMEOUT_SECONDS, EXPORT_MAX_BODY_BYTES, ExportController::withNote/noteSafe"
provides:
  - "api/export.py: POST /export (srt, vtt, txt) und POST /export/meta unter Leck-Regel"
  - "info.xml-Routen ^/export$ und ^/export/meta$ (POST, USER, bruteforce [401])"
  - "Abgleichtest PHP-Grenzen gegen Messung (test_export_budget.py)"
  - "Prüfer-Beweis des PHP-NOTE-Musters mit Spiegel-Gate (test_vtt_note_pattern.py)"
affects: [04-11 (Knöpfe der Abspielseite), 04-14, 04-15 (Push-Tor, PHPUnit in CI), 04-17]

tech-stack:
  added: []
  patterns:
    - "Snapshot unter run_locked, Spracherkennung und Rendern in asyncio.to_thread daneben"
    - "Python-Spiegel einer PHP-Regel plus Regex-Gate mit Mutations-Selbsttest"

key-files:
  created:
    - backend/src/audio_video_search_backend/api/export.py
    - backend/tests/test_api_export.py
    - backend/tests/test_export_budget.py
    - backend/tests/test_vtt_note_pattern.py
  modified:
    - backend/src/audio_video_search_backend/api/__init__.py
    - backend/appinfo/info.xml

key-decisions:
  - "EXPORT_MAX_BODY_BYTES bleibt 16 MiB (nicht 8 MiB): schnelle Rede mit Umlauten über 24 h ergibt 3,59 MB Hülle, mal Reserve 2 = 7,17 MB, nur 1,17x unter 8 MiB; 16 MiB hält Reserve 4,7x"
  - "EXPORT_TIMEOUT_SECONDS bleibt 30 s: build_cues + to_vtt für 100 000 Wörter 0,45 s, mal 8 (Pi 5) = 3,6 s"
  - "Leck-Regel 'ohne Wörter' umfasst auch Wörter ohne sichtbares Zeichen (nur Leerraum/Steuerzeichen): known false; to_vtt([]) erreicht die Route dadurch nie"
  - "Sprache: Store (gespeichert oder Zähler des laufenden Jobs) vor detect; detect nur außerhalb des Locks, set_file_language unter Lock, danach erneut gelesen (erste Bestimmung gewinnt)"

requirements-completed: [EXP-01, EXP-02, EXP-03, SRCH-04]

duration: ca. 50 min
completed: 2026-11-16
---

# Phase 4 Plan 09: Container-Export unter Leck-Regel Summary

**POST /export liefert SRT/VTT/TXT mit Sprache de/en/fr und Teilstand-Info, /export/meta denselben Zustand ohne Text; alles ohne Export antwortet byte-gleich `{"known":false}`. Die PHP-Grenzen (30 s, 16 MiB) sind per Test an die Messung gebunden, das PHP-NOTE-Muster besteht webvtt-py und ffmpeg schon vor dem Push-Tor.**

## Performance

- **Duration:** ca. 50 min
- **Completed:** 2026-11-16
- **Tasks:** 2 (Task 1 TDD RED/GREEN, Task 2 Abgleich + Prüfer-Beweis)
- **Files:** 4 neu, 2 geändert

## Accomplishments

- `api/export.py`: `ExportRequest` (fileId StrictInt > 0, format Literal srt/vtt/txt, extra ignore), `MetaRequest`; `_snapshot` unter `run_locked` liest nur media_for_file, current, effective_words, preview_view und file_language. Außerhalb des Locks: Sichtbarkeitsprüfung, `file_language.detect` (nur wenn der Store keine Sprache kennt), Rendern über `asyncio.to_thread(_render, ...)`. `partial = state in {queued, running, waiting} und chunks_done > 0`, `untilMs = next_start_ms` nur bei partial (wie /excerpt).
- Leck-Regel (T-04-24): unbekannt, ausgeschlossen, nicht aktiv, ohne current, ohne Wörter, nur unsichtbare Wörter und "keine Sprache bestimmbar" ergeben auf beiden Routen und in allen drei Formaten dieselben Bytes wie eine nie gesehene fileId (Status, Body, content-type, content-length verglichen); Positivkontrolle über die aktive Referenz.
- D-04-15: Altbestand ohne Sprache wird beim ersten Aufruf bestimmt und gespeichert, der zweite Aufruf ruft detect nicht mehr (Zähler per Monkeypatch); Wettlauf: eine zwischenzeitlich gespeicherte Sprache gewinnt über die spätere Erkennung. Nie `und` (T-04-27).
- T-04-26: Test hält build_cues an, bis ein paralleler Thread den Store-Lock nehmen konnte; ein zweiter Test prüft, dass detect ohne Lock läuft.
- 422 für format außerhalb der Liste (auch "VTT"), fileId 0/negativ/String/bool/fehlend, ohne Store-Zugriff; unsignierte Aufrufe 401.
- Logs: kein Text, keine Sprache (Test über caplog); die Route selbst loggt nichts, set_file_language loggt nur media_id.

## Abgleich der PHP-Grenzen (Merkzettel 1: 8 oder 16 MiB)

Gemessen auf dem Windows-Laptop, gleicher deterministischer Generator wie `scripts/research/phase4/measure_export.py`:

| Messung | Wert | Grenze | Reserve |
|---|---|---|---|
| build_cues + to_vtt, 100 000 Wörter (12,6 h) | 0,45 s (04-08: 0,46 s) | 30 s / Faktor 8 = 3,75 s | 8 x 0,45 = 3,6 s, rund 8,3x unter 30 s |
| JSON-Hülle SRT, 24 h NORMAL-Tempo (190 408 Wörter) | 2 096 321 B | 16 MiB | 2 x Hülle = 4,19 MB; 8 MiB hätte 2x Reserve, 16 MiB 4x |
| JSON-Hülle SRT, 24 h schnelle Rede mit ä ö ü ß (305 141 Wörter, rund 12 700/h) | 3 585 729 B | 16 MiB | 2 x Hülle = 7,17 MB; **8 MiB (8 388 608) nur 1,17x darüber**, 16 MiB 2,34x |

**Entscheidung: 16 MiB bleibt, 30 s bleibt; ExAppService.php unverändert, kein fix(04-09)-Commit.**

Begründung: Die 8 MiB aus der 04-08-Formel rechnen mit dem NORMAL-Tempo (100 000 Wörter = 12,6 h, Hülle ca. 1,1 MB je 12 h). 24 h ist die harte Obergrenze der Instanz (`MAX_DURATION_CAP_HOURS = 24`), aber dichte Rede mit langen Wörtern und Zwei-Byte-Umlauten bringt die Hülle auf 3,59 MB; mit der Formel-Reserve 2 liegen 8 MiB dann nur noch 17 % über dem Bedarf, eine noch schnellere Sprecherin oder Korrekturen mit längeren Wörtern würden den Export einer gültigen 24-h-Datei mit der 503-Seite scheitern lassen. 16 MiB kosten PHP im schlimmsten Fall einen 16-MiB-String aus dem signierten Container (weit unter dem üblichen memory_limit) und halten die Reserve auch im dichten Fall. Owner-Regel "Qualität vor Speed": ein still scheiternder Export langer Aufnahmen wiegt schwerer als 8 MiB Puffer. Der ExAppServiceTest-Fall "über 1 MiB, unter EXPORT_MAX_BODY_BYTES" gilt unverändert. Der Test liest beide Konstanten per Regex aus der PHP-Datei; außer Faktor 8 und Reserve 2 steht kein Zahlenwert doppelt.

## Leeres Transkript (Merkzettel 2: to_vtt([]))

Vom Plan geregelt, nicht selbst entschieden: must_haves "Dateien ohne Wörter antworten byte-gleich known false" und Verhalten "detect liefert None (Text leer): known false". Die Route prüft deshalb vor jeder Formatierung, dass mindestens ein Wort nach dem Ersetzen von Steuerzeichen-/Leerraum-Läufen etwas zeigt (gleiche `_CONTROL`-Definition wie Cues und TXT). Damit erreicht `to_vtt([])` (nur Kopf), `to_srt([])` und `to_txt([])` (leer) die Route nie; /export und /export/meta antworten für diese Datei gleich. Getestet als Leck-Fall `blank_words` (mit gespeicherter Sprache, damit nicht detect den Fall abfängt).

## PHP-NOTE-Muster (Nyquist, vor dem Push-Tor)

- Python-Spiegel `_with_note` / `_note_safe` von `ExportController::withNote` / `noteSafe`; T35 und T15 aus php/l10n/de|en|fr.json (Schlüssel = englischer Katalogtext), T15 mit "12:34" und "1:02:03".
- NORMAL-, FAST- und Sonder-Fixture ("Bürger", "&", "a<b", "Straße.") je Sprache ohne/mit T15 (27 Fälle): check_vtt wirft nicht, webvtt-py liest genau die Cue-Zahl mit exaktem Text und exakten Zeiten (die NOTE ist keine Caption), check_ffmpeg(".vtt", expected_cues=len(cues)) besteht (ffmpeg 8.1.1 lokal, kein Skip).
- Negativkontrolle: eine NOTE-Zeile mit "-->" lässt die Prüfer anschlagen; `_note_safe` verwirft sie.
- Spiegel-Gate: Regex auf ExportController.php prüft die Anweisungen von withNote in Reihenfolge (`strpos($vtt, "\n\n")`, `substr($vtt, $separator + 2)`, `"WEBVTT\n\nNOTE\n" . implode("\n", $lines) . "\n\n" . $rest`) und die Filterbedingung in noteSafe; vier Mutations-Selbsttests beweisen, dass das Gate anschlägt.

## Task Commits

1. **Task 1 RED:** `35f8576` test(04-09): Export-Route unter Leck-Regel
2. **Task 1 GREEN:** `544d4ed` feat(04-09): Container liefert Untertitel-Entwurf und Transkript
3. **Task 2:** `a53823d` test(04-09): Export-Grenzen passen zur Messung, PHP-NOTE-Muster besteht die Prüfer

_REFACTOR entfiel._

## Deviations from Plan

### Auto-fixed / Zusätze

**1. [Rule 2] Unsichtbare Wörter zählen als "ohne Wörter"**
- **Found during:** Task 1 (Merkzettel to_vtt([]))
- **Issue:** Wörter, deren Oberfläche nur Leerraum/Steuerzeichen trägt, ergeben keine Cues; mit gespeicherter Sprache hätte /export `"WEBVTT\n\n"` bzw. `""` ausgeliefert und /export/meta known true gemeldet.
- **Fix:** `_visible(words)` außerhalb des Locks, sonst known false (Plan-Regel "ohne Wörter"/"Text leer").
- **Commit:** 544d4ed

**2. Zusätzlicher Größenfall im Abgleichtest**
- Neben dem Planfall (24 h NORMAL) prüft der Test 24 h schnelle Rede mit Umlauten, jeweils mit Reserve 2 aus der 04-08-Formel. Grund: der 8/16-MiB-Entscheid braucht den dichtesten realistischen Fall.

**3. Mutations-Selbsttests für das Spiegel-Gate** (Muster der test_php_gates-Selbsttests), nicht ausdrücklich im Plan.

## TDD Gate Compliance

RED `35f8576` (30 von 33 Tests rot mit 404, Skelett-Modul) vor GREEN `544d4ed`. Task 2 ist kein TDD-Task.

## Known Stubs

Keine. Die Abspielseite ruft die Routen erst mit Plan 04-11 auf (geplanter Schnitt).

## Threat Flags

Keine neuen Flächen außerhalb des Threat-Models: /export und /export/meta sind T-04-24 bis T-04-28 zugeordnet und hinter AppAPIAuthMiddleware (401-Test) mit access_level USER in info.xml (Gate test_api_routes.py).

## Gates

- ruff check + format, pyright (latest) 0 Fehler, vulture grün
- volle Suite: 2322 passed, 15 skipped, 4 xfailed (195 s, kein tantivy-Flake); vorher nach Task 1: 2282 passed, 15 skipped, 4 xfailed

## Self-Check: PASSED

- Dateien vorhanden: api/export.py, test_api_export.py, test_export_budget.py, test_vtt_note_pattern.py
- Commits 35f8576 (test), 544d4ed (feat), a53823d (test) im Log; RED vor GREEN
- Akzeptanz-Greps: info.xml `^/export$` (Zeile 94) und `^/export/meta$` (Zeile 101); `export.router` in api/__init__.py; `to_thread` dreimal in export.py (Sichtbarkeit, detect, Rendern)
- ExAppService.php unverändert, daher kein fix(04-09)-Commit; test_php_gates.py grün
