"""Owner rule: everything user facing exists in German, English and French.

German comes first (README.md is German). The rule covers, and this module holds:

- the READMEs: README.md (de), README.en.md, README.fr.md
- every user document under docs/: <name>.md (de) with <name>.en.md and
  <name>.fr.md beside it, in both directions
- the store texts: name, summary and description of appinfo/info.xml in the
  English default, lang="de" and lang="fr"
- the l10n catalogues: l10n/de.json, l10n/en.json, l10n/fr.json with exactly the
  same keys, no empty value, and every string of the settings page among them

Each rule has a mutated sample that has to make it fire, so a gate whose body
was deleted cannot stay green.
"""

import json
from xml.etree import ElementTree

from audio_video_search import settings
from tests.conftest import REPO_ROOT

LANGUAGES = ("de", "en", "fr")
README_FILES = {"de": "README.md", "en": "README.en.md", "fr": "README.fr.md"}
DOCS = REPO_ROOT / "docs"
L10N = REPO_ROOT / "l10n"
INFO_XML = REPO_ROOT / "appinfo" / "info.xml"
STORE_ELEMENTS = ("name", "summary", "description")


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


def catalogue_findings(catalogues: dict[str, dict[str, str]]) -> list[str]:
    """Missing languages, keys that exist in one catalogue only, and empty values."""
    findings = [f"l10n/{language}.json is missing" for language in LANGUAGES if language not in catalogues]
    every_key = set().union(*(set(table) for table in catalogues.values())) if catalogues else set()
    for language, table in sorted(catalogues.items()):
        findings += [f"l10n/{language}.json lacks {key!r}" for key in sorted(every_key - set(table))]
        findings += [
            f"l10n/{language}.json has an empty value for {key!r}" for key, value in table.items() if not value
        ]
    return findings


def load_catalogues() -> dict[str, dict[str, str]]:
    """Every l10n/<lang>.json as language -> translations."""
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))["translations"] for path in sorted(L10N.glob("*.json"))
    }


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


def test_the_catalogues_carry_the_same_keys_in_three_languages() -> None:
    assert catalogue_findings(load_catalogues()) == []


def test_every_string_of_the_settings_page_is_translated() -> None:
    catalogues = load_catalogues()

    for text in settings.user_visible_strings(settings.admin_form()):
        for language in LANGUAGES:
            assert text in catalogues[language], f"{text!r} missing in l10n/{language}.json"


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
