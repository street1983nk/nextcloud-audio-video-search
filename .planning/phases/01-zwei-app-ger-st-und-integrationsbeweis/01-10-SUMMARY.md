---
phase: 01-zwei-app-ger-st-und-integrationsbeweis
plan: 10
subsystem: ci-release
tags: [lockstep, upgrade, drift, release, store, appapi, harp]
requires:
  - phase: 01-09
    provides: deploy-harp sechs Beine, Saat, Playwright-Specs
provides:
  - Job upgrade in deploy-harp.yml (0.0.1 nach 0.1.0, occ upgrade, app_api:app:update)
  - Drift-Schritte 1 bis 4 im Hauptjob (version_drift, version_patch_differs, backend_missing, companion_missing)
  - ci/redeploy.sh, ci/admin-state.sh
  - zwei Store-Archive mit eigener Signatur und eigener Zertifikats-Pin
affects: [01-11]
tech-stack:
  added: []
  patterns:
    - "Drift-Versionen werden aus der PHP-info.xml abgeleitet (Minor+1, Patch+1), nicht fest verdrahtet"
    - "Admin-Zustand per App-Passwort plus OCS-APIRequest, Fallback Login-Formular (Findling-Muster)"
    - "Upgrade-Beweis vergleicht Inode von state.db und CreatedAt des Volumes vorher und nachher"
key-files:
  created:
    - ci/redeploy.sh
    - ci/admin-state.sh
    - backend/tests/test_release_archives.py
  modified:
    - .github/workflows/deploy-harp.yml
    - .github/workflows/release.yml
    - .github/workflows/docker.yml
    - .github/workflows/store-submit.yml
    - .github/workflows/python.yml
    - scripts/release/store-archive.sh
    - ci/playwright/admin.spec.ts
    - backend/tests/test_workflows.py
decisions:
  - "A5 am Quelltext belegt: app_api:app:update (stable33 bis 35) entfernt den Container mit remove_data=false, HaRP löscht das Volume nur bei remove_data und nutzt ein vorhandenes weiter; der Job upgrade beweist es im Lauf"
  - "occ upgrade führt das App-Update aus, weil OC_Util::needUpgrade bei gleicher Serverversion auch aktivierte Apps mit neuerem Code prüft; Exit 0 oder 3 gilt, installed_version muss aber auf die neue Version springen"
  - "PHP-App-Archiv wird wie in Findling zusätzlich per occ integrity:sign-app code-signiert (signature.json im Archiv)"
  - "Backend-Pin bleibt pending-certificate, PR 1417 ist offen; der Backend-Teil von release.yml bricht mit dem vorgegebenen Satz ab, nachdem die PHP-App gebaut und geprüft ist"
  - "store-submit.yml als Matrix mit max-parallel 1 und fail-fast: beide Apps nacheinander, Schlüssel je App über secrets[matrix.key]"
metrics:
  duration: 95 min
  completed: 2026-11-06
  tasks: 2
  files: 11
---

# Phase 1 Plan 10: Lockstep im Lebenszyklus Summary

Upgrade-Beweis beider Apps von einer synthetischen 0.0.1 auf 0.1.0 (occ upgrade, app_api:app:update mit Volume-, Inode- und Trefferabgleich), Drift-Schritte in beide Richtungen im echten HaRP-Lauf und zwei signierte Store-Archive mit getrennten Zertifikats-Pins, alles durch Gates mit Gegenproben abgesichert.

## Was gebaut wurde

### Task 1: Upgrade-Beweis und Drift (Commit 7a8d3df)

