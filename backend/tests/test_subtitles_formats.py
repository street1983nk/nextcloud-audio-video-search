"""Format writers against the three independent checkers (EXP-02, plan 04-08).

Fuzz cases and the NORMAL/FAST fixtures come from test_subtitles_cues (same
generator, fixed seed, plan 04-07). Every expectation here reads the output
with webvtt-py, srt or ffmpeg through tests.subtitle_checkers and never with
the writer's own logic (owner rule: the cross check never uses the pattern of
the implementation).

check_ffmpeg counts the "-->" lines of the SRT that ffmpeg re-encodes to
stdout (plan 04-04: ffmpeg drops an unreadable cue silently, only the count
shows the loss). A cue line whose text itself carries "-->" counts once more:
ffmpeg writes the line back verbatim for SRT and unescapes ``--&gt;`` for
VTT, measured 2026-11-16 with ffmpeg 8.1.1. ``_ffmpeg_expected`` adds those
lines, so the count check stays sharp for every fuzz case.
"""

import html
import re
from collections.abc import Sequence

import webvtt

from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.subtitles.cues import Cue, build_cues
from audio_video_search_backend.subtitles.formats import TXT_PARAGRAPH_PAUSE_MS, to_srt, to_txt, to_vtt
from tests.subtitle_checkers import check_ffmpeg, check_srt, check_vtt, read_srt_subtitles, read_vtt_captions
from tests.test_subtitles_cues import _FUZZ, _fast_words, _normal_words, _visible_tokens, _word


def _cases() -> list[list[Word]]:
    """All fuzz cases of plan 04-07 plus the NORMAL and FAST fixtures."""
    return [*_FUZZ, _normal_words(), _fast_words()]


def _ffmpeg_expected(cues: Sequence[Cue]) -> int:
    """len(cues) plus the cue text lines that carry "-->" themselves (module docstring)."""
    return len(cues) + sum(1 for cue in cues for line in cue.lines if "-->" in line)


def test_the_pause_constant_holds_the_agreed_value() -> None:
    assert TXT_PARAGRAPH_PAUSE_MS == 2000


def test_empty_input_yields_the_bare_vtt_header_and_empty_srt_and_txt() -> None:
    assert to_srt([]) == ""
    assert to_txt([]) == ""
    header_only = to_vtt([])
    assert header_only == "WEBVTT\n" + "\n"
    # webvtt-py (not our code) reads the header-only file as valid with zero
    # captions; the shared checker refuses zero captions on purpose, so this
    # one case talks to the library directly.
    document = webvtt.WebVTT.from_string(header_only, strict=True)
    assert list(document.captions) == []
    assert [issue for issue in document.validate() if issue.severity == "error"] == []


def test_clock_literals_at_12_hours_and_above_100_hours() -> None:
    twelve = Cue(45_296_789, 45_297_789, ("hallo",))
    hundred = Cue(360_000_000, 360_005_000, ("hallo",))

    assert "12:34:56,789 --> 12:34:57,789" in to_srt([twelve])
    assert "12:34:56.789 --> 12:34:57.789" in to_vtt([twelve])
    assert "100:00:00,000 --> 100:00:05,000" in to_srt([hundred])
    assert "100:00:00.000 --> 100:00:05.000" in to_vtt([hundred])

    for cue in (twelve, hundred):
        assert [(c.start_ms, c.end_ms) for c in read_srt_subtitles(to_srt([cue]))] == [(cue.start_ms, cue.end_ms)]
        assert [(c.start_ms, c.end_ms) for c in read_vtt_captions(to_vtt([cue]))] == [(cue.start_ms, cue.end_ms)]


