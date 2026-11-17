# Stack Research

**Domain:** Nextcloud External App (ExApp) für lokale Transkription und Volltextsuche in Audio- und Videodateien, CPU-only, amd64 + arm64
**Researched:** 2026-11-06
**Confidence:** MEDIUM bis HIGH (Versionen und Wheels direkt auf PyPI, GitHub und Hugging Face geprüft; Modellwahl und Einstellungen aus Spike 3 übernommen, nicht neu geöffnet; arm64-Leistung weiterhin ungemessen)

## Kernbefund vorab: Ohne PHP-Companion keine Unified Search

AppAPI bietet einer ExApp **keine** Registrierung eines Unified-Search-Providers. Geprüft am Quellcode von `nextcloud/app_api` (main, 06.11.2026): `lib/Service/UI` kennt nur `FilesActionsMenuService`, `InitialStateService`, `ScriptsService`, `SettingsService`, `StylesService`, `TopMenuService`; `lib/Listener` nur DeclarativeSettings, TaskProcessing, Files-Plugin, Menüeinträge, Sabre-Auth. Auch `nc_py_api 0.30.3` hat unter `ex_app/` nichts zu Search (nur `files_actions`, `resources`, `settings`, `top_menu`, `occ_commands`, `providers/task_processing`). Die offizielle Doku nennt Suchprovider nur über `registerSearchProvider` in einer PHP-App. **Konfidenz HIGH.**

Folge für die Roadmap: Die App braucht wie Findling **zwei Teile**: eine schlanke PHP-Companion-App (Suchprovider, Datei-Events, Crawl, Rechteprüfung, Content-Gateway, SRT/VTT-Download) und den Python-Container (Dekodieren, Erkennung, Index). Das ist exakt das Findling-Muster (`C:/Users/Student/nextcloud-search/php/lib/Search/Provider.php`, `php/lib/Controller/GatewayController.php`, `php/lib/Listener/FileEventListener.php`, `php/lib/BackgroundJobs/StorageCrawlJob.php`).

