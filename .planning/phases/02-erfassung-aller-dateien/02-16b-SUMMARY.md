---
phase: 02-erfassung-aller-dateien
plan: 16b
subsystem: php-discovery
tags: [disc-02, disc-03, d-02-15a, d-02-16, ausschluss, probe, abspielseite, steuerzeichen, gate]
requires:
  - phase: 02-15c
    provides: "Store.media_for_file nur bei state active; Befund zur Probe mit echtem Transkript"
  - phase: 02-16
    provides: "ExclusionService, occ :exclude, Gate-Regel 14; roter PHPUnit-Fall zero byte"
provides:
  - "ExclusionService::normalised kürzt nur Leerzeichen und lehnt Steuerzeichen an jeder Stelle ab, in allen vier Listen"
  - "ExclusionService::ERROR_MOUNTS_UNREADABLE, mountConfigured(): ?bool; occ :exclude nennt eine nicht lesbare Konfiguration externer Speicher in einem eigenen Satz"
  - "Store.file_ids_for_media und Store.media_for_file nennen eine Probe nur, solange der Inhalt auf Level.SAMPLE steht"
  - "PageController::excerpt fragt isExcludedUser und isExcludedFile vor searchAllowed und vor dem Backend; Konstruktor mit ExclusionService als letztem Parameter"
  - "Gate-Regel 14 mit vierter Prüfstelle (PageController::excerpt)"
affects: [02-17, 02-18, 02-22, phase-08]
tech-stack:
  added: []
  patterns:
    - "Ablehnen statt still verändern: geprüft wird der Eintrag, wie er kam"
    - "Paar-Gleichheit als Test: Suche wie vor der Probe, Ausschnitt wie unbekannte Datei-ID, Abspielseite wie ohne Transkript"
key-files:
  created:
    - backend/tests/test_sample_real_transcript.py
    - .planning/phases/02-erfassung-aller-dateien/02-16b-PLAN.md
  modified:
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/tests/test_api_routes.py
    - backend/tests/test_php_gates.py
    - php/lib/Service/ExclusionService.php
    - php/lib/Command/ExcludeCommand.php
    - php/lib/Controller/PageController.php
    - php/tests/Unit/ExclusionServiceTest.php
    - php/tests/Unit/PlayControllerTest.php
    - .planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
key-decisions:
  - "02-16b: Stufe Probe ist current.level gleich Level.SAMPLE; die Bedingung steht in den beiden Abfragen des Store (_FILE_IDS_FOR_MEDIA, _SAMPLE_VISIBLE), nicht in den Routen"
  - "02-16b: Abspielseite prüft Nutzer UND Datei (isExcludedUser, isExcludedFile), vor searchAllowed; die Antwort hängt nicht vom Zustand des Backends ab"
  - "02-16b: Steuerzeichen-Prüfung am unveränderten Eintrag, gekürzt werden nur U+0020 am Rand; Reihenfolge der Codes bleibt empty, too_long, invalid"
  - "02-16b: nicht lesbare Konfiguration externer Speicher ist ein eigener Code (mounts_unreadable), Exit FAILURE"
requirements-completed: []
metrics:
  duration: "ca. 17 min"
  completed: 2026-11-13
  tasks: 3
  files: 12
---

# Phase 2 Plan 16b: Steuerzeichen, Probe und Abspielseite Summary

Drei Nacharbeiten nach 02-16: Ausschlussregeln mit Steuerzeichen am Rand werden abgelehnt statt still gekürzt, eine Probe gibt Text nur noch, solange ihr Inhalt auf der Stufe Probe steht, und die Abspielseite zeigt ausgeschlossenen Nutzern und für ausgeschlossene Dateien keinen Ausschnitt mehr.

**php -l und PHPUnit sind für diesen Plan bei Abgabe NICHT gelaufen.** Auf dem Rechner gibt es kein PHP, Docker wurde nicht gestartet. Kein neuer PHPUnit-Fall ist als grün zu werten; GREEN für (A) und RED/GREEN für (C) und den Nebenbefund sind nicht belegt. Die Hauptsitzung prüft im Container. Erwartete Testzahl dort: 511 + 58 = **569** (siehe unten).

## Performance

