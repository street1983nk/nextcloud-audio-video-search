"""Owner rule: everything user facing exists in German, English and French.

German comes first (README.md is German). The rule covers, and this module holds:

- the READMEs: README.md (de), README.en.md, README.fr.md
- every user document under docs/: <name>.md (de) with <name>.en.md and
  <name>.fr.md beside it, in both directions
- the store texts: name, summary and description of backend/appinfo/info.xml and
  php/appinfo/info.xml in the English default, lang="de" and lang="fr"
- the l10n catalogues of both halves: php/l10n (de, de_DE, en, fr) and
  backend/l10n (de, en, fr), each with exactly the same keys and no empty value;
  de and de_DE are one text (impersonal German); no en or em dash and no emoji
  in any value; every placeholder of the English key in every value; French with
  a no-break space (U+00A0) before : ; ? ! and inside the guillemets; each .js
  twin carries the same translations as its .json source
- every string the PHP app hands to t() and every string of the settings page

Each rule has a mutated sample that has to make it fire, so a gate whose body
was deleted cannot stay green. The forbidden characters are built with chr(), so
this file passes the dash and emoji gate itself.
"""

import json
import re
from pathlib import Path
from xml.etree import ElementTree

from audio_video_search_backend import settings
from tests.conftest import BACKEND_ROOT, REPO_ROOT

LANGUAGES = ("de", "en", "fr")
PHP_LANGUAGES = ("de", "de_DE", "en", "fr")
README_FILES = {"de": "README.md", "en": "README.en.md", "fr": "README.fr.md"}
DOCS = REPO_ROOT / "docs"
L10N = BACKEND_ROOT / "l10n"
PHP_ROOT = REPO_ROOT / "php"
PHP_L10N = PHP_ROOT / "l10n"
INFO_XML = BACKEND_ROOT / "appinfo" / "info.xml"
PHP_INFO_XML = PHP_ROOT / "appinfo" / "info.xml"
STORE_ELEMENTS = ("name", "summary", "description")

NBSP = chr(0xA0)
DASHES = (chr(0x2013), chr(0x2014))
EMOJI = re.compile(f"[{chr(0x1F300)}-{chr(0x1FAFF)}{chr(0x2600)}-{chr(0x27BF)}]")
PLACEHOLDER = re.compile(r"%(?:\d+\$)?s|\{\w+\}")
URL = re.compile(r"https?://\S+")
OPEN_QUOTE, CLOSE_QUOTE = chr(0xAB), chr(0xBB)
FRENCH_SPACING = re.compile(f" [:;?!{CLOSE_QUOTE}]|{OPEN_QUOTE} ")
# t('…') in PHP ($this->l10n->t('…'), $l->t('…')) and t('audio_video_search', '…') in JS.
PHP_T_CALL = re.compile(r"->t\(\s*'((?:[^'\\]|\\.)*)'")
JS_T_CALL = re.compile(r"\bt\(\s*'audio_video_search'\s*,\s*'((?:[^'\\]|\\.)*)'")


def missing_doc_languages(names: list[str]) -> list[str]:
    """The language editions missing from a list of markdown file names."""
    bases = set()
    for name in names:
        stem = name.removesuffix(".md")
        bases.add(stem.removesuffix(".en").removesuffix(".fr"))
    missing = []
    for base in sorted(bases):
        for name in (f"{base}.md", f"{base}.en.md", f"{base}.fr.md"):
            if name not in names:
                missing.append(name)
    return missing


def store_languages_missing(source: str) -> list[str]:
    """Every store element whose de, en (default) or fr edition is missing or empty."""
    info = ElementTree.fromstring(source)  # noqa: S314 - our own file
    findings = []
    for kind in STORE_ELEMENTS:
        present = {element.get("lang", "en"): (element.text or "").strip() for element in info.findall(kind)}
        findings += [f"{kind} lang={language}" for language in LANGUAGES if not present.get(language)]
    return findings


