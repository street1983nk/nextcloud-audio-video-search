---
phase: 02-erfassung-aller-dateien
plan: 15
subsystem: backend-erfassung
tags: [disc-03, disc-06, d-02-04, d-02-09, d-02-12, d-02-13, ausschluss, papierkorb, vergessen, index-rueckzug]
requires:
  - phase: 02-05
    provides: "Intake mit Ack nach dem Commit, apply_intake für content und metadata, Kinds der Warteschlange"
  - phase: 02-08
    provides: "mark_keyed nimmt einer wiederkehrenden media die Verwaist-Marke, Claim-Identität"
  - phase: 02-13
    provides: "erneuter Lesebeweis für stage probing mit media_id, confirm_proof, fail_proof, Gate test_read_proof_gate.py"
provides:
  - "Store.remove_refs(*, file_ids=None, storage_ids=None, cause, now=None) -> list[int] (vergessene media_ids); RemoveCause, REMOVE_CAUSES"
  - "Store.forget_media(media_id) -> bool, Store.orphan_media(media_id, now=None) -> bool"
  - "Rückzugsmarke: Zeile (media_id, 0) in index_outbox, RETIRED_REV; Store.retired_media(), Store.mark_retired(media_ids)"
  - "SearchIndex.retire_forgotten(store) -> int"
  - "Store.apply_intake setzt alle sieben Kinds um; INTAKE_KINDS gleich nc_queue.KINDS"
  - "IntakeResult.retired; Intake zieht nach dem Commit den Index zurück und quittiert danach"
  - "media_id wird nicht neu vergeben, solange index_outbox noch eine Zeile für sie hat"
affects: [02-16, 02-17, 02-19, 02-20, 02-22, phase-08]
tech-stack:
  added: []
  patterns:
    - "Ursache entscheidet: exclude vergisst beim letzten Verweis, jede andere Ursache merkt nur vor"
    - "ID-Listen als ein JSON-Text über json_each, ein DELETE mit RETURNING media_id; aufgeräumt wird nur, was das DELETE zurückgibt"
    - "Index-Rückzug über die Outbox: Marke mit Revision 0 im selben Commit wie das Löschen, abgearbeitet direkt danach unter derselben Sperre, sonst beim nächsten Band oder beim reconcile am Start"
    - "Papierkorb nimmt einem laufenden Download den Claim (fetching wird pending), damit dessen Ergebnis stale ist"
key-files:
  created:
    - backend/tests/test_exclusion_forget.py
  modified:
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/index/publish.py
    - backend/src/audio_video_search_backend/worker/intake.py
    - backend/tests/test_intake.py
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
key-decisions:
  - "02-15: remove_refs gibt die vergessenen media_ids zurück (der Plan nennt nur list[int])"
  - "02-15: Letzter Verweis heißt bei exclude: kein Verweis der Erfassung mehr, gleich in welchem Zustand; hält noch ein trashed, unreadable oder vanished Verweis den Inhalt, wird nur vorgemerkt"
  - "02-15: Rückzugskennzeichen ist index_rev 0 in index_outbox; kein Schema-Wechsel"
  - "02-15: _INSERT_MEDIA vergibt MAX(media, index_outbox) + 1, damit Dokumente einer vergessenen media nie unter einer neuen media auftauchen"
  - "02-15: Scheitert der Index-Rückzug nach dem Commit, wird trotzdem quittiert; die Marke bleibt für das nächste Band und den reconcile"
  - "02-15: restore macht nur einen Verweis sofort active, dessen Beweis beim Wegwerfen galt (keyed oder probing); war der letzte Beweis gescheitert oder unterbrochen, kommt er unreadable und probing zurück"
  - "02-15: content oder restore für einen Verweis, der nicht im Papierkorb liegt, verhalten sich wie content (kein Zurücksetzen auf probing)"
  - "02-15: Zeilen exclude, delete, trash ohne fileId sind ein Fehler vor der Transaktion (Band rollt zurück), exclude_storage braucht keine"
requirements-completed: []
metrics:
  duration: "ca. 20 min (ab Zeitmarke nach dem Einlesen)"
  completed: 2026-11-12
  tasks: 2
  files: 6
