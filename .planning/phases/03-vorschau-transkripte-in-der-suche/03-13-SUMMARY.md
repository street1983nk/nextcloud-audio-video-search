---
phase: 03-vorschau-transkripte-in-der-suche
plan: 13
subsystem: worker
tags: [preview, chunks, resume, yield, vad, verdict, d-03-22, index-load, tdd]
requires: ["03-05", "03-09", "03-10", "03-11"]
provides:
  - "nc.fetch_media_file: Kontextmanager, Temp-Datei mit Zufallsnamen ohne Endung bis zum Ende des Blocks"
  - "worker/preview.py: Preview (prepare, run_once, run_forever), PreviewOutcome, PreviewStep, take, preview_dir, run_forever"
  - "Store.media_of_file_sha256, Store.commit_chunk(..., second_pass=)"
  - "engine/catch.py: SPEECH_ONLY_MS 3000, SPEECH_ONLY_SHARE 0.5 (D-03-22)"
  - "ci/media/fetch_speech.py: SPEECH_ES (FLEURS es_419), AVS_TEST_SPEECH_ES in python.yml"
  - "scripts/research/phase3/verdict22.py, eval22.py"
affects: [03-15, 03-17, 03-18]
tech-stack:
  added: []
  patterns:
    - "Gefälschte Engine antwortet aus einer Tabelle in Medienzeit, auf den dekodierten Bereich zugeschnitten (wie die VAD)"
    - "Echter Download über nc.fetch_media_file mit MockTransport im Worker-Test"
key-files:
  created:
    - backend/src/audio_video_search_backend/worker/preview.py
    - backend/tests/test_fetch_keep.py
    - backend/tests/test_preview_worker.py
    - backend/tests/test_preview_index_load.py
    - scripts/research/phase3/verdict22.py
    - scripts/research/phase3/eval22.py
  modified:
    - backend/src/audio_video_search_backend/nc.py
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/engine/catch.py
    - backend/tests/test_catch_rule.py
    - backend/tests/test_engine_constants.py
    - backend/tests/test_engine_model.py
    - backend/tests/test_fetch_speech.py
    - ci/media/fetch_speech.py
    - .github/workflows/python.yml
decisions:
  - "Fenster, die im Kontext beginnen und über next_start_ms reichen, behalten ihre Wörter ab next_start_ms (sonst Lücke, wenn die VAD des Folgestücks den Rest im Kontext mit der folgenden Sprache zusammenfasst)"
  - "Erreicht der dekodierte Bereich das Dateiende, nimmt das Stück alles bis zum Ende (kein Zwergstück für die letzte Sekunde)"
  - "Andere Bytes als der Inhalts-Schlüssel: Job wartet 300 s ohne Versuchszählung (statt yield_preview), sonst Download-Schleife"
  - "commit_chunk False: finish_preview(transcript), Job beendet und nie erneut versucht (03-09)"
  - "Zweiter Durchgang: Wörter und Verwerfungen zählen dazu, die VAD-Sprache bleibt die des ersten Durchgangs"
  - "Eigener Unterordner tmp/preview, prepare leert ihn ganz; die Capture räumt nur ihre .part-Dateien in tmp"
  - "D-03-22 ohne Wortzahl-Bedingung: gemessen trennt die Wortzahl nicht, VAD-Sprache und Anteil trennen"
  - "CONFIG_VERSION bleibt 1: die neue Regel ändert kein Wort eines Transkripts, nur den Grund einer Datei ohne Transkript"
metrics:
  duration: "ca. 4 h (davon ca. 1 h Korpus laden und messen)"
  completed: 2026-11-14
  tasks: 3
  files: 15
---

# Phase 3 Plan 13: Vorschau-Worker Summary

