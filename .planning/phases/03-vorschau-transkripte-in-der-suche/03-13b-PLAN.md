---
phase: 03-vorschau-transkripte-in-der-suche
plan: 13b
type: execute
wave: 5
depends_on: ["03-13"]
files_modified:
  - scripts/research/phase3/verdict23.py
  - scripts/research/phase3/eval23.py
  - backend/src/audio_video_search_backend/engine/catch.py
  - backend/src/audio_video_search_backend/engine/parakeet.py
  - backend/src/audio_video_search_backend/engine/constants.py
  - backend/tests/test_catch_rule.py
  - backend/tests/test_engine_constants.py
  - backend/tests/test_engine_child.py
autonomous: true
requirements: [TRANS-03, MEDIA-04]

must_haves:
  truths:
    - "Ein Fenster aus dem zweiten VAD-Durchgang (D-03-16) behält seine Wörter nur, wenn seine Textsprache DE, EN oder FR mit p >= 0,9 ist und seine mittlere Wortkonfidenz mindestens die gemessene Schwelle SECOND_PASS_CONF erreicht; sonst zählt es als Verwerfung wegen Konfidenz"
    - "Am Korpus von 03-13 mit der echten Engine: jede kurze DE/EN/FR-Memo (1 bis 4 Wörter), die der zweite Durchgang bisher zurückholte, bleibt ein Transkript; fleurs_ja_jp_00 und jede Fremd-, nicht unterstützte und Nicht-Sprach-Datei behält kein Wort aus dem zweiten Durchgang"
    - "Der erste Durchgang urteilt Wort für Wort wie vorher; die Positivkontrolle zeigt, dass die alte Regel die JA-Fenster durchlässt"
    - "Die Schwelle ist eine feste Konstante mit Wert- und Fingerabdrucktest, kein Schalter, keine Einstellung, keine Umgebungsvariable; das VAD-Gate bleibt grün"
    - "Ist die Trennung am Korpus mehrdeutig, entscheidet der Owner nach einer Checkpoint-Frage mit Messtabelle, nicht der Ausführer"
  artifacts:
    - path: "backend/src/audio_video_search_backend/engine/catch.py"
      provides: "SECOND_PASS_CONF und window_verdict(..., second_pass=)"
      contains: "SECOND_PASS_CONF"
    - path: "backend/src/audio_video_search_backend/engine/parakeet.py"
      provides: "transcribe reicht second_pass an window_verdict weiter"
      contains: "second_pass=second_pass"
    - path: "scripts/research/phase3/verdict23.py"
      provides: "Messung der Fenster des zweiten Durchgangs mit der echten Engine"
    - path: "scripts/research/phase3/eval23.py"
      provides: "Auswertung, Schwellenwahl aus der Lücke, Gegenprobe gegen catch.py"
  key_links:
    - from: "engine/parakeet.py Engine.transcribe"
      to: "engine/catch.window_verdict"
      via: "Schlüsselwort second_pass aus dem Job (child.py job[3])"
      pattern: "window_verdict\\(.*second_pass"
    - from: "worker/preview.py take"
      to: "Window.verdict DROP_CONFIDENCE"
      via: "unverändert: abgelehnte Fenster des zweiten Durchgangs zählen als drop_conf"
      pattern: "DROP_CONFIDENCE"
---

## Phase Goal

**As a** Nutzerin oder Nutzer einer Nextcloud-Instanz, **I want to** gesprochenen Text meiner Aufnahmen in Minuten über die normale Nextcloud-Suche finden, als vorläufig gekennzeichnet und nur in Dateien, die ich lesen darf, **so that** ich meine Aufnahmen durchsuchen kann, ohne dass ein Inhalt den Server verlässt.

<objective>
Owner-Entscheid D-03-23 (14.11.2026, nach Plan 03-13): Der zweite VAD-Durchgang (D-03-16, Schwelle 0,3 für Dateien bis 60 s ohne behaltenes Wort) brachte bei FLEURS ja_jp_00 2 Wortsalat-Wörter in den Index. Wörter aus dem zweiten Durchgang bleiben nur, wenn die Textsprache sicher DE/EN/FR ist (p >= 0,9) und die Wortkonfidenz über einer am Korpus GEMESSENEN Schwelle liegt (TRANS-03: keine Halluzination im Index; MEDIA-04: ehrliches Dateiurteil).