**Offene Owner-Entscheidung, gleich zu Beginn:** Das Zertifikat ist für die ID `audio_video_search` erteilt (05.11.2026) und als ExApp beantragt. Findling nutzt `findling` (PHP) + `findling_backend` (ExApp). Laut Memory-Notiz braucht eine Companion-App einen eigenen Antrag für die zweite ID. Vorschlag nach Findling-Muster: PHP-App = `audio_video_search` (Store-Name "Audio & Video Search", Nutzer sieht diese), ExApp = `audio_video_search_backend` (neuer Zertifikatsantrag, Merge dauert erfahrungsgemäß Tage, also früh stellen). Das berührt `appinfo/info.xml`, Image-Name und `release.yml` des Skeletons.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Konfidenz |
|------------|---------|---------|-----------------|-----------|
| Python | 3.13 (Basis `python:3.13-slim-trixie`, per Digest gepinnt, wie Skeleton) | Laufzeit des Containers | Alle nativen Abhängigkeiten haben cp313-Wheels für `manylinux x86_64` und `aarch64` (unten einzeln geprüft); glibc 2.41 von trixie erfüllt manylinux_2_28 und 2_35 | HIGH |
| nc-py-api[app] | 0.30.3 (aktuell, 11.08.2026) | AppAPI-Vertrag: signierte Anfragen, `/enabled`, `/heartbeat`, `/init`, `set_init_status`, deklarative Einstellungen | Schon im Skeleton gepinnt; nur die Async-API nutzen (Sync-API fällt in 0.31.0) | HIGH |
| FastAPI | 0.162.0 (23.10.2026) | HTTP-Schnittstelle des Containers | Skeleton-Pin, kein Grund zu wechseln | HIGH |
| sherpa-onnx | 2.0.1 (27.10.2026), zieht `sherpa-onnx-core==2.0.1` | Parakeet-TDT-0.6B-v3 int8 (`OfflineRecognizer.from_transducer`, `model_type="nemo_transducer"`, `decoding_method="greedy_search"`) und Silero VAD (`VadModelConfig`) | Spike 1 bis 3 gemessen; Wheels `cp313-manylinux2014_x86_64` und `cp313-manylinux2014_aarch64` vorhanden; kein PyTorch, kein Compiler. `sherpa-onnx-core` bringt ein **eigenes** `libonnxruntime.so` (27 MB, im Wheel nachgesehen) | HIGH |
| faster-whisper | 1.2.1 (31.10.2025, letzter Release; Repo aktiv, Commits bis 02.11.2026) | Whisper large-v3-turbo und large-v3 mit `compute_type="int8"`, `beam_size=1`, `condition_on_previous_text=False`, `vad_filter=True`, `word_timestamps=True` | Gemessen in Spike 3; reines Python-Wheel (`py3-none-any`), läuft also auf beiden Architekturen, sobald CTranslate2 läuft. Release ist über ein Jahr alt: auf 1.2.1 festnageln, ein Folge-Release erst nach Schnell-Gate übernehmen | HIGH (Funktion), MEDIUM (Pflegezustand) |
| CTranslate2 | 4.8.5 (02.11.2026) | Inferenz-Engine unter faster-whisper | Wheels `cp313-manylinux_2_28_x86_64` (42,7 MB) und `cp313-manylinux_2_28_aarch64` (19,1 MB) vorhanden. Auf ARM64 laut offizieller Doku int8 über das **Ruy**-Backend, nur CPU; `int8_float32` usw. werden auf ARM implizit zu `int8_float32`. Gleiche Version wie im Spike, also gemessen | HIGH (Verfügbarkeit), LOW (arm64-Tempo, ungemessen) |
| onnxruntime | 1.31.1 (26.10.2026) | Pflichtabhängigkeit von faster-whisper (dessen eigener Silero-VAD v6 aus `faster_whisper/assets`) | Wheels cp313 für beide Architekturen. Nicht für Parakeet benutzen, das läuft über das gebündelte ORT von sherpa-onnx | HIGH |
| ffmpeg (CLI, statisch, LGPL) | BtbN FFmpeg-Builds, Release-Zweig `n8.1` oder `n9.0`, Variante `linux64-lgpl` und `linuxarm64-lgpl`, aus einem **Monatsend-Autobuild** | Dekodieren jedes Containers/Codecs zu 16 kHz Mono `s16le`/`f32le` auf stdout | Projektentscheidung (Spike 1). BtbN baut beide Architekturen täglich; Assets für beide Arches im aktuellen Release geprüft. **Wichtig:** `latest` wandert, tägliche Builds werden nach 14 Tagen gelöscht, nur der letzte Build jedes Monats bleibt zwei Jahre. Deshalb Monatsend-Tag + sha256 je Architektur im Dockerfile, genau wie frpc im Skeleton. Release-Zweig statt master | MEDIUM |
| Tantivy (tantivy-py) | 0.26.2 (Findling-Pin); 0.27.0 erschienen am 22.10.2026 | Volltextindex über Transkript-Segmente, BM25, Snippets, deutsches Stemming und Komposita | Findling hat Analyzer für de/en/fr (Snowball), Kompositazerlegung, Schema-Versionierung und Umbau-ohne-Reindex bereits gebaut und an 0.26 nachgemessen (`backend/src/findling/index/analyzer.py`, `schema.py`, `open.py`, `rebuild.py`). Mit 0.26.2 starten, damit der Code 1:1 übernommen werden kann; 0.27.0 (pyo3 0.29, musllinux) als eigener Schritt mit Findling zusammen. Wheels `abi3` für beide Architekturen | HIGH (Wahl), MEDIUM (Versionsschritt) |
| SQLite (stdlib `sqlite3`, WAL) | mit Python 3.13 | Quelle der Wahrheit: Datei-Zustand, Transkriptversionen (Vorschau/Endtext), Wortlisten mit Zeit und Konfidenz, Job-Stufen, Fehlgründe | Tantivy ist nur abgeleiteter Index und jederzeit aus SQLite neu baubar. Findling-Muster `store/repo.py` + `store/schema.sql` (Zustand in `$APP_PERSISTENT_STORAGE/state.db`, Pragmas je Verbindung, WAL-Prüfung) | HIGH |
| PHP-Companion | PHP >= 8.2, Nextcloud 33 bis 35, keine Composer-Laufzeitabhängigkeit | `registerSearchProvider` (+ `IFilteringProvider`), Node-/Share-/Gruppen-Events, Mount-Crawl als `QueuedJob`, Content-Gateway per Datei-ID, Proxy über `OCA\AppAPI\PublicFunctions::exAppRequest` | Einziger Weg in die Unified Search (siehe oben); Findling-Muster ist ausgeliefert und gehärtet (Gruppenordner-ACL über `ReaderContext::actAs`, `readableFile`, keine Pfade in Logs) | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Konfidenz |
|---------|---------|---------|-------------|-----------|
| numpy | 2.5.4 (Findling-Pin, aktuell) | PCM-Puffer zwischen ffmpeg und Engines | Immer; beide Engines nehmen `float32`-Arrays | HIGH |
| jiwer | 4.0.0 (zieht `rapidfuzz`) | Wortalignment für ROVER (`jiwer.process_words(...).alignments`) | **Laufzeitabhängigkeit**, nicht nur Test: Spike 3 `spike3/scripts/combine.py:23-27` aligniert damit; dieselbe Bibliothek und Version halten, sonst ist der gemessene ROVER-Gewinn (-4,6 % / DE -12 %) nicht mehr belegt. Gleich für das Gate (WER) | HIGH |
| av (PyAV) | 19.0.2, kommt transitiv über faster-whisper | Nur Importpflicht: `faster_whisper/audio.py` importiert `av` auf Modulebene | Nie selbst zum Dekodieren benutzen; wir geben faster-whisper numpy-Arrays. Lizenzhinweis siehe "What NOT to Use" | HIGH |
| huggingface-hub | transitiv über faster-whisper (aktuell 2.4.0) | Nur Importpflicht (`faster_whisper/utils.py`) | Nie zum Laden benutzen; `WhisperModel` mit lokalem Verzeichnis aufrufen und `HF_HUB_OFFLINE=1` setzen, damit kein Netzaufruf möglich ist. Version in `uv.lock` festhalten | HIGH |
| tokenizers | 0.23.3 (transitiv, Findling-Pin) | Whisper-Tokenizer | automatisch | HIGH |
| niquests oder httpx | niquests 3.21.2 kommt mit nc-py-api; httpx 0.28.1 wie Findling | Modell-Download mit festem sha256 und Host-Allowlist; Datei-Stream vom Content-Gateway | Für den Gateway-Stream das Findling-Muster `nc/client.py:363 fetch_file_stream` (eigener gestreamter httpx-Aufruf, Schreiben im Thread) übernehmen | HIGH |
| eigene SRT/VTT-Ausgabe | keine Bibliothek | Untertitel aus Wort-Zeitstempeln | Beide Formate sind trivial; die Arbeit steckt im Zeilenumbruch (max. 2 Zeilen, ca. 42 Zeichen, Mindest-/Höchstdauer je Untertitel), nicht im Format. `webvtt-py 0.7.0` und `srt 3.5.3` (letzter Release 2023) bringen dafür nichts | HIGH |
| Findling-Bausteine (kopiert, nicht importiert) | Stand Findling 1.6.x | RAM-Wächter (`backend/src/findling/memory_guard.py`: cgroup-v2 `memory.max` minus `anon`, gedeckelt durch `MemAvailable`; `memory.events` für OOM-Erkennung), Hardware-Leser (`hardware.py`), Pause/Backup-Halt (`worker/pause.py`), Reconcile (`worker/reconcile.py`, `nc/files.py`), Queue-Claim mit Lease (`nc/queue.py`) | Von Anfang an, statt neu zu erfinden; stdlib-only, getestet | HIGH |