- **Dauer:** ca. 17 min
- **Beginn:** 2026-11-13T02:28Z (nach dem Einlesen)
- **Ende:** 2026-11-13T02:45Z
- **Tasks:** 3 von 3, dazu der Nebenbefund aus dem Container-Lauf
- **Dateien:** 12 (2 neu, 10 geändert)

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| Plan | Plan, Nachträge in 02-CONTEXT.md, deferred-items | eced02a | 02-16b-PLAN.md, 02-CONTEXT.md, deferred-items.md |
| 1 (B) | Probe: rote Tests | 5308ec3 | backend/tests/test_sample_real_transcript.py |
| 1 (B) | Probe: Umsetzung | 8d3cf30 | store/repo.py, tests/test_api_routes.py |
| 2 (A) | Steuerzeichen am Rand | 5755bde | ExclusionService.php, ExclusionServiceTest.php |
| Zusatz | Nebenbefund occ :exclude --storage | 3ee4529 | ExclusionService.php, ExcludeCommand.php, ExclusionServiceTest.php |
| 3 (C) | Abspielseite | 5fc362f | PageController.php, PlayControllerTest.php, backend/tests/test_php_gates.py |

Alle Commits als street1983nk <k.cherif@outlook.de>, lokal auf main, nicht gepusht. Ausgangsstand 1ba2c39.

## (A) Steuerzeichen am Rand

`ExclusionService::normalised()` begann mit `trim($entry)`; ohne Zeichenliste nimmt trim auch Nullbyte, Tab, Zeilenumbruch und Wagenrücklauf am Rand weg, die Prüfung danach sah sie nicht mehr. Jetzt: `trim($entry, ' ')` (nur U+0020), und Kodierung und Steuerzeichen (`[\x00-\x1F\x7F]`) werden am unveränderten `$entry` geprüft. Die Stelle liegt vor der Listenunterscheidung, gilt also für alle vier Listen. Die Reihenfolge der Codes ist unverändert (empty, too_long, invalid).

Folgen, alle gewollt: `"\t"` oder `" \n "` allein ist invalid statt empty; eine Mount-ID wie `"3\n"` ist invalid (vorher wurde sie zu `3`); `remove` mit einem solchen Eintrag antwortet absent und schreibt nichts; eine gespeicherte Liste mit einem solchen Eintrag ist nicht lesbar und schließt alles aus, bis sie repariert ist.

Am Bestand für Leerzeichen nichts geändert: `'  privat  '` wird `privat`, `' eva '` wird als `eva` geschrieben, `'   '` ist empty.

**RED-Beleg:** der Container-Lauf der Hauptsitzung (511 Tests, 1 Failure, Datensatz "zero byte"). **GREEN: nicht belegt.**

## (B) Probe nur auf Stufe Probe

"Stufe Probe" ist im Bestand `current.level == Level.SAMPLE` (1): daran hängen das Kennzeichen sample im Treffer (`api/search.py`) und `Store.remove_sample` (not_sample bei höherer Stufe). Die Probe wird an genau zwei Stellen sichtbar, beide im Store: `_FILE_IDS_FOR_MEDIA` (Suche über `file_ids_for_media`) und `_SAMPLE_VISIBLE` (Ausschnitt über `media_for_file`). Beide haben jetzt die Bedingung `NOT EXISTS (SELECT 1 FROM current c WHERE c.media_id = s.media_id AND c.level <> :sample)`, der Wert kommt aus `Level.SAMPLE`. Die Routen sind unverändert und erben die Regel.

Was die Routen antworten, an der Route gemessen (TestClient, echte state.db, echter Index):

- Probe auf Inhalt mit echtem Transkript, Datei ohne Verweis (der Weg von occ :sample, Ergebnis stale_rejected): POST /search antwortet Byte für Byte wie vor dem Anlegen der Probe, POST /excerpt Byte für Byte wie für eine unbekannte Datei-ID (`{"known":false,"excerpt":null}`). Verglichen werden Status, Body, content-type, content-length.
- dasselbe mit aktivem Verweis ohne Inhalt (pending).
- Probe zuerst, echtes Transkript danach: Treffer und Ausschnitt der Probe verschwinden.
- aktiver Verweis einer anderen Datei auf denselben Inhalt: nur diese Datei bekommt Treffer und Ausschnitt.
- aktiver Verweis derselben Datei: Treffer (sample false) und Ausschnitt wie bisher.
- Probe auf Stufe Probe: Treffer mit sample true und Ausschnitt wie bisher.