def test_vtt_masks_markup_and_both_parsers_read_the_text_back() -> None:
    cue = Cue(0, 2000, ("a --> b <i>x</i> & y",))

    vtt_text = to_vtt([cue])
    assert "a --&gt; b &lt;i&gt;x&lt;/i&gt; &amp; y" in vtt_text
    assert [c.text for c in read_vtt_captions(vtt_text)] == ["a --> b <i>x</i> & y"]

    srt_text = to_srt([cue])
    assert "\na --> b <i>x</i> & y\n" in srt_text
    assert [c.text for c in read_srt_subtitles(srt_text)] == ["a --> b <i>x</i> & y"]

    check_ffmpeg(vtt_text, ".vtt", expected_cues=_ffmpeg_expected([cue]))
    check_ffmpeg(srt_text, ".srt", expected_cues=_ffmpeg_expected([cue]))


def test_fuzz_and_fixture_cues_pass_both_library_checkers_with_exact_content() -> None:
    for words in _cases():
        cues = build_cues(words)
        if not cues:
            assert to_srt(cues) == ""
            assert to_vtt(cues) == "WEBVTT\n\n"
            continue
        vtt_text = to_vtt(cues)
        srt_text = to_srt(cues)
        check_vtt(vtt_text)
        check_srt(srt_text)
        for parsed in (read_vtt_captions(vtt_text), read_srt_subtitles(srt_text)):
            assert len(parsed) == len(cues)
            for ours, theirs in zip(cues, parsed, strict=True):
                assert theirs.start_ms == ours.start_ms
                assert theirs.end_ms == ours.end_ms
                assert theirs.text == "\n".join(ours.lines)


def test_fuzz_and_fixture_outputs_pass_ffmpeg_with_the_expected_cue_count() -> None:
    for words in _cases():
        cues = build_cues(words)
        if not cues:
            continue
        check_ffmpeg(to_vtt(cues), ".vtt", expected_cues=_ffmpeg_expected(cues))
        check_ffmpeg(to_srt(cues), ".srt", expected_cues=_ffmpeg_expected(cues))


def test_output_carries_no_cr_no_bom_and_no_triple_newline() -> None:
    # A blank line inside a cue would change the parsed cue count, which the
    # exact-content test above pins; here the byte-level rules are held.
    for words in _cases():
        cues = build_cues(words)
        for text in (to_srt(cues), to_vtt(cues), to_txt(words)):
            assert "\r" not in text
            assert "\ufeff" not in text
            assert "\n\n\n" not in text


def test_txt_breaks_a_paragraph_only_above_the_pause_threshold() -> None:
    at_threshold = [_word(0, 500, "eins"), _word(500 + TXT_PARAGRAPH_PAUSE_MS, 3200, "zwei")]
    above = [_word(0, 500, "eins"), _word(501 + TXT_PARAGRAPH_PAUSE_MS, 3200, "zwei")]

    assert to_txt(at_threshold) == "eins zwei\n"
    assert to_txt(above) == "eins\n\nzwei\n"


def test_txt_is_flow_text_without_time_marks() -> None:
    text = to_txt(_normal_words())

    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert re.search(r"\d\d:\d\d", text) is None
    assert "-->" not in text


def test_txt_text_stays_wordwise_identical_across_the_fuzz_cases() -> None:
    for words in _FUZZ:
        assert to_txt(words).split() == _visible_tokens(words)


def test_the_writers_add_no_words_of_their_own() -> None:
    # Text equality line by line: everything beside cue numbers, timing lines
    # and the WEBVTT head is exactly the cue text, so no word (and no "BITV")
    # can come from the writer (EXP-04, T-04-23). The fixture surfaces carry
    # neither "-->" nor digit-only lines, so the line filter is exact.
    for words in (_normal_words(), _fast_words()):
        cues = build_cues(words)
        wanted = [line for cue in cues for line in cue.lines]
        srt_lines = [line for line in to_srt(cues).splitlines() if line and "-->" not in line and not line.isdigit()]
        assert srt_lines == wanted
        vtt_lines = [
            html.unescape(line) for line in to_vtt(cues).splitlines() if line and "-->" not in line and line != "WEBVTT"
        ]
        assert vtt_lines == wanted
        assert to_txt(words).split() == _visible_tokens(words)
