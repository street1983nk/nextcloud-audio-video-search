---
phase: 04-suchqualit-t-und-export
plan: 15
subsystem: ci/push
tags: [push, ci, deploy-harp, discovery, phpunit, SRCH-04, EXP-01, EXP-02, EXP-03, EXP-04]
requires:
  - "04-01 bis 04-14, 04-17: alle Code- und Testbausteine der Phase 4"
provides:
  - "CI-Beweis der Phase 4 auf phase-04 @ 56f3627: Python gates, PHP gates, Deploy through HaRP (sechs Beine, @phase4 49/49 je Bein, Parser-Beweis 11/11 je Bein), Discovery acceptance push und workflow_dispatch legs=all (6 x 22/22, Leak-Kontrolle zeigt das Leck)"
affects: [04-16]
tech-stack:
  added: []
  patterns:
    - "Push-Tor je SHA über Freigabedatei, main und ghcr vorher und nachher gesichert und verglichen"
key-files:
  created:
    - .planning/phases/04-suchqualit-t-und-export/04-15-SUMMARY.md
  modified: []
decisions:
  - "Push 2 (56f3627) vom Owner am 16.11. freigegeben; alle vier Workflows grün, kein weiterer Push nötig"
  - "debug-Prüfung läuft gegen origin/phase-03 statt origin/main: die vier alten debug-Commits stehen schon auf phase-03"
metrics:
  duration: "ca. 60 min (Push 2 bis Discovery legs=all)"
  completed: 2026-11-16
---

# Phase 4 Plan 15: Push auf phase-04 und CI-Beweis Summary

Zwei Pushes auf phase-04: Push 1 (269d173) zeigte sechs Befunde in PHPUnit, Upgrade- und Deploy-Beinen, alle lokal als Produkt- bzw. Schritt-Fix behoben; Push 2 (56f3627) ist in allen vier Workflows und allen sechs Beinen grün, main und ghcr blieben unverändert.

## Push 1 (269d173)

| Workflow | Lauf | Ergebnis |
|---|---|---|
| Python gates | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43914471981 | success |
| PHP gates | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43914472014 | failure |
| Deploy through HaRP | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43914471902 | failure |
| Discovery acceptance (push) | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43914471886 | success |

main (`ea97b587`) und ghcr (`audio_video_search_backend`: 404, Positivkontrolle `findling_backend` 1.6.2) vorher und nachher gleich. Discovery legs=all wurde wegen der roten Läufe nicht gestartet.

Befunde und Fixes (lokal, Gates grün, dann Push 2):

| Commit | Plan | Befund (Lauf) | Fix |
|---|---|---|---|
| 7ea6aba | 04-10 | PHPUnit (43914472014): Medium mit Tab im Namen gab 500, Symfony wirft beim ASCII-Ersatznamen mit Steuerzeichen | `attachmentName()` ersetzt Steuerzeichen im Header-Namen durch Leerzeichen; Test prüft Content-Disposition |
| 355ca4d | 04-05 | Upgrade-Beine (43914471902): Backend meldet schemaVersion 4, Schritt erwartete 3 | Status- und state.db-Prüfung auf 4, dazu words_de/en/fr und language; Regeltest |
| 665153f | 04-11 | X1 grober Zeiger (alle sechs Beine): 36 px statt 44 px, Server-Regel `button:not(.button-vue, ...)` schlägt die Touch-Regel | Touch-Regel hinter `#app-content.avs-play`; test_ui_assets verlangt die ID |
| 7f2c77a | 04-11 | X6 ohne JavaScript (alle sechs Beine): Kern-Overlay `#nojavascript` fängt jeden Klick ab | Overlay nur auf Abspiel- und Fehlerseite der App aus; Owner hat den Fix bestätigt |
| 0f80494 | 04-14 | Parser-Beweis: test_downloaded_subtitles.py suchte `app-src/php/l10n`, die App liegt nach der Installation unter `apps/audio_video_search` | `AVS_L10N_DIR` im Schritt gesetzt und vorab geprüft; Selbsttest und Workflow-Regel |
| 56f3627 | 04-11 | Gleicher Touch-Befund am Knopf "Erneut prüfen" im Admin-Bereich (Owner-Wunsch) | Touch-Regel in admin.css hinter `#avs-admin`; Gegenprobe mit altem CSS rot |

Keine Erwartung wurde aufgeweicht; alle Fixes sind Produkt- oder Schritt-Korrekturen.

