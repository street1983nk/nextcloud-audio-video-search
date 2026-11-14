---
phase: 03-vorschau-transkripte-in-der-suche
plan: 18b
subsystem: ci, abnahme, discovery
tags: [discovery-e2e, abspielseite, leck-probe, p12, srch-02, srch-03, d-03-24]
requires: ["03-14", "03-16", "03-17", "03-18"]
provides:
  - "ci/discovery/playpage.sh: Abspielseiten-Probe P12 (p12a nie active, p12b entzogen) mit Offline-Selbsttest, Positivkontrollen, zwei Mustern und zwei Zustandsquellen"
  - "discovery-e2e.yml: Phase play-leak (22. Phase), before-revoke und after-revoke im Phasenlauf reprove, Urteil über 22 Phasen, play-*.txt und play-*.html im Artefakt"
  - "test_discovery_workflow.py: play_findings mit sechs Positivkontrollen"
  - "preview.spec.ts: P12 als übersprungener Fall mit Annotation covered by, Verweis auf play-leak"
affects: [03-19, 03-20, 03-21]
tech-stack:
  added: []
  patterns:
    - "Leck-Probe auf server-gerendertem HTML: Byte-Vergleich des Blocks plus Strukturprüfung gegen die wörtlichen UI-SPEC-Texte"
    - "Zustand des Verweises aus zwei Quellen (occ files, state.db-Kopie); fehlt eine Zeile oder widersprechen sie sich, ist die Probe INVALID"
    - "Selbsttest legt WORK in einen eigenen mktemp-Ordner (RUNNER_TEMP vor dem Sourcen von common.sh)"
key-files:
  created:
    - ci/discovery/playpage.sh
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-18b-SUMMARY.md
  modified:
    - ci/discovery/README.md
    - ci/discovery/common.sh
    - .github/workflows/discovery-e2e.yml
    - backend/tests/test_discovery_workflow.py
    - ci/playwright/preview.spec.ts
decisions:
  - "OC-1 (Owner 14.11.2026): html-beleg. Wortlaut: \"HTML als Beleg\" = gespeicherte Seiten als Artefakt, Aussehen über den P4-Screenshot; KEIN Playwright in discovery-e2e, kein 03-18c"
  - "P12a an SMB/rede-gesperrt.wav (ana), Kontrolle rede-geteilt.wav zur Zeitmarke ihres ersten Treffers; P12b an SMB/widerruf.webm (cem) vor und nach revoke_cem, Urteil erst in play-leak"
  - "files_accesscontrol (rede-sperre.wav) nicht für P12: die Regel nimmt das Leserecht aus dem Cache-Eintrag, die Seite ist nicht Bereit, kein Block zum Vergleichen"
  - "ref_state ohne Nutzer-Argument: der Container führt einen Verweis je fileId, der Zustand hängt nicht an der Person"
metrics:
  duration: "ca. 1 h 30 min"
  completed: 2026-11-14
---

# Phase 3 Plan 18b: P12 als echte Abspielseiten-Probe in discovery-e2e Summary

Abnahmefall P12 ("Verweis nicht active, Datei über anderen Weg lesbar: Block gleich P4") hat jetzt eine eigene, scheiterfähige Probe auf der echten Abspielseite in discovery-e2e.yml: `ci/discovery/playpage.sh` prüft "nie active" (ana, Samba-Sperre) und "entzogen" (cem, nach `reconcile --reprove`) gegen die A5-Referenz, je mit Live-Positivkontrolle, zwei unabhängigen Mustern und zwei Zustandsquellen; INVALID wird nie PASS.

## Owner-Checkpoint OC-1 (Task 1)

Antwort des Owners (14.11.2026), wörtlich: "HTML als Beleg" = gespeicherte Seiten als Artefakt, Aussehen über den P4-Screenshot; KEIN Playwright in discovery-e2e, kein 03-18c.

Folge: kein Bild von P12 im Abnahmeordner. Die Seiten `play-p12a-*.html` und `play-p12b-*.html` (Referenz, Kontrolle, Probe) liegen im Artefakt `discovery-logs-*`. Diese Abweichung vom Wortlaut des Prüfvertrags (Screenshot 1280 hell) ist in 03-21 zu nennen.

## Was gebaut wurde

**playpage.sh** (Unterbefehle `--self-test`, `before-revoke`, `after-revoke`, `check`):
- `block`, `ready`, `same_bytes` (Muster 1, `cmp -s`), `is_a5` (Muster 2: genau ein Label "Excerpt at this point", genau ein Hinweis "There is no transcript for this file yet.", kein `avs-excerpt__text`, keine Note, kein Clip-Wort, kein T5), `states_say`, `judge_probe`, `judge_control`.
- `ref_state FILEID`: `occ audio_video_search:files --json --all` und `SELECT state FROM file_ref WHERE file_id = N` auf einer Kopie von state.db (Muster von compare.sh, eigener Ordner `statedb-play`).
- `page`: Basic Auth mit `Accept-Language: en`; sonst Zeile `NOTE basic auth refused (http=N), signing in with a session` und Anmeldung über `/index.php/login` (requesttoken aus `data-requesttoken`).
- `hit_seconds`: Zeitmarke aus `resourceUrl` (`t=`) der OCS-Suche, Form wie `parity.sh product_of`.
- `before-revoke` speichert Referenz und Kontrolle von cem samt Zustand in `play-p12b.state`, `after-revoke` die Probe; beide geben kein Phasenurteil. `check` startet zuerst den Selbsttest als eigenen Prozess, prüft die Stabilität der Referenz, dann p12a live und p12b aus den Dateien von reprove.
- Seiten unter WORK und als Kopie im Arbeitsverzeichnis (Collect the logs).

