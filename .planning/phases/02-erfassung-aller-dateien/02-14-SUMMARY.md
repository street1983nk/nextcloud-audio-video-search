---
phase: 02-erfassung-aller-dateien
plan: 14
subsystem: php-discovery
tags: [disc-04, disc-02, rescan, external-storage, files_external, scanner, timed-job, occ, files_no_background_scan]
requires:
  - phase: 02-07
    provides: "CacheEventListener reiht Scanner-Funde (Insert, Update, Remove) ein"
  - phase: 02-12
    provides: "avs_storage mit capturable, mount_id, share_key_hash; StorageClassifier mit Probe je Speicher; StorageService::isExternal"
provides:
  - "RescanService::due(), all(), run(bool $onlyDue = true), rescan(int $storageId, int $deadline), deadline(), backgroundScanDisabled(), backgroundRescan()"
  - "Konstanten RESCAN_SECONDS 86400, BUDGET_SECONDS 300, MAX_READER_TRIES 5, STATUS_SCANNED, STATUS_PARTIAL, STATUS_FAILED, STATUS_NOT_CAPTURABLE, BACKGROUND_ON, BACKGROUND_DISABLED"
  - "ExternalRescanJob (TimedJob, 3600 s), in info.xml unter background-jobs"
  - "occ audio_video_search:rescan --storage=<id> | --all, in info.xml unter commands"
  - "occ audio_video_search:status: Zeile zum Rescan und JSON-Schlüssel backgroundRescan (on, disabled_by_config)"
  - "StorageStateMapper::rescanCandidates(), markRescanned(); StorageService::mediaRows(); StorageClassifier::probe() öffentlich"
affects: [02-16, 02-17, 02-19, 02-20, 02-22]
tech-stack:
  added: []
  patterns:
    - "Rescan über den Scanner von Nextcloud, Funde nur über Cache-Ereignisse; der Dienst reiht selbst nichts ein"
    - "Zeitgrenze im laufenden Scan über die Ordner-Hooks des Scanners, außerhalb der Transaktion eines Ordners"
    - "Gescannt wird nur ein Speicher, den die Probe des StorageClassifier herausgibt"
key-files:
  created:
    - php/lib/Service/RescanService.php
    - php/lib/BackgroundJobs/ExternalRescanJob.php
    - php/lib/Command/RescanCommand.php
    - php/tests/Unit/RescanServiceTest.php
  modified:
    - php/lib/Command/StatusCommand.php
    - php/appinfo/info.xml
    - php/lib/Db/StorageStateMapper.php
    - php/lib/Service/StorageService.php
    - php/lib/Service/StorageClassifier.php
    - php/tests/Unit/FilesCommandTest.php
    - php/tests/Unit/StorageStateMapperTest.php
    - php/tests/Unit/StorageServiceTest.php
key-decisions:
  - "02-14: Das Budget gilt auch im laufenden Scan: an der nächsten Ordnergrenze nach Ablauf bricht er ab (Status partial), rescanned_at bleibt"
  - "02-14: Reihenfolge: Freigabe, die am längsten wartet, zuerst; darin der Speicher mit den meisten Medienzeilen zuerst, bei Gleichstand die kleinere Speicher-ID"
  - "02-14: Leser ist der erste Nutzer (nach UID, höchstens 5) der klassifizierten Mount-Konfiguration, für den StorageClassifier::probe einen Speicher herausgibt"
  - "02-14: Vor dem vollen Lauf ruft rescan() backgroundScan() auf, damit unfertige Ordner zuerst drankommen"
  - "02-14: occ rescan endet nur mit SUCCESS, wenn jeder verlangte Speicher bis zum Ende gescannt wurde; partial und failed sind FAILURE"
  - "02-14: Ein Home oder Gruppenordner ist für --storage 'Storage not capturable.', der Rescan gilt nur externen Speichern"
requirements-completed: []
metrics:
  duration: "ca. 15 min ab Wiederaufnahme (Einlesen lag im unterbrochenen ersten Lauf)"
  completed: 2026-11-12
  tasks: 2
  files: 12
---

# Phase 2 Plan 14: Rescan externer Speicher Summary

Jeder erfassbare externe Speicher wird jetzt einmal in 24 h mit dem Scanner von Nextcloud neu gelesen (stündlicher Zeitjob, 300 s je Lauf, Abbruch an der nächsten Ordnergrenze), und `occ audio_video_search:rescan --storage=<id> | --all` erzwingt denselben Lauf sofort; was der Scanner findet, reiht der vorhandene CacheEventListener ein.

