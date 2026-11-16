---
phase: 04-suchqualit-t-und-export
plan: 14
subsystem: ci/e2e
tags: [SRCH-04, SRCH-05, SRCH-06, EXP-01, EXP-02, EXP-04, S6, S7, playwright, fleurs, deploy-harp]
requires:
  - "04-02, 04-06: Zahlenraum und Präfix-Klausel (numbers.recognize, PREFIX_MIN_CHARS), Beifang-Zählung mit ngerman"
  - "04-04: tests/subtitle_checkers.py (check_vtt, check_srt, check_ffmpeg)"
  - "04-09, 04-11, 04-12: Export-Route, Filter (SearchFilters), Download-Sperre"
provides:
  - "fetch_speech.py: S7Targets, SPEECH_S7_DE, SPEECH_S7_DE_DIGIT, S7_CLIPS, read_member, --s7-env"
  - "scripts/research/phase4/measure_s7_sentences.py: Vorabmessung von FLEURS-Kandidaten (zwei Parakeet-Läufe, Suchprobe im Wegwerf-Index)"
  - "test_engine_model.py: test_the_s7_clips_give_the_measured_target_forms (python.yml, vor jedem E2E)"
  - "seed.sh AVS_PHASE4_MEDIA=1: s7-zahlwort.wav (gesperrt an Gruppe review), s7-ziffer.wav (Nur-Lesen an carol), FILEID_S7_DE, FILEID_S7_DE_DIGIT"
  - "helpers.ts: toggleViewWithoutDownload, sha256OfFile, downloadTo, exportResponse, exportText, s7Expectations, foldedTokens, fold, AVS_SCREENSHOT_DIR"
  - "search-quality.spec.ts @phase4: Vorbedingung S7, S7 (Zahlklasse, Wortformen, Kompositum, 12:30, Dialog), S6 Datum und Person, SRCH-04"
  - "deploy-harp.yml: Schritt @phase4, BtbN-ffmpeg je Architektur, uv, Download-Beweis, Artefakt phase4-screens-<Version>-<Runner>"
  - "test_downloaded_subtitles.py: Parser-Beweis auf echten Downloads (aktiv mit AVS_DOWNLOADS_DIR)"
affects: [04-15, 04-17]
tech-stack:
  added: []
  patterns:
    - "S7-Zielformen nur über fetch_speech.py (S7Targets) und AVS_S7_TARGETS, nie im Spec eingetippt"
    - "Hauptteil gegen Partial matches über .result--unfiltered (NC 33/34: Klasse fest, NC 35: Klassenbindung, Quelltext stable33/34/35 geprüft)"
    - "ffmpeg des Download-Beweises nur im Schritt-Env, nicht in GITHUB_ENV"
key-files:
  created:
    - scripts/research/phase4/measure_s7_sentences.py
    - ci/playwright/search-quality.spec.ts
    - backend/tests/test_downloaded_subtitles.py
  modified:
    - ci/media/fetch_speech.py
    - backend/tests/test_engine_model.py
    - backend/tests/test_fetch_speech.py
    - ci/seed.sh
    - ci/playwright/helpers.ts
    - .github/workflows/deploy-harp.yml
    - backend/tests/test_workflows.py
decisions:
  - "Zwei DE-Clips statt einem: SPEECH_S7_DE (Parakeet schreibt 'zwanzig', Plural 'Polizisten', Kompositum 'Polizeipräsidium') und SPEECH_S7_DE_DIGIT (Parakeet schreibt '12', Kompositum 'Seitenverhältnis'); so ist die Zahlklasse in beiden Richtungen (Wort im Text, Ziffer im Text) belegt"
  - "Beifang-Messung im Container entfällt: 04-06-SUMMARY führt sie mit Zahlen gegen die echte ngerman-Liste als erledigt; das Gate in test_workflows.py verlangt den Schritt nur, solange 04-06 sie offen führt, und verbietet jede Aufweichung, falls er kommt"
  - "SRCH-04-Empfänger ist die Gruppe review (dora, elke, fleur): passt zu reviewer(testInfo) für X3 in 04-17; die Nur-Lesen-Freigabe geht an carol, die damit zugleich die Person des S6-Personenfilters ist"
  - "Feld S7Targets.number_word statt number_token: ruff S106 hielt 'token' für ein Passwort"
