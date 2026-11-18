---
phase: 05-ressourcen-profile-und-modellbezug
plan: 01
subsystem: backend/ressourcen
tags: [RES-01, RES-02, wave-0, D-05-09, messung, parakeet, T-05-01, T-05-02, T-05-03, T-05-04]
requires: []
provides:
  - "ci/measure/peak_probe.py: Sonde (EngineWorker mit echtem Parakeet auf 10 min Sprache plus Vorschau, ru_maxrss der Kinder und VmHWM als JSON)"
  - ".github/workflows/docker.yml: Job peak-measure auf amd64 und arm64, Artefakte peak-amd64 und peak-arm64"
  - "docs/measurements/parakeet-peak-2026-11.json: Rohdaten beider Architekturen mit run_url und sha, dazu der frühere Lauf als zweite Messung (earlier_run)"
  - "backend/src/audio_video_search_backend/measured.py: PARAKEET_PEAK_BYTES (amd64, arm64), MEASURED_RUN"
affects: [05-12, 05-17, 05-20]
tech-stack:
  added: []
  patterns:
    - "Messwert nur aus dem CI-Artefakt, Konstante und Datensatz per Test gleich gehalten"
    - "Sonde außerhalb des Build-Kontexts, im Image nur eingehängt (read only)"
key-files:
  created:
    - ci/measure/peak_probe.py
    - docs/measurements/parakeet-peak-2026-11.json
    - backend/src/audio_video_search_backend/measured.py
    - backend/tests/test_peak_measurement.py
  modified:
    - .github/workflows/docker.yml
decisions:
  - "Quelle der Konstanten ist der Lauf zum aktuellen Stand 106cc67 (44304526791); der Lauf zu 53221a5 (44297803266) steht als zweite Messung im Datensatz, fließt aber nicht in measured.py ein"
  - "PARAKEET_PEAK_BYTES je Architektur = max(ru_maxrss_kib, vmhwm_kib) x 1024 eines Laufs, wie im Plan; kein Maximum über beide Läufe"
  - "measured.py nennt die Sonde nicht beim Dateinamen, weil der Test zu T-05-01 das Wort unter backend/ verbietet"
metrics:
  duration: "Task 1 ca. 30 min (frühere Sitzung), Task 3 ca. 45 min"
  completed: 2026-11-18
  tasks: 3
  files: 5
---

# Phase 5 Plan 01: Linux-Spitze von Parakeet gemessen Summary

Die Linux-Spitze des Parakeet-Kindes ist in der CI auf amd64 und arm64 auf einem Stück von 10 min Sprache plus 60 s Vorschau gemessen: 1089,46 MiB (amd64) und 1124,31 MiB (arm64). Die Rohdaten stehen mit Lauf und Commit im Repo, die Werte als Konstanten in `measured.py`, und ein Test hält beide gleich.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Sonde und CI-Schritt auf amd64 und arm64 | bd35501 | ci/measure/peak_probe.py, .github/workflows/docker.yml, backend/tests/test_peak_measurement.py |
| 2 | Owner-Freigabe für den Push auf phase-05 | kein Commit | approvals/push-53221a5..., approvals/push-106cc67... (nicht versioniert) |
| 3 | Messung abholen, Messsatz und measured.py | 9d0068b | docs/measurements/parakeet-peak-2026-11.json, backend/src/audio_video_search_backend/measured.py, backend/tests/test_peak_measurement.py |

Der Push selbst lief außerhalb dieser Sitzung (zuerst 53221a5, dann 106cc67, beide auf `phase-05`); in dieser Sitzung wurde nichts gepusht.

## Messwerte

Quelle der Konstanten: Workflow "Multi-arch image", Lauf 44304526791, Commit 106cc6781d4a2a25a993d482ec5c2e050b2b6550, Branch phase-05.
Lauf-URL: https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/44304526791

