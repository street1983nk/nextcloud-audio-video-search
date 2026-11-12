"""The gate of the read proof: no way around it, and only two places write a content key (plan 02-13).

The read proof (D-02-01a) stands between a copy and the transcript of a content
that another reader downloaded. D-02-10: the product has NO way to turn it off,
no environment variable, no setting, no marker file, no switch for development.
This file reads the sources of ``php/`` and ``backend/src`` and fails when one
appears. ``scan(root)`` is a function of a tree, so the counter tests below run
it on a changed copy and prove that each rule can fail:

a  no identifier and no text that joins a word for turning something off with
   the read proof or the head, no fixed name of such a switch, no marker name;
b  ``worker/read_proof.py`` and ``worker/capture.py`` read no environment, no
   setting, no file existence and nothing of a development mode;
c  ``prove_read`` has exactly one ``return ProofOutcome.OK``, in the branch of
   ``hmac.compare_digest`` and after the length check; ``attach_by_proof`` and
   ``confirm_proof`` are called only in ``worker/capture.py``, only in the branch
   ``<outcome> is ProofOutcome.OK`` of an outcome that ``prove_read`` returned in
   the same function;
d  the head route of the PHP gateway depends on no configuration;
e  the patch of the control leg lives under ``ci/leak-control/`` only, the build
   context ``backend/`` has no ``ci/``, and no workflow except the acceptance
   test names the patch;
f0 ``Store.mark_keyed`` is called only in ``worker/capture.py``, with the hash
   of the bytes the fetch of the same reference returned in the same function;
f  only ``mark_keyed`` and ``attach_by_proof`` give a reference a content
   (``UPDATE file_ref ... media_id``), no UPDATE has the prefilter key in its
   WHERE clause, and ``attach_by_proof`` is conditional;
g  counter tests: the patch applied to a copy, an inserted environment read and
   an inserted UPDATE by prefilter key each make the gate fail.
"""

import ast
import re
import shutil
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

PACKAGE = Path("backend/src/audio_video_search_backend")
READ_PROOF = PACKAGE / "worker" / "read_proof.py"
CAPTURE = PACKAGE / "worker" / "capture.py"
REPO = PACKAGE / "store" / "repo.py"
MIGRATE = PACKAGE / "store" / "migrate.py"
GATEWAY = Path("php/lib/Controller/GatewayController.php")
GATEWAY_HELPERS = (Path("php/lib/Service/FileAccess.php"), Path("php/lib/Service/ReaderContext.php"))
PATCH_DIR = Path("ci/leak-control")
PATCH_NAME = "read-proof-off.patch"
PATCH = PATCH_DIR / PATCH_NAME
WORKFLOWS = Path(".github/workflows")
ACCEPTANCE_WORKFLOW = "discovery-e2e.yml"

PRUNED = frozenset(
    {".git", ".venv", "node_modules", "vendor", "__pycache__", ".pytest_cache", ".ruff_cache", "playwright-report"}
)
# Trees a patch could hide in; .planning is prose about the plan, not a tree that is built or shipped.
PATCH_SEARCH = ("backend", "php", "ci", "scripts", "docs", ".github")

# Rule a. The words for turning something off, and what must never stand beside them.
SWITCH = re.compile(r"(?i)skip|disabl|bypass|unsafe")
SUBJECT = re.compile(r"(?i)read_?proof|proof|head")
FIXED_NAMES = re.compile(
    r"(?i)read_?proof_?enabled"
    r"|(?:\bno|skip|disabled?|without|bypass)[-_.]?(?:read[-_.]?)?proof"
    r"|proof[-_.](?:off|disabled|skip(?:ped)?|bypass)"
    r"|AVS_[A-Za-z0-9_]*PROOF"
)

# Rule b.
B_FORBIDDEN = ("os.environ", "getenv", "settings.", "exists(", "is_file(")
B_DEVELOPMENT = re.compile(r"(?i)debug")
READ_PROOF_IMPORTS = frozenset(
    {
        "enum",
        "hmac",
        "logging",
        "re",
        "collections.abc",
        "typing",
        "audio_video_search_backend",
        "audio_video_search_backend.store.repo",
    }
)
CAPTURE_FORBIDDEN_IMPORTS = frozenset({"os", "audio_video_search_backend.settings"})

# Rule d.
D_FORBIDDEN = ("getSystemValue", "getAppValue", "IConfig", "IAppConfig", "getValueBool", "getValueString")

# Rule f. The SQL constants that give a reference a content, and the one method each may be used in.
WRITERS = {"_KEY_REF": "mark_keyed", "_ATTACH_REF": "attach_by_proof"}
UPSERT = ("_UPSERT_FILE_REF", "upsert_file_ref")


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _walk(top: Path) -> Iterator[Path]:
    if not top.is_dir():
        return
    for entry in sorted(top.iterdir()):
        if entry.name in PRUNED:
            continue
        if entry.is_dir():
            yield from _walk(entry)
        else:
            yield entry


def product_files(root: Path) -> list[Path]:
    """Every file of the product: php/ without its tests, and backend/src."""
    php = [path for path in _walk(root / "php") if "tests" not in path.relative_to(root / "php").parts[:1]]
    return php + list(_walk(root / "backend" / "src"))


