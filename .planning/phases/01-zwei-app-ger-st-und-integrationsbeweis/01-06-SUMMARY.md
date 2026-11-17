---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 06
subsystem: php-ui
tags: [playback, webdav, template, csp, a11y, ui-spec]
requires:
  - "01-03 (ExAppService::excerpt, searchAllowed, FileAccess, ReaderContext)"
  - "01-04 (alle Texte der Abspielansicht in php/l10n)"
  - "01-12 (Escapes beim Kopieren prüfen, test_php_gates Regeln 1 bis 9)"
provides:
  - "Route GET /apps/audio_video_search/play/{fileId}?t= (audio_video_search.page.play), Zustände ready, not_media, download_blocked, unavailable (404)"
  - "PageController::startMs/seconds/isoDuration als öffentliche statische Helfer"
  - "php/templates/play.php, php/js/play.js, php/css/play.css"
  - "backend/tests/test_ui_assets.py: lokales Asset-Gate für alle Templates, JS und CSS der PHP-App"
affects: [01-07, 01-09, 01-11]
tech-stack:
  added: []
  patterns:
    - "Medium zeigt direkt auf /remote.php/dav/files/{uid}/{pfad}, rawurlencode je Segment und für die UID, kein eigener Stream-Controller"
    - "Startzeit aus ?t= auf Ziffern gerechnet (kein Float), Muster ^\\d{1,5}(\\.\\d{1,3})?$, 0 bis 86400 s, sonst still 0"
    - "Download-Sperre wie der Server: ISharedStorage::getShare()->getAttributes() permissions/download plus core shareapi_allow_view_without_download; Rest per HEAD 403 in play.js"
    - "Alle Banner serverseitig gerendert, JS schaltet nur hidden und Fokus"
    - "Dokumenttitel über TemplateResponse-Parameter pageTitle (wie dashboard/settings in stable33)"
key-files:
  created:
    - php/lib/Controller/PageController.php
    - php/tests/Unit/PlayControllerTest.php
    - php/templates/play.php
    - php/js/play.js
    - php/css/play.css
    - backend/tests/test_ui_assets.py
  modified: []
decisions:
  - "Download-Sperre über die öffentliche Schnittstelle OCP\\Files\\Storage\\ISharedStorage statt OCA\\Files_Sharing\\SharedStorage (gleiches Muster wie ViewOnlyPlugin des Servers)"
  - "Controller liefert src (ohne Fragment, für HEAD und Download) und mediaSrc (mit #t= nur bei t > 0)"
  - "Sprungknopf springt auf die Server-Zeitmarke (die er im Text nennt); #t= der Seitenadresse gilt für den Seek beim Laden"
  - "excerptState skipped für Zustände ohne Medium; Drift auf Vorrat oder stummer Container = unavailable ohne Aufruf"
metrics:
  duration: "ca. 15 min"
  completed: 2026-11-06
  tasks: 2
  files: 6
---

# Phase 1 Plan 06: Abspielansicht play/{fileId} Summary

Eigene Route `play/{fileId}` mit Rechte-Recheck über `ReaderContext::actAs` und `FileAccess::readableFile`, natives `<video>`/`<audio>` auf die kodierte WebDAV-Adresse mit Media Fragment `#t=`, Ausschnitt vom Container und alle Zustände der UI-SPEC, ohne Bundler, ohne Inline-Skripte.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 (RED) | Tests der Abspielroute | 71e8904 | php/tests/Unit/PlayControllerTest.php |
| 1 (GREEN) | PageController::play | 0f31784 | php/lib/Controller/PageController.php |
| 2 | Template, JS, CSS, Asset-Gate | 376434e | php/templates/play.php, php/js/play.js, php/css/play.css, backend/tests/test_ui_assets.py |

## Was gebaut wurde

