---
phase: 02-erfassung-aller-dateien
plan: 15b
subsystem: backend-erfassung
tags: [disc-03, disc-06, d-02-01a, d-02-09, d-02-12, lesebeweis, papierkorb, wiederherstellen, reihenfolge]
requires:
  - phase: 02-13
    provides: "erneuter Lesebeweis (confirm_proof, fail_proof, release_media), Sperrkreis je storage_id, Gate test_read_proof_gate.py"
  - phase: 02-15
    provides: "Papierkorb und Wiederherstellen im Intake (_trash, _restore), Verwaist-Regel"
provides:
  - "Store._restore: mit Beweispflicht (prefilter_key in der Zeile oder am Verweis) unreadable und probing statt active; erst confirm_proof macht active"
  - "_CLAIM_CAPTURE: unreadable, probing mit media_id wird vor aller anderen Arbeit beansprucht"
  - "_INTAKE_TRASH: ein geschuldeter Beweis (unreadable, probing) liegt im Papierkorb als failed"
  - "_INTAKE_ROW liest prefilter_key mit"
affects: [02-16, 02-17, 02-18, 02-20, 02-22]
tech-stack:
  added: []
  patterns:
    - "Kein Treffer ohne eigenen bestandenen Beweis: der vorhandene Zustand unreadable trägt 'Beweis geschuldet', kein neuer Zustand, kein Schema-Feld"
    - "Vorziehen über eine Zustandskombination, die nur _restore schreibt und jedes Urteil der Erfassung verlässt: einmal je Wiederherstellung"
key-files:
  created:
    - backend/tests/test_restore_proof.py
    - .planning/phases/02-erfassung-aller-dateien/02-15b-PLAN.md
  modified:
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/tests/test_intake.py
    - .planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
key-decisions:
  - "02-15b: 'Lesebeweis nötig' ist das Kriterium des Bestands: prefilter_key gesetzt (PHP setzt ihn nur für externe Speicher mit Freigabe-Schlüssel, SMB und SFTP)"
  - "02-15b: Beweispflicht besteht, wenn die restore-Zeile ODER der gespeicherte Verweis einen prefilter_key trägt (strengere Lesart)"
  - "02-15b: 'Keine Treffer' über state unreadable; api/search.py gibt nur Datei-IDs aus Store.file_ids_for_media aus, und die kennt nur active; PHP unverändert"
  - "02-15b: Vorgezogen wird nur unreadable, probing mit media_id (wiederhergestellt), nicht der fällige Beweis eines aktiven Verweises (Plan 20) und kein Wiederholversuch"
  - "02-15b: Der Papierkorb legt unreadable, probing als failed ab, damit zweimal Papierkorb und zurück einen geschuldeten oder gescheiterten Beweis nicht gültig macht"
requirements-completed: []
metrics:
  duration: "ca. 10 min ab der Zeitmarke nach dem Einlesen"
  completed: 2026-11-12
  tasks: 2
  files: 6
---

# Phase 2 Plan 15b: Lesebeweis nach dem Wiederherstellen Summary

Ein aus dem Papierkorb wiederhergestellter Verweis auf einem Speicher mit Beweispflicht (prefilter_key, also SMB und SFTP) kommt jetzt als unreadable und probing zurück, gibt bis zu seinem eigenen bestandenen Lesebeweis keinen Treffer in der Suche, und die Erfassung beansprucht genau diesen Beweis vor aller gewöhnlichen Arbeit, einmal je Wiederherstellung.

## Performance

- **Dauer:** ca. 10 min ab der Zeitmarke nach dem Einlesen der Planunterlagen
- **Beginn:** 2026-11-12T19:39:03Z
- **Ende:** 2026-11-12T19:50Z
- **Tasks:** 2 von 2
- **Dateien:** 6 (2 neu, 4 geändert)

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| Plan | Plan, Nachtrag D-02-01a, deferred-items | 309fdb9 | 02-15b-PLAN.md, 02-CONTEXT.md, deferred-items.md |
| 1 | Rote Tests | 9d951b0 | backend/tests/test_restore_proof.py, backend/tests/test_intake.py |
| 2 | Umsetzung | 853102e | backend/src/audio_video_search_backend/store/repo.py |

Alle Commits als street1983nk <k.cherif@outlook.de>, lokal auf main, nicht gepusht.

## Befunde am Bestand vor dem Bau

