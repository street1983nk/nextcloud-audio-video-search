[Deutsch](README.md) | English | [Français](README.fr.md)

# Audio & Video Search

[![Python gates](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/python.yml)
[![Security scans](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml/badge.svg)](https://github.com/street1983nk/nextcloud-audio-video-search/actions/workflows/security.yml)
[![Nextcloud App Store](https://img.shields.io/badge/App_Store-audio__video__search-0082c9)](https://apps.nextcloud.com/apps/audio_video_search)
[![License](https://img.shields.io/badge/License-AGPL--3.0--or--later-blue)](LICENSE)

Audio & Video Search makes audio and video files in Nextcloud searchable. It transcribes the spoken words locally on your own server, so meetings, interviews and recordings can be found by what was said.

**Status:** in development, not yet in the App Store. State of phase 1: both apps work together, and a test result for developers shows the way from search to the point in time. There is no transcription yet.

## What Audio & Video Search does

- Results from audio and video in the normal Nextcloud search, with a timestamp
- Playback view that opens the recording at the point in time of the result
- Status area for admins with the state of both apps
- Never modifies your files
- Planned: transcription on your own server for German, English and French

Mobile apps (Android, iOS) open a result as a file from 0:00, without the jump to the point in time.

## Two apps, both needed

| App | ID | Task |
|---|---|---|
| Audio & Video Search | `audio_video_search` | PHP app: search, permissions, playback view, status area |
| Audio & Video Search Backend | `audio_video_search_backend` | External App (Python container): decoding, recognition, index |

Both apps must be installed and run the same version. If the versions differ only in the last part, search keeps working; otherwise it returns no results from audio and video until both apps match again.

## Requirements

- Nextcloud 33 to 35 with AppAPI and a configured deploy daemon (HaRP recommended)
- CPU: amd64 or arm64

## Installation

In short: AppAPI with a deploy daemon, then the ExApp `audio_video_search_backend`, then the PHP app `audio_video_search`. The state of both apps is then shown under Administration settings, Audio & Video Search. All steps, the states of the status area and the test result: [docs/install.en.md](docs/install.en.md).

## Architecture

The PHP app hooks into the Nextcloud search, checks permissions and hands files to the backend by file id. The backend is an External App: a Python container (FastAPI) that AppAPI starts through the deploy daemon and reaches only through AppAPI/HaRP. Every request to the container carries the AppAPI signature; without it the answer is 401.

## Privacy

Everything runs locally on your own server, nothing leaves the server, no telemetry.
The app keeps transcripts and index in the data volume of its container.

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).

Third-party parts in the backend image:

- German word list `wngerman` (Debian), GPL-2.0-or-later, for splitting compound words; licence text in the image at `/usr/local/share/audio_video_search_backend/COPYING.wngerman`
- For transcription, later versions are planned to use Parakeet TDT 0.6B v3 by NVIDIA (CC-BY-4.0) and Whisper (MIT). Phase 1 contains no model yet.

Icons of the PHP app: Material Design Icons by Pictogrammers, Apache-2.0, licence text in [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt).
