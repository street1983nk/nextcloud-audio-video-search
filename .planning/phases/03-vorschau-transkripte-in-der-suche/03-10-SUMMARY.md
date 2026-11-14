---
phase: 03-vorschau-transkripte-in-der-suche
plan: 10
subsystem: engine
tags: [sherpa-onnx, parakeet, py3langid, kindprozess, speicherwächter, modelltest, ci-cache, tdd]
requires:
  - "03-01: Paketfreigabe mit sha256 je Wheel"
  - "03-06: engine/constants.py, engine/catch.py"
  - "03-07/03-07b: models/procure.py, catalog.MODEL_SHA256, Release models-2026-11"
provides:
  - "Pins sherpa-onnx 2.0.1, sherpa-onnx-core 2.0.1, numpy 2.5.4, py3langid 0.4.0 (uv.lock, Wheel-sha256 geprüft)"
  - "memory_guard.py: headroom_bytes, admits, anon_bytes, memory_events, memory_limit, meminfo_bytes (Findling 1.6.4)"
  - "engine/parakeet.py: Engine(models_root).transcribe(pcm, offset_ms, *, second_pass) -> list[Window], EngineWord, Window, merge_segments, words_from_tokens, vad_values, language_identifier"
  - "engine/child.py: EngineWorker(models_root, *, factory, headroom) mit start() -> ok|no_room, ask(pcm: bytes, offset_ms, second_pass, *, deadline=900) -> (code, list[Window]), stop(); Codes ok, timeout, out_of_memory, crashed, no_room; ENGINE_NEED_BYTES, ENGINE_RESERVE_BYTES, MAX_CHUNKS_PER_CHILD, THREAD_ENV"
  - "python.yml: Modell-Cache avs-models-<MODEL_SHA256>, Clip-Cache, AVS_TEST_MODELS/SPEECH/SPEECH_TR/WORD"
  - "pytest-Marker model und slow"
affects: [03-13, 03-15, 03-17, 03-18]
tech-stack:
  added: ["sherpa-onnx 2.0.1", "sherpa-onnx-core 2.0.1", "numpy 2.5.4", "py3langid 0.4.0", "actions/cache v6.1.0 (55cc8345)"]
  patterns:
    - "Engine-Fabrik als 'modul:funktion'-Zeichenkette, im Kind importiert; Tests mit tests/engine_fakes.py"
    - "sherpa_onnx und py3langid erst im Engine-Bau importiert; der Hauptprozess lädt nur die Datenklassen"
    - "App-Geheimnisse im Kind per os.environ.update(SECRET_ENV) geleert (erlaubtes Muster des VAD-Gates)"
key-files:
  created:
    - backend/src/audio_video_search_backend/memory_guard.py
    - backend/src/audio_video_search_backend/engine/parakeet.py
    - backend/src/audio_video_search_backend/engine/child.py
    - backend/tests/test_memory_guard.py
    - backend/tests/test_lock_wheels.py
    - backend/tests/test_engine_child.py
    - backend/tests/engine_fakes.py
    - backend/tests/test_engine_model.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
    - .github/workflows/python.yml
    - backend/tests/test_workflow_pins.py
    - backend/tests/test_vad_gate.py
    - scripts/research/phase3/build_extra.py
    - scripts/research/phase3/build_corpus.py
    - scripts/research/phase3/build_short.py
    - scripts/research/phase3/measure.py
    - scripts/research/phase3/shortpass.py
decisions:
  - "App-Geheimnisse im Kind werden auf leere Werte gesetzt statt entfernt: das VAD-Gate erlaubt in engine/ nur os.environ.update(<KONSTANTE>)"
  - "Window trägt zusätzlich latin, lid, lid_p, conf_mean (mit Standardwerten, hinter den sechs geplanten Feldern)"
  - "Fenster ohne Wörter: Urteil confidence mit n_words 0 (zählt im Dateiurteil nichts, wie verdict.py)"
  - "Clip-WAV-sha256 nach Cache-Restore nur als Warnung, wie fetch_speech.py selbst; verbindlich bleibt der Mitglied-sha256 beim Laden, ffmpeg-Binary-sha256 steht im Clip-Schlüssel"
metrics:
  duration: "ca. 2 h"
  completed: 2026-11-14
  tasks: 3
  files: 18
---

# Phase 3 Plan 10: Erkennungspakete, Speicherwächter, Parakeet im Kindprozess Summary