### Modelle (Quellen, Pins, Ablage)

| Modell | Quelle (fest auf Commit/Asset) | Größe | sha256 (Spike-3-Gate) | Lizenz |
|---|---|---|---|---|
| Parakeet-TDT-0.6B-v3 int8 | HF `csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` @ `2bda32ec70b097a55adaa07d9a7173915b43cc78`, Einzeldateien `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx`, `tokens.txt` | 652 + 12 + 6 MB | encoder `acfc2b44...2247` (stimmt mit HF-LFS überein), decoder `179e50c4...db4e`, joiner `3164c13f...48b3` | CC-BY-4.0, Namensnennung NVIDIA Pflicht |
| Silero VAD (für sherpa-onnx) | GitHub `k2-fsa/sherpa-onnx` Release `asr-models`, Asset `silero_vad.onnx` | 0,64 MB | `9e2449e1...1fd6` (GitHub-Digest stimmt) | MIT |
| Whisper large-v3-turbo (CT2) | HF `deepdml/faster-whisper-large-v3-turbo-ct2` @ `4df90f75321148c3a29a9e2351b7ddf8f5b115a8` (`model.bin`, `config.json`, `tokenizer.json`, `vocabulary.json`, `preprocessor_config.json`) | 1,62 GB | `e76620f8...18da` | MIT |
| Whisper large-v3 (CT2) | HF `Systran/faster-whisper-large-v3` @ `edaa852ec7e145841d8ffdb056a99866b5f0a478` | 3,09 GB | `69f74147...d4f1` | MIT |