**Workflow**: Phase play-leak nach search-parity mit eigenem Zweig und `continue`, FAIL-/INVALID-/SELF-TEST-FAILED-Zeilen nach results.txt, PASS nur mit beiden `grep -qx 'PLAY CONTROL SHOWED THE DIFF p12a|p12b'`. In reprove `before-revoke` vor dem `case`, `after-revoke` nach `compare.sh`. Die Zeile `reprove) bash "${d}/topology.sh" revoke_cem && ./occ audio_video_search:reconcile --reprove ;;` ist unverändert. Urteil "of 22 phases", `[ "${passed}" = 22 ]`. Fristen unverändert (nur wenige curl-Aufrufe, im Kommentar begründet). Job leak-control unberührt.

**preview.spec.ts**: P12 als `test(...)` mit `annotation: { type: 'covered by', description: 'discovery-e2e.yml phase play-leak, ci/discovery/playpage.sh (plan 03-18b, D-03-24)' }` und `test.skip(true, ...)`. P13 bleibt test.fixme.

**S4** bleibt wie in 03-18 gebaut (zwei Suchen desselben Nutzers, Owner 14.11.2026). Nicht Teil dieses Plans.

## Gegenproben und Belege (lokal, ohne Docker, ohne Netz)

- Selbsttest: 11 Fälle mit erwartetem und gesehenem Ergebnis, `PLAY SELF-TEST PASSED`, Ausgang 0. Die neun Fälle des Plans plus "Verweis unbekannt" (INVALID) und "Kontrolle mit Unterschied" (SHOWED, sonst könnte keine Kontrolle bestehen). Lief mit Attrappen für docker und curl vorne im PATH, die bei jedem Aufruf mit Ausgang 97 abbrechen: keiner wurde aufgerufen. `/tmp/avs-discovery` wurde nicht angelegt.
- Mutationsproben (nur Scratch-Kopien): `same_bytes` immer wahr ergibt `PLAY SELF-TEST FAILED` (space wird PASS, blockquote/t5/a5-text zeigen bytes=yes, control-differs INVALID); `is_a5` immer wahr ergibt `PLAY SELF-TEST FAILED` (blockquote, t5, a5-text zeigen a5=yes); zusätzlich `ready` immer wahr (no-block wird FAIL statt INVALID) und `states_say` immer ok (ref-active, sources-differ, ref-unknown werden PASS): beide ebenfalls `PLAY SELF-TEST FAILED`.
- Ablaufprobe mit Attrappen (curl liefert synthetische Seiten im Markup von play.php, occ, docker und sqlite3 liefern Zustände): before-revoke, after-revoke, check ergibt `PLAY CONTROL SHOWED THE DIFF p12a`, `... p12b`, `PHASE PASS play-leak`. Gegenproben: blockquote in p12a ergibt `P12 p12a FAIL grund=bytes_differ,not_a5`; T5 in p12b ergibt `P12 p12b FAIL grund=bytes_differ,not_a5`; p12a active ergibt INVALID ref_active; Quellen unreadable/vanished ergibt INVALID sources_differ; keine DB-Zeile ergibt INVALID ref_unknown; jeweils `PHASE FAIL play-leak`, Ausgang 1. Die Attrappen protokollierten nur lesende Aufrufe (curl GET/Login-POST, `occ audio_video_search:files --json --all`, `docker exec ... printf`, `docker cp`, `sqlite3 ... SELECT`).
- Verbotsliste: `grep -v '^\s*#' ci/discovery/playpage.sh | grep -cE 'audio_video_search_backend|php -r|python|INSERT|UPDATE|DELETE FROM'` ergibt 0; kein `sleep`.
- Workflow-Regeln: `play_findings` mit Positivkontrollen auf kaputten Kopien (python3, DELETE FROM, fremder docker exec, sleep; Kontrollzeile fehlt und Selbsttest übergangen; Kontroll-grep durch `true`, play-leak fehlt in der Liste, Urteil zählt 21; after-revoke vor before-revoke; Seiten fehlen im Artefakt; Kommentar wird ignoriert), jede liefert genau die erwarteten Befunde.

## Gates