Purpose: Erfolgskriterium 2 der Phase ("Halluzinationen tauchen nicht im Index auf") auch für den zweiten Durchgang, ohne die kurzen echten Memos zu verlieren, für die D-03-16 den zweiten Durchgang eingeführt hat.
Output: Messskripte verdict23.py und eval23.py, Messtabelle im SUMMARY, Konstante SECOND_PASS_CONF mit Regel in engine/catch.py, Verdrahtung in engine/parakeet.py, Tests, begründete CONFIG_VERSION.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-CONTEXT.md
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-13-SUMMARY.md
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-06-SUMMARY.md
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-10-SUMMARY.md
@backend/src/audio_video_search_backend/engine/catch.py
@scripts/research/phase3/verdict22.py
@scripts/research/phase3/eval22.py

Regeln: Commits nur lokal mit `git -c user.name=street1983nk -c user.email=k.cherif@outlook.de commit`, ohne Claude-Session- oder Co-Authored-By-Zeile, nie "closes/fixes/resolves #N". Kein Push. Kein lokales Docker. STATE.md, ROADMAP.md, REQUIREMENTS.md nicht schreiben. Keine interaktiven `python -`- oder `python -c`-Aufrufe für die Messung: jede Python-Arbeit läuft als Skriptdatei mit `uv run python -I <datei>`. Echte Umlaute in Prosa, Kommentaren und SUMMARY, keine Gedankenstriche (U+2013, U+2014), keine Emojis. Gates vor jedem Commit grün: `cd backend && uv run ruff check . ../scripts && uv run ruff format --check . ../scripts && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -q`. Audio, Modelle und Messergebnisse nie ins Repo; `git status` zeigt am Ende keine .wav-, .onnx- oder .json-Datei aus der Messung. Die fremde, nicht gestagte Änderung an `backend/tests/test_model_download.py` nicht anfassen und nicht mitcommitten (nur die eigenen Dateien einzeln mit `git add <pfad>` stagen).

Dateigrenzen: Plan 03-15 läuft in derselben Welle und besitzt worker/preview.py, main.py, test_main.py, test_preview_settings.py, test_replaced_file.py, test_preview_corpus.py. Diese Dateien hier NICHT ändern. Deshalb nutzt die neue Regel den bestehenden Verwerfungsgrund DROP_CONFIDENCE (take() in preview.py zählt ihn schon als drop_conf), kein neuer Verdict-Text.