**RED aus dem richtigen Grund:** 5 rot, 4 grün. Die Suche gab `{"fileId":42,"startMs":400,"excerpt":"Das Haushaltsgeheimnis","sample":false}`, der Ausschnitt `{"known":true,"excerpt":"Das Haushaltsgeheimnis"}`. Grün waren vorher die Positivkontrolle, der aktive Verweis derselben Datei, die Probe auf Stufe Probe und die Probe ohne Version.

**Mutationen (Produkt geändert, vier Testdateien, Datei bytegenau zurückgesetzt, sha256 verglichen): 5 von 5 rot.** Suche ohne Stufenbedingung (5 rot); Ausschnitt ohne Stufenbedingung (5 rot); Probe nie sichtbar in der Suche (14 rot); Probe nie sichtbar im Ausschnitt (7 rot); Vergleich `<` statt `<>` (6 rot).

## (C) Abspielseite

`PageController::excerpt` fragt als Erstes `isExcludedUser($uid) || isExcludedFile($fileId)`, vor `searchAllowed` und vor `ExAppService::excerpt`, und antwortet dann `EXCERPT_NONE` mit leerem Text: derselbe Zustand, derselbe Text der Vorlage ("There is no transcript for this file yet."), derselbe Status 200 wie für eine Datei ohne Transkript. Es sind dieselben Fragen, die Suchanbieter (`isExcludedUser`) und Gateway (`isExcludedFile`) seit 02-16 stellen.

- **Was der Ausschluss betrifft (am Code geprüft):** `isExcludedUser` deckt den Nutzer und seine Gruppen; `isExcludedFile` deckt Ordner-Präfix, abgeschaltete Mount-Konfiguration und den Eigentümer des Speichers (also auch die Datei aus dem Home eines ausgeschlossenen Nutzers, die mit einem nicht ausgeschlossenen geteilt ist). Beide werden gefragt.
- **Fail-closed:** ExclusionService antwortet für nicht lesbare Listen, einen Fehler des Gruppen-Backends und einen Fehler des Datei-Cache schon selbst "ausgeschlossen". Wirft die Frage trotzdem, gilt das hier ebenfalls als ausgeschlossen; die Logzeile (warning) nennt nur die Klasse der Ausnahme, weder Nutzer noch Datei.
- **Das Medium spielt weiter:** state ready, WebDAV-Adresse wie bisher. Der Entscheid betrifft den Ausschnitt.
- **Konstruktor:** `ExclusionService $exclusions` als letzter Parameter. Einzige Stelle, die PageController von Hand baut, ist PlayControllerTest (per Suche über das Repo geprüft) und ist nachgezogen.

**Gate-Regel 14** (`backend/tests/test_php_gates.py`): zwei neue Einträge in `EXCLUSION_CHECKS` für `PageController::excerpt` (isExcludedUser und isExcludedFile, jeweils vor `->searchAllowed(` und `->excerpt(`), Docstring ergänzt, ein neuer Selbsttest mit vier Mutationen des echten Quelltexts. Gegen den alten PageController war die Regel rot (3 rot, 29 grün: "PageController.php::excerpt does not ask the exclusions"), nach der Umsetzung 32 grün.

**RED und GREEN der PHPUnit-Fälle: nicht belegt.** Tests und Umsetzung stehen in einem Commit.

## Nebenbefund: occ :exclude --storage bei nicht lesbarer Konfiguration

Umgesetzt (3ee4529), weil klein. `mountConfigured()` gibt `?bool` zurück, null wenn die Tabelle nicht lesbar ist; `add()` antwortet dann `ERROR_MOUNTS_UNREADABLE` (`mounts_unreadable`), der Befehl schreibt "The external storage configurations cannot be read, so the mount id could not be checked and nothing changed. Is the app files_external enabled?" mit Exit FAILURE (1, wie bisher). Nichts wird geschrieben; die Warnung im Log bleibt (nur Klasse). `--remove` schlägt die ID weiter nicht nach und funktioniert auch dann.

## Prüfungen

Alle Befehle seriell in backend/, Exit-Codes aus der Ausgabe gelesen.

