---
phase: 03-vorschau-transkripte-in-der-suche
plan: 18
subsystem: ci, abnahme, playwright
tags: [deploy-harp, playwright, preview, kontrast, leck-probe, testmedien, srch-01, srch-02, srch-03, trans-08, media-04]
requires: ["03-02", "03-12", "03-15", "03-16", "03-16b", "03-17"]
provides:
  - "ci/make-testmedia.sh: neun Medien der Phase 3 (mit AVS_SPEECH_DE und AVS_SPEECH_TR)"
  - "ci/seed.sh: AVS_PHASE3_MEDIA=1 lädt sie hoch, Freigaben an dora/elke/fleur, ausgeschlossener Nutzer oskar, FILEID_* der Phase 3"
  - "deploy-harp.yml: Modelle und Clips aus dem Cache ins Volume vor der Registrierung, Schritt @preview (AVS_PREVIEW_E2E=1), Hauptlauf ohne @preview, Leck-Probe EXCERPT LEAK PROBE PASS"
  - "preview.spec.ts: S1 bis S5, P1 bis P11, P12/P13 als test.fixme, Kontrastmessung mit Selbsttest"
  - "helpers.ts: contrastRatio, parseColor, composite, excerptNoteContrast, occ, searchInDialog (aus play.spec.ts), screenshot mit Variante"
affects: [03-19, 03-20, 03-21]
tech-stack:
  added: []
  patterns:
    - "Zustände, die bleiben, im Projekt-Raster; Wege, die die Instanz ändern, einmal in w1280-light mit Varianten (setViewportSize, emulateMedia) auf derselben Seite"
    - "Leck-Probe über Zeitfenster im Zugriffslog des Containers mit Positivkontrolle, weil die fileId im Body steht"
    - "Texte der Erwartung aus der UI-SPEC-Tabelle, nicht aus den Katalogen"
key-files:
  created:
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-18-SUMMARY.md
  modified:
    - ci/make-testmedia.sh
    - ci/seed.sh
    - .github/workflows/deploy-harp.yml
    - backend/tests/test_workflows.py
    - ci/playwright/preview.spec.ts
    - ci/playwright/helpers.ts
    - ci/playwright/play.spec.ts
decisions:
  - "lang-12h01.flac statt lang-1h01.ogg: Plural bei 12 braucht eine Datei über 12 h; Senken auf 1 stellt nichts zurück (03-15), die Seite nennt die aktuelle Grenze, also Plural und Singular an einer Datei"
  - "lang-40min.ogg ist der DE-Clip in Schleife (Sprache in allen vier Stücken) statt Stille: sonst dauert das Teil-Fenster nur Sekunden; die Datei lädt der Test hoch, nicht der Seed"
  - "S1/S2 über bob mit genau zwei Sprachdateien (vier und zwei Stellen): nur so ist Seite 1 mit limit 5 fest (3 + 2, vierte Stelle in Stufe 2); zusätzliche Datei zwei-stellen.ogg"
  - "P11 mit neuem Nutzer oskar (ausgeschlossen, Freigabe der Stille-Datei); mallory bleibt der Nutzer ohne Zugriff"
  - "S4 als zwei Suchen desselben Nutzers: der Probetext teilt kein indexiertes Wort mit dem Clip (Stoppwörter, AND)"
  - "P12 als test.fixme: in der deploy-harp-Topologie nicht erreichbar"
metrics:
  duration: "ca. 2 h"
  completed: 2026-11-14
  tasks: 2
  files: 7
---

# Phase 3 Plan 18: Kernweg und Abnahmefälle der Phase 3 in deploy-harp Summary

deploy-harp legt die Sprachmodelle vor der Registrierung ins Volume, erzeugt neun Testmedien aus den FLEURS-Clips und fährt nach dem Hauptlauf einen eigenen Schritt `AVS_PREVIEW_E2E=1 npx playwright test --grep @preview`: Kernweg, die Zustände S1 bis S5 und P1 bis P11 mit Screenshots, Kontrastmessung der Vorschau-Notiz nach Selbsttest und eine Leck-Probe, die der folgende Workflow-Schritt mit Positivkontrolle im Zugriffslog des Containers prüft.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 | a134d9a | ci(03-18): Testmedien und Kernweg der Phase 3 in deploy-harp |
| Nacharbeit | 526c7d6 | style(03-18): Zeilenlänge und Anführungszeichen in test_workflows.py nach ruff |
| 2 | e76fde1 | test(03-18): Abnahmefälle der Phase 3 mit Kontrastmessung und Leck-Proben |

