"""The Whisper runtime brings network code into the image; the app never calls it (T-05-07).

faster-whisper imports huggingface_hub, and with it come hf-xet, httpx2 and
httpcore2 (plan 05-02). They are import duty only: no audio, no text and no
request for a model may leave the server through them. Three rules hold that,
and none of them needs a model or a network.

1. No module under ``backend/src`` imports ``huggingface_hub``, ``hf_xet``,
   ``httpx2`` or ``httpcore2``, in any form the source can spell out.
2. faster_whisper is only ever given a local directory. ``download_model`` is
   used nowhere, and each ``WhisperModel(...)`` call names no model as a text
   literal, sets ``local_files_only=True`` and passes none of the arguments that
   only mean something for a download.
3. The image keeps ``HF_HUB_OFFLINE=1`` and ``HF_HUB_DISABLE_TELEMETRY=1`` as the
   final value of its last stage, and no script of the image touches them.

Rules 1 and 2 read the source as a syntax tree. What a syntax tree cannot see is
a module name that only exists at run time (``importlib.import_module(name)``);
the network capture of plan 05-21 is the answer to that, not this file.

The counter-checks do not read source: ``tests/hub_import_probe.py`` runs the
violating examples in a fresh interpreter and watches the import statements
execute and the stand-in WhisperModel being built. An example counts as a
violation because the interpreter did it, and the gate has to agree.
"""

import ast
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import BACKEND_ROOT
from tests.test_dockerfile import sets_the_hub_env

SOURCE_ROOT = BACKEND_ROOT / "src"
PACKAGE = "audio_video_search_backend"
PROBE = BACKEND_ROOT / "tests" / "hub_import_probe.py"
HUB_MODULES = ("huggingface_hub", "hf_xet", "httpx2", "httpcore2")
DOWNLOAD_ONLY_ARGUMENTS = ("download_root", "revision", "use_auth_token", "files")
HUB_ENV = {"HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
_NAMES_A_HUB_MODULE = re.compile(rf"^(?:{'|'.join(HUB_MODULES)})(?:[.:]|$)")


# -- rules 1 and 2: the syntax tree ----------------------------------------------


def _top(name: str) -> str:
    return name.split(".")[0]


def _is_text(node: ast.AST | None) -> bool:
    """A text literal: a plain string, an f-string, or literals joined with + or %."""
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str | bytes)
    if isinstance(node, ast.BinOp):
        return _is_text(node.left) or _is_text(node.right)
    return False


def _annotation_nodes(tree: ast.AST) -> set[int]:
    """The nodes inside type annotations, where a class name is no use of the class."""
    inside: set[int] = set()
    for node in ast.walk(tree):
        annotations: list[ast.AST | None] = []
        if isinstance(node, ast.arg | ast.AnnAssign):
            annotations.append(node.annotation)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            annotations.append(node.returns)
        for annotation in annotations:
            if annotation is not None:
                inside |= {id(child) for child in ast.walk(annotation)}
    return inside


def _whisper_call_findings(call: ast.Call) -> list[str]:
    findings: list[str] = []
    keywords = {keyword.arg: keyword.value for keyword in call.keywords}
    if None in keywords or any(isinstance(argument, ast.Starred) for argument in call.args):
        findings.append("WhisperModel is called with * or **, so its arguments cannot be read")
    model = call.args[0] if call.args else keywords.get("model_size_or_path")
    if model is None:
        findings.append("WhisperModel is called without a model directory")
    elif _is_text(model):
        findings.append("WhisperModel is given a text literal, not a local model directory")
    local = keywords.get("local_files_only")
    if not (isinstance(local, ast.Constant) and local.value is True):
        findings.append("WhisperModel is called without local_files_only=True")
    findings += [
        f"WhisperModel is called with {name}, which only a download needs"
        for name in DOWNLOAD_ONLY_ARGUMENTS
        if name in keywords
    ]
    if len(call.args) > 6:
        findings.append("WhisperModel is given download arguments by position")
    return findings


