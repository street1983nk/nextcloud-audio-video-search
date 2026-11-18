"""The compute window in the admin's IANA zone (plan 05-04, RES-05, D-05-03).

The container runs in UTC, "22 to 6" means the wall clock of the admin
(pitfall 4). Every instant goes in as an aware UTC datetime. Both daylight
saving changes of 2026 in Europe/Berlin and the run over midnight are covered.
"""

from datetime import UTC, datetime, time, timedelta

import pytest
from audio_video_search_backend.schedule import (
    WindowError,
    next_change,
    parse_hhmm,
    validate_window,
    window_open,
)

BERLIN = "Europe/Berlin"
NIGHT = (time(22, 0), time(6, 0))
DAY = (time(8, 0), time(17, 0))


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


# --- parse_hhmm -------------------------------------------------------------------


@pytest.mark.parametrize(("raw", "parsed"), [("00:00", time(0, 0)), ("06:05", time(6, 5)), ("23:59", time(23, 59))])
def test_parse_hhmm_accepts_two_digit_times(raw: str, parsed: time) -> None:
    assert parse_hhmm(raw) == parsed


@pytest.mark.parametrize("raw", ["24:00", "7:5", "", "07:60", "7:05", "07:05 ", "0705", "ab:cd", "07:05:00"])
def test_parse_hhmm_refuses_everything_else(raw: str) -> None:
    with pytest.raises(WindowError) as caught:
        parse_hhmm(raw, "window_end")
    assert caught.value.field == "window_end"


def test_parse_hhmm_names_the_start_by_default() -> None:
    with pytest.raises(WindowError) as caught:
        parse_hhmm("x")
    assert caught.value.field == "window_start"


# --- validate_window --------------------------------------------------------------


def test_no_window_is_always() -> None:
    assert validate_window(None, None, BERLIN) == (None, None, BERLIN)


def test_valid_window_is_parsed() -> None:
    assert validate_window("22:00", "06:00", BERLIN) == (time(22, 0), time(6, 0), BERLIN)


def test_same_start_and_end_is_refused() -> None:
    with pytest.raises(WindowError) as caught:
        validate_window("08:00", "08:00", BERLIN)
    assert caught.value.field == "window_same"


@pytest.mark.parametrize("raw", ["24:00", "7:5", ""])
def test_bad_start_is_refused(raw: str) -> None:
    with pytest.raises(WindowError) as caught:
        validate_window(raw, "06:00", BERLIN)
    assert caught.value.field == "window_start"


@pytest.mark.parametrize("raw", ["24:00", "7:5", ""])
def test_bad_end_is_refused(raw: str) -> None:
    with pytest.raises(WindowError) as caught:
        validate_window("22:00", raw, BERLIN)
    assert caught.value.field == "window_end"


def test_start_without_end_is_refused() -> None:
    with pytest.raises(WindowError) as caught:
        validate_window("22:00", None, BERLIN)
    assert caught.value.field == "window_end"


def test_end_without_start_is_refused() -> None:
    with pytest.raises(WindowError) as caught:
        validate_window(None, "06:00", BERLIN)
    assert caught.value.field == "window_start"


@pytest.mark.parametrize("zone", ["Mars/Olympus", "", "../etc/passwd", "Europe/"])
def test_unknown_zone_is_refused(zone: str) -> None:
    with pytest.raises(WindowError) as caught:
        validate_window("22:00", "06:00", zone)
    assert caught.value.field == "window_zone"


def test_window_error_is_a_value_error() -> None:
    assert issubclass(WindowError, ValueError)
    assert str(WindowError("window_zone")) == "window_zone"


# --- window_open --------------------------------------------------------------------


@pytest.mark.parametrize("hour", [0, 5, 12, 23])
def test_no_window_is_always_open(hour: int) -> None:
    assert window_open(_utc(2026, 1, 15, hour), None, None, BERLIN)


def test_one_missing_bound_is_open() -> None:
    assert window_open(_utc(2026, 1, 15, 12), time(22, 0), None, BERLIN)


def test_night_window_in_winter_uses_local_time() -> None:
    assert window_open(_utc(2026, 1, 15, 21, 30), *NIGHT, BERLIN)  # 22:30 CET
    assert not window_open(_utc(2026, 1, 15, 5, 30), *NIGHT, BERLIN)  # 06:30 CET
    assert not window_open(_utc(2026, 1, 15, 20, 30), *NIGHT, BERLIN)  # 21:30 CET


def test_night_window_runs_over_midnight() -> None:
    assert window_open(_utc(2026, 1, 15, 23, 0), *NIGHT, BERLIN)  # 00:00 CET
    assert window_open(_utc(2026, 1, 16, 2, 0), *NIGHT, BERLIN)  # 03:00 CET
    assert not window_open(_utc(2026, 1, 16, 12, 0), *NIGHT, BERLIN)


