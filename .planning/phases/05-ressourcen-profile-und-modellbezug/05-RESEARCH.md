# Phase 5: Ressourcen, Profile und Modellbezug - Research

**Researched:** 2026-11-18
**Domain:** Linux-Ressourcensteuerung im ExApp-Container (cgroup v2, OOM, Threads), Modellbezug über GitHub-Releases mit sha256-Kette, Admin-Einstellungen im Zwei-App-Muster, Drittlizenzen
**Confidence:** MEDIUM bis HIGH (Kernel-, Docker- und GitHub-Fakten HIGH; RAM-Schwellen für turbo und large-v3 MEDIUM, weil nur auf Windows gemessen)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Profil-Vorschlag und Sperre
- **D-05-01:** Vorgeschlagenes Profil, Grund und Auswahl stehen in den bestehenden Admin-Einstellungen der App (php/lib/Settings/Admin.php, php/templates/admin.php). Es gibt kein eigenes neues Panel; die große Zustandsseite kommt in Phase 9.
- **D-05-02:** Profile, die mehr RAM brauchen, als der Container sicher hat, sind HART gesperrt. Ein Erzwingen ist nicht möglich. Die Sperre zeigt einen Grund mit Zahlen (Bedarf und verfügbarer Speicher, z. B. "braucht 4,5 GB, verfügbar 3,1 GB"). Der RAM-Wächter je Modell (RES-02) prüft zusätzlich vor jedem Start.

#### Rechenfenster
- **D-05-03:** Standard nach der Installation: immer rechnen (kein Fenster), passend zum Kernwert "ohne Konfiguration durchsuchbar". Der Admin kann ein Fenster setzen (Uhrzeiten, z. B. 22 bis 6 Uhr, über Mitternacht möglich). Gesetzt gilt es für alle Rechenarbeit, also auch für Vorschauen (ROADMAP-Kriterium 3).
- **D-05-04:** Am Fensterende wird das aktuell laufende Stück (ca. 10 min Medienlänge) fertig gerechnet und gespeichert, danach pausiert die App bis zum nächsten Fenster. Es gibt keinen harten Abbruch und keinen Rechenverlust; ein Überziehen um wenige Minuten ist akzeptiert.

#### Whisper-Modellbezug
- **D-05-05:** Quelle ist das EIGENE GitHub-Release (street1983nk/nextcloud-audio-video-search), wie Parakeet nach D-03-21.
  - Allowlist nur github.com und release-assets.githubusercontent.com (am echten Redirect prüfen).
  - Commit und sha256 sind fest im Katalog.
  - Das Anlegen oder Hochladen der Release-Assets (turbo, large-v3) ist nach außen gerichtet: VORHER den Owner fragen.
  - Größen laut Stack-Recherche: turbo model.bin 1,62 GB, large-v3 3,09 GB. GitHub-Release-Assets haben eine Obergrenze von 2 GiB je Datei. Das muss die Recherche lösen, ohne die sha256-Kette aufzuweichen, z. B. mit Teilen mit sha256 je Teil und für das Ganze. Eine int8-Vorkonvertierung kommt nur in Frage, wenn das Release-Gate dieselbe WER zeigt.
- **D-05-06:** Die App lädt die Modelle des gewählten bzw. vorgeschlagenen Profils automatisch, ohne Admin-Klick. Der Admin sieht Größe und Fortschritt des Downloads in den Admin-Einstellungen. Ein Modell, dessen sha256 nicht passt, wird verworfen und nie geladen.
- **D-05-07:** Offline-Modus: Standard AUS, ein Schalter ist vorhanden. Bei Offline gibt es keinerlei ausgehende Verbindung, belegt per Netzwerkmitschnitt (ROADMAP-Kriterium 4). Der Admin legt die Modelldateien selbst ab (per occ oder in einen Ordner), die sha256-Prüfung gilt auch dann.

#### Lizenzen in der App
- **D-05-08:** Die Admin-Einstellungen bekommen einen eigenen Abschnitt "Modelle und Lizenzen":
  - Namensnennung NVIDIA Parakeet (CC-BY-4.0)
  - Whisper (MIT), Silero VAD (MIT), ffmpeg (LGPL), PyAV-Codecs
  - Link auf THIRD-PARTY.md

  Dazu kommen README (DE/EN/FR) und eine neue THIRD-PARTY.md. In der Abspielansicht gibt es keine Lizenzzeile.

### Claude's Discretion
- Profilschwellen (RAM je Profil) aus den Spike-3-Kennzahlen plus Reserve ableiten:
  - Parakeet 1,2 GB
  - turbo 1,9 GB, ohne Stückelung bis 3,4 GB
  - large-v3 3,3 bis 4,5 GB

  Kurzen Eigentest nur so weit, wie er die RAM-Entscheidung stützt.
- Form der Thread-Grenze (RES-05):
  - Standard aus cgroup cpu.max und Affinität mit einem Deckel.
  - Der Admin kann ihn nur senken.
- OOM-Isolation (RES-03): oom_score_adj hoch und nice für die Erkennungs-Kinder; Nachweis per provoziertem Speichermangel in einem Container mit --memory=2g in der CI.
- Reihenfolge (RES-04) in der vorhandenen Warteschlange: erst Vorschauen, dann Veredelung, je neueste Datei zuerst.
- Texte dreisprachig DE/EN/FR (Dauerregel), echte Umlaute, keine Gedankenstriche.

