---
phase: 05-ressourcen-profile-und-modellbezug
plan: 02
subsystem: backend/abhängigkeiten
tags: [RES-06, RES-07, whisper, lieferkette, uv.lock, netzverbot, T-05-SC, T-05-05, T-05-07]
requires: []
provides:
  - "backend/pyproject.toml: faster-whisper==1.2.1, ctranslate2==4.8.5, onnxruntime==1.31.1 (exakt), tzdata==2026.6 nur Dev und nur win32, [tool.uv] exclude-newer 2026-11-05T00:00:00Z mit Ausnahme webvtt-py"
  - "backend/uv.lock: 69 Pakete (53 vorher unverändert, 16 neu)"
  - "tests/test_lock_wheels.py: APPROVED (direkte Pins), TRANSITIVE (av, huggingface-hub, tokenizers), HELD, check(packages)"
  - "tests/test_lock_platforms.py: installed(packages, environment, dev=...), jsfetch_findings, tzdata_findings, APPROVED_VERSIONS"
  - "tests/test_boundary.py: pyav_offenders, whisper_offenders (faster_whisper und ctranslate2 nur unter engine/)"
  - "tests/test_no_hub_network.py: source_findings, tree_findings, final_environment, hub_env_findings; tests/hub_import_probe.py als zweiter Zeuge"
  - "tests/conftest.py: type ClientResponse (Antworttyp des TestClient)"
affects: [05-07, 05-17, 05-20, 05-21]
tech-stack:
  added:
    - "faster-whisper 1.2.1, ctranslate2 4.8.5, onnxruntime 1.31.1 (direkt)"
    - "av 19.0.2, huggingface-hub 2.4.0, tokenizers 0.23.3, httpx2 2.16.0, httpcore2 2.16.0, hf-xet 1.8.0, truststore 0.10.5, tqdm 4.70.1, fsspec 2026.9.0, flatbuffers 25.12.19, protobuf 7.36.2 (transitiv, im Image)"
    - "httpx2-jsfetch 1.0 (nur Lock-Eintrag, Marker emscripten), tzdata 2026.6 (nur Dev, nur win32)"
  patterns:
    - "Lock wie ein Installer ablaufen: Kanten mit Marker je Umgebung auswerten (packaging.markers)"
    - "Gegenprobe mit anderem Mittel: Syntaxbaum als Regel, frischer Interpreter als Zeuge"
    - "Altersgrenze der Auflösung in [tool.uv] exclude-newer, Ausnahmen einzeln benannt"
key-files:
  created:
    - backend/tests/test_lock_platforms.py
    - backend/tests/test_no_hub_network.py
    - backend/tests/hub_import_probe.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
    - backend/tests/test_lock_wheels.py
    - backend/tests/test_boundary.py
    - backend/tests/conftest.py
    - backend/tests/test_api_export.py
    - backend/tests/test_api_routes.py
    - backend/tests/test_excerpt_states.py
    - backend/tests/test_handshake.py
    - backend/tests/test_sample_real_transcript.py
    - backend/tests/test_search_tiers.py
decisions:
  - "Owner 18.11.2026: Altersgrenze exclude-newer 2026-11-05T00:00:00Z (der ganze 04.11.2026 ist eingeschlossen), einzige Ausnahme der bestehende Dev-Pin webvtt-py (2026-11-09T00:00:00Z)"
  - "Owner 18.11.2026: httpx2-jsfetch 1.0 nur als Lock-Eintrag mit Marker sys_platform == 'emscripten'; ein Test hält das (test_lock_platforms.py)"
  - "tzdata exakt gepinnt (==2026.6) statt ohne Version wie im Probelauf, weil im Projekt alles exakt gepinnt ist; nur Dev-Gruppe, nur win32"
  - "av, huggingface-hub und tokenizers bleiben ohne eigenen Pin im Projekt; Version und Wheel-sha256 hält der Lock, test_lock_wheels.py prüft sie"
  - "Netzverbot als eigene Regel: kein Import von huggingface_hub, hf_xet, httpx2, httpcore2 unter backend/src; WhisperModel nur mit Verzeichnis und local_files_only=True; download_model nirgends"
  - "Der TestClient von starlette läuft seit diesem Plan auf httpx2 (starlette bevorzugt es, sobald es installiert ist); Antworttyp in den Tests über conftest.ClientResponse"
