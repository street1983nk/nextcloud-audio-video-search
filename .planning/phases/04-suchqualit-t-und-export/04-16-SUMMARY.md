---
phase: 04-suchqualit-t-und-export
plan: 16
subsystem: ui/abnahme
tags: [ui-abnahme, playwright, kontrast, SRCH-04, SRCH-06, EXP-01, EXP-03, EXP-04]
requires:
  - "04-15: grüner CI-Beweis auf phase-04 e5a2479 (Deploy through HaRP 43942105866, sechs Beine)"
provides:
  - "Owner-Abnahme aller Prüfpunkte X1 bis X6, D1, D2, E1 bis E7, Spur, S6, S7 (16.11.2026)"
  - "X3: natives Player-Menü ohne Herunterladen bei gesperrter oder unklarer Freigabe (controlslist=nodownload, fail-closed)"
  - "Prüfvertrag S7 auf die gemessenen FLEURS-Begriffe nachgezogen"
affects: [04-15, secure-phase-4, verify-work-4]
tech-stack:
  added: []
  patterns:
    - "Player-Attribut aus demselben Urteil wie der Export (DownloadPolicy, fail-closed), Template liest fehlenden Wert als Sperre"
key-files:
  created:
    - .planning/phases/04-suchqualit-t-und-export/04-16-SUMMARY.md
  modified:
    - php/templates/play.php
    - php/lib/Controller/PageController.php
    - php/tests/Unit/PlayControllerTest.php
    - backend/tests/test_ui_assets.py
    - ci/playwright/export.spec.ts
    - .planning/phases/04-suchqualit-t-und-export/04-UI-SPEC.md
    - .planning/phases/04-suchqualit-t-und-export/04-VALIDATION.md
    - .planning/phases/04-suchqualit-t-und-export/deferred-items.md
decisions:
  - "Owner 16.11.: alle Prüfpunkte abgenommen (Lauf 43942105866)"
  - "Owner 16.11.: Spurmenü T31 ohne Bild akzeptiert, Beleg nur über den DOM-Test"
  - "Owner 16.11.: S7-Vertrag auf Polizei/Seite nachgezogen statt Häuser/Haushalt (FLEURS ohne Haushalt-Kompositum)"
  - "Owner 16.11.: X3 bekommt controlslist=nodownload, fail-closed wie der Export; nur Bedien-Hürde"
  - "Owner 16.11.: abgeschnittenes Suchwort in Trefferzeilen S6/S7 ist Backlog, kein Phase-4-Fix"
  - "Owner 16.11.: X6-Hinweis T20 ohne Knopf und wechselnde Bannerbreiten bleiben so"
metrics:
  duration: "Abnahme gemeinsam mit dem Owner, Fix und Doku ca. 45 min"
  completed: 2026-11-16
---

# Phase 4 Plan 16: Gemeinsame UI-Abnahme Summary

Der Owner hat alle Prüfpunkte an den Bildern des grünen Laufs 43942105866 (phase-04 e5a2479, sechs Beine NC 33/34/35 x amd64/arm64) abgenommen; aus der Abnahme kam ein Produkt-Fix (X3: kein "Herunterladen" im Player-Menü bei gesperrter Freigabe), ein nachgezogener Prüfvertrag (S7) und ein Backlog-Eintrag (Trefferzeilen).

## Grundlage

- Lauf "Deploy through HaRP" 43942105866 auf e5a2479, alle zehn Jobs grün; dazu "Python gates" 43942105900 und "Discovery acceptance" 43942105884.
- Bilder: 696 PNG (6 Beine x 116, Namenslisten identisch, 0 Lücken laut Inventar), 69 Auswahlbilder aus nc35-amd64; Downloads je Bein 6 Dateien.
- Prüfliste mit Befunden: Scratchpad `ui-abnahme-04b/PRUEFLISTE.md` (nicht im Repo).

## Owner-Verdikte je Prüfpunkt

