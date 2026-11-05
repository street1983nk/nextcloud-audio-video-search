[Deutsch](README.md) | English | [Français](README.fr.md)

# Audio & Video Search

[![Python gates](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml)
[![Security scans](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml)
[![Nextcloud App Store](https://img.shields.io/badge/App_Store-audio__video__search-0082c9)](https://apps.nextcloud.com/apps/audio_video_search)
[![License](https://img.shields.io/badge/License-AGPL--3.0--or--later-blue)](LICENSE)

Audio & Video Search makes audio and video files in Nextcloud searchable. It transcribes the spoken words locally on your own server, so meetings, interviews and recordings can be found by what was said.

**Status:** in development, not yet in the App Store.

## What Audio & Video Search does

- Transcription on your own server with open speech models, for German, English and French
- Search in the spoken text, hits with a timestamp
- Runs entirely inside your own instance, no telemetry
- Never modifies your files

## Requirements

- Nextcloud 33 to 35 with AppAPI and a configured deploy daemon (HaRP recommended)
- CPU: amd64 or arm64

## Installation

Install Audio & Video Search from the External Apps section of the App Store. Its
settings are under Administration settings, Additional settings.

## Architecture

Audio & Video Search is an External App: a Python container (FastAPI) that AppAPI
starts through the deploy daemon and reaches only through AppAPI/HaRP. Every
request to the container carries the AppAPI signature; without it the answer
is 401.

## Privacy

Everything runs locally in the container, nothing leaves your server.
The app keeps the transcripts in the data volume of its container; no recording leaves the server.

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
