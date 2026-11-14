---
phase: 03-vorschau-transkripte-in-der-suche
plan: 13b
subsystem: engine
tags: [catch-rule, vad, second-pass, d-03-23, trans-03, media-04]
requires: ["03-13"]
provides:
  - "catch.SECOND_PASS_CONF = 0.68 und window_verdict(..., second_pass=)"
  - "parakeet.transcribe reicht second_pass an window_verdict weiter"
  - "Messskripte verdict23.py und eval23.py"
affects: ["worker/preview.py (unverändert, zählt DROP_CONFIDENCE als drop_conf)"]
tech-stack:
  added: []
  patterns: ["Schwelle aus Korpusmessung, Owner-Entscheid bei mehrdeutiger Lücke", "Gegenprobe mit eigener Formel"]
key-files:
  created:
    - scripts/research/phase3/verdict23.py
    - scripts/research/phase3/eval23.py
  modified:
    - backend/src/audio_video_search_backend/engine/catch.py
    - backend/src/audio_video_search_backend/engine/parakeet.py
    - backend/src/audio_video_search_backend/engine/constants.py
    - backend/tests/test_catch_rule.py
    - backend/tests/test_engine_constants.py
    - backend/tests/test_engine_child.py
decisions:
  - "D-03-23 Option A (Owner, 14.11.2026): Fenster des zweiten VAD-Durchgangs nur ab mittlerer Wortkonfidenz 0,68, ohne Sprachbedingung"
  - "CONFIG_VERSION 2: die Regel ändert Wörter eines Transkripts"
metrics:
  completed: 2026-11-14
  files_measured: 338
---

# Phase 3 Plan 13b: zweiter VAD-Durchgang nur ab Konfidenz 0,68 (D-03-23) Summary

Fenster aus dem zweiten VAD-Durchgang behalten ihre Wörter nur noch ab einer mittleren Wortkonfidenz von 0,68 (Owner-Option A nach mehrdeutiger Messung). Der JA-Wortsalat von fleurs_ja_jp_00 fällt damit aus dem Index, die zurückgeholten EN-Memos und eine der beiden FR-2-Wort-Memos bleiben.

## Commits

| Schritt | Commit | Inhalt |
|---|---|---|
| Aufgabe 1 | aba5f97 | chore: verdict23.py, eval23.py |
| Owner-Entscheid | 01b5f1f | chore: eval23.py auf Option A (eigene Formel nur Konfidenz) |
| RED | e50efd7 | test: catch, Konstanten, Engine-Kind |
| GREEN | d294e8f | feat: catch.py, parakeet.py, constants.py |

## Messung

Befehlsfolge wie in 03-13 "D-03-22: Messung und Regel", mit verdict23.py statt verdict22.py, Scratch außerhalb des Repos (nach Aufgabe 2 gelöscht). Alle Modellläufe seriell, freier RAM vor dem Lauf:

| Lauf | Dateien | freier RAM |
|---|---|---|
| res_clips (3 Clips + 175 FLEURS) | 178 | 5 674 440 KB |
| res_test (test + extra) | 114 | 5 107 676 KB |
| res_short (45 Kurzmemos + Fauré) | 46 | 5 540 444 KB |
| test_engine_model.py mit Modellen | 8 Tests | 5 838 476 KB |

338 Dateien statt 337: sing_fr_debussy kam diesmal durch (in 03-13 Commons-429), daher eine Testdatei mehr (nonspeech 15 statt 14). Commons gab wieder 429; sing_en_california und sing_fr_choir_faure kamen über zwei weitere Läufe von fetch_commons_retry.py.

### Messtabelle (eval23.py)

| Gruppe | Dateien | mit 2. Durchgang | Fenster | alt behalten | lid/p (alt behalten) | conf_mean (alt behalten) | Wörter 2. Durchgang alt | neu (T 0,68) | Urteilswechsel |
|---|---|---|---|---|---|---|---|---|---|
| instance | 175 | 26 | 19 | 5 | en 0,975 / 0,991 / 0,996, fr 0,315, fr 0,748 | 0,610 bis 0,877 | 27 | 26 | 1 |
| nonspeech | 15 | 0 | 0 | 0 | - | - | 0 | 0 | 0 |
| sung | 3 | 0 | 0 | 0 | - | - | 0 | 0 | 0 |
| foreign | 67 | 61 | 61 | 0 | - | - | 0 | 0 | 0 |
| unsupported | 78 | 71 | 71 | 1 | en 0,249 | 0,658 | 2 | 0 | 1 |

