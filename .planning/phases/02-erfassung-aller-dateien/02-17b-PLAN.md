---
phase: 02-erfassung-aller-dateien
plan: 17b
type: execute
wave: 9
depends_on: [02-17]
files_modified:
  - php/lib/Listener/FileEventListener.php
  - php/lib/Listener/CacheEventListener.php
  - php/lib/Service/StorageService.php
  - php/lib/Service/FileAccess.php
  - php/tests/Unit/FileEventListenerTest.php
  - php/tests/Unit/CacheEventListenerTest.php
  - php/lib/Service/JobRegistry.php
  - php/lib/Controller/HandshakeController.php
  - php/tests/Unit/JobRegistryTest.php
  - php/tests/Unit/HandshakeControllerTest.php
  - .github/workflows/discovery-e2e.yml
  - backend/tests/test_discovery_workflow.py
  - backend/tests/test_php_gates.py
  - .planning/phases/02-erfassung-aller-dateien/deferred-items.md
autonomous: false
requirements: [DISC-01, DISC-02, DISC-03, DISC-04, DISC-05, DISC-06]

must_haves:
  truths:
    - "(A) Eine Mediendatei, die ana per WebDAV MOVE aus ihrem Home (Speicher home::ana) in den Gruppenordner Team verschiebt (groupfolders 21.0.16, Datei-ID bleibt gleich), behält ihren Verweis: in der Warteschlange steht danach für diese Datei-ID ein Auftrag content (oder metadata) mit der Speicher-ID des Gruppenordners und kein delete, der das ersetzt; der Inhalt (mediaId) bleibt derselbe, höchstens ein Download (DISC-05, DISC-06)"
    - "(A) Was heute stimmt, bleibt: Umbenennen in einem Speicher ist metadata, Kopie ist content fürs Ziel, Umbenennen weg von einer Medienendung und Verschieben aus der Mount-Menge ist delete, Löschen ist delete; jede Bestandserwartung in FileEventListenerTest und CacheEventListenerTest bleibt unverändert"
    - "(A) Ein Medium, das direkt im Gruppenordner angelegt oder geschrieben wird, kommt per Ereignis in die Warteschlange (derselbe Pfadraum wie beim Verschieben, DISC-01, DISC-04)"
    - "(B) Fehlen SchedulerJob oder ExternalRescanJob in der Jobliste von Nextcloud (zum Beispiel weil cron.php vor dem Aktivieren der App begann und JobList::buildJob sie entfernt hat), trägt die App sie beim nächsten Handshake des Backends (Start und alle fünf Minuten) selbst wieder ein; vorhandene Jobs werden nie doppelt eingetragen; ein Fehler dabei ändert die Antwort des Handshakes nicht"
    - "(C) Im Workflow discovery-e2e.yml startet die Cron-Schleife in beiden Beinen (discovery und leak-control) erst nach `occ app:enable audio_video_search` und nach files_external und files_accesscontrol; ein Python-Gate schlägt an, wenn sie davor steht. Der Workflow wird in diesem Plan NICHT ausgeführt"
    - "PHP-Prüfung im Container (php:8.2-cli, nextcloud/server stable34, Präfix avs-phpcheck-): php -l aller PHP-Dateien Exit 0, PHPUnit grün mit mehr als 569 Tests; die neuen Tests sind auf den Test-Commits rot aus dem richtigen Grund und auf HEAD grün"
    - "Kein Push, kein Dispatch, kein Kommentar; der Plan endet an einem Checkpoint mit der Owner-Frage nach Push 8 auf origin/phase-02"
  artifacts:
    - path: "php/lib/Listener/FileEventListener.php"
      provides: "admissibleFile prüft im Pfadraum der Mount-Wurzeln (Cache-Pfad im numerischen Speicher), nicht im Pfad unter einem Jail"
    - path: "php/tests/Unit/FileEventListenerTest.php"
      provides: "Nachbau des Wegs move-cross (Home nach Gruppenordner, gleiche Datei-ID, Speicher unter Jail) und Anlegen im Gruppenordner"
    - path: "php/lib/Service/JobRegistry.php"
      provides: "ensure(): trägt fehlende Jobs aus info.xml per IJobList::has/add ein, gibt die Klassen der nachgetragenen Jobs zurück"
      contains: "IJobList"
    - path: "php/lib/Controller/HandshakeController.php"
      provides: "ruft JobRegistry::ensure nach der Prüfung des Aufrufers"
    - path: ".github/workflows/discovery-e2e.yml"
      provides: "Cron-Schleife nach dem Aktivieren der Apps, in beiden Beinen"
    - path: "backend/tests/test_discovery_workflow.py"
      provides: "Gate: cron.php-Schleife nach app:enable audio_video_search, mit Selbsttest"
  key_links:
    - from: "FileEventListener::queueRename, queueContent"
      to: "StorageService::mountRelativePath"
      via: "Pfad im selben Raum wie mountRoots rootPath"
      pattern: "mountRelativePath"
    - from: "HandshakeController::handshake"
      to: "JobRegistry::ensure"
      via: "Aufruf nach rejectForeignCaller"
      pattern: "ensure\\("
    - from: "php/appinfo/info.xml background-jobs"
      to: "JobRegistry"
      via: "Gate: dieselbe Klassenliste"
      pattern: "SchedulerJob|ExternalRescanJob"
