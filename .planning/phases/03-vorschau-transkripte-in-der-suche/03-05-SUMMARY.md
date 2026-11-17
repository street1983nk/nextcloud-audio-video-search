---
phase: 03-vorschau-transkripte-in-der-suche
plan: 05
subsystem: media-intake
tags: [ffmpeg, ffprobe, lgpl, sha256, edit-list, härtung, drm, tests]
requires: []
provides:
  - "Dockerfile-Stage ffmpeg: BtbN autobuild-2026-10-31-12-59, n8.1.3 lgpl, sha256 je Architektur, Abbruch bei --enable-gpl; /usr/local/bin/ffmpeg und ffprobe in runtime"
  - "python.yml: Schritt 'Install the pinned LGPL ffmpeg' (gleiches Asset, gleicher sha256), setzt AVS_FFMPEG/AVS_FFPROBE"
  - "media/probe.py: probe(), pick_audio_stream(), has_protection_boxes(), run_tool(), ProbeResult, MEDIA_REASONS, DEMUXERS"
  - "media/decode.py: decode_chunk(), DecodeResult, DEMUXERS (aus probe), SAMPLE_RATE, max_bytes()"
  - "tests/media_fixtures.py: Fixtures ffmpeg_bin, ffprobe_bin, encoders (über pytest_plugins in conftest.py), Erzeuger für Töne, Beeps, zehn Formate"
affects: [03-13, 03-15, 03-20]
tech-stack:
  added: ["ffmpeg/ffprobe 8.1.3 LGPL (BtbN, statisch) im Image und in CI"]
  patterns:
    - "Unterprozess über run_tool: Popen mit Argumentliste, communicate(timeout), bei Überschreitung kill + reap, exit_code None"
    - "Gründe als Final-Konstanten; Logzeile nur reason und exit_code"
    - "Testmedien nur zur Laufzeit; Skip mit Grund, unter CI=true Fehlschlag"
key-files:
  created:
    - backend/src/audio_video_search_backend/media/__init__.py
    - backend/src/audio_video_search_backend/media/probe.py
    - backend/src/audio_video_search_backend/media/decode.py
    - backend/tests/media_fixtures.py
    - backend/tests/test_media_decode.py
    - backend/tests/test_media_timeline.py
    - backend/tests/test_media_hardening.py
  modified:
    - backend/Dockerfile
    - .github/workflows/python.yml
    - backend/tests/test_dockerfile.py
    - backend/tests/conftest.py
decisions:
  - "DEMUXERS und die Gründe liegen in probe.py, decode.py importiert sie (sonst Importzyklus); decode.DEMUXERS bleibt als Name erreichbar"
  - "Zeitüberschreitung ergibt damaged (wie im Plan), Exit ungleich 0 mit 'not on whitelist' ergibt format_unsupported"
  - "Zufallsbytes: Ergebnis hängt an der Endung (gemessen, siehe unten); Tests halten das gemessene Verhalten fest"
metrics:
  duration: "ca. 75 min"
  completed: 2026-11-14
  tasks: 2
  files: 11
---

# Phase 3 Plan 05: Gehärteter Medien-Eingang Summary

LGPL-ffmpeg 8.1.3 (BtbN, Monatsletzter Oktober) per sha256 je Architektur im Image und im Python-CI-Job; `probe()` wählt die Tonspur nach D-03-10 und erkennt DRM, `decode_chunk()` dekodiert Stücke mit Positivlisten, Edit-List-Korrektur, Byte- und Zeitgrenze; zehn Formate, Zeitachse und Härtung durch Tests mit Gegenprobe belegt.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 | afd708e | build(03-05): LGPL-ffmpeg im Image und in CI, per sha256 gepinnt |
| 2 RED | 87a5dda | test(03-05): Medien-Eingang als Vertrag mit Gegenproben |
| 2 GREEN | 6a8bacf | feat(03-05): gehärteter Medien-Eingang |

## Belege