**php -l und PHPUnit sind für diesen Plan bei Abgabe NICHT gelaufen.** Auf dem Rechner gibt es kein PHP, Docker durfte nicht gestartet werden. Die Hauptsitzung prüft im Container (php -l über alle Dateien, PHPUnit 11.5.57 in nextcloud/server stable34 mit PHP 8.2). Bis dahin ist kein neuer PHPUnit-Fall als grün zu werten.

## Performance

- **Dauer:** ca. 15 min ab Wiederaufnahme nach dem Nutzungslimit; das Einlesen der Planunterlagen lag im unterbrochenen ersten Lauf
- **Wiederaufnahme:** 2026-11-12T18:30:54Z
- **Ende:** 2026-11-12T18:50Z
- **Tasks:** 2 von 2
- **Dateien:** 12 (4 neu, 8 geändert)

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | RescanService und ExternalRescanJob | 65de734 | RescanService.php, ExternalRescanJob.php, info.xml, RescanServiceTest.php, StorageStateMapper.php, StorageService.php, StorageClassifier.php, StorageStateMapperTest.php, StorageServiceTest.php |
| 2 | occ audio_video_search:rescan | c2b3760 | RescanCommand.php, StatusCommand.php, info.xml, RescanServiceTest.php, FilesCommandTest.php |

Beide Commits als street1983nk <k.cherif@outlook.de>, lokal auf main, nicht gepusht. Ausgangsstand acc68b8.

## Was gebaut wurde

**Fälligkeit und Reihenfolge (RescanService::due, all).** Kandidaten sind die Zeilen von avs_storage mit capturable 1, die zugleich externe Speicher der Mountmenge sind (`StorageService::isExternal`). Fällig ist ein Speicher ohne rescanned_at oder mit einem, das 86400 s oder älter ist. Speicher mit gleichem share_key_hash stehen hintereinander, der mit den meisten Medienzeilen in oc_filecache zuerst; ein Speicher ohne Freigabe-Schlüssel (S3, lokal, WebDAV) ist eine Gruppe für sich. Die Gruppe, die am längsten wartet (nie gescannt zuerst), kommt zuerst. Lassen sich die Medienzeilen nicht zählen, kostet das nur die Reihenfolge.

**Ein Speicher (rescan).** Nicht erfassbar (keine Zeile, capturable 0, kein externer Speicher der Mountmenge, ID kleiner 1): Status not_capturable, ohne Mount-Abfrage, ohne Probe, ohne Logzeile (T-02-52). Sonst: Nutzer der klassifizierten Mount-Konfiguration aus dem Mount-Cache, nach UID, höchstens 5. Für jeden läuft in `ReaderContext::actAs` die Probe des StorageClassifier (Mount aufsetzen, gleiche Speicher-ID, kein FailedStorage, verfügbar). Der erste Speicher, den sie herausgibt, wird gescannt: `backgroundScan()`, dann `scan('', IScanner::SCAN_RECURSIVE, IScanner::REUSE_ETAG | IScanner::REUSE_SIZE)`. Ein begonnener Scan wird nicht als anderer Nutzer wiederholt.

**Budget (T-02-51).** 300 s je Lauf über ITimeFactory, für Zeitjob und occ gleich. `run()` beginnt nach Ablauf keinen weiteren Speicher und meldet die Zahl der wartenden. Im laufenden Scan prüfen die Hooks scanFolder und postScanFolder des Scanners die Frist; nach Ablauf endet der Scan an der nächsten Ordnergrenze mit Status partial. rescanned_at schreibt nur ein Lauf, der sein Ende erreicht hat (Status scanned), über `StorageStateMapper::markRescanned`.

**Zähler.** Der Hook addToCache zählt neue (Datei-ID -1) und geänderte Einträge, Dateien und Ordner. Die Hooks werden nach jedem Lauf wieder abgenommen, weil der Speicher seinen Scanner für den ganzen Prozess behält.

**Zeitjob (ExternalRescanJob).** TimedJob mit 3600 s, ruft `RescanService::run()`. Bei `files_no_background_scan` true tut er nichts (eine debug-Zeile). Ein Fehler im Lauf verlässt den Job nie. Logzeile nur mit Zählern (scanned, partial, failed, waiting).

**occ audio_video_search:rescan.** `--storage=<id>`: genau dieser Speicher, Ausgabe `Storage 7: rescanned in 12 s, 3 new and 1 changed entries.` `--all`: jeder erfassbare externe Speicher ohne 24-h-Kadenz, mit Budget, eine Zeile je Speicher, bei Resten `Time budget spent, N storages not started. Run the command again.` Nicht erfassbar oder unbekannt: FAILURE mit genau `Storage not capturable.` Keine oder beide Optionen und jede ID, die keine positive ganze Zahl ist: INVALID, ohne Aufruf des Dienstes. Der Befehl fragt `files_no_background_scan` nicht ab.

