---
phase: 05-ressourcen-profile-und-modellbezug
plan: 08
subsystem: backend/models, backend/nc
tags: [RES-06, PLAT-04, whisper, sha256, teile, offline]
requires: ["05-03"]
provides:
  - "catalog.Part(url, sha256, size), catalog.PartedFile(name, sha256, size, parts)"
  - "catalog.WHISPER_RELEASE_TAG = whisper-2026-11, catalog.WHISPER_MODELS, catalog.WHISPER_SOURCES, catalog.WHISPER_TURBO_FILES, catalog.WHISPER_LARGE_V3_FILES"
  - "catalog.MODELS mit whisper-turbo und whisper-large-v3 (Typ tuple[ModelFile | PartedFile, ...]); model_bytes rechnet beide Typen"
  - "nc.fetch_model_part(url, handle, *, start, expected_size, allowed_hosts, client=None, on_chunk=None) -> str"
  - "nc.MODEL_OFFLINE = offline (in MODEL_FETCH_OUTCOMES), nc.set_models_offline(check)"
  - "procure.OFFLINE = offline (in PROCURE_OUTCOMES, nicht in READY_OUTCOMES)"
  - "procure.procure(root, name, *, fetch=nc.fetch_model_asset, fetch_part=nc.fetch_model_part, progress=None)"
affects: [05-10, 05-13, 05-14, 05-16, 05-20, 05-21]
tech-stack:
  added: []
  patterns:
    - "Teile an EINE .part-Datei anhängen, sha256 je Teil und für das Ganze, Fortsetzen nur an Teilgrenzen nach erneutem Hashen"
    - "Offline-Sperre als erste Anweisung am einzigen ausgehenden Weg, Prüfung bei jedem Aufruf neu gelesen, fail closed"
key-files:
  created:
    - backend/tests/test_model_parts.py
    - backend/tests/test_model_offline.py
  modified:
    - backend/src/audio_video_search_backend/models/catalog.py
    - backend/src/audio_video_search_backend/models/procure.py
    - backend/src/audio_video_search_backend/nc.py
    - backend/tests/test_models.py
decisions:
  - "procure bekommt den Teil-Abruf als eigenes Schlüsselwort fetch_part (Standard nc.fetch_model_part); fetch=None schaltet weiterhin jeden Abruf ab, auch den der Teile"
  - "Beim Fortsetzen zählt für die Plattenprüfung nur der noch fehlende Rest plus DISK_RESERVE_BYTES; ohne .part ist das genau Dateigröße plus Reserve wie im Plan"
  - "Eine Offline-Prüfung, die selbst scheitert, gilt als offline (fail closed, T-05-18)"
  - "Stimmen alle Teile und der Gesamtwert nicht, wird die .part gelöscht; eine leere .part bleibt nie liegen"
  - "model.bin steht im Katalog als letzte Datei eines Modells, damit die kleinen Dateien zuerst scheitern, wenn das Release nicht erreichbar ist"
  - "model_dir bleibt unverändert: auch die Whisper-Ordner liegen unter models/<name>/<MODEL_SHA256 des Vorschau-Satzes>/ (Owner-Frage, siehe unten)"
metrics:
  duration: "ca. 25 min"
  completed: 2026-11-18
  tasks: 2
  files: 6
---

# Phase 5 Plan 08: Whisper-Katalog, Teil-Download und Offline-Sperre Summary

Der Katalog kennt whisper-turbo und whisper-large-v3 unter dem Release-Tag `whisper-2026-11` mit den gemessenen Werten aus Plan 05-03; ein geteiltes `model.bin` wird Teil für Teil an eine einzige `.part` angehängt und doppelt geprüft (sha256 je Teil, sha256 des Ganzen), und eine registrierte Offline-Prüfung beendet beide Abruf-Funktionen, bevor ein Client oder eine Namensauflösung entsteht.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Katalog und Teil-Download | 456f3af | catalog.py, procure.py, nc.py, tests/test_model_parts.py, tests/test_models.py |
| 2 | Offline-Sperre am einzigen Ausgang | d27e1bb | nc.py, procure.py, tests/test_model_offline.py, tests/test_model_parts.py |

Beide Commits liegen nur lokal (kein Push), Autor street1983nk.

## Was gebaut wurde

**Katalog (`models/catalog.py`).** `Part` und `PartedFile`; je Whisper-Modell vier ganze Dateien (`ModelFile`) und ein `PartedFile` für `model.bin` (turbo 2 Teile, large-v3 3 Teile). Alle 13 URLs zeigen auf `https://github.com/street1983nk/nextcloud-audio-video-search/releases/download/whisper-2026-11/<asset>`. `WHISPER_SOURCES` nennt Repository und Commit der Herkunft, nur als Angabe; der Katalog enthält keine URL auf Hugging Face. Herkunft und Lizenzen stehen im Docstring (turbo MIT; large-v3 Gewichte OpenAI laut Modellkarte Apache-2.0, CTranslate2-Fassung Systran MIT, D-05-15). `ASSET_HOSTS`, `MODEL_SHA256`, `MODEL_RELEASE_TAG` und die Einträge für Parakeet und Silero sind unverändert.

