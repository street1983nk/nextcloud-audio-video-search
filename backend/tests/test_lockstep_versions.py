"""The version numbers of a release and the server window, held together.

Taken over from Findling's test_lockstep_versions.py. Both halves of this app
carry the same version and are released as a pair, so nobody ends up with a PHP
app and a container that disagree about the protocol between them. Four places
state that version:

* ``<version>`` in ``php/appinfo/info.xml``, the version of the PHP app,
* ``<version>`` in ``backend/appinfo/info.xml``, the version of the ExApp,
* ``<image-tag>`` in ``backend/appinfo/info.xml``, the tag the deploy daemon pulls,
* ``version`` in ``backend/pyproject.toml``, the version of the Python package.

The second gate holds the server window: both info.xml declare the same
``<nextcloud min-version max-version>``, and the matrix of deploy-harp.yml runs
exactly the majors of that window, no more and no fewer.

No number is demanded anywhere: a gate that pinned one would be edited at the
next bump without the equality ever being checked. Every rule has a self test
with a staged sample, so a gate whose body was deleted cannot stay green (the
anti vacuity clause of Findling).
"""

import re
import tomllib
from pathlib import Path

from tests.conftest import BACKEND_ROOT, REPO_ROOT

PHP_INFO = REPO_ROOT / "php" / "appinfo" / "info.xml"
BACKEND_INFO = BACKEND_ROOT / "appinfo" / "info.xml"
PYPROJECT = BACKEND_ROOT / "pyproject.toml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-harp.yml"

# How the values are named in a finding, file names included.
PHP_VERSION = "the version in php/appinfo/info.xml"
BACKEND_VERSION = "the version in backend/appinfo/info.xml"
IMAGE_TAG = "the image-tag in backend/appinfo/info.xml"
PYPROJECT_VERSION = "the version in backend/pyproject.toml"

# Read as text with the same expressions the sed lines of docker.yml use, so the
# gate cannot be green while the release step is red.
_VERSION = re.compile(r"<version>([^<]*)</version>")
_IMAGE_TAG = re.compile(r"<image-tag>([^<]*)</image-tag>")

# The semver type of the store schema (info.xsd): three number groups without
# leading zeros, an optional prerelease tail, no build metadata. Used with
# fullmatch, so no anchors here.
_SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-([0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*))?")


def _first(pattern: re.Pattern[str], source: str) -> str | None:
    """The first value of an element, or None when the file does not carry one."""
    found = pattern.search(source)
    return None if found is None else found.group(1).strip()


def _read(path: Path) -> str:
    """The source of one file, or an empty string when it is not there (fails closed)."""
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _pyproject_version(source: str) -> str | None:
    """The [project] version of a pyproject.toml, or None when it has none."""
    if not source:
        return None
    version = tomllib.loads(source).get("project", {}).get("version")
    return version.strip() if isinstance(version, str) else None


def _findings(php: str | None, backend: str | None, image: str | None, package: str | None) -> list[str]:
    """Every disagreement between the four values, one line each.

    A value that is not a version is reported as that and not a second time as
    a difference: one cause, one line.
    """
    values = {PHP_VERSION: php, BACKEND_VERSION: backend, IMAGE_TAG: image, PYPROJECT_VERSION: package}

    unreadable = [f"{side} could not be read at all" for side, value in values.items() if value is None]
    misshapen = [
        f"{side} is {value!r}, which is not a version of the shape the store accepts"
        for side, value in values.items()
        if value is not None and _SEMVER.fullmatch(value) is None
    ]
    if unreadable or misshapen:
        return unreadable + misshapen

    return [
        f"{side} is {value!r} and {BACKEND_VERSION} is {backend!r}"
        for side, value in ((PHP_VERSION, php), (IMAGE_TAG, image), (PYPROJECT_VERSION, package))
        if value != backend
    ]


def _of_the_tree() -> tuple[str | None, str | None, str | None, str | None]:
    """The four values as they stand in this checkout."""
    backend_source = _read(BACKEND_INFO)
    return (
        _first(_VERSION, _read(PHP_INFO)),
        _first(_VERSION, backend_source),
        _first(_IMAGE_TAG, backend_source),
        _pyproject_version(_read(PYPROJECT)),
    )


# -- the real tree: versions ---------------------------------------------------


def test_every_file_is_where_this_gate_looks_for_it() -> None:
    # The anti vacuity clause: renamed files would read as empty strings.
    missing = [str(path) for path in (PHP_INFO, BACKEND_INFO, PYPROJECT, WORKFLOW) if not path.is_file()]

    assert missing == []