| Prüfpunkt | Verdikt | Anmerkung |
|---|---|---|
| X1 | abgenommen | Reihenfolge SRT, VTT, TXT, kein Akzent, 375 und FR 375 ohne Überlauf, Hochkontrast deutsch. Seit dem Fix: Medium ohne `controlslist` (Playwright-Erwartung) |
| X1a | abgenommen | Audio, kein `<track>` (DOM-Test) |
| X2 | abgenommen | T15 mit Zeit, FR vollständig; gleiche Zeit in TXT/VTT nur im Test |
| X3 | abgenommen mit Fix | nur T13 und T24, 403-Belege im Joblog. Befund: Drei-Punkte-Menü des nativen Players bot "Herunterladen". Fix siehe unten |
| X4 | abgenommen | vier Fälle deutsch, Ausschluss nicht verraten, Pending in allen Beinen erwischt |
| X5 | abgenommen | T23 statt Knopf, drei Knöpfe gleich hell |
| X6 | abgenommen, so lassen | T20 steht ohne Knopf (vertragsgemäß); Owner: bleibt so |
| D1 | abgenommen | Namen mit Umlaut und `.de.`, T35 in TXT und VTT-NOTE |
| D2 | abgenommen | T29, T25, Rückweg T30; `?t=` nur im Test |
| E1 bis E7 | abgenommen | Texte richtig, Fokus wie Vertrag; Bannerbreiten wechseln mit dem Inhalt, Owner: bleibt so |
| Spur aus / Spur an | abgenommen | aus bei 0:00, Cue zur Zeit (Chromium 0:03, Firefox 0:04) |
| Spurmenü (T31) | akzeptiert ohne Bild | GAP in allen Beinen (Chromium-Menü ohne Untertitel-Eintrag, Firefox-Menü nicht erreichbar); Beleg nur DOM-Test. Owner: so akzeptiert |
| S6 | abgenommen | Gruppe "Audio und Video" im Hauptteil, Datum 2 Treffer, Person 1 Treffer |
| S7 | abgenommen, Vertrag nachgezogen | 14 Begriffe je 2 Treffer, "12:30" 0 Treffer ohne Fehler, in allen sechs Beinen gleich |

## Kontrast (CONTRAST-Zeilen, alle sechs Beine gleich)

| Thema | `.avs-export__note` / `__hint` | Download- und Ablage-Knopf |
|---|---|---|
| hell (375, 768, 1280) | 5,33:1 | 12,96:1 |
| dunkel (375, 768, 1280) | 6,29:1 | 8,47:1 |
| Hochkontrast 1280 | 21,00:1 | 12,86:1 |

Alle über 4,5:1, kein Wechsel auf `--color-main-text` nötig. axe: Fälle `@axe` grün (kein serious/critical), Bericht nicht im Artefakt.

## Entscheide und Folgen

1. **X3, Player-Menü (Fix, Commit 42c0cae):** `play.php` setzt `controlslist="nodownload"` am `<video>`/`<audio>`, wenn `mediaNoDownload` nicht ausdrücklich `false` ist. Der Controller setzt `mediaNoDownload = $verdict !== DownloadPolicy::ALLOWED`, also dieselbe fail-closed-Lesart wie der Export: gesperrt (X3) und unklares Freigabe-Attribut (UNKNOWN, spielt, aber ohne Menüeintrag) bekommen das Attribut, eigene Datei und Freigabe mit Download nicht. Kein neuer Text.
   - **Nur eine Bedien-Hürde, keine technische Sperre:** Das Medium wird zum Abspielen an den Browser übertragen; wer will, kommt über Entwicklerwerkzeuge oder einen anderen Browser weiter an die Bytes. Die eigentliche Sperre bleibt WebDAV (ViewOnlyPlugin) und der Server-Schalter "Ansehen ohne Download".
   - Belege: PHPUnit `testOnlyAClearAllowedLeavesTheDownloadEntryOfThePlayer` und `testTheRenderedMediumOfABlockedShareCarriesNoDownloadAndAnOpenOneDoesNot` (laufen nur in CI); Gate `test_a_blocked_share_hides_the_download_entry_of_the_player` mit Gegenprobe `test_self_no_download_rule_fires` (immer an, gar nicht, fail-open-Standard, Wiedergabe-Lesart des Urteils feuern je für sich); Playwright X3 `toHaveAttribute('controlslist', 'nodownload')`, X1 `#avs-media[controlslist]` = 0.
   - Prüfvertrag 04-UI-SPEC (X3-Zeile und Abschnitt "Verhältnis zu Phase 3") und 04-VALIDATION (Zeile 04-16-03) nachgezogen.
