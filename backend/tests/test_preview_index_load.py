"""The load of the index per chunk for a file of 12 h (plan 03-13, RESEARCH Pitfall 7 and assumption A8).

Every chunk of the preview appends its words to the same version and raises the
index revision; the index worker then builds the segments of the whole word
list again (index.reconcile: publish the current revision, retire the old one).
The work therefore grows with every chunk. This test measures it on a real
state.db and a real tantivy index: 72 chunks of 1500 words from a fixed
vocabulary, word times running on through the file, and the time of one chunk
(commit_chunk plus the publication path of the index worker) for chunks 1, 36
and 72, printed for ``-s``. The border is fixed: chunk 72 under 5 s on the
development machine. Above it the test fails, and the answer is the
alternative of the research (publish only the new segments), not a looser border.
"""

import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.model.overlay import Word, normalize
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.models import catalog
from audio_video_search_backend.store.repo import ChunkCounters, IntakeItem, Store

pytestmark = pytest.mark.slow

NOW = 1_800_000_000
SHA = "5" * 64
CHUNKS = 72
WORDS_PER_CHUNK = 1500
CHUNK_MS = 600_000
WORD_STEP_MS = CHUNK_MS // WORDS_PER_CHUNK
LIMIT_SECONDS = 5.0
VOCABULARY = [
    "haushalt",
    "sitzung",
    "antrag",
    "beschluss",
    "gemeinderat",
    "verwaltung",
    "schule",
    "straße",
    "bauplan",
    "bürger",
    "vorlage",
    "ausschuss",
    "förderung",
    "klimaschutz",
    "radweg",
    "kita",
    "personal",
    "stelle",
    "bericht",
    "frage",
    "the",
    "council",
    "meeting",
    "budget",
    "school",
    "road",
    "plan",
    "report",
    "question",
    "answer",
    "le",
    "conseil",
    "réunion",
    "budget",
    "école",
    "route",
    "plan",
    "rapport",
    "question",
    "réponse",
]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    opened = Store.open(tmp_path / "state.db")
    yield opened
    opened.close()


@pytest.fixture
def index(tmp_path: Path) -> Iterator[SearchIndex]:
    opened = SearchIndex.open(tmp_path / "index")
    yield opened
    opened.close()


def _chunk_words(chunk: int) -> list[Word]:
    words = []
    for i in range(WORDS_PER_CHUNK):
        surface = VOCABULARY[(chunk * WORDS_PER_CHUNK + i) % len(VOCABULARY)]
        start = chunk * CHUNK_MS + i * WORD_STEP_MS
        words.append(
            Word(start_ms=start, end_ms=start + 300, surface=surface, norm=normalize(surface), conf=0.9, src="machine")
        )
    return words


def test_the_index_load_of_chunk_72_of_a_12_hour_file_stays_under_5_s(store: Store, index: SearchIndex) -> None:
    store.apply_intake(
        [
            IntakeItem(
                queue_id=1,
                kind="content",
                file_id=1,
                storage_id=3,
                etag="e1",
                size=1000,
                mtime=1_700_000_000,
                prefilter_key=None,
                reader_uid="ana",
            )
        ]
    )
    claimed = store.next_capture(NOW)
    assert claimed is not None
    media_id = store.mark_keyed(claimed, SHA, "9" * 64, NOW)
    assert media_id is not None
    job = store.next_preview(NOW)
    assert job is not None
    prov = Provenance(
        engine="parakeet",
        model_sha256=catalog.MODEL_SHA256,
        config_version=1,
        profile="balanced",
        level=Level.PREVIEW,
        epoch=job.epoch,
        language="und",
        input_file_sha256=SHA,
    )
    counters = ChunkCounters(kept_words=WORDS_PER_CHUNK, drop_script=0, drop_language=0, drop_conf=0, speech_ms=0)

    seconds: dict[int, float] = {}
    for chunk in range(CHUNKS):
        words = _chunk_words(chunk)
        started = time.perf_counter()
        assert store.commit_chunk(job, prov=prov, words=words, next_start_ms=(chunk + 1) * CHUNK_MS, counters=counters)
        assert index.reconcile(store) == 1
        seconds[chunk + 1] = time.perf_counter() - started
        assert store.pending_index_work() == []

    current = store.current(media_id)
    assert current is not None
    # Positive control: the index holds exactly the last revision with every word of the file.
    assert index._keys() == {media_id: {current.index_rev}}
    assert len(store.effective_words(media_id)) == CHUNKS * WORDS_PER_CHUNK
    assert index.search(VOCABULARY[0], 5)

    print(
        f"\nindex load per chunk: chunk 1 {seconds[1]:.3f} s, chunk 36 {seconds[36]:.3f} s, "
        f"chunk 72 {seconds[72]:.3f} s"
    )
    assert seconds[72] < LIMIT_SECONDS