**Teil-Abruf (`nc.fetch_model_part`).** Gleicher Weg wie `fetch_model_asset`: `_stream_model` wurde so erweitert, dass es entweder einen Pfad anlegt oder auf eine offene Datei schreibt; die Sprungprüfung je Hop, das Löschen der Cookies je Sprung und die Längenprüfung sind dadurch derselbe Code für beide Funktionen. Vor dem Abruf wird die Datei auf `start` gekürzt, bei jedem anderen Ergebnis als `fetched` wieder auf `start`. Die Datei gehört dem Aufrufer und wird nie geschlossen. `fetch_model_asset` ist signaturgleich.

**Beschaffung (`models/procure.py`).** Neuer Zweig für `PartedFile`: Zwischendatei `<name>.part`, zwei laufende Hashes, nach dem letzten Teil Länge und Gesamtwert, `fsync`, `os.replace`. Ein falscher Teil wird abgeschnitten, die `.part` endet an der Grenze des letzten geprüften Teils, Ergebnis `WRONG_DIGEST`. Neustart: die Länge der `.part` muss eine Teilgrenze sein und jeder vorhandene Teil wird neu gehasht, sonst wird sie gelöscht. `verify_file` prüft eine abgelegte ganze Datei eines `PartedFile` gegen den Gesamtwert; das Urteil bleibt nur im Speicher (`_VERIFIED`).

**Offline (`nc.set_models_offline`).** Modulweite Prüfung, Standard online. Erste Anweisung in `fetch_model_asset` und `fetch_model_part`: bei offline Log mit `outcome=offline` und Rückgabe `MODEL_OFFLINE`, ohne Client, ohne Namensauflösung, ohne die Datei anzufassen. `procure` bildet das auf `OFFLINE` ab. Die Registrierung der echten Prüfung (state.db, `AVS_OFFLINE`) kommt mit 05-13/05-16.

## Verification

Geprüft (lokal, Windows, 18.11.2026):

| Gate | Ergebnis |
|------|----------|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 148 files already formatted |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | 0 errors, 0 warnings, 0 informations |
| `uv run vulture` | ohne Befund |
| `uv run pytest -q` (Volllauf vor dem letzten Commit) | 2665 passed, 19 skipped, 4 xfailed in 183 s |
| Volllauf nach Task 1 | 2647 passed, 19 skipped, 4 xfailed |

Neue Tests: `tests/test_model_parts.py` 30, `tests/test_model_offline.py` 18 (davon 2 über Parameter), `tests/test_models.py` 8 neue.

Akzeptanzkriterien:

- `git diff --stat HEAD~2 -- backend/tests/test_model_download.py`: leer, Datei unverändert und grün.
- `grep -c "https://huggingface" catalog.py`: 0 (auch `huggingface` allein: 0, die Herkunft steht als "Hugging Face" im Docstring und als Repository-Name in `WHISPER_SOURCES`).
- `grep -c "MODEL_OFFLINE" nc.py`: 6.

**RED belegt.** Task 1: beide Testdateien scheiterten vor der Umsetzung schon beim Sammeln (`catalog` hat kein `PartedFile`). Task 2: 17 failed, 18 errors, 1 passed vor der Umsetzung (`nc` hat kein `set_models_offline`).

**Negativkontrollen.** Je Fall wurde der Produktcode an einer Stelle gebrochen, die Tests liefen, die Datei wurde aus dem Speicher zurückgeschrieben; `git diff` vor und nach jedem Durchgang war bytegleich (`cmp`). Task 1: 26 Fälle (unter anderem Teil-sha256 ignoriert, Gesamtwert ignoriert, falscher Teil nicht abgeschnitten, vorhandene Teile nicht neu gehasht, beliebige Länge als Grenze, nie fortsetzen, keine Plattenprüfung, doppelter Plattenbedarf, Sprungziel nicht gegen die Allowlist geprüft, fremde Datei geschlossen, eine Ziffer eines Teil-Hashes, ein Byte einer Länge, Teile vertauscht, falsches Tag, Hugging-Face-URL als Asset). Task 2: 16 Fälle (Prüfung fehlt in je einer Funktion, Prüfung erst nach dem Client, Prüfung erst nach dem Kürzen, Prüfung nur einmal gelesen, fail open, Standard offline, Log ohne Code, Abbildung in `procure` fehlt, `OFFLINE` als bereit gezählt). Alle Fälle wurden rot.

