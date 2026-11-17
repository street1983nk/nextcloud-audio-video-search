---
phase: 02-erfassung-aller-dateien
plan: 12
subsystem: php-discovery
tags: [disc-02, disc-05, d-02-03, d-02-01, d-02-11, external-storage, files_external, prefilter]
requires: [02-03, 02-06, 02-10, 02-11]
provides:
  - "Externe Speicher (ConfigAdapter) ab Werk in der Mountmenge, erfassbar erst nach Klassifikation"
  - "StorageClassifier::classify/refresh/isDue/skipped, Gründe session_credentials, credentials_missing, unavailable (switched_off für Plan 16)"
  - "StorageStateMapper für avs_storage (find mit 60-s-Puffer, store, skipped)"
  - "StorageService::shareKey, shareKeyHash, prefilterKey, isExternal, EXTERNAL_STORAGE_MOUNT_PROVIDER"
  - "QueueService::storageCapturable (für Plan 19 classifyAbsent), prefilterKey in describe, readerUid-Regel für externe Speicher"
  - "occ audio_video_search:status: skippedStorages [{mountId, backend, authKind, reason, users}] und Hinweissatz"
affects: [02-13, 02-14, 02-16, 02-17, 02-19, 02-22]
tech-stack:
  added: []
  patterns:
    - "Klassifikation vor dem Einreihen: Konfiguration, Anmeldedaten, Probe je Speicher, nie je Datei"
    - "Freigabe-Schlüssel nur als sha256 in avs_storage, Vorfilter-Hash in PHP gebildet"
    - "Sitzungs-Konfigurationen zusätzlich direkt aus oc_external_mounts gemeldet"
key-files:
  created:
    - php/lib/Service/StorageClassifier.php
    - php/lib/Db/StorageStateMapper.php
    - php/tests/Unit/ShareKeyTest.php
    - php/tests/Unit/StorageClassifierTest.php
    - php/tests/Unit/StorageStateMapperTest.php
  modified:
    - php/lib/Service/StorageService.php
    - php/lib/Service/QueueService.php
    - php/lib/BackgroundJobs/SchedulerJob.php
    - php/lib/Command/StatusCommand.php
    - php/tests/Unit/QueueServiceTest.php
    - php/tests/Unit/SchedulerJobTest.php
    - php/tests/Unit/FilesCommandTest.php
    - php/tests/Unit/StorageServiceTest.php
    - backend/tests/test_php_gates.py
decisions:
  - "02-12: Klassifikationspflicht (avs_storage-Zeile mit capturable 1) gilt für ConfigAdapter-Speicher; Homes und Gruppenordner bleiben wie bisher ohne Zeile zulässig"
  - "02-12: prefilter_key = sha256(sha256(share_key) \\0 Pfad in der Freigabe \\0 Größe \\0 storage_mtime); avs_storage hält nur den Hash des Freigabe-Schlüssels"
  - "02-12: Mehrere Mount-Konfigurationen auf einem Speicher: klassifiziert wird nach der ersten (Mount-ID) mit hintergrundfähiger Anmeldung"
  - "02-12: occ :status meldet Konfigurationen mit Sitzungs-Anmeldung immer, auch ohne avs_storage-Zeile (files_external streicht im Hintergrund gescheiterte Mounts aus oc_mounts)"
  - "02-12: Neuprüfung: neu sofort, credentials_missing und session_credentials jeden Lauf (billig), sonst alle 24 h; 60 s Budget je SchedulerJob-Lauf"
metrics:
  duration: "ca. 75 min"
  completed: 2026-11-09
---

# Phase 2 Plan 12: Externe Speicher ab Werk Summary

Externe Speicher sind jetzt in der Mountmenge, werden aber erst eingereiht, wenn der StorageClassifier sie nach Anmeldeart, gespeicherten Anmeldedaten und einer Probe je Speicher als erfassbar einstuft; SMB und SFTP tragen einen Vorfilter-Schlüssel, der den Container nur als sha256 erreicht, und occ :status nennt übersprungene Konfigurationen ohne Pfad, Host oder Freigabename.