Die vier freigegebenen Pakete sind exakt gepinnt (Wheel-sha256 gegen 03-01 im Test), der Speicherwächter ist aus Findling übernommen, und Parakeet läuft nach measure.py 1:1 in einem spawn-Kind mit Wächter vor dem Start, Frist mit Kill und Kindwechsel; das echte Modell findet "Dinosaurier" im FLEURS-Clip bei 6146 ms und mit Stückversatz bei 606146 ms.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 | 234424d | build(03-10): Erkennungspakete gepinnt, Speicherwächter übernommen |
| 2 RED | 06c6c1a | test(03-10): Kindprozess und Fensterlogik der Engine als Vertrag (rot) |
| 2 GREEN | 98e2c7e | feat(03-10): Parakeet im Kindprozess |
| Fix | 5851b2f | fix(03-10): Kind, das beim Hochfahren stirbt, gilt sofort als abgestürzt |
| 3 | 486fe42 | test(03-10): Modelltest mit gepinntem Sprachclip, Modell-Cache in CI |
| Nacharbeit | 8bb6ef2 | chore(03-10): pyright-Unterdrückung der Messskripte entfernt |

Alle nur lokal, Autor und Committer street1983nk <k.cherif@outlook.de>, nicht gepusht.

## Task 1: Pins und Speicherwächter

- `uv add sherpa-onnx==2.0.1 sherpa-onnx-core==2.0.1 numpy==2.5.4 py3langid==0.4.0`: der Resolver zog genau diese vier Pakete und nichts sonst (Paketliste im Lock vorher 47, nachher 51, Diff nur die vier Namen; Abhängigkeiten: sherpa-onnx nur sherpa-onnx-core, py3langid nur numpy).
- Alle sieben freigegebenen sha256 stehen wörtlich im Lock (je Wheel per grep nachgesehen). `python -c "import sherpa_onnx, numpy, py3langid"`: `2.0.1 2.5.4`.
- test_lock_wheels.py liest uv.lock als TOML: Version, Quelle PyPI, freigegebene Wheels mit sha256, je Architektur ein CPython-3.13-manylinux-Wheel (x86_64 und aarch64) bzw. py3-none-any für py3langid. Positivkontrollen: Lock ohne aarch64-Wheel, geänderter Hash, verschobene Version, fehlendes Paket, py3langid ohne Wheel; Tag-Leser lehnt cp312 und cp313t ab. Mutation: ein Zeichen im freigegebenen py3langid-Hash geändert, 1 Test rot.
- memory_guard.py: Findling 1.6.4 (e5c1da70) memory_guard.py Zeilen 35 bis 94 plus memory_limit, meminfo_bytes, CGROUP_ROOT, MEMINFO aus hardware.py; kein RLIMIT_AS (grep leer, Test). 15 Tests; Mutation "ohne MemAvailable-Deckel" 1 Test rot.

## Task 2: Parakeet-Pipeline und Kindprozess

- parakeet.py übernimmt measure.py: VAD (Konstanten, zweiter Durchgang 0,3/0,1, VAD bleibt an), Zusammenfassung (Lücke bis 2 s, Fenster bis 25 s), dec_span (0,4 s Kontext, mindestens 0,5 s, 0,5 s Polster), Schluck-Wächter (ab 1 s, unter 1 Wort/s, 0,3 s Spielraum, reicheres Ergebnis gewinnt), latin_share, py3langid mit norm_probs, conf_mean, `window_verdict`. Rundungen wie measure.py (latin 3, lid_p 3, conf 4 Stellen); Zeiten in ganzen ms Medienzeit = offset_ms + Tokenzeit + Spannenversatz.
- child.py: spawn-Kontext, Linux setsid und nice 10, `os.environ.update(SECRET_ENV)` und `os.environ.update(THREAD_ENV)` vor jedem Import von sherpa_onnx, Engine einmal je Kind, Codes statt Ausnahmen, Wächter vor jedem Start (need 1700 MiB + Reserve 512 MiB), Frist 900 s mit Gruppen-Kill, Kindwechsel nach 12 Stücken und nach jedem Nicht-OK. Logs nur `code` und `seconds`.
- test_engine_child.py (36 Fälle): Antwort mit Versatz, Frist mit Kill und neuem Kind, MemoryError, Absturz, Ausnahme, Bau-Fehler (OUT_OF_MEMORY bzw. CRASHED), NO_ROOM für None/0/need/need+reserve-1 ohne Kind, genau need+reserve zugelassen, Kindwechsel nach 12, stop zweimal, Kind mit gepinnten Threads und leeren Geheimnissen (Eltern unverändert), nice 10 unter Linux, kein sherpa_onnx im Elternprozess (frischer Interpreter), py3langid.server nie geladen (frischer Interpreter, Gegenprobe lädt es und sieht es), Fensterlogik mit geskriptetem Recognizer. Nach jedem Test `multiprocessing.active_children()` leer (autouse-Fixture).
- Mutationsproben, jede gefangen: Kill bei Frist weg (1 rot, 4 Fehler), Geheimnisse nicht geleert (1), Kindwechsel weg (1), Wächter weg (5), MemoryError als crashed (1), Wörter auch bei verworfenem Fenster (2), Schluck-Wächter aus (2), Versatz falsch (2).

