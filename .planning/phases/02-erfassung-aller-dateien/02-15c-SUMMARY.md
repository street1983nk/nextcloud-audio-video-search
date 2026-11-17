---
phase: 02-erfassung-aller-dateien
plan: 15c
subsystem: backend-api
tags: [disc-03, disc-05, disc-06, d-02-01a, d-02-09, d-02-12, ausschnitt, excerpt, lesebeweis]
requires:
  - phase: 02-13
    provides: "unreadable nach gescheitertem Beweis, media_id bleibt"
  - phase: 02-15b
    provides: "unreadable und probing nach dem Wiederherstellen; Befund zur Ausschnitt-Route"
provides:
  - "Store.media_for_file nennt den Inhalt des echten Verweises nur bei state active"
  - "POST /excerpt antwortet für unreadable, trashed und vanished wie für eine unbekannte Datei-ID"
affects: [02-16, 02-17, 02-20, 02-22, phase-08]
tech-stack:
  added: []
  patterns:
    - "Eine Regel für Suche und Ausschnitt: Text nur für Verweise mit state active"
    - "Paar-Gleichheit als Test: Antwort für den nicht aktiven Verweis gleich der Antwort für eine Datei-ID, die es nicht gibt"
key-files:
  created:
    - backend/tests/test_excerpt_states.py
    - .planning/phases/02-erfassung-aller-dateien/02-15c-PLAN.md
  modified:
    - backend/src/audio_video_search_backend/store/repo.py
    - .planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
key-decisions:
  - "02-15c: Die Bedingung sitzt in Store.media_for_file (einziger Aufrufer api/excerpt.py), nicht in der Route: jeder künftige Aufrufer erbt sie"
  - "02-15c: Jeder Zustand außer active gilt als 'kein Text', auch vanished; die Liste der Tests leitet sich aus repo.STATES ab"
  - "02-15c: Die Probe ist unverändert; ihr Befund steht in deferred-items.md"
requirements-completed: []
metrics:
  duration: "ca. 6 min"
  completed: 2026-11-12
  tasks: 2
  files: 5
---

# Phase 2 Plan 15c: Ausschnitt nur für Verweise mit Treffern Summary

POST /excerpt gibt den Text eines Transkripts jetzt nur noch für einen Verweis aus, der auch Treffer geben darf (state active); für unreadable, trashed und vanished in jeder stage antwortet die Route Byte für Byte wie für eine Datei-ID, die es nicht gibt.

## Performance

- **Dauer:** ca. 6 min
- **Beginn:** 2026-11-12T19:51:39Z
- **Ende:** 2026-11-12T19:58Z
- **Tasks:** 2 von 2
- **Dateien:** 5 (2 neu, 3 geändert)

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| Plan | Plan, dritter Nachtrag D-02-01a, deferred-items | 8fd22d4 | 02-15c-PLAN.md, 02-CONTEXT.md, deferred-items.md |
| 1 | Rote Tests | 9e993d4 | backend/tests/test_excerpt_states.py |
| 2 | Umsetzung | a67e5b4 | backend/src/audio_video_search_backend/store/repo.py |

Alle Commits als street1983nk <k.cherif@outlook.de>, lokal auf main, nicht gepusht.

## Was gebaut wurde

`Store.media_for_file` nahm den Inhalt des echten Verweises ohne Blick auf den Zustand; `_FILE_REF` las den Zustand schon mit. Jetzt zählt der echte Verweis nur bei state active (eine Bedingung in einer Zeile, dazu der Docstring). Die Probe daneben war schon über `_SAMPLE_VISIBLE` an "kein nicht aktiver Verweis" gebunden.

**Was die Route für einen nicht aktiven Verweis antwortet:** HTTP 200 mit dem Body `{"known":false,"excerpt":null}`, dieselbe Antwort wie für eine nie gesehene Datei-ID. Der Test vergleicht Status, Body-Bytes, content-type und content-length beider Antworten. Weder `_excerpt` noch die Route schreiben eine Logzeile; auch dort ist kein Unterschied.

