---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 07
subsystem: php-admin
tags: [lockstep, backend-state, admin-settings, debug-switch, a11y, ui-spec]
requires:
  - "01-03 (ExAppService mit lockstep, driftOnRecord, searchAllowed, proxyRequest-Naht)"
  - "01-04 (alle Admin-Texte in php/l10n)"
  - "01-06 (Banner-Klassen avs-banner* in play.css, Asset-Gate test_ui_assets.py)"
provides:
  - "ExAppService::backendState(uid) mit sieben Zuständen, exAppInfo() als Testnaht, STATE_*-Konstanten, KEY_BACKEND_STATE"
  - "searchAllowed() auf gemerktem Zustand (höchstens 60 s, sonst neu unter dem ersten aktiven Admin)"
  - "Routen GET /apps/audio_video_search/admin/state und POST /apps/audio_video_search/admin/sample (nur Admin, requesttoken, 403 ohne debug)"
  - "Eigene Admin-Sektion audio_video_search (Section, Admin, admin.php, admin.js, admin.css), info.xml settings-Block"
affects: [01-08, 01-09, 01-11]
tech-stack:
  added: []
  patterns:
    - "Gegen-App-Zustand: app_api aktiv, Registrierung (getExApp ohne Netz), enabled, Drift aus Registrierung, GET /status, Drift aus appVersion, sonst ok/patch"
    - "Versionen in übersetzten Sätzen über Platzhalter U+E000/U+E001/U+E002 gesplittet, als span/time gerendert, JS ersetzt nur Textknoten"
    - "Übersetzte Wörter für JS (unknown, Checking…, Saved, Fehler) als data-Attribute aus dem Template, kein t() im JS"
key-files:
  created:
    - php/lib/Controller/SettingsController.php
    - php/lib/Settings/Admin.php
    - php/lib/Settings/Section.php
    - php/templates/admin.php
    - php/js/admin.js
    - php/css/admin.css
    - php/tests/Unit/BackendStateTest.php
    - php/tests/Unit/SettingsControllerTest.php
  modified:
    - php/lib/Service/ExAppService.php
    - php/tests/Unit/ExAppServiceTest.php
    - php/appinfo/info.xml
    - backend/tests/test_ui_assets.py
decisions:
  - "exAppInfo() liefert array|false|null: false = AppAPI-PublicFunctions nicht auflösbar (no_app_api), null = nicht registriert (backend_missing)"
  - "Unbekannte Version auf einer Seite = version_patch_differs (Hinweis, Suche normal), nie ok und nie Drift"
  - "Die von /status gemeldete appVersion schlägt die registrierte Version; beide werden als backend_app_version gemerkt, damit ein neuer Befund eine alte Drift auf Vorrat ablöst"
  - "searchAllowed ohne aktiven Admin bleibt offen (Aufruf scheitert ohnehin still in eine leere Gruppe)"
  - "Wirft die Registrierungsabfrage, gilt backend_unreachable; Log nur mit Klassennamen"
  - "Link 'Apps öffnen' wird im Template über IURLGenerator::linkToRoute('settings.AppSettings.viewApps') gebildet"
metrics:
  duration: "ca. 10 min"
  completed: 2026-11-06
  tasks: 2
  files: 12
---

# Phase 1 Plan 07: Gegen-App-Zustand, Admin-Sektion und Debug-Schalter Summary

backendState() mit sieben Zuständen (Registrierung aus AppAPI, dann GET /status), searchAllowed() auf dem höchstens 60 s alten Befund, eigene Admin-Sektion mit serverseitig gerenderten Bannern, "Erneut prüfen" ohne Seitenneuladen und Testtreffer-Schalter, der nur bei `debug => true` erscheint und wirkt.

## Was gebaut wurde

**Task 1 (TDD): backendState, searchAllowed, Admin-Routen**
- `ExAppService::backendState()` prüft in der Reihenfolge von Pattern 1: app_api für den Nutzer aktiv, Registrierung über `exAppInfo()`, enabled (true/1/'1'), Major.Minor der Registrierung, `GET /status` (1,5 s, über dieselbe `call()`-Prüfkette), Major.Minor der gemeldeten `appVersion`. Felder `companion` (ok/missing/unknown) und `sampleCount` (int >= 0) typgeprüft, sonst null.
- Ergebnis `{state, own, backend, companion, sampleCount, checkedAt}` wird als JSON in IAppConfig `backend_state` gemerkt.
- `searchAllowed()`: Drift auf Vorrat sperrt weiter sofort; sonst gilt der gemerkte Zustand, wenn er 0 bis 60 s alt und wohlgeformt ist, sonst neu ermittelt unter dem ersten aktiven Mitglied der Gruppe admin. Offen nur bei ok und version_patch_differs.
- `SettingsController`: `GET /admin/state` (500 mit statischem Satz bei Ausnahme), `POST /admin/sample` (403 "Debug mode is off." ohne debug, 400 bei Nicht-Boolean, 500 bei Speicherfehler). Keine Attribute, die Admin, Token oder Sitzung aufheben; Test liest das per Reflection.
- Tests: BackendStateTest (23 Testmethoden, mit Datenprovidern), SettingsControllerTest (7 Methoden, Datenprovider für Booleans und Nicht-Booleans).

