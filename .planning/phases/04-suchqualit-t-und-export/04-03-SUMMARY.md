---
phase: 04-suchqualit-t-und-export
plan: 03
subsystem: ui-texte
tags: [l10n, exp-04, ui-spec, owner-freigabe]
requires: []
provides:
  - "Katalogschlüssel T13 bis T35 in php/l10n (de, de_DE, en, fr; json und js)"
  - "EXP-04-Gate gegen BITV-Behauptungen mit Selbsttest"
  - "Freigegebener 04-UI-SPEC (status approved) mit geprüften Icon-Pfaden"
affects: [04-10, 04-11, 04-12]
tech-stack:
  added: []
  patterns: ["Text-Gate mit Regex und Selbsttest in test_public_texts.py"]
key-files:
  created:
    - .planning/phases/04-suchqualit-t-und-export/deferred-items.md
  modified:
    - .planning/phases/04-suchqualit-t-und-export/04-UI-SPEC.md
    - php/l10n/de.json
    - php/l10n/de.js
    - php/l10n/de_DE.json
    - php/l10n/de_DE.js
    - php/l10n/en.json
    - php/l10n/en.js
    - php/l10n/fr.json
    - php/l10n/fr.js
    - backend/tests/test_trilingual.py
    - backend/tests/test_public_texts.py
decisions:
  - "Owner-Freigabe 16.11.2026: T13 bis T35 wörtlich wie vorgelegt, O1 bis O10 mit Empfehlung, X3-Lesart mit zwei getrennten Sperrzuständen"
  - "a.button hat in NC 33/34/35 dieselbe Server-Gestalt wie button (core/css/inputs.scss); kein Ersatzstil nötig"
  - "Freigabe-Attribut unentscheidbar ergibt X4 (Abschnitt fehlt), nie einen Sperrsatz T24"
metrics:
  duration: "ca. 40 min (mit Owner-Wartezeit)"
  completed: 2026-11-16
---

# Phase 4 Plan 03: Texte-Schnitt und EXP-04-Gate Summary

Owner-freigegebene Texte T13 bis T35 (Untertitel-Entwurf, Download, Ablage, Fehler, Spurname) in allen acht PHP-Katalogdateien, dazu ein Gate, das jede BITV-Konformitätsbehauptung in Katalogen, Templates, README, docs und info.xml abweist und "Untertitel-Entwurf" / "Subtitle draft" / "Brouillon de sous-titres" je Katalog verlangt.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | Icon-Pfade und Knopfgestalt prüfen, Freigabevorlage | 319ebeb |
| 2 | Owner-Freigabe (Checkpoint, 16.11.2026 freigegeben, ohne Änderungen) | in abd5c49 eingetragen |
| 3 | Kataloge und EXP-04-Gate mit Selbsttest | abd5c49 |

## Ergebnisse

- MDI-Pfade `download`, `file-plus`, `check-circle-outline` gegen Templarian/MaterialDesign-SVG geprüft und im UI-SPEC eingetragen.
- Befund `a.button`: In stable33 (Zeilen 72/213), stable34 und stable35 (Zeilen 63/204) von `core/css/inputs.scss` steht `.button` in denselben Selektorlisten wie `button:not(...)`.
- "Verhältnis zu Phase 3" klärt: `download_blocked` (kein Export-Abschnitt) und X3 (nur T13 + T24) sind zwei Zustände.
- 23 neue Schlüssel (T13 bis T35 ohne T28, T20b, T22a/b, T29b) in de, de_DE, en, fr; js-Zwillinge über `scripts/l10n_js.py` erzeugt.
- Neue Tests: `test_no_text_claims_bitv_conformity_for_drafts`, `test_every_catalogue_names_the_subtitle_draft` (inkl. T15/T35 ohne `-->` und Zeilenumbruch), `test_the_bitv_rule_fires` (9 Muster), `test_the_bitv_rule_leaves_the_draft_alone` (Gegenprobe inkl. "BITV-relevant").

## Deviations from Plan

- **[Rule 2] Gate-Umfang:** Das BITV-Gate prüft zusätzlich `docs/*.md` (Nutzerdokumente, ebenfalls öffentliche Texte) und erkennt den französischen Plural "conformes BITV". Dazu kommt ein Gegenprobe-Test, damit "BITV-relevant" (PRODUCT.md-Wortlaut) nicht anschlägt.
- **[Rule 2] T-04-09:** Die Prüfung auf Zeilenumbrüche in T15/T35 ist zusätzlich zu `-->` umgesetzt (Threat-Register).

## Deferred Issues

- `test_every_user_document_exists_in_three_languages` ist rot, weil `docs/security-guidelines-abgleich.md` (Commit 09c3297, außerhalb dieses Plans) ohne EN/FR-Fassung ist. Siehe `deferred-items.md`. Alle anderen 47 Tests der beiden Dateien sind grün; ruff, ruff format, pyright und vulture sind grün.

## Known Stubs

Keine. Die neuen Schlüssel werden erst von 04-10 bis 04-12 im Template genutzt; das ist geplant.

## Self-Check: PASSED

- Dateien vorhanden: 04-UI-SPEC.md (status approved), php/l10n/*.json/js, deferred-items.md
- Commits vorhanden: 319ebeb, abd5c49
