"""The declarative admin page and the l10n catalogue pair (.json and .js)."""

import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from audio_video_search_backend import APP_ID, settings
from tests.conftest import BACKEND_ROOT, REPO_ROOT


def test_the_form_is_an_admin_form_with_stable_ids() -> None:
    form = settings.admin_form().to_dict()

    assert form["id"] == f"{APP_ID}_admin"
    assert form["section_type"] == "admin"
    assert [field["id"] for field in form["fields"]] == ["processing_enabled", "max_duration_hours"]
    assert set(settings.DEFAULTS) == {field["id"] for field in form["fields"]}


def test_user_visible_strings_skip_numbers_and_empty_texts() -> None:
    texts = settings.user_visible_strings(settings.admin_form())

    assert "12" not in texts
    assert "" not in texts
    assert "Processing" in texts


async def test_read_fills_in_defaults_and_takes_saved_values() -> None:
    async def get_values(keys: list[str]) -> list[Any]:
        assert set(keys) == set(settings.DEFAULTS)
        return [SimpleNamespace(key="max_duration_hours", value="5"), SimpleNamespace(key="unknown", value="x")]

    nc: Any = SimpleNamespace(appconfig_ex=SimpleNamespace(get_values=get_values))

    assert await settings.read(nc) == {"processing_enabled": "1", "max_duration_hours": "5"}


def test_the_js_catalogues_match_their_json_source() -> None:
    result = subprocess.run(  # noqa: S603 - fixed arguments
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "l10n_js.py"),
            "--check",
            "--root",
            str(BACKEND_ROOT / "l10n"),
            "--root",
            str(REPO_ROOT / "php" / "l10n"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout


def test_the_description_works_without_the_php_app() -> None:
    """PLAT-02, owner 07.11.: the admin page of the PHP app is only promised once both apps are installed."""
    description = settings.admin_form().description

    assert 'Without the app "Audio & Video Search" from the App Store' in description
    assert "Once both apps are installed, their state is shown under Administration" in description
    assert "needs the app" not in description


def test_the_longest_recording_replaces_the_largest_file() -> None:
    """D-03-09, D-03-17: a duration limit in hours, default 12; no size limit any more."""
    fields = {field["id"]: field for field in settings.admin_form().to_dict()["fields"]}

    assert "max_file_size_mb" not in fields
    assert "max_file_size_mb" not in settings.DEFAULTS
    field = fields["max_duration_hours"]
    assert field["type"] == "number"
    assert field["default"] == 12
    assert field["placeholder"] == "12"
    assert settings.DEFAULTS["max_duration_hours"] == "12"


def test_the_texts_of_the_duration_field_are_the_approved_ones() -> None:
    """03-01-SUMMARY.md, owner 14.11.2026: "Freigegeben"."""
    texts = settings.user_visible_strings(settings.admin_form())

    assert "Longest recording in hours" in texts
    assert "Longer recordings are skipped as too long. If the limit is raised, they are transcribed later." in texts
    assert "Largest file in MB" not in texts


@pytest.mark.parametrize(
    ("saved", "hours"),
    [
        ("12", 12),
        ("1", 1),
        ("5", 5),
        ("24", 24),
        ("25", 24),
        ("200", 24),
        ("0", 12),
        ("-3", 12),
        ("abc", 12),
        ("", 12),
        (" 7 ", 7),
        ("1.5", 12),
        ("1e3", 12),
    ],
)
def test_the_longest_recording_is_read_with_default_and_cap(saved: str, hours: int) -> None:
    assert settings.read_max_duration_hours({"max_duration_hours": saved}) == hours


def test_a_missing_longest_recording_is_the_default() -> None:
    assert settings.read_max_duration_hours({}) == 12
    assert settings.DEFAULT_MAX_DURATION_HOURS == 12


def test_the_cap_is_the_longest_time_mark_of_the_api() -> None:
    """Owner 14.11.2026: "24 h reicht"; a time mark beyond api.MAX_AT_MS could not be searched."""
    from audio_video_search_backend import api

    assert settings.MAX_DURATION_CAP_HOURS == 24
    assert settings.MAX_DURATION_CAP_HOURS * 3_600_000 == api.MAX_AT_MS