- **Job `upgrade`** in `deploy-harp.yml` (stable33/34/35 auf ubuntu-24.04, stable35 auf ubuntu-24.04-arm): `prev/` mit 0.0.1 in beiden info.xml, Image-Tag, `pyproject.toml` und dem Projekteintrag in `uv.lock` (jede Ersetzung gezählt); beide Images ins lokale Registry; 0.0.1 installieren, `ci/seed.sh`, Ausgangslage festhalten (`/status` appVersion 0.0.1, schemaVersion 1, companion ok, sampleCount; Admin-Zustand ok; Treffer-fileIds; Inode von `state.db`; CreatedAt des Volumes). Dann PHP-Ordner tauschen plus `./occ upgrade` (installed_version muss 0.1.0 sein) und `./occ app_api:app:update audio_video_search_backend --info-xml ... --wait-finish`. Danach: appVersion 0.1.0, schemaVersion 1, gleicher sampleCount, companion ok, gleiche Inode, gleiches Volume, Admin-Zustand ok mit 0.1.0/0.1.0, identische Trefferliste (`cmp`).
- **Drift im Hauptjob** nach den Playwright-Schritten: Drift-Versionen aus der PHP-info.xml abgeleitet; Baseline ok (Debug wieder an); Drift 1 (Minor+1) `version_drift`, beide Versionen, Suche HTTP 200 und leer, Playwright `@drift`; Drift 2 (Patch+1) `version_patch_differs`, Testtreffer da, Playwright `@patch`; Drift 3 unregister ohne Datenflag, `backend_missing`, Suche leer, Playwright `@missing`; Rückkehr zu ok mit Treffern; Drift 4 `occ app:disable audio_video_search`, `/status` bis 90 s auf `companion == "missing"`, signierter `/sample` über HaRP liefert `{"error": "companion_missing"}`, danach `app:enable` und zurück zu `companion == "ok"` und Zustand ok.
- **`ci/redeploy.sh <version>`**: Image unter der Version nachtaggen, info.xml-Kopie mit Version und Image-Tag (genau ein Treffer je Element), vorhandene Registrierung ohne Datenflag abmelden, neu registrieren, `APP_VERSION` im Container und `appVersion` in `/status` prüfen.
- **`ci/admin-state.sh <out.json>`**: `GET /apps/audio_video_search/admin/state` per App-Passwort plus `OCS-APIRequest`, Fallback Login-Formular.
- **`admin.spec.ts`**: drei Tests `@drift @screenshot`, `@patch @screenshot`, `@missing @screenshot`; Hauptlauf schließt alle sechs Umgebungs-Tags aus. `--list`: 121 Tests (vorher 100), 21 Zeilen mit den neuen Tags.
- **Gate** `test_workflows.py::lifecycle_findings` mit fünf Gegenproben (Job fehlt, Update/occ upgrade fehlt, Vergleich fehlt oder rm-data, Drift-Schritt ohne Zustand oder fehlend, Hauptlauf nimmt Drift-Tests mit). shellcheck in `python.yml` deckt die beiden neuen Skripte ab.

### Task 2: Zwei Store-Archive (Commits b21c4d6 RED, f06af75 GREEN)

- `scripts/release/store-archive.sh`: `stage-companion` (Einschlussliste `appinfo lib templates js css img l10n` aus `php/` plus `LICENSE`, `CHANGELOG.md`, `.gitkeep` entfernt), `stage-backend` (nur `backend/appinfo/info.xml` byte-gleich per `cmp`, plus `LICENSE`, `CHANGELOG.md`), `pack <stage> <app> <archive>` mit CRLF-Sperre, `assert-contents <archive> <app> <wants-signature>`.
- `release.yml`: PHP-App mit `integrity:sign-app` und Release-Signatur (`APP_PRIVATE_KEY`, Pin `CERT_PUBKEY_SHA256`, lokal gegen das Zertifikat in `~/.nextcloud/certificates` nachgerechnet: stimmt), Backend mit `BACKEND_PRIVATE_KEY` und Pin `BACKEND_CERT_PUBKEY_SHA256: pending-certificate`; Tag-Prüfung beider info.xml und des Image-Tags; beide Archive und Signaturen als Release-Assets.
- `docker.yml`: Tag-Prüfung liest `php/appinfo/info.xml`, `backend/appinfo/info.xml` und `<image-tag>`.
- `store-submit.yml`: Matrix über beide Apps, `max-parallel: 1`, `fail-fast: true`, Registrierung je App mit eigenem Schlüssel, Image korrigiert auf `audio_video_search_backend`.
- `test_release_archives.py`: 12 Tests (Textregeln, sechs Gegenproben, zwei echte Staging-Läufe mit sh). Zusätzlich lokal `pack` und `assert-contents` für beide Archive ausgeführt: Backend grün, PHP-Archiv ohne signature.json korrekt rot (Gegenprobe), mit wants-signature 0 grün.

## Verifikation (lokal)