Alle nur lokal, Autor und Committer street1983nk <k.cherif@outlook.de>, nichts gepusht, kein Docker, kein Lauf gegen eine Instanz.

## Task 1: Testmedien, Seed, Workflow

**make-testmedia.sh** (nur mit `AVS_SPEECH_DE` und `AVS_SPEECH_TR`; ohne beide wie bisher nur die Medien der Phase 1, mit nur einem bricht das Skript ab; der upgrade-Job bleibt so unberührt):

| Datei | Inhalt | Zustand |
|---|---|---|
| stille-60s.ogg | 60 s Stille, Opus | A6 (P5, S5, P11) |
| kaputt.mp3 | 8 KB Zufallsbytes | A7 (P6) |
| geschuetzt.m4a | DE-Clip AAC, CENC mit festem Testschlüssel | A8 (P7) |
| lang-12h01.flac | 12 h 1 min Stille, FLAC (8 MB, Sekunden) | A10 (P9) |
| lang-40min.ogg | DE-Clip in Schleife bis 40 min | A5, A2, A4 (P4, P2, P3) |
| viele-stellen.ogg | DE-Clip viermal, 30 s Abstand | S1, S2, S3, P1 |
| zwei-stellen.ogg | DE-Clip zweimal, 30 s Abstand | S1 (zweite Datei) |
| tuerkisch.wav | TR-Clip | A9 (P8) |
| ohne-ton.mp4 | nur Bild, mpeg4 | A11 no_audio (P10) |

Lokaler Lauf mit Stand-in-Clips (Sinus) und ffmpeg 8.1.1: alle Dateien in 17 s. Gegenprobe mit ffprobe (nicht mit dem Muster des Skripts): Dauern 60,0 / 43 260 / 2 400 / 120 / 60 s, ohne-ton.mp4 nur ein Videostrom, kaputt.mp3 "Invalid data", geschuetzt.m4a mit Boxen sinf, schm, tenc und nicht dekodierbar, silencedetect zeigt die Stellen bei 0, 30, 60, 90 s.

**seed.sh** (mit `AVS_PHASE3_MEDIA=1`): alice besitzt die sechs Grund-Dateien und gibt sie dora, elke und fleur frei; bob besitzt viele-stellen.ogg und zwei-stellen.ogg (viele-stellen auch an dora für Hochkontrast und Kontrast); neuer Nutzer oskar bekommt stille-60s.ogg und wird mit `occ audio_video_search:exclude --user=oskar` ausgeschlossen; acht neue `FILEID_*` in fileids.env. Fehlt eine Datei, bricht der Seed ab.

**deploy-harp.yml** (Job deploy-harp):
- `Install ffmpeg` vor den Clips; Cache-Schlüssel, Restore, procure bei Fehltreffer, Clips, Übergabe `AVS_SPEECH_DE/TR/WORD` über GITHUB_ENV, Kopie ins Volume als 10001 ohne Prüfdateien: wie 03-17, vor HaRP und der Registrierung. Danach Beleg `init == 100`, je Modell `outcome present`, `models ready`.
- Seed mit `AVS_PHASE3_MEDIA: '1'`, `OSKAR_PASS` in der Workflow-Umgebung.
- Hauptlauf `--grep-invert` um `@preview` ergänzt; neuer Schritt `Playwright, core path and states of phase 3` direkt danach (Debug an, Backend läuft), eigene Frist 45 min, Umgebung `AVS_OCC`, `AVS_MEDIA_DIR`, `AVS_LEAK_PROBE`.
- Schritt `The excerpt leak probe`: sichert das Container-Log als `logs/exapp-preview.log`, zählt `uvicorn.access`-Zeilen mit `POST /excerpt ` in zwei Zeitfenstern aus leak-probe.json; Positivkontrolle muss mindestens 1 sehen (sonst INVALID), das Fenster des ausgeschlossenen Nutzers 0, dann `EXCERPT LEAK PROBE PASS`.
- Namensprüfung im Log um alle neuen Dateinamen erweitert.
- Job-Frist 75 auf 120 min (Kommentar: 03-15 maß 3,5 bis 7,4 s je Datei mit Kindstart; 0,67 GB Modelle bei Fehltreffer; Schritt @preview bis 45 min).