- **sha256 nachgeprüft:** Beide Assets aus `autobuild-2026-10-31-12-59` geladen; `a64f3171...f1f3` (linux64-lgpl-8.1) und `2ea30086...0809` (linuxarm64-lgpl-8.1) stimmen. Archiv enthält `ffmpeg-n8.1.3-27-g8dca1586f4-linux64-lgpl-8.1/bin/{ffmpeg,ffprobe,ffplay}`; nur ffmpeg und ffprobe werden kopiert.
- **LGPL nachgeprüft:** Konfigurationszeile im Linux-Binary gelesen: `--enable-version3`, `--enable-libmp3lame`, `--enable-libopus`, `--enable-libvorbis`, `--enable-libvpx`, `--enable-gpl` null Treffer. Die Test-Encoder (libmp3lame, libopus, libvorbis, libvpx, mpeg4, aac, flac, alac, pcm_s16le) sind damit auch in CI vorhanden.
- **CI-Entpackbefehl** (`tar --strip-components=2` auf die zwei Member) lokal am echten Archiv ausgeführt: genau ffmpeg und ffprobe.
- **hadolint** 2.15.1.3: ohne Befund.
- **Gates:** ruff check, ruff format --check, pyright (latest) 0 Fehler, vulture sauber; pytest **1187 passed, 0 skipped** (vorher 1123), Coverage 95,70 % (probe.py 92 %, decode.py vollständig). Mediendateien mit `CI=true`: 59 passed, kein Skip.

### Gegenproben

- Gleichheit Image/CI: Kopie mit geändertem sha256, anderem Release-Tag oder fehlendem `FFMPEG_BUILD` wird gemeldet (zwei Tests).
- Mutationen der Dockerfile-Stage (gpl-Asset, fehlende GPL-Prüfung, falscher arm64-Hash, ffplay kopiert, CI-Hash abweichend): jede von einem Test gefangen.
- Mutationen der Umsetzung, jede gefangen: ohne `first_pts=0` (2 Fehlschläge), ohne Positivlisten (2), ohne DRM-Prüfung (1), ohne Standardspur-Regel (2), `-map 0:a:0` statt Index (1), `-ss` kaputt (24), ohne `process.kill()` (1, Test mit hängendem Prozess; vorher nicht gefangen, Test ergänzt).
- In den Tests selbst: ffconcat ohne Positivlisten liest secret.wav (440 Hz im PCM); Edit-List-MP4 ohne Filter liefert den Beep bei ca. 5,02 s (eigener ffmpeg-Aufruf); dieselbe M4A ohne Verschlüsselung ist nicht protected; dieselbe Dekodierung ohne Mini-Wandzeit gelingt; ffmpeg-stderr enthält den HIDDEN-Marker, die Logzeilen nicht; `+faststart`-Datei fällt aus der moov-am-Ende-Prämisse; Skip-Regel schlägt unter `CI=true` fehl.

## Gemessene Abweichungen je Format (ffmpeg 8.1.1 gyan, lokal)

Beep bei 5,000 s in 10-s-Datei, Ganzdatei und Stück ab 3 s:

| Format | Ganzdatei | Stück ab 3 s | Länge |
|---|---|---|---|
| MP3, M4A, WAV, OGG, Opus, FLAC, MP4, MOV | +0,12 ms | +0,13 ms | 10,0000 s |
| MKV (mpeg4 + AAC) | -0,12 ms | +0,06 ms | 9,9998 s |
| WebM (VP8 + Opus) | +1,12 ms | +1,12 ms | 10,0000 s |

Edit-List (Video 12 s, Audio `-itsoffset 2`): Beep 7,0 s innerhalb 5 ms, Länge 12,0 s; ohne Filter 4,95 bis 5,10 s. Stück 600 bis 720 s des 12-min-Signals: Beeps bei 7,25 und 67,25 s innerhalb 5 ms für WAV, M4A, Opus, MKV. Große Dateien mit moov am Ende: M4A (ALAC, 60 s Rauschen) und MP4 (mpeg4 q1, 20 s), beide über 10 MiB, vollständig dekodiert.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Zufallsbytes mit Endung .mp3 sind für ffprobe kein Fehler**
- **Found during:** Task 2
- **Issue:** Der Plan erwartet `damaged` aus probe. Gemessen: der mp3-Demuxer nimmt die Datei allein wegen der Endung, ffprobe meldet Exit 0 mit einer Tonspur ohne Dauer. Erst ffmpeg scheitert (Exit 69, keine Samples).
- **Fix:** Tests halten das gemessene Verhalten fest: Zufallsbytes als .m4a/.wav/.ogg/.mkv ergeben in probe und decode `damaged`; als .mp3 akzeptiert probe, decode ergibt `damaged` (mit und ohne erwartete Länge). Der HIDDEN-Test nutzt .m4a, weil ffmpeg dort den Pfad in stderr schreibt ("Header missing" bei .mp3 enthält keinen Pfad, die Gegenprobe wäre leer).
- **Commit:** 87a5dda

