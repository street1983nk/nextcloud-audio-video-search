---
phase: 02-erfassung-aller-dateien
plan: 15b
type: execute
wave: 6
depends_on: [02-13, 02-15]
files_modified:
  - backend/src/audio_video_search_backend/store/repo.py
  - backend/tests/test_restore_proof.py
  - backend/tests/test_intake.py
  - .planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md
  - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
autonomous: true
requirements: [DISC-03, DISC-06]

must_haves:
  truths:
    - "Ein aus dem Papierkorb wiederhergestellter Verweis mit Inhalt, für den der Lesebeweis verlangt ist (prefilter_key gesetzt, in der restore-Zeile oder am gespeicherten Verweis), kommt nicht als active zurück, sondern als state unreadable, stage probing, Versuche 0, next_try_at leer: er liefert bis zum BESTANDENEN eigenen Lesebeweis keinen Treffer (Owner 12.11.2026; ersetzt 'sofort active' aus must_have 3 von 02-15)"
    - "Gemessen wird 'kein Treffer' dort, wo Treffer entstehen: api/search.py gibt je Inhalt nur die Datei-IDs aus Store.file_ids_for_media aus, und die kennt nur state active"
    - "Erst confirm_proof (einziger Aufruf im Zweig outcome is ProofOutcome.OK in worker/capture.py) macht den Verweis wieder active und keyed und nimmt dem Inhalt die Verwaist-Marke"
    - "Die Erfassung beansprucht einen wiederhergestellten Verweis mit fälligem Beweis (unreadable, probing, media_id gesetzt) VOR gewöhnlicher Arbeit, auch vor einem Download mit kleinerer file_id"
    - "Kein Verhungern: jeder Verweis ist je Wiederherstellung genau einmal vorgezogen; nach dem Urteil steht er in keyed, failed oder pending und läuft in der gewöhnlichen Reihenfolge (next_try_at, Versuchszähler); ein hängender Speicher wird nach drei Zeitüberschreitungen vom Sperrkreis ohne Anfrage übergangen"
    - "Scheitert der Beweis, gelten die Regeln aus 02-13: unreadable mit Grund, Kopfabweichung löst und lädt voll (Nachtrag D-02-01a), locked mit neuem Versuch ohne verbrauchten Versuch; nie ein Treffer aus dem alten Transkript"
    - "Ohne Beweispflicht (kein prefilter_key, weder in der Zeile noch gespeichert) bleibt 02-15: sofort active und keyed, kein Beweis"
    - "Die Garantien aus 02-13 und 02-15 bleiben; tests/test_read_proof_gate.py ist unverändert und grün"
  artifacts:
    - path: "backend/src/audio_video_search_backend/store/repo.py"
      provides: "_restore (kein active vor dem Beweis bei Beweispflicht), _CLAIM_CAPTURE (Vorziehen), _INTAKE_ROW mit prefilter_key"
    - path: "backend/tests/test_restore_proof.py"
      provides: "Treffersperre an der Suche gemessen, Vorziehen, kein Verhungern, Papierkorb während des Beweises"
  key_links:
    - from: "Store._restore"
      to: "Store.file_ids_for_media"
      via: "state unreadable gibt keine Datei-ID an api/search.py"
      pattern: "unreadable"
    - from: "_CLAIM_CAPTURE"
      to: "worker/capture.py::_prove_again"
      via: "ORDER BY zieht unreadable, probing mit media_id vor"
      pattern: "ORDER BY CASE"
---

<objective>
Lesebeweis nach dem Wiederherstellen aus dem Papierkorb (Owner-Entscheid 12.11.2026, deferred-items.md Zeile 02-15 `_CLAIM_CAPTURE`): Der erneute Beweis wird in der Erfassung vorgezogen, und auf Speichern mit Beweispflicht gibt ein wiederhergestellter Verweis bis zum bestandenen Beweis keine Treffer.

