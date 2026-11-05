"""The admin settings page, declared to AppAPI instead of built as a frontend.

AppAPI renders a declarative form with Nextcloud's own components, so the page
follows theming, dark mode and high contrast without a line of CSS here. The
values of an admin form land in the app config of the ExApp (appconfig_ex), a
personal form would land in the user preferences (preferences_ex).

Every text below is the English source string. The German and French wording
lives in l10n/de.json and l10n/fr.json under exactly this text as the key, and
tests/test_l10n.py holds the catalogues to this module.
"""

from typing import Final

from audio_video_search import APP_ID
from audio_video_search.nc import AsyncNextcloudApp, SettingsField, SettingsFieldType, SettingsForm

FORM_ID: Final = f"{APP_ID}_admin"

# The admin section the form appears in. "additional" is "Additional settings"
# and exists on every instance; a declarative form cannot create its own section.
SECTION_ID: Final = "additional"

# Field ids double as appconfig_ex keys. Keep them stable across releases: a
# renamed id silently drops the value an admin already saved.
PROCESSING_ENABLED: Final = "processing_enabled"
MAX_FILE_SIZE_MB: Final = "max_file_size_mb"

DEFAULTS: Final[dict[str, str]] = {PROCESSING_ENABLED: "1", MAX_FILE_SIZE_MB: "100"}


def admin_form() -> SettingsForm:
    """The admin form of this app."""
    return SettingsForm(
        id=FORM_ID,
        section_id=SECTION_ID,
        section_type="admin",
        title="Audio & Video Search",
        description="Settings of the Audio & Video Search backend. Changes apply to the next job.",
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
                id=MAX_FILE_SIZE_MB,
                title="Largest file in MB",
                description="Larger files are skipped and listed as skipped.",
                type=SettingsFieldType.NUMBER,
                default=int(DEFAULTS[MAX_FILE_SIZE_MB]),
                placeholder="100",
            ),
        ],
    )


def user_visible_strings(form: SettingsForm) -> list[str]:
    """Every text of a form that a person reads, in the order of the form."""
    texts = [form.title, form.description]
    for field in form.fields:
        texts += [field.title, field.description, field.label, field.placeholder]
    return [text for text in texts if text and not text.isdigit()]


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
