---
phase: 05-ressourcen-profile-und-modellbezug
plan: 06
subsystem: php/l10n
tags: [RES-01, RES-05, RES-06, RES-07, l10n, dreisprachig]
requires: []
provides:
  - "T36 bis T96 (ohne T51, T82; T83a und T83b) in php/l10n/{de,de_DE,en,fr}.{json,js}"
  - "backend/tests/test_l10n_phase5.py: 60 Zeilen wörtlich aus 05-UI-SPEC.md, NBSP, keine Zahl in T48/T50"
affects: [05-09]
tech-stack:
  added: []
  patterns: ["Katalogtexte maschinell aus der freigegebenen UI-SPEC-Tabelle gelesen, nicht abgetippt"]
key-files:
  created:
    - backend/tests/test_l10n_phase5.py
  modified:
    - php/l10n/de.json
    - php/l10n/de.js
    - php/l10n/de_DE.json
    - php/l10n/de_DE.js
    - php/l10n/en.json
    - php/l10n/en.js
    - php/l10n/fr.json
    - php/l10n/fr.js
decisions:
  - "Die Texte wurden per Skript aus der Tabelle 'Neue Texte DE / EN / FR' in 05-UI-SPEC.md gelesen; FR bekommt U+00A0 vor : ; ? ! (betrifft T37, T45, T56 zweimal, T76)"
  - "Die Datei-Ausnahme '# ruff: noqa: E501' in test_l10n_phase5.py, damit jeder freigegebene Text auf einer Zeile wörtlich steht"
  - "Der Dash-, Emoji- und BITV-Test prüft die 60 Phase-5-Texte (Bestandstexte prüft test_trilingual.py)"
metrics:
  duration: "ca. 30 min"
  completed: 2026-11-18
  tasks: 2
  files: 9
---

# Phase 5 Plan 06: Kataloge T36 bis T96 Summary

Die vom Owner am 18.11.2026 freigegebenen Texte T36 bis T96 stehen wörtlich in de, de_DE, en und fr (.json und .js); der englische Text ist der Schlüssel, Französisch trägt das geschützte Leerzeichen vor hohen Satzzeichen.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Test für die Phase-5-Texte (RED) | 937f39a | tests/test_l10n_phase5.py |
| 2 | Kataloge schreiben (GREEN) | f4fc879 | php/l10n/*.json, php/l10n/*.js |

## Ergebnis

- 60 Einträge (T36 bis T96 ohne T51 und T82, T83 als T83a und T83b). T96 kam schon mit Plan 05-05 (e390174) in die Kataloge, hier 59 neue Schlüssel, je Datei angehängt.
- `grep -c "Transcription profile" php/l10n/fr.json` = 1, `grep -c "Profil de transcription" php/l10n/fr.json` = 1.
- T48 und T50 enthalten keine Ziffer außer in Platzhaltern (D-05-09).
- Bestandsschlüssel Saved, "Not saved. Try again.", "Checking…" unverändert.
- .js-Zwillinge mit `scripts/l10n_js.py` neu erzeugt; `node --check` auf allen php/js- und php/l10n-Dateien grün.

## Verification

- `tests/test_l10n_phase5.py tests/test_trilingual.py tests/test_php_gates.py tests/test_public_texts.py`: 108 passed.
- Voller Lauf: 2464 passed, 18 skipped, 4 xfailed; ruff, ruff format, pyright basic (latest), vulture grün.

## Deviations from Plan

- T96 war bereits durch Plan 05-05 eingetragen (dort als Rule-3-Abweichung dokumentiert); dieser Plan prüft ihn mit.
- Sonst keine.

## TDD Gate Compliance

RED (937f39a, 4 Tests rot) vor GREEN (f4fc879).

## Self-Check: PASSED

- test_l10n_phase5.py vorhanden, acht Katalogdateien geändert.
- Commits 937f39a und f4fc879 vorhanden.
