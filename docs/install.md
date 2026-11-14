Deutsch | [English](install.en.md) | [Français](install.fr.md)

# Audio & Video Search installieren

Audio & Video Search besteht aus zwei Apps. Beide sind nötig und müssen dieselbe Version haben:

- `audio_video_search_backend`: External App (Python-Container), dekodiert, erkennt und indexiert
- `audio_video_search`: PHP-App, verbindet das Backend mit der Nextcloud-Suche und zeigt die Abspielansicht

## Reihenfolge

1. AppAPI aktivieren und einen Deploy-Daemon einrichten (HaRP empfohlen).
2. Die External App "Audio & Video Search Backend" (`audio_video_search_backend`) installieren und warten, bis sie aktiviert ist.
3. Die App "Audio & Video Search" (`audio_video_search`) in derselben Version installieren und aktivieren.
4. Unter Verwaltungseinstellungen, Audio & Video Search den Zustand prüfen. Nach einem Update beide Apps auf dieselbe Version bringen.

## Zustände im Statusbereich

Der Statusbereich zeigt genau einen Zustand:

- **Erfolg, beide Apps verbunden:** Beide Apps laufen in derselben Version, die Suche arbeitet normal.
- **Hinweis, Version unterscheidet sich in der letzten Stelle:** Die Suche arbeitet normal; beim nächsten Update beide Apps angleichen.
- **Fehler, unterschiedliche Versionen:** Die Versionen unterscheiden sich in der ersten oder zweiten Stelle, die Suche liefert keine Treffer aus Audio und Video, bis beide Apps dieselbe Version haben.
- **Fehler, Backend nicht installiert:** `audio_video_search_backend` fehlt, die Suche findet nichts in Audio und Video.
- **Fehler, Backend deaktiviert:** `audio_video_search_backend` ist installiert, aber aus; unter Apps aktivieren.
- **Fehler, Backend antwortet nicht:** Der Container läuft nicht oder der Deploy-Daemon ist nicht erreichbar; unter Apps und in den AppAPI-Einstellungen prüfen.
- **Fehler, AppAPI nicht aktiviert:** Ohne AppAPI läuft das Backend nicht; AppAPI aktivieren und einen Deploy-Daemon einrichten.
- **Warnung, Neuprüfung gescheitert:** "Erneut prüfen" kam nicht durch; angezeigt bleibt der Stand beim Laden der Seite.

Bei jedem Fehler führt der Link "Apps öffnen" zur App-Verwaltung.

## Testtreffer (nur für Entwickler)

Für den Integrationsbeweis ohne echte Sprachaufnahme legt ein Befehl einen kurzen Testtreffer für eine echte Audio- oder Videodatei an. Voraussetzung ist der Debug-Modus in `config.php`:

```php
'debug' => true,
```

Ohne Debug-Modus lehnt der Befehl ab, und die Suche zeigt keinen Testtreffer. Eine Produktivinstanz bekommt so nie aus Versehen einen Testtreffer.

Anlegen:

```sh
occ audio_video_search:sample <fileId> [--at=<Sekunden>] [--user=<Benutzer>]
```

- `<fileId>`: numerische ID der Datei, zum Beispiel `12345`
- `--at`: Zeitstelle des Testtreffers in Sekunden, 0 bis 86400, höchstens drei Nachkommastellen, Standard 42
- `--user`: als dieser Benutzer lesen statt als Eigentümer der Datei

Danach unter Verwaltungseinstellungen, Audio & Video Search im Block "Testtreffer" den Schalter "Testtreffer in der Suche zeigen" einschalten. Ausschalten blendet den Testtreffer sofort aus, die Testdaten bleiben erhalten.

Entfernen, nur so:

```sh
occ audio_video_search:sample <fileId> --remove
```

Der Befehl entfernt den Testtreffer und seine Indexeinträge; die Datei selbst bleibt unverändert. Ein echtes Transkript entfernt er nie. Auch das Entfernen braucht den Debug-Modus. Die Oberfläche hat keine Löschaktion.

## Erfassung

