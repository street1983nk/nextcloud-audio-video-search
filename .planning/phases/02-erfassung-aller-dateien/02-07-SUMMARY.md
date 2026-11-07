---
phase: 02-erfassung-aller-dateien
plan: 07
subsystem: php-erfassung
tags: [ereignisse, listener, cache-ereignisse, disc-04, disc-06]
requires: [02-03]
provides:
  - "FileEventListener: NodeCreated/Written/Touched/Copied -> content, NodeRenamed selber Speicher -> metadata, über Speichergrenzen content Ziel plus delete abweichende Quell-ID, nicht mehr zulässiges Ziel -> delete, NodeDeleted -> delete (Datei in der Mountmenge)"
  - "CacheEventListener: CacheEntryInserted/Updated -> content, CacheEntryRemoved -> delete; Medientyp per IMimeTypeDetector::detectPath als erste Frage"
  - "UserEventListener: UserDeletedEvent setzt app config sweep_hint_at (Zeit), sonst nichts"
  - "Application::register: drei Listen von Ereignissen, je eine pro Listener; keine Systemtag-Ereignisse"
affects: [02-11, 02-14, 02-18, 02-20]
tech-stack:
  added: []
  patterns:
    - "Eine Vorprüfung für Crawl und Ereignisse: StorageService::mountRelativePath plus QueueService::admissible"
    - "Löschen ohne Medientyp-Prüfung am Knoten (der Typ entscheidet, was hinein, nie was hinaus), aber nur für Speicher der Mountmenge"
    - "Listener schlucken jeden Fehler, Logzeile nur mit der Klasse"
key-files:
  created:
    - php/lib/Listener/FileEventListener.php
    - php/lib/Listener/CacheEventListener.php
    - php/lib/Listener/UserEventListener.php
    - php/tests/Unit/FileEventListenerTest.php
    - php/tests/Unit/CacheEventListenerTest.php
  modified:
    - php/lib/AppInfo/Application.php
decisions:
  - "Cache-Ereignisse tragen keinen Mimetyp; der Typ kommt aus der Pfadendung (gleiche Zuordnung, mit der Nextcloud ihn speichert), describe prüft die echte Cache-Zeile bei der Ausgabe noch einmal"
  - "Removed eines Mediums nur für Speicher der Mountmenge, damit Vorschauen und app data keine Löschzeilen erzeugen"
  - "Ein umbenanntes Ziel, das nicht mehr zulässig ist (andere Endung, außerhalb der Wurzel), wird als delete eingereiht"
  - "Der gelöschte Nutzer ist nur ein Hinweis (app config sweep_hint_at), das Löschen bleibt beim Sweep (Plan 20)"
  - "Ordner werden im Listener nicht aufgefächert; Umbenennen im Speicher ändert keine file_id, Verschieben über Speichergrenzen holen Cache-Ereignisse und Abgleich nach"
metrics:
  duration: "ca. 35 min"
  completed: 2026-11-07
  tasks: 2
  files: 6
---

# Phase 2 Plan 07: Node- und Cache-Ereignisse Summary

Neue, geänderte, kopierte, verschobene und gelöschte Medien kommen jetzt über drei Listener ohne Abgleich in die Warteschlange: Node-Ereignisse für alles, was über View schreibt, Cache-Ereignisse für Scanner-Funde, und ein gelöschter Nutzer setzt nur einen Hinweis für den Sweep; Taggen reiht nichts ein, Umbenennen nur metadata.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Node- und Nutzerereignisse | c54a2b2 | FileEventListener.php, UserEventListener.php, Application.php, FileEventListenerTest.php |
| 2 | Cache-Ereignisse aus Scannern | 7ebc9c2 | CacheEventListener.php, Application.php, CacheEventListenerTest.php |

## Prüfungen

- Lokal kein PHP: phpunit (FileEventListenerTest 11 Fälle, CacheEventListenerTest 6 Fälle) und `php -l` laufen erst in CI (php.yml, Push in Plan 11).
- test_php_gates.py 27 grün über die neuen Dateien (Regel 6: keine Pfade in Logzeilen; Regel 7/8: Kopf, keine Gedankenstriche; Regel 12/13 unberührt).
- Volle Python-Gates seriell grün: ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture, pytest 487 grün.
- OCP nach stable33: Node-Ereignisse (AbstractNodeEvent, NodeCopiedEvent/NodeRenamedEvent mit Quelle und Ziel), ICacheEvent (getPath, getFileId, getStorageId), CacheEntryInserted/Updated/RemovedEvent(IStorage, path, fileId, storageId), IMimeTypeDetector::detectPath, UserDeletedEvent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2] Umbenennen weg von einer Medienendung**
- Ein Ziel, das nicht mehr zulässig ist, bliebe sonst als Verweis mit altem Typ im Vorrat; es wird jetzt als delete eingereiht. Test im FileEventListenerTest. Commit c54a2b2.

**2. [Rule 2] Removed nur für die Mountmenge**
- CacheEntryRemoved feuert auch für app data und Vorschauen; ohne die Mountmengen-Frage entstünden Löschzeilen für fremde Speicher. Commit 7ebc9c2.

**3. [Rule 3] Medientyp der Cache-Ereignisse aus der Pfadendung**
- Die Cache-Ereignisse tragen keinen Eintrag und keinen Mimetyp; eine Abfrage je Ereignis widerspräche A7. IMimeTypeDetector::detectPath ordnet ohne Datenbank zu, die Mimetyp-ID geht danach durch admissible und damit gegen allowedMimeIds. Commit 7ebc9c2.

**4. Commit-Schnitt von Application.php**
- Task 1 committete Application.php ohne die Cache-Liste, damit kein Commit eine noch fehlende Klasse nennt; Task 2 ergänzt sie.

## Known Stubs

- NodeDeleted reiht delete ein; Papierkorb (trash, restore) unterscheidet Plan 18.
- Gruppenwechsel (UserAdded/UserRemoved) und Freigabe-Ereignisse kommen mit den Ausschlüssen (Plan 16/18).
- sweep_hint_at liest erst der Abgleich in Plan 20.

## Threat Flags

Keine neue Oberfläche über das Threat-Register hinaus (T-02-24: Medientyp-Vorfilter vor jeder Abfrage, try/catch; T-02-25: Reihenfolge Removed vor Inserted übergeben, die Warteschlange lässt content gewinnen).

## Self-Check: PASSED

- FOUND: FileEventListener.php, CacheEventListener.php, UserEventListener.php, FileEventListenerTest.php, CacheEventListenerTest.php
- FOUND: c54a2b2, 7ebc9c2
