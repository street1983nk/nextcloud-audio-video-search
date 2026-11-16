---
phase: 04-suchqualit-t-und-export
plan: 17
subsystem: ci/e2e
tags: [SRCH-04, EXP-01, EXP-02, EXP-03, EXP-04, playwright, export, sidecar, track, deploy-harp]
requires:
  - "04-14: Schritt @phase4, AVS_DOWNLOADS_DIR und Parser-Beweis, toggleViewWithoutDownload, sha256OfFile, downloadTo, exportText, AVS_SCREENSHOT_DIR"
  - "04-11, 04-12, 04-10: Seiten-Vertrag section.avs-export, Banner E1 bis E7, Routen export/track/sidecar mit ihren Antworten"
provides:
  - "export.spec.ts @phase4: X1 (Grundmatrix, FR 375, Hochkontrast), X1 grober Zeiger, X1a, X2 (kontrolliertes Fenster, Tripel), X3, X3 Kombifall, X4, X5, X6, D1, D2"
  - "sidecar.spec.ts @phase4: E1 und E2, E2 Hochkontrast/FR, E3, E4, E5, E7, Spur (Chromium und Firefox), Kontrast, E6"
  - "helpers.ts: EXPORT_TEXTS (freigegebene Texte), phase4User, exportName, playAt, exportRoutes, expectTranscript, requestToken, screenshotVariants, switchUser, deleteFile, uploadTo, findShare/ensureShare/updateShare, ablageShare, excludeUser, stopContainer/startContainer/withContainerStopped, columnFromExcerpt, firstCue, noteLines, textContrast, expectContrastSelfTest"
  - "seed.sh/make-testmedia.sh: S7-Übung.webm (Video mit Sprache, an Gruppe review), Ordner Ablage an carol (Rechte 15), lang-40min-x2.ogg mit eigenen Bytes; FILEID_S7_VIDEO, FILEID_ABLAGE"
  - "playwright.config.ts: Projekt firefox-w1280-light (nur @firefox)"
affects: [04-15, 04-16]
tech-stack:
  added: []
  patterns:
    - "Texte der Specs als Kopie der freigegebenen 04-UI-SPEC-Tabelle in helpers.ts, gegen php/l10n/de.json und fr.json abgeglichen (46 Werte, 0 Abweichungen)"
    - "Instanz-Umbauten (Ansehen ohne Download, Nutzer-Ausschluss, Freigaberechte, Download-Attribut, gestoppter Container) nur in try/finally"
    - "Grundmatrix in Deutsch über elke (de_DE), FR über fleur, Hochkontrast über dora"
key-files:
  created:
    - ci/playwright/export.spec.ts
    - ci/playwright/sidecar.spec.ts
  modified:
    - ci/playwright/helpers.ts
    - ci/playwright/playwright.config.ts
    - ci/seed.sh
    - ci/make-testmedia.sh
    - .github/workflows/deploy-harp.yml
    - .planning/phases/04-suchqualit-t-und-export/deferred-items.md
decisions:
  - "Ein Video mit Sprache kommt neu in den Seed (S7-Übung.webm aus dem S7_DE-Clip, VP9/Opus): ohne Video gibt es keine Spur, kein X1 am Video und keinen Umlaut-Namen für D1; der Clip ist der S7-Satz, nicht speech_de, damit S5 aus Phase 3 (alice findet das Sprachwort nicht) gültig bleibt"
  - "X5, E3 und E4 laufen über eine Ordner-Freigabe (Ablage an carol, Rechte 15), weil der Elternordner einer Datei-Freigabe das Home der Empfängerin ist und dort isCreatable immer true gilt"
  - "X2 lädt lang-40min-x2.ogg hoch, das dieselbe Sprache wie lang-40min.ogg hat, aber andere Bytes (Titel-Tag): sonst übernimmt der Container den fertigen Medieneintrag über media_key file_sha256 und X2 wäre nie zu sehen"
  - "Kombifall X3 und X4 nutzen die Nutzer-Regel (occ audio_video_search:exclude --user), weil occ keine Regel für eine einzelne Datei im Home kennt; ExportController fragt isExcludedUser || isExcludedFile an derselben Stelle"
  - "E5 bekommt die Antwort 400 name_too_long vom Test (page.route): ein echter Dateiname hat höchstens 250 Bytes (FilenameValidator stable33), der Nebendateiname wird höchstens 3 Bytes länger und erreicht 255 nie; die Serverseite belegt ExportControllerTest (04-12)"
  - "axe nicht gebaut: braucht ein npm-Paket, Installation nur nach Owner-Prüfung (blocking-human), Eintrag in deferred-items.md"