- `uv run ruff check .`, `ruff format --check .`, `pyright` (latest), `vulture`: grün
- `uv run pytest -q`: 385 passed (vorher 367)
- shellcheck 0.10.0 (shellcheck-py) für `store-archive.sh`, `redeploy.sh`, `admin-state.sh`: grün; `bash -n` grün
- `npx playwright test --list`: 121 Tests, `grep -c "@drift\|@patch\|@missing"` = 21
- Akzeptanz-greps: `app_api:app:update audio_video_search_backend` 1, `occ upgrade` vorhanden, `0.0.1` vorhanden, `version_drift`/`version_patch_differs`/`backend_missing`/`companion_missing` vorhanden, `rm-data` 0, `app:disable audio_video_search` 1; `stage_backend`/`stage_companion` je mindestens 2; `BACKEND_PRIVATE_KEY`, `BACKEND_CERT_PUBKEY_SHA256` in release.yml; `php/appinfo/info.xml` in docker.yml
- YAML aller geänderten Workflows parsebar; keine Gedankenstriche, kein CR in geänderten Dateien

## Nur in CI beweisbar (Plan 11)

- Job `upgrade` (4 Beine): Build beider Images, `occ upgrade` macht wirklich das App-Update, `app_api:app:update` behält Volume und `state.db` (A5 im Lauf)
- Drift 1 bis 4 gegen HaRP, `ci/admin-state.sh` gegen die echte Route (App-Passwort-Weg), Playwright `@drift/@patch/@missing` inklusive Screenshots
- `release.yml`/`store-submit.yml` laufen nur auf Tag bzw. von Hand und wurden nicht ausgelöst

## Deviations from Plan

### Auto-fixed / ergänzt

**1. [Rule 3] Zusätzliches Hilfsskript `ci/admin-state.sh`**
- Die Admin-Route verlangt Admin plus CSRF-Schutz; ohne Helfer stünde derselbe Login-Block in sieben Schritten. Nicht in files_modified, aber für die Drift- und Upgrade-Schritte nötig. Commit 7a8d3df.

**2. [Rule 2] Code-Signatur der PHP-App im Release**
- Der Plan nennt nur die openssl-Signatur über die Archive. Findling signiert die PHP-App zusätzlich mit `occ integrity:sign-app`; ohne `signature.json` ist das Archiv nicht integritätsgeprüft. Übernommen samt Wegwerf-Instanz. Commit f06af75.

**3. [Rule 2] `uv.lock` im prev/-Baum mitgezogen**
- Nur `pyproject.toml` auf 0.0.1 zu setzen hätte Lock und Projekt auseinanderlaufen lassen (`uv sync --frozen` im Image). Commit 7a8d3df.

**4. Kleinigkeiten**
- Drift-Versionen aus der PHP-Version abgeleitet statt fest 0.2.0/0.1.1 (heute identische Werte, bleibt nach dem nächsten Versionssprung sinnvoll).
- Companion-Polling 90 s statt 60 s (STALE 30 s plus CI-Langsamkeit).
- `deploy-harp`-Timeout 60 auf 75 min (drei Registrierungen und drei Playwright-Läufe mehr, Schätzung).
- `python.yml`: shellcheck um die zwei neuen Skripte erweitert.
- Commit 7a8d3df wurde vor dem nächsten Commit lokal per amend nachgebessert (Umlaute in der Nachricht, Ausführungsbit der Skripte); nichts davon war gepusht.

## Known Stubs

- `release.yml`: `BACKEND_CERT_PUBKEY_SHA256: pending-certificate` (absichtlich, PR 1417 offen). Der aus der lokalen CSR berechnete Wert ist `326dcfa967425902b21160e1af447bbca769c9aa17d73395e29cfff686ba1d80`; erst nach Ausstellung gegen das Zertifikat prüfen und eintragen (deferred-items.md).

## Threat Flags

Keine neue Angriffsfläche über das Bedrohungsmodell hinaus: `ci/admin-state.sh` holt in CI ein App-Passwort der Wegwerf-Instanz und maskiert es (`::add-mask::`); keine Repository-Secrets im Job deploy-harp.

## Self-Check: PASSED

- Dateien vorhanden: ci/redeploy.sh, ci/admin-state.sh, backend/tests/test_release_archives.py, scripts/release/store-archive.sh
- Commits vorhanden: 7a8d3df, b21c4d6, f06af75
