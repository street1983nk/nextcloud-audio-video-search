---
phase: 03-vorschau-transkripte-in-der-suche
plan: 18b
type: execute
wave: 7
depends_on: ["03-17", "03-18"]
files_modified:
  - ci/discovery/playpage.sh
  - ci/discovery/README.md
  - ci/discovery/common.sh
  - .github/workflows/discovery-e2e.yml
  - backend/tests/test_discovery_workflow.py
  - ci/playwright/preview.spec.ts
autonomous: false
requirements: [SRCH-02, SRCH-03]

must_haves:
  truths:
    - "discovery-e2e.yml hat eine eigene Phase play-leak (22. Phase), die P12 auf der echten Abspielseite prüft: Seite im Zustand Bereit, Verweis der Datei nicht active, Ausschnitt-Block byte-gleich zum A5-Block"
    - "P12 wird zweimal geprüft: nie active (Samba-Sperre, ana, SMB/rede-gesperrt.wav, gleicher Sprachclip wie ihre aktive Kopie rede-geteilt.wav) und entzogen (cem, SMB/widerruf.webm, nach revoke_cem und reconcile --reprove, vor vanish)"
    - "Jede der beiden Proben hat eine Live-Positivkontrolle derselben Person, deren Block sich vom A5-Block unterscheidet; ohne sichtbaren Unterschied lautet das Ergebnis INVALID, nie PASS"
    - "Gegenprobe mit unabhängigem Muster: neben dem Byte-Vergleich eine Strukturprüfung gegen die wörtlichen Texte der UI-SPEC, und der Zustand des Verweises kommt aus zwei getrennten Quellen (occ audio_video_search:files und eine Kopie von state.db mit sqlite3 des Runners)"
    - "Der Selbsttest von playpage.sh läuft ohne Netz und ohne Instanz und muss jede eingebaute Verschiebung einzeln als FAIL bzw. INVALID sehen, sonst gibt es kein Urteil"
    - "preview.spec.ts führt P12 nicht mehr als test.fixme, sondern als übersprungenen Fall mit Verweis auf die Phase play-leak; --list zeigt P12 weiter"
  artifacts:
    - path: "ci/discovery/playpage.sh"
      provides: "Abspielseiten-Probe P12 mit Selbsttest, Positivkontrollen und Urteil"
      contains: "PLAY CONTROL SHOWED THE DIFF"
    - path: ".github/workflows/discovery-e2e.yml"
      provides: "Phase play-leak, Mitschnitt im Phasenlauf reprove, Urteil über 22 Phasen"
      contains: "play-leak"
    - path: "backend/tests/test_discovery_workflow.py"
      provides: "Regeln für play-leak mit Positivkontrollen"
      contains: "play-leak"
  key_links:
    - from: ".github/workflows/discovery-e2e.yml"
      to: "ci/discovery/playpage.sh check"
      via: "Phase play-leak mit eigenem Zweig und continue"
      pattern: "PHASE PASS play-leak"
    - from: ".github/workflows/discovery-e2e.yml"
      to: "ci/discovery/playpage.sh before-revoke / after-revoke"
      via: "Phase reprove, vor der Operation und nach compare.sh"
      pattern: "playpage.sh\" (before|after)-revoke"
    - from: "ci/playwright/preview.spec.ts"
      to: "Phase play-leak"
      via: "Annotation am übersprungenen Fall P12"
      pattern: "play-leak"
---

## Phase Goal

**As a** Nutzerin oder Nutzer einer Nextcloud-Instanz, **I want to** gesprochenen Text meiner Aufnahmen in Minuten über die normale Nextcloud-Suche finden, als vorläufig gekennzeichnet und nur in Dateien, die ich lesen darf, **so that** ich meine Aufnahmen durchsuchen kann, ohne dass ein Inhalt den Server verlässt.

<objective>
Folgeplan zu 03-18. Abnahmefall P12 der UI-SPEC ("Leck-Probe: Verweis nicht active (z. B. entzogene Freigabe, Datei noch lesbar über anderen Weg ohne active-Verweis)", Erwartung "Ausschnitt-Block gleich P4") bekommt eine eigene echte Probe auf der Abspielseite in discovery-e2e.yml, weil deploy-harp ihn nicht erreicht.