Der Vorschau-Worker rechnet jede erfasste Datei in Stücken von 10 min mit Kontext und Vorlauf, macht jedes Stück sofort findbar, setzt nach Abbruch und nach Abgabe an ein Ereignis am letzten Stück fort, gibt ehrliche Gründe statt Fehler und trennt seit D-03-22 "keine Sprache" von "Sprache nicht unterstützt" mit gemessenen Schwellen (VAD-Sprache ab 3 s, Anteil ab 50 %, kein behaltenes Wort).

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 RED | fa528c8 | test(03-13): Download, der die Temp-Datei für ffmpeg behält (rot) |
| 1 GREEN | 6886346 | feat(03-13): Download, der die Temp-Datei für ffmpeg behält |
| 2 RED | b52ea53 | test(03-13): Vorschau-Worker-Verhalten (rot) |
| 2 Testkorrektur | 0359b35 | test(03-13): Vorschau-Worker-Tests nachgeschärft (Importfolge, Positivkontrolle mit Wort, usefixtures) |
| 2 GREEN | 2ac0521 | feat(03-13): Vorschau-Worker in Stücken mit Fortsetzen und Unterbrechen |
| 3 | f90a4a6 | test(03-13): Index-Last je Stück für 12-h-Dateien gemessen |
| D-03-22 RED | c04dbe0 | test(03-13): Dateiurteil bei viel Sprache ohne behaltenes Wort (D-03-22, rot) |
| D-03-22 GREEN | 253b213 | feat(03-13): Sprache nicht unterstützt bei viel Sprache ohne behaltenes Wort (D-03-22) |
| D-03-22 Skripte | c48988c | chore(03-13): Messskripte für das Dateiurteil nach D-03-22 |
| D-03-22 ES-Clip | 8056e8d | test(03-13): FLEURS-Clip ES gepinnt, Modelltest mit Dateiurteil für DE, ES und TR |

Alle nur lokal, Autor und Committer street1983nk <k.cherif@outlook.de>, nichts gepusht.

## Task 1: fetch_media_file

`async with nc.fetch_media_file(file_id, user_id, directory, expected_size, cap) as (result, path)`: dieselben Prüfungen wie fetch_to_tempfile (Platz vor dem Request, Ablehnungscodes, genaue Größe, Frist), Strom in `<token_hex(16)>.part`, nach vollständigem Lauf `os.replace` auf den Namen ohne Endung, Löschen beider Namen im finally. fetch_to_tempfile unverändert. 18 Tests (u. a. Datei weg nach Ausnahme, nach Abbruch, 6 Ablehnungscodes, Größenabweichung, Platzgrenze genau und knapp darunter, Frist, abgebrochener Download hinterlässt nur `.part`). Mutationen: ohne Löschen des Zielnamens 3 rot, Name mit `.bin` 1 rot.

D-03-20 nachgeprüft: Zufallsbytes, Text und Nullbytes ohne Endung ergeben in ffprobe 8.1.1 "Invalid data found" (Exit 1), also `damaged`; der Demuxer "bin" greift ohne Endung nicht. Als Test mit echtem ffprobe (`test_garbage_bytes_are_damaged_with_the_real_ffprobe`).

## Task 2: worker/preview.py

