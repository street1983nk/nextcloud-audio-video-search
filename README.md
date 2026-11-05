Deutsch | [English](README.en.md) | [Français](README.fr.md)

# Audio & Video Search

[![Python gates](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml)
[![Security scans](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml)
[![Nextcloud App Store](https://img.shields.io/badge/App_Store-audio__video__search-0082c9)](https://apps.nextcloud.com/apps/audio_video_search)
[![Lizenz](https://img.shields.io/badge/Lizenz-AGPL--3.0--or--later-blue)](LICENSE)

Audio & Video Search macht Audio- und Videodateien in Nextcloud durchsuchbar. Die App schreibt das Gesprochene lokal auf dem eigenen Server mit und findet so Besprechungen, Interviews und Aufzeichnungen über ihren Inhalt.

**Status:** in Entwicklung, noch nicht im App Store.

## Was Audio & Video Search kann

- Transkription auf dem eigenen Server mit offenen Sprachmodellen, für Deutsch, Englisch und Französisch
- Suche im gesprochenen Text, Treffer mit Zeitmarke
- Läuft komplett in Ihrer eigenen Instanz, keine Telemetrie
- Verändert nie Ihre Dateien

## Anforderungen

- Nextcloud 33 bis 35 mit AppAPI und einem eingerichteten Deploy-Daemon (HaRP empfohlen)
- CPU: amd64 oder arm64

## Installation

Im App Store unter External Apps die App Audio & Video Search installieren. Die
Einstellungen stehen danach unter Verwaltungseinstellungen, Weitere
Einstellungen.

## Architektur

Audio & Video Search ist eine External App: ein Python-Container (FastAPI), den AppAPI
über den Deploy-Daemon startet und nur über AppAPI/HaRP erreicht. Jede Anfrage
an den Container trägt die Signatur von AppAPI; ohne sie antwortet er mit 401.

## Datenschutz

Alles läuft lokal im Container, nichts verlässt den Server.
Die App speichert die Transkripte im Datenvolumen ihres Containers, keine Aufnahme verlässt den Server.

## Lizenz

AGPL-3.0-or-later. Siehe [LICENSE](LICENSE).