**D-03-24 (Owner-Entscheid 14.11.2026):** P12 ist in deploy-harp nicht erreichbar (der Container führt einen Verweis je fileId und liest als Eigentümer). Er bekommt eine EIGENE echte Probe auf der Abspielseite in discovery-e2e.yml (Topologie mit Samba-Sperre bzw. files_accesscontrol, wie dort für die Suche schon vorhanden). Der test.fixme für P12 in preview.spec.ts wird durch den echten Test ersetzt bzw. verweist auf ihn. Erwartetes Verhalten genau aus UI-SPEC/CONTEXT ableiten, nicht erfinden; wo unklar, Owner-Checkpoint. Positivkontrolle und Gegenprobe mit unabhängigem Muster. S4 bleibt wie gebaut.

Purpose: Erfolgskriterium 3 der Phase und die Leck-Regel der Abspielseite (D-02-15c, D-02-16, D-03-13) für den Fall "Verweis nicht active" von außen belegen, nicht nur über Unit-Tests (03-14, 03-16) und die Suche (03-17).
Output: ci/discovery/playpage.sh, Phase play-leak im Workflow, Workflow-Regeln, Verweis in preview.spec.ts.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-UI-SPEC.md
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-18-SUMMARY.md
@.planning/phases/03-vorschau-transkripte-in-der-suche/03-17-SUMMARY.md
@.github/workflows/discovery-e2e.yml
@ci/discovery/topology.sh
@ci/discovery/parity.sh
@ci/discovery/compare.sh

Regeln: Commits nur lokal mit `git -c user.name=street1983nk -c user.email=k.cherif@outlook.de commit`, ohne Claude-Session- oder Co-Authored-By-Zeile, nie "closes/fixes/resolves #N". Kein Push, kein Workflow-Start (Lauf in Plan 03-20). KEIN lokales Docker, kein Lauf gegen eine Instanz. STATE.md, ROADMAP.md, REQUIREMENTS.md nicht schreiben. Nie `python -` oder `python -c`; Hilfsskripte nur als Datei im Scratch-Ordner. Deutsche Texte mit echten Umlauten, keine Gedankenstriche (U+2013, U+2014), keine Emojis; Code-Kommentare und Ausgaben der Skripte englisch wie in ci/discovery.

**Herleitung der Erwartung (nicht erfinden):**
- UI-SPEC Fläche 2, Leck-Regel: "Für jeden anderen Verweis antwortet er wie für eine unbekannte Datei: known: false, ohne Grund. Die PHP-Seite zeigt dann A5." und "A5 muss für ausgeschlossen und unbekannt byte-gleich sein".
- UI-SPEC Prüfvertrag P12: Ausschnitt-Block gleich P4 (P4 = A5, kein Transkript).
- UI-SPEC: Der Block erscheint nur im Seitenzustand "Bereit"; in allen anderen Seitenzuständen fehlt er. Eine Probe ohne Block beweist P12 nicht und ist INVALID (siehe Owner-Checkpoint OC-2).
- 03-CONTEXT D-03-13: "für jeden nicht erlaubten Verweis antwortet sie wie für eine Datei ohne Transkript".
- 03-14: /excerpt liefert für jeden nicht aktiven Verweis genau `{"known":false}`; 03-16: known false ergibt A5.
- Texte der Erwartung wörtlich aus der UI-SPEC-Tabelle (EN, weil die Proben mit `Accept-Language: en` laufen), nicht aus den l10n-Katalogen: Label "Excerpt at this point", A5 "There is no transcript for this file yet.", T5 "No speech was found in this file, for example because it only contains music, silence or noise.".

**Warum diese Orte (aus der vorhandenen Topologie, nichts Neues an Samba oder Nextcloud):**
- P12a "nie active": `SMB/rede-gesperrt.wav` von ana (03-17, parity_place): DENY READ für ana, bevor Nextcloud die Datei sieht. Nextcloud listet die Datei und `isReadable()` sagt ja (Findling-Messung A6, D-02-01a), also ist die Abspielseite im Zustand Bereit; der Lesebeweis scheitert, der Verweis ist nicht active. Derselbe Clip ist für ana über einen anderen Weg lesbar und transkribiert: `rede-geteilt.wav` in ihrem Home (nach parity_revoke weiter active, nur die Freigabe an cem ist weg). Genau der Fall der UI-SPEC: Inhalt über anderen Weg lesbar, dieser Verweis nicht active.
- P12b "entzogen": `SMB/widerruf.webm` von cem (Phase reprove: revoke_cem setzt DENY READ für cem, `reconcile --reprove`; compare.sh prüft dort schon `reprove_unreadable`). Vorher ist cems Verweis active (Positivkontrolle), danach unreadable; ana liest dieselbe Datei weiter über ihren eigenen Zugang. Die Probe muss vor der Phase vanish laufen, die cems SMB-Zugang entfernt.
- files_accesscontrol (`rede-sperre.wav`) taugt NICHT für P12: die Regel nimmt das Leserecht aus dem Cache-Eintrag (FileAccess.php, Kopfkommentar), die Seite ist nicht Bereit und zeigt keinen Block; dort gibt es nichts zu vergleichen. Im SUMMARY so begründen.
- Referenz für "gleich P4": ana öffnet `privat/p.webm` (Ordner privat ist vor dem ersten Lauf ausgeschlossen). Das ist A5 über den Ausschluss-Zweig; dass dieser Block byte-gleich zum Block einer unbekannten Datei ist, verlangt die UI-SPEC und belegen 03-16 (PHPUnit, Byte-Vergleich) und P11 in deploy-harp. Die Strukturprüfung (zweites Muster) prüft den A5-Text unabhängig davon.

