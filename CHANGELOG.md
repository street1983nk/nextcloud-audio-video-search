# Changelog

All notable changes are listed here, newest first. The entry of a release is
written before its tag; the GitHub release carries the same facts in English.

## 0.2.0

## 0.1.0

- Two apps in lockstep: PHP app `audio_video_search` and External App `audio_video_search_backend`, same version
- Search provider in the Nextcloud unified search, results link to the playback view with a timestamp
- Playback view `/apps/audio_video_search/play/{fileId}?t=<seconds>` streams the file through WebDAV and shows error states
- Admin section "Audio & Video Search" with the state of the other app, versions and "Check again"
- Handshake and version check between both apps; search stays empty while they do not match
- Test result for developers: `occ audio_video_search:sample <fileId> [--at=<seconds>]`, removed only with `--remove`, debug mode only
- German word list `wngerman` (GPL-2.0-or-later) in the backend image for compound words
- No transcription yet
- Texts in German, English and French