def catalogue_findings(
    catalogues: dict[str, dict[str, str]], languages: tuple[str, ...] = LANGUAGES, prefix: str = "l10n"
) -> list[str]:
    """Missing languages, keys that exist in one catalogue only, and empty values."""
    findings = [f"{prefix}/{language}.json is missing" for language in languages if language not in catalogues]
    every_key = set().union(*(set(table) for table in catalogues.values())) if catalogues else set()
    for language, table in sorted(catalogues.items()):
        findings += [f"{prefix}/{language}.json lacks {key!r}" for key in sorted(every_key - set(table))]
        findings += [
            f"{prefix}/{language}.json has an empty value for {key!r}" for key, value in table.items() if not value
        ]
    return findings


def german_twin_findings(catalogues: dict[str, dict[str, str]]) -> list[str]:
    """de and de_DE are one impersonal text; a difference is a finding."""
    if catalogues.get("de") == catalogues.get("de_DE"):
        return []
    return ["de.json and de_DE.json differ"]


def character_findings(catalogues: dict[str, dict[str, str]]) -> list[str]:
    """An en or em dash or an emoji in any key or value of any language."""
    findings = []
    for language, table in sorted(catalogues.items()):
        for key, value in table.items():
            for text in (key, value):
                if any(dash in text for dash in DASHES):
                    findings.append(f"{language}: dash in {text!r}")
                if EMOJI.search(text):
                    findings.append(f"{language}: emoji in {text!r}")
    return findings


def french_spacing_findings(table: dict[str, str]) -> list[str]:
    """A plain space before : ; ? ! or » or after « in a French value; placeholders and URLs aside."""
    findings = []
    for key, value in table.items():
        bare = PLACEHOLDER.sub("", URL.sub("", value))
        if FRENCH_SPACING.search(bare):
            findings.append(f"fr: plain space instead of U+00A0 in {key!r}")
    return findings


def placeholder_findings(catalogues: dict[str, dict[str, str]]) -> list[str]:
    """Every value carries exactly the placeholders of its English key."""
    findings = []
    for language, table in sorted(catalogues.items()):
        for key, value in table.items():
            if sorted(PLACEHOLDER.findall(key)) != sorted(PLACEHOLDER.findall(value)):
                findings.append(f"{language}: placeholders differ in {key!r}")
    return findings


def js_twin_findings(json_text: str, js_text: str, app: str) -> list[str]:
    """The .js twin registers under the app id with the translations and plural form of the .json."""
    source = json.loads(json_text)
    head = f'OC.L10N.register(\n    "{app}",\n'
    if not js_text.startswith(head):
        return ["js twin registers under another app or in another layout"]
    start, end = js_text.index("{"), js_text.rindex("}")
    findings = []
    if json.loads(js_text[start : end + 1]) != source["translations"]:
        findings.append("js twin carries other translations")
    if json.dumps(source["pluralForm"], ensure_ascii=False) not in js_text[end:]:
        findings.append("js twin carries another plural form")
    return findings


def source_strings(text: str) -> list[str]:
    """Every literal handed to t() in a PHP, template or JS source."""
    found = PHP_T_CALL.findall(text) + JS_T_CALL.findall(text)
    return [literal.replace("\\'", "'") for literal in found]


def load_catalogues(root: Path = L10N) -> dict[str, dict[str, str]]:
    """Every <root>/<lang>.json as language -> translations."""
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))["translations"] for path in sorted(root.glob("*.json"))
    }


def app_id(info_xml: Path) -> str:
    text = info_xml.read_text(encoding="utf-8")
    return text.split("<id>", 1)[1].split("</id>", 1)[0].strip()


def both_roots() -> list[tuple[Path, tuple[str, ...]]]:
    return [(L10N, LANGUAGES), (PHP_L10N, PHP_LANGUAGES)]


# -- the real tree -------------------------------------------------------------


def test_the_three_readmes_exist_and_link_each_other() -> None:
    for language, name in README_FILES.items():
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        others = [other for key, other in README_FILES.items() if key != language]
        assert all(f"({other})" in text for other in others), name


def test_every_user_document_exists_in_three_languages() -> None:
    names = sorted(path.name for path in DOCS.glob("*.md"))

    assert names, "docs/ carries no user document, so this gate would judge nothing"
    assert missing_doc_languages(names) == []


def test_the_store_texts_exist_in_three_languages() -> None:
    assert store_languages_missing(INFO_XML.read_text(encoding="utf-8")) == []
    assert store_languages_missing(PHP_INFO_XML.read_text(encoding="utf-8")) == []


