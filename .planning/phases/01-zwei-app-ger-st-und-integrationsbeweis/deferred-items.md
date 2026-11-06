# Phase 1: Zurückgestellte Punkte

## Aus Plan 01-01

- `.github/workflows/release.yml`, `.github/workflows/store-submit.yml` und `scripts/release/store-archive.sh` lesen noch `appinfo/`, `l10n/`, `img/` an der Repo-Wurzel und `APP_ID: audio_video_search` mit Image `ghcr.io/street1983nk/audio_video_search`. Nach dem Umbau auf `backend/` und `php/` sind sie bis zum Zwei-Archiv-Umbau nicht lauffähig. Zuständig: Plan 01-10 (laut files_modified dort).
- `CONTRIBUTING.md` nennt noch `src/audio_video_search/` und `--cov=src/audio_video_search`; `SECURITY.md` und die README-Badges nennen nur die PHP-App-ID. Zuständig: Doku-Plan 01-13.
- `php/tests/Unit/` ist leer (nur `.gitkeep`); `php.yml` (phpunit-Job, `failOnEmptyTestSuite`, `MINIMUM_TESTS: 1`) wird erst grün, wenn Plan 01-03 die ersten PHP-Tests und `SampleCommand`/`Search\Provider` liefert.
