---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 04
subsystem: l10n-und-e2e
tags: [l10n, trilingual, french-nbsp, playwright, e2e, testmedia]
requires:
  - "01-01 (php/appinfo/info.xml mit App-ID, scripts/l10n_js.py, backend/l10n, test_trilingual.py)"
  - "01-03 (Provider mit t('Audio and video') und t('Test result'))"
provides:
  - "php/l10n/{de,de_DE,en,fr}.json/.js: 48 Schlüssel aller UI-SPEC-Flächen 1 bis 3"
  - "Dreisprachigkeits-Gate über beide Katalogwurzeln, beide info.xml und t()-Literale aus php/lib, php/templates, php/js"
  - "ci/playwright: fehlschlagender E2E-Kernweg in chromium-light und chromium-dark"
  - "ci/make-testmedia.sh: tone-90s.webm (VP9/Opus) und tone-90s.ogg (Opus) per ffmpeg lavfi"
affects: [01-05, 01-06, 01-07, 01-08, 01-09, 01-10, 01-11]
tech-stack:
  added: ["@playwright/test 1.65.0 (nur ci/playwright, devDependency, Lockfile mit Integrity)"]
  patterns:
    - "Katalogschlüssel = englischer UI-SPEC-Text; en.json bildet jeden Schlüssel auf sich selbst ab"
    - "Verbotene Zeichen im Gate per chr() gebaut, damit die Testdatei das eigene Gate besteht"
    - "Jede neue t()-Zeichenkette in PHP/Templates/JS fällt im Gate auf, solange sie im Katalog fehlt"
key-files:
  created:
    - php/l10n/de.json
    - php/l10n/de.js
    - php/l10n/de_DE.json
    - php/l10n/de_DE.js
    - php/l10n/en.json
    - php/l10n/en.js
    - php/l10n/fr.json
    - php/l10n/fr.js
    - ci/playwright/package.json
    - ci/playwright/package-lock.json
    - ci/playwright/playwright.config.ts
    - ci/playwright/play.spec.ts
    - ci/make-testmedia.sh
  modified:
    - backend/tests/test_trilingual.py
    - backend/tests/test_settings.py
    - backend/tests/test_public_texts.py
    - scripts/l10n_js.py
    - .gitignore
key-decisions:
  - "FR-Regel prüft nur normales Leerzeichen vor : ; ? ! » und nach «; Platzhalter und URLs werden vorher entfernt, das Leerzeichen davor bleibt also prüfbar"
  - "Platzhaltervergleich als sortierte Liste je Wert gegen den englischen Schlüssel (%s, %1$s, {name})"
  - "l10n_js.py ohne --root prüft jetzt beide Wurzeln (backend/l10n, php/l10n); App-ID je Wurzel weiter aus der info.xml daneben"
  - "Unified-Search-Öffnen im E2E: Kopfleisten-Knopf, sonst Control+K; Treffer über Link mit Dateiname und Unterzeile '0:42 · '"
requirements-completed: []
metrics:
  duration: "ca. 35 min"
  completed: 2026-11-06
  tasks: 2
  files: 18
---

# Phase 01 Plan 04: Kataloge DE/EN/FR und E2E-Kernweg Summary

Alle 48 UI-SPEC-Texte der PHP-App in php/l10n (de = de_DE byte-gleich, fr mit 13 echten U+00A0), ein auf beide Katalogwurzeln erweitertes Dreisprachigkeits-Gate mit 21 Tests (Selbsttest je Regel) und der Kernweg als fehlschlagender Playwright-Vertrag mit CI-Testmedien.

## Ergebnis

