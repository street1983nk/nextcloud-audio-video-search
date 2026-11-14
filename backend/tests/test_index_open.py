"""Opening the derived index: one opener, three registered chains, version marks.

Pitfall 4 of the phase research: the schema persists the *name* of a tokenizer,
never the tokenizer. An index opened without registering the names answers the
first query with "the tokenizer 'de' ... is unknown", which reads like a broken
index. Only index/open.py may open one, and it registers de, en and fr.
"""

import ast
from pathlib import Path

import pytest
from tantivy import Filter, TextAnalyzerBuilder, Tokenizer

from audio_video_search_backend.index import analyzer, wordlist
from audio_video_search_backend.index.open import (
    MARK_ANALYZER,
    MARK_SCHEMA,
    MARK_TANTIVY,
    TANTIVY_VERSION,
    expected_marks,
    open_index,
    open_reader,
)
from audio_video_search_backend.index.publish import SearchIndex, Segment
from audio_video_search_backend.index.schema import FIELD_BODY_DE, FIELD_BODY_EN, FIELD_BODY_FR, SCHEMA_VERSION
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import SAMPLE_MODEL_SHA256, Level, Provenance
from audio_video_search_backend.store.repo import Store
from tests.conftest import BACKEND_ROOT

PACKAGE_ROOT = BACKEND_ROOT / "src" / "audio_video_search_backend"
OPENING_MODULE = "index/open.py"
# A small stand-in for the Debian list, in the form load_constituents produces.
CONSTITUENTS = sorted({"kündigung", "frist", "audio", "suche", "test", "treffer", *wordlist.FUGEN})
SHA = "a" * 64


def _opens_an_index(source: str, filename: str) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        names: set[str] = set()
        if isinstance(func, ast.Attribute):
            names.add(func.attr)
            if isinstance(func.value, ast.Name):
                names.add(f"{func.value.id}.{func.attr}")
        if isinstance(func, ast.Name):
            names.add(func.id)
        if names & {"Index", "Index.open", "tantivy.Index"}:
            lines.append(node.lineno)
    return lines


def test_only_the_opening_module_opens_an_index() -> None:
    offenders: list[str] = []
    files = sorted(PACKAGE_ROOT.rglob("*.py"))
    for path in files:
        relative = path.relative_to(PACKAGE_ROOT).as_posix()
        if relative == OPENING_MODULE:
            continue
        offenders += [f"{relative}:{line}" for line in _opens_an_index(path.read_text(encoding="utf-8"), relative)]

    assert offenders == []
    # Anti-vacuum: the opener itself is seen by the same scan.
    assert _opens_an_index((PACKAGE_ROOT / OPENING_MODULE).read_text(encoding="utf-8"), OPENING_MODULE)


def test_the_scan_fires_on_a_foreign_opener(tmp_path: Path) -> None:
    foreign = tmp_path / "rogue.py"
    foreign.write_text("from tantivy import Index\nidx = Index.open('x')\nother = Index(schema)\n", encoding="utf-8")

    assert _opens_an_index(foreign.read_text(encoding="utf-8"), "rogue.py") == [2, 3]


def _write(index_dir: Path, text: str) -> SearchIndex:
    search_index = SearchIndex.open(index_dir, constituents=CONSTITUENTS)
    search_index.publish(1, 1, [Segment(seg_idx=0, start_ms=0, end_ms=1000, text=text)])
    return search_index


def _count(index_dir: Path, term: str, field: str) -> int:
    index = open_index(index_dir, CONSTITUENTS)
    searcher = open_reader(index)
    return len(searcher.search(index.parse_query(term, [field]), 10).hits)


def test_the_three_chains_are_registered_on_open(tmp_path: Path) -> None:
    search_index = _write(tmp_path / "idx", "Die Kündigungsfrist beträgt drei Monate. The notice periods. Les délais")
    search_index.close()

    # German: the compound comes apart, "frist" finds "Kündigungsfrist".
    assert _count(tmp_path / "idx", "frist", FIELD_BODY_DE) == 1
    assert _count(tmp_path / "idx", "kündigung", FIELD_BODY_DE) == 1
    # English: Porter stems "periods" and "period" onto one term.
    assert _count(tmp_path / "idx", "period", FIELD_BODY_EN) == 1
    # French: the fold keeps the accented and the flat spelling on one term.
    assert _count(tmp_path / "idx", "delai", FIELD_BODY_FR) == 1


def test_the_french_chain_drops_folded_stop_words() -> None:
    chain = analyzer.french_analyzer()

    assert chain.analyze("était") == []
    assert chain.analyze("etait") == []
    assert chain.analyze("même") == []
    assert chain.analyze("délais") == chain.analyze("delais")