**S4** bleibt wie in 03-18 gebaut (zwei Suchen desselben Nutzers; Owner 14.11.2026: zwei Suchen reichen). Nicht Teil dieses Plans, nur im SUMMARY vermerken.

Lokal grün vor jedem Commit: `bash -n` und `bash ci/discovery/playpage.sh --self-test` (läuft offline), shellcheck 0.11.0 über `uvx shellcheck-py==0.11.0.1` (wie 03-17), actionlint über `uvx actionlint-py` mit `-shellcheck=` (Hänger unter Windows, Run-Blöcke einzeln mit shellcheck), `cd backend && uv run pytest tests/test_discovery_workflow.py tests/test_workflow_pins.py tests/test_workflows.py -q`, ruff check, ruff format --check, pyright (PYRIGHT_PYTHON_FORCE_VERSION=latest), vulture, `cd ci/playwright && npx playwright test --list --grep @preview`.

<interfaces>
Vorhandene Bausteine (nicht neu erfinden, sourcen bzw. nachbauen):
- ci/discovery/common.sh: `fail`, `password_of USER`, `get_id KEY`, `need_id KEY`, `search_ids USER TERM`, `PHASES=(...)` (Reihenfolge der Phasen, Test vergleicht sie mit PHASES in test_discovery_workflow.py), `WORK`.
- ci/discovery/compare.sh: `occ_files OUT` (`occ audio_video_search:files --json --all`, jq auf ein Array), `field_of FILE ID FIELD`, `state_of FILE ID`, `state_db SQL` (docker cp von state.db, -wal, -shm aus `${EXAPP_CONTAINER}` in `${WORK}/statedb`, dann sqlite3 des Runners). compare.sh ist kein Sourcing-Ziel; die zwei Hilfen in playpage.sh mit demselben Muster nachbauen.
- ci/discovery/parity.sh `product_of`: Form der OCS-Suche (`/ocs/v2.php/search/providers/audio_video_search/search`, `term`, `limit`, Cursor), Einträge mit `resourceUrl`, `attributes.fileId`.
- ids.env-Schlüssel (topology.sh `id_key`, aus `record ana SMB/rede-gesperrt.wav` usw.): `ID_ANA_SMB_REDE_GESPERRT_WAV`, `ID_ANA_REDE_GETEILT_WAV`, `ID_ANA_PRIVAT_P_WEBM`, `ID_CEM_SMB_WIDERRUF_WEBM`, `ID_ANA_SMB_WIDERRUF_WEBM`. Vor dem Bau in topology.sh nachlesen (record-Aufrufe), Abweichungen im SUMMARY.
- Abspielroute: `GET ${NC_URL}/index.php/apps/audio_video_search/play/{fileId}?t=SEKUNDEN` (PageController::play, NoAdminRequired, NoCSRFRequired).
- Markup des Blocks (php/templates/play.php Zeilen 207 bis 223): `<section class="avs-excerpt" aria-labelledby="avs-excerpt-label">`, darin `p.avs-excerpt__label`, dann genau eines von `blockquote.avs-excerpt__text` (+ `p.avs-excerpt__note`) oder `p.avs-excerpt__hint`, Ende `</section>`.
- Workflow: `EXAPP_CONTAINER` und `AVS_SPEECH_WORD` stehen über GITHUB_ENV im Job; Schritt "Run the phases" mit Schleife `for phase in ... search-parity; do`; search-parity hat einen eigenen Zweig mit `continue`; Urteil `[ "${passed}" = 21 ]`; "Collect the logs" kopiert Dateien nach logs/.
- test_discovery_workflow.py: `PHASES`-Tupel (Zeile ab 530), `script_findings`, `flow_findings` (RECONCILE_AFTER verlangt die Zeile `reprove) bash "${d}/topology.sh" revoke_cem && ./occ audio_video_search:reconcile --reprove ;;` unverändert), `parity_findings` mit Regel "the verdict does not count 21 phases", `PARITY_FORBIDDEN`.
</interfaces>
</context>

