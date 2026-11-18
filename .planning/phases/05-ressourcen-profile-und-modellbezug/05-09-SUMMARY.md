---
phase: 05-ressourcen-profile-und-modellbezug
plan: 09
subsystem: php/settings, php/templates, php/js, php/css
tags: [RES-01, RES-05, RES-06, RES-07, PLAT-04, admin, ui, polling]
requires: ["05-05", "05-06"]
provides:
  - "Settings\\Admin::getForm(): fragt ExAppService::resources() einmal je Seitenaufruf, Initial State 'resources' (Vertrag plus zones, defaultZone), Template-Parameter resources und resourceText"
  - "ExAppService::withZones(array $resources, IConfig $config, string $uid): array und ExAppService::defaultZone(IConfig $config, string $uid): string (statisch, die eine Stelle der Zonenregel)"
  - "php/templates/admin.php: Abschnitte #avs-profile, #avs-compute, #avs-models mit allen Zuständen R1, R2, R3, R9, M1 bis M11 vorgerendert"
  - "php/js/admin.js: Sofortspeichern Profil und Offline, Formular Rechenzeit mit Browser-Prüfung, Polling GET admin/resources"
  - "backend/tests/test_admin_phase5_assets.py (23 Tests), php/tests/Unit/AdminSettingsTest.php (19 Testmethoden, 15 Zeilen im Data Provider)"
affects: [05-16, 05-19, 05-22, 05-23]
tech-stack:
  added: []
  patterns:
    - "Sätze mit Platzhaltern als Slots (Private-Use-Zeichen U+E010 bis U+E01F): Zahl oder Wort in einem span mit data-value, Lizenz-ID als Link; das Skript ersetzt nur den Text des span"
    - "Eine render-Funktion in admin.js für die Antwort eines Speicherns und eines Polls"
    - "Rundungsregel in PHP und JS an denselben Zeilen: PHPUnit über ResourceFormat, pytest über die Funktion aus admin.js unter node"
key-files:
  created:
    - backend/tests/test_admin_phase5_assets.py
    - php/tests/Unit/AdminSettingsTest.php
  modified:
    - php/lib/Settings/Admin.php
    - php/templates/admin.php
    - php/js/admin.js
    - php/css/admin.css
    - php/lib/Service/ExAppService.php
    - php/lib/Controller/SettingsController.php
    - backend/tests/test_ui_assets.py
decisions:
  - "Die Zonenregel (zones, defaultZone) liegt statisch in ExAppService; SettingsController und Admin rufen dieselbe Funktion, keine zweite Kopie (Orchestrator-Vorgabe)"
  - "Admin bekommt IL10N als achten Konstruktor-Parameter und formatiert alle Mengen mit ResourceFormat; das Template liest die fertigen Texte, das Skript bekommt Einheit und Dezimalzeichen als data-Attribute"
  - "Je Profil stehen zwei Zeilen vorgerendert (avs-profile-{id}-need frei, avs-profile-{id}-lock gesperrt), eine sichtbar; aria-describedby am Radio nennt die sichtbare"
  - "Angehakt ist die gespeicherte Wahl, ohne gespeicherte Wahl das Profil, mit dem gerechnet wird (chosen, sonst effective)"
  - "availableBytes null wird wie R2 behandelt: alle Profile gesperrt, kein Vorschlag, als Zahl der Bestandsschlüssel 'unknown' (Annahme, Owner-Frage offen)"
  - "Threads gleich Standard wird als null gesendet (kein Wert des Admins), damit der Standard einer späteren CPU-Zahl folgt"
  - "Kein t() im Skript: jedes Wort kommt aus einem vorgerenderten Knoten oder einem data-Attribut"
metrics:
  duration: "ca. 60 min (mit Vorprüfung und Rückfrage)"
  completed: 2026-11-18
  tasks: 2
  files: 9
---

# Phase 5 Plan 09: Admin-Seite Profil, Rechenzeit, Modelle und Lizenzen Summary