def test_the_catalogues_carry_the_same_keys_in_three_languages() -> None:
    assert catalogue_findings(load_catalogues()) == []
    assert catalogue_findings(load_catalogues(PHP_L10N), PHP_LANGUAGES, "php/l10n") == []
    assert set(load_catalogues(PHP_L10N)) == set(PHP_LANGUAGES)


def test_german_and_german_germany_are_one_text() -> None:
    assert german_twin_findings(load_catalogues(PHP_L10N)) == []
    assert (PHP_L10N / "de.json").read_bytes() == (PHP_L10N / "de_DE.json").read_bytes()


def test_no_catalogue_carries_a_dash_or_an_emoji() -> None:
    for root, _ in both_roots():
        assert character_findings(load_catalogues(root)) == [], root


def test_french_uses_no_break_spaces() -> None:
    for root, _ in both_roots():
        table = load_catalogues(root)["fr"]
        assert french_spacing_findings(table) == [], root
    # The positive control: the French catalogue really carries U+00A0, so the
    # gate is not green only because no colon occurs.
    assert NBSP in "".join(load_catalogues(PHP_L10N)["fr"].values())


def test_every_value_keeps_the_placeholders_of_its_key() -> None:
    for root, _ in both_roots():
        assert placeholder_findings(load_catalogues(root)) == [], root


def test_every_js_twin_matches_its_json_source() -> None:
    for root, languages in both_roots():
        app = app_id(root.parent / "appinfo" / "info.xml")
        for language in languages:
            json_text = (root / f"{language}.json").read_text(encoding="utf-8")
            js_text = (root / f"{language}.js").read_text(encoding="utf-8")
            assert js_twin_findings(json_text, js_text, app) == [], f"{root}/{language}.js"


def test_every_string_of_the_settings_page_is_translated() -> None:
    catalogues = load_catalogues()

    for text in settings.user_visible_strings(settings.admin_form()):
        for language in LANGUAGES:
            assert text in catalogues[language], f"{text!r} missing in l10n/{language}.json"


def test_every_string_the_php_app_translates_is_in_its_catalogues() -> None:
    sources = [
        path
        for folder in ("lib", "templates", "js")
        for path in sorted((PHP_ROOT / folder).rglob("*"))
        if path.suffix in {".php", ".js"}
    ]
    literals = {literal for path in sources for literal in source_strings(path.read_text(encoding="utf-8"))}
    catalogues = load_catalogues(PHP_L10N)

    assert "Audio and video" in literals, "the provider name must be found, or the scan is blind"
    for literal in sorted(literals):
        for language in PHP_LANGUAGES:
            assert literal in catalogues[language], f"{literal!r} missing in php/l10n/{language}.json"


def test_the_php_catalogue_holds_the_texts_of_the_ui_spec() -> None:
    catalogues = load_catalogues(PHP_L10N)

    assert catalogues["de"]["This file is not available"] == "Diese Datei ist nicht verfügbar"
    assert catalogues["de"]["Jump to %s"] == "Zur Zeitstelle %s springen"
    assert catalogues["fr"]["Audio and video"] == "Audio et vidéo"
    assert catalogues["fr"]["Test result"] == "Résultat de test"
    assert catalogues["fr"]["Playback: %s"] == f"Lecture{NBSP}: %s"
    assert catalogues["en"]["Checking" + chr(0x2026)] == "Checking" + chr(0x2026)
    assert all(key == value for key, value in catalogues["en"].items())


# -- self tests: every rule has to be able to fire ------------------------------


def test_a_missing_document_edition_is_reported_in_both_directions() -> None:
    assert missing_doc_languages(["a.md", "a.en.md", "a.fr.md"]) == []
    assert missing_doc_languages(["a.md", "a.en.md"]) == ["a.fr.md"]
    assert missing_doc_languages(["b.en.md", "b.fr.md"]) == ["b.md"]


def test_a_missing_store_language_is_reported() -> None:
    sample = (
        "<info><name>N</name><name lang='de'>N</name><name lang='fr'>N</name>"
        "<summary>S</summary><summary lang='de'>S</summary>"
        "<description>D</description><description lang='de'>D</description><description lang='fr'> </description>"
        "</info>"
    )

    assert store_languages_missing(sample) == ["summary lang=fr", "description lang=fr"]