| Befehl | Ergebnis |
|--------|----------|
| RED (B): `uv run pytest tests/test_sample_real_transcript.py -q` vor der Umsetzung | Exit 1, 5 rot, 4 grün |
| sechs betroffene Dateien nach der Umsetzung (test_sample_real_transcript, test_sample_layer, test_excerpt_states, test_api_routes, test_excluded_cleanup, test_read_proof_gate) | Exit 0, 155 grün |
| Gate-Regel 14 gegen den alten PageController | Exit 1, 3 rot, 29 grün |
| `uv run pytest tests/test_php_gates.py -q` am Ende | Exit 0, 32 grün (vorher 31) |
| `uv run ruff check .` | Exit 0 |
| `uv run ruff format --check .` | Exit 0, 71 Dateien |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | Exit 0, 0 Fehler, 0 Warnungen |
| `uv run vulture` | Exit 0 |
| `uv run pytest -q` gesamt, nach dem letzten Commit am Code | Exit 0, 937 grün (vorher 927: +9 neue Datei, +1 Gate) |
| php -l | **nicht gelaufen** |
| PHPUnit | **nicht gelaufen** |

`tests/test_read_proof_gate.py` ist unverändert und grün.

**Notbehelf für PHP, kein Syntaxbeweis.** Klammerbilanz außerhalb von Zeichenketten und Kommentaren, genau ein `<?php`, kein `?>`, keine CR, Abgleich der `use`-Zeilen gegen die benutzten Klassennamen über die fünf geänderten PHP-Dateien: ohne Befund (ein Treffer "StorageService ohne use" in ExclusionService.php ist die Klasse im selben Namensraum, vor diesem Plan vorhanden). Positivkontrolle an einer Kopie mit fehlender use-Zeile und überzähliger Klammer schlug an.

### Neue und geänderte PHPUnit-Fälle (ungeprüft, nicht gelaufen)

| Klasse | Änderung | Fälle |
|--------|----------|-------|
| ExclusionServiceTest | neu `testAnEntryWithAControlCharacterIsRefusedInEveryListAtEveryPlaceAndNeverWritten` mit Datenquelle `controlCharacters` (vier Listen, vier Zeichen, Anfang, Ende, Mitte) | +48 |
| ExclusionServiceTest | neu `testOrdinarySpacesAtTheEdgesAreDroppedInEveryListAndNothingElseIs` | +1 |
| ExclusionServiceTest | Datenquelle `answers`: neuer Satz "configurations unreadable" | +1 |
| ExclusionServiceTest | `testAConfigurationTableThatCannotBeReadKnowsNoMountId` umbenannt in `...IsSaidSoAndIsNotAnUnknownMountId` | 0 |
| PlayControllerTest | acht neue Methoden im Abschnitt "the exclusions" | +8 |

Erwartete Gesamtzahl im Container: 511 + 58 = **569**, sofern alles lädt.

### Angepasste Bestandstests (einzeln)

1. **`backend/tests/test_api_routes.py::test_remove_leaves_a_real_transcript_alone`.** Erwartete nach `/sample/remove` einen Treffer mit sample false für Datei 42, die nur eine Probe und keinen Verweis hat: genau das Verhalten, das der Owner-Entscheid abstellt. Jetzt: Antwort not_sample wie bisher, die aktuelle Version steht weiter auf PREVIEW (das eigentliche Anliegen des Tests, vorher nur mittelbar geprüft), kein Treffer ohne Verweis, und mit einem aktiven Verweis der Datei der Treffer mit sample false. Nicht abgeschwächt, sondern auf die neue Regel umgestellt und um die direkte Prüfung der Stufe ergänzt.
2. **`php/tests/Unit/ExclusionServiceTest.php::testAConfigurationTableThatCannotBeReadKnowsNoMountId`.** Erwartete `ERROR_UNKNOWN_MOUNT`; das ist der gemeldete Nebenbefund. Erwartet jetzt `ERROR_MOUNTS_UNREADABLE`, dazu: nichts geschrieben, eine Logzeile mit der Klasse und ohne den Tabellennamen, `remove` geht weiter. Umbenannt.
3. **`backend/tests/test_php_gates.py::test_self_rule14_fires_when_one_of_the_three_checks_is_gone_or_comes_too_late`.** Die Liste für einen leeren Quellbaum hat zwei Zeilen mehr (`PageController.php has no excerpt`, je Frage eine), weil die Regel jetzt vier Stellen kennt. Sonst unverändert.

