---
phase: 02-erfassung-aller-dateien
plan: 16
subsystem: php-discovery
tags: [disc-02, disc-03, d-02-04, d-02-05, d-02-08, d-02-11, d-02-15a, ausschluss, occ, gateway, suchanbieter, gate]
requires:
  - phase: 02-10
    provides: "Gateway und Kopf-Route mit X-AVS-Reason, ein Auflöseweg (resolve)"
  - phase: 02-12
    provides: "QueueService::admissible mit Klassifikation externer Speicher, readerUid je Kopie (D-02-11)"
  - phase: 02-14
    provides: "info.xml mit 2 Jobs und 4 Befehlen"
  - phase: 02-15
    provides: "Store.remove_refs mit cause exclude, Rückzugsmarke im Index"
provides:
  - "ExclusionService::isExcluded(int storageId, string mountRelativePath), isExcludedFile(int fileId), isExcludedUser(string uid), storageOwner(int storageId): ?string, fingerprint(): string"
  - "ExclusionService::entries(list), validate(list, entries), normalise(list, entry), add(list, entry), remove(list, entry); LIST_USERS, LIST_GROUPS, LIST_FOLDERS, LIST_MOUNTS, LISTS, MAX_ENTRIES 64, MAX_ENTRY_LENGTH 256, RESULT_*, ERROR_*"
  - "occ audio_video_search:exclude --user|--group|--folder|--storage [--remove] [--list]"
  - "QueueService::admissible prüft den Ausschluss; describe verwirft nachträglich ausgeschlossene Zeilen"
  - "GatewayController: 403 excluded (REASON_EXCLUDED, Header X-AVS-Reason) für Inhalts- und Kopf-Route, vor jedem Auflösen"
  - "Search\\Provider: leere Gruppe für ausgeschlossene Nutzer vor jedem Container-Aufruf"
  - "Gate-Regel 14 in backend/tests/test_php_gates.py"
  - "Store.delete_ref und remove_refs(cause exclude) entfernen die Probe der Datei; delete_ref vergisst den Inhalt mit dem letzten Verweis; Capture zieht danach den Index zurück"
affects: [02-17, 02-18, 02-19, 02-20, 02-22, phase-08]
tech-stack:
  added: []
  patterns:
    - "Eine Vergleichsstelle für alle Ausschlüsse, drei Prüfstellen mit den Regeln des Augenblicks"
    - "Jeder Zweifel schließt aus: nicht lesbare Regeln, Fehler von Mount-Cache, Gruppen-Backend oder Datei-Cache"
    - "Gateway prüft aus dem Datei-Cache allein: kein Nutzer aufgesetzt, kein Speicher berührt"
    - "Antwort für ausgeschlossene Nutzer gleich der einer Suche ohne Treffer, als Paar-Test"