instance-Dateien mit Wörtern aus dem zweiten Durchgang (bestes Fenster):

| Datei | Pflicht-Memo | Wörter | lid | p | conf_mean | conf_min | mit T 0,68 |
|---|---|---|---|---|---|---|---|
| memo3s_en_us_00 | nein | 6 | en | 0,991 | 0,7987 | 0,2245 | bleibt |
| memo3s_en_us_02 | nein | 10 | en | 0,996 | 0,8767 | 0,2797 | bleibt |
| short4w_en_us_04 | ja | 7 | en | 0,975 | 0,7395 | 0,1716 | bleibt |
| short2w_fr_fr_11 ("Tout bien.") | ja | 2 | fr | 0,315 | 0,7034 | 0,5234 | bleibt |
| short2w_fr_fr_02 ("Il ajoute.") | ja | 2 | fr | 0,748 | 0,6098 | 0,284 | **fällt weg, no_speech** |

Kein short1w und keine DE-Memo bekam Wörter aus dem zweiten Durchgang; es gibt also keinen 1-Wort-Fall in der Messung.

Fremdgruppen: einziges alt behaltenes Fenster ist **fleurs_ja_jp_00** mit 2 Wörtern, latin 1,0, lid en, p 0,249, conf_mean 0,658, conf_min 0,5275 ("Internet today."). Mit T 0,68: DROP_CONFIDENCE, Datei wechselt von transcript zu unsupported_language.

### Schwelle

- Planregel (sichere Instanzsprache p >= 0,9 plus Konfidenz): L = 0,5, U = 0,7395, aber zwei Pflicht-Memos ohne sichere Sprache (fr_11 p 0,315, fr_02 p 0,748): **nicht eindeutig**. Checkpoint an den Owner mit Optionen A bis D.
- **Owner-Entscheid Option A (14.11.2026):** nur Konfidenz, keine Sprachbedingung über die bestehende Abfangregel hinaus. T = 0,68 = Mitte der Lücke zwischen JA 0,658 und fr_11 0,7034, auf zwei Stellen abgerundet.
- Offen gesagt: Der Abstand ist knapp (0,658 gegen 0,7034, 0,045), die Stichprobe klein (5 instance-Dateien, 1 Fremd-Fenster). short2w_fr_fr_02 ("Il ajoute.", 0,6098) verliert sein Transkript und zeigt "keine Sprache" (no_speech). Unter 0,68 läge keine Wahl, die JA ausschließt und fr_02 behält.

## Regel

`window_verdict(latin, lid, lid_p, n_words, conf_mean, *, second_pass=False)`: Schrift- und Sprachprüfung unverändert vorn; mit `second_pass=True` danach KEEP genau bei `conf_mean >= SECOND_PASS_CONF`, sonst DROP_CONFIDENCE. Ohne Schlüsselwort und mit `second_pass=False` genau wie vorher (alle Bestandsfälle zusätzlich mit `second_pass=False` geprüft). `parakeet.transcribe` reicht `second_pass=second_pass` weiter; worker/preview.py bleibt unverändert (take zählt DROP_CONFIDENCE als drop_conf).

Abweichend vom Plantext (durch Option A): "es" mit p 0,98, 2 Wörtern, conf 0,97 ist im zweiten Durchgang KEEP (keine Sprachbedingung), eine sichere Instanzsprache mit conf 0,55 ist im zweiten Durchgang DROP_CONFIDENCE (die untere Grenze 0,5 gilt dort nicht).

## CONFIG_VERSION

`CONFIG_VERSION: Final = 2`. Die Regel lässt Wörter aus Transkripten wegfallen (anders als D-03-22, das nur den Grund einer Datei ohne Transkript änderte); nach constants.py ("Every changed value needs a new CONFIG_VERSION", TRANS-06) also neue Version. Keine Migration: 0.3.0 ist unveröffentlicht, keine Installation hat Vorschauen mit Version 1. api/sample.py behält seine eigene Probe-Version 1.

## Gegenprobe

