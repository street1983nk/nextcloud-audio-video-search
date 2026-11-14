---
phase: 03-vorschau-transkripte-in-der-suche
plan: 07
subsystem: modelle
tags: [downloader, sha256, allowlist, air-gap, appapi-init]
requires:
  - "03-01: freigegebener Fehlertext MODELS_FAILED"
provides:
  - "models/catalog.py: ModelFile, PARAKEET_FILES, SILERO_FILES, MODELS, ASSET_HOSTS, MODEL_SHA256, model_bytes"
  - "models/procure.py: procure(), model_dir(), verify_file(), models_ready()/mark_ready(), PROCURE_OUTCOMES, Kommandozeile"
  - "nc.fetch_model_asset, nc.report_init_status, MODEL_FETCH_OUTCOMES"
  - "main.py: eigene POST /init mit prepare_models, verify_models beim Start"
affects: [03-05, 03-10, 03-11]
tech-stack:
  added: []
  patterns:
    - "Findling weights.py kopiert: .part, Hash im Strom, fsync, os.replace, Ergebnis als Wert"
    - "Findling fetch_release_asset kopiert: Redirects von Hand, Allowlist je Stufe"
key-files:
  created:
    - backend/src/audio_video_search_backend/models/__init__.py
    - backend/src/audio_video_search_backend/models/catalog.py
    - backend/src/audio_video_search_backend/models/procure.py
    - backend/tests/test_models.py
    - backend/tests/test_model_download.py
  modified:
    - backend/src/audio_video_search_backend/nc.py
    - backend/src/audio_video_search_backend/main.py
    - backend/tests/test_main.py
decisions:
  - "Eigene /init-Route mit set_handlers(default_init=False): nc_py_api 0.30.3 bietet keinen Init-Rückruf, nur den synchronen fetch_models_task"
  - "Eine vorhandene, aber falsche Datei (Admin-Ablage) ergibt WRONG_DIGEST und wird nicht überschrieben"
  - "too_large beim Laden zählt als WRONG_DIGEST, foreign_host/http_error/network als UNAVAILABLE"
  - "Nur-Prüfen-Modus ist procure(..., fetch=None)"
metrics:
  duration: "ca. 75 min"
  completed: 2026-11-14
  tasks: 2
  files: 8
---

# Phase 3 Plan 07: Modell-Downloader und /init Summary

Parakeet-TDT-0.6B-v3 int8 (Commit 2bda32ec) und Silero VAD werden nur mit festem sha256 und fester Länge angenommen, geladen über eine eigene Redirect-Verfolgung mit Host-Allowlist aus echten Redirects, gleich geprüft bei Admin-Ablage; POST /init lädt im Hintergrund mit Fortschritt 0 bis 100 und meldet bei Fehlschlag den freigegebenen Text MODELS_FAILED.

## Beobachtete Weiterleitungen (14.11.2026, `curl -sSI --max-redirs 0`, je Stufe einzeln)

| Datei | Stufe 1 (Status, Location-Host) | Stufe 2 (Status) | Länge |
|-------|----------------------------------|------------------|-------|
| encoder.int8.onnx | huggingface.co: `HTTP/1.1 302 Found`, Location-Host `us.aws.cdn.hf.co` (Pfad `/xet-bridge-us/...`), `X-Linked-ETag` = sha256 aus RESEARCH | us.aws.cdn.hf.co: `HTTP/1.1 200 OK` | `X-Linked-Size: 652184281`, `content-length: 652184281` |
| decoder.int8.onnx | huggingface.co: `HTTP/1.1 302 Found`, Location-Host `us.aws.cdn.hf.co`, `X-Linked-ETag` = sha256 aus RESEARCH | us.aws.cdn.hf.co: `HTTP/1.1 200 OK` | 11845275 |
| joiner.int8.onnx | huggingface.co: `HTTP/1.1 302 Found`, Location-Host `us.aws.cdn.hf.co`, `X-Linked-ETag` = sha256 aus RESEARCH | us.aws.cdn.hf.co: `HTTP/1.1 200 OK` | 6355277 |
| tokens.txt | huggingface.co: `HTTP/1.1 307 Temporary Redirect`, Location relativ `/api/resolve-cache/models/...` (Host bleibt huggingface.co) | huggingface.co: `HTTP/1.1 200 OK` | 93939 |
| silero_vad.onnx | github.com: `HTTP/1.1 302 Found`, Location-Host `release-assets.githubusercontent.com` | release-assets.githubusercontent.com: `HTTP/1.1 200 OK` | 643854 |

