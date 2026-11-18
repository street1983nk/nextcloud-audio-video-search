"""The compute window: when the engine may run (plan 05-04, RES-05, D-05-03, D-05-04).

Pure functions, standard library only, reading no environment and no
settings: the caller passes the stored values and the clock. No window
(None/None) means always, the default after the installation (D-05-03). A
window with start after end runs over midnight ("22:00" to "06:00").

The container runs in UTC while "22 to 6" means the admin's wall clock, so the
window carries an IANA zone and every instant is converted with ``zoneinfo``,
which keeps both daylight saving changes right (pitfall 4). Instants must be
aware; a naive datetime is refused instead of being guessed.

An invalid window is refused with a field code and never stored, so a bad
value can never turn into "never compute" (T-05-09).
"""

import re
from datetime import UTC, datetime, time, timedelta
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = ["WindowError", "next_change", "parse_hhmm", "validate_window", "window_open"]

_HHMM: Final = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

# next_change looks at most this far ahead (T-05-09b): every valid window
# opens and closes within a day, 48 hours cover a daylight saving change.
SEARCH_HORIZON: Final = timedelta(hours=48)
_STEP: Final = timedelta(minutes=1)


class WindowError(ValueError):
    """An invalid window; ``field`` is window_start, window_end, window_zone or window_same."""

    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


def parse_hhmm(raw: str, field: str = "window_start") -> time:
    """ "HH:MM" with two digits each, 00:00 to 23:59; anything else is a WindowError(field)."""
    if not _HHMM.fullmatch(raw):
        raise WindowError(field)
    hours, minutes = raw.split(":")
    return time(int(hours), int(minutes))


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        # ValueError covers keys zoneinfo refuses outright, such as "" or a path.
        raise WindowError("window_zone") from exc


def validate_window(start: str | None, end: str | None, zone: str) -> tuple[time | None, time | None, str]:
    """Parse and check a window from the admin; returns (start, end, zone).

    None/None is "always". Only one bound set names the missing one; equal
    bounds are ambiguous and refused as window_same. The zone is checked in
    every case, so a stored zone is always usable.
    """
    parsed_start = None if start is None else parse_hhmm(start, "window_start")
    parsed_end = None if end is None else parse_hhmm(end, "window_end")
    if parsed_start is not None and parsed_end is None:
        raise WindowError("window_end")
    if parsed_start is None and parsed_end is not None:
        raise WindowError("window_start")
    if parsed_start is not None and parsed_start == parsed_end:
        raise WindowError("window_same")
    _zone(zone)
    return parsed_start, parsed_end, zone


def _require_aware(instant: datetime) -> None:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("instant must be timezone aware")


def window_open(now_utc: datetime, start: time | None, end: time | None, zone: str) -> bool:
    """True when the engine may run at ``now_utc``.

    A missing bound is "always" (D-05-03). start < end is a window within the
    day, start > end one over midnight.
    """
    _require_aware(now_utc)
    if start is None or end is None:
        return True
    local = now_utc.astimezone(_zone(zone)).time().replace(tzinfo=None)
    if start < end:
        return start <= local < end
    return local >= start or local < end


def next_change(
    now_utc: datetime,
    start: time | None,
    end: time | None,
    zone: str,
    *,
    horizon: timedelta = SEARCH_HORIZON,
) -> datetime | None:
    """The next opening or closing after ``now_utc`` as an aware datetime in the zone.

    None when the window is always open, or when nothing changes within the
    horizon. The search walks whole minutes, so a bound that does not exist on
    a spring change day (02:30) is found at the first minute after the gap.
    """
    _require_aware(now_utc)
    if start is None or end is None:
        return None
    tz = _zone(zone)
    state = window_open(now_utc, start, end, zone)
    instant = now_utc.astimezone(UTC).replace(second=0, microsecond=0) + _STEP
    limit = now_utc + horizon
    while instant <= limit:
        if window_open(instant, start, end, zone) != state:
            return instant.astimezone(tz)
        instant += _STEP
    return None