metrics:
  duration: "ca. 2 h 30 min"
  completed: 2026-11-16
  tasks: 2
  files: 8
---

# Phase 4 Plan 17: E2E Export-Zustände, Fehlerseite, Ablage, Spur und Kontrast Summary

Zwei neue Playwright-Spezifikationen beweisen im echten Stack die Export-Zustände X1 bis X6, die echten Downloads D1 (in AVS_DOWNLOADS_DIR für den Parser-Beweis aus 04-14), die Fehlerseite D2 bei gestopptem Container, die Ablage E1 bis E7 mit sha256-Beweis und die Untertitel-Spur in Chromium und Firefox samt Kontrast-Gate; ausgeführt wird das alles erst im Push-Tor 04-15. axe fehlt noch (Paketfreigabe durch den Owner).

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Export-Zustände und Fehlerseite (X1 bis X6, D1, D2) | caf1613 | ci/playwright/export.spec.ts, ci/playwright/helpers.ts, ci/seed.sh, ci/make-testmedia.sh, .github/workflows/deploy-harp.yml |
| 2 | Ablage, Spur, Kontrast (E1 bis E7, Spur); axe offen | bae3b00 | ci/playwright/sidecar.spec.ts, ci/playwright/playwright.config.ts, .github/workflows/deploy-harp.yml, deferred-items.md |

## Neue @phase4-Tests

20 Testdefinitionen (export.spec.ts 11, sidecar.spec.ts 9). `npx playwright test --list --grep @phase4` listet jetzt 195 Einträge in 3 Dateien (vorher 54 aus search-quality.spec.ts); davon laufen wegen `only()` je Projekt 37 neue Läufe wirklich:

