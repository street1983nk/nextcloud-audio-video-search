"""Static gates over the admin page of phase 5 (plan 05-09, 05-UI-SPEC.md surface 3).

The development machine has no PHP and no browser in the local suite, so what
the UI contract says in so many words is read out of the files:

* template: the three new sections after the connection section, in the
  profile section banner before proposal before options (checker flag), every
  id of the UI-SPEC, the lock reason outside the label, the server radio,
  licence links with fixed targets, no path, no host and no other address;
* CSS: server variables only, the 24 px indent of the component list (checker
  flag), the hidden rule behind the three new ids;
* Admin.php: the container is asked once per page view, the amounts go
  through ResourceFormat, the zone rule lives in one place;
* admin.js: the route, no markup from a string, the polling rules (a chain of
  timeouts every 5 s, only on a visible page, never two at once, no more
  after three failures), every word out of the template;
* the lists of profiles, models and model states are the same in
  ExAppService, in the template and in the script;
* the rounding of an amount is the same rule in PHP and in the script, held
  to the same rows (PHPUnit runs them through ResourceFormat, this file runs
  them through the function of admin.js under node);
* every text of the page stands in all four catalogues, and every approved
  text of phase 5 is used.

Every rule is a function over the text with a staged violation that has to
make it fire.
"""

import re
from pathlib import Path

from tests.conftest import REPO_ROOT
from tests.test_l10n_phase5 import ROWS
from tests.test_trilingual import PHP_L10N, PHP_LANGUAGES, load_catalogues, source_strings
from tests.test_ui_assets import FUNCTIONAL_COLOUR, IMPORTANT, NO_OUTLINE, STYLE_ATTRIBUTE, findings

PHP_ROOT = REPO_ROOT / "php"
TEMPLATE = PHP_ROOT / "templates" / "admin.php"
SCRIPT = PHP_ROOT / "js" / "admin.js"
STYLE = PHP_ROOT / "css" / "admin.css"
ADMIN = PHP_ROOT / "lib" / "Settings" / "Admin.php"
SERVICE = PHP_ROOT / "lib" / "Service" / "ExAppService.php"
FORMAT = PHP_ROOT / "lib" / "Service" / "ResourceFormat.php"
PHPUNIT = PHP_ROOT / "tests" / "Unit" / "AdminSettingsTest.php"

SECTIONS = ("avs-admin", "avs-profile", "avs-compute", "avs-models")

# Banner (R2, R3) before the proposal (T37) before the minimum (T48) before the options.
PROFILE_ORDER = (
    'id="avs-profile-low"',
    'id="avs-profile-fallback"',
    'class="avs-res__intro"',
    'id="avs-profile-minimum"',
    'class="avs-res__options"',
)

# The ids of the structure trees of the UI-SPEC, as the template writes them.
REQUIRED_IDS = (
    'id="avs-profile"',
    'id="avs-compute"',
    'id="avs-models"',
    'id="avs-profile-intro"',
    'id="avs-profile-<?php p($id); ?>"',
    'id="avs-profile-<?php p($id); ?>-desc"',
    'id="avs-profile-<?php p($id); ?>-need"',
    'id="avs-profile-<?php p($id); ?>-lock"',
    'id="avs-profile-status"',
    'id="avs-compute-form"',
    'id="avs-threads"',
    'id="avs-threads-hint"',
    'id="avs-threads-error"',
    'id="avs-window-always"',
    'id="avs-window-set"',
    'id="avs-window-fields"',
    'id="avs-window-start"',
    'id="avs-window-end"',
    'id="avs-window-zone"',
    'id="avs-window-hint"',
    'id="avs-window-error"',
    'id="avs-window-state"',
    'id="avs-compute-save"',
    'id="avs-compute-status"',
    'id="avs-model-<?php p($id); ?>-name"',
    'id="avs-model-<?php p($id); ?>-text"',
    'id="avs-models-live"',
    'id="avs-offline"',
    'id="avs-offline-status"',
    'id="avs-offline-hint"',
    'id="avs-offline-forced"',
)

HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,6}\b")