def source_findings(source: str) -> list[str]:
    """Every way one source file reaches for the hub or lets faster_whisper do it."""
    tree = ast.parse(source)
    findings: list[str] = []
    model_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            findings += [f"imports {alias.name}" for alias in node.names if _top(alias.name) in HUB_MODULES]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if _top(node.module) in HUB_MODULES:
                findings.append(f"imports {node.module}")
            if _top(node.module) == "faster_whisper":
                for alias in node.names:
                    if alias.name in ("download_model", "*"):
                        findings.append(f"imports {alias.name} from {node.module}")
                    if alias.name == "WhisperModel":
                        model_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _NAMES_A_HUB_MODULE.match(node.value):
                findings.append(f"names the module {node.value!r} in a text")
        elif isinstance(node, ast.Attribute) and node.attr == "download_model":
            findings.append("uses download_model")

    annotations = _annotation_nodes(tree)
    called: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        named = isinstance(function, ast.Name) and function.id in model_names
        dotted = isinstance(function, ast.Attribute) and function.attr == "WhisperModel"
        if named or dotted:
            called.add(id(function))
            findings += _whisper_call_findings(node)
    for node in ast.walk(tree):
        named = isinstance(node, ast.Name) and node.id in model_names and isinstance(node.ctx, ast.Load)
        dotted = isinstance(node, ast.Attribute) and node.attr == "WhisperModel"
        if (named or dotted) and id(node) not in called and id(node) not in annotations:
            findings.append("WhisperModel is passed on instead of being called, so its arguments cannot be read")
    return findings


def tree_findings(root: Path) -> list[str]:
    """The findings of every Python file under a directory, with its path."""
    return [
        f"{path.relative_to(root).as_posix()}: {finding}"
        for path in sorted(root.rglob("*.py"))
        for finding in source_findings(path.read_text(encoding="utf-8"))
    ]


def test_no_product_module_reaches_for_the_hub() -> None:
    files = sorted(SOURCE_ROOT.rglob("*.py"))

    # The whole of backend/src, not one package of it: a second package would be product code too.
    assert len(files) >= 50
    assert [path.name for path in SOURCE_ROOT.iterdir() if path.is_dir()] == [PACKAGE]
    assert tree_findings(SOURCE_ROOT) == []


@pytest.mark.parametrize(
    ("source", "finding"),
    [
        ("import huggingface_hub\n", "imports huggingface_hub"),
        ("import huggingface_hub.constants as constants\n", "imports huggingface_hub.constants"),
        ("from huggingface_hub import snapshot_download\n", "imports huggingface_hub"),
        ("from huggingface_hub.utils import logging\n", "imports huggingface_hub.utils"),
        ("def late():\n    import hf_xet\n    return hf_xet\n", "imports hf_xet"),
        ("try:\n    import httpx2\nexcept ImportError:\n    httpx2 = None\n", "imports httpx2"),
        ("from httpcore2 import ConnectionPool\n", "imports httpcore2"),
        ("import os, httpcore2\n", "imports httpcore2"),
        ("import importlib\nhub = importlib.import_module('huggingface_hub')\n", "names the module 'huggingface_hub'"),
        ("hub = __import__('httpx2.client')\n", "names the module 'httpx2.client'"),
        ("FACTORY = 'huggingface_hub:snapshot_download'\n", "names the module 'huggingface_hub:snapshot_download'"),
    ],
)
def test_each_way_to_spell_a_hub_import_is_reported(source: str, finding: str) -> None:
    assert any(found.startswith(finding) for found in source_findings(source)), source_findings(source)


FW = "from faster_whisper import WhisperModel\n"


@pytest.mark.parametrize(
    "source",
    [
        "import httpx\nimport httpcore\n",
        "text = 'import huggingface_hub'\n# import httpx2\n",
        '"""faster-whisper imports huggingface_hub, the app never does."""\n',
        "from . import httpx2\nfrom .hf_xet import x\n",
        "import httpx2_look_alike\nfrom huggingface_hubs import x\n",
        "note = 'the hub (huggingface_hub) stays offline'\n",
        FW + "model = WhisperModel(str(directory), device='cpu', compute_type='int8', local_files_only=True)\n",
        "import faster_whisper\nmodel = faster_whisper.WhisperModel(directory, local_files_only=True, cpu_threads=2)\n",
        "import faster_whisper\n\n\ndef load(directory) -> 'faster_whisper.WhisperModel':\n    return None\n",
        FW + "\n\ndef use(model: WhisperModel) -> WhisperModel:\n    return model\n",
        FW + "model: WhisperModel | None = None\n",
    ],
)
def test_what_is_allowed_is_not_reported(source: str) -> None:
    assert source_findings(source) == []