2. **S7-Begriffe:** Vertrag 04-UI-SPEC auf die gemessenen Begriffe nachgezogen (20/zwanzig/twenty/vingt, zwölf/12/twelve/douze, Polizist, Polizisten, Polizei, Polizeipräsidium, Seite, Seitenverhältnis, 12:30). Begründung: FLEURS hat kein Kompositum mit dem Kopf "Haushalt"; "Haushalt" findet "Haushaltsplanberatung" belegt `backend/tests/test_compounds.py`, "Häuser" `test_search_numbers.py`/`test_compounds.py`. 04-VALIDATION nannte die alten Begriffe nicht, dort nichts zu ändern.
3. **Spurmenü T31 ohne Bild:** akzeptiert, Beleg bleibt der DOM-Test.
4. **Trefferzeilen S6/S7:** Suchwort oft abgeschnitten (Phase-3-Trefferbild). Backlog-Eintrag in `deferred-items.md` (Abschnitt "Aus Plan 04-16"), kein Fix in Phase 4.
5. **X6-Hinweis ohne Knopf und Bannerbreiten:** bleiben so.

## Lücken (bewusst offen)

- Spurmenü T31: kein Bild (Chromium GAP, Firefox nicht erreichbar), nur DOM-Test.
- Kontrast für Knopfrand/Fokusring (3:1) und die Banner-Paare: ohne Messzahl im Log.
- axe-Bericht nicht im Artefakt, nur Ergebnis der Fälle.
- Der X3-Fix ist lokal und in CI noch nicht belegt (PHPUnit, Playwright X1/X3 brauchen Push 4 mit Owner-Freigabe).
- Transkript "detonier" statt "detonierte" und abweichendes TXT in nc34-amd64: Erkennung, keine UI-Frage.

## Deviations from Plan

- Der Plan sah nur Abnahme ohne Repo-Dateien vor; der Owner-Befund X3 wurde wie vorgesehen als `fix(04-16)` umgesetzt (Korrekturschleife 04-15). Neuer Push (Push 4) steht aus.

## Gates (lokal, vor jedem Commit)

ruff check und format --check grün, pyright 0 Fehler, vulture grün, volle pytest-Suite 2354 passed, 18 skipped, 4 xfailed (vorher 2352, plus zwei Gate-Fälle; Ausgabe im Scratchpad `suite-0416-x3fix.txt`), tsc über Scratchpad-tsconfig 0 Fehler (Kontrolle mit `bad.ts` feuert), `npx playwright test --list --grep @phase4` 207 Tests in 3 Dateien (wie vorher).

## Commits

| SHA | Typ | Inhalt |
|---|---|---|
| 42c0cae | fix(04-16) | X3: Player-Menü ohne Herunterladen, fail-closed; PHPUnit, Gate mit Gegenprobe, Playwright X1/X3 |
| 52e8da1 | docs(04-16) | Prüfvertrag S7 und X3 nachgezogen, VALIDATION-Zeile, Backlog Trefferzeilen |
| (dieser) | docs(04-16) | SUMMARY, REQUIREMENTS SRCH-06, ROADMAP 17/17, STATE |

## Requirements

SRCH-04, SRCH-05, SRCH-06 und EXP-01 bis EXP-04 abgehakt (Belege 04-15-SUMMARY: alle Workflows und sechs Beine grün; 04-16: Owner-Abnahme). SRCH-04, SRCH-05, EXP-01 bis EXP-04 standen schon; neu abgehakt ist SRCH-06 (S6 abgenommen). Phase 4 bleibt im ROADMAP offen, bis secure-phase 4 und Push 4 durch sind.

## Was CI noch belegen muss (Push 4, Owner-Freigabe)

- PHP gates: PHPUnit `PlayControllerTest` mit den zwei neuen Fällen (PHP lokal nicht vorhanden).
- Deploy through HaRP: X3 (`controlslist="nodownload"` am Medium) und X1 (kein `controlslist`) in allen sechs Beinen; die übrigen @phase4-Fälle unverändert grün.

