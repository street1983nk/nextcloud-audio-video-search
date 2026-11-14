# Phase 3: Vorschau-Transkripte in der Suche - Research

**Researched:** 2026-11-14
**Domain:** Medien-Eingang (ffmpeg, gehärtet), Parakeet-Vorschau in Stücken mit Fortsetzen, Abfangregel ohne Whisper, Unified-Search-Paginierung mit Rechteprüfung
**Confidence:** HIGH für Medien-Eingang und Suchvertrag (lokal gemessen bzw. Quelltext gelesen), MEDIUM für die Schwellen (gemessen, aber kleiner Korpus, ein Laptop, synthetisch verschlechtert)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Trefferbild in der Suche
- **D-03-01:** Eine Ergebniszeile je Stelle (wie der bestehende Provider): jede Zeile mit eigener Zeitmarke, eigenem Ausschnitt und eigenem Sprung-Link. Keine Zusammenfassung je Datei.
- **D-03-02:** Höchstens 3 Stellen je Datei pro Ergebnisseite, danach kommt die nächste Datei; weitere Stellen über die Paginierung der Unified Search ("Mehr laden"), ohne Dubletten und ohne Lücken über Seiten hinweg.
- **D-03-03:** Kennzeichen "vorläufig" als Wort im Untertitel, gleiche Form wie das bestehende "Test result": `1:23 · Vorläufig · Ausschnitt` (DE/EN/FR, l10n). Das Dateityp-Icon bleibt.
- **D-03-04:** Die Abspielseite zeigt bei einem Vorschau-Transkript einen kurzen Hinweis (sinngemäß "Vorläufiges Transkript, wird automatisch verbessert"), dreisprachig. Text vor dem Bau dem Owner zeigen.

#### Reihenfolge der Arbeit
- **D-03-05:** Neue und geänderte Dateien (Ereignisweg) zuerst, danach der Altbestand nach Änderungsdatum, neueste zuerst.
- **D-03-06:** Ein neuer Upload darf eine lange Datei unterbrechen, aber nur an der Stückgrenze: das laufende ca. 10-min-Stück wird fertig gerechnet und gesichert, dann kommt der neue Upload dran, danach geht die lange Datei am nächsten Stück weiter (gleicher Mechanismus wie das Fortsetzen nach Neustart, TRANS-07).
- **D-03-07:** Teile einer langen Datei sind je fertigem Stück findbar (als vorläufig), nicht erst nach der ganzen Datei. Die Rechte- und Zustandsregeln aus Phase 2 gelten für Teiltreffer unverändert.

#### Grenzen und Spurwahl
- **D-03-08:** Höchstdauer 12 Stunden Spieldauer; länger wird mit Grund "überlang" übersprungen (nicht still).
- **D-03-09:** Die Höchstdauer ist eine Admin-Einstellung (Standard 12 h). Wird sie erhöht, kommen zuvor wegen Überlänge übersprungene Dateien zurück in den Arbeitsvorrat. In Phase 3 über den bestehenden Einstellungsweg (deklarative Einstellung bzw. occ), die eigentliche Admin-Oberfläche bleibt Phase 9.
- **D-03-10:** Tonspur: die im Container als Standard (default disposition) markierte Audiospur, sonst die erste Audiospur. Fest, ohne Erkennungslauf. Zeitachse muss auch bei Edit-Lists stimmen (MEDIA-02).

#### Ohne Sprache / fremde Sprache
- **D-03-11:** Schwelle für "keine Sprache" wird nicht geraten, sondern in der Research am Medienkorpus (Musik, Gesang, Stille, Rauschen, kurze Sprachmemos) gemessen (z. B. VAD-Sprachanteil und Wortzahl nach Abfangregel) und dann festgelegt. Ein kurzes echtes Sprachmemo darf nicht als "keine Sprache" enden; Messung als Beleg im Plan.
- **D-03-12:** Gemischte Dateien: Teiltranskript behalten. Segmente in Instanz-Sprachen bleiben findbar, fremde Segmente fallen durch die Abfangregel (TRANS-03) weg. "Sprache nicht unterstützt" nur, wenn praktisch nichts übrig bleibt (Schwelle ebenfalls messen).
- **D-03-13:** Gründe (keine Sprache, übersprungen mit Grund, Sprache nicht unterstützt, überlang) sieht der Admin per occ (Admin-Status ohne Dateinamen, Entscheid 06.11.), der Nutzer auf der Abspielseite seiner Datei statt "kein Transkript". Die Abspielseite zeigt den Grund nur unter denselben Rechte- und Ausschlussregeln wie bisher (D-02-15c, D-02-16): für jeden nicht erlaubten Verweis antwortet sie wie für eine Datei ohne Transkript.
- **D-03-14:** Instanz-Sprachen für die Abfangregel in Phase 3 fest DE/EN/FR. Admin-Einschränkung erst später zusammen mit den Profilen.

#### Übernommen aus früheren Entscheiden (nicht neu verhandelt)
- VAD immer an, kein Abschaltweg; Spike-3-Standardwerte Abschnitt 11 als Konstanten mit Test.
- Treffer und Ausschnitt nur über Verweise mit state active (D-02-01a, D-02-15c), Probe-Regeln D-02-15/15a/Nachtrag, Ausschluss D-02-04/08/16, Lesebeweis ohne Abschaltweg D-02-10.
- Kein Inhalt verlässt den Server; Parakeet und Silero über eigenen Downloader mit festem sha256.

### Claude's Discretion
- Fortsetzen nach Neustart: Granularität und Ablage der Stück-Zustände (SQLite-Stufen-Tabelle nach Findling-Muster).
- Wortgenauer Sprung: Parakeet-Wortzeiten bevorzugt (TRANS-08), Rundung wie bestehende `clock()`-Regel (nie vor dem Wort).
- Konkrete Demuxer- und Protokoll-Positivliste, Zeit- und Größengrenzen von ffmpeg, Umgang mit DRM/defekten Dateien (MEDIA-03).
- Medienkorpus für Formate/Fuzz per Skript erzeugt, nicht im Repo (Lizenzregel).
- Parakeet als Kindprozess je Job-Block; voller cgroup-Wächter erst Phase 5.

### Deferred Ideas (OUT OF SCOPE)
- Instanz-Sprachen durch den Admin einschränken (mit den Profilen).
- Mehrere Tonspuren transkribieren bzw. Spurwahl nach Sprach-Tag.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEDIA-01 | Gängige Formate dekodieren, auch MP4 mit Index am Dateiende | Immer erst Temp-Datei, dann ffmpeg auf die lokale Datei; MP4 mit moov am Ende über Pipe bricht nachweislich ab (M-3); 10 Formate gemessen (M-2) |
| MEDIA-02 | Feste Spurwahl, Zeitachse auch bei Edit-Lists | ffprobe-Spurwahl (default disposition, sonst erste), explizites `-map 0:<index>`; `aresample=async=1:first_pts=0` korrigiert den Edit-List-Versatz von 1,98 s auf unter 1 ms (M-1) |
| MEDIA-03 | Gehärtete Dekodierung | `-protocol_whitelist file`, `-format_whitelist`, Wandzeit- und Bytegrenze je Stück; ffconcat-Datei mit Endung .mp3 wird ohne Liste geöffnet, mit Liste abgewiesen (M-4); verschlüsselte MP4: Exit 69, Kennung `enca/sinf/schm/tenc` (M-5) |
| MEDIA-04 | "keine Sprache" statt Fehler | Gemessene Dateiregel (M-7 bis M-10): 11 von 11 Nicht-Sprache-/Instrumentaldateien und alle Gesangsstücke ohne verständlichen Text "keine Sprache"; 49 von 49 natürliche Sprachmemos (4 bis 23 s) mit Transkript |
| TRANS-01 | Parakeet-Vorschau mit Schluck-Wächter, Spike-3-Werte | Konstanten aus SPIKE3 Abschnitt 11 (in dieser Research 1:1 nachgebaut, `measure.py`), Kindprozess je Job-Block |
| TRANS-02 | VAD immer an | Konstante ohne Einstellungsweg; Test, der Einstellungen, Env und Routen absucht (Muster D-02-10) |
| TRANS-03 | Abfangregel je Segment | Parakeet hat keine Sprachkennung; gemessene Ersatzregel je VAD-Fenster aus Schrift, Wortkonfidenz und Text-Sprachkennung (M-8, M-9) |
| TRANS-07 | Stücke ca. 10 min, Fortsetzen | Stückgrenze in einer VAD-Pause; `-ss` als Eingangsoption samplegenau (M-2); `next_start_ms` in derselben Transaktion wie die Wörter |
| TRANS-08 | Wortzeiten stimmen | Parakeet-Tokenzeiten (Raster 80 ms, nie mehr als 0,09 s zu früh, SPIKE2 Abschnitt 1.3); Edit-List-Korrektur (M-1); Link-Zeit abwärts auf 0,1 s |
| SRCH-01 | Treffer mit Zeitmarke, Ausschnitt, mehreren Stellen | Feste Stufen-Folge im Container + Offset-Cursor; Web-Dialog schickt keinen Cursor, sondern wachsendes `limit` (Quelltext NC stable33/34) |
| SRCH-02 | Kennzeichen vorläufig | `preview: bool` je Treffer, Untertitelwort per l10n ("Preliminary" / "Vorläufig" / "Provisoire") |
| SRCH-03 | Rechte zur Abfragezeit | Bestehender Zwei-Schritt (Container schlägt vor, PHP prüft `FileAccess::readableFile` je fileId), Prüfergebnis je fileId einmal pro Anfrage; Paritätstest im HTTP-Pfad gegen eine WebDAV-Wahrheit |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Kein Audio, kein Text, keine Telemetrie verlässt den Server; Modelle nur aus öffentlichen Quellen mit festem sha256.
- Qualität vor Speed; jede Qualitätsentscheidung mit Messung belegen.
- Stack: Python-ExApp (FastAPI, nc_py_api async), sherpa-onnx (Parakeet, Silero VAD), ffmpeg LGPL-Build; PHP-Companion für Suche, Ereignisse, Rechte.
- NC 33 bis 35, AppAPI mit HaRP, amd64 + arm64, nur CPU.
- RAM-Wächter für jedes Modell (voller cgroup-Wächter Phase 5; Phase 3: Kindprozess je Job-Block).
- Lizenzen: Parakeet CC-BY-4.0 (Namensnennung NVIDIA), ffmpeg LGPL; Testdaten nicht ins Repo.
- Nutzersichtbare Texte DE/EN/FR im Gleichstand, Deutsch zuerst, echte Umlaute, keine Gedankenstriche, keine Emojis; Umlaute nur in Prosa, nie in Code.
- Gates: ruff-Vollsatz, pyright basic (`PYRIGHT_PYTHON_FORCE_VERSION=latest`), vulture, pytest lokal grün; Commits nur als street1983nk, kein "closes #N".
- Vor Push, Merge oder Kommentar den Owner fragen; UI-Abnahme gemeinsam per Playwright (3 Breiten, hell/dunkel).
- Änderungen nur über GSD-Befehle; Findling-Muster kopieren, nicht importieren.