**test_workflows.py**: Regel `preview_findings` mit Positivkontrollen (Hauptlauf ohne Ausschluss und fehlender Schalter, Schlüssel ohne MODEL_SHA256 und Prüfdateien im Volume, Volume nach der Registrierung, Leck-Probe ohne Kontrolle und Seed ohne Medien: je genau die erwarteten Befunde); der Python-Ausdruck des Schlüssels wird ausgeführt und mit `catalog.MODEL_SHA256` verglichen.

Leck-Probe-Block lokal mit gefälschtem `docker` und jq 1.7 gegen vier Logs gefahren: korrekt PASS (0/1), Zeile nur im Probe-Fenster INVALID, keine Zeile INVALID, Zeile in beiden Fenstern FAILED.

## Task 2: Playwright-Fälle

| ID | Wo | Prüfung |
|---|---|---|
| S1 | 6 Rasterprojekte, bob | OCS limit 10 wartet auf 6 Stellen; limit 5 genau 3 Zeilen viele-stellen und 2 zwei-stellen, jede `Zeit · Vorläufig · Ausschnitt`, kein Testtreffer-Kennzeichen; im Dialog höchstens 3 Zeilen der Datei, Kennzeichen sichtbar; Screenshot |
| S2 | 1280 hell/dunkel | limit 10: vierte Stelle, keine doppelte resourceUrl, erste 5 = limit 5; Cursor-Seite 2 ohne Dublette; im Dialog "Load more" ergibt 4 Zeilen |
| S3 | 375 hell/dunkel | Range des Kennzeichens liegt in jeder abschneidenden Box (overflow/ellipsis) |
| S4 | 1280 hell, bob | "Audiosuche": nur Testtreffer, kein Vorläufig; Clip-Wort: nur Vorläufig, kein Testtreffer |
| S5 | 1280 hell, alice | erst T5 auf der Seite, dann fehlt die fileId bei drei Begriffen |
| P1 | 6 Raster + hc-1280 | blockquote mit dem Wort, direkt danach genau eine Notiz T2; Kontrast nach Selbsttest, Werte als Annotation, Fehlermeldung "note contrast below 4.5:1: use --color-main-text (UI-SPEC)" |
| P5 bis P8, P10 | Projekte laut UI-SPEC-Zeile, FR über fleur bei P6/P7 | Satz exakt aus der UI-SPEC, kein blockquote, keine Notiz; Format-Banner und Satz zusammen sichtbar, falls der Browser ablehnt; P10 ohne `no_audio` im DOM |
| Kernweg | einmal | Bestand aus 03-02, Hilfen auf die neuen Locator umgestellt |
| P4 | einmal | lang-40min.ogg hochladen, sofort A5, outerHTML als Referenz, 1280 hell/dunkel |
| P3, P2 | einmal | Abfrage alle 2 s bei t=2340 bis T4 (bricht klar ab, wenn die Datei schon fertig war), danach t=6: Ausschnitt mit genau einer Notiz T3, nicht T2; Bilder 3 bzw. 6 Varianten |
| P11 | einmal | Kontrollfenster alice auf der Stille-Datei, dann oskar: Block byte-gleich zu P4, Fenster in leak-probe.json |
| P12 | test.fixme | Begründung im Spec (siehe unten) |
| P13 | test.fixme | disk_full nicht ohne Eingriff erzeugbar; Belege 03-13 (Zurückstellen) und 03-16/03-16b (A13, T12) |
| P9 | einmal | Plural bei 12 in 6 Varianten, DE und FR (FR 375 hell); `occ app_api:app:config:set ... max_duration_hours --value=1`, Abfrage bis 8 min bis "1 hour", DE/FR Singular; im finally zurück auf 12 |

`npx playwright test --list --grep @preview`: 156 Einträge in einer Datei, S1 bis S5 und P1 bis P13 enthalten. Hauptlauf-Liste (`--grep-invert ...|@preview`) enthält 0 Fälle aus preview.spec.ts; alle drei Dateien zusammen 354 Einträge (play.spec.ts übersetzt nach dem Umzug der Dialoghilfen). Kein `waitForTimeout` in preview.spec.ts und helpers.ts.