key-files:
  created:
    - php/lib/Service/ExclusionService.php
    - php/lib/Command/ExcludeCommand.php
    - php/tests/Unit/ExclusionServiceTest.php
    - backend/tests/test_excluded_cleanup.py
  modified:
    - php/lib/Service/QueueService.php
    - php/lib/Controller/GatewayController.php
    - php/lib/Search/Provider.php
    - php/appinfo/info.xml
    - php/tests/Unit/ProviderTest.php
    - php/tests/Unit/QueueServiceTest.php
    - php/tests/Unit/GatewayControllerTest.php
    - backend/tests/test_php_gates.py
    - backend/src/audio_video_search_backend/store/repo.py
    - backend/src/audio_video_search_backend/worker/capture.py
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
key-decisions:
  - "02-16: Listen als JSON-Text in der App-Konfiguration (setValueString); gelesen als Text, damit kaputtes JSON nicht als leere Liste gilt; ein mit Typ array gespeicherter Wert wird gelesen und beim nächsten Schreiben als Text neu angelegt"
  - "02-16: Nicht vollständig lesbare Listen (kein JSON, unbrauchbarer Eintrag, mehr als 64 Einträge, fremder Typ) schließen alles aus, bis sie repariert sind; ein doppelter Eintrag ist eine Regel und kein Fehler"
  - "02-16: Eigentümer eines Speichers: der Nutzer seines Home-Mounts, sonst der eine Nutzer aller ConfigAdapter-Mounts; Mounts anderer Anbieter (Freigaben) zählen nicht; Gruppenordner und Speicher mehrerer Nutzer gehören niemandem"
  - "02-16: Eine abgeschaltete Mount-Konfiguration schließt jeden Speicher aus, den sie erreicht, auch wenn eine zweite Konfiguration denselben Speicher erreicht"
  - "02-16: Nutzer-IDs ohne Rücksicht auf Groß- und Kleinschreibung, Gruppen-IDs und Ordner genau; Ordner in NFC"
  - "02-16: Ein Präfix mit files/ vorn gilt zusätzlich ohne files/ (schließt mehr aus, nie weniger)"
  - "02-16: Gateway prüft den Ausschluss vor resolve, über Datei-ID und Datei-Cache; eine Datei, die der Cache nicht kennt, bleibt die 404 wie bisher"
  - "02-16: occ-Antworten auf eine Änderung wiederholen den Wert nie; nur --list nennt die Regeln; Texte englisch wie alle occ-Texte des Bestands"
  - "02-16: 403 excluded im Lesebeweis bleibt read_denied (nicht geändert, Entscheid offen)"
requirements-completed: []
metrics:
  duration: "ca. 2 h 15 min Arbeitszeit, durch ein Nutzungslimit unterbrochen (Beginn 2026-11-12T20:02Z, Ende 2026-11-13T02:05Z)"
  completed: 2026-11-13
  tasks: 2
  files: 15
---

# Phase 2 Plan 16: Ausschlüsse vor dem ersten Durchlauf Summary

Nutzer, Gruppen, Ordner und externe Speicher lassen sich jetzt per `occ audio_video_search:exclude` ausschließen; ExclusionService entscheidet an einer Stelle, und der Ausschluss wird beim Einreihen, bei der Ausgabe an den Container und im Gateway samt Kopf-Route (403 excluded, ohne die Datei aufzulösen oder zu öffnen) geprüft, ausgeschlossene Nutzer bekommen keine Treffer.

**php -l und PHPUnit sind für diesen Plan bei Abgabe NICHT gelaufen.** Auf dem Rechner gibt es kein PHP, Docker wurde nicht gestartet. Kein neuer PHPUnit-Fall ist als grün zu werten, RED und GREEN der PHP-Seite sind nicht belegt. Die Hauptsitzung prüft im Container (php -l, PHPUnit 11.5 in nextcloud/server stable34).

## Performance

- **Dauer:** ca. 2 h 15 min Arbeitszeit; der Lauf wurde durch ein Nutzungslimit unterbrochen und am 13.11. fortgesetzt (Stand vorher selbst geprüft: zwei Commits, eine unversionierte, vollständige Testdatei)
- **Beginn:** 2026-11-12T20:02Z (nach dem Einlesen)
- **Ende:** 2026-11-13T02:05Z
- **Tasks:** 2 von 2, dazu zwei für Plan 16 vorgemerkte Python-Punkte
- **Dateien:** 15 (4 neu, 11 geändert)

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | ExclusionService und occ :exclude | 14ca912 | ExclusionService.php, ExcludeCommand.php, info.xml, ExclusionServiceTest.php |
| 2 | Dreifache Prüfung, Provider-Sperre, Gate-Regel 14 | 68bee89 | QueueService.php, GatewayController.php, Provider.php, ProviderTest.php, QueueServiceTest.php, GatewayControllerTest.php, test_php_gates.py |
| Zusatz | Vorgemerkte Punkte: rote Tests | 1816871 | backend/tests/test_excluded_cleanup.py |
| Zusatz | Vorgemerkte Punkte: Umsetzung | f8fbaee | store/repo.py, worker/capture.py, test_excluded_cleanup.py |

Alle Commits als street1983nk <k.cherif@outlook.de>, lokal auf main, nicht gepusht. Ausgangsstand a3a0b35.

## Was gebaut wurde