## Summary

Phase 3 baut drei Dinge, die heute fehlen: einen gehärteten Medien-Eingang (ffmpeg), einen Vorschau-Rechner (Parakeet in 10-min-Stücken mit Fortsetzen und Unterbrechen an der Stückgrenze) und echte Suchtreffer mit mehreren Stellen je Datei. Der Phase-2-Bestand trägt viel davon: `file_ref` mit `media_id`, Lesebeweis, `transcript`/`word`/`current` mit Herkunft, `index_outbox`, Tantivy-Segmente und der Zwei-Schritt-Provider mit Rechteprüfung in PHP. Der Download der Erfassung behält die Bytes nicht (Temp-Datei wird nach dem Hashen gelöscht), die Vorschau lädt die Datei also ein zweites Mal über das Gateway.

Die wichtigsten Befunde, alle lokal gemessen oder im Quelltext belegt: (1) Ohne Filter liegt die Zeitachse einer MP4 mit Edit-List 1,98 s daneben; `aresample=async=1:first_pts=0` bringt sie auf unter 1 ms. (2) MP4 mit Index am Ende scheitert über eine Pipe ("partial file"), also immer erst Temp-Datei. (3) `-ss` als Eingangsoption ist auf WAV, MP3 CBR/VBR, M4A, Opus, Ogg, FLAC, WebM, MP4- und MKV-Video samplegenau (0,0 bis 0,2 ms); nur VBR-MP3 ohne Xing/LAME-Kopf liegt konstant 25 ms daneben, wie ein Browser ohne diesen Kopf auch. (4) Eine ffconcat-Datei mit Endung .mp3 öffnet ffmpeg ohne Positivliste als Playlist lokaler Dateien; mit `-format_whitelist` wird sie abgewiesen. (5) Parakeet macht aus nicht unterstützten Sprachen lateinisch geschriebenen Wortsalat, den eine Text-Sprachkennung teils sicher als Englisch einstuft (p bis 0,97). Trennendes Merkmal ist die mittlere Wortkonfidenz je VAD-Fenster: nicht unterstützte Sprachen höchstens 0,57, saubere Instanz-Sprache Median 0,95. (6) Der Web-Dialog der Unified Search (NC stable33 und stable34) schickt keinen Cursor: "Mehr laden" fragt dieselbe Suche mit `limit + 5` neu an, der Knopf erscheint nur bei genau `limit` Einträgen, serverseitig ist `limit` auf 25 gedeckelt.

**Primary recommendation:** Feste, deterministische Stellen-Folge im Container (Dateien nach bestem Treffer, je Datei Stufen zu 3 Stellen), PHP füllt per Offset und Überabruf genau `limit` geprüfte Einträge; Vorschau je 10-min-Stück in einer Transaktion (Wörter + `next_start_ms` + `index_rev` + Outbox); Abfangregel je VAD-Fenster mit den gemessenen Schwellen (Konfidenz 0,6 bzw. 0,5 bei sicherer Instanz-Sprache, Text-Sprache p 0,9, Schrift 50 % lateinisch).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Datei-Bytes holen | API / Backend (ExApp, `nc.fetch_to_tempfile`) | PHP-Gateway (Rechte des Lesers) | Phase-2-Weg; Rechte liegen beim Gateway |
| Dekodieren, Spurwahl, Edit-List | ExApp (ffmpeg/ffprobe-Unterprozess) | - | Absturz im Decoder trifft nur den Unterprozess |
| VAD, Parakeet, Schluck-Wächter, Abfangregel | ExApp-Kindprozess (Engine) | ExApp-Worker (Steuerung) | Modell-RAM geht mit dem Kind zurück |
| Job-Zustand, Stücke, Fortsetzen, Reihenfolge | Database / Storage (SQLite `state.db`) | ExApp-Worker | Quelle der Wahrheit, überlebt Neustart |
| Herkunft "Ereignisweg" | PHP (Listener schreibt Herkunft in `avs_queue`) | ExApp (übernimmt in `file_ref`) | Nur PHP weiß, ob ein Ereignis oder der Crawl die Zeile schrieb |
| Index, Stellen-Folge, Offset | ExApp (Tantivy + SQLite) | - | Rangfolge entsteht dort |
| Rechteprüfung je Treffer | PHP-Companion (`FileAccess::readableFile` unter `ReaderContext::actAs`) | - | Einzige Rechtegrenze |
| "Vorläufig", Hinweis Abspielseite, Gründe als Text | PHP-Companion (l10n) | ExApp liefert nur Codes | Texte DE/EN/FR in PHP-l10n |
| Höchstdauer | ExApp (deklarative Einstellung, appconfig_ex) | occ | D-03-09 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sherpa-onnx | 2.0.1 (+ sherpa-onnx-core 2.0.1) | Parakeet-TDT-0.6B-v3 int8 (`OfflineRecognizer.from_transducer`, `model_type="nemo_transducer"`, `greedy_search`, 2 Threads), Silero VAD (`VoiceActivityDetector`) | Spike 1 bis 3 und diese Research [VERIFIED: lokal installiert und gelaufen, 14.11.] |
| numpy | 2.5.4 | PCM-Puffer | Findling-Pin [VERIFIED: uv-Auflösung 14.11.] |
| ffmpeg/ffprobe (BtbN, statisch, LGPL) | `n8.1.3-27-g8dca1586f4` aus Release `autobuild-2026-10-31-12-59` (Monatsletzter Oktober) | Dekodieren auf 16 kHz mono f32, Spurwahl | BtbN hält den Monatsletzten zwei Jahre [CITED: STACK.md]. Asset-Digests per GitHub-API gelesen [VERIFIED: GitHub API 14.11.]: `ffmpeg-n8.1.3-27-g8dca1586f4-linux64-lgpl-8.1.tar.xz` sha256 `a64f3171e6ad1f7d358d28890a907ee478c331d1177ec696a93418f79ac3f1f3`; `ffmpeg-n8.1.3-27-g8dca1586f4-linuxarm64-lgpl-8.1.tar.xz` sha256 `2ea30086a637e3f0ad0f49a1b38db34121422b85e93cc82df2e01d9ee5200809` |
| Parakeet-TDT-0.6B-v3 int8 | HF `csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` @ `2bda32ec70b097a55adaa07d9a7173915b43cc78` | Vorschau-Engine | Am 14.11. neu geladen, sha256: encoder `acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247`, decoder `179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e`, joiner `3164c13fc2821009440d20fcb5fdc78bff28b4db2f8d0f0b329101719c0948b3`, tokens.txt `d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d` [VERIFIED: sha256sum] |
| Silero VAD | GitHub `k2-fsa/sherpa-onnx` Release `asr-models`, `silero_vad.onnx` | VAD | sha256 `9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6` [VERIFIED: sha256sum] |

Lokale Messungen liefen mit ffmpeg 8.1.1 (gyan.dev, Windows), nicht mit dem BtbN-Linux-Build. Die Optionen sind dieselben (Zweig 8.1); die Beep-Prüfungen M-1/M-2 gehören deshalb als Test in die CI gegen das echte Image [ASSUMED: Gleichverhalten 8.1.1 und 8.1.3].

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| py3langid | 0.4.0 (02.09.2026, BSD-3-Clause, nur numpy, Wheel 4,6 MB) | Text-Sprachkennung je VAD-Fenster (Abfangregel für ES/IT/NL/PL usw., die Parakeet sauber transkribiert) | Gemessen in M-8; neue Laufzeitabhängigkeit, Owner-Freigabe nötig [ASSUMED: slopcheck nicht ausführbar] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Temp-Datei, dann ffmpeg | ffmpeg liest per Pipe aus dem Gateway-Stream | spart Platte, scheitert an MP4/MOV/M4A mit Index am Ende (M-3) |
| `-ss` je Stück | ein ffmpeg-Lauf über die ganze Datei | ohne Seek kein Fortsetzen ohne Dekodieren ab 0; Dekodieren kostet ohnehin nur ca. 0,4 bis 1,0 s je 10 min (M-2) |
| py3langid | Stoppwort-Quote mit Snowball-Listen (de, en, fr, es, it, nl, pt, ru, sv, da, no, fi, hu) | ohne neue Abhängigkeit; in der Messung nicht ausgewertet als Ersatzregel, nur als Merkmal mitgeschrieben (`stop_lang`). Sprachen ohne Snowball-Liste (pl, cs, ro ...) erkennt sie nicht |
| py3langid | `lingua-language-detector` 2.2.0 | 170 MB Wheel (STACK.md) |
| py3langid | Whisper `detect_language` | Whisper ist erst ab Phase 6 geladen; 1 bis 2 GB RAM nur für die Vorschau |
| py3langid | sherpa-onnx `SpokenLanguageIdentification` | liefert nur einen Code ohne Sicherheit (API gelesen: `compute`, `create_stream`), zweites Modell |

**Installation (backend/pyproject.toml, exakt gepinnt, dann `uv lock`):**
```bash
uv add sherpa-onnx==2.0.1 numpy==2.5.4      # py3langid==0.4.0 erst nach Owner-Freigabe
```
ffmpeg als eigener Build-Stage im `backend/Dockerfile` wie frpc: Tag + sha256 je Architektur, nur `ffmpeg` und `ffprobe` nach `/usr/local/bin`.

## Package Legitimacy Audit