## Was gebaut wurde

**Task 1: Freigabe- und Vorfilter-Schlüssel** (d81c712 test, 08ab7f4 feat)
- `StorageService::shareKey()` nach RESEARCH-Skizze (Findling countingKey): Host nach dem letzten `@` vor `//`, SMB `smb::<host>//<share>`, SFTP `sftp::<host>[:<port>]`, Root der Konfiguration wandert in den Pfad. Auch die echte Form `smb::ana@nas//Medien//` (doppelter Schrägstrich aus SMB.php) ist abgedeckt. Leerer Host, fehlendes `@`, fehlendes `//`, leere Freigabe, Nullbyte und alle anderen Speicherarten: null.
- `shareKeyHash()` (sha256) und `prefilterKey()` (sha256 über Hash, Pfad in der Freigabe, Größe, storage_mtime, getrennt durch Nullbytes); null bei Nullbyte, kaputtem Hash, Größe < 0 oder leerem Pfad.
- `StorageStateMapper` für `avs_storage` (Tabelle stand schon in der Migration von 02-03).
- `QueueService::describe` füllt `prefilterKey` aus der gespeicherten Klassifikation, nur für externe Speicher.

**Task 2: Klassifikation, readerUid und occ-Ausgabe** (160c4bc test, edacfa6 feat, 59ed0d8 test)
- `StorageClassifier::classify()`: files_external aus oder `external_mounts` nicht lesbar: unavailable. `password::sessioncredentials` und `smb::kerberosapache`: session_credentials, ohne Aufruf von ICredentialsManager und ohne Setup. logincredentials, userprovided, global (Admin-Mount mit Nutzer ''), global::user mit den Schlüsseln aus Befund 3; nichts gespeichert: credentials_missing; Lesefehler des Speichers: unavailable. Sonst Probe als Mount-Nutzer über `IMountManager::getMountFromMountInfo` in `ReaderContext::actAs`: gleiche numerische Speicher-ID, kein FailedStorage, `getAvailability()['available']`. Der Freigabe-Schlüssel entsteht aus `getId()` des geprobten Speicherobjekts.
- `refresh()` schreibt nach `avs_storage` und meldet `becameCapturable`; `isDue()` wie in den Entscheidungen.
- `QueueService::admissible` prüft über `storageCapturable()`: externer Speicher ohne Zeile oder mit capturable 0 ist nie zulässig, also nie eingereiht und bei der Ausgabe verworfen.
- `readerUid`: Home wie bisher; externer Speicher mit genau einem oc_mounts-Nutzer: dieser (D-02-11); mehrere Nutzer oder Gruppenordner (auch mit nur einem Mitglied): erster mit `readableFile` ja, höchstens 5 Versuche.
- `SchedulerJob` klassifiziert jeden externen Speicher der Mountmenge (60 s Budget, danach nur Lesen), legt Crawls nur für erfassbare an und setzt den Crawl eines erfassbar gewordenen Speichers auf Cursor 0 zurück.
- `occ :status`: JSON-Schlüssel `skippedStorages`, Text je Eintrag `mount <id>: backend <art>, authentication <kennung>, reason <grund>, users <n>` und der Satz "Stored credentials (Log-in credentials, save in database) make these storages capturable." Kennungen, die nicht wie eine files_external-Kennung aussehen, erscheinen als `unknown`.

## Gates

| Gate | Ergebnis |
|------|----------|
| ruff check | grün |
| ruff format --check | grün, 63 Dateien |
| pyright (PYRIGHT_PYTHON_FORCE_VERSION=latest, basic) | 0 Fehler, 0 Warnungen |
| vulture | grün |
| pytest gesamt | 620 grün (darin test_php_gates.py 27) |
| php -l | **nicht gelaufen**: lokal kein PHP, Docker-Daemon aus |
| PHPUnit | **nicht gelaufen**, nicht als grün zu werten; Beleg erst in CI beim nächsten vom Owner freigegebenen Push (php.yml) |

