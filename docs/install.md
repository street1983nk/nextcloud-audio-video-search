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

Phase 1 transkribiert noch nicht. Für den Integrationsbeweis legt ein Befehl einen kurzen Testtreffer für eine echte Audio- oder Videodatei an. Voraussetzung ist der Debug-Modus in `config.php`:

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

## Hinweise

- Abspielen ab einer Zeitstelle kann auf externen Speichern ohne Sprung im Datenstrom (nicht seekbar) langsam starten, weil der Server die Datei bis zur Startstelle liest.
- Mobil-Apps öffnen einen Treffer ab 0:00, ohne Sprung auf die Zeitstelle.