- Externe Speicher werden ab Werk erfasst. Abschalten: `occ audio_video_search:exclude --storage=<Mount-ID>` (ID aus `occ files_external:list`).
- Speicher mit Anmeldedaten nur für die Sitzung werden übersprungen. Erfassbar werden sie erst, wenn der Admin für diesen Speicher "Anmeldedaten des Benutzers (in Datenbank gespeichert)" wählt (bei "Deutsch (du)": "Anmeldedaten in Datenbank speichern"). Dann speichert Nextcloud das Passwort jedes Nutzers verschlüsselt auf dem Server und kann ohne dessen Anmeldung zugreifen. Wer Server und Datenbank kontrolliert, kann es grundsätzlich wiederherstellen. Das ist eine bewusste Entscheidung; ohne sie bleiben diese Speicher von der Suche ausgenommen.
- Nutzer, Gruppen und Ordner ausschließen: `occ audio_video_search:exclude --user=<uid>`, `--group=<gid>` oder `--folder=<Pfad>`. Das geht auch, bevor das Backend installiert ist.
- Ein vom Admin eingebundener SMB-Speicher mit Anmeldedaten je Nutzer gehört beim Ausschluss dem jeweiligen Nutzer.
- `occ audio_video_search:status` zeigt, wie viele Inhalte transkribiert sind (X von Y).
- Änderungen direkt auf dem NAS erscheinen spätestens nach 24 Stunden, sofort mit `occ audio_video_search:rescan --all`, dauerhaft schneller mit `occ files_external:notify`.
- Leserechte auf SMB und SFTP werden mindestens alle 7 Tage neu geprüft.
- Gelöschte Dateien verschwinden sofort aus der Suche. Ihr Transkript bleibt 7 Tage für eine Kopie, die wieder auftaucht.
- Jede Datei wird einmal komplett gelesen.
- Bei php-fpm `request_terminate_timeout` setzen, damit ein hängender SMB-Zugriff keinen Worker dauerhaft belegt.

## Transkription (Vorschau)

- Das Backend transkribiert alle erfassten Audio- und Videodateien lokal mit Parakeet TDT 0.6B v3 (int8) und Silero VAD. Das Ergebnis ist zunächst eine Vorschau: Treffer daraus tragen in der Suche das Wort "Vorläufig", die Abspielseite zeigt "Vorläufiges Transkript. Es kann Fehler enthalten."
- Erkannt werden Deutsch, Englisch und Französisch; Stellen in anderen Sprachen werden verworfen.
- Formate unter anderem MP3, M4A, WAV, OGG, Opus, FLAC, MP4, MOV, MKV und WebM. Bei mehreren Tonspuren zählt die als Standard markierte, sonst die erste.
- Neue und geänderte Dateien kommen vor dem Altbestand dran, der Altbestand nach Änderungsdatum, neueste zuerst. Lange Dateien werden in Stücken von 10 Minuten gerechnet und sind nach jedem fertigen Stück findbar.
- Höchstdauer 12 Stunden, einstellbar bis 24 unter Verwaltungseinstellungen, Zusätzliche Einstellungen, "Längste Aufnahme in Stunden". Längere Dateien werden als überlang übersprungen; wird die Grenze angehoben, kommen sie zurück in die Warteschlange.
- Ohne Transkript bleibt eine Datei, wenn sie keine Sprache enthält, beschädigt oder geschützt ist, ihre Sprache nicht unterstützt wird oder sie überlang ist. Bei zu wenig Speicherplatz versucht das Backend es später erneut. Nutzer sehen den Grund auf der Abspielseite ihrer Datei, Admins die Zahlen mit `occ audio_video_search:status` (ohne Dateinamen).
- Arbeitsspeicher: Die Vorschau braucht ca. 1,7 GB RAM plus 0,5 GB Reserve; ist weniger frei, wartet sie.
- Modelle: Beim Aktivieren lädt das Backend einmalig ca. 0,67 GB aus dem GitHub-Release `models-2026-11` dieses Projekts, nur über `github.com` und `release-assets.githubusercontent.com`, und prüft jede Datei gegen einen festen sha256. Außer diesem Download verlässt nichts den Server.
- Ohne Internetzugang: vor der Installation das Volume `nc_app_audio_video_search_backend_data` anlegen und dieselben Dateien hineinlegen, `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx` und `tokens.txt` unter `models/parakeet/<Prüfwert>/`, `silero_vad.onnx` unter `models/silero/<Prüfwert>/`, Eigentümer der Container-Nutzer 10001. `<Prüfwert>` ist `3a78ea81526430808b60248acbaa45a3361ad99bdd0b05b7da6ad6548a4dd339`. Das Backend prüft die Dateien gegen denselben sha256 und lädt dann nichts.
- Namensnennung: Parakeet TDT 0.6B v3 by NVIDIA, CC-BY-4.0; Silero VAD, MIT; FFmpeg, LGPL (statischer Build, nur zum Dekodieren).

## Hinweise

- Abspielen ab einer Zeitstelle kann auf externen Speichern ohne Sprung im Datenstrom (nicht seekbar) langsam starten, weil der Server die Datei bis zur Startstelle liest.
- Mobil-Apps öffnen einen Treffer ab 0:00, ohne Sprung auf die Zeitstelle.
