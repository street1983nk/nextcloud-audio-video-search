"""GET /status: what the admin section of the PHP app shows about the container.

Route access level ADMIN in appinfo/info.xml; the signature check is the one of
AppAPIAuthMiddleware in main.py, as for every other route.

Fields (the admin section treats a missing field as unknown):

- ``app_id`` and ``version``: unchanged since the walking skeleton.
- ``appVersion``: APP_VERSION of this container, for the lockstep check.
- ``companion`` and ``companionVersion``: the state of the PHP app as the
  container sees it (companion.py); asked again when older than 30 seconds.
- ``schemaVersion``: the schema of the operating state in SQLite.
- ``sampleCount``: media items whose current transcript is a seeded sample.
- ``settings``: the saved settings of the ExApp.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends

from audio_video_search_backend import APP_ID, companion, config, settings
from audio_video_search_backend.api import Services, run_locked, services
from audio_video_search_backend.model.provenance import Level
from audio_video_search_backend.nc import AsyncNextcloudApp, nc_app

router = APIRouter()


async def app_client() -> AsyncIterator[AsyncNextcloudApp]:
    """A request scoped client in the app context, closed after the response."""
    async with nc_app() as nc:
        yield nc


def _store_figures(opened: Services) -> tuple[int, int]:
    return opened.store.schema_version(), opened.store.count_current_at_level(Level.SAMPLE)


@router.get("/status")
async def status(
    nc: Annotated[AsyncNextcloudApp, Depends(app_client)], opened: Annotated[Services, Depends(services)]
) -> dict[str, object]:
    state = await companion.refresh_if_stale()
    schema_version, sample_count = await run_locked(opened, lambda: _store_figures(opened))
    version = config.app_version()
    return {
        "app_id": APP_ID,
        "version": version,
        "appVersion": version,
        "companion": state.state,
        "companionVersion": state.version,
        "schemaVersion": schema_version,
        "sampleCount": sample_count,
        "settings": await settings.read(nc),
    }