| Architektur | Job | Artefakt | ru_maxrss | VmHWM | Spitze (Maximum) | Bytes | Wörter | Sekunden |
|---|---|---|---|---|---|---|---|---|
| amd64 (x86_64) | 134803563017 | peak-amd64/peak-amd64.json | 1 115 276 KiB | 1 115 608 KiB | 1089,46 MiB | 1 142 382 592 | 1180 | 40,5 |
| arm64 (aarch64) | 134803563113 | peak-arm64/peak-arm64.json | 1 151 040 KiB | 1 151 296 KiB | 1124,31 MiB | 1 178 927 104 | 1180 | 35,8 |

Dieselben Zeilen stehen im Job-Log (Schritt "Run the probe in the pushed image"): amd64 Zeile 267, arm64 Zeile 272 des abgerufenen Logs. Gemessen wurde am Image, das dieser Lauf gebaut hat: amd64 `sha256:32830fd2...65ad`, arm64 `sha256:c6472ef0...dd1d`.

Zweite Messung: Lauf 44297803266, Commit 53221a5db3d5ec134a18cc8854f0d1e328c879cd (Image noch ohne die Whisper-Laufzeit aus 05-02).
Lauf-URL: https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/44297803266

| Architektur | Job | ru_maxrss | VmHWM | Spitze | Abstand zum Lauf 106cc67 |
|---|---|---|---|---|---|
| amd64 | 134779934619 | 1 119 792 KiB | 1 120 192 KiB | 1093,94 MiB | +4,48 MiB (+0,41 %) |
| arm64 | 134779934513 | 1 202 960 KiB | 1 203 264 KiB | 1175,06 MiB | +50,75 MiB (+4,51 %) |

## Plausibilität

- Beide Architekturen in beiden Läufen vorhanden, je `code` ok und 1180 Wörter (gleich über Architekturen und Läufe: dieselbe Sprache wurde erkannt).
- Einheiten: `ru_maxrss` unter Linux in KiB, `VmHWM` aus `/proc/<pid>/status` in kB (= KiB). Beide Felder liegen je Lauf höchstens 400 KiB auseinander, zwei unabhängige Zähler des Kernels bestätigen sich.
- `threads_env`: OMP_NUM_THREADS 2, kein OMP_THREAD_LIMIT. Container ohne Speichergrenze.
- Größenordnung: 1,06 bis 1,15 GiB unter Linux gegenüber 1,2 bis 1,7 GB unter Windows (Spike 3, `peak_wset`). Die Linux-Spitze liegt darunter, wie in der Recherche erwartet.
- Streuung: amd64 0,4 %, arm64 4,5 % zwischen den zwei Läufen. Ob der Abstand auf arm64 Zufall des Laufs oder Folge des anderen Images ist, lässt sich mit je einer Messung nicht sagen.
- Gegenprobe ohne den Test: ein eigenes Skript im Scratchpad hat die vier heruntergeladenen Artefakte Feld für Feld mit dem Datensatz verglichen (viermal identisch) und die Bytes neu gerechnet.
- Negativkontrolle des Tests: Konstante um 1 Byte geändert, danach Datensatz um 1 KiB geändert, jeweils `test_the_constants_are_the_record` rot; beides zurückgesetzt und per `cmp` geprüft.

Grenzen der Messung (nicht geschönt, nur benannt):

- Je Lauf und Architektur genau eine Messung auf genau einem Stück; der Plan sieht keine Wiederholung im selben Lauf vor.
- Der Sprachclip ist ein deutscher Clip, auf die Stücklänge wiederholt. Andere Sprache, Musik oder lange Fenster sind nicht gemessen.
- Auf arm64 meldet `fetch_speech.py` eine andere sha256 der erzeugten WAV als erwartet (Warnung "other ffmpeg version?"); die Quelle (member sha256) stimmt. Die Wortzahl ist trotzdem gleich.
- GitHub-Runner sind kein Pi 5 und kein N100.

## Befund für Plan 05-12 (2 GiB mit Reserve)