- **Wo Treffer entstehen.** `api/search.py::_search` macht aus jedem zulässigen Inhalt einen Treffer je Datei-ID aus `Store.file_ids_for_media` (`_FILE_IDS_FOR_MEDIA`: nur state active; eine Probe nur, wenn die Erfassung für die Datei keinen nicht aktiven Verweis hält). PHP prüft danach nur noch Rechte. Der Index selbst kennt keine Datei-IDs. Die maßgebliche Stelle ist also der Zustand des Verweises im Store.
- **Woran "externer Speicher" hängt.** Der Container kennt keine Speicherklasse, nur den prefilter_key. `QueueService::prefilterKey` (PHP) liefert ihn nur für externe Speicher mit Freigabe-Schlüssel aus der Einstufung (SMB, SFTP), sonst null. 02-15 nahm in `_restore` genau `values["prefilter_key"] is not None`. Dieses Kriterium bleibt, kein neues.
- **Vorhandener Zustand.** unreadable, probing mit media_id gab es schon (02-15 Abweichung 3). Er bedeutet: kein Treffer, Beweis sofort fällig. Kein neuer Zustand, kein neuer Grund, kein Schema-Feld.

## Was gebaut wurde

**Wiederherstellen (Store._restore).** Vier Fälle bei gleichen Werten (etag, size, mtime):

| Lage im Papierkorb | Zurück als |
|--------------------|-----------|
| ohne Inhalt | active, pending (unverändert) |
| mit Inhalt, Beweis galt (keyed oder probing), kein prefilter_key in Zeile und Verweis | active, keyed, Verwaist-Marke weg (unverändert) |
| mit Inhalt, Beweis galt, prefilter_key in Zeile oder Verweis | **unreadable, probing, Grund leer, Versuche 0, next_try_at leer; Verwaist-Marke bleibt** |
| mit Inhalt, Beweis gescheitert, unterbrochen oder geschuldet | unreadable, probing, Grund bleibt (unverändert) |

Active wird der Verweis im dritten und vierten Fall nur durch `confirm_proof`, also nur im Zweig `outcome is ProofOutcome.OK` der Erfassung; dort geht auch die Verwaist-Marke.

**Vorziehen (_CLAIM_CAPTURE).** Die Sortierung beginnt mit `CASE WHEN state = 'unreadable' AND stage = 'probing' AND media_id IS NOT NULL THEN 0 ELSE 1 END`, danach wie bisher `COALESCE(next_try_at, 0), file_id`. Die WHERE-Klausel ist unverändert.

**Kein Verhungern.** Die vorgezogene Kombination schreibt nur `_restore`. Jedes Urteil der Erfassung verlässt sie: bestanden wird keyed; gescheitert, ohne Leser und pausiert wird failed mit next_try_at und Versuchszähler; Kopfabweichung löst den Inhalt und endet in keyed, failed oder pending ohne media. Ein Verweis ist damit je Wiederherstellung genau einmal vorgezogen, seine Wiederholversuche stehen in der gewöhnlichen Reihenfolge hinter neuen Downloads. Ein hängender Speicher kostet drei Anfragen, danach setzt der Sperrkreis aus 02-13 die übrigen ohne Anfrage auf storage_paused.

**Papierkorb (_INTAKE_TRASH).** Ein Verweis in unreadable, probing geht als failed in den Papierkorb. Grund siehe Abweichung 1.

## Prüfungen

Alle Befehle seriell in backend/, Exit-Codes aus der Ausgabe gelesen.

| Befehl | Ergebnis |
|--------|----------|
| RED: `uv run pytest tests/test_restore_proof.py tests/test_intake.py -q` vor der Umsetzung | Exit 1, 15 rot, 81 grün |
| Dieselben sechs Dateien wie im verify von Task 2 nach der Umsetzung | Exit 0, 363 grün |
| `uv run ruff check .` | Exit 0 |
| `uv run ruff format --check .` | Exit 0, 68 Dateien |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | Exit 0, 0 Fehler, 0 Warnungen |
| `uv run vulture` | Exit 0 |
| `uv run pytest -q` gesamt | Exit 0, 863 grün (vorher 839) |
| Statische PHP-Gates und Gate des Lesebeweises (test_php_gates.py, test_read_proof_gate.py) mit den beiden Testdateien des Plans | Exit 0, 141 grün |
| php -l, PHPUnit | nicht nötig: keine PHP-Datei geändert |

Testzahlen: test_restore_proof.py 24 (neu), test_intake.py 72 (unverändert), test_read_proof_gate.py 18 (Datei unverändert), gesamt 863.