@pytest.mark.parametrize(
    ("source", "finding"),
    [
        (
            "from faster_whisper import WhisperModel\nmodel = WhisperModel('large-v3', local_files_only=True)\n",
            "WhisperModel is given a text literal, not a local model directory",
        ),
        (
            FW.replace("\n", " as Model\n")
            + "model = Model('Systran/faster-whisper-large-v3', local_files_only=True)\n",
            "WhisperModel is given a text literal, not a local model directory",
        ),
        (
            "import faster_whisper\nmodel = faster_whisper.WhisperModel(f'deepdml/{name}', local_files_only=True)\n",
            "WhisperModel is given a text literal, not a local model directory",
        ),
        (
            "import faster_whisper as fw\nmodel = fw.WhisperModel(model_size_or_path='org/' + name)\n",
            "WhisperModel is given a text literal, not a local model directory",
        ),
        (
            "from faster_whisper import WhisperModel\nmodel = WhisperModel(directory)\n",
            "WhisperModel is called without local_files_only=True",
        ),
        (
            "from faster_whisper import WhisperModel\nmodel = WhisperModel(directory, local_files_only=False)\n",
            "WhisperModel is called without local_files_only=True",
        ),
        (
            "from faster_whisper import WhisperModel\nmodel = WhisperModel(directory, local_files_only=offline)\n",
            "WhisperModel is called without local_files_only=True",
        ),
        (
            FW + "model = WhisperModel(directory, local_files_only=True, download_root='/tmp/x')\n",
            "WhisperModel is called with download_root, which only a download needs",
        ),
        (
            FW + "model = WhisperModel(directory, local_files_only=True, revision='main')\n",
            "WhisperModel is called with revision, which only a download needs",
        ),
        (
            "from faster_whisper import WhisperModel\nmodel = WhisperModel(directory, **options)\n",
            "WhisperModel is called with * or **, so its arguments cannot be read",
        ),
        (
            "from faster_whisper import WhisperModel\nmodel = WhisperModel(local_files_only=True)\n",
            "WhisperModel is called without a model directory",
        ),
        (
            FW + "import functools\nbuild = functools.partial(WhisperModel, 'large-v3')\n",
            "WhisperModel is passed on instead of being called, so its arguments cannot be read",
        ),
        (
            "from faster_whisper import download_model\npath = download_model('large-v3')\n",
            "imports download_model from faster_whisper",
        ),
        (
            "from faster_whisper.utils import download_model as fetch\n",
            "imports download_model from faster_whisper.utils",
        ),
        ("from faster_whisper import *\n", "imports * from faster_whisper"),
        ("import faster_whisper\npath = faster_whisper.download_model('large-v3')\n", "uses download_model"),
        ("import faster_whisper.utils as utils\npath = utils.download_model(name)\n", "uses download_model"),
    ],
)
def test_each_way_to_let_faster_whisper_download_is_reported(source: str, finding: str) -> None:
    assert finding in source_findings(source), source_findings(source)


# -- counter-check: the interpreter, not the syntax tree ---------------------------


