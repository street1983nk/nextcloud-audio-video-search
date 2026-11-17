"""The measured values of the preview engine are constants with a test (plan 03-06).

TRANS-01: the Parakeet pipeline runs with the settings of Spike 3, taken 1:1 from
``scripts/research/phase3/measure.py`` (itself 1:1 from Spike 3 ``bench3.py``).
D-03-16: the second VAD pass is a fixed constant, not a switch. TRANS-07: the
chunk values of RESEARCH Pattern 2. TRANS-06: the provenance of a transcript
names ``CONFIG_VERSION``; every changed constant needs a new one.

Each value is compared one by one with the number of the measurement. On top,
a fingerprint of every constant of ``engine/constants.py`` and ``engine/catch.py``
is compared with a fixed text, so that no value, and no new or removed constant,
moves without this file changing in the same commit.
"""

import ast
import inspect
from types import ModuleType

import pytest

from audio_video_search_backend.engine import catch, constants


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # measure.py: SR, VadModelConfig, VoiceActivityDetector.
        ("SAMPLE_RATE", 16000),
        ("VAD_THRESHOLD", 0.5),
        ("VAD_MIN_SILENCE_S", 0.3),
        ("VAD_MIN_SPEECH_S", 0.25),
        ("VAD_MAX_SPEECH_S", 25),
        ("VAD_THREADS", 1),
        ("VAD_BUFFER_S", 60),
        # measure.py run(): merge while the gap is at most 2 s and the window at most WIN = 25 s.
        ("MERGE_GAP_S", 2),
        ("WINDOW_MAX_S", 25),
        # measure.py dec_span(): CTX = 0.4 s, PAD = SR // 2, safe() pads to SR // 2, token 0.08 s.
        ("CONTEXT_S", 0.4),
        ("PAD_S", 0.5),
        ("MIN_DECODE_S", 0.5),
        ("TOKEN_S", 0.08),
        # measure.py run(): the swallow guard GUARD = 1.0 word/s for parts from 1.0 s, slack 0.3 s.
        ("GUARD_WORDS_PER_S", 1.0),
        ("GUARD_MIN_S", 1.0),
        ("GUARD_SLACK_S", 0.3),
        # measure.py OfflineRecognizer.from_transducer.
        ("RECOGNIZER_THREADS", 2),
        ("DECODING_METHOD", "greedy_search"),
        ("MODEL_TYPE", "nemo_transducer"),
        # D-03-16 and M-10: threshold 0.3, minimum speech 0.1 s, files up to 60 s.
        ("SECOND_PASS_THRESHOLD", 0.3),
        ("SECOND_PASS_MIN_SPEECH_S", 0.1),
        ("SECOND_PASS_MAX_FILE_MS", 60_000),
        # RESEARCH Pattern 2: chunks of 10 min, 1 s context, 60 s lookahead.
        ("CHUNK_MS", 600_000),
        ("CHUNK_CONTEXT_MS", 1_000),
        ("CHUNK_LOOKAHEAD_MS", 60_000),
        # TRANS-06: 2 since D-03-23 (plan 03-13b), the second pass drops words it kept before.
        ("CONFIG_VERSION", 2),
    ],
)
def test_pipeline_constant(name: str, expected: object) -> None:
    assert getattr(constants, name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # D-03-14.
        ("INSTANCE", frozenset({"de", "en", "fr"})),
        # M-8, chosen row of the grid: script 0.5, P 0.9 from 3 words, C 0.6, C2 0.5.
        ("MIN_LATIN", 0.5),
        ("LID_P", 0.9),
        ("LID_MIN_WORDS", 3),
        ("CONF", 0.6),
        ("CONF_INSTANCE", 0.5),
        # M-9: script + language >= 5, or confidence >= 10 with speech >= 10 s and share >= 30 %.
        ("UNSUPPORTED_DROPS", 5),
        ("CONF_DROPS", 10),
        ("CONF_SPEECH_MS", 10_000),
        ("CONF_SPEECH_SHARE", 0.3),
        # D-03-22, plan 03-13 (verdict22.py): no kept word, VAD speech >= 3 s and share >= 50 %;
        # the middles of the measured gaps (2,1 s / 4,3 s and 45 % / 55 %).
        ("SPEECH_ONLY_MS", 3_000),
        ("SPEECH_ONLY_SHARE", 0.5),
        # D-03-23, owner option A (plan 03-13b, verdict23.py / eval23.py): second pass from a mean
        # word confidence of 0.68 on; the gap between JA 0.658 and the FR memo 0.7034.
        ("SECOND_PASS_CONF", 0.68),
    ],
)
def test_catch_constant(name: str, expected: object) -> None:
    assert getattr(catch, name) == expected


