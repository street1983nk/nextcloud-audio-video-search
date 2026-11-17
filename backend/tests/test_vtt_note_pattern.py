"""The VTT the PHP app hands out passes the independent checkers already before the push gate (plan 04-09).

ExportController::withNote (plan 04-10) replaces the header of the container
VTT by ``WEBVTT``, adds a NOTE block with the draft notice T35 and, for a
partial transcript, T15 in the display language of the user, then appends the
cues of the container (D-04-03, D-04-17, EXP-04). PHPUnit runs only in CI, so
this test mirrors the rule in Python (``_with_note``, ``_note_safe``) and puts
the result through webvtt-py (check_vtt) and ffmpeg (check_ffmpeg) for de, en
and fr, each with and without T15: the note is never read as a caption and
every cue arrives.

The negative control shows that the PHP filter of note lines is needed: a
NOTE line with "-->" breaks the file for a checker. The mirror gate binds the
Python copy to the PHP source: when someone changes the literals or the
filter in ExportController.php, this test fails until the mirror follows.
"""

import json
import re
from collections.abc import Sequence
from typing import Final

import pytest

from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.subtitles.cues import Cue, build_cues
from audio_video_search_backend.subtitles.formats import to_vtt
from tests.conftest import REPO_ROOT
from tests.subtitle_checkers import SubtitleCheckError, check_ffmpeg, check_vtt, read_vtt_captions
from tests.test_subtitles_cues import _fast_words, _normal_words, _word

PHP_ROOT: Final = REPO_ROOT / "php"
CONTROLLER: Final = PHP_ROOT / "lib" / "Controller" / "ExportController.php"
T35: Final = "Subtitle draft, created automatically and not reviewed."
T15: Final = "Transcript up to %s, the file is still being processed."
LANGUAGES: Final = ("de", "en", "fr")
CLOCKS: Final = ("12:34", "1:02:03")


# -- the Python mirror of ExportController::withNote and ::noteSafe ----------


def _with_note(vtt: str, lines: Sequence[str]) -> str:
    """Mirror of ExportController::withNote: header replaced, NOTE block, then the cues."""
    separator = vtt.find("\n\n")
    rest = ("" if separator == -1 else vtt[separator + 2 :]) if vtt.startswith("WEBVTT") else vtt
    if not lines:
        return "WEBVTT\n\n" + rest
    return "WEBVTT\n\nNOTE\n" + "\n".join(lines) + "\n\n" + rest


def _note_safe(lines: Sequence[str]) -> list[str]:
    """Mirror of ExportController::noteSafe: no arrow, no line break in a note line."""
    return [line for line in lines if "-->" not in line and "\n" not in line and "\r" not in line]


def _catalogue(language: str) -> dict[str, str]:
    data = json.loads((PHP_ROOT / "l10n" / f"{language}.json").read_text(encoding="utf-8"))
    return data["translations"]


def _note_lines(language: str, clock: str | None) -> list[str]:
    """T35 and, for a partial transcript, T15 with the clock, as headerLines builds them."""
    catalogue = _catalogue(language)
    lines = [catalogue[T35]]
    if clock is not None:
        lines.append(catalogue[T15].replace("%s", clock, 1))
    return lines


def _special_words() -> list[Word]:
    return [_word(0, 400, "Bürger"), _word(450, 900, "&"), _word(950, 1400, "a<b"), _word(1450, 2000, "Straße.")]


FIXTURES: Final = {"normal": _normal_words, "fast": _fast_words, "special": _special_words}
NOTE_CASES: Final = [(language, clock) for language in LANGUAGES for clock in (None, *CLOCKS)]


def _assert_checkers_read_every_cue(text: str, cues: Sequence[Cue]) -> None:
    check_vtt(text)
    captions = read_vtt_captions(text)
    assert len(captions) == len(cues)
    assert [caption.text for caption in captions] == ["\n".join(cue.lines) for cue in cues]
    assert [(caption.start_ms, caption.end_ms) for caption in captions] == [(c.start_ms, c.end_ms) for c in cues]
    check_ffmpeg(text, ".vtt", expected_cues=len(cues))


def test_every_catalogue_has_both_note_lines_and_they_are_note_safe() -> None:
    for language in LANGUAGES:
        for clock in CLOCKS:
            lines = _note_lines(language, clock)
            assert len(lines) == 2
            assert _note_safe(lines) == lines
            assert clock in lines[1]