def test_night_window_on_the_spring_change_2026() -> None:
    # 29.03.2026: 02:00 CET jumps to 03:00 CEST at 01:00 UTC.
    assert window_open(_utc(2026, 3, 29, 3, 30), *NIGHT, BERLIN)  # 05:30 CEST
    assert not window_open(_utc(2026, 3, 29, 4, 30), *NIGHT, BERLIN)  # 06:30 CEST
    assert window_open(_utc(2026, 3, 29, 1, 30), *NIGHT, BERLIN)  # 03:30 CEST, inside


def test_night_window_on_the_autumn_change_2026() -> None:
    # 25.10.2026: 03:00 CEST falls back to 02:00 CET at 01:00 UTC.
    assert window_open(_utc(2026, 10, 25, 4, 30), *NIGHT, BERLIN)  # 05:30 CET
    assert not window_open(_utc(2026, 10, 25, 5, 30), *NIGHT, BERLIN)  # 06:30 CET
    assert window_open(_utc(2026, 10, 25, 0, 30), *NIGHT, BERLIN)  # 02:30 CEST, first pass
    assert window_open(_utc(2026, 10, 25, 1, 30), *NIGHT, BERLIN)  # 02:30 CET, second pass


def test_day_window_edges() -> None:
    assert not window_open(_utc(2026, 6, 1, 7, 59), *DAY, "UTC")
    assert window_open(_utc(2026, 6, 1, 8, 0), *DAY, "UTC")
    assert window_open(_utc(2026, 6, 1, 16, 59), *DAY, "UTC")
    assert not window_open(_utc(2026, 6, 1, 17, 0), *DAY, "UTC")


def test_day_window_in_summer_is_shifted_by_two_hours() -> None:
    assert not window_open(_utc(2026, 7, 1, 5, 30), *DAY, BERLIN)  # 07:30 CEST
    assert window_open(_utc(2026, 7, 1, 6, 0), *DAY, BERLIN)  # 08:00 CEST
    assert not window_open(_utc(2026, 7, 1, 15, 0), *DAY, BERLIN)  # 17:00 CEST


def test_naive_instant_is_refused() -> None:
    with pytest.raises(ValueError, match="aware"):
        window_open(datetime(2026, 1, 15, 12, 0), *NIGHT, BERLIN)


def test_window_open_with_unknown_zone_is_a_window_error() -> None:
    with pytest.raises(WindowError) as caught:
        window_open(_utc(2026, 1, 15, 12), *NIGHT, "Mars/Olympus")
    assert caught.value.field == "window_zone"


# --- next_change --------------------------------------------------------------------


def test_always_open_has_no_change() -> None:
    assert next_change(_utc(2026, 1, 15, 12), None, None, BERLIN) is None


def test_next_opening_is_in_the_zone() -> None:
    change = next_change(_utc(2026, 1, 15, 12), *NIGHT, BERLIN)
    assert change is not None
    assert change.utcoffset() == timedelta(hours=1)
    assert (change.hour, change.minute) == (22, 0)
    assert change.astimezone(UTC) == _utc(2026, 1, 15, 21)


def test_next_closing_over_midnight() -> None:
    change = next_change(_utc(2026, 1, 15, 22), *NIGHT, BERLIN)  # 23:00 CET, open
    assert change is not None
    assert change.astimezone(UTC) == _utc(2026, 1, 16, 5)  # 06:00 CET


def test_next_closing_on_the_spring_change_2026() -> None:
    change = next_change(_utc(2026, 3, 28, 22), *NIGHT, BERLIN)  # 23:00 CET, open
    assert change is not None
    assert change.astimezone(UTC) == _utc(2026, 3, 29, 4)  # 06:00 CEST
    assert change.utcoffset() == timedelta(hours=2)


def test_next_closing_on_the_autumn_change_2026() -> None:
    change = next_change(_utc(2026, 10, 24, 21), *NIGHT, BERLIN)  # 23:00 CEST, open
    assert change is not None
    assert change.astimezone(UTC) == _utc(2026, 10, 25, 5)  # 06:00 CET
    assert change.utcoffset() == timedelta(hours=1)


def test_next_opening_on_the_autumn_change_day() -> None:
    change = next_change(_utc(2026, 10, 25, 12), *NIGHT, BERLIN)
    assert change is not None
    assert change.astimezone(UTC) == _utc(2026, 10, 25, 21)  # 22:00 CET


def test_next_change_from_inside_a_minute_is_the_whole_minute() -> None:
    change = next_change(datetime(2026, 6, 1, 7, 59, 30, tzinfo=UTC), *DAY, "UTC")
    assert change == _utc(2026, 6, 1, 8, 0)


def test_next_change_searches_at_most_48_hours() -> None:
    # A one minute window that never opens within the zone's day cannot be
    # built from valid input; an always closed check stands in for it.
    change = next_change(_utc(2026, 6, 1, 8, 0), *DAY, "UTC", horizon=timedelta(minutes=30))
    assert change is None


def test_next_change_refuses_naive_instants() -> None:
    with pytest.raises(ValueError, match="aware"):
        next_change(datetime(2026, 1, 15, 12, 0), *NIGHT, BERLIN)