Fläche 3 nach 05-UI-SPEC.md: drei Abschnitte unter "Verbindung zum Backend" aus derselben getForm(), mit Vorschlag und Sperrgrund in Zahlen, Rechenzeit mit Browser-Prüfung und einem Knopf, Modellliste mit Herkunft, Lizenz-Links, Größe und elf vorgerenderten Zuständen, Polling alle 5 s als setTimeout-Kette.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Admin.php und Template mit allen Zuständen | 0b462bd | Admin.php, admin.php, admin.css, ExAppService.php, SettingsController.php, AdminSettingsTest.php, test_admin_phase5_assets.py, test_ui_assets.py |
| 2 | admin.js: Speichern, Prüfung, Polling | 11ddd34 | admin.js, test_admin_phase5_assets.py |

## Ergebnis

- Reihenfolge #avs-admin, #avs-profile, #avs-compute, #avs-models; im Profil Banner (R2 role="alert", R3 role="status") vor Vorschlag T37 vor Mindest-RAM T48 vor den Optionen (Checker-FLAG).
- Gesperrte Profile: Radio disabled, Sperrgrund T45 mit Schloss-Icon außerhalb des label, per aria-describedby am Radio; Bedarf auf-, verfügbar abgerundet.
- R9 (resources null oder Ausnahme): ein Warn-Banner T53 in #avs-profile, kein #avs-compute, Modelle nur mit Herkunft und Lizenz; "Weitere Bestandteile" und der Link THIRD-PARTY.md stehen immer.
- Rechenzeit: Threads max = standard, Fenster mit Von, Bis, Zone (Liste aus PHP), Knopf im Markup hidden. Browser-Prüfung in der Reihenfolge der PHP-Route (threads, window_start, window_end, window_same, window_zone); eine 400-Antwort mit Feldcode landet auf derselben Fehlerzeile.
- Modelle: je Modell elf Zustandszeilen, eine sichtbar; progress nur bei downloading; #avs-models-live sagt nur einen Zustandswechsel an (Modellname plus Satz); das Polling ruft nie focus().
- Polling: POLL_EVERY_MS = 5000, POLL_FAILURES = 3, nur bei waiting, downloading, verifying und sichtbarer Seite, der nächste Timer erst nach der Antwort, danach Banner T95. Eine Poll-Antwort, die während eines Speicherns eintrifft, wird nicht gezeichnet.
- CSS nach der Tabelle der UI-SPEC; `.avs-models__others` mit `* 6` (24 px, Checker-FLAG); der 28-px-Einzug der Hinweiszeilen steht mit Begründung und Prüfpunkt im Kommentar.

## Verification

Lokal belegt (Zahlen des letzten Laufs vor dem zweiten Code-Commit):

- `uv run ruff check .`: All checks passed. `uv run ruff format --check .`: 149 files already formatted.
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings. `uv run vulture`: ohne Befund.
- `uv run pytest -q`: 2725 passed, 20 skipped, 4 xfailed (vorher 2702; plus 23 in test_admin_phase5_assets.py).
- `tests/test_admin_phase5_assets.py tests/test_ui_assets.py tests/test_php_gates.py tests/test_trilingual.py tests/test_l10n_phase5.py tests/test_public_texts.py`: 160 passed.
- `scripts/l10n_js.py --check`: grün. `node --check php/js/admin.js`: grün.
- Abnahmekriterien: `id="avs-profile"|"avs-compute"|"avs-models"` 3 Zeilen; THIRD-PARTY.md 3 Treffer; `/nc_app_|APP_PERSISTENT_STORAGE|/models/` 0; `innerHTML|insertAdjacentHTML` 0; `setInterval` 0.
- Stand von Commit 0b462bd (admin.js noch alt) über `git archive` in einen leeren Ordner ausgepackt und dort geprüft: 155 passed; `test_public_texts.py::test_no_tracked_text_carries_a_dash_or_an_emoji` scheitert dort nur, weil der Ordner kein Git-Repository ist (`git ls-files` Exit 128), im Repo grün.
- Negativkontrollen: 24 Eingriffe, jeder einzeln (Datei ändern, benannter Test rot, bytegleich zurück, sha256 gleich, Test wieder grün): Radio ohne Server-Klasse, umbenannte ID, Abschnitt weg, Reihenfolge im Profil, fremde Adresse, fehlender Modellzustand im Template, nicht übersetzter Text, ungenutzter freigegebener Text, 20-px-Einzug, Hex-Farbe, zweite Abfrage des Containers, zweite Kopie der Zonenregel, `radio` aus der Erlaubtliste genommen, fremde Klasse `switch` im Template, Polling jede Sekunde, setInterval, Polling auf verborgener Seite, Schwelle 300, innerHTML, Bedarf im Skript abgerundet, Größengrenze um eins verschoben, PHP-Regel geändert, PHPUnit-Zeile geändert, Modellliste im Skript gekürzt. 24 von 24 rot und wieder grün.
- Rundung PHP gegen JS: 15 feste Zeilen (0, 1 Byte, genau auf der Grenze, eins darunter, eins darüber, je Bedeutung; dazu 1617884929 und 3087284237) plus 45 Werte um drei Grenzen, französisch mit "Go" und Komma; die Funktion aus admin.js lief unter node 22.21.0. Fünf absichtlich falsche Regeln ergeben andere Zeilen.
- l10n nachgezählt: `test_every_text_of_the_page_stands_in_all_four_catalogues` findet mindestens 75 übersetzte Literale in admin.php, Admin.php und ResourceFormat.php, jedes in de, de_DE, en, fr; alle 60 freigegebenen Texte T36 bis T96 werden auf der Seite benutzt; lange Sätze haben in de, de_DE und fr einen eigenen Text.