slopcheck ließ sich in dieser Sitzung nicht installieren (globale pip-Installation verweigert). Alle neuen Pakete sind `[ASSUMED]`; der Planer setzt vor jeder Installation einen `checkpoint:human-verify`.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| sherpa-onnx 2.0.1 | PyPI | seit Jahren, Spike 1 bis 3 | nicht geprüft | github.com/k2-fsa/sherpa-onnx | nicht ausführbar | in STACK.md freigegeben, trotzdem `[ASSUMED]` |
| numpy 2.5.4 | PyPI | sehr alt | sehr hoch | github.com/numpy/numpy | nicht ausführbar | Findling-Pin |
| py3langid 0.4.0 | PyPI | erstes Release 2021, 8 Releases, letztes 02.09.2026 | nicht geprüft | github.com/adbar/py3langid (68 Sterne, Fork von langid.py, LICENSE BSD-3-Clause gelesen) | nicht ausführbar | Owner-Freigabe + checkpoint |

**Packages removed due to slopcheck [SLOP] verdict:** keine (slopcheck nicht gelaufen)
**Packages flagged as suspicious [SUS]:** keine (slopcheck nicht gelaufen); py3langid ist ein reines Python-Wheel ohne Installationsskript

## Architecture Patterns

### System Architecture Diagram

```
PHP Listener / Crawl --(avs_queue: kind, NEU origin=event|crawl)--> Intake (Phase 2) --> file_ref (+origin)
                                                                                           |
Capture (Phase 2): Download -> sha256 -> media_id, state active, stage keyed --------------+
                                                                                           v
                     preview_job (SQLite, eine Zeile je media_id)  Reihenfolge: event vor crawl,
                                                                   dann mtime absteigend
                                                                                           |
Vorschau-Worker (async, seriell) --- claim ------------------------------------------------+
  1. aktiven Verweis + Leser wählen (state active, gültiger Lesebeweis)
  2. Gateway -> Temp-Datei; sha256 == media_key? sonst Abbruch (Inhalt geändert)
  3. ffprobe mit Positivlisten: Tonspur, Dauer, Verschlüsselung
       -> Grund too_long / damaged / protected / no_audio / format_unsupported
  4. je Stück ab next_start_ms: ffmpeg -ss/-t -> PCM 16 kHz f32 (Pipe)
  v
Engine-Kindprozess (Parakeet + Silero, 2 Threads, lebt einen Job-Block)
  VAD -> Fenster bis 25 s -> Parakeet -> Schluck-Wächter -> Wörter (Zeit, Konfidenz)
  -> Abfangregel je Fenster -> behalten | verwerfen(script|language|confidence) + Zähler
  |
  v eine SQLite-Transaktion je Stück
  Stück 1: transcript (parakeet, PREVIEW) + current;  jedes Stück: word anhängen,
  index_rev + 1, index_outbox, preview_job.next_start_ms / chunks_done / Zähler
  |
  +--> Index-Worker (Phase 1/2): publish -> retire -> mark_indexed   (Teiltreffer sofort)
  +--> Stückgrenze: wartet ein event-Job und läuft crawl?  -> Job zurück auf queued
  +--> letztes Stück: Dateiurteil transcript | no_speech | unsupported

Suche: Web-Dialog --(term, limit, cursor=null)--> PHP Provider --(term, offset, n)--> /search
  /search: Tantivy top-K -> zulässige Revision -> Stellen je media -> je file_id
           -> Stufen-Folge (Dateien nach bestem Score, je Stufe 3 Stellen) -> [offset, offset+n)
  PHP: je fileId einmal Ausschluss + readableFile (Cache je Anfrage) -> genau limit Einträge
       -> "m:ss · Vorläufig · Ausschnitt", Link play?t=
```

### Recommended Project Structure (neu oder geändert)
```
backend/src/audio_video_search_backend/
├── media/              # NEU: probe.py (ffprobe, Spurwahl, DRM-Kennung), decode.py (Stück-PCM)
├── engine/             # NEU: child.py (Kindprozess), parakeet.py (Spike-3-Konstanten, Wächter),
│                       #      catch.py (Abfangregel, Dateiurteil)
├── models/             # NEU: Downloader, feste sha256, Host-Allowlist (Findling-Muster)
├── worker/preview.py   # NEU: Claim, Reihenfolge, Unterbrechen, Fortsetzen, Temp-Datei
├── store/schema.sql    # v3: preview_job, file_ref.origin; store/migrate.py v2 -> v3
├── api/search.py       # Stufen-Folge, offset/nextOffset/hasMore, preview
├── api/excerpt.py      # + preview, + reason für Dateien ohne Transkript
└── settings.py         # + max_duration_hours (Standard 12)
php/lib/
├── Search/Provider.php          # getLimit(), Cursor, Runden mit Überabruf, Prüf-Cache, "Preliminary"
├── Service/ExAppService.php     # search(offset), excerpt(preview, reason)
├── Controller/PageController.php (+ Template)  # Hinweis vorläufig, Grund statt "kein Transkript"
├── Db/QueueMapper.php + Migration              # Spalte origin
└── Command/StatusCommand.php    # Gründe als Zähler, ohne Dateinamen
```

### Pattern 1: Medien-Eingang (gehärtet, gemessen)
**What:** Datei vollständig in eine Temp-Datei ohne sprechende Endung (`$APP_PERSISTENT_STORAGE/tmp/<zufall>.bin`) laden, sha256 gegen `media_key` prüfen, dann ffprobe und ffmpeg nur auf diese Datei. Löschen bei jedem Ausgang (wie `fetch_to_tempfile`).
**Example:**
```python
# Quelle: lokal gemessen (M-1 bis M-5); Optionen aus `ffmpeg -h full` 8.1.1
DEMUXERS = "mov,mp3,wav,w64,ogg,flac,matroska,aac,asf,avi,amr,aiff,caf,mpegts,mpeg"  # webm = matroska
cmd = [
    FFMPEG, "-nostdin", "-hide_banner", "-loglevel", "error", "-threads", "1",
    "-protocol_whitelist", "file", "-format_whitelist", DEMUXERS,
    "-ss", f"{start_ms / 1000:.3f}", "-t", f"{dur_ms / 1000:.3f}",   # Eingangsoptionen vor -i
    "-i", str(tmp_path),
    "-map", f"0:{stream_index}", "-vn", "-sn", "-dn",
    "-af", "aresample=async=1:first_pts=0",                           # Edit-List, Priming, Lücken
    "-ac", "1", "-ar", "16000", "-c:a", "pcm_f32le", "-f", "f32le",
    "-fs", str(max_bytes),                                            # (dur_s + 1) * 16000 * 4
    "pipe:1",
]
# subprocess.run(..., timeout=WALL_LIMIT_S); Exit != 0 oder viel zu wenig Samples -> Grund "damaged"
```
Spurwahl (D-03-10): `ffprobe -protocol_whitelist file -format_whitelist ... -show_entries stream=index,codec_type:stream_disposition=default:format=duration -of json`; erste Audiospur mit `disposition.default == 1`, sonst erste Audiospur; keine Audiospur: `no_audio`. Höchstdauer aus `format.duration`; fehlt sie, begrenzt `-t` je Stück und die Stückzahl (`max_duration / 600 s`).

### Pattern 2: Stück mit Grenze in einer VAD-Pause (TRANS-07, D-03-06)
- Stück dekodiert `[next_start_ms - 1 s, next_start_ms + 600 s + 60 s Vorlauf]` (Kontext 1 s vorn, damit der 0,4-s-Kontext der Spike-Pipeline nicht abgeschnitten wird).
- VAD über das ganze Stück; übernommen werden nur zusammengefasste Fenster, die vor `next_start_ms + 600 s` beginnen. Neues `next_start_ms` = Ende des letzten übernommenen Fensters. Ein Fenster ist höchstens 25 s lang, also reicht der Vorlauf. Kein Fenster im Stück: `next_start_ms += 600 s`.
- Eine Transaktion je Stück: Wörter, `index_rev + 1`, Outbox, `next_start_ms`, `chunks_done`, Zähler. Absturz mitten im Stück: das Stück wird neu gerechnet, weil `next_start_ms` noch alt ist.
- Unterbrechen: nach jedem Commit `EXISTS(job queued AND origin = 'event')` und laufender Job `origin = 'crawl'`: Job zurück auf `queued`, Temp-Datei löschen. Fortsetzen nach Neustart und nach Unterbrechen ist derselbe Weg (neu laden, sha256, ab `next_start_ms`).
- Dekodieren ist billig (10 min Audio in 0,36 bis 1,0 s, M-2); das erneute Laden über das Gateway ist der teure Teil bei Videos. Siehe Open Question 3 (Dateigröße).

### Pattern 3: Teiltreffer ohne neues Versionsmodell (D-03-07)
Stück 1 legt die `transcript`-Zeile an (engine `parakeet`, level `PREVIEW`, `input_file_sha256` = Datei-sha256, Sprache `und`) und schreibt `current` über den bestehenden bedingten UPSERT. Jedes weitere Stück hängt `word`-Zeilen mit fortlaufendem `idx` an dieselbe `version_id` und erhöht nur `index_rev` (wie heute eine Korrektur, `_BUMP_INDEX_REV`). Der Index baut die Segmente der ganzen Wortliste neu (`segments_from_words`), `retire` räumt alte Revisionen ab. Damit bleiben `current`, die Herkunftsordnung (TRANS-06) und die Revisionsregel der Suche unverändert. `preview_job.state = 'complete'` markiert die fertige Vorschau für Phase 6. Eine neue Version je Stück geht nicht: der UPSERT verwirft den Gleichstand `(epoch, level, config_version)` als veraltet.

Vorschlag `preview_job` (Ermessen, Findling-Stufenmuster):
```sql
CREATE TABLE IF NOT EXISTS preview_job (
    media_id      INTEGER PRIMARY KEY REFERENCES media (media_id),
    epoch         INTEGER NOT NULL,
    state         TEXT    NOT NULL,   -- queued, running, complete, skipped
    reason        TEXT,               -- too_long, no_audio, damaged, protected, format_unsupported,
                                      -- no_speech, unsupported_language (geschlossene Liste)
    origin        TEXT    NOT NULL,   -- event, crawl
    sort_mtime    INTEGER NOT NULL,
    duration_ms   INTEGER,            -- für D-03-09: too_long-Zeilen kommen bei höherer Grenze zurück
    next_start_ms INTEGER NOT NULL DEFAULT 0,
    chunks_done   INTEGER NOT NULL DEFAULT 0,
    version_id    INTEGER,
    kept_words    INTEGER NOT NULL DEFAULT 0,
    drop_script   INTEGER NOT NULL DEFAULT 0,
    drop_language INTEGER NOT NULL DEFAULT 0,
    drop_conf     INTEGER NOT NULL DEFAULT 0,
    speech_ms     INTEGER NOT NULL DEFAULT 0,
    attempts      INTEGER NOT NULL DEFAULT 0,
    next_try_at   INTEGER,
    updated_at    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS preview_job_order
    ON preview_job (state, CASE origin WHEN 'event' THEN 0 ELSE 1 END, sort_mtime DESC, media_id);
```
`origin`: ein Ereignis gewinnt (wird eine crawl-Datei geändert, wird sie event). Copies: Job je media_id, nicht je file_id.