<tasks>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 1: Owner-Checkpoint OC-1, Screenshot für P12</name>
  <decision>Die UI-SPEC verlangt für P12 einen Screenshot 1280 hell. discovery-e2e.yml hat keinen Browser; die Probe holt die Seite mit curl und vergleicht das server-gerenderte HTML. Wie wird P12 bebildert?</decision>
  <context>Erwartung und Leck-Prüfung sind aus UI-SPEC und CONTEXT eindeutig (A5, byte-gleich). Offen ist nur der Bildbeleg aus dem Prüfvertrag. Ein byte-gleicher Block mit demselben CSS sieht aus wie der Block von P4, der in deploy-harp in 1280 hell und dunkel aufgenommen wird; das ist aber ein Schluss, kein Bild.</context>
  <options>
    <option id="html-beleg">
      <name>HTML-Beleg statt Bild (Empfehlung)</name>
      <pros>Kein Node, kein Browser im 150-min-Job; die gespeicherten Seiten (play-p12a.html, play-p12b.html, Referenz) liegen im Artefakt; der Byte-Vergleich ist strenger als ein Bildvergleich; für die gemeinsame Abnahme (03-21) zeigt P4 das Aussehen.</pros>
      <cons>Kein eigenes Bild von P12 im Abnahmeordner; Abweichung vom Wortlaut des Prüfvertrags, im SUMMARY und in 03-21 zu nennen.</cons>
    </option>
    <option id="playwright-in-discovery">
      <name>Playwright in discovery-e2e.yml für ein Bild 1280 hell</name>
      <pros>Prüfvertrag wörtlich erfüllt.</pros>
      <cons>Node, Chromium und Login im Job discovery (Laufzeit, neue Fehlerquellen, eigene Spec-Datei); eigener Folgeplan 03-18c, weil das den Umfang dieses Plans sprengt. Dieser Plan läuft trotzdem wie beschrieben.</cons>
    </option>
  </options>
  <resume-signal>"html-beleg" oder "playwright-in-discovery"; Antwort wörtlich ins SUMMARY. Bei "playwright-in-discovery" nach diesem Plan 03-18c planen lassen (vor 03-19).</resume-signal>
  <files>keine (nur die Owner-Antwort, sie steht im SUMMARY)</files>
  <action>Owner die zwei Optionen zeigen (Empfehlung html-beleg) und die Antwort abwarten. Nichts bauen, bevor die Antwort da ist; Task 2 und Task 3 laufen bei beiden Antworten gleich, bei "playwright-in-discovery" kommt danach Folgeplan 03-18c.</action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_discovery_workflow.py -x -q</automated>
  </verify>
  <done>Owner-Antwort zu OC-1 liegt vor und ist für das SUMMARY notiert.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: playpage.sh mit Selbsttest, Positivkontrollen und Urteil</name>
  <files>ci/discovery/playpage.sh, ci/discovery/README.md</files>
  <read_first>
    - ci/discovery/common.sh (Hilfen, WORK, Sourcing-Muster), ci/discovery/parity.sh (Aufbau mit Selbsttest, cmd_*-Muster, product_of, Ausgabezeilen PASS/FAIL), ci/discovery/compare.sh Zeilen 37 bis 115 (occ_files, field_of, state_of, state_db)
    - ci/discovery/topology.sh Zeilen 400 bis 445 (record, Schlüssel), 660 bis 760 (revoke_cem, vanish_cem, parity_place, parity_revoke)
    - php/templates/play.php Zeilen 200 bis 225, php/lib/Controller/PageController.php Zeilen 120 bis 175
    - .planning/phases/03-vorschau-transkripte-in-der-suche/03-UI-SPEC.md Abschnitte Fläche 2 und Prüfvertrag (Texte A5, T5, Label)
  </read_first>
  <behavior>
    - Selbsttest (offline, synthetische Seiten in einem mktemp-Ordner): Probe gleich Referenz ergibt PASS; Probe mit blockquote ergibt FAIL; Probe mit T5-Satz statt A5 ergibt FAIL; Probe mit einem zusätzlichen Leerzeichen im Block ergibt FAIL im Byte-Vergleich, während die Strukturprüfung allein PASS sagt (zeigt, dass die Muster getrennt sind); Probe mit geändertem A5-Text bei gleicher Struktur ergibt FAIL in beiden Mustern; Seite ohne section.avs-excerpt (404-Seite) ergibt INVALID; Kontrolle gleich Referenz ergibt INVALID; Zustand des Verweises "active" ergibt INVALID; die zwei Zustandsquellen widersprechen sich ergibt INVALID. Jede Verschiebung muss einzeln ihr erwartetes Ergebnis zeigen, sonst `PLAY SELF-TEST FAILED` und Ausgang ungleich 0.
    - Der Selbsttest ändert nichts außerhalb seines Temp-Ordners und braucht weder curl noch docker.
  </behavior>
  <action>Neues Skript ci/discovery/playpage.sh (set -uo pipefail, sourct common.sh wie parity.sh, ausführbar wie die anderen, Kopfkommentar englisch mit Verweis auf UI-SPEC P12, D-03-24, D-02-15c, D-02-16). Unterbefehle über `main`: `--self-test`, `before-revoke`, `after-revoke`, `check`.

