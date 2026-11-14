Deutsch | [English](README.en.md) | [Français](README.fr.md)

# Audio & Video Search

[![Python gates](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml)
[![Security scans](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml)
[![Nextcloud App Store](https://img.shields.io/badge/App_Store-audio__video__search-0082c9)](https://apps.nextcloud.com/apps/audio_video_search)
[![Lizenz](https://img.shields.io/badge/Lizenz-AGPL--3.0--or--later-blue)](LICENSE)

Audio & Video Search macht Audio- und Videodateien in Nextcloud durchsuchbar. Die App schreibt das Gesprochene lokal auf dem eigenen Server mit und findet so Besprechungen, Interviews und Aufzeichnungen über ihren Inhalt.

**Status:** in Entwicklung, noch nicht im App Store. Stand 0.3.0: die App transkribiert alle Audio- und Videodateien der Instanz lokal, auch auf externen Speichern, zunächst als Vorschau; Treffer daraus tragen in der Suche "Vorläufig". Ein genaueres Transkript ist für spätere Versionen geplant.

## Was Audio & Video Search kann

- Treffer aus Audio und Video in der normalen Nextcloud-Suche, mit Zeitmarke
- Abspielansicht, die die Aufnahme an der Zeitstelle des Treffers öffnet
- Statusbereich für Admins mit dem Zustand beider Apps
- Verändert nie Ihre Dateien
- Transkription auf dem eigenen Server für Deutsch, Englisch und Französisch, zuerst als Vorschau

Mobil-Apps (Android, iOS) öffnen einen Treffer als Datei ab 0:00, ohne Sprung auf die Zeitstelle.

## Zwei Apps, beide nötig

| App | ID | Aufgabe |
|---|---|---|
| Audio & Video Search | `audio_video_search` | PHP-App: Suche, Rechte, Abspielansicht, Statusbereich |
| Audio & Video Search Backend | `audio_video_search_backend` | External App (Python-Container): Dekodieren, Erkennung, Index |

Beide Apps müssen installiert sein und dieselbe Version haben. Unterscheiden sich die Versionen nur in der letzten Stelle, arbeitet die Suche weiter; sonst liefert sie keine Treffer aus Audio und Video, bis beide Apps wieder zusammenpassen.

## Anforderungen

- Nextcloud 33 bis 35 mit AppAPI und einem eingerichteten Deploy-Daemon (HaRP empfohlen)
- CPU: amd64 oder arm64
- Arbeitsspeicher: ca. 2,2 GB frei (1,7 GB plus 0,5 GB Reserve); Speicherplatz: ca. 0,67 GB für die Sprachmodelle

## Installation

Kurz: AppAPI mit Deploy-Daemon, dann die ExApp `audio_video_search_backend`, dann die PHP-App `audio_video_search`. Der Zustand beider Apps steht danach unter Verwaltungseinstellungen, Audio & Video Search. Alle Schritte, die Zustände des Statusbereichs und der Testtreffer: [docs/install.md](docs/install.md).

## Architektur

Die PHP-App hängt sich in die Nextcloud-Suche, prüft die Rechte und liefert Dateien über eine Schnittstelle per Datei-ID an das Backend. Das Backend ist eine External App: ein Python-Container (FastAPI), den AppAPI über den Deploy-Daemon startet und nur über AppAPI/HaRP erreicht. Jede Anfrage an den Container trägt die Signatur von AppAPI; ohne sie antwortet er mit 401.

## Datenschutz

Alles läuft lokal auf dem eigenen Server: kein Audio, kein Text und keine Telemetrie verlässt den Server. Nach außen geht nur der einmalige Download der Sprachmodelle beim Aktivieren.
Die App speichert Transkripte und Index im Datenvolumen ihres Containers.

## Lizenz

AGPL-3.0-or-later. Siehe [LICENSE](LICENSE).

Bestandteile Dritter im Backend:

- Deutsche Wortliste `wngerman` (Debian), GPL-2.0-or-later, für die Zerlegung zusammengesetzter Wörter; Lizenztext im Image unter `/usr/local/share/audio_video_search_backend/COPYING.wngerman`
- Für die Transkription lädt die ExApp beim Aktivieren Parakeet TDT 0.6B v3 von NVIDIA (CC-BY-4.0) und Silero VAD (MIT) aus dem eigenen GitHub-Release `models-2026-11` und prüft jede Datei gegen einen festen sha256; ohne Internetzugang können Admins dieselben Dateien selbst ablegen; Whisper (MIT) ist für spätere Versionen vorgesehen.
- FFmpeg (statischer LGPL-Build von BtbN, Version 8.1) zum Dekodieren der Aufnahmen

Symbole der PHP-App: Material Design Icons von Pictogrammers, Apache-2.0, Lizenztext unter [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt).