- Ablauf je Schritt: Claim, Quelle, Platzprüfung (sonst `defer_preview(disk_full, now + 300)`, kein Request), Download, sha256 gegen `media_of_file_sha256`, Probe, Höchstdauer, Engine-Start im Thread, Stück-Schleife, zweiter Durchgang, Urteil, Engine-Stopp im finally. Store nur über `run_locked` in kurzen Aufrufen; `decode` und `ask` laufen in `asyncio.to_thread`, nie im Lock.
- Stück: dekodiert `[start - 1 s, start + 600 s + 60 s)`, `offset_ms` = Dekodierbeginn, übernimmt Fenster mit Beginn vor `start + 600 s`, die über `start` reichen; `next_start_ms` = Ende des letzten übernommenen Fensters, sonst `start + 600 s`. Erreicht der Bereich das Dateiende, nimmt das Stück den Rest.
- Gründe: Probe- und Decode-Gründe als skip, `too_long` mit duration_ms, ohne bekannte Dauer und ohne Samples ab 0 `damaged` (D-03-20), `engine_failed` nach drei Fehlern (TIMEOUT, OUT_OF_MEMORY, CRASHED), NO_ROOM (beim Start und mitten im Job) wartet 60 s ohne Versuch, abgelehnter Download wartet 300 s ohne Versuch.
- 43 Tests (37 Funktionen) mit echter state.db, echtem fetch_media_file hinter MockTransport, gefälschter Engine aus einer Tabelle in Medienzeit; ein Test mit echtem ffprobe/ffmpeg auf einer erzeugten 25-min-WAV (drei Stücke, PCM-Längen 660 000 / 661 000 / Rest).
- RED: ModuleNotFoundError beim Sammeln. Mutationsproben gegen preview.py, jede gefangen: ohne Abgabe (2 rot), Kontextfenster ganz verworfen wie im Plantext (1), offset ohne Kontext (5), second_pass nicht gespeichert (2), zweiter Durchgang immer (1), ohne sha256-Prüfung (1), ohne Engine-Stopp (5), Versuch nicht gezählt (3), ohne Höchstdauer (1), ohne Ende-Regel (6), alte Wörter behalten (1), STALE ohne Beenden (1), ohne models_ready-Sperre (1).

## Task 3: Index-Last (A8)

`tests/test_preview_index_load.py` (`@pytest.mark.slow`, läuft in der Suite mit): 72 Stücke zu 1500 Wörtern über commit_chunk in eine echte state.db, nach jedem Stück `index.reconcile(store)` wie der Index-Worker (publish der aktuellen Revision, retire der alten, mark_indexed).

| Stück | Zeit (commit_chunk + Veröffentlichung) |
|---|---|
| 1 | 0,101 s (Wiederholung 0,078 s) |
| 36 | 0,295 s (0,265 s) |
| 72 | **0,546 s** (0,530 s) |

Grenze 5 s eingehalten, nicht gelockert. Positivkontrolle: mit Grenze 0,1 s schlägt der Test fehl. Befehl: `cd backend && uv run pytest tests/test_preview_index_load.py -x -q -s`.

## D-03-22: Messung und Regel

Befehle (Scratch-Ordner `S` außerhalb des Repos, nach der Messung gelöscht; freier RAM vor jedem Modelllauf 4,9 bis 5,2 GB, alle Läufe seriell):

```bash
uv run python -m audio_video_search_backend.models.procure --root $S/models
uv run python -I ../scripts/research/phase3/fetch_corpus.py $S/corpus          # Commons brach mit 429 ab
uv run python -I ../scripts/research/phase3/fetch_commons_retry.py $S/corpus
uv run python -I ../ci/media/fetch_speech.py $S/speech
uv run python -I ../scripts/research/phase3/verdict22.py $S/models $S/res_clips $S/speech/*.wav $S/corpus/wav/fleurs_*.wav
uv run python -I ../scripts/research/phase3/build_corpus.py $S/corpus && uv run python -I ../scripts/research/phase3/build_extra.py $S/corpus
uv run python -I ../scripts/research/phase3/verdict22.py $S/models $S/res_test $S/corpus/test/*.wav $S/corpus/extra/*.wav
uv run python -I ../scripts/research/phase3/build_short.py $S/corpus $S/res_test
uv run python -I ../scripts/research/phase3/verdict22.py $S/models $S/res_short $S/corpus/short/*.wav $S/corpus/wav/sing_fr_choir_faure.wav
uv run python -I ../scripts/research/phase3/eval22.py $S/res_clips $S/res_test $S/res_short
```

verdict22.py benutzt die echte Engine (engine/parakeet.py), die Zählung des Workers (`take`), den zweiten Durchgang für Dateien bis 60 s und `file_verdict`. 337 Dateien: alle 175 FLEURS-Einzelclips (DE/EN/FR je 15, 13 weitere Sprachen je 10), die drei gepinnten Clips, 101 abgeleitete Testdateien, 12 verschlechterte, 45 Kurzmemos, der Fauré-Chor (kam erst nach build_corpus, einzeln gemessen). Sing_fr_debussy blieb bei 429 (wie in der Research).