Hilfen:
(a) `page USER FILEID SECONDS OUT`: holt die Abspielseite mit `curl -sS -m 60 -u USER:PASS -H 'Accept-Language: en' -w '%{http_code}'` und speichert den Körper; ist die Antwort nicht HTTP 200 mit HTML, Zeile `NOTE basic auth refused (http=N), signing in with a session` und zweiter Versuch über eine Sitzung (Cookie-Jar in WORK, GET `/index.php/login`, `data-requesttoken` aus dem HTML, POST `/index.php/login` mit user, password, timezone=UTC, timezone_offset=0, requesttoken), dann dieselbe Seite. Welcher Weg genommen wurde, steht in der Ausgabe (Prüfpunkt 03-20).
(b) `block PAGE`: schneidet mit awk die Bytes von der Zeile mit `<section class="avs-excerpt"` bis zum ersten `</section>` aus; leer, wenn es den Block nicht gibt.
(c) `ready PAGE`: Seite hat den Block und ein Medium (`id="avs-media"` laut Template, vor dem Bau nachlesen); sonst ist die Seite nicht Bereit.
(d) `same_bytes A B`: `cmp -s` der zwei Blöcke (Muster 1).
(e) `is_a5 BLOCK`: Muster 2, unabhängig vom Byte-Vergleich: genau ein `class="avs-excerpt__label"` mit dem Text "Excerpt at this point", genau ein `class="avs-excerpt__hint"` mit genau dem A5-Text der UI-SPEC, kein `avs-excerpt__text`, kein `avs-excerpt__note`, das Clip-Wort (`AVS_SPEECH_WORD`, ohne Groß/klein) kommt nicht vor, kein Satz T5. Texte als Konstanten im Skript mit Kommentar "UI-SPEC table, not the catalogues".
(f) `ref_state USER FILEID`: Zustand des Verweises aus zwei Quellen: `occ audio_video_search:files --json --all` (Muster von compare.sh occ_files/state_of) und `state_db "SELECT state FROM file_ref WHERE file_id = N"` über eine Kopie von state.db (Muster von compare.sh state_db, nur lesen, nie schreiben). Beide müssen eine Zeile haben, beide müssen übereinstimmen, keiner darf active sein; fehlt die Zeile, ist das der Fall "unbekannt", nicht P12: INVALID mit Grund.
(g) `hit_seconds USER FILEID`: Zeitmarke des ersten Treffers von FILEID in der OCS-Suche nach AVS_SPEECH_WORD (Form wie parity.sh product_of, `t` aus `resourceUrl`); ohne Treffer INVALID.
(h) `verdict NAME`: liest die Teilergebnisse und schreibt je Probe `P12 NAME PASS|FAIL|INVALID grund=...`; Zeile `PLAY CONTROL SHOWED THE DIFF NAME` nur, wenn die Kontrolle nicht gleich der Referenz ist und nicht A5 nach Muster 2.

