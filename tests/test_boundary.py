"""Only src/audio_video_search/nc.py may import nc_py_api or an HTTP client.

What the container can do in Nextcloud is then readable in one file (Findling's
Gate A in small). The scan uses the AST, so a string or a comment that names the
library is not a finding.
"""

import ast
from pathlib import Path

from tests.conftest import REPO_ROOT

PACKAGE = REPO_ROOT / "src" / "audio_video_search"
BOUNDARY = PACKAGE / "nc.py"
GUARDED = ("nc_py_api", "httpx", "niquests", "requests", "urllib3", "aiohttp")


def guarded_imports(source: str) -> list[str]:
    """The guarded modules one source file imports."""
    found = []
    for node in ast.walk(ast.parse(source)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        found += [name for name in names if name.split(".")[0] in GUARDED]
    return found


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
    assert guarded_imports(BOUNDARY.read_text(encoding="utf-8"))
    assert offenders(files) == []


def test_the_scan_sees_both_import_forms_and_ignores_strings() -> None:
    assert guarded_imports("import httpx\nfrom nc_py_api.ex_app import x\n") == ["httpx", "nc_py_api.ex_app"]
    assert guarded_imports("text = 'import nc_py_api'\n# import httpx\n") == []