Befund vor der neuen Regel: Parakeet gibt bei einzelnen Clips nicht unterstützter Sprachen oft 0 Token (TR 3 von 10, ZH 6, JA 4, HI 1) oder Wortsalat, den die Konfidenz verwirft; ohne behaltenes Wort und unter 10 s Sprache endeten 46 von 78 als no_speech. Die Wortzahl trennt nicht: TR-Clips mit 0 bis 34 verworfenen Wörtern, Senfl a cappella mit 0 Wörtern. Es trennen VAD-Sprache und ihr Anteil:

| Gruppe (ohne behaltenes Wort) | VAD-Sprache | Anteil |
|---|---|---|
| Stille, Rauschen, Sinus, Brummen, Orchester, Kunstgesang, Chöre (14) | 0,0 bis 74,4 s | 0 bis **45 %** (Senfl 74,4 s / 166,7 s) |
| DE/EN/FR ohne behaltenes Wort (21: 1-Wort-Memos, 3-s-Anschnitte, einzelne 2/4-Wort-Memos) | 0,0 bis **2,1 s** | 0 bis 66 % |
| Nicht unterstützte Einzelclips, die die Regel fängt | ab **4,3 s** | ab **55 %** |

Regel: kein behaltenes Wort, VAD-Sprache >= 3 000 ms und Anteil >= 0,5: `unsupported_language`. Schwellen = Mitten der Lücken (2,1/4,3 s; 45/55 %); jede Wahl in (2,1 s, 4,3 s] und (45 %, 55 %] gibt auf diesem Korpus dieselben Urteile.

Ergebnis (`eval22.py`, Urteil aus den gespeicherten Zählern neu berechnet):

| Gruppe | Dateien | Urteil |
|---|---|---|
| instance (DE/EN/FR inkl. Memos, Mischungen, verschlechtert) | 175 | 154 transcript, 21 no_speech (alle ohne Sprache oder höchstens 2,1 s; vorher genauso) |
| nonspeech (Stille, Rauschen, Musik, Gesang ohne Text) | 14 | 14 no_speech |
| sung (Englisch gesungen) | 3 | 3 transcript |
| foreign (ES, IT, NL, PL, RU, EL inkl. speech_es) | 67 | 67 unsupported_language |
| unsupported (TR, AR, ZH, JA, HI, VI, SW inkl. speech_tr) | 78 | **70 unsupported_language** (vorher 31), 7 no_speech, 1 transcript |

Gegenprobe gegen das bei der Messung gespeicherte Urteil der alten Regel (eigenes Skript, nicht das Muster der Umsetzung): genau 39 Dateien wechseln, alle in der Gruppe unsupported von no_speech zu unsupported_language; in instance, nonspeech, sung und foreign wechselt keine. speech_tr (9,1 s, 64 %, 0 Token) ist jetzt unsupported_language.

Verbleibende Fälle der Gruppe unsupported: ZH 00/04/06, JA 04, VI 01 mit Anteil 42 bis 47 % (unter der Senfl-Grenze), JA 05 mit 2,1 s Sprache, SW 09 ohne VAD-Sprache, und JA 00 als transcript (2 Wortsalat-Wörter aus dem zweiten Durchgang behalten).

## ES-Clip und Modelltest

- `SPEECH_ES`: FLEURS es_419 `1001146817223348054.wav`, 12,84 s, Mitglied-sha256 `861ceedc4d50fbe52fc89b6d0c0fa740b9cd6fa668388e754064847386af0faf`, WAV-sha256 `95df54f13e862069293afca618669316d194c1b4c6601eb808b501c86292b527` (ffmpeg 8.1.1 Gyan; DE- und TR-WAV-sha256 im selben Lauf unverändert), gleiche gepinnte Revision `70bb2e84...`. `AVS_TEST_SPEECH_ES` in python.yml; Cache-Schlüssel der Clips ändert sich dadurch automatisch (Mitglied-sha256 aller CLIPS).
- test_engine_model.py: neu `test_the_german_clip_is_a_transcript`, `test_the_spanish_clip_is_transcribed_and_dropped_by_its_text_language` (29 Wörter, alle Fenster `language`, lid `es`, Urteil unsupported_language), `test_the_turkish_clip_is_unsupported_language`. Mit Modellen 8 passed; Positivkontrolle: Regel abgeschaltet (SPEECH_ONLY_MS 3 000 000), TR-Test rot; ohne AVS_TEST_MODELS 8 skipped mit Grund.