<interfaces>
engine/catch.py (Bestand): `INSTANCE = frozenset({"de","en","fr"})`, `MIN_LATIN 0.5`, `LID_P 0.9`, `LID_MIN_WORDS 3`, `CONF 0.6`, `CONF_INSTANCE 0.5`, `UNSUPPORTED_DROPS 5`, `CONF_DROPS 10`, `CONF_SPEECH_MS 10_000`, `CONF_SPEECH_SHARE 0.3`, `SPEECH_ONLY_MS 3_000`, `SPEECH_ONLY_SHARE 0.5`; Verdicts `KEEP "keep"`, `DROP_SCRIPT "script"`, `DROP_LANGUAGE "language"`, `DROP_CONFIDENCE "confidence"`; `window_verdict(latin, lid, lid_p, n_words, conf_mean) -> str` prüft in dieser Folge Schrift, Sprache außerhalb der Instanz (p >= LID_P und n >= LID_MIN_WORDS), Konfidenz; `file_verdict(kept_words, drop_script, drop_language, drop_conf, speech_ms, duration_ms)`; `needs_second_pass(kept_words, duration_ms, done)`.
engine/parakeet.py (Bestand): `Window(start_ms, end_ms, speech_ms, n_words, verdict, words, latin=1.0, lid="", lid_p=0.0, conf_mean=0.0)`, `EngineWord(text, start_ms, end_ms, conf)`; `Engine.transcribe(pcm, offset_ms, *, second_pass) -> list[Window]` ruft je Fenster `window_verdict(latin, lid, lid_p, len(words), conf_mean)` (Zeile um 254) und gibt Wörter nur bei KEEP mit; `_language(text)` liefert py3langid mit norm_probs, p auf 3 Stellen gerundet; conf_mean auf 4 Stellen.
engine/child.py: Job `(pcm, offset_ms, second_pass)`, Kind ruft `engine.transcribe(pcm, job[2], second_pass=job[3])`.
worker/preview.py (Bestand, nicht ändern): `take(windows, start_ms, end_ms, *, count_speech=True) -> Taken(words, counters, next_start_ms)`; zählt KEEP-Wörter als kept, DROP_* als drop_script/drop_language/drop_conf.
engine/constants.py: `CONFIG_VERSION: Final = 1` mit Docstring "Every changed value needs a new CONFIG_VERSION (TRANS-06)"; tests/test_engine_constants.py hält Wert je Konstante (`test_pipeline_constant`, `test_catch_constant`) und `EXPECTED_FINGERPRINT` über alle Konstanten von constants.py und catch.py.
scripts/research/phase3/verdict22.py: `read_wav`, `measure(engine, path)` (erster Durchgang, take, needs_second_pass, zweiter Durchgang mit `take(second, 0, None, count_speech=False)`, JSON je Datei mit u. a. `words` im measure.py-Format, das build_short.py liest). eval22.py: `group(name)` mit den Gruppen instance, nonspeech, sung, foreign, unsupported.
Korpus-Befehle aus 03-13-SUMMARY.md Abschnitt "D-03-22: Messung und Regel" (procure, fetch_corpus, fetch_commons_retry, fetch_speech, build_corpus, build_extra, build_short); Kurzmemos heißen `short{k}w_{code}_{i:02d}.wav` (k = 1 bis 4).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fenster des zweiten Durchgangs am Korpus messen und die Schwelle aus der Lücke bestimmen</name>
  <files>scripts/research/phase3/verdict23.py, scripts/research/phase3/eval23.py</files>
  <read_first>
    - scripts/research/phase3/verdict22.py (ganze Datei: Aufbau, JSON-Felder, Aufruf)
    - scripts/research/phase3/eval22.py (ganze Datei: group, EXPECTED)
    - scripts/research/phase3/build_short.py Zeilen 1 bis 55 (liest `words` aus den Ergebnis-JSONs der memo_*-Dateien)
    - backend/src/audio_video_search_backend/engine/catch.py (ganze Datei)
    - backend/src/audio_video_search_backend/engine/parakeet.py Zeilen 55 bis 100 und 200 bis 269 (Window, _language, transcribe)
    - backend/tests/test_research_scripts.py (Pflichten für Skripte unter scripts/research/phase3: keine lokalen Pfade, kompilierbar)
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-13-SUMMARY.md Abschnitt "D-03-22: Messung und Regel" (Befehlsfolge, Korpusumfang 337 Dateien)
  </read_first>
  <action>
Zwei neue Skripte, beide mit deutschem Docstring wie verdict22.py (Aufruf, Zweck, "kein Text verlässt den Rechner"), ohne lokale Pfade, Argumente nur positional.

verdict23.py (`python -I verdict23.py <models_root> <out_dir> <wav> [<wav> ...]`): Kopie des Ablaufs von verdict22.measure (gleiche Engine, gleiches take, gleiches needs_second_pass, gleiche JSON-Felder einschließlich `words`, damit build_short.py die Ergebnisse von res_test lesen kann), zusätzlich je Datei: `second_windows` als Liste je Fenster des zweiten Durchgangs mit `start_ms`, `end_ms`, `n_words`, `latin`, `lid`, `lid_p`, `conf_mean`, `conf_min` (kleinste Wortkonfidenz aus `window.words`; die Engine gibt Wörter nur bei KEEP mit, deshalb bei verworfenen Fenstern null; die Auswertung braucht nur Fenster, die die alte Regel behielt), `verdict` (alte Regel), und `second_kept` (Wortzahl, die der zweite Durchgang unter der alten Regel behielt). Der zweite Durchgang läuft über `engine.transcribe(pcm, 0, second_pass=True)` wie im Worker, keine Nachbildung von Engine-Interna.