---

<objective>
Lückenschluss nach Push 7 (02-17), nur lokal, vom Owner freigegeben. Drei Befunde aus Lauf 43387183622 (Push 7, 25d241b):

(A) PRODUKTFEHLER move-cross (Befund 5 in 02-17-SUMMARY.md, Zeile "02-17 (Push 7)" FileEventListener in deferred-items.md): `wandern.webm` (Datei-ID 80, vorher active, mediaId 7, storageId 3) wird von ana per WebDAV MOVE aus dem Home nach `Team/wandern.webm` (Gruppenordner, groupfolders 21.0.16, stable33) verschoben. Danach kommt beim Backend genau ein Auftrag an (cause delete, "media orphaned", items 1, applied 1), kein Auftrag fürs Ziel; der einzige Verweis ist weg. FAIL move-cross: active_set fehlt 80, files_count, contents, move_same_media erwartet=7 gefunden=.

(B) PRODUKT, Owner-Entscheid "App trägt ihre Jobs selbst wieder ein" (Befund 4): cron.php, das vor `occ app:enable audio_video_search` begann, meldet "failed to create instance of background job" für SchedulerJob und ExternalRescanJob; `JobList::buildJob` (stable33) entfernt sie. Ohne SchedulerJob gibt es nie einen Erst-Crawl, bis die App neu aktiviert wird.

(C) ABNAHME: die Cron-Schleife in discovery-e2e.yml startet vor dem Aktivieren der App; dadurch kam das Kontrollbein leak-control nie bis zur Prüfung (Positivkontrolle D-02-10 fehlt).

Danach PHP im Container und Python-Gates; Schluss ist ein Checkpoint für die Owner-Frage nach Push 8.

Purpose: Die zwei Produktfehler sind behoben und test-belegt, und der nächste freigegebene Push kann das Kontrollbein tatsächlich laufen lassen.
Output: Test- und Fix-Commits für A und B, ein Workflow-Commit für C, Containerbeleg, SUMMARY, Checkpoint.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/02-erfassung-aller-dateien/02-CONTEXT.md
@.planning/phases/02-erfassung-aller-dateien/02-17-SUMMARY.md
@.planning/phases/02-erfassung-aller-dateien/deferred-items.md
@php/lib/Listener/FileEventListener.php
@php/lib/Listener/CacheEventListener.php
@php/lib/Service/StorageService.php
@php/lib/Db/QueueMapper.php
@php/lib/AppInfo/Application.php
@php/lib/Controller/HandshakeController.php
@php/appinfo/info.xml
@php/tests/Unit/FileEventListenerTest.php
@php/tests/Unit/CacheEventListenerTest.php
@.github/workflows/discovery-e2e.yml
@backend/tests/test_discovery_workflow.py
@backend/tests/test_php_gates.py
@ci/discovery/topology.sh

Belege (lokal, nicht im Repo, `approvals/` ist per .git/info/exclude ausgenommen):
- `.planning/phases/02-erfassung-aller-dateien/approvals/discovery-25d241bd84e5f4984aa75a1f76c8ebd5af18f93a.log` (Job-Log Push 7; move-cross ab Zeile 6001, Operation `move_home_to_team` 07:48:41Z, Urteil Zeile 6369 ff.)
- nextcloud.log, php-server.log, cron.log und Backend-Log des Laufs liegen im Artefakt `discovery-logs-stable33-ubuntu-24.04` und `leak-control-logs` von Lauf 43387183622. Herunterladen nur lesend in ein neues leeres Verzeichnis im Scratchpad: `gh run download 43387183622 -R street1983nk/nextcloud-audio-video-search -n discovery-logs-stable33-ubuntu-24.04 -D <scratchpad>/run-43387183622`. Kein `gh workflow run`, kein `gh run rerun`.
- Weg im Lauf (ci/discovery/topology.sh Zeile 623 ff.): `curl -X MOVE -H "Destination: .../files/ana/Team/wandern.webm" .../files/ana/wandern.webm`; Team entsteht über `occ groupfolders:create Team` (Zeile 519).

<interfaces>
Bestand, aus dem Code gelesen (nicht erneut suchen):

