[Deutsch](install.md) | English | [Français](install.fr.md)

# Installing Audio & Video Search

Audio & Video Search consists of two apps. Both are needed and must run the same version:

- `audio_video_search_backend`: External App (Python container), decodes, recognises and indexes
- `audio_video_search`: PHP app, connects the backend to the Nextcloud search and shows the playback view

## Order

1. Enable AppAPI and set up a deploy daemon (HaRP recommended).
2. Install the External App "Audio & Video Search Backend" (`audio_video_search_backend`) and wait until it is enabled.
3. Install and enable the app "Audio & Video Search" (`audio_video_search`) in the same version.
4. Check the state under Administration settings, Audio & Video Search. After an update, bring both apps to the same version.

## States in the status area

The status area shows exactly one state:

- **Success, both apps connected:** Both apps run the same version, search works normally.
- **Notice, version differs in the last part:** Search works normally; align both apps at the next update.
- **Error, different versions:** The versions differ in the first or second part, search returns no results from audio and video until both apps run the same version.
- **Error, backend not installed:** `audio_video_search_backend` is missing, search finds nothing in audio and video.
- **Error, backend disabled:** `audio_video_search_backend` is installed but off; enable it under Apps.
- **Error, backend does not answer:** The container is not running or the deploy daemon cannot be reached; check under Apps and in the AppAPI settings.
- **Error, AppAPI not enabled:** Without AppAPI the backend does not run; enable AppAPI and set up a deploy daemon.
- **Warning, check failed:** "Check again" did not get through; the state from when the page was loaded stays on screen.

With every error, the link "Open Apps" leads to the app management.

## Test result (developers only)

Phase 1 does not transcribe yet. For the integration proof, a command creates a short test result for a real audio or video file. It requires debug mode in `config.php`:

```php
'debug' => true,
```

Without debug mode the command refuses, and search shows no test result. A production instance therefore never gets a test result by accident.

Create:

```sh
occ audio_video_search:sample <fileId> [--at=<seconds>] [--user=<user>]
```

- `<fileId>`: numeric id of the file, for example `12345`
- `--at`: point in time of the test result in seconds, 0 to 86400, at most three decimals, default 42
- `--user`: read as this user instead of the owner of the file

Then, under Administration settings, Audio & Video Search, turn on "Show the test result in search" in the block "Test result". Switching it off hides the test result at once, the test data stays.

Remove, only this way:

```sh
occ audio_video_search:sample <fileId> --remove
```

The command removes the test result and its index entries; the file itself stays unchanged. It never removes a real transcript. Removing also requires debug mode. The interface has no delete action.

## Discovery

- External storages are captured by default. To switch one off: `occ audio_video_search:exclude --storage=<mount id>` (id from `occ files_external:list`).
- Storages with session-only credentials are skipped. They only become capturable once the admin selects "Log-in credentials, save in database" for that storage. Nextcloud then stores each user's password encrypted on the server and can access the storage without that user logging in. Whoever controls the server and the database can in principle recover it. This is a deliberate decision; without it these storages stay excluded from search.
- Exclude users, groups and folders: `occ audio_video_search:exclude --user=<uid>`, `--group=<gid>` or `--folder=<path>`. This also works before the backend is installed.
- An SMB storage mounted by the admin with credentials per user belongs to that user when it comes to exclusions.
- `occ audio_video_search:status` shows how many contents are transcribed (X of Y).
- Changes made directly on the NAS show up within 24 hours, at once with `occ audio_video_search:rescan --all`, permanently faster with `occ files_external:notify`.
- Read access on SMB and SFTP is checked again at least every 7 days.
- Deleted files leave the search at once. Their transcript is kept for 7 days in case a copy turns up again.
- Every file is read in full once.
- With php-fpm, set `request_terminate_timeout` so a hanging SMB access does not hold a worker for good.

## Notes

- Playback from a point in time can start slowly on external storage that cannot seek within the data stream, because the server reads the file up to the start position.
- Mobile apps open a result from 0:00, without the jump to the point in time.
