"""The only module that imports nc_py_api.

Every other module takes the AppAPI building blocks from here. Two reasons,
both from Findling:

1. An nc_py_api update hits exactly one file. The sync API disappears in 0.31.0,
   so only the async entry points are handed out.
2. What the container may do in Nextcloud is checkable by reading one file.
   tests/test_boundary.py fails when another module imports nc_py_api.

Clients live only inside ``nc_app()``: every AsyncNextcloudApp opens its own
HTTP sessions and nc_py_api has no public close, so a client that is never
closed leaks connections until the garbage collector finds it (Gameworld WR-05).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from nc_py_api import AsyncNextcloudApp, NextcloudException
from nc_py_api.ex_app import AppAPIAuthMiddleware, run_app, set_handlers
from nc_py_api.ex_app.ui.settings import SettingsField, SettingsFieldType, SettingsForm

__all__ = [
    "AppAPIAuthMiddleware",
    "AsyncNextcloudApp",
    "NextcloudException",
    "SettingsField",
    "SettingsFieldType",
    "SettingsForm",
    "close_nc",
    "nc_app",
    "run_app",
    "set_handlers",
]

LOGGER = logging.getLogger(__name__)

# The release the code was read against; an upgrade re-verifies this module.
NC_PY_API_VERIFIED_VERSION: Final = "0.30.3"

_ADAPTERS: Final = ("adapter", "adapter_dav")


async def close_nc(nc: object) -> None:
    """Close both HTTP sessions of a client; a failure while closing is logged, never raised."""
    session = getattr(nc, "_session", None)
    for name in _ADAPTERS:
        close = getattr(getattr(session, name, None), "close", None)
        if close is None:
            continue
        try:
            await close()
        except Exception as exc:  # closing must never disturb the caller
            LOGGER.debug("nextcloud session not closed", extra={"error_type": type(exc).__name__})


@asynccontextmanager
async def nc_app() -> AsyncIterator[AsyncNextcloudApp]:
    """A client in the app context without a user, closed on every way out."""
    nc = AsyncNextcloudApp()
    try:
        yield nc
    finally:
        await close_nc(nc)
