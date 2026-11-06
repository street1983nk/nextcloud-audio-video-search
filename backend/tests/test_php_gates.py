"""Static gates over the PHP app, the local stand-in for a PHP toolchain.

The development machine has no PHP, so ``php -l`` and phpunit run in CI only
(``.github/workflows/php.yml``). What can be decided by reading the sources is
decided here, on every local test run, so a broken trust boundary does not
wait for a push to turn red.

The eleven rules:

1. Every method carrying ``ExAppRequired`` opens with
   ``$foreign = $this->rejectForeignCaller();``. The attribute only answers "is
   this a registered external app"; the comparison against the one backend app
   id is what keeps every other container out (Findling Gate B).
2. No ``PublicPage`` anywhere in ``php/lib``: every route needs a session or
   the signed AppAPI path.
3. ``exAppRequest(`` appears in ``ExAppService.php`` only, and there once: one
   place that talks to the container, one timeout, one way to fail.
4. ``->getFirstNodeById(`` appears in ``FileAccess.php`` only: the readability
   question is asked in exactly one place.
5. No ``error_log``, ``var_dump`` or ``print_r`` in ``php/lib``.
6. A logger call never carries ``getPath()``, ``getName()`` or ``$path``:
   the Nextcloud log is not a private place.
7. Every ``.php`` file starts with ``<?php`` and ``declare(strict_types=1);``.
8. No U+2013 or U+2014 anywhere under ``php/``.
9. ``php/composer.json`` is valid JSON and maps both app namespaces.
10. No helper in ``php/tests`` is named like a final method of PHPUnit's TestCase.
11. Every ``[hidden]`` rule under ``php/css`` hangs off an id: the server rule
    ``button:not(...) > span[class^=icon-] { display: block }`` outranks two
    classes and showed a hidden spinner (``!important`` is ruled out by the
    UI-SPEC).

Each rule has a mutated sample that has to make it fire, so a gate whose body
was deleted cannot stay green. The real tree is additionally held to a floor
(the files this plan writes exist and carry their one call each), so the gates
cannot pass on an empty directory.
"""

import json
import re
from pathlib import Path

from tests.conftest import REPO_ROOT

PHP_ROOT = REPO_ROOT / "php"
LIB = PHP_ROOT / "lib"
SKIPPED_DIRECTORIES = {"vendor", "node_modules", ".phpunit.cache"}

GUARD_STATEMENT = "$foreign = $this->rejectForeignCaller();"
EXAPP_ATTRIBUTE = "ExAppRequired"
FORBIDDEN_ATTRIBUTE = "PublicPage"
PROXY_CALL = "exAppRequest("
PROXY_HOME = "ExAppService.php"
LOOKUP_CALL = "->getFirstNodeById("
LOOKUP_HOME = "FileAccess.php"
DEBUG_OUTPUT = ("error_log", "var_dump", "print_r")
LEAKING_LOG_ARGUMENTS = re.compile(r"getPath\(\)|getName\(\)|\$path\b")
DASHES = ("\u2013", "\u2014")
PHP_HEADER = re.compile(r"\A<\?php\r?\n(?:\r?\n)*declare\(strict_types=1\);")

_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_HIDDEN_RULE = re.compile(r"([^{}]*\[hidden\])\s*\{")
_FUNCTION = re.compile(r"^\s*(?:public|protected|private)\s+(?:static\s+)?function\s+(\w+)\s*\(")
_LOGGER_CALL = re.compile(r"->logger->(?:debug|info|notice|warning|error|critical|alert|emergency|log)\(")
_NOT_A_STATEMENT = ("//", "/*", "*", "#")


def php_files(root: Path) -> list[Path]:
    """Every .php file below root, without dependency and cache directories."""
    return sorted(
        path for path in root.rglob("*.php") if not SKIPPED_DIRECTORIES.intersection(path.relative_to(root).parts)
    )


def text_files(root: Path) -> list[Path]:
    """Every file below root that reads as UTF-8 text, same exclusions."""
    found = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or SKIPPED_DIRECTORIES.intersection(path.relative_to(root).parts):
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        found.append(path)
    return found


# -- rule 1 ---------------------------------------------------------------------


def _attributes_above(lines: list[str], index: int) -> list[str]:
    """The attribute lines directly above a method; the docblock is the wall."""
    collected = []
    cursor = index - 1
    while cursor >= 0 and lines[cursor].strip().startswith("#["):
        collected.append(lines[cursor].strip())
        cursor -= 1
    return collected