**RED aus dem richtigen Grund.** 13 der 24 neuen Fälle und die beiden Fälle des angepassten Bestandstests waren rot: die Suche nannte die wiederhergestellte Datei (`[10, 12]` statt `[10]`), der Zustand war active statt unreadable, und die Erfassung nahm die kleinere file_id zuerst (`5` statt `12`). Kein Import- oder Syntaxfehler. 11 Fälle waren vor der Umsetzung schon grün und halten Bestand fest: bestandener und gescheiterter Beweis (fünf Gründe), Kopfabweichung (zwei), einmaliges Vorziehen, fälliger Beweis eines aktiven Verweises nicht vorgezogen, Speicher ohne Beweispflicht. Jeder davon wird von mindestens einer Mutation unten rot (M2a, M4, M6, M8).

**Mutationen (Produkt geändert, drei Testdateien gelaufen, Datei bytegenau zurückgesetzt, sha256 verglichen): 9 von 9 rot.**

| Mutation | rot |
|----------|-----|
| M1 Vorziehen entfernt | 4 |
| M2a Treffersperre entfernt (immer active, keyed) | 23 |
| M2b Treffersperre entfernt (active, probing wie 02-15) | 13 |
| M3 gespeicherter prefilter_key ignoriert | 1 |
| M4 jeder fällige Beweis vorgezogen (auch aktive Verweise) | 1 |
| M5 Papierkorb lässt geschuldeten Beweis als probing | 1 |
| M6 jeder unreadable mit Inhalt vorgezogen (auch Wiederholversuche) | 2 |
| M7 prefilter_key der Zeile ignoriert | 1 |
| M8 auch ohne Beweispflicht unreadable (Zweig active, keyed entfernt) | 5 |

**Gate aus Plan 13.** `tests/test_read_proof_gate.py` ist unverändert und grün. Keine Schreibstelle für media_id ist neu oder geändert, kein UPDATE hat prefilter_key im WHERE (er wird in `_INTAKE_ROW` nur gelesen, die Entscheidung fällt in Python), worker/capture.py und worker/read_proof.py sind unberührt.

## Angepasste Bestandstests

Genau einer, in test_intake.py:

- `test_a_restore_on_smb_or_sftp_asks_for_the_read_proof_again` (beide Parameter restore und content): erwartete `("active", "probing")` und eine gelöschte Verwaist-Marke. Jetzt `("unreadable", "probing")`, Grund leer, Versuche 0, Marke bleibt, `file_ids_for_media` leer. Der Rest (sofort fällig, als Beweis beansprucht) ist unverändert.

Keine andere Erwartung wurde geändert. `test_a_restore_takes_the_prefilter_key_of_its_own_row`, `test_a_restore_delivered_twice_ends_in_the_same_state`, `test_a_restore_never_gives_hits_to_a_reference_whose_last_proof_failed` und `test_trash_and_restore_in_one_band_end_active` sind unverändert grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Sicherheit] Zweimal Papierkorb und zurück machte einen gescheiterten Beweis gültig**
- **Gefunden bei:** Task 1 (rote Tests)
- **Problem:** Schon im Stand von 02-15: Ein Verweis, dessen Beweis gescheitert war, kam nach dem ersten Wiederherstellen als unreadable, probing zurück. Ging er vor dem Beweis noch einmal in den Papierkorb, las `_restore` beim zweiten Mal stage probing als "Beweis galt" und machte ihn active (mit Schlüssel active, probing; ohne Schlüssel active, keyed). Das widerspricht der Garantie aus 02-15 Abweichung 3. Rot gesehen in `test_a_proof_that_failed_before_the_trash_stays_invalid_through_any_number_of_restores` und `test_trash_and_restore_twice_never_make_a_missing_proof_valid`.
- **Fix:** `_INTAKE_TRASH` legt stage probing eines nicht aktiven Verweises als failed ab. probing im Papierkorb heißt damit immer "der letzte Beweis galt".
- **Dateien:** store/repo.py
- **Commit:** 853102e

### Abweichungen vom Auftrag

- **Zwei Commits für Tests und Umsetzung** (RED als eigener Commit 9d951b0), wie im Plan 02-15b vorgesehen.
- **Keine weiteren.** Kein neuer Zustand, kein Schema-Feld, kein PHP, kein Gate gelockert, STATE.md und ROADMAP.md unberührt.

### Auslegungen (bitte bei Gelegenheit bestätigen)