### Pattern 4: Feste Stellen-Folge und Paginierung (SRCH-01, D-03-02)
Belegt im Quelltext `nextcloud/server` stable33 und stable34, `core/src/components/UnifiedSearch/UnifiedSearchModal.vue`: der Dialog schickt `cursor: null`, startet mit `limit` 5, `loadMoreResultsForProvider` setzt `providerResultLimit += 5` und fragt neu; der Knopf erscheint nur bei `providerResult.results.length === providerResult.limit`. `core/Controller/UnifiedSearchController.php` deckelt `limit` mit `unified-search.max-results-per-request` (Standard 25), `SearchQuery::LIMIT_DEFAULT = 5`.
Folgerungen:
1. Die Antwort für `limit = 10` muss mit der für `limit = 5` beginnen. Das geht nur mit einer festen, deterministischen Folge im Container: Dateien nach bestem Stellen-Score (Gleichstand: fileId), Stellen je Datei nach Score (Gleichstand: Zeit). Stufe 1 = je Datei die besten 3 Stellen, Stufe 2 = Stellen 4 bis 6 usw.; Folge = Stufe 1 über alle Dateien, dann Stufe 2 über alle Dateien.
2. PHP liefert genau `limit` geprüfte Einträge, solange es mehr gibt, sonst verschwindet "Mehr laden". Also Runden mit Überabruf wie Findling `SearchService::run` (Offset-Cursor, `nextOffset`, `hasMore`, Prüfbudget, Wandzeit 2,5 s); Prüfergebnis je fileId nur einmal pro Anfrage, weil eine Datei bis zu 3 Stellen je Stufe bringt.
3. Clients mit Cursor: Cursor = Offset in derselben Folge, `SearchResult::paginated($name, $entries, $nextOffset)`.
4. Gibt es nur eine Datei mit vielen Stellen, füllt Stufe 2 die Seite auf (siehe Open Question 1).
5. Der heutige Provider fragt immer 25 Treffer und antwortet `complete`; er ignoriert `getLimit()` und `getCursor()`. Das ändert sich in Phase 3.
6. Eine Stelle = ein Index-Segment (`segments_from_words`: bis 40 Wörter, Schnitt bei Pause über 1,5 s). Treffen zwei Wörter dasselbe Segment, ist es eine Stelle. Zeit der Stelle wie heute: erstes passendes Wort, sonst Segmentanfang.

### Pattern 5: Abfangregel ohne Whisper (TRANS-03, D-03-12, D-03-14)
Parakeet liefert keine Sprachkennung (SPIKE2; Modellkarte nennt nur automatische Erkennung ohne Ausgabe [CITED: huggingface.co/nvidia/parakeet-tdt-0.6b-v3]). Die Regel arbeitet je zusammengefasstem VAD-Fenster (bis 25 s), gemessen in M-8/M-9:

```python
# Quelle: Messung dieser Research (verdict.py); Werte als Konstanten mit Test
INSTANCE = frozenset({"de", "en", "fr"})
MIN_LATIN = 0.5        # Anteil lateinischer Buchstaben, sonst "script"
LID_P = 0.9            # py3langid, Wahrscheinlichkeit normiert
LID_MIN_WORDS = 3      # kürzere Fenster werden nicht nach Text-Sprache verworfen
CONF = 0.6             # mittlere Wortkonfidenz (exp(min Token-Logprob) je Wort, wie Spike 3)
CONF_INSTANCE = 0.5    # niedrigere Grenze, wenn die Text-Sprache sicher DE/EN/FR ist

def window_verdict(latin: float, lid: str, lid_p: float, n_words: int, conf_mean: float) -> str:
    if latin < MIN_LATIN:
        return "script"
    if lid not in INSTANCE and lid_p >= LID_P and n_words >= LID_MIN_WORDS:
        return "language"
    if conf_mean >= CONF or (lid in INSTANCE and lid_p >= LID_P and conf_mean >= CONF_INSTANCE):
        return "keep"
    return "confidence"
```
Dateiurteil nach dem letzten Stück:
```python
if kept_words >= 1:
    verdict = "transcript"                       # auch Teiltranskript (D-03-12)
elif drop_script + drop_language >= 5 or (drop_conf >= 10 and speech_s >= 10 and speech_share >= 0.3):
    verdict = "unsupported_language"
else:
    verdict = "no_speech"
```
Verworfene Fenster werden nicht gespeichert und nicht indexiert, nur gezählt. Für den Plan: TRANS-03 nennt "Sicherheit < 0,5" für die erkannte Sprache; das ist die Whisper-Fassung aus Spike 3. Für Parakeet ersetzt die gemessene Kombination diese Regel; die Whisper-Fassung bleibt für Phase 6 (siehe Assumption A3).

### Pattern 6: Kindprozess je Job-Block
Worker startet `python -m audio_video_search_backend.engine.child`, schickt Stückaufträge (Pfad einer PCM-Datei oder PCM über stdin, Startzeit) als JSON-Zeilen, bekommt Fenster mit Wörtern, Konfidenzen und Sprachmerkmalen zurück. Das Kind lädt Parakeet einmal (ca. 0,8 GB RSS nach Laden, Spitze 1,2 bis 1,7 GB, SPIKE3 Abschnitt 6) und endet nach dem Job oder nach N Stücken. Vor dem Start: freier Speicher (Findling `memory_guard.headroom_bytes`) mindestens Bedarf 1,7 GB + Reserve, sonst warten; Wandzeit je Stück begrenzen, bei Überschreitung Kind beenden, Stück zählt als Versuch. Voller Wächter in Phase 5.

### Anti-Patterns to Avoid
- **ffmpeg aus der Gateway-Pipe:** scheitert an MP4/MOV/M4A mit Index am Ende (M-3).
- **Ohne `aresample=async=1:first_pts=0`:** Zeitachse bei Edit-List um 1,98 s verschoben (M-1).
- **`-ss` nach `-i`:** dekodiert alles bis zur Stelle; als Eingangsoption ist es genau (M-2).
- **Automatische Spurwahl von ffmpeg:** bewertet Kanalzahl und Standardkennzeichen gemeinsam; die feste Regel D-03-10 braucht `-map` nach ffprobe (M-6).
- **Provider mit festem `SEARCH_LIMIT` und `SearchResult::complete`:** liefert im Dialog 25 statt 5 und keinen Weg zu weiteren Stellen.
- **Neue transcript-Version je Stück:** UPSERT verwirft den Gleichstand.
- **VAD- oder Abfangschwellen als Einstellung:** Konstanten mit Test (Owner-Regel, wie D-02-10).
- **Text-Sprachkennung allein:** Wortsalat aus nicht unterstützten Sprachen wird mit p bis 0,97 als Englisch erkannt (M-8); nur zusammen mit der Konfidenz.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Container, Edit-Lists, Codecs | eigener Demuxer, PyAV im Worker | ffmpeg-CLI (LGPL) im Unterprozess | Edit-List, Priming, Lücken; Absturz bleibt draußen |
| Stück-Zeitachse | Samples über Pipes zählen | `-ss`/`-t` als Eingangsoption + `aresample=async=1:first_pts=0` | gemessen samplegenau (M-2) |
| Text-Sprachkennung | eigene n-Gramm-Tabellen | py3langid (langid.py-Modell, 97 Sprachen) | trainiertes Modell |
| Job-Warteschlange | Celery/Redis | SQLite-Tabelle mit Claim (Findling-Muster) | ein Prozessbaum, überlebt Neustart |
| Rechteprüfung | Rechte im Container nachbauen | `FileAccess::readableFile` unter `ReaderContext::actAs` | einzige Rechtegrenze inkl. Gruppenordner-ACL |
| Modell-Download | `huggingface_hub`, `nc_py_api.fetch_models_task` | eigener Downloader, fester sha256, Host-Allowlist (Findling) | prüft gegen festen Wert |

**Key insight:** Die schwierigen Teile (Zeitachse, Containerformate, Rechte) sind gelöst, wenn die vorhandenen Werkzeuge mit den richtigen Optionen laufen; Fehler entstehen bei Abkürzungen (Pipe statt Datei, Auto-Spurwahl, festes Limit).

## Messungen (Belege)