**Vier Listen (ExclusionService).** `excluded_users`, `excluded_groups`, `excluded_folders`, `excluded_mounts` in der App-Konfiguration, je eine JSON-Liste, also auch per `occ config:app:set` vor der Installation des Backends setzbar. Höchstens 64 Einträge je Liste, höchstens 256 Bytes je Eintrag, keine Steuerzeichen.

- **Ordner:** Präfix relativ zur Wurzel des Mounts (nach Findling, ohne dessen Muster-Sprache). `privat` trifft `privat/a.mp3` in jedem Home und jedem anderen Mount, nicht `privatsache/a.mp3`. Mehrfache Schrägstriche fallen zusammen, ein Segment `.` oder `..` wird abgewiesen und nicht gefiltert (T-02-59).
- **Nutzer und Gruppen:** `isExcludedUser` ist wahr für einen Nutzer der Liste oder ein Mitglied einer ausgeschlossenen Gruppe (IGroupManager::isInGroup).
- **Eigentum (D-02-08, D-02-11):** `storageOwner` liest den Mount-Cache. Ein Home gehört seinem Nutzer, auch wenn andere eine Freigabe daraus haben. Ein externer Speicher gehört einem Nutzer, wenn alle ConfigAdapter-Mounts des Speichers genau ihn nennen; das gilt auch für den Speicher, den files_external aus einer Admin-Konfiguration mit den Anmeldedaten je Nutzer baut. Der Speicher von ana auf derselben Freigabe ist ein anderer und bleibt. Gruppenordner und ein Speicher für mehrere Nutzer gehören niemandem.
- **Externe Speicher (DISC-02):** Steht die Mount-ID einer Konfiguration in `excluded_mounts`, ist jeder Speicher ausgeschlossen, den sie erreicht.
- **fingerprint():** sha256 über die vier Listen in fester Reihenfolge, jede sortiert (Name der Liste, Zeilenumbruch, Einträge je Zeile, Listen durch Nullbyte getrennt); nicht lesbare Listen haben einen eigenen Wert. Für Plan 18.

**Jeder Zweifel schließt aus.** Ist eine Liste nicht vollständig lesbar, gilt alles als ausgeschlossen (jede Datei, jeder Nutzer), mit einer Warnung je Prozess, die nur den Namen der Liste nennt. Scheitert der Mount-Cache, während eine Regel ihn braucht, ist der Speicher ausgeschlossen; scheitert das Gruppen-Backend, der Nutzer; scheitert der Datei-Cache im Gateway, die Datei. Ohne Regel wird weder Mount-Cache noch Gruppen-Backend gefragt.

**occ audio_video_search:exclude.** `--user=<uid>`, `--group=<gid>`, `--folder=<Präfix>`, `--storage=<Mount-ID>`, mehrere zugleich möglich; `--remove` nimmt die Einträge heraus, `--list` druckt die Regeln (nach einer Änderung desselben Aufrufs). `--storage` nimmt nur eine Mount-ID, die in `oc_external_mounts` steht; beim Entfernen wird nicht nachgesehen, damit die Regel einer gelöschten Konfiguration zurückgenommen werden kann. Ein Nutzer oder eine Gruppe, die es nicht gibt, wird eingetragen, mit einem Hinweis (ein Tippfehler bliebe sonst unbemerkt). Der Befehl schreibt nur die App-Konfiguration. Exit-Codes: SUCCESS, wenn jede Änderung gemacht ist oder schon galt; INVALID für unbrauchbare Optionen und Werte; FAILURE bei voller Liste, unbekannter Mount-ID und nicht lesbaren Listen.