def test_every_folded_french_supplement_entry_is_a_folded_stop_word() -> None:
    plain = TextAnalyzerBuilder(Tokenizer.simple()).filter(Filter.lowercase()).filter(Filter.stopword("french")).build()
    fold = TextAnalyzerBuilder(Tokenizer.simple()).filter(Filter.lowercase()).filter(Filter.ascii_fold()).build()
    for entry in analyzer.FOLDED_STOPWORDS["french"]:
        # Not a stop word on its own: otherwise the entry would be ballast.
        assert plain.analyze(entry), entry
        assert fold.analyze(entry) == [entry]


def test_an_unknown_snowball_language_is_refused() -> None:
    with pytest.raises(ValueError, match="no chain"):
        analyzer.snowball_analyzer("klingon")


def test_the_german_automaton_is_built_once_per_list() -> None:
    first = analyzer.cached_german_analyzer(wordlist.wordlist_hash(CONSTITUENTS), CONSTITUENTS)
    builds = analyzer.build_count()
    second = analyzer.cached_german_analyzer(wordlist.wordlist_hash(CONSTITUENTS), CONSTITUENTS)

    assert first is second
    assert analyzer.build_count() == builds


def test_a_missing_system_list_degrades_to_the_linking_elements(tmp_path: Path) -> None:
    assert wordlist.load_constituents(tmp_path / "missing") == sorted(wordlist.FUGEN)


def test_the_recipe_keeps_the_window_and_umlauts(tmp_path: Path) -> None:
    source = tmp_path / "ngerman"
    source.write_text("Kündigung\nFrist\nab\nRindfleischetikettierung\nMüller's\nHaus\n", encoding="utf-8")

    assert wordlist.load_constituents(source) == sorted({"kündigung", "frist", "haus", *wordlist.FUGEN})


def test_normalize_composes_and_repairs_surrogates() -> None:
    assert analyzer.normalize("Kündigung") == "Kündigung"
    assert analyzer.normalize("x\ud800y") == "x�y"
    assert analyzer.normalize("plain") == "plain"


def test_the_marks_name_schema_analyzer_list_and_format() -> None:
    marks = expected_marks("d" * 64)

    assert marks[MARK_SCHEMA] == str(SCHEMA_VERSION)
    assert marks[MARK_ANALYZER] == f"{analyzer.ANALYZER_VERSION}:{'d' * 64}"
    assert marks[MARK_TANTIVY] == TANTIVY_VERSION
    assert "index_format" in TANTIVY_VERSION


def _seed(store: Store, text: str) -> int:
    media_id = store.media_for_file_sha256(SHA)
    store.put_sample(7, media_id)
    prov = Provenance(
        engine="sample",
        model_sha256=SAMPLE_MODEL_SHA256,
        config_version=1,
        profile="debug",
        level=Level.SAMPLE,
        epoch=store.media_epoch(media_id),
        language="de",
        input_file_sha256=SHA,
    )
    words = [Word(i * 400, i * 400 + 350, w, w.lower(), 1.0, "machine") for i, w in enumerate(text.split())]
    assert store.publish_version(media_id, prov, words).published
    return media_id


def test_open_generation_rebuilds_when_a_mark_differs(tmp_path: Path, store: Store) -> None:
    media_id = _seed(store, "Hier ist die Audiosuche")
    root = tmp_path / "index"

    first = SearchIndex.open_generation(root, store, constituents=CONSTITUENTS)
    try:
        # A fresh directory is built from SQLite and the marks are written.
        assert [h.media_id for h in first.search("Audiosuche", 5)] == [media_id]
        assert store.meta_value(MARK_SCHEMA) == str(SCHEMA_VERSION)
        assert store.pending_index_work() == []
    finally:
        first.close()
    generation = store.index_generation()

    again = SearchIndex.open_generation(root, store, constituents=CONSTITUENTS)
    again.close()
    assert store.index_generation() == generation

    store.set_meta(MARK_ANALYZER, "0:old")
    rebuilt = SearchIndex.open_generation(root, store, constituents=CONSTITUENTS)
    try:
        assert store.index_generation() == generation + 1
        assert store.meta_value(MARK_ANALYZER) == expected_marks(wordlist.wordlist_hash(CONSTITUENTS))[MARK_ANALYZER]
        assert [h.media_id for h in rebuilt.search("Audiosuche", 5)] == [media_id]
    finally:
        rebuilt.close()


@pytest.mark.parametrize("key", ["schema_version", "index_generation", "Bad-Key", ""])
def test_set_meta_refuses_the_stores_own_marks_and_odd_keys(store: Store, key: str) -> None:
    with pytest.raises(ValueError, match="key"):
        store.set_meta(key, "1")

    assert store.schema_version() == 3
    assert store.index_generation() == 0
