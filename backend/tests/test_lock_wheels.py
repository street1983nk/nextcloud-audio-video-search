"""The engine packages are the ones the owner approved, byte for byte (plan 03-10, T-03-SC).

Plan 03-01 approved exactly sherpa-onnx 2.0.1, sherpa-onnx-core 2.0.1, numpy 2.5.4
and py3langid 0.4.0, with the sha256 of each wheel for amd64 and arm64 read from
PyPI. This test reads uv.lock as TOML and holds three things: each package is
pinned exactly in pyproject.toml and locked at that version from PyPI, the image
architectures both have a wheel (CPython 3.13 or a pure wheel, manylinux, x86_64
and aarch64), and every approved sha256 is the one in the lock. A lock fragment
without an aarch64 wheel and one with a changed hash are fed to the same checker
to prove it can fail.

Plan 05-02 added the Whisper runtime the same way (T-05-SC): faster-whisper 1.2.1,
ctranslate2 4.8.5 and onnxruntime 1.31.1 as exact pins, and the three packages
that only come with faster-whisper (av 19.0.2, huggingface-hub 2.4.0, tokenizers
0.23.3), which the lock alone holds. The sha256 are the ones of the PyPI JSON the
owner saw at the legitimacy checkpoint of that plan.
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
    # Approved in plan 05-02 (owner: "freigegeben"). Never 4.9.0 or 1.32.0 without a measurement.
    "faster-whisper": (
        "1.2.1",
        {"faster_whisper-1.2.1-py3-none-any.whl": "79a66ad50688c0b794dd501dc340a736992a6342f7f95e5811be60b5224a26a7"},
    ),
    "ctranslate2": (
        "4.8.5",
        {
            "ctranslate2-4.8.5-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl": (
                "b9efe6d3a4a3bda42ac579c461d073985dc9d2796773d13a95d7d26018363807"
            ),
            "ctranslate2-4.8.5-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl": (
                "61b7297633b4a26eb79c53830438de792c0721a45d121a2217b27c7f7af53743"
            ),
        },
    ),
    "onnxruntime": (
        "1.31.1",
        {
            "onnxruntime-1.31.1-cp313-cp313-manylinux_2_28_x86_64.whl": (
                "74a6a52994616c4d18b33db1e13c226333a70a6ba07480a5cab9c2a50dff1430"
            ),
            "onnxruntime-1.31.1-cp313-cp313-manylinux_2_28_aarch64.whl": (
                "dcaedc50333876f3829ab966b242147f0e548229e29c36fe44622ecf748c25ee"
            ),
        },
    ),
}
# What faster-whisper brings along and the project never names itself (plan 05-02):
# only the lock pins these, so the lock is where the version and the wheels are held.
TRANSITIVE: dict[str, tuple[str, dict[str, str]]] = {
    "av": (
        "19.0.2",
        {
            "av-19.0.2-cp312-abi3-manylinux_2_28_x86_64.whl": (
                "9c1da7aad0fa6c13b4a5c1e7985be0d13f8526a96284573acaf3d55ead6d3fe8"
            ),
            "av-19.0.2-cp312-abi3-manylinux_2_28_aarch64.whl": (
                "04c8e412642c652cb2b1997a9cb2114546ee7d894600c631f4be8ceb26a0d0d2"
            ),
        },
    ),
    "huggingface-hub": (
        "2.4.0",
        {"huggingface_hub-2.4.0-py3-none-any.whl": "42ecfd93ede47bdd333daebbf66a32d7bfe2e18752754fe4d2d4f98a0179d801"},
    ),
    "tokenizers": (
        "0.23.3",
        {
            "tokenizers-0.23.3-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl": (
                "376851d22bcf9d650a5c3090bb83e6cf9e895fbf0595369fa4cd43c1f69b5f87"
            ),
            "tokenizers-0.23.3-cp310-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64.whl": (
                "ec82e80e65a862275b97c3d90b7a523df8d9519ee48aeb4e9625b2cc909274e0"
            ),
        },
    ),
}
HELD: dict[str, tuple[str, dict[str, str]]] = {**APPROVED, **TRANSITIVE}
# These ship one pure wheel; the native packages need one wheel per image architecture.
PURE: frozenset[str] = frozenset({"py3langid", "faster-whisper", "huggingface-hub"})
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
    """Every finding about the held packages in a list of uv.lock package tables."""
    findings: list[str] = []
    by_name = {package["name"]: package for package in packages}
    for name, (version, approved) in HELD.items():
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


def test_the_project_pins_the_approved_packages_exactly() -> None:
    with (BACKEND_ROOT / "pyproject.toml").open("rb") as handle:
        dependencies = tomllib.load(handle)["project"]["dependencies"]
    for name, (version, _) in APPROVED.items():
        assert f"{name}=={version}" in dependencies
    # The transitive three stay unnamed: a pin of the project would make them a choice of the app.
    named = {entry.split("==")[0].split("[")[0].strip() for entry in dependencies}
    assert named.isdisjoint(TRANSITIVE)


def test_the_whisper_runtime_is_held_like_the_first_engine() -> None:
    assert {"faster-whisper", "ctranslate2", "onnxruntime"} <= APPROVED.keys()
    assert TRANSITIVE.keys() == {"av", "huggingface-hub", "tokenizers"}
    # Two wheels for each native package, one for each pure one.
    for name, (_, wheels) in HELD.items():
        assert len(wheels) == (1 if name in PURE else 2), name


def test_a_newer_ctranslate2_or_onnxruntime_and_a_changed_transitive_wheel_are_reported() -> None:
    packages = []
    for package in _lock()["package"]:
        if package["name"] == "ctranslate2":
            package = {**package, "version": "4.9.0"}
        elif package["name"] == "onnxruntime":
            package = {**package, "version": "1.32.0"}
        elif package["name"] == "av":
            wheels = [
                {**wheel, "hash": "sha256:" + "f" * 64} if "x86_64" in _wheel_name(wheel) else wheel
                for wheel in package["wheels"]
            ]
            package = {**package, "wheels": wheels}
        elif package["name"] == "huggingface-hub":
            package = {**package, "source": {"registry": "https://example.invalid/simple"}}
        elif package["name"] == "tokenizers":
            wheels = [wheel for wheel in package["wheels"] if "aarch64" not in _wheel_name(wheel)]
            package = {**package, "wheels": wheels}
        packages.append(package)

    findings = check(packages)

    assert "ctranslate2: locked at 4.9.0, approved 4.8.5" in findings
    assert "onnxruntime: locked at 1.32.0, approved 1.31.1" in findings
    assert any(finding.startswith("av: av-19.0.2-cp312-abi3-manylinux_2_28_x86_64.whl has") for finding in findings)
    assert "huggingface-hub: not from PyPI" in findings
    assert "tokenizers: no CPython 3.13 manylinux aarch64 wheel" in findings


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
    assert _runs_on_cpython313("av-19.0.2-cp312-abi3-manylinux_2_28_aarch64.whl")
    assert _runs_on_cpython313("faster_whisper-1.2.1-py3-none-any.whl")