Kontrast: Selbsttest lokal grün; Mutation der Luminanzgewichte macht ihn rot (20,44 statt 21). `excerptNoteContrast` lokal in einem Chromium (ältere installierte Version, nur `setContent`, keine Instanz) gegen echte berechnete Stile: #767676 auf Weiß 4,54, transparenter Block über schwarzem body nimmt Schwarz, halbtransparenter Text wird korrekt gemischt. Die Hilfsdatei ist gelöscht.

## Gates

- `bash -n` make-testmedia.sh, seed.sh; shellcheck 0.11.0 ohne Befund (Positivkontrolle mit `echo $(ls)` meldet); Leck-Probe-Block einzeln mit shellcheck ohne Befund.
- actionlint (actionlint-py, `-shellcheck=` wie in 03-17 wegen Hängern unter Windows) ohne Befund.
- pytest test_workflows, test_workflow_pins, test_discovery_workflow, test_lockstep_versions, test_sample_layer: 151 passed.
- ruff check, ruff format --check grün; pyright (latest) test_workflows.py 0 Fehler; vulture still.
- Keine U+2013/U+2014 in den geänderten Dateien (Byteprüfung, Positivkontrolle an einer Probe mit U+2014 positiv). Erwartungstexte wörtlich aus der UI-SPEC-Tabelle.

## Erst die CI zeigt (Plan 03-20)

- Ob alle Fälle grün laufen: kein Docker, keine Instanz lokal. Besonders: Zeitfenster des Teiltranskripts (lang-40min.ogg, geschätzt Minuten; scheitert mit klarer Meldung, falls die Datei zwischen zwei Blicken fertig wurde), Erkennung des Clip-Worts in jeder Kopie der Opus-Dateien (S1 erwartet genau 6 Stellen), Schwellen für kaputt.mp3 (damaged) und geschuetzt.m4a (protected) im echten Container.
- `occ app_api:app:config:set <appid> <key> --value=` (Befehlsform aus der Connector-Doku, nicht am AppAPI-Quelltext geprüft) und dass der Worker den Wert im 300-s-Takt übernimmt.
- Dass der Zugriffslog des Containers `POST /excerpt` als `uvicorn.access`-Zeile mit `ts` schreibt; die Positivkontrolle macht einen Irrtum sichtbar (INVALID statt PASS).
- "Load more" im Dialog (Name des Knopfs je Version 33/34/35), Seitengröße des Dialogs, Abschneidebox in S3.
- Kontrastwerte hell/dunkel/Hochkontrast; unter 4,5:1 schlägt P1 mit der vorgesehenen Meldung fehl und `.avs-excerpt__note` braucht laut UI-SPEC `--color-main-text`.
- Ob die Namensprüfung im Nextcloud-Log mit den neuen Namen ruhig bleibt (z. B. Vorschaubild-Fehler von Nextcloud selbst zu kaputt.mp3).
- Laufzeit und neue Job-Frist 120 min, Modell-Download bei Fehltreffer (setzt das Release aus 03-07b voraus, wie 03-17).
- deploy-harp.yml erwartet im upgrade-Job weiter schemaVersion 2 (offener Punkt aus 03-03, Plan 03-19); hier nicht berührt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3] Teil-Fenster wäre mit Stille nur Sekunden lang**
- lang-40min.ogg ist der DE-Clip in Schleife statt Clip, Stille, Clip bei 25 min: VAD über Stille ist schnell, das Fenster partial hätte keine verlässliche Abfrage erlaubt. Die Datei lädt P4 hoch (der Seed läge zu weit vor dem Schritt @preview). Commit a134d9a, e76fde1.

**2. [Rule 3] Plural bei 12 braucht eine Datei über 12 h**
- lang-12h01.flac ersetzt lang-1h01.ogg. Anheben stellt zurück, Senken nicht (03-15), und die Seite nennt die aktuelle Grenze: erst Plural bei 12 (Standard), dann Senken auf 1 für den Singular, im finally zurück auf 12. FLAC statt Opus: 12 h Stille in Sekunden und 8 MB. Kein Neustart des Containers nötig.

