---
phase: 05-ressourcen-profile-und-modellbezug
plan: 07
subsystem: backend/engine
tags: [RES-02, RES-03, RES-05, oom, threads, kindprozess, vad-gate]
requires: ["05-04"]
provides:
  - "child.OOM_SCORE_ADJ = 1000, child.OOM_SCORE_PATH, child.DEFAULT_MODEL = parakeet"
  - "child.thread_env(threads) -> {OMP_NUM_THREADS: N, OPENBLAS_NUM_THREADS: 1, MKL_NUM_THREADS: 1}, ValueError unter 1; THREAD_ENV entfällt"
  - "child.EngineWorker(models_root, *, model='parakeet', factory, headroom, threads=_standard_threads, need=_catalog_need, events=memory_guard.memory_events)"
  - "EngineWorker.threads -> int | None (Zahl des laufenden Kindes), EngineWorker.last_peak_bytes -> int | None"
  - "Factory-Signatur factory(models_root: Path, threads: int); parakeet.Engine(models_root, threads)"
  - "Pipe-Antwort des Kindes (code, windows, peak_bytes); ask() gibt unverändert (code, windows) zurück"
  - "OUT_OF_MEMORY bei gestiegenem oom_kill oder Exit -9 ohne eigenen Kill (child._death_code)"
affects: [05-11, 05-12, 05-15, 05-16, 05-18, 05-20]
tech-stack:
  added: []
  patterns:
    - "Kind senkt sich selbst als erste Anweisung (_lower_self: setsid, oom_score_adj, nice), danach Umgebung, danach Bibliothek"
    - "Eine Thread-Zahl N je Kind, einmal im Elternprozess gelesen, in Umgebung und Bibliothek gleich; OMP_THREAD_LIMIT nie gesetzt und aus geerbter Umgebung entfernt"
    - "OOM-Erkennung über memory.events (Zähler vor dem Senden, nach dem Tod) plus Exit-Code"
key-files:
  created: []
  modified:
    - backend/src/audio_video_search_backend/engine/child.py
    - backend/src/audio_video_search_backend/engine/parakeet.py
    - backend/tests/test_engine_child.py
    - backend/tests/engine_fakes.py
    - backend/tests/test_engine_model.py
    - backend/tests/test_vad_gate.py
    - ci/measure/peak_probe.py
    - scripts/research/phase3/verdict22.py
    - scripts/research/phase3/verdict23.py
decisions:
  - "VAD-Gate Regel 1 erlaubt in engine/ zusätzlich genau zwei wörtliche ganze Zeilen (Owner-Freigabe 18.11.2026, Option A in enger Fassung); thread_env muss in derselben Datei auf oberster Ebene definiert sein"
  - "Standard-Thread-Zahl ist hardware.default_threads(hardware.usable_cpus()) statt fest 2; bei 2 nutzbaren CPUs läuft 1 Thread"
  - "Der Wächter liest zuerst den Speicher, erst danach die Thread-Zahl; eine Zahl unter 1 ist ein ValueError im Elternprozess, kein Kind startet"
  - "_catalog_need kennt bis Plan 05-12 nur parakeet (ENGINE_NEED_BYTES), jedes andere Modell ist ein ValueError"
  - "last_peak_bytes behält den Wert der letzten Antwort auch nach dem Ende des Kindes; unter Windows None"
  - "Ein Commit je TDD-Task statt getrenntem RED-Commit (Gates vor jedem Commit, vom Orchestrator bestätigt)"
metrics:
  duration: "ca. 75 min (zwei Sitzungen, dazwischen Halt für den Owner-Entscheid)"
  completed: 2026-11-18
  tasks: 2
  files: 9
---

# Phase 5 Plan 07: OOM-Isolation, Wächter je Modell und eine Thread-Zahl Summary

Das Erkennungs-Kind schreibt als erste Anweisung `oom_score_adj` 1000 und läuft mit nice 10 in eigener Sitzung; der Wächter prüft den Bedarf des konkreten Modells plus Reserve; ein vom Kernel getötetes Kind heißt `OUT_OF_MEMORY` statt `CRASHED`; Kind, Umgebung und Bibliothek rechnen mit derselben Thread-Zahl N, und `OMP_THREAD_LIMIT` kommt im Kind nie vor.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | OOM-Wert, Wächter je Modell, OOM-Erkennung, Spitze | 5711ac5 | engine/child.py, tests/test_engine_child.py, tests/engine_fakes.py |
| 2 | Eine Thread-Zahl für Kind, Umgebung und Bibliothek | 81500ac | engine/child.py, engine/parakeet.py, tests/test_engine_child.py, tests/engine_fakes.py, tests/test_engine_model.py, tests/test_vad_gate.py, ci/measure/peak_probe.py, scripts/research/phase3/verdict22.py, verdict23.py |

