"""What the lock installs where: the conditions of the owner approval of plan 05-02.

The Whisper runtime brought sixteen packages into uv.lock. Two of them were
approved under a condition (owner, 18 November 2026):

* ``httpx2-jsfetch`` is a lock entry only. httpx2 names it for Pyodide
  (``sys_platform == 'emscripten'``), so no Linux image and no Windows machine
  ever installs it. The approval ends the moment an edge to it loses that marker.
* ``tzdata`` gives zoneinfo its database on the Windows machine of the developer.
  It sits in the dev group behind ``sys_platform == 'win32'``; the image builds
  with ``--no-dev`` on Linux and reads /usr/share/zoneinfo.

The check walks the lock the way an installer does: from the project over every
dependency edge whose marker is true in one environment. A second test reads
the same fact out of the raw text of the lock, and a third looks at what is
installed where the tests run, so the walk is not its own only witness.
"""

import re
import tomllib
from importlib import metadata
from typing import Any

from packaging.markers import Marker

from tests.conftest import BACKEND_ROOT

LOCK_FILE = BACKEND_ROOT / "uv.lock"
JSFETCH = "httpx2-jsfetch"
TZDATA = "tzdata"
PYPI = "https://pypi.org/simple"
PYTHON = {
    "implementation_name": "cpython",
    "implementation_version": "3.13.0",
    "platform_python_implementation": "CPython",
    "python_version": "3.13",
    "python_full_version": "3.13.0",
    "platform_release": "",
    "platform_version": "",
}
LINUX_AMD64 = {**PYTHON, "sys_platform": "linux", "platform_machine": "x86_64", "os_name": "posix"} | {
    "platform_system": "Linux"
}
LINUX_ARM64 = {**LINUX_AMD64, "platform_machine": "aarch64"}
WINDOWS = {**PYTHON, "sys_platform": "win32", "platform_machine": "AMD64", "os_name": "nt"} | {
    "platform_system": "Windows"
}
EMSCRIPTEN = {**PYTHON, "sys_platform": "emscripten", "platform_machine": "wasm32", "os_name": "posix"} | {
    "platform_system": "Emscripten"
}
# The image architectures and the machine of the developer: where the app is ever installed.
REAL: dict[str, dict[str, str]] = {"linux amd64": LINUX_AMD64, "linux arm64": LINUX_ARM64, "windows": WINDOWS}
# Everything plan 05-02 added, at the version the owner approved.
APPROVED_VERSIONS: dict[str, str] = {
    "faster-whisper": "1.2.1",
    "ctranslate2": "4.8.5",
    "onnxruntime": "1.31.1",
    "av": "19.0.2",
    "huggingface-hub": "2.4.0",
    "tokenizers": "0.23.3",
    "httpx2": "2.16.0",
    "httpcore2": "2.16.0",
    "hf-xet": "1.8.0",
    "truststore": "0.10.5",
    "tqdm": "4.70.1",
    "fsspec": "2026.9.0",
    "flatbuffers": "25.12.19",
    "protobuf": "7.36.2",
    JSFETCH: "1.0",
    TZDATA: "2026.6",
}
NOT_IN_THE_IMAGE = frozenset({JSFETCH, TZDATA})


def lock_packages() -> list[dict[str, Any]]:
    with LOCK_FILE.open("rb") as handle:
        return tomllib.load(handle)["package"]


def holds(edge: dict[str, Any], environment: dict[str, str]) -> bool:
    """Whether an installer in this environment follows a dependency edge of the lock."""
    marker = edge.get("marker")
    return marker is None or Marker(marker).evaluate(environment)


def edges_of(package: dict[str, Any], extras: tuple[str, ...], dev: bool) -> list[dict[str, Any]]:
    edges = list(package.get("dependencies", []))
    for extra in extras:
        edges += package.get("optional-dependencies", {}).get(extra, [])
    if dev:
        for group in package.get("dev-dependencies", {}).values():
            edges += group
    return edges


def installed(packages: list[dict[str, Any]], environment: dict[str, str], *, dev: bool) -> set[str]:
    """The packages an install of the project brings into one environment."""
    by_name = {package["name"]: package for package in packages}
    assert len(by_name) == len(packages), "one package twice in the lock"
    roots = [package["name"] for package in packages if "registry" not in package.get("source", {})]
    assert len(roots) == 1, roots
    seen: set[tuple[str, tuple[str, ...]]] = set()
    todo: list[tuple[str, tuple[str, ...]]] = [(roots[0], ())]
    while todo:
        name, extras = todo.pop()
        if (name, extras) in seen:
            continue
        seen.add((name, extras))
        # Only the project carries a dev group that an install of the project follows.
        for edge in edges_of(by_name[name], extras, dev and name == roots[0]):
            if holds(edge, environment):
                todo.append((edge["name"], tuple(edge.get("extra", []))))
    return {name for name, _ in seen} - {roots[0]}