def _probe(*arguments: str) -> dict[str, Any]:
    completed = subprocess.run(  # noqa: S603 - the interpreter of this test and a fixed file of the tests
        [sys.executable, str(PROBE), *arguments], capture_output=True, text=True, check=False, cwd=BACKEND_ROOT
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _package(root: Path, name: str, modules: dict[str, str]) -> Path:
    for relative, source in {"__init__.py": "", **modules}.items():
        target = root / name / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.parent != root / name:
            (target.parent / "__init__.py").touch()
        target.write_text(source, encoding="utf-8")
    return root


BAD_IMPORTS = {
    "top.py": "import huggingface_hub\n",
    "named.py": "from hf_xet import PyXetDownloadInfo\n",
    "inner/client.py": "import httpx2.client as client\n",
    "inner/pool.py": "from httpcore2 import ConnectionPool\n",
    "guarded.py": "try:\n    import httpx2\nexcept ImportError:\n    httpx2 = None\n",
    "dynamic.py": "import importlib\n\nhub = importlib.import_module('huggingface_hub')\n",
    "clean.py": "import json\n\nVALUE = json.dumps({})\n",
}


def test_the_interpreter_and_the_gate_agree_on_violating_imports(tmp_path: Path) -> None:
    root = _package(tmp_path, "avs_bad_example", BAD_IMPORTS)

    seen = _probe("imports", str(root), "avs_bad_example", *HUB_MODULES)
    at_run_time = {
        (record["importer"].removeprefix("avs_bad_example."), _top(record["module"])) for record in seen["records"]
    }

    # What the interpreter did: six modules tried, each one was refused, nothing was loaded.
    assert at_run_time == {
        ("top", "huggingface_hub"),
        ("named", "hf_xet"),
        ("inner.client", "httpx2"),
        ("inner.pool", "httpcore2"),
        ("guarded", "httpx2"),
        ("dynamic", "huggingface_hub"),
    }
    assert seen["loaded"] == []
    assert "avs_bad_example.clean" in seen["modules"]
    assert "avs_bad_example.clean" not in seen["failed"]

    # What the gate says about the same files: the same six, and not the clean one.
    in_the_tree = {finding.split(": ")[0].removesuffix(".py").replace("/", ".") for finding in tree_findings(root)}
    assert in_the_tree == {f"avs_bad_example.{module}" for module, _ in at_run_time}


def test_the_interpreter_sees_no_hub_import_in_the_product() -> None:
    seen = _probe("imports", str(SOURCE_ROOT), PACKAGE, *HUB_MODULES)

    # One module for each file of the product, each of them run.
    assert len(seen["modules"]) == len(list(SOURCE_ROOT.rglob("*.py"))) >= 50
    assert f"{PACKAGE}.engine.child" in seen["modules"]
    assert f"{PACKAGE}.api.search" in seen["modules"]
    assert seen["failed"] == {}
    assert seen["records"] == []


BAD_CALLS = {
    "by_name": "from faster_whisper import WhisperModel\n\n\ndef load(directory):\n"
    "    return WhisperModel('large-v3')\n",
    "by_repo": "import faster_whisper\n\n\ndef load(directory):\n"
    "    return faster_whisper.WhisperModel('Systran/faster-whisper-large-v3', download_root=directory)\n",
    "open_door": "from faster_whisper import WhisperModel\n\n\ndef load(directory):\n"
    "    return WhisperModel(directory + '-missing')\n",
    "fetch": "from faster_whisper import download_model\n\n\ndef load(directory):\n"
    "    return download_model('large-v3', output_dir=directory)\n",
    "fetch_dotted": "import faster_whisper.utils\n\n\ndef load(directory):\n"
    "    return faster_whisper.utils.download_model('large-v3')\n",
}
GOOD_CALL = (
    "from faster_whisper import WhisperModel\n\n\ndef load(directory):\n"
    "    return WhisperModel(directory, device='cpu', compute_type='int8', local_files_only=True)\n"
)


@pytest.mark.parametrize("name", sorted(BAD_CALLS))
def test_the_interpreter_and_the_gate_agree_on_violating_model_loads(name: str, tmp_path: Path) -> None:
    (tmp_path / f"{name}.py").write_text(BAD_CALLS[name], encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()

    seen = _probe("calls", str(tmp_path), name, "load", str(models))

    # What the interpreter did with the stand-in: a load that may use the network, or a download.
    assert seen["downloads"] or any(model["may_use_the_network"] for model in seen["built"]), seen
    # And the gate reports the same file.
    assert source_findings(BAD_CALLS[name]) != []


def test_the_interpreter_and_the_gate_agree_on_a_local_model_load(tmp_path: Path) -> None:
    (tmp_path / "local.py").write_text(GOOD_CALL, encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()

    seen = _probe("calls", str(tmp_path), "local", "load", str(models))

    assert seen["downloads"] == []
    assert [
        (model["is_directory"], model["asks_the_hub"], model["may_use_the_network"]) for model in seen["built"]
    ] == [(True, False, False)]
    assert source_findings(GOOD_CALL) == []


def test_the_stand_in_has_the_names_of_the_installed_faster_whisper() -> None:
    # The counter-check is only worth something while the real package still loads a
    # model this way: a directory is opened, everything else goes to download_model.
    package = next(path for path in map(Path, sys.path) if (path / "faster_whisper" / "transcribe.py").is_file())
    transcribe = (package / "faster_whisper" / "transcribe.py").read_text(encoding="utf-8")
    exported = (package / "faster_whisper" / "__init__.py").read_text(encoding="utf-8")

    assert "elif os.path.isdir(model_size_or_path):" in transcribe
    assert "model_path = download_model(" in transcribe
    assert "local_files_only=local_files_only," in transcribe
    assert "from faster_whisper.utils import available_models, download_model, format_timestamp" in exported
    arguments = transcribe.split("class WhisperModel:", 1)[1].split("):", 1)[0]
    positions = [line.split(":")[0].strip() for line in arguments.splitlines() if ":" in line and "def " not in line]
    # download_root is the seventh argument after self: six positions are safe, the gate reports more.
    assert positions[:7] == [
        "model_size_or_path",
        "device",
        "device_index",
        "compute_type",
        "cpu_threads",
        "num_workers",
        "download_root",
    ]
    assert set(DOWNLOAD_ONLY_ARGUMENTS) <= set(positions)


# -- rule 3: the offline switches of the image ------------------------------------


def final_environment(dockerfile: str) -> dict[str, str]:
    """The ENV values the last stage of a Dockerfile ends with, a later ENV winning."""
    joined = re.sub(r"\\[ \t]*\r?\n", " ", dockerfile)
    environment: dict[str, str] = {}
    for line in joined.splitlines():
        words = line.strip().split(None, 1)
        if not words:
            continue
        instruction = words[0].upper()
        if instruction == "FROM":
            environment = {}
        elif instruction == "ENV" and len(words) == 2:
            parts = shlex.split(words[1], comments=False, posix=True)
            if parts and "=" not in parts[0]:
                # The old form: ENV NAME the rest of the line.
                environment[parts[0]] = " ".join(parts[1:])
                continue
            for part in parts:
                name, _, value = part.partition("=")
                environment[name] = value
    return environment


def hub_env_findings(dockerfile: str, scripts: dict[str, str]) -> list[str]:
    environment = final_environment(dockerfile)
    findings = [
        f"{name} is {environment.get(name)!r} in the last stage, not {value!r}"
        for name, value in HUB_ENV.items()
        if environment.get(name) != value
    ]
    findings += [f"{name} touches {switch}" for name, text in scripts.items() for switch in HUB_ENV if switch in text]
    return findings


def _image_scripts() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted((BACKEND_ROOT / "docker").iterdir())}


def test_the_image_ends_with_the_hub_offline_and_without_telemetry() -> None:
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")
    scripts = _image_scripts()

    assert {"entrypoint.sh", "start.sh"} <= scripts.keys()
    assert hub_env_findings(dockerfile, scripts) == []
    # The control that the reader took the last stage: it is the one that sets the path of the venv.
    assert final_environment(dockerfile)["PATH"].startswith("/app/.venv/bin")


RUNTIME = "FROM base AS build\nENV UV_COMPILE_BYTECODE=1\nFROM base AS runtime\n"


def test_a_switch_that_is_overridden_missing_or_not_one_is_reported() -> None:
    kept = RUNTIME + "ENV PATH=/app/bin \\\n    HF_HUB_OFFLINE=1 \\\n    HF_HUB_DISABLE_TELEMETRY=1\n"
    assert hub_env_findings(kept, {}) == []
    assert hub_env_findings(RUNTIME + 'ENV HF_HUB_OFFLINE="1" HF_HUB_DISABLE_TELEMETRY=1\n', {}) == []
    assert hub_env_findings(RUNTIME + "ENV HF_HUB_OFFLINE 1\nENV HF_HUB_DISABLE_TELEMETRY 1\n", {}) == []

    overridden = kept + "ENV HF_HUB_OFFLINE=0\n"
    assert hub_env_findings(overridden, {}) == ["HF_HUB_OFFLINE is '0' in the last stage, not '1'"]
    # The older rule of test_dockerfile.py looks for the text only and lets this one through.
    assert sets_the_hub_env(overridden)

    assert hub_env_findings(kept.replace("HF_HUB_OFFLINE=1", "HF_HUB_OFFLINE=10"), {}) == [
        "HF_HUB_OFFLINE is '10' in the last stage, not '1'"
    ]
    assert hub_env_findings(kept + "ENV HF_HUB_DISABLE_TELEMETRY=\n", {}) == [
        "HF_HUB_DISABLE_TELEMETRY is '' in the last stage, not '1'"
    ]
    build_only = "FROM base AS build\nENV HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1\nFROM base AS runtime\nENV A=1\n"
    assert hub_env_findings(build_only, {}) == [
        "HF_HUB_OFFLINE is None in the last stage, not '1'",
        "HF_HUB_DISABLE_TELEMETRY is None in the last stage, not '1'",
    ]
    commented = RUNTIME + "# ENV HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1\n"
    assert len(hub_env_findings(commented, {})) == 2


def test_a_script_of_the_image_that_touches_a_switch_is_reported() -> None:
    kept = RUNTIME + "ENV HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1\n"

    assert hub_env_findings(kept, {"entrypoint.sh": '#!/bin/sh\nunset HF_HUB_OFFLINE\nexec "$@"\n'}) == [
        "entrypoint.sh touches HF_HUB_OFFLINE"
    ]
    assert hub_env_findings(kept, {"start.sh": "export HF_HUB_DISABLE_TELEMETRY=0\n"}) == [
        "start.sh touches HF_HUB_DISABLE_TELEMETRY"
    ]