def _first_statement(lines: list[str], index: int) -> str:
    """The first line inside the body of the method declared at index."""
    start = len(lines)
    for cursor in range(index, len(lines)):
        if lines[cursor].rstrip().endswith("{"):
            start = cursor + 1
            break
    for line in lines[start:]:
        stripped = line.strip()
        if stripped and not stripped.startswith(_NOT_A_STATEMENT):
            return stripped
    return ""


def unguarded_exapp_methods(source: str) -> list[str]:
    """Methods with ExAppRequired whose first statement is not the guard."""
    lines = source.splitlines()
    findings = []
    for index, line in enumerate(lines):
        match = _FUNCTION.match(line)
        if match is None:
            continue
        if not any(EXAPP_ATTRIBUTE in attribute for attribute in _attributes_above(lines, index)):
            continue
        if _first_statement(lines, index) != GUARD_STATEMENT:
            findings.append(match.group(1))
    return findings


def exapp_methods(source: str) -> list[str]:
    """Every method that carries the ExAppRequired attribute."""
    lines = source.splitlines()
    return [
        match.group(1)
        for index, line in enumerate(lines)
        if (match := _FUNCTION.match(line)) is not None
        and any(EXAPP_ATTRIBUTE in attribute for attribute in _attributes_above(lines, index))
    ]


# -- rules 2 to 5 ---------------------------------------------------------------


def misplaced(sources: dict[str, str], needle: str, home: str) -> list[str]:
    """Files other than home that contain needle."""
    return sorted(name for name, text in sources.items() if needle in text and Path(name).name != home)


def debug_output_calls(source: str) -> list[str]:
    """The debug printers a source calls."""
    return [name for name in DEBUG_OUTPUT if re.search(rf"\b{name}\s*\(", source)]


# -- rule 6 ---------------------------------------------------------------------


