---
phase: 03-vorschau-transkripte-in-der-suche
plan: 07b
subsystem: modelle
tags: [downloader, github-release, allowlist, lizenz, dockerfile]
requires:
  - "03-07: Katalog, procure, fetch_model_asset, Festwerte sha256/Länge"
provides:
  - "GitHub-Release models-2026-11 mit fünf byte-gleichen Modelldateien"
  - "catalog.py: MODEL_RELEASE_REPOSITORY, MODEL_RELEASE_TAG, URLs auf das Release, ASSET_HOSTS aus Messung"
  - "Dockerfile: HF_HUB_OFFLINE=1, HF_HUB_DISABLE_TELEMETRY=1 im Runtime-ENV"
affects: [03-10, 03-11, 03-19]
key-files:
  modified:
    - backend/src/audio_video_search_backend/models/catalog.py
    - backend/tests/test_models.py
    - backend/tests/test_model_download.py
    - backend/Dockerfile
    - backend/tests/test_dockerfile.py
    - README.md
    - README.en.md
    - README.fr.md
decisions:
  - "Modellquelle ist das eigene Release models-2026-11 (D-03-21), Hugging Face ist nicht mehr erlaubt"
  - "ASSET_HOSTS = {github.com, release-assets.githubusercontent.com}, gemessen am 14.11.2026"
  - "README-Überschrift auf 'Bestandteile Dritter im Backend' (EN/FR entsprechend) geändert, Owner-Entscheid"
metrics:
  completed: 2026-11-14
  tasks: 2
  files: 8
---

# Phase 3 Plan 07b: Modellquelle eigenes Release Summary

Die fünf Modelldateien (Parakeet TDT 0.6B v3 int8 von NVIDIA, CC-BY-4.0, und Silero VAD, MIT) liegen byte-gleich im öffentlichen Release `models-2026-11`. Der Downloader lädt nur noch dort, mit fester Allowlist aus der gemessenen Redirect-Kette. sha256, Längen und MODEL_SHA256 sind unverändert, und das Image hält huggingface-hub offline.

## Owner-Freigabe (14.11.2026, wörtlich, über die Hauptsitzung)

Release = "Freigabe"; README-Überschrift = "Ja, anpassen (Empfohlen)".

## Task 1: Release

Vorprüfung (nur lesend):
- Konto street1983nk, Repo PUBLIC, main; `gh release view models-2026-11` gab "release not found"; keine Tags, keine Releases, keine Rulesets.
- Tag-Muster in docker, python, php, deploy-harp und release: nur `v[0-9]+.[0-9]+.[0-9]+`; discovery-e2e, scorecard und security nur Branches; store-submit nur workflow_dispatch; kein `release:`-Auslöser.

Download über `procure --root <scratch>/models-07b` (Hugging Face/k2-fsa, wie 03-07): `silero procured`, `parakeet procured`, Exit 0. Gegenprobe mit `sha256sum` und `certutil` sowie `stat -c %s` gegen die Literalwerte: alle fünf gleich; Positivkontrolle: ein verfälschter Hash wird als ungleich erkannt.

Release als Entwurf (`--draft --latest=false`), Titel "Speech models 2026-11 (not an app release)", Text als englische Faktenliste (NVIDIA, CC BY 4.0, Quell-Commit 2bda32ec70b097a55adaa07d9a7173915b43cc78, byte-identisch, Silero MIT-Text wörtlich, "Copyright (c) 2020-present Silero Team"). Nur die fünf Dateien hochgeladen, keine `*.verified.json`.

API-Digest vor dem Veröffentlichen:

| Asset | Größe | Digest |
|-------|------:|--------|
| encoder.int8.onnx | 652184281 | sha256:acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247 |
| decoder.int8.onnx | 11845275 | sha256:179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e |
| joiner.int8.onnx | 6355277 | sha256:3164c13fc2821009440d20fcb5fdc78bff28b4db2f8d0f0b329101719c0948b3 |
| tokens.txt | 93939 | sha256:d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d |
| silero_vad.onnx | 643854 | sha256:9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6 |

Alle gleich den Festwerten, danach `gh release edit --draft=false --latest=false`. Verify: `models-2026-11 draft=false assets=5`.

`gh run list --limit 5`: jüngster Lauf 2026-11-14T07:14:03Z (push phase-02), also vor dem Release; kein Lauf durch den Tag.

### Beobachtete Weiterleitungen (14.11.2026, `curl -sSI --max-redirs 0`, je Stufe einzeln, HEAD)