**Task 2: Admin-Sektion**
- info.xml: `<settings>` mit Admin und Section.
- Section: ID `audio_video_search`, Name "Audio & Video Search", Priorität 75, `app-dark.svg`.
- Admin: Zustand, `debug`, `sampleVisible` als Initial-State `bootstrap` (nur Codes, Versionen, Zahlen, Booleans), Zeit über `IDateTimeFormatter::formatTime`, `RENDER_AS_BLANK`.
- admin.php: h2, Zustandsbereich `#avs-backend-state` (`role="status" aria-live="polite" tabindex="-1"`) mit allen sieben Bannern (aktueller sichtbar), Fehler-Banner mit Link "Apps öffnen", Warn-Banner für gescheiterte Neuprüfung, Versions- und Zeitzeile, Knopf "Erneut prüfen", Debug-Block nur mit `debug`.
- admin.js: Neuprüfung mit `disabled`, Spinner, "Wird geprüft…", `aria-busy`, danach Fokus auf den Zustandsbereich; Schalter mit "Gespeichert" für 3 s oder Fehlertext und Rücksprung.
- admin.css: nur Admin-Ergänzungen; Banner-Regeln kommen aus play.css. Asset-Gate um `test_the_admin_section_keeps_its_contract` erweitert.

## Verifikation

- `uv run pytest -q`: 323 passed; ruff check, ruff format --check, pyright (latest, 0 Fehler), vulture grün.
- test_php_gates (Regeln 1 bis 9), test_ui_assets, test_trilingual grün.
- Alle grep-Abnahmen beider Tasks erfüllt (sieben Codes, `getExApp(` genau 1, Routen je 1, `<admin-section>` 1, kein `innerHTML`).
- phpunit läuft lokal nicht (kein PHP); BackendStateTest und SettingsControllerTest laufen in CI (php.yml, Plan 11).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] exAppInfo mit Rückgabe array|false|null statt ?array**
- **Found during:** Task 1
- **Issue:** Mit `?array` ließen sich "PublicFunctions nicht auflösbar" (no_app_api laut Zustandstabelle) und "nicht registriert" (backend_missing) nicht unterscheiden.
- **Fix:** false für nicht auflösbare AppAPI, null für nicht registriert; dokumentiert und getestet.
- **Commit:** 242a195

**2. [Rule 3 - Blocking] ExAppService-Konstruktor um IGroupManager und ITimeFactory erweitert**
- **Found during:** Task 1
- **Issue:** Erster Admin und Alter des gemerkten Zustands brauchen beide Dienste; ExAppServiceTest übergab nur vier Argumente.
- **Fix:** Konstruktor ergänzt (DI löst automatisch auf), ExAppServiceTest angepasst.
- **Commit:** 242a195

**3. [Rule 2 - Missing] Link-Klasse avs-banner__action statt avs-banner__link**
- **Found during:** Task 2
- **Issue:** Der Plan nennt `avs-banner__link`, play.css (Plan 06) definiert die Banner-Aktion als `avs-banner__action`. Eine neue Klasse hätte doppelte Banner-Regeln in admin.css erzwungen, was der Plan gerade ausschließt.
- **Fix:** Vorhandene Klasse `avs-banner__action` verwendet.
- **Commit:** c929838

## Anforderungen

PLAT-02 bleibt offen: die PHP-Seite (Meldung und leere Suche) ist gebaut und getestet, die Gegenrichtung (/status.companion, Plan 08) und der CI-Beweis (Pläne 10, 11, 13) fehlen noch. Deshalb nicht als erledigt markiert.

## Known Stubs

Keine. `companion` und `sampleCount` kommen erst ab Plan 08 aus `/status`; fehlen sie, gelten sie als unbekannt (Leer-Hinweis des Testtreffers sichtbar), wie im Plan vorgesehen.

## Threat Flags

Keine neuen Flächen außerhalb des Threat-Registers (T-01-32 bis T-01-36 umgesetzt: Admin+Token durch fehlende Attribute, 403 ohne debug, nur Codes/Versionen/Zahlen, Versionen per VERSION_PATTERN und p()).

## TDD Gate Compliance

RED `9618c19` (test), GREEN `242a195` (feat). Der RED-Lauf konnte lokal nicht ausgeführt werden (kein PHP); phpunit läuft in CI.

## Self-Check: PASSED