**Drei Prüfstellen (T-02-57), jede mit Kommentar, warum dreimal.**
1. `QueueService::admissible` fragt `isExcluded`, vor der Klassifikation des Speichers: eine ausgeschlossene Datei wird nie eingereiht (Ereignis, Crawl, Rescan-Funde gehen alle hier durch).
2. `QueueService::describe` ruft `admissible` erneut mit den Regeln von jetzt: eine Zeile, die vor der Regel eingereiht wurde, wird verworfen und gezählt.
3. `GatewayController::getFileContents` und `getFileHead` fragen `isExcludedFile`, bevor irgendetwas aufgelöst wird: 403 mit `code` excluded und `X-AVS-Reason: excluded`. Die Prüfung liest nur den Datei-Cache; kein Nutzer wird aufgesetzt, kein Speicher berührt, `fopen` nie aufgerufen. Der Guard gegen fremde ExApps bleibt die erste Anweisung; ein fremder Aufrufer bekommt für eine ausgeschlossene Datei dieselbe Antwort wie für jede andere, die Ausschlüsse werden dafür nicht einmal gefragt.

**Suchanbieter (T-02-58).** `Provider::search` fragt `isExcludedUser` vor `searchAllowed` und vor der Suche im Container. Die Antwort ist die einer Suche ohne Treffer (Paar-Test über `jsonSerialize`), die Logzeile nennt weder Nutzer noch Suchwort.

**Gate-Regel 14.** Keine andere Datei unter `php/lib` definiert eine Methode `isExcluded*` oder nennt einen der vier Listenschlüssel; `admissible` fragt `isExcluded` vor der Klassifikation, `describeRow` geht über `admissible`, beide Gateway-Routen fragen `isExcludedFile` vor `resolve`, `fopen` und `actAs`, `Provider::search` fragt `isExcludedUser` vor `searchAllowed`, `search` und `entries`. Gelesen werden Methodenrümpfe ohne Kommentare und Zeichenketten. Vier neue Tests, darunter Selbsttests mit sieben Mutationen des echten Quelltexts.

**Logs (T-02-60).** Neue Zeilen nennen nur den Namen einer Liste, Datei-ID, Speicher-ID, Grund und Klasse einer Ausnahme; nie einen Nutzer, eine Gruppe, einen Präfix oder einen Pfad. Per Test belegt (PHP, ungelaufen) für nicht lesbare Listen, Mount-Cache, Gruppen-Backend, Datei-Cache, Gateway und Suchanbieter.

## Die drei für Plan 16 vorgemerkten Punkte

| Punkt | Ergebnis |
|-------|----------|
| (a) `delete_ref` bei 403 excluded merkt nur vor | **Erledigt**, testgetrieben (1816871 rot, f8fbaee grün). `Store.delete_ref` wendet die Regel des exclude-Auftrags an: der Inhalt geht mit dem letzten Verweis sofort (Wörter, Transkripte, Korrekturen, Schlüssel, media, Rückzugsmarke). Hält ein anderer Verweis den Inhalt, bleibt alles; ist keiner davon aktiv, wird nur vorgemerkt (Regel aus 02-15). `Capture` zieht direkt danach unter derselben Sperre den Index zurück; scheitert das, bleibt die Marke für den nächsten Lauf. |
| (b) 403 excluded der Kopf-Route im Lesebeweis gilt als read_denied | **Nicht geändert, offener Punkt.** Der Plan trifft die Entscheidung nicht. Stand: Verweis wird unreadable (kein Treffer), behält seinen Inhalt, und der exclude-Auftrag aus Plan 18 löscht ihn und vergisst den Inhalt nach derselben Regel wie (a). Ein eigenes Ergebnis excluded würde read_proof.py, test_read_proof_gate.py und den CI-Patch unter ci/leak-control ändern. Empfehlung: so lassen. |
| (c) Probe einer ausgeschlossenen Datei bleibt stehen (D-02-15a) | **Erledigt für den Ausschluss**, testgetrieben (dieselben Commits). exclude (je Datei, auch ohne Verweis der Erfassung), exclude_storage (Dateien der gelöschten Verweise) und 403 excluded beim Download löschen die Probe der Datei; zeigt danach nichts mehr auf den Inhalt, geht er samt Index-Dokumenten. Die Probe einer anderen Datei auf demselben Inhalt bleibt, jede andere Ursache (delete, gone, vanished_expired, trash) fasst keine Probe an. Phase 8 (Vergessen) bleibt offen. Rest siehe Offene Punkte. |