metrics:
  duration: "ca. 45 min"
  completed: 2026-11-16
  tasks: 3
  files: 10
---

# Phase 4 Plan 14: S7-Sätze vorab gemessen, E2E Suchqualität und Download-Beweis Summary

Zwei FLEURS-Sätze sind vorab mit der Engine-Kette des Containers gemessen (zwei gleiche Parakeet-Läufe) und mit member_sha256 gepinnt; ein Modelltest in python.yml prüft ihre Zielformen vor jedem E2E-Lauf, search-quality.spec.ts beweist S6, S7 und SRCH-04 im echten Stack, und deploy-harp.yml führt alle @phase4-Spezifikationen samt Parser-Beweis auf den echten Downloads aus. Ausgeführt wird das alles erst im Push-Tor 04-15.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | S7-Testsätze wählen, vorab messen, pinnen | d928650 | ci/media/fetch_speech.py, scripts/research/phase4/measure_s7_sentences.py, backend/tests/test_engine_model.py, backend/tests/test_fetch_speech.py |
| 2 | Seed und Suchqualitäts-Spezifikation (S6, S7, SRCH-04) | 099876f | ci/seed.sh, ci/playwright/helpers.ts, ci/playwright/search-quality.spec.ts, ci/media/fetch_speech.py (--s7-env), backend/tests/test_fetch_speech.py |
| 3 | Workflow-Schritte, Beifang-Regel, Parser-Beweis | 40e76d1 | .github/workflows/deploy-harp.yml, backend/tests/test_downloaded_subtitles.py, backend/tests/test_workflows.py |

## Messbeleg S7 (Task 1)

Messung am 16.11.2026 lokal (Windows, Projekt-venv, Parakeet-TDT-0.6B-v3 int8 und Silero aus dem gepinnten Modellordner, `procure --verify-only` = present; ffmpeg 8.1.1, dessen WAV-sha256 dem Pin von speech_de.wav gleicht). Quelle FLEURS, Google, CC-BY-4.0, google/fleurs@70bb2e84b976b7e960aa89f1c648e09c59f894dd, Archiv data/de_de/audio/test.tar.gz, Mitglied je per sha256 gepinnt. Lauf 2 jeweils in einem frischen Kindprozess. Suchprobe: Wegwerf-Index mit dem gemessenen Transkript und der echten ngerman-Liste (276 496 Bestandteile), Suche über `SearchIndex.search`.

| Kandidat (Mitglied) | Transkript Lauf 1 = Lauf 2 | Zielformen | Suchprobe | Wahl |
|---|---|---|---|---|
| 7739349083395946674 | "Eine Autobombe detonierte am Morgen des gestrigen Tages im Polizeipräsidium des türkischen Gazi Antep, tötete zwei Polizisten und verwundete über zwanzig weitere Menschen." (gleich) | zwanzig, Polizisten, Polizeipräsidium | 20, zwanzig, twenty, vingt, Polizist, Polizisten, Polizei, Polizeipräsidium: alle Treffer | **SPEECH_S7_DE** |
| 12345915225289351467 | gleicher Satz, "Garciantab" statt "Gazi Antep" (gleich) | wie oben | alle Treffer | Reserve |
| 11014175886747870273 | "Das Seitenverhältnis dieses Formats geteilt durch 12 und das einfachste ganzzeilige Verhältnis zu erhalten, wird daher als 3 zu 2 bezeichnet." (gleich) | 12, Seitenverhältnis | 12, zwölf, twelve, douze, Seite, Seitenverhältnis: alle Treffer | **SPEECH_S7_DE_DIGIT** |
| 4932595101551775223 | "Das Zeitenverhältnis ..." (gleich) | Kompositum falsch erkannt | "Seite" kein Treffer | verworfen |
| 1368065425607103631, 9957275888441805405, 16017599593113495706 | "Infolgedessen sind zwei Fischarten ausgestorben ..." (je gleich) | zwei, Fischarten | "Fischart" findet "Fischarten" nicht (alle anderen ja) | verworfen, Befund in deferred-items.md |