def test_all_four_values_can_be_read() -> None:
    # The second half of the clause: a pattern that stopped matching would
    # compare None with None, which agrees perfectly.
    assert all(value not in (None, "") for value in _of_the_tree())


def test_both_halves_the_image_tag_and_the_package_carry_the_same_version() -> None:
    assert _findings(*_of_the_tree()) == []


# -- self tests: versions ------------------------------------------------------


def test_a_clean_sample_produces_no_finding() -> None:
    assert _findings("1.2.3", "1.2.3", "1.2.3", "1.2.3") == []
    assert _findings("1.2.3-rc.1", "1.2.3-rc.1", "1.2.3-rc.1", "1.2.3-rc.1") == []


def test_the_rule_fires_on_a_php_app_one_patch_ahead() -> None:
    # The acceptance case of plan 01-01: php/appinfo/info.xml on 0.1.1.
    findings = _findings("0.1.1", "0.1.0", "0.1.0", "0.1.0")

    assert findings == [f"{PHP_VERSION} is '0.1.1' and {BACKEND_VERSION} is '0.1.0'"]


def test_the_rule_fires_on_a_staged_copy_of_the_real_php_info(tmp_path: Path) -> None:
    # The same case against the real file, changed in a temporary copy only.
    copy = tmp_path / "info.xml"
    staged = re.sub(r"<version>[^<]*</version>", "<version>0.1.1</version>", _read(PHP_INFO), count=1)
    copy.write_text(staged, encoding="utf-8")
    _, backend, image, package = _of_the_tree()

    findings = _findings(_first(_VERSION, _read(copy)), backend, image, package)

    assert len(findings) == 1
    assert findings[0].startswith(PHP_VERSION)
    assert "'0.1.1'" in findings[0]


def test_an_image_tag_of_its_own_is_reported_as_the_image_tag() -> None:
    findings = _findings("1.2.3", "1.2.3", "1.2.4", "1.2.3")

    assert len(findings) == 1
    assert findings[0].startswith(IMAGE_TAG)


def test_a_package_version_of_its_own_is_reported_as_that() -> None:
    findings = _findings("1.2.3", "1.2.3", "1.2.3", "1.3.0")

    assert len(findings) == 1
    assert findings[0].startswith(PYPROJECT_VERSION)


def test_a_value_that_is_not_a_version_is_reported_as_that_and_only_that() -> None:
    findings = _findings("1.2", "1.2.3", "1.2.3", "1.2.3")

    assert len(findings) == 1
    assert findings[0].startswith(PHP_VERSION)
    assert "not a version" in findings[0]


def test_a_leading_zero_is_not_a_version_either() -> None:
    findings = _findings("01.2.3", "01.2.3", "01.2.3", "01.2.3")

    assert len(findings) == 4
    assert all("not a version" in finding for finding in findings)


def test_a_value_that_could_not_be_read_is_a_finding_and_never_a_match() -> None:
    assert _findings(None, "1.2.3", "1.2.3", "1.2.3") == [f"{PHP_VERSION} could not be read at all"]
    assert _pyproject_version("") is None
    assert _pyproject_version('[project]\nname = "x"\n') is None


# -- the server window: two declarations and the matrix that runs them ---------

PHP_WINDOW = "the server window in php/appinfo/info.xml"
BACKEND_WINDOW = "the server window in backend/appinfo/info.xml"
MATRIX = "the matrix of .github/workflows/deploy-harp.yml"

_WINDOW = re.compile(r'<nextcloud\s+min-version="([^"]*)"\s+max-version="([^"]*)"\s*/>')

# Only the lines that open an item of the include list; a later
# "server-version: ${{ matrix.server-version }}" hands the value on and must
# not count as a second entry.
_MATRIX_ENTRY = re.compile(r"^[ \t]*-[ \t]+server-version:[ \t]*['\"]?stable(\d+)['\"]?[ \t]*$", re.MULTILINE)

_MAJOR = re.compile(r"0|[1-9][0-9]*")


def _window_of(source: str) -> tuple[str, str] | None:
    """The declared server window of one info.xml, or None when it has none."""
    found = _WINDOW.search(source)
    return None if found is None else (found.group(1).strip(), found.group(2).strip())


def _matrix_of(source: str) -> list[str]:
    """The server majors the deploy job really runs, in file order."""
    return [found.group(1) for found in _MATRIX_ENTRY.finditer(source)]


