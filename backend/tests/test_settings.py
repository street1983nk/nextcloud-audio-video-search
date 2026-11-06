"""The declarative admin page and the l10n catalogue pair (.json and .js)."""

import subprocess
import sys
from types import SimpleNamespace
from typing import Any

from audio_video_search_backend import APP_ID, settings
from tests.conftest import BACKEND_ROOT, REPO_ROOT


def test_the_form_is_an_admin_form_with_stable_ids() -> None:
    form = settings.admin_form().to_dict()

    assert form["id"] == f"{APP_ID}_admin"
    assert form["section_type"] == "admin"
    assert [field["id"] for field in form["fields"]] == ["processing_enabled", "max_file_size_mb"]
    assert set(settings.DEFAULTS) == {field["id"] for field in form["fields"]}


def test_user_visible_strings_skip_numbers_and_empty_texts() -> None:
    texts = settings.user_visible_strings(settings.admin_form())

    assert "100" not in texts
    assert "" not in texts
    assert "Processing" in texts


async def test_read_fills_in_defaults_and_takes_saved_values() -> None:
    async def get_values(keys: list[str]) -> list[Any]:
        assert set(keys) == set(settings.DEFAULTS)
        return [SimpleNamespace(key="max_file_size_mb", value="5"), SimpleNamespace(key="unknown", value="x")]

    nc: Any = SimpleNamespace(appconfig_ex=SimpleNamespace(get_values=get_values))

    assert await settings.read(nc) == {"processing_enabled": "1", "max_file_size_mb": "5"}


def test_the_js_catalogues_match_their_json_source() -> None:
    result = subprocess.run(  # noqa: S603 - fixed arguments
        [sys.executable, str(REPO_ROOT / "scripts" / "l10n_js.py"), "--check", "--root", str(BACKEND_ROOT / "l10n")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