Keine andere bestehende Erwartung wurde geändert; `PlayControllerTest::controller()` hat nur das Double der Ausschlüsse, einen mitschreibenden Logger und einen Zähler für `searchAllowed` bekommen.

## Risiken für den Container-Lauf

- **ExclusionServiceTest, neue Datenquelle:** 48 Sätze mit Nullbyte, Tab, LF, CR in Zeichenketten; `"\0"` ist als eigenes Literal verkettet (kein Oktal mit der folgenden Ziffer). Der Schritt "gespeicherte Liste" verlässt sich darauf, dass `json_encode` Steuerzeichen als `\u00XX` schreibt und `json_decode` sie zurückgibt.
- **ExclusionServiceTest::service():** Das Callback für `mountConfigured` ist weiter als `: bool` deklariert, die Methode hat jetzt den Rückgabetyp `?bool`; für PHPUnit zulässig, aber ungelaufen.
- **testAConfigurationTableThatCannotBeRead...:** erwartet genau eine Logzeile; sie entsteht in `mountConfigured`, der Logger ist das mitschreibende Double aus setUp.
- **PlayControllerTest:** `answer()` liest `getStatus`, `getApp`, `getTemplateName`, `getRenderAs`, `getParams` und vergleicht zwei solche Arrays mit assertSame; die Kopfzeilen der Antwort vergleiche ich bewusst nicht (`Response::getHeaders` greift auf den Server-Container zu). Ein Fall baut einen echten ExclusionService aus sieben Doubles (`IAppConfig::getValueString` gibt `'eva'`), obwohl die Klasse nur `#[CoversClass(PageController::class)]` trägt; `beStrictAboutCoverageMetadata` ist false. Der Logger wird in einer Schleife über fünf Stufen mit `string|\Stringable` belegt (Muster aus ExclusionServiceTest).
- **Autowiring:** PageController hat zehn Konstruktor-Parameter, der neue ist über seinen Typ auflösbar.
- **ExcludeCommand:** ein neuer Arm im `match`, vor `ERROR_UNREADABLE`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bestandstest hielt das Leck fest] test_remove_leaves_a_real_transcript_alone**
- **Gefunden bei:** Task 1, erster Lauf nach der Umsetzung (1 rot, 154 grün)
- **Fix:** siehe "Angepasste Bestandstests", Punkt 1. `backend/tests/test_api_routes.py` steht nicht in files_modified.
- **Commit:** 8d3cf30

**2. [Rule 2 - Auftrag der Hauptsitzung] Nebenbefund occ :exclude --storage**
- `php/lib/Command/ExcludeCommand.php` steht in files_modified; eigener Commit 3ee4529.

**3. [Rule 3 - Gate] SQL ohne f-String**
- Der erste Entwurf setzte die Stufenbedingung per f-String in beide Abfragen; ruff S608 schlug an. Statt einer Ausnahme steht die Bedingung jetzt in beiden Abfragen ausgeschrieben. Kein Gate gelockert.

### Abweichungen im Ablauf

- **Ein Aufruf des System-Python, ohne Wirkung.** Beim Aufräumen der neuen Testdatei habe ich einmal `python -` mit leerer Eingabe vor `uv run python` gestellt; das System-Python lief mit leerem Skript (keine Datei geändert, nichts installiert), der uv-Teil lief deshalb nicht. Danach nur noch `uv run`. Verstoß gegen "Python nur über uv", folgenlos, hier genannt.
- **TDD in einem Commit je PHP-Task:** wie in 02-16, ausgeführt wurde kein PHPUnit-Fall.
- **Kein l10n:** occ-Texte englisch wie der Bestand; die Abspielseite hat keinen neuen Text.

### Auslegungen (bitte bei Gelegenheit bestätigen)

