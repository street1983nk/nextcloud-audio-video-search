---
phase: 02-erfassung-aller-dateien
plan: 17b
subsystem: php-ereignisse, hintergrundjobs, abnahme-workflow
tags: [move-cross, groupfolders, jail, background-jobs, cron, discovery-e2e]
requires: [02-17]
provides:
  - "FileAccess::storagePath: Pfad eines Nodes im Cache seines numerischen Speichers (durch jedes Jail)"
  - "JobRegistry::ensure beim Handshake: fehlende Jobs aus info.xml werden nachgetragen"
  - "discovery-e2e.yml: Cron-Schleife erst nach dem Aktivieren der Apps, in beiden Beinen"
affects: [02-18, 02-19, 02-20, Push 8]
tech-stack:
  added: []
  patterns:
    - "Pfadvergleich mit den Mount-Wurzeln immer im Raum des numerischen Speichers, nie unter einem Jail"
    - "Selbsteintragung der Hintergrundjobs nur über OCP\\BackgroundJob\\IJobList::has/add"
key-files:
  created:
    - php/lib/Service/JobRegistry.php
    - php/tests/Unit/JobRegistryTest.php
  modified:
    - php/lib/Service/FileAccess.php
    - php/lib/Listener/FileEventListener.php
    - php/lib/Controller/HandshakeController.php
    - php/tests/Unit/FileEventListenerTest.php
    - php/tests/Unit/HandshakeControllerTest.php
    - backend/tests/test_php_gates.py
    - backend/tests/test_discovery_workflow.py
    - .github/workflows/discovery-e2e.yml
    - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
decisions:
  - "move-cross: Ursache in der App (Pfad unter dem Jail des Gruppenordners), kein Kern- oder groupfolders-Fehler; Fix allgemein über Jail, ohne Klassennamen von groupfolders"
  - "Selbsteintragung der Jobs im Handshake (Start und alle fünf Minuten), nicht in Application::boot"
  - "JobRegistry ist nicht final, damit der Handshake-Test sie ersetzen kann"
metrics:
  duration: "ca. 90 min (davon ca. 60 min Warten auf freien RAM)"
  completed: 2026-11-13
  tasks: "5 von 5 (Task 5: Owner-Wahl push-8, Push 8 auf bf2342c)"
---

# Phase 2 Plan 17b: move-cross, Selbsteintragung der Jobs, Cron-Reihenfolge Summary

Verschieben aus dem Home in einen Gruppenordner verliert den Verweis nicht mehr (Pfad durch das Jail in den Raum der Mount-Wurzeln), die App trägt fehlende Hintergrundjobs beim Handshake selbst wieder ein, und die Abnahme startet Cron erst nach dem Aktivieren der Apps. Alles lokal, nichts gepusht.

## Befund A: Ursache von move-cross (belegt)

Belege aus Lauf 43387183622 (Artefakt `discovery-logs-stable33-ubuntu-24.04`, nur lesend in den Scratchpad geladen):

- `php-server.log` Zeile 832: genau ein `MOVE /remote.php/dav/files/ana/wandern.webm` um 07:48:41, danach nur PROPFIND, claim, ack.
- `exapp.log` Zeile 321 bis 323: 07:49:04 "media orphaned", cause delete; "intake written" items 1, applied 1, removed 1; "intake round" claimed 1. Also genau ein Auftrag, und der ist delete.
- `occ-files-initial.json`: Datei 80 auf Speicher 3 (Home ana); die Dateien des Gruppenordners 102 bis 104 auf Speicher 15. `occ-files-move-cross.json`: 80 fehlt. Speicher 15 ist also in der Mount-Menge und vom Crawl bekannt.

Quellen (nur lesend in den Scratchpad):