def _call_arguments(source: str, open_paren: int) -> str:
    """The text between an opening parenthesis and its partner, strings respected."""
    depth = 0
    quote = ""
    index = open_paren
    while index < len(source):
        char = source[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[open_paren + 1 : index]
        index += 1
    return source[open_paren + 1 :]


def leaking_log_calls(source: str) -> list[str]:
    """Logger calls whose arguments carry a path or a file name."""
    findings = []
    for match in _LOGGER_CALL.finditer(source):
        arguments = _call_arguments(source, match.end() - 1)
        if LEAKING_LOG_ARGUMENTS.search(arguments):
            findings.append(" ".join(arguments.split())[:120])
    return findings


def logger_call_count(source: str) -> int:
    """How many logger calls the scanner recognises in a source."""
    return len(_LOGGER_CALL.findall(source))


# -- rules 7 and 8 --------------------------------------------------------------


def lacks_strict_header(source: str) -> bool:
    """True when the file does not open with <?php and declare(strict_types=1)."""
    return PHP_HEADER.match(source) is None


def dashes_in(source: str) -> list[str]:
    """The forbidden dash characters a text contains, by code point."""
    return [f"U+{ord(dash):04X}" for dash in DASHES if dash in source]


# -- the real tree ----------------------------------------------------------------


def _lib_sources() -> dict[str, str]:
    return {path.relative_to(REPO_ROOT).as_posix(): path.read_text(encoding="utf-8") for path in php_files(LIB)}


def test_the_tree_carries_the_files_the_gates_are_about() -> None:
    """Anti vacuum: the gates below must have something to judge."""
    service = LIB / "Service" / PROXY_HOME
    access = LIB / "Service" / LOOKUP_HOME
    gateway = LIB / "Controller" / "GatewayController.php"
    for path in (service, access, gateway):
        assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"
    assert service.read_text(encoding="utf-8").count(PROXY_CALL) == 1
    assert LOOKUP_CALL in access.read_text(encoding="utf-8")
    assert exapp_methods(gateway.read_text(encoding="utf-8")), "the gateway route lost ExAppRequired"
    assert logger_call_count(gateway.read_text(encoding="utf-8")) >= 2


def test_rule1_every_exapp_route_opens_with_the_foreign_caller_guard() -> None:
    findings = {name: unguarded_exapp_methods(text) for name, text in _lib_sources().items()}
    assert {name: methods for name, methods in findings.items() if methods} == {}


def test_rule2_no_public_page_in_lib() -> None:
    assert [name for name, text in _lib_sources().items() if FORBIDDEN_ATTRIBUTE in text] == []


def test_rule3_the_container_is_called_from_exapp_service_only() -> None:
    assert misplaced(_lib_sources(), PROXY_CALL, PROXY_HOME) == []


def test_rule4_the_node_lookup_lives_in_file_access_only() -> None:
    assert misplaced(_lib_sources(), LOOKUP_CALL, LOOKUP_HOME) == []


def test_rule5_no_debug_output_in_lib() -> None:
    findings = {name: debug_output_calls(text) for name, text in _lib_sources().items()}
    assert {name: calls for name, calls in findings.items() if calls} == {}


def test_rule6_no_path_or_file_name_in_a_log_call() -> None:
    findings = {name: leaking_log_calls(text) for name, text in _lib_sources().items()}
    assert {name: calls for name, calls in findings.items() if calls} == {}


def test_rule7_every_php_file_is_strict() -> None:
    files = php_files(PHP_ROOT)
    assert files, "no PHP file found"
    assert [
        path.relative_to(REPO_ROOT).as_posix()
        for path in files
        if lacks_strict_header(path.read_text(encoding="utf-8"))
    ] == []


def test_rule8_no_dash_characters_under_php() -> None:
    findings = {
        path.relative_to(REPO_ROOT).as_posix(): dashes_in(path.read_text(encoding="utf-8"))
        for path in text_files(PHP_ROOT)
    }
    assert {name: found for name, found in findings.items() if found} == {}


COMPOSER_NAMESPACES = {"OCA\\AudioVideoSearch\\": "lib/"}
COMPOSER_TEST_NAMESPACES = {"OCA\\AudioVideoSearch\\Tests\\": "tests/"}


def composer_namespaces(text: str) -> tuple[dict[str, str], dict[str, str]]:
    """The psr-4 maps of a composer.json; raises on text that is not JSON."""
    data = json.loads(text)
    return data["autoload"]["psr-4"], data["autoload-dev"]["psr-4"]


# Final methods of PHPUnit\Framework\TestCase (11.5): a test helper with one of
# these names is a fatal error the moment phpunit loads the class.
FINAL_TESTCASE_METHODS = frozenset(
    {
        "count",
        "dataName",
        "dataSetAsString",
        "groups",
        "name",
        "nameWithDataSet",
        "numberOfAssertionsPerformed",
        "providedData",
        "result",
        "run",
        "size",
        "status",
        "usesDataProvider",
        "valueObjectForEvents",
    }
)


def helpers_shadowing_final_methods(source: str) -> list[str]:
    """Names of methods in source that PHPUnit's TestCase declares final."""
    return [
        match.group(1)
        for line in source.splitlines()
        if (match := _FUNCTION.match(line)) and match.group(1) in FINAL_TESTCASE_METHODS
    ]


def test_rule10_no_test_helper_shadows_a_final_testcase_method() -> None:
    findings = {
        path.relative_to(REPO_ROOT).as_posix(): found
        for path in php_files(PHP_ROOT / "tests")
        if (found := helpers_shadowing_final_methods(path.read_text(encoding="utf-8")))
    }
    assert findings == {}


def weak_hidden_rules(source: str) -> list[str]:
    """Selectors of ``[hidden]`` rules in source that do not hang off an id."""
    rules = _CSS_COMMENT.sub("", source)
    return [selector.strip() for selector in _HIDDEN_RULE.findall(rules) if "#" not in selector]


def test_rule11_every_hidden_rule_wins_over_the_server_styles() -> None:
    sheets = sorted((PHP_ROOT / "css").glob("*.css"))
    assert sheets, "php/css carries no style sheet"
    findings = {path.name: found for path in sheets if (found := weak_hidden_rules(path.read_text(encoding="utf-8")))}
    assert findings == {}
    assert all(_HIDDEN_RULE.search(path.read_text(encoding="utf-8")) for path in sheets)


def test_rule9_composer_json_parses_and_maps_the_app_namespaces() -> None:
    # A copy that lost one backslash ("OCA\AudioVideoSearch") is invalid JSON
    # and broke every composer step in CI; this catches it before a push.
    autoload, autoload_dev = composer_namespaces((PHP_ROOT / "composer.json").read_text(encoding="utf-8"))
    assert autoload == COMPOSER_NAMESPACES
    assert autoload_dev == COMPOSER_TEST_NAMESPACES


# -- the self tests: every rule has to fire on a staged violation ----------------

GUARDED_ROUTE = """
	#[\\OCP\\AppFramework\\Http\\Attribute\\ExAppRequired]
	#[\\OCP\\AppFramework\\Http\\Attribute\\NoCSRFRequired]
	public function get(int $fileId): DataResponse {
		// a comment first is fine
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}
		return new DataResponse([]);
	}
"""


def test_self_rule1_fires_on_a_route_without_the_guard_and_passes_the_guarded_one() -> None:
    assert unguarded_exapp_methods(GUARDED_ROUTE) == []
    late = GUARDED_ROUTE.replace(
        "// a comment first is fine", "$this->logger->info('Audio & Video Search: before the guard');"
    )
    missing = GUARDED_ROUTE.replace(GUARD_STATEMENT, "$x = 1;")
    assert unguarded_exapp_methods(late) == ["get"]
    assert unguarded_exapp_methods(missing) == ["get"]
    # A method without the attribute is not judged.
    plain = GUARDED_ROUTE.replace("#[\\OCP\\AppFramework\\Http\\Attribute\\ExAppRequired]\n", "")
    assert unguarded_exapp_methods(plain.replace(GUARD_STATEMENT, "$x = 1;")) == []


def test_self_rule2_fires_on_a_public_page_attribute() -> None:
    sources = {"php/lib/Controller/X.php": "#[PublicPage]\npublic function x(): void {}"}
    assert [name for name, text in sources.items() if FORBIDDEN_ATTRIBUTE in text] == ["php/lib/Controller/X.php"]


def test_self_rule3_fires_on_a_second_caller_of_the_proxy() -> None:
    sources = {
        "php/lib/Service/ExAppService.php": "$appApi->exAppRequest($id);",
        "php/lib/Search/Provider.php": "$appApi->exAppRequest($id);",
    }
    assert misplaced(sources, PROXY_CALL, PROXY_HOME) == ["php/lib/Search/Provider.php"]


def test_self_rule4_fires_on_a_lookup_outside_file_access() -> None:
    sources = {
        "php/lib/Service/FileAccess.php": "$folder->getFirstNodeById($id);",
        "php/lib/Command/SampleCommand.php": "$root->getFirstNodeById($id);",
    }
    assert misplaced(sources, LOOKUP_CALL, LOOKUP_HOME) == ["php/lib/Command/SampleCommand.php"]


def test_self_rule5_fires_on_each_debug_printer() -> None:
    for name in DEBUG_OUTPUT:
        assert debug_output_calls(f"{name}($value);") == [name]
    assert debug_output_calls("$this->logger->debug('fine');") == []


def test_self_rule6_fires_on_a_path_or_a_name_in_a_log_call() -> None:
    staged = [
        "$this->logger->warning('x', ['file' => $file->getPath()]);",
        "$this->logger->info('x', [\n\t'name' => $node->getName(),\n]);",
        "$this->logger->error('x', ['p' => $path]);",
    ]
    for source in staged:
        assert len(leaking_log_calls(source)) == 1, source
    clean = "$this->logger->warning('x (y)', ['fileId' => $fileId]); $path = $file->getPath();"
    assert leaking_log_calls(clean) == []
    assert logger_call_count(clean) == 1


def test_self_rule7_fires_on_a_missing_or_late_strict_declaration() -> None:
    assert not lacks_strict_header("<?php\n\ndeclare(strict_types=1);\n\nnamespace X;\n")
    assert lacks_strict_header("<?php\n\nnamespace X;\n")
    assert lacks_strict_header("<?php\nnamespace X;\ndeclare(strict_types=1);\n")
    assert lacks_strict_header(" <?php\n\ndeclare(strict_types=1);\n")


def test_self_rule8_fires_on_both_dashes() -> None:
    assert dashes_in("a \u2013 b \u2014 c") == ["U+2013", "U+2014"]
    assert dashes_in("a - b \u00b7 c \u2026") == []


def test_self_rule9_fires_on_a_lost_backslash() -> None:
    broken = r'{"autoload": {"psr-4": {"OCA\AudioVideoSearch\\": "lib/"}}, "autoload-dev": {"psr-4": {}}}'
    try:
        composer_namespaces(broken)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("a single backslash before a letter has to be rejected")


def test_self_rule10_fires_on_a_helper_named_status() -> None:
    assert helpers_shadowing_final_methods("\tprivate function status(array $value): IResponse {") == ["status"]
    assert helpers_shadowing_final_methods("\tprivate function statusResponse(array $value): IResponse {") == []


def test_self_rule11_fires_on_a_hidden_rule_without_an_id() -> None:
    assert weak_hidden_rules(".avs-admin [hidden] {\n\tdisplay: none;\n}") == [".avs-admin [hidden]"]
    assert weak_hidden_rules("#avs-admin [hidden] {\n\tdisplay: none;\n}") == []