Ablauf:
`before-revoke` (Phase reprove, vor revoke_cem): Referenz ana `ID_ANA_PRIVAT_P_WEBM` bei t=0 (muss Bereit und is_a5 sein, sonst INVALID), Kontrolle cem `ID_CEM_SMB_WIDERRUF_WEBM` bei t=0 (Bereit, Verweis active in beiden Quellen, Block ungleich Referenz: Grund-Satz oder Text), Seiten als `play-p12b-reference.html`, `play-p12b-control.html` unter WORK sichern, Ergebnisse in `${WORK}/play-p12b.state`.
`after-revoke` (Phase reprove, nach compare.sh): cem dieselbe fileId bei t=0 als `play-p12b-probe.html`; Bereit (sonst INVALID, OC-2), ref_state nicht active, same_bytes gegen die Referenz aus before-revoke, is_a5; Zeilen in `${WORK}/play-p12b.state` anhängen. Gibt nie selbst ein Phasenurteil.
`check` (Phase play-leak): erst den Selbsttest laufen lassen (ohne `PLAY SELF-TEST PASSED` kein Urteil, Zeile `PLAY SELF-TEST FAILED`); P12a: Referenz ana privat/p.webm neu holen und gegen die Referenz von before-revoke vergleichen (Stabilität, sonst FAIL); t aus hit_seconds für `ID_ANA_REDE_GETEILT_WAV`; Kontrolle ana rede-geteilt.wav bei t (Bereit, active, blockquote enthält das Clip-Wort, ungleich Referenz); Probe ana `SMB/rede-gesperrt.wav` bei demselben t (Bereit, ref_state nicht active, fileId nicht in `search_ids ana AVS_SPEECH_WORD`, same_bytes und is_a5); dann P12b aus der Datei des Phasenlaufs reprove urteilen; `PHASE PASS play-leak` nur, wenn Selbsttest, beide Kontrollzeilen und beide Proben PASS sind, sonst `PHASE FAIL play-leak` mit allen FAIL/INVALID-Zeilen. INVALID ist nie PASS. Alle Seiten und `play-*.txt` nach `${WORK}` und als Kopie ins Arbeitsverzeichnis (für "Collect the logs").

Verboten in playpage.sh (Test in Task 3 prüft das): `audio_video_search_backend`, `php -r`, `python`, `INSERT`, `UPDATE`, `DELETE FROM`, `docker exec ... sh -c` mit etwas anderem als dem Pfad von state.db (Muster von compare.sh). Keine festen Wartezeiten und kein sleep: die Phase wartet vorher über compare.sh bzw. parity.sh.

README.md in ci/discovery: Absatz zu playpage.sh (P12, zwei Fälle, Referenz, zwei Muster, INVALID-Regel, warum files_accesscontrol nicht passt), englisch wie der Rest.</action>
  <verify>
    <automated>bash -n ci/discovery/playpage.sh && out=$(mktemp) && bash ci/discovery/playpage.sh --self-test > "$out" && grep -qx 'PLAY SELF-TEST PASSED' "$out" && uvx shellcheck-py==0.11.0.1 ci/discovery/playpage.sh</automated>
  </verify>
  <acceptance_criteria>
    - `bash ci/discovery/playpage.sh --self-test` endet mit 0 und `PLAY SELF-TEST PASSED`; jeder der neun Fälle steht mit erwartetem und gesehenem Ergebnis in der Ausgabe.
    - Gegenprobe des Selbsttests: in einer Scratch-Kopie `same_bytes` auf immer wahr gesetzt ergibt `PLAY SELF-TEST FAILED`; ebenso `is_a5` auf immer wahr. Beide Mutationen nur in der Kopie, Ergebnis im SUMMARY.
    - `grep -v '^\s*#' ci/discovery/playpage.sh | grep -cE 'audio_video_search_backend|php -r|python|INSERT|UPDATE|DELETE FROM'` ergibt 0.
    - Die Texte A5, T5 und das Label stehen wörtlich wie in der UI-SPEC-Tabelle im Skript.
  </acceptance_criteria>
  <done>Commit `ci(03-18b): Abspielseiten-Probe P12 mit Selbsttest und Positivkontrollen`.</done>
</task>

<task type="auto">
  <name>Task 3: Phase play-leak im Workflow, Regeln, Verweis in preview.spec.ts</name>
  <files>.github/workflows/discovery-e2e.yml, ci/discovery/common.sh, backend/tests/test_discovery_workflow.py, ci/playwright/preview.spec.ts</files>
  <read_first>
    - .github/workflows/discovery-e2e.yml Zeilen 438 bis 566 (settle, Run the phases, Urteil, Collect the logs)
    - backend/tests/test_discovery_workflow.py Zeilen 520 bis 720 (PHASES, script_findings, flow_findings) und 1160 bis 1270 (PARITY_FORBIDDEN, parity_findings und ihre Positivkontrollen)
    - ci/playwright/preview.spec.ts Zeilen 736 bis 752 (P12 und P13 als test.fixme)
  </read_first>
  <action>discovery-e2e.yml, Schritt "Run the phases" (D-03-24):