Pins der gewählten Clips (in fetch_speech.py):

- SPEECH_S7_DE: member_sha256 f451f0cb4df52872a837745ddeae9c640a2450483d4b1b9a5faf620735c5c3b2, wav_sha256 bd7c8d0e869d9c0216823fb6803dcba6b5bf4434b6c73c57122df258c05087cb, 22,8 s, expected_word "zwanzig".
- SPEECH_S7_DE_DIGIT: member_sha256 f62551ec2ec42f69ae29b6147e6954b62a3a46fcaf520265af301e9fa9a46c61, wav_sha256 3e2e231c7a25b5d4e266ba7d451cf34efd62faf0e0ebb585634480375492a6e9, 7,98 s, expected_word "12".

Begründung: FLEURS-DE (862 Testsätze) enthält kein Kompositum mit Kopf "Haushalt"; Ersatz sind "Polizeipräsidium" (Kopf "Polizei", 7 Zeichen) und "Seitenverhältnis" (Kopf "Seite", 5 Zeichen = PREFIX_MIN_CHARS). Der wörtliche Fall "Haushalt" findet "Haushaltsplanberatung" bleibt durch test_compounds.py (Plan 04-06) auf Index-Ebene bewiesen, ebenso "zwölf" und "Häuser" (Plan 04-01/04-06). Der Kopf steht in keinem der beiden Sätze als eigenes Wort (Test in test_fetch_speech.py), die Suche danach kann also nur über Zerlegung oder Präfix-Klausel treffen.

Modelltest lokal: `test_the_s7_clips_give_the_measured_target_forms` 2 passed (zusammen mit dem DE-Basistest 3 passed, 10,4 s). Positivkontrolle: speech_s7_de.wav unter dem Namen des Ziffer-Clips, Test rot mit "measured target forms missing ... ['12', 'Seitenverhältnis']". Ohne AVS_TEST_MODELS 2 skipped mit Grund; unter CI=true Fehlschlag statt Skip.

## Ergebnis Task 2 und 3

- `npx playwright test --list --grep @phase4`: 54 Einträge (9 Tests mal 6 Rasterprojekte; Sprach- und Hochkontrastprojekte filtern per @screenshot), darunter "Vorbedingung S7", S7 Zahlklasse/Wortformen/Kompositum/12:30/Dialog, S6 Datum, S6 Person, SRCH-04. Kein `waitForTimeout`, kein Satz eines Clips im Spec. `bash -n ci/seed.sh` ohne Fehler.
- Freigaben von alice: 8 (Phase 1) + 7 (Phase 3) + 2 (Phase 4) = 17 von 20, beide neuen über `share` (count_share).
- deploy-harp.yml: `--s7-env` hängt AVS_SPEECH_S7_DE, AVS_SPEECH_S7_DE_DIGIT und AVS_S7_TARGETS an GITHUB_ENV (Skriptdatei mit `python3 -I`, kein `-c`); Seed mit AVS_PHASE4_MEDIA=1; Hauptlauf `--grep-invert` um @phase4 ergänzt; neue Schritte "Playwright, search quality and export of phase 4" (AVS_PHASE4_E2E=1, AVS_DOWNLOADS_DIR, AVS_SCREENSHOT_DIR=screenshots/phase4, 30 min), BtbN-ffmpeg mit den Dockerfile-Pins je Architektur, setup-uv mit derselben SHA wie python.yml, "The parsers on the real downloads of phase 4" (CI=true, AVS_DOWNLOADS_DIR, AVS_FFMPEG, ohne continue-on-error), Upload `phase4-screens-<Version>-<Runner>` mit `if: always()`; Log-Leck-Probe um s7-zahlwort/s7-ziffer erweitert; Job-Grenze 120 auf 150 min (Schätzung).
- test_downloaded_subtitles.py: ohne Env 1 skipped mit Grund; mit Env auf leeren Ordner rot (lokal geprüft); Selbsttests in der Datei (leer, fehlend, ohne VTT, fremder Name, vollständig grün, TXT ohne T35, BITV, kaputte VTT) 9 passed.
- test_workflows.py: `phase4_findings` mit sechs Regeltests (Hauptlauf ohne @phase4, Schalter fehlt, CI fehlt, --s7-env fehlt, anderes ffmpeg, Artefakt umbenannt, offene Beifang-Zählung ohne Schritt, aufgeweichter Beifang-Schritt).

