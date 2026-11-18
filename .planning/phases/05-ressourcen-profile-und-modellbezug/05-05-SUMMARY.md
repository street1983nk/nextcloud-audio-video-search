---
phase: 05-ressourcen-profile-und-modellbezug
plan: 05
subsystem: php/settings
tags: [RES-01, RES-05, RES-06, PLAT-04, admin, occ, contract]
requires: []
provides:
  - "SettingsController: GET /admin/resources (ExApp-Antwort + zones + defaultZone), POST /admin/resources (strenge Prüfung, 400 field, 409 durchgereicht, 503 bei stillem Backend)"
  - "ExAppService: resources(), saveResources(array) -> {status, body}, verifyModels(), isZone(), Konstanten RESOURCE_PROFILES, RESOURCE_MODELS, RESOURCE_MODEL_STATES, RESOURCE_FIELDS, RESOURCE_KEYS, TIME_PATTERN, VERIFY_TIMEOUT_SECONDS"
  - "ResourceFormat::gigabytes(int, need|available|size, IL10N)"
  - "occ audio_video_search:models [--verify] (Exit 0, 1, 2)"
affects: [05-09, 05-16, 05-22]
tech-stack:
  added: []
  patterns: ["callWithStatus neben call(): 4xx-Körper mit Status, call() unverändert", "Vertragsprüfung Schlüssel für Schlüssel, Antwort neu aufgebaut"]
key-files:
  created:
    - php/lib/Service/ResourceFormat.php
    - php/lib/Command/ModelsCommand.php
    - php/tests/Unit/ResourceFormatTest.php
    - php/tests/Unit/ModelsCommandTest.php
  modified:
    - php/lib/Service/ExAppService.php
    - php/lib/Controller/SettingsController.php
    - php/appinfo/info.xml
    - php/tests/Unit/ExAppServiceTest.php
    - php/tests/Unit/SettingsControllerTest.php
    - php/l10n/{de,de_DE,en,fr}.{json,js} (nur T96)
decisions:
  - "POST 200 trägt wie GET zones und defaultZone, damit admin.js Antwort und Polling gleich verarbeitet"
  - "window als Nicht-Objekt oder mit fremdem Schlüssel ist field body; fehlende Zeit nennt ihr Feld, fehlende Zone window_zone"
  - "Prüfreihenfolge im Controller: Schlüssel, profile, offline, window, threads; threads holt die Obergrenze erst nach der Ganzzahlprüfung über resources()"
  - "verifyModels hat ein eigenes Zeitbudget von 300 s (sha256 über 4,7 GB)"
  - "ModelsCommand: Zustände waiting, downloading, verifying, disk_full sind kein Fehler (Exit 0), nur die vier aus dem Plan sind Exit 1"
metrics:
  duration: "ca. 60 min"
  completed: 2026-11-18
  tasks: 2
  files: 17
---

# Phase 5 Plan 05: PHP-Routen, Format und occ Summary

PHP-Hälfte des Einstellungswegs: Admin-Routen GET/POST `/admin/resources` ohne lockernde Attribute, strenge Prüfung mit Feldcodes vor dem ExApp-Aufruf, exakte Vertragsprüfung jeder ExApp-Antwort, ein einziger GB-Formatierer mit richtungsabhängiger Rundung und `occ audio_video_search:models [--verify]`.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | ExAppService-Methoden, Controller-Routen, ResourceFormat | e390174 | ExAppService.php, SettingsController.php, ResourceFormat.php, 3 Testdateien, 8 Katalogdateien (T96) |
| 2 | occ audio_video_search:models | f67a2d7 | ModelsCommand.php, info.xml, ModelsCommandTest.php |

## Ergebnis

- Vertrag aus dem Plan wörtlich: GET-Form mit genau zehn Schlüsseln, drei Profile und vier Modelle in fester Reihenfolge, Zeiten nur `^([01]\d|2[0-3]):[0-5]\d$`, Zone nur aus `DateTimeZone::listIdentifiers()`. Fremder Schlüssel, unbekannter Code, negative Zahl, "7:5" ergeben null.
- POST: `{"threads": 0}`, `"2"`, `2.0`, Standard+1 ergeben 400 threads, ohne `saveResources`; Start = Ende window_same; "Mars/Base" window_zone; `{"foo": 1}` und leerer Körper body; "turbo" und "none" profile; "yes", 1, null bei offline offline. 409 profile_locked kommt mit needBytes/availableBytes durch. Logs nennen nur den Feldcode.
- Attribut-Test erweitert: genau vier Routen, keine trägt NoAdminRequired, NoCSRFRequired, PublicPage oder ähnliches (T-05-10).
- ResourceFormat: 4831838208 B Bedarf "4,9 GB" / "4.9 GB" / "4,9 Go"; verfügbar 3149999999 "3,1 GB"; Größen 1617884929 "1,6 GB", 3087284237 "3,1 GB"; Bedarf 1 B "0,1 GB"; 0 "0,0 GB". Test hält, dass Bedarf > verfügbar nie gleich aussieht.
- occ: "parakeet: in_image (0/670000000)" usw., Exit 0/1/2, keine Pfade, Hosts, URLs.

## Verification

- PHP ist lokal nicht installiert: `php -l` und PHPUnit laufen erst in CI (php.yml). OFFEN bis zum nächsten CI-Lauf.
- Statische PHP-Gates (`tests/test_php_gates.py`), `test_trilingual.py`, `test_public_texts.py`, `test_release_archives.py`, `test_ui_assets.py`: 138 passed.
- Voller Python-Lauf: 2453 passed, 18 skipped, 4 xfailed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] T96 schon in diesem Plan in die Kataloge**
- **Found during:** Task 1
- **Issue:** `ResourceFormat` ruft `$l->t('%s GB', ...)`. `test_every_string_the_php_app_translates_is_in_its_catalogues` verlangt jeden übersetzten String in allen Katalogen; die Kataloge schreibt erst Plan 05-06. Ohne Eintrag wäre der Commit rot.
- **Fix:** Nur T96 ("%s GB", fr "%s Go", wörtlich aus 05-UI-SPEC.md, Owner-freigegeben) in de, de_DE, en, fr (.json und .js über scripts/l10n_js.py). Plan 05-06 schreibt die übrigen 59 Texte und prüft T96 mit.
- **Commit:** e390174

## Threat Flags

Keine neue Fläche außerhalb des Bedrohungsmodells: die zwei Routen und der occ-Befehl sind T-05-10 bis T-05-12b.

## Self-Check: PASSED

- Dateien vorhanden: ResourceFormat.php, ModelsCommand.php, ResourceFormatTest.php, ModelsCommandTest.php.
- Commits vorhanden: e390174, f67a2d7.
