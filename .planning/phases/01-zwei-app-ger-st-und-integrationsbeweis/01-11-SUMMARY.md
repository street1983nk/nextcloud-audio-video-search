---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 11
subsystem: ci-abnahme
tags: [push, ci, playwright, abnahme, zertifikat]
requires:
  - phase: 01-10
    provides: Upgrade-Job, Drift-Schritte, Store-Archive
provides:
  - Grüne CI auf phase-01 (PHP, Python, sechs HaRP-Beine plus Upgrade-Job)
  - Owner-Abnahme der Oberfläche am 07.11.2026 ("Approved")
affects: [01-VERIFICATION]
key-files:
  modified:
    - php/templates/admin.php
    - php/templates/play.php
    - php/css/play.css
    - php/css/admin.css
    - php/js/admin.js
    - php/l10n/de.json
    - php/l10n/de_DE.json
    - php/l10n/en.json
    - php/l10n/fr.json
    - ci/playwright/admin.spec.ts
    - ci/playwright/play.spec.ts
    - ci/playwright/helpers.ts
    - ci/playwright/playwright.config.ts
    - ci/seed.sh
    - .github/workflows/deploy-harp.yml
    - backend/tests/test_ui_assets.py
    - .planning/phases/01-zwei-app-ger-st-und-integrationsbeweis/01-UI-SPEC.md
duration: 07.11.2026, Push 10 bis 14
completed: 2026-11-07
---

# Plan 01-11: Push, CI und gemeinsame Abnahme

## Ergebnis

- Task 1: Owner-Wahl `push-branch`. Alle Pushes gingen nach `phase-01` (`git push origin main:phase-01`), `main` blieb unberührt; docker.yml läuft nur auf `main` und lief deshalb nicht.
- Task 2: CI auf dem letzten Stand `bedbc13` komplett grün. Zertifikatsantrag nextcloud/app-certificate-requests#1417: OPEN (nur gelesen, kein Kommentar). #1419 (PII) ebenfalls OPEN.
- Task 3: Gemeinsame Abnahme mit dem Owner über Playwright-Screenshots, NC 33/34/35, amd64 und arm64, elf Raster (EN 375/768/1280 hell und dunkel, hoher Kontrast 1280, DE und FR je 375 hell und 1280 dunkel). Owner: "Approved".

## CI-Läufe

| Push | Commit | Workflow | Ergebnis | Lauf |
|------|--------|----------|----------|------|
| 10 | cd44ea6 | Deploy through HaRP | success | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42330693906 |
| 10 | cd44ea6 | Python gates | success | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42330693914 |
| 11 | 1fb003d | Deploy through HaRP | success | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42341046230 |
| 11 | 1fb003d | PHP gates | success | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42341046188 |
| 12 | 49b28ee | Deploy through HaRP | success | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42343249043 |
| 13 | 6d28ed1 | Deploy through HaRP | success | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42345770236 |
| 14 | bedbc13 | Deploy through HaRP | success | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42347921936 |
| 14 | bedbc13 | PHP gates | success | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42347921902 |
| 14 | bedbc13 | Python gates | success | https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42347922004 |

## Befunde aus der Vorprüfung und der Abnahme

1. Link "Apps öffnen" fehlte ab NC 34: Die App-Verwaltung ist dort die App `appstore`, Route `appstore.page.viewApps`; die alte Route ergab einen leeren Link. Fix 4291faa mit Rückfall auf `settings.AppSettings.viewApps`, Playwright verlangt den Link in jedem Fehlerzustand.
2. Bannertext erbte Grau aus der Server-Regel `.section p` (Kontrast 4,5 zu 1). Fix 3d07c81: Statusfarbpaar, Abstände md, "Apps öffnen" als Akzent.
3. "Noch kein Testtreffer" stand auch bei unbekanntem Zähler. Fix d463d55: nur bei gemeldeter Null.
4. Fehlende Bilder (Suchtreffer, drei Abspiel-Banner, Admin ohne Debug) und keine DE/FR-Bilder. Fix abe74ed, 1fb003d (Nutzer elke de_DE, fleur fr).
5. Owner: Bannertexte zu lang und KI-artig. Fix 49b28ee (Admin), 7508e19 (Abspielansicht, Debug-Hinweis); Versionen nur noch in der Versionszeile. Präzisierung des Owners: nicht extrem kurz, nur nicht sinnlos lang.
6. Format-Banner empfahl Herunterladen auch bei gesperrtem Download. Fix bedbc13: eigene Variante ohne Download-Hinweis, mit Test.
7. Testbilder mit Zwischenzuständen. Ursachen belegt (6d28ed1): NC 35 sucht beim Tippen zweimal (open-Watcher ruft `find()`, der Entprell-Timer läuft weiter) und leert dabei die Liste; Chromium dreht den Ladering nach dem Laden bis 1,3 s weiter. Der Test wartet auf die letzte Suche und bis Chromium den Ring entfernt; nichts wird ausgeblendet.

## Abweichungen

- Mehr Pushes als geplant (10 bis 14), jeder einzeln vom Owner freigegeben.
- Der NC-35-Doppelsuchfehler ist ein Upstream-Fehler in nextcloud/server; eine Meldung nur nach Owner-Freigabe.

## Offen für die Verifikation

- MDI-Lizenzeintrag und Markierung der Anforderungen nach der Phasenverifikation.
- Zertifikat #1417 offen; danach Backend-Pin in release.yml und Secret BACKEND_PRIVATE_KEY.
