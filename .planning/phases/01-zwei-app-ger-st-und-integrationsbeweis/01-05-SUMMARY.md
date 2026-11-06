---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 05
subsystem: backend
tags: [tantivy, index, appapi, gateway, sha256, search, excerpt, sample]
requires:
  - "01-02 (Store: media/media_key/file_ref/current, publish_version, effective_words, remove_sample, index_outbox)"
  - "01-03 (Container-Vertrag, Content-Gateway GET /ocs/v2.php/apps/audio_video_search/files/{fileId})"
  - "01-12 (Hinweis: Escapes beim Kopieren aus Findling prüfen)"
provides:
  - "index/: SearchIndex (publish, retire, search, first_match_ms, reconcile, rebuild_from_store, open_generation), Segment, IndexHit, segments_from_words"
  - "index/open.py: einziger Index-Öffner, registriert de/en/fr; Marken index_schema_version, index_analyzer, index_tantivy"
  - "nc.fetch_file_sha256: gestreamter Gateway-GET mit sha256 je Block (einziger httpx-Ort)"
  - "Container-Routen POST /search, /excerpt, /sample, /sample/remove nach Vertrag 01-03"
  - "Store: meta_value, set_meta, index_generation, bump_index_generation, current_media_ids"
  - "config.storage_root(): APP_PERSISTENT_STORAGE oder eigenes Temp-Verzeichnis"
affects: [01-06, 01-07, 01-08, 01-11]
tech-stack:
  added: ["tantivy 0.26.2 (Laufzeit)", "httpx 0.28.1 (von dev nach Laufzeit)"]
  patterns:
    - "Index abgeleitet: SQLite-Commit mit Outbox, dann add+commit, dann delete anderer Revisionen+commit, dann mark_indexed"
    - "Suchfilter: index_rev == current oder current-1, je media_id höchste Revision"
    - "Generationsverzeichnis index/gen-N; Markenabweichung baut aus SQLite neu"
    - "Eine Sperre (api.Services.lock) um alle Store- und Indexarbeit, ausgeführt per asyncio.to_thread"
key-files:
  created:
    - backend/src/audio_video_search_backend/index/__init__.py
    - backend/src/audio_video_search_backend/index/analyzer.py
    - backend/src/audio_video_search_backend/index/wordlist.py
    - backend/src/audio_video_search_backend/index/schema.py
    - backend/src/audio_video_search_backend/index/open.py
    - backend/src/audio_video_search_backend/index/publish.py
    - backend/src/audio_video_search_backend/api/__init__.py
    - backend/src/audio_video_search_backend/api/search.py
    - backend/src/audio_video_search_backend/api/excerpt.py
    - backend/src/audio_video_search_backend/api/sample.py
    - backend/tests/test_index_open.py
    - backend/tests/test_index_publish.py
    - backend/tests/test_api_routes.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
    - backend/appinfo/info.xml
    - backend/src/audio_video_search_backend/nc.py
    - backend/src/audio_video_search_backend/main.py
    - backend/src/audio_video_search_backend/config.py
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/tests/conftest.py
    - backend/tests/test_boundary.py
    - backend/tests/test_config.py
key-decisions:
  - "Trefferzeit = Beginn des ersten Worts im Segment, das mit dem Begriff einen Token in einer der drei Ketten teilt (sonst Segmentbeginn); 'Audiosuche' liegt bei atMs + 6*400"
  - "Französische Kette mit eigenem gefaltetem Stoppwort-Zusatz (15 Einträge), gegen tantivy 0.26.2 gemessen; Findling hatte für Französisch keinen"
  - "Analyzer-Marke = ANALYZER_VERSION:Digest der Wortliste; fehlt /usr/share/dict/ngerman, läuft Deutsch ohne Kompositazerlegung weiter"
  - "Index-Marken in meta unter eigenen Schlüsseln (index_schema_version, index_analyzer, index_tantivy), damit store.schema_version unberührt bleibt; set_meta verweigert schema_version und index_generation"
  - "Suche mit conjunction_by_default=True wie Findling (alle Wörter müssen im Segment stehen)"
  - "Gateway-Header-Nutzer leer (App-Kontext wie Findling), Nutzer nur als userId-Parameter; Redirects werden nicht verfolgt"
requirements-completed: []  # PLAY-01: Container-Hälfte steht; der Klick-Beweis auf die Zeitstelle folgt mit Plan 06 und CI. TRANS-06 war schon erledigt.
metrics:
  duration: "ca. 60 min"
  completed: 2026-11-06
  tasks: 2
  files: 23
---

# Phase 1 Plan 05: Container-Hälfte des Testtreffers Summary

Tantivy 0.26.2 als aus SQLite abgeleiteter Segmentindex mit Findling-Ketten für Deutsch (Snowball plus Kompositazerlegung), Englisch und Französisch, dazu die Container-Routen `/sample` (Saat über das PHP-Gateway mit sha256 im Strom), `/search` (index_rev-Filter, Zeit des passenden Worts), `/excerpt` (effektiver Text mit Korrekturen) und `/sample/remove`.

## Ergebnis