# The only addresses the page may carry (UI-SPEC, licence table, T89, T94).
ALLOWED_ADDRESSES = frozenset(
    {
        "https://creativecommons.org/licenses/by/4.0/",
        "https://opensource.org/license/mit",
        "https://www.apache.org/licenses/LICENSE-2.0",
        "https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html",
        "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
        "https://github.com/street1983nk/nextcloud-audio-video-search#offline",
        "https://github.com/street1983nk/nextcloud-audio-video-search/blob/main/THIRD-PARTY.md",
    }
)
ADDRESS = re.compile(r"""[a-z][a-z0-9+.-]*://[^'"\s<]+""")
PATH_NEEDLES = ("/nc_app_", "APP_PERSISTENT_STORAGE", "/models/", "huggingface", "hf.co", "localhost")
# What a link of the new sections may point to: a slot of $say or one of the two fixed targets.
LINK_TARGETS = frozenset({"$found[1]", "$readmeOffline", "$thirdParty"})
# The whole opening tag: the "?>" of a PHP block inside it does not end it.
LINK = re.compile(r"<a\b(?:\?>|[^>])*>")
LINK_TARGET = re.compile(r'href="<\?php p\(([^)]*)\); \?>"')
OCC_COMMAND = '<code class="avs-admin__command">occ audio_video_search:models --verify</code>'

MODEL_NAMES = {
    "parakeet": "Parakeet TDT 0.6B v3",
    "silero": "Silero VAD",
    "whisper-turbo": "Whisper large-v3-turbo",
    "whisper-large-v3": "Whisper large-v3",
}

_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_LABEL = re.compile(r"<label\b.*?</label>", re.DOTALL)
_RADIO = re.compile(r'<input type="radio"[^>]*>')
_QUOTED = re.compile(r"'([A-Za-z0-9_-]+)'")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def new_part(template: str) -> str:
    """The template from the profile section on: what plan 05-09 added."""
    start = template.find('<div id="avs-profile"')
    return template[start:] if start >= 0 else ""


def profile_section(template: str) -> str:
    """The markup of the profile section, up to the section that follows it."""
    start = template.find('<div id="avs-profile"')
    end = template.find('<div id="avs-compute"')
    return template[start:end] if 0 <= start < end else ""


# -- the template -------------------------------------------------------------------


def section_findings(template: str) -> list[str]:
    """The four sections, each once and in the order of the UI-SPEC."""
    found = [
        f"{name} stands {template.count(f'id="{name}"')} times"
        for name in SECTIONS
        if template.count(f'id="{name}"') != 1
    ]
    places = [template.find(f'id="{name}"') for name in SECTIONS]
    if not found and places != sorted(places):
        found.append("sections out of order")
    return found


def profile_order_findings(section: str) -> list[str]:
    """Banner, proposal, minimum and options of the profile section, each once and in this order."""
    found = [f"{marker} stands {section.count(marker)} times" for marker in PROFILE_ORDER if section.count(marker) != 1]
    places = [section.find(marker) for marker in PROFILE_ORDER]
    if not found and places != sorted(places):
        found.append("profile section out of order")
    return found


def missing_ids(template: str) -> list[str]:
    return [marker for marker in REQUIRED_IDS if marker not in template]


def forbidden_findings(style: str, template: str) -> list[str]:
    """Colour values, forced or removed rules in the style sheet; a style attribute or a colour in the template."""
    found = []
    for name, text in (("css", style), ("template", template)):
        found += [f"{name}: {hit}" for hit in findings(HEX_COLOUR, text)]
        found += [f"{name}: {hit}" for hit in findings(FUNCTIONAL_COLOUR, text)]
        found += [f"{name}: {hit}" for hit in findings(IMPORTANT, text)]
        found += [f"{name}: {hit}" for hit in findings(NO_OUTLINE, text)]
    found += [f"template: {hit.strip()}" for hit in findings(STYLE_ATTRIBUTE, template)]
    return found


def address_findings(template: str) -> list[str]:
    """Addresses other than the fixed ones, links to anything else, and words of a path or a host."""
    found = sorted({hit for hit in ADDRESS.findall(template) if hit not in ALLOWED_ADDRESSES})
    found += [needle for needle in PATH_NEEDLES if needle in template]
    for link in LINK.findall(new_part(template)):
        target = LINK_TARGET.search(link)
        if target is None or target.group(1) not in LINK_TARGETS:
            found.append(f"link target: {link}")
        if 'rel="noreferrer noopener"' not in link:
            found.append(f"link without rel: {link}")
        if "target=" in link:
            found.append(f"link with target: {link}")
    return found


