---
phase: 02-erfassung-aller-dateien
verified: 2026-11-14T12:00:00Z
status: passed
score: 4/4 Erfolgskriterien verifiziert, 6/6 DISC-Anforderungen erfüllt
overrides_applied: 0
gaps: []
deferred:
  - truth: "Ordner im Papierkorb: Verweise der Medien darin gehen erst beim nächsten fälligen Abgleich-Walk (24 h oder occ :reconcile) aus dem Vorrat, nicht sofort"
    addressed_in: "Phase 8 (Lebenszyklus und DSGVO)"
    evidence: "Phase-8-SC1: 'Ein Nutzer löscht eine Datei: der Treffer ist sofort weg'; Research flag 'Papierkorb ohne Löschereignis'. Kein Leck heute: Treffer prüfen die Lesbarkeit im Ordner des Suchenden"
  - truth: "Abgeschaltete externe Speicher-Konfiguration (occ :exclude --storage) erscheint in occ :status nicht unter skippedStorages; REASON_SWITCHED_OFF wird nirgends gesetzt"
    addressed_in: "Phase 9 (Ehrliche Admin-Zustände)"
    evidence: "Phase-9-SC1: 'übersprungene ... Dateien erscheinen nur als Zähler mit Grund'. Erfassung selbst ist korrekt: ExclusionService sperrt Einreihen und Laden, Phase exclude-storage-after grün auf 6 Beinen"
  - truth: "Messwerte Rescan je 1000 Dateien, Dauer des Lesebeweises, Annahmen A2 bis A7, Laufzeit von POST /reconcile/run auf großen Instanzen"
    addressed_in: "Phase 11 (Release-Gate, Hardware-Messung und Volltest)"
    evidence: "Phase-11-SC2/SC3: Messung auf Pi 5 und N100, 50-Dateien-Dauertest; in CI mit 52 bis 54 Dateien nicht messbar"
---

# Phase 2: Erfassung aller Dateien, Verifikationsbericht

**Phasenziel:** Ohne Konfiguration kennt das System alle Audio- und Videodateien der Instanz, inklusive Gruppenordner und externer Speicher, respektiert Ausschlüsse von Anfang an und rechnet gleichen Inhalt nur einmal.
**Verifiziert:** 2026-11-14 (lokaler main-HEAD 8debafe; gepushter Stand origin/phase-02 = a99565a, Unterschied nur 02-22-SUMMARY.md)
**Status:** passed
**Re-Verifikation:** Nein, Erstprüfung

Hinweis MVP-Modus: Die Phase ist als `mode: mvp` markiert, das Ziel steht aber nicht in User-Story-Form. Wie in Phase 1 wurde gegen die vier Erfolgskriterien der ROADMAP und DISC-01 bis DISC-06 geprüft, nicht gegen eine User-Flow-Tabelle.

## Zielerreichung

### Beobachtbare Wahrheiten (Erfolgskriterien der ROADMAP)

| # | Wahrheit | Status | Beleg |
|---|----------|--------|-------|
| 1 | Nach der Installation listet `occ` alle Audio- und Videodateien aller Nutzer und Gruppenordner im Arbeitsvorrat; externe Speicher (SMB, S3) erscheinen, bis der Admin sie per Schalter ausschließt | VERIFIED | Code: `StorageService::providers()` nimmt Home-, Gruppenordner- (`OCA\GroupFolders\Mount\MountProvider`) und files_external-Provider; `SchedulerJob::run` plant je Mount einen `StorageCrawlJob` (Bänder, Cursor, Fortsetzung), externe nur nach Einstufung durch `StorageClassifier`; `QueueService::admissible` prüft Mime, Mountmenge, Ausschluss, Erfassbarkeit; `occ audio_video_search:files` und `:status` (FilesCommand, StatusCommand). Schalter: `occ audio_video_search:exclude --storage=<mount id>` (ExcludeCommand, Liste `excluded_mounts`). Abnahme: compare.sh vergleicht `occ :files --json --all` mit truth.sh (unabhängig: find, sqlite3 auf oc_filecache, smbclient, S3-API), Phase initial PASS auf 6 Beinen |
| 2 | Ausgeschlossene Nutzer, Gruppen und Ordner landen nie im Arbeitsvorrat, auch bei Ausschluss vor dem ersten Durchlauf; ein nachträglicher Ausschluss entfernt vorhandene Einträge und Transkripte | VERIFIED | `ExclusionService` (Nutzer, Gruppen über `isInGroup`, Ordner-Präfixe, Mounts; unlesbare Regeln = alles ausgeschlossen) wirkt dreifach: admissible, Gateway (403 excluded), Suchanbieter. Rückwirkend: `SchedulerJob::applyExclusionChanges` (Fingerabdruck), `ExclusionClearJob`, `GroupEventListener`; Container `remove_refs`/`_forget` und `delete_ref` mit Regel des exclude-Auftrags (02-16, f8fbaee). neverFetched in truth.sh (eva, Gruppe extern, Ordner privat) ohne Gateway-Zeile; Phasen exclude-user-after, exclude-storage-after, exclude-after PASS auf 6 Beinen |
| 3 | Neue oder geänderte Datei innerhalb weniger Minuten im Vorrat; außerhalb von Nextcloud geänderte Datei auf externem Speicher spätestens beim periodischen Abgleich | VERIFIED | `FileEventListener`, `CacheEventListener`, `UserEventListener` in Application.php registriert; `ExternalRescanJob` stündlich (INTERVAL_SECONDS 3600), `occ :rescan`; Container-Abgleich `worker/reconcile.py` (Takt 300 s, Walk 24 h), `occ :reconcile`. Gemessen: Datei 140 nach 11 bis 27 s im Vorrat; Phasen upload, overwrite, foreign-change, vanish, reattach PASS auf 6 Beinen |
| 4 | Kopie, Verschieben, Umbenennen, Taggen und dieselbe externe Freigabe bei mehreren Nutzern erzeugen keinen zweiten Rechenauftrag | VERIFIED | Inhalts-Schlüssel sha256 aus Phase 1 plus Vorfilter-Schlüssel (`StorageService::shareKey`/`prefilterKey`, `file_ref.prefilter_key`, Anhängen an media_id ohne Download in repo.py); compare.sh prüft Y (Zahl verschiedener sha256) und `move_same_media`; Phasen copy, rename, move-cross, tag, shares PASS auf 6 Beinen. Fehler aus Push 7 (move-cross über Gruppenordner-Jail) in 02-17b behoben und jetzt grün |