eval23.py (`python -I eval23.py [--check] <result_dir> [<result_dir> ...]`): Gruppen über `group` wie eval22 (eigene Kopie der Tupel, kein Import aus eval22). Die Regel prüft eval23 SELBST nach (eigene Formel, nicht aus catch importiert, Regel "Gegenprobe nie mit dem Muster der Umsetzung"): ein Fenster des zweiten Durchgangs bleibt, wenn die alte Regel es behielt UND `lid in {"de","en","fr"}` UND `lid_p >= 0.9` UND `conf_mean >= T`. Auswertung:
(a) P = Dateien der Gruppe instance, deren `second_kept > 0` ist; daraus Pflichtmenge P4 = die Kurzmemos `short1w` bis `short4w`. Für jede P-Datei das beste Fenster (höchstes conf_mean unter den Fenstern mit Instanzsprache und p >= 0,9, die die alte Regel behielt); fehlt es, ist die Datei "ohne sichere Sprache".
(b) N = alle Fenster des zweiten Durchgangs in den Gruppen nonspeech, foreign, unsupported (fleurs_ja_jp_00 einzeln ausweisen), die die alte Regel behielt.
(c) Untergrenze L = max(0,5 = CONF_INSTANCE, größtes conf_mean der N-Fenster mit Instanzsprache und p >= 0,9); Obergrenze U = kleinstes conf_mean der besten Fenster aller P-Dateien. Eindeutig ist die Trennung genau dann, wenn keine P-Datei "ohne sichere Sprache" ist und U - L >= 0,02; dann T = Mitte von L und U auf zwei Nachkommastellen abgerundet (muss > L und <= U bleiben, sonst auf drei Stellen).
(d) Mit T je Gruppe: Dateien, deren Urteil wechselt (alte gegen neue Zählung: abgelehnte Fenster wandern von kept zu drop_conf, file_verdict aus catch wie eval22), verlorene Wörter je P-Datei, behaltene Wörter aus dem zweiten Durchgang je N-Gruppe (Soll 0).
(e) sung nur berichten.
Ausgabe als Markdown-Tabellen auf stdout (Gruppe, Dateien mit zweitem Durchgang, Fenster, lid/p-Spanne, conf_mean-Spanne, L, U, T, Urteilswechsel). `--check`: zusätzlich für jedes gespeicherte Fenster `catch.window_verdict(latin, lid, lid_p, n_words, conf_mean, second_pass=True)` gegen die eigene Formel mit `catch.SECOND_PASS_CONF` vergleichen und Abweichungen zählen (nur nach Task 2 lauffähig; vorher mit Exit 2 und Hinweis abbrechen, wenn catch.SECOND_PASS_CONF fehlt).

Messung (seriell, nie parallel zu einem anderen Modelllauf oder Docker): Scratch-Ordner S außerhalb des Repos anlegen (z. B. unter `%LOCALAPPDATA%\Temp\avs-0313b`); vor jedem Modelllauf freien RAM mit `powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"` prüfen: unter 4 194 304 KB nicht starten, warten und erneut prüfen; den Wert je Lauf im SUMMARY nennen. Befehlsfolge aus 03-13-SUMMARY wiederholen, aber mit verdict23.py statt verdict22.py (procure nach $S/models, fetch_corpus und fetch_commons_retry nach $S/corpus, fetch_speech nach $S/speech, verdict23 auf Clips und FLEURS-Einzelclips nach $S/res_clips, build_corpus und build_extra, verdict23 auf test und extra nach $S/res_test, build_short mit $S/res_test, verdict23 auf short und den Fauré-Chor nach $S/res_short), dann `uv run python -I ../scripts/research/phase3/eval23.py $S/res_clips $S/res_test $S/res_short > $S/eval23.md`. Die Zahl der gemessenen Dateien gegen 337 aus 03-13 abgleichen und Abweichungen (z. B. Commons-429) nennen.