def every_edge_to(packages: list[dict[str, Any]], target: str) -> list[tuple[str, dict[str, Any]]]:
    """Each edge of the lock that names a package, with the package it starts at."""
    found = []
    for package in packages:
        groups = [package.get("dependencies", [])]
        groups += list(package.get("optional-dependencies", {}).values())
        groups += list(package.get("dev-dependencies", {}).values())
        found += [(package["name"], edge) for group in groups for edge in group if edge["name"] == target]
    return found


def jsfetch_findings(packages: list[dict[str, Any]]) -> list[str]:
    """Why httpx2-jsfetch is more than a lock entry, if it is."""
    if all(package["name"] != JSFETCH for package in packages):
        return []
    findings: list[str] = []
    edges = every_edge_to(packages, JSFETCH)
    if not edges:
        findings.append(f"{JSFETCH} is locked but nothing names it")
    for start, edge in edges:
        if "marker" not in edge:
            findings.append(f"{start} names {JSFETCH} without a marker")
            continue
        findings += [
            f"{start} names {JSFETCH} under {edge['marker']!r}, true on {label}"
            for label, environment in REAL.items()
            if holds(edge, environment)
        ]
        if not holds(edge, EMSCRIPTEN):
            findings.append(f"{start} names {JSFETCH} under {edge['marker']!r}, not the emscripten marker")
    for label, environment in REAL.items():
        for dev in (False, True):
            if JSFETCH in installed(packages, environment, dev=dev):
                findings.append(f"{JSFETCH} is installed on {label}{' with the dev group' if dev else ''}")
    return findings


def tzdata_findings(packages: list[dict[str, Any]]) -> list[str]:
    """Why tzdata is more than a dev package of the Windows machine, if it is."""
    findings = [
        f"{TZDATA} is installed without the dev group on {label}"
        for label, environment in {**REAL, "emscripten": EMSCRIPTEN}.items()
        if TZDATA in installed(packages, environment, dev=False)
    ]
    findings += [
        f"{TZDATA} is installed with the dev group on {label}"
        for label, environment in REAL.items()
        if label != "windows" and TZDATA in installed(packages, environment, dev=True)
    ]
    if TZDATA not in installed(packages, WINDOWS, dev=True):
        findings.append(f"{TZDATA} is missing on windows with the dev group")
    return findings


def with_edges(packages: list[dict[str, Any]], start: str, key: str, edges: list[dict[str, Any]]) -> list[dict]:
    """The lock with one more list of edges at one package (a changed copy, for the controls)."""
    changed = []
    for package in packages:
        if package["name"] == start:
            if key == "dev":
                groups = dict(package.get("dev-dependencies", {}))
                groups["dev"] = [*groups.get("dev", []), *edges]
                package = {**package, "dev-dependencies": groups}
            else:
                package = {**package, "dependencies": [*package.get("dependencies", []), *edges]}
        changed.append(package)
    return changed


