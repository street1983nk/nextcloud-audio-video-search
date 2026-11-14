---
phase: 03-vorschau-transkripte-in-der-suche
plan: 01
subsystem: freigaben-ui-vertrag
tags: [owner-freigabe, package-legitimacy, copywriting, ui-spec]
requires: []
provides:
  - "Paketfreigabe sherpa-onnx 2.0.1, sherpa-onnx-core 2.0.1, numpy 2.5.4, py3langid==0.4.0 mit sha256 je Wheel (für Plan 03-10)"
  - "Freigegebener Modell-Fehlertext MODELS_FAILED (für Plan 03-07)"
  - "Freigegebene Texte Einstellungsfeld Höchstdauer, Deckel 24 h (für Plan 03-11, 03-15, 03-16b)"
  - "03-UI-SPEC.md: A13 disk_full, Positivliste, P13, Wahrheitsbedingungen"
affects: [03-07, 03-10, 03-11, 03-13, 03-15, 03-16b]
tech-stack:
  added: []
  patterns: []
key-files:
  created:
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-01-SUMMARY.md
  modified:
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-UI-SPEC.md
decisions:
  - "Alle vier Laufzeitpakete freigegeben (Owner: \"Alle freigegeben\")"
  - "Texte Einstellungsfeld und Modell-Fehler freigegeben (Owner: \"Freigegeben\"); Deckel der Höchstdauer 24 h, Standard 12 h (Owner: \"24 h reicht\")"
  - "T12 nicht erneut vorgelegt, Zeile in 03-UI-SPEC.md zeichengleich"
metrics:
  duration: "ca. 5 min (Task 3; Task 1 und 2 in der Hauptsitzung)"
  completed: 2026-11-14
  tasks: 3
  files: 2
---

# Phase 3 Plan 01: Owner-Freigaben und UI-Nachtrag Summary

Lieferkette sherpa-onnx/sherpa-onnx-core/numpy/py3langid mit sha256 je Wheel freigegeben, Einstellungs- und Modell-Fehlertexte DE/EN/FR freigegeben (Deckel 24 h), 03-UI-SPEC.md um A13 `disk_full`, P13 und Wahrheitsbedingungen ergänzt.

## Task 1: Paket-Legitimität (Hauptsitzung, 14.11.2026)

Owner-Antwort wörtlich: **"Alle freigegeben"** (nach Empfehlung der Hauptsitzung). PyPI-JSON gelesen, nichts installiert.

| Paket | Version | Lizenz | Upload | Quelle | Wheel amd64 (sha256) | Wheel arm64 (sha256) | requires |
|-------|---------|--------|--------|--------|----------------------|----------------------|----------|
| sherpa-onnx | 2.0.1 | Apache-2.0 (PyPI-Feld "Apache licensed, as found in the LICENSE") | 2026-10-26 | github.com/k2-fsa/sherpa-onnx | sherpa_onnx-2.0.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl `a52606059a84495374bbd752c8de2b36d3f018cd715eddac559686b4e6868789` | sherpa_onnx-2.0.1-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl `dae9c8972e2dfe1fcaccdc48f7465f0db2e4220f1f7b299b4c0970a5f46c66e2` | sherpa-onnx-core==2.0.1 |
| sherpa-onnx-core | 2.0.1 | Apache-2.0 | 2026-10-26 | github.com/k2-fsa/sherpa-onnx | sherpa_onnx_core-2.0.1-py3-none-manylinux2014_x86_64.whl `f4ee0ab91c4ae596e0e49d7de32522a946295e038a652f1c1884d89014ee4ec2` | sherpa_onnx_core-2.0.1-py3-none-manylinux2014_aarch64.whl `4a855a5c89c89885111e4e9c570e5da1aed63373c031b757d8046792d95fe8fe` | keine |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 2026-10-10 | github.com/numpy/numpy | numpy-2.5.4-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl `6ffa07666f8da0eef81d149934a626d0d95fbd6838432a33e66245423a9062c0` | numpy-2.5.4-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl `1c2e71b04c6cad90026e544501bbe0ab9290fa8a4d845e7e8c0d124fb429c988` | keine |
| py3langid | 0.4.0 | BSD-3-Clause (LICENSE v0.4.0 gelesen; GitHub-API meldet NOASSERTION wegen Kopfsatz) | 2026-09-02 | github.com/adbar/py3langid (Tag v0.4.0, pushed 2026-10-29, nicht archiviert) | py3langid-0.4.0-py3-none-any.whl `c25bd038147951ba3a89efe9ec12cc7d2116cb6f311ff8af84ade398a8bc0616` (heruntergeladen, sha256 stimmt) | dasselbe Wheel | numpy>=2.0.0 (dev-Extras pytest) |