Ablage und Laden:
- **Nicht ins Image.** Image bleibt klein (Basis + ca. 150 MB Wheels + ffmpeg), Dependabot-Rebuilds und arm64-CI bleiben schnell. Modelle liegen unter `$APP_PERSISTENT_STORAGE/models/<name>/<sha256>/` und überleben Updates.
- **`/init` lädt nur Parakeet + Silero** (ca. 0,67 GB) mit `set_init_status`-Fortschritt. AppAPI bricht `/init` nach `init_timeout` ab, Standard **40 Minuten** (`app_api/lib/BackgroundJob/ExAppInitStatusCheckJob.php:39`); 3+ GB Whisper-Modelle dürfen deshalb nicht im `/init` hängen. turbo und large-v3 lädt der Hintergrund-Worker nach dem Aktivieren, nur wenn das gewählte Profil sie braucht (large-v3 nur Qualität + DE), mit ehrlichem Status.
- **Eigener Downloader statt `nc_py_api.fetch_models_task`**: Die nc_py_api-Routine prüft sha256 nur gegen den ETag des Servers, nicht gegen einen festen Wert, und kann keine Commit-Pins für Einzeldateien sauber ausdrücken. Eigener Downloader: feste URL mit Commit, Host-Allowlist (Findling-Muster `ASSET_HOSTS`, `nc/client.py` ab Zeile 493), Fortsetzen über `.tmp`, sha256 gegen den eingebauten Wert, `os.replace` erst nach Treffer, sonst verwerfen.
- **Offline-/Air-Gap-Weg**: Admin legt dieselben Dateien in den Modellordner; Prüfung über denselben sha256. Doku in DE/EN/FR.
- **Datenschutz**: Diese Downloads sind die einzigen ausgehenden Verbindungen; sie senden nichts außer der Dateianfrage. `HF_HUB_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1` setzen; faster-whisper bekommt immer einen lokalen Pfad.
- **Hugging-Face-Weiterleitungen**: `resolve/<commit>/...` leitet für LFS-Dateien auf CDN-Hosts weiter (heute Xet-/LFS-Hosts unter `hf.co`). Die Allowlist muss diese Hosts enthalten; vor dem Bau am echten Redirect prüfen. **Konfidenz MEDIUM.**

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv 0.11.7 (Image), `uv_build` | Lock und Build | Skeleton unverändert; `uv.lock` hält auch die transitiven `av`, `huggingface-hub`, `rapidfuzz` fest |
| ruff 0.17.3, pyright 1.1.414 (basic), vulture 2.16, pytest 9.2.0 | Qualitäts-Gates | Owner-Regel, wie Skeleton |
| GitHub Actions `ubuntu-24.04-arm` | Native arm64-Builds und Smoke-Tests | Skeleton `docker.yml` nutzt bereits native arm64-Runner. Dort auch das **Schnell-Gate** (core_* + ns_* + gaps_*) je Build laufen lassen: belegt Funktion und WER auf arm64, nicht Pi-/N100-Tempo |
| Gate-Skripte aus Spike 3 | Release-Gate | `spike3/scripts/fetch3.py`, `fetch_long.py`, `fetch_vox.py`, `prep3.py`, `gate.py` + `release-gate-2026-11-06.json` (sha256 `101fa929...`) ins Repo; Audiodaten nie |
| PHP: phpunit 11.5.x, Findling-Muster `php.yml` gegen `stable34` | Companion-Tests | wie Findling (`php/composer.json`) |

## Installation

```bash
# Container (pyproject.toml, alles exakt gepinnt)
uv add "nc-py-api[app]==0.30.3" "fastapi==0.162.0" \
       "sherpa-onnx==2.0.1" "faster-whisper==1.2.1" "ctranslate2==4.8.5" \
       "onnxruntime==1.31.1" "numpy==2.5.4" "tantivy==0.26.2" \
       "jiwer==4.0.0" "httpx==0.28.1"

# Dev wie Skeleton
uv add --dev ruff==0.17.3 pyright==1.1.414 vulture==2.16 pytest==9.2.0 pytest-asyncio pytest-cov
```

```dockerfile
# ffmpeg: eigener Build-Stage wie frpc; Tag = letzter Autobuild eines Monats (bleibt 2 Jahre)
FROM ${BASE_IMAGE} AS ffmpeg
ARG TARGETARCH
RUN set -eux; \
    FF_TAG=autobuild-YYYY-MM-DD-HH-MM; FF_BRANCH=n8.1; \
    case "${TARGETARCH}" in \
      amd64) FF_ARCH=linux64;    FF_SHA256=<sha256 amd64> ;; \
      arm64) FF_ARCH=linuxarm64; FF_SHA256=<sha256 arm64> ;; \
      *) exit 1 ;; esac; \
    curl -fsSL --proto '=https' -o /tmp/ff.tar.xz \
      "https://github.com/BtbN/FFmpeg-Builds/releases/download/${FF_TAG}/ffmpeg-${FF_BRANCH}-latest-${FF_ARCH}-lgpl-${FF_BRANCH#n}.tar.xz"; \
    echo "${FF_SHA256}  /tmp/ff.tar.xz" | sha256sum -c -; \
    tar -C /tmp -xJf /tmp/ff.tar.xz; install -m 0755 /tmp/ffmpeg-*/bin/ffmpeg /tmp/ffmpeg-*/bin/ffprobe /usr/local/bin/
# Laufzeit-ENV
ENV HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 OMP_NUM_THREADS=2
```

(Asset-Namensschema gegen den gewählten Tag prüfen; im aktuellen Release heißen sie `ffmpeg-n8.1-latest-linux64-lgpl-8.1.tar.xz` und `ffmpeg-n8.1-latest-linuxarm64-lgpl-8.1.tar.xz`.)

## Wie die Bausteine zusammenspielen (Stack-Sicht)

