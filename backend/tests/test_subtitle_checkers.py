"""Positive and negative control of the three independent subtitle checkers (plan 04-04).

Each checker must pass a hand written valid file and must fire on broken ones,
otherwise a green export test (plans 04-08, 04-09, 04-14) would prove nothing.
The literals are written by hand here, never produced by the writer under test.
A broken variant a checker does not catch is named as a strict xfail with its
reason, so the gap stays visible and the test fails once the checker learns it.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tests.subtitle_checkers import (
    Cue,
    SubtitleCheckError,
    check_ffmpeg,
    check_srt,
    check_vtt,
    read_srt_subtitles,
    read_vtt_captions,
)

VALID_VTT = (
    "WEBVTT\n"
    "\n"
    "NOTE Entwurf aus der Spracherkennung, bitte prüfen\n"
    "\n"
    "00:00:01.000 --> 00:00:03.500\n"
    "Grüße aus der Sitzung\n"
    "\n"
    "00:00:04.000 --> 00:00:06.250\n"
    "Haushalt &amp; Planung für Köln\n"
)

VALID_SRT = (
    "1\n"
    "00:00:01,000 --> 00:00:03,500\n"
    "Grüße aus der Sitzung\n"
    "\n"
    "2\n"
    "00:00:04,000 --> 00:00:06,250\n"
    "Haushalt & Planung für Köln\n"
)

EXPECTED = [
    Cue(1000, 3500, "Grüße aus der Sitzung"),
    Cue(4000, 6250, "Haushalt & Planung für Köln"),
]

VTT_WITHOUT_HEADER = VALID_VTT.removeprefix("WEBVTT\n\n")
VTT_SHORT_ARROW = VALID_VTT.replace("00:00:01.000 --> 00:00:03.500", "00:00:01.000 -> 00:00:02.000")
VTT_END_BEFORE_START = VALID_VTT.replace("00:00:04.000 --> 00:00:06.250", "00:00:06.250 --> 00:00:04.000")
VTT_GARBAGE = "das ist keine Untertiteldatei\n"

SRT_NO_BLANK_LINE = VALID_SRT.replace("Sitzung\n\n2\n", "Sitzung\n2\n")
SRT_TEXT_ON_TIMING_LINE = VALID_SRT.replace(
    "00:00:04,000 --> 00:00:06,250\n", "00:00:04,000 --> 00:00:06,250 Haushalt\n"
)
SRT_END_BEFORE_START = VALID_SRT.replace("00:00:04,000 --> 00:00:06,250", "00:00:06,250 --> 00:00:04,000")
SRT_GARBAGE = "das ist keine Untertiteldatei\n"

NO_BLANK_LINE_GAP = (
    "known limit: srt and ffmpeg both recover two SRT cues without the blank line between them; "
    "export tests compare the exact text they expect"
)


class CheckerMissedIt(AssertionError):
    """A checker passed a broken file. Only this exception satisfies a known-limit xfail.

    A missing ffmpeg under CI=true raises pytest's own failure, which these
    xfail marks do not accept, so it can never pass as an expected gap.
    """


def expect_fire(check: Callable[[], None]) -> None:
    try:
        check()
    except SubtitleCheckError:
        return
    raise CheckerMissedIt("the checker passed a broken file")


# webvtt-py


def test_webvtt_reads_the_valid_file() -> None:
    check_vtt(VALID_VTT)
    assert read_vtt_captions(VALID_VTT) == EXPECTED


@pytest.mark.parametrize(
    "broken",
    [VTT_WITHOUT_HEADER, VTT_SHORT_ARROW, VTT_END_BEFORE_START, VTT_GARBAGE],
    ids=["no-header", "short-arrow", "end-before-start", "garbage"],
)
def test_webvtt_fires_on_broken_files(broken: str) -> None:
    with pytest.raises(SubtitleCheckError):
        check_vtt(broken)


# srt


def test_srt_reads_the_valid_file() -> None:
    check_srt(VALID_SRT)
    assert read_srt_subtitles(VALID_SRT) == EXPECTED


@pytest.mark.parametrize(
    "broken",
    [SRT_TEXT_ON_TIMING_LINE, SRT_END_BEFORE_START, SRT_GARBAGE],
    ids=["text-on-timing-line", "end-before-start", "garbage"],
)
def test_srt_fires_on_broken_files(broken: str) -> None:
    with pytest.raises(SubtitleCheckError):
        check_srt(broken)


@pytest.mark.xfail(strict=True, raises=CheckerMissedIt, reason=NO_BLANK_LINE_GAP)
def test_srt_known_limit_no_blank_line() -> None:
    expect_fire(lambda: check_srt(SRT_NO_BLANK_LINE))


def test_no_blank_line_is_recovered_not_lost() -> None:
    """srt reads both cues of the gap case unchanged, so the gap hides no lost text."""
    assert read_srt_subtitles(SRT_NO_BLANK_LINE) == EXPECTED


# ffmpeg


@pytest.mark.parametrize(("text", "suffix"), [(VALID_VTT, ".vtt"), (VALID_SRT, ".srt")], ids=["vtt", "srt"])
def test_ffmpeg_decodes_the_valid_files(text: str, suffix: str) -> None:
    check_ffmpeg(text, suffix, expected_cues=2)


@pytest.mark.parametrize(
    ("broken", "suffix"),
    [
        (VTT_SHORT_ARROW, ".vtt"),
        (VTT_GARBAGE, ".vtt"),
        (SRT_GARBAGE, ".srt"),
    ],
    ids=["vtt-short-arrow", "vtt-garbage", "srt-garbage"],
)
def test_ffmpeg_fires_on_broken_files(broken: str, suffix: str) -> None:
    with pytest.raises(SubtitleCheckError):
        check_ffmpeg(broken, suffix, expected_cues=2)


FFMPEG_GAP = "ffmpeg decodes it without a word (known limit); webvtt-py catches it"


@pytest.mark.parametrize(
    ("broken", "suffix"),
    [
        pytest.param(
            VTT_WITHOUT_HEADER,
            ".vtt",
            id="vtt-no-header",
            marks=pytest.mark.xfail(strict=True, raises=CheckerMissedIt, reason=FFMPEG_GAP),
        ),
        pytest.param(
            VTT_END_BEFORE_START,
            ".vtt",
            id="vtt-end-before-start",
            marks=pytest.mark.xfail(strict=True, raises=CheckerMissedIt, reason=FFMPEG_GAP),
        ),
        pytest.param(
            SRT_NO_BLANK_LINE,
            ".srt",
            id="srt-no-blank-line",
            marks=pytest.mark.xfail(strict=True, raises=CheckerMissedIt, reason=NO_BLANK_LINE_GAP),
        ),
    ],
)
def test_ffmpeg_known_limits(broken: str, suffix: str) -> None:
    expect_fire(lambda: check_ffmpeg(broken, suffix, expected_cues=2))