Purpose: D-02-01a, D-02-09, D-02-12, T-02-55 ohne Fenster zwischen Wiederherstellen und Beweis.
Output: Änderung in store/repo.py, neue Testdatei, angepasster Bestandstest, Nachtrag in 02-CONTEXT.md.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md
@.planning/phases/02-erfassung-aller-dateien/02-13-SUMMARY.md
@.planning/phases/02-erfassung-aller-dateien/02-15-SUMMARY.md
@.planning/phases/02-erfassung-aller-dateien/deferred-items.md
@backend/src/audio_video_search_backend/store/repo.py
@backend/src/audio_video_search_backend/worker/capture.py
@backend/src/audio_video_search_backend/api/search.py

Regeln: Commits nur als `street1983nk <k.cherif@outlook.de>`, ohne Claude-Session-Zeile, nie "closes/fixes/resolves #N". Kein Push. Kein Docker, Python nur über uv. Gates vor Commit grün, seriell. STATE.md und ROADMAP.md bleiben unberührt.

Befunde am Bestand (vor dem Plan gelesen):
- Treffer entstehen in `api/search.py::_search` über `Store.file_ids_for_media` (`_FILE_IDS_FOR_MEDIA`: nur state active, Probe nur ohne nicht aktiven Verweis). PHP prüft danach nur noch Rechte. Ein Verweis in state unreadable gibt also keinen Treffer; PHP muss nicht geändert werden.
- "Lesebeweis nötig" macht der Bestand am prefilter_key fest: PHP (`QueueService::prefilterKey`) setzt ihn nur für externe Speicher mit Freigabe-Schlüssel (SMB, SFTP), sonst null; 02-15 nimmt in `_restore` genau `values["prefilter_key"] is not None`. Dieses Kriterium bleibt, kein neues.
- unreadable, probing mit media_id gibt es schon (02-15 Abweichung 3: Beweis war vor dem Papierkorb gescheitert). Der Zustand trägt die Bedeutung "wiederhergestellt, Beweis fällig, kein Treffer"; kein neuer Zustand, kein Schema-Feld.
- Nur `_restore` schreibt diese Kombination. Jedes Urteil der Erfassung verlässt sie (confirm_proof: keyed; fail_proof und Sperrkreis: failed; release_media und Download: keyed, failed oder pending ohne media).

