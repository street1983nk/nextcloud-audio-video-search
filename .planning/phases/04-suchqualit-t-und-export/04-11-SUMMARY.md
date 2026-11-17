---
phase: 04-suchqualit-t-und-export
plan: 11
subsystem: php-abspielseite
tags: [export, sidecar, vtt, track, exp-01, exp-03, exp-04, srch-04, ui]
requires:
  - "04-03 (freigegebene Texte T13 bis T35, Icon-Pfade, a.button-Befund)"
  - "04-10 (DownloadPolicy::decide, ExAppService::exportMeta, ExportController::downloadName, Routen export.download und export.track)"
  - "04-12 (Route export.sidecar mit Antworten 201/409/403/400/404/503/429)"
provides:
  - "PageController::exportState: available|partial|blocked|none, Datenvertrag exportUrls, sidecarAllowed/Name/Url, trackUrl/Lang/Label"
  - "section.avs-export (X1 bis X3) unter dem Ausschnitt, X4 ohne Abschnitt; Banner E1 bis E7 vorgerendert"
  - "<track kind=subtitles> ohne default am Video"
  - "play.js: Ablage-POST mit requesttoken und Banner-Auswahl"
affects: [04-13, 04-14, 04-16, 04-17]
tech-stack:
  added: []
  patterns:
    - "Ein decide-Aufruf je Seite: Wiedergabe liest fail open, Export fail closed"
    - "Ausschluss-Befund verlässt excerpt() als 'excluded', exportState nutzt ihn (einmal gefragt)"
    - "Namensplatz per Platzhalterzeichen U+E000 in T15/T20/T21/T22b, play.js füllt span.avs-export__name nur per textContent"
key-files:
  created: []
  modified:
    - php/lib/Controller/PageController.php
    - php/tests/Unit/PlayControllerTest.php
    - php/templates/play.php
    - php/css/play.css
    - php/js/play.js
    - backend/tests/test_ui_assets.py
decisions:
  - "Sperre vor Ausschluss in exportState: BLOCKED ist X3 auch für ausgeschlossene Nutzer und Dateien (T-04-45a); UNKNOWN ist X4"
  - "sidecarAllowed wird nur in X1/X2 gefragt (isCreatable als Nutzer, Ausnahme = false, Log nur fileId und class), damit X4 byte-gleich bleibt"
  - "Zielname über 255 Bytes: sidecarName leer, die Seite zeigt T20b, der Klick endet in E5"
  - "Sidecar-Banner über eigene present()-Funktion statt show(): show() verbirgt Medium und Sprung-Knopf"
metrics:
  duration: "ca. 75 min"
  completed: 2026-11-16
---

# Phase 4 Plan 11: Abspielseite mit Untertitel-Entwurf, Spur und Ablage Summary

Die Abspielseite zeigt unter dem Ausschnitt den Abschnitt "Untertitel-Entwurf" mit SRT/VTT/TXT als echten Links, dem Ablage-Knopf (Ergebnis-Banner E1 bis E7) und hängt an Videos eine ausgeschaltete Untertitel-Spur; bei Download-Sperre steht nur T24, ohne Transkript oder bei Ausschluss fehlt der Abschnitt byte-gleich.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | Export-Zustand im PageController | ef9061e |
| 2 | Abschnitt Untertitel-Entwurf, Spur und Banner in Template und CSS | 8614e5a |
| 3 | Ablage-Knopf in play.js | eebab66 |

## Ergebnisse

- `PageController`: Konstanten `EXPORT_AVAILABLE/PARTIAL/BLOCKED/NONE`; `play()` ruft `DownloadPolicy::decide` einmal (Wiedergabe wie bisher `!== BLOCKED`), `exportState()` wertet BLOCKED vor `$excluded` aus, dann UNKNOWN, Ausschluss, `searchAllowed`, `exportMeta`. URLs nur über `linkToRoute` (`export.download` je Format, `export.track`, `export.sidecar`). `exportParams()` liefert für jeden Nicht-X1/X2-Fall dieselbe Schlüsselmenge mit leeren Werten, auch `unavailable()`. Spurname T31 mit T32 bis T34.
- `play.php`: Parameter defensiv gelesen (`exportState` aus geschlossener Liste, X1/X2 ohne alle drei URLs fällt auf X4); Icons `download`, `file-plus`, `check-circle-outline` mit den Pfaden aus 04-UI-SPEC; `<track>` nur bei Video und X1/X2; `section.avs-export` mit h3 T13, X3 nur T24, X1/X2 mit T14, T15 + `<time>`, Gruppe der drei Links (Reihenfolge fest), Ablage-Block T20/T20b + verborgenem Knopf + sieben Bannern oder T23.
- `play.css`: Regeln exakt laut Tabelle "CSS (neu)", `.avs-export__download`/`.avs-export__save` in der 44-px-Regel bei `pointer: coarse`. Keine neue hidden-Regel nötig: `#app-content.avs-play [hidden]` (mit ID, Gate-Regel 11) deckt die neuen Elemente. Kein Ersatzstil für `a.button` (Befund 04-03).
- `play.js`: eigene IIFE vor dem Medien-Teil; Klick verbirgt alte Banner, setzt `disabled` + `aria-busy`, POST mit `requesttoken`, Abbildung 201/409/403 not_writable/403 blocked/400 name_too_long/429/sonst auf E1 bis E7, Name nur bei `/^[^\/\\]{1,255}$/` und nur per `textContent`; E1 Fokus zurück auf den Knopf, sonst Fokus auf den Banner.
- Tests: PHPUnit (CI) mit den zehn Behavior-Fällen plus Render-Fällen (X1 Video mit drei Links, Knopf, Spur und sieben Bannern; Audio ohne Spur; X3 ohne jede Export-Adresse; X4 ausgeschlossen = unbekannt byte-gleich mit Positivkontrolle). `test_ui_assets.py`: `test_the_export_section_follows_the_ui_spec`, `test_the_sidecar_button_posts_with_the_token_and_shows_one_banner`, Selbsttest `test_self_export_rules_find_the_accent`.

