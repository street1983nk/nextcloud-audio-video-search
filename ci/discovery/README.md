# Discovery acceptance test

The acceptance test of phase 2 (D-02-07), run by the workflow
`Discovery acceptance` (`.github/workflows/discovery-e2e.yml`). Findling #25
passed three times because only the single parts were tested; this test runs
the whole discovery path on a real Samba server and compares the result with a
count that never runs code of this app.

- `topology.sh` builds the instance and runs the operations of the phases.
- `truth.sh`, `ledger.sh`, `compare.sh` and `controls.sh` (plan 02-04) build the
  independent truth, compare it per phase and hold the positive controls.
- `ids.env` is written in CI only; it is the one place that pairs a test file
  with its file id.

The job stays red until the discovery exists (plan 02-01: the failing
acceptance test comes first). One leg runs per push; `workflow_dispatch` with
`legs=all` runs the six legs of `deploy-harp.yml`. The second job,
`leak-control`, runs an image built out of a patched copy of `backend/` without
the read proof; it has to show the leak the main legs must never show
(D-02-10). That image only ever lives in the local registry of the runner.

## Persons

| Person | Role |
|--------|------|
| ana | Samba and Nextcloud, owns the home media, the M3/M5 mounts and the shares |
| ben | Samba and Nextcloud, denied `gesperrt.webm` by Samba, member of `team`, ACL in the team folder, excluded after the first run |
| cem | Samba and Nextcloud, alone in `nur-cem/`, gets a reshare, loses `widerruf.webm` and later the mount M1 |
| dan | own home medium, receives a share out of the SMB mount, is deleted |
| eva | excluded before the first run, receives a share from ana |
| fritz | member of the group `extern`, which is excluded before the first run |

## Mounts

| Mount | Backend and authentication | Users |
|-------|----------------------------|-------|
| M1 `/SMB` | smb, `password::logincredentials`, `timeout=20` (fallback: one personal `password::password` mount per user, logged) | ana, ben, cem |
| M2 `/SMB-Sitzung` | smb, `password::sessioncredentials` | ana |
| M3 `/SMB-Teil` | smb, `password::password`, root `gemeinsam` | ana |
| M4 `/Lokal` | local | ana, cem |
| M5 `/S3` | amazons3 against SeaweedFS (MinIO publishes no image any more) | ana |

## Cases

| Case | Statement | Decision |
|------|-----------|----------|
| SMB share in M1 for three users, `nur-ana/` and `nur-cem/` by Unix mode | every user's view is captured, one file reference per user and file | D-02-01, D-02-02 |
| `doppelt/a.webm` and `doppelt/b.webm`, same bytes | two files, one content | D-02-01 |
| `gesperrt.webm` with DENY READ for ben (A6) | ben's copy is unreadable, never attached, no hit for ben | D-02-01a |
| leak-control image without the read proof | the same case shows the leak there, so the test can see it | D-02-01a, D-02-10 |
| `widerruf.webm`, DENY READ for cem later | the renewed read proof removes cem's hits at once | D-02-12 |
| `klein.ogg`, below 64 KiB | the read proof works on a file shorter than its window | D-02-01a |
| M2 with session credentials | skipped with a reason, never fetched, no file name in the message | D-02-03 |
| M3, same share with another root | the prefilter key normalises the root into the path | D-02-01 |
| M4 local, M5 S3 | external storages are captured out of the box | DISC-02 |
| team folder `Team`, ben `+read -share` on `frei/`, `-read` on `intern/` | one file reference per team folder file, the reader is a member who may read | D-02-02 |
| shares ana to ben, reshare ben to cem, ana to eva, `/SMB/gemeinsam` ana to dan | a shared file stays one file id; recipients find it, the excluded eva does not | D-02-02, D-02-08 |
| files_accesscontrol rule on the tag `avs-sperre` | the gateway answers access_control, the reference is unreadable | DISC-05 |
| eva, group `extern`, folder `privat` excluded before the first run | never in the work stock, never in the access log | D-02-05, D-02-08 |
| `upload_new`, `overwrite` | a new file is in the work stock within minutes; an overwrite gives a new content, the old one is orphaned | DISC-04, D-02-13 |
| `copy_in_home`, `move_home_to_team` | same content, at most one download | DISC-06 |
| `rename_in_home`, `tag_file` | no download, same content | DISC-06 |
| `trash_file`, `restore_file` | trashed is not counted and not found, a restore brings it back without a download | D-02-09 |
| `exclude_user_after` (ben) | ben's own storages go, ana's copies of the same share stay with their transcript | D-02-08, D-02-11 |
| `exclude_storage_after` (M3) | M3's references go, the contents stay through M1 | D-02-04 |
| `exclude_after` (folder `archiv-spaeter`) | x is forgotten, z keeps transcript and correction through `gemeinsam/` | D-02-04 |
| `vanish_cem` (cem leaves M1) | cem's references are vanished and not counted | D-02-07 |
| `delete_dan` | dan's references go, his content is only orphaned | D-02-13 |
| `reattach` (dan's bytes into ana's home) | the new file attaches to the orphaned content and keeps its transcript | D-02-13 |
| `foreign_change` (file replaced on the Samba side) | after a rescan the work stock holds the new hash | DISC-04 |