## Push 2 (56f3627d97200a59b4381d2f66ac31b98e2c3aed)

Freigabe: `$A/push-56f3627…` = `push-phase-04 56f3627…` (Owner 16.11.). Push fast-forward `269d173..56f3627 HEAD -> phase-04`, kein --force, kein PR, Kommentar, Merge, Tag oder Release.

| Workflow | Lauf | Ergebnis |
|---|---|---|
| Python gates (push) | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43926051406 | success (2369 passed, 1 skipped, 4 xfailed; ruff, format, pyright 0 errors, vulture) |
| PHP gates (push) | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43926051467 | success (OK, 921 tests, 11512 assertions) |
| Deploy through HaRP (push) | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43926051392 | success, alle zehn Jobs (6 deploy-harp, 4 upgrade) |
| Discovery acceptance (push) | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43926051421 | success |
| Discovery acceptance (workflow_dispatch, legs=all) | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43933705196 | success, sechs Beine je "22 of 22 phases passed", leak-control "LEAK CONTROL SHOWED THE LEAK" |

PHP gates lief mit dem Push an, ein manueller Start von php.yml war nicht nötig. Läufe einzeln nacheinander beobachtet.

### Deploy through HaRP je Bein

| Bein | Hauptlauf | Phase 3 | @phase4 | Parser-Beweis | disabled / unreachable / ohne debug / Drift 1-3 |
|---|---|---|---|---|---|
| stable33 amd64 | 132 passed | 46 passed | 49 passed, 152 skipped | 11 passed | je 11 passed |
| stable33 arm64 | 132 passed | 46 passed | 49 passed, 152 skipped | 11 passed | je 11 passed |
| stable34 amd64 | 132 passed | 46 passed | 49 passed, 152 skipped | 11 passed | je 11 passed |
| stable34 arm64 | 132 passed | 46 passed | 49 passed, 152 skipped | 11 passed | je 11 passed |
| stable35 amd64 | 132 passed | 46 passed | 49 passed, 152 skipped | 11 passed | je 11 passed |
| stable35 arm64 | 132 passed | 46 passed | 49 passed, 152 skipped | 11 passed | je 11 passed |

Kein Bein meldet `failed` oder `flaky` (grep über das ganze Log). Die 152 skipped sind die Projekt-Zuordnung (`only(testInfo, ...)`), nicht übersprungene Fälle: jeder @phase4-Fall läuft in seinen Projekten.

@phase4-Zeilen (stable35 amd64, gleich in allen sechs Beinen, alle PASS), darunter die in Push 1 rot gebliebenen bzw. nicht erreichten:

- X1 Export am Video (w375/w768/w1280 hell und dunkel, hc-1280, fr-w375), X1 grober Zeiger 44 px (w375-light)
- X1a Audiodatei: drei Downloads, keine Spur
- X2 Teiltranskript: gleiche Zeit auf der Seite, im TXT-Kopf und in der VTT-NOTE
- X3 Download-Sperre, Ansehen erlaubt: nur T13 und T24, Export, Spur und Ablage 403; X3 Kombifall gesperrt und ausgeschlossen
- X4 ohne Transkript und ausgeschlossen: Hauptbereich ab dem Ausschnitt byte-gleich
- X5 nur lesen mit Download: T23 statt Knopf
- X6 ohne JavaScript: Downloads gehen, Ablage-Knopf unsichtbar, T20 steht
- D1 Downloads SRT, VTT, TXT (Name mit Sprache und Umlaut, MIME, TXT-Zeile 2 = T35); D2 Fehlerseite bei gestopptem Container, T29/T25/T30, gleiches ?t=
- S7 Vorbedingung, Zahlklasse, Wortformen, Kompositum, "12:30", Suche im Dialog; S6 Datums- und Personenfilter (hell und dunkel); SRCH-04 Empfänger mit Download-Sperre findet Treffer
- E1 und E2 Ablage und Kollision (byte-gleich), E2 Hochkontrast und Französisch, E3, E4, E5 name_too_long, E6 Rate-Limit, E7 Container gestoppt
- Spur im Player (Chromium und firefox-w1280-light): "Deutsch, Untertitel-Entwurf", standardmäßig aus, Cue zur Zeit der VTT
- Kontrast-Fall (w375/w768/w1280 hell und dunkel, hc-1280): Erklärsatz, Ablage-Satz und Knöpfe mindestens 4,5:1
- axe-Selbsttest (Knopf ohne Namen, Bild ohne Alt sind kritisch)