Entscheidung nach der Messung: Ist die Trennung nach (c) eindeutig und behält keine N-Gruppe ein Wort, steht T fest; Task 2 setzt genau diesen Wert. Ist sie mehrdeutig (eine Pflicht-Memo ohne sichere Sprache, U - L unter 0,02, eine Überlappung, oder eine andere instance-Datei verliert ihr Transkript), endet die Ausführung nach dem Commit dieses Tasks mit einer Checkpoint-Rückgabe vom Typ decision an den Orchestrator (D-03-23 "ist die Messung mehrdeutig, Owner fragen"): Messtabelle aus eval23.md, betroffene Dateien mit lid, lid_p, conf_mean, und die Optionen (A) Schwelle T' mit Liste der dann verlorenen Memos, (B) sichere Sprache nur ab einer Wortzahl, darunter nur Konfidenz mit gemessener Schwelle, (C) zweiten Durchgang nur noch für Wörter mit Instanzsprache aus dem ersten Durchgang derselben Datei, (D) andere Owner-Vorgabe. Task 2 startet dann erst nach der Owner-Antwort. Nicht raten, keine Schwelle ohne eindeutige Lücke setzen.

Die Ergebnis-JSONs und eval23.md bleiben bis zum Ende von Task 2 im Scratch (für `--check`), Audio und Modelle ebenfalls bis dahin; nach Task 2 den ganzen Ordner S löschen. Commit nur der zwei Skripte: `chore(03-13b): Messskripte für den zweiten VAD-Durchgang (D-03-23)`.
  </action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_research_scripts.py -x -q && uv run ruff check ../scripts && uv run ruff format --check ../scripts && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright ../scripts/research/phase3/verdict23.py ../scripts/research/phase3/eval23.py</automated>
  </verify>
  <acceptance_criteria>
    - `scripts/research/phase3/verdict23.py` und `eval23.py` existieren, test_research_scripts.py ist grün (keine lokalen Pfade, beide kompilieren).
    - verdict23.py ruft für beide Durchgänge nur `Engine.transcribe` auf (`grep -c "_decode_span\|_segments" scripts/research/phase3/verdict23.py` ist 0).
    - Die Prüfformel der Messung steht in eval23.py selbst (`grep -n "lid_p >= 0.9" scripts/research/phase3/eval23.py` trifft); aus catch holt eval23 nur file_verdict, die Verdict-Namen und, nur im Zweig --check, window_verdict und SECOND_PASS_CONF.
    - Das SUMMARY enthält die Messtabelle: je Gruppe Dateien mit zweitem Durchgang, Fenster, lid/p-Spanne, conf_mean-Spanne, behaltene Wörter alt und neu; L, U, T; die Zeile fleurs_ja_jp_00 mit lid, lid_p, conf_mean ihrer 2 Wörter; je Pflicht-Memo (short1w bis short4w mit second_kept > 0) Sprache, p, conf_mean und ob sie Transkript bleibt; freier RAM je Lauf; Zahl der gemessenen Dateien.
    - Bei mehrdeutiger Trennung: Checkpoint-Rückgabe mit Tabelle und Optionen A bis D statt Task 2.
  </acceptance_criteria>
  <done>Commit `chore(03-13b): Messskripte für den zweiten VAD-Durchgang (D-03-23)`; Schwelle T eindeutig gemessen oder Owner-Frage gestellt.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Regel für den zweiten Durchgang in catch.py mit gemessener Konstante (RED und GREEN getrennt)</name>
  <files>backend/src/audio_video_search_backend/engine/catch.py, backend/src/audio_video_search_backend/engine/parakeet.py, backend/src/audio_video_search_backend/engine/constants.py, backend/tests/test_catch_rule.py, backend/tests/test_engine_constants.py, backend/tests/test_engine_child.py</files>
  <read_first>
    - backend/src/audio_video_search_backend/engine/catch.py (ganze Datei, Docstring mit D-03-22-Absatz als Vorbild)
    - backend/src/audio_video_search_backend/engine/constants.py (ganze Datei, CONFIG_VERSION-Regel)
    - backend/src/audio_video_search_backend/engine/parakeet.py Zeilen 240 bis 269 (transcribe)
    - backend/tests/test_catch_rule.py (ganze Datei: Parametrisierung von window_verdict)
    - backend/tests/test_engine_constants.py (Wertlisten, fingerprint, EXPECTED_FINGERPRINT, Positivkontrolle)
    - backend/tests/test_engine_child.py Zeilen 370 bis 500 (ScriptedEngine, _span_len, Tests mit second_pass)
    - backend/tests/test_vad_gate.py Zeilen 1 bis 100 (was als Schalter oder Einstellung gilt)
    - backend/src/audio_video_search_backend/worker/preview.py Zeilen 177 bis 225 (take, nur lesen)
    - $S/eval23.md aus Task 1 (Schwelle T und die Fenstermerkmale für die Testfälle)
  </read_first>
  <behavior>
    - `window_verdict(latin, lid, lid_p, n_words, conf_mean)` ohne Schlüsselwort und mit `second_pass=False` gibt für jede bestehende Parametrisierung dasselbe wie vorher (erster Durchgang unverändert).
    - Mit `second_pass=True`: Schrift unter 0,5 bleibt DROP_SCRIPT; Fremdsprache mit p >= 0,9 und mindestens 3 Wörtern bleibt DROP_LANGUAGE (Bestandstest `test_a_dropped_window_carries_no_words_but_its_counts` mit TR bleibt grün); sonst KEEP genau dann, wenn lid in INSTANCE, lid_p >= LID_P und conf_mean >= SECOND_PASS_CONF; alles andere DROP_CONFIDENCE.
    - Grenzen inklusiv: conf_mean == SECOND_PASS_CONF mit de 0,9 ist KEEP; SECOND_PASS_CONF minus 0,01 ist DROP_CONFIDENCE; lid_p 0,89 ist DROP_CONFIDENCE; "es" mit p 0,98, 2 Wörtern und conf 0,97 ist im ersten Durchgang KEEP (Bestandsfall two-words-no-language-decision), im zweiten DROP_CONFIDENCE; lid "" (kein Text) ist DROP_CONFIDENCE.
    - Fälle aus der Messung (Werte aus eval23.md, wie gespeichert gerundet): jedes behaltene Fenster von fleurs_ja_jp_00 ist im zweiten Durchgang DROP_CONFIDENCE; Positivkontrolle: dieselben Merkmale mit `second_pass=False` ergeben KEEP (die alte Regel lässt JA durch). Je Sprache DE, EN, FR mindestens eine zurückgeholte 1-Wort-Memo und eine 4-Wort-Memo (soweit gemessen) sind KEEP; das N-Fenster mit dem höchsten conf_mean unter sicherer Instanzsprache (falls vorhanden) ist DROP_CONFIDENCE.
    - parakeet: `ScriptedEngine` mit einem Fenster, Instanzsprache de 0,95 und Wörtern mit conf unter SECOND_PASS_CONF (aber >= CONF_INSTANCE): `transcribe(..., second_pass=False)` gibt KEEP mit Wörtern, `transcribe(..., second_pass=True)` gibt DROP_CONFIDENCE, `words == ()`, n_words unverändert.
    - Konstante: `catch.SECOND_PASS_CONF == T` (gemessen) in test_catch_constant; Fingerabdruck neu; der Positivkontrolltest des Fingerabdrucks bleibt grün.
  </behavior>
  <action>
