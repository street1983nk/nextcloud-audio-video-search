"""The one place that opens an index, because opening is registering.

The schema persists the *name* of a tokenizer and never the tokenizer. An index
opened without registering the names answers the first query with "the
tokenizer 'de' ... is unknown", which looks like a broken index and is a missing
line of setup (pitfall 4). Every other ``Index(...)`` or ``Index.open(...)`` in
the package is a defect; tests/test_index_open.py walks the package and says so.

The marks below are compared against the meta table of SQLite. A difference
means the directory on disk was built by other code, and the index is rebuilt
from SQLite into a new generation directory (index/publish.py).
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Final

import tantivy
from tantivy import Index, Searcher

from audio_video_search_backend.index.analyzer import (
    ANALYZER_VERSION,
    TOKENIZER_DE,
    TOKENIZER_EN,
    TOKENIZER_FR,
    cached_german_analyzer,
    english_analyzer,
    french_analyzer,
)
from audio_video_search_backend.index.schema import SCHEMA_VERSION, build_schema
from audio_video_search_backend.index.wordlist import wordlist_hash

# Keys in the meta table of SQLite. The store's own schema_version is a
# different key; these describe the derived index only.
MARK_SCHEMA: Final = "index_schema_version"
MARK_ANALYZER: Final = "index_analyzer"
MARK_TANTIVY: Final = "index_tantivy"

# The banner of the extension module, e.g. "tantivy v0.26.2, index_format v7".
# The stub does not declare it; a fallback value would make a renamed attribute
# a mark that quietly says the wrong thing.
TANTIVY_VERSION: Final[str] = tantivy.__version__  # pyright: ignore[reportAttributeAccessIssue]


def open_index(path: Path, constituents: Sequence[str]) -> Index:
    """Create or open the index at ``path`` and register its three chains."""
    path.mkdir(parents=True, exist_ok=True)
    index = Index.open(str(path)) if Index.exists(str(path)) else Index(build_schema(), path=str(path))
    index.register_tokenizer(TOKENIZER_DE, cached_german_analyzer(wordlist_hash(constituents), constituents))
    index.register_tokenizer(TOKENIZER_EN, english_analyzer())
    index.register_tokenizer(TOKENIZER_FR, french_analyzer())
    return index


def open_reader(index: Index) -> Searcher:
    """Reload after every commit; a writer in the same process also calls ``reload``."""
    index.config_reader(reload_policy="commit")
    return index.searcher()


def expected_marks(wordlist_digest: str) -> dict[str, str]:
    """The marks an index built by this code carries."""
    return {
        MARK_SCHEMA: str(SCHEMA_VERSION),
        MARK_ANALYZER: f"{ANALYZER_VERSION}:{wordlist_digest}",
        MARK_TANTIVY: TANTIVY_VERSION,
    }