## Self-Check: PASSED

- 42c0cae und 52e8da1 im Log, Dateien vorhanden (play.php, PageController.php, PlayControllerTest.php, test_ui_assets.py, export.spec.ts, 04-UI-SPEC.md, 04-VALIDATION.md, deferred-items.md).

## Push 4 (CI-Beleg des nodownload-Fixes)

Push mit Owner-Freigabe: `phase-04` e5a2479..f7bb9da (42c0cae, 52e8da1, c2896a8, f7bb9da). Nur Push-Läufe, kein Discovery-Dispatch mit `legs=all`. `main` unverändert: `git ls-remote origin refs/heads/main` per `cmp` identisch mit `approvals/main-before-f7bb9dafe0bf0d5a5fa82017c6cb400a286944b6` (ea97b58).

| Workflow | Lauf | Ergebnis |
|---|---|---|
| PHP gates | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43955067820 | grün, PHPUnit `OK (923 tests, 11531 assertions)`, darunter die zwei neuen Fälle in `PlayControllerTest` (`testOnlyAClearAllowedLeavesTheDownloadEntryOfThePlayer`, `testTheRenderedMediumOfABlockedShareCarriesNoDownloadAndAnOpenOneDoesNot`) |
| Python gates | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43955067741 | grün (inkl. Gate `test_ui_assets`) |
| Discovery acceptance (Push-Lauf) | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43955067760 | grün |
| Deploy through HaRP | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/43955067783 | grün nach Versuch 2 (alle sechs deploy-Beine und vier upgrade-Beine) |

**HaRP Versuch 1:** fünf deploy-Beine grün; `deploy-harp stable35 ubuntu-24.04` mit einem Fehler in "Playwright on the running instance" (131 passed, 1 failed): `[w375-light] play.spec.ts:194 Suchtreffer für die Abnahme @screenshot`, Login blieb auf `/index.php/login` (`helpers.ts:121`, `not.toHaveURL` nach 5 s). Kein Bezug zum Fix, derselbe Test in allen anderen Projekten und Beinen grün: Flake, einmal `gh run rerun --failed`. **Versuch 2:** Bein grün, Job 133630300374, "Playwright on the running instance" 132 passed.

**@phase4 je Bein** (Schritt "Playwright, search quality and export of phase 4"): 50 passed, 157 skipped in allen sechs Beinen (stable33/34/35 je amd64 und arm64; stable35 amd64 aus Versuch 2). Phase-3-Schritt je Bein 46 passed, Parser der echten Downloads 11 passed.

**X3 (Attribut vorhanden) und X1 (kein Attribut), PASS-Zeilen** (je Bein 11 X1/X3-Treffer grün), Beispiel stable35 amd64, Versuch 2:

```
✓    5 [w375-light] › export.spec.ts:471:1 › X3 Freigabe mit Download-Sperre, Ansehen erlaubt: nur T13 und T24, Export, Spur und Ablage 403 @phase4 @axe @screenshot (3.9s)
✓    1 [w375-light] › export.spec.ts:258:1 › X1 Export am Video: Reihenfolge SRT, VTT, TXT, kein Akzent, Klickfläche, Spur ohne default @phase4 @axe @screenshot (4.3s)
```

und stable33 arm64, Versuch 1:

```
✓  129 [w1280-light] › export.spec.ts:471:1 › X3 Freigabe mit Download-Sperre, Ansehen erlaubt: nur T13 und T24, Export, Spur und Ablage 403 @phase4 @axe @screenshot (6.6s)
✓  125 [w1280-light] › export.spec.ts:258:1 › X1 Export am Video: Reihenfolge SRT, VTT, TXT, kein Akzent, Klickfläche, Spur ohne default @phase4 @axe @screenshot (5.7s)
```

X3 prüft `toHaveAttribute('controlslist', 'nodownload')` an `#avs-media`, X1 `#avs-media[controlslist]` mit Anzahl 0 (Diff 42c0cae in `ci/playwright/export.spec.ts`).