Plan 05-12 rechnet den Parakeet-Bedarf als Maximum beider Architekturen x 1,15, auf MiB aufgerundet, plus 512 MiB Reserve.

| Grundlage | Maximum | x 1,15 aufgerundet | plus Reserve 512 MiB | Rest bis 2048 MiB |
|---|---|---|---|---|
| Lauf 106cc67 (in measured.py) | 1124,31 MiB | 1293 MiB | 1805 MiB | 243 MiB |
| Lauf 53221a5 (nur zum Vergleich) | 1175,06 MiB | 1352 MiB | 1864 MiB | 184 MiB |

- Rechnerisch ist 2 GiB mit Reserve erreichbar; mit dem alten Bedarf von 1700 MiB (Windows) war es das nicht (2212 MiB).
- Es bleibt nur dann Platz, wenn `anon` des Hauptprozesses unter dem Rest liegt (243 MiB, mit dem höheren Wert 184 MiB). `anon` des Hauptprozesses ist hier nicht gemessen; das zeigt erst der CI-Nachweis bei 2 GiB aus der Phase.
- Der Zuschlag von 15 % deckt die beobachtete Streuung von 4,5 % auf arm64.

## Verification

- `uv run pytest -q tests/test_peak_measurement.py tests/test_workflows.py tests/test_workflow_pins.py`: 77 passed.
- Voller Lauf: 2589 passed, 18 skipped, 4 xfailed (vorher 2585 passed; vier neue Tests).
- `ruff check` und `ruff format --check` über `.` und `../scripts` (167 Dateien): grün. pyright basic mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`: 0 errors. vulture: ohne Befund. `uv lock --check`: 69 Pakete, passt.
- Akzeptanz: der Datensatz enthält `amd64` und `arm64` mit `"code": "ok"` und `run_url`; `PARAKEET_PEAK_BYTES` steht in measured.py; `git ls-remote origin refs/heads/main` ist 2f998f9 und gleich `origin/main` (main unberührt).
- CI zu 106cc67: Multi-arch image 44304526791, Python gates 44304523518, Discovery acceptance 44304523200, Deploy through HaRP 44304523475 (laut Übergabe grün; in dieser Sitzung selbst geprüft wurde nur der Lauf 44304526791: success, beide Messjobs success, der Job merge übersprungen wie für einen Phasen-Branch vorgesehen).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - eigener Fehler] measured.py nannte die Sonde beim Dateinamen**
- **Found during:** Task 3, voller Testlauf
- **Issue:** Der Docstring von measured.py enthielt den Dateinamen der Sonde; `test_the_probe_lives_under_ci_only` (T-05-01) verbietet das Wort in jeder Datei unter `backend/` und wurde rot.
- **Fix:** Der Docstring nennt jetzt "the probe under ci/measure". Der Test blieb unverändert.
- **Commit:** 9d0068b (vor dem Commit behoben)

### Ergänzungen über den Plantext hinaus

**2. Zweite Messung im Datensatz**
- Der Plan verlangt "beide JSON-Objekte unverändert plus run_url und sha". Zusätzlich steht der frühere Lauf (53221a5) unter `earlier_run` im selben Datensatz, damit der Vergleich nachprüfbar im Repo liegt und der höhere arm64-Wert nicht verschwindet. Die Konstanten kommen nur aus dem Lauf 106cc67.

**3. Zwei zusätzliche Tests**
- Der Datensatz trägt nur die sieben Felder der Sonde (kein Wort des Transkripts, T-05-04), und die zweite Messung ist ein anderer Lauf und ein anderer Commit mit gleicher Wortzahl.

**4. Ablauf von Task 3**
- Push und Beobachtung des Laufs waren schon erledigt; kein `gh run watch`. Abgerufen wurden die Metadaten beider Läufe, die vier Artefakte und die zwei Job-Logs des Laufs 106cc67 (lesend).

### Nicht ausgeführt

- RES-01 und RES-02 stehen im Kopf des Plans, sind mit der Messung allein aber nicht erfüllt (Profilvorwahl und Wächter kommen mit 05-12 und folgenden). In REQUIREMENTS.md bewusst nicht abgehakt.
- STATE.md und ROADMAP.md von Hand nachgeführt, nicht über `gsd-sdk`, wie in 05-02 (freie deutsche Texte in STATE.md).

## Zusatzprüfung: pip-audit über den Lock

security.yml (CodeQL, REUSE, pip-audit) läuft nur bei Push auf main, bei Pull Requests und per Zeitplan, also nicht auf phase-05. Die in 05-02 neu gelockten Pakete sind dort noch nicht gelaufen.

Lokal nachgestellt mit den zwei Befehlen aus security.yml, Requirements-Datei im Scratchpad, nichts ins Projekt installiert (pip-audit lief über `uvx` im Werkzeug-Cache von uv):

- `uv export --frozen --format requirements-txt --no-emit-project --no-dev`: 54 Einträge.
- `uvx pip-audit --strict --disable-pip -r <datei>`: "No known vulnerabilities found", Exit 0.
- Geprüft wurden 52 der 54 Einträge. Nicht geprüft, weil ihr Marker unter Windows falsch ist: uvloop 0.23.0 (nur Linux, kein neues Paket) und httpx2-jsfetch 1.0 (nur emscripten; auch der Linux-Runner der CI überspringt es).
- Von den 16 neuen Paketen aus 05-02 sind damit 14 geprüft (alle, die ins Image kommen). httpx2-jsfetch wird von diesem Aufruf nie geprüft, tzdata ist nur Dev und steht nicht im Laufzeit-Export.
- Das ersetzt den CI-Lauf nicht: CodeQL und REUSE liefen lokal nicht, und uvloop fehlt.

## Threat Flags

Keine neue Fläche außerhalb des Bedrohungsmodells.

| Threat | Stand | Beleg |
|---|---|---|
| T-05-01 (Sonde im Image) | gemindert | Sonde nur unter ci/, Test verbietet sie unter backend/ (hat in dieser Sitzung gegriffen) |
| T-05-02 (Push ohne Freigabe) | gemindert | Freigabedateien je SHA vorhanden; in dieser Sitzung kein Push |
| T-05-03 (geschönter Messwert) | gemindert | Werte nur aus den CI-Artefakten, Datensatz mit Lauf-URL und SHA, Test hält Konstante und Datensatz gleich, der höhere Wert des früheren Laufs steht sichtbar daneben |
| T-05-04 (Transkriptwörter im Artefakt) | gemindert | Artefakt und Datensatz tragen nur die Wortzahl; Test über die Feldnamen |

## Offene Punkte für den Owner

1. arm64 lag im früheren Lauf 50,75 MiB (4,5 %) höher als im Lauf, der in measured.py steht. Plan 05-12 rechnet mit 15 % Zuschlag, das deckt den Abstand. Falls der Bedarf lieber auf dem höchsten je gemessenen Wert stehen soll: Entscheidung vor 05-12, dann wäre die Regel "Maximum über alle Läufe im Datensatz".
2. Der Commit 9d0068b und dieser Abschluss liegen nur lokal. Ein Push auf phase-05 braucht eine neue Freigabe.
3. pip-audit lief nur lokal und ohne uvloop; der echte Lauf von security.yml (auch CodeQL und REUSE) kommt erst mit einem Pull Request oder dem Merge nach main.
4. Die Artefakte der CI verfallen nach 30 Tagen; die Rohdaten stehen deshalb im Repo.

## Self-Check: PASSED

- Dateien vorhanden: ci/measure/peak_probe.py, docs/measurements/parakeet-peak-2026-11.json, backend/src/audio_video_search_backend/measured.py, backend/tests/test_peak_measurement.py.
- Commits vorhanden: bd35501, 9d0068b.
