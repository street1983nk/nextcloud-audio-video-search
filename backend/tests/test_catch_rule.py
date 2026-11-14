"""The catch rule per window and the verdict per file (plan 03-06, TRANS-03, MEDIA-04).

Parakeet gives no language of its own. The rule of D-03-19 works per merged VAD
window from the script, the text language and the word confidence; the file
verdict of D-03-11 and D-03-12 counts what the rule kept and dropped. Every case
below is a row of the measurements M-8 and M-9 in 03-RESEARCH.md or a border of
a measured threshold, so a moved threshold breaks a named case. The rule of
D-03-22 (much VAD speech, no kept word) is measured with
``scripts/research/phase3/verdict22.py`` on the same corpus (plan 03-13).
"""

import pytest

from audio_video_search_backend.engine import catch


@pytest.mark.parametrize(
    ("latin", "lid", "lid_p", "n_words", "conf_mean", "expected"),
    [
        pytest.param(0.0, "ru", 1.0, 20, 0.95, catch.DROP_SCRIPT, id="cyrillic"),
        pytest.param(1.0, "es", 0.98, 12, 0.97, catch.DROP_LANGUAGE, id="spanish-clean"),
        pytest.param(1.0, "es", 0.98, 2, 0.97, catch.KEEP, id="two-words-no-language-decision"),
        pytest.param(1.0, "en", 0.97, 6, 0.34, catch.DROP_CONFIDENCE, id="word-salad-as-english"),
        pytest.param(1.0, "mt", 1.0, 8, 0.39, catch.DROP_LANGUAGE, id="arabic-as-maltese"),
        pytest.param(1.0, "de", 0.95, 10, 0.55, catch.KEEP, id="sure-instance-language"),
        pytest.param(1.0, "de", 0.95, 10, 0.49, catch.DROP_CONFIDENCE, id="sure-instance-below-half"),
        pytest.param(1.0, "de", 0.85, 10, 0.55, catch.DROP_CONFIDENCE, id="unsure-instance-below-0.6"),
        pytest.param(1.0, "fr", 0.5, 4, 0.60, catch.KEEP, id="confidence-border-inclusive"),
        pytest.param(0.5, "de", 0.95, 4, 0.9, catch.KEEP, id="script-border-inclusive"),
        # Borders of the language rule: p and the word count are inclusive.
        pytest.param(1.0, "es", 0.9, 3, 0.97, catch.DROP_LANGUAGE, id="language-borders-inclusive"),
        pytest.param(1.0, "es", 0.89, 3, 0.97, catch.KEEP, id="language-p-below-border"),
        pytest.param(1.0, "de", 0.9, 10, 0.5, catch.KEEP, id="instance-borders-inclusive"),
    ],
)
def test_window_verdict(latin: float, lid: str, lid_p: float, n_words: int, conf_mean: float, expected: str) -> None:
    assert catch.window_verdict(latin, lid, lid_p, n_words, conf_mean) == expected


