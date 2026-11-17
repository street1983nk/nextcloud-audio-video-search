---
phase: 03-vorschau-transkripte-in-der-suche
plan: 02
subsystem: messbarkeit-kernweg
tags: [research-skripte, pfad-gate, fleurs, sha256, playwright, kernweg]
requires: []
provides:
  - "ci/media/fetch_speech.py: speech_de.wav und speech_tr.wav mit festem sha256 (für 03-10, 03-15, 03-17, 03-18)"
  - "EXPECTED_WORD dinosaurier für Abnahme und Kernweg"
  - "ci/playwright/preview.spec.ts: Kernweg @preview hinter AVS_PREVIEW_E2E=1 (scharf ab 03-18)"
  - "Messskripte scripts/research/phase3 ohne lokale Pfade, ffmpeg über --ffmpeg/AVS_FFMPEG/PATH"
affects: [03-10, 03-15, 03-17, 03-18]
tech-stack:
  added: []
  patterns:
    - "Pfad-Gate local_paths(root) mit Positivkontrolle auf veränderter Kopie"
    - "Tar-Strom mit genau einem benannten Mitglied, sha256-Pin, kein extractall"
key-files:
  created:
    - ci/media/fetch_speech.py
    - backend/tests/test_fetch_speech.py
    - backend/tests/test_research_scripts.py
    - ci/playwright/preview.spec.ts
  modified:
    - scripts/research/phase3/*.py (alle zwölf)
decisions:
  - "Gate-Muster mit Lookbehind (?<![a-z]) vor dem Laufwerksbuchstaben, sonst trifft jedes https://"
  - "Kernweg läuft nur im Projekt w1280-light (ein Upload pro Lauf statt sechs)"
  - "WAV-Wandlung bitexact ohne Metadaten, damit der WAV-sha256 weniger von der ffmpeg-Version abhängt"
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-14
  tasks: 3
  files: 16
---

# Phase 3 Plan 02: Messbarkeit und Kernweg Summary

Messskripte ohne lokale Pfade (ffmpeg aus `--ffmpeg`, `AVS_FFMPEG` oder `PATH`, sonst Exit 2) mit Pfad-Gate, zwei gepinnte FLEURS-Clips (DE, TR) mit sha256 je Tar-Mitglied und ein fehlschlagender Playwright-Kernweg `@preview` hinter `AVS_PREVIEW_E2E=1`.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 | 04ef0b6 | chore(03-02): Messskripte ohne lokale Pfade, Pfad-Gate |
| 2 | 818ecdc | test(03-02): gepinnte Sprachclips für Modell- und Abnahmetests |
| 3 | 9bfbe8a | test(03-02): Kernweg der Phase 3 als Playwright-Vertrag |

## Pins (ci/media/fetch_speech.py)

Quelle: Hugging Face `google/fleurs`, Lizenz CC-BY-4.0 (Namensnennung "FLEURS, Google, CC-BY-4.0").
Revision: `70bb2e84b976b7e960aa89f1c648e09c59f894dd` (API am 14.11.2026, lastModified 2026-05-15).

| Clip | Tar | Mitglied (unter `test/`) | Mitglied-sha256 (verbindlich) | WAV-sha256 (16 kHz mono s16, ffmpeg 8.1.1 Gyan) | Dauer |
|------|-----|--------------------------|-------------------------------|---------------------------|-------|
| speech_de.wav | data/de_de/audio/test.tar.gz | 10009182821551087671.wav | 90d0470adf728783e98cc8dddd51e2c2cbf0d6bf360da65f7d2ac5c3e65876aa | 97d77a9d323b903dcc10c608521fa07fb78766d4b65d016ba620caae442dece9 | 11,16 s |
| speech_tr.wav | data/tr_tr/audio/test.tar.gz | 10000377651956138413.wav | e2efd9f3ce2fcc9e191126dcded8e674233a9ce83a9c2132541700e8f1bd57c3 | bee83b904f9c506159b0d026b66e7372839b63bc76591341c62ea73601d3dd31 | 14,16 s |

- `EXPECTED_WORD = "dinosaurier"`
- `EXPECTED_TEXT = "Er griff auch alles an, was ins Wasser kam; selbst ein großer Dinosaurier wie der T. Rex war ihm nicht gewachsen."` (Spalte raw_transcription der FLEURS-TSV)
- Beide Mitglieder liegen am Anfang ihres Archivs (Position 2 bzw. 1), der Strom bricht danach ab; geladen werden nur wenige MB statt 569 MB.

Echtlauf (lokal, leerer Scratch-Ordner, Dateien danach gelöscht):

```
speech_de.wav: member 10009182821551087671.wav sha256 90d0470a...76aa ok, wav sha256 97d77a9d...dece9
speech_tr.wav: member 10000377651956138413.wav sha256 e2efd9f3...57c3 ok, wav sha256 bee83b90...dd31
source: FLEURS, Google, CC-BY-4.0, google/fleurs@70bb2e84b976b7e960aa89f1c648e09c59f894dd
exit=0
```

Gegenproben: ffprobe meldet s16, 16000 Hz, 1 Kanal, 11,16 s bzw. 14,16 s; `certutil -hashfile` liefert dieselben WAV-sha256. Kopie mit um ein Zeichen geändertem Mitglied-sha256: Exit 3, Meldung mit beiden Werten, Ausgabeordner leer.

## Verifikation

- `ruff check . ../scripts ../ci/media`: grün; `ruff format --check . ../scripts ../ci/media`: 92 Dateien formatiert
- `pyright` (latest, inkl. `../scripts`): 0 Fehler; `pyright ../ci/media/fetch_speech.py`: 0 Fehler
- `vulture` (inkl. `../ci/media`): grün
- `pytest -q`: 1064 passed (vorher 1023; neu 24 in test_research_scripts.py, 17 in test_fetch_speech.py)
- Pfad-Gate Positivkontrollen: eingefügte Zeile `FF = "C:/tools/ffmpeg.exe"` gibt genau `fetch_corpus.py:21`; je ein Treffer für `D:\`, `/Users/`, `AppData`, `WinGet`; https-Adresse kein Treffer. Gegenprobe auf dem HEAD-Stand vor Task 1: `phase3/build_extra.py:13`, `phase3/fetch_corpus.py:15`.
- `python -I fetch_corpus.py` mit leerem PATH, ohne AVS_FFMPEG: `ffmpeg not found: pass --ffmpeg or set AVS_FFMPEG (tried 'ffmpeg')`, Exit 2; Kontrolle mit ffmpeg auf PATH: kommt bis zur Usage-Meldung (Exit 2 wegen fehlendem Ordner).
- Mutationsprobe `../evil`: eine Kopie von `pick_member` mit `extractall` wird vom Test gefangen.
- `git ls-files | grep -Ei "\.(wav|mp3|ogg|opus|flac|m4a)$"`: leer.
- `npx playwright test --list --grep @preview`: 18 Einträge (3 Tests x 6 Rasterprojekte), ohne Übersetzungsfehler; ohne Flag alle übersprungen; mit `AVS_PREVIEW_E2E=1` und ohne Umgebung schlägt der erste Test mit "AVS_SPEECH_WORD is not set" fehl (Vertrag ist scharf); in anderen Projekten übersprungen. `waitForTimeout`: keine Zeile.
- Keine U+2013/U+2014 in neuen und geänderten Dateien (Prüfung mit Kontrolle).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Gate-Muster aus dem Plan trifft jede https-Adresse**
- **Found during:** Task 1
- **Issue:** `(?i)([a-z]:[\\/]|...)` trifft `s:/` in `https://`; damit wäre Test 1 nie grün (fetch_corpus.py enthält 13 URLs). Das Akzeptanz-grep `[a-z]:[\\/]` trifft dieselben URLs.
- **Fix:** Lookbehind `(?<![a-z])` vor dem Laufwerksbuchstaben; eigener Test, dass eine https-Adresse kein Treffer ist. Akzeptanz-grep ohne URL-Zeilen geprüft: leer.
- **Commit:** 04ef0b6

**2. [Rule 3 - Blocking] ruff und pyright waren auf scripts/research schon vor dem Plan rot**
- **Found during:** Task 1 (Baseline auf HEAD: `ruff check ../scripts` 29 Fehler, 12 Dateien unformatiert, `pyright` 11 Fehler)
- **Fix:** `ruff format` (verhaltensneutral), `zip(..., strict=False)` (bisheriges Verhalten), `l` in `lpv` umbenannt, `assert` in `measure.read_pcm` durch `ValueError` ersetzt, `# noqa: S603/S310` mit Begründung, `fetch_commons_retry.py` entflochten. Für numpy, sherpa_onnx, py3langid (nur Messumgebung) je Datei `# pyright: reportMissingImports=false` mit Kommentar; nach Plan 03-10 sind die Pakete gepinnt und das Pragma kann weg.
- **Commit:** 04ef0b6

**3. [Rule 3 - Blocking] fetch_corpus.py hatte Seiteneffekte beim Laden**
- **Fix:** Ordner und ffmpeg-Auswahl in `open_corpus(argv)`, Zustand in `Corpus`; `fetch_commons_retry.py` und `build_extra.py` laden `fetch_corpus.py` per `spec_from_file_location` (wegen `-I` kein Import über sys.path) und nutzen dieselbe Auswahl, statt sie zu kopieren.

**4. Erweiterung: Ersatzumlaute auch in analyze.py, evalrule.py, grid.py, verdict.py**
- Der Auftrag nennt alle zwölf Skripte, die Dateiliste nur sieben. Nur Docstrings und Kommentare geändert; Ausgabestrings in confdist.py ("nicht unterstuetzt", "Woerter") bleiben, weil Code.

**5. Tar-Mitglieder liegen unter `test/`**
- Der Plan verlangt Mitgliedsnamen ohne `/`. Die Konstante hält den reinen Dateinamen, `TAR_MEMBER_DIR = "test/"` den festen Ordner; `pick_member` vergleicht den vollen Namen exakt und weist Namen mit `/`, `\` oder `..` ab.

**6. Zusätze zur Härtung (Rule 2)**
- Host-Allowlist (`huggingface.co`, `*.hf.co`, `*.huggingface.co`, nur https) vor dem Abruf und nach der Weiterleitung; ffmpeg mit `-map_metadata -1 -fflags +bitexact -flags:a +bitexact`.
- Kernweg nur im Projekt `w1280-light`, sonst lädt jeder der sechs Rasterprojekte erneut hoch. Der dritte Test prüft zusätzlich, dass alice den Clip weiter findet (Gegenprobe für die leere Liste bei mallory).

## Offene Punkte

- System-Python 3.13.1 unter `AppData/Local/Programs/Python/Python313` ist lokal defekt (`ImportError: cannot import name '_specializations' from 'opcode'`); alle Läufe mit dem uv-Python 3.13.13 der backend-.venv. Nicht Teil des Repos.
- preview.spec.ts ist nicht per tsc typgeprüft (kein TypeScript im Repo); Playwright übersetzt sie fehlerfrei.
- CI muss ab Plan 03-18 `AVS_SPEECH_DE`, `AVS_SPEECH_WORD=dinosaurier` und `AVS_PREVIEW_E2E=1` setzen und fetch_speech.py vorher ausführen. Der Rasterlauf in deploy-harp.yml (`--grep-invert ...`) nimmt @preview heute mit, alle drei Tests werden ohne Flag übersprungen.
- WAV-sha256 ist mit ffmpeg 8.1.1 (Gyan, Windows) gemessen; weicht er mit dem BtbN-LGPL-Build in CI ab, gibt es nur eine Warnung (Mitglied-sha256 bleibt verbindlich). Wert dann aus dem CI-Log übernehmen.

## Known Stubs

Keine. preview.spec.ts schlägt bewusst fehl, bis Plan 03-18 die Phase fertigstellt (Vertrag, kein Stub).

## Threat Flags

Keine neue Fläche außerhalb des Threat-Modells (T-03-03 bis T-03-06 umgesetzt).

## Self-Check: PASSED

- FOUND: ci/media/fetch_speech.py, backend/tests/test_fetch_speech.py, backend/tests/test_research_scripts.py, ci/playwright/preview.spec.ts
- FOUND: Commits 04ef0b6, 818ecdc, 9bfbe8a