FileEventListener (php/lib/Listener/FileEventListener.php):
- `queueRename(Node $source, Node $target)`: `identity($target)` = [fileId, numericStorageId des Mount-Punkts]; `admissibleFile($target)`; ist das null: `enqueue(KIND_DELETE, fileId, targetStorage)` und Ende. Gleicher Speicher: metadata. Anderer Speicher: content fürs Ziel, delete für die Quelle nur bei anderer Datei-ID.
- `admissibleFile(Node)`: Mimetyp aus dem Node, dann `StorageService::mountRelativePath($storageId, (string)$node->getInternalPath())`; null heißt "nicht zulässig".

StorageService::mountRoots(int $storageId) (php/lib/Service/StorageService.php Zeile 104 ff.): je Zeile aus oc_mounts `rootPath` = Pfad des Cache-Eintrags von `overridden_root` im numerischen Speicher (über FileAccess). `mountRelativePath` vergleicht `internalPath` per Präfix mit diesem `rootPath`.

CacheEventListener: nimmt `$event->getPath()` (Pfad im Cache des Speichers) und `$event->getStorageId()`; removed: delete; inserted, updated: content.

QueueMapper::enqueue, REPLACES (Zeile 69 ff.): content ersetzt delete und trash; delete ersetzt content, metadata, trash, restore; ersetzt wird NUR nach file_id, ohne storage_id. Bei gleicher Datei-ID gewinnt also der zuletzt eingereihte Auftrag.

Hintergrundjobs: php/appinfo/info.xml `<background-jobs>` nennt `OCA\AudioVideoSearch\BackgroundJobs\SchedulerJob` und `OCA\AudioVideoSearch\BackgroundJobs\ExternalRescanJob`. StorageCrawlJob ist ein QueuedJob, den der SchedulerJob einreiht (nicht in info.xml).

HandshakeController: `handshake()` mit `#[ExAppRequired]`, erste Anweisung `rejectForeignCaller()`, Antwort nur `companionVersion`. Das Backend ruft die Route beim Start und alle fünf Minuten (backend/src/audio_video_search_backend/companion.py, nc.fetch_handshake).

FileAccess.php (Zeile 116) kennt `\OC\Files\Storage\Wrapper\Jail` schon: "Below a jail the path is another one".
</interfaces>