- groupfolders v21.0.16 `lib/Folder/FolderManager.php` Zeile 883: neue Ordner bekommen `'separate-storage' => true`. `lib/Mount/FolderStorageManager.php` Zeile 125 bis 146 und 112 bis 122: eigener Speicher `Local` unter `__groupfolders/<id>`, darüber `new Jail(['storage' => ..., 'root' => 'files'])`; `root_id` ist die Cache-ID von `''` im Jail, also des Eintrags `files` im ungejailten Speicher (Zeile 45 bis 59). Für die Mount-Wurzel liefert `StorageService::mountRoots(15)` darum `rootPath = 'files'`.
- nextcloud/server stable33 `lib/private/Files/View.php` Zeile 809 bis 846: `moveFromStorage`, dann `renameUpdate` (Cache), erst danach der Hook `post_rename`. `lib/private/Files/Cache/Cache.php` Zeile 836 bis 841 (`moveFromCache`, Speicherwechsel): `CacheEntryRemovedEvent` für den Quellspeicher, dann `CacheEntryInsertedEvent` für das Ziel, beide mit dem Pfad im Cache des numerischen Speichers; `Cache/Wrapper/CacheJail.php` Zeile 300 bis 305 reicht dafür `getSourcePath($targetPath)` weiter, also `files/wandern.webm`. `lib/private/Files/Node/HookConnector.php` Zeile 162 bis 169: aus `post_rename` wird `NodeRenamedEvent`. `lib/private/Files/Node/Node.php` Zeile 179 bis 181: `getInternalPath()` ist der Pfad im Speicher des Mounts, beim Gruppenordner also unter dem Jail: `wandern.webm`.

Ablauf in der App vor dem Fix:

1. CacheEventListener: removed(80, Speicher 3) gibt delete, inserted(80, Speicher 15, `files/wandern.webm`) gibt content; content ersetzt delete.
2. FileEventListener::queueRename: `admissibleFile` vergleicht `wandern.webm` mit der Wurzel `files`; kein Präfix passt, `mountRelativePath` gibt null, also `enqueue(delete, 80, 15)`. Nach QueueMapper REPLACES ersetzt dieses delete den content derselben Datei-ID. Ergebnis: ein Auftrag, cause delete. Genau das Bild des Laufs.

- H1 (Pfad unter dem Jail): bestätigt, siehe oben; außerdem im Container: auf dem Test-Commit 7c612ef ist der letzte Auftrag für 80 `['delete', 80, 4]` statt `['content', 80, 4]`.
- H2 (removed nach content ersetzt ihn): verworfen. Die Cache-Ereignisse kommen in der Reihenfolge removed, inserted; danach steht content. Das spätere delete stammt aus dem NodeRenamedEvent.
- H3 (Speicher des Gruppenordners nicht in oc_mounts): verworfen. Der Crawl fand 102 bis 104 auf Speicher 15 über dieselben Mount-Wurzeln, `unmapped` war in move-cross PASS.

Die Ursache liegt in der App, nicht im Kern und nicht in groupfolders: kein Abbruchkriterium.

Fix: `FileAccess::storagePath(Node)` geht die Speicher-Wrapper hinunter und bildet den Pfad an jedem `\OC\Files\Storage\Wrapper\Jail` mit `getUnjailedPath` ab, so wie das Jail selbst einen Aufruf weiterreicht. Ohne Jail bleibt der interne Pfad unverändert (Bestand). Bei einem Fehler oder mehr als 32 Schichten: null, also wie bisher "nicht zulässig". `admissibleFile` vergleicht diesen Pfad mit den Mount-Wurzeln. Kein Zweig für groupfolders per Klassennamen. Nebenwirkung: auch Medien, die direkt im Gruppenordner angelegt oder geschrieben werden, kommen jetzt per Ereignis in die Warteschlange (vorher nur über Cache-Ereignisse oder Crawl).

## Befund B: Selbsteintragung der Jobs