1. **Dateien finden (PHP):** `NodeCreated/Written/Renamed/Copied/Deleted/Touched`, `MoveToTrash`, `NodeRestored`, Share- und Gruppen-Events schreiben in eine Queue-Tabelle der Companion (Findling `FileEventListener.php`, `QueueService`); Erstbestand und externe Speicher per `StorageCrawlJob` je Mount in Scheiben über den Datei-Cache. Filter auf `audio/*`, `video/*` (plus Sonderfälle wie `application/ogg`, `.m4a`, `.mkv`, `.webm` ohne sauberen MIME-Typ). Admin-Ausschlüsse (Nutzer, Gruppen, Ordner, externe Speicher) vor dem Einreihen, Findling `ExclusionService`.
2. **Externe Speicher:** Änderungen, die außerhalb von Nextcloud passieren (SMB/S3 direkt), lösen **keine** Events aus. Abhilfe ist der periodische Abgleich über `etag`/`mtime` im Datei-Cache (Findling `worker/reconcile.py` + `nc/files.py`); der Datei-Cache selbst wird nur aktuell, wenn Nextcloud den Speicher scannt (Zugriff oder `occ files:scan`). In der Admin-Doku offen sagen.
3. **Holen:** Container claimt Arbeit mit Lease (Findling `nc/queue.py`), streamt die Datei über das Content-Gateway (`GET /files/{fileId}?userId=...`, Rechte über `ReaderContext::actAs` + `readableFile`) in eine Temp-Datei auf dem Volume. Kein Pfad in Logs.
4. **Dekodieren:** `ffmpeg -nostdin -hide_banner -v error -i <tmp> -map 0:a:0 -vn -sn -dn -ac 1 -ar 16000 -f f32le pipe:1` im Unterprozess mit Zeitlimit; `ffprobe` vorher für Dauer und Audiospur (Video ohne Ton = "übersprungen, keine Tonspur"). Lange Dateien in Stücken von ca. 10 min an faster-whisper (Spike 3, Abschnitt 6).
5. **Erkennen:** je Engine ein **eigener Worker-Unterprozess** (Parakeet-Prozess importiert nie `faster_whisper`, Whisper-Prozess nie `sherpa_onnx`), immer nur ein Modell geladen, Start nur bei `headroom >= Bedarf + 1 GB` (Bedarf aus Spike 3: Parakeet 1,4 GB, turbo 2,0 bis 2,5 GB, large-v3 4,0 bis 4,5 GB). Threads aus `cpu.max` der cgroup (Findling `hardware.py`), Standard 2.
6. **Kombinieren:** ROVER (Spike 3 Abschnitt 7, Parameter 0,15 / 0,2 / 0,6) und Schluck-Wächter in reinem Python + jiwer.
7. **Speichern und ersetzen:** neue Transkriptversion in einer SQLite-Transaktion, danach Tantivy `delete_term(file_id)` + neue Segment-Dokumente + `commit`. Leser sehen bis zum Commit die alte Version, danach die neue: die Suche bleibt durchgehend verfügbar.
8. **Suchen (PHP -> Container):** Provider fragt den Container über `exAppRequest`, bekommt Kandidaten `(file_id, segment_start, snippet)`, prüft jede Datei für den aktuellen Nutzer mit `readableFile` und gibt nur sichtbare Treffer aus (Findling `SearchService`, `ApprovedHit`). Entzogene Rechte wirken dadurch sofort.
9. **SRT/VTT:** Companion-Route (Datei-Aktion im Files-Menü), die nach Rechteprüfung die Untertitel vom Container holt und als Download ausliefert. Kein Schreiben in Nutzerordner in v1 (Findling hält eine Read-only-Grenze, die beibehalten werden sollte).

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| PHP-Companion für Events + Suche | AppAPI-Webhooks über `webhook_listeners` (nc_py_api `webhooks.py`) für Node-Events | Nur wenn es nie eine Unified Search gäbe. Da die Companion ohnehin nötig ist, wäre das ein zweiter Weg in dieselbe Queue; Findling verwirft ihn ausdrücklich (asynchron, keine Share-Events, `FileEventListener.php` Kopfkommentar) |
| Tantivy 0.26.2 | SQLite FTS5 | Wenn auf Stemming/Komposita verzichtet würde. FTS5 hat nur `porter` (Englisch); "Haushaltsplan" fände "Haushalt" nicht. Für eine deutschsprachige Behördensuche nicht gut genug |
| Tantivy | Meilisearch/OpenSearch als Sidecar | Nie für dieses Zielsystem: zweiter Dienst, 100+ MB Leerlauf, kein deutscher Stemmer bei Meilisearch |
| ffmpeg-CLI im Unterprozess | Dekodieren mit PyAV im Worker (ist ohnehin installiert) | Wenn das Image-Budget sehr knapp wird. Nachteil: Absturz im Decoder trifft den Erkennungsprozess, keine harte Zeitgrenze, und die PyAV-Wheels enthalten GPL-Codecs (x264/x265). Projektentscheidung ist der LGPL-Build |
| BtbN statisch, Monatsend-Tag | Debian-Paket `ffmpeg` aus trixie | Wenn automatische Sicherheitsupdates über die Basis-Digests wichtiger werden als LGPL und Imagegröße. Debian baut mit `--enable-gpl` und zieht viele Bibliotheken nach. Mit AGPL-3.0 lizenzrechtlich vereinbar, widerspricht aber der Spike-Entscheidung |
| Eigener Downloader mit festem sha256 | `nc_py_api` `models_to_fetch` / `huggingface_hub.snapshot_download` | Nur für Prototypen; beide prüfen nicht gegen einen festen Hash |
| Modelle beim Start laden | Parakeet ins Image backen (+0,67 GB) | Wenn viele Installationen keinen Zugang zu GitHub/Hugging Face haben. Dann nur Parakeet + Silero ins Image, Whisper weiter per Download oder Admin-Ablage |
| SQLite + eigene Stufen-Tabelle als Job-Zustand | Celery, RQ, Redis, Dramatiq | Nie: ein Container, ein Prozessbaum, zweiter Dienst wäre nur RAM-Kosten und Fehlerquelle |
| Audio-Spracherkennung über `WhisperModel.detect_language` je Fenster | Text-Spracherkennung (`lingua-language-detector` 2.2.0) | lingua-Wheel ist 170 MB groß; für 3 Sprachen reicht Whisper-LID (ist in Ausgewogen/Qualität ohnehin geladen) oder eine Stoppwort-Quote mit den Findling-Listen. Für das Schnell-Profil noch zu messen |
| turbo-Modell wie gemessen (`model.bin` float16, Umwandlung beim Laden) | vorab nach int8 umgewandeltes CT2-Modell | Würde die Ladespitze (1,9 GB, entsteht laut Spike 3 bei float16 nach int8) senken und mehr Geräte für Ausgewogen öffnen. Nur übernehmen, wenn das Release-Gate dieselbe WER zeigt; Umwandlung braucht `transformers`/`torch`, also nur in einem eigenen CI-Schritt, nie im Image |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Externe STT- oder Embedding-Dienste (OpenAI, Deepgram, HF Inference, Assistant mit Cloud-Backend) | Owner-Regel: kein Audio, kein Text verlässt den Server | sherpa-onnx + faster-whisper lokal |
| `huggingface_hub`-Download zur Laufzeit, `WhisperModel("large-v3")` mit Namen | löst Netzaufrufe aus, Revision nicht gepinnt | lokaler Pfad + `HF_HUB_OFFLINE=1` |
| `BatchedInferencePipeline`, `beam_size=5`, `condition_on_previous_text=True`, `initial_prompt`, `vad_filter=False`, Parakeet `modified_beam_search`/Hotwords | Spike 3 gemessen: gleich oder signifikant schlechter, ohne VAD Halluzinationen | Spike-3-Standardwerte (Abschnitt 11), als Konstanten mit Test festhalten |
| Canary-1B-v2, whisper.cpp, Vosk, openai-whisper (PyTorch) | Spike 2: kein gesicherter Vorsprung / keine Wortzeiten; PyTorch-Stack ist Gigabytes groß und langsamer auf CPU | gemessene Kombination |
| pyannote (Diarisierung) | v2, Modell gated, ungemessen, PyTorch | später |
| Beide Engines in einem Prozess | sherpa-onnx bringt eigenes `libonnxruntime.so`, das `onnxruntime`-Wheel ein zweites; Symbolkonflikte möglich [Schätzung]. Außerdem geben CTranslate2- und ORT-Speicherarenen RAM nicht zuverlässig an das System zurück | ein Worker-Unterprozess je Engine und Job-Block, danach beenden |
| `RLIMIT_AS` als RAM-Grenze | ORT und CTranslate2 reservieren viel virtuellen Speicher; harte AS-Grenze führt zu Abstürzen trotz freiem RAM [Schätzung] | Vorab-Prüfung über cgroup-Headroom (Findling `memory_guard.py`) + RSS-Beobachtung + Kill des Workers |
| BtbN `latest` oder tägliche Tags | `latest` wandert, Tagesbuilds verschwinden nach 14 Tagen: Build nicht reproduzierbar, sha256 bricht | Monatsend-Autobuild + sha256 je Architektur |
| BtbN `gpl`-Varianten | unnötig (nur Dekodieren), widerspricht LGPL-Entscheidung | `lgpl` |
| Eigene App-Seite mit Medienübersicht in v1 | Owner: v1 nur Unified Search plus minimale Abspielansicht für genau einen Treffer (Owner 06.11.) | Treffer-Link auf die Abspielroute `/apps/audio_video_search/play/{fileId}?t=` |
| `webvtt-py`, `srt`, `pysubs2` | Formate trivial; Bibliothek löst das eigentliche Problem (Zeilenumbruch, Lesedauer) nicht | ca. 100 Zeilen eigener Writer mit Tests |
| Celery/Redis/RabbitMQ | zweiter Dienst im RAM-knappen Container | SQLite-Stufen + Companion-Queue mit Lease |

