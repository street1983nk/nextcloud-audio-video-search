---
phase: 02-erfassung-aller-dateien
plan: 16b
type: execute
wave: 6
depends_on: [02-15c, 02-16]
files_modified:
  - backend/src/audio_video_search_backend/store/repo.py
  - backend/tests/test_sample_real_transcript.py
  - backend/tests/test_php_gates.py
  - php/lib/Service/ExclusionService.php
  - php/lib/Command/ExcludeCommand.php
  - php/lib/Controller/PageController.php
  - php/tests/Unit/ExclusionServiceTest.php
  - php/tests/Unit/PlayControllerTest.php
  - .planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md
  - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
autonomous: true
requirements: [DISC-02, DISC-03]

must_haves:
  truths:
    - "(A) Ein Eintrag einer Ausschlussliste mit einem Steuerzeichen an irgendeiner Stelle, auch am Rand, wird in allen vier Listen als ungültig abgelehnt und nie geschrieben; nur gewöhnliche Leerzeichen (U+0020) am Rand werden wie bisher entfernt"
    - "(B) Eine Probe gibt in Suche und Ausschnitt nur Text, solange der Inhalt, auf den sie zeigt, auf der Stufe Probe steht (current.level gleich Level.SAMPLE). Hat der Inhalt ein echtes Transkript, antwortet die Suche wie ohne die Probe und der Ausschnitt wie für eine unbekannte Datei-ID; Treffer und Ausschnitt gibt dann nur ein echter Verweis mit state active"
    - "(C) Die Abspielseite zeigt einem ausgeschlossenen Nutzer und für eine ausgeschlossene Datei denselben Zustand wie für eine Datei ohne Transkript (EXCERPT_NONE, gleiche Parameter, gleicher Status), ohne das Backend zu fragen; eine Prüfung, die scheitert, gilt als ausgeschlossen"
    - "Alle Stellen fragen ExclusionService (isExcludedUser, isExcludedFile); Gate-Regel 14 hält die neue Prüfstelle fest"
  artifacts:
    - path: "backend/src/audio_video_search_backend/store/repo.py"
      provides: "_FILE_IDS_FOR_MEDIA und _SAMPLE_VISIBLE nennen eine Probe nur bei Stufe Probe"
    - path: "backend/tests/test_sample_real_transcript.py"
      provides: "Paar-Gleichheit an Suche und Ausschnitt-Route, echte state.db"
    - path: "php/lib/Service/ExclusionService.php"
      provides: "normalised() prüft Steuerzeichen am unveränderten Eintrag, kürzt nur Leerzeichen"
    - path: "php/lib/Controller/PageController.php"
      provides: "excerpt() fragt die Ausschlüsse vor searchAllowed und vor dem Backend"
  key_links:
    - from: "api/search.py::_search, api/excerpt.py::_excerpt"
      to: "Store.file_ids_for_media, Store.media_for_file"
      via: "einzige Aufrufer im Produkt"
      pattern: "file_ids_for_media|media_for_file"
    - from: "PageController::excerpt"
      to: "ExclusionService::isExcludedUser, isExcludedFile"
      via: "Gate-Regel 14"
      pattern: "isExcluded(User|File)"
---

<objective>
Drei Nacharbeiten nach 02-16, vor 02-17.

(A) Roter PHPUnit-Fall aus dem Container-Lauf (511 Tests, 1 Failure): `ExclusionServiceTest::testAFolderThatIsNoUsablePrefixIsRefusedAndNeverWritten`, Datensatz "zero byte". Ursache: `normalised()` beginnt mit `trim($entry)`, das Nullbyte, Tab, Zeilenumbruch und Wagenrücklauf am Rand entfernt, bevor die Steuerzeichen-Prüfung läuft. Der Test hat recht, das Produkt wird korrigiert (Auftrag der Hauptsitzung, ablehnen statt still verändern).

(B) Owner-Entscheid 13.11.2026 ("Go für beide"): Probe gibt nur Text, solange der Inhalt auf Stufe Probe steht (deferred-items.md, Zeile 02-15c).