Beweis in CI offen (lokal kein PHP, kein Browser):

- `php -l` auf Admin.php, admin.php, ExAppService.php, SettingsController.php, AdminSettingsTest.php. Lokal nur eine Klammerbilanz per Skript (kein Parser).
- PHPUnit: AdminSettingsTest (neu, rendert das Template über TemplateResponse) und der unveränderte SettingsControllerTest gegen die umgestellte Zonenregel (drei Zonen-Tests, POST-Antwort mit zones).
- DI: Nextcloud muss IL10N in den Konstruktor von Settings\Admin einsetzen (Muster Settings\Section, dort belegt).
- Alles Sichtbare: Gestalt von input.radio, input[type=time], select, progress in NC 33 bis 35, Bündigkeit des 28-px-Einzugs, Hell/Dunkel/Hochkontrast, 375/768/1280 px, Kontrast-Gate, axe, Tastaturweg (Pläne 05-19 und 05-23).
- Verhalten von admin.js im Browser: Speichern, 400/409, Fokus, Live-Region, Polling-Takt, Stopp nach drei Fehlern, Lesen des Initial State aus `#initial-state-audio_video_search-resources`. Lokal ist nur die Rundungsfunktion wirklich gelaufen, der Rest ist statisch geprüft.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking, Orchestrator-Entscheid] `radio` in ALLOWED_SERVER_CLASSES**
- **Found during:** Vorprüfung zu Task 1 (angehalten, berichtet, Entscheid abgewartet)
- **Issue:** 05-UI-SPEC.md nennt `input.radio` (Zeilen 33, 103, 161, 200, 201); das Klassen-Gate in `backend/tests/test_ui_assets.py` kannte die Server-Klasse nicht. Datei außerhalb von `files_modified`.
- **Fix:** nur `"radio"` ergänzt, im Selbsttest eine Positivzeile und eine Gegenzeile (`radio-big`, `switch` bleiben Befund). Negativkontrollen: ohne `radio` wird das Gate am Template rot, mit `class="radio switch"` ebenfalls.
- **Commit:** 0b462bd

**2. [Orchestrator-Vorgabe] Zonenregel an einer Stelle**
- **Issue:** Der Plan verlangt "gleiche Hilfe wie der Controller"; dort war sie privat. Eine Kopie in Admin.php war nicht erwünscht.
- **Fix:** `ExAppService::withZones()` und `ExAppService::defaultZone()` (public static, `use OCP\IConfig`); `SettingsController::withZones()` ruft nur noch dorthin, `defaultZone()` im Controller entfällt. Aufrufer per Grep: SettingsController Zeilen 133, 200, 255; Admin.php Zeile 128; sonst keiner. Statischer Test: `\DateTimeZone::listIdentifiers()` und `'default_timezone'` stehen unter php/lib nur in ExAppService.php. Dateien außerhalb von `files_modified`: ExAppService.php, SettingsController.php.
- **Commit:** 0b462bd