- **Beweispflicht auch über den gespeicherten Schlüssel.** Der Entscheid nennt "externer Speicher". Maßgeblich ist der prefilter_key; ich nehme Beweispflicht an, wenn die restore-Zeile oder der gespeicherte Verweis einen trägt. PHP liefert null auch, wenn die Einstufung des Speichers fehlt; ein Verweis, der seinen Inhalt über einen Speicher mit Beweispflicht bekommen hat, käme sonst ohne Beweis zurück. Gegenüber 02-15 ("Maßgeblich ist der Schlüssel der restore-Zeile") ist das strenger; der neue Schlüssel der Zeile wird weiter gespeichert.
- **content nach trash.** Wie in 02-15 verhält sich content mit gleichen Werten für einen Verweis im Papierkorb wie restore, also ebenfalls ohne Treffer bis zum Beweis.
- **Nur Wiederhergestellte sind vorgezogen.** Der fällige Beweis eines aktiven Verweises (Plan 20, alle 7 Tage) bleibt in der gewöhnlichen Reihenfolge: er gibt weiter Treffer, und tausende davon würden sonst jeden Erst-Crawl anhalten.
- **Vorziehen ist begrenzt, nicht gedrosselt.** Viele Wiederherstellungen auf einem langsamen, aber antwortenden Speicher laufen alle vor gewöhnlichen Downloads, je ein Lesen von höchstens 64 KiB. Eine Quote (zum Beispiel jeder zweite Schritt gewöhnliche Arbeit) habe ich nicht gebaut, weil jeder aufgeschobene Beweis einen Nutzer ohne Treffer lässt und die Menge durch die Zahl der Wiederherstellungen begrenzt ist.
- **Nach einem Neustart** (reset_fetching) steht ein gerade beanspruchter wiederhergestellter Verweis als unreadable, pending mit Inhalt da: kein Treffer, Beweis fällig, aber nicht mehr vorgezogen.
- **Zählung.** Bis zum bestandenen Beweis zählt der Verweis nicht mit (coverage zählt nur aktive), und eine Probe derselben Datei gibt keinen Treffer (D-02-15). Beides folgt aus dem Zustand unreadable.
- **Grund leer.** Der wiederhergestellte Verweis mit gültigem altem Beweis ist unreadable ohne Grund; die geschlossene Liste der Gründe (in PHP gespiegelt) bleibt unverändert.

## Annahmen der Pläne 02-16 bis 02-22

Keiner dieser Pläne wurde geändert. Berührt:

- **02-17, 02-22 (Abnahme):** `ci/discovery/compare.sh` prüft nach restore `restore_active`. Die Datei der Abnahme liegt im Home von ana (kein prefilter_key), bleibt also sofort active; die Prüfung gilt weiter. Ein künftiges Bein mit restore auf SMB müsste den Beweis abwarten.
- **02-18 (PHP sendet restore):** unverändert passend; maßgeblich bleibt, dass die restore-Zeile den prefilter_key trägt.
- **02-20 (Abgleich):** "vanished nach active" soll laut D-02-12 sofort beweisen. Soll dort dasselbe gelten wie hier, muss Plan 20 unreadable und probing schreiben; active und probing wird nicht vorgezogen. In deferred-items.md eingetragen.

## Known Stubs

Keine. DISC-03 und DISC-06 stehen nicht unter requirements-completed: wie in 02-15 erst nach der PHP-Seite und der Abnahme.

## Threat Flags

Keine neue Oberfläche. T-02-55 ist jetzt ohne Fenster umgesetzt (kein Treffer vor dem bestandenen Beweis), T-02-55b (viele Wiederherstellungen auf hängendem Speicher) per Test belegt.

## Offene Punkte

- **POST /excerpt antwortet auch für Verweise ohne Treffer (vor diesem Plan vorhanden, nicht behoben).** `Store.media_for_file` sieht beim echten Verweis nicht auf den Zustand. Lokal belegt: für unreadable/probing, unreadable/failed und trashed/keyed liefert `_excerpt` einen Text, während `file_ids_for_media` leer ist. Die Abspielseite prüft davor nur `FileAccess::readableFile` (isReadable), das bei einer SMB-ACL ja sagt (A6). Wer die Datei-ID kennt, bekommt über die Abspielroute einen Ausschnitt, auch wenn sein Beweis gescheitert oder geschuldet ist. Das betrifft jeden solchen Verweis seit 02-13, nicht nur wiederhergestellte. Außerhalb des Umfangs (api/excerpt.py, Route aus Phase 1); in deferred-items.md mit Fix-Vorschlag, Owner-Entscheid.
- **Abnahme mit restore auf SMB** gibt es nicht; das neue Verhalten ist nur durch Unit-Tests gegen echte state.db und echten Index belegt.
- Aus 02-15 weiter offen: `delete_ref` bei excluded (Plan 16).

## Self-Check: PASSED

- Dateien vorhanden: backend/tests/test_restore_proof.py, 02-15b-PLAN.md, 02-15b-SUMMARY.md.
- Commits vorhanden: 309fdb9, 9d951b0, 853102e.
