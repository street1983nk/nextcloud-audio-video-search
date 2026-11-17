---
phase: 03-vorschau-transkripte-in-der-suche
plan: 15
subsystem: worker, lifespan
tags: [preview, lifespan, settings, max-duration, truth-conditions, corpus, model, tdd]
requires: ["03-07", "03-11", "03-13"]
provides:
  - "main.py: Task preview im Lifespan, Abbruch im finally"
  - "worker/preview.py: SETTINGS_REFRESH_SECONDS (300), read_admin_settings(), Preview(read_settings=...), Preview.sync_limits(reader)"
  - "tests/test_replaced_file.py: Beleg der Wahrheitsbedingungen T6/T7"
  - "tests/test_preview_corpus.py: Korpus-Langtest mit echtem Modell, echtem ffprobe/ffmpeg und echtem Worker"
affects: [03-17, 03-18]
tech-stack:
  added: []
  patterns:
    - "Einstellungsleser als Konstruktor-Parameter; conftest ersetzt den Nextcloud-Leser durch einen, der wie ein unerreichbares Nextcloud scheitert"
key-files:
  created:
    - backend/tests/test_preview_settings.py
    - backend/tests/test_replaced_file.py
    - backend/tests/test_preview_corpus.py
  modified:
    - backend/src/audio_video_search_backend/main.py
    - backend/src/audio_video_search_backend/worker/preview.py
    - backend/tests/conftest.py
    - backend/tests/test_main.py
decisions:
  - "Nur eine höhere Grenze stellt zurück; gleich oder niedriger fasst keinen Job an (sonst käme ein too_long-Job ohne bekannte Dauer alle 5 min zurück)"
  - "Erst requeue_too_long, dann set_max_duration_hours in einem run_locked-Aufruf: ein Stopp dazwischen liest beim nächsten Mal die alte Grenze und stellt erneut zurück (folgenlos)"
  - "Der Abgleich läuft unabhängig vom Companion-Zustand beim Start und alle 300 s; ein Lesefehler loggt nur den Fehlertyp und lässt die gespeicherte Grenze stehen"
  - "Standardleser in preview.py (nc.nc_app + settings.read), nicht in nc.py: settings importiert nc, nc.py würde sonst zirkulär"
  - "TR-Clip erwartet unsupported_language (D-03-22); zusätzlich ES-Clip als WebM, ebenfalls unsupported_language"
metrics:
  duration: "ca. 1 h 15 min"
  completed: 2026-11-14
  tasks: 3
  files: 7
---

# Phase 3 Plan 15: Vorschau im Container, Höchstdauer beim Anheben, T6/T7 und Korpus-Langtest Summary

Der Container startet den Vorschau-Worker im Lifespan; der Worker liest die Höchstdauer beim Start und alle 300 s und stellt beim Anheben die passenden too_long-Jobs zurück. Die Wahrheitsbedingungen T6/T7 sind durch den echten Ereignisweg belegt, und ein Korpus-Langtest mit echtem Modell zeigt no_speech, transcript und unsupported_language an ganzen Dateien.

## Commits

| Task | Commit | Betreff |
|------|--------|---------|
| 1 RED | ebb8ce9 | test(03-15): Vorschau im Lifespan und Höchstdauer-Abgleich (rot) |
| 1 GREEN | 8a03674 | feat(03-15): Vorschau im Container, Höchstdauer wirkt beim Anheben |
| 2 | 4ff38e1 | test(03-15): ersetzte Datei kommt zurück in den Arbeitsvorrat (T6/T7) |
| 3 | a3b77e9 | test(03-15): Korpus-Langtest der Vorschau mit echtem Modell |

Alle nur lokal, Autor und Committer street1983nk <k.cherif@outlook.de>, nichts gepusht.

## Task 1: Lifespan und Einstellungsabgleich