Alle Läufe am 14.11.2026 auf dem Owner-Laptop (i5-1335U, 15,7 GB RAM, Windows 11), kein Docker, seriell, je Lauf ein Prozess, ein Modell, 2 Threads; freier RAM vor jedem Modelllauf geprüft (6,05 / 6,56 / 6,59 GB frei). Kein Audio und kein Text hat den Rechner verlassen; aus dem Netz kamen nur die gepinnten Modelle und öffentliche Testdaten. Skripte (nicht im Repo, Audiodaten nie im Repo) im Scratchpad dieser Sitzung: `C:\Users\Student\AppData\Local\Temp\claude\f797e4cbc4775e2e\641cb9cc-a8aa-42df-8fa7-62e6f0242d3e\scratchpad\scripts\` (`fetch_corpus.py`, `fetch_commons_retry.py`, `build_corpus.py`, `build_extra.py`, `build_short.py`, `measure.py`, `shortpass.py`, `evalrule.py`, `grid.py`, `confdist.py`, `verdict.py`) und die ffmpeg-Prüfskripte in `...\scratchpad\ff\` (`beeppos.py`, `beeps.py`). Der Scratchpad ist sitzungsgebunden: der Planer sollte die Skripte (ohne Daten) als Wave-0-Aufgabe nach `scripts/research/phase3/` übernehmen.

### Korpus
- FLEURS-Testsätze (google/fleurs, CC-BY-4.0), aus dem Tar-Strom gelesen: DE/EN/FR je 15 Clips; Fremdsprachen je 10 Clips: von Parakeet v3 unterstützt ES, IT, PL, NL, RU, EL; nicht unterstützt TR, AR, ZH (cmn), JA, HI, VI, SW.
- Wikimedia Commons: Mendelssohn Nocturne und Scherzo (gemeinfrei), USAF Band "America" (gemeinfrei, mit Gesang), Spohr "Wiegenlied" und "Sei still mein Herz" (CC BY-SA 2.0), Senfl "Ach Elslein" a cappella (CC BY 3.0), Mendelssohn "Song with choir" (gemeinfrei), Al Bowlly "Guilty" und "I Love You, California" (gemeinfrei, gesungenes Englisch), Bruant "Nini peau d'chien" 1905 (gemeinfrei).
- Synthetisch: Stille, weißes Rauschen -45 dBFS, rosa -25 dBFS, braunes -20 dBFS (je 5 min), Sinus 440 Hz und Netzbrummen 50 Hz (je 2 min).
- Abgeleitet: Sprachmemos (einzelne FLEURS-Clips 4 bis 23 s, 45 Stück), 3-s-Anschnitte (15), Kurzmemos an Wortgrenzen geschnitten mit 1, 2 und 4 Wörtern (je 15), DE-Memo in 5 min Stille / rosa Rauschen -40 dBFS / unter Musik SNR 10 und 0 dB, 3 min Musik dann DE-Sprache, Mischdateien DE10/AR90, DE20/TR80, DE50/ES50, FR30/JA70, verschlechterte Instanz-Sprache (rosa Rauschen SNR 5 und 0 dB, Stimmengewirr aus 6 Fremdsprachen SNR 5 dB, Telefonband 300 bis 3400 Hz mit 8 kHz µ-law).
- Insgesamt 161 Dateien, 181,5 min Audio.

Befehle (Pfad `S` = Scratchpad):
```bash
uv venv --python 3.13 $S/work/venv && uv pip install --python $S/work/venv/Scripts/python.exe sherpa-onnx==2.0.1 numpy py3langid
# Modelle: HF csukuangfj/...-int8 @ 2bda32ec... und k2-fsa asr-models/silero_vad.onnx, danach sha256sum (Werte oben)
python -I fetch_corpus.py $S/corpus && python -I fetch_commons_retry.py $S/corpus
python -I build_corpus.py $S/corpus && python -I build_extra.py $S/corpus
python -I measure.py $S/models $S/stop $S/results $S/corpus/test/*.wav
python -I build_short.py $S/corpus $S/results
python -I measure.py $S/models $S/stop $S/results2 $S/corpus/short/*.wav $S/corpus/extra/*.wav $S/corpus/sing2/*.wav
python -I verdict.py $S/results $S/results2      # Endregel je Datei
python -I grid.py $S/results $S/results2         # Schwellenraster
python -I confdist.py $S/results $S/results2     # Konfidenzverteilung je Gruppe
```
`measure.py` baut die Spike-3-Pipeline 1:1 nach (`spike3/scripts/bench3.py` Zeilen 44 bis 132: Silero 0,5 / Mindeststille 0,3 s / Mindestsprache 0,25 s / max. 25 s, Fenster bis 25 s mit Zusammenfassung bei Lücke bis 2 s, 0,4 s Kontext, 0,5 s Polster, Schluck-Wächter 1,0 Wort/s ab 1 s, greedy, 2 Threads) und schreibt je Fenster Text, Wortzahl, mittlere Konfidenz, lateinischen Anteil, Snowball-Stoppwort-Sprache und py3langid.

### M-1 Edit-List und Zeitachse [gemessen]
Testdatei: 10-s-WAV mit Beep bei genau 5,000 s, in MP4 mit Video 12 s und Audio `-itsoffset 2` (Edit-List vorhanden, `elst` gefunden; ffprobe Audio `start_time=1.978`). Erwartet im Player: ca. 7,0 s.

| Dekodierung | Beep im PCM | Länge |
|---|---|---|
| WAV direkt | 5,000 s | 10,000 s |
| M4A ohne Versatz | 5,000 s | 10,005 s |
| MP4 mit Edit-List, ohne Filter | **5,021 s (1,98 s zu früh)** | 10,027 s |
| MP4 mit Edit-List, `-af aresample=async=1:first_pts=0` | **6,999 s** | 12,005 s |
| dito mit `-copyts` | 6,999 s | 12,005 s |

`first_pts=0` füllt laut ffmpeg-Doku den Anfang mit Stille, wenn die Audiospur nach dem Video beginnt, und schneidet Samples mit negativem pts (Encoder-Delay) weg [CITED: ffmpeg.org/ffmpeg-resampler.html]; `async=1` füllt und kürzt auch Lücken in der Mitte.

### M-2 Stückgenauigkeit `-ss` als Eingangsoption [gemessen]
25-min-Signal (44,1 kHz) mit 50-ms-Beep bei n·60 + 7,25 s, in 10 Formate kodiert. Abweichung aller Beeps zur Sollzeit, ganze Datei und Stück `-ss 600 -t 600`:

| Format | ganze Datei | Stück 600 bis 1200 s |
|---|---|---|
| WAV, MP3 CBR 128k, MP3 VBR (LAME-Kopf), M4A AAC, Ogg Vorbis, FLAC, MP4 Video (H.264+AAC) | 0,1 ms | 0,1 ms |
| Opus (.opus), WebM (Opus) | 0,0 bis 0,1 ms | 0,0 bis 0,1 ms |
| MKV Video (H.264+AAC) | 0,1 ms | 0,2 ms |
| MP3 VBR ohne Xing/LAME-Kopf (`-write_xing 0`) | 25,1 ms | 25,1 ms |

Die 25,1 ms sind der nicht ausgeglichene Encoder-Delay (1105 Samples bei 44,1 kHz); ohne LAME-Kopf kann auch ein Browser ihn nicht ausgleichen [ASSUMED], also stimmt die Zeit relativ zum Player. Dekodierzeit eines 10-min-Stücks (`-threads 1`): M4A 0,43 s, MP4-Video 0,42 s, Opus 1,01 s, MP3 0,51 s, FLAC 0,36 s.

### M-3 MP4 mit Index am Ende [gemessen]
`l.m4a` (18 MB, moov bei Byte 18 054 088, mdat bei 40) über `cat | ffmpeg -i pipe:0`: `stream 0, offset 0x2c: partial file`, `Error during demuxing: Invalid data found`, keine Samples. Dieselbe Datei als lokale Datei: alle 25 Beeps auf 0,1 ms. Eine 18-KB-Datei ging über die Pipe noch durch (passte in den Puffer), daher in Tests eine große Datei benutzen.

### M-4 Positivlisten [gemessen]
- Datei `evil_concat.mp3` mit Inhalt `ffconcat version 1.0 / file 'long.wav'`: ohne Listen öffnet ffmpeg sie als concat-Playlist und liest die fremde lokale Datei; mit `-protocol_whitelist file -format_whitelist mp3,mov,wav,ogg,flac,matroska,aac,asf,avi,amr,aiff,mpegts,mpeg,caf,w64`: `Format not on whitelist`, Abbruch.
- HLS-Playlist mit Endung .mp3: schon ohne Liste nicht erkannt ("Not detecting m3u8/hls with non standard extension"), mit Liste ebenso; die Liste ist hier zweite Verteidigung.
- `-format_whitelist mov` genügt für M4A/MP4/MOV (Demuxername `mov,mp4,m4a,3gp,3g2,mj2`), `matroska` für WebM und MKV (`matroska,webm`); eine M4A mit nur `mp3` erlaubt: Exit 127 `Format not on whitelist 'mp3'`.
- Zufallsbytes: `Invalid data found when processing input`. Abgeschnittene M4A (Index fehlt): `moov atom not found`. Abgeschnittene MP3: dekodiert bis zum Ende der Bytes (13 von 25 Beeps, Zeit korrekt).

### M-5 Verschlüsselte Dateien (DRM) [gemessen]
CENC-verschlüsselte M4A (`-encryption_scheme cenc-aes-ctr`): ffprobe meldet `codec_name=aac codec_tag_string=mp4a` (unauffällig), Dekodieren ohne Schlüssel liefert 0 Samples, 1070 Fehlerzeilen, **Exit 69**. In der Datei stehen die Boxen `enca`, `sinf`, `schm`, `tenc`, `senc`. Empfehlung: bei mov-Demuxer Kopf/moov auf diese Kennungen prüfen (Grund `protected`), sonst bei Exit != 0 oder Sampleanteil unter 50 % der erwarteten Dauer Grund `damaged`. FairPlay (`drms`) und Audible (`aax`) sind nicht gemessen [ASSUMED: gleiche Erkennung über `drms`/`aavd`].

### M-6 Spurwahl [gemessen]
MKV und MP4 mit zwei AAC-Spuren (mono 300 Hz / stereo 900 Hz), Standardkennzeichen wechselweise gesetzt. ffprobe zeigt `disposition:default` korrekt für beide Container. ffmpeg 8.1.1 wählte ohne `-map` in beiden Fällen die Standardspur; das ist aber eine Bewertung aus Kanalzahl und Kennzeichen, keine zugesicherte Regel [ASSUMED]. Deshalb explizites `-map 0:<index>` aus ffprobe.

### M-7 Nicht-Sprache, Musik, Gesang [gemessen]
| Datei | Dauer | VAD-Sprache | Wörter roh | nach Regel behalten | Urteil |
|---|---|---|---|---|---|
| Stille, weiß -45, rosa -25, braun -20 (je 5 min), Sinus, Brummen (je 2 min) | 300 / 120 s | 0,0 bis 0,7 s | 0 | 0 | no_speech |
| Nocturne, Scherzo (Orchester) | 314 / 298 s | 0,5 / 0,0 s | 0 | 0 | no_speech |
| Senfl a cappella | 167 s | 74,4 s | 0 | 0 | no_speech |
| Spohr Wiegenlied | 200 s | 29,1 s | 0 | 0 | no_speech |
| Spohr "Sei still" | 376 s | 52,1 s (14 %) | 27 (Wortsalat, Konfidenz 0,22 bis 0,46) | 0 | no_speech |
| Mendelssohn Chor | 264 s | 1,8 s | 3 | 0 | no_speech |
| Bruant 1905 | 170 s | 2,1 s | 0 | 0 | no_speech |
| USAF Band "America" (gesungen) | 174 s | 63,2 s | 53 | 34 ("sweet land of liberty", "pilgrims pride") | transcript |
| Bowlly "Guilty" (Crooner, Englisch) | 191 s | 111,6 s | 98 (Konfidenz 0,81 bis 0,90, Text richtig) | 98 | transcript |
| "I Love You, California" | 237 s | 190,2 s | 230 | 222 | transcript |

Befund: Instrumentalmusik und Rauschen erzeugen mit VAD praktisch nichts (deckt sich mit SPIKE3 Abschnitt 5). Gesang mit verständlichem Text in DE/EN/FR wird transkribiert und ist dann findbar; das ist kein Fehler, sondern gesprochener (gesungener) Text. Kunstgesang ohne verständlichen Text endet als "keine Sprache".

### M-8 Fremde Sprachen und Abfangregel [gemessen]
Mittlere Wortkonfidenz je VAD-Fenster (Fenster mit mindestens 1 Wort):

| Gruppe | Fenster | Wörter | min | p05 | Median | p95 | max |
|---|---|---|---|---|---|---|---|
| nicht unterstützt (AR, ZH, HI, JA, SW, TR, VI) | 43 | 733 | 0,13 | 0,21 | 0,39 | 0,50 | **0,57** |
| Fremd, von Parakeet unterstützt, lateinisch (ES, IT, NL, PL) | 33 | 831 | 0,85 | 0,85 | 0,97 | 1,00 | 1,00 |
| Instanz-Sprache sauber (FLEURS, Memos, Kurzmemos, Podcast) | 125 | 2501 | 0,38 | 0,61 | **0,95** | 1,00 | 1,00 |
| Instanz-Sprache verschlechtert (Rauschen SNR 5/0, Telefon, Gewirr) | 97 | 2123 | 0,25 | 0,32 | 0,84 | 0,99 | 0,99 |
| Musik/Gesang | 36 | 411 | 0,22 | 0,25 | 0,63 | 0,88 | 0,90 |

Beobachtungen: Arabisch wird zu maltesisch aussehendem Text (py3langid `mt`, p bis 1,0), Japanisch/Chinesisch/Türkisch/Vietnamesisch teils zu "Englisch" mit p 0,84 bis 0,97 ("Choping push a cop here", "But this year no spaying this."), Swahili bleibt Swahili (`sw` 1,0). RU und EL kommen in kyrillischer bzw. griechischer Schrift (lateinischer Anteil 0,0). ES/IT/NL/PL werden sauber transkribiert (Konfidenz 0,85 bis 1,0) und nur über die Text-Sprache (p 0,96 bis 1,0) erkannt. `result.lang` von sherpa-onnx ist für den NeMo-Transducer leer (SPIKE2); im Ergebnisobjekt gibt es das Feld (`lang`), es wurde nicht ausgewertet.

Schwellenraster (`grid.py`, behaltene Wörter):

| C | C2 | P | Instanz sauber | Instanz verschlechtert | nicht unterstützt | Fremd (Parakeet) | Musik/Gesang |
|---|---|---|---|---|---|---|---|
| 0,50 | 0,40 | 0,9 | 2493/2501 | 1731/1818 | **36**/733 | 0/1247 | 372/411 |
| 0,60 | 0,45 | 0,9 | 2493/2501 | 1684/1818 | 0/733 | 0/1247 | 367/411 |
| **0,60** | **0,50** | **0,9** | **2493/2501 (99,7 %)** | **1684/1818 (92,6 %)** | **0/733** | **0/1247** | 354/411 |
| 0,60 | 0,60 | 0,9 | 2485/2501 | 1587/1818 | 0/733 | 0/1247 | 304/411 |
| 0,65 | 0,65 | 0,9 | 2478/2501 | 1569/1818 | 0/733 | 0/1247 | 215/411 |