Der Befund "Probe gibt Text eines Inhalts mit echtem Transkript" aus 02-15c ist nicht angefasst und wird von diesem Plan nicht geregelt.

## Prüfungen

Alle Befehle seriell in backend/, Exit-Codes aus der Ausgabe gelesen.

| Befehl | Ergebnis |
|--------|----------|
| Task 1 verify: `uv run pytest tests/test_php_gates.py tests/test_store_metadata.py -x -q` | Exit 0, 40 grün |
| Zusätzlich nach Task 1: test_read_proof_gate, test_lockstep_versions, test_release_archives, test_public_texts, test_trilingual | Exit 0, 79 grün |
| Task 2 verify: `uv run pytest tests/test_php_gates.py -x -q` | Exit 0, 31 grün (vorher 27) |
| `uv run ruff check .` | Exit 0 |
| `uv run ruff format --check .` | Exit 0, 70 Dateien |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | Exit 0, 0 Fehler, 0 Warnungen |
| `uv run vulture` | Exit 0 |
| RED der Python-Punkte: `uv run pytest tests/test_excluded_cleanup.py -q` vor der Umsetzung | Exit 1, 12 rot, 8 grün |
| Sieben betroffene Dateien nach der Umsetzung (test_excluded_cleanup, test_exclusion_forget, test_intake, test_capture, test_read_proof_gate, test_sample_layer, test_read_proof) | Exit 0, 367 grün |
| `uv run pytest -q` gesamt, nach dem letzten Commit am Code | Exit 0, 927 grün (vorher 903: +4 Gate, +20 neue Datei) |
| php -l | **nicht gelaufen** |
| PHPUnit | **nicht gelaufen** |

**RED aus dem richtigen Grund (Python).** Die 12 roten Fälle scheiterten daran, dass die Probe stehen blieb (`sample_media(10)` nannte den Inhalt) und dass `delete_ref` den Inhalt nur vormerkte (`(1, 1, 1, 0)` statt `(0, 0, 0, 0)` Zeilen). Kein Import- oder Syntaxfehler. Die 8 vorher grünen Fälle halten Bestand fest (anderer Verweis hält den Inhalt, andere Ursachen, veralteter Claim, delete und trash aus der Warteschlange); jede davon wird von einer Mutation unten rot.

**Mutationen (Produkt geändert, vier Testdateien gelaufen, Datei bytegenau zurückgesetzt, sha256 verglichen): 9 von 9 rot.** Probe bleibt trotz Ausschluss (zwei Varianten); delete_ref merkt nur vor; delete_ref lässt die Probe; andere Ursachen nehmen die Probe mit; Speicher-Ausschluss lässt Proben; Erfassung zieht den Index nicht zurück; Index-Fehler bricht den Schritt; Vergessen trotz haltender Kopie.

**Ein Testfehler im ersten ganzen Lauf, behoben.** `test_an_index_that_fails_keeps_the_mark_and_the_step` verglich alle Logzeilen und sah im ganzen Lauf auch die anderer Logger; er filtert jetzt auf den Logger der Erfassung. Keine Erwartung abgeschwächt.

**Gate aus Plan 13.** `tests/test_read_proof_gate.py` ist unverändert und grün. read_proof.py und der CI-Patch sind unberührt; capture.py hat keinen neuen Import, GatewayController nennt keine Konfigurationsklasse (Regel d), die neuen Store-Anweisungen sind DELETEs.

**Notbehelf für PHP, kein Syntaxbeweis.** Klammerbilanz außerhalb von Zeichenketten und Kommentaren, genau ein `<?php`, kein `?>`, LF-Zeilenenden und Abgleich der `use`-Zeilen gegen die benutzten Klassennamen über alle neun neuen und geänderten PHP-Dateien: ohne Befund (Positivkontrolle an einer Kopie mit fehlender use-Zeile und überzähliger Klammer schlug an). info.xml mit ElementTree gelesen: zwei Jobs, fünf Befehle.

### Neue und geänderte PHPUnit-Fälle (ungeprüft, nicht gelaufen)

