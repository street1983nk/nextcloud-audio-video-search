---
phase: 03-vorschau-transkripte-in-der-suche
plan: 17
subsystem: ci, abnahme
tags: [discovery-e2e, search-parity, webdav-truth, self-test, model-cache, air-gap, srch-03]
requires: ["03-02", "03-12", "03-15", "03-16", "03-16b"]
provides:
  - "discovery-e2e.yml: Modelle per Cache avs-models-<MODEL_SHA256> ins Volume der ExApp vor der Registrierung, Beleg init 100 mit outcome present"
  - "AVS_SPEECH_DE, AVS_SPEECH_TR, AVS_SPEECH_WORD im Job discovery (über GITHUB_ENV)"
  - "ci/discovery/parity.sh: baseline, wait, before, settle, --self-test, check"
  - "topology.sh: parity_place, parity_revoke"
  - "Phase search-parity als 21. Phase der Abnahme"
affects: [03-18, 03-19, 03-20]
tech-stack:
  added: []
  patterns:
    - "Wahrheit je Person per WebDAV (PROPFIND Ordner für Ordner, GET, sha256sum), Ausschlüsse aus den Regeln des Tests"
    - "Selbsttest nach compare.sh-Muster: die echte Antwort als Erwartung, jede Verschiebung muss einzeln scheitern"
    - "Positivkontrolle vor dem Entzug: entzogene Freigabe und Papierkorb-Kopie sind vorher Treffer"
key-files:
  created:
    - ci/discovery/parity.sh
  modified:
    - .github/workflows/discovery-e2e.yml
    - ci/discovery/topology.sh
    - ci/discovery/common.sh
    - ci/discovery/README.md
    - backend/tests/test_discovery_workflow.py
decisions:
  - "Samba-Sperre auf ana selbst und ACL-Fall mit cem: ben ist ab exclude-user-after ausgeschlossen, cem hat ab vanish kein SMB mehr, dan ist gelöscht"
  - "Modelle bei Fehltreffer mit procure aus dem Image dieses Commits (kein uv im Job), Clips mit python3 und ffmpeg des Runners"
  - "Pfade der Clips über GITHUB_ENV statt Job-env: runner-Kontext ist dort verboten (bestehende Regel)"
  - "search-parity hat ein eigenes Urteil; compare.sh würde den neuen Sprachinhalt im transcribed-Zähler als Fehler werten"
  - "Neuer Schritt parity.sh settle vor den Phasen (begrenzt, nie ein Urteil): mit Modellen lädt die Vorschau jedes Testmedium über das Gateway"
metrics:
  duration: "ca. 1 h 45 min"
  completed: 2026-11-14
  tasks: 2
  files: 6
---

# Phase 3 Plan 17: Modelle in der Abnahme, Rechte-Paritätstest der Suche im HTTP-Pfad Summary

Die Abnahme legt die Modelle aus dem Cache (Schlüssel `avs-models-<MODEL_SHA256>`) vor der Registrierung ins Volume der ExApp und belegt, dass `/init` ohne Download 100 meldet; die neue letzte Phase `search-parity` legt den DE-Clip an sieben Orte mit unterschiedlichem Leserecht und vergleicht je Person die Treffer der OCS-Suche mit einer WebDAV-Wahrheit (GET plus sha256), nach einem Selbsttest, der eine zusätzliche, eine fehlende und eine doppelte fileId sowie einen nicht gekennzeichneten Treffer einzeln als FAIL sehen muss.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 | 5225cb1 | ci(03-17): Modelle und Sprachclip in der Abnahme |
| 2 | a2712be | ci(03-17): Rechte-Paritätstest der Suche im HTTP-Pfad |
| Nacharbeit | 8dcae55 | chore(03-17): parity.sh ausführbar wie die anderen Skripte der Abnahme |

Alle nur lokal, Autor und Committer street1983nk <k.cherif@outlook.de>, nichts gepusht, kein Workflow gestartet, kein Docker.

## Task 1: Modelle und Clip im Job discovery

Neue Schritte nach dem Image-Bau, vor HaRP und der Registrierung:

1. Schlüssel: `avs-models-` aus `MODEL_SHA256` von `models/catalog.py`, Clip-Schlüssel aus den Mitglied-sha256 von `fetch_speech.py` plus sha256 des ffmpeg (beides mit `python3 -I` des Runners per `runpy`, die Dateien haben nur Konstanten und stdlib; lokal unter Python 3.12 nachgeprüft: gleicher Wert wie `MODEL_SHA256`).
2. `actions/cache` (gleicher SHA-Pin wie python.yml) für `$RUNNER_TEMP/avs-models` ohne `*.verified.json`, und für `$RUNNER_TEMP/avs-speech`.
3. Fehltreffer: `procure --root` aus dem Image dieses Commits (fester URL, Allowlist, fester sha256, als Runner-Nutzer), bzw. `fetch_speech.py`.
4. Clip-Prüfung (WAV-sha256 nur Warnung wie python.yml), dann `AVS_SPEECH_DE`, `AVS_SPEECH_TR`, `AVS_SPEECH_WORD` in `GITHUB_ENV`.
5. Air-Gap-Weg: `docker volume create nc_app_audio_video_search_backend_data`, Kopie als uid 10001 mit dem Image, Prüfdateien gelöscht (T-03-59: der Container hasht jede Datei neu).
6. Nach der Registrierung: `oc_ex_apps.status` hat `init == 100`; im Container-Log je Modell eine Zeile `model procure` mit `outcome present`, keine mit anderem Ergebnis, und `models ready`.

Job-Frist 120 auf 150 min, Schritt "Run the phases" 90 auf 110 min (Begründung als Kommentar: 03-15 maß 3,5 bis 7,4 s je Datei mit Kindstart; etwa 40 Dateien mal zwei auf dem Runner plus Modell-Download plus Wartezeiten der neuen Phase). Job leak-control unverändert.

Tests (test_discovery_workflow.py): Schlüssel aus `MODEL_SHA256` (der Python-Ausdruck aus dem Workflow wird ausgeführt und mit `catalog.MODEL_SHA256` verglichen), Restore unter dem Schlüssel, Prüfdateien ausgenommen, procure bei Fehltreffer, Clip-Cache, drei Variablen, Volume vor `app_api:app:register`, Beleg danach, leak-control ohne `avs-models`, `actions/cache@`, `models.procure`, `AVS_SPEECH`, `fetch_speech`. Positivkontrollen: Schlüssel ohne `MODEL_SHA256`, Prüfdateien nicht gelöscht, Volume-Schritt nach der Registrierung, fehlende Download-Prüfung und Variable, Cache-Schritt in leak-control: je genau die erwarteten Befunde.

## Task 2: Phase search-parity

Orte (`topology.sh parity_place`), Erwartung nach der Wahrheit:

| Kopie | erwartet |
|---|---|
| `rede-geteilt.wav` (ana, an cem freigegeben, danach entzogen) | ana |
| `rede-papierkorb.wav` (ana, danach gelöscht) | niemand |
| `Team/rede-frei/rede.wav` (cem `+read -share`, cem tritt `team` bei) | ana, cem |
| `Team/rede-intern/rede.wav` (cem `-read`) | ana |
| `rede-gesperrt.wav` auf der Samba-Freigabe, DENY READ für ana | niemand (nur ben liest, ausgeschlossen) |
| `rede-sperre.wav` unter der files_accesscontrol-Regel (erst Ton, dann Tag, dann Clip über die Kommandozeile wie access_control) | niemand |
| `rede-eva.wav` (eva, ausgeschlossen, an cem freigegeben) | niemand (ausgeschlossene Person und Eigentümerin) |

Ablauf in der Schleife: `parity.sh baseline` (complete vor dem Clip), `parity_place`, `rescan` von ana's SMB-Speicher, `compare.sh wait`, `parity.sh wait` (complete über der Basis, nichts running, dann erster Treffer für ana), `parity.sh before` (cem findet die Freigabe, ana die spätere Papierkorb-Kopie), `parity_revoke`, `compare.sh wait`, `parity.sh check`. PASS nur mit `PARITY CONTROL SHOWED THE DIFF` und `PHASE PASS search-parity`; Urteil jetzt über 21 Phasen.