**occ audio_video_search:status.** Textzeile `Rescan of external storages: background rescan on` oder `Rescan of external storages: background rescan disabled by configuration`; in `--json` der Schlüssel `backgroundRescan` mit `on` oder `disabled_by_config`, hinter skippedStorages.

**info.xml.** `<job>OCA\AudioVideoSearch\BackgroundJobs\ExternalRescanJob</job>` hinter dem SchedulerJob und `<command>OCA\AudioVideoSearch\Command\RescanCommand</command>` hinter dem StatusCommand, beide in der einzeiligen Schreibweise des Bestands; der Kopfkommentar nennt jetzt zwei Hintergrundjobs.

**Logs.** `rescan of an external storage` (storage_id, status, seconds, new, changed), `an external storage could not be rescanned` (storage_id, class), `the media rows of an external storage could not be counted` (storage_id, class). Kein Pfad, kein Dateiname, kein Host, keine Freigabe, auch nicht in den occ-Ausgaben.

## Prüfungen

Alle Befehle seriell in backend/, Exit-Codes aus der Ausgabe gelesen.

| Befehl | Ergebnis |
|--------|----------|
| Task 1 verify: `uv run pytest tests/test_php_gates.py tests/test_store_metadata.py -x -q` | Exit 0, 40 grün |
| Zusätzlich nach Task 1: test_read_proof_gate, test_lockstep_versions, test_release_archives, test_public_texts, test_trilingual | Exit 0, 79 grün |
| Task 2 verify: dieselben zwei Dateien | Exit 0, 40 grün |
| `uv run ruff check .` | Exit 0 |
| `uv run ruff format --check .` | Exit 0, 67 Dateien |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | Exit 0, 0 Fehler, 0 Warnungen |
| `uv run vulture` | Exit 0 |
| `uv run pytest -q` gesamt, nach dem zweiten Commit | Exit 0, 839 grün (unverändert, der Plan ändert nur PHP) |
| php -l | **nicht gelaufen** |
| PHPUnit | **nicht gelaufen** |

**Notbehelf, kein Syntaxbeweis:** Klammer- und Tag-Bilanz (runde, eckige, geschweifte Klammern außerhalb von Zeichenketten und Kommentaren, genau ein `<?php`, kein `?>`) über alle 11 geänderten und neuen PHP-Dateien: ohne Befund. Abgleich der `use`-Zeilen gegen die benutzten Klassennamen: nichts fehlt, nichts Neues ist unbenutzt. info.xml mit ElementTree gelesen: zwei Jobs, vier Befehle. Zeilenenden LF.

**RED und GREEN sind nicht belegt.** Tests und Umsetzung stehen je Task in einem Commit, wie der Plan es nennt; kein einziger PHPUnit-Fall wurde ausgeführt.

### Neue und geänderte PHPUnit-Fälle (ungeprüft)

| Klasse | Methoden vorher | nachher | Fälle mit Datensätzen |
|--------|-----------------|---------|------------------------|
| RescanServiceTest (neu) | 0 | 35 | 48 (drei Datenquellen mit 5, 2 und 9 Sätzen) |
| FilesCommandTest | 13 | 15 | +2; dazu eine Erwartung erweitert (Schlüsselliste um backgroundRescan, Wert on) |
| StorageStateMapperTest | 4 | 6 | +2, gegen die echte Datenbank |
| StorageServiceTest | 7 | 9 | +2, einer gegen die echte oc_filecache |

Erwartete Gesamtzahl im Container: 366 + 54 = 420 Tests, sofern alles lädt.

RescanServiceTest deckt: Fälligkeit und Reihenfolge (4), ein Speicher (13: voller Lauf mit Zählern und Leser, Logzeile, Abbruch an der Frist, Ende genau auf der Frist, Aufruf nach der Frist, nie gescannt mit 5 Sätzen, erster brauchbarer Nutzer, Ende nach 5 Nutzern, nur Nutzer der klassifizierten Konfiguration, kein Leser, werfender Scanner ohne Host oder Dateiname im Log, kein Root, Scanner ohne Hooks), ein Lauf (3), Schalter (1), Zeitjob (5), occ rescan (9). Der Scanner ist ein kleiner Ersatz als anonyme Klasse, der eine Liste von Hook-Aufrufen abspielt und dazwischen die Uhr stellt.

## Belege am Quelltext (nextcloud/server stable34, gelesen, nicht gelaufen)

