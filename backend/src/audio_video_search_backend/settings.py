"""The admin settings page, declared to AppAPI instead of built as a frontend.

AppAPI renders a declarative form with Nextcloud's own components, so the page
follows theming, dark mode and high contrast without a line of CSS here. The
values of an admin form land in the app config of the ExApp (appconfig_ex), a
personal form would land in the user preferences (preferences_ex).

Every text below is the English source string. The German and French wording
lives in l10n/de.json and l10n/fr.json under exactly this text as the key, and
tests/test_trilingual.py holds the catalogues to this module.
"""

from collections.abc import Mapping
from typing import Final

from audio_video_search_backend import APP_ID
from audio_video_search_backend.nc import AsyncNextcloudApp, SettingsField, SettingsFieldType, SettingsForm

FORM_ID: Final = f"{APP_ID}_admin"

# The admin section the form appears in. "additional" is "Additional settings"
# and exists on every instance; a declarative form cannot create its own section.
SECTION_ID: Final = "additional"

# Field ids double as appconfig_ex keys. Keep them stable across releases: a
# renamed id silently drops the value an admin already saved.
PROCESSING_ENABLED: Final = "processing_enabled"
# The longest recording in hours (D-03-08, D-03-09). It replaced the largest
# file in MB (D-03-17, plan 03-11): the id of that old field is gone, so a
# value saved under it is no longer read. No other size limit is left but the
# guard MAX_CAPTURE_BYTES of worker/capture.py.
MAX_DURATION_HOURS: Final = "max_duration_hours"
DEFAULT_MAX_DURATION_HOURS: Final = 12
# The cap is the longest time mark the API takes: api.MAX_AT_MS is 86 400 000 ms,
# 24 h (owner 14.11.2026: "24 h reicht"). A higher cap would first need a
# higher MAX_AT_MS here and a higher PageController::MAX_START_SECONDS in the
# PHP app; that is not part of phase 3.
MAX_DURATION_CAP_HOURS: Final = 24

DEFAULTS: Final[dict[str, str]] = {PROCESSING_ENABLED: "1", MAX_DURATION_HOURS: str(DEFAULT_MAX_DURATION_HOURS)}


def admin_form() -> SettingsForm:
    """The admin form of this app."""
    return SettingsForm(
        id=FORM_ID,
        section_id=SECTION_ID,
        section_type="admin",
        title="Audio & Video Search",
        description=(
            "This app is the backend of Audio & Video Search. "
            'Without the app "Audio & Video Search" from the App Store, search finds nothing in audio and video '
            "files. Once both apps are installed, their state is shown under Administration, Audio & Video Search."
        ),
        priority=50,
        fields=[
            SettingsField(
                id=PROCESSING_ENABLED,
                title="Processing",
                type=SettingsFieldType.CHECKBOX,
                label="Process new files automatically",
                default=True,
            ),
            SettingsField(
                id=MAX_DURATION_HOURS,
                title="Longest recording in hours",
                description=(
                    "Longer recordings are skipped as too long. If the limit is raised, they are transcribed later."
                ),
                type=SettingsFieldType.NUMBER,
                default=DEFAULT_MAX_DURATION_HOURS,
                placeholder=str(DEFAULT_MAX_DURATION_HOURS),
            ),
        ],
    )


def user_visible_strings(form: SettingsForm) -> list[str]:
    """Every text of a form that a person reads, in the order of the form."""
    texts = [form.title, form.description]
    for field in form.fields:
        texts += [field.title, field.description, field.label, field.placeholder]
    return [text for text in texts if text and not text.isdigit()]


def read_max_duration_hours(values: Mapping[str, str]) -> int:
    """The longest recording in whole hours, 1 to MAX_DURATION_CAP_HOURS.

    The value comes from appconfig_ex as text. Anything that is not a whole
    positive number (empty, 0, negative, a fraction, a word) is the default,
    so a slip in the form never stops or floods the work; a number above the
    cap is the cap (T-03-37).
    """
    text = values.get(MAX_DURATION_HOURS, "").strip()
    if not (text.isascii() and text.isdigit()):
        return DEFAULT_MAX_DURATION_HOURS
    digits = text.lstrip("0")
    if not digits:
        return DEFAULT_MAX_DURATION_HOURS
    # More digits than the cap has is above the cap; int() never sees a long text.
    if len(digits) > len(str(MAX_DURATION_CAP_HOURS)):
        return MAX_DURATION_CAP_HOURS
    return min(int(digits), MAX_DURATION_CAP_HOURS)


async def register(nc: AsyncNextcloudApp) -> None:
    """Register or update the admin form."""
    await nc.ui.settings.register_form(admin_form())


async def unregister(nc: AsyncNextcloudApp) -> None:
    """Remove the admin form; a form that is already gone is not an error."""
    await nc.ui.settings.unregister_form(FORM_ID)


async def read(nc: AsyncNextcloudApp) -> dict[str, str]:
    """The saved values with the defaults filled in."""
    values = dict(DEFAULTS)
    for entry in await nc.appconfig_ex.get_values(list(DEFAULTS)):
        if entry.key in values and entry.value is not None:
            values[entry.key] = entry.value
    return values