**2. [Rule 1 - Bug] Zufallsbytes ohne Medienendung sind format_unsupported**
- **Found during:** Task 2
- **Issue:** Unter `.bin` (geplante Temp-Endung in 03-13) greift der Demuxer "bin" und die Positivliste weist ab: Grund `format_unsupported` statt `damaged`.
- **Prüfung:** Alle zehn Formate (plus MP3 ohne Xing/ID3) unter `.bin` von Hand geprobt: werden am Inhalt richtig erkannt (wav, mp3, mov, ogg, flac, matroska). Nur Müll landet bei format_unsupported. Als Test festgehalten.
- **Commit:** 87a5dda

**3. [Rule 3 - Blocking] lavfi-Ausdrücke mit Kommas gequotet, Ton-Amplitude**
- Kommas in `aevalsrc` zerlegten die Filterkette; Ausdruck in einfache Anführungszeichen gesetzt. `sine` liefert Amplitude 1/8, daher `volume=3.2` für Spitze 0,4. Nur Testerzeuger.

**4. [Rule 2] Test für den Kill eines hängenden Prozesses ergänzt**
- Die Mutation "ohne kill" blieb unentdeckt, weil ffmpeg eine 600-s-WAV schneller fertig dekodiert, als `communicate()` wartet. Neuer Test `test_a_hung_tool_is_killed_at_its_wall_time` mit einem 60-s-Schlafprozess; Mutation jetzt gefangen.

**5. Fixtures über `pytest_plugins` in tests/conftest.py**
- Statt Import in jede Testdatei (F401/F811/vulture), zwei Zeilen in conftest.py (nicht in files_modified des Plans).

**6. Frequenzmessung im Test ab 0,5 s**
- AAC in MKV dekodiert die ersten ca. 22 ms nahezu still (beide Spuren gleich). Die Zeitachse ist davon nicht verschoben (Beep-Messung oben, -0,12 ms). `dominant_hz` misst deshalb ab 0,5 s.

## TDD Gate Compliance

RED 87a5dda (Tests ohne Modul `media`, Sammlung bricht mit ModuleNotFoundError ab), GREEN 6a8bacf. Die RED-Tests wurden vor dem GREEN-Commit an gemessenes ffmpeg-Verhalten angepasst (Abweichungen 1, 2, 6); der Commit zeigt den Stand nach der Anpassung.

## Offene Punkte

- **Image-Beleg** (Stage baut, `ffmpeg -version` ohne `--enable-gpl` auf amd64 und arm64) kommt aus CI in Plan 03-20; lokal kein Docker.
- **CI-Lauf der Medientests** gegen den BtbN-Build 8.1.3 steht aus (lokal 8.1.1 gyan, Windows) [ASSUMED: Gleichverhalten, RESEARCH].
- **Für 03-13:** Mit Temp-Endung `.bin` wird Müll `format_unsupported`, nicht `damaged`. Falls der nutzersichtbare Grund "beschädigt" lauten soll, braucht 03-13 eine Regel (z. B. format_unsupported mit Demuxer bin/tty als damaged werten) oder die Endung der Originaldatei. Owner-Entscheid oder Planerentscheid.
- Zufallsbytes als .mp3 laufen durch probe (ohne Dauer); der Worker in 03-13/03-15 muss `duration_ms is None` zulassen und auf decode-Grund vertrauen.

## Threat Flags

Keine neue Angriffsfläche außer der geplanten (T-03-14 bis T-03-18 umgesetzt). Neue ausgehende Verbindung nur zur Build-/CI-Zeit (GitHub-Release, sha256-geprüft).

## Self-Check: PASSED

- Dateien vorhanden: media/__init__.py, probe.py, decode.py, media_fixtures.py, test_media_decode.py, test_media_timeline.py, test_media_hardening.py.
- Commits vorhanden: afd708e, 87a5dda, 6a8bacf.
