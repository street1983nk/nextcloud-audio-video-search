---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 09
subsystem: ci-integration
tags: [deploy-harp, matrix, arm64, seed, playwright, screenshots, wngerman, plat-03, play-01, play-02]
requires:
  - "01-03 (SampleCommand, Provider mit resourceUrl/subline/fileId/path, Gateway)"
  - "01-04 (ci/make-testmedia.sh, Playwright-Grundgerüst, package-lock)"
  - "01-06 (Abspielansicht play.php/play.js mit Bannern und Sprungknopf)"
  - "01-07 (Admin-Sektion mit sieben Zuständen, Debug-Schalter, /admin/state, /admin/sample)"
  - "01-08 (Handshake, companion im /status, /sample-Sperre)"
provides:
  - "deploy-harp.yml: sechs Beine stable33/34/35 x ubuntu-24.04/ubuntu-24.04-arm, beide Apps, Saat, OCS-Rechteprüfung, Range-Probe 206, Playwright in vier Läufen, Log-Prüfung ohne Testdateinamen, Artefakte je Bein"
  - "ci/seed.sh: alice/bob/carol/mallory/dora, Gruppe team, Gruppenordner Team, Freigaben (eine ohne Download), Testmedien, fileids.env, occ audio_video_search:sample je Datei"
  - "Playwright: sieben Projekte (375/768/1280 x hell/dunkel + hc-1280), play.spec.ts und admin.spec.ts mit @disabled/@unreachable/@nodebug/@screenshot"
  - "test_workflows.py: harp_findings + matrix_legs mit Selbsttest je Regel"
  - "Image mit wngerman=20161207-15 und Komposita-Probe im laufenden Container"
affects: [01-10, 01-11, 01-13]
tech-stack:
  added: ["actions/setup-node v7.1.0 (SHA-gepinnt, nur CI)", "Debian-Paket wngerman=20161207-15 (Image)"]
  patterns:
    - "Zustände, die die Instanz umbauen, laufen als eigene Workflow-Schritte mit --grep-Tag; der Hauptlauf schließt sie mit --grep-invert aus"
    - "Hoher Kontrast über eine eigene Prüfnutzerin (dora: admin + team, Theme light-highcontrast), Projekt hc-1280 mit grep @screenshot"
    - "Ein Worker: der Debug-Schalter ist globaler Zustand der einen Instanz"
    - "206 im Browser-Kontext über page.request mit Range-Header gegen die src des Mediums; im Kernweg zusätzlich waitForResponse"
    - "Workflow-Gate als Text-Parser (matrix_legs, steps_of), keine YAML-Bibliothek"
key-files:
  created:
    - ci/seed.sh
    - ci/playwright/admin.spec.ts
    - ci/playwright/helpers.ts
  modified:
    - .github/workflows/deploy-harp.yml
    - ci/playwright/playwright.config.ts
    - ci/playwright/play.spec.ts
    - backend/tests/test_workflows.py
    - backend/tests/test_dockerfile.py
    - backend/Dockerfile
    - .gitignore
decisions:
  - "Alle sechs Beine laufen den identischen Schrittplan; kein Bein toleriert Fehler (fail-fast false, kein continue-on-error)"
  - "Die PHP-App wird vor der ExApp-Registrierung aktiviert, damit der Container beim Start companion ok sieht; der Workflow prüft .companion == ok im /status"
  - "Saat als alice (--user=alice) für alle fünf Dateien, auch für die Gruppenordner-Kopie"
  - "Funktionstests laufen in allen sechs Rasterprojekten; das hc-Projekt macht nur Screenshots"
  - "wngerman kommt in diesem Plan ins Image (Owner 06.11.), weil 01-10 das Dockerfile nicht anfasst und deploy-harp das Image baut"
metrics:
  duration: "ca. 55 min"
  completed: 2026-11-06
  tasks: 3 (+1 Owner-Auftrag wngerman)
  files: 10
---

# Phase 1 Plan 09: Integrationsbeweis auf sechs Beinen mit Playwright-Abnahme Summary