Neue bzw. geänderte PHPUnit-Fälle, ungeprüft ausgeführt: ShareKeyTest 9 Methoden (2 mit Datenquellen, 9 und 15 Fälle), StorageClassifierTest 22 Methoden, StorageStateMapperTest 4, QueueServiceTest +9, SchedulerJobTest +4, FilesCommandTest +3, StorageServiceTest +1 (eine umbenannt). Die TDD-Reihenfolge ist in den Commits eingehalten (test vor feat), RED und GREEN konnten aber lokal nicht ausgeführt werden.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Fehlende Funktion] Sitzungs-Konfigurationen direkt aus oc_external_mounts melden**
- **Gefunden bei:** Task 2, beim Abgleich mit `ci/discovery/compare.sh` (Prüfung `skipped_session_mount`) und `topology.sh` (M1 und M2 auf derselben SMB-Freigabe mit demselben Login).
- **Problem:** (a) M2 (Sitzung) und M1 (Anmeldedaten in DB) für ana ergeben dieselbe Storage-ID, also eine avs_storage-Zeile, die nach M1 erfassbar ist; M2 tauchte nie als übersprungen auf. (b) `UserMountCache::registerMounts` streicht Mounts mit FailedStorage (Root-ID -1) aus oc_mounts, sobald der Nutzer im Hintergrund aufgesetzt wird (stable33 nachgelesen); ein Sitzungs-Speicher kann so vor der ersten Klassifikation verschwinden.
- **Fix:** `skipped()` vereinigt die nicht erfassbaren avs_storage-Zeilen mit allen Konfigurationen, deren `auth_backend` in NEVER liegt (Nutzerzahl aus oc_mounts je mount_id, auch 0). Die Klassifikation eines Speichers mit mehreren Konfigurationen nimmt die erste hintergrundfähige. Nur Ausgabe, keine Erfassung über den Sitzungsweg; Research Befund 3 empfiehlt die Meldung je Konfiguration.
- **Commit:** edacfa6

**2. [Rule 1 - Fehler] Datenquelle `never` in StorageClassifierTest hätte TestCase::never() überschrieben**
- **Problem:** PHPUnit erklärt `never()`, `once()`, `any()` usw. final und statisch; eine gleichnamige Datenquelle ist ein fataler Fehler. Gate-Regel 10 kannte nur die finalen Instanzmethoden.
- **Fix:** Datenquelle in `neverCapturable` umbenannt; `FINAL_TESTCASE_METHODS` um any, atLeast, atLeastOnce, atMost, exactly, never, once ergänzt, mit Selbsttest.
- **Commit:** 160c4bc

**3. [Ablauf] StorageStateMapper in Task 1 statt Task 2; StorageStateMapperTest zusätzlich**
- describe braucht den gespeicherten Hash schon für den Vorfilter; der Mapper kam deshalb mit Task 1. Ein Test gegen die echte Datenbank (Muster CrawlMapperTest) kam als eigener Commit dazu (59ed0d8).

### Auslegungen (bitte bei Gelegenheit bestätigen)

