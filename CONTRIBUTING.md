# Contributing

Thanks for considering a contribution. Audio & Video Search is solo-maintained with hard
quality gates; small, focused pull requests get reviewed fastest.

## The shape of the repository

Audio & Video Search is two Nextcloud apps that always carry the same version:

- `backend/`: the External App `audio_video_search_backend`, a Python container
  (FastAPI) that AppAPI deploys and reaches through HaRP. `src/audio_video_search_backend/`
  holds the code, `appinfo/info.xml` the store metadata, `l10n/` the German,
  English and French catalogues.
- `php/`: the PHP app `audio_video_search` (search provider, playback view,
  admin section, `occ audio_video_search:sample`), with its own `appinfo/`,
  `l10n/` and phpunit tests.

## The gates

Green locally before you push, in `backend/`:

```sh
cd backend
uv sync
uv run ruff check .
uv run ruff format --check .
PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright
uv run vulture
uv run pytest -q --cov=src/audio_video_search_backend
```

The PHP app is checked by the `php.yml` workflow (lint, phpunit against a real
Nextcloud).

## Pull requests

- One concern per pull request, with tests; a behaviour change without a test
  will be asked for one.
- Every user-visible text exists in German, English and French
  (`backend/tests/test_trilingual.py`).
- No content leaves the server: no external service receives file content.
- The store texts (`backend/appinfo/info.xml`, `php/appinfo/info.xml`) and the
  version travel with releases;
  do not change them in a feature pull request.
- Dependencies are locked in `backend/uv.lock`; change it only through `uv` and say why.

## Security problems

See [SECURITY.md](SECURITY.md); please do not open a public issue.