Lizenzhinweis zu PyAV: Die PyAV-Wheels bündeln FFmpeg mit `--enable-libx264`/`--enable-libx265` (geprüft in `PyAV-Org/pyav-ffmpeg/scripts/build-ffmpeg.py`), also GPL-Bestandteile. Sie lassen sich nicht weglassen, weil faster-whisper `av` beim Import lädt. Mit AGPL-3.0-or-later vereinbar (GPLv2-or-later von x264 ist mit v3 kombinierbar), muss aber in `THIRD-PARTY.md` stehen, und die Pflicht zur Quellenangabe für das ausgelieferte Image gilt wie bei Findling (`backend/tests/test_corresponding_source.py` als Vorlage). Gleiches für den BtbN-LGPL-Build. **Konfidenz MEDIUM** (Lizenzlage, keine Rechtsberatung).

## Stack Patterns by Variant

**Wenig RAM (unter ca. 4 GB frei für den Container):**
- nur Schnell-Profil (Parakeet + Wächter, selektives turbo-Nachrechnen nur wenn Headroom für turbo reicht)
- weil Spike 3: turbo-Spitze 1,9 bis 3,4 GB; Parakeet 1,2 bis 1,7 GB

**4 bis 8 GB:**
- Ausgewogen (Standard), turbo strikt in 10-min-Stücken
- weil turbo ohne Stückelung auf 3,4 GB steigt

