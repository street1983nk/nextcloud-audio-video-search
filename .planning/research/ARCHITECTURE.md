# Architecture Research

**Domain:** Nextcloud-ExApp für lokale Transkription von Audio und Video mit mehrstufiger Pipeline (Vorschau, Veredelung, ROVER) und Suche über Unified Search
**Researched:** 2026-11-06
**Confidence:** HIGH für die Nextcloud-Integrationsgrenzen (im AppAPI-Quellbaum der Zweige stable30 bis stable35 und in nc_py_api 0.30.3 nachgesehen) und für die Pipeline-Semantik (aus SPIKE3-REPORT.md Abschnitt 7, 8, 11 und `combine.py`/`bench3.py` gelesen). MEDIUM für Scheduler, Speicherwächter und Wiederanlauf (übertragen aus Findling, für lange Mediendateien nicht gemessen). LOW für Sprung an die Zeitstelle im Nextcloud-Viewer und für die Kosten der Sprachwechsel-Erkennung je Fenster (beide unten als VERIFIZIEREN markiert).

---

## Die fünf Befunde, die die Struktur festlegen

**1. Eine reine ExApp kann in NC 33 bis 35 keinen Unified-Search-Provider registrieren. Es braucht eine PHP-Companion-App, genau wie bei Findling.** Geprüft im AppAPI-Quellbaum: Auf `main`, `stable33`, `stable34` und `stable35` gibt es keinen einzigen Pfad mit "Search" (`lib/Db/` kennt nur Console, TaskProcessing, TalkBot und UI: FilesActionsMenu, TopMenu, Script, Style, InitialState, SettingsForm). nc_py_api 0.30.3 hat unter `ex_app/ui/` nur `files_actions`, `resources`, `settings`, `top_menu`; kein Such-API. Die Nextcloud-Doku beschreibt Suchprovider ausschließlich als PHP-Klassen, die über `IRegistrationContext::registerSearchProvider` im Bootstrap registriert werden. Findling macht genau das (`php/lib/AppInfo/Application.php:55`, `Provider implements IFilteringProvider`, bewusst nicht `IExternalProvider`, weil der in der Such-UI ab Werk aus ist und Null-Konfiguration bricht). [HIGH]

**2. Auch für Dateiereignisse gibt es keinen brauchbaren reinen ExApp-Weg mehr.** Der AppAPI-Events-Listener (`EventsListenerController`, `ExAppEventsListener`) existiert in `stable30` und `stable31` und ist ab `stable32` entfernt. Ersatz ist `webhook_listeners`: muss vom Admin aktiviert werden, feuert über Hintergrundjobs ("by default every 5 minutes", schneller nur mit `occ background-job:worker`), kennt Node-Ereignisse, aber keine Freigabe- oder Gruppenereignisse. Findling hat sich aus denselben Gründen für synchrone PHP-Listener entschieden (`FileEventListener.php`, Klassenkommentar). Die Companion-App aus Befund 1 löst das mit. [HIGH]