(C) Owner-Entscheid 13.11.2026 ("Go für alle Empfehlungen"): Abspielseite zeigt Ausgeschlossenen keinen Ausschnitt (deferred-items.md, Zeile 02-16 PageController).

Output: je eine Änderung in store/repo.py, ExclusionService.php, PageController.php; Tests; Gate-Regel 14 erweitert.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md
@.planning/phases/02-erfassung-aller-dateien/02-15c-SUMMARY.md
@.planning/phases/02-erfassung-aller-dateien/02-16-SUMMARY.md
@.planning/phases/02-erfassung-aller-dateien/deferred-items.md
@backend/src/audio_video_search_backend/store/repo.py
@php/lib/Service/ExclusionService.php
@php/lib/Controller/PageController.php
@php/lib/Search/Provider.php

Regeln: Commits nur als `street1983nk <k.cherif@outlook.de>`, ohne Claude-Session-Zeile, nie "closes/fixes/resolves #N". Kein Push. Kein Docker, kein PHP auf dem Rechner: php -l und PHPUnit prüft die Hauptsitzung im Container. Python nur über uv. Gates vor Commit grün, seriell. STATE.md und ROADMAP.md bleiben unberührt.

Befund am Bestand:
- "Stufe Probe" ist `current.level == Level.SAMPLE` (1): daran hängt das Kennzeichen sample im Treffer (api/search.py) und `Store.remove_sample` (not_sample bei höherer Stufe).
- Die Probe wird an zwei Stellen sichtbar: `_FILE_IDS_FOR_MEDIA` (Suche) und `_SAMPLE_VISIBLE` (Ausschnitt über `media_for_file`). Beide kennen die Stufe nicht.
- `PageController::excerpt` fragt nur `searchAllowed` und das Backend. Provider fragt `isExcludedUser`, das Gateway `isExcludedFile`.
- Bestand zu Leerzeichen am Rand: `'  privat  '` wird `privat`, `' eva '` wird als `eva` geschrieben, `'   '` ist empty. Bleibt.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (B): Probe nur auf Stufe Probe</name>
  <files>backend/tests/test_sample_real_transcript.py, backend/src/audio_video_search_backend/store/repo.py</files>
  <behavior>
    - Probe zeigt auf Inhalt mit echtem Transkript, Datei ohne Verweis der Erfassung: Suche antwortet Byte für Byte wie vor dem Anlegen der Probe, Ausschnitt wie für eine unbekannte Datei-ID
    - dasselbe mit aktivem Verweis ohne Inhalt (pending)
    - Probe zuerst, echtes Transkript danach: Treffer und Ausschnitt der Probe verschwinden
    - echter aktiver Verweis auf denselben Inhalt: Treffer und Ausschnitt wie bisher, sample false; eine fremde Datei mit Probe daneben bekommt nichts
    - Probe auf Stufe Probe: Treffer mit sample true und Ausschnitt wie bisher (Wächter)
    - Store: file_ids_for_media und media_for_file nennen die Probe nicht
  </behavior>
  <action>Rot laufen lassen, Grund festhalten, Commit `test(02-16b): ...`. Dann beide Abfragen um die Stufe ergänzen (Wert aus Level.SAMPLE, nicht als Zahl im SQL). Mutationsprobe je Abfrage, bytegenau zurücksetzen. Commit `fix(02-16b): ...`.</action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_sample_real_transcript.py tests/test_sample_layer.py tests/test_excerpt_states.py tests/test_api_routes.py tests/test_excluded_cleanup.py tests/test_read_proof_gate.py -q</automated>
  </verify>
  <acceptance_criteria>RED aus dem richtigen Grund (Text des echten Transkripts in der Antwort), danach grün; Mutation rot; kein Bestandstest abgeschwächt.</acceptance_criteria>
  <done>Zwei Commits, Suite grün.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (A): Steuerzeichen am Rand ablehnen</name>
  <files>php/lib/Service/ExclusionService.php, php/tests/Unit/ExclusionServiceTest.php</files>
  <behavior>
    - Nullbyte, Tab, Zeilenumbruch, Wagenrücklauf am Anfang oder am Ende eines Eintrags: invalid in allen vier Listen bei validate, normalise (null), add (nichts geschrieben, Mount-ID nicht nachgeschlagen), remove (absent, nichts geschrieben); eine gespeicherte Liste mit so einem Eintrag ist nicht lesbar
    - Leerzeichen am Rand werden in allen vier Listen weiter entfernt
    - der rote Fall "zero byte" wird grün, keine Erwartung des Bestands ändert sich
  </behavior>
  <action>`normalised()`: Kodierung und Steuerzeichen am unveränderten `$entry` prüfen, nur `trim($entry, ' ')`. Reihenfolge der Codes sonst wie bisher (empty, too_long, invalid). Neue Datenquelle über Liste, Zeichen und Rand. RED-Beleg ist der Container-Lauf der Hauptsitzung; GREEN ist hier nicht belegbar.</action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_php_gates.py -q</automated>
  </verify>
  <acceptance_criteria>Statische Gates grün, Klammer- und use-Bilanz ohne Befund; PHPUnit im Container durch die Hauptsitzung.</acceptance_criteria>
  <done>Commit vorhanden.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3 (C): Abspielseite ohne Ausschnitt für Ausgeschlossene</name>
  <files>php/lib/Controller/PageController.php, php/tests/Unit/PlayControllerTest.php, backend/tests/test_php_gates.py</files>
  <behavior>
    - ausgeschlossener Nutzer: Parameter, Status, Vorlage der Antwort gleich denen für "kein Transkript" (Paar-Test); weder searchAllowed noch excerpt des Backends wird aufgerufen
    - ausgeschlossene Datei (isExcludedFile): dasselbe
    - Prüfung wirft: wie ausgeschlossen (fail-closed), Logzeile ohne Nutzer, Namen, Pfad
    - nicht ausgeschlossen: wie bisher, die Ausschlüsse werden einmal gefragt
    - Gate-Regel 14: PageController::excerpt fragt isExcludedUser und isExcludedFile vor searchAllowed und vor excerpt des Backends; Selbsttest mit Mutationen
  </behavior>
  <action>Konstruktor: `ExclusionService $exclusions` als letzter Parameter (wie 02-16). Prüfung als erste Anweisung von `excerpt()`. PlayControllerTest baut den Controller von Hand: nachziehen. Tests zuerst schreiben; RED und GREEN der PHP-Seite sind hier nicht belegbar und werden nicht behauptet. Gate-Regel erst rot gegen den alten PageController sehen (Python), dann umsetzen.</action>
  <verify>
    <automated>cd backend && uv run pytest tests/test_php_gates.py -q && uv run ruff check . && uv run ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -q</automated>
  </verify>
  <acceptance_criteria>Alle Python-Gates Exit 0; Gate-Regel 14 rot ohne die Prüfung in PageController; Klammer- und use-Bilanz der PHP-Dateien ohne Befund.</acceptance_criteria>
  <done>Commit vorhanden, SUMMARY geschrieben.</done>
</task>

</tasks>

<threat_model>
## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-59b | Tampering | Eintrag mit Steuerzeichen am Rand wird still zu einer anderen Regel | mitigate | Prüfung am unveränderten Eintrag, ablehnen statt kürzen |
| T-02-46c | Information Disclosure | Probe gibt Text eines echten Transkripts ohne Verweis der Erfassung | mitigate | Probe nur bei Stufe Probe, Antwort nicht von "unbekannt" unterscheidbar |
| T-02-58b | Information Disclosure | Ausschnitt auf der Abspielseite für ausgeschlossene Nutzer oder Dateien | mitigate | Prüfung vor jedem Aufruf des Backends, fail-closed, Antwort gleich "kein Transkript" |
</threat_model>

<verification>
Volle Backend-Suite grün, Gates grün. php -l und PHPUnit im Container durch die Hauptsitzung.
</verification>

<success_criteria>
- Kein Steuerzeichen in einer Ausschlussregel, kein Text eines echten Transkripts über eine Probe, kein Ausschnitt für Ausgeschlossene.
</success_criteria>

<output>
Create `.planning/phases/02-erfassung-aller-dateien/02-16b-SUMMARY.md` when done
</output>