metrics:
  duration: "ca. 150 min (Task 2 und Zusatztests; Task 1 lief in einer früheren Sitzung)"
  completed: 2026-11-18
  tasks: 2
  files: 14
---

# Phase 5 Plan 02: Whisper-Laufzeit gepinnt und abgegrenzt Summary

faster-whisper 1.2.1, ctranslate2 4.8.5 und onnxruntime 1.31.1 sind exakt gepinnt, der Lock wächst von 53 auf 69 Pakete genau wie vom Owner freigegeben, und vier Testdateien halten Versionen, Wheel-sha256 beider Architekturen, die Importgrenzen (kein `av`, Whisper nur unter `engine/`), die Marker von httpx2-jsfetch und tzdata und das Netzverbot für den Hub-Code.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Legitimität (Owner-Checkpoint) | kein Commit | keine |
| 2 | Pins, Lock und Grenz-Tests | d200a5d | pyproject.toml, uv.lock, test_lock_wheels.py, test_boundary.py, conftest.py und sechs Testdateien (Typnamen) |
| 2b | Auflage httpx2-jsfetch und tzdata | a7508a8 | test_lock_platforms.py |
| 2c | Netzverbot (Abweichung, siehe unten) | d5720c0 | test_no_hub_network.py, hub_import_probe.py |

## Owner-Freigabe (Task 1)

Die Freigabe wurde dem Ausführer vom Orchestrator übermittelt, nicht vom Owner direkt gelesen. Wortlaut der Übergabe: Task 1 (Paket-Legitimität) ist vom Owner "freigegeben". Dazu die zwei Entscheidungen des Owners vom 18.11.2026:

1. Altersgrenze `exclude-newer` so, dass der ganze 04.11.2026 eingeschlossen ist, plus Ausnahme nur für den bestehenden Dev-Pin webvtt-py. Keine weitere Ausnahme.
2. httpx2-jsfetch 1.0 ist als reiner Lock-Eintrag freigegeben (nur mit Marker `sys_platform == 'emscripten'`), mit der Auflage eines Tests, der rot wird, falls es je ohne diesen Marker im Lock steht oder unter Linux oder Windows installiert wäre.

## Der Lock: vorher und nachher

Frisch im Repo erzeugt mit `uv lock` (uv 0.11.7), nicht aus dem Probelauf kopiert. Vergleich mit dem Stand vorher über das Hilfsskript des Vorlaufs (`lock_tools.py diff`): 53 Pakete vorher, 69 nachher, 16 neu, keines entfernt, keines in der Version geändert. `git diff` des Locks: 246 Zeilen eingefügt, 0 gelöscht.

| Paket | Version im Lock | freigegeben | Abgleich | wohin |
|---|---|---|---|---|
| faster-whisper | 1.2.1 | 1.2.1 | gleich | Image |
| ctranslate2 | 4.8.5 | 4.8.5 | gleich | Image |
| onnxruntime | 1.31.1 | 1.31.1 | gleich | Image |
| av | 19.0.2 | 19.0.2 | gleich | Image (nur Importpflicht) |
| huggingface-hub | 2.4.0 | 2.4.0 | gleich | Image (nur Importpflicht) |
| tokenizers | 0.23.3 | 0.23.3 | gleich | Image |
| httpx2 | 2.16.0 | 2.16.0 | gleich | Image (nur Importpflicht) |
| httpcore2 | 2.16.0 | 2.16.0 | gleich | Image (nur Importpflicht) |
| hf-xet | 1.8.0 | 1.8.0 | gleich | Image (nur Importpflicht) |
| truststore | 0.10.5 | 0.10.5 | gleich | Image |
| tqdm | 4.70.1 | 4.70.1 | gleich | Image |
| fsspec | 2026.9.0 | 2026.9.0 | gleich | Image |
| flatbuffers | 25.12.19 | 25.12.19 | gleich | Image |
| protobuf | 7.36.2 | 7.36.2 | gleich | Image |
| httpx2-jsfetch | 1.0 | 1.0 | gleich | nirgends (Marker emscripten) |
| tzdata | 2026.6 | 2026.6 | gleich | nur Dev unter Windows |

