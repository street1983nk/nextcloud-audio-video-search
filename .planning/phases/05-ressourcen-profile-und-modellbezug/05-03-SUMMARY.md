---
phase: 05-ressourcen-profile-und-modellbezug
plan: 03
subsystem: scripts/models
tags: [RES-06, whisper, sha256, teile, release-assets]
requires: []
provides:
  - "scripts/models/split_whisper.py: download(client, url, dest, size, sha256), split_file(path, part_size, out_dir, prefix), run(work, out, *, models, part_size, skip_download), MODELS, PART_SIZE = 1073741824"
  - "scripts/models/whisper-parts-2026-11.json: Identität aller 13 Whisper-Assets (tag whisper-2026-11), je model.bin die Teile in Reihenfolge und der Gesamtwert"
affects: [05-08, 05-10]
tech-stack:
  added: []
  patterns: ["Weiterleitungen von Hand folgen, jeder Sprung vor der Anfrage gegen die Host-Regel geprüft", "erst alle ganzen Dateien prüfen, dann Teile schreiben"]
key-files:
  created:
    - scripts/models/split_whisper.py
    - scripts/models/whisper-parts-2026-11.json
    - backend/tests/test_whisper_parts_script.py
  modified: []
decisions:
  - "Host-Regel des Skripts: nur https, nur huggingface.co oder Hosts unter .hf.co (gemessen us.aws.cdn.hf.co); gilt nur für diesen Entwicklerschritt, die App-Allowlist bleibt ohne Hugging Face (D-03-21)"
  - "Ablage im Arbeitsordner: originals/<modell>/ für die ganzen Dateien, assets/ für die 13 Release-Assets"
  - "Ein begonnener Download (.part) wird per Range fortgesetzt und dabei neu gehasht; eine vorhandene Datei mit falschem Wert wird nie ersetzt, sondern ist ein Fehler"
  - "JSON mit sortierten Schlüsseln und LF auf jeder Plattform (write_text mit newline), sonst hätte Windows CRLF geschrieben"
metrics:
  duration: "ca. 60 min"
  completed: 2026-11-18
  tasks: 2
  files: 3
---

# Phase 5 Plan 03: Whisper-Teile mit sha256 Summary

Beide Whisper-model.bin (turbo, large-v3) sind am festen Hugging-Face-Commit geladen, gegen den Gesamt-sha256 geprüft und in Teile zu genau 1 GiB zerlegt; die Identität aller 13 Assets steht als gemessenes JSON im Repo, die Dateien selbst liegen außerhalb des Repos unter `C:\Users\Student\av-whisper-assets`.

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | Teil-Skript mit Tests (RED, GREEN) | 5ed5e2a (RED), 2f779d0 (GREEN) | scripts/models/split_whisper.py, backend/tests/test_whisper_parts_script.py |
| 2 | Echter Lauf und JSON | 23b8620 | scripts/models/whisper-parts-2026-11.json, backend/tests/test_whisper_parts_script.py |

## Ergebnis des echten Laufs (18.11.2026)

Quelle: nur `huggingface.co` und die Weiterleitung auf `us.aws.cdn.hf.co` (model.bin); die kleinen Dateien kamen ohne fremden Host. Alle zehn Dateien trafen Länge und sha256 aus dem Plan.

| Asset | Bytes | sha256 |
|---|---|---|
| whisper-large-v3-turbo.model.bin (ganz) | 1 617 884 929 | e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da |
| whisper-large-v3-turbo.model.bin.001 | 1 073 741 824 | 229405133905b758bbdef3a8104ab31939bf8994125d1547ed950799af20d555 |
| whisper-large-v3-turbo.model.bin.002 | 544 143 105 | bfa3916ab9fc48c3af1d994331aadc6df5cfe40776b0d33b4081f5503203dcb4 |
| whisper-large-v3.model.bin (ganz) | 3 087 284 237 | 69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1 |
| whisper-large-v3.model.bin.001 | 1 073 741 824 | ffb5a6cd5d53b9188fc30dfc8c9e59d596fdbc2b2fb61368c0564b407be46591 |
| whisper-large-v3.model.bin.002 | 1 073 741 824 | c14e94cdd7837754a73f63b3b197925addda5fd0f39cb92bcdfb9e146a0e71d5 |
| whisper-large-v3.model.bin.003 | 939 800 589 | 4daea110817f4be7bfe5c0cfb82d01f12adc2684ab3bd548bd43634f658d5380 |