**Ab 8 GB frei:**
- Qualität wählbar, large-v3 nur für deutsche Dateien
- weil large-v3 bis 4,5 GB braucht und nur DE gewinnt (Spike 3 Abschnitt 11)

**arm64 (Pi 5, Ampere, Graviton):**
- gleicher Stack, gleiche Wheels; CTranslate2 nutzt Ruy für int8
- Profil-Vorwahl darf erst nach echter Messung auf Pi 5 / N100 von RAM-only auf RAM+Tempo umgestellt werden (Owner-Vorgabe: vor Release messen)

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| faster-whisper 1.2.1 | ctranslate2 `>=4.0,<5` (4.8.5), onnxruntime `>=1.14,<2` (1.31.1), tokenizers `<1` (0.23.3), av `>=11` (19.0.2), huggingface-hub `>=0.21` | Spike 3 lief mit faster-whisper 1.2.1 + CTranslate2 4.8.5 auf Windows; die Linux-Kombination mit huggingface-hub 2.x (zieht `httpx2`) ist nicht gemessen, nur importiert wird es. Im ersten Container-Build prüfen |
| sherpa-onnx 2.0.1 | sherpa-onnx-core 2.0.1 (exakt) | eigenes ORT gebündelt; Version des gebündelten ORT unbekannt, unabhängig vom `onnxruntime`-Wheel |
| ctranslate2 4.8.5 | Python 3.9 bis 3.15, manylinux_2_28 | trixie (glibc 2.41) passt |
| onnxruntime 1.31.1 | Python >= 3.11, manylinux_2_28 | passt |
| av 19.0.2 | Python >= 3.12, abi3 | passt zu 3.13 |
| tantivy 0.26.2 | Python >= 3.11 abi3; Index-Format | Schema/Analyzer-Versionen im `meta`-Table wie Findling, sonst stumme leere Suche nach Upgrade (Findling-Architekturrecherche, Befund "Zweitens") |
| nc-py-api 0.30.3 | starlette >= 1.0.1 (Constraint im Skeleton), filelock-Override >= 4.2.1 | unverändert übernehmen |
| Nextcloud 33 bis 35 | AppAPI mit HaRP, PHP >= 8.2 | Viewer ist ab 2026 eine Bibliothek (`nextcloud-libraries/nextcloud-viewer`), siehe Lücke unten |

## Lücken, die die Roadmap kennen muss

1. **Sprung auf die Zeitstelle:** Der Nextcloud-Viewer hat **keinen** URL-Parameter für eine Startzeit. Issue `nextcloud/viewer#2176` wurde am 25.10.2026 als "not planned" geschlossen, Begründung: Viewer wird nicht mehr als eigene App entwickelt, Code liegt jetzt in der Bibliothek `@nextcloud/viewer`. Der Treffer-Link muss also über ein eigenes kleines Skript der Companion (lädt auf der Files-Seite, liest z. B. `#t=123` und setzt `currentTime` am Video/Audio-Element des Viewers) oder eine schlichte eigene Abspielroute laufen. Eigene Recherche/Spike in der Such-Phase, gegen NC 33, 34 und 35 testen. **Konfidenz HIGH für das Fehlen, LOW für den Lösungsweg.**
2. **Zweite App-ID / Zertifikat** für die Companion bzw. das Backend (siehe Kernbefund). Früh beantragen.
3. **arm64- und N100-Tempo** ungemessen; CTranslate2-Ruy auf Cortex-A76 kann deutlich vom x86-Wert abweichen.
4. **Hugging-Face-CDN-Hosts** für die Allowlist am echten Redirect bestimmen.
5. **ROVER auf normalisierten Tokens:** `combine.py` arbeitet auf klein geschriebenen Wörtern ohne Satzzeichen (`n2`). Für Anzeige, Snippets und Untertitel braucht der Produktivcode die Originalwörter mit Groß-/Kleinschreibung und Satzzeichen; die Abbildung normalisiertes Token -> Originalwort muss gebaut und gegen das Gate geprüft werden (WER darf sich nicht ändern).
6. **Untertitel neben der Datei** (z. B. `.vtt`, die der Viewer als Spur lädt): ob und in welchem Namensschema der Viewer Untertitel-Spuren findet, ist nicht geprüft; v1 liefert Download.