deploy-harp.yml installiert beide Apps auf NC 33/34/35 x amd64/arm64 mit HaRP, sät über `occ audio_video_search:sample`, prüft OCS-Rechte (Besitzerin, Gruppenordner, Freigabe, kein Zugriff), WebDAV-206 und Logs ohne Dateinamen, fährt Playwright über alle drei UI-Flächen mit Screenshot-Raster; dazu ein selbsttestendes Workflow-Gate und die deutsche Wortliste im Image.

## Was gebaut wurde

**Task 1, deploy-harp.yml und ci/seed.sh (1496995)**
- Matrix `include` mit sechs Einträgen, `runs-on: ${{ matrix.runner }}`, Jobname mit Server und Runner, `fail-fast: false`, Timeout 60 min (Schätzung bis zum ersten Lauf).
- Setup: debug an, PHP-App per `mv app-src/php apps/audio_video_search && ./occ app:enable audio_video_search`, danach Image-Build und ExApp-Registrierung wie bisher; `/status` muss `companion == "ok"` melden.
- Testmedien per apt-ffmpeg und `ci/make-testmedia.sh`; `ci/seed.sh` legt Nutzer, Gruppe, Gruppenordner (Store, Fallback Tarball wie Findling), Uploads, zwei Freigaben (locked.webm mit `download=false`), `shareapi_allow_view_without_download=no`, fileIds und Saat an und schaltet `sample_visible` ein.
- OCS-Suche je Leserin mit jq (Form jedes Eintrags: Abspielroute mit `t=42.0`, Subline `0:42 · `, Attribute fileId und path), mallory 0 Einträge; Range-Probe 206 für alice, carol, bob.
- Abschluss: grep auf `tone-90s|broken.webm|locked.webm` in nextcloud.log und Container-Log muss leer sein. Artefakte: Logs plus Playwright-Report, test-results, screenshots, alle `if: always()`.

**Task 2, Playwright (de57aaa)**
- `playwright.config.ts`: Projekte `w375|w768|w1280` x `light|dark` und `hc-1280` (grep @screenshot), ein Worker.
- `play.spec.ts`: Kernweg (aus 01-04, jetzt als alice), Gruppenordner (carol), Freigabe (bob), abgelaufene Sitzung, fremde fileId 404 ohne Namen, Download-Sperre, Format-Banner mit Fokus, Sprungknopf, Seitentitel und kein autoplay, Screenshot `screenshots/play-{projekt}.png`.
- `admin.spec.ts`: ok mit 0.1.0 auf beiden Seiten, Debug-Schalter an/aus/an gegen die OCS-Suche von alice, "Erneut prüfen" mit aria-busy (Antwort per route zurückgehalten) und Fokus, `@disabled`, `@unreachable`, `@nodebug`; Screenshots `admin-{zustand}-{projekt}.png`.
- Workflow: setup-node (SHA), `npm ci --ignore-scripts`, `npx playwright install --with-deps chromium`, Hauptlauf mit `--grep-invert`, dann disable, docker stop/start mit Warten auf `/status`, debug aus.
- `npx playwright test --list`: 100 Tests in 2 Dateien, `--grep @disabled` ergibt 7 (6 Raster + hc).

**Task 3, Workflow-Gate (fc0109b RED, d7ffa9e GREEN)**
- `matrix_legs` liest die include-Einträge als Text, die Menge muss exakt `{stable33..35} x {ubuntu-24.04, ubuntu-24.04-arm}` sein; Regeln für runs-on aus der Matrix, fail-fast false, `app:enable audio_video_search`, `npx playwright test`, `if: always()` je Upload-Schritt.
- 9 neue Tests (11 auf 20), je Regel ein Selbsttest mit manipuliertem Workflow-Text.

**Owner-Auftrag wngerman (0085d0a RED, 37f1ad0 GREEN)**
- `backend/Dockerfile` Laufzeitstufe: `wngerman=20161207-15`, `test -s /usr/share/dict/ngerman`, Lizenztext nach `/usr/local/share/audio_video_search_backend/COPYING.wngerman` (Muster Findling, gleicher Basis-Digest).
- `test_dockerfile.py`: Liste in der Laufzeitstufe gepinnt, Pfad gleich `wordlist.SYSTEM_WORDLIST`, Selbsttest der Stufenerkennung.
- deploy-harp-Schritt "The image carries the German word list and splits compounds": im laufenden Container mehr als 200000 Einträge, `frist` steckt in der Analyse von `Kündigungsfrist`. Lokal mit Ersatzliste geprüft: `['kundig', 'frist']`.