- **Kataloge:** Flächen 1 bis 3 vollständig, inkl. "Saved", "Not saved. Try again.", "Checking…" (U+2026) und "Jump to %s". Die Backend-Beschreibung bleibt in backend/l10n. Die beiden in Plan 03 nur englisch gelieferten Provider-Texte ("Audio and video", "Test result") haben jetzt DE/FR.
- **Gate (`test_trilingual.py`):** Schlüsselgleichstand php/l10n (de, de_DE, en, fr) und backend/l10n (de, en, fr); leere Werte; de != de_DE; U+2013/U+2014 und Emoji (U+1F300 bis U+1FAFF, U+2600 bis U+27BF) in Schlüssel oder Wert; FR-Leerzeichen; Platzhalter; .js-Zwilling (App-ID, Übersetzungen, Pluralform); Store-Texte beider info.xml; alle `t()`-Literale der PHP-App im Katalog (mit Positivkontrolle "Audio and video"). Positivkontrolle für FR: U+00A0 kommt im Katalog wirklich vor.
- **`test_settings.py`:** `l10n_js.py --check` über beide Wurzeln. **`test_public_texts.py`:** Umlaut-Audit liest zusätzlich php/l10n/de.json.
- **E2E:** `npx playwright test --list` zeigt "Kernweg" in chromium-light und chromium-dark (2 Tests). Keine Browser geladen (`npm ci --ignore-scripts`). Der Test schlägt bis zum CI-Lauf in Plan 11 fehl.
- **Testmedien:** `ci/make-testmedia.sh` nur per `bash -n` geprüft (lokal kein ffmpeg), Ausführung in CI.

## Commits

| Task | Commit | Inhalt |
|------|--------|--------|
| 1 RED | d57ff8d | test(01-04): Dreisprachigkeits-Gate für php/l10n als rote Tests |
| 1 GREEN | c8b50fb | feat(01-04): Kataloge DE/DE_DE/EN/FR der PHP-App aus der UI-SPEC |
| 1 | bd13cd8 | feat(01-04): l10n_js.py prüft ohne --root beide Katalogwurzeln |
| 2 | cacb593 | feat(01-04): fehlschlagender E2E-Kernweg und Testmedien-Skript für CI |

## Verifikation

- `uv run pytest -q`: 221 passed; ruff check, ruff format --check, pyright (latest), vulture grün.
- `cmp php/l10n/de.json php/l10n/de_DE.json`: gleich. Skriptprüfung: 0 Gedankenstriche in allen php/l10n-Dateien, 13 U+00A0 in fr.json und fr.js, 0 in de/en.
- Akzeptanz-greps: "Diese Datei ist nicht verfügbar" 1, "Audio et vidéo" 1, "Résultat de test" 1, "Zur Zeitstelle %s springen" 1, `def test_` 21; package.json-Pin 1, "Audiosuche" vorhanden, "206" vorhanden, waitForTimeout 0, libvpx-vp9 1, libopus 2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Umlaut-Audit auch über php/l10n/de.json**
- **Found during:** Task 1
- **Issue:** `test_public_texts.py` prüfte nur backend/l10n/de.json auf Umschreibungen (ae/oe/ue); der neue deutsche Katalog wäre ungeprüft geblieben (Owner-Regel Umlaut-Audit aller nutzersichtbaren Texte).
- **Fix:** php/l10n/de.json in `german_texts()` aufgenommen.
- **Files modified:** backend/tests/test_public_texts.py
- **Commit:** d57ff8d

**2. [Rule 2 - Missing critical] t()-Literale der PHP-App gegen den Katalog geprüft**
- **Found during:** Task 1
- **Issue:** Ohne diese Regel könnte ein späterer Plan einen `t()`-Text einführen, der nur englisch erscheint (wie in Plan 03 geschehen).
- **Fix:** Test scannt php/lib, php/templates, php/js nach `->t('…')` und `t('audio_video_search', '…')`, mit Selbsttest.
- **Commit:** d57ff8d

## Known Stubs

Keine. Der E2E-Test ist bewusst fehlschlagend (Vertrag für Plan 05 bis 11), kein Stub.

## Hinweise für Folgepläne

- JS übersetzt mit `t('audio_video_search', 'Jump to %s')` und ersetzt `%s` selbst; das Gate erkennt nur diese Literalform.
- Locators im E2E (Kopfleisten-Knopf, Dialog-Eingabe, Treffer-Link) sind ungeprüft gegen eine echte Instanz; Plan 09/11 justiert sie am ersten CI-Lauf.
- Anforderungen PLAY-01, PLAY-02, PLAT-02 sind durch diesen Plan nur als Vertrag festgeschrieben, nicht erfüllt; deshalb nicht als erledigt markiert.

## Self-Check: PASSED