(Fremd = ES, IT, NL, PL, RU, EL; "verschlechtert" hier ohne Stimmengewirr, das gesondert unten steht.) Gewählt: **C = 0,6, C2 = 0,5, P = 0,9, Schrift 0,5, LID ab 3 Wörtern**. Bei C2 = 0,45 bleibt der Abstand zu den nicht unterstützten Sprachen (max. 0,57 allgemein, Fenster mit sicherer Instanz-LID bis ca. 0,45) zu knapp; 0,5 kostet keine weiteren Instanz-Wörter. Stimmengewirr aus Fremdsprachen bei SNR 5 dB: Parakeet transkribiert dann die lautere Fremdsprache (ES-Sätze statt EN), die Regel verwirft diese richtig (EN 106 von 112 Wörtern als `language`); das ist eine Grenze des Modells, nicht der Regel.

### M-9 Dateiurteil [gemessen, `verdict.py`]
| Datei | VAD-Sprache | behalten | conf / language / script verworfen | Urteil |
|---|---|---|---|---|
| lang_de / en / fr | 156 / 88 / 120 s | 375 / 224 / 419 | 0 | transcript |
| lang_es / it / nl / pl | 68 bis 89 s | 0 | 0 / 175 bis 234 / 0 | unsupported |
| lang_ru / el | 96 / 84 s | 0 | 0 / 0 / 191 bzw. 225 | unsupported |
| lang_ar / cmn / hi / ja / sw / tr / vi | 63 bis 110 s, Anteil 55 bis 82 % | 0 | 49 bis 242 Wörter | unsupported (7/7) |
| mix_de10_ar90 | 106 s | 18 (der DE-Satz) | 77 / 139 / 0 | transcript |
| mix_de20_tr80 | 81 s | 38 | 59 / 0 / 0 | transcript |
| mix_de50_es50 | 128 s | 201 | 0 / 163 / 0 | transcript |
| mix_fr30_ja70 | 71 s | 99 | 45 / 0 / 0 | transcript |
| Memo DE in 5 min Stille / in rosa -40 dBFS / unter Musik SNR 10 und 0 dB | 7 bis 20 s | 18 bis 23 | 0 | transcript (4/4) |
| 3 min Musik, dann DE | 44,5 s | 119 | 0 | transcript |
| deg_tel_de / en / fr | 74 bis 150 s | 370 / 212 / 413 | 3 / 3 / 0 | transcript |
| deg_pink5 / deg_pink0 (je DE/EN/FR) | 22 bis 105 s | 47 bis 175 | 0 bis 82 | transcript (6/6) |
| Nicht-Sprache, Instrumental, Kunstgesang (M-7) | 0 bis 74 s | 0 | 0 bis 27 | no_speech (11/11) |

"Praktisch nichts übrig" (D-03-12) ist damit messbar **"0 behaltene Wörter"**: in keiner Datei einer nicht unterstützten Sprache überlebte auch nur ein Fenster, während der kleinste echte Instanzanteil (mix_de10_ar90, ein Satz von 18 Wörtern in 139 s) erhalten bleibt. Die Trennung "keine Sprache" gegen "Sprache nicht unterstützt" bei 0 behaltenen Wörtern: `script + language >= 5` oder (`confidence >= 10` und VAD-Sprache >= 10 s und VAD-Anteil >= 30 %). Kunstgesang hatte Anteile von 1 bis 15 % (Senfl 45 %, aber 0 Wörter), gesprochene Fremdsprache 55 bis 82 %.

### M-10 Kurze Sprachmemos (D-03-11) [gemessen]
| Art | Anzahl | Urteil transcript | Urteil no_speech |
|---|---|---|---|
| Ganze FLEURS-Sätze als Memo (4 bis 23 s, 3 bis 57 Wörter) | 45 + 4 eingebettete | **49** | 0 |
| 4 Wörter, an Wortgrenzen geschnitten (1,5 bis 3,5 s) | 15 | 13 | 2 |
| 2 Wörter (1,5 bis 3 s) | 15 | 9 | 6 |
| 1 Wort (1 bis 2 s) | 15 | 1 | 14 |
| 3-s-Anschnitte (Schnitt mitten im Satz) | 15 | 10 | 5 (davon 3 ohne Sprache im Anschnitt) |

Gegenprobe zu den leeren Kurzmemos (`shortpass.py`, erste 30 s): Bei 1-Wort-Clips liefert Parakeet auch **ohne** VAD in 11 von 12 Fällen kein Wort; die Grenze liegt im Modell, nicht in der VAD. Ein zweiter Durchgang mit Silero-Schwelle 0,3 und Mindestsprache 0,1 s (VAD bleibt an) holt 4 von 5 leeren 2- und 4-Wort-Memos zurück ("Tout bien", "People don't think about them as"), teils mit falschen Wörtern ("With I'm with any."). Negativkontrolle desselben Durchgangs auf 6 Rauschdateien, 2 Orchesterstücken, 3 Gesangsstücken: 0 Wörter außer 1 Wort "Yeah." (Konfidenz 0,24, fällt durch die Abfangregel). Mit Schwelle 0,2 kamen beim Chanson von Bruant 21 Wörter Wortsalat. Empfehlung: zweiter Durchgang mit 0,3/0,1 nur für Dateien bis 60 s, deren erster Durchgang 0 behaltene Wörter hat (siehe Open Question 2, weil es eine zweite Konstante der VAD einführt).

Grenzen der Messung: ein Laptop, synthetische Verschlechterung, FLEURS ist vorgelesene Sprache, je Sprache 10 bis 15 Clips (5 bis 14 Fenster), keine echten Behörden- oder Dialektaufnahmen, keine WER-Messung der behaltenen Wörter (Referenztexte nicht ausgewertet). Die Schwellen sind deshalb MEDIUM; ein Test im Repo muss sie gegen einen erzeugten Korpus festhalten.

## Common Pitfalls

### Pitfall 1: Zeitachse bei Edit-List und Priming
**What goes wrong:** Sprung und spätere Untertitel liegen bei Handy-Videos und Bildschirmaufnahmen um bis zu Sekunden daneben.
**Why:** Rohes PCM verliert die Zeitstempel; ohne Füllen beginnt Sample 0 beim ersten Audio-Paket (M-1).
**How to avoid:** `aresample=async=1:first_pts=0` immer; Test mit Beep-Datei mit `-itsoffset`.
**Warning signs:** Beep-Test weicht um ein Vielfaches von 21,3 ms (AAC-Priming) oder um den Versatz ab.

