"""Probe for plan 04-05: importing file_language must not load py3langid.

tests/test_file_language.py runs this file in a fresh interpreter; the answer
is one word on stdout. A helper file instead of an inline program on purpose:
the suite never calls the interpreter with an inline program.
"""

import sys

from audio_video_search_backend import file_language

assert file_language.LANGUAGE_SAMPLE_WORDS > 0
print("loaded" if "py3langid" in sys.modules else "clean")