axe: Alle @axe-Fälle (X1, X1a, X2, X3, X4, X5, D2, E1 bis E7) bestanden in allen sechs Beinen, also keine serious/critical-Befunde; der Selbsttest belegt, dass die Prüfung anschlägt.

Kontrast: Der Fall prüft `ratio >= 4.5` für vier Teile je Projekt und bestand überall. Die gemessenen Zahlen landen nur als Playwright-Annotation `contrast`; der list-Reporter druckt sie nicht ins Log und das Artefakt `phase4-screens-*` enthält nur Bilder und Downloads. Zahlenwerte liegen deshalb nicht im CI-Beleg (siehe Lücken).

test_downloaded_subtitles.py (`uv run pytest tests/test_downloaded_subtitles.py -q -rs`, CI=true, AVS_FFMPEG = gepinntes BtbN-LGPL-ffmpeg, AVS_L10N_DIR gesetzt): `...........  [100%]  11 passed` in jedem Bein (1,03 s bis 1,20 s), kein skip.

Beifang-Messung mit echter ngerman: in 04-14 als erledigt über 04-06 geführt, kein CI-Schritt vorgesehen.

### PHPUnit-Dateien

Der Lauf meldet nur die Gesamtsumme (OK, 921 tests, 11512 assertions); `php -l` nennt jede Datei. Testmethoden je Datei (statisch gezählt, Datenprovider vervielfachen die Fälle): ExportControllerTest 33 (5 Provider), SidecarTest 8 (2), SearchFiltersTest 16 (0), DownloadPolicyTest 6 (2), PlayControllerTest 51 (6). Alle fünf liegen in `php/tests/Unit` und laufen im grünen Gesamtlauf.

### main und ghcr

- main: vorher und nachher `ea97b587154426a8a23daab57f34905a7089afdb refs/heads/main` (`cmp` gleich)
- ghcr `audio_video_search_backend`: vorher und nachher `STATE 404 Package not found`; Positivkontrolle `findling_backend` liefert 1.6.2
- Plan-Prüfung: `gh run list --commit 56f3627…`: 0 nicht-success, vier Workflows

## Korrekturschleife aus 04-16: Abnahmebilder (lokal, wartet auf Push 3)

Owner-Entscheide 16.11.2026 nach der Prüfliste der UI-Abnahme. Nur Testcode und Prüfvertrag, kein Produktcode; keine Erwartung aufgeweicht, kein neuer Text.

| Commit | Inhalt |
|---|---|
| ce6a68d | docs(04-16): S6 im Prüfvertrag nennt den Providernamen des Produkts ("Audio and video", DE "Audio und Video", FR "Audio et vidéo") |
| a6c0e3f | test(04-16): Abspielseite ganz, deutsch, Abschnitts- und Bannerbilder, X4-Fälle, Spur aus und Spurmenü, X5/X6 in Ruhe, Kontrastwerte im Log |
| ee556b4 | test(04-16): S6/S7 deutsch, je S7-Suchbegriff ein Bild der Trefferliste |

**Warum die Bilder Fensterausschnitte waren:** `screenshot()` setzte schon `fullPage: true`, aber auf Nextcloud wächst das Dokument nie; `#app-content` scrollt in sich. Playwright misst die Dokumenthöhe und nimmt deshalb genau das Fenster (x 900 px). `wholePage()` vergrößert das Fenster, bis kein innerer Scroller mehr überläuft (höchstens vier Runden, Deckel 8000 px), und setzt es danach zurück.

**Warum die DE-Bilder englisch waren:** Nur `phase4User()` liefert elke (de_DE). Die Fälle, deren Zustand an einer bestimmten Person hängt, meldeten sich als alice (X1a, X2, X4, S6, S7: Eigentümerin der Clips), carol (X5, E3, E4: Freigabe des Ordners Ablage) oder dora (Hochkontrast) an. ci/seed.sh setzt die Sprache nur für elke und fleur; alle anderen bekommen bei der ersten Anmeldung die Browsersprache (en-US) als Nutzersprache gespeichert. `phase4User()` gab für Hochkontrast ausdrücklich `en` zurück. Jetzt schaltet `withLanguage()` die Person für den Fall per occ (`core lang`/`locale` wie im Seed) auf Deutsch und baut in finally zurück; ein Worker, also trifft kein anderer Fall die Person dazwischen. Die Byte-Vergleiche von X4 laufen weiter mit dora und oskar auf demselben (englischen) Katalog, die deutschen X4-Bilder entstehen danach.

