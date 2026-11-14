"""The gate of the VAD and the catch rule: no way to turn them off or to move them (plan 03-06).

Owner rule: the VAD is always on and has no way to be turned off (TRANS-02; "VAD
abschaltbar" is out of scope). The same holds for the catch rule of TRANS-03:
its thresholds are measured constants with a test (tests/test_engine_constants.py),
never a setting, an environment value or a route. The pattern is the one of the
read proof (D-02-10, tests/test_read_proof_gate.py): ``scan(root)`` is a function
of a tree, the real tree gives no finding, and the counter tests below change a
copy and prove that each rule can fail.

1  ``engine/**/*.py`` reads no environment and no setting: no ``getenv``, no
   ``environ.get``, no ``environ[``, no ``import settings``, no ``settings.``,
   no ``nc_app``, no import of the modules ``settings``, ``config`` or ``nc``
   (they read the environment and the app config). The one exception is the
   later ``engine/child.py``: it sets the thread variables of the engine only by
   writing, with ``os.environ.update(<CONSTANT>)``. Every other use of
   ``environ`` in ``engine/`` is a finding, so every read is one.
2  In the whole package, the words ``vad``, ``catch``, ``threshold``, ``conf`` and
   ``confidence`` never stand in a line with ``SettingsField``, ``@router.``,
   ``environ`` or ``getenv``; no ``SettingsField`` call and no route (decorator
   and handler name) contains them, and no text or name of ``settings.py`` does.
3  No switch word joined to the VAD or the catch rule
   (``(?i)(skip|disabl|bypass|unsafe)[a-z]*[_-]?(vad|catch)``) anywhere in the package or
   in ``php/lib``.
"""

import ast
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

PACKAGE = Path("backend/src/audio_video_search_backend")
ENGINE = PACKAGE / "engine"
SETTINGS = PACKAGE / "settings.py"
PHP_LIB = Path("php/lib")
PRUNED = frozenset({"__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", "vendor"})

# Rule 1.
ENGINE_FORBIDDEN = ("getenv", "environ.get", "environ[", "import settings", "settings.", "nc_app")
ENGINE_FORBIDDEN_MODULES = re.compile(
    r"audio_video_search_backend(?:\.(?:settings|config|nc)\b|\s+import\s+.*\b(?:settings|config|nc)\b)"
)
ENVIRON = re.compile(r"\benviron\b")
ENVIRON_WRITE = re.compile(r"\bos\.environ\.update\(\s*[A-Z][A-Z0-9_]*\s*\)")

# Rule 2. Letters only bound a word, so ``vad_threshold`` and ``AVS_VAD`` match, ``configured`` does not.
SUBJECT = re.compile(r"(?i)(?<![a-z])(?:vad|catch|threshold|conf|confidence)(?![a-z])")
CONFIGURABLE = re.compile(r"SettingsField|@router\.|\benviron\b|getenv")

# Rule 3.
# The pattern of the plan, ``(skip|disabl|bypass|unsafe)_?(vad|catch)``, missed ``disable_catch``
# and ``disabled_vad``; the letters after the stem are allowed here.
SWITCH = re.compile(r"(?i)(skip|disabl|bypass|unsafe)[a-z]*[_-]?(vad|catch)")


def _walk(top: Path, suffix: str) -> Iterator[Path]:
    if not top.is_dir():
        return
    for entry in sorted(top.iterdir()):
        if entry.name in PRUNED:
            continue
        if entry.is_dir():
            yield from _walk(entry, suffix)
        elif entry.suffix == suffix:
            yield entry