Zwei Fälle waren im ersten Durchgang nicht rot und haben die Tests verbessert:

1. "Kein Kürzen nach einem zu langen Teil" blieb grün, weil httpx die Blöcke auf 1 MiB sammelt und der zu lange Körper deshalb abgelehnt wurde, bevor ein Byte geschrieben war. Der Test setzt jetzt `nc.CHUNK_SIZE` auf 64; danach sind beide Parameter (network, too_large) rot.
2. "Standard ohne Registrierung ist offline" blieb grün, weil die Test-Fixture nach jedem Test selbst eine Online-Prüfung registrierte. Die Fixture stellt jetzt die Prüfung des Moduls wieder her; danach sind `test_without_a_registered_check_the_download_is_online` und die Tests in `test_model_download.py` rot.

**Kontrolle der Fallen.** Der Test mit dem echten Client (ohne Mock-Transport) zeigt, dass die Falle auf `socket.getaddrinfo` einen Versuch sieht: online wird genau `github.com` aufgelöst (die Falle antwortet wie ein toter Resolver, kein Paket verlässt den Rechner, Ergebnis `network`), offline bleibt die Liste leer.

## Deviations from Plan

### Ergänzungen (Rule 2, Sicherheit und Korrektheit)

**1. Offline-Prüfung, die scheitert, zählt als offline**
- **Found during:** Task 2
- **Issue:** Die spätere echte Prüfung liest state.db; wirft sie, hätte der Abruf mit einer fremden Ausnahme geendet oder (bei falscher Behandlung) verbunden.
- **Fix:** `_models_offline` fängt die Ausnahme, loggt nur den Fehlertyp und antwortet offline. Test `test_a_check_that_fails_counts_as_offline`.
- **Commit:** d27e1bb

**2. Datei wird vor dem Teil auf `start` gekürzt**
- **Found during:** Task 1
- **Issue:** Der Plan verlangt das Kürzen nur im Fehlerfall. Reste hinter `start` (abgebrochener Lauf) wären sonst Teil der Datei geblieben, wenn der neue Teil kürzer endet.
- **Fix:** `fetch_model_part` kürzt zuerst auf `start`. Test `test_a_part_overwrites_what_stood_behind_the_start`.
- **Commit:** 456f3af

### Abweichungen in der Form

**3. `procure` hat ein zusätzliches Schlüsselwort `fetch_part`**
- Der Plan nennt nur `fetch`. Die Teile brauchen eine andere Funktion (`nc.fetch_model_part`, offene Datei statt Pfad). `fetch_part` hat den Standard `nc.fetch_model_part`; alle Aufrufe aus 05-13 und 05-20 (`procure(root, name)`, `procure(fetch=None)`, `procure(fetch=nc.fetch_model_asset, progress=...)`) funktionieren unverändert.

**4. Plattenprüfung beim Fortsetzen: nur der Rest**
- Plan: "Freier Platz < Dateigröße + DISK_RESERVE_BYTES -> NO_ROOM". Umgesetzt: fehlender Rest plus Reserve. Ohne `.part` ist das identisch mit dem Plan. Mit geprüften Teilen in der `.part` wäre die volle Dateigröße zu viel verlangt (large-v3 mit 2 GiB vorhanden bräuchte sonst noch 3 GB frei statt 0,9 GB). Tests für beide Grenzen.

**5. Bestehende Tests in `tests/test_models.py` auf die Vorschau-Modelle eingegrenzt**
- `_all_files()` lief über alle Einträge von `catalog.MODELS` und verlangte genau fünf Dateien unter `models-2026-11`. Mit den Whisper-Modellen im selben Katalog gilt das nur noch für Silero und Parakeet. `_all_files()` liest jetzt genau diese zwei Modelle; keine Erwartung wurde gelockert (gleiche Hashes, gleiche Längen, gleiche URLs, `MODEL_SHA256`). Ein neuer Test hält die Schlüsselmenge von `MODELS` fest, die Whisper-Einträge haben eigene Tests. Negativkontrolle "Vorschau-Hash verändert" ist rot.

**6. `_stream_model` umgebaut statt kopiert**
- Plan: `fetch_model_part` "nach dem Muster von `_stream_model`". Umgesetzt als ein gemeinsamer Codeweg (Pfad oder offene Datei), damit die Sprungprüfung nicht zweimal existiert. `tests/test_model_download.py` ist unverändert grün.

**7. Die Testdatei aus Task 1 wurde in Task 2 noch einmal geändert**
- `tests/test_model_parts.py` (12 Zeilen) steht im Commit d27e1bb, weil die Negativkontrolle den schwachen too_large-Fall erst dort gezeigt hat.

