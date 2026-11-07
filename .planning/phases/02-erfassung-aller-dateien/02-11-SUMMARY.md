---
phase: 02-erfassung-aller-dateien
plan: 11
subsystem: ci-push
tags: [push-1, phase-02, ci, discovery-acceptance, ghcr, disc-01, disc-04]
requires: [02-01, 02-02, 02-03, 02-04, 02-05, 02-06, 02-07, 02-08, 02-09, 02-10]
provides:
  - "Branch phase-02 auf origin mit Spitze ad6a32c (43 Commits seit origin/phase-01 82f1655)"
  - "Erster CI-Beleg für PHP (PHPUnit 272 Tests) und Python (606 Tests) von Phase 2"
  - "Lokal, nicht gepusht: fix(02-01) 6e02526 für die ungültige Workflow-Datei discovery-e2e.yml, mit neuem Gate"
affects: [02-12, 02-13, 02-17, 02-22]
tech-stack:
  added: []
  patterns:
    - "Gate: kein Workflow liest den runner-Kontext im env von Workflow oder Job (GitHub verwirft sonst die ganze Datei)"
key-files:
  created: []
  modified:
    - .github/workflows/discovery-e2e.yml
    - backend/tests/test_discovery_workflow.py
    - .planning/phases/02-erfassung-aller-dateien/02-17-PLAN.md
    - .planning/phases/02-erfassung-aller-dateien/02-22-PLAN.md
decisions:
  - "Push 1 nur für ad6a32c (Owner 07.11.: 'Ja, pushen'); die lokale Korrektur 6e02526 braucht eine neue Owner-Freigabe"
  - "ghcr-Abfrage in Plan 17 und 22 mit --paginate und per_page=100"
metrics:
  duration: "ca. 60 min"
  completed: 2026-11-07
---

# Phase 2 Plan 11: Push 1 auf phase-02 Summary

Push 1 von ad6a32c auf phase-02 lief durch das Tor; Python gates und PHP gates sind grün, Discovery acceptance startete nie, weil GitHub die Workflow-Datei ablehnt (runner.temp im Job-env, Zeile 414); die Korrektur liegt lokal als 6e02526 und wartet auf eine neue Owner-Freigabe.

## Freigabe und Tor

