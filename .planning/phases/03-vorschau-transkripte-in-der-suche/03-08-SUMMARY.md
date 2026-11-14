---
phase: 03-vorschau-transkripte-in-der-suche
plan: 08
subsystem: api
tags: [search, unified-search, paginierung, stufen-folge, offset, stage, tdd]
requires: []
provides:
  - "api/search.py: tiered(), admissible() (alle Segmente der höchsten zulässigen Revision je Medium), stage_of(), SearchRequest mit offset (0 bis MAX_OFFSET 1200)"
  - "Konstanten MAX_CANDIDATES = 2000, PER_TIER = 3, MAX_OFFSET = 1200"
  - "POST /search antwortet {appVersion, hits[{fileId, startMs, excerpt, sample, stage}], nextOffset, hasMore}"
affects: [03-12]
tech-stack:
  added: []
  patterns:
    - "Präfix-stabile Folge: feste Kandidatenzahl, unabhängig von limit und offset; Schnitt [offset, offset + limit)"
    - "Test-Orakel ohne tiered: handgeschriebene Folgen plus Invarianten über 50 Zufallslagen (fester Seed), dazu Permutations-Unabhängigkeit"
key-files:
  created:
    - backend/tests/test_search_tiers.py
  modified:
    - backend/src/audio_video_search_backend/api/search.py
    - backend/tests/test_restore_proof.py
decisions:
  - "Eine Datei, die zwei Inhalte nennen (aktiver Verweis und sichtbare Probe anderer Bytes), bekommt nur die Stellen des Inhalts, den Store.media_for_file nennt (dieselbe Quelle wie der Ausschnitt der Abspielseite); nie eine Mischung"
  - "nextOffset = offset + Anzahl Treffer, auch bei leerem Begriff (dann gleich offset), hasMore dann false"
  - "Words je Medium werden nur einmal geladen; Zeit der Stelle wie bisher (erstes passendes Wort, sonst Segmentanfang)"
metrics:
  duration: "ca. 40 min"
  completed: 2026-11-14
  tasks: 1
  files: 3
---

# Phase 3 Plan 08: Stufen-Folge mit Offset und Stufe je Treffer Summary

POST /search liefert jetzt je Stelle (Segment der höchsten zulässigen Revision) einen Treffer in einer festen, präfix-stabilen Stufen-Folge: Dateien nach bestem Score (Gleichstand fileId), je Datei Stufen zu 3 Stellen (Score, Gleichstand Zeit), erst Stufe 1 aller Dateien, dann Stufe 2. offset und limit schneiden die Folge, die Antwort trägt nextOffset, hasMore und stage je Treffer.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 RED | ded6f7c | test(03-08): Stufen-Folge, Offset und Stufe als Fälle mit unabhängigem Orakel |
| 1 GREEN | ea60b6b | feat(03-08): Stellen je Datei in fester Stufen-Folge |

Beide nur lokal, Autor und Committer street1983nk <k.cherif@outlook.de>, nicht gepusht.

## Belege

- RED: test_search_tiers.py scheiterte beim Import (stage_of fehlte).
- GREEN: test_search_tiers.py 80 Fälle grün; Zielsatz (tiers, api_routes, excerpt_states) 180 grün; volle Suite 1375 grün.
- Gates: ruff check, ruff format --check (94 Dateien), pyright latest 0 Fehler, vulture still.
- Über HTTP mit echter state.db und echtem Index (Inhalt mit 8 Stellen, Inhalt mit 1 stärkeren Stelle): handgeschriebene Folge, limit 5/10/15 präfixgleich, Seiten [0,5), [5,10), [10,15) ohne Dublette und Lücke, hasMore an der Kante (offset 3 true, offset 4 false), Einzeldatei füllt limit 5 auf (D-03-15), stage preview/final/sample, alte Revision mischt sich nicht mit der aktuellen, Kandidatenzahl immer 2000, offset -1/1201/True/"5" und limit 0/51 ergeben 422, offset 1200 ergibt 200.
- Positivkontrolle der Tests durch Mutationen (je einzeln, danach zurückgesetzt): PER_TIER 2 (42 rot), Kandidaten aus limit (1 rot), alte Revisionsregel (2 rot), stage fest preview (2 rot), hasMore mit >= (1 rot), Dateireihenfolge nur nach fileId (35 rot), andere Wahl bei zwei Inhalten je Datei (1 rot).
- Log: nur hits, limit, offset; der bestehende Test, dass kein Log den Begriff trägt, bleibt grün.
- Leck-Regel D-02-15c unverändert: Dateien kommen weiter nur aus store.file_ids_for_media (aktive Verweise, sichtbare Proben); test_excerpt_states.py und test_sample_real_transcript.py grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] test_restore_proof.py rief _search mit alter Signatur**
- **Found during:** Task 1 GREEN (pyright und 24 rote Fälle)
- **Issue:** Der Helfer `found()` rief `search_api._search(services, term, limit)` direkt; die neue Signatur ist `(opened, term, offset, limit)` und gibt `(hits, has_more)` zurück.
- **Fix:** Aufruf auf `_search(..., "Haushalt", 0, 50)` mit Entpacken umgestellt; Prüfinhalt unverändert.
- **Files modified:** backend/tests/test_restore_proof.py
- **Commit:** ea60b6b

**2. [Rule 2 - Korrektheit] Datei unter zwei Inhalten**
- **Found during:** Task 1 GREEN
- **Issue:** Der Plan sagt "je file_id dieselben Stellen" der Medien aus file_ids_for_media; eine Datei kann aber von zwei Inhalten genannt werden (aktiver Verweis plus sichtbare Probe anderer Bytes). Ohne Regel wären zwei Stände in einer Datei gemischt worden.
- **Fix:** Bei mehr als einem Inhalt gilt der von `Store.media_for_file` (dieselbe Wahl wie der Ausschnitt). Eigener Test mit Positivkontrolle, dass beide Inhalte die Datei nennen.
- **Files modified:** backend/src/audio_video_search_backend/api/search.py, backend/tests/test_search_tiers.py
- **Commit:** ded6f7c, ea60b6b

Sonst wie geplant. test_api_routes.py musste nicht angepasst werden: die bestehenden Prüfungen lesen nur einzelne Felder und bleiben mit der neuen Antwortform grün (einschließlich des alten admissible-Falls).

## Known Stubs

Keine.

## Offene Punkte

- PHP-Seite (Plan 03-12): ExAppService::search muss offset senden, nextOffset/hasMore und stage prüfen; bis dahin ignoriert PHP die neuen Felder.
- RESEARCH Open Question 1 (Auffüllen bei nur einer Datei) ist durch D-03-15 entschieden und so umgesetzt.

## Self-Check: PASSED

- backend/tests/test_search_tiers.py vorhanden, backend/src/audio_video_search_backend/api/search.py geändert.
- Commits ded6f7c und ea60b6b im Log.