## Sources

- PyPI JSON-API, abgefragt 06.11.2026: sherpa-onnx 2.0.1 / sherpa-onnx-core 2.0.1 (Wheels cp313 x86_64 + aarch64), faster-whisper 1.2.1 (requires_dist), ctranslate2 4.8.5, onnxruntime 1.31.1, av 19.0.2, numpy 2.5.4, tantivy 0.27.0 (+0.26.2), nc-py-api 0.30.3, fastapi 0.162.0, jiwer 4.0.0, huggingface-hub 2.4.0, lingua-language-detector 2.2.0, webvtt-py 0.7.0, srt 3.5.3 (HIGH)
- Wheel-Inhalt `sherpa_onnx_core-2.0.1-py3-none-manylinux2014_x86_64.whl`: enthält `sherpa_onnx/lib/libonnxruntime.so` (HIGH)
- https://opennmt.net/CTranslate2/quantization.html und https://opennmt.net/CTranslate2/hardware_support.html: int8 auf AArch64 über Ruy, aarch64-Wheels nur CPU (HIGH)
- GitHub `OpenNMT/CTranslate2` Releases 4.8.2 bis 4.8.5; `SYSTRAN/faster-whisper` Releases und Commits bis 02.11.2026 (HIGH)
- `faster_whisper/audio.py`, `utils.py`, `vad.py` @ v1.2.1: Modul-Importe von `av`, `huggingface_hub`, ORT-VAD (HIGH)
- GitHub `BtbN/FFmpeg-Builds` README (Retention: Monatsletzter 2 Jahre, 14 Tagesbuilds, `latest` wandert; lgpl ohne x264/x265) und Release-Assets vom 05.11.2026 für linux64/linuxarm64 lgpl, n8.1 und n9.0 (HIGH)
- `PyAV-Org/pyav-ffmpeg/scripts/build-ffmpeg.py`: `--enable-libx264`, `--enable-libx265` (MEDIUM, Build-Skript, nicht Wheel-Inhalt geprüft)
- Hugging Face API: `deepdml/faster-whisper-large-v3-turbo-ct2` @ 4df90f75, `Systran/faster-whisper-large-v3` @ edaa852e, `csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` @ 2bda32ec, LFS-sha256 stimmen mit Spike-3-Gate überein (HIGH)
- GitHub `k2-fsa/sherpa-onnx` Release `asr-models`: `silero_vad.onnx` Digest = Spike-3-Wert (HIGH)
- `nextcloud/app_api` Quellbaum `lib/Service`, `lib/Service/UI`, `lib/Listener`, `lib/BackgroundJob/ExAppInitStatusCheckJob.php` (init_timeout 40 min) (HIGH)
- https://nextcloud.github.io/app_api/tech_details/api/index.html, https://docs.nextcloud.com/server/33/developer_manual/digging_deeper/search.html: Suchprovider nur über `registerSearchProvider` (HIGH)
- `nc_py_api 0.30.3` lokal (`ex_app/integration_fastapi.py:193-320` Download-Logik, `webhooks.py`) (HIGH)
- `nextcloud/viewer#2176` (geschlossen not_planned 25.10.2026, Kommentar susnux) (HIGH)
- Findling-Quellen: `C:/Users/Student/nextcloud-search/php/lib/Listener/FileEventListener.php`, `php/lib/BackgroundJobs/StorageCrawlJob.php`, `php/lib/Controller/GatewayController.php`, `php/lib/AppInfo/Application.php:55-135`, `backend/src/findling/memory_guard.py`, `backend/src/findling/worker/pause.py`, `backend/src/findling/nc/queue.py`, `backend/src/findling/nc/client.py:363`, `backend/src/findling/store/schema.sql`, `.planning/research/ARCHITECTURE.md` (HIGH)
- Spike 3: `C:/Users/Student/audio-video-spike-2026-11-04/SPIKE3-REPORT.md`, `spike3/scripts/combine.py` (Modelle, Einstellungen, RAM, ROVER) (HIGH, gemessen)

---
*Stack research for: Nextcloud-ExApp Audio & Video Search (lokale Transkription + Unified Search)*
*Researched: 2026-11-06*