**3. [Rule 2] Zwei IDs je Profilzeile statt einer**
- **Issue:** Die UI-SPEC gibt Bedarf und Sperrgrund dieselbe ID `avs-profile-{id}-need` ("EINES von"). Weil alle Zustände vorgerendert sein müssen und das Skript kein Markup baut, stehen beide Zeilen im DOM.
- **Fix:** `-need` (T44) und `-lock` (T45), eine davon hidden; aria-describedby am Radio nennt die sichtbare (ein verborgener Knoten würde sonst mitgelesen). Gleiches gilt für aria-describedby am fieldset, das in R2 entfällt.

**4. Klassen über die CSS-Tabelle hinaus**
- `avs-res__choice` (Zeile aus Radio und Label, trägt die Mindesthöhe; die Touch-Regel hängt an ihr statt an `.avs-res__option`, weil die Option auch die Hinweiszeilen enthält), `avs-res__icon`, `avs-res__number`, `avs-res__banner`, `avs-res__form`, `avs-models__line` mit `--muted`, `avs-models__icon--success|warning|error`, `avs-models__more`, `avs-models__all`. Alle mit Präfix, nur Server-Variablen.

**5. Reihenfolge der Arbeit**
- admin.js war beim ersten Commit schon geschrieben, aber nicht gestaged. Für Commit 0b462bd wurde die Testdatei auf die Teile gekürzt, die das alte Skript nicht lesen; der Stand wurde über `git archive` getrennt geprüft. Commit 11ddd34 bringt die volle Testdatei.

### Annahmen (nicht aus Plan oder UI-SPEC ableitbar)

- `availableBytes === null`: wie R2 (alles gesperrt, kein Vorschlag), Zahl "unbekannt" über den Bestandsschlüssel `unknown`. Kein neuer Text.
- Angehaktes Radio ohne gespeicherte Wahl: das wirksame Profil. Die UI-SPEC sagt nur "checked wenn chosen".
- T79 ohne wirksames Profil (effective none): Name der gespeicherten Wahl, sonst "unbekannt".
- Threads gleich Standard wird als `null` gesendet.
- 409 profile_locked trägt nur needBytes und availableBytes: das Skript setzt daraus die Sperre des gewählten Profils und die verfügbare Menge im letzten bekannten Stand und zeichnet neu.
- T56 und T57 (CPU-Zahl, Höchstwert im Satz) werden nach dem Laden nicht neu geschrieben, weil `%d` keinen Slot erlaubt; `max` am Feld und die Prüfung folgen der Antwort.
- Nach dem Polling-Stopp startet nur ein Neuladen das Polling neu (UI-SPEC), auch ein späteres Speichern nicht.
- In R2 kann eine Sperrzeile einen Bedarf zeigen, der unter der verfügbaren Menge liegt (Profil passt für sich, App insgesamt unter dem Minimum); das Banner T50 nennt den Grund.

## Known Stubs

Keine. Die Seite zeigt, was `GET /resources` der ExApp liefert; diese Route baut Plan 05-16. Bis dahin antwortet die ExApp nicht im Vertrag und die Seite steht in R9.

## Threat Flags

Keine neue Fläche außerhalb des Bedrohungsmodells. T-05-19 (kein Markup aus Strings, p() im Template, Test), T-05-19b (nur feste Adressen, Test auf Pfadwörter und fremde Adressen), T-05-19c (5-s-Kette, sichtbar, Stopp nach 3) sind umgesetzt und statisch belegt; T-05-19d bleibt bei PHP 400/409 (05-05) und ExApp 409 (05-16), disabled ist nur Komfort.

## Offene Fragen an den Owner

1. `availableBytes` null: reicht "unbekannt" im Satz T50/T45, oder soll es einen eigenen Text geben?
2. Soll ohne gespeicherte Wahl das wirksame Profil angehakt sein (so gebaut) oder keines?
3. Threads gleich Standard als "kein Wert des Admins" speichern (so gebaut) oder als feste Zahl?
4. Requirements RES-01, RES-05, RES-06, RES-07, PLAT-04 stehen im Kopf dieses Plans, sind aber erst mit 05-16 (ExApp-Route), 05-19 und 05-23 erfüllt; nicht abgehakt.

## Self-Check: PASSED

- Dateien vorhanden: backend/tests/test_admin_phase5_assets.py, php/tests/Unit/AdminSettingsTest.php, 05-09-SUMMARY.md.
- Commits vorhanden: 0b462bd, 11ddd34 (Autor street1983nk <k.cherif@outlook.de>, nur lokal).