**Neue Bilder:** `*-section` (X1, X1a, X2, X3, X5, X6), `*-banner` (D2, E1 bis E7), `x4-reason` (kaputt.mp3), `x4-excluded` (elke ausgeschlossen, A5), `x4-pending` (Datei aus X2 vor dem ersten fertigen Stück, wenn erwischt, sonst Annotation `gap`), `track-off` (Chromium und Firefox), `track-menu` und `track-menu-player` (nur Chromium; Firefox-Menü ist von der Seite aus nicht erreichbar, Annotation `gap`), `s7-term-NN-<begriff>` je Suchbegriff plus "12:30".

**Prüfbar im Log nach Push 3:** `CONTRAST kontrast-<projekt> <teil> <wert>:1 text <farbe>` (vier Zeilen je Kontrast-Projekt), `S7-TERM <bild> "<begriff>" hits in the dialog: <n>`, bei Bedarf `GAP track-menu ...`.

**X5/X6:** Der dunklere TXT-Knopf ist Hover und Fokus nach dem letzten Download-Klick (`a.button` des Kerns färbt bei `:hover`/`:focus`). Vor dem Bild verlässt der Zeiger die Seite und der Fokus wird gelöst (X6 ohne JavaScript: neu laden); eine neue Prüfung verlangt dann dieselbe Hintergrundfarbe für alle drei Knöpfe.

**Statisch geprüft:** tsc 5.9.3 über die Scratchpad-tsconfig 0 Fehler (Positivkontrolle 2 Fehler); `--list --grep @phase4` 207 Einträge in 3 Dateien (vorher 201, neu der S7-Bilderfall in 6 Projekten); Hauptlauf 132, `--grep @axe` 105 unverändert; Python-Gates grün, pytest 2352 passed, 18 skipped, 4 xfailed.

**Offen bis Push 3:** Spurmenü über die DevTools-Box des Bedienelements ist ungetestet gegen echtes Chromium (fällt nur als Lücke, nicht als Fehler aus); die S7-Bilder je Begriff zeigen die Gruppe nach dem letzten Suchlauf, ein kurzes Nachrendern ist nicht eigens abgewartet.

## Deviations from Plan

1. **debug-Prüfung gegen origin/phase-03 statt origin/main.** `git log --name-only origin/main..HEAD` trifft vier alte Commits mit `.planning/debug/`: afec969, 6c2ba5e (discovery-push11-wait-preview.md), f61cb37, 6ddfd34 (discovery-push9-exclude-after.md). Alle vier stehen schon auf origin/phase-03 und sind damit längst öffentlich; gegen origin/phase-03 ist die Prüfung leer. Autor- und Textprüfung gegen origin/phase-04 waren sauber.
2. **Sechs Fix-Commits zwischen Push 1 und Push 2** (Tabelle oben), jeweils dem verursachenden Plan zugeordnet.
3. **ghcr-Dateien normalisiert:** Die gh-Ausgabe beim 404 wurde wie bei Push 1 als `STATE 404 Package not found` gespeichert, damit der Vorher/Nachher-Vergleich dieselbe Form hat.

## Lücken

- Kontrast-Zahlen nicht im Log (nur Annotation). Der Grenzwert 4,5:1 ist in allen Projekten und Beinen belegt; wer die Zahlen braucht, bekommt sie über einen JSON-Reporter oder ein `console.log` im Kontrast-Fall (Owner-Entscheid, kein Fix ohne Freigabe).
- PHPUnit-Zähler je Datei nur statisch, der CI-Lauf druckt keine testdox-Ausgabe.

## Threat Flags

Keine neue Angriffsfläche im Code (nachgetragen im Sicherheitsaudit 17.11.2026, Formlücke laut 04-SECURITY.md); der Plan ist ein Push- und CI-Tor.
- T-04-54: Freigabedateien `approvals/push-*`, Autor und Committer aller Commits street1983nk, keine Sitzungs- oder closes-Zeilen.
- T-04-55: `main-before-*`/`main-after-*` und `ghcr-before-*`/`ghcr-after-*` gleich, main und ghcr unverändert.
- T-04-56: Läufe einzeln nacheinander beobachtet, ein Rerun statt Neustart.

## Self-Check: PASSED

- Läufe 43926051406, 43926051467, 43926051392, 43926051421, 43933705196 für 56f3627 alle success
- Commits 7ea6aba, 355ca4d, 665153f, 7f2c77a, 0f80494, 56f3627 vorhanden und auf origin/phase-04
