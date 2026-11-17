"""The engine packages are the ones the owner approved, byte for byte (plan 03-10, T-03-SC).

Plan 03-01 approved exactly sherpa-onnx 2.0.1, sherpa-onnx-core 2.0.1, numpy 2.5.4
and py3langid 0.4.0, with the sha256 of each wheel for amd64 and arm64 read from
PyPI. This test reads uv.lock as TOML and holds three things: each package is
pinned exactly in pyproject.toml and locked at that version from PyPI, the image
architectures both have a wheel (CPython 3.13 or a pure wheel, manylinux, x86_64
and aarch64), and every approved sha256 is the one in the lock. A lock fragment
without an aarch64 wheel and one with a changed hash are fed to the same checker
to prove it can fail.
"""

import tomllib
from typing import Any

from tests.conftest import BACKEND_ROOT

# Wheel file name and sha256 as approved in 03-01-SUMMARY.md (owner: "Alle freigegeben").
APPROVED: dict[str, tuple[str, dict[str, str]]] = {
    "sherpa-onnx": (
        "2.0.1",
        {
            "sherpa_onnx-2.0.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl": (
                "a52606059a84495374bbd752c8de2b36d3f018cd715eddac559686b4e6868789"
            ),
            "sherpa_onnx-2.0.1-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl": (
                "dae9c8972e2dfe1fcaccdc48f7465f0db2e4220f1f7b299b4c0970a5f46c66e2"
            ),
        },
    ),
    "sherpa-onnx-core": (
        "2.0.1",
        {
            "sherpa_onnx_core-2.0.1-py3-none-manylinux2014_x86_64.whl": (
                "f4ee0ab91c4ae596e0e49d7de32522a946295e038a652f1c1884d89014ee4ec2"
            ),
            "sherpa_onnx_core-2.0.1-py3-none-manylinux2014_aarch64.whl": (
                "4a855a5c89c89885111e4e9c570e5da1aed63373c031b757d8046792d95fe8fe"
            ),
        },
    ),
    "numpy": (
        "2.5.4",
        {
            "numpy-2.5.4-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl": (
                "6ffa07666f8da0eef81d149934a626d0d95fbd6838432a33e66245423a9062c0"
            ),
            "numpy-2.5.4-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl": (
                "1c2e71b04c6cad90026e544501bbe0ab9290fa8a4d845e7e8c0d124fb429c988"
            ),
        },
    ),
    "py3langid": (
        "0.4.0",
        {"py3langid-0.4.0-py3-none-any.whl": "c25bd038147951ba3a89efe9ec12cc7d2116cb6f311ff8af84ade398a8bc0616"},
    ),
}
# py3langid ships one pure wheel; the three native packages need one wheel per image architecture.
PURE: frozenset[str] = frozenset({"py3langid"})
PYPI = "https://pypi.org/simple"


def _lock() -> dict[str, Any]:
    with (BACKEND_ROOT / "uv.lock").open("rb") as handle:
        return tomllib.load(handle)


def _wheel_name(wheel: dict[str, Any]) -> str:
    return str(wheel["url"]).rsplit("/", 1)[-1]


def _runs_on_cpython313(name: str) -> bool:
    tags = name.removesuffix(".whl").split("-")[-3:]
    python, abi = tags[0], tags[1]
    if abi == "none":
        return python.startswith("py3")
    return abi in {"cp313", "abi3"}


def check(packages: list[dict[str, Any]]) -> list[str]:
    """Every finding about the approved packages in a list of uv.lock package tables."""
    findings: list[str] = []
    by_name = {package["name"]: package for package in packages}
    for name, (version, approved) in APPROVED.items():
        package = by_name.get(name)
        if package is None:
            findings.append(f"{name}: not in the lock")
            continue
        if package.get("version") != version:
            findings.append(f"{name}: locked at {package.get('version')}, approved {version}")
        if package.get("source", {}).get("registry") != PYPI:
            findings.append(f"{name}: not from PyPI")
        wheels = {_wheel_name(wheel): str(wheel.get("hash", "")) for wheel in package.get("wheels", [])}
        for wheel_name, digest in approved.items():
            if wheel_name not in wheels:
                findings.append(f"{name}: approved wheel {wheel_name} missing")
            elif wheels[wheel_name] != f"sha256:{digest}":
                findings.append(f"{name}: {wheel_name} has {wheels[wheel_name]}, approved sha256:{digest}")
        usable = [wheel for wheel in wheels if _runs_on_cpython313(wheel)]
        if name in PURE:
            if not any(wheel.endswith("-py3-none-any.whl") for wheel in usable):
                findings.append(f"{name}: no py3-none-any wheel")
            continue
        for arch in ("x86_64", "aarch64"):
            if not any("manylinux" in wheel and wheel.endswith(f"{arch}.whl") for wheel in usable):
                findings.append(f"{name}: no CPython 3.13 manylinux {arch} wheel")
    return findings


def test_the_lock_holds_exactly_the_approved_wheels() -> None:
    assert check(_lock()["package"]) == []


def test_the_project_pins_the_four_packages_exactly() -> None:
    with (BACKEND_ROOT / "pyproject.toml").open("rb") as handle:
        dependencies = tomllib.load(handle)["project"]["dependencies"]
    for name, (version, _) in APPROVED.items():
        assert f"{name}=={version}" in dependencies


def test_a_lock_without_an_aarch64_wheel_is_reported() -> None:
    packages = _lock()["package"]
    stripped = []
    for package in packages:
        if package["name"] == "sherpa-onnx-core":
            package = {
                **package,
                "wheels": [wheel for wheel in package["wheels"] if not _wheel_name(wheel).endswith("aarch64.whl")],
            }
        stripped.append(package)

    findings = check(stripped)

    assert "sherpa-onnx-core: no CPython 3.13 manylinux aarch64 wheel" in findings
    assert any("sherpa-onnx-core: approved wheel" in finding and "aarch64" in finding for finding in findings)


def test_a_changed_hash_a_moved_version_and_a_missing_package_are_reported() -> None:
    packages = []
    for package in _lock()["package"]:
        if package["name"] == "numpy":
            wheels = [
                {**wheel, "hash": "sha256:" + "0" * 64} if "aarch64" in _wheel_name(wheel) else wheel
                for wheel in package["wheels"]
            ]
            package = {**package, "wheels": wheels}
        elif package["name"] == "sherpa-onnx":
            package = {**package, "version": "2.0.2"}
        elif package["name"] == "py3langid":
            continue
        packages.append(package)

    findings = check(packages)

    assert any(finding.startswith("numpy: numpy-2.5.4-cp313-cp313-manylinux_2_27_aarch64") for finding in findings)
    assert "sherpa-onnx: locked at 2.0.2, approved 2.0.1" in findings
    assert "py3langid: not in the lock" in findings


def test_a_pure_package_without_its_wheel_is_reported() -> None:
    packages = [
        {**package, "wheels": []} if package["name"] == "py3langid" else package for package in _lock()["package"]
    ]

    assert "py3langid: no py3-none-any wheel" in check(packages)


def test_the_wheel_tags_are_read_right() -> None:
    assert _runs_on_cpython313("numpy-2.5.4-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl")
    assert _runs_on_cpython313("sherpa_onnx_core-2.0.1-py3-none-manylinux2014_aarch64.whl")
    assert _runs_on_cpython313("tantivy-0.26.2-cp311-abi3-manylinux_2_28_aarch64.whl")
    assert not _runs_on_cpython313("numpy-2.5.4-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl")
    assert not _runs_on_cpython313("numpy-2.5.4-cp313-cp313t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl")