## Verifikation (lokal)

- `bash -n ci/seed.sh` ok; YAML-Parse ok (actionlint nicht installiert).
- Acceptance-greps: 6x `server-version: stable3[345]`, arm-Runner vorhanden, `app:enable audio_video_search`, `Range: bytes=`, `206`, `playwright install --with-deps chromium` genau 1, `upload-artifact` 2, `waitForTimeout` 0, `colorScheme` 4, `@disabled/@unreachable/@nodebug` je vorhanden.
- backend: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 359 passed.
- jq-Formfilter mit Positiv- und Negativbeispiel geprüft.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Gemeinsame Hilfsdatei `ci/playwright/helpers.ts`**
- Nicht in files_modified; Login, OCS-Suche, Position, 206-Probe und Screenshots werden von beiden Specs gebraucht. Commit de57aaa.

**2. [Rule 3 - Blocking] Prüfnutzerin `dora` für hohen Kontrast**
- Das Theme wird je Nutzer gesetzt; damit die anderen Projekte nicht mitkippen, bekommt eine eigene Admin-und-team-Nutzerin das Theme und öffnet die Gruppenordner-Kopie bzw. die Admin-Sektion.

**3. [Rule 2 - Kritisch] `.gitignore` um `ci/fileids.env` und `ci/playwright/screenshots/`**
- Erzeugte CI-Dateien dürfen nicht versehentlich eingecheckt werden. Commit 1496995.

**4. [Rule 2 - Kritisch] companion-Prüfung und Wortlisten-Probe im Workflow**
- `/status` muss `companion == "ok"` melden, sonst würde die Saat mit `companion_missing` scheitern und die Ursache wäre unklar.

**5. Plan-Zuschnitt:** Die Playwright-Workflow-Schritte (Task 2) stehen bereits im Commit von Task 1, weil die Datei in einem Zug neu geschrieben wurde.

**6. Owner-Auftrag wngerman** zusätzlich in diesem Plan (siehe oben), weil Plan 10 das Dockerfile nicht anfasst.

Sonstige Änderung: Admin-Passwort der Wegwerfinstanz von `skeleton-ci-only` auf `avs-ci-admin-2026-11` (alle Passwörter als Job-Variablen, keine Repo-Secrets).

## Offene Punkte für Plan 11 (erster echter Lauf)

- Nichts davon ist gelaufen: Matrix, Saat, Playwright und Wortlisten-Probe brauchen den Owner-Push.
- Risiken: Selektoren der Unified Search im Kernweg; ob die Medienanfrage von Chromium in `waitForResponse` auftaucht (sonst Kernweg auf page.request umstellen); `occ config:app:set ... --value=no --type=boolean`; groupfolders aus dem Store auf stable35 (kein Tarball-Fallback für 35 hinterlegt); Laufzeit gegen 60 min.
- PLAT-03, PLAY-01, PLAY-02 sind vorbereitet, aber erst mit dem grünen CI-Lauf belegt; deshalb hier nicht als erledigt markiert.

## Threat Flags

Keine neuen Flächen außerhalb des Threat-Modells: Artefakte enthalten nur synthetische Medien und Testnutzer der Wegwerfinstanz (T-01-41), Log-Prüfung umgesetzt (T-01-42), alle Actions per SHA gepinnt (T-01-43), mallory in OCS und Playwright (T-01-44), `npm ci --ignore-scripts` (T-01-SC).

## Self-Check: PASSED

- Dateien vorhanden: ci/seed.sh, ci/playwright/admin.spec.ts, ci/playwright/helpers.ts, ci/playwright/play.spec.ts, ci/playwright/playwright.config.ts, .github/workflows/deploy-harp.yml, backend/tests/test_workflows.py, backend/tests/test_dockerfile.py, backend/Dockerfile
- Commits vorhanden: 1496995, de57aaa, fc0109b, d7ffa9e, 0085d0a, 37f1ad0