Hausregeln (gelten für jeden Task):
- Commits nur als Autor und Committer `street1983nk <k.cherif@outlook.de>` (`git -c user.name=street1983nk -c user.email=k.cherif@outlook.de commit ...`); kein Co-Authored-By, keine Claude-Session-Zeile, keine andere Trailer-Zeile; nie "closes", "fixes" oder "resolves" mit Issue-Nummer im Commit-Text.
- Testgetrieben: je Befund zuerst ein Commit nur mit Tests (`test(02-17b): ...`), dann der Fix (`fix(02-17b): ...`). Kein Bestandstest wird aufgeweicht oder gelöscht; geänderte Erwartungen nur, wo die alte Erwartung den Fehler festschreibt, und dann mit Begründung im SUMMARY.
- Python nur über uv; pytest immer mit `-p no:xdist`; pyright mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`.
- Deutsche Prosa (SUMMARY, deferred-items.md, Kommentare in Planungsdateien) mit echten Umlauten, ohne Gedankenstriche (U+2013, U+2014), ohne Emojis. Code-Kommentare unter php/ englisch wie im Bestand (Gate-Regel 8 verbietet beide Striche unter php/).
- Ändert sich ein nutzersichtbarer Text (l10n, info.xml, README), dann DE, EN und FR im Gleichstand. Erwartet wird keiner: JobRegistry loggt englisch auf Admin-Ebene wie der Bestand, ohne Pfad und Namen (Gate-Regel 6).
- Kein Push, kein Merge, kein Kommentar, kein `gh workflow run`, kein `gh run rerun`. STATE.md und ROADMAP.md bleiben unberührt.
- Docker nur in Task 4 und nur nach den dortigen Vorprüfungen.

Abbruchkriterien (STOP, Befund ins SUMMARY, Rückgabe an die Hauptsitzung zur Owner-Frage, nichts weiter ändern):
- Die Ursache von move-cross liegt außerhalb der App (Nextcloud-Kern oder groupfolders): zum Beispiel kein NodeRenamedEvent beim Verschieben in den Gruppenordner, falsche Datei-ID oder Speicher-ID im Ereignis, oder der Cache meldet das Ziel nie. Dann kein Umweg im Produkt ohne Owner-Entscheid.
- Der Fix verlangt eine Änderung der Bestandssemantik (z. B. delete bei unklarem Pfad nicht mehr einreihen), die einen anderen Befund öffnen kann (Leck, Datei bleibt nach Entfernen aus der Mount-Menge im Vorrat).
- Die App kann ihre Jobs nicht ohne Eingriff in Kern-Interna eintragen (nur `OCP\BackgroundJob\IJobList` ist erlaubt).
- RAM unter 4 GB frei oder ein fremder Live-Test belegt Docker länger als 60 Minuten (Task 4).
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (A): move-cross, Ursache belegen, RED-Test, Fix</name>
  <files>php/tests/Unit/FileEventListenerTest.php, php/tests/Unit/CacheEventListenerTest.php, php/lib/Listener/FileEventListener.php, php/lib/Listener/CacheEventListener.php, php/lib/Service/StorageService.php, php/lib/Service/FileAccess.php</files>
  <read_first>
    - Artefakt von Lauf 43387183622 (siehe context): nextcloud.log, php-server.log und Backend-Log rund um 07:48:41Z bis 07:49:10Z; welche Zeilen der Warteschlange (kind, storage) entstanden, welche Requests liefen
    - nextcloud/server stable33, nur lesend über `gh api` oder raw.githubusercontent.com in den Scratchpad: lib/private/Files/View.php (rename über Speichergrenzen), lib/private/Files/Cache/Cache.php `moveFromCache` (welche Cache-Ereignisse mit welchem Speicher und Pfad, in welcher Reihenfolge), lib/private/Files/Node/HookConnector.php (Reihenfolge NodeRenamedEvent zu den Cache-Ereignissen), lib/private/Files/Storage/Wrapper/Jail.php
    - nextcloud/groupfolders v21.0.16: lib/Mount/MountProvider.php und der Speicher des Ordners (Jail über dem Speicher `__groupfolders`, welche numerische Speicher-ID, welche Zeile in oc_mounts, welche Wurzel `overridden_root`)
  </read_first>
  <behavior>
    - Nachbau des genauen Wegs: Quelle im Home von ana (Speicher A, Pfad `files/wandern.webm`), Ziel im Gruppenordner Team (Speicher B unter einem Jail, Datei-ID gleich, Mount-Wurzel aus oc_mounts mit dem Cache-Pfad des Ordners im ungejailten Speicher); die Ereignisse in der Reihenfolge und mit den Pfaden und Speicher-IDs, die der Kern laut read_first wirklich liefert (NodeRenamedEvent und die Cache-Ereignisse, soweit sie bei diesem Weg feuern). Erwartung: am Ende steht für die Datei-ID ein Auftrag content (bzw. metadata, falls belegt) mit Speicher B, kein delete, das ihn ersetzt
    - Anlegen eines Mediums direkt im Gruppenordner (NodeCreatedEvent über einen gejailten Speicher): content mit Speicher B
    - Wächter, unverändert grün: Verschieben aus der Mount-Menge und Umbenennen weg von einer Medienendung bleiben delete; gleiche Datei-ID über Speichergrenzen ohne Gruppenordner reiht kein delete ein (bestehender Test testAMoveAcrossStoragesThatKeepsTheFileIdQueuesNoDelete)
    - Die Tests nutzen, wo es um Pfadräume geht, echte Klassen des Servers (`\OC\Files\Storage\Wrapper\Jail` über `\OC\Files\Storage\Temporary`) statt reiner Mocks, damit der Unterschied zwischen Pfad unter dem Jail und Cache-Pfad nicht im Test erfunden ist; die Warteschlange bleibt ein Mock oder die bestehende Testhilfe des Bestands
  </behavior>
  <action>
Schritt 1, Ursache (vor jedem Code): aus Artefakt und Quellen belegen, warum beim Verschieben nur delete ankommt. Die naheliegende Hypothese H1, am Bestand gelesen: `admissibleFile` übergibt `$node->getInternalPath()` an `mountRelativePath`; beim Gruppenordner ist das der Pfad UNTER dem Jail (z. B. `wandern.webm`), `mountRoots` liefert aber den Cache-Pfad der Wurzel im ungejailten Speicher (z. B. `__groupfolders/1`); kein Präfix passt, `admissibleFile` gibt null, `queueRename` reiht delete für Datei-ID 80 ein, und dieses delete ersetzt nach REPLACES jeden content derselben Datei-ID. Das erklärt "ein Auftrag, cause delete". Gegenhypothesen, die ebenso zu prüfen und im SUMMARY mit Beleg zu verwerfen oder zu bestätigen sind: H2 ein Cache-Ereignis removed kommt nach dem content und ersetzt ihn (Reihenfolge in Cache::moveFromCache und HookConnector); H3 der Speicher des Gruppenordners steht zu dem Zeitpunkt nicht in oc_mounts für die Mount-Menge. Erst wenn eine Ursache belegt ist, weiter. Liegt sie im Kern oder in groupfolders: Abbruch laut context.

Schritt 2, RED: Tests laut behavior in FileEventListenerTest (und CacheEventListenerTest, falls H2 beteiligt ist), Namen im Stil des Bestands (z. B. `testAMoveFromTheHomeIntoAGroupFolderKeepsTheReference`, `testAMediumCreatedInAGroupFolderIsQueued`). PHP läuft hier nicht lokal; der RED-Beleg entsteht in Task 4 auf diesem Commit. Klammer- und use-Bilanz per Python-Gate prüfen. Commit `test(02-17b): move across storages into a group folder keeps the reference`.

Schritt 3, GREEN: Der Pfad, den `admissibleFile` (und jeder andere Aufrufer von `mountRelativePath` mit einem Node) übergibt, muss im selben Raum liegen wie `rootPath` der Mount-Wurzeln: der Pfad des Cache-Eintrags der Datei im numerischen Speicher (z. B. über `$node->getStorage()` und die bestehende Ungejailt-Logik bzw. den Cache-Eintrag der Datei-ID im Speicher über FileAccess), nicht der Pfad unter dem Jail. Gate-Regel 4 (Node-Lookup nur in FileAccess) und Gate-Regel 12 (Mounts nur in StorageService) bleiben eingehalten; eine neue Hilfsmethode gehört nach FileAccess oder StorageService. Kann der Pfad nicht bestimmt werden, gilt die bisherige Regel (nicht zulässig) unverändert, damit nichts außerhalb der Mount-Menge in den Vorrat kommt. Kein Zweig nur für groupfolders per Klassennamen, wenn der allgemeine Jail-Weg reicht. Mutationsprobe: Fix bytegenau entfernen, der neue Test muss in Task 4 rot werden (dort ausgeführt). Commit `fix(02-17b): event path of a jailed storage in the space of the mount roots`.

Schritt 4: Zeile "02-17 (Push 7)" FileEventListener in deferred-items.md mit "ERLEDIGT LOKAL in 02-17b (Commits), CI-Beleg steht aus" ergänzen.
  </action>
  <verify>
    <automated>cd backend && uv run pytest -p no:xdist tests/test_php_gates.py -q</automated>
  </verify>
  <acceptance_criteria>Ursache mit Zeilenbeleg (Artefakt und Quelltext stable33 bzw. groupfolders 21.0.16) im SUMMARY; zwei Commits in der Reihenfolge test, fix; statische PHP-Gates grün; PHPUnit-RED und GREEN folgen in Task 4.</acceptance_criteria>
  <done>Ursache belegt, Test-Commit und Fix-Commit vorhanden, deferred-items.md nachgezogen.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (B): App trägt ihre Hintergrundjobs selbst wieder ein</name>
  <files>php/lib/Service/JobRegistry.php, php/tests/Unit/JobRegistryTest.php, php/lib/Controller/HandshakeController.php, php/tests/Unit/HandshakeControllerTest.php, backend/tests/test_php_gates.py</files>
  <read_first>
    - nextcloud/server stable33 lib/private/BackgroundJob/JobList.php `buildJob`, `has`, `add` (nur lesend in den Scratchpad), um zu belegen, dass `has($class, null)` und `add($class)` ohne Argument genau die Zeile prüfen und anlegen, die info.xml beim Aktivieren anlegt
    - php/tests/Unit/HandshakeControllerTest.php (wie der Controller von Hand gebaut wird)
  </read_first>
  <behavior>
    - JobRegistry::ensure: fehlt SchedulerJob, wird genau er eingetragen (add einmal, mit der Klasse und Argument null); fehlen beide, beide; sind beide da, kein add
    - die Klassenliste in JobRegistry ist genau die Liste aus php/appinfo/info.xml `<background-jobs>` (Python-Gate liest beide und vergleicht; Selbsttest mit einer fehlenden und einer zusätzlichen Klasse)
    - wirft `has` oder `add`, gibt ensure eine leere Liste zurück und loggt eine Warnung nur mit der Fehlerklasse (kein Pfad, kein Name, Gate-Regel 6)
    - jeder nachgetragene Job wird einmal mit seiner Klasse auf Stufe warning geloggt (sichtbar für den Admin, dass ein Job gefehlt hat)
    - HandshakeController: ein fremder Aufrufer bekommt 403 wie bisher und ensure wird NICHT gerufen; der eigene Aufrufer bekommt dieselbe Antwort wie bisher (nur companionVersion), ensure wird einmal gerufen; wirft ensure trotzdem, bleibt die Antwort gleich
  </behavior>
  <action>
Owner-Entscheid laut Auftrag: die App trägt ihre Jobs selbst wieder ein. Ort per Ermessen des Plans: der Handshake, weil das Backend ihn beim Start und alle fünf Minuten aufruft, er nur bei aktiver App erreichbar ist und in einem frischen PHP-Prozess läuft, der die Klassen der App kennt; kein Eingriff in `Application::boot()` (dort wäre es eine Datenbankfrage bei jedem Request). Neue Klasse `OCA\AudioVideoSearch\Service\JobRegistry` mit Konstruktor `IJobList $jobList, LoggerInterface $logger`, Konstante `JOBS` mit `SchedulerJob::class` und `ExternalRescanJob::class`, Methode `ensure(): array` (Liste der nachgetragenen Klassen). Nur `OCP\BackgroundJob\IJobList`, keine Kern-Interna. HandshakeController bekommt `JobRegistry $jobs` als letzten Konstruktorparameter und ruft `ensure()` direkt nach `rejectForeignCaller()`, eingehüllt so, dass kein Fehler die Antwort ändert. Antwortvertrag des Handshakes bleibt unverändert (Backend unberührt).

RED: JobRegistryTest, angepasster HandshakeControllerTest, Gate in test_php_gates.py (nächste freie Regelnummer, Regel plus Selbsttest wie Regel 12 bis 14: info.xml und JobRegistry nennen dieselben Jobs; HandshakeController::handshake ruft ensure nach rejectForeignCaller). Das Python-Gate lokal rot sehen (Klasse fehlt). Commit `test(02-17b): the app puts its missing background jobs back`. GREEN: JobRegistry, Controller. Commit `fix(02-17b): the handshake puts missing background jobs back`. Zeile "02-17 (Push 7)" Cron in deferred-items.md: Produktseite "ERLEDIGT LOKAL in 02-17b".
  </action>
  <verify>
    <automated>cd backend && uv run pytest -p no:xdist tests/test_php_gates.py -q</automated>
  </verify>
  <acceptance_criteria>Neues Gate rot vor dem Fix, grün danach, Selbsttest schlägt mit beiden Mutationen an; Klammer- und use-Bilanz ohne Befund; PHPUnit in Task 4.</acceptance_criteria>
  <done>Zwei Commits (test, fix), Gate grün.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3 (C): Cron im Workflow erst nach dem Aktivieren der Apps</name>
  <files>.github/workflows/discovery-e2e.yml, backend/tests/test_discovery_workflow.py, .planning/phases/02-erfassung-aller-dateien/deferred-items.md</files>
  <behavior>
    - Gate: in beiden Jobs (discovery und leak-control) steht die Zeile mit der Schleife `php cron.php` nach `./occ app:enable audio_video_search` und nach `./occ app:enable files_external` (und im Bein discovery nach files_accesscontrol); `./occ background:cron` darf davor stehen
    - Selbsttest: der Stand von 25d241b (Schleife vor dem Aktivieren) löst die Regel in beiden Jobs einzeln aus; der neue Stand nicht
  </behavior>
  <action>
RED: Regel und Selbsttest in test_discovery_workflow.py im Stil der bestehenden Regeln (Befundtext z. B. "the job discovery starts cron before the app is enabled"), lokal gegen den heutigen Workflow rot sehen. Commit `test(02-17b): cron starts after the apps are enabled`.

GREEN: Im Bein discovery den Schritt "Run cron every 15 seconds" hinter den Schritt "Enable files_external, files_accesscontrol and the PHP app" verschieben (Kommentar mitnehmen, Grund ergänzen: ein cron.php, das vor dem Aktivieren beginnt, entfernt die Jobs der App). Im Bein leak-control im selben Schritt die zwei Cron-Zeilen hinter `./occ app:enable audio_video_search` setzen. Sonst nichts am Workflow ändern: kein Trigger, keine Berechtigung, kein Pin, keine Registry; die WAL-Zeile aus deferred-items.md (state.db) ist nicht Teil dieses Auftrags. Nicht ausführen (kein Push, kein Dispatch). `actionlint` nur, falls lokal vorhanden. Commit `fix(02-17b): discovery acceptance starts cron after enabling the apps`.

deferred-items.md, Zeile "02-17 (Push 7)" Cron: Abnahmeseite "ERLEDIGT LOKAL in 02-17b, nicht ausgeführt". Neue Zeile: topology.sh aktiviert groupfolders während die Cron-Schleife läuft (derselbe Wettlauf kann Jobs von groupfolders entfernen); nur beobachten, nicht ändern.
  </action>
  <verify>
    <automated>cd backend && uv run pytest -p no:xdist tests/test_discovery_workflow.py tests/test_workflows.py tests/test_workflow_pins.py -q</automated>
  </verify>
  <acceptance_criteria>Regel rot gegen den alten Workflow, grün danach; Diff des Workflows nur die verschobenen Cron-Zeilen samt Kommentar (im SUMMARY als `git diff --stat` und Ausschnitt).</acceptance_criteria>
  <done>Zwei Commits, Workflow-Tests grün, deferred-items.md nachgezogen.</done>
</task>

<task type="auto">
  <name>Task 4: PHP im Container (RED-Belege und HEAD) und Python-Gates</name>
  <files>(keine Repo-Dateien; Belege ins SUMMARY)</files>
  <action>
Vorprüfung vor JEDEM docker-Befehl (auch vor `docker ps`, wenn ein Container gestartet werden soll), Ergebnis ins SUMMARY:
1. Freier RAM: `powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)"` muss mindestens 4 (GB) zeigen.
2. Fremde Live-Tests: `docker ps --format '{{.Names}} {{.Status}} {{.Image}}'`. Läuft ein Container, dessen Name nicht mit `avs-phpcheck-` beginnt und der ein Live-Test einer anderen Sitzung ist (z. B. Präfix `nc-mcp-exapp-`, `nc35`, Nextcloud-, Playwright- oder Testinstanzen), dann NICHT starten: alle 5 Minuten neu prüfen, höchstens 60 Minuten; danach Abbruch laut context.
3. Nur eigene Container mit Präfix `avs-phpcheck-` starten, stoppen und entfernen (`docker rm -f avs-phpcheck-<name>`); nie einen fremden Container anfassen, nie `docker compose down`, nie `docker system prune`, nie `docker stop` ohne den eigenen Namen. Streng seriell: höchstens ein eigener Container zugleich.

