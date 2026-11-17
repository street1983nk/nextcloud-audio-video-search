# Phase 2: Erfassung aller Dateien - Research

**Researched:** 2026-11-07
**Domain:** Nextcloud-Dateierfassung (Mount-Crawl, Ereignisse, Abgleich), externe Speicher (SMB, SFTP, S3, lokal), Gruppenordner, Ausschlüsse, Inhalts-Dedupe mit Vorfilter, Ende-zu-Ende-Abnahme gegen unabhängige Wahrheit
**Confidence:** HIGH für Nextcloud-Kern und Findling-Befunde (am Quelltext belegt), MEDIUM für Zuschnitt Cache-Ereignisse und Rescan externer Speicher, MEDIUM für die Semantik von Nutzer- und Gruppenausschluss (Owner-Bestätigung nötig)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Freigabe pro Nutzer (Lehre aus Findling #25)
- **D-02-01:** Vorfilter vor dem Hash: gleiche Freigabe (Speicher-Schlüssel ohne Nutzeranteil, Muster Findling `StorageService::countingKey`), gleicher Pfad innerhalb der Freigabe, gleiche Größe und gleiches Änderungsdatum gelten als dieselbe Datei. Sie wird nur einmal geladen und gehasht (sha256 der Bytes bleibt der Inhalts-Schlüssel aus Phase 1), weitere Kopien hängen sich an dieselbe media_id. Jede Abweichung (Größe, mtime, etag) führt zu neuem Hash.
- **D-02-02:** Rechte bleiben pro Nutzer: jede Kopie behält ihre eigene file_id als Verweis, die Suche prüft weiter über den Ordner des suchenden Nutzers (Findling-Lehre: Index nur einmal pro Freigabe würde Treffer für andere Nutzer verstecken).

#### Anmeldung per Sitzung
- **D-02-03:** Externe Speicher mit Anmeldedaten aus der Sitzung (oder ohne gespeicherte Anmeldedaten) werden übersprungen. Der Admin sieht, welche Speicher betroffen sind, warum, und dass gespeicherte Anmeldedaten sie erfassbar machen. Keine Dateinamen in dieser Meldung. Erfassen bei Anmeldung: deferred.

#### Rückwirkender Ausschluss
- **D-02-04:** Ein Ausschluss (Nutzer, Gruppe, Ordner, externer Speicher) entfernt sofort die Verweise der betroffenen Dateien, ausgeschlossene Nutzer sehen keine Treffer mehr. Transkript und Korrekturen von Hand bleiben, solange noch ein erfasster Verweis auf denselben Inhalt existiert. Fällt der letzte Verweis, werden Transkript, Index-Einträge und Korrekturen gelöscht.
- **D-02-05:** Ausschlüsse greifen vor dem ersten Durchlauf: eine ausgeschlossene Datei landet nie im Arbeitsvorrat und wird nie geladen.

#### Zahl im Admin
- **D-02-06:** Die Fortschrittszahl zählt Inhalte: "X von Y Inhalten transkribiert", Zähler und Nenner beide nach Inhalts-Schlüssel (vor dem Hash nach Vorfilter-Schlüssel), klein daneben die Zahl der Dateien. Quote nie über 100 %. Ob die Anzeige selbst schon in Phase 2 oder erst in Phase 9 (ehrliche Admin-Zustände) kommt, entscheidet der Plan; die Zählung muss aber in Phase 2 stimmen und per occ abfragbar sein.
- **D-02-07:** Pflicht-Abnahmetest gegen eine UNABHÄNGIGE Zählung (nicht mit dem Code der Umsetzung): SMB-Freigabe mehrfach pro Nutzer mit unterschiedlicher Sicht, Gruppenordner, Kopie/Verschieben/Umbenennen/Taggen, verschwundener Speicher, gelöschter Nutzer, Ausschluss vor und nach dem ersten Durchlauf. Dazu eine Positivkontrolle. Findling #25 ging dreimal durch, weil nur Einzelteile getestet wurden.

### Claude's Discretion
- Ereignisweg (AppAPI node_event) und periodischer Abgleich nach Findling-Muster (reconcile, Quiet-Gate, Sweep), inklusive der 1.6.3-Lehre: der Sweep verschwundener Speicher darf nicht hinter dem Quiet-Gate hängen.
- Sperrfrist für lange Vorschauen, SMB/S3-Timeouts, files_accesscontrol, Crawl-Flag-Tor: Recherche.

### Deferred Ideas (OUT OF SCOPE)
- Speicher mit Sitzungs-Anmeldedaten erfassen, während der Nutzer angemeldet ist.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DISC-01 | Ohne Konfiguration werden alle Audio- und Videodateien aller Nutzer erfasst, inklusive Gruppenordner | Mount-Crawl über `IFileAccess::getDistinctMounts` + `getByAncestorInStorage` mit Mimetyp-IDs `audio/%` und `video/%` (Befund 1, 2); Gruppenordner sind ein Speicher mit einer file_id für alle Mitglieder (Befund 4) |
| DISC-02 | Externe Speicher (SMB, S3 usw.) werden erfasst; Admin kann sie per Schalter ausschließen | ConfigAdapter im Provider-Satz ab Werk; Anmeldeart je Mount-Konfiguration aus `oc_external_mounts.auth_backend` + `ICredentialsManager` (Befund 3); Schalter je Mount-Konfiguration (`mount_id`), Wirkung über `storage_id` |
| DISC-03 | Ausschlüsse greifen vor dem ersten Durchlauf und rückwirkend | Prüfung beim Einreihen UND bei der Übergabe an den Container (zweimal, Befund 7); rückwirkend über Löschaufträge nach Speicher-ID oder file_id-Bändern, Aufräumen der media über Verweiszählung (Pattern 4) |
| DISC-04 | Neue/geänderte Dateien in Minuten (Ereignisse), Änderungen außerhalb über periodischen Abgleich | Node-Ereignisse wie Findling plus `CacheEntryInsertedEvent`/`CacheEntryUpdatedEvent` für Scanner-Funde; Rescan externer Speicher als eigener Job, weil Nextcloud Fremdänderungen im Hintergrund nicht sieht (Befund 5) |
| DISC-05 | Gleicher Inhalt nur einmal (Inhalts-Schlüssel), auch bei Kopien, Verschieben, Umbenennen, je Nutzer eingebundenen Speichern | `file_ref` je file_id, `media_key(file_sha256)`; Vorfilter-Schlüssel aus normalisiertem Freigabe-Schlüssel + Pfad + Größe + mtime, **mit Lesebeweis je Kopie** (Befund 6, Pflicht wegen Findling-Messung A6) |
| DISC-06 | Verschieben, Umbenennen, Taggen lösen keine Neuberechnung aus | Umbenennen/Verschieben im selben Speicher behält die file_id; Taggen ändert kein ETag in `oc_filecache` (nur `oc_systemtag.etag`, Befund 8); Verschieben über Speichergrenzen = neue file_id, gleicher sha256, gleiche media_id |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Kein Audio, kein Text, keine Telemetrie verlässt den Server; Logzeilen nur mit Zählern und IDs, nie Pfade, Dateinamen, Hosts, Freigaben oder Nutzer (Findling T-36-17, T-39-01).
- Qualität vor Speed; Entwicklungsaufwand ist kein Grund, eine messbar bessere Lösung wegzulassen.
- Python 3.13 über uv, FastAPI, nc_py_api nur Async-API; ruff-Vollsatz, pyright basic (lokal `PYRIGHT_PYTHON_FORCE_VERSION=latest`), vulture lokal grün vor Commit.
- PHP >= 8.2, NC 33 bis 35, AppAPI mit HaRP, amd64 + arm64; PHP-Tests nur in CI (`php.yml`), lokal kein PHP.
- Nutzersichtbare Texte DE/EN/FR im Gleichstand, Deutsch zuerst, echte Umlaute nur in Prosa (nie in Code, URLs, YAML), keine Gedankenstriche, keine Emojis.
- Commits nur als street1983nk <k.cherif@outlook.de>, kein "closes #N"; vor jedem Push, Merge oder Kommentar den Owner fragen.
- UI-Abnahme gemeinsam per Playwright (3 Breiten, hell/dunkel); neue UI löst den UI-Phase-Ablauf aus (`workflow.ui_phase: true`).
- Rechte nie über den Inhalts-Schlüssel vererben (Phase 1, Entscheid 3); Rechteprüfung in PHP über den Ordner des Nutzers.
- Gegenprobe nie mit dem Muster der Umsetzung; Positivkontrolle Pflicht.

## Summary

Die Erfassung lässt sich fast vollständig aus Findling übernehmen: Mount-Liste über `IFileAccess::getDistinctMounts` (NC 32+, öffentlich), Datei-Scheiben über `getByAncestorInStorage` mit Mimetyp-Filter in der Abfrage, eine PHP-Warteschlange mit bedingtem Claim, Node-Ereignisse, ein Container-Abgleich über ETag, Sweep verschwundener Speicher mit `classifyAbsent`. Alle Medienformate aus MEDIA-01 tragen in Nextcloud einen Mimetyp `audio/*` oder `video/*` (`mimetypemapping.dist.json`, stable33), der Filter ist also eine `LIKE`-Abfrage auf `oc_mimetypes` ohne Sonderliste. Neu gegenüber Findling sind fünf Dinge: externe Speicher sind ab Werk an (Findling: aus), es gibt Nutzer- und Gruppenausschlüsse, die Dedupe läuft über Inhalt statt über Zählung, die eigentliche Arbeit (Transkription) dauert Minuten bis Stunden statt Sekunden, und die Abnahme muss eine echte SMB-Topologie fahren.

Der wichtigste Befund betrifft D-02-01: **Findling hat genau diese Variante ("Weg A") am 28.10.2026 auf echtem Samba gemessen und verworfen** (Findling `39-DEDUP-ERGEBNIS.md`, Messung A6, CI-Lauf 40716240639). Ein SMB-Nutzer B sieht eine Datei, die ihm der Server per ACL sperrt, trotzdem gelistet, `isReadable()` ist true im Node und im SMB-Speicher, auch mit `check_acl`; nur der Download liefert nichts (er hängt sogar ohne Antwort). Hängt sich B's file_id per Vorfilter an die media_id von A, besteht B die Suchprüfung `FileAccess::readableFile()` und sieht A's Transkript: ein Rechteleck, das D-02-02 nicht abfängt. Die Lösung, die D-02-01 im Kern erhält: **Lesebeweis je Kopie**. Jede weitere Kopie wird über ihre eigene file_id und ihren eigenen Leser einmal kurz angelesen (erste 64 KiB, harte Zeitgrenze), der Kopf-Hash muss zum Kopf-Hash der media passen; erst dann hängt sie sich an. Voll geladen und gehasht wird weiter nur einmal. Das ist Findlings T-39-11 ("Übernahme nur nach eigenem erfolgreichem Download"), billig gemacht. Owner-Bestätigung nötig (Open Question 1).

Der zweite große Befund betrifft die Research-Flags "Sperrfrist" und "Quiet-Gate": Wenn der Container einen Eintrag der PHP-Warteschlange erst nach der Transkription quittiert, bräuchte eine 3-Stunden-Aufnahme eine Sperrfrist von Stunden (Findling: 900 bis 1800 s, danach `failed(repeatedly_stuck)` mitten in korrekter Arbeit, T-03-503), und die Warteschlange wäre dauerhaft voll, womit Findlings Quiet-Gate den Abgleich verhungern ließe (#25, 38x `queue_busy`, 0x `walked`). **Empfehlung: Die PHP-Warteschlange trägt nur die Erfassung.** Der Container quittiert, sobald er den Verweis dauerhaft in `state.db` eingetragen hat (Sekunden). Laden, Hashen und später Transkribieren laufen in einer Stufen-Tabelle des Containers mit eigener Wiederaufnahme. Damit bleibt die PHP-Warteschlange klein, die Sperrfrist kurz und fest, und das Tor vor dem Abgleich ist nur noch "Erst-Crawl dieses Mounts fertig" (Crawl-Flag je Mount), nicht mehr die Länge einer Warteschlange.

**Primary recommendation:** Findling-Erfassung (getDistinctMounts, Warteschlange mit Claim, Node-Ereignisse, Abgleich, Sweep vor dem Tor) übernehmen, die PHP-Warteschlange auf "Verweis eintragen" beschränken, Vorfilter-Schlüssel in PHP aus dem unverkürzten Storage-ID-String des Speicherobjekts bilden und als sha256 übergeben, jede Vorfilter-Kopie per 64-KiB-Lesebeweis absichern, externe Speicher nach Anmeldeart vorab klassifizieren und Fremdänderungen über einen budgetierten Rescan-Job sichtbar machen; abgenommen per Samba-CI-Job mit Wahrheit aus Dateisystem, `sha256sum` und dem Zugriffslog des Webservers.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Mount-Liste, Datei-Scheiben, Mimetyp-Filter | PHP (StorageService) | Container (fragt Scheiben für den Abgleich) | nur PHP sieht `oc_mounts`/`oc_filecache` |
| Anmeldeart externer Speicher, Erfassbarkeit (D-02-03) | PHP (StorageService, eigene Tabelle `avs_storage`) | Container (zeigt Zustand per Status) | nur PHP sieht `oc_external_mounts` und `ICredentialsManager` |
| Freigabe-Schlüssel, Vorfilter-Schlüssel | PHP (aus `IStorage::getId()` des Speicherobjekts) | Container (vergleicht nur Hashes) | Container bekommt nie Pfade; `oc_storages.id` ist über 64 Zeichen md5-verkürzt |
| Ausschlussregeln, Auswertung | PHP (ExclusionService) | Container (löscht auf Auftrag) | Regeln brauchen Pfade, Gruppen, Mitgliedschaften |
| Ereignisse | PHP (Listener) | , | AppAPI-Webhooks verworfen (Findling, STACK.md) |
| Erst-Crawl, Rescan externer Speicher | PHP (QueuedJob/TimedJob, Hintergrund) | , | Dateisystem-Setup und Scanner nur in PHP |
| Arbeitsvorrat (Verweise, Stufen), Dedupe, Zählung | Container (`state.db`) | PHP (occ fragt per Admin-Route) | Inhalts-Schlüssel und Transkripte liegen im Container |
| Lesebeweis, Laden, Hashen | Container (Ablauf) | PHP (Gateway liefert Bytes/Kopf als Leser) | Rechteentscheid im Gateway über den Ordner des Lesers |
| Abgleich (ETag-Vergleich), Sweep | Container (Takt) | PHP (Mountliste, `classifyAbsent`) | Findling D-01: kein zweiter Weckkanal |
| Treffer nur für erlaubte Nutzer | PHP (Provider, Phase 1) | , | unverändert, zusätzlich: ausgeschlossene Nutzer bekommen leer |

## Standard Stack

Keine neuen Bibliotheken. Alles mit Nextcloud-OCP, Findling-Mustern und vorhandenem Python-Stack.

### Core (Nextcloud-APIs, am Quelltext stable33 geprüft)
| API | Seit | Zweck | Beleg |
|-----|------|-------|-------|
| `OCP\Files\Cache\IFileAccess::getDistinctMounts(array $providers, bool $onlyUserFilesMounts)` | 32.0.0 | Mount-Liste einmal je (root_id, storage_id), Home auf `files` umgebogen | [VERIFIED: nextcloud/server stable33 `lib/public/Files/Cache/IFileAccess.php:113`, `lib/private/Files/Cache/FileAccess.php:190-230`] |
| `IFileAccess::getByAncestorInStorage(storage, folderId, cursor, max, mimeIds, e2e, sse)` | 32.0.0 | Datei-Scheiben mit Mimetyp-Filter in der Abfrage | [VERIFIED: IFileAccess.php:99] |
| `OCP\Files\Config\IUserMountCache::getMountsForStorageId()` → `ICachedMountInfo::getMountId()/getMountProvider()/getUser()` | alt | Mount-Konfiguration (files_external `mount_id`) und Nutzer je Speicher | [VERIFIED: IUserMountCache.php:48; `oc_mounts` hat `mount_id`, `mount_provider_class`, `user_id`, UserMountCache.php:174-180] |
| `OCP\Security\ICredentialsManager::retrieve(uid, identifier)` | alt | Prüfen, ob gespeicherte Anmeldedaten existieren (D-02-03) | [VERIFIED: LoginCredentials.php, UserProvided.php, GlobalAuth.php nutzen genau diese Kennungen] |
| `OCP\Files\Storage\IStorage::getScanner()` → `IScanner::scan(path, SCAN_RECURSIVE, REUSE_ETAG\|REUSE_SIZE)` / `backgroundScan()` | alt | Rescan externer Speicher für Fremdänderungen | [VERIFIED: IStorage.php:395, IScanner.php:19-89] |
| `OCP\Files\Cache\CacheEntryInsertedEvent`, `CacheEntryUpdatedEvent`, `CacheEntryRemovedEvent` | NC 22+ | Funde des Scanners (auch `occ files:scan` des Admins) als Ereignis | [VERIFIED: `lib/private/Files/Cache/Cache.php:316,386,595`] |
| Node-Ereignisse `NodeCreated/Written/Touched/Copied/Renamed/Deleted`, Trashbin `MoveToTrash/NodeRestored`, `OCP\User\Events\UserDeletedEvent`, `OCP\Group\Events\UserAdded/UserRemoved` | alt | Ereignisweg | [VERIFIED: Findling `Application.php:77-127`] |

### Supporting (Findling-Bausteine, kopiert, nicht importiert)
| Baustein | Findling-Ort | Zweck |
|----------|--------------|-------|
| QueueMapper (Claim per bedingtem Update, Ablauf der Sperre, dirty-Markierung, Kind-Reihenfolge) | `php/lib/Db/QueueMapper.php` | Arbeitsvorrat in PHP bis zur Übergabe |
| StorageService (`providers()`, `getMounts()`, `classifyAbsent()`, `countingKey()`) | `php/lib/Service/StorageService.php:244-578` | Mountmenge, gone/deselected, Freigabe-Schlüssel |
| StorageCrawlJob, SubtreeExpandJob, ExclusionSweepJob | `php/lib/BackgroundJobs/` | Erst-Crawl in Bändern, Aufräumen eines Teilbaums |
| FileEventListener, GroupEventListener | `php/lib/Listener/` | Ereignisweg |
| reconcile.py (`run_once`, `_sweep_vanished`, `_cadence_due`, `_hand_over` in Bändern) mit Phase-43-Umbau | `backend/src/findling/worker/reconcile.py`, `43-RESEARCH.md` Pattern 1 | Abgleich und Sweep unabhängig vom Tor |
| `nc/queue.py`, `nc/files.py` | `backend/src/findling/nc/` | Claim/Ack/Unlock, Mountliste, Scheiben, gone_storages |
| smb-acl-measure (Samba auf dem Runner, Positivkontrolle am Server) | `.github/workflows/smb-acl-measure.yml`, `scripts/ci/smb_acl_measure.sh` | Vorlage für den D-02-07-Job |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PHP-Listener | AppAPI `node_event`-Webhooks | asynchron, keine Share-/Gruppen-/Cache-Ereignisse; Findling verwirft es; PHP-App ist ohnehin da |
| Anmeldeart aus `oc_external_mounts.auth_backend` (DB) | `OCA\Files_External\Service\GlobalStoragesService::getStorage(mountId)->getAuthMechanism()->getIdentifier()` | App-interne Klasse statt privater Tabelle; beides nicht OCP. DB-Spalten sind seit NC 9 unverändert (`DBConfigService.php:54`), Klassen wurden mehrfach umgebaut. Empfehlung DB, hinter `try/catch` und `IAppManager::isEnabledForAnyone('files_external')` |
| Rescan-Job | `occ files_external:notify` (nur SMB, Dauerprozess) | widerspricht "ohne Konfiguration"; in der Doku als Beschleuniger nennen |
| Vorfilter mit Lesebeweis | Jede Kopie voll laden und hashen | korrekt und einfach, aber n-facher Download (bei 12 Nutzern einer Freigabe 12x jedes Video) |
| Vorfilter mit Lesebeweis | Vorfilter ohne Lesebeweis (D-02-01 wörtlich) | Rechteleck A6, nicht empfehlbar |

**Installation:** keine.

## Package Legitimacy Audit

Diese Phase installiert keine externen Pakete (weder PyPI noch Composer noch npm). slopcheck nicht nötig. Im CI-Job kommen `samba`, `smbclient` und `sqlite3` aus dem Ubuntu-Archiv des Runners (wie Findling `smb_acl_measure.sh`).

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
  Quellen der Wahrheit "welche Dateien gibt es"
  ┌───────────────────────────────────────────────────────────────────────────┐
  │ Upload/WebDAV/Apps ──> Node-Ereignisse ─┐                                 │
  │ occ files:scan / Rescan-Job ──> Cache-Ereignisse (Insert/Update) ─┤        │
  │ Erst-Crawl je Mount (QueuedJob, Bänder, Cursor) ──────────────────┤        │
  │ Abgleich des Containers (ETag-Vergleich je Scheibe) ──────────────┤        │
  └───────────────────────────────────────────────────────────────────┼───────┘
                                                                      v
                PHP: Vorprüfung je Datei (billig, ohne Fernzugriff)
                  Mimetyp audio/* oder video/*? ── nein ──> verwerfen
                  Speicher in Mountmenge? ── nein ──> verwerfen
                  Speicher erfassbar? (avs_storage: Anmeldeart) ── nein ──> zählen als
                        "Speicher übersprungen" (ohne Dateiname), nicht einreihen
                  Ausschluss? (Nutzer/Gruppe über Speicher-Eigentümer, Ordnerpräfix,
                        Speicherschalter) ── ja ──> nicht einreihen (D-02-05)
                  sonst: Zeile in oc_avs_queue (file_id, storage_id, kind,
                        prefilter_key = sha256(share_key, path_in_share, size, mtime))
                                                                      |
                Container-Poller (alle ~30 s): Claim n Zeilen  <──────┘
                  PHP prüft bei der Ausgabe NOCHMAL Ausschluss + Erfassbarkeit,
                  liefert je Zeile: file_id, storage_id, etag, size, mtime,
                  prefilter_key, reader_uid (erster Nutzer, der lesen kann)
                                                                      |
                Container: Eintrag in state.db (eine Transaktion), dann Ack
                  file_ref(file_id) neu/aktualisiert, stage = 'pending'
                  (etag,size,mtime) unverändert und media_id bekannt? ──> fertig
                                                                      |
                Container-Stufe "Erfassen" (eigene Wiederaufnahme, keine PHP-Sperre)
                  Vorfilter-Geschwister mit media_id da?
                     ja ──> Lesebeweis: GET Kopf 64 KiB über eigene file_id + reader
                             ok und Kopf-Hash == media.head_sha256 ──> media_id anhängen
                             verweigert/Zeitgrenze ──> state 'unreadable' (zählt nicht)
                             Kopf passt nicht ──> wie "kein Geschwister"
                     nein ──> voller Download über Gateway in temp-Datei,
                             sha256 + Kopf-sha256 im Strom ──> media_key(file_sha256)
                             ──> media_id (neu oder vorhanden) ──> wartende
                             Geschwister bekommen ihren Lesebeweis
                                                                      |
                Phase 3 nimmt media ohne current als Transkriptionsarbeit

  Ausschluss gesetzt (Admin) ──> PHP: betroffene Speicher-IDs (Nutzer, Gruppe,
     Speicherschalter) oder Teilbaum-Bänder (Ordner) ──> Löschaufträge kind 'exclude'
     ──> Container: file_ref löschen, media ohne Verweis ──> Transkripte, Wörter,
     current, Korrekturen, Index-Dokumente weg (D-02-04)

  Container-Takt (alle 300 s): Sweep fällig? (eigener Stempel, NICHT hinter dem Tor)
     ──> Mountliste ──> gone/deselected sofort, sonst 30-Tage-Stempel
     Walk fällig und Mount-Crawl fertig? (Crawl-Flag je Mount) ──> ETag-Vergleich

  occ audio_video_search:files / :status ──> Container /workstock, /coverage (ADMIN)
     ──> "X von Y Inhalten, N Dateien", Speicher übersprungen mit Grund, nur Zahlen/IDs
```

### Recommended Project Structure
```
php/lib/
├── Db/QueueMapper.php, QueueFile.php        # Arbeitsvorrat bis zur Übergabe (Findling)
├── Db/StorageStateMapper.php                # avs_storage: share_key, auth_kind, capturable, reason
├── Migration/Version000200Date2026111X.php  # avs_queue, avs_storage, avs_crawl
├── Service/StorageService.php               # providers(), getMounts(), classifyAbsent(),
│                                            # shareKey(), authKind(), prefilterKey()
├── Service/ExclusionService.php             # Nutzer, Gruppen, Präfixe, Speicherschalter
├── Service/QueueService.php                 # enqueue mit Vorprüfung, describe() bei Ausgabe
├── Listener/FileEventListener.php           # Node-Ereignisse
├── Listener/CacheEventListener.php          # Insert/Update aus Scannern
├── Listener/GroupEventListener.php, UserEventListener.php
├── BackgroundJobs/SchedulerJob.php          # neue Mounts, Rescan-Fälligkeit
├── BackgroundJobs/StorageCrawlJob.php       # Erst-Crawl je Mount, Cursor, finished_at
├── BackgroundJobs/ExternalRescanJob.php     # Scanner mit Zeitbudget je Lauf
├── BackgroundJobs/ExclusionClearJob.php     # rückwirkend, Bänder
├── Controller/QueueController.php           # /queues/media (Claim, Ack, Unlock)
├── Controller/ReconcileController.php       # /mounts, /mounts/{s}/slice, /storages/gone
├── Controller/GatewayController.php         # + Kopf-Route für den Lesebeweis
└── Command/FilesCommand.php, StatusCommand.php
backend/src/audio_video_search_backend/
├── nc/queue.py, nc/files.py                 # Claim/Ack, Mountliste, Scheiben
├── worker/intake.py                         # Claim -> state.db -> Ack
├── worker/capture.py                        # Lesebeweis, Download+Hash, Anhängen
├── worker/reconcile.py                      # Abgleich + Sweep (Findling 1.6.3-Form)
├── store/schema.sql, repo.py                # Schema v2 (siehe Pattern 3)
└── api/workstock.py, api/coverage.py        # ADMIN-Routen für occ
```

### Befund 1: Mountmenge ab Werk

Findling-Provider-Satz plus external storage an: `LocalHomeMountProvider`, `ObjectHomeMountProvider`, `OCA\GroupFolders\Mount\MountProvider`, `OCA\Files_External\Config\ConfigAdapter` [VERIFIED: Findling StorageService.php:52-86]. Eingehende Freigaben (`files_sharing`) werden nicht gelaufen, die Datei ist dieselbe file_id wie beim Eigentümer. Föderierte Freigaben bleiben draußen (fremder Server). `onlyUserFilesMounts=true` lässt Papierkorb und Versionen weg (FileAccess.php:194-230). Kosten-Hinweis: Findling hat externe Speicher bewusst ab Werk aus (T-04-52, "multi terabyte share"); DISC-02 verlangt sie ab Werk an. Für Medien ist das vertretbar, weil die Bytes für die Transkription ohnehin gelesen werden, die Doku muss es aber nennen.

### Befund 2: Mimetyp-Filter

Alle Formate aus MEDIA-01 haben in Nextcloud einen `audio/*`- oder `video/*`-Typ: mp3 `audio/mpeg`, m4a `audio/mp4`, wav `audio/wav`, ogg/oga/opus `audio/ogg`, flac `audio/flac`, mp4/m4v `video/mp4`, mov `video/quicktime`, mkv `video/x-matroska`, webm `video/webm`, weba `audio/webm`, mts `video/MP2T` (Großbuchstaben!), avi, wmv, 3gp, mpeg [VERIFIED: `resources/config/mimetypemapping.dist.json` stable33]. Die ID-Liste kommt aus `SELECT id FROM oc_mimetypes WHERE LOWER(mimetype) LIKE 'audio/%' OR LOWER(mimetype) LIKE 'video/%'`, je Prozess einmal (Findling `getAllowedMimeIds`-Muster), weil `IMimeTypeLoader` keine Liste anbietet. Ein Mimetyp, den die Instanz erst später sieht, kommt beim nächsten Prozess dazu; der Abgleich holt verpasste Dateien nach.

### Befund 3 (D-02-03): Anmeldearten externer Speicher, zuverlässig erkannt

Was im Hintergrund passiert [VERIFIED: stable33 `apps/files_external/lib/Config/ConfigAdapter.php` `getAvailableStorages`]: Jede Mount-Konfiguration wird je Nutzer gebaut; wirft `manipulateStorageConfig` (fehlende Anmeldedaten), wird daraus ein `FailedStorage` mit `getId() === 'failedstorage'`, dessen Cache leer ist. In der Weboberfläche angelegte Cache-Zeilen aus einer früheren Sitzung bleiben aber in `oc_filecache` stehen, und der Mount steht in `oc_mounts`. Der Crawl (liest nur `oc_filecache`) würde diese Dateien also finden, und jeder Download scheitert mit `StorageNotAvailableException`. Deshalb **vorab nach Konfiguration klassifizieren, nicht am Fehler**:

| `auth_backend` (Kennung) | Text in der Oberfläche | Im Hintergrund erfassbar? | Prüfung |
|---|---|---|---|
| `password::sessioncredentials` | "Log-in credentials, save in session" | nie | Kennung reicht [VERIFIED: SessionCredentials.php, wirft ohne Sitzung `InsufficientDataForMeaningfulAnswerException`] |
| `smb::kerberosapache` | "Kerberos ticket Apache mode" | nie (Ticket aus der Webanfrage) | Kennung reicht [VERIFIED: KerberosApacheAuth.php:26] |
| `password::logincredentials` | "Log-in credentials, save in database" | erst nach erster Anmeldung des Nutzers | `ICredentialsManager::retrieve(uid, 'password::logincredentials/credentials') !== null` [VERIFIED: LoginCredentials.php `CREDENTIALS_IDENTIFIER`] |
| `password::userprovided` | "User entered, store in database" | nur wenn der Nutzer eingetragen hat | `retrieve(uid, 'password::userprovided/' . mountId)` [VERIFIED: UserProvided.php:24,44] |
| `password::global` | "Global credentials" | Admin-Mount: ja, wenn `retrieve('', 'password::global')`; persönlich: je Nutzer | GlobalAuth.php:65-80 [VERIFIED] |
| `password::global::user` | "Global credentials, user entered" | je Nutzer | `retrieve(uid, 'password::global')` [VERIFIED: UserGlobalAuth.php:24,31] |
| `password::password`, `null::null`, `builtin::builtin`, `publickey::rsa`, `amazons3::accesskey`, `smb::kerberos` | feste Zugangsdaten bzw. keine | ja, Erreichbarkeit separat | `smb::kerberos` braucht ein Ticket im Cron-Prozess [ASSUMED: im Hintergrund meist nicht vorhanden]; über die Verfügbarkeitsprobe unten erkennen |

Weg in PHP: je Speicher-ID aus der Mountmenge mit Provider ConfigAdapter `IUserMountCache::getMountsForStorageId()` → `getMountId()` und `getUser()`; `SELECT mount_id, auth_backend FROM oc_external_mounts WHERE mount_id IN (...)`; Zustand je `(storage_id)` in `avs_storage` (`auth_kind`, `capturable`, `reason` aus geschlossener Liste: `session_credentials`, `credentials_missing`, `unavailable`, `switched_off`), Prüfzeit. Zusätzlich eine **Verfügbarkeitsprobe** pro Speicher und Lauf: Dateisystem des Mount-Nutzers aufsetzen, `$storage->instanceOfStorage(FailedStorage::class)` bzw. `getAvailability()['available']` (ConfigAdapter macht genau das). Das fängt Kerberos, falsche Passwörter und abgeschaltete Server ohne eine einzige Dateioperation. Die Admin-Meldung nennt nur Mount-Konfiguration (Mountpunkt-Bezeichnung der Konfiguration ist Admin-Wissen, aber D-02-03 sagt "keine Dateinamen": empfohlen werden Konfigurations-ID, Backend-Art und Anzahl betroffener Nutzer, kein Pfad) und den Satz "Mit gespeicherten Anmeldedaten (Anmeldedaten, in Datenbank speichern) wird dieser Speicher erfasst". Kein Einreihen für nicht erfassbare Speicher; sobald die Klassifikation wechselt (Nutzer hat sich angemeldet), stößt der SchedulerJob den Crawl dieses Mounts an.

### Befund 4: Gruppenordner als Speicher

Ein Gruppenordner ist **ein** Speicher mit **einer** file_id je Datei für alle Mitglieder [VERIFIED: groupfolders stable33 `lib/Mount/FolderStorageManager.php`]. Zwei Formen: alt als Jail auf dem Wurzelspeicher unter `__groupfolders/<id>` (Speicher `local::<datadir>/` bzw. Objektspeicher der Instanz), neu als eigener Speicher (`Local` mit `datadir = <datadir>/__groupfolders/<id>`, also `local::<datadir>/__groupfolders/<id>/`, Unterordner `files`, `trash`, `versions`; oder Objektspeicher `object::groupfolder:<id>.<store>`). ACLs wirken als `ACLStorageWrapper` je Nutzer, der Cache bleibt gemeinsam. Folgen: (a) Kein Vorfilter nötig, die file_id ist schon eindeutig; (b) `getDistinctMounts` liefert den Ordner einmal je (root_id, storage_id), nicht je Mitglied; (c) der Leser für den Download muss ein Mitglied mit Leserecht sein, und das Gateway muss über `ReaderContext::actAs` laufen (Phase 1 hat das schon, Findling-Befund "groupfolders baut den Mount als in share, wenn jemand anderes aktiv ist"); (d) Papierkorb des Gruppenordners liegt unter `trash`, nicht unter `files`, und fällt durch `onlyUserFilesMounts` heraus, solange der Mountpunkt nicht `/%/files/%` trifft [ASSUMED: Trash-Mount des Gruppenordners hat keinen `/files/`-Mountpunkt; im CI-Job prüfen].

### Befund 5: Fremdänderungen auf externen Speichern sieht Nextcloud im Hintergrund nicht

- `oc_filecache` eines externen Speichers ändert sich nur, wenn jemand scannt: Weboberfläche/WebDAV mit Mount-Option "Änderungen prüfen" (bei jedem direkten Zugriff), `occ files:scan`, `files_external:notify`. Der Kern-Job `OCA\Files\BackgroundJob\ScanFiles` scannt nur Ordner mit `size = -1` (unvollständig), für bis zu 500 Nutzer alle 10 Minuten, er erkennt **keine** geänderten Dateien [VERIFIED: stable33 `apps/files/lib/BackgroundJob/ScanFiles.php`; config.sample.php:2738-2744].
- Ein Abgleich, der nur `oc_filecache` liest (Findling), erkennt Fremdänderungen also nie, solange niemand den Ordner öffnet. Erfolgskriterium 3 verlangt es "spätestens beim periodischen Abgleich".
- **Empfehlung `ExternalRescanJob`:** TimedJob (z. B. stündlich geweckt), fällig je erfassbarem externen Speicher alle 24 h (gleiche Kadenzregel wie der Abgleich), Zeitbudget je Lauf (Vorschlag 300 s), Dateisystem des Mount-Nutzers aufsetzen, `$storage->getScanner()->scan('', IScanner::SCAN_RECURSIVE, IScanner::REUSE_ETAG | IScanner::REUSE_SIZE)`. Der Scanner schreibt geänderte Einträge in den Cache und feuert `CacheEntryUpdatedEvent`/`CacheEntryInsertedEvent`; der `CacheEventListener` reiht Medien daraus ein. Abgebrochene Läufe hinterlassen `size = -1`, die `backgroundScan()` beim nächsten Mal fortsetzt [ASSUMED: Scanner markiert bei Abbruch unvollständig; im CI messen].
- Je Nutzer eingebundene Freigabe: jeder Mitgliedsspeicher hat einen eigenen Cache, ein Scan aktualisiert nur seinen. Kosten wachsen mit der Nutzerzahl. Empfehlung: Mitglieder einer Freigabe-Gruppe nacheinander, zuerst das Mitglied mit den meisten Medienzeilen; geänderte Dateien der anderen Mitglieder kommen beim nächsten Scan, und der Vorfilter macht sie billig. Messung im CI-Job (Laufzeit je 1000 Dateien über Samba lokal).
- `files_no_background_scan` des Admins respektieren (dann nur `occ files:scan`/Ereignisse) und als Zustand anzeigen.
- Lokale externe Speicher (`local::`) und S3 laufen über denselben Job. S3 listet seitenweise, Kosten pro Objekt gering; S3-Standardzeiten `connect_timeout` 5 s, `timeout` 15 s, 5 Wiederholungen [VERIFIED: S3ConnectionTrait.php:56-63].

### Befund 6 (D-02-01/D-02-02): Vorfilter-Schlüssel und Lesebeweis

**Freigabe-Schlüssel (share_key), normalisiert:**

| Speicher | `getId()` (unverkürzt) | share_key | Pfad in der Freigabe |
|---|---|---|---|
| SMB | `smb::<user>@<host>//<share>/<root>` mit root = `/…/` [VERIFIED: SMB.php:114-116,136-141] | `smb::<host>//<share>` | `<root ohne führenden />` + internal path |
| SFTP | `sftp::<user>@<host>[:<port>]/<root>` mit root = `/…` [VERIFIED: SFTP.php:155-165] | `sftp::<host>[:<port>]` | root + internal path |
| S3 extern | `amazon::external::md5(host:bucket:key)` [VERIFIED: AmazonS3.php:51] | `sid:<numeric>` (keine Gruppierung) | internal path |
| lokal extern | `local::<pfad>/` (ohne Nutzer, ein Speicher für alle) | `sid:<numeric>` | internal path |
| WebDAV/Nextcloud/ownCloud | `webdav::<user>@<host>/<root>` | `sid:<numeric>` (Findling: Host und Root nicht trennbar) | internal path |
| Home, Gruppenordner | `home::<uid>`, `local::…`, `object::…` | `sid:<numeric>` | internal path |

- Host ist der Text nach dem **letzten** `@` vor dem ersten `//` (Anmeldename mit eigenem `@` bleibt draußen, Findling countingKey). Unbekanntes Format → `sid:<numeric>`, also keine Gruppierung: korrekt, nur teurer (sha256 je Kopie).
- **Wichtig, neu gegenüber Findling:** `oc_storages.id` wird über 64 Zeichen als md5 gespeichert [VERIFIED: `lib/private/Files/Cache/Storage.php:85-90`]. `smb::verwaltung.mustermann@nas.example.local//Daten//Projekte/` ist schon 62 Zeichen lang; Findling liest den String aus `oc_storages` und gibt bei md5 auf. Deshalb den Schlüssel aus dem **Speicherobjekt** bilden (`$mount->getStorage()->getId()` nach Setup des Mount-Nutzers, das der Crawl ohnehin für die Verfügbarkeitsprobe braucht) und in `avs_storage.share_key` ablegen.
- Root-Normalisierung (Root in den Pfad statt in den Schlüssel) lässt auch zwei Konfigurationen derselben Freigabe mit verschiedenem Unterordner zusammenfallen. Ein Root mit `$user` ergibt je Nutzer einen anderen Pfad, also nie fälschlich gleich.
- **prefilter_key** = `sha256(share_key \0 path_in_share \0 size \0 storage_mtime)` als Hex in PHP berechnet, nur bei gruppierbarem share_key (SMB, SFTP), sonst NULL. Der Container sieht nie einen Pfad, nur den Hash. `mtime`: `ICacheEntry::getStorageMTime()` (Zeit des Servers, für alle Mitglieder gleich), nicht `getMTime()` (kann per `X-OC-Mtime` gesetzt sein) [ASSUMED: storage_mtime ist bei SMB je Mitglied gleich; im CI prüfen].
- **ETag gehört nicht in den Vorfilter über Kopien hinweg:** SMB liefert kein ETag, Nextcloud vergibt es je Cache-Zeile, jede Nutzerkopie hat ein anderes. Das ETag bleibt der Änderungsmerker **je file_id** (D-02-01 "jede Abweichung ... etag ... neuer Hash" gilt für die eigene Vorgeschichte).

**Lesebeweis (Pflicht, sonst Leck A6):**
- Findling-Messung A6 [VERIFIED: Findling `39-DEDUP-ERGEBNIS.md`, `39-04-SUMMARY.md`]: Samba 4.19.5, DENY READ für userb per `smbcacls`; userb sieht die Datei gelistet, `isReadable()` true (Node und SMB-Speicher), mit und ohne `check_acl`; Download hängt ohne Antwort (curl-Timeout 90 s). Unser `FileAccess::readableFile()` prüft genau `isReadable()` (php/lib/Service/FileAccess.php) und fiele darauf herein.
- Ablauf: Kopie mit gleichem prefilter_key wie eine Verweiszeile mit media_id → Container fragt `GET /ocs/v2.php/apps/audio_video_search/files/{fileId}/head?userId=<reader>` (neue Route, ExAppRequired, gleicher Rechteweg wie das Gateway, `fread` max. 65536 Bytes). Container vergleicht `sha256(kopf)` mit `media.head_sha256`. Treffer → `media_id` setzen. 403/404/Timeout/500 → `state='unreadable'`, `reason='read_denied'` bzw. `read_timeout`, nicht zählen, nach ETag-/mtime-Änderung erneut. Kopf passt nicht → wie ohne Geschwister (voller Download).
- Zeitgrenzen: Container `httpx.Timeout(connect=10, read=30)` für den Kopf; PHP selbst kann einen hängenden `smbclient` nicht abbrechen (A6), der PHP-Worker bleibt bis `max_execution_time` belegt [ASSUMED: Verhalten bei php-fpm]. Deshalb Lesebeweise seriell (Parallelität 1) und Sperrkreis je Speicher: nach 3 Zeitüberschreitungen in Folge diesen Speicher 1 h nicht mehr anfragen. Ein Kopf-Fehler sagt nichts über die anderen Nutzer.
- Kosten: eine SMB-Öffnung + 64 KiB je zusätzlicher Kopie statt GB-Downloads; D-02-01 ("nur einmal geladen und gehasht") bleibt für den vollen Inhalt wahr.

### Befund 7: Ausschlüsse, Semantik und Zeitpunkte

- **Ordner:** Findling-Präfixe und Muster relativ zur Mount-Wurzel (`ExclusionService::mountRelativePath`), eine Vergleichsstelle für Ereignis, Crawl, Ausgabe und Diagnose [VERIFIED: Findling ExclusionService.php Kopf]. Übernehmen.
- **Externer Speicher:** Schalter je Mount-Konfiguration (`mount_id`), wirkt auf alle `storage_id` dieser Konfiguration (je Nutzer eine bei SMB mit Nutzeranmeldung).
- **Nutzer** [ASSUMED, Owner bestätigen]: Ausgeschlossen sind Dateien auf Speichern, deren Eigentümer der Nutzer ist: Home, persönliche externe Speicher, je Nutzer gebaute externe Speicher mit seiner Anmeldung (`oc_mounts.user_id` bei Speicher mit genau einem Nutzer). Gruppenordner und gemeinsam eingebundene Speicher bleiben für andere erfasst. Zusätzlich liefert der Provider für ausgeschlossene Nutzer immer leer (D-02-04 "sehen keine Treffer mehr"). Freigaben aus dem Home eines ausgeschlossenen Nutzers an andere werden nicht erfasst (gleiche file_id, Speicher des Ausgeschlossenen).
- **Gruppe** [ASSUMED, Owner bestätigen]: Nutzer-Ausschluss für jedes Mitglied, dynamisch: `UserAddedEvent`/`UserRemovedEvent` lösen Neubewertung aus (Findling GroupEventListener-Muster).
- **Vor dem ersten Durchlauf (D-02-05):** Der Erst-Crawl startet erst, wenn der Handshake mit dem Backend `ok` ist (Phase 1 ExAppService-Zustand), damit der Admin nach Installation der PHP-App Ausschlüsse setzen kann. Ausschluss wird zweimal geprüft: beim Einreihen (Listener, Crawl) und bei der Ausgabe an den Container (`describe()` im QueueController), weil zwischen beiden Minuten liegen. Der Container lädt nur über Gateway und Kopf-Route; beide prüfen die Ausschlussregel ein drittes Mal (billig, schließt das Fenster zwischen Ausgabe und Download).
- **Rückwirkend (D-02-04):** Nutzer/Gruppe/Speicherschalter → Löschauftrag je Speicher-ID (`kind='exclude_storage'`), Container `DELETE FROM file_ref WHERE storage_id IN (...)` über Index. Ordner → `ExclusionClearJob` läuft den Teilbaum in Bändern über `getByAncestorInStorage` und reiht `kind='exclude'` je file_id ein (Findling SubtreeExpandJob, gleiche Scheiben-API, damit kein zweiter "was liegt im Mount"-Weg). Löschaufträge haben Vorrang vor allem anderen (Findling `QueueMapper::KINDS`).
- Ausschluss zurückgenommen → Erst-Crawl der betroffenen Mounts neu anstoßen (Cursor zurück auf 0); dank Vorfilter/sha256 kostet das bei behaltenen Inhalten nichts.

### Befund 8: Verschieben, Umbenennen, Taggen, Kopieren

- Umbenennen/Verschieben im selben Speicher: gleiche file_id (`Cache::moveFromCache`), `NodeRenamedEvent`. Container aktualisiert nur `prefilter_key` (Pfad ändert sich) und behält `media_id`. Kein Download.
- Verschieben über Speichergrenzen (Home → Gruppenordner): `Cache::moveFromCache` über Caches hinweg feuert `CacheEntryRemovedEvent` + `CacheEntryInsertedEvent` mit derselben `sourceId` [VERIFIED: Cache.php:838-841], bei Kopie über Speichergrenzen entsteht eine neue file_id. Beides endet ohne Neuberechnung, weil sha256 gleich ist; es kostet höchstens einen Download.
- Taggen: `SystemTagObjectMapper::updateEtagForTags` schreibt `oc_systemtag.etag`, nicht `oc_filecache.etag` [VERIFIED: stable33 `lib/private/SystemTag/SystemTagObjectMapper.php:164,200,216-221`]. Kein Ereignis, kein Download.
- Kopie (`NodeCopiedEvent`): neue file_id, gleicher Inhalt → voller Download + sha256 → gleiche media_id. Bei Kopien im selben SMB-Speicher ist der Pfad anders, der Vorfilter greift nicht. Akzeptiert (D-02-01 nennt "gleicher Pfad").

### Pattern 1: PHP-Warteschlange nur bis zur Übergabe (Sperrfrist)

**What:** Kinds `delete`, `exclude`, `exclude_storage`, `metadata` (Umbenennen, nur Pfad/Vorfilter), `content` (neu, geändert, Erst-Crawl). Claim mit fester Sperrfrist 900 s (Findling `LOCK_TIMEOUT`). Der Container quittiert nach der `state.db`-Transaktion, nicht nach Download oder Transkription.
**Why:** Eine Sperrfrist, die an der Arbeitsdauer hängt, ist bei Medien nicht beherrschbar (3 h Aufnahme auf ARM, 10 GB Video über SMB). Findling-Fehlerklasse T-03-503: Zeile kommt während korrekter Arbeit frei, zählt Wiederholungen, endet als `failed(repeatedly_stuck)`.
**Folgen:** Laden, Hashen und Transkription haben ihre eigene Stufen-Tabelle im Container (`stage`, `attempts`, `next_try_at`, `last_reason`), Wiederaufnahme nach Neustart aus `state.db`. Phase 3 hängt die Transkriptionsstufen an dieselbe Tabelle.
**Download nie direkt in den Decoder:** Das Gateway hält für die Dauer des Streams eine geteilte Dateisperre; Schreiber (neue Version) warten bzw. bekommen 423. `filelocking.ttl` ist 3600 s [VERIFIED: config.sample.php:2564-2571]. Deshalb immer zuerst vollständig in `$APP_PERSISTENT_STORAGE/tmp/` laden (sha256 im Strom, Findling `fetch_file_stream`), danach liest nur noch der Container. Die Sperre dauert so lang wie der Download, nie so lang wie eine Vorschau.

### Pattern 2: Abgleich mit Crawl-Flag je Mount und Sweep vor dem Tor

- **Sweep** (Findling 1.6.3, `43-RESEARCH.md` Pattern 1): eigener Meta-Stempel `storage_sweep_at`, gleiche Kadenzregel `_cadence_due`, läuft auch, wenn der Walk blockiert ist; Voraussetzungen T-36-13 (Mountliste erreichbar, nicht leer, nichts verworfen); gone/deselected sofort, sonst 30 Tage Frist; Stempel nur bei vollständigem Durchlauf.
- **Walk-Tor:** Statt Findlings `_quiet` (Crawl irgendwo aktiv oder Warteschlange >= quiet_max) **je Mount**: Walk nur über Mounts mit `avs_crawl.finished_at IS NOT NULL`. Die Warteschlangenlänge ist kein Tor mehr, weil die PHP-Warteschlange nach Pattern 1 nur Sekundenarbeit trägt. Eine nicht lesbare Warteschlange (`stats.ok=false`) bleibt Abbruchgrund (Findling D-43-02).
- **Verweise verschwundener Speicher:** `state='vanished'` statt löschen (zählen nicht, D-43-07), nach Frist löschen; kommt der Speicher zurück, reicht ein Zustandswechsel (kein Download).
- **Gelöschter Nutzer:** Home-Speicher verliert seine `oc_storages`-Zeile → `classifyAbsent` sagt gone → Verweise sofort weg [VERIFIED: Findling StorageService.php:422-456, Befund D-43-05]. Zusätzlich `UserDeletedEvent` als Beschleuniger.

### Pattern 3: Verweis-Modell in `state.db` (Schema v2)

```sql
-- Migration v1 -> v2 (schema_version 2). file_ref.storage_id war TEXT und trägt
-- bei Proben '' (api/sample.py:_seed); v2 macht daraus INTEGER, Proben bekommen 0.
CREATE TABLE file_ref (
    file_id        INTEGER PRIMARY KEY,
    media_id       INTEGER REFERENCES media (media_id),
    storage_id     INTEGER NOT NULL,          -- numerische Nextcloud-ID
    prefilter_key  TEXT,                      -- sha256 hex oder NULL (nicht gruppierbar)
    reader_uid     TEXT,                      -- Leser für Gateway und Lesebeweis
    etag           TEXT    NOT NULL,
    size           INTEGER NOT NULL,
    mtime          INTEGER NOT NULL,          -- storage_mtime
    state          TEXT    NOT NULL,          -- active | unreadable | vanished | sample
    stage          TEXT    NOT NULL,          -- pending | probing | fetching | keyed | failed
    reason         TEXT,                      -- geschlossene Liste STATE_REASONS
    attempts       INTEGER NOT NULL DEFAULT 0,
    next_try_at    INTEGER,
    updated_at     INTEGER NOT NULL
);
CREATE INDEX file_ref_media     ON file_ref (media_id);
CREATE INDEX file_ref_storage   ON file_ref (storage_id);
CREATE INDEX file_ref_prefilter ON file_ref (prefilter_key) WHERE prefilter_key IS NOT NULL;
CREATE INDEX file_ref_stage     ON file_ref (stage, next_try_at) WHERE stage <> 'keyed';
ALTER TABLE media ADD COLUMN head_sha256 TEXT;   -- Kopf 64 KiB, für den Lesebeweis
ALTER TABLE media ADD COLUMN orphaned_at INTEGER;-- letzter Verweis weg (Phase 8 nutzt es)
```

- **Rückwirkender Ausschluss billig:** `DELETE FROM file_ref WHERE storage_id IN (json_each(?))` bzw. je file_id-Band, danach in derselben Transaktion `SELECT media_id FROM media m WHERE NOT EXISTS (SELECT 1 FROM file_ref r WHERE r.media_id = m.media_id)` für die berührten media_ids (nicht global) → `forget_media(media_id)`: `word`, `transcript`, `current`, `correction`, `media_key`, `media` löschen, Index-Arbeit über `index_outbox` (Retire). D-02-04: Korrekturen fallen mit dem letzten Verweis.
- **Lösch-Ursachen unterscheiden:** `exclude*` und gone → sofort `forget_media`. `delete` (Papierkorb) → Verweis weg, media bekommt `orphaned_at`, Löschung nach Phase-8-Regel (Papierkorb kann zurückkommen). Bis Phase 8: Waisen zählen nicht, Index-Treffer gibt es nicht (keine lesbare file_id). Owner-Bestätigung: Open Question 3.
- **Zählung (D-02-06), eine Abfrage, gemessen:**

```sql
-- Nenner: Inhalte über aktive Verweise eingebundener Speicher
WITH k AS (
  SELECT COALESCE(r.media_id,
         (SELECT s.media_id FROM file_ref s
           WHERE s.prefilter_key = r.prefilter_key AND s.media_id IS NOT NULL
             AND s.state = 'active' LIMIT 1),
         r.prefilter_key,
         'f' || r.file_id) AS key
  FROM file_ref r WHERE r.state = 'active')
SELECT COUNT(DISTINCT key) AS contents,
       (SELECT COUNT(*) FROM file_ref WHERE state = 'active') AS files
FROM k;
-- Zähler: Inhalte mit Transkript UND mindestens einem aktiven Verweis
SELECT COUNT(*) FROM current c
 WHERE EXISTS (SELECT 1 FROM file_ref r WHERE r.media_id = c.media_id AND r.state = 'active');
```

  Gemessen in dieser Session (uv-Python, SQLite 3.50.4, Laptop): 139.617 Verweise auf 40.000 Inhalte, bis 6 Kopien je Inhalt, Nenner 0,17 s (Ergebnis exakt 40.000), Zähler 0,015 s [VERIFIED: Benchmark-Skript im Scratchpad]. Der Unterausdruck für Geschwister verhindert die Doppelzählung "eine Kopie schon gehasht, die andere noch nicht". Zähler ⊆ Nenner per Konstruktion (jede gezählte media_id hat einen aktiven Verweis, dessen Schlüssel diese media_id ist), also Quote ≤ 100 %.
- **Mountmenge im Nenner:** Verweise verschwundener Speicher stehen auf `vanished`, zählen also nicht; damit braucht die Zählung keine Mountliste von PHP (anders als Findling 1.6.3), solange der Sweep läuft. Gegenprobe im E2E-Test.

### Pattern 4: occ-Vertrag

- `occ audio_video_search:status [--json]`: "X von Y Inhalten transkribiert (N Dateien)", übersprungene Speicher mit Grund (IDs, Backend-Art, Nutzerzahl), Crawl-Fortschritt je Mount (fertig/offen), Warteschlange PHP (offen je kind), Stufen im Container (je stage). Nur Zahlen und IDs.
- `occ audio_video_search:files [--state=...] [--json]`: Liste der file_ids im Arbeitsvorrat mit state/stage/reason und media_id; das ist die Schnittstelle für Erfolgskriterium 1 und den E2E-Vergleich. Keine Pfade (Admin kann `occ info:file <id>` selbst aufrufen).
- Container-Routen `/workstock` und `/coverage` mit `access_level` ADMIN in `backend/appinfo/info.xml` (HaRP gleicht deklarierte Routen ab, Findling `/probe`-Muster); PHP ruft über `ExAppService::adminSend`.

### Anti-Patterns to Avoid
- **Vorfilter ohne Lesebeweis:** Leck A6, siehe Befund 6.
- **Quittieren nach der Transkription:** Sperrfrist unbeherrschbar, Warteschlange dauerhaft voll, Tor verhungert (#25).
- **Freigabe-Schlüssel aus `oc_storages.id`:** über 64 Zeichen md5, Gruppierung fällt still aus.
- **Erfassbarkeit am Fehler erkennen:** FailedStorage erzeugt Downloadfehler je Datei und Wiederholungsschleifen; Klassifikation vorab nach `auth_backend`.
- **Abgleich nur über `oc_filecache` für externe Speicher:** sieht Fremdänderungen nie (Befund 5).
- **Sweep hinter dem Walk oder dem Tor:** Findling #25, 0x `walked` in 24 h.
- **`delete` absorbiert alles bei Speicherwechsel-Verschieben:** Removed + Inserted mit gleicher file_id; das Inserted danach muss als `content` wieder gewinnen. Findlings Regel "delete absorbiert alles" (`refreshExisting`) nicht blind übernehmen, Reihenfolge testen.
- **Download direkt in ffmpeg streamen:** hält die Nextcloud-Dateisperre für die ganze Dekodierzeit.
- **Pfade, Dateinamen, Hosts, Freigabenamen in Logs oder Antworten:** Grep-Test wie Findling `test_the_sweep_logs_counters_and_storage_ids_and_never_a_path`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Mountliste | eigene `oc_mounts`-Abfrage für Home/Gruppenordner | `IFileAccess::getDistinctMounts` | Home-Umbiegen auf `files`, Papierkorb/Versionen draußen, öffentlich |
| Datei-Scheiben | eigene `oc_filecache`-Abfrage | `IFileAccess::getByAncestorInStorage` mit Mimetyp-IDs | E2E-Verschlüsselung, Teilbaum, Cursor schon gelöst |
| Warteschlange mit Claim | neues Sperrmodell | Findling `QueueMapper` (bedingtes Update, Ablauf, dirty) | getestet über 40 Phasen |
| Sweep, gone/deselected | Container-Heuristik | Findling `_sweep_vanished` + `classifyAbsent` in 1.6.3-Form | Löschen nie aus leerer Liste (T-36-13) |
| Teilbaum-Aufräumen | Präfix-Löschung im Container | Findling SubtreeExpandJob über dieselbe Scheiben-API | Container kennt keine Pfade |
| Rescan | eigener SMB-Lister | `IStorage::getScanner()->scan()` | Cache-Konsistenz, Ereignisse, Sperren macht Nextcloud |
| Anmeldedaten prüfen | `oc_credentials` direkt lesen (verschlüsselt) | `ICredentialsManager::retrieve` | entschlüsselt korrekt, öffentlich |
| ID-Listen an SQLite | `IN (?,?,…)` in Bändern | `json_each(?)` | keine Platzhaltergrenze (Findling 1.6.3) |
| Freigabe-Schlüssel | neue Parserregeln | Findling `countingKey` + Root-Normalisierung | Grenzfälle (`@` im Namen, md5-IDs) dokumentiert |

**Key insight:** Jede zweite Antwort auf "welche Dateien gibt es" driftet. Findling hält Ereignis, Crawl, Abgleich und Diagnose auf einer Vergleichsstelle (`providers()`, `isExcluded`, `getFileSlice` auf `getFilesInMount`) und prüft das per Quelltext-Test (`test_exclusion_path_space.py`). Dasselbe hier für Mimetyp-Filter, Ausschluss und Erfassbarkeit.

## Bestehender Laufzeitzustand (Schemawechsel)

| Kategorie | Befund | Aktion |
|----------|--------|--------|
| Stored data (state.db) | `file_ref.storage_id TEXT` mit `''` aus Probe-Saat (`api/sample.py:_seed`), `SCHEMA_VERSION = 1` (`store/repo.py:38`), Schema wird bei jedem Start per `executescript` angewandt und Version hart geprüft (`repo.py:258-263`) | Migration v1 → v2 als Code (Tabelle neu anlegen, Daten kopieren, `''` → 0), Upgrade-Job in `deploy-harp.yml` prüft v2 nach Update; kein harter Abbruch bei v1 mehr |
| Live service config | neue AppConfig-Schlüssel (Ausschlüsse, Speicherschalter), neue Tabellen `avs_queue`, `avs_storage`, `avs_crawl` | PHP-Migration; Uninstall-Schritt räumt sie |
| OS-registered state | keiner (Hintergrundjobs registriert Nextcloud über info.xml `<background-jobs>`) | Jobs in `php/appinfo/info.xml` eintragen |
| Secrets/env vars | keine neuen | , |
| Build artifacts | neue ExApp-Routen `/workstock`, `/coverage` in `backend/appinfo/info.xml` wirken erst nach ExApp-Update | Upgrade-Strecke prüft Routen |

## Common Pitfalls

### Pitfall 1: Rechteleck über den Vorfilter
**What goes wrong:** Nutzer B sieht Transkript einer Datei, die ihm der SMB-Server sperrt. **Why:** Listing und `isReadable()` sagen ja (A6). **How to avoid:** Lesebeweis je Kopie; Negativtest im E2E mit `smbcacls DENY READ`. **Warning signs:** Verweise mit media_id, deren Leser nie einen erfolgreichen Kopf-/Vollabruf hatte.

### Pitfall 2: Session-Speicher als Fehlerlawine
**What goes wrong:** Tausende `gateway_failed` je Datei eines Speichers mit Sitzungsanmeldung. **Why:** Cache-Zeilen aus früheren Sitzungen, im Hintergrund `FailedStorage`. **How to avoid:** Klassifikation vor dem Einreihen, Verfügbarkeitsprobe je Speicher statt je Datei.

### Pitfall 3: Fremdänderung bleibt unsichtbar
**What goes wrong:** Datei auf dem NAS ersetzt, Erfassung merkt es nie. **Why:** Hintergrund-Scan von Nextcloud prüft nur `size=-1`. **How to avoid:** ExternalRescanJob; E2E-Schritt "Datei direkt auf dem Samba-Pfad ersetzen, ohne Nextcloud" mit Erwartung "nach einem Rescan im Arbeitsvorrat mit neuem Hash".

### Pitfall 4: Zähler und Nenner messen verschiedene Mengen (#25)
**What goes wrong:** Quote falsch oder über 100 %. **Why:** Zeilen vs. Dokumente, verschwundene Speicher, Geschwister halb gehasht. **How to avoid:** beide aus derselben Verweismenge, Zähler als Teilmenge definiert (Pattern 3), E2E-Vergleich mit unabhängiger Wahrheit.

### Pitfall 5: Sweep verhungert hinter dem Tor
**How to avoid:** Findling 1.6.3-Form (eigener Stempel, vor dem Walk); Test mit Uhr-Fake über zwei Takte bei blockiertem Walk.

### Pitfall 6: Hängender Download blockiert PHP-Worker
**What goes wrong:** smbclient hängt bei gesperrter Datei (A6), jeder Versuch belegt einen php-fpm-Worker. **How to avoid:** Lesebeweis und Downloads seriell, Sperrkreis je Speicher nach Zeitüberschreitungen, Container-Zeitgrenzen (connect 10 s, read 30 s zwischen Bytes).

### Pitfall 7: files_accesscontrol
**What goes wrong:** Gateway antwortet 500, Datei kreist in Wiederholungen. **Why:** files_accesscontrol hängt seinen Speicher-Wrapper nur in Webanfragen ein (`!OC::$CLI`) [VERIFIED: files_accesscontrol main `lib/AppInfo/Application.php:44-48`]; der Crawl (Cron, CLI) sieht die Datei, das Gateway (OCS-Webanfrage der ExApp) bekommt `OCP\Files\ForbiddenException('Access denied by access control')` [VERIFIED: `lib/Operation.php:118`], wenn eine Regel greift (Gruppe, IP, User-Agent, Uhrzeit, Typ, Tag). Phase-1-Gateway fängt das als `\Throwable` → 500. **How to avoid:** `ForbiddenException` im Gateway und in der Kopf-Route eigens fangen → 403 mit Code `access_control`; Container: `state='unreadable'`, `reason='access_control'`, nächster Versuch beim nächsten Abgleich-Takt (Regeln können zeitabhängig sein), höchstens ein Versuch je Takt; anderen Leser versuchen, wenn vorhanden. Zur Suchzeit wertet files_accesscontrol die Regeln mit der echten Anfrage des Nutzers aus (Provider-Recheck läuft in seiner Webanfrage), dort ist nichts zu tun.

### Pitfall 8: Gesperrte Datei beim Upload
**What goes wrong:** `LockedException` beim Öffnen während eines laufenden Uploads. **How to avoid:** 423-ähnlicher Code `locked` aus dem Gateway, kurzer Rückversuch (Minuten), kein Fehlerurteil (Findling StorageCrawlJob fängt `LockedException`).

### Pitfall 9: Prozesszeit-Grenzen im Hintergrund
**What goes wrong:** Rescan oder Erst-Crawl eines großen Speichers läuft in einen Cron-Abbruch. **How to avoid:** Zeitbudget je Lauf (Rescan 300 s, Crawl-Bänder wie Findling), Fortsetzung über Cursor bzw. `size=-1`; SMB-Zeitgrenze ist Backend-Option `timeout` (Standard der icewind/smb-Bibliothek 20 s) [VERIFIED: icewind1991/SMB `src/Options.php:11`; files_external `Backend/SMB.php:53`].

### Pitfall 10: Zwei Wege zu "was liegt im Mount"
**How to avoid:** Abgleich-Scheiben bauen auf derselben Methode wie der Crawl (Findling `getFileSlice` auf `getFilesInMount`), Quelltext-Test, der eine zweite `getDistinctMounts`- oder `getByAncestorInStorage`-Stelle meldet.

## Code Examples

### Freigabe-Schlüssel mit Root-Normalisierung (PHP, Skizze aus Findling `countingKey`)
```php
// Source: Findling php/lib/Service/StorageService.php:546-578, erweitert um Root im Pfad
/** @return array{0: string, 1: string}|null [share_key, root_prefix] */
public static function shareKey(string $storageId): ?array {
	foreach (['smb::', 'sftp::'] as $prefix) {
		if (!str_starts_with($storageId, $prefix)) {
			continue;
		}
		$rest = substr($storageId, strlen($prefix));
		$split = strpos($rest, '//');
		if ($split === false || $split === 0) {
			return null;
		}
		$at = strrpos(substr($rest, 0, $split), '@');
		$host = $at === false ? '' : substr($rest, $at + 1, $split - $at - 1);
		if ($host === '') {
			return null;
		}
		$tail = substr($rest, $split + 2);            // smb: "<share>/<root>", sftp: "<root>"
		if ($prefix === 'smb::') {
			$slash = strpos($tail, '/');
			$share = $slash === false ? $tail : substr($tail, 0, $slash);
			$root = $slash === false ? '' : substr($tail, $slash);
			return ['smb::' . $host . '//' . $share, trim($root, '/')];
		}
		return ['sftp::' . $host, trim($tail, '/')];
	}
	return null;
}
```

### Erfassbarkeit nach Anmeldeart (PHP, Skizze)
```php
// Source: Kennungen aus nextcloud/server stable33 apps/files_external/lib/Lib/Auth/**
private const NEVER = ['password::sessioncredentials', 'smb::kerberosapache'];

private function credentialsPresent(string $auth, string $uid, int $mountId, bool $adminMount): ?bool {
	return match ($auth) {
		'password::logincredentials' => $this->credentials->retrieve($uid, 'password::logincredentials/credentials') !== null,
		'password::userprovided' => $this->credentials->retrieve($uid, 'password::userprovided/' . $mountId) !== null,
		'password::global' => $this->credentials->retrieve($adminMount ? '' : $uid, 'password::global') !== null,
		'password::global::user' => $this->credentials->retrieve($uid, 'password::global') !== null,
		default => null, // feste Zugangsdaten: Verfügbarkeitsprobe entscheidet
	};
}
```

### Kadenzregel für Sweep und Walk (Python, aus Findling 1.6.3)
```python
# Source: Findling 43-RESEARCH.md, Code Examples (aus reconcile.py:1026-1033)
def _cadence_due(self, last_at: int | None) -> bool:
    if last_at is None:
        return True
    elapsed = self._clock() - last_at
    interval = self._min_interval * 3600.0
    if elapsed < interval:
        return False
    if self._hour_of() == self._hour:
        return True
    return elapsed >= 2 * interval
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mount-Crawl über eigene `oc_mounts`/`oc_filecache`-Abfragen | `IFileAccess::getDistinctMounts`/`getByAncestorInStorage` | NC 32 | öffentlich, Findling nutzt es |
| Sweep hinter vollem Walk | Sweep mit eigenem Stempel vor dem Tor | Findling 1.6.3 (Nov. 2026) | gone-Speicher gehen sofort |
| Zählung je Zeile, gruppierter Nenner | Zählung je Dokument/Inhalt über dieselbe Menge | Findling 1.6.3 | Quote nie über 100 % |
| Weg A (eine Lesung je Freigabe) | verworfen nach A6; hier: Vorfilter + Lesebeweis | Findling D-39-01 (28.10.2026) | Rechte bleiben je Nutzer belegt |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Nutzer-Ausschluss = Speicher, deren Eigentümer der Nutzer ist, plus leere Treffer; Gruppen-Ausschluss = Nutzer-Ausschluss je Mitglied | Befund 7 | falsche Semantik; Owner muss bestätigen (Open Question 2) |
| A2 | `storage_mtime` ist für alle Mitglieder einer SMB-Freigabe gleich | Befund 6 | Vorfilter greift nie, nur Kosten (voller Hash je Kopie), keine Falschaussage |
| A3 | Abgebrochener Scanner-Lauf hinterlässt `size=-1`, `backgroundScan()` setzt fort | Befund 5 | Rescan beginnt jedes Mal von vorn; Zeitbudget pro Mitglied nötig |
| A4 | Gruppenordner-Papierkorb hat keinen `/files/`-Mountpunkt | Befund 4 | Papierkorbdateien im Arbeitsvorrat; E2E zeigt es |
| A5 | Hängender smbclient belegt einen php-fpm-Worker bis `max_execution_time` | Befund 6, Pitfall 6 | Worker-Erschöpfung bei vielen gesperrten Dateien; Sperrkreis mildert |
| A6 | `smb::kerberos` hat im Cron-Prozess meist kein Ticket | Befund 3 | Verfügbarkeitsprobe fängt es ohnehin |
| A7 | Cache-Ereignisse feuern nicht für die Ordner-Größen-/ETag-Fortpflanzung (Propagator schreibt direkt) | Standard Stack | Listener-Last; Listener muss vor jeder Abfrage per Endung/Mimetyp verwerfen |
| A8 | Ein 64-KiB-Kopf reicht als Lesebeweis, weil SMB-Leserechte für die ganze Datei gelten | Befund 6 | theoretische Teilrechte gibt es bei SMB nicht [ASSUMED]; mit DENY READ im CI belegen |

## Open Questions

1. **(RESOLVED: D-02-01a, D-02-10, D-02-12) D-02-01 mit Lesebeweis:**
   - What we know: D-02-01 wörtlich ist Findlings Weg A; A6 zeigt das Leck auf echtem Samba, auch mit `check_acl`; Findling-Owner hat Weg A deshalb am 28.10. abgelehnt.
   - Recommendation: Vorfilter behalten, je Kopie 64-KiB-Lesebeweis über eigene file_id und Leser plus Kopf-Hash-Vergleich, erst dann anhängen. Voller Download bleibt einmalig. Alternative: jede Kopie voll laden (sicher, n-fache Kosten).
2. **(RESOLVED: D-02-08, D-02-11) Semantik Nutzer- und Gruppenausschluss:** Empfehlung A1. Alternative "Gruppe = Gruppenordner dieser Gruppe" wäre eine eigene Regel.
3. **(RESOLVED: D-02-09, D-02-13) Löschen in den Papierkorb vs. Ausschluss:** Empfehlung: Ausschluss und gone löschen sofort (D-02-04), Papierkorb setzt nur `orphaned_at`, endgültig in Phase 8. Owner bestätigt, dass D-02-04 nur für Ausschlüsse gilt.
4. **(RESOLVED: D-02-06, Anzeige per occ in Phase 2, Oberfläche Phase 9) Anzeige in Phase 2 oder 9:** Empfehlung: Phase 2 liefert die Zahl und die Liste übersprungener Speicher per occ, die Admin-Seite in Phase 9 (eigener UI-Vertrag, Dreisprachigkeit, Playwright). Falls der Owner "Admin sieht" als Oberfläche liest: eine Zeile in der vorhandenen Admin-Sektion, dann `/gsd:ui-phase 2` vor dem Plan.
5. **(RESOLVED: Startwerte 24 h je Speicher und 300 s je Lauf, Messung im CI-Abnahmelauf, per occ erzwingbar) Rescan-Kadenz und Budget:** 24 h je Speicher, 300 s je Lauf als Startwert; im E2E messen und nach Messung festlegen.
6. **(RESOLVED: Erst-Crawl startet erst nach Backend-Handshake ok, D-02-05) Crawl-Start erst nach Handshake ok:** Empfehlung ja (Fenster für Ausschlüsse vor dem ersten Durchlauf). Dokumentieren, dass Ausschlüsse vor Installation des Backends gesetzt werden können.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv / Python 3.13 | Backend-Tests, Gates | ✓ | uv 0.11.7 | , |
| SQLite (uv-Python) mit `json_each` | Zählung, Migration | ✓ | 3.50.4 | , |
| gh CLI | Quelltext-Recherche, CI | ✓ | vorhanden | , |
| ffmpeg | Testmedien | ✓ (anders als Phase 1 notiert) | 8.1.1 full build (winget, Gyan) | CI `make-testmedia.sh` |
| Docker | lokale Instanz | Client 29.5.2, Daemon nicht geprüft/gestartet | , | CI (`deploy-harp.yml`); lokal nicht starten (RAM ca. 6 GB frei) |
| PHP / Composer | phpunit | ✗ | , | CI `php.yml` |
| Samba, smbclient | D-02-07 | ✗ lokal | , | Ubuntu-Runner `apt-get install samba smbclient` (Findling-Muster) |
| Nextcloud-Testinstanz | Integration | ✗ lokal | , | CI, 33/34/35 x amd64/arm64 |

**Missing dependencies with no fallback:** keine.
**Missing dependencies with fallback:** PHP, Samba, Nextcloud lokal: über CI.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 (Backend), phpunit 11.5 (PHP, nur CI), Bash + Samba + sqlite3 im CI-Job |
| Config file | `backend/pyproject.toml`, `php/phpunit.xml` |
| Quick run command | `cd backend && uv run pytest tests/test_store_schema.py tests/test_capture.py -x` |
| Full suite command | `cd backend && uv run pytest -x` (seriell), PHP über `php.yml`, E2E über neuen Job `discovery-e2e` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DISC-01 | alle Medien aller Nutzer + Gruppenordner im Vorrat | E2E | CI `discovery-e2e`, Schritt "Vorrat gleich Wahrheit" | ❌ Wave 0 |
| DISC-01 | Mimetyp-Filter audio/video, kein Papierkorb/Versionen | PHP-Unit + E2E | `php.yml` StorageServiceTest | ❌ Wave 0 |
| DISC-02 | SMB/SFTP/lokal erfasst, Schalter schließt aus, Session-Speicher übersprungen mit Grund | E2E + PHP-Unit | `discovery-e2e`; `StorageCapturabilityTest` | ❌ Wave 0 |
| DISC-03 | Ausschluss vor erstem Durchlauf: nie im Vorrat, nie geladen | E2E | Zugriffslog des Webservers ohne Gateway-Zeile für ausgeschlossene IDs | ❌ Wave 0 |
| DISC-03 | Ausschluss nachträglich: Verweise weg, letzter Verweis löscht Transkript/Korrektur/Index | Unit + E2E | `uv run pytest tests/test_exclusion_forget.py -x` | ❌ Wave 0 |
| DISC-04 | Upload in Minuten im Vorrat; Fremdänderung nach Rescan | E2E | Zeitmessung Upload → `occ …:files`; Datei direkt auf Samba-Pfad ersetzen | ❌ Wave 0 |
| DISC-04 | Sweep läuft bei blockiertem Walk genau einmal je Takt | Unit | `uv run pytest tests/test_reconcile_sweep.py -x` | ❌ Wave 0 |
| DISC-05 | Kopie/Freigabe je Nutzer: ein Inhalt, mehrere Dateien; Lesebeweis verweigert Anhängen bei DENY READ | Unit + E2E | `uv run pytest tests/test_capture.py -x`; E2E mit `smbcacls` | ❌ Wave 0 |
| DISC-05 | Zählung: Zähler ⊆ Nenner, Geschwister nicht doppelt | Unit (Eigenschaftstest) | `uv run pytest tests/test_coverage_count.py -x` | ❌ Wave 0 |
| DISC-06 | Verschieben/Umbenennen/Taggen: kein Download, keine neue media | E2E + Unit | Download-Zähler im `/status` unverändert, Zugriffslog ohne neue Gateway-Zeile | ❌ Wave 0 |

### D-02-07: Abnahme-Topologie und unabhängige Wahrheit

**Topologie (ein CI-Bein Pflicht je Push auf den Phasenzweig, alle 6 Beine vor der Verifikation):**
- Samba auf dem Runner (Findling `smb_acl_measure.sh`), Freigabe `Medien` mit `acl_xattr`, Unix-Nutzer `ana`, `ben`, `cem` mit Samba-Konten; Unterordner `nur-ana/` per Unix-Rechten nur für ana betretbar (unterschiedliche Sicht, kein Mitglied umfasst alle), eine Datei mit `smbcacls DENY READ` für ben (A6-Fall), eine Datei doppelt (gleicher Inhalt) unter zwei Pfaden.
- Eine Mount-Konfiguration "Log-in credentials, save in database" für alle drei (Anmeldung je Nutzer einmal per WebDAV, damit Zugangsdaten gespeichert sind), eine zweite Konfiguration mit `password::sessioncredentials` (muss als übersprungen erscheinen), eine mit Unterordner-Root derselben Freigabe (Root-Normalisierung).
- Gruppenordner `Team` (vorhanden in `ci/seed.sh`) mit Medien, ACL `+read -share` für ein Mitglied.
- Homes mit Medien; Kopie (WebDAV COPY), Verschieben, Umbenennen (MOVE), Taggen (DAV `systemtags-relations`), Verschieben Home → Gruppenordner.
- Verschwundener Speicher: `occ files_external:applicable --remove-user cem` (vanished, zählt nicht); gelöschter Nutzer `occ user:delete` mit Medien im Home (gone, sofort weg).
- Ausschluss vor dem ersten Durchlauf: Ordnerpräfix und Nutzer per `occ config:app:set` setzen, **bevor** die ExApp registriert wird; Ausschluss nach dem ersten Durchlauf: zweiter Präfix, danach Probe-Transkript (`occ …:sample`) auf einem Inhalt, der nur dort liegt, und auf einem, der auch außerhalb liegt (D-02-04: einer verschwindet, einer bleibt mit Korrektur).
- Fremdänderung: eine Datei direkt im Samba-Verzeichnis ersetzen (ohne Nextcloud), dann Rescan auslösen (Takt kurz gesetzt).

**Unabhängige Wahrheit (andere Sprache, anderer Datenweg, Regel "Gegenprobe nie mit dem Muster der Umsetzung"):**
- Dateien je Nutzer aus dem Dateisystem: `sudo -u <nutzer> find <samba-pfad> -type f` (Unix-Sicht), Homes `find <datadir>/<uid>/files -type f`, Gruppenordner `find <datadir>/__groupfolders/<id>[/files] -type f`; Medien per Endungsliste in Bash, Ausschlüsse per `grep -v` der Präfixe.
- Erwartete Dateizahl N = Summe der Sichten (eine Datei je Nutzer und SMB-Mount, eine je Gruppenordnerdatei, eine je Homedatei) ohne Ausgeschlossene, ohne Session-Mount, ohne vanished/gone.
- Erwartete Inhaltszahl Y = `sha256sum` über alle von mindestens einem erfassten Leser lesbaren Dateien (`sudo -u … cat | sha256sum`), `sort -u | wc -l`. Die DENY-Datei zählt für ben nicht als lesbar.
- Vergleich: `occ audio_video_search:status --json` (Y, N) und `occ …:files --json` (Menge der file_ids) gegen die Wahrheit; die file_ids der Wahrheit kommen über `sqlite3 data/owncloud.db` aus `oc_filecache` (storage, path) gegen die `find`-Pfade, also ohne App-Code.
- "Nie geladen" (D-02-05) und "keine Neuberechnung" (DISC-06): Zugriffslog des Webservers im CI (Zeilen `GET /ocs/v2.php/apps/audio_video_search/files/<id>` und `/head`), nicht ein App-Zähler. Ausgeschlossene IDs dürfen nie auftauchen, Umbenennen/Taggen erzeugt keine neue Zeile. Für Samba zusätzlich `vfs_full_audit` (open je Nutzer) als zweite Wahrheit für die SMB-Dateien.
- Lesebeweis: Datei mit DENY READ für ben muss in `occ …:files` für bens file_id `unreadable/read_denied` (oder `read_timeout`) zeigen, und eine Suche als ben nach dem Probe-Wort dieses Inhalts liefert keinen Treffer (OCS-Suche wie `deploy-harp.yml:291-316`).
- **Positivkontrolle:** derselbe Vergleich gegen eine absichtlich um 1 verschobene Erwartung muss rot werden (Skript-Selbsttest im Job), UND ein Kontrolllauf ohne Lesebeweis muss den DENY-Fall als Treffer zeigen (belegt, dass der Test das Leck sieht). [ÜBERHOLT durch D-02-10: keine Debug-Variable im Produkt; der Kontrolllauf nutzt ein CI-only-Image, gebaut aus einer Kopie mit dem Patch `ci/leak-control/read-proof-off.patch`.] Zusätzlich die Positivkontrolle am Samba-Server aus Findling (ana liest, ben bekommt `NT_STATUS_ACCESS_DENIED`); ohne sie ist der Lauf ungültig.

### Sampling Rate
- **Per task commit:** betroffene pytest-Datei; PHP über CI-Lauf des Zweigs.
- **Per wave merge:** volle Backend-Suite seriell (RAM), ruff/pyright/vulture, `php.yml`.
- **Phase gate:** `discovery-e2e` auf allen 6 Beinen grün inkl. beider Positivkontrollen, `deploy-harp.yml` + Upgrade-Job grün (Schema v2).

### Wave 0 Gaps
- [ ] `backend/tests/test_store_migration_v2.py`: v1 mit Probe-Zeile → v2, `''` → 0
- [ ] `backend/tests/test_capture.py`: Lesebeweis ok/verweigert/Timeout/Kopf passt nicht, Geschwister warten, Anhängen in einer Transaktion
- [ ] `backend/tests/test_coverage_count.py`: Eigenschaftstest Zähler ⊆ Nenner, halb gehashte Geschwister, vanished zählt nicht
- [ ] `backend/tests/test_exclusion_forget.py`: letzter Verweis löscht Wörter, Transkript, Korrektur, Index-Outbox; nicht letzter Verweis lässt alles
- [ ] `backend/tests/test_reconcile_sweep.py`: Sweep bei blockiertem Walk, Stempel nur bei Erfolg (Findling-Fakes)
- [ ] `php/tests/Unit/StorageServiceTest.php`: shareKey (smb, sftp, `@` im Namen, md5-ID, Root-Normalisierung), Erfassbarkeit je `auth_backend`
- [ ] `php/tests/Unit/ExclusionServiceTest.php`, `QueueServiceTest.php` (doppelte Prüfung bei Ausgabe)
- [ ] `.github/workflows/discovery-e2e.yml` + `ci/discovery/*.sh` (Samba, Topologie, Wahrheit, Positivkontrollen)
- [ ] Quelltext-Gate in `backend/tests/test_php_gates.py`: eine Stelle für Mountliste, Scheiben, Mimetyp-IDs, Ausschluss; keine Pfade in Logzeilen

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein (AppAPI-Signatur unverändert) | , |
| V3 Session Management | nein | , |
| V4 Access Control | ja | Gateway und Kopf-Route nur für `EX-APP-ID` des Backends (Phase-1-Muster `rejectForeignCaller`), Rechte über `ReaderContext::actAs` + `FileAccess`; Lesebeweis vor jedem Anhängen; Provider leer für ausgeschlossene Nutzer; Queue-Routen `ExAppRequired` |
| V5 Input Validation | ja | pydantic-Modelle mit Grenzen für Claim-Antworten und Admin-Routen (422 vor Abfrage); PHP-Listen-Validierung wie Findling `QueueController::intList`; `json_each` mit gebundenen Parametern |
| V6 Cryptography | nein (sha256 nur als Schlüssel, `hashlib`/`hash('sha256')`) | , |
| V7 Logging | ja | nur Zähler und IDs; Grep-Test |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Transkript über Vorfilter an Nutzer ohne Leserecht | Information Disclosure | Lesebeweis je Kopie, E2E mit DENY READ und Positivkontrolle |
| Ausgeschlossene Datei wird trotzdem geladen (Fenster zwischen Regel und Download) | Information Disclosure | Prüfung bei Einreihen, Ausgabe und im Gateway |
| Pfade, Freigabenamen, Hosts in Log/occ/Status | Information Disclosure | nur IDs, Backend-Art, Zähler; Grep-Test |
| Fremde ExApp liest über Kopf-Route | Elevation of Privilege | `EX-APP-ID`-Vergleich wie Gateway |
| Löschen aus leerer/gestörter Mountliste | Tampering | T-36-13-Bedingung, gone nur per `classifyAbsent` |
| Hängende SMB-Downloads erschöpfen PHP-Worker | Denial of Service | Seriell, Sperrkreis je Speicher, Container-Zeitgrenzen |
| Riesige Claim-/Admin-Listen | Denial of Service | Obergrenzen, Bänder (Findling REQUEUE_BAND 200, Controller-Limit 256) |

## Sources

### Primary (HIGH confidence)
- nextcloud/server stable33 (gh api, 07.11.2026): `apps/files_external/lib/Config/ConfigAdapter.php`; `Lib/Auth/Password/{SessionCredentials,LoginCredentials,UserProvided,GlobalAuth,UserGlobalAuth}.php`; `Lib/Auth/SMB/{KerberosApacheAuth,KerberosAuth}.php`; `Lib/SessionStorageWrapper.php`; `Lib/Storage/{SMB,SFTP,AmazonS3}.php`; `Lib/Backend/SMB.php`; `Service/DBConfigService.php`; `lib/private/Files/Storage/FailedStorage.php`; `lib/private/Files/Cache/{FileAccess,Cache,Storage}.php`; `lib/private/Files/Config/UserMountCache.php`; `lib/private/Files/ObjectStore/S3ConnectionTrait.php`; `lib/private/SystemTag/SystemTagObjectMapper.php`; `lib/public/Files/Cache/{IFileAccess,IScanner}.php`; `lib/public/Files/Storage/IStorage.php`; `lib/public/Files/Config/IUserMountCache.php`; `apps/files/lib/BackgroundJob/ScanFiles.php`; `config/config.sample.php`; `resources/config/mimetypemapping.dist.json`
- nextcloud/groupfolders stable33: `lib/Mount/FolderStorageManager.php`, `GroupFolderStorage.php`
- nextcloud/files_accesscontrol main: `lib/Operation.php`, `lib/AppInfo/Application.php`
- icewind1991/SMB: `src/Options.php`
- Findling (C:/Users/Student/nextcloud-search, main): `php/lib/Service/StorageService.php`, `ExclusionService.php`, `php/lib/Db/QueueMapper.php`, `php/lib/Controller/QueueController.php`, `php/lib/AppInfo/Application.php`, `php/lib/Listener/GroupEventListener.php`, `backend/src/findling/worker/reconcile.py`, `.github/workflows/smb-acl-measure.yml`, `.planning/phases/43-*/43-CONTEXT.md`, `43-RESEARCH.md`, `.planning/phases/39-*/39-DEDUP-ERGEBNIS.md`, `39-04-SUMMARY.md`
- GitHub street1983nk/nextcloud-search Issue #25 mit allen Kommentaren
- Dieses Repo: `backend/src/audio_video_search_backend/store/schema.sql`, `store/repo.py`, `api/sample.py`, `nc.py`, `php/lib/Controller/GatewayController.php`, `php/lib/Service/FileAccess.php`, `.github/workflows/deploy-harp.yml`, `ci/seed.sh`, Phase-1-RESEARCH Entscheid 3, 01-VERIFICATION
- Benchmark Zählabfrage in dieser Session (Scratchpad `bench/count.py`)

### Secondary (MEDIUM confidence)
- Websuche zu ETag bei Systemtags (keine eindeutige Quelle, durch Quelltext ersetzt): [nextcloud/server#8477](https://github.com/nextcloud/server/issues/8477), [nextcloud/server#60657](https://github.com/nextcloud/server/pull/60657)

### Tertiary (LOW confidence)
- Annahmen A2 bis A8 (siehe Log), alle im E2E-Job prüfbar

## Metadata

**Confidence breakdown:**
- Nextcloud-Kern (Anmeldearten, FailedStorage, Mount-/Datei-APIs, Gruppenordner, Tags, files_accesscontrol): HIGH, am Quelltext stable33 gelesen
- Findling-Übernahme und A6-Befund: HIGH, Code und Messprotokoll
- Lesebeweis als Ausweg: MEDIUM, logisch belegt, im E2E zu beweisen
- Rescan externer Speicher (Kosten, Fortsetzung): MEDIUM, Messung offen
- Ausschluss-Semantik Nutzer/Gruppe: MEDIUM bis LOW, Owner-Entscheid

**Research date:** 2026-11-07
**Valid until:** 2026-12-07 (Nextcloud stable33 bis 35 stabil; bei Findling-Änderungen an reconcile.py/StorageService.php neu prüfen)
