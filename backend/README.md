# Audio & Video Search Backend

The External App (ExApp) half of Audio & Video Search: a FastAPI service that
AppAPI deploys as a container. It decodes, transcribes and indexes audio and
video files, all locally on the server. On its own it does nothing; the PHP app
`audio_video_search` (in `../php`) connects it to the Nextcloud search.

Both halves always carry the same version. The user documentation is in
[../README.en.md](../README.en.md) (German: `../README.md`, French: `../README.fr.md`).