stable33 `lib/private/BackgroundJob/JobList.php`: `add` (Zeile 44 ff.) legt `class` und `argument_hash` von `json_encode($argument)` an, `has` (Zeile 120 ff.) prüft genau dieses Paar; `buildJob` (Zeile 312 ff.) entfernt eine Zeile, deren Klasse nicht ladbar ist. `OC_App::setupBackgroundJobs` ruft beim Aktivieren `add($job)` mit Argument null. `JobRegistry::ensure` prüft darum `has($job, null)` und ruft nur für fehlende `add($job, null)`; jeder nachgetragene Job wird einmal auf warning mit seiner Klasse geloggt, ein Fehler nur mit der Fehlerklasse. Der Handshake ruft `ensure()` nach `rejectForeignCaller`, eingehüllt in try/catch; die Antwort bleibt `companionVersion`. Nur `OCP\BackgroundJob\IJobList`, keine Kern-Interna.

Gate-Regel 15 in `backend/tests/test_php_gates.py`: `JobRegistry::JOBS` gleich `<background-jobs>` aus info.xml; `handshake` ruft `->ensure(` erst nach dem Wächter. Selbsttests: fehlende und zusätzliche Klasse, Liste nur im Kommentar, ensure vor dem Wächter, ensure nur im Kommentar. Lokal rot vor dem Fix (JobRegistry.php fehlt), grün danach.

## Befund C: Cron im Workflow

Diff des Workflows (Commit 1b3b842), `git diff --stat`: `.github/workflows/discovery-e2e.yml | 21 ++++++++++++---------`. Inhalt: im Bein discovery steht der Schritt "Run cron every 15 seconds" jetzt hinter "Enable files_external, files_accesscontrol and the PHP app" (Kommentar ergänzt: ein früheres cron.php entfernt die Jobs der App); im Bein leak-control stehen `./occ background:cron` und die Schleife jetzt hinter `./occ app:enable audio_video_search`, mit einer Kommentarzeile. Kein Trigger, keine Berechtigung, kein Pin, keine Registry geändert. Nicht ausgeführt. actionlint ist lokal nicht vorhanden.

Gate in `backend/tests/test_discovery_workflow.py`: die Schleife `do php cron.php;` (Kommentarzeilen zählen nicht) steht in discovery nach `./occ app:enable audio_video_search`, `./occ app:enable files_external`, `./occ app:install files_accesscontrol`, in leak-control nach den ersten beiden. Gegen den alten Workflow rot mit fünf Befunden (drei discovery, zwei leak-control); Selbsttests: Schleife je Bein einzeln zurück hinter app_api, die wörtlichen Zeilen von 25d241b im Kontrollbein, Kommentar, fehlende Schleife.

## Task 4: Container und Gates

Vorprüfung (jeweils direkt vor dem Start):

- 19:46Z: RAM 3,7 GB, kein Container. Neuprüfung alle 5 Minuten: 3,7 bis 3,8 GB bis 20:14Z, 20:19Z 4,3 GB, kein fremder Container; 20:20Z nochmals 4,3 GB, `docker ps` leer. Start `avs-phpcheck-17b`.
- Zweiter Lauf (nach dem Testfix, siehe Abweichungen): 20:52Z 3,9 GB; 20:57Z fremde Container `nc35-caddy nc35-harp nc35-nc` liefen (nicht angefasst, gewartet); 21:02Z 4,2 GB, keine fremden Container. Start `avs-phpcheck-17b2`.
- Danach `docker rm -f` nur der eigenen Namen; `docker ps -a --filter name=avs-phpcheck-` leer. Kein fremder Container berührt, kein down, kein prune.

Umgebung: `php:8.2-cli` (PHP 8.2.33), Erweiterungen zip intl gd pdo_sqlite, nextcloud/server stable34 Commit 4959f29943ab4b1c0241f1b9eb0c39ce5c63b3c8 (Version 34.0.6.2), 3rdparty 8e50d96adefcf598dd6f57c31d9608078bdf7933, PHPUnit 11.5.57, Composer über den Installer mit geprüfter Signatur, App per `git archive` des jeweiligen Commits.