Zu "53 von 53 unverändert", genau gesagt: Die 52 fremden Pakete sind Feld für Feld gleich (Version, Quelle, Wheels, Hashes). Der 53. Eintrag ist das Projekt selbst (`audio-video-search-backend`); er führt jetzt die drei neuen Abhängigkeiten und tzdata in seiner Liste, sonst nichts.

Unterschied zum Probelauf (Variante B): eine Zeile. tzdata trägt im Projekt `==2026.6` statt keiner Versionsangabe, entsprechend steht im Lock `specifier = "==2026.6"`. Die aufgelösten Pakete sind dieselben.

Die sha256 der zehn Linux-Wheels von faster-whisper, ctranslate2, onnxruntime, av, huggingface-hub und tokenizers im Lock stimmen mit der Audit-Datei aus Task 1 (PyPI-JSON, `pypi_audit.json` im Scratchpad der Sitzung) überein; sie stehen jetzt in test_lock_wheels.py.

## Die Tests

**test_lock_wheels.py (erweitert).** Die drei Pins stehen in `APPROVED` (exakt im Projekt, Version im Lock, von PyPI, Wheel-sha256 für amd64 und arm64). Neu `TRANSITIVE` für av, huggingface-hub und tokenizers: gleiche Prüfung, aber ohne Pin im Projekt. Negativkontrolle: ctranslate2 4.9.0, onnxruntime 1.32.0, geänderter Hash, fremde Registry und fehlendes aarch64-Wheel werden gemeldet.

**test_boundary.py (erweitert).** Kein Modul der App importiert `av`; `faster_whisper` und `ctranslate2` nur unter `engine/` (heute nirgends). Positivkontrollen mit Quelltext-Strings in beiden Importformen; Strings, Kommentare, relative Importe und ähnlich beginnende Namen (`avs`, `available`) sind keine Treffer.

**test_lock_platforms.py (neu, Auflage aus Punkt 2).** Läuft den Lock ab wie ein Installer, für Linux amd64, Linux arm64 und Windows, je mit und ohne Dev-Gruppe; Marker wertet `packaging.markers` aus.
- httpx2-jsfetch: jede Kante dorthin muss einen Marker tragen, der in allen drei echten Umgebungen falsch und unter emscripten wahr ist; in keiner echten Umgebung wird es erreicht.
- Zweiter Zeuge ohne TOML-Leser und ohne Marker-Bibliothek: der rohe Text des Locks enthält genau die eine Kante mit `sys_platform == 'emscripten'`.
- Dritter Zeuge: in der Umgebung, in der die Tests laufen (Windows lokal, Linux in der CI), ist httpx2-jsfetch nicht installiert, httpx2 als Kontrolle schon.
- tzdata: ohne Dev-Gruppe nirgends, mit Dev-Gruppe nur unter Windows.
- Alle 16 Pakete stehen in der freigegebenen Version und von PyPI im Lock; das Image (beide Architekturen, ohne Dev) bekommt die 14 Laufzeitpakete und weder httpx2-jsfetch noch tzdata.

**test_no_hub_network.py (neu, Netzverbot).** Drei Regeln:
1. Kein Modul unter `backend/src` importiert `huggingface_hub`, `hf_xet`, `httpx2` oder `httpcore2` (alle Importformen, auch in Funktionen, in try/except, als Text an `import_module` oder `__import__`, als Fabrik-Text `modul:name`).
2. faster_whisper lädt nie: `download_model` wird weder importiert noch benutzt; jeder Aufruf von `WhisperModel` gibt kein Textliteral als Modell an, setzt `local_files_only=True` wörtlich und reicht keines der Download-Argumente (`download_root`, `revision`, `use_auth_token`, `files`), auch nicht per `**` oder Position; die Klasse darf nicht weitergereicht werden (z. B. `functools.partial`).
3. Die letzte Stufe des Dockerfiles endet mit `HF_HUB_OFFLINE=1` und `HF_HUB_DISABLE_TELEMETRY=1` als gültigem Endwert (ein späteres ENV gewinnt), und kein Skript unter `backend/docker/` nennt die Schalter.