- `lib/public/Files/Cache/IScanner.php`: SCAN_RECURSIVE true, REUSE_ETAG 1, REUSE_SIZE 2, `scan($path, $recursive, $reuse, $lock)`, `backgroundScan()`.
- `lib/public/Files/Storage/IStorage.php:395`: `getScanner()`.
- `lib/private/Files/Mount/Manager.php:274`: `getMountFromMountInfo` setzt das Dateisystem für den Mountpunkt auf (über die vorhandene Probe genutzt).
- `lib/private/Files/Cache/Scanner.php`: Hooks im Bereich `\OC\Files\Cache\Scanner`; scanFolder am Anfang und postScanFolder am Ende von `scanChildren`, beide außerhalb der Transaktion von `handleChildren`; addToCache mit (Pfad, Speicher, Daten, Datei-ID). `handleChildren` fängt nur `Doctrine\DBAL\Exception` und `LockedException`.
- `lib/private/Hooks/EmitterTrait.php`: `listen($scope, $method, callable)`, `removeListener(...)`, beide seit 18.0.0 als veraltet markiert. `lib/private/Files/Utils/Scanner.php` hängt sich genauso an.
- `apps/files/lib/BackgroundJob/ScanFiles.php:131`: `getSystemValueBool('files_no_background_scan', false)`.
- `lib/public/BackgroundJob/TimedJob.php`: `setInterval`, `getInterval` (seit 32).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] Drei Bestandsklassen außerhalb von files_modified berührt**
- **Gefunden bei:** Task 1
- **Problem:** rescanned_at liegt in avs_storage (ein Mapper für die Tabelle), die Medienzeilen eines Speichers sind eine Frage an StorageService (Gate-Regel 12: eine Stelle weiß, was in einem Mount liegt), und der brauchbare Speicher eines Nutzers ist die Probe des StorageClassifier.
- **Fix:** `StorageStateMapper::rescanCandidates()` und `markRescanned()` (schreibt nur bei capturable 1; `store()` fasst rescanned_at weiter nicht an), `StorageService::mediaRows()` (eine COUNT-Abfrage je Speicher auf der Spalte storage, damit sie auch auf geteilter oc_filecache läuft), `StorageClassifier::probe()` von private auf public, sonst unverändert. Dazu je zwei Fälle in StorageStateMapperTest und StorageServiceTest.
- **Commit:** 65de734

**2. [Rule 3 - Blocker] FilesCommandTest angepasst**
- **Gefunden bei:** Task 2
- **Problem:** StatusCommand hat einen fünften Konstruktor-Parameter (RescanService), die Tests zu :status stehen in FilesCommandTest.
- **Fix:** Helfer `statusCommand()` um den Dienst ergänzt, Schlüsselliste der JSON-Ausgabe um backgroundRescan erweitert, zwei neue Fälle. Keine andere Erwartung geändert.
- **Commit:** c2b3760

**3. [Rule 2 - Sicherheit, T-02-51] Frist auch im laufenden Scan**
- **Problem:** Wörtlich nach dem behavior-Block ("nach Ablauf kein weiterer Speicher") hätte ein einzelner großer Speicher den Cron-Lauf beliebig lange belegt; must_have 1 sagt "höchstens 300 s je Lauf".
- **Fix:** Abbruch an der nächsten Ordnergrenze über die Hooks des Scanners. Ein sehr großer flacher Ordner läuft zu Ende, ein Scanner ohne Hooks wird nicht unterbrochen.
- **Commit:** 65de734

### Auslegungen (bitte bei Gelegenheit bestätigen)

- **Hooks des Scanners sind keine öffentliche API.** `listen` und `removeListener` gehören zu `OC\Hooks\Emitter` und sind seit Nextcloud 18 als veraltet markiert, werden vom Kern aber selbst so benutzt. Angesprochen per `is_callable`, ohne eine private Klasse zu nennen; fehlen sie, läuft der Scan ohne Frist im Speicher und ohne Zähler. Einen öffentlichen Weg, in einen laufenden Scan zu sehen, gibt es nicht.
- **backgroundScan() vor jedem vollen Lauf.** Der Plan sagt "abgebrochene Läufe setzt backgroundScan() fort". Gebaut: rescan ruft es immer zuerst auf (ohne unfertige Ordner eine Abfrage), dann den vollen Lauf.
- **Leser.** "Dateisystem des readerUid aufsetzen": `QueueService::readerUid` braucht eine Datei-ID. Gebaut: erster Nutzer der klassifizierten Mount-Konfiguration, für den die Probe einen Speicher herausgibt, höchstens 5.
- **Reihenfolge der Gruppen.** Der Plan regelt nur die Reihenfolge in einer Freigabe. Zwischen den Freigaben: die am längsten wartende zuerst, damit bei knappem Budget jede drankommt.
- **Exit-Codes.** partial und failed sind FAILURE, damit ein Skript einen unvollständigen Rescan bemerkt; `--all` mit wartenden Speichern ebenso.
- **Homes und Gruppenordner** sind für `--storage` nicht erfassbar im Sinn dieses Befehls (ein Satz, keine Details).
- **Zähler** zählen Einträge, also auch Ordner, deren Daten sich geändert haben.
- **Wortlaut in :status.** Der Satz des Plans steht hinter dem Vorsatz `Rescan of external storages: `.
- **Tests in einer Datei.** Zeitjob und Befehl sind laut files_modified in RescanServiceTest geprüft, nicht in eigenen Dateien.