`parity.sh check`: Wahrheit für ana, ben, cem, eva, fritz (WebDAV PROPFIND Ordner für Ordner mit `oc:fileid`, `oc:owner-id`; jede `.wav` per GET, `sha256sum` gegen den Clip; minus Ausschlüsse aus den Regeln des Tests), Produkt über die OCS-Route mit `limit=25` und Cursor bis zur letzten Seite; dann Selbsttest, Wahrheitskontrolle (`truth_says_no`: ana sieht die Samba- und die files_accesscontrol-Kopie und liest keine), je Person `parity <person> erwartet=<ids> gefunden=<ids>` mit Mengen-, Doppel- und Vorläufig-Prüfung, `at_least_one_hit_ana`/`_cem`. Kein App-Code, kein Zustand des Containers; `occ audio_video_search:status` nur zum Warten (Test erzwingt, dass das der einzige occ-Befehl der App ist).

### Attrappen-Lauf (lokal, gefälschtes curl/occ, WebDAV-Baum mit Ausschlussfällen, zweiseitige Suche)

| Szenario | Ergebnis |
|---|---|
| korrekt | `PARITY CONTROL SHOWED THE DIFF`, alle PASS, `PHASE PASS search-parity`, exit 0; Paging über Cursor gefolgt (104 auf Seite 2); SMB-Teil, privat, Ton-Datei und gesperrte Kopien richtig nicht erwartet |
| cem findet eva's Kopie | `FAIL set_cem zuviel=107` |
| cem findet `-read`-Kopie | `FAIL set_cem zuviel=104` |
| ana fehlt ein Treffer | `FAIL set_ana fehlt=104` |
| fileId doppelt über Seiten | `FAIL unique_ana doppelt=101` |
| Untertitel ohne Kennzeichnung | `FAIL preliminary_ana ohne=104` |
| Wahrheit liest gesperrte Kopie | `FAIL truth_says_no` und `FAIL set_ana fehlt=105` |
| niemand hat Treffer | `PARITY SELF-TEST FAILED`, kein Urteil |
| wait ohne neuen complete | `FAIL wait_preview` nach Frist; mit neuem complete PASS |
| before ohne bzw. mit Treffer | 2 FAIL bzw. 2 PASS |
| settle ruhig / mit laufendem Job | Ruhe nach 3 s / `::warning::`, exit 0 |

## Gates

- `pytest tests/test_discovery_workflow.py tests/test_workflow_pins.py tests/test_workflows.py`: 111 passed. Positivkontrollen für jede neue Regel (11 Tests mit kaputten Kopien).
- Plan-Verify: `bash -n`, `PHASE PASS search-parity`, `PARITY CONTROL SHOWED THE DIFF`, `sha256sum` vorhanden, kein `audio_video_search_backend`/`state.db` in parity.sh.
- shellcheck 0.11.0 (`uvx shellcheck-py==0.11.0.1`): parity.sh und topology.sh ohne Befund; common.sh nur die vorbestehenden SC2034 (auch auf HEAD). Positivkontrolle: eingefügte ungeklammerte Substitution gibt SC2046.
- Run-Blöcke des Jobs discovery einzeln mit shellcheck: nur vorbestehend SC2181 (Phasenschleife) und SC2024 (Logsammlung), beide auch auf HEAD; ein eigenes SC2015 wurde behoben.
- actionlint 1.7.12 (`uvx actionlint-py`) ohne Befund; Positivkontrolle mit unbekanntem Step-Verweis gibt einen Fehler. Mit eingebautem shellcheck hing actionlint lokal mehrmals (Windows), daher die Run-Blöcke separat geprüft.
- ruff check, ruff format --check (132 Dateien), pyright latest 0 Fehler, vulture still.
- Volle Suite: **1862 passed, 15 skipped** (Modelltests ohne lokale Modelle), 205 s.
- Keine U+2013/U+2014 in den geänderten Dateien (Prüfer mit Probe positiv).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Personen der Planvorgabe nach Phase 2 nicht mehr verfügbar**
- ben ist ab `exclude-user-after` ausgeschlossen (Suche liefert ihm nie etwas), cem hat ab `vanish` keinen SMB-Mount mehr. Mit ben als `+read -share`-Person wäre die Mindestens-ein-Treffer-Regel nie erfüllbar, die Samba-Sperre für ben bewiese nichts.
- Lösung: cem tritt `team` bei und bekommt `+read -share` bzw. `-read` auf zwei neuen Unterordnern; die Samba-Sperre trifft ana selbst. Commit a2712be.