### Pitfall 2: Pipe statt Datei
**What goes wrong:** MP4/M4A/MOV mit moov am Ende fallen still als "defekt" aus; kleine Testdateien gehen durch, große nicht (M-3).
**How to avoid:** Immer Temp-Datei; Test mit einer Datei deutlich über dem Probe-Puffer (> 10 MB).

### Pitfall 3: Web-Dialog nutzt keinen Cursor
**What goes wrong:** Weniger als `limit` Einträge (z. B. weil Rechteprüfung Treffer verwarf oder weil nach 3 Stellen abgebrochen wurde) lassen "Mehr laden" verschwinden; weitere Treffer sind im Web unerreichbar.
**How to avoid:** Runden mit Überabruf bis genau `limit`; Folge deterministisch, damit `limit + 5` mit denselben 5 beginnt; Test "Antwort(limit=10) beginnt mit Antwort(limit=5)".

### Pitfall 4: Parakeet-Wortsalat wird als Instanz-Sprache erkannt
**What goes wrong:** Japanisch, Chinesisch, Türkisch erscheinen als englischer Text im Index.
**How to avoid:** Konfidenzregel C = 0,6 je Fenster, Text-Sprache nur als zusätzlicher Filter (M-8).

### Pitfall 5: Dateigröße der Phase-2-Einstellung
**What goes wrong:** `max_file_size_mb` hat Standard 100 MB (`settings.py`); fast jedes Video und jede lange Aufnahme (12 h MP3 128k = ca. 690 MB) wird als `too_large` nie transkribiert.
**How to avoid:** Owner-Entscheid zum Standard (Open Question 3) und Plattenreserve für die Temp-Datei (`free_bytes` prüft `fetch_to_tempfile` bereits).

### Pitfall 6: Herkunft "Ereignis" geht verloren
**What goes wrong:** Crawl und Listener schreiben beide `kind = content`; ohne Herkunft gibt es kein "neue Dateien zuerst" (D-03-05).
**How to avoid:** Spalte `origin` in `avs_queue` (Migration), `ITEM_KEYS` und Claim-Vertrag erweitern, `file_ref.origin` übernehmen; Lockstep der Versionen beachten.

### Pitfall 7: Revision je Stück und Index-Last
**What goes wrong:** Jedes Stück baut die Segmente der ganzen Datei neu; bei 72 Stücken (12 h) wächst die Arbeit quadratisch.
**How to avoid:** Für Phase 3 hinnehmbar (Segmente sind kurz, Tantivy-Commit einmal je Stück), aber messen; Alternative später: nur neue Segmente veröffentlichen und alte Revision behalten [ASSUMED: Aufwand vertretbar].

### Pitfall 8: Schnitt einer Kurzdatei am Dateiende
**What goes wrong:** Endet die Sprache ohne Pause am Dateiende, liefert Parakeet für das letzte Fenster teils 0 Wörter (memo3s_en_us_02: 1,8 s VAD-Sprache, 0 Wörter; das volle Memo liefert die Wörter).
**How to avoid:** Das 0,5-s-Polster der Pipeline beibehalten; Kurzdatei-Nachlauf (Open Question 2).

### Pitfall 9: Rechteprüfung pro Stelle statt pro Datei
**What goes wrong:** Bis zu 3 Stellen je Datei je Stufe verdreifachen die teuren `readableFile`-Aufrufe und sprengen das 2,5-s-Budget.
**How to avoid:** Cache `fileId => File|null` je Anfrage; Ausschlussprüfung ebenfalls je fileId.

## Code Examples

### Tonspur nach D-03-10 wählen
```python
# Quelle: ffprobe-Ausgabe lokal geprüft (M-6)
def pick_audio_stream(probe: dict) -> int | None:
    audio = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
    for s in audio:
        if s.get("disposition", {}).get("default") == 1:
            return int(s["index"])
    return int(audio[0]["index"]) if audio else None
```

### Stufen-Folge im Container
```python
# Quelle: Ableitung aus NC-Dialoglogik (Pattern 4); deterministisch, ohne Serverzustand
def tiered(stellen_by_file: dict[int, list[tuple[float, int, str]]], per_tier: int = 3) -> list[tuple[int, int, str]]:
    # stellen_by_file: file_id -> [(score, start_ms, excerpt)], bereits ohne unzulässige Revisionen
    files = sorted(stellen_by_file, key=lambda f: (-max(s[0] for s in stellen_by_file[f]), f))
    ordered = {f: sorted(stellen_by_file[f], key=lambda s: (-s[0], s[1])) for f in files}
    out, tier = [], 0
    while True:
        added = False
        for f in files:
            for score, start_ms, excerpt in ordered[f][tier * per_tier:(tier + 1) * per_tier]:
                out.append((f, start_ms, excerpt))
                added = True
        if not added:
            return out
        tier += 1
```

### Link-Zeit und Zeitmarke (TRANS-08)
Bestehende Regeln bleiben: `clock()` schneidet Millisekunden ab, der Link nutzt `intdiv(startMs, 100) / 10`. Parakeet-Wortanfänge liegen höchstens 0,09 s zu früh (SPIKE2 1.3), mit Abrunden auf 0,1 s beginnt die Wiedergabe also höchstens ca. 0,19 s vor dem Wort und nie danach.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Unified-Search-Provider mit Cursor-Seiten | Web-Dialog fragt mit wachsendem `limit` neu, Cursor nur noch für API-Clients | NC stable33/34 (Quelltext 14.11. gelesen) | Präfix-stabile Folge nötig |
| ffmpeg `latest`-Builds | BtbN Monatsletzter (2 Jahre gehalten) | STACK.md | Tag `autobuild-2026-10-31-12-59` |

**Deprecated/outdated:**
- Fester `SEARCH_LIMIT = 25` im Provider: ersetzt durch `ISearchQuery::getLimit()`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | BtbN ffmpeg 8.1.3 verhält sich bei `-ss`, `aresample first_pts` und Positivlisten wie gyan 8.1.1 | Standard Stack | Zeitachse/Härtung weicht im Container ab; CI-Beep-Test fängt es |
| A2 | py3langid ist eine vertrauenswürdige Abhängigkeit (slopcheck lief nicht) | Supporting | Lieferkettenrisiko; Owner-Checkpoint |
| A3 | Die Parakeet-Abfangregel (Konfidenz + Schrift + Text-Sprache) erfüllt TRANS-03 anstelle der Whisper-Formulierung "Sicherheit < 0,5" | Pattern 5 | Anforderungstext muss angepasst oder bestätigt werden |
| A4 | Die Schwellen (0,6 / 0,5 / 0,9 / 0,5) tragen auf echten Aufnahmen (Sitzungen, Dialekt, Telefon) | M-8 | Echte DE-Sprache wird verworfen oder Wortsalat bleibt; Gate auf erweitertem Korpus nötig |
| A5 | FairPlay/Audible-Dateien sind über `drms`/`aavd`-Boxen erkennbar | M-5 | Grund "damaged" statt "protected" (kein Sicherheitsrisiko) |
| A6 | ffmpeg-Auto-Spurwahl ist keine feste Regel | M-6 | keins, da explizites `-map` empfohlen |
| A7 | Ein Browser gleicht den Encoder-Delay von VBR-MP3 ohne LAME-Kopf ebenfalls nicht aus | M-2 | 25 ms Versatz, unter der Wahrnehmungsgrenze für einen Sprung |
| A8 | Neuaufbau der Segmente je Stück ist für 12-h-Dateien schnell genug | Pitfall 7 | lange Commits im Index-Worker; messen im Plan |

## Open Questions

1. **D-03-02 bei nur einer (oder wenigen) Treffer-Dateien**
   - What we know: Der Web-Dialog zeigt "Mehr laden" nur bei genau `limit` Einträgen und schickt keinen Cursor.
   - What's unclear: Ob eine Seite mit 5 Stellen derselben Datei (3 aus Stufe 1, 2 aus Stufe 2) im Sinne von D-03-02 ist, wenn es keine nächste Datei gibt.
   - Recommendation: Stufen-Folge wie Pattern 4 (füllt auf). Die Alternative (Seite endet nach 3 Stellen) macht weitere Stellen im Web unerreichbar. Owner bestätigen lassen.
2. **Kurzdatei-Nachlauf mit zweiter VAD-Schwelle**
   - What we know: 1-Wort-Memos erkennt Parakeet auch ohne VAD kaum; 2- und 4-Wort-Memos fallen in 8 von 30 Fällen auf "keine Sprache"; ein zweiter Durchgang mit Silero 0,3 / 0,1 s holt 4 von 5 der geprüften zurück, ohne neue Treffer auf Rauschen/Musik (nach Abfangregel).
   - What's unclear: Ob der Owner eine zweite, feste VAD-Konstante für Dateien bis 60 s akzeptiert (VAD bleibt an).
   - Recommendation: Ja, als Konstante mit Test; sonst Grenze ehrlich dokumentieren ("Memos unter ca. 3 Wörtern werden oft nicht erkannt").
3. **Standard `max_file_size_mb = 100`**
   - What we know: Phase-2-Einstellung, Dateien darüber bleiben `too_large`. Videos und lange Aufnahmen liegen fast immer darüber.
   - Recommendation: Owner entscheidet einen höheren Standard (z. B. 4096 MB) zusammen mit einer Plattenreserve; Höchstdauer 12 h ist die eigentliche Grenze (D-03-08).
4. **Text "Vorläufig" und Hinweis der Abspielseite**
   - Recommendation: Untertitelwort EN "Preliminary", DE "Vorläufig", FR "Provisoire"; Hinweis EN "Preliminary transcript, it will be improved automatically", DE "Vorläufiges Transkript, wird automatisch verbessert", FR "Transcription provisoire, elle sera améliorée automatiquement". Vor dem Bau dem Owner zeigen (D-03-04).
5. **Gründe-Texte für die Abspielseite (D-03-13)**
   - Codes: `no_speech`, `unsupported_language`, `too_long`, `no_audio`, `damaged`, `protected`, `format_unsupported`, `too_large` (Phase 2). Texte DE/EN/FR vor dem Bau zeigen.
6. **py3langid als Abhängigkeit**
   - Recommendation: freigeben; ohne Text-Sprachkennung blieben ES/IT/NL/PL-Aufnahmen (Konfidenz 0,85 bis 1,0) als Fremdtext im Index. Alternative Stoppwort-Quote ist nicht als Regel gemessen.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| ffmpeg/ffprobe (lokal, Windows) | Tests M-1 bis M-6, lokale pytest-Läufe | ja | 8.1.1 (gyan.dev) | - |