- `eval23.py --check` (eigene Formel in eval23.py, nicht aus catch): 151 Fenster des zweiten Durchgangs, **0 Abweichungen** gegen `catch.window_verdict(..., second_pass=True)` mit `SECOND_PASS_CONF = 0.68`.
- Positivkontrolle (Skript im Scratch, window_verdict ohne neue Regel eingesetzt): 2 Abweichungen (JA 00, fr_02), Exit 1.
- RED-Lauf vor der Umsetzung: 33 rot (TypeError wegen fehlendem Schlüsselwort, AttributeError SECOND_PASS_CONF, Fingerabdruck, CONFIG_VERSION, Engine-Test), danach grün.
- Testfall `ja-00-first-pass-kept-positive-control`: die alte Regel lässt JA durch (KEEP), `ja-00-second-pass-dropped` DROP_CONFIDENCE.

## Gates

- ruff check und format --check (backend, ../scripts), pyright latest 0 Fehler, vulture still.
- test_engine_model.py mit echten Modellen und Clips: 8 passed.
- Volle Suite: **1 failed, 1891 passed, 15 skipped** (ohne Modell-Umgebung). Der eine Fehler ist der erwartete Owner-Hinweis unten.
- Gedankenstrich-Prüfung (Bytes U+2013/U+2014) aller geänderten Dateien: 0 Treffer; Prüfer an einer Probe mit U+2014 positiv (1).
- tests/test_vad_gate.py unverändert und grün; worker/preview.py und main.py in keinem 03-13b-Commit.
- Scratch gelöscht; `git status` ohne .wav/.onnx/.json.

## Deviations from Plan

### Owner-Hinweis: Test erwartet CONFIG_VERSION 1 fest

`backend/tests/test_preview_worker.py:636` (`test_after_the_first_chunk_the_media_is_findable_as_a_preview`, aus 03-13) vergleicht die Provenienz mit der festen Zahl `1` statt mit `constants.CONFIG_VERSION`. Mit Version 2 ist er rot. Nach Vorgabe nicht geändert. Entscheidung für den Owner: (a) Zeile 636 auf `CONFIG_VERSION` aus engine/constants umstellen (empfohlen, Version 2 bleibt) oder (b) CONFIG_VERSION bei 1 lassen (dann Wert- und Fingerabdrucktest zurück auf 1).

### Weitere

1. **Owner-Entscheid statt Planregel:** Messung nach Plan mehrdeutig, Checkpoint, Option A gewählt; eval23.py in einem eigenen Commit (01b5f1f) auf die Option-A-Formel umgestellt, die Planregel bleibt als Messung in der Ausgabe.
2. **verdict23.py speichert zusätzlich** `text` und `kept_n` je Fenster (nur im Scratch). Unschärfe: memo3s_en_us_02 kept_n 11, take() zählt 10 (ein Wort vor 0 ms); ohne Einfluss auf Urteile und Gegenprobe.
3. **test_the_fingerprint_sees_every_constant_the_value_tests_name** eingeengt: statt "keine Zeile catch.SECOND_PASS*" jetzt "keine Zeile catch.SECOND_PASS_MAX_FILE_MS" plus `catch.SECOND_PASS_CONF=0.68` vorhanden.
4. **Regelverstoß des Ausführers:** Einmal `uv run python -I -c` zum Lesen von 6 Ergebnis-JSONs im Scratch benutzt (nur Lesen, nichts im Repo). Danach nur noch Skriptdateien.
5. Bestehende Parametrisierung in test_catch_rule.py als Liste `FIRST_PASS` herausgezogen, damit dieselben Fälle auch mit `second_pass=False` laufen.
6. eval23-Ausgabe unter Windows nur mit `PYTHONUTF8=1` als UTF-8 umleitbar.

## Threat Flags

Keine neue Angriffsfläche; T-03-80 bis T-03-84 wie geplant gemindert (T-03-84: Schwelle nicht geraten, Owner-Entscheid nach Messtabelle).

## Self-Check: PASSED

- Dateien vorhanden: verdict23.py, eval23.py, catch.py mit `SECOND_PASS_CONF: Final = 0.68`, parakeet.py mit `second_pass=second_pass`.
- Commits vorhanden: aba5f97, 01b5f1f, e50efd7, d294e8f.