| Klasse | Methoden vorher | nachher | Fälle |
|--------|-----------------|---------|-------|
| ExclusionServiceTest (neu) | 0 | 41 | 76 (vier Datenquellen mit 12, 14, 10 und 3 Sätzen) |
| ProviderTest | 18 | 22 | +4 |
| QueueServiceTest | 18 | 22 | +4 |
| GatewayControllerTest | 35 | 42 | +7 |

Erwartete Gesamtzahl im Container: 420 + 91 = 511 Tests, sofern alles lädt (ein Fall überspringt sich ohne intl).

ExclusionServiceTest deckt: Ordner (Präfix in jedem Home, nicht `privatsache`, Schreibweise mit `files/`, 12 abgewiesene Formen, eine Schreibweise, NFC), Grenzen und Doppelte, Nutzer und Gruppen, Eigentum, D-02-08, Gruppe je Mitglied, D-02-11, abgeschaltete Konfiguration, eine Frage je Speicher, 14 nicht lesbare gespeicherte Werte, Logzeile ohne Regel, Typ array, Fehler von Mount-Cache, Gruppen-Backend und Datei-Cache, Urteil aus dem Datei-Cache, Fingerabdruck, Schreiben, Mount-ID, und 10 Methoden zum Befehl.

## Belege am Quelltext (nextcloud/server stable34, gelesen, nicht gelaufen)

- `lib/public/IAppConfig.php`: `getValueString($app, $key, $default = '', $lazy = false)`, `getValueArray(...)`, `setValueString($app, $key, $value, $lazy = false, $sensitive = false): bool`, `deleteKey($app, $key): void`.
- `lib/private/AppConfig.php`: `getValueArray` fängt JsonException und gibt `[]` zurück (deshalb wird als Text gelesen); `getTypedValue` wirft AppConfigTypeConflictException nur, wenn der gespeicherte Typ weder mixed noch der verlangte ist; `setTypedValue` nimmt einen anderen Typ nur über einem mixed-Wert an.
- `core/Command/Config/App/SetConfig.php`: ohne `--type` wird ein neuer Schlüssel als mixed gespeichert.
- `lib/public/Exceptions/AppConfigTypeConflictException.php` vorhanden.
- `lib/public/IGroupManager.php`: `isInGroup($userId, $group)`, `groupExists($gid)`; `lib/public/IUserManager.php`: `userExists(string $uid, array $excludeBackends = [])`.
- `lib/public/Files/Config/ICachedMountInfo.php`: `getUser(): IUser`, `getMountId(): ?int`, `getMountProvider(): string`; `IUserMountCache::getMountsForStorageId($numericStorageId, $user = null)` (beides schon im Bestand benutzt).

## Risiken für den Container-Lauf

- **ExclusionService.php:** Eigenschaft mit Typ `array|false|null`; `catch` ohne Variable; `array_is_list`; Abfrage auf `external_mounts` wie in StorageClassifier.
- **ExclusionServiceTest.php:** Teil-Mock über `getMockBuilder(...)->onlyMethods(['mountConfigured'])` einer geschützten Methode (Muster aus StorageClassifierTest); Datensätze mit Nullbyte und ungültigem UTF-8 in einer Datenquelle; `OutputFormatter::escape` mit `<alt>` in der Ausgabe von `--list` (erwartet wird der Text ohne Rückstrich); der NFC-Fall überspringt sich ohne intl; Logger-Double für fünf Stufen mit `string|\Stringable`.
- **GatewayControllerTest.php:** In zwei Fällen steht `expects(self::never())` neben einem vorher gesetzten Stub derselben Methode (Muster gibt es im Bestand für `setVolatileActiveUser`).
- **ProviderTest.php:** Paar-Vergleich zweier `SearchResult::jsonSerialize()` mit assertSame.
- **Autowiring:** ExclusionService hat sieben Konstruktor-Parameter, alle über Typen auflösbar; QueueService, GatewayController und Provider haben je einen Parameter mehr am Ende. Andere Stellen im Baum bauen diese Klassen nicht von Hand (per Suche geprüft).
- **Jobliste und Befehle:** ein neuer Eintrag unter commands, Version unverändert 0.1.0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] QueueServiceTest und GatewayControllerTest angepasst**
- **Gefunden bei:** Task 2
- **Problem:** QueueService und GatewayController haben einen Konstruktor-Parameter mehr; beide Testklassen stehen nicht in files_modified.
- **Fix:** Double von ExclusionService in beiden, dazu 4 und 7 neue Fälle. Keine bestehende Erwartung geändert.
- **Commit:** 68bee89