## Gegenproben

**Mit anderem Mittel als die Umsetzung.** Die Regeln 1 und 2 lesen den Syntaxbaum. Die Gegenprobe liest keinen Quelltext: `tests/hub_import_probe.py` startet einen frischen Interpreter.
- Modus `imports`: ersetzt `builtins.__import__` und `importlib.import_module`, importiert jedes Modul eines Pakets und schreibt jeden Import eines verbotenen Moduls mit, dessen Importeur im Paket liegt; der Import wird verweigert, das verbotene Modul also nie geladen. An einem absichtlich verletzenden Beispielpaket (sechs Verstöße in sechs Formen, ein sauberes Modul) meldet der Interpreter genau die sechs Module, und die Syntaxbaum-Regel meldet genau dieselben sechs. Am Produkt: 56 Module importiert, keines scheitert, kein Eintrag.
- Modus `calls`: setzt einen Platzhalter für `faster_whisper` ein, ruft die Ladefunktion des Beispiels auf und schreibt mit, wie `WhisperModel` gebaut und ob `download_model` gerufen wurde. Fünf verletzende Beispiele (Modellname, Repo-ID, fehlendes Verzeichnis ohne `local_files_only`, `download_model` direkt und über `faster_whisper.utils`) führen im Interpreter zu einem Laden mit möglichem Netz oder zu einem Download, und die Regel meldet jede dieser Dateien; das saubere Beispiel öffnet ein Verzeichnis und bleibt ohne Befund. Ein weiterer Test hält fest, dass faster-whisper 1.2.1 wirklich so lädt (Verzeichnis oder `download_model`) und dass `download_root` das siebte Argument ist.
- Dockerfile: Die ältere Regel in test_dockerfile.py sucht nur den Text; ein späteres `ENV HF_HUB_OFFLINE=0` lässt sie durch, die neue Regel meldet es (im Test gezeigt).

**Am echten Repo (von Hand, danach zurückgesetzt und per `cmp` geprüft).**

| Eingriff | Ergebnis |
|---|---|
| `import huggingface_hub` in hardware.py | Syntaxbaum-Test rot, Interpreter-Test rot |
| `WhisperModel("large-v3")` in einer Funktion von engine/catch.py | Syntaxbaum-Test rot |
| `import av` und `import ctranslate2` in hardware.py | beide Grenz-Tests rot |
| Marker der Kante zu httpx2-jsfetch im Lock entfernt | 4 Tests rot (mit `uv run` 5, siehe Abweichung 4) |
| `ENV HF_HUB_OFFLINE=0` ans Dockerfile gehängt | neuer Test rot, alter Test in test_dockerfile.py grün |
| ctranslate2 im Lock auf 4.9.0 | test_lock_wheels und test_lock_platforms rot |
| tzdata als Laufzeit-Abhängigkeit in den Lock geschrieben | 2 Tests rot |

## Verification