| Prüf-ID | Test | Projekte (Läufe) | Nutzer |
|---|---|---|---|
| X1 | Reihenfolge SRT/VTT/TXT, Texte T13/T14/T16 bis T20, Gruppe, Spur ohne default, kein Akzent, Höhe >= --default-clickable-area, kein seitliches Scrollen | Grundmatrix 6, hc-1280, fr-w375-light (8) | elke / dora / fleur |
| X1 | grober Zeiger: Knöpfe >= 44 px, mit Vorbedingung `(pointer: coarse)` | w375-light (1) | elke |
| X1a | Audio: drei Downloads, kein `<track>` | w1280-light (1) | alice |
| X2 | Upload, Fenster mit expect.poll, Bilder 6 + FR 375, Tripel Seite/TXT-Zeile 3/VTT-NOTE, Wiederholung bei bewegter Uhr | w1280-light (1) | alice, fleur |
| X3 | nur T13+T24, kein Download/Ablage/Track/Export-URL in `#app-content`, GET export x3 und track 403, POST sidecar 403 `{"reason":"blocked"}` | w1280-light, w1280-dark, w375-light (3) | elke |
| X3 Kombifall | gesperrt + ausgeschlossen: Abschnitt-HTML und Ablage-Antwort byte-gleich, Positivkontrolle A5 im Ausschnitt | w1280-light (1) | elke |
| X4 | ausgeschlossen (Video mit Transkript) = ausgeschlossen (stille) ab dem Ausschnitt byte-gleich; ohne Transkript gleicher Rest nach dem Ausschnitt; Positivkontrolle X1 vor dem Ausschluss | w1280-light (1) | dora, oskar, alice |
| X5 | Ordner-Freigabe kurz nur lesen: T23 statt Knopf, drei Downloads; Positivkontrolle Knopf mit Recht | w1280-light (1) | carol |
| X6 | ohne JavaScript (Sitzung per storageState): T20 steht, Knopf hidden, drei Downloads | w1280-light (1) | elke |
| D1 | `waitForEvent('download')` über downloadTo nach AVS_DOWNLOADS_DIR, Name `^.+\.(de\|en\|fr)\.(srt\|vtt\|txt)$` und genau `S7-Übung.de.*` bzw. `s7-ziffer.de.*`, Content-Type wie ExportController::MIME_TYPES, attachment, TXT Zeile 1 Name, Zeile 2 T35, VTT-NOTE T35 | w1280-light (1) | elke (DE, Umlaut), alice (EN) |
| D2 | Container gestoppt: Klick auf den Link der Seite gibt 503-Fehlerseite T29/T25/T30; direkte Route mit `?t=12.5`: 503, T30 führt auf `/play/<id>?t=12.5`; Bilder 1280 hell/dunkel, 375 hell | w1280-light (1) | elke |
| E1/E2 | alte Nebendatei weg, Klick 201: E1 role status, T21 mit Name, Link "In Dateien anzeigen", Fokus bleibt auf dem Knopf, Datei = VTT mit T35; Klick 409: E2 T22a/T22b, Fokus auf dem Banner, sha256 vor/nach gleich; Bilder 6+6 | w1280-light (1) | elke |
| E2 | Hochkontrast und Französisch mit sha256-Vergleich | hc-1280, fr-w375-light (2) | dora, fleur |
| E3 | Rechte nach Seitenaufbau auf 1: 403, T29b/T23, nichts angelegt | w1280-light (1) | carol |
| E4 | Download-Attribut nach Seitenaufbau false: 403, T29b/T24, nichts angelegt | w1280-light (1) | carol |
| E5 | Antwort 400 name_too_long vom Test: T29b/T26 (siehe Abweichungen) | w1280-light (1) | elke |
| E7 | Container nach Seitenaufbau gestoppt: 503, T29b/T25 | w1280-light (1) | elke |
| E6 | bis zu 11 schnelle POSTs bis 429, vorher nur 409; Klick 429: T29b/T27 | w1280-light (1), als letzter Test | elke |
| Spur | Label "Deutsch, Untertitel-Entwurf", srclang de, ohne default, mode disabled/hidden, nach `mode = 'showing'` erster Cue mit Zeit +-100 ms und Text aus `exportText(..., 'vtt')`, activeCues zur Zeit | w1280-light (Chromium), firefox-w1280-light (2) | elke |
| Kontrast | Selbsttest, dann .avs-export__note, .avs-export__hint, Download- und Ablage-Knopf >= 4,5:1, Werte als Annotation | Grundmatrix 6, hc-1280 (7) | elke / dora |

Jeder E3- bis E7-Banner wird zusätzlich auf Worte geprüft: kein roher Statuscode, kein JSON. Kein `waitForTimeout` in beiden Dateien.

## Herkunft der Selektoren

