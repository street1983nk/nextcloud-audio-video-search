---
phase: 03-vorschau-transkripte-in-der-suche
plan: 19
subsystem: release, ci, doku
tags: [version, lockstep, upgrade, positive-control, models, docs, trilingual, changelog]
requires: ["03-17", "03-18", "03-18b"]
provides:
  - "Lockstep 0.3.0 in beiden info.xml, pyproject.toml, uv.lock, admin.spec.ts"
  - "deploy-harp.yml Job upgrade: vom echten 0.2.0 (a99565a2, Spitze origin/phase-02), Vorher-Kontrolle Schema 2 ohne preview_job und oc_avs_queue ohne origin, Modelle ins Volume vor dem Update, Nachher Schema 3, preview_job, origin, byPreview"
  - "Abschnitt Transkription (Vorschau) in docs/install DE/EN/FR, README-Stand 0.3.0, CHANGELOG 0.3.0"
affects: [03-20, 03-21]
key-files:
  created:
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-19-SUMMARY.md
  modified:
    - php/appinfo/info.xml
    - backend/appinfo/info.xml
    - backend/pyproject.toml
    - backend/uv.lock
    - ci/playwright/admin.spec.ts
    - .github/workflows/deploy-harp.yml
    - backend/tests/test_workflows.py
    - docs/install.md
    - docs/install.en.md
    - docs/install.fr.md
    - README.md
    - README.en.md
    - README.fr.md
    - CHANGELOG.md
decisions:
  - "Modelle im Upgrade-Job nach der Vorher-Kontrolle und vor app_api:app:update ins vorhandene Volume (0.2.0 braucht keine), gleicher Cache-Schlüssel wie deploy-harp, Nachweis: /init von 0.3.0 lädt nichts"
  - "Owner 14.11.2026: Entwürfe freigegeben, FFmpeg-Zeile in allen drei README, zusätzliche Anforderungen-Zeile zu Arbeitsspeicher und Speicherplatz"
metrics:
  duration: "ca. 1 h 30 min"
  completed: 2026-11-14
  tasks: 3
  files: 14
---

# Phase 3 Plan 19: Version 0.3.0, Upgrade vom echten 0.2.0, Doku Summary

Beide Apps tragen 0.3.0. Der Upgrade-Job baut prev/ aus dem echten 0.2.0 (a99565a2243f5c1e11adfb71fc2909a1b6c88fe8), prüft vorher Schema 2 ohne preview_job und oc_avs_queue ohne origin, legt die Modelle ins Volume und prüft nachher Schema 3, preview_job, origin, gleiche Inode und byPreview. Doku, README und CHANGELOG beschreiben die Vorschau-Transkription in DE, EN und FR, vom Owner freigegeben.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 | 316f0d3 | chore(03-19): Version 0.3.0 und Upgrade-Beweis vom echten 0.2.0 |
| 2 | (keiner) | Entwürfe gezeigt, Owner-Freigabe 14.11.2026 |
| 3 | d81bec4 | docs(03-19): Vorschau-Transkription in DE, EN und FR beschrieben |

Alle lokal, Autor und Committer street1983nk <k.cherif@outlook.de>. Kein Push, kein Tag, kein Docker.

## Task 1

- PREV_COMMIT mit `git rev-parse origin/phase-02` bestätigt, `<version>0.2.0` in dessen php/appinfo/info.xml.
- Vorher-Kontrolle ("upgrade positive control failed"): schema_version 2, keine Tabelle preview_job, Probe in sample_ref mit Transkript (current); `PRAGMA table_info(oc_avs_queue)` mit file_id, ohne origin. Status `.schemaVersion == 2`.
- Neue Schritte: Cache key of the speech models, Restore, Fetch on a cache miss (procure aus dem 0.3.0-Image), Put the speech models into the volume before the update (uid 10001, ohne verified.json), After the update, the models came from the volume (init 100, outcome present, models ready).
- Nachher: `.schemaVersion == 3`, preview_job, sample_ref mit Transkript, keine alten file_ref-Zeilen, origin in oc_avs_queue, `has("byPreview")`; Inode und Volume gleich, Treffer gleich. Frist 45 auf 60 min. procure-lines.json im Log-Artefakt.
- test_workflows.py vorher rot (lifecycle, 17 Befunde), nachher grün; neue Regeln `upgrade_model_findings` und schrittgenaue Vorher-/Nachher-Prüfung mit Positivkontrollen (Commit von 0.1.0, fehlende Tabelle/Spalte, Modelle nach dem Update, kein Modellnachweis).