## Geprüfte Ausgabestellen

| Stelle | Gibt nach außen | Befund |
|--------|-----------------|--------|
| POST /excerpt (`api/excerpt.py`, `Store.media_for_file`) | Text eines Segments | **Lücke, behoben.** Einziger Aufrufer von `media_for_file` im Produkt; daneben nur ein Test |
| POST /search (`api/search.py`) | Datei-ID, Zeitmarke, Text des Segments | In Ordnung: ein Treffer entsteht nur je Datei-ID aus `file_ids_for_media` (state active); in 02-15b an der Suche gemessen |
| Probe in Suche und Ausschnitt (`_FILE_IDS_FOR_MEDIA`, `_SAMPLE_VISIBLE`) | Text des Inhalts, auf den die Probe zeigt | Für einen nicht aktiven Verweis kein Text (Test und Probe-Lauf). Nicht geändert. Eigener Befund unten |
| POST /sample, /sample/remove (`api/sample.py`) | result, mediaId, indexRev | Kein Text, keine Wörter. ADMIN, nur über occ |
| GET /status | Versionen, Zähler, Einstellungen | Kein Text |
| GET /coverage | Zahlen | Kein Text |
| GET /workstock | fileId, mediaId, storageId, Zustand, Stufe, Grund | Kein Text; nennt bewusst auch nicht aktive Verweise, ADMIN für occ :files |
| Index (`index/publish.py`) | Dokumente je Inhalt, ohne Datei-ID | Einziger Leser ist `api/search.py`; keine eigene Route |
| Erfassung, Intake, nc.py, nc_queue.py | IDs, Codes | Senden keinen Text an PHP |
| Export | | Gibt es im Container noch nicht; die Regel steht jetzt in 02-CONTEXT.md |

Weitere Python-Stellen mit derselben Lücke: keine gefunden.

**Befund zur Probe (nicht geändert, wie beauftragt).** Eine Probe kann für einen nicht aktiven Verweis keinen Text ausgeben, weder in der Suche noch im Ausschnitt. Sie gibt aber den Text des Inhalts, auf den sie zeigt, auch dann, wenn dieser Inhalt ein echtes Transkript hat und die Datei der Probe gar keinen Verweis der Erfassung hat (oder einen aktiven ohne Inhalt). Lokal ausgeführt: Suche nennt die Datei, `_excerpt` liefert den echten Text, Stufe 100; das Kennzeichen sample im Treffer ist dann false, der Debug-Schalter in PHP blendet ihn nicht aus. Entsteht nur über occ :sample. In deferred-items.md eingetragen.

## Befund zur PHP-Seite (nur gelesen, nichts geändert, nichts ausgeführt)

- **Abspielseite.** `PageController::excerpt` wertet `known false` als `EXCERPT_NONE`; `templates/play.php` zeigt dann "There is no transcript for this file yet." Das ist derselbe saubere Zustand wie für eine Datei ohne Transkript, keine Fehlerseite, HTTP 200. Die Seite rendert weiter den Player mit der WebDAV-Adresse; ob die Datei spielt, entscheidet WebDAV beim Abruf. Eine PHP-Änderung ist nicht nötig.
- **Kein Text ohne das Backend.** `Search/Provider.php` nimmt den Ausschnitt nur aus den Treffern von `ExAppService::search`, `PageController` nur aus `ExAppService::excerpt`, `ExAppService` reicht beides nur durch (`plainText`, Längengrenze). `SampleCommand` gibt nur Ergebnis-Codes aus. `GatewayController` liefert Dateibytes an den Container, keinen Transkripttext. `FileAccess` gibt nichts aus. Einen PlayController gibt es nicht; die Controller sind Gateway, Handshake, Page, Queue, Settings.
- **Wortlaut.** "Noch kein Transkript" ist für einen Verweis mit gescheitertem Beweis nicht die ganze Wahrheit, verrät aber nichts. Ein eigener Hinweis wäre unterscheidbar und damit selbst eine Auskunft; so belassen.

