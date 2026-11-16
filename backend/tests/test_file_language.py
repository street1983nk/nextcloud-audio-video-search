"""file_language.detect: the fallback for the stock without a stored language (plan 04-05, D-04-15).

The identifier is restricted to de, en and fr like the file languages of the
store, so a foreign text can never leave the three and ``und`` can never come
out (T-04-13). At most LANGUAGE_SAMPLE_WORDS words are read (T-04-14), and
py3langid is loaded on the first call, never at import time: the probe below
runs in a fresh interpreter and looks at sys.modules.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from audio_video_search_backend import file_language
from audio_video_search_backend.model.overlay import Word
from tests.conftest import BACKEND_ROOT

PROBE = Path(__file__).with_name("file_language_probe.py")

GERMAN = (
    "Der Gemeinderat hat in seiner heutigen Sitzung den Haushaltsplan für das kommende Jahr beraten"
    " und nach langer Aussprache mit großer Mehrheit beschlossen, die Mittel für Schulen und Kitas zu erhöhen"
)
ENGLISH = (
    "The council discussed the budget for the coming year during today's meeting"
    " and after a long debate decided with a large majority to raise the funds for schools and libraries"
)
FRENCH = (
    "Le conseil municipal a discuté du budget pour l'année prochaine lors de la séance d'aujourd'hui"
    " et après un long débat a décidé à une large majorité d'augmenter les moyens pour les écoles"
)
# The dotless i is the point: real Turkish, a language outside the three.
TURKISH = (
    "Belediye meclisi bugünkü toplantısında gelecek yıl için bütçeyi görüştü"  # noqa: RUF001
    " ve uzun bir tartışmanın ardından okullara ayrılan kaynakların artırılmasına karar verdi"  # noqa: RUF001
)


def _word(surface: str, idx: int) -> Word:
    start = idx * 400
    return Word(start_ms=start, end_ms=start + 300, surface=surface, norm=surface.casefold(), conf=0.9, src="machine")


def _words(text: str) -> list[Word]:
    return [_word(surface, idx) for idx, surface in enumerate(text.split())]


@pytest.mark.parametrize(
    ("text", "language"), [(GERMAN, "de"), (ENGLISH, "en"), (FRENCH, "fr")], ids=["de", "en", "fr"]
)
def test_detect_names_the_language_of_a_clear_text(text: str, language: str) -> None:
    assert file_language.detect(_words(text)) == language


def test_a_foreign_language_never_leaves_the_three() -> None:
    # Restricted to de/en/fr: a Turkish text gets one of the three, never
    # something that could reach a file name (D-04-15, pitfall 3).
    assert file_language.detect(_words(TURKISH)) in ("de", "en", "fr")


def test_an_empty_or_blank_text_is_none() -> None:
    assert file_language.detect([]) is None
    blank = [Word(start_ms=0, end_ms=100, surface="  ", norm="", conf=0.5, src="machine")]
    assert file_language.detect(blank) is None


def test_detect_reads_at_most_the_sample_words() -> None:
    # A word past the sample limit is never touched: the poison would raise.
    class Poison:
        @property
        def surface(self) -> str:
            raise AssertionError("read past LANGUAGE_SAMPLE_WORDS")

    tokens = (GERMAN.split() * 200)[: file_language.LANGUAGE_SAMPLE_WORDS]
    words: list[Any] = [_word(token, idx) for idx, token in enumerate(tokens)]
    words.append(Poison())

    assert file_language.LANGUAGE_SAMPLE_WORDS == 3000
    assert len(words) == file_language.LANGUAGE_SAMPLE_WORDS + 1
    assert file_language.detect(words) == "de"


def test_the_identifier_is_loaded_once_and_cached() -> None:
    assert file_language.detect(_words(GERMAN)) == "de"
    # Positive control for the probe below: a detect call does load py3langid.
    assert "py3langid" in sys.modules
    assert file_language._identifier() is file_language._identifier()


def test_importing_the_module_does_not_load_py3langid() -> None:
    completed = subprocess.run(  # noqa: S603 - the interpreter of this test run with a fixed script
        [sys.executable, str(PROBE)], capture_output=True, text=True, check=True, cwd=BACKEND_ROOT
    )
    assert completed.stdout.strip() == "clean"