---

# Phase 2 Plan 15: Ausschluss, endgültiges Löschen und Papierkorb im Container Summary

Der Container setzt jetzt alle sieben Kinds der Warteschlange in einer Transaktion um: ein Ausschluss entfernt Verweise und vergisst den Inhalt mit dem letzten (Wörter, Transkript, current, Korrekturen, media_key, media, Index-Dokumente), ein gelöschter Dateieintrag und der Papierkorb merken den Inhalt nur mit orphaned_at vor, und eine Wiederherstellung mit gleichen Werten kostet keinen Download, auf SMB und SFTP nur den erneuten Lesebeweis.

## Performance

- **Dauer:** ca. 20 min ab der Zeitmarke nach dem Einlesen der Planunterlagen
- **Beginn:** 2026-11-12T14:36:31Z
- **Ende:** 2026-11-12T14:56Z
- **Tasks:** 2 von 2
- **Dateien:** 6 (1 neu, 4 geändert, dazu deferred-items.md)

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Entfernen, Vergessen, Vormerken | 97b792a | store/repo.py, index/publish.py, tests/test_exclusion_forget.py |
| 2 | Intake-Kinds | 3fa399b | store/repo.py, worker/intake.py, tests/test_intake.py |

Beide Commits als street1983nk <k.cherif@outlook.de>, lokal auf main, nicht gepusht.

## Was gebaut wurde

**Entfernen (Store.remove_refs).** Genau eine der beiden ID-Listen, eine Ursache aus der geschlossenen Liste (exclude, delete, gone, vanished_expired), alles vor der Transaktion geprüft. Die IDs gehen als ein JSON-Text an ein `DELETE ... WHERE file_id IN (SELECT value FROM json_each(?)) RETURNING media_id` (für Speicher über storage_id und damit über den Index file_ref_storage). Angesehen werden danach nur die media_ids, die dieses DELETE zurückgibt (T-02-56).

**Vergessen (cause exclude, D-02-04).** Hält kein Verweis der Erfassung mehr den Inhalt, gehen in der Reihenfolge der Fremdschlüssel: Korrekturen, current, Wörter, Transkripte, media_key, media. Hält noch irgendein Verweis den Inhalt, wird nichts gelöscht; ist keiner davon active, bekommt der Inhalt nur orphaned_at. `forget_media` tut dasselbe für eine einzelne media und verweigert, solange ein Verweis sie hält.

**Vormerken (alle anderen Ursachen, D-02-09, D-02-13).** orphaned_at gleich jetzt, nur wenn kein aktiver Verweis bleibt und noch keine Marke steht (die erste Marke bleibt, die sieben Tage aus Phase 8 laufen ab ihr). Transkript, Korrekturen und Index-Dokumente bleiben; findbar ist der Inhalt nicht, weil kein Verweis active ist, und gezählt wird er nicht. Kommt ein Verweis mit gleichem Inhalt über mark_keyed, geht die Marke, Transkript und Korrekturen sind da.

**Probe (D-02-15).** Zeigt eine Probe auf den Inhalt, bleiben media, media_key und die Zeilen der Probe (engine sample); alles Echte geht. Der Inhalt einer Probe wird weiter nur über remove_sample entfernt. sample_ref wird hier weder gelesen (außer der Frage, ob eine Probe darauf zeigt) noch geschrieben.

**Index-Rückzug.** Das Vergessen schreibt im selben Commit eine Zeile (media_id, 0) in index_outbox und nimmt offene Arbeit dieser media heraus. Revisionen beginnen bei 1, die 0 ist das Rückzugskennzeichen. `SearchIndex.retire_forgotten` löscht die Dokumente aller markierten Inhalte in einem Commit des Index und danach die Marken. Der vorhandene `reconcile` am Start versteht die Marke ohne Änderung (Zeile ohne current: retire mit keep_rev 0).