**8. Anforderungen nicht abgehakt**
- RES-06 und PLAT-04 stehen im Kopf des Plans, sind aber mit diesem Plan allein nicht erfüllt (Upload 05-10, Image 05-14, Registrierung der Prüfung 05-13/05-16, Mitschnitt 05-21). `requirements.mark-complete` wurde deshalb nicht ausgeführt, wie bei 05-02.

## Beweis in CI offen

- Alle Tests liefen nur unter Windows (Python des lokalen venv). Linux amd64 und arm64 (Kürzen und Anhängen an offener Datei, `fsync`, `os.replace`) belegt erst der CI-Lauf nach einem Push.
- Kein Docker: nichts im Container geprüft.
- Kein echter Abruf: das Release `whisper-2026-11` existiert noch nicht (Upload ist Plan 05-10, Owner). Die echte Weiterleitungskette der 13 Assets und die `digest`-Werte der GitHub-API sind ungeprüft; die Allowlist ist die für `models-2026-11` gemessene.
- "Kein Verbindungsaufbau bei offline" ist hier per Falle auf Client und `socket.getaddrinfo` belegt, nicht per Netzwerkmitschnitt; der Mitschnitt ist Plan 05-21.
- security.yml (CodeQL, REUSE, pip-audit) läuft erst nach einem Push.

## Nur angenommen, nicht selbst geprüft

- Die Werte in `scripts/models/whisper-parts-2026-11.json` stimmen mit den echten Dateien unter `C:\Users\Student\av-whisper-assets` überein. Das hat Plan 05-03 gemessen; in diesem Plan wurden die 8,8 GB nicht noch einmal gehasht. Geprüft ist hier nur: Katalog gleich JSON, Gesamtwerte gleich 05-RESEARCH.md.
- Dass faster-whisper das Verzeichnis mit `model.bin`, `config.json`, `tokenizer.json`, `vocabulary.json`, `preprocessor_config.json` lädt, ist erst mit 05-20 belegt.

## Offene Fragen an den Owner

1. **Ordner der Whisper-Modelle.** `procure.model_dir` ist unverändert, also liegen die Whisper-Dateien unter `models/whisper-turbo/3a78ea81.../` und `models/whisper-large-v3/3a78ea81.../`. Der Ordnername ist der Satz-Hash von Parakeet und Silero, nicht der der Whisper-Dateien. Der Plan ändert `model_dir` nicht und 05-20 nutzt `procure.model_dir(root, name)`; die Recherche schreibt `<modell>/<set-sha>/`. Soll Whisper einen eigenen Satz-Hash je Modell bekommen (dann auch als Herkunft der Veredelung in Phase 6), bevor 05-10 und die Offline-Doku den Pfad nach außen nennen? Bis zur Antwort bleibt es beim bestehenden Verhalten.
2. **Fortsetzen bei Plattenprüfung** (Abweichung 4): Rest statt volle Dateigröße in Ordnung?
3. **Gesamtwert falsch bei richtigen Teilen:** die `.part` wird gelöscht, jeder weitere Versuch lädt neu (bis 3 GB). Das kann nur bei einem Fehler im Katalog oder im Release eintreten; Alternative wäre, die `.part` liegen zu lassen und ohne Anfrage `wrong_digest` zu melden.

## Threat Flags

Keine neue Fläche außerhalb des Bedrohungsmodells. T-05-17 (sha256 je Teil und Ganzes, Kürzen, `os.replace` erst nach Treffer), T-05-17b (Allowlist je Sprung, Test mit fremdem Host), T-05-17c (eine Datei, Plattenprüfung vor dem Abruf), T-05-18 (Sperre vor Client und Namensauflösung, Test mit Falle) und T-05-18b (Logs nur Code und Fehlertyp, Test auf fehlende URL) sind umgesetzt und getestet; der Mitschnitt zu T-05-18 bleibt bei 05-21.

## Known Stubs

Keine. `nc.set_models_offline` hat in diesem Plan bewusst noch keinen Aufrufer im Produktcode; die Registrierung ist Plan 05-13/05-16 (im Plan so festgelegt).

## TDD Gate Compliance

Test und Umsetzung liegen je Task in einem Commit (Owner-Regel: vor jedem Commit alle Gates grün). RED wurde lokal vor der Umsetzung belegt, siehe Verification. Ein eigener `test(...)`-Commit existiert deshalb nicht.

## Self-Check: PASSED

- Dateien vorhanden: backend/tests/test_model_parts.py, backend/tests/test_model_offline.py, backend/src/audio_video_search_backend/models/catalog.py, backend/src/audio_video_search_backend/models/procure.py, backend/src/audio_video_search_backend/nc.py, backend/tests/test_models.py.
- Commits vorhanden: 456f3af, d27e1bb.