- `main.py`: `preview_task = start_background(preview.run_forever(services), "preview")` nach capture, `preview_task.cancel()` im finally. Der Worker rechnet nur bei Companion ok und `procure.models_ready()` (Bestand aus 03-13).
- `Preview.sync_limits(reader)`: Leser außerhalb des Locks, dann ein `run_locked`-Aufruf: alte Grenze lesen, bei höherer Grenze `requeue_too_long(h * 3 600 000)`, dann speichern. Lesefehler: Warnung mit `error_type`, Grenze bleibt.
- `run_forever` ruft den Abgleich vor der ersten Runde und danach, sobald `SETTINGS_REFRESH_SECONDS` (300) über die Uhr des Workers abgelaufen sind.
- Tests (test_preview_settings.py, 10 Fälle): 12 auf 24 (Job 20 h queued, 30 h bleibt skipped, requeue mit 86 400 000 ms), 24 auf 12 (nichts zurück, laufender Job bleibt running), gleich (Job ohne Dauer bleibt skipped), Lesefehler (Grenze 20 bleibt, kein "secret" im Log), Textwerte abc/48/leer (12/24/12), Job ohne Dauer kommt beim Anheben zurück, Reihenfolge in der Schleife `read, step, step, read, step, step, read, step`, Standardleser über nc_app und settings.read. test_main: Task "preview" während des Lifespans vorhanden, danach keiner.
- RED: Importfehler beim Sammeln (SETTINGS_REFRESH_SECONDS fehlt), test_main 1 rot.
- Mutationen (jede gefangen): immer zurückstellen (2 rot), nie zurückstellen (2 rot), Abgleich nur beim Start (1 rot), Lesefehler nicht abgefangen (1 rot).

## Task 2: Wahrheitsbedingungen T6/T7

Gegen echten Store, echte Capture und echten Preview-Worker; nur Gateway, Probe und Engine sind gefälscht. Claims laufen über `nc_queue.ClaimItem(...).to_intake()` wie der Intake.

| Fall | Ergebnis |
|---|---|
| beschädigt, gleiche file_id, neuer Inhalt (origin event) | neue media, Job queued mit origin event, preview_view zeigt queued statt damaged, Worker nimmt ihn |
| geschützt, gleiche file_id, neuer Inhalt | ebenso |
| ungeschützte Fassung unter neuer file_id | eigener queued-Job (event), Original bleibt skipped protected |
| Gegenprobe: gleiche Bytes, neuer etag | gleiche media, Job bleibt skipped damaged, Worker IDLE (keine Schleife) |

Alle vier grün: **T6 und T7 Satz 2 stimmen im Code**, keine Owner-Frage nötig. Positivkontrollen am Produktcode (danach zurückgesetzt): ohne Saat des Vorschau-Jobs in `mark_keyed` 4 rot; Saat setzt auch skipped-Jobs auf queued: nur die Gegenprobe rot.

## Task 3: Korpus-Langtest (Messbeleg D-03-11, D-03-22)

Echtes Modell (Parakeet + Silero, `procure --root` in einen Scratch-Ordner außerhalb des Repos), echtes ffprobe/ffmpeg 8.1.1 (Gyan), echter Preview-Worker mit EngineWorker je Job, Bytes über MockTransport vor `nc.fetch_media_file`. Freier RAM vor den Läufen 5,4 GB, alle Läufe seriell. Befehl:

```bash
cd backend && AVS_TEST_MODELS=... AVS_TEST_SPEECH=... AVS_TEST_SPEECH_TR=... AVS_TEST_SPEECH_ES=... AVS_TEST_WORD=dinosaurier \
  uv run pytest tests/test_preview_corpus.py -x -q -rs -s
```

| Datei | Urteil | Wörter (current / alle Versionen) | Treffer "dinosaurier" | Laufzeit |
|---|---|---|---|---|
| Stille 60 s, WAV | no_speech | 0 / 0 | | 3,5 s |
| rosa Rauschen 120 s, -25 dBFS, Opus | no_speech | 0 / 0 | | 3,5 s |
| Sinus 440 Hz 60 s, MP3 | no_speech | 0 / 0 | | 3,6 s |
| DE-Clip, M4A (AAC) | transcript | 20 / 20 | 6 114 ms | 3,8 s |
| DE-Clip ab 150 s in 5 min Stille, FLAC | transcript | 20 / 20 | 156 130 ms (150 000 bis 150 000 + Cliplänge) | 4,9 s |
| TR-Clip, OGG (Vorbis) | **unsupported_language** | 0 / 0 | | 7,4 s |
| ES-Clip, WebM (Opus) | unsupported_language | 0 / 0 | | 5,3 s |