`ASSET_HOSTS` = {huggingface.co, us.aws.cdn.hf.co, github.com, release-assets.githubusercontent.com}, kein Muster.

Gegenprobe der Digests unabhängig vom Spike: die drei LFS-Dateien über `X-Linked-ETag` (HF nennt den sha256), tokens.txt (94 KB) und silero_vad.onnx (644 KB) einmal geladen und mit `sha256sum` gehasht: beide stimmen mit 03-RESEARCH.md überein; Dateien danach aus dem Scratch-Ordner gelöscht. Der 652-MB-Encoder wurde nicht geladen.

`MODEL_SHA256` = `3a78ea81526430808b60248acbaa45a3361ad99bdd0b05b7da6ad6548a4dd339` (sha256 über die fünf sortierten, mit Komma verbundenen sha256); der Test rechnet ihn aus eigenen Literalen nach.

## Task 1: Katalog und Downloader (Commit 19916f9)

- `catalog.py`: `ModelFile(name, url, sha256, size)`, vier Parakeet-Dateien mit Commit-URL, Silero aus Release `asr-models`, `MODELS`, `ASSET_HOSTS`, `MODEL_SHA256`, `model_bytes`.
- `nc.fetch_model_asset(url, dest, *, expected_size, allowed_hosts, client=None, on_chunk=None) -> str`: eigener Client (`follow_redirects=False`, User-Agent `audio_video_search_backend/<APP_VERSION>`, `Accept-Encoding: identity`, keine AppAPI-Header), höchstens 5 Stufen, jede Stufe https und Host in der Allowlist, Cookie-Jar vor jeder Stufe geleert, Abbruch über `expected_size` (Header und Strom), kurzer Body = `network`; jede Nicht-Erfolgs-Antwort löscht `dest`.
- `procure.py`: `model_dir = root/models/<name>/<MODEL_SHA256>`; je Datei Urteil (Länge, dann sha256, Cache in `<datei>.verified.json` nach Größe und mtime_ns); fehlt sie: Platzprüfung (Größe + `nc.DISK_RESERVE_BYTES`), `.part`, sha256 im Strom über `on_chunk`, fsync, `os.replace`, sonst `.part` weg. Kommandozeile `python -m audio_video_search_backend.models.procure --root PFAD [--verify-only]`, Ausgabe nur `<modell> <ergebnis>`, Exit 0 nur bei present/procured für beide.

## Task 2: /init mit Fortschritt (Commit 13eb778)

- `set_handlers(app, enabled_handler, default_init=False)` und eigene Route `POST /init` (`init_handler`), signiert wie alle Routen außer /heartbeat; ein zweites /init während eines laufenden startet nichts Neues.
- `prepare_models(root)`: Silero, dann Parakeet; Fortschritt nach Bytes beider Modelle auf 0 bis 99, streng steigend ohne Wiederholung, 100 erst nach `procure.mark_ready()`. Fehlschlag: Log `{"model", "outcome"}`, `report_init_status(<letzter Wert>, MODELS_FAILED)`, `models_ready()` bleibt False.
- `nc.report_init_status(progress, error)`: einzige Stelle mit `set_init_status` (Async-API), wirft nie.
- Lifespan startet `verify_models(storage_root())` mit `fetch=None`: nach Neustart ist `models_ready()` richtig, ohne Anfrage.
- `MODELS_FAILED` wörtlich aus 03-01-SUMMARY.md: "Audio & Video Search could not download its speech models. Details are in the log of the ExApp."

## Tests und Gates