def test_a_key_in_one_catalogue_only_is_reported() -> None:
    catalogues = {"de": {"A": "A-de", "B": "B-de"}, "en": {"A": "A"}, "fr": {"A": ""}}

    assert catalogue_findings(catalogues) == [
        "l10n/en.json lacks 'B'",
        "l10n/fr.json lacks 'B'",
        "l10n/fr.json has an empty value for 'A'",
    ]
    assert catalogue_findings({"de": {}, "en": {}}) == ["l10n/fr.json is missing"]
    assert catalogue_findings({"de": {}, "en": {}, "fr": {}}, PHP_LANGUAGES, "php/l10n") == [
        "php/l10n/de_DE.json is missing"
    ]


def test_a_german_twin_that_differs_is_reported() -> None:
    assert german_twin_findings({"de": {"A": "Ä"}, "de_DE": {"A": "Ä"}}) == []
    assert german_twin_findings({"de": {"A": "Ä"}, "de_DE": {"A": "Ae"}}) == ["de.json and de_DE.json differ"]


def test_a_dash_or_an_emoji_is_reported() -> None:
    assert character_findings({"de": {"A": "Audio, Video"}}) == []
    assert character_findings({"de": {"A": f"Audio {DASHES[0]} Video"}}) == [
        f"de: dash in {'Audio ' + DASHES[0] + ' Video'!r}"
    ]
    assert character_findings({"fr": {"A": f"x{DASHES[1]}y"}}) == [f"fr: dash in {'x' + DASHES[1] + 'y'!r}"]
    assert len(character_findings({"en": {"A": f"ok {chr(0x1F600)}"}})) == 1
    assert len(character_findings({"en": {"A": f"ok {chr(0x2705)}"}})) == 1


def test_a_plain_space_in_french_is_reported() -> None:
    samples = {
        "a": f"Lecture{NBSP}: %s",
        "b": f"{OPEN_QUOTE}{NBSP}Audio{NBSP}{CLOSE_QUOTE}",
        "c": f"Vraiment{NBSP}?",
        "d": "Voir https://example.org/a:b",
        "e": "Valeur %1$s : non",
    }
    assert french_spacing_findings(samples) == ["fr: plain space instead of U+00A0 in 'e'"]
    for bad in ("Lecture : %s", "Oui ;", "Quoi ?", "Non !", f"{OPEN_QUOTE} Audio", f"Audio {CLOSE_QUOTE}"):
        assert french_spacing_findings({"k": bad}) == ["fr: plain space instead of U+00A0 in 'k'"], bad


def test_a_lost_or_extra_placeholder_is_reported() -> None:
    assert placeholder_findings({"fr": {"From %1$s to %2$s": "De %1$s à %2$s"}}) == []
    assert placeholder_findings({"de": {"Hi {name}": "Hallo {name}"}}) == []
    assert placeholder_findings({"de": {"Start at %s": "Start bei"}}) == ["de: placeholders differ in 'Start at %s'"]
    assert placeholder_findings({"fr": {"From %1$s to %2$s": "De %1$s à %1$s"}}) == [
        "fr: placeholders differ in 'From %1$s to %2$s'"
    ]


def test_a_js_twin_that_drifted_is_reported() -> None:
    source = json.dumps({"translations": {"A": "Ä"}, "pluralForm": "nplurals=2; plural=(n != 1);"})
    good = 'OC.L10N.register(\n    "app",\n    {\n    "A": "Ä"\n},\n"nplurals=2; plural=(n != 1);");\n'

    assert js_twin_findings(source, good, "app") == []
    assert js_twin_findings(source, good.replace('"Ä"', '"Ae"'), "app") == ["js twin carries other translations"]
    assert js_twin_findings(source, good, "other") == ["js twin registers under another app or in another layout"]
    assert js_twin_findings(source, good.replace("n != 1", "n > 1"), "app") == ["js twin carries another plural form"]


def test_translated_literals_are_found_in_php_and_js() -> None:
    php = "return $this->l10n->t('Audio and video'); $l->t( 'It\\'s here' );"
    js = "t('audio_video_search', 'Saved'); t('other_app', 'Nope'); t(\"x\")"

    assert source_strings(php) == ["Audio and video", "It's here"]
    assert source_strings(js) == ["Saved"]