def package_sources(root: Path) -> dict[str, str]:
    """The Python sources of the backend package by their path below the root."""
    sources = {}
    for path in _walk(root / PACKAGE):
        text = _read(path) if path.suffix == ".py" else None
        if text is not None:
            sources[path.relative_to(root).as_posix()] = text
    return sources


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _tail(node: ast.AST) -> str | None:
    """The last name of ``a``, ``a.b`` or ``a.b.c``."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_attr(node: ast.AST, base: str, attr: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attr
        and isinstance(node.value, ast.Name)
        and node.value.id == base
    )


def _is_ok(node: ast.AST) -> bool:
    """``ProofOutcome.OK`` or ``<module>.ProofOutcome.OK``."""
    return isinstance(node, ast.Attribute) and node.attr == "OK" and _tail(node.value) == "ProofOutcome"


def _function_of(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    current = parents.get(node)
    while current is not None and not isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
        current = parents.get(current)
    return current


def _calls(tree: ast.AST, method: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == method
    ]


def _stores(function: ast.AST, name: str) -> list[ast.Name]:
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Store)
    ]


def _parameters(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    arguments = function.args
    names = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    return {argument.arg for argument in names}


# Rule a.


def python_tokens(source: str) -> list[str]:
    """Every identifier and every line of every text of a Python source (comments are no text)."""
    tokens: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            tokens.append(node.id)
        elif isinstance(node, ast.Attribute):
            tokens.append(node.attr)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            tokens.append(node.name)
        elif isinstance(node, ast.arg | ast.keyword) and node.arg:
            tokens.append(node.arg)
        elif isinstance(node, ast.alias):
            tokens += [node.name, node.asname or ""]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            tokens += node.value.splitlines()
    return tokens


def split_php(source: str) -> tuple[str, list[str]]:
    """(the code without comments and with emptied string literals, the string literals)."""
    code: list[str] = []
    strings: list[str] = []
    index, end = 0, len(source)
    while index < end:
        char, two = source[index], source[index : index + 2]
        if two == "/*":
            close = source.find("*/", index + 2)
            index = end if close < 0 else close + 2
            code.append(" ")
        elif two == "//" or (char == "#" and two != "#["):
            close = source.find("\n", index)
            index = end if close < 0 else close
        elif char in "'\"":
            close = index + 1
            while close < end and source[close] != char:
                close += 2 if source[close] == "\\" else 1
            strings.append(source[index + 1 : close])
            code.append(char + char)
            index = close + 1
        else:
            code.append(char)
            index += 1
    return "".join(code), strings


def php_tokens(source: str) -> list[str]:
    code, strings = split_php(source)
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", code) + [line for text in strings for line in text.splitlines()]


def switch_tokens(tokens: Iterable[str]) -> list[str]:
    """The tokens that join a word for turning something off with the read proof or the head."""
    return sorted({token.strip() for token in tokens if SWITCH.search(token) and SUBJECT.search(token)})


def rule_a_file(name: str, source: str) -> list[str]:
    findings = [f"a: {name} names a switch: {match.group(0)}" for match in FIXED_NAMES.finditer(source)]
    if name.endswith(".py"):
        tokens = python_tokens(source)
    elif name.endswith(".php") and "/lib/" in name:
        tokens = php_tokens(source)
    else:
        tokens = source.splitlines()
    return findings + [f"a: {name} joins a switch word with the read proof: {token}" for token in switch_tokens(tokens)]


def rule_a(root: Path) -> list[str]:
    findings: list[str] = []
    for path in product_files(root):
        source = _read(path)
        if source is not None:
            findings += rule_a_file(path.relative_to(root).as_posix(), source)
    return findings


# Rule b.


def _imports(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names += [node.module] + [f"{node.module}.{alias.name}" for alias in node.names]
    return names


def rule_b_file(name: str, source: str) -> list[str]:
    findings = [f"b: {name} contains {needle}" for needle in B_FORBIDDEN if needle in source]
    if B_DEVELOPMENT.search(source):
        findings.append(f"b: {name} names a development mode")
    tree = ast.parse(source)
    imported = _imports(tree)
    if name.endswith("read_proof.py"):
        modules = {
            node.module if isinstance(node, ast.ImportFrom) else alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
        }
        findings += [f"b: {name} imports {module}" for module in sorted(str(m) for m in modules - READ_PROOF_IMPORTS)]
    else:
        findings += [f"b: {name} imports {module}" for module in imported if module in CAPTURE_FORBIDDEN_IMPORTS]
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and _tail(node.value) == "config" and node.attr != "storage_root":
                findings.append(f"b: {name} reads config.{node.attr}")
    return findings


def rule_b(root: Path) -> list[str]:
    findings: list[str] = []
    for relative in (READ_PROOF, CAPTURE):
        source = _read(root / relative)
        if source is None:
            findings.append(f"b: {relative.as_posix()} is missing")
        else:
            findings += rule_b_file(relative.as_posix(), source)
    return findings


# Rule c.


def prove_read_findings(source: str) -> list[str]:
    """What is wrong with the one place that may say ok."""
    tree = ast.parse(source)
    parents = _parents(tree)
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "prove_read"
    ]
    if len(functions) != 1:
        return [f"c: read_proof.py defines prove_read {len(functions)} times"]
    function = functions[0]
    findings: list[str] = []
    imports = _imports(tree)
    bound = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "hmac" and isinstance(n.ctx, ast.Store)]
    if "hmac" not in imports or bound:
        findings.append("c: hmac in read_proof.py is not the module of the standard library")
    ok_everywhere = [node for node in ast.walk(tree) if _is_ok(node)]
    returns = [
        node for node in ast.walk(function) if isinstance(node, ast.Return) and node.value and _is_ok(node.value)
    ]
    if len(returns) != 1:
        return [*findings, f"c: prove_read has {len(returns)} return ProofOutcome.OK, not exactly one"]
    if len(ok_everywhere) != 1:
        findings.append("c: read_proof.py names ProofOutcome.OK outside the one return")
    only = returns[0]
    branch = parents.get(only)
    test = branch.test if isinstance(branch, ast.If) else None
    if not (
        isinstance(branch, ast.If)
        and only in branch.body
        and isinstance(test, ast.Call)
        and _is_attr(test.func, "hmac", "compare_digest")
    ):
        findings.append("c: return ProofOutcome.OK is not in the branch of hmac.compare_digest")
    length_checks = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.If)
        and node.lineno < only.lineno
        and isinstance(node.test, ast.Compare)
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.NotEq)
        and {_tail(node.test.left), _tail(node.test.comparators[0])} == {"length", "expected_length"}
        and any(isinstance(statement, ast.Return) for statement in node.body)
    ]
    if not length_checks:
        findings.append("c: prove_read does not refuse a wrong head length before it compares")
    return findings


def _ok_branch(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> tuple[ast.If, str] | None:
    """The If ``<name> is ProofOutcome.OK`` whose body holds the call, and the name."""
    child: ast.AST = call
    parent = parents.get(child)
    while parent is not None:
        if isinstance(parent, ast.If) and child in parent.body:
            test = parent.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Is)
                and _is_ok(test.comparators[0])
            ):
                return parent, test.left.id
        child, parent = parent, parents.get(parent)
    return None


def _from_prove_read(value: ast.AST | None) -> bool:
    if not isinstance(value, ast.Await) or not isinstance(value.value, ast.Call):
        return False
    func = value.value.func
    return _is_attr(func, "read_proof", "prove_read") or (isinstance(func, ast.Name) and func.id == "prove_read")


def proof_use_findings(sources: dict[str, str]) -> list[str]:
    """Where a proof is turned into a content, and whether an ok can come from anywhere else."""
    findings: list[str] = []
    definitions = 0
    for name, source in sources.items():
        tree = ast.parse(source)
        parents = _parents(tree)
        in_capture = name == CAPTURE.as_posix()
        in_read_proof = name == READ_PROOF.as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "prove_read":
                definitions += 1
                if not in_read_proof:
                    findings.append(f"c: {name} defines its own prove_read")
            if isinstance(node, ast.Attribute) and node.attr == "prove_read" and isinstance(node.ctx, ast.Store):
                findings.append(f"c: {name} replaces prove_read")
            if isinstance(node, ast.Call | ast.Subscript):
                target = node.func if isinstance(node, ast.Call) else node.value
                if _tail(target) == "ProofOutcome":
                    findings.append(f"c: {name} builds a ProofOutcome instead of naming it")
            if _is_ok(node) and not in_read_proof:
                compare = parents.get(node)
                if not (
                    isinstance(compare, ast.Compare)
                    and len(compare.ops) == 1
                    and isinstance(compare.ops[0], ast.Is)
                    and node in compare.comparators
                ):
                    findings.append(f"c: {name} uses ProofOutcome.OK outside an 'is' comparison")
        for method in ("attach_by_proof", "confirm_proof"):
            for call in _calls(tree, method):
                if not in_capture:
                    findings.append(f"c: {name} calls {method}")
                    continue
                branch = _ok_branch(call, parents)
                function = _function_of(call, parents)
                if branch is None or function is None:
                    findings.append(f"c: {method} is called outside the branch 'is ProofOutcome.OK'")
                    continue
                guard, outcome = branch
                stores = _stores(function, outcome)
                assignment = parents.get(stores[0]) if len(stores) == 1 else None
                if (
                    outcome in _parameters(function)
                    or not isinstance(assignment, ast.Assign)
                    or not _from_prove_read(assignment.value)
                    or assignment.lineno >= guard.lineno
                ):
                    findings.append(f"c: the outcome before {method} is not the one answer of prove_read")
    if definitions != 1:
        findings.append(f"c: the package defines prove_read {definitions} times")
    return findings


def rule_c(root: Path) -> list[str]:
    source = _read(root / READ_PROOF)
    if source is None:
        return [f"c: {READ_PROOF.as_posix()} is missing"]
    return prove_read_findings(source) + proof_use_findings(package_sources(root))


# Rule d.


def php_method_body(code: str, method: str) -> str | None:
    """The body of a method out of comment free PHP code, by counting braces."""
    match = re.search(r"function\s+" + re.escape(method) + r"\s*\(", code)
    if match is None:
        return None
    start = code.find("{", match.end())
    depth, index = 0, start
    while 0 <= index < len(code):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                return code[start : index + 1]
        index += 1
    return None


def rule_d_sources(gateway: str, helpers: dict[str, str]) -> list[str]:
    findings: list[str] = []
    code, _strings = split_php(gateway)
    body = php_method_body(code, "getFileHead")
    if body is None:
        return ["d: GatewayController has no getFileHead"]
    for needle in ("debug", *D_FORBIDDEN):
        if needle.lower() in body.lower():
            findings.append(f"d: getFileHead contains {needle}")
    for name, source in {GATEWAY.as_posix(): gateway, **helpers}.items():
        stripped, _ = split_php(source)
        findings += [f"d: {name} contains {needle}" for needle in D_FORBIDDEN if needle in stripped]
        # The one use of the word that is no switch: a log call of the lowest level.
        if "debug" in stripped.replace("->debug(", "").lower():
            findings.append(f"d: {name} depends on a development mode")
    return findings


def rule_d(root: Path) -> list[str]:
    gateway = _read(root / GATEWAY)
    if gateway is None:
        return [f"d: {GATEWAY.as_posix()} is missing"]
    helpers = {}
    for relative in GATEWAY_HELPERS:
        source = _read(root / relative)
        if source is None:
            return [f"d: {relative.as_posix()} is missing"]
        helpers[relative.as_posix()] = source
    return rule_d_sources(gateway, helpers)


# Rule e.


def rule_e(root: Path) -> list[str]:
    findings: list[str] = []
    if not (root / PATCH).is_file():
        findings.append(f"e: {PATCH.as_posix()} is missing")
    for top in PATCH_SEARCH:
        for path in _walk(root / top):
            relative = path.relative_to(root)
            if path.suffix in {".patch", ".diff"} and relative.parent != PATCH_DIR:
                findings.append(f"e: a patch outside {PATCH_DIR.as_posix()}: {relative.as_posix()}")
    if (root / "backend" / "ci").exists() or (root / "backend" / "leak-control").exists():
        findings.append("e: the build context backend/ holds ci/ or leak-control/")
    dockerfile = _read(root / "backend" / "Dockerfile") or ""
    for needle in ("leak", ".patch", "ci/"):
        if needle in dockerfile:
            findings.append(f"e: backend/Dockerfile names {needle}")
    for path in _walk(root / WORKFLOWS):
        text = _read(path) or ""
        if path.name != ACCEPTANCE_WORKFLOW and (PATCH_NAME in text or "leak-control" in text):
            findings.append(f"e: the workflow {path.name} names the control leg or its patch")
    return findings


# Rule f0.


def _single_assignment(function: ast.AST, name: str, parents: dict[ast.AST, ast.AST]) -> ast.AST | None:
    """The value a name is given, when it is given exactly once by a plain assignment."""
    stores = _stores(function, name)
    if len(stores) != 1:
        return None
    holder = parents.get(stores[0])
    if isinstance(holder, ast.Tuple):
        holder = parents.get(holder)
    return holder.value if isinstance(holder, ast.Assign) else None


def _is_fetch_of(value: ast.AST | None, reference: str) -> bool:
    """``await self._fetch(<reference>.file_id, ...)`` or the same with nc.fetch_to_tempfile."""
    if not isinstance(value, ast.Await) or not isinstance(value.value, ast.Call):
        return False
    call = value.value
    known = _is_attr(call.func, "self", "_fetch") or _is_attr(call.func, "nc", "fetch_to_tempfile")
    return known and bool(call.args) and _is_attr(call.args[0], reference, "file_id")


def _hash_of_own_fetch(function: ast.AST, name: str, reference: str, parents: dict[ast.AST, ast.AST]) -> bool:
    """Whether ``name`` is the validated hash of the fetch of ``reference`` in this function."""
    checked = _single_assignment(function, name, parents)
    if not isinstance(checked, ast.Name):
        return False
    validated = _single_assignment(function, checked.id, parents)
    if not (
        isinstance(validated, ast.Call)
        and isinstance(validated.func, ast.Name)
        and validated.func.id == "_validated"
        and len(validated.args) == 2
        and isinstance(validated.args[0], ast.Name)
        and validated.args[0].id == reference
        and isinstance(validated.args[1], ast.Name)
    ):
        return False
    return _is_fetch_of(_single_assignment(function, validated.args[1].id, parents), reference)


def _validated_returns_the_fetched_hash(tree: ast.AST) -> bool:
    """``_validated(ref, result)`` hands out ``result.sha256`` and ``result.head_sha256`` and nothing else."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_validated":
            parameters = [argument.arg for argument in node.args.args]
            if len(parameters) != 2:
                return False
            result = parameters[1]
            pairs: list[tuple[ast.Tuple, ast.Tuple]] = []
            tuples: list[ast.Tuple] = []
            for statement in ast.walk(node):
                if isinstance(statement, ast.Assign):
                    target, value = statement.targets[0], statement.value
                    if isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple):
                        pairs.append((target, value))
                elif isinstance(statement, ast.Return) and isinstance(statement.value, ast.Tuple):
                    tuples.append(statement.value)
            if len(pairs) != 1 or len(tuples) != 1:
                return False
            targets = [_tail(target) for target in pairs[0][0].elts]
            values = pairs[0][1].elts
            returned = [_tail(element) for element in tuples[0].elts]
            return (
                len(values) == 2
                and _is_attr(values[0], result, "sha256")
                and _is_attr(values[1], result, "head_sha256")
                and returned == targets
                and all(len(_stores(node, str(target))) == 1 for target in targets)
            )
    return False