**Keine Wiedervergabe einer media_id mit offener Index-Arbeit.** media.media_id ist ein rowid ohne AUTOINCREMENT; SQLite gäbe die höchste ID nach dem Löschen wieder aus. Dokumente der vergessenen media stünden dann, bis der Rückzug gelaufen ist, unter der ID eines neuen Inhalts, und die Suche lässt Dokumente zu, deren Revision zu current passt. `_INSERT_MEDIA` nimmt deshalb das Maximum aus media und index_outbox plus eins.

**Intake-Kinds (Store.apply_intake).** Das Band wird in seiner Reihenfolge abgearbeitet, aufeinanderfolgende Zeilen gleicher Art gehen als eine Liste an json_each:

| Kind | Wirkung |
|------|---------|
| exclude_storage | remove_refs über storage_ids, Ursache exclude |
| exclude | remove_refs über file_ids, Ursache exclude |
| delete | remove_refs über file_ids, Ursache delete |
| trash | state trashed; stage fetching wird pending; orphaned_at, wenn kein aktiver Verweis bleibt |
| restore, content, gleiche (etag, size, mtime), Verweis im Papierkorb | zurück ohne Download, siehe unten |
| restore, content, abweichende Werte | pending, media_id NULL, alte media nach der Verwaist-Regel |
| restore für unbekannte Datei | wie content: neuer Verweis, pending |
| metadata | wie bisher nur Vorfilter-Schlüssel und Leser, auch im Papierkorb |

Wiederherstellung mit gleichen Werten: Hing der Verweis an seinem Inhalt und galt sein Beweis (stage keyed oder probing), wird er active und die media verliert orphaned_at; mit prefilter_key der Zeile (SMB, SFTP) ist die stage probing, sonst keyed. Hing er an einem Inhalt, aber sein letzter Beweis war gescheitert oder vom Papierkorb unterbrochen, kommt er unreadable und probing zurück (kein Treffer, Beweis sofort fällig, orphaned_at bleibt). Ohne Inhalt beginnt die Erfassung neu (active, pending, Versuche 0).

**Intake-Runde (worker/intake.py).** Transaktion des Bands, danach unter derselben Sperre der Index-Rückzug, danach das Ack. Der Entsperr-Zweig aus Plan 05 ist entfernt; entsperrt wird nur noch bei gescheitertem Commit und bei stats.ok false. `IntakeResult.retired` zählt zurückgezogene Inhalte.

**Logs.** `media forgotten` (media, references, cause, transcripts, words, corrections), `media orphaned` (media, references, cause), `references removed`, `intake written` (zusätzlich removed, trashed, forgotten, restored), `index documents retired`, `index retirement failed` (nur error_type). Keine Datei-ID in den Sammelzeilen, kein Name, kein Inhalt.

## Prüfungen

Alle Befehle seriell, Exit-Codes aus der Ausgabe gelesen.

| Befehl | Ergebnis |
|--------|----------|
| Task 1 verify: `uv run pytest tests/test_exclusion_forget.py tests/test_index_publish.py -x -q` | Exit 0, 57 grün |
| Task 2 verify als ganze Kette (pytest der drei Dateien, ruff check, pyright, vulture, pytest gesamt) | Exit 0; 127 grün, dann 839 grün |
| ruff check . | Exit 0 |
| ruff format --check . | Exit 0, 67 Dateien |
| pyright (PYRIGHT_PYTHON_FORCE_VERSION=latest) | Exit 0, 0 Fehler, 0 Warnungen |
| vulture | Exit 0 |
| pytest gesamt nach Task 1 | Exit 0, 802 grün |
| pytest gesamt am Ende (nach der letzten Änderung, einem Docstring) | Exit 0, 839 grün |
| PHP | nicht berührt, nichts zu prüfen |

Testzahlen: test_exclusion_forget.py 36 (neu), test_intake.py 72 (vorher 35), test_read_proof_gate.py 18 (unverändert), gesamt 839 (vorher 766).

**RED aus dem richtigen Grund.** Task 1: der erste Test scheiterte an `AttributeError: 'Store' object has no attribute 'remove_refs'`. Task 2: 35 von 72 Tests in test_intake.py rot (fehlende Kinds, fehlendes `IntakeResult.retired`), 37 grün. Ein Fall war vor der Umsetzung zufällig grün: Wiederherstellung per content mit gleichen Werten, weil trash noch nichts tat; nach der Umsetzung prüft er das Gewollte (Mutation 15 unten macht ihn rot).