- `bash -n` und `shellcheck -x` 0.11.0 (`uvx --from shellcheck-py==0.11.0.1 shellcheck.exe`) auf playpage.sh ohne Befund; ohne `-x` nur SC1091 (info), wie bei parity.sh.
- Run-Blöcke "Run the phases", "The verdict of all phases", "Collect the logs" einzeln mit shellcheck: keine neuen Befunde gegenüber HEAD (je dieselbe SC2181- bzw. SC2024-Altmeldung).
- actionlint (`uvx --from actionlint-py actionlint.exe -shellcheck=`) ohne Befund.
- `pytest tests/test_discovery_workflow.py tests/test_workflow_pins.py tests/test_workflows.py`: 124 passed (davon 7 neue play-Tests).
- Volle Backend-Suite: 1905 passed, 15 skipped (Arbeitsbaum enthält die fremde, nicht gestagte Änderung an test_model_download.py).
- ruff check, ruff format --check, pyright (latest, basic) 0 errors, vulture still.
- `npx playwright test --list --grep @preview`: vorher 156, nachher 156 Einträge; P12 in allen sechs Projekten gelistet; kein `test.fixme('P12`.

## Deviations from Plan

1. **[Rule 2] Zehnter und elfter Selbsttest-Fall:** "Verweis unbekannt" (keine Zeile in einer Quelle) und "Kontrolle mit Unterschied wird als SHOWED erkannt". Ohne den zweiten könnte eine kaputte `judge_control` jede Kontrolle als INVALID melden, ohne dass der Selbsttest es merkt.
2. **[Rule 1] "-" als fehlende Quelle:** `ref_state` meldet eine fehlende Zeile als "-"; `states_say` behandelt "-" wie leer (vor der Korrektur hätten zwei "-" als gleicher, nicht aktiver Zustand gegolten). Im Selbsttest durch den Fall ref-unknown abgedeckt.
3. **Signatur `ref_state FILEID` statt `ref_state USER FILEID`:** der Zustand hängt am Verweis je fileId, nicht an der Person.
4. **Regel `play_findings` geteilt** in `play_script_findings` (Skript) und `play_findings` (Skript plus Workflow), wegen der Zeilenlänge; zusätzlich Regeln für `sleep` und für `docker exec` mit etwas anderem als dem Pfad von state.db.
5. **Testname `test_the_flow_rule_fires_on_a_missing_phase`** auf die neue Liste angepasst (die Positivkontrolle nimmt search-parity aus der Liste, play-leak bleibt).
6. ids.env-Schlüssel wie im Plan (`ID_ANA_SMB_REDE_GESPERRT_WAV`, `ID_ANA_REDE_GETEILT_WAV`, `ID_ANA_PRIVAT_P_WEBM`, `ID_CEM_SMB_WIDERRUF_WEBM`), in topology.sh nachgelesen; keine Abweichung.

## Erst der echte Lauf zeigt (Plan 03-20)

1. Ob Basic Auth die Abspielseite liefert oder die Sitzung nötig ist (Zeile NOTE in `compare-play-leak.txt`, `play-before-revoke.txt`, `play-after-revoke.txt`); ob der Login-POST mit dem requesttoken auf Nextcloud 33 bis 35 klappt.
2. Ob ana `SMB/rede-gesperrt.wav` und cem `SMB/widerruf.webm` nach reprove im Zustand Bereit öffnen (Findling A6); sonst INVALID probe_not_ready, dann OC-2.
3. Ob beide Verweise in occ files und in der state.db-Kopie denselben Zustand ungleich active haben (erwartet unreadable) und überhaupt eine Zeile existiert.
4. Ob die Kontrollen den Unterschied zeigen: ana rede-geteilt.wav mit Clip-Wort im blockquote zur Zeitmarke des Treffers; cem widerruf.webm vor dem Entzug mit Grund-Satz (Testton, erwartet T5) oder Text, und ob die Vorschau nach `parity.sh settle` dafür fertig ist.
5. Ob `Accept-Language: en` für ana und cem dieselben EN-Texte liefert; sonst FAIL reference_changed_since_reprove bzw. not_a5.
6. Ob der eingebaute PHP-Server die Seite mit dem Ausschnitt-Aufruf an den Container ohne Hänger ausliefert (wie bei der Suche in search-parity).
7. Urteil "22 of 22 phases passed", Laufzeit in den Fristen, Artefakt mit play-*.html; leak-control unverändert grün.

## Offene Owner-Fragen

- Keine neue. OC-2 (INVALID wegen Seite nicht Bereit) wird erst in 03-20 nach dem ersten echten Lauf entschieden.

## Known Stubs

Keine. P12 in preview.spec.ts ist bewusst ein übersprungener Fall mit Verweis auf die echte Probe in discovery-e2e.yml.

## Threat Flags

Keine neue Angriffsfläche: playpage.sh liest nur (GET-Seiten, Login-POST der Testnutzer, occ files, Kopie von state.db).

## Commits

- aa87404 ci(03-18b): Abspielseiten-Probe P12 mit Selbsttest und Positivkontrollen
- 0f231f3 ci(03-18b): Phase play-leak mit P12 auf der Abspielseite in der Abnahme

## Self-Check: PASSED