1. Phasenliste um `play-leak` nach `search-parity` ergänzen; common.sh `PHASES` ebenso (gleiche Reihenfolge).
2. Phase reprove: vor dem `case` ein eigener Block `if [ "${phase}" = reprove ]; then bash "${d}/playpage.sh" before-revoke | tee play-before-revoke.txt; fi`, nach `compare.sh "${phase}"` ein Block mit `after-revoke` und `tee play-after-revoke.txt`. Die Zeile `reprove) bash "${d}/topology.sh" revoke_cem && ./occ audio_video_search:reconcile --reprove ;;` bleibt Zeichen für Zeichen (flow_findings). Diese Blöcke ändern das Urteil von reprove nicht.
3. Phase play-leak: eigener Zweig wie search-parity mit `continue`: `bash "${d}/playpage.sh" check | tee "compare-${phase}.txt"`, FAIL-, INVALID- und SELF-TEST-FAILED-Zeilen nach results.txt, `PHASE PASS play-leak` nur mit `ok=1`, beiden Zeilen `PLAY CONTROL SHOWED THE DIFF p12a` und `... p12b` (grep -qx) und `PHASE PASS play-leak` in der Datei.
4. Urteil: `echo "${passed} of 22 phases passed"` und `[ "${passed}" = 22 ]`.
5. "Collect the logs": zusätzlich `play-*.txt` und `play-*.html` nach logs/.
6. Kopfkommentar der Schleife: ein Satz zu play-leak (P12, D-03-24). Job- und Schrittfristen bleiben (wenige curl-Aufrufe); falls doch geändert, mit Begründung im Kommentar.
Job leak-control bleibt unberührt.

test_discovery_workflow.py: PHASES-Tupel um play-leak; Regel "the verdict does not count 22 phases" (bestehende Regel und ihre Positivkontrolle von 21 auf 22 umstellen); neue Regel `play_findings(script, workflow)` mit: Unterbefehle `--self-test`, `before-revoke`, `after-revoke`, `check` vorhanden; Kontrollzeile und `PHASE PASS play-leak` im Skript; Verbotsliste PLAY_FORBIDDEN (`audio_video_search_backend`, `php -r`, `python`, `INSERT`, `UPDATE`, `DELETE FROM`) in Nicht-Kommentarzeilen; im Workflow before-revoke vor dem `case` und after-revoke nach compare.sh innerhalb der Schleife, play-leak-Zweig mit beiden grep -qx auf die Kontrollzeilen, `play-*.html` in Collect the logs. Positivkontrollen wie bei parity_findings: je eine kaputte Kopie (Kontroll-grep durch `true` ersetzt, after-revoke vor before-revoke, `python3` im Skript, play-leak fehlt in der Liste, Urteil zählt 21) muss genau die erwarteten Befunde liefern.