Rezept (wie zuletzt, 569 Tests): Repo read-only in den Container mounten, nach /work kopieren; Image `php:8.2-cli`, `docker-php-ext-install zip intl gd pdo_sqlite`; nextcloud/server Zweig stable34 flach samt 3rdparty; App nach `apps/audio_video_search`; `php occ maintenance:install` mit SQLite; `php occ app:enable audio_video_search`; in der App `composer install --no-scripts`; `vendor/bin/phpunit --no-progress`. Server-Commit und PHPUnit-Version ins SUMMARY.

In EINEM Container drei Läufe, jeweils mit eigener Kopie des Stands per `git worktree` bzw. `git archive` des Commits:
- a) Test-Commit von Task 1 (ohne Fix): die neuen move-cross-Tests sind rot, und zwar an der fehlenden Einreihung bzw. dem delete (Meldung zitieren); alle anderen grün.
- b) Test-Commit von Task 2 (ohne Fix): JobRegistryTest rot wegen fehlender Klasse, Bestand grün.
- c) HEAD: `php -l` über alle PHP-Dateien unter php/ Exit 0 (mit Positivkontrolle: eine absichtlich kaputte Kopie liefert Exit ungleich 0), PHPUnit "OK" mit mehr als 569 Tests, 0 Failures, 0 Errors; Anzahl Tests und Assertions ins SUMMARY. Mutationsprobe aus Task 1 (Fix in der Kopie entfernen): der neue Test wird rot.
Danach den eigenen Container entfernen und mit `docker ps -a --filter name=avs-phpcheck-` belegen, dass keiner übrig ist.