**Score:** 4/4 Erfolgskriterien verifiziert

### Erforderliche Artefakte

| Artefakt | Status | Details |
|----------|--------|---------|
| php/lib/BackgroundJobs/SchedulerJob.php, StorageCrawlJob.php, ExternalRescanJob.php, ExclusionClearJob.php | VERIFIED | substanziell (280/152/61/131 Zeilen), über info.xml und `JobRegistry::ensure` beim Handshake eingetragen (02-17b) |
| php/lib/Service/ExclusionService.php, StorageClassifier.php, QueueService.php, StorageService.php, RescanService.php | VERIFIED | genutzt von Jobs, Listenern, Gateway, Suchanbieter |
| php/lib/Listener/*.php | VERIFIED | in Application.php registriert |
| php/lib/Command/{Files,Status,Exclude,Rescan,Reconcile}Command.php | VERIFIED | von compare.sh in CI aufgerufen |
| php/lib/Migration/Version000200Date20261107000000.php | VERIFIED | Upgrade-Job: oc_avs_queue, oc_avs_crawl, oc_avs_storage nach Update vorhanden |
| backend/src/.../worker/{intake,capture,read_proof,reconcile}.py, store/repo.py, store/migrate.py, api/{workstock,coverage,reconcile}.py | VERIFIED | Schema v2, Upgrade vom echten 0.1.0: `schema_version ('2',)`, gleiche Inode, Treffer vor/nach gleich |
| ci/discovery/*.sh, .github/workflows/discovery-e2e.yml | VERIFIED | unabhängige Wahrheit, Selbsttests, Positivkontrollen, Kontrollbein |

### Key Links

| Von | Nach | Status | Details |
|-----|------|--------|---------|
| SchedulerJob | StorageCrawlJob | WIRED | `jobList->add` nach `crawlMapper->upsert` |
| StorageCrawlJob | QueueService::admissible/enqueue | WIRED | je Cache-Eintrag |
| Container intake | PHP Queue-Routen | WIRED | nc_queue.py, Ack nach Eintrag |
| ExclusionService | Gateway, Suchanbieter, admissible, PageController::excerpt | WIRED | 02-16, 02-16b |
| ExternalRescanJob | RescanService | WIRED | stündlich, respektiert abgeschaltete Hintergrund-Scans |

### Verhaltens-Stichproben (lokal)

| Verhalten | Befehl | Ergebnis | Status |
|-----------|--------|----------|--------|
| Backend-Tests | `uv run pytest -p no:xdist -q` | 1023 passed | PASS |
| Lint/Format | `ruff check .`, `ruff format --check .` | All checks passed, 76 files formatted | PASS |
| Typen | `pyright` (latest) | 0 errors, 0 warnings | PASS |
| HEAD gegen gepushten Stand | `git diff --stat a99565a 8debafe` | nur 02-22-SUMMARY.md | PASS |

### CI-Belege für a99565a (per `gh run view` gegengeprüft, nur lesend)

| Lauf | Workflow | Ereignis | Ergebnis |
|------|----------|----------|----------|
| 43570120264 | Discovery acceptance | workflow_dispatch legs=all | success; Log: 6x "20 of 20 phases passed", "LEAK CONTROL SHOWED THE LEAK" 1x, keine echte FAIL-Zeile außerhalb der Selbsttests |
| 43570120704 | Discovery acceptance | push, attempt 2 | success (damit ist Abweichung 1 aus 02-22-SUMMARY erledigt) |
| 43570120498 | Deploy through HaRP | push | success, inkl. Upgrade vom echten 0.1.0 |
| 43570120510 | Python gates | push | success |
| 43570120508 | PHP gates | push | success |

### Anforderungsabdeckung

| Anforderung | Beschreibung | Status | Beleg |
|-------------|--------------|--------|-------|
| DISC-01 | alle Audio/Video aller Nutzer inkl. Gruppenordner ohne Konfiguration | SATISFIED | SC1 |
| DISC-02 | externe Speicher erfasst, per Schalter ausschließbar | SATISFIED | SC1; Sitzungs-Anmeldedaten bewusst übersprungen (D-02-03, Doku cf122c4) |
| DISC-03 | Ausschlüsse vor dem ersten Durchlauf und rückwirkend | SATISFIED | SC2 |
| DISC-04 | Ereignisse in Minuten, periodischer Abgleich | SATISFIED | SC3 |
| DISC-05 | gleicher Inhalt nur einmal | SATISFIED | SC4 |
| DISC-06 | Verschieben/Umbenennen/Taggen ohne Neuberechnung | SATISFIED | SC4 |

Keine verwaisten Anforderungen: REQUIREMENTS.md ordnet Phase 2 genau DISC-01 bis DISC-06 zu. Die Häkchen in REQUIREMENTS.md, ROADMAP.md (Pläne 13 bis 22) und STATE.md sind noch nicht gesetzt; das ist Buchhaltung des Orchestrators, nicht Teil dieser Prüfung.

### Offene Zeilen aus deferred-items.md, eingeordnet

| Zeile | Einordnung |
|-------|------------|
| 02-18 Ordner in den Papierkorb erst beim Walk | Deferral, Phase 8 (siehe Frontmatter) |
| 02-16 REASON_SWITCHED_OFF, :status ohne abgeschaltete Konfiguration | Deferral, Phase 9 |
| Messwerte A2 bis A7, Rescan je 1000, reconcile/run auf großen Instanzen (02-20) | Deferral, Phase 11 |
| 02-17 SchedulerJob: bis 300 s zwischen bereitem Backend und Erst-Crawl | angenommen, kein Gap: "nach der Installation" erfüllt, Erst-Vorrat in CI nach 228 bis 258 s vollständig; optionaler Owner-Entscheid |
| 02-13 Lesebeweis wertet 403 excluded als read_denied | angenommen: kein Treffer, exclude-Auftrag löscht Verweis und vergisst den Inhalt |
| 02-18 ExclusionService liest Regeln einmal je Instanz (langlebiger `occ background-job:worker`) | WARNING ohne Zielphase: bei cron.php und Web-Anfragen ohne Wirkung; Fix klein (reload je Queue-Anfrage), für Backlog empfohlen |
| 02-08 `_hash_stream` wertet 3xx als Inhalt; 02-16 Probe ohne Speicher-ID bleibt bei exclude_storage | WARNING ohne Zielphase, nur Debug-Weg `occ :sample`; weiter offen im Code (nc.py:179 prüft nur `>= 400`) |
| 02-13 `.claude-active` fehlt in backend/.dockerignore | WARNING, nur lokaler `docker build`; Datei ist nicht im Repo, CI unberührt |
| 02-18 zurückgenommener Ordner-Präfix setzt Crawl aller Mounts zurück | INFO, bewusst, kein Leck |
| 02-16 topology.sh Ersatzweg `excluded_storages`, 02-17 WAL-Kopie im Artefakt, 02-17b groupfolders-Wettlauf | INFO, nur Abnahme-Harness; Wettlauf im Lauf 43570120264 nicht aufgetreten |

### Anti-Patterns

Kein TBD/FIXME/XXX ohne Verweis in den Produktdateien der Phase gefunden, keine Stubs; alle Pfade sind über Tests und die Abnahme auf sechs Beinen ausgeübt.

### Menschliche Prüfung

Keine. Phase 2 hat keinen UI-Vertrag (D-02-06: Fortschritt nur per occ und Abnahmetest, Oberfläche in Phase 9).

### Zusammenfassung

Das Phasenziel ist im Code und in der Abnahme belegt: Erst-Crawl über Homes, Gruppenordner und externe Speicher, dreifach geprüfte Ausschlüsse vor dem ersten Durchlauf und rückwirkend, Ereignisse plus stündlicher Rescan und Container-Abgleich, Dedupe über Vorfilter- und Inhalts-Schlüssel. Die unabhängige Abnahme D-02-07 ist auf stable33/34/35 je amd64 und arm64 mit 20 von 20 Phasen grün, das Kontrollbein zeigt das Leck, das Upgrade vom echten 0.1.0 ist grün. Lokal: 1023 Tests, ruff und pyright grün. Keine Gaps; drei Deferrals mit Zielphase und vier kleine Warnungen ohne Zielphase (Backlog).

---

_Verifiziert: 2026-11-14_
_Verifier: Claude (gsd-verifier)_