## Offene Punkte

- **php -l und PHPUnit im Container** durch die Hauptsitzung. Stellen mit dem höchsten Risiko: die beiden anonymen Klassen in RescanServiceTest (implementieren IScanner samt statischer Methode), `RescanService&MockObject` als Rückgabetyp, die COUNT-Abfrage in `StorageService::mediaRows`.
- **Annahme A3 trägt laut Quelltext nur zum Teil (Messung in Plan 22).** `scanFile` übernimmt bei unveränderter storage_mtime die alte Größe eines Ordners; -1 bleibt nach einem Abbruch höchstens an Ordnern stehen, deren mtime sich geändert hat und deren Kinder nicht fertig wurden. Der noch nicht besuchte Rest trägt keine Marke. Folge: Ein abgebrochener Lauf beginnt beim nächsten Mal wieder an der Wurzel; ein Speicher, dessen Durchgang länger als 300 s braucht, bekommt nie rescanned_at, ist jede Stunde wieder fällig, und sein hinterer Teil wird nie erreicht. Wie SMB die Größe eines Ordners meldet, habe ich nicht nachgelesen. Wenn Plan 22 das misst, braucht es eine Entscheidung (größeres Budget, Cursor je Ordner oder Lauf ohne Frist im Speicher).
- **Keine Etag-Weitergabe über die Speicherwurzel hinaus.** Der Plan nennt den Scanner des Speichers, nicht `OC\Files\Utils\Scanner`; der Scanner trägt geänderte Etags bis zur Wurzel des Speichers, nicht in die Ordner darüber. Für die Erfassung ohne Belang, Sync-Clients sehen die Änderung erst beim nächsten Zugriff.
- **Wurzel nicht gefunden.** Meldet der Speicher seine Wurzel als nicht vorhanden, nimmt der Scanner des Kerns sie aus dem Cache (wie bei occ files:scan); das gäbe delete-Aufträge für alle Medien des Speichers. Die Probe prüft vorher die Verfügbarkeit, der Fall endet als failed ohne rescanned_at.
- **Jobliste.** Ein neuer Eintrag unter background-jobs kommt bei Installation oder Update in die Jobliste; die Version ist unverändert 0.1.0, CI installiert frisch.
- **Abnahme** foreign-change (discovery-e2e.yml ruft `occ audio_video_search:rescan --storage=...`) läuft erst in CI (Plan 17 und 22).
- **Ein Ausrutscher im Ablauf:** Eine Textersetzung in RescanServiceTest.php lief einmal über das System-Python statt über uv; danach nur noch uv und das Edit-Werkzeug. Am Ergebnis ändert das nichts.

## Known Stubs

Keine. DISC-02 und DISC-04 stehen nicht unter requirements-completed: wie in den Vorgängern erst nach der Abnahme. STATE.md, ROADMAP.md und REQUIREMENTS.md habe ich nicht angefasst.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: outbound-scan | php/lib/Service/RescanService.php | Der Rescan listet im Cron-Prozess den externen Server im Namen eines Nutzers auf (Trust Boundary des Plans). Begrenzt durch 24 h je Speicher und 300 s je Lauf; gelesen werden nur Metadaten, keine Datei wird geöffnet, nichts verlässt den Server außer den Anfragen von files_external selbst. |

T-02-51 (Budget, Kadenz, Fortsetzung mit der oben genannten Einschränkung zu A3) und T-02-52 (nie gescannt) sind umgesetzt.

## Self-Check: PASSED

- Dateien vorhanden: RescanService.php, ExternalRescanJob.php, RescanCommand.php, RescanServiceTest.php, 02-14-SUMMARY.md.
- Commits vorhanden: 65de734, c2b3760.