def mark_keyed_findings(sources: dict[str, str]) -> list[str]:
    findings: list[str] = []
    seen = 0
    for name, source in sources.items():
        tree = ast.parse(source)
        parents = _parents(tree)
        for call in _calls(tree, "mark_keyed"):
            seen += 1
            if name != CAPTURE.as_posix():
                findings.append(f"f0: {name} calls mark_keyed")
                continue
            function = _function_of(call, parents)
            arguments = call.args
            if (
                function is None
                or len(arguments) < 2
                or not isinstance(arguments[0], ast.Name)
                or not isinstance(arguments[1], ast.Name)
                or not _hash_of_own_fetch(function, arguments[1].id, arguments[0].id, parents)
            ):
                findings.append("f0: mark_keyed gets a hash that is not the one of the fetch of the same reference")
        if name == CAPTURE.as_posix() and not _validated_returns_the_fetched_hash(tree):
            findings.append("f0: _validated does not hand out the hashes of the fetch result unchanged")
    if seen == 0:
        findings.append("f0: nothing calls mark_keyed")
    return findings


# Rule f.


def _sql_constants(source: str) -> list[tuple[str | None, str]]:
    """(name of the module constant or None, text) of every text that names file_ref."""
    tree = ast.parse(source)
    named: dict[int, str] = {}
    for node in tree.body:
        value = getattr(node, "value", None)
        target = node.target if isinstance(node, ast.AnnAssign) else None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant):
            named[id(value)] = target.id
    return [
        (named.get(id(node)), node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "file_ref" in node.value.lower()
    ]


def _update_parts(text: str) -> tuple[str, str] | None:
    """(SET clause, WHERE clause) of an UPDATE of file_ref."""
    match = re.search(r"(?is)\bUPDATE\s+file_ref\s+SET\b(.*)", text)
    if match is None:
        return None
    rest = match.group(1)
    where = re.search(r"(?i)\bWHERE\b", rest)
    if where is None:
        return rest, ""
    # What RETURNING hands out is no condition.
    condition = re.split(r"(?i)\bRETURNING\b", rest[where.end() :])[0]
    return rest[: where.start()], condition


def _sets_media_id(set_clause: str) -> bool:
    values = re.findall(r"(?i)(?<![\w.])media_id\s*=\s*([^\s,]+)", set_clause)
    return any(value.upper() != "NULL" for value in values)


def _insert_gives_media_id(text: str) -> str | None:
    """The table an INSERT gives a content to, None when it gives none (or NULL)."""
    match = re.search(r"(?is)\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+(file_ref\w*)\s*\(([^)]*)\)\s*(.*)", text)
    if match is None:
        return None
    table, columns, rest = match.group(1), [c.strip().lower() for c in match.group(2).split(",")], match.group(3)
    if "media_id" not in columns:
        return None
    values = re.match(r"(?is)VALUES\s*\(([^)]*)\)(.*)", rest)
    if values is None:
        return table  # INSERT ... SELECT
    given = [value.strip() for value in values.group(1).split(",")]
    position = columns.index("media_id")
    literal_null = position < len(given) and given[position].upper() == "NULL"
    conflict = re.search(r"(?is)\bDO\s+UPDATE\s+SET\b(.*)", values.group(2))
    if literal_null and (conflict is None or not _sets_media_id(conflict.group(1))):
        return None
    return table


def sql_findings(sources: dict[str, str]) -> list[str]:
    findings: list[str] = []
    for name, source in sources.items():
        for constant, text in _sql_constants(source):
            label = constant or "a text"
            update = _update_parts(text)
            if update is not None:
                set_clause, where_clause = update
                if "prefilter_key" in where_clause.lower():
                    findings.append(f"f: {name}: {label} is an UPDATE with prefilter_key in its WHERE clause")
                if _sets_media_id(set_clause) and (name != REPO.as_posix() or constant not in WRITERS):
                    findings.append(f"f: {name}: {label} sets media_id on file_ref")
            table = _insert_gives_media_id(text)
            if table is not None:
                allowed = (name == REPO.as_posix() and constant == UPSERT[0]) or (
                    name == MIGRATE.as_posix() and table == "file_ref_v2"
                )
                if not allowed:
                    findings.append(f"f: {name}: {label} inserts a media_id into {table}")
    return findings


def writer_findings(sources: dict[str, str]) -> list[str]:
    """Each writing constant is used in its one method; attach_by_proof is conditional; the upsert has no caller."""
    findings: list[str] = []
    repo = sources.get(REPO.as_posix())
    if repo is None:
        return [f"f: {REPO.as_posix()} is missing"]
    tree = ast.parse(repo)
    parents = _parents(tree)
    texts = {name: text for name, text in _sql_constants(repo) if name is not None}
    for constant, method in (*WRITERS.items(), UPSERT):
        if constant not in texts:
            findings.append(f"f: repo.py has no {constant}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == constant and isinstance(node.ctx, ast.Load):
                function = _function_of(node, parents)
                if function is None or function.name != method:
                    findings.append(f"f: {constant} is used outside {method}")
    attach = texts.get("_ATTACH_REF", "")
    parts = _update_parts(attach)
    where = "" if parts is None else " ".join(parts[1].lower().split())
    for condition in ("file_id = :file_id", "etag = :etag", "media_id is null"):
        if condition not in where:
            findings.append(f"f: attach_by_proof is not conditional on {condition}")
    for name, source in sources.items():
        if _calls(ast.parse(source), UPSERT[1]):
            findings.append(f"f: {name} calls {UPSERT[1]}, the unconditional write of the tests")
    return findings


def rule_f(root: Path) -> list[str]:
    sources = package_sources(root)
    return mark_keyed_findings(sources) + sql_findings(sources) + writer_findings(sources)


def scan(root: Path) -> list[str]:
    """Every way around the read proof this gate knows, found in the tree under ``root``."""
    return rule_a(root) + rule_b(root) + rule_c(root) + rule_d(root) + rule_e(root) + rule_f(root)


# The tree as it is.


def test_the_product_has_no_way_around_the_read_proof() -> None:
    assert scan(REPO_ROOT) == []


def test_the_scan_reads_the_files_it_is_about() -> None:
    names = {path.relative_to(REPO_ROOT).as_posix() for path in product_files(REPO_ROOT)}

    assert READ_PROOF.as_posix() in names
    assert CAPTURE.as_posix() in names
    assert GATEWAY.as_posix() in names
    assert not any(name.startswith("php/tests/") or "/vendor/" in name for name in names)
    assert len(package_sources(REPO_ROOT)) >= 15


# Rule g: the counter tests on a changed copy.


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A copy of what the scan reads, laid out like the repository."""
    root = tmp_path / "copy"
    ignore = shutil.ignore_patterns(*PRUNED, "tests")
    shutil.copytree(REPO_ROOT / "backend" / "src", root / "backend" / "src", ignore=ignore)
    shutil.copy(REPO_ROOT / "backend" / "Dockerfile", root / "backend" / "Dockerfile")
    shutil.copytree(REPO_ROOT / "php", root / "php", ignore=ignore)
    shutil.copytree(REPO_ROOT / WORKFLOWS, root / WORKFLOWS)
    shutil.copytree(REPO_ROOT / PATCH_DIR, root / PATCH_DIR)
    return root


def _edit(root: Path, relative: Path, old: str, new: str) -> None:
    path = root / relative
    source = path.read_text(encoding="utf-8")
    assert old in source, f"{relative.as_posix()} no longer contains the anchor of this counter test"
    path.write_text(source.replace(old, new, 1), encoding="utf-8", newline="\n")


def _append(root: Path, relative: Path, text: str) -> None:
    path = root / relative
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def test_the_copy_is_clean_before_it_is_changed(tree: Path) -> None:
    assert scan(tree) == []


def test_g_the_patch_of_the_control_leg_makes_the_gate_fail(tree: Path) -> None:
    git = shutil.which("git")
    assert git is not None, "git is needed to apply the patch"
    patch = REPO_ROOT / PATCH
    before = (tree / READ_PROOF).read_text(encoding="utf-8")

    # The same call as the control leg of discovery-e2e.yml: the copy holds backend/ at its top.
    subprocess.run([git, "-C", str(tree), "apply", "--check", str(patch)], check=True)  # noqa: S603
    subprocess.run([git, "-C", str(tree), "apply", str(patch)], check=True)  # noqa: S603

    assert (tree / READ_PROOF).read_text(encoding="utf-8") != before
    findings = scan(tree)
    assert any(finding.startswith("c: prove_read has") for finding in findings), findings
    # The patch changes the read proof and nothing else of the product.
    changed = [
        path.relative_to(tree).as_posix()
        for path in product_files(tree)
        if _read(path) != _read(REPO_ROOT / path.relative_to(tree))
    ]
    assert changed == [READ_PROOF.as_posix()]


def test_the_patch_touches_one_file_of_the_backend() -> None:
    text = (REPO_ROOT / PATCH).read_text(encoding="utf-8")
    touched = re.findall(r"^\+\+\+ b/(\S+)$", text, re.MULTILINE)

    assert touched == [READ_PROOF.as_posix()]
    assert "\r" not in text


def test_g_an_environment_read_in_the_capture_makes_rule_b_fail(tree: Path) -> None:
    _edit(tree, CAPTURE, "import asyncio\n", 'import asyncio\nimport os\n\nQUICK = os.environ.get("AVS_QUICK")\n')

    findings = scan(tree)

    assert f"b: {CAPTURE.as_posix()} contains os.environ" in findings
    assert f"b: {CAPTURE.as_posix()} imports os" in findings


def test_g_an_update_by_prefilter_key_makes_rule_f_fail(tree: Path) -> None:
    _append(
        tree,
        REPO,
        '\n_SHORTCUT: Final = "UPDATE file_ref SET media_id = :media_id WHERE prefilter_key = :prefilter_key"\n',
    )

    findings = scan(tree)

    assert f"f: {REPO.as_posix()}: _SHORTCUT is an UPDATE with prefilter_key in its WHERE clause" in findings
    assert f"f: {REPO.as_posix()}: _SHORTCUT sets media_id on file_ref" in findings


# Every other rule fails on its own sample.


def test_self_a_fires_on_identifiers_texts_and_marker_names() -> None:
    assert rule_a_file("x.py", "def skip_read_proof():\n    return 1\n") == [
        "a: x.py names a switch: skip_read_proof",
        "a: x.py joins a switch word with the read proof: skip_read_proof",
    ]
    assert rule_a_file("x.py", 'FLAG = "unsafe-head"\n') == [
        "a: x.py joins a switch word with the read proof: unsafe-head"
    ]
    assert rule_a_file("x.py", "value = read_proof_enabled\n") == ["a: x.py names a switch: read_proof_enabled"]
    assert rule_a_file("x.py", 'MARKER = ".noproof"\n') == ["a: x.py names a switch: noproof"]
    assert rule_a_file("x.py", 'NAME = "AVS_PROOF"\n') == ["a: x.py names a switch: AVS_PROOF"]
    assert rule_a_file("php/lib/X.php", "<?php\n$bypassHead = true;\n") == [
        "a: php/lib/X.php joins a switch word with the read proof: bypassHead"
    ]
    assert rule_a_file("php/lib/X.php", "<?php\n$x = $c->get('disable_proof');\n") == [
        "a: php/lib/X.php names a switch: disable_proof",
        "a: php/lib/X.php joins a switch word with the read proof: disable_proof",
    ]
    assert rule_a_file("php/js/x.js", "const headSkipped = 1;\n") == [
        "a: php/js/x.js joins a switch word with the read proof: const headSkipped = 1;"
    ]


def test_self_a_ignores_comments_and_plain_words() -> None:
    assert rule_a_file("x.py", "# never skip the read proof\nhead = 1\nskipped = 2\n") == []
    assert (
        rule_a_file("php/lib/X.php", "<?php\n// no way to bypass the head route\n/* skip proof */\n$head = 1;\n") == []
    )
    assert rule_a_file("x.py", "def prove_read():\n    return attach_by_proof\n") == []


def test_self_b_fires_on_each_forbidden_read() -> None:
    name = CAPTURE.as_posix()
    for line, finding in [
        ('x = os.environ["A"]', "contains os.environ"),
        ('x = os.getenv("A")', "contains getenv"),
        ("x = settings.current()", "contains settings."),
        ("x = marker.exists()", "contains exists("),
        ("x = marker.is_file()", "contains is_file("),
        ("x = DEBUG", "names a development mode"),
        ("x = config.proof_mode()", "reads config.proof_mode"),
    ]:
        assert f"b: {name} {finding}" in rule_b_file(name, line + "\n"), line
    assert rule_b_file(name, "x = config.storage_root()\n") == []
    assert rule_b_file(READ_PROOF.as_posix(), "import os\n") == [f"b: {READ_PROOF.as_posix()} imports os"]
    assert rule_b_file(READ_PROOF.as_posix(), "import hmac\nfrom audio_video_search_backend import nc\n") == []


GOOD_PROOF = """
import hmac

async def prove_read(ref, media_head_sha256, expected_length, fetch):
    result = await fetch(ref.file_id, ref.reader_uid)
    if result.length != expected_length:
        return ProofOutcome.GATEWAY_FAILED
    if hmac.compare_digest(result.sha256, media_head_sha256):
        return ProofOutcome.OK
    return ProofOutcome.HEAD_MISMATCH
"""


def test_self_c_accepts_the_one_shape_and_fires_on_every_other() -> None:
    assert prove_read_findings(GOOD_PROOF) == []
    early = GOOD_PROOF.replace("    result = await", "    return ProofOutcome.OK\n    result = await")
    assert prove_read_findings(early) == ["c: prove_read has 2 return ProofOutcome.OK, not exactly one"]
    negated = GOOD_PROOF.replace("if hmac.compare_digest(", "if not hmac.compare_digest(")
    assert prove_read_findings(negated) == ["c: return ProofOutcome.OK is not in the branch of hmac.compare_digest"]
    equal = GOOD_PROOF.replace("hmac.compare_digest(result.sha256, media_head_sha256)", "result.sha256")
    assert prove_read_findings(equal) == ["c: return ProofOutcome.OK is not in the branch of hmac.compare_digest"]
    no_length = GOOD_PROOF.replace("result.length != expected_length", "result.length < 0")
    assert prove_read_findings(no_length) == ["c: prove_read does not refuse a wrong head length before it compares"]
    late = GOOD_PROOF.replace(
        "    if result.length != expected_length:\n        return ProofOutcome.GATEWAY_FAILED\n", ""
    )
    late += "    if result.length != expected_length:\n        return ProofOutcome.GATEWAY_FAILED\n"
    assert prove_read_findings(late) == ["c: prove_read does not refuse a wrong head length before it compares"]
    aliased = GOOD_PROOF + "\nALWAYS = ProofOutcome.OK\n"
    assert prove_read_findings(aliased) == ["c: read_proof.py names ProofOutcome.OK outside the one return"]
    own = GOOD_PROOF.replace("import hmac", "import hmac\nhmac = Fake()")
    assert prove_read_findings(own) == ["c: hmac in read_proof.py is not the module of the standard library"]
    assert prove_read_findings("x = 1\n") == ["c: read_proof.py defines prove_read 0 times"]


GOOD_USE = """
async def step(self, ref, media_id, head):
    outcome = await read_proof.prove_read(ref, head, 1, self._head)
    if outcome is ProofOutcome.OK:
        return await run_locked(self._services, lambda: store.attach_by_proof(ref.file_id, media_id, ref.etag))
    return None
"""


def _use(source: str) -> list[str]:
    return proof_use_findings({READ_PROOF.as_posix(): GOOD_PROOF, CAPTURE.as_posix(): source})


def test_self_c_holds_every_attach_to_the_ok_branch_of_prove_read() -> None:
    assert _use(GOOD_USE) == []
    assert _use(GOOD_USE.replace("attach_by_proof", "confirm_proof")) == []
    outside = GOOD_USE.replace("    if outcome is ProofOutcome.OK:\n    ", "")
    assert _use(outside) == ["c: attach_by_proof is called outside the branch 'is ProofOutcome.OK'"]
    other_branch = GOOD_USE.replace("outcome is ProofOutcome.OK", "outcome is not ProofOutcome.OK")
    assert _use(other_branch) == [
        f"c: {CAPTURE.as_posix()} uses ProofOutcome.OK outside an 'is' comparison",
        "c: attach_by_proof is called outside the branch 'is ProofOutcome.OK'",
    ]
    in_else = GOOD_USE.replace(
        "    if outcome is ProofOutcome.OK:\n", "    if outcome is ProofOutcome.OK:\n        pass\n    else:\n"
    )
    assert _use(in_else) == ["c: attach_by_proof is called outside the branch 'is ProofOutcome.OK'"]
    made_up = GOOD_USE.replace("await read_proof.prove_read(ref, head, 1, self._head)", "self._cached")
    assert _use(made_up) == ["c: the outcome before attach_by_proof is not the one answer of prove_read"]
    twice = GOOD_USE.replace("    if outcome", "    outcome = self._other or outcome\n    if outcome")
    assert _use(twice) == ["c: the outcome before attach_by_proof is not the one answer of prove_read"]
    parameter = GOOD_USE.replace("media_id, head):", "media_id, head, outcome):").replace(
        "    outcome = await read_proof.prove_read(ref, head, 1, self._head)\n", ""
    )
    assert _use(parameter) == ["c: the outcome before attach_by_proof is not the one answer of prove_read"]
    forced = GOOD_USE + "\nFORCED = ProofOutcome.OK\n"
    assert _use(forced) == [f"c: {CAPTURE.as_posix()} uses ProofOutcome.OK outside an 'is' comparison"]
    built = GOOD_USE + '\nBUILT = ProofOutcome("ok")\n'
    assert _use(built) == [f"c: {CAPTURE.as_posix()} builds a ProofOutcome instead of naming it"]
    replaced = GOOD_USE + "\nread_proof.prove_read = fake\n"
    assert _use(replaced) == [f"c: {CAPTURE.as_posix()} replaces prove_read"]
    second = GOOD_USE + "\nasync def prove_read():\n    return None\n"
    assert _use(second) == [
        f"c: {CAPTURE.as_posix()} defines its own prove_read",
        "c: the package defines prove_read 2 times",
    ]
    elsewhere = proof_use_findings(
        {READ_PROOF.as_posix(): GOOD_PROOF, "backend/src/audio_video_search_backend/api/x.py": GOOD_USE}
    )
    assert elsewhere == ["c: backend/src/audio_video_search_backend/api/x.py calls attach_by_proof"]


def test_self_d_fires_on_a_configuration_in_the_head_route() -> None:
    good = (
        "<?php\nclass G {\n\tpublic function getFileHead(int $fileId) {\n\t\treturn $this->resolve($fileId);\n\t}\n}\n"
    )
    assert rule_d_sources(good, {}) == []
    # A comment may say what the route does not do.
    assert rule_d_sources(good.replace("<?php\n", "<?php\n// no debug, no IConfig\n"), {}) == []
    switched = good.replace(
        "return $this->resolve", "if ($this->config->getSystemValue('debug')) { return 1; }\n\t\treturn $this->resolve"
    )
    assert rule_d_sources(switched, {}) == [
        "d: getFileHead contains getSystemValue",
        f"d: {GATEWAY.as_posix()} contains getSystemValue",
    ]
    mode = good.replace("return $this->resolve", "if ($this->debugMode) { return 1; }\n\t\treturn $this->resolve")
    assert rule_d_sources(mode, {}) == [
        "d: getFileHead contains debug",
        f"d: {GATEWAY.as_posix()} depends on a development mode",
    ]
    logged = good.replace("return $this->resolve", "$this->logger->debug('x');\n\t\treturn $this->resolve")
    assert rule_d_sources(logged, {}) == ["d: getFileHead contains debug"]
    helper = "<?php\nuse OCP\\IAppConfig;\n"
    assert rule_d_sources(good, {"php/lib/Service/FileAccess.php": helper}) == [
        "d: php/lib/Service/FileAccess.php contains IAppConfig"
    ]
    assert rule_d_sources("<?php\n", {}) == ["d: GatewayController has no getFileHead"]


def test_self_e_fires_when_the_patch_leaves_its_place(tree: Path) -> None:
    shutil.copy(tree / PATCH, tree / "backend" / "src" / PATCH_NAME)
    (tree / "backend" / "ci").mkdir()
    _append(tree, Path("backend/Dockerfile"), "COPY ci/leak-control /app/leak\n")
    _append(tree, WORKFLOWS / "docker.yml", f"# git apply {PATCH_NAME}\n")
    _append(tree, WORKFLOWS / "release.yml", "# leak-control\n")
    (tree / PATCH).unlink()

    assert rule_e(tree) == [
        f"e: {PATCH.as_posix()} is missing",
        f"e: a patch outside {PATCH_DIR.as_posix()}: backend/src/{PATCH_NAME}",
        "e: the build context backend/ holds ci/ or leak-control/",
        "e: backend/Dockerfile names leak",
        "e: backend/Dockerfile names ci/",
        "e: the workflow docker.yml names the control leg or its patch",
        "e: the workflow release.yml names the control leg or its patch",
    ]


GOOD_KEYED = """
def _validated(ref, result):
    if result.error is not None:
        return result.error
    sha, head = result.sha256, result.head_sha256
    return sha, head


class Capture:
    async def _download(self, ref, reader):
        result = await self._fetch(ref.file_id, reader, self._directory, ref.size, self._max_bytes)
        checked = _validated(ref, result)
        sha, head = checked
        return await run_locked(self._services, lambda: store.mark_keyed(ref, sha, head, self._now()))
"""


def _keyed(source: str) -> list[str]:
    return mark_keyed_findings({CAPTURE.as_posix(): source})


def test_self_f0_fires_on_a_content_that_is_not_the_one_of_the_own_fetch() -> None:
    wrong = "f0: mark_keyed gets a hash that is not the one of the fetch of the same reference"
    assert _keyed(GOOD_KEYED) == []
    foreign = GOOD_KEYED.replace("sha, head = checked", "sha, head = sibling.sha256, sibling.head")
    assert _keyed(foreign) == [wrong]
    other_file = GOOD_KEYED.replace("self._fetch(ref.file_id,", "self._fetch(sibling.file_id,")
    assert _keyed(other_file) == [wrong]
    other_reference = GOOD_KEYED.replace("store.mark_keyed(ref, sha,", "store.mark_keyed(other, sha,")
    assert _keyed(other_reference) == [wrong]
    not_fetched = GOOD_KEYED.replace(
        "await self._fetch(ref.file_id, reader, self._directory, ref.size, self._max_bytes)",
        "self._known[ref.prefilter_key]",
    )
    assert _keyed(not_fetched) == [wrong]
    swapped = GOOD_KEYED.replace(
        "sha, head = result.sha256, result.head_sha256", "sha, head = ref.etag, result.head_sha256"
    )
    assert _keyed(swapped) == ["f0: _validated does not hand out the hashes of the fetch result unchanged"]
    assert mark_keyed_findings({"backend/src/audio_video_search_backend/api/x.py": GOOD_KEYED}) == [
        "f0: backend/src/audio_video_search_backend/api/x.py calls mark_keyed"
    ]
    assert _keyed("x = 1\n") == [
        "f0: _validated does not hand out the hashes of the fetch result unchanged",
        "f0: nothing calls mark_keyed",
    ]


def test_self_f_reads_the_sql_texts() -> None:
    name = REPO.as_posix()

    def found(statement: str, constant: str = "_X") -> list[str]:
        return sql_findings({name: f'{constant} = """{statement}"""\n'})

    assert found("UPDATE file_ref SET media_id = :m WHERE file_id = :f") == [f"f: {name}: _X sets media_id on file_ref"]
    assert found("UPDATE file_ref SET media_id = :m WHERE file_id = :f", "_KEY_REF") == []
    assert found("UPDATE file_ref SET media_id = :m WHERE file_id = :f", "_ATTACH_REF") == []
    assert found("UPDATE file_ref SET media_id = NULL, stage = 'pending' WHERE file_id = :f") == []
    assert found("UPDATE file_ref SET stage = 'keyed' WHERE file_id = :f AND media_id IS NOT NULL") == []
    assert found("UPDATE file_ref SET next_try_at = NULL WHERE prefilter_key = :p") == [
        f"f: {name}: _X is an UPDATE with prefilter_key in its WHERE clause"
    ]
    assert found("UPDATE file_ref SET prefilter_key = :p WHERE file_id = :f") == []
    assert found("SELECT media_id FROM file_ref WHERE prefilter_key = :p") == []
    assert found("INSERT INTO file_ref (file_id, media_id) VALUES (:f, NULL)") == []
    assert found("INSERT INTO file_ref (file_id, media_id) VALUES (:f, :m)") == [
        f"f: {name}: _X inserts a media_id into file_ref"
    ]
    assert found(
        "INSERT INTO file_ref (file_id, media_id) VALUES (:f, NULL) "
        "ON CONFLICT (file_id) DO UPDATE SET media_id = excluded.media_id"
    ) == [f"f: {name}: _X inserts a media_id into file_ref"]
    assert found("INSERT INTO file_ref (file_id, media_id) VALUES (:f, :m)", "_UPSERT_FILE_REF") == []
    assert found("INSERT INTO file_ref (file_id, media_id) SELECT file_id, media_id FROM other") == [
        f"f: {name}: _X inserts a media_id into file_ref"
    ]
    # In another module even the name of a writer does not help.
    other = "backend/src/audio_video_search_backend/worker/x.py"
    assert sql_findings({other: '_KEY_REF = "UPDATE file_ref SET media_id = :m WHERE file_id = :f"\n'}) == [
        f"f: {other}: _KEY_REF sets media_id on file_ref"
    ]


def test_self_f_holds_each_writer_to_its_method(tree: Path) -> None:
    _append(
        tree,
        REPO,
        "\n\ndef shortcut(connection: sqlite3.Connection) -> None:\n    connection.execute(_ATTACH_REF, {})\n",
    )
    _append(tree, CAPTURE, "\n\ndef seed(store: object) -> None:\n    store.upsert_file_ref(1, 2)\n")
    _append(
        tree,
        PACKAGE / "worker" / "intake.py",
        "\n\ndef hang(store: object) -> None:\n    store.attach_by_proof(1, 2, 'e')\n",
    )

    findings = scan(tree)

    assert "f: _ATTACH_REF is used outside attach_by_proof" in findings
    assert f"f: {CAPTURE.as_posix()} calls upsert_file_ref, the unconditional write of the tests" in findings
    assert f"c: {(PACKAGE / 'worker' / 'intake.py').as_posix()} calls attach_by_proof" in findings


def test_self_f_wants_a_conditional_attach(tree: Path) -> None:
    _edit(tree, REPO, "AND media_id IS NULL AND stage = 'fetching'", "AND stage = 'fetching'")

    assert "f: attach_by_proof is not conditional on media_id is null" in scan(tree)