## Beifang-Messung der Präfix-Klausel

04-06-SUMMARY führt sie NICHT als offen, sondern mit Zahlen gegen die echte ngerman-Liste (wngerman_20161207-15, 356 010 Einträge; Obergrenze echter Wörter je Stamm-Präfix: Haushalt 126, Sitzung 12, Beratung 94, Vertrag 146, Verwaltung 83, Gemeinderat 9, Bebauung 28, Schule 453, Feuerwehr 6, Antrag 39; p95 mit Präfix 1,136 ms bei 100 000 Dokumenten). Laut Plan entfällt damit der Container-Schritt; `test_04_06_closed_the_catch_count_with_numbers` hält diese Begründung fest, und die Regel verlangt den Schritt automatisch, sobald 04-06 die Tabelle verliert.

## Erst in CI belegt (Beleg in 04-15/04-17)

Lokal nur statisch geprüft (Listen, Syntax, YAML-Parse, Workflow-Gates), nicht ausgeführt, nichts gepusht:

1. Modelltest S7 in python.yml auf Linux: dass Parakeet dort dieselben Zielformen liefert (lokal Windows gemessen). Beleg in 04-15.
2. Alle neun @phase4-Tests in deploy-harp auf NC 33/34/35, amd64 und arm64: Vorbedingung S7, S7, S6 (Selektoren `[data-cy-unified-search-filter="date"|"people"]`, Menüpunkt "This year", `.searchable-list__list`, `.result--unfiltered` aus dem Quelltext von stable33/34/35 abgeleitet, nicht am DOM erprobt), SRCH-04 (inklusive WebDAV-403 als Positivkontrolle der Sperre). Beleg in 04-15.
3. Seed-Erweiterung (Uploads, Gruppenfreigabe mit Download-Attribut, carol-Freigabe, Datei-IDs). Beleg in 04-15.
4. Download-Beweis auf echten Dateien: setzt die Downloads von D1 aus Plan 04-17 voraus; bis 04-17 gebaut ist, scheitert der Schritt bewusst am leeren Ordner. Beleg in 04-15 nach 04-17.
5. Artefakt phase4-screens (S6 hell/dunkel 1280, S7 hell 1280). Beleg in 04-15.

Werkzeuge: actionlint und shellcheck sind lokal nicht installiert; statt dessen YAML-Parse mit PyYAML (51 Schritte im Job, Grenze 150), die Workflow-Gates des Repos (test_workflows.py, test_workflow_pins.py) und `bash -n`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] read_member in fetch_speech.py**
- **Found during:** Task 1
- **Issue:** pick_member verlangt einen bekannten sha256; die Vorabmessung muss ihn erst ermitteln.
- **Fix:** read_member (ohne Pin, gleiche Namensprüfung, nie extractall) herausgelöst, pick_member nutzt es und prüft weiter den Pin. Tests für beide.
- **Commit:** d928650