Beide Commits liegen nur lokal (kein Push), Autor street1983nk.

## Was gebaut wurde

**OOM-Isolation (RES-03, T-05-14).** `_lower_self()` ist die erste Anweisung in `_child_main`: `os.setsid()`, `_raise_oom_score()` (schreibt `1000\n` nach `/proc/self/oom_score_adj`, ein `OSError` ergibt False), `os.nice(10)`. Erst danach folgen Umgebung und Factory. Der Hauptprozess bleibt unverändert. Kein Adressraum-Limit.

**Wächter je Modell (RES-02).** `EngineWorker.start()` prüft `memory_guard.admits(headroom, need=need(model) + ENGINE_RESERVE_BYTES)`. `need` wird mit dem Modellnamen aufgerufen; der Standard `_catalog_need` liefert für "parakeet" `ENGINE_NEED_BYTES` und sonst einen `ValueError`. Plan 05-12 reicht den Bedarf aus resources.py herein.

**OOM-Erkennung (T-05-15).** Vor dem Senden eines Auftrags liest der Worker `oom_kill` aus `memory.events`. Stirbt das Kind, ohne dass der Worker es selbst getötet hat, liest er erneut: gestiegen oder Exit-Code -9 ergibt `OUT_OF_MEMORY` (mit Log `extra={"code": OUT_OF_MEMORY}`), sonst `CRASHED`. Ein unlesbarer Zähler beweist nichts. Der eigene Kill nach der Frist bleibt `TIMEOUT`.

**Spitze.** Jede Antwort des Kindes ist ein Tripel `(code, windows, peak_bytes)` mit `ru_maxrss * 1024` unter Linux, sonst None. `ask()` gibt weiter `(code, windows)` zurück (das Protokoll in `worker/preview.py` bleibt), die Spitze steht in `EngineWorker.last_peak_bytes`.

**Eine Thread-Zahl (RES-05, T-05-16).** `thread_env(threads)` ersetzt die Konstante `THREAD_ENV`. Der Worker liest `threads()` genau einmal je Kind (nach dem Wächter) und übergibt die Zahl an `_child_main(pipe, models_root, factory, threads)`. Das Kind entfernt `OMP_THREAD_LIMIT`, setzt `SECRET_ENV` und `thread_env(threads)` vor dem Laden der Factory und ruft `factory(Path(models_root), threads)`. `parakeet.Engine(models_root, threads)` gibt `num_threads=threads` an `OfflineRecognizer.from_transducer`; die VAD bleibt bei `VAD_THREADS` (1). `EngineWorker.threads` nennt die Zahl des laufenden Kindes, ein geänderter Wert gilt erst für das nächste Kind.

`RECOGNIZER_THREADS` und `CONFIG_VERSION` in `engine/constants.py` sind bytegleich, `tests/test_engine_constants.py` ist unverändert und grün. vulture meldet die nun unbenutzte Konstante nicht, ein Whitelist-Eintrag war nicht nötig.

## Vom Owner ausdrücklich festzuhalten

**(a) Gate-Änderung mit Owner-Freigabe vom 18.11.2026.** `backend/tests/test_vad_gate.py` Regel 1 erlaubte in `engine/` bisher nur `os.environ.update(<KONSTANTE>)`. Die vom Plan verlangten Zeilen wären ein Befund gewesen; die Ausführung hielt deshalb an Task 2 an. Der Owner hat Option A in enger Fassung freigegeben. Umgesetzt ist genau das:
- Zwei wörtliche Zeilen, keine Muster, jeweils als ganze Zeile mit nur Leerzeichen-Einrückung davor: `os.environ.pop("OMP_THREAD_LIMIT", None)` und `os.environ.update(thread_env(threads))`.
- Eine Datei mit der zweiten Zeile muss `thread_env` selbst auf oberster Ebene definieren (`^def thread_env(`), sonst Befund. Damit liegt die Funktion in `engine/` und unterliegt selbst dem Leseverbot. Ein Test hält fest, dass `engine/child.py` beide Zeilen je einmal trägt, `thread_env` dort genau einmal definiert ist und nirgends sonst im Paket.
- Die bestehende Form `os.environ.update(<KONSTANTE>)` und die bisherige Liste der Lesefälle sind unverändert; `os.environ.update(read_variables())` bleibt Befund.
- 20 Gegentests für Abwandlungen (anderer Schlüssel, ohne Default, anderer Default, Name statt Literal, Zuweisung, `if`, `print(...)`, `or`, zweite Anweisung in der Zeile, `return`, anderer Funktionsname, anderes Argument, zweites Argument, `|`, `**`, `module.thread_env`, Zuweisung des update, `or dict(os.environ)`, `setdefault`), dazu Import von außerhalb `engine/` und verschachtelte Definition.