def _own_constants(module: ModuleType) -> dict[str, object]:
    """The upper-case names a module assigns itself at its top level, with their values."""
    names: list[str] = []
    for node in ast.parse(inspect.getsource(module)).body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        names += [target.id for target in targets if isinstance(target, ast.Name) and target.id.isupper()]
    return {name: getattr(module, name) for name in names}


def _render(value: object) -> str:
    if isinstance(value, frozenset):
        return "{" + ",".join(sorted(repr(item) for item in value)) + "}"
    return repr(value)


def fingerprint() -> str:
    lines = [
        f"{module.__name__.rsplit('.', 1)[-1]}.{name}={_render(value)}"
        for module in (constants, catch)
        for name, value in _own_constants(module).items()
    ]
    return "\n".join(sorted(lines))


EXPECTED_FINGERPRINT = """\
catch.CONF=0.6
catch.CONF_DROPS=10
catch.CONF_INSTANCE=0.5
catch.CONF_SPEECH_MS=10000
catch.CONF_SPEECH_SHARE=0.3
catch.DROP_CONFIDENCE='confidence'
catch.DROP_LANGUAGE='language'
catch.DROP_SCRIPT='script'
catch.INSTANCE={'de','en','fr'}
catch.KEEP='keep'
catch.LID_MIN_WORDS=3
catch.LID_P=0.9
catch.MIN_LATIN=0.5
catch.NO_SPEECH='no_speech'
catch.SECOND_PASS_CONF=0.68
catch.SPEECH_ONLY_MS=3000
catch.SPEECH_ONLY_SHARE=0.5
catch.TRANSCRIPT='transcript'
catch.UNSUPPORTED_DROPS=5
catch.UNSUPPORTED_LANGUAGE='unsupported_language'
constants.CHUNK_CONTEXT_MS=1000
constants.CHUNK_LOOKAHEAD_MS=60000
constants.CHUNK_MS=600000
constants.CONFIG_VERSION=2
constants.CONTEXT_S=0.4
constants.DECODING_METHOD='greedy_search'
constants.GUARD_MIN_S=1.0
constants.GUARD_SLACK_S=0.3
constants.GUARD_WORDS_PER_S=1.0
constants.MERGE_GAP_S=2.0
constants.MIN_DECODE_S=0.5
constants.MODEL_TYPE='nemo_transducer'
constants.PAD_S=0.5
constants.RECOGNIZER_THREADS=2
constants.SAMPLE_RATE=16000
constants.SECOND_PASS_MAX_FILE_MS=60000
constants.SECOND_PASS_MIN_SPEECH_S=0.1
constants.SECOND_PASS_THRESHOLD=0.3
constants.TOKEN_S=0.08
constants.VAD_BUFFER_S=60.0
constants.VAD_MAX_SPEECH_S=25.0
constants.VAD_MIN_SILENCE_S=0.3
constants.VAD_MIN_SPEECH_S=0.25
constants.VAD_THREADS=1
constants.VAD_THRESHOLD=0.5
constants.WINDOW_MAX_S=25.0"""


def test_the_fingerprint_of_all_constants_is_fixed() -> None:
    assert fingerprint() == EXPECTED_FINGERPRINT, "constant changed: raise CONFIG_VERSION and update this fingerprint"


def test_the_fingerprint_sees_every_constant_the_value_tests_name() -> None:
    """Counter test of the fingerprint helper: it finds the names, not an empty list."""
    lines = fingerprint().splitlines()
    assert "constants.CONFIG_VERSION=2" in lines
    assert "catch.CONF=0.6" in lines
    assert "catch.SECOND_PASS_CONF=0.68" in lines
    # catch.py imports SECOND_PASS_MAX_FILE_MS; only the module that assigns a name lists it.
    assert not any(line.startswith("catch.SECOND_PASS_MAX_FILE_MS") for line in lines)


def test_the_fingerprint_changes_with_a_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: a moved threshold changes the fingerprint (the value read is the live one)."""
    monkeypatch.setattr(catch, "CONF", 0.55)
    assert fingerprint() != EXPECTED_FINGERPRINT
    assert "catch.CONF=0.55" in fingerprint().splitlines()