| ffmpeg BtbN im Image | Produkt | nein (noch nicht im Dockerfile) | n8.1.3 geplant | Build-Stage mit sha256 |
| uv / Python 3.13 | Backend | ja | uv vorhanden, Python 3.13 per uv | - |
| sherpa-onnx 2.0.1 | Engine | ja (Scratch-venv) | 2.0.1 | - |
| Parakeet + Silero (lokal) | Engine-Tests | ja (Scratchpad, sha256 geprüft) | Pins oben | Download per Skript |
| Docker | e2e | vorhanden, aber für diese Sitzung gesperrt (parallele Sitzung) | - | e2e nur in CI |
| freier RAM | Modelltests | 6,0 bis 6,6 GB frei gemessen | - | seriell, unter 4 GB warten |

**Missing dependencies with no fallback:** keine.
**Missing dependencies with fallback:** ffmpeg im Image (Build-Stage im Plan).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.2.0 (backend), phpunit 11.5 (php, CI), Bash + curl im CI-Workflow "Discovery acceptance" |
| Config file | `backend/pyproject.toml`, `php/phpunit.xml`, `.github/workflows/discovery-e2e.yml` |
| Quick run command | `cd backend && uv run pytest -q -x` |
| Full suite command | `cd backend && uv run ruff check . && uv run ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright && uv run vulture && uv run pytest -q` (PHP und e2e in CI) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MEDIA-01 | 10 Formate dekodieren, MP4 moov am Ende > 10 MB | unit (ffmpeg, Medien per Test erzeugt) | `uv run pytest tests/test_media_decode.py -x` | ❌ Wave 0 |
| MEDIA-02 | Standardspur/erste Spur; Beep mit `-itsoffset 2` bei 7,0 s ± 5 ms; `-ss`-Stücke ± 5 ms | unit | `uv run pytest tests/test_media_timeline.py -x` | ❌ Wave 0 |
| MEDIA-03 | ffconcat-als-mp3 abgewiesen, Zufallsbytes/abgeschnitten = damaged, CENC = protected, Wandzeit-Abbruch | unit | `uv run pytest tests/test_media_hardening.py -x` | ❌ Wave 0 |
| MEDIA-04 | Dateiurteil aus Zählern (Tabelle M-9 als Fälle) | unit | `uv run pytest tests/test_catch_rule.py -x` | ❌ Wave 0 |
| TRANS-01 | Spike-3-Konstanten unverändert; Engine liefert Wörter für eine Sprachdatei | unit + Modelltest (markiert, CI mit Modell-Cache) | `uv run pytest tests/test_engine_constants.py tests/test_engine_model.py -x` | ❌ Wave 0 |
| TRANS-02 | kein Einstellungs-/Env-/Routenweg für VAD | unit (Quelltext-Gate wie `test_read_proof_gate.py`) | `uv run pytest tests/test_vad_gate.py -x` | ❌ Wave 0 |
| TRANS-03 | Fensterregel mit Fällen aus M-8 (Wortsalat EN p 0,97 + Konfidenz 0,34 -> verworfen usw.) | unit | `uv run pytest tests/test_catch_rule.py -x` | ❌ Wave 0 |
| TRANS-07 | Stückgrenze in Pause, keine Dopplung; Abbruch nach Commit k -> Fortsetzen bei k+1; Unterbrechen durch event-Job | unit (Engine gefälscht) | `uv run pytest tests/test_preview_worker.py -x` | ❌ Wave 0 |
| TRANS-08 | Wortzeit + Stückversatz = Medienzeit; Link rundet abwärts | unit | `uv run pytest tests/test_preview_worker.py -k timeline -x` | ❌ Wave 0 |
| SRCH-01 | Stufen-Folge, Präfix-Stabilität `limit` 5/10/15, offset ohne Dubletten/Lücken | unit (backend) + phpunit (Provider) | `uv run pytest tests/test_search_tiers.py -x`; `php.yml` ProviderTest | ❌ Wave 0 |
| SRCH-02 | `preview` im Treffer, Untertitel mit "Preliminary" (l10n DE/EN/FR) | phpunit + `test_trilingual.py` | CI `php.yml`; `uv run pytest tests/test_trilingual.py -x` | teilweise |
| SRCH-03 | Paritätstest HTTP-Pfad: je Nutzer Treffermenge der OCS-Suche == lesbare und transkribierte Dateien laut WebDAV (entzogene Freigabe, Gruppenordner-ACL, Papierkorb) | e2e (CI, echte Sprachdatei + Parakeet) | Workflow `discovery-e2e.yml`, neue Phase `search-parity` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** betroffene pytest-Datei, dann `cd backend && uv run pytest -q -x`
- **Per wave merge:** Full suite command
- **Phase gate:** Full suite grün + CI (php.yml, discovery-e2e inkl. search-parity) vor `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/media_fixtures.py`: erzeugt Beep-/Formatdateien per ffmpeg zur Laufzeit (nichts eingecheckt), skip mit Grund, wenn ffmpeg fehlt
- [ ] ffmpeg im Python-CI-Job (`python.yml`): BtbN-Asset mit sha256 wie im Dockerfile
- [ ] Modell-Cache in CI (actions/cache, Schlüssel = sha256 der Modelle) für Engine- und e2e-Tests
- [ ] Sprachdatei für e2e: ein FLEURS-Clip (CC-BY-4.0) per Skript mit festem sha256 laden, nicht einchecken
- [ ] `scripts/research/phase3/` mit den Messskripten dieser Research (ohne Daten), damit die Schwellen nachmessbar bleiben
- [ ] Korpus-Test der Abfangregel: kleiner per Skript erzeugter Korpus (Rauschen, Sinus synthetisch; Sprache aus FLEURS) als markierter Langtest

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein (AppAPI-Signatur bestehend) | nc_py_api |
| V3 Session Management | nein | - |
| V4 Access Control | ja | PHP-Recheck je fileId zur Abfragezeit, Ausschluss je Vorschlag, Grund auf der Abspielseite nur unter denselben Regeln (D-03-13) |
| V5 Input Validation | ja | pydantic für `/search` (`offset` begrenzt, `limit` 1 bis 50), ffmpeg-Positivlisten, ffprobe-JSON defensiv lesen |
| V6 Cryptography | nein (nur sha256 für Integrität, hashlib) | hashlib |
| V12 Files and Resources | ja | Temp-Datei ohne Endung, Löschen auf jedem Weg, Plattenreserve, `-fs`, Wandzeit |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Bösartige Mediendatei liest lokale Dateien (concat/HLS) | Information Disclosure | `-protocol_whitelist file`, `-format_whitelist` (M-4) |
| Decoder-Absturz / Endlosschleife | Denial of Service | ffmpeg im Unterprozess, Wandzeit je Stück, `-fs`, `-threads 1`, Exit-Code prüfen |
| Datei während der Vorschau geändert (falsches Transkript an fremdem Inhalt) | Tampering | sha256 der Temp-Datei gegen `media_key`, sonst Abbruch |
| Treffer aus nicht lesbarer Datei, Probe über Grund-Text | Information Disclosure | Recheck je fileId, Grund nur für erlaubte Verweise, sonst Antwort wie "kein Transkript" |
| Paging-Cursor als Hebel (riesiger Offset) | Denial of Service | Offset-Obergrenze im Container und in PHP (Findling `MAX_CONTAINER_OFFSET`-Muster) |
| Logs mit Inhalt | Information Disclosure | nur ids, Codes, Zähler; nie Wörter, Begriffe, Pfade |

## Sources

### Primary (HIGH confidence)
- Lokale Messungen M-1 bis M-10 (Skripte im Scratchpad, Befehle oben)
- `nextcloud/server` stable33 und stable34: `core/src/components/UnifiedSearch/UnifiedSearchModal.vue` (Zeilen 155, 185, 509 bis 577, 669 bis 671), `core/Controller/UnifiedSearchController.php` (Zeilen 79 bis 104), `lib/private/Search/SearchQuery.php` (`LIMIT_DEFAULT = 5`), `lib/public/Search/SearchResult.php`
- Repo-Quellen: `php/lib/Search/Provider.php`, `php/lib/Service/ExAppService.php`, `php/lib/Controller/PageController.php`, `php/lib/Db/QueueMapper.php`, `backend/src/audio_video_search_backend/api/search.py`, `api/excerpt.py`, `index/publish.py`, `index/schema.py`, `store/schema.sql`, `store/repo.py`, `worker/capture.py`, `settings.py`, `model/provenance.py`
- Findling: `php/lib/Search/Provider.php` (Cursor, paginated), `php/lib/Service/SearchService.php` (Runden, Überabruf, Prüfbudget), `backend/src/findling/memory_guard.py`
- `C:/Users/Student/audio-video-spike-2026-11-04/SPIKE3-REPORT.md` Abschnitte 1, 5, 6, 11, 12; `SPIKE2-REPORT.md` 1.3; `spike3/scripts/bench3.py`
- https://ffmpeg.org/ffmpeg-resampler.html (`async`, `first_pts`)
- GitHub API `BtbN/FFmpeg-Builds` Releases (Asset-Digests 2026-10-31)
- `ffmpeg -h full` (8.1.1): `protocol_whitelist`, `format_whitelist`, `codec_whitelist`, `fs`, `max_alloc`, `advanced_editlist`

### Secondary (MEDIUM confidence)
- https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 (25 Sprachen, automatische Spracherkennung ohne dokumentierte Ausgabe)
- PyPI-JSON und GitHub `adbar/py3langid` (Version, Lizenz, Abhängigkeiten)

### Tertiary (LOW confidence)
- keine

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (Pins und sha256 geprüft); py3langid MEDIUM (Owner-Freigabe offen)
- Architecture: HIGH für Medien-Eingang und Suchvertrag, MEDIUM für Job-Tabelle (Ermessen, nicht gebaut)
- Pitfalls: HIGH (fast alle gemessen oder im Quelltext belegt)
- Schwellen: MEDIUM (gemessen, kleiner und teils synthetischer Korpus)

**Research date:** 2026-11-14
**Valid until:** 2026-12-14 (Nextcloud-Dialoglogik und BtbN-Tags vor dem Bau erneut prüfen)