Zwei getrennte Commits Pflicht. RED zuerst: nur die Tests (test_catch_rule.py: neue Parametrisierung `test_window_verdict_second_pass` mit den behavior-Fällen und Messfällen, ids wie `ja-00-second-pass-dropped`, `ja-00-first-pass-kept-positive-control`, `de-1w-memo-kept` usw.; test_engine_constants.py: Eintrag `("SECOND_PASS_CONF", T)` in der catch-Wertliste, Zeile `catch.SECOND_PASS_CONF=T` und neue CONFIG_VERSION im EXPECTED_FINGERPRINT, `("CONFIG_VERSION", 2)` und die Zeile in `test_the_fingerprint_sees_every_constant_the_value_tests_name` entsprechend; test_engine_child.py: der parakeet-Test aus behavior). Lauf zeigt Fehlschläge (AttributeError oder TypeError wegen fehlendem Schlüsselwort, Fingerabdruck), Commit `test(03-13b): zweiter VAD-Durchgang nur mit sicherer Instanzsprache und gemessener Konfidenz (rot)`.

GREEN danach, nur Umsetzung: In catch.py neue Konstante `SECOND_PASS_CONF: Final = T` (der in Task 1 gemessene Wert, per D-03-23, kein Schalter, keine Einstellung, keine Umgebungsvariable) neben CONF_INSTANCE; `window_verdict(latin, lid, lid_p, n_words, conf_mean, *, second_pass: bool = False)`: nach Schrift- und Sprachprüfung (unverändert) bei second_pass KEEP nur, wenn `lid in INSTANCE and lid_p >= LID_P and conf_mean >= SECOND_PASS_CONF`, sonst DROP_CONFIDENCE; ohne second_pass die bisherige Konfidenzprüfung. Docstring des Moduls um einen Absatz D-03-23 ergänzen (Befund ja_jp_00, gemessene Lücke L bis U, T = Mitte, Messskripte verdict23.py und eval23.py), Docstring von window_verdict um das Schlüsselwort. In parakeet.py `window_verdict(latin, lid, lid_p, len(words), conf_mean, second_pass=second_pass)` in transcribe; Modul-Docstring (TRANS-03-Absatz) um einen Satz zum zweiten Durchgang ergänzen. worker/preview.py NICHT ändern (03-15 besitzt die Datei; take zählt DROP_CONFIDENCE schon).

