---
phase: 02-erfassung-aller-dateien
plan: 15c
type: execute
wave: 6
depends_on: [02-13, 02-15, 02-15b]
files_modified:
  - backend/src/audio_video_search_backend/store/repo.py
  - backend/tests/test_excerpt_states.py
  - .planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md
  - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
autonomous: true
requirements: [DISC-03, DISC-05, DISC-06]

must_haves:
  truths:
    - "POST /excerpt gibt Text eines Transkripts nur für einen Verweis aus, der auch Treffer liefern darf (state active). Für unreadable, trashed und vanished in jeder stage antwortet die Route genau wie für eine Datei-ID, die es nicht gibt: gleicher Status, gleicher Body, gleiche Kopfzeilen des Inhalts"
    - "Für active bleibt alles wie bisher, auch mit fälligem erneutem Beweis (active, probing)"
    - "Die Regeln der Probe (D-02-15) sind unverändert: eine Probe gibt weiter nur dann Text, wenn die Erfassung für die Datei keinen nicht aktiven Verweis hält"
    - "Keine weitere Route des Containers gibt Text, Wörter oder Zeitmarken eines Transkripts für einen nicht aktiven Verweis aus; die geprüften Stellen stehen mit Befund im SUMMARY"
  artifacts:
    - path: "backend/src/audio_video_search_backend/store/repo.py"
      provides: "Store.media_for_file nimmt den echten Verweis nur bei state active"
    - path: "backend/tests/test_excerpt_states.py"
      provides: "Paar-Gleichheit nicht aktiver Verweis gegen unbekannte Datei-ID, an der Route gemessen"
  key_links:
    - from: "api/excerpt.py::_excerpt"
      to: "Store.media_for_file"
      via: "einziger Aufrufer im Produkt"
      pattern: "media_for_file"
---

<objective>
Die in 02-15b gefundene Lücke schließen (deferred-items.md, Zeile 02-15b `media_for_file`): Die Ausschnitt-Route gab Text auch für Verweise aus, die keine Treffer geben. D-02-01a verlangt, dass ein Verweis ohne bestandenen Lesebeweis keinen Inhalt preisgibt; die Abspielseite prüft davor nur isReadable, und das sagt bei einer SMB-ACL ja (A6).

Purpose: D-02-01a, D-02-09, D-02-12, T-02-06, T-02-46 auch für den Ausschnitt.
Output: eine Bedingung in store/repo.py, neue Testdatei, Satz in 02-CONTEXT.md.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md
@.planning/phases/02-erfassung-aller-dateien/02-15b-SUMMARY.md
@.planning/phases/02-erfassung-aller-dateien/deferred-items.md
@backend/src/audio_video_search_backend/store/repo.py
@backend/src/audio_video_search_backend/api/excerpt.py
@php/lib/Controller/PageController.php

Regeln: Commits nur als `street1983nk <k.cherif@outlook.de>`, ohne Claude-Session-Zeile, nie "closes/fixes/resolves #N". Kein Push. Kein Docker, Python nur über uv. PHP nur lesen. Gates vor Commit grün, seriell. STATE.md und ROADMAP.md bleiben unberührt.

Befund am Bestand: `Store.media_for_file` nimmt den Inhalt des echten Verweises ohne Blick auf den Zustand (`_FILE_REF` liest den Zustand schon mit); nur die Probe ist über `_SAMPLE_VISIBLE` an active gebunden. Einziger Aufrufer im Produkt: `api/excerpt.py::_excerpt`.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Rote Tests</name>
  <files>backend/tests/test_excerpt_states.py</files>
  <behavior>
    - an der Route (TestClient, echte state.db) gemessen: Verweis mit Inhalt und Transkript in unreadable, trashed, vanished, jeweils jede stage: Status, Body und Inhalts-Kopfzeilen gleich der Antwort für eine unbekannte Datei-ID
    - active in keyed und probing: Text wie bisher
    - nach trash kein Text; nach restore mit Beweispflicht kein Text bis confirm_proof; nach gescheitertem erneutem Beweis kein Text
    - Probe neben nicht aktivem Verweis: kein Text (Bestand, Wächter)
    - `Store.media_for_file` gibt für nicht aktive Verweise None
  </behavior>
  <action>Rot laufen lassen und den Grund festhalten. Commit `test(02-15c): Ausschnitt nur für Verweise mit Treffern, rote Tests`.</action>
  <verify>
    <automated>cd backend && ! uv run pytest tests/test_excerpt_states.py -q</automated>
  </verify>
  <acceptance_criteria>Rot, weil die Route Text ausgibt; kein Import- oder Syntaxfehler.</acceptance_criteria>
  <done>Tests rot, Commit vorhanden.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Umsetzung, Mutationsprobe, weitere Ausgabestellen, Gates</name>
  <files>backend/src/audio_video_search_backend/store/repo.py</files>
  <behavior>
    - alle Tests aus Task 1 grün, ganze Suite grün, test_read_proof_gate.py unverändert grün
  </behavior>
  <action>`media_for_file`: der echte Verweis zählt nur bei state active. Alle Aufrufer und jede Stelle prüfen, die Text, Wörter, Zeitmarken oder Proben-Text nach außen gibt (Suche, Ausschnitt, Probe, Status, Zählung, Arbeitsvorrat, Index); dieselbe Lücke in Python mit rotem Test zuerst beheben, die Probe nicht ändern. Mutationsprobe: Zustandsbedingung entfernen, rot sehen, bytegenau zurücksetzen. PHP nur lesen: wie reagiert die Abspielseite auf "nicht bekannt", gibt PHP Text ohne das Backend aus. Commit `fix(02-15c): Ausschnitt nur für Verweise, die Treffer geben`.</action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_excerpt_states.py tests/test_api_routes.py tests/test_sample_layer.py tests/test_read_proof_gate.py -q && uv run ruff check . && uv run ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -q</automated>
  </verify>
  <acceptance_criteria>Alle Gates Exit 0; Mutation rot; kein PHP geändert; Probe unverändert.</acceptance_criteria>
  <done>Commit vorhanden, SUMMARY geschrieben.</done>
</task>

</tasks>

<threat_model>
## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-46b | Information Disclosure | Ausschnitt für Verweis ohne gültigen Beweis | mitigate | Text nur bei state active, Antwort nicht von "unbekannt" unterscheidbar |
</threat_model>

<verification>
Volle Backend-Suite grün, Gates grün.
</verification>

<success_criteria>
- Kein Weg des Containers gibt Text eines Transkripts für einen Verweis aus, der keine Treffer geben darf.
</success_criteria>

<output>
Create `.planning/phases/02-erfassung-aller-dateien/02-15c-SUMMARY.md` when done
</output>