def label_findings(template: str) -> list[str]:
    """What keeps the lock reason readable and the radio groups named."""
    found = []
    for label in _LABEL.findall(new_part(template)):
        if "avs-res__lock" in label or "Locked:" in label:
            found.append("lock reason inside a label")
    section = profile_section(template)
    if '<legend class="hidden-visually">' not in section:
        found.append("profile legend not visually hidden")
    if "\t\t\t<legend><?php p($l->t('When to compute')); ?></legend>" not in template:
        found.append("window legend not visible")
    radios = _RADIO.findall(template)
    if len(radios) != 3:
        found.append(f"{len(radios)} radio inputs in the template")
    found += [f"radio without the server class: {radio}" for radio in radios if 'class="radio"' not in radio]
    return found


def test_the_three_sections_follow_the_connection_section() -> None:
    assert section_findings(read(TEMPLATE)) == []


def test_the_profile_section_shows_banner_then_proposal_then_options() -> None:
    section = profile_section(read(TEMPLATE))
    assert section, "no profile section in the template"
    assert profile_order_findings(section) == []


def test_every_id_of_the_ui_spec_is_in_the_template() -> None:
    assert missing_ids(read(TEMPLATE)) == []


def test_no_colour_no_force_no_style_attribute() -> None:
    assert forbidden_findings(read(STYLE), read(TEMPLATE)) == []


def test_the_page_carries_no_path_and_only_the_fixed_addresses() -> None:
    template = read(TEMPLATE)
    assert address_findings(template) == []
    # Every fixed address is really there, and the occ command as code: in
    # the state "wrong checksum, placed" and in the offline hint.
    for address in ALLOWED_ADDRESSES:
        assert template.count(address) == 1, address
    assert template.count(OCC_COMMAND) == 2
    assert template.count("THIRD-PARTY.md") >= 1


def test_the_lock_reason_stands_outside_the_label_and_the_groups_are_named() -> None:
    assert label_findings(read(TEMPLATE)) == []


def test_the_models_carry_their_proper_names() -> None:
    template = read(TEMPLATE)
    for ident, name in MODEL_NAMES.items():
        assert f"'{ident}' => '{name}'," in template, ident


def test_self_template_rules_fire() -> None:
    template = read(TEMPLATE)
    section = profile_section(template)

    # The compute section in front of the profile section.
    swapped = template.replace('id="avs-compute"', "id=X").replace('id="avs-profile"', 'id="avs-compute"', 1)
    assert section_findings(swapped.replace("id=X", 'id="avs-profile"')) == ["sections out of order"]
    assert section_findings(template.replace('<div id="avs-models"', "<div")) == ["avs-models stands 0 times"]

    # The proposal in front of the banners.
    intro = section[section.index('\t\t<p id="avs-profile-intro"') : section.index('\t\t<p id="avs-profile-minimum"')]
    moved = section.replace(intro, "").replace(
        '\t\t<div id="avs-profile-low"', intro + '\t\t<div id="avs-profile-low"', 1
    )
    assert moved != section
    assert profile_order_findings(moved) == ["profile section out of order"]

    assert missing_ids(template.replace('id="avs-models-live"', 'id="avs-live"')) == ['id="avs-models-live"']

    assert forbidden_findings("a { color: #1a2b3c; }", "") == ["css: #1a2b3c"]
    assert forbidden_findings("a { color: rgb(0, 0, 0); }", "") == ["css: rgb("]
    assert forbidden_findings("a { margin: 0 !important; outline: none; }", "") == [
        "css: !important",
        "css: outline: none",
    ]
    assert forbidden_findings("", '<p style="margin: 0">') == ["template: style="]
    assert forbidden_findings("#avs-admin [hidden] { display: none; }", '<a href="x#offline">') == []

    staged = template + '<a href="https://example.org/models/x" rel="noreferrer noopener">x</a>'
    assert "https://example.org/models/x" in address_findings(staged)
    assert "/models/" in address_findings(staged)
    bare = template.replace(
        '<a href="<?php p($thirdParty); ?>" rel="noreferrer noopener">', '<a href="<?php p($thirdParty); ?>">'
    )
    assert address_findings(bare) == ['link without rel: <a href="<?php p($thirdParty); ?>">']
    foreign = template.replace('<a href="<?php p($readmeOffline); ?>"', '<a href="<?php p($modelFolder); ?>"')
    assert len(address_findings(foreign)) == 1
    assert address_findings(foreign)[0].startswith("link target: ")

    inside = template.replace(
        "</span></label>\n\t\t\t\t\t</span>",
        '<span class="avs-res__lock">x</span></span></label>\n\t\t\t\t\t</span>',
    )
    assert inside != template
    assert label_findings(inside) == ["lock reason inside a label"]
    plain = template.replace(
        '<input type="radio" class="radio" id="avs-window-set"', '<input type="radio" id="avs-window-set"'
    )
    assert len(label_findings(plain)) == 1
    assert label_findings(plain)[0].startswith("radio without the server class")