Python-Gates auf HEAD, seriell, im Ordner backend: `uv run ruff check .`, `uv run ruff format --check .`, `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`, `uv run vulture`, `uv run pytest -p no:xdist -q` (zuletzt 943 grün, jetzt mehr). Commit-Prüfung über `origin/phase-02..HEAD`: Autor und Committer jedes Commits `street1983nk <k.cherif@outlook.de>`; 0 Treffer für `Co-Authored-By`, `Claude-Session` und Schließwort mit Issue-Nummer (`git log --format=%B origin/phase-02..HEAD | grep -Ei 'co-authored-by|claude-session|(close[sd]?|fix(e[sd])?|resolve[sd]?) #[0-9]+'` leer).
  </action>
  <verify>
    <automated>cd backend && uv run ruff check . && uv run ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -p no:xdist -q</automated>
  </verify>
  <acceptance_criteria>RAM- und Fremdtest-Prüfung vor dem Start belegt; RED a) und b) aus dem richtigen Grund; HEAD: php -l Exit 0 mit Positivkontrolle, PHPUnit OK über 569 Tests; kein avs-phpcheck-Container übrig; kein fremder Container berührt; Python-Gates Exit 0; Commit-Prüfung ohne Treffer.</acceptance_criteria>
  <done>Belege im SUMMARY, SUMMARY geschrieben und committet (`docs(02-17b): ...`).</done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 5: Owner-Frage Push 8 auf origin/phase-02</name>
  <decision>Soll der Stand von 02-17b als dritter Zwischen-Push (Push 8) auf origin/phase-02 gehen?</decision>
  <context>Alles ist lokal. Push 8 würde den move-cross-Fix, die Selbsteintragung der Jobs und die Cron-Reihenfolge erstmals in CI zeigen; nur dort ist belegbar, ob das Kontrollbein leak-control das Leck zeigt (D-02-10) und ob move-cross und trash grün werden. Vorzulegen: HEAD-SHA, Anzahl Commits seit 25d241b, Ergebnis von Task 4, offene Grenzen (Lauf noch nie mit Cron nach dem Aktivieren gelaufen; groupfolders wird weiter bei laufendem Cron aktiviert). Bei Freigabe gilt das Vorgehen von 02-17 (Freigabedatei `approvals/push-<sha>` mit Inhalt `push-phase-02 <sha>`, nur `git push origin HEAD:phase-02`, kein main, kein Dispatch ohne eigene Freigabe), ausgeführt von der Hauptsitzung bzw. einem Folgeplan, nicht in diesem Plan.</context>
  <options>
    <option id="push-8">
      <name>Push 8 freigeben</name>
      <pros>CI belegt Kontrollbein und move-cross; DISC-02, DISC-03, DISC-05 können danach abgehakt werden, wenn grün</pros>
      <cons>Ein weiterer Lauf auf phase-02; Pläne 18 bis 20 bleiben als erlaubte Folgefehler rot</cons>
    </option>
    <option id="stop">
      <name>Nicht pushen, erst 02-18 bis 02-20 lokal</name>
      <pros>Weniger Zwischenläufe</pros>
      <cons>Positivkontrolle des Lesebeweises bleibt länger ohne CI-Beleg</cons>
    </option>
  </options>
  <files>(keine)</files>
  <action>Anhalten und die Frage mit den unter context genannten Angaben an die Hauptsitzung zurückgeben. Nichts pushen, nichts dispatchen, keine Freigabedatei schreiben.</action>
  <verify>git ls-remote origin refs/heads/phase-02 zeigt weiter 25d241b</verify>
  <done>Owner-Wahl push-8 oder stop liegt vor und ist im SUMMARY vermerkt; kein Push in diesem Plan.</done>
  <resume-signal>Owner wählt: push-8 oder stop</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Nextcloud-Ereignisse zu Warteschlange | Pfade und Speicher-IDs aus dem Kern entscheiden, was in den Vorrat kommt |