def without_edges_to(packages: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    changed = []
    for package in packages:
        package = {**package, "dependencies": [e for e in package.get("dependencies", []) if e["name"] != target]}
        if "dev-dependencies" in package:
            groups = {
                group: [e for e in edges if e["name"] != target] for group, edges in package["dev-dependencies"].items()
            }
            package = {**package, "dev-dependencies": groups}
        changed.append(package)
    return changed


# -- the sixteen packages ------------------------------------------------------


def test_every_package_of_plan_05_02_is_locked_at_the_approved_version_from_pypi() -> None:
    by_name = {package["name"]: package for package in lock_packages()}

    for name, version in APPROVED_VERSIONS.items():
        assert name in by_name, name
        assert by_name[name]["version"] == version, name
        assert by_name[name]["source"] == {"registry": PYPI}, name


def test_the_image_gets_the_whisper_runtime_on_both_architectures() -> None:
    packages = lock_packages()

    for environment in (LINUX_AMD64, LINUX_ARM64):
        image = installed(packages, environment, dev=False)
        assert APPROVED_VERSIONS.keys() - NOT_IN_THE_IMAGE <= image
        assert image.isdisjoint(NOT_IN_THE_IMAGE)
        # The checkers of the dev group are the control that --no-dev is what keeps a group out.
        assert "pytest" not in image
        assert "pytest" in installed(packages, environment, dev=True)


# -- httpx2-jsfetch: a lock entry only -----------------------------------------


def test_httpx2_jsfetch_is_reached_on_emscripten_only() -> None:
    packages = lock_packages()

    assert jsfetch_findings(packages) == []
    # Positive control: the walk does reach it where the marker is true.
    assert [start for start, _ in every_edge_to(packages, JSFETCH)] == ["httpx2"]
    assert JSFETCH in installed(packages, EMSCRIPTEN, dev=False)


def test_the_raw_lock_text_says_the_same() -> None:
    # No TOML reader and no marker library here: the lines as uv wrote them.
    text = LOCK_FILE.read_text(encoding="utf-8")
    mentions = [line.strip() for line in text.splitlines() if JSFETCH in line and "files.pythonhosted.org" not in line]

    assert mentions == [
        f'{{ name = "{JSFETCH}", marker = "sys_platform == \'emscripten\'" }},',
        f'name = "{JSFETCH}"',
    ]
    block = text.split(f'name = "{JSFETCH}"\n', 1)[1].split("[[package]]", 1)[0]
    assert "dependencies" not in block


def test_httpx2_jsfetch_is_not_installed_where_the_tests_run() -> None:
    # Windows on the machine of the developer, Linux in CI: neither is emscripten.
    names = {re.sub(r"[-_.]+", "-", (dist.metadata["Name"] or "").lower()) for dist in metadata.distributions()}

    assert "httpx2" in names  # the control: the listing does see what huggingface-hub brings
    assert JSFETCH not in names


def test_an_edge_without_the_emscripten_marker_is_reported() -> None:
    packages = lock_packages()

    bare = with_edges(packages, "huggingface-hub", "dependencies", [{"name": JSFETCH}])
    assert f"huggingface-hub names {JSFETCH} without a marker" in jsfetch_findings(bare)
    assert f"{JSFETCH} is installed on linux amd64" in jsfetch_findings(bare)
    assert f"{JSFETCH} is installed on windows" in jsfetch_findings(bare)

    widened = with_edges(
        without_edges_to(packages, JSFETCH),
        "httpx2",
        "dependencies",
        [{"name": JSFETCH, "marker": "sys_platform == 'emscripten' or sys_platform == 'linux'"}],
    )
    findings = jsfetch_findings(widened)
    assert any("true on linux amd64" in finding for finding in findings)
    assert any("true on linux arm64" in finding for finding in findings)
    assert f"{JSFETCH} is installed on linux arm64" in findings
    assert not any("windows" in finding for finding in findings)

    other = with_edges(
        without_edges_to(packages, JSFETCH),
        "httpx2",
        "dependencies",
        [{"name": JSFETCH, "marker": "sys_platform != 'win32'"}],
    )
    assert f"{JSFETCH} is installed on linux amd64" in jsfetch_findings(other)

    never = with_edges(
        without_edges_to(packages, JSFETCH),
        "httpx2",
        "dependencies",
        [{"name": JSFETCH, "marker": "sys_platform == 'cygwin'"}],
    )
    assert jsfetch_findings(never) == [
        f"httpx2 names {JSFETCH} under \"sys_platform == 'cygwin'\", not the emscripten marker"
    ]


def test_a_direct_or_a_dev_dependency_on_httpx2_jsfetch_is_reported() -> None:
    packages = lock_packages()
    project = "audio-video-search-backend"

    direct = jsfetch_findings(with_edges(packages, project, "dependencies", [{"name": JSFETCH}]))
    assert f"{project} names {JSFETCH} without a marker" in direct
    assert f"{JSFETCH} is installed on linux amd64" in direct

    dev = jsfetch_findings(with_edges(packages, project, "dev", [{"name": JSFETCH, "marker": "os_name == 'nt'"}]))
    assert f"{JSFETCH} is installed on windows with the dev group" in dev
    assert f"{JSFETCH} is installed on windows" not in dev
    assert not any("linux" in finding for finding in dev)


def test_a_locked_httpx2_jsfetch_nobody_names_is_reported_and_an_absent_one_is_fine() -> None:
    packages = lock_packages()

    assert jsfetch_findings(without_edges_to(packages, JSFETCH)) == [f"{JSFETCH} is locked but nothing names it"]
    gone = [package for package in without_edges_to(packages, JSFETCH) if package["name"] != JSFETCH]
    assert jsfetch_findings(gone) == []


# -- tzdata: the dev group of the Windows machine only -------------------------


def test_tzdata_is_a_dev_package_of_windows_only() -> None:
    packages = lock_packages()

    assert tzdata_findings(packages) == []
    assert every_edge_to(packages, TZDATA) == [
        ("audio-video-search-backend", {"name": TZDATA, "marker": "sys_platform == 'win32'"})
    ]


def test_tzdata_in_the_image_or_without_its_marker_is_reported() -> None:
    packages = lock_packages()

    runtime = with_edges(packages, "fastapi", "dependencies", [{"name": TZDATA}])
    assert f"{TZDATA} is installed without the dev group on linux amd64" in tzdata_findings(runtime)

    unmarked = with_edges(without_edges_to(packages, TZDATA), "audio-video-search-backend", "dev", [{"name": TZDATA}])
    assert tzdata_findings(unmarked) == [
        f"{TZDATA} is installed with the dev group on linux amd64",
        f"{TZDATA} is installed with the dev group on linux arm64",
    ]

    assert tzdata_findings(without_edges_to(packages, TZDATA)) == [f"{TZDATA} is missing on windows with the dev group"]


def test_the_environments_are_told_apart() -> None:
    edge = {"name": "x", "marker": "sys_platform == 'emscripten'"}

    assert [holds(edge, environment) for environment in (*REAL.values(), EMSCRIPTEN)] == [False, False, False, True]
    assert holds({"name": "x"}, LINUX_AMD64)
    machine = {"name": "x", "marker": "platform_machine == 'aarch64' or platform_machine == 'x86_64'"}
    assert [holds(machine, environment) for environment in REAL.values()] == [True, True, False]