**3. [Rule 3] S1 wäre mit alice nicht fest**
- Mit dem Kernweg-Clip und lang-40min.ogg hängt die Reihenfolge der Dateien vom BM25-Wert ab. bob liest genau zwei Sprachdateien (4 + 2 Stellen), dadurch ist Seite 1 mit limit 5 genau 3 + 2. Neue neunte Datei zwei-stellen.ogg.

**4. [Rule 2] Leck-Probe ohne fileId im Log**
- Das Zugriffslog nennt nur die Route, die fileId steht im Body. Prüfung über Zeitfenster mit Positivkontrolle (alice öffnet dieselbe Datei) statt "keine Zeile für diese fileId"; ohne Kontrolle kein PASS.

**5. [Rule 2] Neuer Nutzer oskar statt mallory**
- mallory ist im Kernweg und in play.spec.ts der Nutzer ohne Zugriff; ausgeschlossen würde er diese Prüfungen aushöhlen.

**6. [Rule 3] Dialoghilfen nach helpers.ts**
- openUnifiedSearch, searchField, watchProviderSearches, expectFinalSearchDone, GROUP_NAME von play.spec.ts nach helpers.ts (play.spec.ts nicht in files_modified), dazu `searchInDialog`. Verhalten unverändert.

**7. ffmpeg-Installation vorgezogen**
- Eigener Schritt `Install ffmpeg` vor den Clips (fetch_speech.py und Clip-Schlüssel brauchen es); "Make the test media" installiert nicht mehr selbst.

**8. Namensprüfung erweitert** um alle neuen Dateinamen und speech_de.wav.

### Bewusst nicht wie im Plan

- **S4** zeigt Testtreffer und echten Treffer in zwei Suchen desselben Nutzers, nicht in einer Liste: der Probetext ("Dies ist ein Testtreffer für die Audiosuche in Audio und Video") teilt nach Stoppwortfilter kein Wort mit dem Clip, und der Index verknüpft Begriffe mit AND.
- **P12** als `test.fixme` mit Begründung: der Container führt einen Verweis je fileId und liest als Eigentümer; eine entzogene Freigabe ändert ihn nicht, und eine Datei mit nicht aktivem Verweis (verschwunden, Papierkorb, für den Leser unlesbar) kann der Nutzer in dieser Topologie auch nicht öffnen. Abgedeckt bis dahin durch 03-14 (known false), 03-16 (A5 byte-gleich) und 03-17 (Suche, Samba-Sperre, files_accesscontrol). Siehe Owner-Frage.
- **Hochkontrast** für P1 (mit Kontrast) und P5 über das Projekt hc-1280 (dora). Screenshots von P6/P7 FR über das Projekt fr-w375-light, P9 FR im Ablauf mit fleur.

## Offene Owner-Fragen

1. **P12**: Soll der Fall "Verweis nicht active, Datei über anderen Weg lesbar" eine Abspielseiten-Probe in discovery-e2e.yml bekommen (Topologie mit Samba-Sperre und files_accesscontrol, Plan 03-19 oder 03-20), oder reicht der Beleg aus 03-14/03-16/03-17 mit dem fixme?
2. **S4**: Reicht der Beleg in zwei Suchen, oder soll ein Testtreffer gezielt neben einem echten Treffer stehen (bräuchte einen Testtreffer auf einer Sprachdatei mit einem gemeinsamen Wort, also eine Änderung an `occ audio_video_search:sample`)?

## Known Stubs

Keine. P12 und P13 sind ausdrücklich als `test.fixme` mit Begründung geführt (T-03-62), nicht still ausgelassen.

## Threat Flags

Keine neue Oberfläche der App. Im CI-Job neu: `actions/cache` (SHA-gepinnt wie python.yml und discovery-e2e.yml) und der Download der Modelle bzw. Clips bei Fehltreffer, beides wie 03-17. T-03-60 (Selbsttest vor der Messung), T-03-61 (P11 Byte-Vergleich, Logprüfung mit Positivkontrolle) und T-03-62 (P13 als fixme mit Begründung) umgesetzt.

## Self-Check: PASSED

- FOUND: ci/make-testmedia.sh, ci/seed.sh, .github/workflows/deploy-harp.yml, backend/tests/test_workflows.py, ci/playwright/preview.spec.ts, ci/playwright/helpers.ts, ci/playwright/play.spec.ts
- FOUND: Commits a134d9a, 526c7d6, e76fde1
