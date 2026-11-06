"""backend/appinfo/info.xml against the store schema edges and the release lockstep.

Taken over from Findling's test_store_metadata.py, reduced to what every ExApp
needs. The store validation path itself (pre-info.xslt plus info.xsd at a pinned
appstore commit) runs in release.yml; this gate says the same things offline,
in a second, and names the file and the value.
"""

import re
import tomllib
from xml.etree import ElementTree

from audio_video_search_backend import APP_ID, config
from tests.conftest import BACKEND_ROOT, REPO_ROOT

INFO_XML = BACKEND_ROOT / "appinfo" / "info.xml"
OWNER = "street1983nk"
# One repository carries both halves; its name follows the PHP app, not the backend.
REPOSITORY_NAME = "nextcloud-audio-video-search"
REPOSITORY = f"https://github.com/{OWNER}/{REPOSITORY_NAME}"
RAW_MEDIA_PREFIX = f"https://raw.githubusercontent.com/{OWNER}/{REPOSITORY_NAME}/main/store/media/"
LENGTH_LIMIT = 128
INFO_XML_MAX_BYTES = 512 * 1024
ALLOWED_LANGUAGES = ("", "de", "fr")

# Read out of nextcloudappstore/core/fixtures/categories.json and info.xsd at the
# appstore commit release.yml pins (Findling, 06.09.2026). Raise both together.
STORE_CATEGORIES = frozenset(
    {
        "ai",
        "customization",
        "dashboard",
        "files",
        "games",
        "integration",
        "monitoring",
        "multimedia",
        "office",
        "organization",
        "search",
        "security",
        "social",
        "tools",
        "workflow",
    }
)
ROUTE_URL = re.compile(r"^\^/[A-Za-z0-9_./\-*()|?+\\\[\]]*\$?$")
ACCESS_LEVELS = frozenset({"PUBLIC", "USER", "ADMIN"})


def info() -> ElementTree.Element:
    return ElementTree.fromstring(INFO_XML.read_text(encoding="utf-8"))  # noqa: S314 - our own file


def text(element: ElementTree.Element, path: str) -> str:
    found = element.find(path)
    assert found is not None, path
    return (found.text or "").strip()


def test_the_id_is_the_package_app_id() -> None:
    assert text(info(), "id") == APP_ID


def test_version_image_tag_and_pyproject_are_one_number() -> None:
    root = info()
    project = tomllib.loads((BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    version = text(root, "version")
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert text(root, "external-app/docker-install/image-tag") == version
    assert project["version"] == version


def test_the_changelog_carries_the_current_version() -> None:
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert f"## {text(info(), 'version')}" in changelog


def test_the_image_lives_under_the_owner_on_ghcr() -> None:
    root = info()

    assert text(root, "external-app/docker-install/registry") == "ghcr.io"
    assert text(root, "external-app/docker-install/image") == f"{OWNER}/{APP_ID}"


def test_names_and_summaries_fit_the_schema_and_use_known_languages() -> None:
    for kind in ("name", "summary", "description"):
        seen = []
        for element in info().findall(kind):
            language = element.get("lang", "")
            assert language in ALLOWED_LANGUAGES, f"{kind} lang={language}"
            assert language not in seen, f"{kind} lang={language} twice"
            seen.append(language)
            if kind != "description":
                assert len((element.text or "").strip()) <= LENGTH_LIMIT, f"{kind} lang={language}"


def test_licence_and_categories_are_values_the_store_accepts() -> None:
    root = info()

    assert [element.text for element in root.findall("licence")] == ["AGPL-3.0-or-later"]
    categories = [(element.text or "").strip() for element in root.findall("category")]
    assert categories
    assert set(categories) <= STORE_CATEGORIES


def test_the_links_point_at_this_repository() -> None:
    root = info()

    assert text(root, "website") == REPOSITORY
    assert text(root, "bugs") == f"{REPOSITORY}/issues"
    assert text(root, "repository") == f"{REPOSITORY}.git"


def test_screenshots_point_into_store_media_and_exist() -> None:
    # Optional while the app is young; SKELETON.md asks for one before the first
    # store release. An address no image stands behind shows an empty frame.
    for element in info().findall("screenshot"):
        url = (element.text or "").strip()
        assert url.startswith(RAW_MEDIA_PREFIX), url
        assert len(url) <= 256
        assert (REPO_ROOT / "store" / "media" / url[len(RAW_MEDIA_PREFIX) :]).is_file(), url


def test_routes_are_anchored_regular_expressions_with_an_access_level() -> None:
    routes = info().findall("external-app/routes/route")

    assert routes
    for route in routes:
        url = text(route, "url")
        assert ROUTE_URL.match(url), f"{url} is not of the form ^/<name>$"
        assert text(route, "access_level") in ACCESS_LEVELS
        assert text(route, "verb")


def test_environment_variables_carry_the_app_prefix_and_a_default() -> None:
    variables = info().findall("external-app/environment-variables/variable")

    assert [text(variable, "name") for variable in variables] == [config.LOG_LEVEL_VARIABLE]

    for variable in variables:
        assert text(variable, "name").startswith(config.ENV_PREFIX)
        assert variable.find("default") is not None
        assert text(variable, "display-name")


def test_the_file_stays_far_under_the_store_limit() -> None:
    assert INFO_XML.stat().st_size < INFO_XML_MAX_BYTES