### Deferred Ideas (OUT OF SCOPE)
- Lizenzzeile in der Abspielansicht für Nutzer: bewusst nicht (Owner 18.11.2026).
- Hardware-basierte Profilvorwahl mit CPU-Messung über RAM hinaus: Phase 11 (Hardware-Messung).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RES-01 | Profilvorschlag beim Start (RAM und CPU aus der cgroup, kurzer Eigentest), Admin kann ändern, nicht lauffähige Profile mit Grund gesperrt | Abschnitte "Profilschwellen", "Eigentest", Pattern 1 und 6; `memory_guard.headroom_bytes` ist die Basis |
| RES-02 | RAM-Wächter je Modell (Bedarf + Reserve) | Pattern 1: Bedarfstabelle je Modell statt der einen Konstante `ENGINE_NEED_BYTES`; OOM-Erkennung über `memory.events` |
| RES-03 | Kindprozesse mit niedriger Priorität und hohem OOM-Wert | Pattern 2: `oom_score_adj` 1000 im Kind (Nicht-root darf erhöhen), nice; Kernel-Beleg, dass ein cgroup-OOM nie außerhalb der cgroup tötet; CI-Nachweis mit `--memory=2g --memory-swap=2g` |
| RES-04 | Erst Vorschauen, dann Veredelung, neueste Datei zuerst | Pattern 4: ein Rechen-Planer mit genau einem Engine-Platz; Vorschau-Claim sortiert schon `sort_mtime DESC` |
| RES-05 | Threads begrenzen, Rechenfenster | Pattern 3 (Threads aus `cpu.max` und Affinität, Deckel, nur senken, kein `OMP_THREAD_LIMIT`), Pattern 4 (Fenster über Mitternacht, Zeitzone, Pause an der Stückgrenze) |
| RES-06 | Parakeet und Silero im Image; Whisper mit festem Commit und sha256 oder offline | Pattern 5: Modell-Stage im Dockerfile (Muster frpc/ffmpeg), Teildateien für das 2-GiB-Limit, sha256 je Teil und für das Ganze, Ablage durch den Admin |
| RES-07 | Namensnennung CC-BY-4.0 und alle Drittlizenzen in App, README, THIRD-PARTY.md | Abschnitt "Lizenzen": Inhalt von THIRD-PARTY.md, Befund PyAV-Wheel bündelt libx264/libx265, Lizenzangabe large-v3 uneinheitlich, REUSE-Fallen |
| PLAT-04 | Keine Daten nach außen, einziger Ausgang ist der Modell-Download, abschaltbar | Pattern 5 (Offline-Sperre in `nc.fetch_model_asset`), CI-Mitschnitt im Netz-Namensraum des Containers mit Positivkontrolle |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Datenschutz: kein Audio, kein Text, keine Telemetrie verlässt den Server; Modelle einmal aus öffentlichen Quellen laden oder ins Image legen.
- Qualität vor Speed; jede Qualitätsentscheidung mit WER-Messung belegen. Für diese Phase: eine int8-Vorkonvertierung von turbo nur mit gleicher WER im Release-Gate.
- Stack: Python-ExApp (FastAPI, nc_py_api 0.30.3, nur Async-API), sherpa-onnx 2.0.1, faster-whisper/CTranslate2, ffmpeg LGPL-Build.
- Kompatibilität: Nextcloud 33 bis 35, AppAPI mit HaRP, amd64 + arm64, nur CPU.
- Ressourcen: RAM-Wächter für jedes Modell; kein Profil braucht mehr RAM, als die Hardware sicher hat.
- Lizenzen: Parakeet CC-BY-4.0 (Namensnennung NVIDIA Pflicht), Whisper MIT, ffmpeg LGPL; Gate-Daten nie ins Repo.
- Sprache: alle nutzersichtbaren Texte und README DE/EN/FR im Gleichstand, Deutsch zuerst, echte Umlaute, keine Gedankenstriche, keine Emojis.
- Qualitäts-Gates: ruff-Vollsatz, pyright basic (lokal mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`), vulture lokal grün; Commits nur als street1983nk <k.cherif@outlook.de>, ohne "closes #N".
- Prozess: vor jedem Push, Merge, Kommentar und vor jedem Anlegen oder Hochladen von Release-Assets den Owner fragen; UI-Abnahme gemeinsam per Playwright (3 Breiten, hell/dunkel); vor Store-Release großer Volltest DE/EN/FR.
- GSD-Workflow: Änderungen nur über GSD-Befehle.
- Security hat höchste Priorität: secure-phase zum Phasenabschluss, offene Threats blockieren (Owner-Regel 15.11.).
- Neue Abhängigkeiten brauchen eine Owner-Freigabe (Muster "owner approved in plan 03-01" in pyproject.toml).
- Kein lokales Docker; Container-Nachweise laufen in der GitHub-CI.

## Summary

Die Phase hat vier getrennte technische Kerne: (1) Speicher und OOM, (2) Threads und Rechenfenster, (3) Modellbezug mit sha256-Kette und Offline-Modus, (4) Admin-Oberfläche und Lizenzen. Die Codebasis bringt für (1) und (3) fertige, getestete Bausteine mit: `memory_guard.py` liest `memory.max`, `anon`, `MemAvailable` und `memory.events`; `engine/child.py` startet die Erkennung schon als Kindprozess mit nice 10, eigener Sitzung und Wächter-Prüfung; `models/procure.py` und `nc.fetch_model_asset` laden mit Host-Allowlist je Sprung, Längenprüfung, sha256 im Strom, `.part` und `os.replace`. Phase 5 erweitert diese Bausteine, statt neue zu bauen.

Drei Befunde ändern die Planung spürbar. Erstens: Parakeet und Silero liegen heute NICHT im Image, `/init` lädt sie aus dem Release `models-2026-11` auf das Volume; RES-06 verlangt das Image, also braucht das Dockerfile eine Modell-Stage nach dem Muster von frpc und ffmpeg, ohne `MODEL_SHA256` zu ändern (sonst gelten alle Vorschauen als veraltet). Zweitens: Die GitHub-Grenze ist belegt mit "Each file included in a release must be under 2 GiB" [CITED: docs.github.com/en/repositories/releasing-projects-on-github/about-releases]. turbo `model.bin` hat genau 1 617 884 929 Bytes und passt als Ganzes, large-v3 `model.bin` hat 3 087 284 237 Bytes und muss geteilt werden [VERIFIED: Hugging-Face-API, Tree am festen Commit]. Empfohlen sind einheitliche Teile von 1 GiB für beide `model.bin`, die beim Laden direkt in eine einzige `.part`-Datei angehängt werden: sha256 je Teil, sha256 der ganzen Datei gleich dem Hugging-Face-LFS-Wert, Plattenbedarf nur einmal die Dateigröße, Fortsetzen an der Teilgrenze. Drittens: Mit den heutigen Werten (Parakeet 1,7 GiB Bedarf + 0,5 GiB Reserve = 2,2 GiB) startet in einem Container mit `--memory=2g` überhaupt kein Modell. Das erfüllt Kriterium 2 formal, macht die App dort aber nutzlos; die Zahlen stammen aus Windows-Messungen (`peak_wset`). Phase 5 sollte die Linux-Spitze von Parakeet in der CI auf beiden Architekturen messen (VmHWM bzw. `ru_maxrss` des Kindes) und den Bedarf daraus ableiten.

Für die OOM-Isolation gilt: Ein OOM in einer cgroup tötet laut Kernel-Doku nie Prozesse außerhalb dieser cgroup ("If the OOM killer is invoked in a cgroup, it's not going to kill any tasks outside of this cgroup") [CITED: docs.kernel.org/admin-guide/cgroup-v2.html]. Mit Speichergrenze trifft ein OOM also nie Nextcloud oder die Datenbank in anderen Containern; ohne Grenze (AppAPI setzt standardmäßig keine) entscheidet der globale OOM-Killer, und dann macht `oom_score_adj = 1000` im Kind dieses zum ersten Opfer. Erhöhen darf auch ein Prozess ohne Rechte, nur das Senken unter den letzten privilegiert gesetzten Wert braucht `CAP_SYS_RESOURCE` [CITED: docs.kernel.org/filesystems/proc.html].

**Primary recommendation:** Bestehende Bausteine erweitern: Bedarfstabelle je Modell plus Profilrechner auf `memory_guard`, `oom_score_adj` 1000 und Thread-Zahl als Argument im Kind von `engine/child.py`, Fenster- und Reihenfolge-Planer vor dem Vorschau-Claim, Teildatei-Download in `procure.py`, Offline-Sperre zentral in `nc.fetch_model_asset`, Einstellungen mit dem ExApp-Zustand (`state.db`) als einziger Wahrheit, die PHP-Seite liest und schreibt über `exAppRequest`. Alle Container-Nachweise (OOM, Threads, Offline-Mitschnitt) in `docker.yml` auf beiden nativen Runnern, jeweils mit Positivkontrolle.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hardware lesen (memory.max, anon, MemAvailable, cpu.max, Affinität) | ExApp (Python, Hauptprozess) | none | Nur der Container sieht seine cgroup |
| Profilvorschlag, Sperre mit Zahlen | ExApp | PHP-App (Anzeige) | Entscheidung braucht die Messung; PHP rendert nur Codes und Zahlen (T-01-34-Muster) |
| RAM-Wächter je Modell, OOM-Erkennung | ExApp (`engine/child.py`, `memory_guard.py`) | none | Prüfung unmittelbar vor jedem Kindstart |
| oom_score_adj, nice, Thread-Umgebung | ExApp-Kindprozess | none | Muss im Kind vor dem Import der nativen Bibliothek passieren |
| Rechenfenster und Reihenfolge | ExApp (Worker-Schleife) | none | Der Claim aus `state.db` entscheidet die nächste Arbeit |
| Modell-Download, sha256, Allowlist, Offline-Sperre | ExApp (`nc.py`, `models/procure.py`) | none | `nc.py` ist laut `tests/test_boundary.py` der einzige Ort mit HTTP-Client |
| Admin-Formular, Validierung, Rechte | PHP-App (`Settings/Admin.php`, `SettingsController`) | ExApp (zweite Validierung) | Admin-Seite liegt im PHP-Teil (D-05-01); ExApp prüft jeden Wert erneut |
| Ablage durch den Admin (occ) | PHP-App (occ-Befehl) | ExApp (Prüfung) | occ läuft im Nextcloud-Container und kann das ExApp-Volume nicht beschreiben; es stößt nur die Prüfung an |
| Parakeet und Silero ausliefern | Image (Dockerfile-Stage) | none | RES-06 |
| Lizenztexte | Repo (THIRD-PARTY.md, README) | Image (Hinweisdatei), PHP-Seite | RES-07 an drei Stellen |

## Standard Stack

### Core (alles schon im Projekt, keine neue Bibliothek nötig für RES-01 bis RES-05)

| Library / Baustein | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `os`, `resource`, `zoneinfo`, `pathlib` | 3.13 | `os.sched_getaffinity`, `os.process_cpu_count`, `os.nice`, `resource.getrusage(RUSAGE_CHILDREN).ru_maxrss`, Zeitzonen | Keine Abhängigkeit; `os.process_cpu_count()` ist in 3.13 `len(sched_getaffinity(0))` [VERIFIED: CPython 3.13.13 Lib/os.py Zeile 1174] |
| `memory_guard.py` (Projekt) | Findling 1.6.4 | Headroom aus cgroup v2, `memory.events` | Getestet, stdlib-only |
| `engine/child.py` (Projekt) | Phase 3 | Kindprozess, spawn, Gruppen-Kill, Wächter | Erweitern statt neu bauen |
| `models/catalog.py`, `procure.py`, `nc.fetch_model_asset` (Projekt) | Phase 3 | Feste Identität je Datei, Allowlist je Sprung | D-03-21-Muster |
| tzdata im Basis-Image | aus `python:3.13-slim-trixie` | `zoneinfo.ZoneInfo("Europe/Berlin")` | Das offizielle Python-Slim-Dockerfile installiert `tzdata` [VERIFIED: docker-library/python 3.13/slim-trixie/Dockerfile] |

### Supporting (nur wenn Phase 5 faster-whisper schon ins Image nimmt, siehe Open Question 2)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| faster-whisper | 1.2.1 (einziges aktuelles Release) | `WhisperModel(..., cpu_threads=N, num_workers=1)` | Für Linux-RAM-Messung von turbo/large-v3 und den CT2-Thread-Nachweis |
| ctranslate2 | 4.8.5 (02.11.2026, gemessen in Spike 3) | Engine unter faster-whisper | 4.9.0 erschien am 10.11.2026 [VERIFIED: PyPI upload_time]; NICHT nehmen, 4.8.5 ist die gemessene Version; Wheels cp313 manylinux_2_28 für x86_64 und aarch64 vorhanden [VERIFIED: PyPI] |
| onnxruntime | 1.31.1 | Pflichtabhängigkeit von faster-whisper | 1.32.0 erschien am 13.11.2026; bei 1.31.1 bleiben, wie STACK.md |
| av (PyAV) | 19.0.2 | Nur Importpflicht von faster-whisper | Lizenzbefund siehe "Lizenzen" |
| huggingface-hub | 2.4.0 | Nur Importpflicht | `HF_HUB_OFFLINE=1` ist im Image schon gesetzt |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Teildateien im eigenen Release | HTTP-Range-Fortsetzen einer Ganzdatei | Range geht (Asset-Host antwortet 206 und `Accept-Ranges: bytes`) [VERIFIED: curl auf tokens.txt], löst aber das 2-GiB-Limit von large-v3 nicht |
| Teildateien | int8-Vorkonvertierung | Nur mit gleicher WER im Release-Gate (D-05-05); braucht torch/transformers in einem eigenen CI-Schritt; nicht in Phase 5 |
| Teildateien | Git LFS oder ein anderer Host | Erweitert die Allowlist; widerspricht D-05-05 |
| Einstellungen in `state.db` der ExApp | PHP `IAppConfig` als Wahrheit, ExApp zieht | ExApp müsste beim Start Nextcloud erreichen, bevor sie weiß, ob sie offline ist; bricht die Offline-Garantie beim Kaltstart |
| Einstellungen über `exAppRequest` | ExApp-eigenes Deklarativ-Formular (appconfig_ex) | D-05-01 legt die PHP-Seite fest; Fortschritt und Sperrgrund passen nicht in ein Deklarativ-Formular |

**Installation (nur falls Open Question 2 mit Ja beantwortet wird; vorher Owner-Freigabe):**
```bash
cd backend && uv add "faster-whisper==1.2.1" "ctranslate2==4.8.5" "onnxruntime==1.31.1"
```

## Package Legitimacy Audit

slopcheck ließ sich in dieser Sitzung nicht installieren (die Installation wurde vom Rechte-System abgelehnt). Alle Pakete sind deshalb `[ASSUMED]` im Sinne des Protokolls; die Registry-Existenz und die Versionen sind über die PyPI-JSON-API geprüft, die Namen stammen aus STACK.md und den offiziellen Projektseiten.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| faster-whisper 1.2.1 | PyPI | Release 31.10.2025 | nicht geprüft | github.com/SYSTRAN/faster-whisper | nicht gelaufen | [ASSUMED], Owner-Freigabe vor Aufnahme |
| ctranslate2 4.8.5 | PyPI | 02.11.2026 | nicht geprüft | github.com/OpenNMT/CTranslate2 | nicht gelaufen | [ASSUMED], Owner-Freigabe |
| onnxruntime 1.31.1 | PyPI | 26.10.2026 | nicht geprüft | github.com/microsoft/onnxruntime | nicht gelaufen | [ASSUMED], Owner-Freigabe |
| av 19.0.2 (transitiv) | PyPI | 21.10.2026 (Wheel-Datum) | nicht geprüft | github.com/PyAV-Org/PyAV | nicht gelaufen | [ASSUMED], Lizenzhinweis Pflicht |
| huggingface-hub 2.4.0 (transitiv) | PyPI | nicht geprüft | nicht geprüft | github.com/huggingface/huggingface_hub | nicht gelaufen | [ASSUMED] |

**Packages removed due to slopcheck [SLOP] verdict:** keine (nicht gelaufen)
**Packages flagged as suspicious [SUS]:** keine bekannt; der Planer setzt vor jede Installation einen `checkpoint:human-verify`.

Für RES-01 bis RES-05, RES-07 und PLAT-04 wird KEIN neues Paket gebraucht.

## Architecture Patterns

### System Architecture Diagram

```
                    Admin (Browser)
                         |
                         v
   PHP-App: Settings/Admin.php + admin.js + SettingsController (Admin, CSRF)
        |  GET /admin/resources                 |  POST /admin/resources (validiert)
        v                                       v
   ExAppService::exAppRequest  -------->  ExApp-Routen GET/POST /resources (access_level ADMIN, info.xml)
                                                |
                                                v
                          +---------- state.db meta (Profilwahl, Threads, Fenster, Zeitzone, Offline) ----+
                          |                                                                              |
   Start/Eigentest:       v                                                                              |
   cgroup lesen -> Hardware-Snapshot -> Profilrechner -> {vorgeschlagen, gesperrt+Zahlen}               |
                          |                                                                              |
                          v                                                                              |
   Modell-Worker: Profil braucht Modell X? --nein--> nichts                                             |
        | ja                                                                                             |
        v                                                                                                |
   offline? --ja--> nur prüfen (Volume, sha256), nie Netz                                               |
        | nein                                                                                           |
        v                                                                                                |
   fetch_model_asset: github.com --302--> release-assets.githubusercontent.com (Host je Sprung geprüft) |
        -> Teil i an .part anhängen, sha256 Teil + Ganzes -> os.replace -> Fortschritt in Status         |
                                                                                                         |
   Rechen-Planer (Schleife): Fenster offen? --nein--> schlafen bis Fensterbeginn <-----------------------+
        | ja
        v
   Vorschau-Job da? (event vor crawl, sort_mtime DESC) --ja--> Vorschau
        | nein
        v
   Veredelungs-Job da? (Phase 6 füllt die Quelle, neueste zuerst) --> Veredelung
        |
        v
   EngineWorker.start(modell): Wächter: headroom >= Bedarf(modell) + Reserve? --nein--> NO_ROOM, warten
        | ja
        v
   spawn Kind: setsid, nice, oom_score_adj=1000, OMP_NUM_THREADS=N, Bibliothek num_threads=N
        -> Stück (10 min) rechnen -> commit -> Fenster noch offen? --nein--> Job zurück (Fortschritt bleibt), Pause
        |
   Kind stirbt mit SIGKILL und memory.events oom_kill stieg -> OUT_OF_MEMORY (Hauptprozess lebt weiter)
```

### Recommended Project Structure (nur Neues und Geändertes)

```
backend/src/audio_video_search_backend/
├── hardware.py            # neu: cpu.max, Affinität, MemTotal, Snapshot (Findling hardware.py als Vorlage)
├── resources.py           # neu: Bedarfstabelle je Modell, Profile, Schwellen, Sperrgrund mit Zahlen, Threads-Standard
├── schedule.py            # neu: Rechenfenster (über Mitternacht, ZoneInfo), reine Funktionen
├── memory_guard.py        # erweitert: memory.peak optional, oom_kill-Zähler-Helfer
├── engine/child.py        # erweitert: oom_score_adj, Thread-Zahl als Argument, OOM-Erkennung, ru_maxrss
├── engine/constants.py    # RECOGNIZER_THREADS wird Deckel/Messwert, siehe Pitfall 6
├── models/catalog.py      # erweitert: Identität je Modell (turbo, large-v3), Teile, Image-Pfad für Parakeet/Silero
├── models/procure.py      # erweitert: Teildateien, Offline, Fortschritt in Status
├── worker/models.py       # neu: Hintergrund-Download des Profils, Backoff
├── worker/preview.py      # erweitert: Fenster-Gate, Pause an der Stückgrenze
├── api/resources.py       # neu: GET/POST /resources (Zustand und Einstellungen)
└── settings.py            # unverändert bis auf ggf. Hinweistext
backend/Dockerfile         # neue Stage "models": Parakeet + Silero mit sha256 je Datei
backend/appinfo/info.xml   # neue Routen, ggf. AVS_OFFLINE als Deploy-Variable
php/lib/Settings/Admin.php, php/templates/admin.php, php/js/admin.js, php/lib/Controller/SettingsController.php
php/lib/Command/ModelsCommand.php   # occ audio_video_search:models (prüfen/zeigen)
THIRD-PARTY.md, README.md, README.en.md, README.fr.md
ci/oom/, ci/netcap/        # Probe-Skripte für docker.yml (nicht im Image)
```

### Pattern 1: Bedarf je Modell, Profilrechner, Sperrgrund mit Zahlen (RES-01, RES-02)

**What:** Eine Tabelle `MODEL_NEED_BYTES = {"parakeet": ..., "turbo": ..., "large-v3": ...}` und eine Reserve. Ein Profil ist lauffähig, wenn der sichere Speicher den größten Bedarf seiner Modelle plus Reserve deckt. Es läuft immer nur EIN Engine-Kind (Pattern 4), deshalb addieren sich die Bedarfe nicht.

**Profilschwellen (Empfehlung, Begründung unten):**

| Modell | Spike-3-Messung (Windows, peak_wset) | Empfohlener Bedarf | Quelle der Zahl |
|---|---|---|---|
| Parakeet + Silero | Median 1,2 GB, max 1,7 GB | 1,7 GiB (heute `ENGINE_NEED_BYTES`), nach Linux-Messung neu setzen | Spike 3 Abschnitt 6 [VERIFIED: SPIKE3-REPORT.md] |
| turbo (10-min-Stücke in Phase 6) | Ladespitze 1,9 GB, ungestückelt bis 3,4 GB bei 41 min | 2,5 GiB | Spike-3-Warteschlange nutzte 2,0 bis 2,5 GB [VERIFIED: SPIKE3-REPORT.md Abschnitt 1]; Wirkung der Stückelung ungemessen [ASSUMED] |
| large-v3 | 3,3 GB Median, bis 4,5 GB | 4,5 GiB | Maximum, weil Stückelung ungemessen [ASSUMED] |
| Reserve | Spike nutzte "frei mindestens Bedarf + 1 GB" auf dem freien Speicher des Hosts | 0,5 GiB (heute `ENGINE_RESERVE_BYTES`) | Der Headroom zieht `anon` des Hauptprozesses schon ab; die Reserve deckt Wachstum des Hauptprozesses (Index-Merge, Anfragen), ffmpeg (`-threads 1`, PCM eines Stücks ca. 45 MB) und die Kopie des PCM im Kind |

| Profil | Modelle | Mindest-Headroom ohne laufendes Kind |
|---|---|---|
| (keins) | | unter 2,2 GiB: nichts läuft, Zustand "zu wenig Speicher" mit Zahlen |
| Schnell | Parakeet; turbo selektiv nur wenn dessen Bedarf passt | 1,7 + 0,5 = 2,2 GiB |
| Ausgewogen (Standard) | Parakeet, turbo | 2,5 + 0,5 = 3,0 GiB |
| Qualität | Parakeet, turbo, large-v3 (nur DE) | 4,5 + 0,5 = 5,0 GiB |

Plausibilisierung: Spike 3 empfiehlt "Auf Rechnern mit weniger als 8 GB RAM sollte Qualität = Ausgewogen sein" [VERIFIED: SPIKE3-REPORT.md Abschnitt 11]. 5,0 GiB Headroom für die ExApp entspricht auf einem Host mit Nextcloud, Datenbank und System grob 8 GB Gesamt-RAM [ASSUMED].

**Basis der Sperre:** der Headroom ohne laufendes Kind beim Start und bei "Erneut prüfen" (`memory_guard.headroom_bytes()`: `memory.max - anon`, gedeckelt durch `MemAvailable`, sonst `MemAvailable`). Die Sperre nennt beide Zahlen, z. B. Code `profile_locked` mit `needBytes=5368709120`, `availableBytes=3328599654`; die PHP-Vorlage formatiert sie lokalisiert ("braucht 5,0 GB, verfügbar 3,1 GB"). Ändert sich der Headroom nach einem Neustart so, dass das gewählte Profil gesperrt ist, fällt die App auf das beste lauffähige zurück und zeigt das mit Grund (D-05-02, kein Erzwingen). Zur Laufzeit schwankender Speicher wird NICHT über die Profilsperre, sondern über den Wächter vor jedem Kindstart (`NO_ROOM`, warten) abgefangen.

**Einheiten:** Code rechnet in Bytes mit `1024**2`/`1024**3`; die Anzeige nennt "GB" mit einer Nachkommastelle wie in D-05-02. Eine Einheit festlegen und im Test halten (Pitfall 9).

### Pattern 2: OOM-Isolation im Kind (RES-03)

**What:** Erste Anweisungen in `_child_main` nach `os.setsid()`:

```python
# Source: docs.kernel.org/filesystems/proc.html (oom_score_adj), engine/child.py
OOM_SCORE_ADJ: Final = 1000  # höchster Wert: bei Speichermangel zuerst dieses Kind

def _raise_oom_score() -> bool:
    """Make this process the first OOM victim; raising needs no privilege."""
    try:
        Path("/proc/self/oom_score_adj").write_text(f"{OOM_SCORE_ADJ}\n", encoding="ascii")
    except OSError:
        return False  # off Linux or a read-only /proc; logged by the parent as a code
    return True
```

Fakten:
- Wertebereich -1000 bis +1000, der Wert wird vor der Opferwahl zur Badness addiert; Senken unter den letzten von einem `CAP_SYS_RESOURCE`-Prozess gesetzten Wert braucht `CAP_SYS_RESOURCE`, für das Erhöhen nennt die Doku keine Einschränkung [CITED: docs.kernel.org/filesystems/proc.html]. Der Container läuft als uid 10001 ohne Capabilities (Dockerfile), also: erhöhen ja, senken nein.
- Ein cgroup-OOM tötet nie außerhalb der eigenen cgroup [CITED: docs.kernel.org/admin-guide/cgroup-v2.html, memory.oom.group]. Mit `--memory` sind Nextcloud und Datenbank in anderen Containern damit strukturell geschützt; `oom_score_adj` wählt dann innerhalb des ExApp-Containers das Kind statt des Hauptprozesses.
- Ohne Speichergrenze (Normalfall unter AppAPI [ASSUMED: AppAPI setzt kein --memory]) gilt der globale OOM-Killer über alle Prozesse des Hosts; dort ist `oom_score_adj = 1000` das einzige Mittel, das Kind vor Nextcloud und Datenbank zu stellen.
- `memory.events` Feld `oom_kill`: "The number of processes belonging to this cgroup killed by any kind of OOM killer" [CITED: docs.kernel.org/admin-guide/cgroup-v2.html]. Zählt also auch globale OOM-Kills von Prozessen im Container. OOM-Erkennung im Elternprozess: Zähler vor `ask` lesen; stirbt das Kind und ist `oom_kill` gestiegen (oder `exitcode == -9` ohne eigenen Kill), lautet der Code `OUT_OF_MEMORY` statt `CRASHED`.
- `nice`: bleibt bei 10 oder steigt auf 19. Wichtig: Unter cgroup v2 mit CPU-Controller konkurrieren Container als Gruppen über `cpu.weight`; nice wirkt nur innerhalb der eigenen Gruppe [CITED: docs.kernel.org/scheduler/sched-design-CFS.html, Gruppen-Scheduling; Folgerung ASSUMED]. nice schützt also den eigenen Hauptprozess (Suche), nicht Nextcloud. Nextcloud schützt die Thread-Grenze (Pattern 3).
- Kubernetes: Der Kubelet setzt auf cgroup v2 standardmäßig `memory.oom.group` je Container, ein OOM tötet dann den ganzen Container [CITED: kubernetes.io/blog/2026/10/06/kubernetes-cgroups-v2-shift/]. Das lässt sich aus dem Container nicht ändern; als bekannte Grenze dokumentieren.
- Messung der Spitze: `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss` (KiB unter Linux) meldet das Kind mit jeder Antwort; daraus lernt der Eigentest die echte Spitze je Modell [ASSUMED: Einheit KiB unter Linux, Standardwissen].

### Pattern 3: Thread-Grenze aus cpu.max und Affinität, nur senken (RES-05)

```python
# Source: docs.kernel.org/admin-guide/cgroup-v2.html (cpu.max "$MAX $PERIOD", "max" = keine Grenze)
def usable_cpus(root: Path = CGROUP_ROOT) -> int:
    affinity = len(os.sched_getaffinity(0))          # spiegelt --cpuset-cpus
    raw = _read(root / "cpu.max")                     # z. B. "200000 100000" oder "max 100000"
    if raw:
        quota, _, period = raw.partition(" ")
        if quota.isdigit() and period.strip().isdigit() and int(period) > 0:
            return max(1, min(affinity, int(quota) // int(period)))   # --cpus=1.5 ergibt 1
    return max(1, affinity)

def default_threads(cpus: int) -> int:
    return max(1, min(THREAD_CAP, cpus // 2))         # halbe CPU bleibt Nextcloud und DB

def effective_threads(admin_value: int | None, cpus: int) -> int:
    standard = default_threads(cpus)
    return standard if admin_value is None else max(1, min(admin_value, standard))  # nur senken
```

- `--cpus` ist Kurzform für CFS-Periode und -Quote, z. B. `--cpus=1.5` = Quote 150000 bei Periode 100000 [CITED: docs.docker.com/engine/containers/resource_constraints/].
- `os.process_cpu_count()` beachtet nur die Affinität, nicht die Quote [VERIFIED: CPython 3.13 Lib/os.py]. Deshalb beide lesen.
- Deckel `THREAD_CAP`: Spike 3 hat nur mit 2 Threads gemessen [VERIFIED: SPIKE3-REPORT.md]. CTranslate2 rät, `inter_threads * intra_threads` nicht über die Zahl physischer Kerne zu setzen [CITED: opennmt.net/CTranslate2/performance.html]. Empfehlung: Deckel 4, Standard `cpus // 2`; über 2 Threads ungemessen [ASSUMED], Phase 11 misst.
- Eine Zahl N für alles im Kind, gesetzt VOR dem Import der nativen Bibliothek: `OMP_NUM_THREADS=N`, sherpa-onnx `OfflineRecognizer.from_transducer(num_threads=N)`, faster-whisper `WhisperModel(cpu_threads=N, num_workers=1)`. faster-whisper reicht `cpu_threads` als `intra_threads` und `num_workers` als `inter_threads` an CTranslate2 weiter; ein Wert ungleich 0 übersteuert `OMP_NUM_THREADS` [VERIFIED: faster_whisper/transcribe.py v1.2.1]. `intra_threads` sind laut CTranslate2 "OpenMP threads per worker" [CITED: opennmt.net/CTranslate2/python/ctranslate2.models.Whisper.html]. Silero-VAD bleibt bei 1 Thread (≤ N). `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1` wie heute.
- **NIE `OMP_THREAD_LIMIT` setzen.** Lehre aus PII 02-16 (18.11.2026): `OMP_THREAD_LIMIT=1` zusammen mit einer Bibliothek, die mehr Threads plant, ließ arm64 hängen. Ein Test hält fest, dass `OMP_THREAD_LIMIT` in keiner Umgebung des Kindes vorkommt.
- Messung in der CI auf amd64 UND arm64: Kind mit N=1 und N=2 auf einem Sprachclip laufen lassen, währenddessen `/proc/<pid>/status` (`Threads:`) und die CPU-Zeit (`/proc/<pid>/stat` utime+stime) abtasten. Prüfen: CPU-Zeit/Wandzeit ≤ N + 0,5; die Laufzeit bleibt unter einer harten Grenze (Hängen = Fehler, nicht Warten); Zahl der OS-Threads nach oben begrenzt (ONNX Runtime legt je Sitzung eigene Pools an, deshalb ist die rohe Thread-Zahl größer als N und nur als Obergrenze sinnvoll [ASSUMED]).

### Pattern 4: Rechen-Planer: Fenster, Reihenfolge, Pause an der Stückgrenze (RES-04, RES-05)

```python
# Source: eigene Ableitung; zoneinfo ist stdlib, tzdata liegt im Basis-Image
from datetime import datetime, time
from zoneinfo import ZoneInfo

def window_open(now_utc: datetime, start: time | None, end: time | None, zone: str) -> bool:
    """None/None = immer (D-05-03). start > end = über Mitternacht."""
    if start is None or end is None:
        return True
    local = now_utc.astimezone(ZoneInfo(zone)).time()
    if start < end:
        return start <= local < end
    return local >= start or local < end   # 22:00 bis 06:00
```

- **Zeitzone:** Der Container läuft in UTC; "22 bis 6 Uhr" meint die Wanduhr des Admins. Speichere zum Fenster einen IANA-Namen. Vorbelegung auf der PHP-Seite: Zeitzone des Admin-Kontos (`core`/`timezone`), sonst `default_timezone` aus config.php, sonst UTC. `default_timezone` ist laut config.sample.php ein IANA-Name, Standard UTC [CITED: github.com/nextcloud/server config/config.sample.php]. PHP prüft gegen `DateTimeZone::listIdentifiers()`, Python gegen `ZoneInfo()` (Fehler → Fenster ungültig, Wert verwerfen, nicht "nie rechnen").
- `start == end` als Eingabe ablehnen (mehrdeutig).
- **Pause an der Stückgrenze (D-05-04):** `worker/preview.py` hat mit `YIELDED` schon den Mechanismus "nach einem Stück zurück in die Warteschlange, Fortschritt bleibt" (`store.yield_preview(job)`). Nach jedem `commit` im Stück-Loop zusätzlich `window_open(...)` prüfen; geschlossen → `yield_preview`, Ergebnis `PAUSED`. Die Schleife `run_forever` prüft das Fenster vor jedem Claim und schläft bis zum nächsten Fensterbeginn (höchstens `IDLE_SECONDS`-Takt, damit eine Einstellungsänderung schnell wirkt).
- **Was das Fenster sperrt:** Vorschau und (ab Phase 6) Veredelung. Empfehlung: auch `capture` (lädt jede Datei über das Gateway und hasht sie, also Last auf Nextcloud), aber NIE `intake` und Löschungen/Ausschlüsse (Rechte und Löschen müssen sofort wirken). Siehe Open Question 4.
- **Reihenfolge:** Der Vorschau-Claim sortiert heute `origin event vor crawl, sort_mtime DESC` (D-03-05) [VERIFIED: store/repo.py `_CLAIM_PREVIEW`]. RES-04 verlangt "neueste zuerst"; das ist innerhalb jeder Herkunft erfüllt und D-03-05 bleibt. Der Planer fragt zuerst die Vorschau-Quelle, nur bei leerer Vorschau die Veredelungs-Quelle (Protokoll mit `next_refinement()`, in Phase 5 mit Fake getestet, Phase 6 füllt es). Ein laufender Veredelungsjob gibt nach jedem Stück ab, wenn ein Vorschau-Job wartet (gleiches Muster wie `has_waiting_event`).
- **Ein Engine-Platz:** Nie zwei Kinder gleichzeitig. Das macht die Profilschwellen additiv-frei (Pattern 1).

### Pattern 5: Modellbezug mit Teilen, Image-Stage, Offline (RES-06, PLAT-04)

**Größen und Hashes (fest, am Commit):**

| Modell | Datei | Bytes | sha256 |
|---|---|---|---|
| turbo @ 4df90f75321148c3a29a9e2351b7ddf8f5b115a8 | model.bin | 1 617 884 929 | e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da |
| | config.json | 2 263 | b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e |
| | preprocessor_config.json | 340 | 7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711 |
| | tokenizer.json | 2 710 337 | 297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd |
| | vocabulary.json | 1 068 114 | c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1 |
| large-v3 @ edaa852ec7e145841d8ffdb056a99866b5f0a478 | model.bin | 3 087 284 237 | 69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1 |
| | config.json | 2 394 | a9306624f5ec14270a014b647e5c316b6e03a662c369758d1b90697a7b0655b9 |
| | preprocessor_config.json | 340 | 7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711 |
| | tokenizer.json | 2 480 617 | 6d8cbd7cd0d8d5815e478dac67b85a26bbe77c1f5e0c6d76d1ce2abc0e5f21ca |
| | vocabulary.json | 1 068 114 | c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1 |

[VERIFIED: Hugging-Face-API `/api/models/<repo>/tree/<commit>` für Größen und LFS-sha256 von model.bin; kleine Dateien am Commit geladen und mit sha256sum gehasht, 18.11.2026]. Die LFS-Werte der model.bin stimmen mit den Spike-3-Gate-Werten (`e76620f8...18da`, `69f74147...d4f1`) überein.

**Teilung:**
- Grenze: "Each file included in a release must be under 2 GiB", höchstens 1000 Assets je Release [CITED: docs.github.com/en/repositories/releasing-projects-on-github/about-releases].
- Empfehlung: Teile zu genau 1 GiB (1 073 741 824 Bytes) für beide model.bin. turbo: 2 Teile (1 073 741 824 + 544 143 105). large-v3: 3 Teile (2 × 1 073 741 824 + 939 800 589). turbo bräuchte die Teilung nicht, ein Codeweg für beide ist einfacher und gibt eine Fortsetz-Einheit von 1 GiB.
- Asset-Namen eindeutig, weil beide Modelle gleichnamige Dateien haben: z. B. `whisper-large-v3-turbo.model.bin.001`, `whisper-large-v3.config.json`. `ModelFile` trennt schon `name` (Datei im Volume) und `url` (Asset).
- Katalog-Form: `WholeFile(name, sha256, size, parts=(Part(url, sha256, size), ...))`. Laden: Teil i wird gestreamt und an EINE `model.bin.part` angehängt, dabei laufen zwei Hashes (Teil, Ganzes). Passt ein Teil nicht, wird die `.part` auf den Teilanfang zurückgeschnitten und der Lauf endet mit `WRONG_DIGEST`. Nach dem letzten Teil: Länge und Gesamt-sha256 prüfen, `fsync`, `os.replace`. Plattenbedarf = einmal die Dateigröße plus `DISK_RESERVE_BYTES`, nicht doppelt.
- Fortsetzen nach Neustart: Länge der vorhandenen `.part` muss eine Teilgrenze sein, die vorhandenen Teile werden neu gehasht (Prozess vertraut keinem gespeicherten Urteil, wie heute `_VERIFIED` nur im Speicher), sonst `.part` löschen.
- `nc.fetch_model_asset` öffnet `dest` heute mit `"wb"` und löscht `dest` bei jedem Fehler. Für Teile braucht es eine Variante, die an eine offene Datei anhängt und bei Fehler nur auf den Teilanfang kürzt.
- Allowlist unverändert: `github.com` antwortet `302 Found` auf `release-assets.githubusercontent.com`, das mit `200 OK` liefert [VERIFIED: curl -I am 18.11.2026 auf models-2026-11/tokens.txt; schon so in catalog.py vom 14.11.]. Der Asset-Host kann Range (206, `Accept-Ranges: bytes`) [VERIFIED: curl -r 0-9]. Die GitHub-API liefert je Asset einen `digest`-Wert `sha256:...` [VERIFIED: gh api .../releases/tags/models-2026-11]; damit prüft der Upload-Plan jedes hochgeladene Teil gegen den Katalog.
- Hugging Face leitet weiter auf `us.aws.cdn.hf.co` [VERIFIED: curl -I am 18.11.2026 auf large-v3 model.bin]; bestätigt D-03-21, HF nicht in die Allowlist.
- Der Upload (Release-Tag ohne `v`, z. B. `models-2026-11` erweitern oder `models-2026-12`) ist nach außen gerichtet: eigener Plan mit `checkpoint:human-action`, Owner fragt bzw. lädt hoch. Die Release-Beschreibung trägt MIT-Lizenztext und Herkunft (Whisper wird hier weitergegeben).

**Parakeet und Silero ins Image:**
- Neue Build-Stage `models` wie `frpc`/`ffmpeg`: `curl -fsSL --proto '=https' --tlsv1.2` je Datei aus `models-2026-11`, `sha256sum -c`, `install -m 0444` nach z. B. `/usr/local/share/audio_video_search_backend/models/<name>/<MODEL_SHA256>/`. Stoppt bei jeder Abweichung.
- `MODEL_SHA256` und die Dateihashes NICHT ändern: Die Herkunft jedes Vorschau-Transkripts (`Provenance.model_sha256`) zeigt darauf. Gleiche Bytes, anderer Ort.
- `/init` lädt danach nichts mehr; es meldet nach einer Prüfung 100. Whisper-Downloads gehören NICHT in `/init` (AppAPI bricht `/init` nach 40 min ab, STACK.md), sondern in den Modell-Worker nach dem Aktivieren.
- Image wächst um ca. 671 MB (encoder 652 MB + Rest) [VERIFIED: catalog.py Größen]. Die CC-BY-Namensnennung muss im Image liegen, sobald das Modell im Image weitergegeben wird (Hinweisdatei, wie `COPYING.wngerman`).

**Offline-Modus:**
- Zentrale Sperre in `nc.fetch_model_asset` (der einzige ausgehende Weg ins Internet, `tests/test_boundary.py` hält HTTP-Clients in `nc.py`): ist offline aktiv, Rückgabe `MODEL_OFFLINE` ohne Client, ohne DNS. Zusätzlich prüft `worker/models.py` vorab und ruft gar nicht erst auf.
- Kaltstart: Der Offline-Wert muss VOR dem ersten Download-Versuch feststehen. Wert in `state.db` (überlebt Neustarts, ohne Nextcloud lesbar) und zusätzlich eine Deploy-Variable `AVS_OFFLINE` in `info.xml` `<environment-variables>`, die beim Installieren gesetzt werden kann und offline erzwingt (UI zeigt dann "durch Deploy-Option gesetzt"). Ohne diese Variable versucht eine air-gapped Instanz nach der Installation einmal zu laden, bevor der Admin den Schalter umlegen kann.
- Ablage durch den Admin: Dateien als GANZE Dateien (keine Teile) nach `$APP_PERSISTENT_STORAGE/models/<modell>/<set-sha>/`; geprüft wird das Gesamt-sha256. Weil das Gesamt-sha256 gleich dem HF-LFS-Wert ist, darf der Admin die Dateien auch direkt von Hugging Face holen. Bei falschem Hash: Datei wird nie geladen, Status zeigt `wrong_digest` (heutiges Verhalten von `procure`: Datei bleibt liegen, damit der Admin den Fehler sieht).
- occ: `occ audio_video_search:models [--verify]` im PHP-Teil ruft über `exAppRequest` eine ExApp-Route, die `procure(..., fetch=None)` laufen lässt und den Zustand je Modell meldet. occ selbst kann das Volume des ExApp-Containers nicht beschreiben; der Admin kopiert die Dateien (z. B. `docker cp`) und stößt dann die Prüfung an. Den bestehenden Weg `python -m audio_video_search_backend.models.procure --root PATH --verify-only` im Container behalten.

### Pattern 6: Eigentest, nur so weit er die RAM-Entscheidung stützt (RES-01)

1. Snapshot lesen: `memory.max`, `anon`, `MemAvailable`, `MemTotal`, `memory.swap.max`, `cpu.max`, Affinität. Unlesbar (cgroup v1 ohne Grenze, Nicht-Linux) → `MemAvailable` wie heute; gar nichts lesbar → kein Profil zugelassen (fail closed).
2. Plausibilität: `memory.max` größer als `MemTotal` → `MemTotal` zählt.
3. Kurzer Engine-Probelauf (einmal nach Installation bzw. nach Image-Wechsel, Ergebnis in `state.db`): Parakeet-Kind auf 10 s Stille starten, `ru_maxrss` melden lassen. Liegt die gemessene Spitze über dem Katalogbedarf, gilt `max(Katalog, gemessen × 1,15)`. Dauer wenige Sekunden. turbo/large-v3 werden beim ersten echten Lauf (Phase 6) gemessen und in denselben Speicher geschrieben.
4. Ergebnis: Vorschlag = bestes lauffähiges Profil nach Tabelle; Gründe als Codes plus Zahlen. Bis Phase 11 nur RAM (Research flag, Deferred).

### Pattern 7: Weg der Einstellungen PHP zu ExApp

- Wahrheit: `state.db` der ExApp (Tabelle `meta` hat schon `set_meta`/`meta_value`). Keys z. B. `profile_choice`, `threads_admin`, `window_start`, `window_end`, `window_zone`, `offline`.
- PHP `SettingsController` bekommt `GET /admin/resources` und `POST /admin/resources`; beide ohne Attribute, die Admin-Pflicht oder CSRF lockern (wie die bestehenden zwei Routen, T-01-32). POST validiert streng (Profil-Enum, Threads ganze Zahl 1 bis Standard, `HH:MM` per Regex, Zone in `listIdentifiers`, Offline bool) und reicht über `ExAppService::exAppRequest` an `POST /resources` der ExApp weiter.
- ExApp-Routen in `backend/appinfo/info.xml` `<routes>` mit `access_level ADMIN` eintragen (Regex `^/resources$`). Pitfall: AppAPI liest die Routen aus dem Release-Archiv, `store-archive.sh` prüft das mit `cmp`.
- ExApp validiert erneut mit einem strikten pydantic-Modell (`extra="forbid"`, `strict=True` wie `nc_queue.ClaimItem`), schreibt in einer Transaktion und antwortet mit dem neuen Zustand. Ein gesperrtes Profil wird abgelehnt (409 mit Code `profile_locked` und Zahlen).
- Antwort von `GET /resources` (nur Codes, Zahlen, Bools): Hardware-Snapshot, `proposed`, `chosen`, `effective`, je Profil `{locked, needBytes, availableBytes}`, je Modell `{state, doneBytes, totalBytes, reason}`, Threads `{standard, cap, admin, effective}`, Fenster, Offline `{value, forcedByEnv}`. admin.js fragt während eines Downloads alle paar Sekunden neu.
- Die bestehenden Deklarativ-Felder (`processing_enabled`, `max_duration_hours` in `settings.py`) bleiben, wo sie sind; keine Doppelung.

### Anti-Patterns to Avoid

- **`RLIMIT_AS` als RAM-Grenze:** ORT und CTranslate2 reservieren viel virtuellen Speicher (STACK.md "What NOT to Use"). Wächter + Kill bleibt.
- **`OMP_THREAD_LIMIT` oder abweichende Zahlen in Umgebung und Bibliothek:** arm64-Hänger (PII-Lehre).
- **Whisper-Download in `/init`:** 40-min-Timeout von AppAPI.
- **Zwei Engine-Kinder gleichzeitig:** Schwellen würden additiv, OOM wahrscheinlicher.
- **`fork` statt `spawn`:** Elternprozess hat Event-Loop und Sockets (Kommentar in child.py).
- **Teile auf der Platte sammeln und am Ende verketten:** doppelter Plattenbedarf (6,2 GB für large-v3).
- **Fenster in Container-Zeit (UTC):** "22 bis 6 Uhr" läge in Berlin eine bzw. zwei Stunden daneben.
- **HF in die Allowlist:** regionsabhängige CDN-Hosts (D-03-21).
- **Signierte Redirect-URLs loggen oder in SUMMARY schreiben:** nur Host nennen (T-03-77).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| cgroup-Speicher lesen | neuen Leser | `memory_guard.py` (Findling 1.6.4) | schon getestet, `anon` statt `memory.current` wegen mmap-Index |
| HTTP mit Allowlist | zweiten Client | `nc.fetch_model_asset` erweitern | Sprungprüfung vor jeder Anfrage, Cookies je Sprung gelöscht, Boundary-Test |
| Zeitzonen | Offset-Arithmetik | `zoneinfo` + tzdata im Image | Sommerzeit |
| Kind-Lebenszyklus | neues Prozessmodell | `EngineWorker` | Gruppen-Kill, Ablauf, Recycling |
| Pause mit Fortschritt | eigene Pause-Tabelle | `store.yield_preview(job)` | schon transaktional mit `next_start_ms` |
| Lizenzliste der Wheels | Handliste | `uv.lock` + `dist-info/licenses` im venv | vollständig, versioniert |
| Asset-Hash nach Upload | lokale Rechnung allein | `digest` der GitHub-API je Asset | unabhängige Gegenprobe |

**Key insight:** Fast jeder Baustein dieser Phase existiert schon in kleinerer Form; das Risiko liegt in den Übergängen (Kaltstart offline, Teilgrenzen, Einheiten, Zeitzone), nicht in neuer Technik.

## Runtime State Inventory

Phase ist kein Rename, aber sie VERSCHIEBT Modelle vom Volume ins Image. Deshalb kurz:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Bestehende Installationen haben Parakeet/Silero unter `$APP_PERSISTENT_STORAGE/models/{parakeet,silero}/3a78ea81.../` [VERIFIED: procure.model_dir] | Nach Umstieg auf den Image-Pfad sind diese 671 MB verwaist: einmalige Aufräumung beim Start (nur genau diese Pfade, nur wenn das Image die Dateien hat) oder bewusst liegen lassen; Entscheid im Plan |
| Live service config | Keine; Einstellungen neu | keine |
| OS-registered state | Keine | keine |
| Secrets/env vars | Neue Deploy-Variable `AVS_OFFLINE` (Empfehlung) | `info.xml` und Doku |
| Build artifacts | Image wächst um ca. 671 MB; `buildcache-amd64/arm64` in ghcr | erster Build lädt die Modelle aus dem Release |

## Common Pitfalls

### Pitfall 1: Swap verfälscht den OOM-Nachweis
**What goes wrong:** Mit `--memory=2g` ohne `--memory-swap` darf der Container bis 2 GB zusätzlich swappen, wenn der Host Swap hat [CITED: docs.docker.com/engine/containers/resource_constraints/]. Der Speicherfresser swappt statt OOM, der Test läuft lange oder in den Timeout.
**How to avoid:** `--memory=2g --memory-swap=2g` (gleiche Werte = kein Swap).
**Warning signs:** Test dauert Minuten, `memory.events` `oom_kill` bleibt 0.

### Pitfall 2: Mit 2 GiB startet gar kein Modell
**What goes wrong:** 1,7 GiB + 0,5 GiB > 2 GiB minus `anon` des Hauptprozesses. Der Container rechnet nie.
**How to avoid:** Linux-Spitze von Parakeet in der CI messen (Pattern 6), Bedarf daraus ableiten; der CI-Nachweis zeigt beides: bei 2 GiB `NO_ROOM` (falls der Bedarf bleibt), bei 4 GiB Start (Positivkontrolle).

### Pitfall 3: Offline erst nach dem ersten Download-Versuch
**What goes wrong:** Ein Admin installiert ohne Internetzugang; der Modell-Worker versucht sofort GitHub, bevor der Admin den Offline-Schalter in der Oberfläche setzen kann. Der Schalter ist Standard AUS (D-05-07), es gibt also mindestens einen Verbindungsversuch nach außen.
**How to avoid:** `AVS_OFFLINE` als Deploy-Variable; Modell-Worker liest Offline vor jedem Versuch aus `state.db`/Env.

### Pitfall 4: Fenster in UTC
**What goes wrong:** Container-Zeit ist UTC. **How to avoid:** IANA-Zone speichern, `zoneinfo`.

### Pitfall 5: Teilgrenze und Fortsetzen
**What goes wrong:** `.part` endet mitten in einem Teil nach Absturz, oder ein falscher Teil bleibt im Ganzen. **How to avoid:** nur an Teilgrenzen fortsetzen, vorhandene Teile neu hashen, Gesamt-sha256 als letztes Urteil.

### Pitfall 6: Thread-Zahl ist im Konstanten-Fingerabdruck
**What goes wrong:** `RECOGNIZER_THREADS = 2` steht in `engine/constants.py` und im Fingerabdruck von `tests/test_engine_constants.py`; jede Änderung verlangt dort ein höheres `CONFIG_VERSION` [VERIFIED: constants.py Kopfkommentar]. Ein höheres `CONFIG_VERSION` würde alle Vorschauen als anders konfiguriert markieren.
**How to avoid:** Die Thread-Zahl als Laufzeitargument ans Kind geben und belegen, dass sie das Ergebnis nicht ändert: CI-Test, der denselben Clip mit 1 und 2 Threads transkribiert und wortgleiche Ausgabe verlangt (greedy_search). Nur wenn das hält, gehört die Zahl nicht in die Herkunft; `RECOGNIZER_THREADS` bleibt als gemessener Wert bzw. Deckel stehen. Hält es nicht, ist das ein Owner-Entscheid (Open Question 3).

### Pitfall 7: nice schützt Nextcloud nicht
**What goes wrong:** Unter Gruppen-Scheduling teilen Container über `cpu.weight`; nice gilt nur innerhalb des Containers. **How to avoid:** Thread-Grenze (Standard halbe CPU) ist der Schutz für Nextcloud; nice schützt den eigenen Hauptprozess.

### Pitfall 8: Kubernetes tötet den ganzen Container
**What goes wrong:** `memory.oom.group=1` vom Kubelet [CITED: kubernetes.io blog 06.10.2026]. **How to avoid:** Nicht lösbar im Container; Wächter vor dem Start ist dort die einzige Linie. In README als Grenze nennen.

### Pitfall 9: GB und GiB gemischt
**What goes wrong:** Spike nennt "GB", Code rechnet MiB (`1_700 * 1024**2`). Sperrgrund zeigt andere Zahl als Doku. **How to avoid:** intern Bytes, Anzeige einheitlich, Test für die Formatierung.

### Pitfall 10: REUSE-Lint bricht bei fremden Lizenztexten
**What goes wrong:** `security.yml` lässt `reuse lint` laufen [VERIFIED]. Neue Dateien unter `LICENSES/` ohne Verweis in `REUSE.toml` gelten als ungenutzt, fremde Lizenztexte unter `**` würden als AGPL eigener Autorschaft annotiert [ASSUMED: Verhalten von reuse lint bei ungenutzten Lizenzen].
**How to avoid:** THIRD-PARTY.md ist eigener Text (AGPL, deckt `**`) mit SPDX-IDs und Links; keine fremden Lizenzdateien ins Repo; Lizenztexte im Image aus den `dist-info/licenses` der Wheels und als eigene Hinweisdatei.

### Pitfall 11: Release-Routen vergessen
**What goes wrong:** Neue ExApp-Route ohne `<route>` in `backend/appinfo/info.xml` ist hinter HaRP nicht erreichbar. **How to avoid:** Route + `access_level ADMIN` eintragen; `tests/test_store_metadata.py` und `store-archive.sh` decken das Archiv ab.

### Pitfall 12: Verwaiste Modelle auf dem Volume
Siehe Runtime State Inventory.

## Code Examples

### OOM-Erkennung im Elternprozess
```python
# Source: docs.kernel.org/admin-guide/cgroup-v2.html (memory.events oom_kill), memory_guard.memory_events
def _oom_kills() -> int | None:
    events = memory_guard.memory_events()
    return None if events is None else events.get("oom_kill")

before = _oom_kills()
code, windows = self._ask(...)
if code == CRASHED:
    after = _oom_kills()
    if before is not None and after is not None and after > before:
        code = OUT_OF_MEMORY
```

### Thread-Umgebung im Kind (Argument statt Konstante)
```python
# Source: faster_whisper/transcribe.py v1.2.1 (cpu_threads -> intra_threads), engine/child.py
def thread_env(threads: int) -> dict[str, str]:
    # Never OMP_THREAD_LIMIT (PII lesson 18.11.2026: arm64 hang)
    return {"OMP_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
```

### CI-Mitschnitt im Netz-Namensraum des Containers (Offline-Nachweis)
```bash
# docker.yml, je Architektur; tcpdump ist auf ubuntu-24.04 nicht vorinstalliert
sudo apt-get install -y --no-install-recommends tcpdump
docker run -d --name off -e AVS_OFFLINE=1 --memory=4g --memory-swap=4g ... "${IMAGE}@${DIGEST}"
pid=$(docker inspect -f '{{.State.Pid}}' off)
sudo nsenter -t "$pid" -n tcpdump -i any -nn -w off.pcap &   # sieht auch DNS an 127.0.0.11
# ... App-Zustand so setzen, dass ein Profil Whisper bräuchte, 60 s warten ...
# Erlaubt: nur Loopback (NEXTCLOUD_URL im Test auf 127.0.0.1) und der veröffentlichte Port.
test "$(tcpdump -nn -r off.pcap 'not host 127.0.0.1 and not tcp port 10035' | wc -l)" = 0
# Positivkontrolle: gleicher Lauf ohne AVS_OFFLINE muss DNS/TCP Richtung GitHub zeigen.
```

### OOM-Nachweis
```bash
docker run -d --name oom --memory=2g --memory-swap=2g \
  -v "$PWD/ci/oom:/probe:ro" ... "${IMAGE}@${DIGEST}"
before=$(docker exec oom cat /sys/fs/cgroup/memory.events | awk '/^oom_kill /{print $2}')
docker exec oom /app/.venv/bin/python -I /probe/oom_probe.py   # EngineWorker mit Fresser-Factory aus /probe
after=$(docker exec oom cat /sys/fs/cgroup/memory.events | awk '/^oom_kill /{print $2}')
curl -sf http://127.0.0.1:10035/heartbeat                       # Hauptprozess lebt
test "$after" -gt "$before"
sudo dmesg | grep -E "oom_score_adj=1000" | tail -1              # Opfer war das Kind
```
Optional stärker: App-Container und ein "Nachbar"-Container (z. B. kleiner Postgres) gemeinsam unter eine Eltern-cgroup mit Grenze (`--cgroup-parent` auf eine systemd-Slice mit `MemoryMax`), dann zeigt der Test, dass der Nachbar überlebt. Ob die Slice auf dem Runner so anlegbar ist, ist ungeprüft [ASSUMED]; Fallback ist der Kernel-Beleg, dass ein cgroup-OOM die cgroup nie verlässt.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Parakeet/Silero per `/init` aufs Volume | ins Image (RES-06) | Phase 5 | offline sofort lauffähig |
| HF-Download | eigenes GitHub-Release | D-03-21, 14.11.2026 | feste Allowlist |
| ctranslate2 4.8.5 | 4.9.0 erschienen 10.11.2026 | | nicht übernehmen ohne Messung |
| onnxruntime 1.31.1 | 1.32.0 erschienen 13.11.2026 | | nicht übernehmen ohne Messung |
| Kubernetes cgroup v1 Einzel-Kill | v2 Gruppen-Kill je Container | | Pitfall 8 |

## Lizenzen (RES-07): Inhalt von THIRD-PARTY.md

| Bestandteil | Lizenz | Wo | Pflichten / Befund |
|---|---|---|---|
| Parakeet-TDT-0.6B-v3 (NVIDIA), int8-ONNX-Export von k2-fsa/sherpa-onnx (csukuangfj) | CC-BY-4.0 [VERIFIED: HF-API license=cc-by-4.0 für nvidia/... und csukuangfj/...] | Image | Namensnennung NVIDIA, Lizenz-URI, Hinweis auf Bearbeitung (int8-Quantisierung durch sherpa-onnx), unverändert weitergegeben [CITED: creativecommons.org/licenses/by/4.0/legalcode Abschnitt 3(a)] |
| Silero VAD | MIT | Image | Copyright- und Lizenztext beilegen [ASSUMED: Copyright-Zeile aus snakers4/silero-vad prüfen] |
| Whisper large-v3-turbo (CT2 deepdml) | MIT [VERIFIED: HF-API mit openai/whisper-large-v3-turbo und deepdml/...] | eigenes Release, Volume | MIT-Text in Release-Beschreibung bzw. als Asset |
| Whisper large-v3 (CT2 Systran) | Systran-Repo: MIT; openai/whisper-large-v3 auf HF: **apache-2.0** [VERIFIED: HF-API] | eigenes Release, Volume | Angaben widersprechen sich; das GitHub-Repo openai/whisper (Code und Gewichte) steht unter MIT [ASSUMED]. Empfehlung: beide nennen, Apache-2.0-Pflichten (Lizenztext, NOTICE falls vorhanden) mit erfüllen |
| FFmpeg 8.1.3 statisch, BtbN `lgpl` | LGPL-2.1-or-later (Build-Prüfung auf `--enable-gpl` im Dockerfile) | Image | Quelle angeben: FFmpeg-Tag und BtbN-Build-Skripte; Lizenztext |
| PyAV 19.0.2 (falls faster-whisper kommt) | PyAV selbst BSD-3-Clause; gebündeltes FFmpeg meldet "LGPL version 3 or later", Konfiguration mit `--enable-version3 --enable-libx264 --enable-libx265`; das Wheel enthält `libx264-*.so.165` und `libx265-*.so.217` [VERIFIED: av-19.0.2-cp312-abi3-manylinux_2_28_x86_64.whl entpackt und durchsucht, 18.11.2026] | Image | x264 und x265 sind GPL-2.0-or-later [ASSUMED: Standardwissen]; mit AGPL-3.0 vereinbar, aber Quellenangebot nötig; die App dekodiert nie mit PyAV. arm64-Wheel nicht geprüft |
| sherpa-onnx / sherpa-onnx-core 2.0.1 (mit eigenem libonnxruntime) | Apache-2.0 | Image | |
| onnxruntime, ctranslate2, faster-whisper | MIT | Image (falls aufgenommen) | |
| tantivy, fastapi, starlette, uvicorn, pydantic | MIT | Image | |
| numpy, httpx, py3langid, nc-py-api | BSD-3-Clause [ASSUMED für nc-py-api] | Image | |
| tokenizers, huggingface-hub | Apache-2.0 | Image (falls aufgenommen) | |
| wngerman | GPL-2.0-or-later | Image | schon dokumentiert |
| frpc | Apache-2.0 [ASSUMED] | Image | |
| Material Design Icons | Apache-2.0 | PHP | schon in REUSE.toml |

Vollständige Liste der Laufzeit-Wheels aus `backend/uv.lock` ziehen (heute u. a. annotated-types, anyio, certifi, h11, httpcore, httptools, idna, jh2, niquests, opentelemetry-api, packaging, python-dotenv, pyyaml, qh3, urllib3-future, uvloop, wassima, watchfiles, websockets, xmltodict); Lizenz je Paket aus `dist-info` im gebauten venv lesen, nicht raten. Ein Test kann prüfen, dass jedes Laufzeitpaket aus `uv.lock` in THIRD-PARTY.md vorkommt.

Admin-Abschnitt "Modelle und Lizenzen" (D-05-08): Namensnennung NVIDIA mit Link auf CC-BY-4.0, Whisper, Silero, FFmpeg, PyAV-Codecs, Link auf THIRD-PARTY.md im Repo (feste URL auf github.com), dreisprachig über `$l->t()`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | turbo-Bedarf mit 10-min-Stücken ≤ 2,5 GiB | Pattern 1 | Ausgewogen auf zu kleinen Geräten freigegeben; Wächter fängt es zur Laufzeit ab, aber OOM-Kills möglich |
| A2 | large-v3 ≤ 4,5 GiB auch auf Linux | Pattern 1 | wie A1 |
| A3 | 5,0 GiB Headroom ≈ 8 GB-Host | Pattern 1 | nur Plausibilisierung |
| A4 | AppAPI setzt standardmäßig kein `--memory` | Pattern 2 | nur Gewichtung der Argumente |
| A5 | nice wirkt nur innerhalb der Container-cgroup | Pattern 2, Pitfall 7 | Begründung, nicht Umsetzung |
| A6 | Deckel 4 Threads, Standard halbe CPU | Pattern 3 | Tempo/Last; Admin kann senken |
| A7 | ORT-Thread-Zahl größer als N, deshalb CPU-Quote als Maß | Pattern 3 | Messmethode |
| A8 | Parakeet-Ausgabe gleich bei 1 und 2 Threads | Pitfall 6 | dann CONFIG_VERSION-Frage |
| A9 | systemd-Slice per `--cgroup-parent` auf dem Runner anlegbar | Code Examples | nur optionaler Zusatznachweis |
| A10 | reuse lint meldet ungenutzte Lizenzdateien als Fehler | Pitfall 10 | CI-Bruch, schnell sichtbar |
| A11 | x264/x265 GPL-2.0-or-later; Whisper-Repo MIT | Lizenzen | Texte in THIRD-PARTY.md |
| A12 | `ru_maxrss` in KiB unter Linux | Pattern 2/6 | Faktor 1024 falsch; Test fängt es |

## Open Questions

1. **Linux-Bedarf von Parakeet und Betrieb bei 2 GiB**
   - What we know: Windows-Spitze bis 1,7 GB; mit 0,5 GiB Reserve startet bei 2 GiB nichts.
   - What's unclear: echte Linux-Spitze (amd64/arm64) im 10-min-Stück.
   - Recommendation: Wave-0-Messung in `docker.yml` (ru_maxrss/VmHWM), Bedarf = Messung × 1,15; Owner entscheidet, ob 2 GiB ein unterstütztes Ziel ist.
2. **faster-whisper schon in Phase 5 ins Image?**
   - What we know: Research flag nennt "huggingface-hub 2.x im ersten Container-Build"; ohne CT2 im Image gibt es keine Linux-Zahlen für turbo/large-v3 und keinen CT2-Thread-Nachweis.
   - Recommendation: Ja, mit Owner-Freigabe der Pakete (Pins 1.2.1 / 4.8.5 / 1.31.1), nur für Messung und Thread-Nachweis; die Veredelung selbst bleibt Phase 6. Alternative: Schwellen aus Spike übernehmen, Messung in Phase 6.
3. **Thread-Zahl und Herkunft:** falls 1 und 2 Threads verschiedene Wörter liefern: Thread-Zahl in die Herkunft (TRANS-06) oder Deckel = Standard = 2 fest? Owner-Entscheid.
4. **Sperrt das Fenster auch `capture`?** D-05-03 sagt "alle Rechenarbeit". Empfehlung: ja für capture, nein für intake/Löschungen.
5. **Release für Whisper:** bestehendes `models-2026-11` erweitern oder neues Tag? Upload durch Owner (D-05-05).
6. **Alte Parakeet-Kopien auf dem Volume löschen?** (Runtime State Inventory)
7. **Lizenz large-v3:** MIT oder Apache-2.0 nennen? Empfehlung: beide.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker lokal | Container-Nachweise | bewusst nicht genutzt (Regel) | | GitHub-CI |
| GitHub Runner ubuntu-24.04 / ubuntu-24.04-arm | OOM, Threads, Offline | ja (in docker.yml genutzt) | Docker 28.0.4 [VERIFIED: runner-images Ubuntu2404-Readme] | |
| tcpdump auf Runner | Mitschnitt | nein, nicht gelistet [VERIFIED: Ubuntu2404-Readme] | | `sudo apt-get install tcpdump` |
| nsenter (util-linux), dmesg mit sudo | Mitschnitt, OOM-Opfer | [ASSUMED] vorhanden | | Mitschnitt per Sidecar-Container mit `--net container:` |
| systemd auf Runner | optionale Slice | ja, 255.4 [VERIFIED] | | Kernel-Zitat |
| GitHub-Release-Upload | Whisper-Assets | Owner | | Owner lädt hoch |
| uv, pytest, phpunit, Playwright | Tests | ja (CI) | pytest 9.2.0 | |

**Missing dependencies with no fallback:** keine.
**Missing dependencies with fallback:** tcpdump (apt im Job).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 + pytest-asyncio 1.4.1.post1 (Backend), phpunit 11.5 (PHP), Playwright (Admin-UI), Shell-Schritte in docker.yml (Container) |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]`, `php/tests/bootstrap.php`, `ci/playwright/playwright.config.ts` |
| Quick run command | `cd backend && uv run pytest -q -x tests/test_memory_guard.py tests/test_engine_child.py tests/test_models.py` |
| Full suite command | `cd backend && uv run pytest -q -rs --cov=src/audio_video_search_backend --cov-report=term` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RES-01 | Profilrechner aus Snapshot, Sperre mit Zahlen, Rückfall bei gesperrter Wahl | unit (Fake-cgroup-Baum) | `uv run pytest tests/test_resources.py -x` | ❌ Wave 0 |
| RES-01 | cpu.max/Affinität lesen ("max", Quote, kaputt) | unit | `uv run pytest tests/test_hardware.py -x` | ❌ Wave 0 |
| RES-01 | Admin sieht Vorschlag, gesperrte Profile mit Grund | e2e Playwright | `npx playwright test admin.spec.ts` | ✅ erweitern |
| RES-02 | Wächter je Modell, NO_ROOM unter Bedarf+Reserve | unit | `uv run pytest tests/test_engine_child.py -x` | ✅ erweitern |
| RES-02 | `--memory=2g`: kein Start ohne Bedarf+Reserve; 4 GiB: Start (Positivkontrolle) | Container, beide Arches | docker.yml Schritt | ❌ Wave 0 |
| RES-03 | Kind schreibt oom_score_adj 1000, nice; OOM-Code über memory.events | unit (Fake /proc, Fake events) | `uv run pytest tests/test_engine_child.py -x` | ✅ erweitern |
| RES-03 | Provozierter OOM tötet nur das Kind, Heartbeat bleibt, oom_kill steigt | Container, beide Arches | docker.yml Schritt `ci/oom/` | ❌ Wave 0 |
| RES-04 | Vorschau vor Veredelung, neueste zuerst, Veredelung gibt nach Stück ab | unit (Fake-Quelle) | `uv run pytest tests/test_schedule.py tests/test_preview_worker.py -x` | ❌/✅ |
| RES-05 | Fenster über Mitternacht, Zone, Sommerzeit, start==end abgelehnt | unit | `uv run pytest tests/test_schedule.py -x` | ❌ Wave 0 |
| RES-05 | Pause an der Stückgrenze, Fortschritt bleibt | unit | `uv run pytest tests/test_preview_worker.py -x` | ✅ erweitern |
| RES-05 | Threads nur senken; Env und Bibliothek gleich; kein OMP_THREAD_LIMIT | unit | `uv run pytest tests/test_engine_child.py -x` | ✅ erweitern |
| RES-05 | CPU-Quote ≤ N+0,5, kein Hängen, auf amd64 und arm64 | Container | docker.yml Schritt | ❌ Wave 0 |
| RES-05 | 1 und 2 Threads gleiche Wörter | Container oder python.yml mit Clip | docker.yml | ❌ Wave 0 |
| RES-06 | Image enthält Parakeet/Silero mit Katalog-sha256 | Container + `tests/test_dockerfile.py` | docker.yml + pytest | ✅ erweitern |
| RES-06 | Teile: falscher Teil → WRONG_DIGEST, `.part` gekürzt; Fortsetzen an Teilgrenze; Ganzes-sha256 | unit (Fake-Server) | `uv run pytest tests/test_model_download.py tests/test_models.py -x` | ✅ erweitern |
| RES-06 | Ablage durch Admin: richtig → present, falsch → wrong_digest, nie geladen | unit | `uv run pytest tests/test_models.py -x` | ✅ erweitern |
| PLAT-04 | Offline: `fetch_model_asset` öffnet keinen Client | unit (Socket-Fake) | `uv run pytest tests/test_model_download.py -x` | ✅ erweitern |
| PLAT-04 | Offline: Mitschnitt null Pakete nach außen; ohne Offline sichtbar (Positivkontrolle) | Container | docker.yml Schritt `ci/netcap/` | ❌ Wave 0 |
| RES-07 | THIRD-PARTY.md nennt jedes Laufzeitpaket aus uv.lock; README DE/EN/FR gleich; Admin-Abschnitt dreisprachig | unit | `uv run pytest tests/test_public_texts.py tests/test_trilingual.py -x` | ✅ erweitern |
| alle PHP-Seiten | Controller-Validierung, Admin-Pflicht | phpunit | `cd php && vendor/bin/phpunit` | ✅ erweitern |

### Sampling Rate
- **Per task commit:** Quick run command plus der jeweils neue Testdatei.
- **Per wave merge:** Full suite, ruff, pyright, vulture lokal; PHP-Tests.
- **Phase gate:** Full suite grün, docker.yml auf beiden Arches grün (OOM, Threads, Offline-Mitschnitt jeweils mit Positivkontrolle), Playwright-Admin 3 Breiten hell/dunkel, dann `/gsd:verify-work` und secure-phase.

### Wave 0 Gaps
- [ ] `backend/tests/test_resources.py`, `test_hardware.py`, `test_schedule.py`
- [ ] `ci/oom/oom_probe.py` + Fresser-Factory (nur CI, nie im Image)
- [ ] `ci/netcap/` Mitschnitt-Skript mit Positivkontrolle
- [ ] Thread- und RSS-Messschritt in `docker.yml` (beide Arches, `timeout-minutes` hart)
- [ ] Sprachclip in docker.yml bereitstellen (Muster "Fetch the speech clips" aus python.yml)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein (Nextcloud/AppAPI) | |
| V3 Session Management | nein | |
| V4 Access Control | ja | PHP-Routen ohne Lockerungs-Attribute (Admin + CSRF, T-01-32-Muster); ExApp-Routen `access_level ADMIN` |
| V5 Input Validation | ja | PHP strenge Prüfung, ExApp pydantic `strict`, `extra="forbid"`; Zeitzone aus Liste; Zahlen begrenzt |
| V6 Cryptography | ja (Integrität) | sha256 aus hashlib gegen feste Werte; nie selbst bauen |
| V10/V14 Supply Chain, Konfiguration | ja | feste Commits, sha256 je Teil und Ganzes, Allowlist je Sprung, https only, Dockerfile-Stage mit `sha256sum -c` |
| V8 Data Protection | ja | Offline ohne jede Verbindung; keine Telemetrie (`HF_HUB_OFFLINE`, `HF_HUB_DISABLE_TELEMETRY`); keine URLs in Logs |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Manipuliertes Modell (Release, CDN, Admin-Ablage) | Tampering | sha256 je Teil und Ganzes; Datei nie laden ohne Treffer |
| Umleitung auf fremden Host | Spoofing/Tampering | Host je Sprung prüfen bevor die Anfrage existiert (vorhanden) |
| Ressourcen-Erschöpfung (RAM, Platte, CPU) | DoS | Wächter vor Start, oom_score_adj, Thread-Grenze, Plattenprüfung vor Download |
| Nicht-Admin ändert Profil/Offline | Elevation | Admin-Pflicht beidseitig |
| Offline-Schalter wirkungslos beim Kaltstart | Information Disclosure (Metadaten: IP, Zeitpunkt) | `AVS_OFFLINE`, Prüfung vor jedem Versuch, Mitschnitt-Test |
| Signierte Asset-URLs in Logs | Information Disclosure | nur Codes loggen (bestehend) |
| Symlink-/Austausch-Angriff zwischen Prüfung und Laden einer abgelegten Datei | Tampering | Volume gehört uid 10001, Urteil an Größe + mtime_ns gebunden (bestehend in `_VERIFIED`); Image-Dateien `0444` |
| Speicherfresser-Probe gerät ins Image | Tampering | Probe nur unter `ci/`, Test in `test_dockerfile.py`, dass `ci/` nicht im Build-Kontext liegt (Kontext ist `backend/`) |

## Sources

### Primary (HIGH confidence)
- docs.github.com about-releases: 2-GiB-Grenze, 1000 Assets
- docs.kernel.org/filesystems/proc.html: oom_score_adj
- docs.kernel.org/admin-guide/cgroup-v2.html: cpu.max, memory.events, memory.oom.group, cpu.idle
- docs.docker.com/engine/containers/resource_constraints/: --memory-swap, --cpus
- faster-whisper v1.2.1 transcribe.py; opennmt.net CTranslate2 performance.html und models.Whisper
- CPython 3.13.13 Lib/os.py (process_cpu_count)
- docker-library/python 3.13/slim-trixie Dockerfile (tzdata)
- nextcloud/server config.sample.php (default_timezone)
- Hugging-Face-API Trees und Lizenzen; curl-Prüfung Redirect- und Range-Verhalten; GitHub-API Asset-Digests
- PyAV-Wheel av-19.0.2 manylinux x86_64, selbst entpackt
- Projektcode: memory_guard.py, engine/child.py, constants.py, parakeet.py, models/catalog.py, procure.py, nc.py, worker/preview.py, store/repo.py, main.py, settings.py, Dockerfile, info.xml, Admin.php, admin.php, SettingsController.php, Workflows
- SPIKE3-REPORT.md Abschnitte 1, 6, 11

### Secondary (MEDIUM confidence)
- kubernetes.io Blog 06.10.2026 (cgroup v2, memory.oom.group); KEP-5573
- docs.kernel.org sched-design-CFS (Gruppen-Scheduling)
- PyAV-Org/pyav-ffmpeg build-ffmpeg.py

### Tertiary (LOW confidence)
- Verhalten von `reuse lint` bei ungenutzten Lizenzen, Runner-Werkzeuge nsenter/dmesg (ungeprüft)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, weil fast alles im Projekt vorhanden ist
- Architecture: HIGH für Modellbezug und OOM-Mechanik, MEDIUM für Einstellungsweg (Entscheid, kein Fakt)
- Pitfalls: HIGH (aus Code und Doku belegt), Schwellenwerte MEDIUM

**Research date:** 2026-11-18
**Valid until:** 2026-12-18 (Paketversionen bewegen sich schnell; ctranslate2 und onnxruntime haben in den letzten 10 Tagen neue Releases bekommen)