## Task 3: Modelltest und CI-Cache

Freier RAM vor jedem Modelllauf geprüft (4,7 bis 5,0 GiB), alle Läufe seriell. Modelle per `procure --root <scratch>` aus dem Release models-2026-11 (`silero procured`, `parakeet procured`), Clips per fetch_speech.py (Mitglied- und WAV-sha256 beider Clips stimmen mit ffmpeg 8.1.1 Gyan). Scratch-Ordner danach gelöscht.

Messung (Windows-Laptop, EngineWorker mit echtem Kind, FLEURS DE 11,16 s):

| Messgröße | Wert |
|---|---|
| Erster Auftrag inkl. Kindstart und Modell-Laden | 3,62 s |
| Zweiter Auftrag (Modell geladen) | 0,75 s |
| Fenster | 2246 bis 8852 ms, Sprache 6108 ms, 20 Wörter, keep, lid de p 1,0, latin 1,0, conf_mean 0,9948 |
| Wort "Dinosaurier" | 6146 bis 6786 ms, conf 0,9836 |
| Gleicher Clip mit offset_ms 600000 | 606146 ms |
| TR-Clip | ein Fenster, Sprache 9070 ms, 0 Wörter, confidence |
| Spitze Arbeitsspeicher des Kinds / Spitze Commit | 997 MiB / 1448 MiB |

- test_engine_model.py mit Modellen: 5 passed (DE-Wort und Zeit im Clip, Versatz für Wörter und Fenster, Stille ohne Wort in beiden Durchgängen, TR ohne keep). Ohne Modelle: 5 skipped mit "AVS_TEST_MODELS is not set"; unter CI=true Fehlschlag statt Skip (Helfer `missing` aus media_fixtures). Gegenprobe: falsches Erwartungswort, 2 Tests rot (nach Schärfung des Versatz-Tests).
- python.yml: Schlüssel `avs-models-<MODEL_SHA256>` (lokal nachgespielt: `avs-models-3a78ea81...d339`), Clip-Schlüssel aus den Mitglied-sha256 plus sha256 des ffmpeg-Binärs; `actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0` (per `gh api repos/actions/cache/releases/latest` und `git/ref/tags/v6.1.0` aufgelöst, leichter Tag auf Commit); `*.verified.json` vom Cache ausgenommen, damit der Test jede Modelldatei neu hasht; bei Fehltreffer procure bzw. fetch_speech.py; Clip-Prüfschritt lokal mit Positivkontrolle (verfälschte WAV gibt die Warnung). YAML mit PyYAML geladen, Schrittfolge bestätigt. Job-Frist 15 auf 20 min (erster Lauf lädt ca. 670 MB).
- test_workflow_pins.py: Schlüssel aus MODEL_SHA256, Cache-Schritt, AVS_TEST_MODELS, kein `-m "not model"`, `-k "not model"` oder `--deselect` der Modelltests; Positivkontrollen für alle vier.
- `git status --porcelain`: keine .onnx- oder .wav-Datei.

## Gates

ruff check und format --check (backend und ../scripts), pyright latest 0 Fehler, vulture still, hadolint ohne Befund. Volle Suite am Ende mit Modellen **1763 passed**, Abdeckung 94,01 % (child.py 71 %, parakeet.py 70 %: der Kindcode läuft im Unterprozess und wird nicht gezählt); ohne Modelle skippen die 5 Modelltests mit Grund (einzeln geprüft). Vorher 1713 nach Task 1.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pyright-Fehler in build_extra.py, sobald numpy installiert war**
- `sum(np.resize(...) for ...)` ist für pyright `ndarray | Literal[0]`. Fix: `sum(..., start=np.zeros(n, dtype=np.float32))`; Gleichheit mit dem alten Ausdruck auf Zufallsdaten geprüft (gleich, float32; Kontrolle mit verändertem Wert ungleich). Commit 234424d.