- **Task 1:** `index/open.py` öffnet als einziger Ort einen Index und registriert `de`, `en`, `fr`. Schema mit `media_id`, `index_rev`, `seg_idx`, `start_ms` als unsigned fast fields, `body_de` gespeichert, `body_en`/`body_fr` nicht. `SearchIndex.publish` ist idempotent je `(media_id, index_rev)`, `retire` löscht per Term-Query (I64-Falle aus Findling), `reconcile` arbeitet die Outbox ab, löscht Waisen und veraltete Revisionen und trägt fehlende current-Versionen nach, `rebuild_from_store` baut aus `effective_words` neu. `open_generation` vergleicht die Marken in `meta` und baut bei Abweichung oder fehlendem Verzeichnis eine neue Generation aus SQLite.
- **Task 2:** `nc.fetch_file_sha256` streamt über httpx mit den AppAPI-Headern, hasht je Block, kennt `gateway_denied` (403/404) und `gateway_failed` (sonstiger Status, Netzfehler, zu kurze Antwort, mehr als 8 GiB). Routen nach dem Vertrag aus 01-03 mit strikten Pydantic-Grenzen (`StrictInt`, fileId > 0, atMs 0 bis 86 400 000, limit 1 bis 50, userId 1 bis 64). Lifespan öffnet `state.db` und `index/` unter `APP_PERSISTENT_STORAGE`, ruft `reconcile` im Hintergrund und schließt beides beim Stopp. Routenblock in `backend/appinfo/info.xml` in der Form `^/<name>$`.

Gates in `backend/`: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture leer, pytest 303 passed (Abdeckung 95,6 %). Positivkontrolle des Log-Tests: ein absichtlich geloggter Suchbegriff macht ihn rot. uv.lock: tantivy-Wheels amd64 `0c083f1c...6c75b` und arm64 `535aec46...3660` stimmen mit der Owner-Freigabe überein.

## Task Commits

1. **Task 1 RED:** `8e72236` (test) Index-Öffner, Revisionen, Abgleich, Neuaufbau
2. **Task 1 GREEN:** `9320b57` (feat) Tantivy-Index, Store-Metamethoden, Abhängigkeiten
3. **Task 2 RED:** `293de2b` (test) Routen und Gateway-Strom
4. **Task 2 GREEN:** `14baac0` (feat) Routen, nc.fetch_file_sha256, Lifespan, info.xml

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Trefferzeit und Wortposition im Plan**
- **Issue:** Der Plan erwartet `startMs = atMs + 7*400`. "Audiosuche" ist das siebte Wort, liegt also sechs Schritte nach `atMs`; außerdem lieferte ein reiner Segmentindex nur den Segmentbeginn (`atMs`).
- **Fix:** `SearchIndex.first_match_ms` sucht im Segment das erste Wort, das mit dem Begriff einen Token teilt; Test erwartet `atMs + 6*400`.
- **Commit:** 14baac0

**2. [Rule 3 - Blocking] Französische Kette ohne Stoppwort-Zusatz**
- **Issue:** Findlings `snowball_analyzer("french")` verweigert den Bau, weil es keinen gefalteten Zusatz gibt.
- **Fix:** Zusatz aus 15 Einträgen gegen tantivy 0.26.2 gemessen (nur Einträge, die `stopword("french")` mit Akzent entfernt und ohne Akzent nicht), Test prüft jeden Eintrag.
- **Commit:** 9320b57

**3. [Rule 2 - Missing] Store-Methoden für Marken und Neuaufbau**
- **Issue:** `meta.index_generation` hatte keine Lese-/Schreibmethoden, und `rebuild_from_store` braucht die Liste aller current-Versionen.
- **Fix:** `meta_value`, `set_meta` (verweigert die eigenen Schlüssel), `index_generation`, `bump_index_generation`, `current_media_ids` in `store/repo.py` (nicht in files_modified, laut Übergabe aus 01-02 aber in diesem Plan fällig).
- **Commit:** 9320b57

**4. [Rule 1 - Bug] Gleichzeitige Transaktionen auf einer SQLite-Verbindung**
- **Issue:** Routen in Worker-Threads und der Start-Abgleich hätten auf derselben Verbindung `BEGIN IMMEDIATE` ineinander geschachtelt.
- **Fix:** `api.Services.lock` und `run_locked`; der Hintergrund-Abgleich nimmt dieselbe Sperre.
- **Commit:** 14baac0

**5. [Rule 2 - Missing] Testumgebung schrieb in das System-Temp**
- **Issue:** Mit dem neuen Lifespan hätte jeder Test mit `TestClient` `state.db` im gemeinsamen Temp-Verzeichnis angelegt.
- **Fix:** `conftest.appapi_environment` setzt `APP_PERSISTENT_STORAGE` auf `tmp_path`.
- **Commit:** 293de2b

Weitere Ergänzungen: `test_boundary` verlangt jetzt beide Clients (nc_py_api, httpx) in `nc.py` als Positivkontrolle; `config.storage_root()` mit Test.

## Deferred Issues

In `deferred-items.md` eingetragen: `wngerman` fehlt im Dockerfile (ohne Liste keine Kompositazerlegung, Index baut nach dem Nachrüsten einmal neu), Schlüsselliste von `reconcile` per Aggregation über alle Dokumente, eine Sperre um Store und Index (langer Neuaufbau beim Start blockiert die Suche).

## Known Stubs

Keine. Der Saat-Text ist absichtlich fest (Testtreffer des Gerüsts).

## Threat Flags

Keine neue Fläche außerhalb des Bedrohungsmodells: Gateway-Strom (T-01-23: 8 GiB, Timeouts, kein Puffern, keine Redirects), Eingabegrenzen (T-01-20), Logs nur mit IDs und Codes (T-01-21, caplog-Test mit Positivkontrolle), index_rev-Filter und Abgleich (T-01-24), Routenblock (T-01-19).

## Next Phase Readiness

- Plan 06 (Abspielansicht) nutzt `/excerpt` mit `fileId` und `atMs`.
- Plan 08 ergänzt `/status` um `sampleCount` usw.; `Store.count_current_at_level(Level.SAMPLE)` ist da.
- Für den Container-Build: `wngerman` nachrüsten (siehe Deferred).

## Self-Check: PASSED

- Dateien vorhanden: alle unter key-files.created
- Commits vorhanden: 8e72236, 9320b57, 293de2b, 14baac0
