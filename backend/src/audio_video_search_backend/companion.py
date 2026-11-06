"""Is the PHP app there? The container side of the counterpart state.

The PHP app (the companion) owns the search provider, the events and the
content gateway; without it the container has nothing to work for and no way
to read a file. The container asks the handshake route of the PHP app at its
start and every five minutes (nc.fetch_handshake) and keeps one of three
states:

- ``ok``: the PHP app answered with a version that looks like a version.
- ``missing``: the PHP app answered 404 (not installed or not enabled), or the
  instance could not be reached three times in a row.
- ``unknown``: nothing asked yet, an answer without a valid version, or fewer
  than three failures in a row.

/status reports the state, /sample refuses to work while it is ``missing``.
A change to ``missing`` is logged once as a warning, with the state code and a
reason code only; no URL, no path, no answer content.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Final

from audio_video_search_backend import nc

LOGGER = logging.getLogger(__name__)

OK: Final = "ok"
MISSING: Final = "missing"
UNKNOWN: Final = "unknown"

CHECK_INTERVAL_SECONDS: Final = 300
# /status asks again when the last answer is older than this, so a change shows
# up in the admin section without waiting for the next periodic round.
STALE_SECONDS: float = 30.0
FAILURES_UNTIL_MISSING: Final = 3
_NOT_FOUND: Final = 404
_OK_STATUS: Final = 200
# The same shape the PHP app accepts for a version (ExAppService VERSION_PATTERN).
VERSION_PATTERN: Final = re.compile(r"\d{1,5}\.\d{1,5}(?:\.[0-9A-Za-z][0-9A-Za-z.-]{0,19})?")


@dataclass(frozen=True, slots=True)
class CompanionState:
    """What the container knows about the PHP app; ``checked_at`` is a monotonic clock value."""

    state: str
    version: str | None
    checked_at: float | None


_INITIAL: Final = CompanionState(state=UNKNOWN, version=None, checked_at=None)
_current: CompanionState = _INITIAL
_failures: int = 0


def current() -> CompanionState:
    """The last known state, without asking."""
    return _current


def reset() -> None:
    """Forget everything, as at the start of the process."""
    global _current, _failures  # one state per process, by design
    _current = _INITIAL
    _failures = 0


def _valid_version(value: str | None) -> str | None:
    if value is None:
        return None
    return value if VERSION_PATTERN.fullmatch(value) else None


def _judge(status: int | None, version: str | None) -> tuple[str, str | None, str]:
    """State, version and reason code for one answer; counts failures in a row."""
    global _failures
    if status == _OK_STATUS:
        _failures = 0
        valid = _valid_version(version)
        return (OK, valid, "answered") if valid is not None else (UNKNOWN, None, "no_version")
    if status == _NOT_FOUND:
        _failures = 0
        return MISSING, None, "not_found"
    _failures += 1
    if _failures >= FAILURES_UNTIL_MISSING:
        return MISSING, None, "unreachable"
    return UNKNOWN, None, "unreachable"


async def check_once() -> CompanionState:
    """Ask the PHP app once and remember the answer. Never raises."""
    global _current
    status, version = await nc.fetch_handshake()
    state, valid, reason = _judge(status, version)
    previous = _current.state
    _current = CompanionState(state=state, version=valid, checked_at=time.monotonic())
    if state != previous:
        level = logging.WARNING if state == MISSING else logging.INFO
        LOGGER.log(level, "companion state changed", extra={"companion": state, "reason": reason, "status": status})
    return _current


async def refresh_if_stale() -> CompanionState:
    """Ask again when the last answer is older than STALE_SECONDS, else return it."""
    checked_at = _current.checked_at
    if checked_at is None or time.monotonic() - checked_at > STALE_SECONDS:
        return await check_once()
    return _current


async def run_periodic(interval_s: int = CHECK_INTERVAL_SECONDS) -> None:
    """Ask at once and then every ``interval_s`` seconds until cancelled."""
    while True:
        try:
            await check_once()
        except Exception as exc:  # the loop must outlive any single round
            LOGGER.exception("companion check failed", extra={"error_type": type(exc).__name__})
        await asyncio.sleep(interval_s)