| Datei | Stufe 1 (Status, Location-Host) | Stufe 2 (Status) | Länge |
|-------|----------------------------------|------------------|------:|
| encoder.int8.onnx | github.com: `HTTP/1.1 302 Found`, Location-Host `release-assets.githubusercontent.com` (Pfad `/github-production-release-asset/...`) | release-assets.githubusercontent.com: `HTTP/1.1 200 OK` | 652184281 |
| decoder.int8.onnx | github.com: `HTTP/1.1 302 Found`, `release-assets.githubusercontent.com` | `HTTP/1.1 200 OK` | 11845275 |
| joiner.int8.onnx | github.com: `HTTP/1.1 302 Found`, `release-assets.githubusercontent.com` | `HTTP/1.1 200 OK` | 6355277 |
| tokens.txt | github.com: `HTTP/1.1 302 Found`, `release-assets.githubusercontent.com` | `HTTP/1.1 200 OK` | 93939 |
| silero_vad.onnx | github.com: `HTTP/1.1 302 Found`, `release-assets.githubusercontent.com` | `HTTP/1.1 200 OK` | 643854 |

Der Asset-Host antwortete auf HEAD mit 200, ein Ein-Byte-GET war nicht nötig. Content-Length gleich der Festlänge. Hosts für ASSET_HOSTS: {github.com, release-assets.githubusercontent.com}.

## Task 2: Umstellung (TDD)

- RED `390027d`: 7 Tests rot (Release-URLs, Tag ohne v, Allowlist gleich Messung, kein HF, Katalog-Allowlist verweigert HF-CDN und HF-Start, Dockerfile-ENV).
- GREEN `d40588b`: catalog.py mit `MODEL_RELEASE_REPOSITORY`, `MODEL_RELEASE_TAG`, `_RELEASE_BASE`; `PARAKEET_REPOSITORY`/`PARAKEET_REVISION`/`_PARAKEET_BASE` entfernt (nirgends sonst benutzt), Commit 2bda32ec im Docstring als Herkunft; Dockerfile Runtime-ENV mit `HF_HUB_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`; README DE/EN/FR: Überschrift und Zeile 58 ersetzt, sonst nichts.
- Hash-Positivkontrolle: echte Katalogdatei silero_vad.onnx mit falschen Bytes gleicher Länge ergibt WRONG_DIGEST ohne Datei; derselbe Aufbau mit passendem Digest ergibt PROCURED.
- Mutationsproben (jede gefangen): `us.aws.cdn.hf.co` zurück in ASSET_HOSTS (3 rot), ein Zeichen im Silero-sha256 geändert (2 rot), `HF_HUB_DISABLE_TELEMETRY` im Dockerfile entfernt (1 rot).
- Gates: ruff check, ruff format --check, pyright (latest, 0 Fehler), vulture grün; volle Suite **1692 passed**.
- Abnahme: Katalog ohne HF-Host/URL (Exit 0), MODEL_SHA256 genau einmal, Commit-Hash vorhanden, Diff ohne sha256=/size=-Zeilen, HF-ENV nach `FROM ${BASE_IMAGE} AS runtime` (Zeilen 144, 145), README ohne U+2013/U+2014, FR mit U+00A0 vor `;` und `:`.

### Ende-zu-Ende über die neue Kette

Frischer leerer Ordner `<scratch>/models-07b-e2e`: `silero procured`, `parakeet procured`, Exit 0; danach `--verify-only`: `silero present`, `parakeet present`, Exit 0. Scratch-Ordner `models-07b`, `models-07b-e2e` und die Notizdateien danach gelöscht; `git status` zeigt keine .onnx- oder tokens.txt-Datei.

## Deviations from Plan

- **README-Überschrift geändert** (über den Plan hinaus, nur nach Owner-Entscheid): DE "Bestandteile Dritter im Backend:", EN "Third-party components of the backend:", FR "Composants tiers du backend :" (mit U+00A0), weil die Modelle nicht im Image liegen.
- **Zusätzlicher Test** `test_the_release_tag_never_looks_like_an_app_version` mit Positivkontrolle `v0.1.0`.
- Zeilenenden: Python schrieb catalog.py zunächst mit CRLF; vor dem Commit auf LF zurückgesetzt.
- test_main.py Zeile 219 nicht angefasst (kein Test schlug fehl).
- Fremde, nicht gestagte Änderungen aus 03-14 (api/excerpt.py und Tests) im Arbeitsbaum nicht berührt; sie wurden in der Zwischenzeit von der Parallel-Session committet.

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche. T-03-74 bis T-03-78 umgesetzt (Digest-Prüfung vor dem Veröffentlichen, Allowlist aus Messung, HF-ENV, Namensnennung); T-03-79 akzeptiert wie geplant.

## Self-Check: PASSED

- FOUND: Release models-2026-11 (draft=false, assets=5)
- FOUND: Commit 390027d, Commit d40588b