**(b) Thread-Zahl und Speichermessung.** Der Standard ist jetzt `hardware.default_threads(hardware.usable_cpus())` (halbe nutzbare CPUs, höchstens 4). Bei 2 nutzbaren CPUs läuft künftig 1 Thread, bei 8 oder mehr laufen 4. Die Speichermessung in `measured.PARAKEET_PEAK_BYTES` (amd64 1 147 076 608, arm64 1 232 142 336) lief mit 2 Threads. Die Spitze bei 1, 3 oder 4 Threads ist nicht gemessen.

**(c) Fingerabdruck.** Der Fingerabdruck nennt weiter `RECOGNIZER_THREADS = 2`, auch wenn ein Kind mit einer anderen Zahl rechnet. Dass Parakeet bei 1 Thread wortgleiche Transkripte liefert wie bei 2 (Annahme A8, Pitfall 6), ist nicht gemessen; der CI-Vergleich ist für Plan 05-20 vorgesehen, die Zahl in der Herkunft für Plan 05-11.

## Verifikation

Gates im Ordner `backend`, auf dem Endstand vor Commit 81500ac:

| Gate | Ergebnis |
|------|----------|
| `uv run ruff check .` (auch `../scripts`, `../ci/measure`) | All checks passed |
| `uv run ruff format --check .` (mit `../scripts`) | 169 Dateien formatiert |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | 0 errors, 0 warnings |
| `uv run vulture` | Exit 0 |
| `uv run pytest -q` | 2702 passed, 20 skipped, 4 xfailed, 232,89 s |

Vor Commit 5711ac5 (Task 1): dieselben Gates grün, Volllauf 2609 passed, 19 skipped, 4 xfailed.

Akzeptanzkriterien: `OOM_SCORE_ADJ: Final = 1000` einmal; `RLIMIT_AS` ohne Kommentarzeilen null; `"OMP_THREAD_LIMIT":` ohne Kommentarzeilen null; `num_threads=threads` einmal in parakeet.py; `test_engine_constants.py` unverändert.

RED: Task 1 Sammelfehler `cannot import name 'OOM_SCORE_ADJ'`, Task 2 Sammelfehler `cannot import name 'thread_env'`, jeweils vor der Umsetzung.