**2. [Rule 1 - Bug] Gegenproben in test_vad_gate.py gingen von fehlender child.py aus**
- Zehn Tests erwarteten die Meldung in Zeile 2 einer neuen child.py. Jetzt zählen sie die Zeile hinter der vorhandenen Datei (`_next_line`). Commit 98e2c7e.

**3. [Rule 2 - Härtung] Kind, das beim Hochfahren stirbt**
- Gemessen: stirbt das Kind, bevor es sein Pipe-Ende hält, wartete `ask` unter Windows die ganze Frist und meldete timeout (20,0 s bei Frist 20). Jetzt wartet `_answered` in Scheiben von 1 s und schaut nach dem Kind: crashed nach 1,0 s. Tests mit Attrappen und einem Kind, das beim Engine-Bau stirbt; Mutation "ohne Lebendprüfung" rot. Commit 5851b2f.

**4. Plan-Text: sherpa-onnx hat kein py3-none-any-Wheel**
- Laut 03-01 sind die sherpa-onnx-Wheels cp313-manylinux je Architektur; nur py3langid ist rein. Der Lock-Test prüft das tatsächliche Muster.

**5. TR-Clip greift nicht über die Sprachregel (Befund, siehe Offene Punkte)**
- Der Plan erwartete, dass die Abfangregel auf echter Ausgabe greift. Parakeet gibt auf diesem Clip gar kein Token aus; der Test prüft deshalb "VAD hörte Sprache, kein Fenster keep" statt "Wörter vorhanden".

**6. RED-Commit mit einem ruff-I001-Befund**
- In 06c6c1a sortierte ruff den Import von engine.parakeet als Fremdpaket, weil das Modul noch fehlte; im GREEN-Commit richtig sortiert.

## Offene Punkte

- **TR-Clip ergibt "keine Sprache" statt "Sprache nicht unterstützt":** Parakeet liefert auf speech_tr.wav (FLEURS 10000377651956138413) null Token, auch mit sherpa-onnx allein über den ganzen Clip (unabhängige Gegenprobe, DE-Clip dabei 40 Token). Damit zählt das Dateiurteil weder script noch language noch confidence, und `file_verdict` ergibt `no_speech`. Pläne, die mit diesem Clip den Grund "Sprache nicht unterstützt" belegen wollen (03-15, 03-17, 03-18 laut 03-02), brauchen einen anderen Clip mit erkannter Fremdsprache (laut RESEARCH etwa ES/IT/NL/PL über die Text-Sprache) oder eine andere Erwartung. Entscheidung für den Owner bzw. den nächsten Planer.
- **Clip-WAV-sha256 in CI:** gemessen nur mit ffmpeg 8.1.1 Gyan. Weicht er mit BtbN 8.1.3 ab, warnt der CI-Schritt nur; Wert dann aus dem Log in fetch_speech.py übernehmen (wie in 03-02 vorgesehen).
- Der CI-Weg selbst (Cache, Download auf dem Runner, nice 10 unter Linux) ist nicht gelaufen, weil nichts gepusht wurde.
- Im Arbeitsbaum liegen fremde, nicht gestagte Änderungen einer Parallel-Sitzung (php/l10n, play.php, play.css, mehrere Tests); nicht berührt. Die volle Suite lief über diesem Stand.

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche außerhalb des Bedrohungsmodells. T-03-SC (Pins mit Wheel-sha256 gegen Freigabe), T-03-33 (Wächter, Frist, Kill, Kindwechsel), T-03-34 (spawn, Geheimnisse leer), T-03-35 (Logs nur Code und Dauer) umgesetzt und getestet. Neu in CI: actions/cache, SHA-gepinnt.

## Self-Check: PASSED

- FOUND: memory_guard.py, engine/parakeet.py, engine/child.py, test_memory_guard.py, test_lock_wheels.py, test_engine_child.py, engine_fakes.py, test_engine_model.py
- FOUND: Commits 234424d, 06c6c1a, 98e2c7e, 5851b2f, 486fe42, 8bb6ef2
