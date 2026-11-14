"""Static gates over the browser assets of the PHP app (templates, JS, CSS).

The development machine has no PHP and no browser run in the local suite, so
what the UI contract (01-UI-SPEC.md, DESIGN.md) forbids in so many words is
checked here by reading the files:

* templates: no inline script (CSP), no style attribute (theme), no printer
  that skips escaping (only p() prints a value), every class either carries
  the app prefix avs- or is one of the few server classes the UI-SPEC names;
* JS: no markup from a string, no eval;
* CSS: server variables only, so no hex, rgb or hsl colour, no !important,
  no removed focus outline, no shadow, no gradient;
* nowhere: no attribute that starts a medium on its own.

Every rule has a staged violation that has to make it fire, so a gate whose
body was deleted cannot stay green, and the real tree is held to a floor (the
three files of the playback page exist), so the gates cannot pass on an empty
directory.
"""

import re
from pathlib import Path

from tests.conftest import REPO_ROOT

PHP_ROOT = REPO_ROOT / "php"
TEMPLATES = PHP_ROOT / "templates"
SCRIPTS = PHP_ROOT / "js"
STYLES = PHP_ROOT / "css"

ALLOWED_SERVER_CLASSES = frozenset(
    {"section", "settings-hint", "checkbox", "primary", "icon-loading-small", "hidden-visually"}
)
CLASS_PREFIX = "avs-"