## Prüfungen

Alle Befehle seriell in backend/, Exit-Codes aus der Ausgabe gelesen.

| Befehl | Ergebnis |
|--------|----------|
| RED: `uv run pytest tests/test_excerpt_states.py -q` vor der Umsetzung | Exit 1, 36 rot, 4 grün |
| test_excerpt_states.py, test_api_routes.py, test_sample_layer.py, test_read_proof_gate.py nach der Umsetzung | Exit 0, 126 grün |
| `uv run ruff check .` | Exit 0 |
| `uv run ruff format --check .` | Exit 0, 69 Dateien |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | Exit 0, 0 Fehler, 0 Warnungen |
| `uv run vulture` | Exit 0 |
| `uv run pytest -q` gesamt | Exit 0, 903 grün (vorher 863) |
| php -l, PHPUnit | nicht nötig: keine PHP-Datei geändert |

Testzahlen: test_excerpt_states.py 40 (neu); test_read_proof_gate.py unverändert und grün.

**RED aus dem richtigen Grund.** Die Route gab den Text aus (`b'{"known":true,"excerpt":"Das Haushaltsgeheimnis"}'`) für alle 15 Paare aus drei Zuständen und fünf Stufen, ebenso `media_for_file` (15), dazu die Fälle Papierkorb und Wiederherstellen, gescheiterter erneuter Beweis, aktive Kopie daneben und Probe neben nicht aktivem Verweis (3). Grün waren vorher nur: active in keyed und probing, Probe ohne Verweis, und der Wächter über die Zustandsliste.

**Mutation.** Zustandsbedingung in `media_for_file` entfernt: 36 rot, 72 grün (drei Dateien); Datei bytegenau zurückgesetzt, sha256 verglichen.

## Deviations from Plan

Keine. Kein PHP, kein Schema, keine Änderung an der Probe, kein Gate gelockert, kein Bestandstest angepasst.

### Auslegungen (bitte bei Gelegenheit bestätigen)

- **vanished zählt als "kein Text".** Der Auftrag nennt "jeden anderen nicht aktiven Zustand"; vanished (Speicher nicht mehr eingehängt) gibt schon heute keine Treffer und jetzt auch keinen Ausschnitt.
- **active mit fälligem erneutem Beweis (active, probing) behält den Ausschnitt.** Er gibt auch Treffer; das ist der Stand aus 02-13 und Plan 20.
- **Probe neben nicht aktivem Verweis** gibt keinen Ausschnitt. Das war schon Regel der Probe (D-02-15); sichtbar wurde es erst jetzt, weil vorher der echte Verweis den Text geliefert hat.
- **Dritter Nachtrag in 02-CONTEXT.md** ist als Auftrag der Hauptsitzung nach der Owner-Regel Datenschutz zuerst gekennzeichnet, nicht als eigener Owner-Entscheid.

## Annahmen der Pläne 02-16 bis 02-22

Keiner wurde geändert. ci/discovery und die Workflows nennen den Ausschnitt nicht (per Suche nach excerpt geprüft), die Abnahme ist also nicht berührt; ein künftiger Export oder jede neue Route mit Text muss dieselbe Regel einhalten (Nachtrag in 02-CONTEXT.md).

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche. T-02-46b (Ausschnitt für Verweis ohne gültigen Beweis) ist umgesetzt.

## Offene Punkte

- **Probe mit echtem Transkript** (siehe Befund oben, deferred-items.md): Owner-Entscheid, zusammen mit D-02-15a in Plan 16.
- **Zeitverhalten** der beiden Antworten habe ich nicht gemessen; beide Wege enden nach höchstens zwei kurzen SELECTs.
- Die PHP-Seite ist am Quelltext belegt, nicht per Lauf.

## Self-Check: PASSED

- Dateien vorhanden: backend/tests/test_excerpt_states.py, 02-15c-PLAN.md, 02-15c-SUMMARY.md.
- Commits vorhanden: 8fd22d4, 9e993d4, a67e5b4.