**2. [Rule 2] Positivkontrollen vor dem Entzug und Wahrheitskontrolle**
- Entzogene Freigabe und Papierkorb werden erst nach Indexierung entzogen, vorher muss die Suche sie zeigen (`parity.sh before`); `truth_says_no` zeigt, dass die WebDAV-Wahrheit gesperrte Kopien sieht und nicht liest. eva's Kopie zusätzlich an cem freigegeben (prüft den Ausschluss über die Eigentümerin).

**3. [Rule 3] Vorschau lädt mit Modellen jedes Testmedium**
- Mit Modellen im Volume holt die Vorschau jede Datei über das Gateway. Phasen wie rename/tag/restore prüfen "0 Gateway-Zeilen" je fileId; ein später Vorschau-Download im Fenster einer Phase wäre ein falsches FAIL. Neuer Schritt `parity.sh settle` vor den Phasen: wartet, bis nichts läuft und die Zähler dreimal gleich sind, höchstens 600 s, nie ein Urteil. compare.sh unverändert (eine Wartebedingung auf queued == 0 hätte hängen können: Jobs ohne lesbare Quelle bleiben queued).

**4. Plantext-Abweichungen, bewusst**
- Fehltreffer der Modelle mit `procure` aus dem gebauten Image statt `uv run` (kein uv-Toolchain im Job; gleicher Downloader wie `/init`). Clips mit python3 und apt-ffmpeg des Runners; der WAV-sha256 wird dort sehr wahrscheinlich abweichen und nur warnen (Mitglied-sha256 bindet), deshalb anderer Clip-Schlüssel als python.yml.
- "Job-Umgebung" der drei Variablen über `GITHUB_ENV` (runner-Kontext in `env:` des Jobs bricht die Datei, bestehende Regel).
- Wartebedingung "keine queued/running für diesen Inhalt": status kennt keine Inhalte; umgesetzt als complete über dem Stand vor dem Clip und nichts running, danach erster Treffer für ana.
- search-parity läuft in der Schleife mit eigenem Zweig (`continue`), nicht über truth.sh/compare.sh: deren transcribed-Prüfung kennt den neuen Sprachinhalt nicht.
- Bestehender Test der Step-Frist auf 110 min nachgezogen; Test "fehlende Phase" auf die neue Schleifenzeile.

## Offene Punkte (für 03-20)

- **Annahmen, die erst der echte Lauf belegt:** HaRP übernimmt das vorab angelegte Volume samt Inhalt (deploy-harp.yml stützt das für Updates, nicht für eine Erstinstallation); ein frisches benanntes Volume übernimmt Eigentümer 10001 aus dem Image; `oc_ex_apps.status` ist JSON mit `init`; ana kann per smbcacls sich selbst READ verweigern und sieht die Datei weiter im Listing; Nextcloud liefert `oc:owner-id` für Freigaben aus eva's Home.
- **Laufzeit:** Vorschau aller Testmedien auf dem Runner ungemessen; Fristen sind Schätzungen.
- **deploy-harp.yml (offener Punkt aus 03-03, schemaVersion 2 nach dem Update):** von 03-17 nicht berührt; bleibt für 03-19.
- **dan** ist zur Phase gelöscht und wird nicht geprüft; fritz und ben werden geprüft (erwartet leer).
- Parallel-Executor 03-13b hat während des Laufs committet (c722587, 01b5f1f) und hat ungestagte Änderungen in test_catch_rule.py, test_engine_child.py, test_engine_constants.py, test_model_download.py; nicht berührt. Die volle Suite lief über diesem Stand.

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche außerhalb des Bedrohungsmodells. T-03-57 (Selbsttest mit zusätzlicher und fehlender fileId, Mindestens-ein-Treffer-Regel), T-03-58 (Wahrheit per WebDAV-GET und sha256, Vergleich je Person) und T-03-59 (Cache nur Ablage, Prüfdateien ausgenommen und im Volume gelöscht) umgesetzt. Neu im Job: `actions/cache` (SHA-gepinnt wie python.yml) und ein Download der Modelle bzw. Clips aus öffentlichen Quellen auf dem Runner.

## Self-Check: PASSED

- FOUND: ci/discovery/parity.sh, .github/workflows/discovery-e2e.yml, ci/discovery/topology.sh, ci/discovery/common.sh, ci/discovery/README.md, backend/tests/test_discovery_workflow.py
- FOUND: Commits 5225cb1, a2712be, 8dcae55