| Lauf | Stand | Ergebnis |
|------|-------|----------|
| a) | 7c612ef (Test A ohne Fix) | 573 Tests, 3 Failures, alle neu und aus dem richtigen Grund: `testAMoveFromTheHomeIntoAGroupFolderKeepsTheReference` "Expected 'content' ... Actual 'delete', 80, 4"; `testAMediumCreatedInAGroupFolderIsQueued` und `testAMediumWrittenInAGroupFolderOnTheRootStorageIsQueued` ohne Einreihung; Bestand grün |
| b) | 26e45bc (Test B ohne Fix) | 13 Errors "Class OCA\AudioVideoSearch\Service\JobRegistry not found" bzw. "does not exist" (5 von 6 JobRegistryTest, 8 HandshakeControllerTest, weil setUp die Klasse mockt), 2 Warnungen des Autoloaders zur fehlenden Datei JobRegistry.php, 1 Failure `testTheListIsTheOneOfInfoXml` (siehe Abweichungen); sonst grün |
| Mutation | HEAD mit FileEventListener.php von 7c612ef | 582 Tests, 3 Failures: genau die drei neuen move-cross-Tests |
| c) HEAD | 9db00a7 | **OK (582 tests, 7457 assertions)**, 0 Failures, 0 Errors |
| php -l | HEAD, 61 Dateien unter php/ | fails=0; Positivkontrolle: kaputte Kopie liefert Exit 255 |

Der erste Lauf von c) auf 875a78f zeigte 1 Failure (`testTheListIsTheOneOfInfoXml`), behoben in 9db00a7, zweiter Lauf grün.

Python-Gates auf HEAD (backend, seriell): `ruff check .` grün, `ruff format --check .` 71 Dateien unverändert, `pyright` (latest) 0 errors, `vulture` Exit 0, `pytest -p no:xdist -q` **950 passed** (vorher 943). Nach 9db00a7 nur eine PHP-Testdatei geändert; `test_php_gates.py` erneut 35 passed.

Commit-Prüfung `origin/phase-02..HEAD`: Autor und Committer jedes Commits `street1983nk <k.cherif@outlook.de>`; `grep -Ei 'co-authored-by|claude-session|(close[sd]?|fix(e[sd])?|resolve[sd]?) #[0-9]+'` ohne Treffer. `git ls-remote origin refs/heads/phase-02` weiter 25d241b.

## Commits

| Task | Commit | Inhalt |
|------|--------|--------|
| 1 RED | 7c612ef | test: move-cross nachgebaut, Anlegen und Schreiben im Gruppenordner, Wächter |
| 1 GREEN | 0cb48a6 | fix: FileAccess::storagePath, admissibleFile im Raum der Mount-Wurzeln |
| 2 RED | 26e45bc | test: JobRegistryTest, HandshakeControllerTest, Gate-Regel 15 |
| 2 GREEN | 58c4f20 | fix: JobRegistry, Aufruf im Handshake |
| 3 RED | 2a797ff | test: Cron-Reihenfolge im Workflow |
| 3 GREEN | 1b3b842 | fix: Cron nach dem Aktivieren der Apps |
| 1 bis 3 | 875a78f | docs: deferred-items.md nachgezogen, neue Zeile groupfolders-Wettlauf |
| 4 | 9db00a7 | test: info.xml als String lesen (Testfehler, siehe unten) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Neuer Test las info.xml mit simplexml_load_file**
- **Found during:** Task 4, Lauf c) auf 875a78f
- **Issue:** `lib/base.php` (stable34 Zeile 653) schaltet den externen Entity-Loader ab; `simplexml_load_file` gibt in der Suite false zurück, `testTheListIsTheOneOfInfoXml` schlug fehl.
- **Fix:** `file_get_contents` plus `simplexml_load_string`.
- **Files modified:** php/tests/Unit/JobRegistryTest.php
- **Commit:** 9db00a7

### Weitere Abweichungen