@pytest.mark.parametrize("fixture", sorted(FIXTURES))
@pytest.mark.parametrize(("language", "clock"), NOTE_CASES)
def test_the_php_note_pattern_passes_webvtt_py_and_ffmpeg(fixture: str, language: str, clock: str | None) -> None:
    cues = build_cues(FIXTURES[fixture]())
    lines = _note_safe(_note_lines(language, clock))

    text = _with_note(to_vtt(cues), lines)

    assert text.startswith("WEBVTT\n\nNOTE\n" + lines[0] + "\n")
    assert (clock is not None) == (len(lines) == 2)
    _assert_checkers_read_every_cue(text, cues)


def test_without_note_lines_the_container_vtt_stays_as_it_came() -> None:
    cues = build_cues(_normal_words())
    vtt = to_vtt(cues)

    assert _with_note(vtt, []) == vtt
    _assert_checkers_read_every_cue(_with_note(vtt, []), cues)


def test_the_special_cue_keeps_its_masked_characters_after_the_note() -> None:
    cues = build_cues(_special_words())
    text = _with_note(to_vtt(cues), _note_lines("de", "12:34"))

    assert "&amp;" in text
    assert "a&lt;b" in text
    assert "Bürger" in text
    assert "Straße." in text
    assert "\n".join(caption.text for caption in read_vtt_captions(text)) == "\n".join(
        "\n".join(cue.lines) for cue in cues
    )


def test_an_arrow_in_a_note_line_breaks_the_file_for_a_checker() -> None:
    # Negative control: without the PHP filter such a line ends the note and
    # becomes a cue timing; webvtt-py or ffmpeg must notice.
    cues = build_cues(_normal_words())
    broken = _with_note(to_vtt(cues), ["Entwurf 00:00:01.000 --> 00:00:02.000 nicht geprüft"])

    with pytest.raises(SubtitleCheckError):
        _assert_checkers_read_every_cue(broken, cues)
    assert _note_safe(["Entwurf 00:00:01.000 --> 00:00:02.000 nicht geprüft"]) == []


# -- mirror gate: the Python copy follows the PHP source ---------------------

_WITH_NOTE_BODY = re.compile(
    r"public static function withNote\(string \$vtt, array \$lines\): string \{(?P<body>.*?)\n\t\}", re.DOTALL
)
_NOTE_SAFE_BODY = re.compile(
    r"private function noteSafe\(array \$lines, int \$fileId\): array \{(?P<body>.*?)\n\t\}", re.DOTALL
)
# The statements of withNote the mirror copies, in their order.
WITH_NOTE_STATEMENTS: Final = (
    '$separator = strpos($vtt, "\\n\\n");',
    "$rest = str_starts_with($vtt, 'WEBVTT')",
    "? ($separator === false ? '' : substr($vtt, $separator + 2))",
    ": $vtt;",
    "if ($lines === []) {",
    'return "WEBVTT\\n\\n" . $rest;',
    'return "WEBVTT\\n\\nNOTE\\n" . implode("\\n", $lines) . "\\n\\n" . $rest;',
)
NOTE_SAFE_CONDITION: Final = (
    'if (str_contains($line, \'-->\') || str_contains($line, "\\n") || str_contains($line, "\\r")) {'
)


def _mirror_findings(source: str) -> list[str]:
    """What in the PHP source no longer matches the Python mirror; empty when it does."""
    findings: list[str] = []
    with_note = _WITH_NOTE_BODY.search(source)
    if with_note is None:
        findings.append("withNote not found")
    else:
        statements = [line.strip() for line in with_note["body"].splitlines() if line.strip()]
        wanted = iter(statements)
        for statement in WITH_NOTE_STATEMENTS:
            if statement not in wanted:  # consumes the iterator: order matters
                findings.append(f"withNote lacks {statement}")
                break
    note_safe = _NOTE_SAFE_BODY.search(source)
    if note_safe is None or NOTE_SAFE_CONDITION not in note_safe["body"]:
        findings.append("noteSafe lacks the arrow and line break filter")
    return findings


def test_the_mirror_follows_the_php_note_pattern() -> None:
    assert _mirror_findings(CONTROLLER.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    ("original", "mutated"),
    [
        ('"WEBVTT\\n\\nNOTE\\n" . implode', '"WEBVTT\\nNOTE\\n" . implode'),
        ('implode("\\n", $lines) . "\\n\\n" . $rest', 'implode("\\n", $lines) . "\\n" . $rest'),
        ("$separator + 2", "$separator + 1"),
        ("str_contains($line, '-->') || ", ""),
    ],
)
def test_self_the_mirror_gate_fires_on_a_changed_php_pattern(original: str, mutated: str) -> None:
    source = CONTROLLER.read_text(encoding="utf-8")
    assert original in source

    assert _mirror_findings(source.replace(original, mutated, 1)) != []
