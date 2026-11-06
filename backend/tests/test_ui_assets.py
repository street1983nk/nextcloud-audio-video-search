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
