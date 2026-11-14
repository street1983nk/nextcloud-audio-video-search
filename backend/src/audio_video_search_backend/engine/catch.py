"""The catch rule per window and the verdict per file (plan 03-06).

Parakeet gives no language of its own. TRANS-03 per D-03-19: a merged VAD window
is dropped when its script is less than half Latin, when its text language is
surely outside the instance languages, or when its mean word confidence is low;
a lower confidence border holds when the text language is surely one of the
instance languages. The file verdict (MEDIA-04 per D-03-11, D-03-12) keeps a
partial transcript from one kept word on and tells "language not supported" from
"no speech" by what was dropped. All thresholds are the measured ones of M-8 and
M-9 in 03-RESEARCH.md (``scripts/research/phase3/verdict.py``); they are
constants, never a setting or an environment value (tests/test_vad_gate.py).

The text language and its probability come in as arguments; the language
identification itself belongs to the engine (plan 03-10).
"""

import unicodedata
from typing import Final

from audio_video_search_backend.engine.constants import SECOND_PASS_MAX_FILE_MS

# D-03-14: the instance languages are fixed in phase 3.
INSTANCE: Final = frozenset({"de", "en", "fr"})

# Per window (M-8): script, text language from 3 words with p >= 0.9, word confidence.
MIN_LATIN: Final = 0.5
LID_P: Final = 0.9
LID_MIN_WORDS: Final = 3
CONF: Final = 0.6
CONF_INSTANCE: Final = 0.5

# Per file with no kept word (M-9).
UNSUPPORTED_DROPS: Final = 5
CONF_DROPS: Final = 10
CONF_SPEECH_MS: Final = 10_000
CONF_SPEECH_SHARE: Final = 0.3

# The verdicts of a window.
KEEP: Final = "keep"
DROP_SCRIPT: Final = "script"
DROP_LANGUAGE: Final = "language"
DROP_CONFIDENCE: Final = "confidence"

# The verdicts of a file.
TRANSCRIPT: Final = "transcript"
NO_SPEECH: Final = "no_speech"
UNSUPPORTED_LANGUAGE: Final = "unsupported_language"


def latin_share(text: str) -> float:
    """The share of Latin letters among the letters of a text; 1.0 without letters."""
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 1.0
    latin = sum(1 for char in letters if "LATIN" in unicodedata.name(char, ""))
    return latin / len(letters)


def window_verdict(latin: float, lid: str, lid_p: float, n_words: int, conf_mean: float) -> str:
    """KEEP or the reason a window is dropped."""
    if latin < MIN_LATIN:
        return DROP_SCRIPT
    if lid not in INSTANCE and lid_p >= LID_P and n_words >= LID_MIN_WORDS:
        return DROP_LANGUAGE
    if conf_mean >= CONF or (lid in INSTANCE and lid_p >= LID_P and conf_mean >= CONF_INSTANCE):
        return KEEP
    return DROP_CONFIDENCE


def file_verdict(
    kept_words: int, drop_script: int, drop_language: int, drop_conf: int, speech_ms: int, duration_ms: int
) -> str:
    """The verdict of a file after its last chunk, from the counted words and the VAD speech."""
    if kept_words >= 1:
        return TRANSCRIPT
    share = speech_ms / duration_ms if duration_ms else 0.0
    if drop_script + drop_language >= UNSUPPORTED_DROPS or (
        drop_conf >= CONF_DROPS and speech_ms >= CONF_SPEECH_MS and share >= CONF_SPEECH_SHARE
    ):
        return UNSUPPORTED_LANGUAGE
    return NO_SPEECH


def needs_second_pass(kept_words: int, duration_ms: int, done: bool) -> bool:
    """D-03-16: one second VAD pass for a file up to 60 s whose first pass kept no word."""
    return kept_words == 0 and duration_ms <= SECOND_PASS_MAX_FILE_MS and not done