**Mutationen (Produkt geändert, Tests gelaufen, Datei bytegenau zurückgesetzt).** Task 1: 22 von 22 rot (delete vergisst wie exclude; exclude merkt nur vor; Vergessen trotz verbleibendem Verweis; nur aktive Verweise zählen als Halt; Probe nicht beachtet; Probe hält echtes Transkript; keine Rückzugsmarke; offene Index-Arbeit bleibt; media_id wird neu vergeben; Korrekturen, Wörter, media_key bleiben; andere Ursachen merken nicht vor; Speicher-Löschen über file_id; ohne Index file_ref_storage; IDs ungeprüft; Ursache ungeprüft; beide Listen zugleich; Index behält Dokumente; Index behält Marken; Verwaist-Marke überschrieben; Marke trotz aktivem Verweis). Task 2: 23 von 24 rot (exclude merkt nur vor; delete vergisst; Speicher-Ausschluss merkt nur vor; trash merkt nicht vor; trash lässt den Zustand; trash lässt den Claim; restore lässt die Marke; restore nimmt die Marke bei unreadable; restore nie probing; restore immer probing; gescheiterter Beweis wird gültig; alter Vorfilter-Schlüssel bleibt; Versuche und Wartezeit bleiben; Grund bleibt bei neuem Anlauf; trashed bleibt trotz gleicher Werte; abweichende Werte ignoriert; fileId ungeprüft; trash nicht quittiert; kein Index-Rückzug; Index-Fehler bricht die Runde; nur ein Teil quittiert; Löschen in eigener Transaktion; Reihenfolge des Bands ignoriert).

Die eine überlebende Mutation ist gleichwertig: `AND state = 'trashed'` im WHERE von `_INTAKE_RESTORE` entfernt. Python ruft die Anweisung nur, nachdem es in derselben Transaktion state trashed gelesen hat; die Bedingung ist eine zweite Sicherung ohne eigenes beobachtbares Verhalten.

**Gate aus Plan 13.** `tests/test_read_proof_gate.py` ist unverändert und grün (18). Keine der dort festgehaltenen Schreibstellen ist berührt: Die neuen Anweisungen setzen media_id nie auf einen Wert (nur `_INTAKE_CHANGED` wie bisher auf NULL), kein UPDATE hat prefilter_key im WHERE (die Entscheidung probing oder keyed fällt in Python aus der Zeile des Auftrags), `_KEY_REF`, `_ATTACH_REF` und `upsert_file_ref` sind unverändert und werden nirgends neu benutzt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Sicherheit] media_id wird nicht neu vergeben, solange der Index noch Arbeit für sie hat**
- **Gefunden bei:** Task 1
- **Problem:** Nach dem Vergessen der media mit der höchsten ID hätte der nächste neue Inhalt dieselbe ID bekommen. Bis zum Rückzug (Absturz zwischen Commit und Rückzug) lägen die Dokumente des vergessenen Transkripts unter der ID eines fremden Inhalts; die Suche prüft Dokumente nur gegen current.index_rev dieser ID.
- **Fix:** `_INSERT_MEDIA` vergibt MAX über media und index_outbox plus eins. Test: `test_a_media_id_is_not_handed_out_again_before_the_index_let_go_of_it`.
- **Dateien:** store/repo.py
- **Commit:** 97b792a

**2. [Rule 2 - Sicherheit] Der Papierkorb nimmt einem laufenden Download den Claim**
- **Gefunden bei:** Task 2
- **Problem:** Die Schreibstellen der Erfassung (mark_keyed, confirm_proof) hängen an stage fetching und der Identität, nicht am Zustand. Ein Download, der beim Wegwerfen lief, hätte den Verweis danach wieder active gemacht.
- **Fix:** trash setzt stage fetching auf pending; das Ergebnis des Downloads ist stale. Test: `test_the_trash_takes_the_claim_of_a_running_download`.
- **Commit:** 3fa399b

