"""The measuring scripts of the research carry no local path (plan 03-02).

The thresholds of phase 3 (D-03-11, D-03-19) must stay measurable on any
machine, so no script under ``scripts/research`` may name a drive, a home
directory or a package cache of one laptop. ``local_paths(root)`` is a function
of a tree; the counter tests run it on a changed copy and prove that it fails.
ffmpeg comes from ``--ffmpeg``, ``AVS_FFMPEG`` or ``PATH``, in that order.
"""

import importlib.util
import os
import py_compile
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.conftest import REPO_ROOT

RESEARCH = REPO_ROOT / "scripts" / "research"
PHASE3 = RESEARCH / "phase3"
FETCH_CORPUS = PHASE3 / "fetch_corpus.py"

# A drive letter must not follow a letter, else every "https://" would count.
LOCAL_PATH = re.compile(r"(?i)((?<![a-z])[a-z]:[\\/]|/users/|appdata|winget)")


def local_paths(root: Path) -> list[str]:
    """Every line of a ``*.py`` under ``root`` that names a local path, as ``file:line``."""
    hits = []
    for path in sorted(root.rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if LOCAL_PATH.search(line):
                hits.append(f"{path.relative_to(root).as_posix()}:{number}")
    return hits


def load_fetch_corpus() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fetch_corpus_under_test", FETCH_CORPUS)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # no __pycache__ beside the scripts
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


def test_research_tree_has_no_local_path() -> None:
    assert sorted(PHASE3.glob("*.py")), "the scripts of phase 3 are missing"
    assert local_paths(RESEARCH) == []


def test_inserted_windows_path_is_found(tmp_path: Path) -> None:
    copy = tmp_path / "fetch_corpus.py"
    lines = FETCH_CORPUS.read_text(encoding="utf-8").splitlines()
    lines.insert(20, 'FF = "C:/tools/ffmpeg.exe"')
    copy.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # The copy keeps every https address of the original; only the inserted line counts.
    assert local_paths(tmp_path) == ["fetch_corpus.py:21"]


@pytest.mark.parametrize(
    "line",
    [
        'FF = r"D:\\ffmpeg\\bin\\ffmpeg.exe"',
        'ROOT = "/Users/someone/corpus"',
        'CACHE = "~/AppData/Local/x"',
        'FF = "Microsoft/WinGet/Packages/ffmpeg"',
    ],
)
def test_each_kind_of_local_path_is_found(tmp_path: Path, line: str) -> None:
    (tmp_path / "script.py").write_text(f'"""Doc."""\n{line}\n', encoding="utf-8")
    assert local_paths(tmp_path) == ["script.py:2"]


def test_url_is_no_local_path(tmp_path: Path) -> None:
    (tmp_path / "script.py").write_text('URL = "https://huggingface.co/datasets/google/fleurs"\n', encoding="utf-8")
    assert local_paths(tmp_path) == []


@pytest.mark.parametrize("script", sorted(PHASE3.glob("*.py")), ids=lambda p: p.name)
def test_script_compiles(script: Path, tmp_path: Path) -> None:
    py_compile.compile(str(script), cfile=str(tmp_path / "out.pyc"), doraise=True)


def test_ffmpeg_option_wins_over_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = load_fetch_corpus()
    missing = Path(sys.executable).with_name("no-such-ffmpeg")
    assert not missing.exists()
    monkeypatch.setenv("AVS_FFMPEG", str(missing))
    assert Path(fc.ffmpeg_binary(sys.executable)).samefile(sys.executable)


def test_ffmpeg_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    fc = load_fetch_corpus()
    monkeypatch.setenv("AVS_FFMPEG", sys.executable)
    assert Path(fc.ffmpeg_binary(None)).samefile(sys.executable)


def test_missing_ffmpeg_option_exits_2(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    fc = load_fetch_corpus()
    monkeypatch.setenv("AVS_FFMPEG", sys.executable)
    with pytest.raises(SystemExit) as stop:
        fc.ffmpeg_binary(str(Path(sys.executable).with_name("no-such-ffmpeg")))
    assert stop.value.code == 2
    assert "ffmpeg not found: pass --ffmpeg or set AVS_FFMPEG" in capsys.readouterr().err


def test_split_keeps_positional_arguments() -> None:
    fc = load_fetch_corpus()
    assert fc.split_ffmpeg(["--ffmpeg", "/opt/ff", "corpus"]) == ("/opt/ff", ["corpus"])
    assert fc.split_ffmpeg(["corpus", "--ffmpeg=/opt/ff"]) == ("/opt/ff", ["corpus"])
    assert fc.split_ffmpeg(["corpus"]) == (None, ["corpus"])


def test_script_without_ffmpeg_exits_2(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    env = {key: value for key, value in os.environ.items() if key != "AVS_FFMPEG"}
    env["PATH"] = str(empty)
    assert shutil.which("ffmpeg", path=str(empty)) is None
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-I", str(FETCH_CORPUS)],
        cwd=empty,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 2
    assert "ffmpeg not found" in done.stderr
    assert list(empty.iterdir()) == []