# -- the style sheet ------------------------------------------------------------------


def css_rules(style: str) -> list[tuple[str, str]]:
    """Every rule of a style sheet as (selector list, declarations), comments removed."""
    return [(head.strip(), body) for head, body in _CSS_RULE.findall(_CSS_COMMENT.sub("", style))]


def declarations(style: str, selector: str) -> list[str]:
    """The declarations of every rule whose selector list names selector."""
    return [
        line.strip()
        for head, body in css_rules(style)
        if selector in [part.strip() for part in head.split(",")]
        for line in body.split("\n")
        if line.strip()
    ]


def style_findings(style: str) -> list[str]:
    found = []
    others = declarations(style, ".avs-admin .avs-models__others")
    if "padding-inline-start: calc(var(--default-grid-baseline) * 6);" not in others:
        found.append("component list not indented by 24 px")
    if any("* 5)" in line for line in others):
        found.append("component list still indented by 20 px")
    for selector in (".avs-res__option .avs-res__hint", ".avs-res__option .avs-res__lock"):
        if "padding-inline-start: calc(var(--default-grid-baseline) * 7);" not in declarations(style, selector):
            found.append(f"{selector} not flush under the label text")
    hidden = [head for head, body in css_rules(style) if "[hidden]" in head and "display: none;" in body]
    wanted = {f"#{name} [hidden]" for name in SECTIONS[1:]}
    if not any(wanted <= {part.strip() for part in head.split(",")} for head in hidden):
        found.append("hidden rule of the new sections missing")
    if "accent-color: var(--color-primary-element);" not in declarations(style, ".avs-models__progress"):
        found.append("progress without the accent of the theme")
    return found


def test_the_style_sheet_follows_the_css_table() -> None:
    style = read(STYLE)
    assert style_findings(style) == []
    # The reason for the 28 px that are off the 24 px scale stands beside the rule.
    assert "flush" in style
    assert "Nextcloud 33 to 35" in style


def test_self_style_rules_fire() -> None:
    style = read(STYLE)
    twenty = style.replace(
        "\tpadding-inline-start: calc(var(--default-grid-baseline) * 6);\n\tcolor: var(--color-text-maxcontrast);",
        "\tpadding-inline-start: calc(var(--default-grid-baseline) * 5);\n\tcolor: var(--color-text-maxcontrast);",
    )
    assert twenty != style
    assert style_findings(twenty) == ["component list not indented by 24 px", "component list still indented by 20 px"]
    unhidden = style.replace("#avs-compute [hidden],\n", "")
    assert unhidden != style
    assert style_findings(unhidden) == ["hidden rule of the new sections missing"]
    assert declarations(".a,\n.b {\n\tmargin: 0;\n}\n/* .c { top: 0; } */\n.c { left: 0; }", ".b") == ["margin: 0;"]
    assert declarations(".a { margin: 0; }", ".b") == []


# -- Admin.php and the one place of the zone rule --------------------------------------


def admin_findings(admin: str, controller: str, sources: dict[str, str]) -> list[str]:
    found = []
    if admin.count("->exAppService->resources()") != 1:
        found.append("the container is not asked exactly once")
    if "ResourceFormat::gigabytes(" not in admin:
        found.append("amounts not formatted by ResourceFormat")
    if "$this->initialState->provideInitialState('resources', $resources);" not in admin:
        found.append("no initial state for the script")
    if "ExAppService::withZones($resources, $this->config, " not in admin:
        found.append("the page does not use the zone rule of the routes")
    if "ExAppService::withZones($resources, $this->config, $this->userId())" not in controller:
        found.append("the routes do not use the shared zone rule")
    # The call itself (with its leading backslash), not a sentence that names it.
    keepers = sorted(name for name, text in sources.items() if "\\DateTimeZone::listIdentifiers()" in text)
    if keepers != ["ExAppService.php"]:
        found.append(f"zone list read in {keepers}")
    deciders = sorted(name for name, text in sources.items() if "'default_timezone'" in text)
    if deciders != ["ExAppService.php"]:
        found.append(f"default zone decided in {deciders}")
    return found