- **Klassifikationspflicht nur für externe Speicher.** Der Plan schreibt "Speicher ohne avs_storage-Zeile -> admissible false"; die must_haves und der key_link nennen ConfigAdapter-Speicher. Homes und Gruppenordner brauchen weiter keine Zeile, sonst würden Ereignisse neuer Homes bis zum nächsten SchedulerJob verworfen. Sicher, weil "extern" aus `getDistinctMounts([ConfigAdapter])` kommt und ein unbekannter externer Speicher nie zulässig ist.
- **prefilter_key über den Hash des Freigabe-Schlüssels.** must_have nennt sha256(share_key, ...); gebaut ist sha256(sha256(share_key), ...), weil avs_storage den Schlüssel selbst nicht halten soll (er nennt einen Host). Gruppierung gleich, der Container sieht in beiden Fällen nur einen Hash.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: outbound-probe | php/lib/Service/StorageClassifier.php | Die Probe setzt den Mount eines Nutzers im Cron-Prozess auf; files_external kann dabei den externen Server kontaktieren (Verfügbarkeit). Begrenzt durch 60 s je Lauf und 24 h je erfassbarem Speicher; keine Datei wird gelesen, nichts verlässt den Server außer der Anmeldung von files_external selbst. |

## Known Stubs

- `REASON_SWITCHED_OFF` ist definiert, wird erst vom Admin-Schalter in Plan 16 gesetzt.
- `avs_storage.rescanned_at` bleibt unberührt (Plan 14).

## Offene Punkte

- PHPUnit und `php -l` für alle neuen PHP-Dateien stehen aus (nächster freigegebener Push, Plan 17).
- Annahme aus Research, im CI zu belegen: `getAvailability()` nach dem Setup erkennt falsche Passwörter erst, nachdem files_external den Speicher einmal als nicht verfügbar markiert hat; bis dahin gilt ein solcher Speicher als erfassbar, und die Downloads scheitern im Container mit Wiederholung (kein Leck, nur Kosten).
- Veraltete avs_storage-Zeilen von Speichern, die ganz verschwunden sind, räumt erst Plan 19 (classifyAbsent) auf; bis dahin stehen sie in `skippedStorages`.

## Self-Check: PASSED

- Dateien vorhanden: StorageClassifier.php, StorageStateMapper.php, ShareKeyTest.php, StorageClassifierTest.php, StorageStateMapperTest.php.
- Commits vorhanden: d81c712, 08ab7f4, 160c4bc, edacfa6, 59ed0d8.

## Push 5, fa3af22 (09.11.2026)

- PHP gates 42581644685 grün: die neuen PHPUnit-Fälle von 02-12 liefen zum ersten Mal und bestehen. Python gates 42581644528 grün.
- Deploy through HaRP 42581644614 (nach einer Wiederholung mit Owner-Freigabe): alle sechs deploy-harp-Beine und upgrade stable33/stable35 amd64 grün; upgrade stable34 amd64 und stable35 arm64 zweimal rot am Download von frp aus den GitHub-Releases (curl 504, 07:49 und 08:14 UTC), kein Befund am Produkt.
- Discovery acceptance 42581644556: Aufbau lief durch, Urteil rot wie bei Push 4 (Pläne 13 bis 22); leak-control rot, Patch kommt mit Plan 13.
- Gegen Push 4 (42387720556): grün geworden sind initial:skipped_session_mount (Ziel dieses Plans) sowie rename/tag/trash/restore unreadable_set und unreadable_count, transcribed in rename/tag/trash/restore und reprove:cem_finds_before (Positivkontrolle greift jetzt).
- Neu rot, eingeordnet:
  - reprove:cem_finds_no_revoked_copy (erwartet false, gefunden true): die Positivkontrolle greift erst jetzt, weil die SMB-Datei von cem nun erfasst wird. Nach dem Samba-Entzug findet cem die Kopie noch, weil der erneute Lesebeweis fehlt. Gehört zu Plan 13 (Lesebeweis) und 20, wie reprove:reprove_unreadable schon in Push 4. Nichts davon ist veröffentlicht.
  - vanish und reattach unreadable_set/unreadable_count (erwartet 1, gefunden 2, zuviel 52): Datei 52 wird jetzt früh als unlesbar erkannt und bleibt es nach dem Verschwinden ihres Speichers. Das Aufräumen verschwundener Speicher ist Plan 19 (classifyAbsent).