**2. [Rule 2 - fehlende Absicherung] Zweiter S7-Clip und Bestandstest der Clip-Liste**
- **Found during:** Task 1
- **Issue:** test_fetch_speech.py erwartete genau drei Clips mit 8 bis 15 s; die S7-Clips sind 22,8 und 7,98 s lang. Ein Clip allein hätte die Zahlklasse nur in einer Richtung belegt.
- **Fix:** Liste auf fünf Clips, eigene Pin- und Zielformtests für S7 (Zahlformen ergeben über numbers.recognize genau einen Wert, Kopf ab PREFIX_MIN_CHARS und nicht im Satz).
- **Commit:** d928650

**3. [Rule 3 - Blocker] Umgebung der S7-Formen ohne `python -c`**
- **Found during:** Task 2
- **Issue:** Plan verlangt Skriptdatei statt `-c`; es gab keine.
- **Fix:** `fetch_speech.py OUTDIR --s7-env` (lädt nichts, braucht kein ffmpeg, Exit 3 bei fehlendem Clip), mit Tests.
- **Commit:** 099876f

**4. [Rule 2 - Absicherung] Testdateinamen in der Log-Leck-Probe**
- **Found during:** Task 3
- **Issue:** Die neuen Medien s7-zahlwort.wav und s7-ziffer.wav fehlten in der grep-Liste "a test file name reached a log".
- **Fix:** beide Namen ergänzt.
- **Commit:** 40e76d1

**5. [Rule 3 - Werkzeug] S106 auf `number_token`**
- **Found during:** Task 1 (ruff)
- **Fix:** Feld heißt `number_word`.
- **Commit:** d928650

### Anmerkungen ohne Code-Abweichung

- `AVS_SCREENSHOT_DIR` in helpers.ts `screenshot()` (Standard unverändert `screenshots`), damit phase4-screens getrennt hochgeladen wird.
- Der Download-Beweis bekommt eigenes BtbN-ffmpeg und uv in deploy-harp (vorher nur apt-ffmpeg, kein uv); setup-uv mit derselben SHA wie python.yml, damit das Pin-Gate "kein Action zweimal gepinnt" hält.
- Befund "Fischart findet Fischarten nicht" (Analyzer, nicht von 04-14 verursacht) in deferred-items.md.

## Known Stubs

Keine. test_downloaded_subtitles.py ist ohne Downloads bewusst rot unter AVS_DOWNLOADS_DIR, nicht still.

## Threat Flags

Keine neue Angriffsfläche außerhalb des Threat-Registers. T-04-58 (Testclip) über member_sha256 und feste REVISION; T-04-59 über Fehlschlag bei leerem Download-Ordner, ffmpeg-Pflicht unter CI=true und das Verbot von continue-on-error im Gate; T-04-52 vorbereitet (toggleViewWithoutDownload, Nutzung mit finally in 04-17); T-04-53 akzeptiert (nur FLEURS und synthetische Medien im Artefakt).

## Gates

ruff check und format (`--no-cache`, backend, scripts, ci) grün, pyright (latest) 0 Fehler, vulture grün. Volle Suite: nach Task 1 2332 passed, 17 skipped, 4 xfailed; nach Task 2 2334 passed, 17 skipped, 4 xfailed; nach Task 3 2350 passed, 18 skipped, 4 xfailed (210 s, kein Abbruch, kein Fehlschlag; die drei neuen Skips sind die zwei S7-Modelltests ohne Modelle und der Download-Beweis ohne AVS_DOWNLOADS_DIR).

## Self-Check: PASSED

- FOUND: scripts/research/phase4/measure_s7_sentences.py, ci/playwright/search-quality.spec.ts, backend/tests/test_downloaded_subtitles.py, ci/media/fetch_speech.py (SPEECH_S7)
- FOUND: d928650, 099876f, 40e76d1 (Autor street1983nk, ohne Session- oder Co-Authored-Zeilen)
