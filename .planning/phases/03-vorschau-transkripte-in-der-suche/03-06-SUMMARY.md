---
phase: 03-vorschau-transkripte-in-der-suche
plan: 06
subsystem: engine
tags: [parakeet, vad, abfangregel, dateiurteil, konstanten, gate, tdd]
requires: []
provides:
  - "engine/constants.py: Spike-3-Pipeline (SAMPLE_RATE, VAD_*, MERGE_GAP_S, WINDOW_MAX_S, CONTEXT_S, PAD_S, MIN_DECODE_S, TOKEN_S, GUARD_*, RECOGNIZER_THREADS, DECODING_METHOD, MODEL_TYPE), SECOND_PASS_* (D-03-16), CHUNK_* (TRANS-07), CONFIG_VERSION = 1"
  - "engine/catch.py: window_verdict, file_verdict, latin_share, needs_second_pass, INSTANCE, Schwellen aus M-8/M-9, Ergebnis-Konstanten KEEP, DROP_SCRIPT, DROP_LANGUAGE, DROP_CONFIDENCE, TRANSCRIPT, NO_SPEECH, UNSUPPORTED_LANGUAGE"
  - "tests/test_vad_gate.py: scan(root) mit Positivkontrollen; erlaubt in engine/ nur os.environ.update(<KONSTANTE>)"
affects: [03-10, 03-13]
tech-stack:
  added: []
  patterns:
    - "Gemessene Werte als Final-Konstanten plus Fingerabdruck-Test, der bei jeder Änderung eine neue CONFIG_VERSION verlangt"
    - "Text-Sprachkennung kommt als Argument (lid, lid_p); py3langid erst in 03-10"
key-files:
  created:
    - backend/src/audio_video_search_backend/engine/__init__.py
    - backend/src/audio_video_search_backend/engine/constants.py
    - backend/src/audio_video_search_backend/engine/catch.py
    - backend/tests/test_catch_rule.py
    - backend/tests/test_engine_constants.py
    - backend/tests/test_vad_gate.py
  modified: []
decisions:
  - "Sekundenwerte als float (VAD_MAX_SPEECH_S 25.0, VAD_BUFFER_S 60.0, MERGE_GAP_S 2.0, WINDOW_MAX_S 25.0); Zahlenwert gleich measure.py"
  - "Dateiurteil: Sprachanteil = speech_ms / duration_ms, bei Dauer 0 gleich 0,0 (wie verdict.py)"
  - "Schalterwort-Regel weiter als im Plan: (skip|disabl|bypass|unsafe)[a-z]*[_-]?(vad|catch), weil das Plan-Muster disable_catch und disabled_vad nicht fand"
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-14
  tasks: 2
  files: 6
---

# Phase 3 Plan 06: Spike-3-Konstanten, Abfangregel, Dateiurteil, VAD-Gate Summary

Die Werte der Parakeet-Vorschau aus measure.py, die Abfangregel je Fenster (M-8) und das Dateiurteil (M-9) sind jetzt reine Konstanten und Funktionen mit Tests. Ein Fingerabdruck hält alle Werte fest, und ein Quelltext-Gate ohne Abschaltweg schützt VAD und Regel.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 RED | 1c9c725 | test(03-06): Abfangregel, Dateiurteil und Spike-3-Konstanten als Fälle |
| 1 GREEN | 90e2874 | feat(03-06): Spike-3-Konstanten, Abfangregel und Dateiurteil |
| 2 | 0d5f9dc | test(03-06): VAD und Abfangregel ohne Abschaltweg |

## Ergebnisse