7 passed in 33,9 s (Laufzeit inkl. Start des Engine-Kinds je Datei). Die Verschiebung 156 130 - 6 114 = 150 016 ms entspricht dem Versatz von 150 s plus Encoder-Vorlauf. Positivkontrolle: TR-Variable auf den DE-Clip und falsches Erwartungswort: 3 rot (TR wird transcript, beide DE-Dateien ohne Treffer), Stille bleibt grün. Ohne AVS_TEST_MODELS: 7 skipped mit Grund "AVS_TEST_MODELS is not set".

## Gates

- ruff check und format --check (115 Dateien), pyright latest 0 Fehler, vulture still. Positivkontrollen: ruff meldete im Entwurf ASYNC240/RUF100, pyright 1 Fehler an einer Probe mit falschem Typ, vulture meldet unerreichbaren Code an einer Probe.
- Volle Suite mit Modellen und Clips: **1866 passed** in 181 s.
- Gedankenstrich-Prüfung aller geänderten Dateien: 0 Treffer (Prüfer an einer Probe mit U+2014 positiv).
- Scratch-Ordner mit Modellen und Clips gelöscht; keine Audio- oder Modelldatei im Repo.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3] conftest.py erweitert (nicht in files_modified)**
- Autouse-Fixture `no_preview`: Lifespan-Vorschau in Tests ausgeschaltet (wie no_capture) und `preview.read_admin_settings` durch einen Leser ersetzt, der wie ein unerreichbares Nextcloud scheitert. Sonst hätte jeder Lifespan-Test und jeder `run_forever`-Test in test_preview_worker.py NEXTCLOUD_URL angefragt. Commit 8a03674.

**2. [Rule 1] Reihenfolge Zurückstellen vor Speichern**
- Der Plan nennt nur "speichern; bei höherer Grenze requeue". Speichern zuerst hätte bei einem Stopp dazwischen die zurückzustellenden Jobs dauerhaft vergessen. Umgesetzt: requeue zuerst, dann speichern, beides in einem Lock-Aufruf.

**3. Erwartung TR angepasst (Auftrag D-03-22)**
- Plan-Frontmatter nennt den TR-Clip als unsupported_language bereits; der Test erwartet das so. Zusätzlich ES-Clip als WebM (D-03-22), nicht im Plantext.

**4. Planabweichung, bewusst**
- `worker/preview.py` statt `nc.py` für den Standardleser (Zirkel settings -> nc).
- Datei mit 5 min Länge passt in ein Stück (CHUNK_MS 10 min): belegt wird die Wortzeit über Format und Dekodierbeginn, nicht über eine Stückgrenze. Die Stückgrenze belegt schon test_preview_worker (25-min-WAV mit echtem ffmpeg).

## Offene Punkte

- 03-13b ändert parallel die Regel des zweiten Durchgangs (catch.py, constants.py, parakeet.py, hier nicht angefasst). Der Korpustest lief gegen den Stand vor 03-13b; Stille (60 s) und Sinus (60 s) laufen durch den zweiten Durchgang. Nach 03-13b den Korpustest einmal erneut laufen lassen; ein Konflikt ist bis jetzt nicht aufgetreten.
- CI nicht gelaufen (nichts gepusht); test_preview_corpus.py braucht dort libmp3lame, libopus/libvorbis und aac im BtbN-LGPL-Build (pick_encoder; fehlt einer, scheitert der Test unter CI=true mit Grund).
- Fremde, nicht gestagte Änderung im Arbeitsbaum: `backend/tests/test_model_download.py` (schon vor Beginn, nicht berührt).
- Versehentlich gestarteter `python -` (wartete auf stdin) wurde nach Sekunden beendet; ohne Folgen.

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche. Einziger neuer Netzweg ist das Lesen der eigenen appconfig_ex über nc_py_api (wie /status). T-03-51 (Gegenprobe), T-03-52 (ein UPDATE nur beim Anheben) und T-03-53 (TR und ES: 0 Wörter in allen Versionen) belegt.

## TDD Gate Compliance

ebb8ce9 (test, rot) vor 8a03674 (feat). Task 2 und 3 sind reine Testaufgaben gegen bestehenden Code.

## Self-Check: PASSED

- FOUND: main.py, worker/preview.py, conftest.py, test_main.py, test_preview_settings.py, test_replaced_file.py, test_preview_corpus.py
- FOUND: Commits ebb8ce9, 8a03674, 4ff38e1, a3b77e9