INLINE_SCRIPT = re.compile(r"<script", re.IGNORECASE)
STYLE_ATTRIBUTE = re.compile(r"\sstyle\s*=", re.IGNORECASE)
UNESCAPED_PRINTER = re.compile(r"<\?=|<\?php\s+echo\b|\becho\s|\bprint_unescaped\s*\(|\bprint\s*\(")
MARKUP_FROM_STRING = re.compile(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write")
EVAL_CALL = re.compile(r"\beval\s*\(|new\s+Function\s*\(")
SELF_START = re.compile(r"autoplay", re.IGNORECASE)
HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
FUNCTIONAL_COLOUR = re.compile(r"\b(?:rgb|hsl)a?\(", re.IGNORECASE)
IMPORTANT = re.compile(r"!\s*important", re.IGNORECASE)
NO_OUTLINE = re.compile(r"outline\s*:\s*(?:none|0)\b", re.IGNORECASE)
SHADOW = re.compile(r"box-shadow|text-shadow", re.IGNORECASE)
GRADIENT = re.compile(r"gradient", re.IGNORECASE)

_CLASS_ATTRIBUTE = re.compile(r"\bclass=\"([^\"]*)\"")
_PHP_BLOCK = re.compile(r"<\?php.*?\?>", re.DOTALL)


def files(folder: Path, suffix: str) -> list[Path]:
    """The files of one asset folder with one suffix, sorted."""
    return sorted(path for path in folder.glob(f"*{suffix}") if path.is_file())


def findings(pattern: re.Pattern[str], text: str) -> list[str]:
    """Every match of pattern in text."""
    return [match.group(0) for match in pattern.finditer(text)]


def foreign_classes(template: str) -> list[str]:
    """Class names that neither carry the app prefix nor are allowed server classes.

    A PHP block inside a class value is removed first; the literal text in
    front of it ("avs-banner--") is what the rule judges.
    """
    found = []
    for match in _CLASS_ATTRIBUTE.finditer(template):
        value = _PHP_BLOCK.sub("", match.group(1))
        for name in value.split():
            if not name.startswith(CLASS_PREFIX) and name not in ALLOWED_SERVER_CLASSES:
                found.append(name)
    return found


_FORMAT_BANNER = re.compile(
    r"'format' => \[[^\]]*?"
    r"'text' => \$downloadAllowed\s*\?\s*\$l->t\('([^']*)'\)\s*:\s*\$l->t\('([^']*)'\),[^\]]*?"
    r"'action' => \$downloadAllowed \? 'download' : 'none',",
)


def format_banner_texts(template: str) -> tuple[str, str] | None:
    """The two texts of the format banner: with and without a download.

    None when the text does not depend on $downloadAllowed the same way the
    download button does, so a banner without a button could still tell the
    reader to download.
    """
    match = _FORMAT_BANNER.search(template)
    return (match.group(1), match.group(2)) if match else None


def _read(paths: list[Path]) -> dict[str, str]:
    return {path.relative_to(REPO_ROOT).as_posix(): path.read_text(encoding="utf-8") for path in paths}


def _templates() -> dict[str, str]:
    return _read(files(TEMPLATES, ".php"))


def _scripts() -> dict[str, str]:
    return _read(files(SCRIPTS, ".js"))


def _styles() -> dict[str, str]:
    return _read(files(STYLES, ".css"))


def _hits(sources: dict[str, str], pattern: re.Pattern[str]) -> dict[str, list[str]]:
    return {name: found for name, text in sources.items() if (found := findings(pattern, text))}


# -- the real tree ------------------------------------------------------------------


def test_the_tree_carries_the_assets_of_the_playback_page() -> None:
    for path in (TEMPLATES / "play.php", SCRIPTS / "play.js", STYLES / "play.css"):
        assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"
    template = (TEMPLATES / "play.php").read_text(encoding="utf-8")
    assert 'id="avs-media"' in template
    assert "\\OCP\\Util::addScript('audio_video_search', 'play')" in template
    assert "\\OCP\\Util::addStyle('audio_video_search', 'play')" in template


def test_templates_have_no_inline_script() -> None:
    assert _hits(_templates(), INLINE_SCRIPT) == {}


def test_templates_have_no_style_attribute() -> None:
    assert _hits(_templates(), STYLE_ATTRIBUTE) == {}


def test_templates_print_only_through_p() -> None:
    assert _hits(_templates(), UNESCAPED_PRINTER) == {}


def test_template_classes_carry_the_prefix_or_are_server_classes() -> None:
    found = {name: names for name, text in _templates().items() if (names := foreign_classes(text))}
    assert found == {}


def test_scripts_build_no_markup_from_strings() -> None:
    assert _hits(_scripts(), MARKUP_FROM_STRING) == {}


def test_scripts_have_no_eval() -> None:
    assert _hits(_scripts(), EVAL_CALL) == {}


def test_nothing_starts_a_medium_on_its_own() -> None:
    sources = {**_templates(), **_scripts(), **_styles()}
    assert _hits(sources, SELF_START) == {}


def test_styles_use_no_colour_values() -> None:
    styles = _styles()
    assert _hits(styles, HEX_COLOUR) == {}
    assert _hits(styles, FUNCTIONAL_COLOUR) == {}


def test_styles_do_not_force_or_remove() -> None:
    styles = _styles()
    assert _hits(styles, IMPORTANT) == {}
    assert _hits(styles, NO_OUTLINE) == {}


def test_styles_stay_flat() -> None:
    styles = _styles()
    assert _hits(styles, SHADOW) == {}
    assert _hits(styles, GRADIENT) == {}


def test_the_playback_page_keeps_its_contract() -> None:
    template = (TEMPLATES / "play.php").read_text(encoding="utf-8")
    script = (SCRIPTS / "play.js").read_text(encoding="utf-8")
    style = (STYLES / "play.css").read_text(encoding="utf-8")
    assert 'preload="metadata"' in template
    assert "playsinline" in template
    assert 'id="avs-play-state"' in template
    assert 'id="avs-jump"' in template
    assert template.count('role="alert" tabindex="-1"') == 1
    assert "loadedmetadata" in script
    assert script.count("method: 'HEAD'") == 1
    assert "credentials: 'same-origin'" in script
    assert ".play(" not in script
    assert "max-height: 70vh" in style
    assert "pointer: coarse" in style


EXCERPT_NOTE_RULE = (
    "margin: calc(var(--default-grid-baseline) * 2) 0 0;",
    "color: var(--color-text-maxcontrast);",
    "font-size: var(--font-size-small);",
    "line-height: var(--default-line-height);",
    "overflow-wrap: anywhere;",
)


def css_rule(style: str, selector: str) -> list[str] | None:
    """The declarations of the one rule whose whole selector list is selector, or None."""
    blocks = re.findall(r"([^{}]+)\{([^{}]*)\}", style)
    found = [body for head, body in blocks if [part.strip() for part in head.split(",")] == [selector]]
    if len(found) != 1:
        return None
    return [line.strip() for line in found[0].split("\n") if line.strip()]


def selectors_with(style: str, declaration: str) -> list[str]:
    """Every selector whose rule carries declaration."""
    blocks = re.findall(r"([^{}]+)\{([^{}]*)\}", style)
    return [part.strip() for head, body in blocks if declaration in body for part in head.split(",")]


def test_the_excerpt_note_follows_the_ui_spec() -> None:
    template = (TEMPLATES / "play.php").read_text(encoding="utf-8")
    style = (STYLES / "play.css").read_text(encoding="utf-8")
    # 03-UI-SPEC.md, surface 2: these five declarations and nothing else.
    assert css_rule(style, ".avs-excerpt__note") == list(EXCERPT_NOTE_RULE)
    # The longest sentences wrap at 375 px: both the hint and the note may break anywhere.
    wrapping = selectors_with(style, "overflow-wrap: anywhere;")
    assert ".avs-excerpt__hint" in wrapping
    assert ".avs-excerpt__note" in wrapping
    # The note is read after the excerpt: both of its paragraphs come after the blockquote.
    quote = template.index('<blockquote class="avs-excerpt__text">')
    notes = [match.start() for match in re.finditer(r'<p class="avs-excerpt__note">', template)]
    assert len(notes) == 2
    assert all(note > quote for note in notes)
    # The hints print only fixed texts: no raw state or reason reaches the page.
    assert "p($excerptState)" not in template
    assert "p($excerptHints[$excerptState])" in template
    # The branch for no transcript (A5) keeps its markup and text.
    assert (
        "\t\t\t<?php } elseif ($excerptState === 'none') { ?>\n"
        "\t\t\t\t<p class=\"avs-excerpt__hint\"><?php p($l->t('There is no transcript for this file yet.')); ?></p>\n"
    ) in template


def test_self_css_rule_reads_one_rule_exactly() -> None:
    style = ".a {\n\tcolor: x;\n}\n\n.b,\n.a {\n\tmargin: 0;\n}\n.c { overflow-wrap: anywhere; }\n"
    assert css_rule(style, ".a") == ["color: x;"]
    assert css_rule(style, ".z") is None
    assert css_rule(style + ".a { top: 0; }", ".a") is None
    assert css_rule(".a {\n\tcolor: x;\n\tbox-shadow: none;\n}", ".a") != ["color: x;"]
    assert selectors_with(style, "overflow-wrap: anywhere;") == [".c"]
    assert selectors_with(style, "margin: 0;") == [".b", ".a"]


def test_the_format_banner_offers_a_download_only_with_the_button() -> None:
    template = (TEMPLATES / "play.php").read_text(encoding="utf-8")
    texts = format_banner_texts(template)
    assert texts is not None
    with_download, without_download = texts
    assert with_download == "Download it and open it in another program."
    assert without_download == "This share does not allow downloads. The person who shared the file can allow them."
    assert "open it" not in without_download
    assert not without_download.startswith("Download")


def test_the_admin_section_keeps_its_contract() -> None:
    template = (TEMPLATES / "admin.php").read_text(encoding="utf-8")
    script = (SCRIPTS / "admin.js").read_text(encoding="utf-8")
    style = (STYLES / "admin.css").read_text(encoding="utf-8")
    # One state area, announced politely and the focus target after a recheck.
    assert template.count('id="avs-backend-state"') == 1
    assert 'role="status" aria-live="polite" tabindex="-1"' in template
    # The seven states and the recheck warning, rendered on the server.
    for state in (
        "ok",
        "version_patch_differs",
        "version_drift",
        "backend_missing",
        "backend_disabled",
        "backend_unreachable",
        "no_app_api",
    ):
        assert f"'{state}' =>" in template, state
    assert 'id="avs-recheck-failed"' in template
    # Nextcloud 34 moved the app management into the app "appstore".
    assert "linkToRoute('appstore.page.viewApps')" in template
    assert "linkToRoute('settings.AppSettings.viewApps')" in template
    # Banner rules come from play.css, the debug block only in debug mode.
    assert "\\OCP\\Util::addStyle('audio_video_search', 'play')" in template
    assert "\\OCP\\Util::addStyle('audio_video_search', 'admin')" in template
    assert "\\OCP\\Util::addScript('audio_video_search', 'admin')" in template
    assert "<?php if ($debug) { ?>" in template
    assert ".avs-banner {" not in style
    assert "#avs-admin [hidden]" in style
    assert "pointer: coarse" in style
    # The script asks its own routes with the token of the moment.
    assert "admin/state" in script
    assert "admin/sample" in script
    assert script.count("requesttoken: document.head.dataset.requesttoken") == 2
    assert "aria-busy" in script
    assert "stateArea.focus()" in script


# -- the self tests: every rule has to fire on a staged violation --------------------


def test_self_inline_script_and_style_attribute_fire() -> None:
    assert findings(INLINE_SCRIPT, '<SCRIPT nonce="x">go()</SCRIPT>') == ["<SCRIPT"]
    assert findings(STYLE_ATTRIBUTE, '<div style="color: red">') == [" style="]
    assert findings(STYLE_ATTRIBUTE, '<div class="avs-style">') == []


def test_self_unescaped_printers_fire() -> None:
    for staged in ("<?= $name ?>", "<?php echo $name; ?>", "<?php print_unescaped($name); ?>", "<?php print($x); ?>"):
        assert findings(UNESCAPED_PRINTER, staged), staged
    assert findings(UNESCAPED_PRINTER, "<?php p($name); ?>") == []


def test_self_foreign_classes_fire_and_php_values_pass() -> None:
    assert foreign_classes('<div class="avs-banner avs-banner--<?php p($kind); ?>">') == []
    assert foreign_classes('<input class="checkbox"><p class="settings-hint">') == []
    assert foreign_classes('<div class="card avs-x">') == ["card"]


def test_self_script_rules_fire() -> None:
    assert findings(MARKUP_FROM_STRING, "node.innerHTML = text") == ["innerHTML"]
    assert findings(MARKUP_FROM_STRING, "node.insertAdjacentHTML('a', t)") == ["insertAdjacentHTML"]
    assert findings(EVAL_CALL, "eval (code)") == ["eval ("]
    assert findings(EVAL_CALL, "node.textContent = value") == []


def test_self_self_start_fires_in_any_case() -> None:
    assert findings(SELF_START, "<video AutoPlay>") == ["AutoPlay"]
    assert findings(SELF_START, "media.autoplay = true") == ["autoplay"]


def test_self_colour_rules_fire() -> None:
    assert findings(HEX_COLOUR, "color: #fff;") == ["#fff"]
    assert findings(HEX_COLOUR, "color: #00679e80;") == ["#00679e80"]
    assert findings(FUNCTIONAL_COLOUR, "background: rgba(0, 0, 0, .5)") == ["rgba("]
    assert findings(FUNCTIONAL_COLOUR, "color: HSL(0 0% 0%)") == ["HSL("]
    assert findings(HEX_COLOUR, "color: var(--color-main-text);") == []


def test_self_force_remove_and_flat_rules_fire() -> None:
    assert findings(IMPORTANT, "display: none !important;") == ["!important"]
    assert findings(NO_OUTLINE, "outline:none;") == ["outline:none"]
    assert findings(NO_OUTLINE, "outline: 0;") == ["outline: 0"]
    assert findings(NO_OUTLINE, "outline: 2px solid currentColor;") == []
    assert findings(SHADOW, "box-shadow: 0 2px 8px") == ["box-shadow"]
    assert findings(GRADIENT, "background: linear-gradient(red, blue)") == ["gradient"]


def test_self_format_banner_rule_fires_on_an_unconditional_text() -> None:
    staged = (
        "'format' => [\n\t\t'title' => $l->t('T'),\n"
        "\t\t'text' => $l->t('Download it and open it in another program.'),\n"
        "\t\t'action' => $downloadAllowed ? 'download' : 'none',\n"
    )
    assert format_banner_texts(staged) is None
    passing = staged.replace(
        "$l->t('Download it and open it in another program.')", "$downloadAllowed ? $l->t('A') : $l->t('B')"
    )
    assert format_banner_texts(passing) == ("A", "B")