## Task 2 und 3: Freigabe und Texte

Owner 14.11.2026: Entwurf drafts_03_19.diff freigegeben; FFmpeg-Zeile unter Bestandteilen Dritter in allen drei Sprachen ja; zusätzlich eine Anforderungen-Zeile. Eingespielt (docs und CHANGELOG byte-gleich zum Entwurf geprüft):

- DE: `- Arbeitsspeicher: ca. 2,2 GB frei (1,7 GB plus 0,5 GB Reserve); Speicherplatz: ca. 0,67 GB für die Sprachmodelle`
- EN: `- Memory: about 2.2 GB free (1.7 GB plus a 0.5 GB reserve); disk space: about 0.67 GB for the speech models`
- FR: `- Mémoire : environ 2,2 Go libres (1,7 Go plus 0,5 Go de réserve) ; espace disque : environ 0,67 Go pour les modèles vocaux` (mit U+00A0 vor : und ;)

Speicherplatz als 0,67 GB statt "ca. 0,7 GB", weil der Owner Werte exakt wie in docs/install.md verlangte.

## Gates

- pytest komplett 1909 passed, 15 skipped (ein vorheriger Lauf hatte 1 failed, beim Wiederholen grün; Test nicht festgehalten, vermutlich zeitabhängig unter Last).
- test_trilingual, test_public_texts, test_public_artifacts, test_store_metadata: 50 passed. Lockstep, workflows, store_metadata: 80 passed.
- ruff check, ruff format, pyright latest 0 Fehler, vulture still; actionlint ohne Befund; shellcheck 0.11.0 auf allen 21 run-Blöcken des Upgrade-Jobs ohne Befund (Positivkontrolle meldet).
- Kontrollblöcke gegen 15 synthetische Datenbanken: alle wie erwartet.
- CC-BY-4.0 je README genau einmal, keine U+2013/U+2014, Umlaut-Audit der deutschen Zusätze ohne ASCII-Ersatz.
- PHP-Tests lokal nicht möglich (kein php), erst CI.

## Deviations from Plan

1. [Regel 3] admin.spec.ts VERSION auf 0.3.0, weil das Lockstep-Gate sie liest.
2. [Regel 3] CHANGELOG in Task 1 nur mit Überschrift `## 0.3.0` (test_store_metadata), Einträge nach Freigabe in Task 3 (wie 02-21).
3. README mit vier statt höchstens drei geänderten Stellen plus Anforderungen-Zeile, beides vom Owner freigegeben bzw. verlangt.
4. Testtreffer-Einleitung der Doku ("Phase 1 transkribiert noch nicht") im Faktencheck ersetzt.

## Erst die CI zeigt (03-20)

- Ob der Upgrade-Job grün läuft: Seed und sample gegen 0.2.0, Probe in sample_ref, Modell-Kopie ins vorhandene Volume (Eigentümer 10001), /init von 0.3.0 mit outcome present, gleiche Treffer nach dem Update trotz Transkription der Töne, Laufzeit unter 60 min.
- PHP-Tests mit 0.3.0.

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche. T-03-63/64 über echten Commit, Vorher-Kontrolle und Inode; T-03-65 über belegte Hosts (03-07b), Owner-Freigabe und Faktencheck.

## Self-Check: PASSED

- FOUND: alle 14 Dateien, Commits 316f0d3 und d81bec4.