## Gates

- ruff check und format --check (backend, ../scripts, ../ci), pyright latest 0 Fehler, vulture still.
- Volle Suite mit Modellen und Clips: **1842 passed**, 0 skipped, Abdeckung 93,97 % (preview.py 95 %, nc.py 88 %), 171 s.
- Gedankenstrich-Prüfung aller geänderten Dateien: 0 Treffer (Prüfer an einer Probe mit U+2014 positiv).
- Logs: Test mit Marker HIDDEN im Pfad und "geheimwort" in den Wörtern, beide nachweislich vorhanden, in keiner Logzeile; Logzeilen tragen media_id, outcome, reason, chunks.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lücke an der Stückgrenze bei der Regel "Fenster vor next_start_ms verwerfen"**
- Die VAD des Folgestücks hört im 1-s-Kontext den Rest des letzten Fensters; liegt die nächste Sprache weniger als 2 s dahinter (Fenster des Vorgängers am 25-s-Deckel geteilt), fasst sie beides zu einem Fenster, das vor next_start_ms beginnt. Nach dem Plantext fiele es ganz weg, mit den neuen Wörtern. Umsetzung: ein solches Fenster behält seine Wörter ab next_start_ms; Fenster ganz im Kontext fallen weg (wie geplant). Test `test_a_window_that_begins_inside_the_context_and_reaches_on_keeps_only_its_new_words`, Mutation "Plantext-Regel" rot.

**2. [Rule 1 - Bug] Zwergstück am Dateiende**
- Endet das letzte Fenster kurz vor dem Dateiende, hätte die Schleife ein weiteres Stück für die letzte Sekunde dekodiert. Reicht der dekodierte Bereich bis zum Ende, nimmt das Stück den Rest und setzt next_start_ms auf die Dauer.

**3. [Rule 2 - T-03-45] Andere Bytes als der Inhalts-Schlüssel: warten statt yield**
- yield_preview stellt den Job sofort zurück; der Claim holt ihn gleich wieder (der Verweis bleibt aktiv, bis die Capture die Änderung sieht): Download-Schleife. Jetzt `retry_preview(now + 300, count=False)`, Outcome STALE, kein Wort, kein Versuch. Ebenso abgelehnte Downloads (300 s, ohne Versuch).

**4. [Rule 3] Store-Erweiterungen (repo.py, nicht in files_modified)**
- `media_of_file_sha256` (liest, legt nie an) für den sha256-Abgleich; `commit_chunk(..., second_pass=False)` setzt die Spalte second_pass in derselben Transaktion (vorher hatte sie keinen Schreiber). Tests in test_preview_worker.py.

**5. Eigener Temp-Unterordner `tmp/preview`**
- prepare() leert ihn ganz (auch fertige Dateien ohne `.part` eines gestoppten Prozesses); die Capture räumt in `tmp` nur ihre `.part`-Dateien und kann so keinen laufenden Vorschau-Download löschen.

**6. Testkorrektur zwischen RED und GREEN (eigener Commit 0359b35)**
- Ein Positivkontroll-Fall erwartete "complete" ohne Wort in der Engine-Tabelle (richtig ist no_speech), Importfolge (ruff I001 wie in 03-10, weil das Modul im RED fehlte), vulture-Fund `companion_ok` als Parameter (jetzt usefixtures). Getrennt von Umsetzung und RED.