- HandshakeControllerTest: die Bestandstests sind unverändert, nur der Konstruktoraufruf im Helfer bekommt den neuen Parameter `JobRegistry` (zwingend durch die neue Abhängigkeit). Darum sind auf dem Test-Commit 26e45bc auch die fünf Bestandstests des Handshakes rot, Grund ebenfalls die fehlende Klasse.
- CacheEventListenerTest und CacheEventListener blieben unverändert: H2 war nicht beteiligt. Der Nachbau in FileEventListenerTest nutzt den echten CacheEventListener für die Cache-Ereignisse.
- Zwei Containerläufe statt einem, wegen des Testfehlers; beide mit Vorprüfung.

## Offene Punkte

- CI-Beleg fehlt: move-cross, trash, restore (Folgefehler von 80) und das Kontrollbein leak-control sind nur lokal belegt; das Kontrollbein lief noch nie mit Cron nach dem Aktivieren.
- groupfolders wird in topology.sh weiter bei laufender Cron-Schleife aktiviert (neue Zeile in deferred-items.md, nur beobachten).
- Nebenbefund, nicht geprüft: Empfangene Freigaben sind ebenfalls ein Jail (SharedStorage); der Fix bildet auch deren Pfad in den Speicher des Besitzers ab. Ob Verschieben in einen empfangenen Ordner vorher ebenfalls delete ergab, belegt erst ein Lauf.

## Threat Flags

Keine neue Fläche außerhalb des Threat-Modells. T-02-82 bis T-02-87 umgesetzt wie geplant (Pfad nicht bestimmbar bleibt "nicht zulässig"; ensure nach dem Wächter mit fester Klassenliste; Logzeilen nur Klassen; Workflow-Diff nur Reihenfolge; Docker nur eigene Container nach Vorprüfung).

## Checkpoint (Task 5): Owner-Wahl push-8

- Frage: Soll der Stand von 02-17b als Push 8 auf origin/phase-02 gehen (`push-8`) oder erst 02-18 bis 02-20 lokal (`stop`)?
- Owner-Entscheid 13.11.2026: `push-8` ("Ja, push-8 (Empfohlen)" per AskUserQuestion der Hauptsitzung, über die Hauptsitzung übermittelt). Gilt für genau einen Push.
- Vorgehen wie 02-17: `main-before-bf2342c…` (main unverändert ea97b58), `ghcr-before-bf2342c…` mit `STATE 404 Package not found` (Positivkontrolle findling_backend mit Tag 1.6.2: Exit 0, Treffer), Freigabedatei `approvals/push-bf2342c…` mit Inhalt `push-phase-02 bf2342cb12fdd6aa071d9669cc179787b5468b05`; `approvals/` per `git check-ignore` ausgenommen, darum nicht committet (wie 02-17). Autoren- und Textprüfung über `origin/phase-02..HEAD` ohne Treffer, Fast-Forward vorab mit `git merge-base --is-ancestor` geprüft.
- Push: genau ein `git push origin HEAD:phase-02`, Fast-Forward 25d241b..bf2342c um 21:18:01Z. Kein Workflow von Hand gestartet (PHP gates lief durch den Pfadfilter von selbst).
- Läufe für bf2342c (Stand 21:18Z, nicht abgewartet): 43509442470 Discovery acceptance (in_progress, Jobs discovery und leak-control laufen), 43509442497 PHP gates (in_progress), 43509442333 Deploy through HaRP (queued), 43509442366 Python gates (in_progress).
- Auswertung der Läufe (Kontrollbein, move-cross, trash, restore, ghcr-after) folgt in der Hauptsitzung bzw. einem Folgeplan.

## Self-Check: PASSED

- Dateien vorhanden: php/lib/Service/JobRegistry.php, php/tests/Unit/JobRegistryTest.php, php/lib/Service/FileAccess.php (storagePath).
- Commits vorhanden: 7c612ef, 0cb48a6, 26e45bc, 58c4f20, 2a797ff, 1b3b842, 875a78f, 9db00a7.