Nur aus Template, JS und UI-SPEC abgeleitet, nicht am DOM erprobt: `php/templates/play.php` (section.avs-export, h3.avs-export__title, p.avs-export__note, p.avs-export__partial mit time.avs-play__time, div.avs-export__downloads role=group, a.button.avs-export__download, .avs-export__sidecar > p.avs-export__hint, #avs-sidecar hidden, #avs-sidecar-result mit #avs-sidecar-e1 bis -e7, span.avs-export__name, `<track kind="subtitles" srclang label>`), `php/templates/export_error.php` (.avs-banner--error role=alert, p.avs-banner__title/__text, a.avs-banner__action), `php/js/play.js` (POST mit Header requesttoken aus document.head.dataset.requesttoken, Fokusregel E1 Knopf, sonst Banner), `ExportController` (Routen /export/{id}/{fmt}, /track/{id}, POST /sidecar/{id}, MIME_TYPES, errorPage mit ?t=), `PageController::exportState`. Der HaRP-Status-Weg `http://localhost:8090/exapps/<id>/status` stammt aus dem @unreachable-Schritt von deploy-harp.yml.

## Erst in CI belegt (Beleg in 04-15)

Lokal nur statisch geprüft, nichts gegen eine Instanz ausgeführt, kein Docker, nichts gepusht:

1. Alle 37 neuen Läufe auf NC 33/34/35, amd64 und arm64, samt Screenshots im Artefakt phase4-screens. Beleg in 04-15.
2. Seed-Erweiterung: Upload `S7-%C3%9Cbung.webm`, MKCOL Ablage, die zwei Freigaben (alice 19 von 20), FILEID_S7_VIDEO und FILEID_ABLAGE; make-testmedia.sh mit VP9/Opus-Video und lang-40min-x2.ogg (ffmpeg des Runners). Beleg in 04-15.
3. Download-Beweis `test_downloaded_subtitles.py` auf den D1-Dateien (6 Dateien, je Format 2). Beleg in 04-15.
4. Firefox auf beiden Architekturen (`npx playwright install --with-deps chromium firefox`, auch ubuntu-24.04-arm). Beleg in 04-15.
5. Container-Stopp und -Start aus dem Test (`docker stop/start $EXAPP_CONTAINER`, Heartbeat über HaRP) und die Rückkehr des Exports danach. Beleg in 04-15.
6. Annahmen über Nextcloud, die nur der Stack zeigt: OCS-PUT der Freigabe mit `attributes`, sofortige Wirkung geänderter Rechte, Rate-Limit-Speicher ohne Memcache, Sichtbarkeit der X2-Freigabe für fleur ohne files:scan (sonst nur Annotation "gap", kein Fehlschlag), `testInfo.project.use.baseURL` für die Zusatz-Kontexte (Fallback NC_URL). Beleg in 04-15.

## Geschätzte zusätzliche CI-Laufzeit

Je Matrix-Bein etwa 10 bis 25 min: X2-Fenster bis 10 min (Phase 3 brauchte ähnlich lange), zwei Container-Neustarts je 1 bis 3 min, Firefox-Installation etwa 1 min, die übrigen 35 Läufe je 5 bis 20 s. Grenzen angehoben: Schritt @phase4 30 auf 60 min, Job 150 auf 180 min (Schätzung, bis ein grüner Lauf misst).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] Kein Video mit Sprache im Stack**
- **Found during:** Task 1
- **Issue:** X1 (Video), die Spur und D1 mit Umlaut brauchen ein Video mit Transkript; der Seed hatte nur tone-90s.webm (keine Sprache) und ohne-ton.mp4 (kein Ton).
- **Fix:** make-testmedia.sh macht s7-video.webm aus dem S7_DE-Clip (wenn AVS_SPEECH_S7_DE gesetzt ist), seed.sh lädt es als "S7-Übung.webm" hoch und gibt es an die Gruppe review frei.
- **Commit:** caf1613

**2. [Rule 1 - falscher Testaufbau] X5 über eine Datei-Freigabe hätte T23 nie gezeigt**
- **Found during:** Task 1
- **Issue:** Der Seed aus 04-14 sah s7-ziffer.wav (Datei-Freigabe an carol) für X5 vor; deren Elternordner ist carols Home, isCreatable ist dort true.
- **Fix:** Ordner Ablage an carol (Rechte 15); X5, E3 und E4 setzen Rechte bzw. Download-Attribut nur in try/finally um. Kommentar in seed.sh angepasst, Befund in deferred-items.md (Produktfrage an den Owner).
- **Commit:** caf1613

**3. [Rule 3 - Blocker] X2 wäre durch Dedup nie partiell**
- **Found during:** Task 1
- **Issue:** Ein bytegleiches lang-40min.ogg bekäme über media_key file_sha256 sofort das fertige Transkript der Phase-3-Kopie.
- **Fix:** make-testmedia.sh macht lang-40min-x2.ogg mit eigenem Titel-Tag und bricht ab, falls die Bytes doch gleich sind.
- **Commit:** caf1613

**4. [Rule 2 - Absicherung] Log-Leck-Probe um die neuen Namen erweitert**
- **Found during:** Task 1
- **Fix:** `s7-video|s7-ablage|S7-.{1,12}bung` in der grep-Liste "a test file name reached a log" (lang-40min-x2 deckt `lang-40min` schon).
- **Commit:** caf1613

**5. [Rule 3 - Werkzeug] Firefox-Projekt und -Installation**
- **Found during:** Task 2
- **Fix:** Projekt firefox-w1280-light mit `grep: /@firefox/` (nur die Spur), Installation `chromium firefox`; der Hauptlauf und die Schritte mit eigenem grep bekommen dadurch keinen Test dazu (geprüft: `--list` mit dem grep-invert des Hauptlaufs listet 132 Tests wie vorher, kein Firefox-Eintrag).
- **Commit:** bae3b00