**3. [Rule 2 - Sicherheit] Ein gescheiterter Lesebeweis wird durch Papierkorb und Wiederherstellung nicht gültig**
- **Gefunden bei:** Task 2
- **Problem:** Wörtlich nach Plan ("restore macht active ... sonst keyed") wäre ein Verweis, der vor dem Wegwerfen unreadable war (fail_proof behält media_id), nach der Wiederherstellung active und gäbe Treffer, auf Speichern ohne Vorfilter-Schlüssel sogar ohne jeden neuen Beweis.
- **Fix:** Nur stage keyed oder probing gelten als gültiger Beweis. Sonst unreadable, probing, Beweis sofort fällig, orphaned_at bleibt. Test: `test_a_restore_never_gives_hits_to_a_reference_whose_last_proof_failed`.
- **Commit:** 3fa399b

**4. [Rule 2 - Robustheit] Zeilen über eine Datei ohne fileId**
- Der Vertrag (nc_queue.ClaimItem) erlaubt fileId null für exclude, delete und trash; PHP liefert null nur für exclude_storage. Eine solche Zeile wäre stumm quittiert worden. `_check_intake` weist sie vor der Transaktion ab (ValueError, Band wird entsperrt, wie jede ungültige Zeile seit Plan 05).
- **Commit:** 3fa399b

**5. [Rule 1 - Tests aus Plan 05 an den Plan angepasst]**
- Drei Tests hielten den Zwischenstand "andere Kinds werden entsperrt" fest, den der Plan ausdrücklich beendet: `test_kinds_this_plan_does_not_handle_are_neither_written_nor_returned`, `test_the_ack_carries_only_written_rows_and_other_kinds_are_unlocked`, `test_a_full_band_of_only_unlocked_kinds_waits_for_the_interval`. Ersetzt durch `test_every_kind_of_the_queue_is_written_and_returned`, `test_a_kind_outside_the_list_is_neither_written_nor_returned`, `test_every_kind_is_acknowledged_and_none_is_unlocked`, `test_a_full_band_of_deletes_is_written_and_followed_by_the_next_claim`. Keine andere Erwartung geändert.
- **Commit:** 3fa399b

### Abweichungen von den Schnittstellen des Plans

- **TDD in einem Commit je Task.** Der Plan nennt je Task einen Commit. RED ist gelaufen und gesehen (siehe oben), steht aber nicht als eigener test-Commit im Verlauf.
- **remove_refs** hat zusätzlich `now`. `forget_media(media_id) -> bool` und `orphan_media(media_id, now=None) -> bool` sind öffentlich, im Produkt ruft sie noch niemand (Phase 8, Plan 20); die Arbeit im Intake läuft über die inneren Helfer in der einen Transaktion.
- **trash_ref, restore_ref** aus der Artefaktzeile gibt es nicht als öffentliche Methoden. Papierkorb und Wiederherstellung müssen in der Transaktion des Bands laufen; sie sind `Store._trash` und `Store._restore` und nur über apply_intake erreichbar.
- **Zusätzlich:** `Store.retired_media`, `Store.mark_retired`, `RETIRED_REV`, `SearchIndex.retire_forgotten`, `IntakeResult.retired`.
- **Index-Tests** stehen in test_exclusion_forget.py und test_intake.py; test_index_publish.py ist unverändert (steht nicht in files_modified), läuft aber im verify mit.
- **delete_ref:** nur der Docstring ist berichtigt (er verwies für das Vergessen auf Plan 15), das Verhalten ist unverändert.

### Auslegungen (bitte bei Gelegenheit bestätigen)