Wheel-Inhalt py3langid: `__init__.py`, `langid.py`, `modelio.py`, `server.py`, `data/model.npz.xz` (4,6 MB), dist-info; keine Installationsskripte, keine `.pth`.

Pins für Plan 03-10: `sherpa-onnx==2.0.1`, `sherpa-onnx-core==2.0.1`, `numpy==2.5.4`, `py3langid==0.4.0`.

**Auflage für Plan 03-10:** Test, dass `py3langid.server` nie importiert wird.

slopcheck nicht ausgeführt (Hinweis aus der Hauptsitzung).

## Task 2: Texte und Deckel (Hauptsitzung, 14.11.2026)

Owner-Antwort wörtlich: **"Freigegeben"**; zum Deckel: **"24 h reicht"**. T12 wurde nicht erneut vorgelegt (seit 14.11. in 03-UI-SPEC.md freigegeben).

Freigegebene Endfassungen (englischer Text ist l10n-Schlüssel):

| Element | EN | DE | FR |
|---------|----|----|----|
| Feld-Titel | Longest recording in hours | Längste Aufnahme in Stunden | Durée maximale d'un enregistrement en heures |
| Feld-Beschreibung | Longer recordings are skipped as too long. If the limit is raised, they are transcribed later. | Längere Aufnahmen werden als überlang übersprungen. Wird die Grenze angehoben, werden sie später transkribiert. | Les enregistrements plus longs sont ignorés car trop longs. Si la limite est relevée, ils seront transcrits plus tard. |
| Modell-Fehler (MODELS_FAILED) | Audio & Video Search could not download its speech models. Details are in the log of the ExApp. | Audio & Video Search konnte die Sprachmodelle nicht laden. Details stehen im Protokoll der ExApp. | Audio & Video Search n'a pas pu télécharger ses modèles vocaux. Les détails figurent dans le journal de l'ExApp. |

Deckel der Einstellung: 24 h, Standard 12 h. Keine höhere Grenze in Phase 3, also keine Zusatzaufgabe für Plan 03-11/03-16.

## Task 3: Nachtrag 03-UI-SPEC.md

Commit `c5da6f8` `docs(03-01): UI-Vertrag um Speicherplatz-Grund und Einstellungstexte ergänzt`:
- Kopfzeile "Nachtrag 14.11.2026 (Plan 03-01) ..."
- Zustandstabelle: A13 `disk_full`, Erkennung "Grund disk_full (Datei wartet auf Speicherplatz)", Inhalt `hint` T12
- Leck-Regel: Positivliste um `disk_full` erweitert
- Copywriting: Unterabschnitte "Einstellungsfeld Höchstdauer (Admin, deklarative Einstellung)" und "Fehlertext beim Aktivieren (AppAPI-Status)"
- Wahrheitsbedingungen: T12 Satz 2 (Plan 03-13, DISK_FULL_RETRY_SECONDS) und Beschreibung Höchstdauer Satz 2 (Plan 03-15)
- Prüfvertrag: P13 "Abspielseite A13 zu wenig Speicherplatz", 1280 hell, FR 375 hell

Verify: grep A13/disk_full/T12/P13 grün, Gedankenstrich-Prüfung `[]` (Exit 0), `grep -c disk_full` = 3, `git diff` zeigt an der Zeile "| T12 |" keine Änderung.

## Deviations from Plan

Keine. Task 1 und 2 wurden laut Auftrag in der Hauptsitzung erledigt; deren Verify-Befehle (PyPI-curl, `test_trilingual.py`) wurden hier nicht erneut ausgeführt.

## Self-Check: PASSED

- FOUND: .planning/phases/03-vorschau-transkripte-in-der-suche/03-UI-SPEC.md
- FOUND: Commit c5da6f8