CONFIG_VERSION prüfen und begründen: Die neue Regel ändert Wörter eines Transkripts (Wörter aus dem zweiten Durchgang fallen weg), anders als D-03-22 in 03-13, das nur den Grund einer Datei ohne Transkript änderte. Nach der Regel in constants.py ("Every changed value needs a new CONFIG_VERSION", TRANS-06) deshalb `CONFIG_VERSION: Final = 2`; vorher mit `grep -rn "CONFIG_VERSION\|config_version=1" backend/src backend/tests` prüfen, dass nur preview.py (liest die Konstante) und test_engine_constants.py sie als Engine-Version nutzen (api/sample.py hat eine eigene Probe-Version 1 und bleibt). Keine Migration nötig, weil noch keine Installation Vorschauen mit Version 1 hat (0.3.0 ist unveröffentlicht); das im SUMMARY nennen. Zeigt die volle Suite, dass ein Test die Engine-Version 1 fest erwartet, diesen Test nicht ändern, sondern im SUMMARY als Abweichung melden und die Entscheidung 1 oder 2 als Owner-Hinweis aufnehmen.

Nach GREEN: `uv run python -I ../scripts/research/phase3/eval23.py --check $S/res_clips $S/res_test $S/res_short` muss 0 Abweichungen zwischen catch.window_verdict(..., second_pass=True) und der Messformel zeigen; Ergebnis ins SUMMARY. Mit Modellen (falls `AVS_TEST_MODELS` gesetzt) zusätzlich `uv run pytest tests/test_engine_model.py -x -q -rs`. Danach Scratch-Ordner S vollständig löschen und `git status --short` zeigen. Commit `feat(03-13b): zweiter VAD-Durchgang nur mit sicherer Instanzsprache und gemessener Konfidenz (D-03-23)`.
  </action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_catch_rule.py tests/test_engine_constants.py tests/test_engine_child.py tests/test_vad_gate.py tests/test_preview_worker.py tests/test_research_scripts.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "SECOND_PASS_CONF: Final" backend/src/audio_video_search_backend/engine/catch.py` zeigt genau eine Zeile mit dem gemessenen Wert T aus dem SUMMARY.
    - `grep -n "second_pass=second_pass" backend/src/audio_video_search_backend/engine/parakeet.py` zeigt den Aufruf von window_verdict in transcribe.
    - `uv run pytest tests/test_catch_rule.py -k "second_pass" -x -q` ist grün und enthält die Fälle `ja-00-second-pass-dropped` und `ja-00-first-pass-kept-positive-control`.
    - tests/test_vad_gate.py ist unverändert und grün (`git diff --stat HEAD~2 -- backend/tests/test_vad_gate.py` leer).
    - `git log --format=%s -3` zeigt den RED-Commit `test(03-13b): ...` vor dem GREEN-Commit `feat(03-13b): ...` als getrennte Commits; Autor und Committer street1983nk <k.cherif@outlook.de>, keine Claude-Zeile.
    - `git diff --name-only HEAD~3 -- backend/src/audio_video_search_backend/worker/preview.py backend/src/audio_video_search_backend/main.py` ist leer (keine Kollision mit 03-15).
    - `eval23.py --check` meldet 0 Abweichungen; CONFIG_VERSION-Entscheidung mit Begründung im SUMMARY.
    - Volle Gates grün (ruff, format, pyright latest, vulture, pytest); Gedankenstrich-Prüfung der geänderten Dateien 0 Treffer mit Positivprobe des Prüfers an einer Datei mit U+2014; Scratch gelöscht, `git status` ohne .wav/.onnx/.json aus der Messung.
  </acceptance_criteria>
  <done>Zwei getrennte Commits RED und GREEN; JA-Wortsalat bleibt draußen, zurückgeholte DE/EN/FR-Memos bleiben, Gegenprobe 0 Abweichungen.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Engine-Kind nach Worker | Wörter des zweiten Durchgangs mit niedriger VAD-Schwelle, oft Rauschen oder fremde Sprache |
| Messkorpus nach Rechner | heruntergeladene Audiodaten und Modelle, untrusted, nur im Scratch |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-80 | Tampering | Wortsalat aus dem zweiten Durchgang im Index (D-03-23) | mitigate | window_verdict mit second_pass: nur Instanzsprache mit p >= 0,9 und conf_mean >= SECOND_PASS_CONF; Testfall ja_jp_00 plus Positivkontrolle; Gegenprobe eval23 --check |
| T-03-81 | Tampering | Schwelle zur Laufzeit verschiebbar oder abschaltbar | mitigate | feste Konstante in catch.py, Wert- und Fingerabdrucktest, test_vad_gate.py unverändert grün (keine Einstellung, keine Umgebungsvariable, kein Schalterwort) |
| T-03-82 | Information Disclosure | Korpus, Modelle oder Messergebnisse (FLEURS-Texte) im Repo | mitigate | alles nur im Scratch außerhalb des Repos, nach Task 2 gelöscht; Commits stagen nur benannte Dateien; git status ohne .wav/.onnx/.json |
| T-03-83 | Denial of Service | Messung erschöpft RAM neben anderen Läufen | mitigate | seriell, freier RAM >= 4 GB vor jedem Modelllauf geprüft, kein Docker, kein paralleler Modelllauf |
| T-03-84 | Repudiation | Schwelle geraten statt gemessen | mitigate | T nur aus eindeutiger Lücke (U - L >= 0,02), sonst Checkpoint mit Owner-Frage; Messtabelle im SUMMARY |
</threat_model>

<verification>
Volle Backend-Suite grün; Regel wirkt nur im zweiten Durchgang; Messtabelle und Gegenprobe im SUMMARY; keine Datei aus 03-15 berührt.
</verification>

<success_criteria>
- Kein Wort aus dem zweiten Durchgang bei fleurs_ja_jp_00 und bei allen Fremd-, nicht unterstützten und Nicht-Sprach-Dateien des Korpus.
- Jede bisher zurückgeholte kurze DE/EN/FR-Memo (1 bis 4 Wörter) bleibt ein Transkript.
- SECOND_PASS_CONF ist gemessen, fest, getestet; CONFIG_VERSION begründet.
</success_criteria>

<output>
Create `.planning/phases/03-vorschau-transkripte-in-der-suche/03-13b-SUMMARY.md` when done
</output>