- test_catch_rule.py: 13 window_verdict-Fälle (10 aus dem Plan, 3 Grenzen für p 0,9, Wortzahl 3 und C2 0,5), 15 file_verdict-Fälle (7 aus dem Plan, 8 Grenzen: script+language 5, Wortzahl 10/9, Sprache 10 s, Anteil 30 %, ein behaltenes Wort, leere Datei), 6 latin_share-, 4 needs_second_pass-Fälle.
- test_engine_constants.py: 26 Pipeline- und 10 Abfangwerte einzeln gegen measure.py bzw. M-8/M-9, Fingerabdruck aller 43 Konstanten als fester Text mit der Meldung "constant changed: raise CONFIG_VERSION and update this fingerprint".
- Probe der Abnahme: CONF lokal auf 0.55 gesetzt, 4 Tests rot (Fall unsure-instance-below-0.6, CONF-Wert, Fingerabdruck, Fingerabdruck-Helfer), danach zurückgesetzt und wieder grün.
- test_vad_gate.py: echter Baum ohne Meldung, 23 Gegenproben auf Kopien (Env-Lesen in engine/constants.py genau eine Meldung, SettingsField vad_threshold genau eine Meldung, SettingsField über mehrere Zeilen, os.environ.update(THREAD_ENV) keine Meldung, os.environ["X"] genau eine Meldung, 9 weitere Lesearten in engine/, zwei Routen, Env-Lesen eines VAD-Werts außerhalb engine/, 6 Schalterwörter inklusive php/lib), dazu Selbsttest für harmlose Wörter (configured, skip_reason).
- Volle Suite: 1295 passed (vorher 1266). ruff check, ruff format --check, pyright (latest, 0 Fehler), vulture grün.
- `grep -nE "os\.environ|getenv|settings"` auf catch.py und constants.py: keine Treffer.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Schalterwort-Muster des Plans zu eng**
- **Found during:** Task 2, durch die Gegenprobe `def disable_catch()`
- **Issue:** `(skip|disabl|bypass|unsafe)_?(vad|catch)` findet `disable_catch` und `disabled_vad` nicht (nach "disabl" folgt "e").
- **Fix:** `(skip|disabl|bypass|unsafe)[a-z]*[_-]?(vad|catch)`; Gegenproben für disable_catch, disabled_vad, skip-vad ergänzt.
- **Commit:** 0d5f9dc

**2. [Rule 2 - Härtung] Gate strenger als die Plan-Muster**
- In engine/ ist jede Nutzung von `environ` eine Meldung außer genau `os.environ.update(<KONSTANTE>)`; so fallen auch `dict(os.environ)`, `.copy()`, `in os.environ`, `from os import environ` und `update(<Aufruf>)` auf. Importe von settings, config und nc aus engine/ werden gemeldet.
- SettingsField und Routen werden zusätzlich per AST geprüft (die echte Form schreibt die id in eine eigene Zeile, die reine Zeilenregel hätte sie verfehlt); alle Texte und Namen in settings.py werden auf die Wörter geprüft.
- Wortliste um `confidence` ergänzt; Wortgrenzen nur an Buchstaben, damit `vad_threshold` und `AVS_VAD` treffen, `configured` nicht.

**3. RED-Commit enthält engine/__init__.py**
- Ohne das Paket ordnet ruff den Import als Fremdpaket ein (I001). test_catch_rule.py importiert deshalb `from audio_video_search_backend.engine import catch`; der RED-Stand war ruff-grün und schlug in pytest mit ImportError fehl.

## TDD Gate Compliance

RED 1c9c725 (test), GREEN 90e2874 (feat), danach Task 2 als test-Commit 0d5f9dc. Kein Refactor nötig.

## Known Stubs

Keine. Die Funktionen sind vollständig; ihre Nutzung im Kindprozess folgt in 03-10, die Ablage in 03-13.

## Offene Punkte

- py3langid nicht installiert (wie vorgegeben); window_verdict nimmt lid und lid_p als Argumente.
- Zwischen GREEN und Task 2 liegt der fremde Commit 443b747 (docs(03): D-03-20), nicht von diesem Plan.

## Self-Check: PASSED

Dateien vorhanden: engine/__init__.py, constants.py, catch.py, test_catch_rule.py, test_engine_constants.py, test_vad_gate.py. Commits vorhanden: 1c9c725, 90e2874, 0d5f9dc.