@pytest.mark.parametrize(
    ("kept", "drop_script", "drop_language", "drop_conf", "speech_ms", "duration_ms", "expected"),
    [
        pytest.param(18, 0, 139, 77, 106_000, 139_000, catch.TRANSCRIPT, id="mix-de10-ar90"),
        pytest.param(0, 0, 175, 0, 68_000, 90_000, catch.UNSUPPORTED_LANGUAGE, id="spanish"),
        pytest.param(0, 191, 0, 0, 96_000, 120_000, catch.UNSUPPORTED_LANGUAGE, id="russian"),
        pytest.param(0, 0, 0, 27, 52_100, 376_000, catch.NO_SPEECH, id="spohr-share-14"),
        pytest.param(0, 0, 0, 12, 63_000, 100_000, catch.UNSUPPORTED_LANGUAGE, id="confidence-63s-63"),
        pytest.param(0, 0, 0, 0, 0, 300_000, catch.NO_SPEECH, id="silence"),
        pytest.param(0, 2, 2, 0, 2_000, 10_000, catch.NO_SPEECH, id="script-plus-language-4"),
        # Borders of the confidence branch, each one inclusive, each one just below.
        pytest.param(0, 3, 2, 0, 5_000, 10_000, catch.UNSUPPORTED_LANGUAGE, id="script-plus-language-5"),
        pytest.param(0, 0, 0, 10, 10_000, 20_000, catch.UNSUPPORTED_LANGUAGE, id="count-and-speech-borders"),
        pytest.param(0, 0, 0, 10, 30_000, 100_000, catch.UNSUPPORTED_LANGUAGE, id="share-border-inclusive"),
        pytest.param(0, 0, 0, 9, 45_000, 100_000, catch.NO_SPEECH, id="confidence-9-words"),
        pytest.param(0, 0, 0, 12, 9_999, 20_000, catch.NO_SPEECH, id="speech-below-10s"),
        pytest.param(0, 0, 0, 12, 29_999, 100_000, catch.NO_SPEECH, id="share-below-30"),
        pytest.param(1, 0, 500, 500, 100_000, 100_000, catch.TRANSCRIPT, id="one-kept-word"),
        pytest.param(0, 0, 0, 0, 0, 0, catch.NO_SPEECH, id="empty-file"),
        # D-03-22, measured in plan 03-13 (verdict22.py): much VAD speech and no kept word.
        pytest.param(0, 0, 0, 0, 9_070, 14_160, catch.UNSUPPORTED_LANGUAGE, id="turkish-clip-no-token"),
        pytest.param(0, 0, 0, 16, 4_430, 5_100, catch.UNSUPPORTED_LANGUAGE, id="hindi-clip-short"),
        pytest.param(0, 0, 0, 8, 7_690, 13_740, catch.UNSUPPORTED_LANGUAGE, id="chinese-clip-share-56"),
        pytest.param(0, 0, 0, 0, 74_400, 166_700, catch.NO_SPEECH, id="senfl-a-cappella-share-45"),
        pytest.param(0, 0, 0, 4, 2_100, 3_200, catch.NO_SPEECH, id="two-word-memo-without-a-kept-word"),
        pytest.param(0, 0, 0, 0, 3_000, 6_000, catch.UNSUPPORTED_LANGUAGE, id="speech-only-borders-inclusive"),
        pytest.param(0, 0, 0, 0, 2_999, 4_000, catch.NO_SPEECH, id="speech-only-below-3s"),
        pytest.param(0, 0, 0, 0, 4_999, 10_000, catch.NO_SPEECH, id="speech-only-share-below-half"),
        pytest.param(1, 0, 0, 0, 9_070, 14_160, catch.TRANSCRIPT, id="speech-only-but-one-kept-word"),
    ],
)
def test_file_verdict(
    kept: int, drop_script: int, drop_language: int, drop_conf: int, speech_ms: int, duration_ms: int, expected: str
) -> None:
    assert catch.file_verdict(kept, drop_script, drop_language, drop_conf, speech_ms, duration_ms) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Größe", 1.0),
        ("Привет", 0.0),
        ("", 1.0),
        ("12 3", 1.0),
        ("ab вг", 0.5),
        ("Ελλάδα und", 1 / 3),
    ],
)
def test_latin_share(text: str, expected: float) -> None:
    assert catch.latin_share(text) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("kept", "duration_ms", "done", "expected"),
    [
        (0, 60_000, False, True),
        (0, 60_001, False, False),
        (1, 30_000, False, False),
        (0, 30_000, True, False),
    ],
)
def test_needs_second_pass(kept: int, duration_ms: int, done: bool, expected: bool) -> None:
    assert catch.needs_second_pass(kept_words=kept, duration_ms=duration_ms, done=done) is expected


def test_the_instance_languages_are_fixed() -> None:
    assert frozenset({"de", "en", "fr"}) == catch.INSTANCE


def test_the_verdicts_are_distinct_texts() -> None:
    windows = {catch.KEEP, catch.DROP_SCRIPT, catch.DROP_LANGUAGE, catch.DROP_CONFIDENCE}
    files = {catch.TRANSCRIPT, catch.NO_SPEECH, catch.UNSUPPORTED_LANGUAGE}
    assert len(windows) == 4
    assert len(files) == 3
    assert all(isinstance(value, str) and value for value in windows | files)
