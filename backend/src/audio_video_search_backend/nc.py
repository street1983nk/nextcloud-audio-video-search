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

The second client here is httpx, for two jobs: reading the bytes of a file from
the content gateway of the PHP app as a stream (Findling ``nc/client.py``
``fetch_file_stream``), since nc_py_api's OCS entry point parses every answer as
JSON and a media file cannot go through it; and the three routes of the PHP
work stock (claim, ack, unlock), which run every 30 seconds on one long lived
client instead of a new nc_py_api client per call (plan 02-05). nc_queue.py
holds the contract of those routes and never imports a client itself.
"""

import asyncio
import hashlib
import logging
import os
import secrets
import shutil
from base64 import b64encode
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Final

import httpx
from nc_py_api import AsyncNextcloudApp, NextcloudException
from nc_py_api.ex_app import AppAPIAuthMiddleware, run_app, set_handlers
from nc_py_api.ex_app.ui.settings import SettingsField, SettingsFieldType, SettingsForm

__all__ = [
    "QUEUE_ACTIONS",
    "QUEUE_TIMEOUT",
    "AppAPIAuthMiddleware",
    "AsyncNextcloudApp",
    "FetchResult",
    "HttpClient",
    "NextcloudException",
    "SettingsField",
    "SettingsFieldType",
    "SettingsForm",
    "close_nc",
    "fetch_file_sha256",
    "fetch_handshake",
    "fetch_to_tempfile",
    "nc_app",
    "new_queue_client",
    "queue_post",
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
    """The hash of a file read through the gateway, or an error code.

    ``head_sha256`` (the first 64 KiB) and ``status`` (the HTTP status of a
    refusal) are filled by :func:`fetch_to_tempfile` only.
    """

    sha256: str | None
    size: int
    error: str | None
    head_sha256: str | None = None
    status: int | None = None


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


# The work stock of the PHP app (plan 02-03). Only these three actions exist;
# the path has no other variable part.
QUEUE_PATH: Final = "/ocs/v2.php/apps/audio_video_search/queues/media/{action}"
QUEUE_ACTIONS: Final = frozenset({"claim", "ack", "unlock"})
# Connect fast or fail, and a claim of a full band answers within seconds.
QUEUE_TIMEOUT: Final = httpx.Timeout(30.0, connect=10.0)

# The client type the work stock client holds, so nc_queue.py needs no import
# of its own.
HttpClient = httpx.AsyncClient


def queue_url(action: str) -> str:
    """Absolute URL of one queue route, NEXTCLOUD_URL normalised like gateway_url."""
    if action not in QUEUE_ACTIONS:
        raise ValueError("invalid queue action")
    base = os.environ.get("NEXTCLOUD_URL", "").removesuffix("/").removesuffix("/index.php").removesuffix("/")
    return base + QUEUE_PATH.format(action=action)


def new_queue_client() -> httpx.AsyncClient:
    """One client for the queue routes, held for the life of the intake. No redirects (credential)."""
    return httpx.AsyncClient(verify=_certificate_setting(), timeout=QUEUE_TIMEOUT, follow_redirects=False)


async def queue_post(client: httpx.AsyncClient, action: str, body: dict[str, object]) -> tuple[int | None, object]:
    """POST one queue route and return (status, the data of the OCS answer).

    ``(None, None)`` when the instance could not be reached, ``(status, None)``
    for an error status or an answer that is not an OCS JSON document. Never
    raises for a network error; logs carry the action, a status and the error
    type, never the URL or the body.
    """
    try:
        response = await client.post(
            queue_url(action),
            json=body,
            headers=app_api_headers() | {"Accept": "application/json"},
        )
    except httpx.HTTPError as error:
        LOGGER.info("queue not reached", extra={"action": action, "error_type": type(error).__name__})
        return None, None
    if response.status_code >= _FIRST_ERROR_STATUS:
        LOGGER.warning("queue refused", extra={"action": action, "status": response.status_code})
        return response.status_code, None
    try:
        payload = response.json()
    except ValueError:
        return response.status_code, None
    ocs = payload.get("ocs") if isinstance(payload, dict) else None
    data = ocs.get("data") if isinstance(ocs, dict) else None
    return response.status_code, data


# The capture of the discovery (plan 02-08): every reference is read once, in
# full, through its own file id and its own reader, into a temporary file under
# the persistent volume. Never straight into a decoder: the gateway holds a
# shared lock on the file for as long as the stream runs, so the lock lasts as
# long as the download and never as long as a decode (RESEARCH, Pattern 1).
#
# The error codes are the closed list of the state machine in
# worker/capture.py. Every one of them is a verdict on this one copy as read by
# this one reader; none of them is ever a success.
READ_DENIED: Final = "read_denied"
ACCESS_CONTROL: Final = "access_control"
EXCLUDED: Final = "excluded"
LOCKED: Final = "locked"
NOT_FOUND: Final = "not_found"
READ_TIMEOUT: Final = "read_timeout"
SIZE_MISMATCH: Final = "size_mismatch"
DISK_FULL: Final = "disk_full"
TOO_LARGE: Final = "too_large"
FETCH_ERRORS: Final = frozenset(
    {
        READ_DENIED,
        ACCESS_CONTROL,
        EXCLUDED,
        LOCKED,
        NOT_FOUND,
        READ_TIMEOUT,
        GATEWAY_FAILED,
        SIZE_MISMATCH,
        DISK_FULL,
        TOO_LARGE,
    }
)

# The head of a content: what the read proof of a further copy reads (D-02-01a).
HEAD_BYTES: Final = 65536
# The PHP app names the reason of a 403 in this header of its answer
# (GatewayController, plan 02-10): access_control (files_accesscontrol) or
# excluded (plan 02-16); 423 carries locked. A header, because the OCS body is
# XML or JSON depending on the request, while a header survives both unchanged.
REASON_HEADER: Final = "X-AVS-Reason"
_FORBIDDEN_REASONS: Final = frozenset({ACCESS_CONTROL, EXCLUDED})
_STATUS_OK: Final = 200
_STATUS_FORBIDDEN: Final = 403
_STATUS_NOT_FOUND: Final = 404
_STATUS_UNPROCESSABLE: Final = 422
_STATUS_LOCKED: Final = 423
# Connect fast or fail, and at most 30 s of silence between two blocks.
CAPTURE_TIMEOUT: Final = httpx.Timeout(30.0, connect=10.0)
# A whole download has a deadline too, so an answer that trickles one byte
# every 29 s cannot hold the one capture slot forever: two minutes plus the
# time of the expected size at 256 KiB/s.
CAPTURE_DEADLINE_BASE_SECONDS: Final = 120.0
CAPTURE_DEADLINE_BYTES_PER_SECOND: Final = 256 * 1024
# What stays free on the volume besides the file itself.
DISK_RESERVE_BYTES: Final = 256 * 1024 * 1024
PART_SUFFIX: Final = ".part"


def free_bytes(directory: Path) -> int:
    """Free space of the file system that holds ``directory``; a test replaces this."""
    return shutil.disk_usage(directory).free


def capture_deadline(expected_size: int) -> float:
    """Seconds one download of ``expected_size`` bytes may take in total."""
    return CAPTURE_DEADLINE_BASE_SECONDS + expected_size / CAPTURE_DEADLINE_BYTES_PER_SECOND


def new_capture_client() -> httpx.AsyncClient:
    """A client for the capture. Redirects are not followed: they would carry the credential away."""
    return httpx.AsyncClient(verify=_certificate_setting(), timeout=CAPTURE_TIMEOUT, follow_redirects=False)


def _refused(file_id: int, error: str, status: int | None) -> FetchResult:
    # A code, the file id and a status; never the user, a name, a path or the body.
    LOGGER.info("capture read refused", extra={"file_id": file_id, "reason": error, "status": status})
    return FetchResult(sha256=None, size=0, error=error, status=status)


def refusal_code(status: int, reason_header: str) -> str:
    """The error code of an answer that is not 200, from its status and the reason header."""
    reason = reason_header.strip().lower()
    if status == _STATUS_LOCKED:
        return LOCKED
    if status == _STATUS_FORBIDDEN:
        # Only the two named reasons change the verdict; anything else in the
        # header (or none) is the plain refusal of the gateway.
        return reason if reason in _FORBIDDEN_REASONS else READ_DENIED
    if status == _STATUS_UNPROCESSABLE:
        # fopen failed in the gateway (GatewayController): this reader cannot
        # read the bytes, whatever the listing says.
        return READ_DENIED
    if status == _STATUS_NOT_FOUND:
        return NOT_FOUND
    # 5xx, 401, 412, a redirect or any other answer: never content.
    return GATEWAY_FAILED


def _write(handle: BinaryIO, chunk: bytes) -> None:
    handle.write(chunk)


def _open_part(part: Path) -> BinaryIO:
    # "x": the name is fresh and random; an existing file is an error, never overwritten.
    return part.open("xb")


async def _stream_to_file(
    client: httpx.AsyncClient, file_id: int, user_id: str, part: Path, expected_size: int
) -> FetchResult:
    digest = hashlib.sha256()
    head = hashlib.sha256()
    size = 0
    async with client.stream(
        "GET", gateway_url(file_id), params={"userId": user_id}, headers=app_api_headers()
    ) as response:
        if response.status_code != _STATUS_OK:
            # The body is not read: it may be an OCS document or a proxy page.
            code = refusal_code(response.status_code, response.headers.get(REASON_HEADER, ""))
            return _refused(file_id, code, response.status_code)
        declared = response.headers.get("Content-Length", "")
        if declared.isdigit() and int(declared) != expected_size:
            return _refused(file_id, SIZE_MISMATCH, response.status_code)
        handle = await asyncio.to_thread(_open_part, part)
        try:
            async for chunk in response.aiter_bytes(CHUNK_SIZE):
                if size < HEAD_BYTES:
                    head.update(chunk[: HEAD_BYTES - size])
                size += len(chunk)
                if size > expected_size:
                    return _refused(file_id, SIZE_MISMATCH, response.status_code)
                digest.update(chunk)
                await asyncio.to_thread(_write, handle, chunk)
        finally:
            await asyncio.to_thread(handle.close)
    if size != expected_size:
        return _refused(file_id, SIZE_MISMATCH, _STATUS_OK)
    return FetchResult(sha256=digest.hexdigest(), size=size, error=None, head_sha256=head.hexdigest())


def _unlink(part: Path) -> None:
    part.unlink(missing_ok=True)


async def fetch_to_tempfile(
    file_id: int,
    user_id: str,
    tmp_dir: Path,
    expected_size: int,
    max_bytes: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> FetchResult:
    """Read one file completely through the gateway into a temporary file and hash it on the way.

    The sha256 of all bytes and the sha256 of the first 64 KiB come out of the
    stream; the temporary file under ``tmp_dir`` is deleted on every way out,
    so nothing of the content stays behind. Only a 200 whose byte count is
    exactly ``expected_size`` is a result; every other outcome is an error code
    of :data:`FETCH_ERRORS` and never a hash:

    - more than ``max_bytes`` expected: ``too_large``, no request;
    - not enough free space for the file plus a reserve: ``disk_full``, no request;
    - 403 ``read_denied`` (or ``access_control`` / ``excluded`` by the reason
      header), 422 ``read_denied``, 423 ``locked``, 404 ``not_found``;
    - a timeout or the overall deadline: ``read_timeout``;
    - any other status, a network error or a stream that breaks off: ``gateway_failed``;
    - fewer or more bytes than expected: ``size_mismatch``.

    Logs carry the file id, a status and a code; never the user, a name or a path.
    """
    if expected_size > max_bytes:
        return _refused(file_id, TOO_LARGE, None)
    try:
        free = await asyncio.to_thread(free_bytes, tmp_dir)
    except OSError:
        return _refused(file_id, DISK_FULL, None)
    if free < expected_size + DISK_RESERVE_BYTES:
        return _refused(file_id, DISK_FULL, None)
    part = tmp_dir / (secrets.token_hex(16) + PART_SUFFIX)
    try:
        async with asyncio.timeout(capture_deadline(expected_size)):
            if client is not None:
                return await _stream_to_file(client, file_id, user_id, part, expected_size)
            async with new_capture_client() as owned:
                return await _stream_to_file(owned, file_id, user_id, part, expected_size)
    except (TimeoutError, httpx.TimeoutException):
        return _refused(file_id, READ_TIMEOUT, None)
    except httpx.HTTPError as error:
        LOGGER.warning("capture stream broke off", extra={"file_id": file_id, "error_type": type(error).__name__})
        return _refused(file_id, GATEWAY_FAILED, None)
    except OSError as error:
        # Writing the temporary file failed (volume full after all, read only).
        LOGGER.warning("capture could not write", extra={"file_id": file_id, "error_type": type(error).__name__})
        return _refused(file_id, DISK_FULL, None)
    finally:
        await asyncio.to_thread(_unlink, part)


def remove_stale_parts(tmp_dir: Path) -> int:
    """Delete the temporary files a stopped process left behind; returns how many."""
    if not tmp_dir.is_dir():
        return 0
    removed = 0
    for leftover in tmp_dir.glob("*" + PART_SUFFIX):
        if leftover.is_file():
            leftover.unlink(missing_ok=True)
            removed += 1
    return removed
