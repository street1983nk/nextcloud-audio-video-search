"""The measured values of the Parakeet preview, as constants with a test (plan 03-06).

TRANS-01: the pipeline runs with the values of Spike 3, taken 1:1 from
``scripts/research/phase3/measure.py`` (itself 1:1 from Spike 3 ``bench3.py``).
TRANS-02: the VAD is always on; its values live here and nowhere else, read no
environment and no setting, and have no switch (tests/test_vad_gate.py).
Every changed value needs a new ``CONFIG_VERSION`` (TRANS-06), and
tests/test_engine_constants.py holds both with a fingerprint.
"""

from typing import Final

# The provenance of a transcript names this version; raise it with every change below
# and in engine/catch.py. 2: D-03-23 (plan 03-13b), the second VAD pass keeps fewer words.
CONFIG_VERSION: Final = 2

SAMPLE_RATE: Final = 16000

# Silero VAD (sherpa-onnx VadModelConfig and VoiceActivityDetector).
VAD_THRESHOLD: Final = 0.5
VAD_MIN_SILENCE_S: Final = 0.3
VAD_MIN_SPEECH_S: Final = 0.25
VAD_MAX_SPEECH_S: Final = 25.0
VAD_THREADS: Final = 1
VAD_BUFFER_S: Final = 60.0

# VAD segments merge into one window while the gap is at most 2 s and the window at most 25 s.
MERGE_GAP_S: Final = 2.0
WINDOW_MAX_S: Final = 25.0

# A window is decoded with 0.4 s of context on each side, padded with 0.5 s of silence on
# each side, and never shorter than 0.5 s. A token lasts 0.08 s.
CONTEXT_S: Final = 0.4
PAD_S: Final = 0.5
MIN_DECODE_S: Final = 0.5
TOKEN_S: Final = 0.08

# The swallow guard: a part of a merged window from 1.0 s with fewer than 1.0 word per
# second (counted with 0.3 s of slack) is decoded again on its own.
GUARD_WORDS_PER_S: Final = 1.0
GUARD_MIN_S: Final = 1.0
GUARD_SLACK_S: Final = 0.3

# Parakeet-TDT-0.6B-v3 int8 (OfflineRecognizer.from_transducer).
RECOGNIZER_THREADS: Final = 2
DECODING_METHOD: Final = "greedy_search"
MODEL_TYPE: Final = "nemo_transducer"

# D-03-16 and M-10: a second VAD pass with these values (the VAD stays on) for files up to
# 60 s whose first pass kept no word.
SECOND_PASS_THRESHOLD: Final = 0.3
SECOND_PASS_MIN_SPEECH_S: Final = 0.1
SECOND_PASS_MAX_FILE_MS: Final = 60_000

# TRANS-07, RESEARCH Pattern 2: chunks of 10 min with 1 s of context and 60 s of lookahead.
CHUNK_MS: Final = 600_000
CHUNK_CONTEXT_MS: Final = 1_000
CHUNK_LOOKAHEAD_MS: Final = 60_000
