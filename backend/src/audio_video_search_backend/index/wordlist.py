"""The constituent list for the German compound splitter, and its digest.

Copied from Findling (``findling/index/wordlist.py``, recipe A) and cut down to
what this app needs: no artifact on the volume, no noun variant.

Recipe A, measured by Findling against sixteen real administrative compounds:
all words of ``/usr/share/dict/ngerman``, lowercased, alphabetic only, length 4
to 14, plus the six linking elements as entries of their own. 276496 entries,
0.44 s to build the automaton, roughly 23 MB resident.

Two properties are load bearing:

- *The window has an upper end.* An entry longer than MAX_LEN is itself a
  compound, and the splitter matches leftmost-longest, so "Kuendigungsfrist"
  in the list would swallow the whole token and "Frist" would find nothing.
- *The list keeps its umlauts.* The splitter compares the raw lowercased token,
  so a folded list would never match and the splitting would fail silently.

The digest of the list is part of the analyzer mark of the index (index/open.py):
a changed list changes the tokenisation, and the index is rebuilt from SQLite.

When the system list is missing (a development machine, an image without the
Debian package ``wngerman``) the list is the linking elements alone. German
stemming still works then, only compounds stay whole; the digest changes with
it, so an index built that way is rebuilt once the list is there.
"""

import hashlib
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Final

_LOG: Final = logging.getLogger(__name__)

# The file the Debian package wngerman installs (Architecture: all).
SYSTEM_WORDLIST: Final = Path("/usr/share/dict/ngerman")

MIN_LEN: Final = 4
MAX_LEN: Final = 14

# The German linking elements, entries of their own. The same constant goes into
# the splitter and comes back out as a custom stop word in index/analyzer.py.
FUGEN: Final = ("s", "es", "n", "en", "er", "ns")

ENCODING: Final = "utf-8"


def load_constituents(source: Path = SYSTEM_WORDLIST) -> list[str]:
    """Apply recipe A to a raw word list and return the sorted constituents."""
    words: set[str] = set(FUGEN)
    try:
        raw = source.read_text(encoding=ENCODING, errors="replace")
    except OSError:
        _LOG.warning("german word list missing, compounds stay whole", extra={"entries": len(words)})
        return sorted(words)
    for word in raw.split():
        if word.isalpha() and MIN_LEN <= len(word) <= MAX_LEN:
            words.add(word.lower())
    return sorted(words)


def wordlist_hash(entries: Sequence[str]) -> str:
    """The SHA-256 of the filtered list, stable across processes and machines."""
    digest = hashlib.sha256()
    digest.update("\n".join(entries).encode(ENCODING))
    return digest.hexdigest()