**Negativkontrollen.** Jede Mutation machte den genannten Test rot; danach wurden die Dateien bytegleich zurückgeschrieben (`cmp`), `git status` nach den Commits sauber.
- Task 1, 18 Mutationen an child.py: `_lower_self` entfernt; OOM-Wert 0; OSError nicht gefangen; Wächter ohne Modellbedarf; ohne Reserve; Katalog für jedes Modell; Zähleranstieg ignoriert; jeder Tod als OOM; unlesbarer Zähler als Anstieg; Exit -9 ignoriert; Zähler nur einmal gelesen; Anstieg bei beantworteter Störung; Antwort ohne Spitze; KiB als 1000; Worker vergisst die Spitze; Standard-Events ersetzt; Konstante 500. Eine Kontrolle war zuerst nicht rot, der Test wurde geschärft.
- Task 2, 16 Mutationen an child.py und parakeet.py: `thread_env` ignoriert die Zahl (zwei Tests); setzt `OMP_THREAD_LIMIT` (zwei Tests); nimmt Zahlen unter 1; pop entfernt (Kind und im Prozess); Thread-Variablen erst nach der Factory; Factory mit fester 2; keine Prüfung im Elternprozess; `threads` überlebt das Kind; Zahl vor dem Wächter gelesen; Zahl für ein laufendes Kind neu gelesen; Standard fest 2; Erkenner mit fester 2; VAD mit 2.
- Gate selbst, 6 Mutationen an test_vad_gate.py: Erlaubnis zu einem Muster aufgeweicht (ohne Abbruch beim ersten Fehler: 20 von 29 Gegentests rot, darunter `os.environ.update(read_variables())`); Teilzeile erlaubt; jedes update erlaubt; Definitionsort nicht geprüft; verschachtelte Definition zählt; Erlaubnis ganz entfernt (Positivtest rot).
- Produkt gegen das Gate, 2 Mutationen: `thread_env` aus der Datei genommen; Wert des pop zugewiesen. Beide Male meldet der Produkt-Scan einen Befund.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ci/measure/peak_probe.py` importierte `THREAD_ENV`**
- **Found during:** Task 2
- **Issue:** Die Konstante entfällt, der Messjob wäre mit einem ImportError gescheitert.
- **Fix:** Die Probe liest die Standard-Zahl einmal, gibt sie dem Worker und schreibt `thread_env(threads)` in das unveränderte Feld `threads_env`. `docs/measurements/parakeet-peak-2026-11.json` ist nicht angefasst.
- **Commit:** 81500ac (vom Orchestrator freigegeben)

**2. [Rule 3 - Blocking] `scripts/research/phase3/verdict22.py` und `verdict23.py` riefen `Engine(path)`**
- **Found during:** Task 2
- **Issue:** pyright schließt `../scripts` ein und meldete zwei fehlende Argumente.
- **Fix:** `Engine(path, RECOGNIZER_THREADS)`, also dieselbe Zahl wie bei den damaligen Messungen.
- **Commit:** 81500ac (vom Orchestrator freigegeben)

### Weitere Abweichungen

- **Halt an Task 2 und Gate-Änderung.** Widerspruch zwischen Plan und VAD-Gate, Owner-Entscheid 18.11.2026 (siehe oben). `tests/test_vad_gate.py` stand nicht in `files_modified`.
- **Kein eigener RED-Commit.** Die Owner-Regel "Gates vor jedem Commit" schließt einen Commit mit rotem pyright und pytest aus; RED ist lokal belegt, je Task ein Commit.
- **`_raise_oom_score` läuft nur außerhalb von Windows** (im selben Block wie setsid und nice). Die Funktion selbst gibt unter Windows False zurück, das Kind läuft (Test).
- **Zusätzliche kleine Funktionen** `_lower_self`, `_rss_bytes`, `_peak_bytes`, `_death_code`, `_standard_threads` und die Konstanten `OOM_SCORE_PATH`, `DEFAULT_MODEL`, damit die Logik auch unter Windows prüfbar ist.
- **Test für `num_threads` steht in `test_engine_child.py`** (mit einem Ersatz für sherpa_onnx, ohne Modell); `test_engine_model.py` bekam stattdessen einen Test am echten Kind (Standard-Zahl und Spitze), der lokal ohne Modelle übersprungen wird.

## Beweis in CI offen

Lokal lief alles unter Windows, Docker ist aus. Erst ein CI-Lauf nach einem Push belegt:
- Das Kind liest aus dem Kernel `oom_score_adj` gleich 1000 zurück und nice 10 (Linux-Zweig des Tests vorhanden). Fiele `_raise_oom_score()` aus `_lower_self` heraus, merkt das nur dieser Zweig.
- Ein von außen mit SIGKILL beendetes Kind ergibt `OUT_OF_MEMORY` (Test unter Windows übersprungen); der eigene Kill nach der Frist bleibt `TIMEOUT`, obwohl der Exit-Code dort ebenfalls -9 ist.
- `ru_maxrss` ist wirklich KiB (Annahme A12): Plausibilitätstest am Kind (5 MiB bis 2 GiB) und am echten Modell (über 300 MiB, unter dem Doppelten des Messwerts). Lokal ist nur die Umrechnung geprüft.
- `test_engine_model.py` am echten Parakeet (lokal `AVS_TEST_MODELS` nicht gesetzt, 20 Skips).
- Der Messjob `peak-measure` in `docker.yml` mit der geänderten Probe.
- Provozierter Speichermangel im Container (Plan 05-18), Thread-Messung und Wortgleichheit bei 1 und 2 Threads auf amd64 und arm64 (Plan 05-20).

## Threat Flags

Keine neue Angriffsfläche. Die Gate-Änderung erweitert die Schreiberlaubnis in `engine/` um zwei wörtliche Zeilen; Lesen der Umgebung bleibt in `engine/` vollständig verboten.

Stand der Threats dieses Plans: T-05-14 und T-05-16 sind im Code umgesetzt und per Unit-Test gehalten, der Nachweis im Container steht mit 05-18 und 05-20 aus (Severity high, bleiben bis dahin offen). T-05-15 umgesetzt und getestet. T-05-16b unverändert (`SECRET_ENV`, Test grün).

## Known Stubs

Keine. `_catalog_need` kennt bewusst nur Parakeet, bis Plan 05-12 den Bedarf je Modell hereinreicht.

## Offene Punkte für den Owner

- Der Elternprozess erfährt nicht, ob das Schreiben von `oom_score_adj` im Kind gelang (zum Beispiel bei nur lesbarem /proc). Der Plan verlangt es nicht; der Nachweis kommt mit 05-18. Soll das Kind das Ergebnis mitmelden?
- Exit -9 ohne eigenen Kill gilt laut Plan als `OUT_OF_MEMORY`, auch wenn ein anderer Prozess das Kind getötet hat und der Zähler lesbar und unverändert ist.
- RES-02, RES-03 und RES-05 stehen im Kopf dieses Plans, sind aber erst mit 05-11, 05-12, 05-15, 05-18 und 05-20 erfüllt; nicht abgehakt.

## Self-Check: PASSED

- 05-07-SUMMARY.md vorhanden
- Commits 5711ac5 und 81500ac in `git log` gefunden
- Alle neun geänderten Dateien vorhanden