- **Abspielseite: Prüfung vor searchAllowed.** Ein ausgeschlossener Nutzer sieht "kein Transkript" auch dann, wenn das Backend gerade nicht erreichbar ist oder die Hälften auseinandergelaufen sind (ein nicht ausgeschlossener sähe "kann gerade nicht geladen werden"). Strengere Lesart von "ohne dass das Backend gefragt wird"; so hält es auch der Suchanbieter. Der Paar-Test vergleicht mit "kein Transkript" bei erreichbarem Backend.
- **Ausgeschlossene Datei auf der Abspielseite gilt für jeden Nutzer.** Bis Plan 18 das rückwirkende Aufräumen bringt, kann eine nachträglich ausgeschlossene Datei anderen Nutzern noch Suchtreffer geben (offener Punkt aus 02-16); auf der Abspielseite bekommt für sie schon jetzt niemand mehr einen Ausschnitt. Die Seite ist damit bis Plan 18 strenger als die Suche.
- **Probe ohne aktuelle Version** bleibt "sichtbar" im Sinn der Abfrage, gibt aber nichts aus (kein Treffer ohne Indexdokument, Ausschnitt wie unbekannt, per Test belegt).
- **Stufe Probe heißt genau Level.SAMPLE**, nicht "kleiner als PREVIEW": jede andere Stufe gilt als echtes Transkript.
- **Steuerzeichen** sind wie im Bestand C0 und DEL (`\x00-\x1F`, `\x7F`). C1-Zeichen und Unicode-Leerraum (etwa U+00A0) sind nicht Teil der Regel und werden weder abgelehnt noch gekürzt, wie vorher.
- **`\t` allein ist invalid, nicht empty.** Folgt aus "nur U+0020 wird entfernt".
- **D-02-16** als Kennung für den Entscheid zur Abspielseite in 02-CONTEXT.md ist von mir vergeben (die Nummer war frei, per Suche geprüft).

## Annahmen der Pläne 02-17 bis 02-22

Keiner wurde geändert. Durchsucht nach Probe, sample, Ausschnitt, Abspielseite, play:

- **02-17, 02-22 (Abnahme), deploy-harp, ci/playwright:** nutzen die Probe auf Stufe Probe und die Abspielseite mit einem nicht ausgeschlossenen Nutzer; nicht berührt. In Phase 2 entsteht kein echtes Transkript.
- **02-18:** nennt `fingerprint()`; unverändert. Ein Eintrag mit Steuerzeichen, den jemand per `occ config:app:set` schreibt, macht die Liste jetzt in jedem Fall unlesbar (vorher wurde ein Zeichen am Rand still entfernt), der Fingerabdruck ist dann der für "nicht lesbar".
- **02-21:** die migrierte Probe aus 0.1.0 steht auf Stufe Probe; nicht berührt.
- Die Meldung "No external storage configuration has this mount id." kommt in ci/ und den Workflows nicht vor.

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche: keine neue Route, kein Schema. T-02-59b, T-02-46c und T-02-58b aus dem Plan sind umgesetzt.

## Offene Punkte

- **php -l und PHPUnit im Container** durch die Hauptsitzung (erwartet 569 Tests).
- **`ExclusionService::stored()` liest einen gespeicherten Wert, der nur aus Leerraum besteht, als leere Liste**, und benutzt dafür weiter `trim($raw)` ohne Zeichenliste: auch ein Wert, der nur aus einem Nullbyte oder `\v` besteht, gilt als "keine Regel" statt als nicht lesbar. Betrifft den ganzen gespeicherten Wert, nicht einen Eintrag, und liegt damit außerhalb des Auftrags (A); eine Zeile (`trim($raw, " \t\n\r")`, der Leerraum von JSON) plus Test. Nicht geändert.
- **`MOUNT_ID` ohne Modifikator D:** `/^[1-9][0-9]{0,17}$/` ließe `"3\n"` durch; seit (A) fängt die Steuerzeichen-Prüfung davor das ab. Kein Leck, nur eine zweite Sicherung, die fehlt.
- **Probe ohne Verweis auf einem ausgeschlossenen Speicher** bleibt stehen (deferred-items.md, Zeile 02-16). Sie gibt seit diesem Plan aber keinen Text eines echten Transkripts mehr, nur noch den festen Probetext.
- **Zeitverhalten** der Paare (Suche, Ausschnitt, Abspielseite) ist nicht gemessen. Auf der Abspielseite ist der ausgeschlossene Weg kürzer (kein Aufruf des Backends).
- Unverändert offen aus 02-16: switched_off, ci/discovery/topology.sh, 403 excluded im Lesebeweis, rückwirkendes Aufräumen (Plan 18).

## Self-Check: PASSED

- Dateien vorhanden: backend/tests/test_sample_real_transcript.py, 02-16b-PLAN.md, 02-16b-SUMMARY.md.
- Commits vorhanden: eced02a, 5308ec3, 8d3cf30, 5755bde, 3ee4529, 5fc362f.