Auslegung (strengere Lesart): Beweispflicht besteht, wenn die restore-Zeile ODER der gespeicherte Verweis einen prefilter_key trägt. PHP liefert null auch dann, wenn die Einstufung des Speichers gerade fehlt; ein Verweis, der seinen Inhalt über einen Speicher mit Beweispflicht bekommen hat, soll dadurch nicht ohne Beweis zurückkommen.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Rote Tests</name>
  <files>backend/tests/test_restore_proof.py, backend/tests/test_intake.py</files>
  <behavior>
    - restore und content mit gleichen Werten auf Speicher mit prefilter_key: Suche (`api.search._search` mit echtem Index) nennt die Datei nicht; state unreadable, stage probing, Grund leer, Versuche 0; Verwaist-Marke bleibt, wenn es der letzte Verweis war
    - Beweis bestanden: Suche nennt die Datei wieder, active, keyed, proved_at neu, Marke weg, kein Download
    - Beweis gescheitert (403, Zeitüberschreitung, access_control, gateway_failed, locked): Zustand, Grund, Versuche und Wartezeit wie in 02-13, nie ein Treffer
    - Kopfabweichung: gelöst, voll geladen, eigener Inhalt; kein Treffer aus dem alten Transkript
    - Vorziehen: der Beweis eines wiederhergestellten Verweises wird vor einem gewöhnlichen Download mit kleinerer file_id beansprucht
    - Kein Verhungern: viele Wiederherstellungen auf hängendem Speicher kosten drei Anfragen, der Rest wird ohne Anfrage pausiert, danach läuft der gewöhnliche Download; ein gescheiterter vorgezogener Beweis ist beim nächsten Versuch nicht mehr vorgezogen; ein fälliger Beweis eines aktiven Verweises (Plan 20) ist nicht vorgezogen
    - doppelt geliefertes restore endet im selben Zustand, vor und nach dem Beweis
    - Beweis war vor dem Papierkorb gescheitert: bleibt ungültig, auch ohne prefilter_key in der Zeile
    - ohne Beweispflicht: sofort active, Treffer, nichts für die Erfassung
    - gespeicherter prefilter_key, Zeile ohne: kein Treffer bis zum Beweis (Auslegung)
    - Papierkorb während des laufenden vorgezogenen Beweises: Ergebnis stale, kein Treffer; nach erneutem restore wieder vorgezogen
    - test_intake.py: `test_a_restore_on_smb_or_sftp_asks_for_the_read_proof_again` erwartet unreadable statt active und die bleibende Marke
  </behavior>
  <action>Neue Datei mit der Bühne aus test_read_proof.py (Stage, FakeHead, Uhr) und einem echten SearchIndex. Rot laufen lassen und den Grund festhalten. Commit `test(02-15b): Lesebeweis nach dem Wiederherstellen, rote Tests`.</action>
  <verify>
    <automated>cd backend && ! uv run pytest tests/test_restore_proof.py tests/test_intake.py -q</automated>
  </verify>
  <acceptance_criteria>Rot aus dem richtigen Grund (Zustand active statt unreadable, Reihenfolge nach file_id), kein Import- oder Syntaxfehler.</acceptance_criteria>
  <done>Tests rot, Commit vorhanden.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Umsetzung, Mutationsproben, Gates</name>
  <files>backend/src/audio_video_search_backend/store/repo.py</files>
  <behavior>
    - alle Tests aus Task 1 grün, ganze Suite grün
    - test_read_proof_gate.py unverändert und grün
  </behavior>
  <action>`_INTAKE_ROW` liest prefilter_key mit. `_restore`: mit Inhalt und gültigem Beweis nur dann active und keyed, wenn weder Zeile noch Verweis einen prefilter_key haben; sonst unreadable, probing (Grund leer bei gültigem Beweis, sonst behalten), Marke bleibt. `_CLAIM_CAPTURE`: ORDER BY beginnt mit `CASE WHEN state = 'unreadable' AND stage = 'probing' AND media_id IS NOT NULL THEN 0 ELSE 1 END`. Kommentare und Docstrings nachziehen. Mutationsproben: Vorziehen entfernen, Treffersperre entfernen (restore wieder active), gespeicherten Schlüssel ignorieren, alle probing vorziehen; jeweils rot sehen, Datei bytegenau zurücksetzen. Commit `feat(02-15b): Wiederhergestellte Verweise ohne Treffer bis zum vorgezogenen Lesebeweis`.</action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_restore_proof.py tests/test_intake.py tests/test_read_proof.py tests/test_read_proof_gate.py tests/test_capture.py tests/test_exclusion_forget.py -q && uv run ruff check . && uv run ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -q</automated>
  </verify>
  <acceptance_criteria>Alle Gates Exit 0; Mutationen rot; kein neuer Zustand, kein Schema-Feld, kein PHP geändert.</acceptance_criteria>
  <done>Commit vorhanden, SUMMARY geschrieben.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Papierkorb nach Suche | Wiederherstellen darf kein Recht behaupten, das der Speicher inzwischen entzogen hat |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-55 | Information Disclosure | Wiederherstellen mit entzogenem Recht | mitigate | kein Treffer vor dem bestandenen Beweis, Beweis vorgezogen |
| T-02-55b | Denial of Service | viele Wiederherstellungen auf hängendem Speicher | mitigate | einmal vorgezogen je Wiederherstellung, Sperrkreis je storage_id, Test |
</threat_model>

<verification>
Volle Backend-Suite grün, Gates grün.
</verification>

<success_criteria>
- Kein Fenster mit Treffern vor dem eigenen bestandenen Lesebeweis auf Speichern mit Beweispflicht; der Beweis läuft vor gewöhnlicher Arbeit, ohne sie dauerhaft zu blockieren.
</success_criteria>

<output>
Create `.planning/phases/02-erfassung-aller-dateien/02-15b-SUMMARY.md` when done
</output>
