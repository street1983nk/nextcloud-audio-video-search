"""The analysis chains for German, English and French. Filter order is the design.

Copied from Findling (``findling/index/analyzer.py``, measured against tantivy
0.26.2) and cut down to the three languages of this app.

German chain, every position measured by Findling:

    | # | Filter                  | Why exactly here                            |
    |---|-------------------------|---------------------------------------------|
    | 0 | Tokenizer.simple        | Splits on non alphanumeric, keeps digits    |
    | 1 | lowercase               | The constituent list is lowercase           |
    | 2 | split_compound(list)    | Needs the raw, unstemmed, unfolded token    |
    | 3 | custom_stopword(FUGEN)  | Otherwise a bare "s" reaches the index      |
    | 4 | stopword("german")      | The built in list carries real umlauts      |
    | 5 | remove_long(48)         | AFTER the splitter: a 63 character compound |
    |   |                         | would otherwise vanish as a whole           |
    | 6 | stemmer("german")       | Last; a stemmed compound matches no entry   |

The German branch has no folding filter: the Snowball stemmer folds umlauts and
sharp s by itself, and folding in front of the splitter would make the list,
which carries umlauts, miss silently.

Snowball chain of English and French:

    | # | Filter                  | Why exactly here                            |
    |---|-------------------------|---------------------------------------------|
    | 0 | Tokenizer.simple        |                                             |
    | 1 | lowercase               |                                             |
    | 2 | ascii_fold              | Keeps accented and flat spelling on one term|
    | 3 | stopword(lang)          | Built in Snowball list                      |
    | 4 | custom_stopword(folded) | The built in list compares exactly and      |
    |   |                         | carries accents, so after the fold its      |
    |   |                         | accented entries no longer match            |
    | 5 | remove_long(48)         |                                             |
    | 6 | stemmer(lang)           | Last                                        |

Any change to a chain raises ANALYZER_VERSION: an index written with one chain
and queried with another disagrees with itself, and the answer is a rebuild from
SQLite (index/open.py compares the mark).

Nothing here logs a token or a word: this path sees user content.
"""

import logging
import threading
import time
import unicodedata
from collections.abc import Sequence
from typing import Final

from tantivy import Filter, TextAnalyzer, TextAnalyzerBuilder, Tokenizer

from audio_video_search_backend.index.wordlist import FUGEN

_LOG: Final = logging.getLogger(__name__)

ANALYZER_VERSION: Final = 1

# The schema stores these names; index/open.py registers a chain for each.
TOKENIZER_DE: Final = "de"
TOKENIZER_EN: Final = "en"
TOKENIZER_FR: Final = "fr"

MAX_TOKEN_CHARS: Final = 48

# The folded supplement per Snowball language. English carries no accented stop
# word, so its supplement is empty (an empty custom stop word filter is a no-op).
# French: the folded forms of the accented entries tantivy 0.26.2 removes with
# stopword("french"), measured on 2026-11-06 with the probe in
# tests/test_index_open.py; entries whose flat form the built in list already
# drops (eut) are left out. Every entry is ASCII by construction.
FOLDED_STOPWORDS: Final[dict[str, tuple[str, ...]]] = {
    "english": (),
    "french": (
        "a",
        "meme",
        "etee",
        "etees",
        "etant",
        "etes",
        "etais",
        "etait",
        "etions",
        "etiez",
        "etaient",
        "fumes",
        "futes",
        "eumes",
        "eutes",
    ),
}

_CACHED_GERMAN: dict[str, TextAnalyzer] = {}
_GERMAN_LOCK: Final = threading.Lock()
_BUILD_COUNT = 0


def build_count() -> int:
    """How many German automata this process has built (the cache is testable)."""
    return _BUILD_COUNT


def normalize(text: str) -> str:
    """The one Unicode spelling of this index (NFC), used on both sides.

    A macOS client hands text over decomposed; the simple tokenizer splits on the
    combining mark, so both sides must be composed. Lone surrogate halves are
    replaced by U+FFFD first, because tantivy refuses them.
    """
    return unicodedata.normalize("NFC", _without_surrogates(text))


def _without_surrogates(text: str) -> str:
    if text.isascii():
        return text
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    return text


def german_analyzer(constituents: Sequence[str]) -> TextAnalyzer:
    """Build the German chain over a prepared constituent list (expensive, see the cache)."""
    global _BUILD_COUNT

    started = time.perf_counter()
    analyzer = (
        TextAnalyzerBuilder(Tokenizer.simple())
        .filter(Filter.lowercase())
        .filter(Filter.split_compound(list(constituents)))
        .filter(Filter.custom_stopword(list(FUGEN)))
        .filter(Filter.stopword("german"))
        .filter(Filter.remove_long(MAX_TOKEN_CHARS))
        .filter(Filter.stemmer("german"))
        .build()
    )
    _BUILD_COUNT += 1
    _LOG.info(
        "german automaton built",
        extra={"entries": len(constituents), "seconds": round(time.perf_counter() - started, 3)},
    )
    return analyzer


def cached_german_analyzer(digest: str, constituents: Sequence[str]) -> TextAnalyzer:
    """The process wide German chain for this list; built at most once per digest."""
    with _GERMAN_LOCK:
        cached = _CACHED_GERMAN.get(digest)
        if cached is not None:
            return cached
        analyzer = german_analyzer(constituents)
        _CACHED_GERMAN.clear()
        _CACHED_GERMAN[digest] = analyzer
        return analyzer


def snowball_analyzer(language: str) -> TextAnalyzer:
    """Build the Snowball chain of one language that has a measured supplement."""
    name = language.lower()
    if name not in FOLDED_STOPWORDS:
        raise ValueError(f"{language} has no measured folded supplement, so no chain is built for it")
    return (
        TextAnalyzerBuilder(Tokenizer.simple())
        .filter(Filter.lowercase())
        .filter(Filter.ascii_fold())
        .filter(Filter.stopword(name))
        .filter(Filter.custom_stopword(list(FOLDED_STOPWORDS[name])))
        .filter(Filter.remove_long(MAX_TOKEN_CHARS))
        .filter(Filter.stemmer(name))
        .build()
    )


def english_analyzer() -> TextAnalyzer:
    return snowball_analyzer("english")


def french_analyzer() -> TextAnalyzer:
    return snowball_analyzer("french")