| Backend (ExApp) zu Handshake-Route | nur das eigene Backend darf die Route rufen; sie schreibt jetzt in die Jobliste |
| Lokale Docker-Umgebung | geteilt mit einer anderen Sitzung |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-82 | Information Disclosure | FileEventListener::admissibleFile nach dem Fix | mitigate | Pfad im Raum der Mount-Wurzeln; ist er nicht bestimmbar, bleibt "nicht zulässig"; Wächtertests für Verschieben aus der Mount-Menge und weg von der Medienendung (delete bleibt) |
| T-02-83 | Denial of Service | Jobliste ohne SchedulerJob nach Cron-Wettlauf | mitigate | JobRegistry::ensure beim Handshake, idempotent über IJobList::has |
| T-02-84 | Elevation of Privilege | Handshake-Route schreibt in die Jobliste | mitigate | ensure erst nach rejectForeignCaller; nur die fest eingebaute Klassenliste aus info.xml, keine Eingabe des Aufrufers; Gate prüft Reihenfolge und Liste |
| T-02-85 | Information Disclosure | Logzeilen von JobRegistry und Listener | mitigate | nur Klassennamen von Jobs und Fehlern, keine Pfade und Namen (Gate-Regel 6) |
| T-02-86 | Tampering | Workflow discovery-e2e.yml | mitigate | Diff nur Reihenfolge der Cron-Zeilen; kein Trigger, keine Berechtigung, kein Pin geändert; nicht ausgeführt |
| T-02-87 | Denial of Service | Docker-Lauf neben fremder Sitzung | mitigate | RAM mindestens 4 GB, kein fremder Live-Test, nur eigene avs-phpcheck-Container, nie down oder prune |
</threat_model>

<verification>
- Ursache von move-cross mit Beleg im SUMMARY; Tests rot auf den Test-Commits, grün auf HEAD (Container).
- PHP: php -l Exit 0, PHPUnit OK über 569 Tests. Python: ruff, format, pyright, vulture, pytest Exit 0.
- `git log origin/phase-02..HEAD` nur mit dem Owner als Autor und Committer, ohne Trailer und ohne Schließwort.
- `git ls-remote origin refs/heads/phase-02` unverändert 25d241b (kein Push).
</verification>

<success_criteria>
- Verschieben in den Gruppenordner verliert den Verweis nicht mehr (Unit-Beleg), Bestandssemantik unverändert.
- Fehlende Hintergrundjobs kommen spätestens fünf Minuten nach dem Start des Backends zurück.
- Der Workflow kann das Kontrollbein beim nächsten freigegebenen Push bis zur Prüfung bringen.
- Plan endet am Checkpoint, ohne Push.
</success_criteria>

<output>
Create `.planning/phases/02-erfassung-aller-dateien/02-17b-SUMMARY.md` when done
</output>