- **PageController::play**: `NoAdminRequired`, `NoCSRFRequired`, `FrontpageRoute(GET, '/play/{fileId}', fileId \d+)`, keine Freigabe ohne Sitzung. Nicht lesbar, fremd, fehlend und Ausnahme beim Auflösen ergeben dieselbe 404-Seite mit `h2` "Playback", ohne Dateiname und ohne Pfad in den Parametern. `text/*` und andere Typen: `not_media` (200). Freigabe mit gesperrtem Download und abgeschaltetem view-without-download: `download_blocked` (200, kein src). Logs nur mit `fileId` und Ausnahmeklasse.
- **play.php**: Reihenfolge wie UI-SPEC (h2, Startzeile mit `<time datetime>`, `#avs-play-state`, Medium, Aktionszeile, Ausschnitt-Block). Sieben Banner (unavailable, not_media, download_blocked, moved, format, network, other) mit MDI-Icon 20 px, Titel 700, Satz 400; Fehler- und vom JS eingeblendete Banner mit `role="alert" tabindex="-1"`. "Datei herunterladen" nur bei erlaubtem Download.
- **play.js**: `#t=` hat Vorrang vor `data-start`, Seek nach `loadedmetadata` (oder sofort bei `readyState >= 1`), Sprungknopf ohne Abspielen, Fokus auf das Medium; bei `error` ein `HEAD` auf dieselbe Origin: 403 download_blocked, 404 moved, sonst MediaError 2 network, 3/4 format, Rest other; Medium wird ausgeblendet, Banner fokussiert.
- **play.css**: nur Server-Variablen, Lesespalte 960 px, Rand md/lg, oberer Abstand xl ab 768 px, Video `max-height: 70vh; object-fit: contain`, Statuspaare, `tabular-nums`, `overflow-wrap: anywhere`, 44 px bei `pointer: coarse`, `[hidden]` gewinnt gegen eigene display-Werte.
- **test_ui_assets.py**: 19 Tests (Untergrenze, 11 Regeln, Vertrag der Abspielseite, 7 Selbsttests).

## Verifikation

- `uv run pytest -q` (backend): 322 passed.
- `ruff check`, `ruff format --check`, `pyright` (latest), `vulture`: grün.
- Akzeptanz-Greps beider Tasks erfüllt (Route 1x, PublicPage 0, rawurlencode 2, STATUS_NOT_FOUND 1, shareapi-Schlüssel 1, 16 Testmethoden; avs-media 1, autoplay 0, script 0, loadedmetadata 1, HEAD 1, innerHTML 0, 70vh 1, pointer: coarse 1, 19 def test_).
- Kein Nicht-ASCII-Zeichen in den neuen Dateien (Escapes geprüft: `\OCP\...`, `'\d+'`, `"\u{E000}"` erhalten).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2] Zweite Quelle src/mediaSrc statt einer**
- Der Plan nennt nur `src`; für HEAD und Download braucht es die Adresse ohne Fragment. Controller liefert beide, Template nutzt `mediaSrc` am Medium.

**2. [Rule 2] Asset-Gate strenger als verlangt**
- Zusätzlich verboten: `outerHTML`, `insertAdjacentHTML`, `document.write`, `new Function`, `print_unescaped`, `print(`, `rgba/hsla`, `outline: 0`, `text-shadow`.

**3. [Rule 1] CSS-Kommentar löste das eigene Gate aus**
- Der Kopfkommentar nannte die verbotenen Wörter wörtlich; umformuliert vor dem Commit.

## Offene Punkte / Nachweis

- **phpunit** (`PlayControllerTest`, 16 Methoden inkl. Datenprovider) läuft nur in CI; lokal kein PHP. Erster CI-Lauf nach Owner-Freigabe zum Push.
- **PLAY-01, PLAY-02 nicht als erledigt markiert**: Umsetzung steht, der Beleg (Playwright gegen NC 33 bis 35, 3 Breiten, hell/dunkel, Seek-Toleranz 0,5 s, Download-Sperre mit `shareapi_allow_view_without_download` aus) folgt in Plan 09; vorher kein Nachweis im Sinne der Owner-Regel.
- MDI-Pfaddaten (Apache-2.0) stehen im Template mit Quellenvermerk; ein THIRD-PARTY-Eintrag bzw. REUSE-Angabe gehört in den Release-Plan (11).
- Annahme aus RESEARCH (A3, DAV-Pfadschema für Gruppenordner und empfangene Freigaben) erst im E2E belegt.

## Threat Flags

Keine neue Fläche außerhalb des Threat-Modells (T-01-25 bis T-01-31 umgesetzt: Recheck, rawurlencode, p() überall, t-Muster, kein eigener Stream, keine Inline-Skripte, kein PublicPage).

## Self-Check: PASSED