- Owner-Freigabe 07.11. (Claude-Code-Terminal, Antwort auf "Darf ich Push 1 von AV Phase 2 ausführen (Plan 02-11, 43 Commits nur auf den Branch phase-02, nicht main)?"): "Ja, pushen". Gilt für genau einen Push.
- Freigabedatei `approvals/push-ad6a32c413d0a6d5890251f7c91c4928cddd9fca` mit Inhalt `push-phase-02 ad6a32c413d0a6d5890251f7c91c4928cddd9fca`; `approvals/` per `.git/info/exclude` (Muster `.planning/phases/02-erfassung-aller-dateien/approvals/`) ausgeschlossen, `git check-ignore` bestätigt.
- Autoren- und Textprüfung über `origin/phase-01..HEAD` (43 Commits, alle Autor und Committer `street1983nk <k.cherif@outlook.de>`, kein Claude-Session, kein closes/fixes/resolves #N): grün.
- Lokale Gates vor dem Push: ruff check, ruff format --check (62 Dateien), pyright latest 0 Fehler, vulture, pytest 606 grün.
- Push 12:38:03Z: `git push origin HEAD:phase-02` -> `* [new branch] HEAD -> phase-02`, genau einmal, kein --force, kein PR.

## CI-Ergebnis für ad6a32c

| Workflow | Lauf | Ergebnis |
|---|---|---|
| Python gates | [42373357005](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42373357005) | success (606 passed, Lint und shellcheck grün) |
| PHP gates | [42373356995](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42373356995) | success (php -l, composer validate/audit, PHPUnit OK 272 Tests, 5203 Assertions); lief direkt per Push, kein workflow_dispatch nötig |
| Deploy through HaRP | [42373357012](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42373357012) | success (10 Jobs: upgrade stable33/34/35 amd64 und stable35 arm64, deploy-harp stable33/34/35 auf amd64 und arm64) |
| Discovery acceptance | [42373356051](https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/42373356051) | failure ohne Jobs: "Invalid workflow file" |

Befund Discovery acceptance (Seite des Laufs, `gh run view` meldet "This run likely failed because of a workflow file issue"):

```
Invalid workflow file
(Line: 414, Col: 18): Unrecognized named-value: 'runner'. Located at position 1 within expression: runner.temp
```

Zeile 414 ist `LEAK_ROOT: ${{ runner.temp }}/leak-backend` im `env` des Jobs `leak-control`. Der runner-Kontext ist im env von Workflow und Job nicht erlaubt, nur in Schritten. Folge: kein Job lief, auch das Bein `discovery` nicht; es gibt keine PASS/FAIL-Zeilen, keine Samba-, Selbsttest- oder access-log-Kontrolle. Der Lauf trägt als workflowName den Dateipfad `.github/workflows/discovery-e2e.yml` statt "Discovery acceptance".

Das Workflow-Gate aus 02-01 (`leak_findings`) verlangte genau diesen Text (`"LEAK_ROOT: ${{ runner.temp }}/" in leak`) und konnte den Fehler darum nicht finden.

### Zuordnung der Discovery-Prüfungen

| Prüfung | Ergebnis | Zuordnung |
|---|---|---|
| Samba-Kontrolle | nicht gelaufen | Fehler 02-01 (Workflow-Datei), Korrektur 6e02526 lokal |
| Selbsttest des Vergleichs | nicht gelaufen | dito |
| access-log-Kontrolle | nicht gelaufen | dito |
| initial (Homes, Gruppenordner), upload, overwrite, copy, rename, tag | nicht gelaufen | dito |
| übrige Phasen | nicht gelaufen | dito (erwartet rot bis Plan 12 bis 20) |
| leak-control | nicht gelaufen | dito; Patch fehlt ohnehin bis Plan 13 |

## main und ghcr

- main vorher (`approvals/main-before-<sha>`): `f908a858402c4cae5a16c3cd3fe9b116f9ea0350 refs/heads/main`; nachher per `git ls-remote origin refs/heads/main | cmp -` identisch.
- ghcr `audio_video_search_backend` vorher: Exit 1, `{"message":"Package not found.", ... "status":"404"}` / `gh: Package not found. (HTTP 404)` -> Datei `STATE 404 Package not found`; nachher dieselbe Antwort (Exit 1, gleicher 404-Körper, Fehlerausgabe `gh: Package not found. (HTTP 404)`) -> `approvals/ghcr-after-<sha>` `STATE 404 Package not found`; `cmp` vorher/nachher gleich, kein `leak-control`. Hinweis: gh schreibt den 404-JSON-Körper auf stdout, die Meldung `HTTP 404` auf stderr.
- Scope: Token mit `read:packages` (gh auth status).
- Positivkontrolle: `gh api "users/street1983nk/packages?package_type=container"` nennt findling_backend, mcp_connector, gameworld, pdf_accessibility, audio_video_search, pii_redaction. `gh api --paginate "users/street1983nk/packages/container/findling_backend/versions?per_page=100" --jq '.[].metadata.container.tags[]'` Exit 0, 352 Tags, enthält `1.6.2`. Die Positivkontrolle setzt voraus, dass `findling_backend:1.6.2` existiert; fehlt es, nennt der Owner einen anderen bekannten Tag, und der Plan wird mit diesem Tag wiederholt.
- Zusatzbeleg: Es gibt ein öffentliches Paket `audio_video_search` (nicht `_backend`, angelegt 05.11. aus main-Läufen des Gerüsts, Tags `dev`, Commit-SHAs, `buildcache-*`). Vorher-Stand in `approvals/ghcr-extra-before-<sha>`; nachher `approvals/ghcr-extra-after-<sha>` identisch, kein `leak-control`.

## Deviations from Plan

**1. [Koordinator-Befund] ghcr-Abfrage mit per_page=100**
- Der Koordinator meldete, dass die erste Seite der findling_backend-Versionen `1.6.2` nicht enthält. Gemessen: ohne `--paginate` fehlt 1.6.2; die Plan-Abfrage mit `--paginate` (ohne per_page) fand 1.6.2 ebenfalls (352 Zeilen). Ausgeführt wurde die Form `gh api --paginate "...versions?per_page=100"`; Plan 17 und 22 auf diese Form umgestellt.
- Commit: a412bb6 (lokal)

**2. [Rule 1 - Bug] Workflow-Datei discovery-e2e.yml ungültig (Task 3, nur lokal)**
- Gefunden: Push 1, Lauf 42373356051.
- Fix: LEAK_ROOT aus dem env des Jobs in das env des Schritts "Build the control image out of a patched copy"; neues Gate `runner_env_findings` über alle Workflows mit Selbsttest. Positivkontrolle: am gepushten Stand meldet die Regel genau `old:414 reads the runner context in a job env`, also dieselbe Zeile wie GitHub.
- Gates lokal: ruff, format, pyright 0, vulture, pytest 608 grün.
- Commit: 6e02526 (lokal, NICHT gepusht; Push nur nach neuer Owner-Freigabe).

## Offen für den Owner

- Freigabe für Push 2 (Korrektur): neuer SHA ist HEAD nach dem docs-Commit dieses SUMMARY; Inhalt seit ad6a32c: a412bb6 (docs Plan 17/22), 6e02526 (fix 02-01), docs(02-11).
</content>

## Prüfung aus verify (mit festem SHA ad6a32c, weil HEAD lokal weitergewandert ist)

- Pflicht-Workflows success: 3 von 3 (Python gates, PHP gates, Deploy through HaRP).
- main unverändert (`cmp` grün), phase-02 = ad6a32c.
- ghcr-before und ghcr-after vorhanden, gleich, kein leak-control; Positivkontrolle findling_backend 1.6.2 grün.
- Discovery acceptance: rot wegen ungültiger Workflow-Datei, die Muss-Wahrheit "läuft auf einem Bein, Kontrollen grün" ist damit NICHT erfüllt. Plan 11 bleibt offen bis Push 2 (neue Owner-Freigabe) und ein Lauf mit Jobs.

## Self-Check: PASSED

- Commits a412bb6, 6e02526 vorhanden; Freigabe-, main- und ghcr-Dateien unter approvals/ vorhanden (nicht committet).