**6. [Rule 3] Kombifall und X4 mit Nutzer-Regel statt Datei-Regel**
- occ `audio_video_search:exclude` kennt --user, --group, --folder, --storage, keine Datei; die Clips liegen im Home-Wurzelordner. ExportController und PageController fragen isExcludedUser und isExcludedFile an derselben Stelle, der Beweis der Reihenfolge Sperre vor Ausschluss bleibt gleich. Positivkontrolle: der Ausschnitt zeigt nach der Regel A5.

**7. E5 mit Antwort vom Test**
- Ein echter Dateiname hat höchstens 250 Bytes (`isset($filename[250])` in `OC\Files\FilenameValidator`, stable33, Zeile 185); `<Name>.<de>.vtt` ist höchstens 3 Bytes länger als ein Name mit `.wav`, `.ogg` usw. und erreicht 255 nie. E5 prüft deshalb nur den Seitenteil (play.js-Abbildung, Text T26) mit `page.route`, als Annotation "answered by the test" sichtbar; die Serverseite belegt ExportControllerTest (04-12).

**8. D2: Rückweg über den Link verliert die Zeitmarke (Befund, nicht behoben)**
- Die Export-Links der Seite tragen kein `?t=`; D2 prüft den Weg über den Link (Fehlerseite, Rückweg auf dieselbe Datei, Zeitmarke als Annotation "finding") und die Route mit `?t=12.5` (Rückweg mit gleicher Zeitmarke). Produkt-Fix (t an die drei URLs) in deferred-items.md, weil PHPUnit nur in CI läuft.

### Offen (Checkpoint, blocking-human)

**axe ohne serious/critical** ist nicht gebaut: In `ci/playwright` ist nur `@playwright/test` installiert, axe braucht ein neues npm-Paket. Paketinstallationen sind laut Ausführungsregeln keine Auto-Korrektur; der Owner prüft das Paket (Vorschlag `@axe-core/playwright`, Deque Systems) und gibt die Installation frei. Danach kommt eine axe-Spezifikation über dieselben Wege (X1 bis X5, E1 bis E7, D2). Eintrag in deferred-items.md. Das Akzeptanzkriterium "listet ... axe" von Task 2 ist damit nicht erfüllt.

### Prüfung

- Typprüfung: kein tsconfig und kein TypeScript in ci/playwright; geprüft mit vorhandenem tsc 5.9.3 und @types/node 20 aus einem anderen Projekt über eine Scratchpad-tsconfig (strict) für alle sechs .ts-Dateien: 0 Fehler. Positivkontrolle: eine Datei mit zwei Typfehlern gegen helpers.ts ergibt zwei Fehler.
- Texte: EXPORT_TEXTS gegen php/l10n/de.json und fr.json (Schlüssel = englischer Text): 46 Werte, 0 Abweichungen.
- `bash -n ci/seed.sh`, `bash -n ci/make-testmedia.sh` ohne Fehler; YAML-Parse aller Workflows (deploy-harp: Job 180 min, 51 Schritte, @phase4 60 min, Installation mit firefox).
- Workflow-Gates (test_workflows.py, test_workflow_pins.py) in der vollen Suite grün.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche im Produkt. Die Specs bauen Instanz-Zustände nur in finally zurück (T-04-52): toggleViewWithoutDownload, excludeUser, updateShare (Rechte und Download-Attribut), withContainerStopped. T-04-51 und T-04-60 über X3 samt Kombifall, X4, X5, E3 und E4 im echten Stack (Beleg in 04-15).

## Gates

ruff check und format (`--no-cache`, backend, scripts, ci) grün, pyright (latest) 0 Fehler, vulture grün. Volle Suite (Ausgabe vollständig im Scratchpad) vor Task 1: 2350 passed, 18 skipped, 4 xfailed (221 s); vor Task 2: 2350 passed, 18 skipped, 4 xfailed (226 s). Kein Abbruch, kein Fehlschlag.

## Self-Check: PASSED

- FOUND: ci/playwright/export.spec.ts, ci/playwright/sidecar.spec.ts (keine waitForTimeout)
- FOUND: caf1613, bae3b00 (Autor street1983nk, ohne Session- oder Co-Authored-Zeilen)
- OFFEN: axe (Paketfreigabe, siehe oben), kein Fehler der Selbstprüfung