- Volle Suite: **1424 passed** (nach Task 1: 1416, Task 2: +8 netto); ruff check, ruff format --check, pyright (latest, 0 Fehler), vulture grün.
- test_models.py 24, test_model_download.py 17, test_main.py 25 Fälle.
- Positivkontrollen: Header-Prüfer findet absichtlich gesetzte `Authorization` und `Cookie`; vulture meldet einen absichtlich eingefügten ungenutzten Import; pyright meldete einen echten Typfehler (verify_models gab bool an start_background), danach behoben; Strich-/Emoji-Prüfung zählt 2 in einer Probe mit U+2013/U+2014.
- Mutationsproben (jede gefangen): Cookie-Jar nicht geleert, Host-Prüfung weg, Schema-Prüfung weg, Größengrenze weg, `.part`-Aufräumen weg, Digest-Prüfung weg, Urteils-Cache immer wahr, Platzreserve weg, Admin-Hash weg, mark_ready im Startcheck weg, default_init wieder an, MODELS_FAILED nicht gemeldet, Startcheck mit Download. Eine Mutation überlebte (`min(99, ...)` beim Fortschritt), weil sie mathematisch redundant war: `min` entfernt, Kommentar ergänzt.
- Hinweis: die Mutation "Startcheck mit Download" hat im Test einmal echt silero_vad.onnx (644 KB, öffentlich) in ein tmp-Verzeichnis geladen; der unveränderte Code tut das nicht (Test prüft `fetch=None`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Kein Init-Rückruf in nc_py_api 0.30.3**
- `set_handlers` kennt nur `default_init` und `models_to_fetch`; der Standard ruft den synchronen `fetch_models_task` (prüft nur gegen ETag). Lösung: `default_init=False` und eigene `POST /init` in main.py. Der alte Test `test_init_acknowledges_at_once` (patchte `fetch_models_task`) ist durch Tests der eigenen Route ersetzt, plus Kontrolle, dass `fetch_models_task` nie erreicht wird.

**2. [Rule 3] `on_chunk` als zusätzlicher Parameter von `fetch_model_asset`**
- Der Plan verlangt sha256 im Strom in procure, aber HTTP nur in nc.py. Der Rückruf je Block liefert Hash und Fortschritt, ohne dass procure einen Client sieht.

**3. [Rule 3] `config.persistent_storage()` gibt es nicht**
- Verwendet wird `config.storage_root()` (APP_PERSISTENT_STORAGE).

**4. Abbildung der Codes (Entscheid im Rahmen des Plans)**
- `too_large` gilt als WRONG_DIGEST (Quelle liefert etwas anderes als erfasst), `foreign_host`/`http_error`/`network` als UNAVAILABLE; ein Schreibfehler ENOSPC als NO_ROOM. Eine vorhandene falsche Datei wird gemeldet und nicht überschrieben, damit der Admin den Fehler sieht.

## Offene Punkte

- **CDN-Host regional (Owner-Entscheid nötig):** Hugging Face hat von hier auf `us.aws.cdn.hf.co` (`xet-bridge-us`) weitergeleitet. Instanzen in anderen Regionen könnten einen anderen Host bekommen (etwa einen `eu.`-Host); dann endet der Download mit `foreign_host` und /init mit MODELS_FAILED. Laut Plan nur beobachtete Hosts, kein Muster. Optionen: weitere Hosts nach Beobachtung aus anderer Region (z. B. AWS-Messung) ergänzen, oder Parakeet ebenfalls als GitHub-Release-Asset spiegeln.
- **Dockerfile setzt HF_HUB_OFFLINE=1 und HF_HUB_DISABLE_TELEMETRY=1 nicht** (geprüft: `backend/Dockerfile` ENV-Zeilen 14 und 138). Laut Plan nicht hier geändert; Folgearbeit für Plan 03-05 bzw. dessen Nachfolger.
- Der echte End-to-End-Download des 652-MB-Encoders über `fetch_model_asset` lief nicht (Plan verlangt es nicht); belegt sind Hosts, Längen und Digests per Header und die zwei kleinen Dateien per Hash.
- Ein eigener, hängender Hilfsprozess (python, gestartet 13:58:52, Heredoc-Fehler im Werkzeugaufruf, keine Repo-Änderung) konnte nicht beendet werden, weil das Beenden abgelehnt wurde.

## Known Stubs

Keine. `models_ready()` hat noch keinen Leser; den bekommt die Vorschau in einem späteren Plan (03-10/03-11).

## Threat Flags

Keine neue Oberfläche außerhalb des Bedrohungsmodells; T-03-22 bis T-03-25 umgesetzt und getestet. Die einzige neue ausgehende Verbindung ist `fetch_model_asset` (T-03-23/24).

## Self-Check: PASSED

- FOUND: backend/src/audio_video_search_backend/models/catalog.py, procure.py, __init__.py
- FOUND: backend/tests/test_models.py, backend/tests/test_model_download.py
- FOUND: Commit 19916f9, Commit 13eb778
