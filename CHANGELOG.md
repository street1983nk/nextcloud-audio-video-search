# Changelog

All notable changes are listed here, newest first. The entry of a release is
written before its tag; the GitHub release carries the same facts in English.

## 0.3.0

## 0.2.0

- Discovery of every audio and video file of the instance: home folders, team folders, shares and external storages
- External storages are captured by default; `occ audio_video_search:exclude --storage=<mount id>` switches one off
- Storages with session-only credentials are skipped; they become capturable only when the admin selects "Log-in credentials, save in database", which stores each user's password encrypted on the server
- Exclusions for users, groups and folders with `occ audio_video_search:exclude`, also before the backend is installed
- `occ audio_video_search:status` shows transcribed contents, open work and skipped storages
- Changes made directly on a storage show up within 24 h, at once with `occ audio_video_search:rescan`
- Read access on SMB and SFTP is checked again at least every 7 days
- Deleted files leave the search at once; their transcript is kept 7 days for a copy that comes back
- Every file is read in full once
- Update from 0.1.0 migrates the stored state and keeps the test results
- No transcription yet

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
