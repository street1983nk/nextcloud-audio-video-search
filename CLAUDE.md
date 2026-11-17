<!-- GSD:project-start source:PROJECT.md -->
## Project

**Audio & Video Search**

Nextcloud-App aus zwei Teilen (PHP-App `audio_video_search` für Suche, Ereignisse, Rechte und Abspielansicht; ExApp `audio_video_search_backend` für Dekodieren, Erkennung und Index), die alle Audio- und Videodateien einer Instanz automatisch und vollständig lokal transkribiert und den gesprochenen Text über die normale Nextcloud-Suche mit Sprung auf die Zeitstelle findbar macht. Zielgruppe: Selfhoster, kleine Organisationen, Behörden und Schulen, die ihre Aufnahmen (Sitzungen, Interviews, Vorlesungen, Videos) durchsuchen wollen, ohne Inhalte an einen Cloud-Dienst zu geben. Sprachen DE, EN, FR.

**Core Value:** Nach der Installation werden alle Audio- und Videodateien ohne Konfiguration lokal transkribiert und sind in der Nextcloud-Suche mit Zeitmarke findbar, mit der bestmöglichen Transkriptqualität, die auf der vorhandenen Hardware sicher läuft. Kein Inhalt verlässt den Server.

### Constraints

- **Datenschutz**: Kein Audio, kein Text, keine Telemetrie verlässt den Server; Modelle werden einmal aus öffentlichen Quellen geladen oder ins Image gelegt: Owner-Regel
- **Qualität vor Speed**: Standard nach Qualität; Entwicklungsaufwand ist kein Grund, eine messbar bessere Lösung wegzulassen; jede Qualitätsentscheidung mit WER-Messung belegen: Owner 04./06.11.
- **Tech stack**: Python-ExApp (FastAPI, nc_py_api) aus dem Skeleton, sherpa-onnx (Parakeet, Silero VAD), faster-whisper/CTranslate2, ffmpeg LGPL-Build: Spike 1 bis 3
- **Kompatibilität**: Nextcloud 33 bis 35, AppAPI mit HaRP, amd64 + arm64, nur CPU
- **Ressourcen**: RAM-Wächter für jedes Modell; Profil darf nie mehr RAM brauchen, als die Hardware sicher hat
- **Lizenzen**: Parakeet CC-BY-4.0 (Namensnennung NVIDIA Pflicht), Whisper MIT, ffmpeg LGPL; Gate-Daten nicht ins Repo (Metamorphosis-Referenz nicht gemeinfrei, ns_music ungeprüft)
- **Sprache**: Alle nutzersichtbaren Texte und README DE/EN/FR im Gleichstand, Deutsch zuerst, echte Umlaute, keine Gedankenstriche, keine Emojis
- **Qualitäts-Gates**: ruff-Vollsatz, pyright basic, vulture lokal grün; Commits nur als street1983nk <k.cherif@outlook.de>, ohne "closes #N"
- **Prozess**: Vor jedem Push, Merge oder Kommentar den Owner fragen; UI-Abnahme gemeinsam per Playwright (3 Breiten, hell/dunkel); vor Store-Release großer Volltest DE/EN/FR
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Kernbefund vorab: Ohne PHP-Companion keine Unified Search
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
# Container (pyproject.toml, alles exakt gepinnt)
# Dev wie Skeleton
# ffmpeg: eigener Build-Stage wie frpc; Tag = letzter Autobuild eines Monats (bleibt 2 Jahre)
# Laufzeit-ENV
## Wie die Bausteine zusammenspielen (Stack-Sicht)
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
## Stack Patterns by Variant
- nur Schnell-Profil (Parakeet + Wächter, selektives turbo-Nachrechnen nur wenn Headroom für turbo reicht)
- weil Spike 3: turbo-Spitze 1,9 bis 3,4 GB; Parakeet 1,2 bis 1,7 GB
- Ausgewogen (Standard), turbo strikt in 10-min-Stücken
- weil turbo ohne Stückelung auf 3,4 GB steigt
- Qualität wählbar, large-v3 nur für deutsche Dateien
- weil large-v3 bis 4,5 GB braucht und nur DE gewinnt (Spike 3 Abschnitt 11)
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
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