preview.spec.ts: `test.fixme('P12 ...')` ersetzen durch einen übersprungenen Fall mit demselben Titel und `@preview`, der als Annotation `{ type: 'covered by', description: 'discovery-e2e.yml phase play-leak, ci/discovery/playpage.sh (plan 03-18b, D-03-24)' }` trägt und mit `test.skip(true, ...)` und derselben Begründung übersprungen wird. Den Kommentar darüber auf den neuen Stand bringen (deploy-harp erreicht den Zustand nicht; echte Probe in discovery; Unit-Belege 03-14, 03-16 bleiben). P13 bleibt test.fixme wie gebaut. Kein waitForTimeout.</action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_discovery_workflow.py tests/test_workflow_pins.py tests/test_workflows.py -q && uv run ruff check . && uv run ruff format --check . && cd ../ci/playwright && npx playwright test --list --grep @preview | grep -c "P12"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "play-leak" .github/workflows/discovery-e2e.yml ci/discovery/common.sh` zeigt Phasenliste, Zweig und PHASES; `grep -n '= 22 \]' .github/workflows/discovery-e2e.yml` zeigt das Urteil.
    - `grep -n "playpage.sh\" before-revoke\|playpage.sh\" after-revoke" .github/workflows/discovery-e2e.yml` zeigt beide Aufrufe in der Phase reprove.
    - `grep -n "test.fixme('P12" ci/playwright/preview.spec.ts` liefert nichts; `npx playwright test --list --grep @preview` listet P12 weiter (Zählung im SUMMARY, vorher 156 Einträge).
    - actionlint ohne Befund; Run-Block "Run the phases" einzeln mit shellcheck ohne neuen Befund gegenüber HEAD.
    - pyright (latest) und vulture still; volle Backend-Suite grün (Zahl im SUMMARY).
  </acceptance_criteria>
  <done>Commit `ci(03-18b): Phase play-leak mit P12 auf der Abspielseite in der Abnahme`.</done>
</task>

</tasks>

<owner_checkpoints>
- **OC-1 (Task 1, jetzt):** Bildbeleg für P12, siehe Task 1.
- **OC-2 (in Plan 03-20, nach dem ersten echten Lauf):** Zeigt eine Probe INVALID, weil die Seite nicht Bereit ist (z. B. `isReadable()` auf einer Nextcloud-Version für die SMB-Sperre doch falsch, Seite 404 ohne Block), ist das laut UI-SPEC leckfrei (der Block fehlt außerhalb von Bereit), beweist P12 aber nicht. Die UI-SPEC sagt nicht, was dann gilt. Der Owner entscheidet: anderer Ort in der Topologie suchen, oder P12 für diese Version mit Beleg als nicht erreichbar führen. Die Phase bleibt bis dahin rot; INVALID wird nie als PASS gewertet.
</owner_checkpoints>

<ci_checkpoints_for_03_20>
Erst der echte Lauf zeigt (Plan 03-20 prüft und nennt es im SUMMARY):
1. Ob Nextcloud die Abspielseite mit Basic Auth ausliefert oder playpage.sh auf die Sitzung ausweicht (Zeile NOTE in compare-play-leak.txt bzw. play-*.txt).
2. Ob ana `SMB/rede-gesperrt.wav` und cem nach reprove `SMB/widerruf.webm` im Zustand Bereit öffnen (Findling-Befund A6 für Nextcloud 33, 34, 35); sonst OC-2.
3. Ob beide Verweise in occ files und in der state.db-Kopie denselben Zustand ungleich active haben (erwartet unreadable) und für die Probe überhaupt eine Zeile existiert.
4. Ob die Positivkontrollen den Unterschied zeigen: ana rede-geteilt.wav mit Clip-Wort im blockquote, cem widerruf.webm vor dem Entzug mit Grund-Satz oder Text (setzt voraus, dass die Vorschau der Testmedien nach parity.sh settle fertig ist).
5. Ob `Accept-Language: en` für ana und cem dieselben EN-Texte liefert (kein Sprachwert der Testnutzer); sonst FAIL im Stabilitätsvergleich der Referenz.
6. Urteil "22 of 22 phases passed", Laufzeit innerhalb der bestehenden Fristen, Artefakt mit play-*.html.
7. leak-control unverändert grün.
</ci_checkpoints_for_03_20>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Testharness nach Instanz | Die Abnahme darf nichts beschönigen; eine blinde Probe darf nicht als PASS zählen |
| Abspielseite nach Container | Für nicht aktive Verweise darf kein Grund, keine Stufe und kein Text durchkommen |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-85 | Information Disclosure | Abspielseite für nicht aktiven Verweis (P12a, P12b) | mitigate | Byte-Vergleich des Blocks gegen A5 und Strukturprüfung mit UI-SPEC-Texten, Clip-Wort und T5 dürfen nicht vorkommen |
| T-03-86 | Repudiation | Probe prüft einen anderen Fall als P12 (Verweis doch active oder unbekannt, Seite nicht Bereit) | mitigate | ref_state aus zwei Quellen, Bereit-Prüfung, sonst INVALID; INVALID nie PASS |
| T-03-87 | Repudiation | Vergleich kann nicht scheitern | mitigate | Offline-Selbsttest mit neun Verschiebungen und Mutationsproben, Live-Positivkontrolle je Probe mit Zeile PLAY CONTROL SHOWED THE DIFF |
| T-03-88 | Tampering | Probe verändert den Zustand der Instanz | mitigate | playpage.sh liest nur (Verbotsliste im Test, state.db nur als Kopie mit sqlite3 des Runners) |
</threat_model>

<verification>
Selbsttest offline grün, Workflow-Regeln mit Positivkontrollen grün, Spec übersetzt; echter Lauf in Plan 03-20 mit den Prüfpunkten oben.
</verification>

<success_criteria>
- P12 hat eine eigene, scheiterfähige Probe auf der echten Abspielseite in discovery-e2e.yml, für "nie active" und "entzogen".
- Jede Probe hat Positivkontrolle und Gegenprobe mit unabhängigem Muster; INVALID wird nie PASS.
- preview.spec.ts verweist für P12 auf die Phase play-leak; S4 unverändert und im SUMMARY vermerkt.
</success_criteria>

<output>
Create `.planning/phases/03-vorschau-transkripte-in-der-suche/03-18b-SUMMARY.md` when done
</output>