def _window_findings(php: tuple[str, str] | None, backend: tuple[str, str] | None, matrix: list[str]) -> list[str]:
    """Every disagreement between the two declarations and the matrix, cause before consequence."""
    if php is None or backend is None or not matrix:
        unreadable = [
            f"{side} could not be read at all"
            for side, value in ((PHP_WINDOW, php), (BACKEND_WINDOW, backend))
            if value is None
        ]
        return unreadable + ([] if matrix else [f"{MATRIX} carries no server version at all"])

    misshapen = [
        f"{side} is {window!r}, which is not a pair of server majors"
        for side, window in ((PHP_WINDOW, php), (BACKEND_WINDOW, backend))
        if any(_MAJOR.fullmatch(value) is None for value in window)
    ]
    if misshapen:
        return misshapen

    if php != backend:
        return [f"{PHP_WINDOW} is {php!r} and {BACKEND_WINDOW} is {backend!r}"]

    floor, ceiling = int(php[0]), int(php[1])
    if floor > ceiling:
        return [f"{BACKEND_WINDOW} is {php!r}, and a window whose floor is above its ceiling promises nothing"]

    running = sorted(set(matrix), key=int)
    outside = [
        f"{MATRIX} runs stable{major} while the window is {php!r}"
        for major in running
        if not floor <= int(major) <= ceiling
    ]
    unproven = [
        f"the window is {php!r} and {MATRIX} has no entry for stable{major}"
        for major in (str(value) for value in range(floor, ceiling + 1))
        if major not in running
    ]
    return outside + unproven


def _window_of_the_tree() -> tuple[tuple[str, str] | None, tuple[str, str] | None, list[str]]:
    return _window_of(_read(PHP_INFO)), _window_of(_read(BACKEND_INFO)), _matrix_of(_read(WORKFLOW))


# -- the real tree: window -----------------------------------------------------


def test_both_declarations_and_the_matrix_can_be_read() -> None:
    php, backend, matrix = _window_of_the_tree()

    assert php is not None
    assert backend is not None
    assert matrix != []


def test_the_window_stands_in_both_halves_and_the_matrix_runs_exactly_it() -> None:
    assert _window_findings(*_window_of_the_tree()) == []


# -- self tests: window --------------------------------------------------------


def test_a_window_that_agrees_with_its_matrix_produces_no_finding() -> None:
    assert _window_findings(("33", "35"), ("33", "35"), ["33", "34", "35"]) == []
    assert _window_findings(("34", "34"), ("34", "34"), ["34"]) == []


def test_two_different_windows_are_reported_with_both_sides_named() -> None:
    findings = _window_findings(("32", "35"), ("33", "35"), ["33", "34", "35"])

    assert len(findings) == 1
    assert "php/appinfo/info.xml" in findings[0]
    assert "backend/appinfo/info.xml" in findings[0]


def test_entries_outside_the_window_are_reported() -> None:
    assert len(_window_findings(("33", "35"), ("33", "35"), ["32", "33", "34", "35"])) == 1
    assert "stable36" in _window_findings(("33", "35"), ("33", "35"), ["33", "34", "35", "36"])[0]


def test_a_promised_version_that_nobody_runs_is_reported() -> None:
    findings = _window_findings(("33", "35"), ("33", "35"), ["33", "35"])

    assert len(findings) == 1
    assert "stable34" in findings[0]


def test_a_misshapen_or_backwards_window_is_reported_as_that_and_only_that() -> None:
    misshapen = _window_findings(("33.0", "35"), ("33.0", "35"), ["33", "34", "35"])
    backwards = _window_findings(("35", "33"), ("35", "33"), ["33", "34", "35"])

    assert len(misshapen) == 2
    assert all("not a pair of server majors" in finding for finding in misshapen)
    assert len(backwards) == 1
    assert "floor is above its ceiling" in backwards[0]


def test_an_unreadable_side_or_an_empty_matrix_is_a_finding() -> None:
    assert _window_findings(None, ("33", "35"), ["33", "34", "35"]) == [f"{PHP_WINDOW} could not be read at all"]
    assert _window_findings(("33", "35"), ("33", "35"), []) == [f"{MATRIX} carries no server version at all"]


def test_the_matrix_expression_reads_the_include_list_and_nothing_else() -> None:
    source = (
        "        include:\n"
        "          - server-version: stable33\n"
        "            php-version: '8.2'\n"
        "          - server-version: stable34\n"
        "          - server-version: stable35\n"
        "        with:\n"
        "          server-version: ${{ matrix.server-version }}\n"
    )

    assert _matrix_of(source) == ["33", "34", "35"]


def test_the_window_expression_reads_the_dependencies_element() -> None:
    source = '\t<dependencies>\n\t\t<php min-version="8.2"/>\n\t\t<nextcloud min-version="33" max-version="35"/>\n'

    assert _window_of(source) == ("33", "35")
    assert _window_of("<dependencies>\n</dependencies>\n") is None