- **Rückgabe von remove_refs.** Der Plan sagt `-> list[int]`. Gebaut: die vergessenen media_ids, sortiert; bei jeder anderen Ursache leer.
- **"Letzter Verweis" beim Ausschluss.** must_have 1: "fällt dabei der letzte Verweis ... bleibt ein aktiver Verweis, bleibt alles". Nicht geregelt ist der Fall, dass nur noch nicht aktive Verweise (trashed, unreadable, vanished) den Inhalt halten. Gebaut: nichts wird gelöscht, der Inhalt wird vorgemerkt. Grund: Der Verweis im Papierkorb gehört einem nicht ausgeschlossenen Nutzer und käme sonst ohne Transkript zurück; außerdem verbietet der Fremdschlüssel das Löschen der media.
- **Inhalt mit Probe.** "Probe-media wird nur über remove_sample entfernt" lese ich so: media, media_key und die Zeilen der Probe bleiben, echte Transkripte und Korrekturen gehen trotzdem. Die Probe einer ausgeschlossenen Datei bleibt stehen, bis Plan 16 sie entfernt (D-02-15a, steht schon in deferred-items.md).
- **Index-Fehler nach dem Commit.** Quittiert wird trotzdem. SQLite ist die Wahrheit, die Suche gibt für einen Inhalt ohne current nichts aus, und die Marke bleibt. Die Alternative (entsperren und wiederholen) hätte bei kaputtem Index den ganzen Intake angehalten.
- **restore und content auf einen Verweis, der nicht im Papierkorb liegt.** Gleiche Werte: nur Vorfilter-Schlüssel und Leser, kein Zurücksetzen auf probing. So endet ein doppelt geliefertes restore im selben Zustand, auch wenn der Beweis dazwischen schon bestätigt wurde.
- **prefilter_key bei restore.** Maßgeblich ist der Schlüssel der restore-Zeile (frische Einstufung durch PHP), nicht der gespeicherte.
- **Vorgemerkt heißt: Dokumente bleiben im Index.** Bei delete und trash bleibt der Index unberührt; Treffer gibt es nicht, weil kein Verweis active ist. Bei Wiederkehr ist nichts neu zu bauen.

## Known Stubs

- `forget_media` und `orphan_media` haben im Produkt noch keinen Aufrufer (Phase 8: Vergessen nach 7 Tagen; Plan 20: Abgleich). Die Ursachen gone und vanished_expired nimmt remove_refs an, ausgelöst werden sie erst von Plan 20.
- DISC-03 und DISC-06 sind nicht abgehakt und stehen nicht unter requirements-completed: wie in den Vorgängern erst nach der PHP-Seite (Plan 16) und der Abnahme (Plan 17 und 22). STATE.md, ROADMAP.md und REQUIREMENTS.md habe ich nicht angefasst.

## Threat Flags

Keine neue Oberfläche über das Threat-Register hinaus. T-02-53 (sofortiges Vergessen samt Index über die Marke im selben Commit, dazu die Sperre gegen Wiedervergabe der ID), T-02-54 (vorgemerkte media hat keinen aktiven Verweis, zählt nicht), T-02-55 (restore mit Vorfilter-Schlüssel setzt probing; gescheiterter Beweis bleibt ungültig) und T-02-56 (nur media_ids aus dem RETURNING des DELETE) sind umgesetzt.

## Offene Punkte

- **delete_ref (Erfassung, Gateway sagt excluded)** merkt den Inhalt nur vor; der spätere exclude-Auftrag findet den Verweis nicht mehr und vergisst nichts. Bis Phase 8 bleibt das Transkript vorgemerkt statt sofort gelöscht. Nicht findbar, aber eine Lücke zu D-02-04. In deferred-items.md für Plan 16 eingetragen.
- **Erneuter Beweis nach restore wird nicht vorgezogen.** Der Verweis ist laut Plan sofort active; die Erfassung nimmt ihn in der Reihenfolge der file_id. Bei langem Vorrat gibt er so lange Treffer ohne neuen Beweis. In deferred-items.md eingetragen, Owner-Entscheid.
- **Abnahme** (Ausschluss vor und nach dem ersten Durchlauf, gelöschter Nutzer, Papierkorb) läuft erst in CI mit der PHP-Seite (Plan 16, 17, 22).
- Aus Plan 13 weiter offen: PHPUnit und php -l der dortigen PHP-Änderungen.

## Self-Check: PASSED

- Dateien vorhanden: backend/tests/test_exclusion_forget.py, 02-15-SUMMARY.md.
- Commits vorhanden: 97b792a, 3fa399b.