def lib_sources() -> dict[str, str]:
    return {path.name: read(path) for path in sorted((PHP_ROOT / "lib").rglob("*.php"))}


def test_the_page_asks_the_container_once_and_shares_the_zone_rule() -> None:
    sources = lib_sources()
    assert len(sources) > 20, "the scan is blind"
    assert admin_findings(read(ADMIN), sources["SettingsController.php"], sources) == []


def test_self_admin_rules_fire() -> None:
    sources = lib_sources()
    admin = read(ADMIN)
    controller = sources["SettingsController.php"]
    twice = admin + "\n$again = $this->exAppService->resources();\n"
    assert admin_findings(twice, controller, sources) == ["the container is not asked exactly once"]
    copied = {**sources, "Admin.php": admin + "\n$zones = \\DateTimeZone::listIdentifiers();\n"}
    assert admin_findings(admin, controller, copied) == ["zone list read in ['Admin.php', 'ExAppService.php']"]
    own = controller.replace("ExAppService::withZones(", "self::zones(")
    assert admin_findings(admin, own, sources) == ["the routes do not use the shared zone rule"]


# -- one list of profiles, models and states --------------------------------------------


def listed(text: str, opening: str) -> list[str]:
    """The quoted words of the list literal that starts with opening."""
    start = text.find(opening)
    if start < 0:
        return []
    end = text.find("]", start + len(opening))
    return _QUOTED.findall(text[start + len(opening) : end])


def keyed(text: str, opening: str) -> list[str]:
    """The keys of the PHP array literal that starts with opening."""
    start = text.find(opening)
    if start < 0:
        return []
    end = text.find("\n];", start)
    return re.findall(r"^\t'([A-Za-z0-9_-]+)' =>", text[start:end], re.MULTILINE)


def test_profiles_models_and_states_are_one_list_in_php_template_and_script() -> None:
    service = read(SERVICE)
    template = read(TEMPLATE)

    profiles = listed(service, "public const RESOURCE_PROFILES = [")
    models = listed(service, "public const RESOURCE_MODELS = [")
    states = listed(service, "public const RESOURCE_MODEL_STATES = [")
    assert profiles == ["fast", "balanced", "quality"]
    assert models == list(MODEL_NAMES)
    assert len(states) == 11

    assert listed(template, "$profileIds = [") == profiles
    assert keyed(template, "$profileNames = [") == profiles
    assert keyed(template, "$profileHints = [") == profiles
    assert keyed(template, "$modelNames = [") == models
    assert keyed(template, "$modelOrigins = [") == models
    assert keyed(template, "$modelStates = [") == states


def test_self_list_readers_read_a_list_and_its_keys() -> None:
    assert listed("const A = ['x', 'y-1']\nconst B = ['z']", "const A = [") == ["x", "y-1"]
    assert listed("const A = ['x']", "const C = [") == []
    assert keyed("$a = [\n\t'x' => 1,\n\t'y' => ['z' => 2],\n];\n$b = [\n\t'q' => 1,\n];", "$a = [") == ["x", "y"]


# -- the rounding rule: PHP and script on the same rows ------------------------------------

# (bytes, meaning, text with a point as decimal sign): on the boundary of a
# tenth of a GB, just below, just above, and zero. AdminSettingsTest.php
# carries the same rows for ResourceFormat (gigabyteRows).
GIGABYTE_ROWS: tuple[tuple[int, str, str], ...] = (
    (0, "need", "0.0 GB"),
    (1, "need", "0.1 GB"),
    (2999999999, "need", "3.0 GB"),
    (3000000000, "need", "3.0 GB"),
    (3000000001, "need", "3.1 GB"),
    (0, "available", "0.0 GB"),
    (2999999999, "available", "2.9 GB"),
    (3000000000, "available", "3.0 GB"),
    (3000000001, "available", "3.0 GB"),
    (0, "size", "0.0 GB"),
    (3049999999, "size", "3.0 GB"),
    (3050000000, "size", "3.1 GB"),
    (3050000001, "size", "3.1 GB"),
    (1617884929, "size", "1.6 GB"),
    (3087284237, "size", "3.1 GB"),
)