def _tail(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def rule_1(source: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for number, line in enumerate(source.splitlines(), start=1):
        findings += [(number, f"engine reads {pattern!r}") for pattern in ENGINE_FORBIDDEN if pattern in line]
        if ENGINE_FORBIDDEN_MODULES.search(line):
            findings.append((number, "engine imports settings, config or nc"))
        allowed = {match.start() + len("os.") for match in ENVIRON_WRITE.finditer(line)}
        findings += [
            (number, "engine uses the environment other than os.environ.update(<CONSTANT>)")
            for match in ENVIRON.finditer(line)
            if match.start() not in allowed
        ]
    return findings


def rule_2_lines(source: str) -> list[tuple[int, str]]:
    return [
        (number, "a VAD or catch word beside a setting, a route or the environment")
        for number, line in enumerate(source.splitlines(), start=1)
        if SUBJECT.search(line) and CONFIGURABLE.search(line)
    ]


def rule_2_tree(source: str, is_settings: bool) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _tail(node.func) == "SettingsField":
            segment = ast.get_source_segment(source, node) or ""
            if SUBJECT.search(segment):
                findings.append((node.lineno, "a SettingsField names the VAD or the catch rule"))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for decorator in node.decorator_list:
                segment = ast.get_source_segment(source, decorator) or ""
                if segment.startswith("router.") and (SUBJECT.search(segment) or SUBJECT.search(node.name)):
                    findings.append((decorator.lineno, "a route names the VAD or the catch rule"))
        if is_settings:
            texts: list[str] = []
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                texts = [node.value]
            elif isinstance(node, ast.Name):
                texts = [node.id]
            elif isinstance(node, ast.Attribute):
                texts = [node.attr]
            if any(SUBJECT.search(text) for text in texts):
                findings.append((getattr(node, "lineno", 0), "settings.py names the VAD or the catch rule"))
    return findings


def rule_3(source: str) -> list[tuple[int, str]]:
    return [
        (number, f"a switch of the VAD or the catch rule: {match.group(0)}")
        for number, line in enumerate(source.splitlines(), start=1)
        for match in SWITCH.finditer(line)
    ]


def scan(root: Path) -> list[str]:
    """One finding per file and line, with every rule that fired on it."""
    found: dict[tuple[str, int], set[str]] = {}

    def add(name: str, hits: list[tuple[int, str]]) -> None:
        for number, reason in hits:
            found.setdefault((name, number), set()).add(reason)

    for path in _walk(root / PACKAGE, ".py"):
        name = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        if path.is_relative_to(root / ENGINE):
            add(name, rule_1(source))
        add(name, rule_2_lines(source))
        try:
            add(name, rule_2_tree(source, is_settings=path == root / SETTINGS))
        except SyntaxError:
            add(name, [(0, "the source does not parse, so the gate cannot read it")])
        add(name, rule_3(source))
    for path in _walk(root / PHP_LIB, ".php"):
        add(path.relative_to(root).as_posix(), rule_3(path.read_text(encoding="utf-8")))
    return [f"{name}:{number}: {'; '.join(sorted(reasons))}" for (name, number), reasons in sorted(found.items())]


def test_the_product_has_no_way_to_turn_off_the_vad_or_the_catch_rule() -> None:
    assert scan(REPO_ROOT) == []


def test_the_scan_reads_the_files_it_is_about() -> None:
    """Without the files the clean result above would say nothing."""
    names = [path.relative_to(REPO_ROOT).as_posix() for path in _walk(REPO_ROOT / PACKAGE, ".py")]
    assert f"{ENGINE.as_posix()}/constants.py" in names
    assert f"{ENGINE.as_posix()}/catch.py" in names
    assert SETTINGS.as_posix() in names
    assert any(name.startswith(f"{PACKAGE.as_posix()}/api/") for name in names)
    assert any(_walk(REPO_ROOT / PHP_LIB, ".php"))


# Counter tests on a changed copy.


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "copy"
    ignore = shutil.ignore_patterns(*PRUNED)
    shutil.copytree(REPO_ROOT / PACKAGE, root / PACKAGE, ignore=ignore)
    shutil.copytree(REPO_ROOT / PHP_LIB, root / PHP_LIB, ignore=ignore)
    return root


def _append(root: Path, relative: Path, text: str) -> None:
    path = root / relative
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(before + text, encoding="utf-8", newline="\n")


def test_the_copy_is_clean_before_it_is_changed(tree: Path) -> None:
    assert scan(tree) == []


def test_an_environment_read_of_a_threshold_in_the_engine_is_one_finding(tree: Path) -> None:
    _append(tree, ENGINE / "constants.py", 'import os\nTHRESHOLD = float(os.getenv("AVS_VAD"))\n')
    findings = scan(tree)
    assert len(findings) == 1, findings
    assert findings[0].startswith(f"{ENGINE.as_posix()}/constants.py:")


def test_a_settings_field_for_the_vad_threshold_is_one_finding(tree: Path) -> None:
    _append(
        tree,
        SETTINGS,
        'VAD_FIELD = SettingsField(id="vad_threshold", title="VAD", type=SettingsFieldType.NUMBER, default=0.5)\n',
    )
    findings = scan(tree)
    assert len(findings) == 1, findings
    assert findings[0].startswith(f"{SETTINGS.as_posix()}:")


def test_a_settings_field_over_several_lines_is_found(tree: Path) -> None:
    """The real form puts the id on its own line; the field is found anyway."""
    _append(
        tree,
        SETTINGS,
        '\nFIELD = SettingsField(\n    id=PROCESSING_ENABLED,\n    title="Minimum confidence",\n'
        "    type=SettingsFieldType.NUMBER,\n)\n",
    )
    assert any(finding.startswith(f"{SETTINGS.as_posix()}:") for finding in scan(tree))


def test_writing_the_thread_variables_in_the_child_is_no_finding(tree: Path) -> None:
    _append(
        tree,
        ENGINE / "child.py",
        'import os\nTHREAD_ENV = {"OMP_NUM_THREADS": "2"}\nos.environ.update(THREAD_ENV)\n',
    )
    assert scan(tree) == []


def test_reading_the_environment_in_the_child_is_one_finding(tree: Path) -> None:
    _append(tree, ENGINE / "child.py", 'import os\nTHREADS = os.environ["X"]\n')
    findings = scan(tree)
    assert len(findings) == 1, findings
    assert findings[0].startswith(f"{ENGINE.as_posix()}/child.py:2:")


@pytest.mark.parametrize(
    "line",
    [
        "ENV = dict(os.environ)\n",
        "ENV = os.environ.copy()\n",
        'FLAG = "X" in os.environ\n',
        "os.environ.update(read_variables())\n",
        "from os import environ\n",
        "from audio_video_search_backend import settings\n",
        "from audio_video_search_backend.config import persistent_dir\n",
        "from audio_video_search_backend import nc\n",
        "VALUE = nc_app.appconfig_ex.get_value('x')\n",
    ],
)
def test_every_other_read_in_the_engine_is_a_finding(tree: Path, line: str) -> None:
    _append(tree, ENGINE / "child.py", "import os\n" + line)
    findings = scan(tree)
    assert len(findings) == 1, findings
    assert findings[0].startswith(f"{ENGINE.as_posix()}/child.py:2:")


def test_a_route_for_the_vad_is_a_finding(tree: Path) -> None:
    _append(
        tree,
        PACKAGE / "api" / "status.py",
        '\n\n@router.post("/vad/off")\nasync def turn_off() -> None:\n    return None\n',
    )
    assert any(finding.startswith(f"{PACKAGE.as_posix()}/api/status.py:") for finding in scan(tree))


def test_a_route_whose_handler_names_the_catch_rule_is_a_finding(tree: Path) -> None:
    _append(
        tree,
        PACKAGE / "api" / "status.py",
        '\n\n@router.post("/rule")\nasync def set_catch_threshold() -> None:\n    return None\n',
    )
    assert any(finding.startswith(f"{PACKAGE.as_posix()}/api/status.py:") for finding in scan(tree))


def test_an_environment_read_of_a_vad_value_outside_the_engine_is_a_finding(tree: Path) -> None:
    _append(tree, PACKAGE / "config.py", '\nVAD_LEVEL = os.environ.get("AVS_VAD_LEVEL", "0.5")\n')
    findings = scan(tree)
    assert len(findings) == 1, findings
    assert findings[0].startswith(f"{PACKAGE.as_posix()}/config.py:")


@pytest.mark.parametrize(
    ("relative", "line"),
    [
        (PACKAGE / "worker" / "capture.py", "SKIP_VAD = False\n"),
        (PACKAGE / "worker" / "capture.py", "def disable_catch() -> None: ...\n"),
        (PACKAGE / "worker" / "capture.py", "disabled_vad = True\n"),
        (PACKAGE / "worker" / "capture.py", 'MODE = "skip-vad"\n'),
        (PACKAGE / "main.py", "unsafeVAD = True\n"),
        (PHP_LIB / "AppInfo" / "Application.php", "// bypass_vad\n"),
    ],
)
def test_a_switch_word_is_a_finding(tree: Path, relative: Path, line: str) -> None:
    _append(tree, relative, line)
    findings = scan(tree)
    assert len(findings) == 1, findings
    assert findings[0].startswith(f"{relative.as_posix()}:")


@pytest.mark.parametrize(
    "line",
    [
        "configured = persistent_dir()\n",
        "level = os.environ.get(LOG_LEVEL_VARIABLE)\n",
        "skip_reason = 'too large'\n",
    ],
)
def test_plain_words_are_no_finding(line: str) -> None:
    """The rules bound their words by letters: these lines hold none of them."""
    source = "import os\n" + line
    assert rule_2_lines(source) == []
    assert rule_3(source) == []