**2. [Rule 2 - Datenschutz] Nicht lesbare Regeln schließen alles aus**
- **Problem:** Die Findling-Vorlage liest eine kaputte Liste als leer und kürzt über der Obergrenze still, beides in die falsche Richtung. `IAppConfig::getValueArray` gibt für Text, der kein JSON ist, eine leere Liste.
- **Fix:** Lesen als Text, strenge Prüfung, sonst alles ausgeschlossen bis zur Reparatur; `--list` und jede Änderung nennen den Schlüssel.
- **Commit:** 14ca912

**3. [Rule 2 - Datenschutz] Gateway prüft vor dem Auflösen**
- **Problem:** "ohne die Datei zu öffnen" ließe zu, erst den Nutzer aufzusetzen; das würde den Mount eines abgeschalteten externen Speichers aufbauen.
- **Fix:** `isExcludedFile` liest nur den Datei-Cache und steht vor `resolve`.
- **Commit:** 68bee89

**4. [Rule 2 - D-02-04, D-02-15a] Zwei vorgemerkte Python-Punkte**
- Siehe Tabelle oben; `backend/src` und die neue Testdatei stehen nicht in files_modified. Auftrag der Hauptsitzung.
- **Commits:** 1816871, f8fbaee

### Abweichungen von den Schnittstellen des Plans

- **Speicherform:** Der Plan sagt "JSON-Listen"; gebaut als JSON-Text (Typ string), nicht über setValueArray, aus dem Grund unter Abweichung 2.
- **Zusätzliche Methoden:** `isExcludedFile`, `entries`, `validate`, `normalise`, `add`, `remove`.
- **Tests zum Befehl** stehen in ExclusionServiceTest.php (einzige Testdatei des Plans für Task 1).
- **TDD in einem Commit je Task (PHP):** Tests und Umsetzung stehen je Task in einem Commit, wie der Plan es nennt; ausgeführt wurde kein PHPUnit-Fall.
- **Kein l10n:** occ-Texte sind im Bestand englisch und nicht übersetzt; der Suchanbieter hat keinen neuen Text.

### Auslegungen (bitte bei Gelegenheit bestätigen)

- **Eigentümer trotz Freigabe.** Der Plan sagt "wenn alle oc_mounts-Zeilen des Speichers genau einen Nutzer nennen". Eine Freigabe aus einem Home steht in oc_mounts unter derselben Speicher-ID mit dem Empfänger; wörtlich hätte ein ausgeschlossener Nutzer mit einer einzigen Freigabe sein Home wieder erfasst. Gebaut: der Home-Mount entscheidet, sonst zählen nur ConfigAdapter-Mounts.
- **Zwei Konfigurationen auf einem Speicher.** Eine abgeschaltete genügt für den Ausschluss.
- **Nutzer-IDs ohne Groß- und Kleinschreibung**, Gruppen-IDs genau (so vergleicht Nextcloud).
- **`files/privat`** gilt auch als `privat`.
- **Unbekannte Nutzer und Gruppen** werden eingetragen, mit Hinweis (D-02-05: vor dem ersten Durchlauf, auch vor dem Anlegen des Kontos).
- **Fingerabdruck** über die Einträge, wie sie gespeichert sind; `Eva` und `eva` sind dieselbe Regel, aber zwei Fingerabdrücke.
- **Probe und Verwaist-Marke.** Zeigt nach dem Ausschluss noch die Probe einer anderen Datei auf den Inhalt und kein Verweis der Erfassung, bekommt der Inhalt die Marke (D-02-15a: sie richtet sich nur nach echten Verweisen und versteckt keinen Probetreffer).

