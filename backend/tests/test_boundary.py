"""Only src/audio_video_search_backend/nc.py may import nc_py_api or an HTTP client.

What the container can do in Nextcloud is then readable in one file (Findling's
Gate A in small). The scan uses the AST, so a string or a comment that names the
library is not a finding.

Plan 05-02 brought the Whisper runtime into the image and two more borders with
it. PyAV comes with faster-whisper and bundles GPL codecs (libx264, libx265), so
no module of the app imports ``av``: decoding stays with the LGPL ffmpeg binary
(T-05-05). And faster_whisper and ctranslate2 are engine code: only modules
under ``engine/`` may import them (T-05-07), which keeps the place where a model
is loaded as small as the place where Nextcloud is called.
"""

import ast
from pathlib import Path

from tests.conftest import BACKEND_ROOT

PACKAGE = BACKEND_ROOT / "src" / "audio_video_search_backend"
BOUNDARY = PACKAGE / "nc.py"
GUARDED = ("nc_py_api", "httpx", "niquests", "requests", "urllib3", "aiohttp")
ENGINE = PACKAGE / "engine"
# PyAV: imported by nobody. The Whisper engine: imported under engine/ only.
PYAV = ("av",)
WHISPER = ("faster_whisper", "ctranslate2")


def guarded_imports(source: str, guarded: tuple[str, ...] = GUARDED) -> list[str]:
    """The guarded modules one source file imports."""
    found = []
    for node in ast.walk(ast.parse(source)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        found += [name for name in names if name.split(".")[0] in guarded]
    return found


def pyav_offenders(sources: dict[Path, str]) -> list[str]:
    """Every import of PyAV in the app, whichever module it is in."""
    return [
        f"{path.relative_to(PACKAGE).as_posix()}: {name}"
        for path, source in sources.items()
        for name in guarded_imports(source, PYAV)
    ]


def whisper_offenders(sources: dict[Path, str]) -> list[str]:
    """Every import of the Whisper engine outside engine/."""
    return [
        f"{path.relative_to(PACKAGE).as_posix()}: {name}"
        for path, source in sources.items()
        if ENGINE not in path.parents
        for name in guarded_imports(source, WHISPER)
    ]


def _sources() -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in sorted(PACKAGE.rglob("*.py"))}


def offenders(files: list[Path]) -> list[str]:
    """Files outside the boundary that import a guarded module."""
    return [
        f"{path.name}: {name}"
        for path in files
        if path != BOUNDARY
        for name in guarded_imports(path.read_text(encoding="utf-8"))
    ]


def test_only_the_boundary_imports_nc_py_api() -> None:
    files = sorted(PACKAGE.rglob("*.py"))

    assert len(files) >= 5
    # Both guarded clients live in the boundary: nc_py_api for AppAPI, httpx
    # for the streamed read of the content gateway.
    assert {name.split(".")[0] for name in guarded_imports(BOUNDARY.read_text(encoding="utf-8"))} == {
        "nc_py_api",
        "httpx",
    }
    assert offenders(files) == []


def test_the_scan_sees_both_import_forms_and_ignores_strings() -> None:
    assert guarded_imports("import httpx\nfrom nc_py_api.ex_app import x\n") == ["httpx", "nc_py_api.ex_app"]
    assert guarded_imports("text = 'import nc_py_api'\n# import httpx\n") == []


def test_no_module_of_the_app_imports_pyav() -> None:
    sources = _sources()

    assert len(sources) >= 5
    assert pyav_offenders(sources) == []


def test_the_pyav_scan_sees_both_import_forms_and_ignores_strings_and_look_alikes() -> None:
    # Positive control: a source that does import av is seen, in every form.
    assert guarded_imports("import av\n", PYAV) == ["av"]
    assert guarded_imports("import av.audio as audio\nfrom av import open\nfrom av.container import x\n", PYAV) == [
        "av.audio",
        "av",
        "av.container",
    ]
    assert guarded_imports("def decode():\n    import av\n    return av\n", PYAV) == ["av"]
    # A string, a comment, a relative import and a module that only starts with the letters are none.
    assert guarded_imports("text = 'import av'\n# import av\n", PYAV) == []
    assert guarded_imports("from . import av\nfrom .av import x\nimport avs\nimport available\n", PYAV) == []
    assert pyav_offenders({PACKAGE / "media" / "decode.py": "import av\n"}) == ["media/decode.py: av"]
    assert pyav_offenders({ENGINE / "whisper.py": "from av import open\n"}) == ["engine/whisper.py: av"]


def test_the_whisper_engine_is_imported_under_engine_only() -> None:
    sources = _sources()

    assert ENGINE.is_dir()
    assert any(ENGINE in path.parents for path in sources)
    assert whisper_offenders(sources) == []


def test_the_whisper_border_fires_outside_engine_and_lets_engine_through() -> None:
    whisper = "from faster_whisper import WhisperModel\nimport ctranslate2\n"

    assert whisper_offenders({ENGINE / "whisper.py": whisper}) == []
    assert whisper_offenders({ENGINE / "sub" / "deep.py": whisper}) == []
    assert whisper_offenders({PACKAGE / "worker" / "runner.py": whisper}) == [
        "worker/runner.py: faster_whisper",
        "worker/runner.py: ctranslate2",
    ]
    # A sibling whose name only starts like the engine folder is outside of it.
    assert whisper_offenders({PACKAGE / "engine_tools.py": "import ctranslate2.converters\n"}) == [
        "engine_tools.py: ctranslate2.converters"
    ]
    assert whisper_offenders({PACKAGE / "main.py": "text = 'import faster_whisper'\n"}) == []