- `uv run pytest -q tests/test_lock_wheels.py tests/test_boundary.py`: grün; die drei Pins stehen in pyproject.toml; `4.9.0` und `1.32.0` kommen im Lock nicht vor.
- Voller Lauf ohne `PYTHONTZPATH` (Variable leer): 2585 passed, 18 skipped, 4 xfailed (vorher 2516 passed; 69 neue Tests: 4 Grenzen, 2 Lock-Wheels, 11 Lock-Plattformen, 52 Netzverbot). Die Fenster-Tests aus 05-04 laufen unter Windows jetzt mit tzdata aus der Dev-Gruppe.
- `ruff check .` und `ruff format --check .` (145 Dateien), dasselbe über `../scripts` (21 Dateien): grün. pyright basic mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`: 0 errors. vulture: ohne Befund.
- `uv lock --check`: Lock passt zum Projekt (69 Pakete).
- Import-Probe lokal (Windows, `HF_HUB_OFFLINE=1`): faster_whisper 1.2.1, ctranslate2 4.8.5 und onnxruntime 1.31.1 lassen sich importieren, int8 auf CPU vorhanden.
- Nicht gelaufen: Docker (Owner-Regel), also kein Image-Bau; der Linux-Bau mit huggingface-hub 2.x ist weiter ungemessen (STACK.md) und kommt mit der CI nach einem Push. pip-audit läuft nur im Workflow security.yml, lokal nicht.

## Deviations from Plan

### Vom Auftrag verlangte Ergänzungen (über den Plantext hinaus)

**1. Netzverbots-Test (Auftrag Punkt c, Rule 2, T-05-07)**
- Der Plan nennt für T-05-07 nur die Offline-Umgebung im Image, "Import nur unter engine/" und den Netzmitschnitt in Plan 05-21. Neu ist eine eigene, unabhängige Regel mit Gegenprobe: test_no_hub_network.py und hub_import_probe.py (Commit d5720c0). Sie ist strenger als der Plan: `huggingface_hub`, `hf_xet`, `httpx2` und `httpcore2` darf auch `engine/` nicht importieren.
- Bekannte Grenze: Ein Modulname, der erst zur Laufzeit entsteht (`importlib.import_module(name)` mit Variable, wie in `engine/child.py` für die Engine-Fabrik), ist im Syntaxbaum nicht lesbar. Der Standardwert dort ist ein Textliteral und wird geprüft; den Rest deckt der Netzmitschnitt aus Plan 05-21.

**2. Test zur Auflage httpx2-jsfetch, dazu tzdata (Auftrag Punkt b)**
- test_lock_platforms.py (Commit a7508a8). tzdata wurde mit aufgenommen, weil dieselbe Frage gilt (darf nicht ins Image).

**3. Altersgrenze im Projekt (Owner 18.11.2026)**
- `[tool.uv] exclude-newer` und `exclude-newer-package` stehen nicht im Plan; sie setzen die Owner-Entscheidung um. Folge für später: Ein Dependabot- oder Hand-Update auf ein Paket, das nach dem 04.11.2026 hochgeladen wurde, löst nicht mehr auf, bis die Grenze bewusst verschoben wird.

### Auto-fixed Issues

**4. [Rule 1 - eigener Fehler bei der Gegenprobe] httpx2-jsfetch war kurz im lokalen venv installiert**
- **Found during:** Gegenprobe "Marker entfernt"
- **Issue:** Der erste Lauf dieser Gegenprobe nutzte `uv run`; uv hat die Umgebung dabei an den absichtlich veränderten Lock angeglichen und httpx2-jsfetch 1.0 unter Windows installiert. Der Test "nicht installiert, wo die Tests laufen" wurde dadurch echt rot, das Paket war aber für etwa eine Minute im lokalen venv, obwohl es nur als Lock-Eintrag freigegeben ist. Es wurde nichts daraus importiert oder ausgeführt.
- **Fix:** Lock zurückgesetzt, `uv sync --frozen` hat das Paket entfernt (`- httpx2-jsfetch==1.0`), `uv pip list` zeigt es nicht mehr. Die übrigen Lock-Gegenproben liefen danach direkt mit dem Python des venv, ohne `uv run`.
- **Files modified:** keine (nur lokales venv)

**5. [Rule 3 - Blocker] pyright rot durch httpx2 im Testclient**
- **Found during:** Task 2, Gate pyright
- **Issue:** `starlette.testclient` baut seinen Client auf httpx2, sobald das Paket installiert ist (`if TYPE_CHECKING: import httpx2 as httpx`, zur Laufzeit erst httpx2, dann httpx mit Warnung). httpx2 kommt über huggingface-hub. Damit liefert der TestClient `httpx2.Response`; acht Hilfsfunktionen in sechs Testdateien waren mit `httpx.Response` beschriftet (8 Fehler), dazu ein Parametertyp `dict[str, object]` für `params` (1 Fehler).
- **Fix:** `type ClientResponse = httpx2.Response` in tests/conftest.py (ein Typalias wird erst ausgewertet, wenn jemand seinen Wert verlangt; `httpx2` wird nur unter `TYPE_CHECKING` importiert), die Hilfsfunktionen nutzen den Namen; `params: dict[str, int | str]`. Nur Beschriftungen, kein Test wurde gelockert, keine Erwartung geändert.
- **Wichtig für den Owner:** Das ist nicht nur ein Typthema. Die API-Tests mit TestClient laufen seit diesem Plan tatsächlich über httpx2 statt httpx (im Prozess, ASGI-Transport, kein Netz). Alle 2585 Tests sind damit grün. Der Produktcode nutzt weiter nur httpx in nc.py; der Eintrag in `filterwarnings` zur starlette-Warnung greift nicht mehr, schadet aber nicht.
- **Files modified:** tests/conftest.py, test_api_export.py, test_api_routes.py, test_excerpt_states.py, test_handshake.py, test_sample_real_transcript.py, test_search_tiers.py
- **Commit:** d200a5d

**6. [Rule 2 - Konvention] tzdata exakt gepinnt**
- Im Probelauf stand `tzdata; sys_platform == 'win32'` ohne Version. Im Projekt ist jede Abhängigkeit exakt gepinnt, deshalb `tzdata==2026.6; sys_platform == 'win32'`. Aufgelöst wird dasselbe Paket.

**7. `uv lock` statt `uv add`**
- Der Plan nennt `uv add`. Die Pins wurden von Hand in pyproject.toml geschrieben und mit `uv lock` aufgelöst, damit vor dem Vergleich mit der freigegebenen Liste nichts installiert wird. Installiert wurde erst nach dem Abgleich (`uv sync --frozen`).

### Nicht ausgeführt

- Anforderungen RES-06 und RES-07 stehen im Kopf des Plans, sind mit diesem Plan aber nicht erfüllt (RES-06 braucht den Modellbezug aus 05-08 und 05-10, RES-07 die Lizenztexte aus 05-17). Sie wurden in REQUIREMENTS.md bewusst nicht abgehakt.
- STATE.md und ROADMAP.md wurden von Hand nachgeführt, nicht über `gsd-sdk`, weil STATE.md freie deutsche Texte trägt, die die Befehle überschreiben würden.

## Threat Flags

Keine neue Fläche außerhalb des Bedrohungsmodells. Stand der drei Threats dieses Plans:

| Threat | Stand | Beleg |
|---|---|---|
| T-05-SC (Lieferkette) | gemindert | Owner-Freigabe, exakte Pins, Wheel-sha256 beider Architekturen im Lock und in test_lock_wheels.py, Altersgrenze, test_lock_platforms.py |
| T-05-05 (PyAV-Codecs) | gemindert | test_boundary.py: kein Import von `av`; Lizenzhinweis folgt in 05-17 |
| T-05-07 (huggingface-hub ruft das Netz) | gemindert, Rest offen bis 05-21 | Offline-Umgebung im Image als Endwert geprüft, Importverbot und Ladeverbot per Test; der Netzmitschnitt am laufenden Container steht noch aus |

Hinweis für die Sicherheitsprüfung der Phase: hf-xet, httpx2, httpcore2 und truststore liegen als Code im Image (hf-xet mit nativer Bibliothek). Sie werden nur geladen, weil faster_whisper beim Import `huggingface_hub` importiert; aufgerufen wird nichts davon.

## Offene Punkte für den Owner

1. Push: Die drei Commits liegen nur lokal auf main. Die Workflows (python.yml, security.yml mit pip-audit, docker.yml mit dem ersten Linux-Bau samt Whisper-Laufzeit) laufen erst nach einem freigegebenen Push.
2. Testclient auf httpx2 (Abweichung 5): zur Kenntnis oder Einwand.
3. Altersgrenze `exclude-newer` bleibt im Projekt stehen und bremst künftige Updates, bis sie verschoben wird: so gewollt lassen oder nach dem Plan wieder entfernen.
4. httpx2-jsfetch war durch die Gegenprobe kurz lokal installiert (Abweichung 4) und ist wieder entfernt.

## Self-Check: PASSED

- Dateien vorhanden: backend/tests/test_lock_platforms.py, backend/tests/test_no_hub_network.py, backend/tests/hub_import_probe.py, backend/pyproject.toml, backend/uv.lock.
- Commits vorhanden: d200a5d, a7508a8, d5720c0.