**3. Daraus folgt eine Zwei-App-Architektur und eine App-ID-Entscheidung, die vor allem anderen fallen muss.** Findling heißt `findling` (PHP) plus `findling_backend` (ExApp). Das vorhandene Zertifikat (PR #1410) gilt für `audio_video_search`, und das Skeleton benutzt diese ID heute für die ExApp. Empfehlung: Findling-Muster spiegeln, also `audio_video_search` wird die PHP-App (Store-Eintrag, Suchprovider, Admin-Seite) und die ExApp zieht auf eine neue ID, z. B. `audio_video_search_backend`, für die ein zweites Zertifikat beantragt werden muss. Das ist ein Owner-Tor mit Vorlaufzeit (Zertifikats-PR) und gehört in Phase 1. [HIGH für die Notwendigkeit, Benennung ist Owner-Entscheid]

**4. "Klick öffnet Datei an der Zeitstelle" hat in Nextcloud kein fertiges Mittel.** Der Viewer kennt keinen Zeit-Parameter (Feature-Wunsch nextcloud/viewer#2176, offen; `OCA.Viewer.open()` ohne Startzeit), und AppAPI-Skripte einer ExApp landen im Files-App nur als Dateiaktionen (`LoadFilesPluginListener.php` lädt nur `ex_files_actions_menu`). Robusteste Lösung: eine kleine Abspiel-Route der PHP-App (`/apps/audio_video_search/play/{fileId}#t=123.4`), die ein HTML5-`<video>`/`<audio>` mit WebDAV-Quelle rendert; Media-Fragmente `#t=` kann jeder Browser, Nextcloud beantwortet Range-Anfragen für das Spulen. Das ist keine "eigene App-Seite mit Medienübersicht" (Out of Scope v1), sondern ein Sprungziel. Owner-Entscheid nötig. [MEDIUM, VERIFIZIEREN am Harness: Range-Seek über WebDAV mit Sitzungs-Cookie]

**5. Die Pipeline ist kein Fließband, sondern eine Folge veröffentlichter Transkript-Stufen je Inhalt.** Spike 3 Abschnitt 11 legt fest: Parakeet mit Schluck-Wächter liefert immer zuerst, alles danach ersetzt. Architektonisch heißt das: Jede Datei hat ein *erreichtes Niveau* (Vorschau, selektiv, turbo+ROVER, large-v3+ROVER) und ein *Zielniveau* aus dem effektiven Profil. Die Nacharbeit ist keine zweite Warteschlange, sondern eine Abfrage `erreicht < Ziel`. Ein Profilwechsel durch den Admin plant damit ohne Migration neu, und ein Neustart verliert nichts. [Entwurfsentscheidung, abgeleitet aus Findling `store/repo.py` "There is no pending state and no work queue"]

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Nextcloud-Prozess: PHP-Companion `audio_video_search`                     │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────┐ ┌───────────────┐ ┌──────────────┐ ┌───────────────┐  │
│  │ Listener      │ │ Crawl-Jobs    │ │ Search       │ │ Player- und   │  │
│  │ File/Share/   │ │ je Mount      │ │ Provider +   │ │ Export-Route  │  │
│  │ Group         │ │ (Home, Team-  │ │ SearchService│ │ (#t=, SRT/VTT)│  │
│  │               │ │ folder, Extern│ │ (Recheck)    │ │               │  │
│  └──────┬────────┘ └──────┬────────┘ └──────┬───────┘ └──────┬────────┘  │
│         └────────┬────────┘                 │                │           │
│           ┌──────▼──────────┐  ┌────────────▼────────────────▼────────┐  │
│           │ Arbeitsvorrat   │  │ ExAppService (einziger Draht in den  │  │
│           │ (DB-Tabelle,    │  │ Container, Timeout, Lockstep-Prüfung)│  │
│           │ Queue/Gateway-  │  └────────────┬─────────────────────────┘  │
│           │ Controller)     │               │                            │
│           └──────▲──────────┘               │                            │
├──────────────────┼──────────────────────────┼────────────────────────────┤
│ AppAPI/HaRP (signierte Anfragen in beide Richtungen)                      │
├──────────────────┼──────────────────────────┼────────────────────────────┤
│ ExApp-Container `audio_video_search_backend` (Python, FastAPI)           │
│  ┌───────────────┴───────┐   ┌──────────────▼─────────────────────────┐  │
│  │ Discovery-Client      │   │ API: /search /snippets /export /status │  │
│  │ claim/ack, Reconcile, │   │      /transcript (für Findling später) │  │
│  │ Download + sha256     │   └──────────────┬─────────────────────────┘  │
│  └───────────┬───────────┘                  │ liest                      │
│  ┌───────────▼─────────────────────────┐    │                            │
│  │ Scheduler (Prioritäten, Leerlauf,   │    │                            │
│  │ Vorkaufsrecht an Stückgrenzen)      │    │                            │
│  └───────────┬─────────────┬───────────┘    │                            │
│  ┌───────────▼──────┐ ┌────▼────────────┐   │                            │
│  │ Pipeline-Planer  │ │ Hardware, RAM-  │   │                            │
│  │ (Profil → Stufen)│ │ Wächter, Profil │   │                            │
│  └───────────┬──────┘ └────┬────────────┘   │                            │
│  ┌───────────▼─────────────▼────────────┐   │                            │
│  │ Engine-Host-Kindprozesse (je Modell) │   │                            │
│  │ ffmpeg │ Silero+Parakeet │ turbo │ l3│   │                            │
│  └───────────┬──────────────────────────┘   │                            │
├──────────────┼──────────────────────────────┼────────────────────────────┤
│ Persistentes Volume (APP_PERSISTENT_STORAGE)│                            │
│  ┌───────────▼────────┐ ┌───────────────────▼──┐ ┌──────────────────┐    │
│  │ work/<hash>/       │ │ state.db (SQLite WAL)│ │ models/ (sha256- │    │
│  │ audio.flac, chunks │ │ Dateien, Inhalte,    │ │ gepinnt, .part-  │    │
│  │ (bis Ziel erreicht)│ │ Fenster, Versionen,  │ │ Download)        │    │
│  │                    │ │ FTS5, ACL-Vorfilter  │ │                  │    │
│  └────────────────────┘ └──────────────────────┘ └──────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Komponente | Seite | Verantwortung (besitzt) | Übernahme aus Findling |
|---|---|---|---|
| **FileEventListener** | PHP | Node-Ereignisse (Created, Written, Touched, Copied, Renamed, Deleted, MoveToTrash, Restored) zu Zeilen im Arbeitsvorrat; Mimetype-Filter `audio/*`, `video/*` | `php/lib/Listener/FileEventListener.php`, ein Listener für alle Node-Ereignisse |
| **ShareEventListener / GroupEventListener** | PHP | Rechteänderung als billige `acl`-Zeile; Ordnerfreigabe als Teilbaum-Job in Bändern | `ShareEventListener.php`, `GroupEventListener.php`, `SubtreeExpandJob.php` |
| **SchedulerJob / StorageCrawlJob** | PHP | Erstlauf und Nachlauf über alle Mounts in Scheiben (Home, Teamordner über `OCA\GroupFolders\Mount\MountProvider`, externe Speicher über `OCA\Files_External\Config\ConfigAdapter` nur bei Admin-Schalter); Zählerbasis für "Abdeckung" | `SchedulerJob.php`, `StorageCrawlJob.php` (BATCH_SIZE 2000), `StorageService.php` |
| **Arbeitsvorrat (Queue-Tabelle + QueueController)** | PHP | Wahrheit über "noch nicht beim Container angekommen"; claim/ack/requeue mit Sperrfrist und Zustell-Zähler (`repeatedly_stuck`) | `QueueMapper.php` (Arten acl, delete, metadata, content), `QueueService.php`, `QueueController.php` |
| **GatewayController** | PHP | Einziger Lesekanal für Dateibytes, löst die Datei über den Ordner des Nutzers auf (echtes Rechtemodell); hier zusätzlich **Range-fähiges Streaming** für große Videos | `GatewayController.php`, `ReaderContext.php` (Teamordner-ACL-Falle #14) |
| **Search Provider + SearchService** | PHP | Unified-Search-Gruppe; zweistufig: Kandidaten (nur file_id + Zeitmarke) vom Container, Recheck `getUserFolder()->getFirstNodeById()` plus Lesebit, erst dann Ausschnitte | `Search/Provider.php`, `Service/SearchService.php`, `ExAppService.php` (2,5-s-Wanduhr, Lockstep D-11) |
| **Player-Route** | PHP | Sprungziel `play/{fileId}#t=` mit HTML5-Medienelement und WebDAV-Quelle, Recheck wie Suche | neu |
| **Export-Route** | PHP | `export/{fileId}.vtt|.srt` in Nutzersitzung, Recheck, holt Untertitel vom Container | neu, Muster wie SearchService |
| **Admin-Seite + Einstellungen** | PHP | Profilwahl, Ausschlüsse (Nutzer, Gruppen, Ordner), Schalter externe Speicher, Pause; Status ehrlich anzeigen | `Settings/Admin.php`, `SettingsService.php`, `ExclusionService.php`, `/profile`-Route |
| **Discovery-Client** | Python | claim/ack gegen den Arbeitsvorrat, Download über Gateway nach `work/<hash>/src.part` mit sha256 im Strom, Dedup-Entscheid | `nc/queue.py`, `nc/files.py`, Kommentar "It creates no client, ever" |
| **Reconcile** | Python | ETag-Abgleich als Reparatur ohne Ereignisse; Bookmark lokal, weil idempotent | `worker/reconcile.py` (D-02: nach einem Zyklus korrekt, auch ohne ein einziges Ereignis) |
| **Scheduler** | Python | Wählt die nächste Arbeitseinheit nach Priorität, hält Leerlauf-Regel, gibt an Stückgrenzen ab | neu (Findling hat Bahnen in `lane.py`, aber keine Mehrstufen-Pipeline) |
| **Pipeline-Planer** | Python | Aus Profil, Dateisprache, erreichtem Niveau und Fensterkonfidenzen die nächsten Stufen ableiten (reine Funktion, ohne I/O) | neu |
| **Engine-Host** | Python | Kindprozess je Modell (Parakeet+VAD, turbo, large-v3), JSON-Zeilen über Pipe, hält Modell warm, solange Arbeit derselben Art ansteht | Spike-Prinzip "ein Prozess = eine Engine" (`bench3.py`), OOM-Isolation wie Findling-OCR-Kinder mit erhöhtem `oom_score_adj` |
| **Hardware / RAM-Wächter / Profil** | Python | cgroup `memory.max`, `anon`, `memory.events`, Kerne aus Affinität und `cpu.max`; Profilvorschlag; effektives Niveau = min(gewählt, passend, Wächter-Deckel) | `hardware.py`, `memory_guard.py`, `guard.py`, `profile.py`, `worker/watch.py` |
| **Transkript-Store + Suchindex** | Python | `state.db`: Inhalte nach Hash, Datei-Referenzen, Fenster, Transkript-Versionen, Wörter, FTS5-Segmente, ACL-Vorfilter; einziger SQL-Ort | `store/repo.py` ("The one module in Findling that contains SQL", geschlossene Grundliste) |
| **Untertitel-Formatierer** | Python | Wörter zu Cues (Zeilenlänge, Dauer, Pausen), SRT und WebVTT | neu, reine Funktion |
| **Modell-Register** | Python | sha256-Pins (Release-Gate-Werte), Download mit `.part`, fsync, Rename; Aufräumen von Resten | `embed/weights.py` |
| **Pause / Instanz-Marke** | Python | Sicherungspause (alle Schreiber halten, Checkpoint), Volume-Fremdinstanz-Erkennung | `worker/pause.py` (#37), `instance.py` (DI-06.1-22) |

---

## Recommended Project Structure

Das Repo zieht auf das Findling-Layout `backend/` + `php/` um. Das ist in Phase 1 billig und später teuer (CI, Release-Archive, Signaturen, Lockstep-Test hängen am Pfad).

```
nextcloud-audio-video-search/
├── backend/                         # ExApp audio_video_search_backend
│   ├── appinfo/info.xml             # external-app, routes, env
│   ├── Dockerfile                   # ffmpeg LGPL, sherpa-onnx, faster-whisper; Parakeet+Silero im Image
│   └── src/audio_video_search/
│       ├── main.py                  # Lifespan, Hintergrund-Tasks (bestehend)
│       ├── nc.py                    # einziger nc_py_api-Import (bestehend, test_boundary.py)
│       ├── config.py, settings.py, logs.py
│       ├── hardware.py              # Kerne/RAM aus cgroup, eingefrorener Schnappschuss
│       ├── memory.py                # Kopf-Raum anon, memory.events
│       ├── guard.py                 # Zulassung je Modell, Eskalation, Deckel
│       ├── profile.py               # Schnell/Ausgewogen/Qualität, Vorschlag, effektiv
│       ├── discovery/
│       │   ├── queue.py             # claim/ack/requeue gegen Companion
│       │   ├── fetch.py             # Gateway-Download, sha256 im Strom, Platzprüfung
│       │   └── reconcile.py         # ETag-Abgleich
│       ├── scheduler/
│       │   ├── units.py             # Arbeitseinheit = (hash, Stufe, Stück)
│       │   └── scheduler.py         # Priorität, Leerlauf, Vorkaufsrecht
│       ├── pipeline/                # reine Logik, offline testbar
│       │   ├── plan.py              # Profil + Zustand → nächste Stufen
│       │   ├── decode.py            # ffmpeg → 16 kHz mono
│       │   ├── windows.py           # VAD-Segmente → Fenster ≤25 s (+0,4 s Kontext)
│       │   ├── swallow_guard.py     # Schluck-Wächter (1 Wort/s ab 1 s)
│       │   ├── hallucination.py     # Fremdsprache < 0,5, fremde Schrift
│       │   ├── langswitch.py        # Fenster-Spracherkennung, Verdachtsbereiche
│       │   ├── selective.py         # Konfidenz < 0,8 → Fenster nachrechnen
│       │   ├── chunking.py          # ca. 10-min-Stücke, Schnitt in VAD-Pausen
│       │   ├── rover.py             # rover2 aus combine.py, mit Oberflächenform
│       │   └── publish.py           # Version schreiben + FTS tauschen, eine Transaktion
│       ├── engines/
│       │   ├── host.py              # Kindprozess-Einstieg, Pipe-Protokoll
│       │   ├── protocol.py          # Anfrage/Antwort-Typen
│       │   ├── parakeet.py          # sherpa-onnx greedy + Silero VAD
│       │   └── whisper.py           # faster-whisper int8, beam 1, Fenster-/Stück-Modus
│       ├── models/
│       │   ├── registry.py          # sha256-Pins aus release-gate-2026-11-06.json
│       │   └── download.py          # .part, fsync, Rename, Reste löschen
│       ├── store/
│       │   ├── repo.py              # einziges SQL, geschlossene Zustands-/Grundliste
│       │   └── schema.py            # Schema-Version, Migrationen
│       ├── subtitles/cues.py, srt.py, vtt.py
│       ├── api/search.py, snippets.py, export.py, status.py, transcript.py
│       └── worker/pause.py, instance.py
├── php/                             # PHP-App audio_video_search
│   ├── appinfo/info.xml, routes.php
│   ├── lib/AppInfo/Application.php
│   ├── lib/Listener/{FileEvent,ShareEvent,GroupEvent}Listener.php
│   ├── lib/BackgroundJobs/{Scheduler,StorageCrawl,SubtreeExpand}Job.php
│   ├── lib/Controller/{Queue,Gateway,Player,Export,Settings,Profile}Controller.php
│   ├── lib/Search/Provider.php
│   ├── lib/Service/{SearchService,ExAppService,ReaderContext,StorageService,ExclusionService,QueueService}.php
│   ├── lib/Migration/, lib/Settings/Admin.php, templates/{admin,player}.php
│   └── l10n/ (de, en, fr)
├── gate/                            # Release-Gate: Skripte + sha256-Datei, KEINE Audiodaten
└── .github/workflows/               # zwei Archive, zwei Signaturen, Lockstep-Test
```

### Structure Rationale

- **pipeline/ ohne I/O:** Planer, Fensterbildung, Wächter, Abfangregel, ROVER und Chunking sind reine Funktionen über Wortlisten und Zeitstempel. So laufen sie im Schnell-Gate gegen gespeicherte Engine-Ausgaben (die Spike-JSONs haben genau dieses Format: `words` = (Wort, Start, Ende, Konfidenz[, Job]), `windows` mit `s`, `e`, `conf_mean`), ohne ein Modell zu laden.
- **engines/ als Kindprozess:** Nur hier werden Modelle geladen. Ein OOM-Kill trifft den Kindprozess, nicht Suche und Status. Speicher geht beim Prozessende sicher an das System zurück; bei CTranslate2 und onnxruntime im selben Prozess ist das nicht garantiert.
- **store/repo.py als einziger SQL-Ort:** Findling-Regel. Ein einziger Schreiber (Hauptprozess), Engines liefern Ergebnisse über die Pipe zurück. Damit gibt es keinen SQLite-Schreibkonflikt zwischen Prozessen.
- **php/ trägt die Sicherheitsgrenze:** Wer was sehen darf, entscheidet ausschließlich PHP über das echte Nextcloud-Rechtemodell. Der Container hat nur einen Vorfilter.

---

## Architectural Patterns

### Pattern 1: Abholen statt Schieben (Pull-Arbeitsvorrat in Nextcloud)

**What:** Listener und Crawl schreiben Zeilen in eine Tabelle der PHP-App; der Container holt in Stapeln, wenn er Kapazität hat, und quittiert. Ein abgestürzter Container staut Arbeit an, statt sie zu verlieren (Findling `QueueController`: "Nobody pushes anything into the container").
**When to use:** Immer für Discovery. Hier besonders wichtig, weil eine einzelne Datei Stunden Rechenzeit kosten kann und ein Push-Modell sofort überläuft.
**Anpassung für Audio/Video:** Die Zeile wird quittiert, sobald die **Vorschau veröffentlicht** ist (erste dauerhafte Aussage) oder ein Endzustand feststeht (skipped/failed mit Grund). Bis dahin trägt die Sperrfrist; ihre Länge muss sich nach der Dauer richten (Findling hat `LOCK_TIMEOUTS` je Art; hier zusätzlich eine Verlängerung "noch dran" je fertigem Fenster-Block, sonst wird eine 3-h-Aufnahme während der Vorschau neu zugestellt). Die Veredelung danach braucht keine Zeile im Arbeitsvorrat mehr, siehe Pattern 2.
**Trade-offs:** Zwei Apps, zwei Releases im Gleichschritt; dafür Rückdruck, Absturzfestigkeit und keine verlorenen Dateien.

### Pattern 2: Niveau statt Warteschlange (abgeleitete Nacharbeit)

**What:** Je Inhalt (Hash) speichert `state.db` das erreichte Niveau. Das Ziel ergibt sich aus dem effektiven Profil und der Dateisprache. Offene Veredelung = `SELECT ... WHERE achieved < target`. Es gibt keine persistente Veredelungs-Warteschlange.
**When to use:** Für alles nach der Vorschau.
**Trade-offs:** Profilwechsel, Wächter-Deckel oder ein neues Modell ändern nur `target`; der Rest folgt. Kein Doppelbestand, der nach einem harten Kill vom Index abweicht (genau die Fehlerklasse, die Findling `store/repo.py` beschreibt).

```python
LEVELS = ("none", "preview", "selective", "turbo_rover", "l3_rover")

def target_level(profile: str, lang: str | None, fits_l3: bool) -> str:
    if profile == "fast":
        return "selective"
    if profile == "quality" and lang == "de" and fits_l3:
        return "l3_rover"
    return "turbo_rover"   # Ausgewogen, und Qualität für EN/FR (Spike 3 Abschnitt 11)
```

### Pattern 3: Versioniertes Transkript mit atomarem Tausch

**What:** Jede Stufe, die ein ganzes Transkript ergibt, schreibt eine neue Version (Wörter, Segmente) und setzt in **derselben SQLite-Transaktion** den Zeiger `current_version` und ersetzt die FTS5-Zeilen dieses Inhalts. Leser im WAL-Modus sehen entweder alt oder neu, nie halb. Alte Version wird erst danach gelöscht (oder für Vergleich/Gate eine Version zurückbehalten).
**When to use:** Vorschau (v1), selektiv oder turbo+ROVER (v2), large-v3+ROVER (v3). In Qualität wird turbo+ROVER als Zwischenstand veröffentlicht, bevor large-v3 läuft.
**Trade-offs:** FTS5 im selben `state.db` macht den Tausch trivial atomar. Ein separater Suchindex (tantivy wie Findling) bräuchte ein Zweiphasen-Protokoll; dafür gibt es hier keinen Grund, Transkripte sind klein (60 min Sprache ca. 9.000 Wörter).

```python
def publish(repo, content_hash, level, words, segments):
    with repo.tx():                       # BEGIN IMMEDIATE
        v = repo.insert_version(content_hash, level, words, segments)
        repo.fts_replace(content_hash, v, segments)
        repo.set_current(content_hash, v, level)
    repo.prune_versions(content_hash, keep=v)
```

### Pattern 4: Arbeitseinheit = Stück, Vorkaufsrecht an Stückgrenzen

**What:** Der Scheduler vergibt nie "eine Datei", sondern eine Einheit (Hash, Stufe, Stück-Index). Vorschau: Fenster-Block von z. B. 5 min Audio. turbo/large-v3: Stück von ca. 10 min (Spike 3 Abschnitt 6: lange Dateien in ca. 10-min-Stücken an faster-whisper, turbo-Spitze sonst 3,4 GB bei 41 min). Nach jeder Einheit wird das Ergebnis des Stücks persistiert (Cursor + Teilwörter), dann darf eine höher priorisierte Einheit vorgehen.
**When to use:** Immer. Die Stückgrenze ist zugleich Speichergrenze, Wiederanlaufpunkt und Vorkaufsrecht.
**Trade-offs:** Stücke müssen in VAD-Pausen geschnitten werden (nicht hart bei 600 s), sonst zerschneidet der Schnitt Wörter; faster-whisper bekommt `vad_filter=True` je Stück. Teilergebnisse eines Stücks sind nicht durchsuchbar, bis das ganze Niveau fertig ist (ROVER braucht das vollständige Zweittranskript, Spike 3 Abschnitt 10 "1 + 2 nicht sinnvoll kombinierbar").

### Pattern 5: Zulassung je Modell statt fester Slots

**What:** Bevor ein Engine-Host startet, fragt der Scheduler den Wächter: frei (cgroup `memory.max` minus `anon`, sonst `MemAvailable`) ≥ Bedarf + Reserve. Bedarf aus Spike 3: Parakeet 1,4 GB, turbo 2,0 bis 2,5 GB (gestückelt), large-v3 4,0 bis 4,5 GB, Reserve 1 GB (`spike3/scripts/queue3.sh`). Nicht zugelassen heißt warten oder auf das nächstniedrigere Niveau ausweichen, nie "trotzdem laden". Ein OOM-Kill eines Kindes senkt den Deckel sofort um eine Stufe (Findling `guard.py`, D-26-01/03).
**When to use:** Für jedes Modell, auch Parakeet. Nextcloud, Datenbank und eventuell Findling laufen auf derselben Box; statische Tabellen nach Gesamt-RAM reichen nicht.
**Trade-offs:** Zwei Modelle gleichzeitig (Parakeet für neue Datei, während turbo warm ist) nur, wenn der Kopf-Raum beide trägt; sonst wird turbo an der Stückgrenze entladen und später neu geladen (Ladespitze turbo 1,9 GB entsteht beim Laden, Spike 3 Abschnitt 6).

---

## Data Flow

### Fluss 1: Discovery (Ereignis oder Crawl bis zur Einheit)

```
Upload/Änderung (WebDAV, Client, Web, occ)
    ↓ View → HookConnector → typisierte Node-Events
FileEventListener (PHP, synchron, Mimetype audio/* video/*, Ausschlüsse)
    ↓ insert
Arbeitsvorrat (DB-Tabelle der PHP-App)  ←── StorageCrawlJob (Erstlauf, Scheiben je Mount)
    ↑ claim (OCS, signiert)                ←── Share/Group-Listener (Art acl)
Discovery-Client (Container)
    ↓ Art?
    ├─ acl      → ACL-Vorfilter in state.db neu schreiben, ack
    ├─ delete   → file_ref löschen (Inhalt bleibt Karenzzeit, siehe Fluss 6), ack
    ├─ metadata → etag/Pfadlose Metadaten, ack (Umbenennen/Verschieben im selben Storage: file_id bleibt)
    └─ content  → Download via Gateway → work/<tmp>/src.part, sha256 im Strom
                    ↓ Hash bekannt und current_version vorhanden?
                    ├─ ja  → file_ref auf vorhandenen Inhalt zeigen, ACL schreiben, ack (Dedup, keine Rechenzeit)
                    └─ nein→ Inhalt anlegen (level none), Einheit "decode" für Scheduler
```

### Fluss 2: Pipeline je Inhalt (Ausgewogen als Standard)

```
src.part ──ffmpeg──→ audio.flac (16 kHz mono)   src.part löschen
    ↓
Silero VAD (0,5 / 0,3 s / max 25 s) → Segmente → Fenster ≤25 s (+0,4 s Kontext, +0,5 s Polster)
    ↓ persistiert: windows(hash, idx, s, e, segs)
Parakeet greedy je Fenster → Schluck-Wächter (Segment ≥1 s mit <1 Wort/s einzeln neu dekodieren,
    übernehmen bei mehr Wörtern) → conf_mean je Fenster
    ↓ Abfangregel (Parakeet: kaum nötig, Füllwörter auf Musik)
publish(level=preview)  ═══► sofort durchsuchbar, Arbeitsvorrat-Zeile ack
    ↓ (Leerlauf: keine Vorschau-Arbeit offen)
turbo je ca. 10-min-Stück (Schnitt in VAD-Pause), Sprache automatisch, beam 1, int8,
    vad_filter 0,5 / 2000 ms, word_timestamps
    ↓ je Stück: Sprache + Sicherheit, Segmente mit no_speech_prob/avg_logprob
Abfangregel: Sprache ∉ Instanz-Sprachen und p < 0,5 → Stück/Segment verwerfen; fremde Schrift → Segment verwerfen
    ↓
Sprachwechsel-Detektor: Verdachtsfenster (siehe Fluss 3) → turbo je Fenster mit eigener Spracherkennung
    ↓
ROVER(A = Parakeet, B = turbo als Gerüst; 0,15 / 0,2 / 0,6) auf Fenstern der Dateisprache;
    Sprachwechsel-Fenster: besseres von {Nachrechnung, ROVER} nach mittlerer Wortkonfidenz
    ↓
publish(level=turbo_rover)  ═══► atomarer Tausch, Suche durchgehend verfügbar
    ↓ nur Qualität + Dateisprache DE + Wächter erlaubt 4,5 GB
large-v3 je Stück → ROVER(A = turbo, B = large-v3 als Gerüst) → publish(level=l3_rover)
    ↓
audio.flac löschen, wenn achieved == target
```

**Schnell** ersetzt den turbo-Ganzlauf durch: Fenster mit `conf_mean < 0,8` (plus Sprachwechsel-Verdacht) mit turbo nachrechnen, je 0,4 s Rand, Sprache der Datei vorgegeben, ohne VAD im Fenster (`bench3.py`: `wins` setzt `vad_filter=False`), dann `selective()` aus `combine.py` → publish(level=selective). Kein ROVER (Spike 3 Abschnitt 10).

**Dateisprache:** Vor der Veredelung braucht die Pipeline eine Dateisprache (Schnell gibt sie im selektiven Nachrechnen vor; Qualität entscheidet daran über large-v3). Quelle: Spracherkennung von turbo auf den ersten Sprachfenstern, Mehrheitsentscheid über mehrere Stichproben, nicht nur die ersten 30 s.

### Fluss 3: Sprachwechsel-Erkennung (offen laut Spike 3 Abschnitt 13)

```
Auslöser (billig, ohne Zusatzlauf):
    - turbo-Stücke derselben Datei melden verschiedene Sprachen, oder
    - Parakeet-Fenster mit Text in anderer Sprache als die Dateisprache (Parakeet springt in FR-Spontansprache ins Englische), oder
    - Fenster mit conf_mean < 0,8 (Schnell)
    ↓
Prüfung (teuer, nur im Verdachtsbereich): turbo-Spracherkennung je Parakeet-Fenster
    ↓ Fenster mit anderer Sprache bei hoher Sicherheit
Nachrechnen je Fenster mit eigener Sprache → besseres Ergebnis behalten
```

Gemessen ist nur der teure Vollweg (mixlang 69,8 % auf 34,9 % WER, RTF 1,39). Der Auslöser-Ansatz ist eine Entwurfsableitung und muss im Phasenplan gemessen werden (Trefferquote des Auslösers auf mixlang, Fehlalarme auf den einsprachigen Sätzen). [LOW, VERIFIZIEREN]

### Fluss 4: Suche (Unified Search)

```
Nutzer tippt "Haushaltsplan"
    ↓
Provider (PHP, IFilteringProvider, Wanduhr 2,5 s) → SearchService
    ↓ exAppRequest POST /search {term, uid, limit}   (nur uid, kein Inhalt)
Container: FTS5 MATCH auf current_version-Segmenten → content_hash → file_refs → ACL-Vorfilter(uid)
    ← Kandidaten [(file_id, t_start, score)], keine Texte
SearchService: je Kandidat getUserFolder(uid)->getFirstNodeById(file_id) + Lesebit (ReaderContext für Teamordner)
    ↓ nur Überlebende
exAppRequest POST /snippets {file_ids, term}
    ← Ausschnitte mit Zeitmarke
SearchResultEntry: Titel = Dateiname, Unterzeile = "12:34 … Haushaltsplan …", Link = play/{fileId}#t=754
```

Die Reihenfolge ist Sicherheitsregel, keine Optimierung: Ein Ausschnitt ist Dateiinhalt und darf für eine Datei, die der Nutzer nicht öffnen darf, den PHP-Prozess nie erreichen (Findling `SearchService.php`, SRCH-02).

### Fluss 5: Export SRT/VTT

```
Nutzer → GET /apps/audio_video_search/export/{fileId}.vtt  (Sitzung)
    ↓ PHP: Recheck wie Suche
    ↓ exAppRequest GET /export?file_id&format
Container: current_version-Wörter → Cues (max. 2 Zeilen à ca. 42 Zeichen, max. ca. 7 s, Schnitt an Pausen) → VTT/SRT
    ← text/vtt; PHP liefert als Download mit Dateiname
```

### Fluss 6: Löschen, Verschieben, Wiederherstellen

- **Umbenennen/Verschieben im selben Storage:** `file_id` bleibt; Container speichert keinen Pfad (Findling-Regel: kein Pfad, kein Dateiname im Log oder Zustand), also nur ACL neu.
- **Verschieben über Storage-Grenzen / Kopieren:** neue `file_id`, Download, gleicher Hash → Dedup, keine Neutranskription.
- **Löschen / Papierkorb:** `file_ref` sofort weg (Suche findet nichts mehr, Recheck sowieso). Der **Inhalt** (Transkript nach Hash) bleibt eine Karenzzeit (Vorschlag 30 Tage, an Papierkorb-Aufbewahrung koppeln), damit eine Wiederherstellung keine Stunden Rechenzeit kostet. Danach Müllsammlung über Referenzzähler.
- **Rechteänderung:** acl-Zeile, vor jeder Inhaltsarbeit vergeben (Findling D-04).

### State Management (state.db)

```
media(content_hash PK, duration_s, lang, lang_p, achieved_level, model_set, created_at, orphaned_at)
file_ref(file_id PK, content_hash, storage_id, etag, size, state, reason, attempts, updated_at)
acl(file_id, uid)                                   -- Vorfilter, keine Sicherheitsgrenze
unit(content_hash, stage, cursor, attempts, updated_at)   -- Fortschritt laufender Stufen
window(content_hash, idx, s, e, conf_mean, lang, lang_p)
version(content_hash, v, level, created_at) ; word(content_hash, v, i, surface, norm, s, e, conf, src)
current(content_hash PK, v)
segment_fts USING fts5(text, content_hash UNINDEXED, v UNINDEXED, s UNINDEXED, e UNINDEXED)
meta(key PK, value)                                 -- Schema-Version, Wächter-Deckel, Instanz-Marke
```

`state`/`reason` aus geschlossener Liste (Findling `STATE_REASONS`), z. B. `skipped(no_audio_stream|excluded|external_off|too_short)`, `failed(decode_error|out_of_memory|repeatedly_stuck|model_missing|disk_full)`. Freitext ist der kürzeste Weg, einen Dateinamen auf die Admin-Seite zu bringen.

---

## Scheduler: Prioritäten und Leerlauf

Strikte Reihenfolge, je Durchlauf neu bewertet:

| Rang | Arbeit | Begründung |
|---|---|---|
| 0 | acl, delete, metadata | Kostet Millisekunden, wirkt sofort auf Sichtbarkeit (Findling D-04) |
| 1 | decode + Vorschau für Dateien aus **Ereignissen** | Der Nutzer hat gerade hochgeladen und sucht gleich |
| 2 | decode + Vorschau für Dateien aus dem **Crawl** | Bestand, Kernversprechen "in Minuten durchsuchbar" |
| 3 | Schnell: selektiv; alle Profile: Sprachwechsel-Fenster | Kleinster Aufwand je Qualitätsgewinn (FR -33 % bei RTF +0,11) |
| 4 | turbo-Ganzlauf (Ausgewogen, Qualität) | Leerlauf = Rang 1 und 2 leer |
| 5 | large-v3 (Qualität, nur DE) | Teuerste Stufe, kleinster Gewinn außerhalb DE |

Innerhalb eines Rangs: angefangene Inhalte vor neuen (hält Arbeitsverzeichnis klein), dann kürzere Dateien vor längeren (mehr Dateien pro Stunde auf neues Niveau). Modell-Kampagnen: Solange Einheiten derselben Engine anstehen, bleibt sie warm; ein Wechsel kostet Laden plus Ladespitze.

**Leerlauf** heißt in v1: keine Vorschau-Arbeit offen. Ein optionales Zeitfenster (z. B. nur nachts veredeln) ist billig nachrüstbar, weil die Regel an einer Stelle steht.

---

## Hardware, RAM-Wächter, Profil-Vorwahl

- **Erkennung:** Findling `hardware.py` 1:1 (Kerne = min(Affinität, `cpu.max`); RAM = `memory.max`, sonst `MemTotal`; AppAPI setzt standardmäßig keine `resourceLimits`). [HIGH, in Findling gemessen]
- **Vorwahl (Vorschlag, VERIFIZIEREN auf Pi 5 / N100):**
  - Gesamt-RAM < ca. 4 GB: nur Schnell (Parakeet 1,2 GB, selektiv turbo 1,9 GB).
  - 4 bis < 8 GB: Ausgewogen (Standard).
  - ≥ 8 GB: Ausgewogen vorgewählt, Qualität wählbar (Spike 3 Abschnitt 11: "Auf Rechnern mit weniger als 8 GB RAM sollte Qualität = Ausgewogen sein").
  - Die Admin-Auswahl zeigt nur Profile, deren Spitzenbedarf + Reserve in den Gesamt-RAM passt.
- **Effektiv:** min(gewählt, passend, Wächter-Deckel). Der gewählte Wert wird nie überschrieben; der Deckel geht nur per Admin-Bestätigung weg (Findling D-24-07, D-26-04).
- **Threads:** Spike gemessen nur mit 2 Threads. Mehr Kerne eher als zweite Engine-Instanz für Vorschau neben der Veredelung nutzen als als mehr Threads für ein Modell; Skalierung ist ungemessen. [LOW]

---

## Modellablage

| Modell | Größe (ca.) | Ort | Begründung |
|---|---|---|---|
| Silero VAD | < 5 MB | Image | Pflicht für jede Datei |
| Parakeet-TDT-0.6B-v3 int8 | ca. 0,65 GB | Image | Vorschau muss ohne Netz sofort laufen |
| faster-whisper turbo | ca. 1,6 GB (`model.bin` fp16) | Volume `models/`, Download bei erstem Bedarf | Image bliebe sonst je Architektur über 5 GB |
| faster-whisper large-v3 | ca. 3,1 GB | Volume, nur wenn Qualität gewählt und passt | Nur DE-Gewinn |

Download aus der öffentlichen Quelle (Hugging Face, fester Revisions-Pin) nach `.part`, sha256 gegen die Release-Gate-Werte (`e76620f8...` turbo, `69f74147...` large-v3), fsync, Rename (Findling `embed/weights.py`). Für Instanzen ohne Netz: Datei von Hand ins Volume legen, gleiche Prüfung. Kein Text und kein Audio verlässt dabei den Server; nur Modelldateien kommen herein (Owner-Regel erlaubt das).

Prüffrage für STACK/PITFALLS: Vorab nach int8 konvertierte CTranslate2-Modelle würden die Ladespitze (fp16 nach int8) und den Platz halbieren, ändern aber die gepinnten sha256 und verlangen einen neuen Release-Gate-Lauf. [MEDIUM]

---

## Wiederanlauf und Idempotenz

1. **Start:** Instanz-Marke prüfen; `.part`-Reste löschen; `unit`-Zeilen lesen. Jede Stufe setzt am letzten persistierten Stück fort (Vorschau: Fenster-Block, turbo/l3: 10-min-Stück). Einheiten ohne gültige Ausgangsdatei (`audio.flac` fehlt) fallen auf `decode` zurück; fehlt die Quelle, lädt der Discovery-Client neu (Arbeitsvorrat-Zeile ist ja noch nicht quittiert oder ein Requeue wird gestellt).
2. **Zustell-Zähler:** Eine Datei, die ffmpeg oder ein Modell dreimal abstürzen lässt, endet als `failed(repeatedly_stuck|out_of_memory)` mit Grund, statt ewig zu kreisen (Findling `QueueService.php`, Arithmetik "greater than", drei Zustellungen).
3. **Idempotenz:** Alle Schreibvorgänge sind Upserts nach (Hash, Version) bzw. (Hash, Stufe, Stück). Eine wiederholte Einheit ersetzt, verdoppelt nicht. Ein Inhalt mit gleichem Hash wird nie zweimal transkribiert.
4. **SIGTERM:** Lifespan-Ende hält den Scheduler an der nächsten Stückgrenze an, beendet Engine-Kinder, checkpointet WAL (Skeleton `main.py` hat `stop_background` mit Frist).
5. **Upgrade mit neuem Modell oder neuen Parametern:** `model_set` je Version speichern. Ob ein Modellwechsel den Bestand neu rechnet, ist eine Owner-Entscheidung je Release (kostet Tage CPU); Standard: nur neue Dateien.

---

## Scaling Considerations

| Maßstab | Anpassung |
|---|---|
| Bis ca. 100 h Audio | Ein Container, eine Engine zur Zeit; Vorschau des Bestands in Stunden (Parakeet RTF ca. 0,11 auf i5-1335U, 2 Threads) |
| 100 bis 2.000 h | Vorschau in Tagen, Veredelung Ausgewogen in Wochen (RTF ca. 0,47 turbo zusätzlich). Admin-Status muss ETA ehrlich zeigen. Zweite Engine-Instanz für Vorschau, wenn Kerne und RAM reichen |
| Darüber | CPU-Grenze. GPU ist v2. Kein Verteilen auf mehrere Container in v1 (ein Schreiber, ein state.db) |

### Scaling Priorities

1. **Erster Engpass: CPU-Zeit der Veredelung.** Gegenmittel ist die Prioritätsordnung (Vorschau zuerst) und ehrliche ETA, nicht Abkürzungen an der Qualität.
2. **Zweiter Engpass: Plattenplatz im Arbeitsverzeichnis.** 16 kHz mono sind ca. 115 MB je Stunde als PCM, als FLAC ungefähr die Hälfte; Quelldateien (Videos mit mehreren GB) liegen nur bis zum Ende von `decode` auf der Platte. Vor dem Download Platzprüfung (Größe + Reserve), sonst `failed(disk_full)` und Wartestand.

---

## Anti-Patterns

### Anti-Pattern 1: Reine ExApp mit Webhooks und eigener Suchseite

**What people do:** Companion vermeiden, `webhook_listeners` für Ereignisse und eine Top-Menü-Seite der ExApp für die Suche nutzen.
**Why it's wrong:** Treffer erscheinen nicht in der Nextcloud-Suche (Kernwert verfehlt), Webhooks sind ab Werk aus, laufen mit bis zu 5 min Verzug über Cron und kennen keine Freigabe- und Gruppenereignisse; die ExApp müsste Rechte selbst nachbauen.
**Do this instead:** PHP-Companion nach Findling-Muster.

### Anti-Pattern 2: ROVER auf normalisierten Tokens ausgeben

**What people do:** `combine.rover2` unverändert übernehmen. `toks()` normalisiert über `n2()` (klein, Satzzeichen weg, Füllwörter weg, optional Zahlen zu Wörtern) und gibt diese Tokens aus.
**Why it's wrong:** Das Spike-Ziel war WER, nicht Anzeige. Im Produkt verschwinden Großschreibung, Satzzeichen und Zahlen aus Ausschnitten und Untertiteln; ein Wort kann in mehrere Tokens zerfallen.
**Do this instead:** Ausrichten auf der normalisierten Form, aber je Token die Oberflächenform, Zeitstempel und Herkunft mitführen und ausgeben. Gate-Prüfung: WER auf Produktausgabe nach derselben Normalisierung muss den Spike-Wert treffen.

### Anti-Pattern 3: Ganze lange Datei in einem Stück an faster-whisper

**What people do:** `transcribe(audio)` auf 3 h Sitzungsaufnahme.
**Why it's wrong:** RAM-Spitze steigt mit der Länge (turbo 3,4 GB bei 41 min, large-v3 bis 4,5 GB), kein Wiederanlauf, kein Vorkaufsrecht für neue Dateien.
**Do this instead:** ca. 10-min-Stücke, in VAD-Pausen geschnitten, je Stück persistiert.

### Anti-Pattern 4: Zweite Veredelungs-Warteschlange neben dem Zustand

**What people do:** Eine Tabelle `refine_queue`, die beim Veröffentlichen der Vorschau befüllt wird.
**Why it's wrong:** Nach einem Kill zwischen Veröffentlichen und Einreihen fehlt die Datei für immer in der Veredelung, und niemand merkt es.
**Do this instead:** Niveau-Abfrage (Pattern 2).

### Anti-Pattern 5: Modelle im Hauptprozess laden

**What people do:** Parakeet und turbo im FastAPI-Prozess halten.
**Why it's wrong:** Ein OOM-Kill nimmt Suche, Status und Export mit; Speicher kommt nach dem Entladen nicht verlässlich zurück; GIL-freie Inferenz blockiert trotzdem Ereignisschleife und Threads.
**Do this instead:** Engine-Host-Kindprozesse mit erhöhtem `oom_score_adj`.

### Anti-Pattern 6: Dateien in den Nutzerordner schreiben (Untertitel-Beifile)

**What people do:** `.film.de.vtt` neben das Video legen, damit der Viewer Untertitel zeigt.
**Why it's wrong:** Erste Schreibkante in Nutzerdaten (Findling ist strikt nur lesend, Gateway hat keinen Schreibpfad), erzeugt Sync-Verkehr auf allen Clients, und ob der Viewer solche Dateien heute lädt, ist nicht belegt (nextcloud/viewer PR #907, Stand unklar). [LOW]
**Do this instead:** v1 Export auf Anfrage; Beifile höchstens v2 als Opt-in.

---

## Integration Points

### External Services

| Dienst | Muster | Hinweise |
|---|---|---|
| Nextcloud Unified Search | PHP `IFilteringProvider` | Nicht `IExternalProvider` (ab Werk aus). Wanduhr 2,5 s, ein langsamer Provider kostet die ganze Suche |
| AppAPI / HaRP | `exAppRequest` (PHP → Container), signierte OCS (Container → PHP) | Lockstep Major.Minor beider Apps, sonst Suche leer statt geraten (Findling D-11); Migration je Minor, die den Merker zurücksetzt |
| groupfolders | über `StorageService` und `ReaderContext` | in_share-Falle bei +read -share (Findling #14) |
| files_external | Mount-Provider-Filter + Admin-Schalter | SMB/S3 langsam: Download-Timeout und Requeue statt failed |
| Hugging Face (nur Modell-Download) | HTTPS GET, sha256-geprüft | Einziger ausgehender Verkehr; Revision fest pinnen |
| Findling (später) | `GET /transcript?file_id` des Containers oder Textkörper über PHP | Schema der Wörter jetzt stabil halten |

### Internal Boundaries

| Grenze | Kommunikation | Hinweise |
|---|---|---|
| PHP ↔ Container | nur über `ExAppService` (eine Klasse) und `QueueController`/`GatewayController` | Container bekommt nie einen Pfad, nur file_id und uid |
| Hauptprozess ↔ Engine-Host | JSON-Zeilen über stdin/stdout, Audio als Pfad auf Volume | Engine schreibt nie in state.db |
| Scheduler ↔ Wächter | synchrone Zulassungsfrage vor jedem Modellstart | Wächter ohne I/O-Entscheidungslogik (Findling `guard.py`) |
| Pipeline-Logik ↔ Engines | Wortlisten im Spike-Format | ermöglicht Gate auf gespeicherten Ausgaben |
| API ↔ Store | Lesen im WAL, Schreiben nur Scheduler/Publish | Suche nie durch Schreibsperre blockiert |

---

## Build Order (Abhängigkeiten für den Roadmapper)

1. **Zwei-App-Gerüst und Integrationsbeweis** (Owner-Tor zuerst: App-ID-Aufteilung, zweites Zertifikat beantragen). Repo auf `backend/` + `php/`, PHP-Companion aus Findling abgeleitet, Lockstep, ein Dummy-Treffer des Containers erscheint in der Unified Search, Link auf Player-Route springt an `#t=`. *Risiko zuerst*: genau so hat Findling Phase 1 geschnitten. Klärt Befund 1, 3, 4.
2. **Discovery** (hängt an 1): Arbeitsvorrat, Listener, Crawl je Mount inkl. Teamordner und externe Speicher (Schalter), Ausschlüsse, Reconcile, Gateway mit Range-Streaming, Download mit sha256, Dedup-Entscheid, Zustell-Zähler. Noch ohne Transkription (Inhalte bleiben `none`), Abdeckungszähler sichtbar.
3. **Store, Vorschau-Pipeline, Wiederanlauf** (hängt an 2): state.db-Schema, ffmpeg-Decode, VAD-Fenster, Parakeet + Schluck-Wächter im Engine-Host, Abfangregel, publish(preview) mit FTS5, Stück-Cursor, Kill-Resume-Test. Einfacher Wächter (Parakeet-Zulassung) schon hier. Gate: pkg-Teil des Schnell-Gates.
4. **Suche und Export Ende zu Ende** (hängt an 3): `/search` + `/snippets` mit Zeitmarke, PHP-Recheck, Paritätstest Rechte (geteilt, entzogen, gelöscht, Teamordner), SRT/VTT-Export. Ab hier ist das Produkt mit Vorschau-Qualität benutzbar.
5. **Hardware, Profile, Wächter, Scheduler** (hängt an 3): Profilvorwahl, effektives Niveau, Zulassung je Modell, OOM-Deckel, Prioritäten, Leerlauf, Vorkaufsrecht, Modell-Download mit sha256.
6. **Veredelung** (hängt an 5): turbo gestückelt, selektives Nachrechnen (Schnell), ROVER mit Oberflächenform, atomarer Tausch, Qualität mit large-v3 (DE), Dateisprache. Gate: Schnell-Gate komplett gegen Spike-Werte.
7. **Sprachwechsel** (hängt an 6): Auslöser messen, Fensterprüfung, besseres Ergebnis behalten. Eigene Phase, weil Spike 3 sie offen lässt und eine Messung braucht.
8. **Admin-Status, Pause, ehrliche Zustände, Dreisprachigkeit** (parallel ab 4 möglich, Abschluss nach 7).
9. **Release-Gate, arm64, Pi 5 / N100, Härtung, Store** (zuletzt): Release-Gate 8,2 h Audio, echte Messung auf schwacher Hardware (ändert evtl. Profilschwellen aus 5), Volltest DE/EN/FR.

Begründung der Reihenfolge: 1 ist die einzige Stelle mit Plattform-Unbekannten und Vorlaufzeit (Zertifikat). 2 vor 3, weil die Pipeline echte Dateien und deren Lebenszyklus braucht. 4 direkt nach 3 liefert früh den Kernwert mit Vorschau-Qualität. 5 vor 6, weil turbo und large-v3 ohne Wächter auf 4-GB-Boxen den Container töten. 7 nach 6, weil der Detektor die turbo-Stückergebnisse als Auslöser nutzt.

### Forschungsbedarf je Phase

- **Phase 1:** Player-Route: Range-Seek über WebDAV mit Sitzungs-Cookie, Verhalten in Nextcloud-Mobil-Apps (öffnen die Links im Browser?). Store-Ablauf für zwei Apps mit einer bestehenden ID.
- **Phase 2:** Sperrfrist für sehr lange Vorschauen; Download großer Videos von SMB/S3 (Timeouts).
- **Phase 6:** ROVER-Kosten auf 3-h-Dateien (jiwer-Alignment ganzer Dateien vs. je Stück); Wahl "besseres Ergebnis" je Fenster.
- **Phase 7:** Komplett offen, Messung Pflicht.
- **Phase 9:** Profilschwellen auf Pi 5 / N100.
- Standardmuster ohne Zusatzrecherche: Phase 3 (Spike-Code liegt vor), Phase 4 (Findling-Muster), Phase 8.

---

## Sources

- AppAPI-Quellbaum, Zweige `main`, `stable30` bis `stable35` (über GitHub-API gelesen am 06.11.2026): kein Suchprovider; `EventsListenerController.php`/`ExAppEventsListener.php` in stable30/31, ab stable32 entfernt; `lib/Listener/LoadFilesPluginListener.php` (nur Dateiaktionen). https://github.com/nextcloud/app_api [HIGH]
- nc_py_api 0.30.3, installiert in `.venv`: `ex_app/ui/{files_actions,resources,settings,top_menu}.py`, `webhooks.py` (`/ocs/v1.php/apps/webhook_listeners/api/v1/webhooks`) [HIGH]
- Nextcloud Developer Manual, Search: https://docs.nextcloud.com/server/stable/developer_manual/digging_deeper/search.html (Provider als PHP-Klassen, `IExternalProvider` seit NC 32 ab Werk aus) [HIGH]
- Nextcloud Admin Manual, Webhook Listeners: https://docs.nextcloud.com/server/latest/admin_manual/webhook_listeners/index.html (Aktivierung per occ, Hintergrundjobs, 5 min, `background-job:worker`) [HIGH]
- nextcloud/viewer#2176 (Zeitstempel per URL, offen): https://github.com/nextcloud/viewer/issues/2176 [MEDIUM]
- nextcloud/viewer PR #907 (Untertitel-Beifiles, Merge-Stand unklar): https://github.com/nextcloud/viewer/pull/907 [LOW]
- Findling-Quellcode `C:/Users/Student/nextcloud-search`: `php/lib/AppInfo/Application.php`, `Listener/*`, `BackgroundJobs/{Scheduler,StorageCrawl}Job.php`, `Search/Provider.php`, `Service/{SearchService,ExAppService,ReaderContext,QueueService,StorageService}.php`, `Controller/{Queue,Gateway}Controller.php`, `Db/QueueMapper.php`; `backend/src/findling/{hardware,memory_guard,guard,profile,lane,instance}.py`, `store/repo.py`, `worker/{poller,reconcile,pause,watch}.py`, `nc/{queue,files}.py`, `embed/weights.py` [HIGH, gelesen]
- Spike 3: `C:/Users/Student/audio-video-spike-2026-11-04/SPIKE3-REPORT.md` Abschnitte 5 bis 13; `spike3/scripts/combine.py` (`rover2`, `selective`, `toks`), `bench3.py` (Fensterbildung, Schluck-Wächter, `wins`-Modus), `ana5.py` (ROVER-Paare: pkg+tu mit tu als Gerüst, tu+l3 mit l3 als Gerüst), `ev.py` (`n2`-Normalisierung) [HIGH, gelesen]
- Projekt: `C:/Users/Student/nextcloud-audio-video-search/.planning/PROJECT.md`, `appinfo/info.xml`, `src/audio_video_search/{main,nc}.py`

---
*Architecture research for: Nextcloud-ExApp lokale Audio-/Video-Transkription mit Suche*
*Researched: 2026-11-06*