**7. D-03-22 zusätzlich (Owner-Auftrag)**
- engine/catch.py, test_catch_rule.py, test_engine_constants.py, test_engine_model.py, test_fetch_speech.py, fetch_speech.py, python.yml, zwei Messskripte. Zwei bestehende Grenzfälle in test_catch_rule.py (`script-plus-language-4`, `confidence-9-words`) lagen mit 50 % bzw. 63 % Anteil in der neuen Regel; ihre Sprache wurde gesenkt, damit sie weiter die Grenze ihres Zweigs prüfen.

**8. Plantext-Abweichungen, bewusst**
- PreviewOutcome.CHUNK_DONE ist definiert, wird aber nicht ausgegeben (ein Schritt rechnet den Job bis zum Ende, zur Abgabe oder zum Fehler).
- D-03-22 ohne Wortzahl-Bedingung ("kein oder fast kein Wort"): gemessen haben nicht unterstützte Einzelclips 0 bis 34 verworfene Wörter und Senfl 0; die Wortzahl trennt nicht, der Anteil schon. Die Regel verlangt "kein behaltenes Wort".

## Offene Punkte

- **D-03-22 Restfälle**: 5 Einzelclips (ZH, JA, VI) mit 42 bis 47 % Anteil bleiben no_speech, weil Senfl a cappella 45 % hat; ein zweites a-cappella-Stück über 50 % würde "Sprache nicht unterstützt" statt "keine Sprache" zeigen (beides ohne Transkript). Gemessen an einem Laptop, FLEURS ist vorgelesene Sprache.
- **Wortsalat aus dem zweiten Durchgang**: fleurs_ja_jp_00 behält 2 Wörter aus dem zweiten Durchgang (D-03-16) und wird transcript. In M-10 war die Negativkontrolle 1 Wort ("Yeah.", verworfen). Für Owner oder Planer: zweiten Durchgang strenger werten oder hinnehmen.
- **Tests anderer Pläne** (03-15, 03-17, 03-18) auf TR = unsupported_language umstellen (laut D-03-22).
- **CONFIG_VERSION** bleibt 1 (Begründung in decisions); falls der Owner jede catch-Konstante als Konfiguration zählt, auf 2 heben.
- **main.py** startet den Worker noch nicht (Plan 03-15); `read_max_duration_hours` weiter ungelesen (03-11).
- **CI nicht gelaufen** (nichts gepusht): ES-Clip-WAV-sha256 nur mit ffmpeg 8.1.1 Gyan gemessen; weicht BtbN 8.1.3 ab, warnt der CI-Schritt nur.
- Fremde, nicht gestagte Änderung im Arbeitsbaum: `backend/tests/test_model_download.py` (schon vor Beginn, nicht berührt).

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche außerhalb des Bedrohungsmodells. T-03-43 (sha256 gegen Inhalts-Schlüssel, STALE ohne Wort), T-03-44 (Zufallsname ohne Endung, finally, eigener Ordner, prepare leert, Test "tmp leer" auf allen Wegen), T-03-45 (Platzprüfung, disk_full 300 s, engine_failed nach drei Versuchen, keine Download-Schleife), T-03-46 (Abgabe an der Stückgrenze), T-03-47 (HIDDEN-Test) umgesetzt und getestet.

## TDD Gate Compliance

fa528c8 (test) vor 6886346 (feat); b52ea53 (test, rot) und 0359b35 (test) vor 2ac0521 (feat); c04dbe0 (test, rot) vor 253b213 (feat).

## Self-Check: PASSED

- FOUND: worker/preview.py, test_fetch_keep.py, test_preview_worker.py, test_preview_index_load.py, verdict22.py, eval22.py
- FOUND: Commits fa528c8, 6886346, b52ea53, 0359b35, 2ac0521, f90a4a6, c04dbe0, 253b213, c48988c, 8056e8d
- Scratch-Ordner mit Modellen, Korpus und Clips nach der Messung gelöscht; `git status` zeigt keine .wav- oder .onnx-Datei.