## Annahmen der Pläne 02-17 bis 02-22

Keiner wurde geändert. Berührt:

- **02-17, 02-22 (Abnahme):** `ci/discovery/topology.sh` ruft `exclude --user=`, `--group=`, `--folder=`, `--storage=<Mount-ID>` und `--list`; das passt. Die Abnahme setzt die Ausschlüsse vor dem ersten Durchlauf zum Teil, bevor der Befehl existiert, über `occ config:app:set` als JSON-Text: wird gelesen. Der Ersatzweg schriebe `--storage` aber in `excluded_storages`, der Schlüssel heißt `excluded_mounts` (läuft nicht mehr, sobald der Befehl da ist).
- **02-18:** `fingerprint()` ist da; der Plan nennt `ExclusionService::mountRelativePath`, das es hier nicht gibt (der Pfadraum kommt aus `StorageService::mountRelativePath`). Der Speicher-Ausschluss kennt Proben nur über Verweise (siehe Offene Punkte); ein exclude-Auftrag je Datei entfernt auch eine Probe ohne Verweis.
- **02-19 bis 02-21:** keine Annahme berührt, soweit aus den Plänen ersichtlich.

## Offene Punkte

- **php -l und PHPUnit im Container** durch die Hauptsitzung.
- **Abspielseite gibt einem ausgeschlossenen Nutzer weiter einen Ausschnitt** für eine Datei, die er lesen darf und die für andere erfasst ist. Kein Suchtreffer, aber Text bei bekannter Datei-ID. PageController steht nicht im Plan; kleiner Fix mit Paar-Test möglich, Owner-Entscheid (deferred-items.md).
- **`switched_off` wird nicht gesetzt.** Eine abgeschaltete Konfiguration wird nie eingereiht und nie geladen, aber weiter eingestuft, stündlich vom Rescan gelesen (nur Metadaten) und gecrawlt; `occ :status` nennt sie nicht als übersprungen. StorageClassifier steht nicht im Plan (deferred-items.md).
- **Rückwirkendes Aufräumen** (Verweise und Inhalte von Dateien, die vor der Regel erfasst wurden) ist Plan 18. Bis dahin gibt eine nachträglich ausgeschlossene Datei anderen Nutzern weiter Treffer; neue Downloads und Lesebeweise scheitern am Gateway.
- **403 excluded im Lesebeweis** (Punkt b oben).
- **Probe ohne Verweis auf einem ausgeschlossenen Speicher** bleibt stehen (deferred-items.md).
- **Zeitverhalten** der 403 excluded gegenüber der 404 ist nicht gemessen; der Aufrufer ist nur das eigene Backend.
- **Stale-Zeit der Regeln:** Die Listen werden je Prozess einmal gelesen; ein Cron-Lauf, der schon läuft, sieht eine neue Regel erst im nächsten Prozess. Gateway und Suche sind eigene Anfragen und sehen sie sofort.

## Known Stubs

Keine. DISC-02 und DISC-03 stehen nicht unter requirements-completed: wie in den Vorgängern erst nach Plan 18 und der Abnahme. STATE.md, ROADMAP.md und REQUIREMENTS.md habe ich nicht angefasst.

## Threat Flags

Keine neue Oberfläche über das Threat-Register hinaus: keine neue Route, kein neues Schema. T-02-57 (drei Prüfstellen, Gate-Regel 14), T-02-58 (Provider leer, Paar-Test), T-02-59 (normalise und validate) und T-02-60 (keine Regeln in Logs) sind umgesetzt. Der neue occ-Befehl schreibt nur vier Schlüssel der App-Konfiguration.

## Self-Check: PASSED

- Dateien vorhanden: php/lib/Service/ExclusionService.php, php/lib/Command/ExcludeCommand.php, php/tests/Unit/ExclusionServiceTest.php, backend/tests/test_excluded_cleanup.py, 02-16-SUMMARY.md.
- Commits vorhanden: 14ca912, 68bee89, 1816871, f8fbaee.