# The arithmetic of ResourceFormat::gigabytes, word for word.
PHP_RULE = (
    "\tprivate const TENTH = 100000000;\n",
    "\t\t$bytes = max(0, $bytes);\n",
    "\t\t\tself::MODE_NEED => intdiv($bytes + self::TENTH - 1, self::TENTH),\n",
    "\t\t\tself::MODE_AVAILABLE => intdiv($bytes, self::TENTH),\n",
    "\t\t\tself::MODE_SIZE => intdiv($bytes + intdiv(self::TENTH, 2), self::TENTH),\n",
    "\t\t$number = intdiv($tenths, 10) . self::separator($l) . ($tenths % 10);\n",
)
_PHPUNIT_ROW = re.compile(r"^\t\t\t\[(\d+), '(need|available|size)', '([0-9.]+ GB)'\],$", re.MULTILINE)


def php_reference(amount: int, mode: str, decimal: str = ".", unit: str = "%s GB") -> str:
    """PHP_RULE in Python, line for line."""
    tenth = 100000000
    amount = max(0, amount)
    if mode == "need":
        tenths = (amount + tenth - 1) // tenth
    elif mode == "available":
        tenths = amount // tenth
    else:
        tenths = (amount + tenth // 2) // tenth
    return unit.replace("%s", f"{tenths // 10}{decimal}{tenths % 10}")


def test_the_php_rule_stands_word_for_word_and_gives_the_rows() -> None:
    source = read(FORMAT)
    for line in PHP_RULE:
        assert line in source, line
    for amount, mode, expected in GIGABYTE_ROWS:
        assert php_reference(amount, mode) == expected, (amount, mode)
    # A lock never shows the same number twice: a need above what is available reads higher.
    for available in (0, 1, 2999999999, 3000000000, 3049999999, 3099999999):
        assert php_reference(available + 1, "need") != php_reference(available, "available"), available


def test_phpunit_runs_resource_format_on_the_same_rows() -> None:
    rows = [(int(amount), mode, text) for amount, mode, text in _PHPUNIT_ROW.findall(read(PHPUNIT))]
    assert rows == list(GIGABYTE_ROWS)
    assert "self::assertSame($expected, ResourceFormat::gigabytes($bytes, $mode, $this->l10n()));" in read(PHPUNIT)


# -- the texts ---------------------------------------------------------------------------------


def page_literals() -> set[str]:
    """Every literal the page translates: template, Admin.php and the formatter."""
    return {literal for path in (TEMPLATE, ADMIN, FORMAT) for literal in source_strings(read(path))}


def test_every_text_of_the_page_stands_in_all_four_catalogues() -> None:
    literals = page_literals()
    catalogues = load_catalogues(PHP_L10N)
    assert set(PHP_LANGUAGES) <= set(catalogues)
    assert len(literals) >= 75, "the scan is blind"
    missing = [
        f"{language}: {literal}"
        for literal in sorted(literals)
        for language in PHP_LANGUAGES
        if literal not in catalogues[language]
    ]
    assert missing == []
    # German and French really carry a text of their own for the long sentences.
    for language in ("de", "de_DE", "fr"):
        same = [literal for literal in literals if len(literal) > 40 and catalogues[language][literal] == literal]
        assert same == [], language


def test_every_approved_text_of_phase_5_is_used_on_the_page() -> None:
    literals = page_literals()
    unused = [ident for ident, english, _, _ in ROWS if english not in literals]
    assert unused == []
    # No text of the script: every word comes out of the template.
    assert source_strings(read(SCRIPT)) == []


def test_self_the_text_scan_finds_a_missing_catalogue_entry() -> None:
    catalogues = load_catalogues(PHP_L10N)
    staged = source_strings("<?php p($l->t('Models and licenses')); p($l->t('A text nobody translated')); ?>")
    assert staged == ["Models and licenses", "A text nobody translated"]
    assert [literal for literal in staged if literal not in catalogues["fr"]] == ["A text nobody translated"]