## Verifikation

- Volle Backend-Suite: 2325 passed, 15 skipped, 4 xfailed (Stand vorher 2322; drei neue Tests). Beim Lauf vor dem Task-2-Commit schlug ein Test einmal fehl (1 failed, 2323 passed; Name wegen gekürzter Ausgabe nicht erfasst), der Wiederholungslauf war grün (Flake, wie erlaubt einmal wiederholt).
- ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture grün; `test_ui_assets`, `test_php_gates`, `test_trilingual`, `test_public_texts` grün.
- `node --check php/js/play.js` grün; eine Node-Probe mit DOM-Attrappe (nur Scratchpad, nicht im Repo) bestätigt alle 14 Abbildungsfälle inkl. Schrägstrich, Backslash, 256 Zeichen, fehlendem Namen, fremdem reason, Netzfehler und 429 mit HTML-Antwort, dazu Fokusregel und POST mit Token.
- Grep-Prüfungen des Plans: `EXPORT_BLOCKED`, `audio_video_search.export.sidecar`, `audio_video_search.export.track` im Controller; `avs-export__download`, `kind="subtitles"`, kein `<track ... default`; `grep -c "avs-sidecar-e[1-7]" php/templates/play.php` = 7; kein `color-primary` in den neuen Regeln.
- PHPUnit und `php -l` laufen erst in CI (kein lokales PHP). Keine neue OCP-Signatur: `Node::getParent`, `Folder::isCreatable`, `IURLGenerator::linkToRoute` sind in 04-12 gegen stable34 belegt.

## Deviations from Plan

1. **[Rule 3] Server-Klasse `button` in `ALLOWED_SERVER_CLASSES`:** Das Klassen-Gate kannte nur `section`, `primary` usw.; 04-UI-SPEC verlangt `<a class="button">`. Ergänzt in `test_ui_assets.py` (Commit 8614e5a).
2. **[Rule 3] Vertragstest Phase 3 angepasst:** `template.count('role="alert" tabindex="-1"') == 1` wurde zu `== 2` (eine Schleife für die Seiten-Banner, eine für E2 bis E7), mit Kommentar (Commit 8614e5a).
3. **Banner E2 bis E7 als Schleife:** Die IDs stehen als Schlüssel der Liste `$sidecarErrors` im Template-Kopf, die Schleife im Abschnitt rendert sie; `grep -c` ergibt 7, der neue Test prüft beides.
4. **present() statt show():** Der Plan nennt das bestehende `show()` für die Fehler-Banner. `show()` verbirgt aber Medium und Sprung-Knopf und sucht nur `avs-banner-*`; die Ablage nutzt deshalb eine eigene Funktion mit demselben Muster (hidden aus, Fokus auf den Banner).
5. **[Rule 2] Zusätzliche Render-Tests in PlayControllerTest** (CI), damit X3 und X4 nicht nur über Parameter, sondern über das gerenderte HTML geprüft werden (T-04-44, T-04-45).

## Prozessvermerk

Ein versehentlicher Aufruf `python -` (leerer Heredoc, Regelverstoß) blieb am Windows-Store-Stub hängen und läuft als Hintergrundprozess (WindowsApps\python.exe, PID 1990 in Git-Bash); das Beenden wurde vom Berechtigungssystem abgelehnt. Er hat nichts geschrieben und kann im Task-Manager beendet werden.

## Fehlende Texte

Keine. Alle sichtbaren Texte sind Bestands- oder freigegebene Schlüssel T13 bis T35 (de, de_DE, en, fr); kein neuer Katalogschlüssel.

## Known Stubs

Keine.

## Threat Flags

Keine neuen Flächen: Abschnitt, Spur und Ablage-Knopf nutzen nur die Routen aus 04-10/04-12 (T-04-44 bis T-04-48 umgesetzt: X3 ohne URLs im DOM, X4 byte-gleich, decide vor `$excluded`, p()/textContent mit Namensmuster, requesttoken, Spurname mit "Untertitel-Entwurf" ohne default).

## Self-Check: PASSED

- FOUND: php/lib/Controller/PageController.php, php/templates/play.php, php/css/play.css, php/js/play.js, php/tests/Unit/PlayControllerTest.php, backend/tests/test_ui_assets.py
- FOUND: ef9061e, 8614e5a, eebab66
