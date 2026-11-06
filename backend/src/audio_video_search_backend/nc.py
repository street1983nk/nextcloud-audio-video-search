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

The second client here is httpx, for one job: reading the bytes of a file from
the content gateway of the PHP app as a stream (Findling ``nc/client.py``
``fetch_file_stream``). nc_py_api's OCS entry point parses every answer as
JSON, so a media file cannot go through it.
"""

import hashlib
import logging
import os
from base64 import b64encode
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Final

import httpx
from nc_py_api import AsyncNextcloudApp, NextcloudException
from nc_py_api.ex_app import AppAPIAuthMiddleware, run_app, set_handlers
from nc_py_api.ex_app.ui.settings import SettingsField, SettingsFieldType, SettingsForm

__all__ = [
    "AppAPIAuthMiddleware",
    "AsyncNextcloudApp",
    "FetchResult",
    "NextcloudException",
    "SettingsField",
    "SettingsFieldType",
    "SettingsForm",
    "close_nc",
    "fetch_file_sha256",
    "fetch_handshake",
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


# The content gateway of the PHP app. The file id is the only variable part; no
# path string exists anywhere on this way, so traversal is impossible by shape.
GATEWAY_PATH: Final = "/ocs/v2.php/apps/audio_video_search/files/{file_id}"
# One mebibyte per block, Findling's measured value; nothing is kept per block.
CHUNK_SIZE: Final = 1024 * 1024
_DEFAULT_AA_VERSION: Final = "2.2.0"
# Connect fast or fail; a block may take a while on a slow external storage.
_GATEWAY_TIMEOUT: Final = httpx.Timeout(60.0, connect=10.0)
_DENIED_STATUS: Final = frozenset({403, 404})
_FIRST_ERROR_STATUS: Final = 400

GATEWAY_DENIED: Final = "gateway_denied"
GATEWAY_FAILED: Final = "gateway_failed"


@dataclass(frozen=True, slots=True)
class FetchResult:
    """The hash of a file read through the gateway, or an error code."""

    sha256: str | None
    size: int
    error: str | None


def gateway_url(file_id: int) -> str:
    """Absolute URL of the gateway for one file id, NEXTCLOUD_URL normalised like nc_py_api does."""
    base = os.environ.get("NEXTCLOUD_URL", "").removesuffix("/").removesuffix("/index.php").removesuffix("/")
    return base + GATEWAY_PATH.format(file_id=file_id)


def app_api_headers(header_user: str = "") -> dict[str, str]:
    """The headers AppAPI authenticates an ExApp call with, built from the environment."""
    secret = os.environ.get("APP_SECRET", "")
    return {
        "AA-VERSION": os.environ.get("AA_VERSION", _DEFAULT_AA_VERSION),
        "EX-APP-ID": os.environ.get("APP_ID", ""),
        "EX-APP-VERSION": os.environ.get("APP_VERSION", ""),
        "AUTHORIZATION-APP-API": b64encode(f"{header_user}:{secret}".encode()).decode(),
        "OCS-APIRequest": "true",
    }


def _certificate_setting() -> bool | str:
    """Mirror NPA_NC_CERT of nc_py_api: True, False, or a path to a CA bundle."""
    value = os.environ.get("NPA_NC_CERT", "True")
    if value.lower() in {"false", "0"}:
        return False
    if value.lower() in {"true", "1"}:
        return True
    return value


def new_gateway_client() -> httpx.AsyncClient:
    """A client for the gateway. Redirects are not followed: they would carry the credential away."""
    return httpx.AsyncClient(verify=_certificate_setting(), timeout=_GATEWAY_TIMEOUT, follow_redirects=False)


def _failed(file_id: int, reason: str, *, status: int | None = None) -> FetchResult:
    LOGGER.warning("gateway read failed", extra={"file_id": file_id, "reason": reason, "status": status})
    return FetchResult(sha256=None, size=0, error=GATEWAY_FAILED)


async def _hash_stream(client: httpx.AsyncClient, file_id: int, user_id: str, max_bytes: int) -> FetchResult:
    digest = hashlib.sha256()
    size = 0
    async with client.stream(
        "GET", gateway_url(file_id), params={"userId": user_id}, headers=app_api_headers()
    ) as response:
        if response.status_code in _DENIED_STATUS:
            LOGGER.info("gateway denied the file", extra={"file_id": file_id, "status": response.status_code})
            return FetchResult(sha256=None, size=0, error=GATEWAY_DENIED)
        if response.status_code >= _FIRST_ERROR_STATUS:
            # The body is not read: it may be an OCS document or a proxy page.
            return _failed(file_id, "status", status=response.status_code)
        async for chunk in response.aiter_bytes(CHUNK_SIZE):
            size += len(chunk)
            if size > max_bytes:
                return _failed(file_id, "too_large")
            digest.update(chunk)
        declared = response.headers.get("Content-Length", "")
        if declared.isdigit() and size < int(declared):
            return _failed(file_id, "short_read")
    return FetchResult(sha256=digest.hexdigest(), size=size, error=None)


async def fetch_file_sha256(
    file_id: int, user_id: str, *, max_bytes: int, client: httpx.AsyncClient | None = None
) -> FetchResult:
    """Read one file through the gateway as a stream and return its SHA-256.

    The bytes are hashed block by block and never kept. 403 and 404 are the
    gateway's verdict that this user may not read the file (``gateway_denied``);
    every other status, a network error, a short answer or more than
    ``max_bytes`` is ``gateway_failed``. Logs carry the file id, a status and a
    reason code, never the user, a name or a path.
    """
    try:
        if client is not None:
            return await _hash_stream(client, file_id, user_id, max_bytes)
        async with new_gateway_client() as owned:
            return await _hash_stream(owned, file_id, user_id, max_bytes)
    except httpx.HTTPError as error:
        return _failed(file_id, type(error).__name__)


# The handshake route of the PHP app; it answers only this backend.
HANDSHAKE_PATH: Final = "/ocs/v2.php/apps/audio_video_search/api/v1/handshake"


async def fetch_handshake() -> tuple[int | None, str | None]:
    """Ask the PHP app whether it is there; returns (status, companionVersion).

    200 with the version string as the PHP app sent it (unchecked, the caller
    validates it), a Nextcloud error as its status code (404: not installed or
    not enabled), and ``(None, None)`` when the instance could not be reached.
    Never raises; logs carry the error type only, never the URL.
    """
    try:
        async with nc_app() as nc:
            answer = await nc._session.ocs("GET", HANDSHAKE_PATH)
    except NextcloudException as error:
        return error.status_code, None
    except Exception as error:  # a network error must never stop the caller
        LOGGER.debug("handshake not answered", extra={"error_type": type(error).__name__})
        return None, None
    version = answer.get("companionVersion") if isinstance(answer, dict) else None
    return 200, version if isinstance(version, str) else None
