"""Static gates over the PHP app, the local stand-in for a PHP toolchain.

The development machine has no PHP, so ``php -l`` and phpunit run in CI only
(``.github/workflows/php.yml``). What can be decided by reading the sources is
decided here, on every local test run, so a broken trust boundary does not
wait for a push to turn red.

The fourteen rules:

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
12. ``getDistinctMounts(``, ``getByAncestorInStorage(`` and the media type
    query on ``mimetypes`` appear in ``StorageService.php`` only: event, crawl,
    reconcile and diagnosis ask one place what lies in a mount (RESEARCH,
    Pitfall 10).
13. Nothing the container gets from the PHP app carries a key ``path``,
    ``name``, ``mountPoint`` or ``host``: not the rows of
    ``QueueService::describe``, not the answers of an ExApp route, not a body
    ``ExAppService`` sends (T-02-23).
14. The exclusions are decided in ``ExclusionService.php`` only: no other file
    under ``php/lib`` defines a method whose name begins with ``isExcluded``
    or names one of the four list keys, so no rule is compared a second way.
    And the three checks stay where plan 02-16 put them (T-02-57, T-02-58):
    ``QueueService::admissible`` asks ``isExcluded`` and the hand over goes
    through ``admissible``, both gateway routes ask ``isExcludedFile`` before
    they resolve or open anything, and ``Provider::search`` asks
    ``isExcludedUser`` before the first call that could reach the container.

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
        "any",
        "atLeast",
        "atLeastOnce",
        "atMost",
        "count",
        "dataName",
        "exactly",
        "dataSetAsString",
        "groups",
        "name",
        "nameWithDataSet",
        "never",
        "numberOfAssertionsPerformed",
        "once",
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
    # The matcher factories are final and static: a data provider of that name is a fatal error.
    assert helpers_shadowing_final_methods("	public static function never(): array {") == ["never"]
    assert helpers_shadowing_final_methods("	public static function neverCapturable(): array {") == []


def test_self_rule11_fires_on_a_hidden_rule_without_an_id() -> None:
    assert weak_hidden_rules(".avs-admin [hidden] {\n\tdisplay: none;\n}") == [".avs-admin [hidden]"]
    assert weak_hidden_rules("#avs-admin [hidden] {\n\tdisplay: none;\n}") == []


# -- rules 12 and 13 ----------------------------------------------------------------

MOUNT_HOME = "StorageService.php"
MOUNT_NEEDLES = ("getDistinctMounts(", "getByAncestorInStorage(", "->from('mimetypes')")
FORBIDDEN_KEYS = ("path", "name", "mountPoint", "host")
# An array key in a literal ('path' => ...), a write ($item['path'] = ...) or a
# list entry of a key constant (ITEM_KEYS = [..., 'path', ...]).
_FORBIDDEN_KEY = re.compile(
    r"""(?:(['"])(?P<a>path|name|mountPoint|host)\1\s*=>)"""
    r"""|(?:\[\s*(['"])(?P<b>path|name|mountPoint|host)\3\s*\]\s*=(?!=))"""
)
_KEY_CONSTANT = re.compile(r"const\s+\w*KEYS\s*=\s*\[(?P<body>[^\]]*)\]")
CONTAINER_FACING = ("QueueService.php", PROXY_HOME)


def mount_lookups_outside_home(sources: dict[str, str]) -> list[str]:
    """Files other than StorageService.php that enumerate mounts, files or media types."""
    return sorted({name for needle in MOUNT_NEEDLES for name in misplaced(sources, needle, MOUNT_HOME)})


def container_facing(sources: dict[str, str]) -> dict[str, str]:
    """The sources whose arrays reach the container: ExApp routes, describe, ExAppService."""
    return {
        name: text for name, text in sources.items() if EXAPP_ATTRIBUTE in text or Path(name).name in CONTAINER_FACING
    }


def forbidden_keys(source: str) -> list[str]:
    """The keys of FORBIDDEN_KEYS a source writes into an array or lists as a key constant."""
    found = [match.group("a") or match.group("b") for match in _FORBIDDEN_KEY.finditer(source)]
    for constant in _KEY_CONSTANT.finditer(source):
        found += [key for key in FORBIDDEN_KEYS if re.search(rf"""['"]{key}['"]""", constant.group("body"))]
    return found


def test_rule12_mounts_files_and_media_types_are_enumerated_in_storage_service_only() -> None:
    sources = _lib_sources()
    storage = sources.get("php/lib/Service/StorageService.php", "")
    assert all(needle in storage for needle in MOUNT_NEEDLES), "StorageService lost one of its enumerations"
    assert mount_lookups_outside_home(sources) == []


def test_rule13_nothing_the_container_gets_carries_a_path_or_a_name() -> None:
    facing = container_facing(_lib_sources())
    assert "php/lib/Service/QueueService.php" in facing
    assert "php/lib/Controller/QueueController.php" in facing
    findings = {name: forbidden_keys(text) for name, text in facing.items()}
    assert {name: keys for name, keys in findings.items() if keys} == {}


def test_self_rule12_fires_on_a_second_mount_enumeration() -> None:
    sources = _lib_sources()
    sources["php/lib/BackgroundJobs/Other.php"] = "$this->fileAccess->getDistinctMounts([], true);"
    sources["php/lib/Service/Other.php"] = "$qb->select('id')->from('mimetypes');"

    assert mount_lookups_outside_home(sources) == ["php/lib/BackgroundJobs/Other.php", "php/lib/Service/Other.php"]


def test_self_rule13_fires_on_a_path_key_in_queue_service() -> None:
    sources = _lib_sources()
    name = "php/lib/Service/QueueService.php"
    assert forbidden_keys(sources[name]) == []
    staged = [
        "$item['path'] = $entry->getPath();",
        "return ['fileId' => $id, 'name' => $file->getName()];",
        "public const ITEM_KEYS = ['queueId', 'mountPoint'];",
        '$answer["host"] = $host;',
    ]
    for line in staged:
        assert len(forbidden_keys(sources[name] + "\n" + line)) == 1, line
    # A comparison or a variable of that name is no key.
    assert forbidden_keys("if ($row['path'] === $x) { $path = 1; }") == []


# -- rule 14 ------------------------------------------------------------------------

EXCLUSION_HOME = "ExclusionService.php"
EXCLUSION_LISTS = ("excluded_users", "excluded_groups", "excluded_folders", "excluded_mounts")
EXCLUSION_QUESTIONS = ("isExcluded", "isExcludedFile", "isExcludedUser")
QUEUE_SERVICE = "php/lib/Service/QueueService.php"
GATEWAY = "php/lib/Controller/GatewayController.php"
SEARCH_PROVIDER = "php/lib/Search/Provider.php"
_EXCLUSION_DEFINITION = re.compile(r"function\s+(isExcluded\w*)\s*\(")
# Per method: the question to the exclusions and what must not come before it.
EXCLUSION_CHECKS = (
    (QUEUE_SERVICE, "admissible", "$this->exclusions->isExcluded(", ("->storageCapturable(", "->find(")),
    (GATEWAY, "getFileContents", "$this->exclusions->isExcludedFile(", ("->resolve(", "fopen(", "->actAs(")),
    (GATEWAY, "getFileHead", "$this->exclusions->isExcludedFile(", ("->resolve(", "fopen(", "->actAs(")),
    (SEARCH_PROVIDER, "search", "$this->exclusions->isExcludedUser(", ("->searchAllowed(", "->search(", "->entries(")),
)


def php_code(source: str) -> str:
    """A PHP source without its comments and with every string emptied, so braces can be counted."""
    out: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        pair = source[index : index + 2]
        if pair == "//" or (char == "#" and pair != "#["):
            end = source.find("\n", index)
            index = len(source) if end < 0 else end
        elif pair == "/*":
            end = source.find("*/", index + 2)
            index = len(source) if end < 0 else end + 2
        elif char in "'\"":
            end = index + 1
            while end < len(source) and source[end] != char:
                end += 2 if source[end] == "\\" else 1
            out.append(char + char)
            index = end + 1
        else:
            out.append(char)
            index += 1
    return "".join(out)


def php_method(source: str, method: str) -> str | None:
    """The body of a method, comments and string contents removed, by counting braces."""
    code = php_code(source)
    match = re.search(r"function\s+" + re.escape(method) + r"\s*\(", code)
    if match is None:
        return None
    start = code.find("{", match.end())
    depth = 0
    for index in range(max(start, 0), len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                return code[start : index + 1]
    return None


def second_exclusion_deciders(sources: dict[str, str]) -> list[str]:
    """Files other than ExclusionService.php that define an isExcluded method or name a rule list."""
    findings = []
    for name, text in sorted(sources.items()):
        if Path(name).name == EXCLUSION_HOME:
            continue
        findings += [f"{name} defines {found}" for found in _EXCLUSION_DEFINITION.findall(php_code(text))]
        findings += [f"{name} names {key}" for key in EXCLUSION_LISTS if key in text]
    return findings


def missing_exclusion_checks(sources: dict[str, str]) -> list[str]:
    """The places of EXCLUSION_CHECKS that do not ask the exclusions first, or not at all."""
    findings = []
    for name, method, question, later in EXCLUSION_CHECKS:
        body = php_method(sources.get(name, ""), method)
        if body is None:
            findings.append(f"{name} has no {method}")
            continue
        asked = body.find(question)
        if asked < 0:
            findings.append(f"{name}::{method} does not ask the exclusions")
            continue
        findings += [
            f"{name}::{method} reaches {needle} before the exclusions"
            for needle in later
            if 0 <= body.find(needle) < asked
        ]
    describe = php_method(sources.get(QUEUE_SERVICE, ""), "describeRow")
    if describe is None or "$this->admissible(" not in describe:
        findings.append(f"{QUEUE_SERVICE}::describeRow does not ask admissible again")
    return findings


def test_rule14_the_exclusions_are_decided_in_one_place_and_asked_at_three() -> None:
    sources = _lib_sources()
    home = sources.get(f"php/lib/Service/{EXCLUSION_HOME}", "")
    public = re.findall(r"public\s+function\s+(isExcluded\w*)\s*\(", php_code(home))
    assert sorted(public) == sorted(EXCLUSION_QUESTIONS)
    assert all(key in home for key in EXCLUSION_LISTS), "ExclusionService lost one of its lists"
    assert second_exclusion_deciders(sources) == []
    assert missing_exclusion_checks(sources) == []


def test_self_rule14_fires_on_a_second_place_that_decides_an_exclusion() -> None:
    sources = _lib_sources()
    sources["php/lib/Listener/Other.php"] = (
        "<?php\n// isExcluded() is asked elsewhere\n"
        "private function isExcludedHere(string $path): bool { return str_starts_with($path, 'privat/'); }\n"
    )
    sources["php/lib/Command/Other.php"] = "<?php\n$list = $this->appConfig->getValueString('x', 'excluded_folders');\n"

    assert second_exclusion_deciders(sources) == [
        "php/lib/Command/Other.php names excluded_folders",
        "php/lib/Listener/Other.php defines isExcludedHere",
    ]
    # A call is no definition, and a comment is no code.
    only_asks = {"php/lib/X.php": "<?php\n// function isExcluded(\n$a->isExcluded($b, $c);\n"}
    assert second_exclusion_deciders(only_asks) == []


def _mutated(sources: dict[str, str], name: str, old: str, new: str) -> dict[str, str]:
    assert sources[name].count(old) >= 1, f"{name} no longer holds {old!r}"
    return {**sources, name: sources[name].replace(old, new)}


def test_self_rule14_fires_when_one_of_the_three_checks_is_gone_or_comes_too_late() -> None:
    sources = _lib_sources()

    queue = _mutated(sources, QUEUE_SERVICE, "$this->exclusions->isExcluded(", "$this->nothing(")
    assert missing_exclusion_checks(queue) == [f"{QUEUE_SERVICE}::admissible does not ask the exclusions"]

    # Only named in a comment: the body is read without comments.
    commented = _mutated(
        sources,
        QUEUE_SERVICE,
        "if ($this->exclusions->isExcluded($storageId, $mountRelativePath)) {",
        "// $this->exclusions->isExcluded($storageId, $mountRelativePath)\n\t\tif (false) {",
    )
    assert missing_exclusion_checks(commented) == [f"{QUEUE_SERVICE}::admissible does not ask the exclusions"]

    handover = _mutated(sources, QUEUE_SERVICE, "!$this->admissible(", "!$this->cheaper(")
    assert missing_exclusion_checks(handover) == [f"{QUEUE_SERVICE}::describeRow does not ask admissible again"]

    gateway = _mutated(sources, GATEWAY, "$this->exclusions->isExcludedFile(", "$this->nothing(")
    assert missing_exclusion_checks(gateway) == [
        f"{GATEWAY}::getFileContents does not ask the exclusions",
        f"{GATEWAY}::getFileHead does not ask the exclusions",
    ]

    # Asked, but only after the file was resolved through the user.
    late = _mutated(sources, GATEWAY, "\t\ttry {\n", "\t\ttry {\n\t\t\t$early = $this->resolve($fileId, $userId);\n")
    assert missing_exclusion_checks(late) == [
        f"{GATEWAY}::getFileContents reaches ->resolve( before the exclusions",
        f"{GATEWAY}::getFileHead reaches ->resolve( before the exclusions",
    ]

    provider = _mutated(sources, SEARCH_PROVIDER, "$this->exclusions->isExcludedUser(", "$this->nothing(")
    assert missing_exclusion_checks(provider) == [f"{SEARCH_PROVIDER}::search does not ask the exclusions"]

    asked_late = _mutated(
        sources,
        SEARCH_PROVIDER,
        "\t\t$uid = $user->getUID();\n",
        "\t\t$uid = $user->getUID();\n\t\t$this->exAppService->searchAllowed();\n",
    )
    assert missing_exclusion_checks(asked_late) == [
        f"{SEARCH_PROVIDER}::search reaches ->searchAllowed( before the exclusions"
    ]

    assert missing_exclusion_checks({}) == [
        f"{QUEUE_SERVICE} has no admissible",
        f"{GATEWAY} has no getFileContents",
        f"{GATEWAY} has no getFileHead",
        f"{SEARCH_PROVIDER} has no search",
        f"{QUEUE_SERVICE}::describeRow does not ask admissible again",
    ]


def test_self_rule14_reads_a_method_body_without_comments_and_strings() -> None:
    source = (
        "<?php\nclass X {\n"
        "\tpublic function one(): string {\n\t\t// } not the end\n\t\treturn '} neither';\n\t}\n"
        "\tpublic function two(): void {\n\t\t$this->later();\n\t}\n}\n"
    )
    assert php_method(source, "one") == "{\n\t\t\n\t\treturn '';\n\t}"
    assert php_method(source, "two") == "{\n\t\t$this->later();\n\t}"
    assert php_method(source, "three") is None
