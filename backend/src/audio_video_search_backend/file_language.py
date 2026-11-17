"""The fallback language of a file that predates schema v4 (plan 04-05, D-04-15).

New transcriptions store their majority language through the counters of the
worker (store/repo.py); the stock from before has none. ``detect`` names it
from the transcript text itself, out of de, en and fr alone: the py3langid
identifier is restricted to the three, so a foreign text gets the closest of
them and ``und`` can never reach a file name (pitfall 3). The export stores
the answer once through ``Store.set_file_language``.

Only the first ``LANGUAGE_SAMPLE_WORDS`` words are read, so a twelve hour
transcript costs the same as a short one (T-04-14). Nothing leaves the server
and nothing here logs a word or a language (T-04-15). py3langid is loaded on
the first call and cached, never at import time, and only its langid module,
never the HTTP server part (like engine/parakeet.py).
"""

import functools
from collections.abc import Sequence
from typing import Any, Final

from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.store.repo import FILE_LANGUAGES

# Enough text for a sure answer, a hard line against unbounded input (T-04-14).
LANGUAGE_SAMPLE_WORDS: Final = 3000


@functools.cache
def _identifier() -> Any:
    """The py3langid identifier, loaded once and restricted to the file languages."""
    from py3langid import langid  # loaded on the first detect call only

    identifier = langid.LanguageIdentifier.from_modelpath(langid.MODEL_DIR / langid.MODEL_FILE, norm_probs=True)
    identifier.set_languages(list(FILE_LANGUAGES))
    return identifier


def detect(words: Sequence[Word]) -> str | None:
    """The language of a transcript: de, en or fr, None for no usable text (D-04-15)."""
    text = " ".join(word.surface for word in words[:LANGUAGE_SAMPLE_WORDS])
    if not text.strip():
        return None
    language, _probability = _identifier().classify(text)
    code = str(language)
    return code if code in FILE_LANGUAGES else None