Die acht kleinen Dateien (config, preprocessor_config, tokenizer, vocabulary je Modell) tragen die Werte aus dem Plan, siehe JSON.

Gegenprobe mit einem anderen Werkzeug (`sha256sum`, nicht das Skript): die verketteten Teile ergeben für beide Modelle den Gesamtwert, jeder Teilwert stimmt mit dem JSON überein.

Ablage für Plan 05-10 (außerhalb des Repos, 8,8 GB):

- Assets: `C:\Users\Student\av-whisper-assets\assets`
- Originale: `C:\Users\Student\av-whisper-assets\originals`

Hinweis (Korrektur 18.11.2026): Die Dateien lagen zuerst im Sitzungs-Scratchpad unter Temp und liegen jetzt dauerhaft unter `C:\Users\Student\av-whisper-assets`. Geht der Ordner vor Plan 05-10 verloren, erzeugt derselbe Befehl die Assets neu; die Werte im JSON sind dann die Prüfung.

## Verification

- `uv run pytest -q tests/test_whisper_parts_script.py`: 46 passed (40 Skript, 6 über das eingecheckte JSON).
- `find scripts/models -size +1M`: 0 Treffer; `git ls-files | grep -c model.bin`: 0; `grep huggingface.co backend/src`: 0.
- Voller Lauf: 2516 passed, 18 skipped, 4 xfailed; ruff check und format (auch ../scripts), pyright basic (latest), vulture grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] JSON bekam unter Windows CRLF**
- **Found during:** Task 1 (GREEN), Test `test_json_is_stable`
- **Issue:** `write_text` übersetzt unter Windows `\n` in `\r\n`; das versionierte JSON wäre je Plattform verschieden.
- **Fix:** `newline="\n"` beim Schreiben.
- **Commit:** 2f779d0

**2. [Rule 1 - Bug] Test-Antworten waren schon gelesen**
- **Found during:** Task 1 (GREEN)
- **Issue:** `httpx.Response(content=...)` ist bereits gelesen, `iter_raw` scheitert; ein echter Server liefert einen ungelesenen Strom.
- **Fix:** Testhilfe `body()` mit `httpx.ByteStream`. Kein Test wurde gelockert.
- **Commit:** 2f779d0

### Ergänzungen über den Plan hinaus (Rule 2, Sicherheit)

- Weiterleitungen werden von Hand verfolgt (höchstens fünf), jeder Sprung wird vor der Anfrage geprüft; ein fremder Host wird nie angefragt (Test).
- Ein zu langer Körper wird abgeschnitten und verworfen, ein zu kurzer ist ein Fehler; die Zieldatei entsteht nur bei Treffer von Länge und sha256.
- Fortsetzen per Range mit Prüfung des Offsets in `Content-Range`.

## TDD Gate Compliance

RED (5ed5e2a, 39 Fehler, weil das Skript fehlte) vor GREEN (2f779d0, 40 passed).

## Threat Flags

Keine neue Fläche außerhalb des Bedrohungsmodells (T-05-06, T-05-06b). Das Skript ist ein Entwicklerschritt, kein Teil der App oder des Images.

## Self-Check: PASSED

- Dateien vorhanden: scripts/models/split_whisper.py, scripts/models/whisper-parts-2026-11.json, backend/tests/test_whisper_parts_script.py.
- Commits vorhanden: 5ed5e2a, 2f779d0, 23b8620.
