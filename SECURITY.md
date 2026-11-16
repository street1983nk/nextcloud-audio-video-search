# Security Policy

## Supported versions

Only the latest release of the two apps `audio_video_search` and
`audio_video_search_backend` in the
[Nextcloud App Store](https://apps.nextcloud.com/apps/audio_video_search) is
supported; both carry the same version. Please update before reporting.

## Reporting a vulnerability

Please do not open a public issue for a security problem.

- Preferred: GitHub private vulnerability reporting, via "Report a
  vulnerability" under the Security tab of this repository
- Alternative: mail to admin@infranode.dev

You will get a first answer within 7 days. Please include the app version, your
Nextcloud version, and steps to reproduce.

## Scope

The backend `audio_video_search_backend` is an External App: a Python container
reachable only through AppAPI and HaRP. The PHP app `audio_video_search` serves
search results and the playback view inside Nextcloud. The promises worth
attacking: every request to the container without a valid AppAPI signature is
refused, routes marked ADMIN are not reachable for other users, search results
and the playback view only show files the user may read, the container runs
without root, and nothing leaves your server.

For the subtitle draft (not yet in a released version) the promises are:
exports and the subtitle track are served only for files the user may read and
only when the share allows downloads (an undecidable share attribute counts as
blocked); a sidecar file is created only with create permission in the folder
of the recording and never overwrites an existing file; search filters never
reveal shares the user cannot see, they only remove results the user may read
anyway.

When a share does not allow downloads (or this cannot be decided), the playback
view also hides the download entry of the browser's media player. This is a
usability measure, not a protection: the browser still receives the media to
play it. The download block itself is enforced by Nextcloud.

Known residual risk, accepted: the app checks that the sidecar name is free and
creates the file under its own exclusive lock, which keeps parallel saves
through the app apart. Another client (for example a sync client or WebDAV)
that creates a file with the same name in the milliseconds between that check
and the creation is not covered by this lock; in that case the file of the
other client can be overwritten.
