"""Owner rules over every public text: no em or en dash, no emoji, real umlauts.

- Dashes and emoji: every tracked text file, code included, because comments and
  strings end up in logs, archives and screenshots. The licence texts are third
  party and exempt.
- Umlauts: German prose must not spell ä, ö, ü, ß as ae, oe, ue, ss. A general
  pattern would hit correct words (Quelle, aktuell, Masse), so the gate holds a
  list of transcribed words that never occur in correct German. Code is exempt
  (identifiers stay ASCII), so the scan covers the German texts only: README.md,
  German docs, l10n/de.json, the German store texts and the project documents.

The forbidden characters are written as escapes, so this file passes itself.
"""

import json
import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest

from tests.conftest import REPO_ROOT

EM_DASH = "\u2014"
EN_DASH = "\u2013"
EMOJI = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f]")
EXEMPT = frozenset({"LICENSE", "LICENSES/AGPL-3.0-or-later.txt", "uv.lock"})
BINARY_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".gz", ".zip"})

# Transcribed spellings that are never correct German. Lowercase stems; a match
# needs a word boundary in front, so "Quelle" or "aktuell" never match.
TRANSCRIBED = (
    "fuer",
    "ueber",
    "koenn",
    "moeglich",
    "muess",
    "waehl",
    "waehrend",
    "wuerd",
    "groess",
    "aender",
    "aenderung",
    "geloescht",
    "loesch",
    "pruef",
    "schluessel",
    "spaeter",
    "zurueck",
    "hoechst",
    "naechst",
    "gemaess",
    "laeuft",
    "oeffn",
    "oeffentlich",
    "benoetig",
    "verfuegbar",
    "unterstuetz",
    "ausfuehr",
    "eingefuegt",
    "hinzufueg",
    "schliess",
    "gross",
    "strasse",
    "massnahme",
    "regelmaessig",
    "faehig",
    "zusaetzlich",
    "ueberpruef",
    "veroeffentlich",
)
TRANSCRIBED_PATTERN = re.compile(r"(?i)\b(?:" + "|".join(TRANSCRIBED) + r")\w*")
# SKELETON.md exists only in the skeleton; new_app.py does not copy it.
GERMAN_DOCUMENTS = ("README.md", "SKELETON.md", "DESIGN.md", "PRODUCT.md", "CHANGELOG.md")


def tracked_files() -> list[Path]:
    """Every file git tracks or would track, so a new file is checked from its first day."""
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],  # noqa: S607 - git from PATH
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO_ROOT / line for line in output.splitlines() if line and (REPO_ROOT / line).is_file()]


def dash_and_emoji_findings(name: str, source: str) -> list[str]:
    findings = []
    if EM_DASH in source:
        findings.append(f"{name}: em dash")
    if EN_DASH in source:
        findings.append(f"{name}: en dash")
    if EMOJI.search(source):
        findings.append(f"{name}: emoji")
    return findings


def transcription_findings(name: str, source: str) -> list[str]:
    return [f"{name}: {match.group(0)!r} instead of a real umlaut" for match in TRANSCRIBED_PATTERN.finditer(source)]


def german_texts() -> list[tuple[str, str]]:
    """(name, text) of every German public text."""
    texts = [
        (name, (REPO_ROOT / name).read_text(encoding="utf-8"))
        for name in GERMAN_DOCUMENTS
        if name != "SKELETON.md" or (REPO_ROOT / name).is_file()
    ]
    texts += [
        (f"docs/{path.name}", path.read_text(encoding="utf-8"))
        for path in sorted((REPO_ROOT / "docs").glob("*.md"))
        if not path.name.endswith((".en.md", ".fr.md"))
    ]
    catalogue = json.loads((REPO_ROOT / "l10n" / "de.json").read_text(encoding="utf-8"))
    texts.append(("l10n/de.json", "\n".join(catalogue["translations"].values())))
    info = ElementTree.fromstring((REPO_ROOT / "appinfo" / "info.xml").read_text(encoding="utf-8"))  # noqa: S314
    texts += [(f"info.xml {element.tag} de", element.text or "") for element in info if element.get("lang") == "de"]
    return texts


def test_no_tracked_text_carries_a_dash_or_an_emoji() -> None:
    files = tracked_files()
    assert len(files) > 30

    findings = []
    for path in files:
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative in EXEMPT or path.suffix in BINARY_SUFFIXES:
            continue
        findings += dash_and_emoji_findings(relative, path.read_text(encoding="utf-8"))

    assert findings == []


def test_german_texts_use_real_umlauts() -> None:
    texts = german_texts()
    assert len(texts) >= 8

    findings = [finding for name, source in texts for finding in transcription_findings(name, source)]

    assert findings == []


def test_the_german_texts_really_contain_umlauts() -> None:
    # The positive control: a gate over texts without a single umlaut would be
    # green for the wrong reason.
    joined = "".join(source for _, source in german_texts())

    assert all(letter in joined for letter in "äöüß")


@pytest.mark.parametrize(
    ("sample", "count"),
    [
        ("Gr" + "oesse und f" + "uer alle", 2),
        ("Die Quelle ist aktuell, die Masse stimmt.", 0),
        ("Größe für alle", 0),
    ],
)
def test_the_umlaut_rule_fires_on_transcriptions_only(sample: str, count: int) -> None:
    assert len(transcription_findings("sample", sample)) == count


def test_the_dash_rule_fires() -> None:
    assert dash_and_emoji_findings("s", "a \u2014 b \u2013 c \U0001f600") == ["s: em dash", "s: en dash", "s: emoji"]
    assert dash_and_emoji_findings("s", "a - b, c: d") == []
