"""A second witness for tests/test_no_hub_network.py: watch the imports while they run.

The gate itself reads source text as a syntax tree. This program reads no source
at all. It is started as its own interpreter and has two modes:

``imports <search path> <package> <forbidden module>...``
    Imports every module of a package and watches each import statement while it
    executes. An import of a forbidden module whose importer is a module of that
    package is written down and refused, so the forbidden module is never loaded.

``calls <search path> <module> <function> <model directory>``
    Puts a stand-in for faster_whisper in place, imports one module, calls one
    function of it with a model directory and writes down how WhisperModel was
    built and whether download_model was called.

Both print one JSON object. Only the standard library is used.
"""

import builtins
import importlib
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from typing import Any


def watch_imports(search_path: str, package: str, forbidden: frozenset[str]) -> dict[str, Any]:
    records: list[dict[str, str]] = []
    original_import = builtins.__import__
    original_import_module = importlib.import_module

    def inside(importer: str) -> bool:
        return importer == package or importer.startswith(f"{package}.")

    def refuse(name: str, importer: str) -> None:
        if name.split(".")[0] in forbidden and inside(importer):
            records.append({"importer": importer, "module": name})
            raise ImportError(f"refused by the probe: {name}")

    def watching_import(name: str, *args: Any, **kwargs: Any) -> Any:
        # builtins.__import__(name, globals, locals, fromlist, level): every import statement.
        module_globals = args[0] if args else kwargs.get("globals")
        level = args[3] if len(args) > 3 else kwargs.get("level", 0)
        if level == 0:
            refuse(name, str((module_globals or {}).get("__name__", "")))
        return original_import(name, *args, **kwargs)

    def watching_import_module(name: str, *args: Any, **kwargs: Any) -> Any:
        # importlib.import_module(name, package=None): the importer is the caller.
        if not name.startswith("."):
            refuse(name, str(sys._getframe(1).f_globals.get("__name__", "")))
        return original_import_module(name, *args, **kwargs)

    sys.path.insert(0, search_path)
    # The package is found without running it, so its own first line is watched too.
    spec = importlib.util.find_spec(package)
    if spec is None or spec.submodule_search_locations is None:
        raise SystemExit(f"{package} is not a package on {search_path}")
    failed: dict[str, str] = {}
    builtins.__import__ = watching_import
    importlib.import_module = watching_import_module
    # Every file of the package is a module to import; the list comes from the folder,
    # so a module nobody imports is run as well.
    root = Path(next(iter(spec.submodule_search_locations)))
    names = sorted(
        ".".join([package, *path.relative_to(root).with_suffix("").parts]).removesuffix(".__init__")
        for path in root.rglob("*.py")
    )
    try:
        for name in names:
            try:
                original_import_module(name)
            except Exception as error:
                failed[name] = f"{type(error).__name__}: {error}"
    finally:
        builtins.__import__ = original_import
        importlib.import_module = original_import_module
    loaded = sorted(top for top in forbidden if top in sys.modules)
    return {"modules": names, "records": records, "failed": failed, "loaded": loaded}


def watch_calls(search_path: str, module: str, function: str, model_directory: str) -> dict[str, Any]:
    built: list[dict[str, Any]] = []
    downloads: list[dict[str, Any]] = []

    class WhisperModel:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            model = args[0] if args else kwargs.get("model_size_or_path")
            local = os.path.isdir(str(model))
            built.append(
                {
                    "model": str(model),
                    "is_directory": local,
                    "local_files_only": kwargs.get("local_files_only", False),
                    # faster-whisper 1.2.1, WhisperModel.__init__: a directory is opened,
                    # everything else goes to download_model.
                    "asks_the_hub": not local,
                    "may_use_the_network": not local and kwargs.get("local_files_only", False) is not True,
                }
            )

    def download_model(*args: Any, **kwargs: Any) -> str:
        downloads.append({"args": [str(arg) for arg in args], "kwargs": sorted(kwargs)})
        return model_directory

    stand_in = types.ModuleType("faster_whisper")
    stand_in.WhisperModel = WhisperModel  # type: ignore[attr-defined]
    stand_in.download_model = download_model  # type: ignore[attr-defined]
    utils = types.ModuleType("faster_whisper.utils")
    utils.download_model = download_model  # type: ignore[attr-defined]
    stand_in.utils = utils  # type: ignore[attr-defined]
    sys.modules["faster_whisper"] = stand_in
    sys.modules["faster_whisper.utils"] = utils
    sys.path.insert(0, search_path)
    getattr(importlib.import_module(module), function)(model_directory)
    return {"built": built, "downloads": downloads}


def main(arguments: list[str]) -> int:
    mode, search_path, *rest = arguments
    if mode == "imports":
        result = watch_imports(search_path, rest[0], frozenset(rest[1:]))
    elif mode == "calls":
        result = watch_calls(search_path, rest[0], rest[1], rest[2])
    else:
        raise SystemExit(f"unknown mode {mode}")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
