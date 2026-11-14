"""POST /search gives one hit per place in a fixed tier sequence (plan 03-08, D-03-01, D-03-02, D-03-15).

The web dialog of the unified search asks again with a growing ``limit`` and
sends no cursor (03-RESEARCH Pattern 4). "Load more" only works without a gap
or a duplicate when the answer for ``limit`` 10 starts with the answer for
``limit`` 5. So the container orders every place in a fixed sequence: files by
their best place, per file tiers of three places, first tier 1 of every file,
then tier 2 and so on; ``offset`` and ``limit`` cut that sequence.

The expected sequences here are written by hand, never computed with
``tiered``. The random check states the order as invariants (each file's places
in score order, tier numbers never fall, files in a tier by best score) and
checks those, not a second copy of the algorithm.
"""

import hashlib
import itertools
import random
from collections import Counter
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend import main
from audio_video_search_backend.api import sample as sample_api
from audio_video_search_backend.api import search as search_api
from audio_video_search_backend.api.search import admissible, stage_of, tiered
from audio_video_search_backend.index.publish import IndexHit, SearchIndex, segments_from_words
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import SAMPLE_MODEL_SHA256, Level, Provenance
from audio_video_search_backend.store.repo import Store
from tests.conftest import signed_headers

SPOKEN = "Haushaltsgeheimnis"
MODEL = "c" * 64
EIGHT = 10  # the file of the content with eight places
ONE = 20  # the file of the content with one stronger place
STEP_MS = 5000  # far above the 1.5 s pause, so every pair of words is its own segment

# -- the pure sequence ---------------------------------------------------------


def test_the_file_with_the_best_place_comes_first_and_fills_its_tier() -> None:
    by_file = {
        1: [(0.9, 1000, "a1"), (0.8, 2000, "a2"), (0.7, 3000, "a3"), (0.6, 4000, "a4")],
        2: [(0.95, 500, "b1")],
    }

    assert tiered(by_file) == [(2, 500, "b1"), (1, 1000, "a1"), (1, 2000, "a2"), (1, 3000, "a3"), (1, 4000, "a4")]


def test_a_single_file_with_eight_places_gives_all_eight_in_score_order() -> None:
    # D-03-15: with one file only, tier 2 and 3 fill the page, so limit 5 gives 5.
    places = [
        (0.3, 6000, "p6"),
        (0.8, 1000, "p1"),
        (0.1, 8000, "p8"),
        (0.6, 3000, "p3"),
        (0.7, 2000, "p2"),
        (0.2, 7000, "p7"),
        (0.5, 4000, "p4"),
        (0.4, 5000, "p5"),
    ]

    assert tiered({7: places}) == [
        (7, 1000, "p1"),
        (7, 2000, "p2"),
        (7, 3000, "p3"),
        (7, 4000, "p4"),
        (7, 5000, "p5"),
        (7, 6000, "p6"),
        (7, 7000, "p7"),
        (7, 8000, "p8"),
    ]


def test_tiers_of_three_interleave_the_files() -> None:
    by_file = {
        3: [(0.9, 10, "a1"), (0.8, 20, "a2"), (0.7, 30, "a3"), (0.6, 40, "a4"), (0.5, 50, "a5")],
        1: [(0.85, 11, "b1"), (0.84, 21, "b2"), (0.83, 31, "b3"), (0.82, 41, "b4")],
        2: [(0.95, 12, "c1")],
    }

    assert tiered(by_file) == [
        # tier 1: C (0.95), A (0.9), B (0.85)
        (2, 12, "c1"),
        (3, 10, "a1"),
        (3, 20, "a2"),
        (3, 30, "a3"),
        (1, 11, "b1"),
        (1, 21, "b2"),
        (1, 31, "b3"),
        # tier 2
        (3, 40, "a4"),
        (3, 50, "a5"),
        (1, 41, "b4"),
    ]


def test_a_tie_orders_files_by_id_and_places_by_time() -> None:
    by_file = {
        9: [(0.5, 300, "x3"), (0.5, 100, "x1"), (0.5, 200, "x2")],
        4: [(0.5, 900, "y1")],
    }

    assert tiered(by_file) == [(4, 900, "y1"), (9, 100, "x1"), (9, 200, "x2"), (9, 300, "x3")]


def test_no_places_give_an_empty_sequence() -> None:
    assert tiered({}) == []


def test_the_tier_size_is_three() -> None:
    assert search_api.PER_TIER == 3


# -- random layouts, checked against invariants --------------------------------


def _layout(rng: random.Random) -> dict[int, list[tuple[float, int, str]]]:
    files = rng.sample(range(1, 60), rng.randint(1, 6))
    layout: dict[int, list[tuple[float, int, str]]] = {}
    for file_id in files:
        times = rng.sample(range(0, 100_000, 250), rng.randint(1, 10))
        # Few distinct scores, so ties between places and between files happen.
        layout[file_id] = [(rng.choice((0.25, 0.5, 0.75, 1.0)), t, f"{file_id}@{t}") for t in times]
    return layout


def _shuffled(rng: random.Random, layout: dict[int, list[tuple[float, int, str]]]) -> dict[int, list]:
    keys = list(layout)
    rng.shuffle(keys)
    out: dict[int, list] = {}
    for key in keys:
        places = list(layout[key])
        rng.shuffle(places)
        out[key] = places
    return out


LAYOUTS = [(seed, _layout(random.Random(seed))) for seed in range(50)]  # noqa: S311 - test data, not a secret


@pytest.mark.parametrize(("seed", "layout"), LAYOUTS)
def test_every_random_layout_keeps_the_rules(seed: int, layout: dict[int, list[tuple[float, int, str]]]) -> None:
    sequence = tiered(layout)

    # Nothing lost, nothing twice.
    given = Counter((f, t, e) for f, places in layout.items() for _s, t, e in places)
    assert Counter(sequence) == given
    assert len(set(sequence)) == len(sequence)

    score = {(f, t): s for f, places in layout.items() for s, t, _e in places}
    best = {f: max(s for s, _t, _e in places) for f, places in layout.items()}

    # The k-th place of a file in the sequence belongs to tier k // 3.
    seen: Counter[int] = Counter()
    tiers: list[int] = []
    for file_id, _t, _e in sequence:
        tiers.append(seen[file_id] // 3)
        seen[file_id] += 1
    assert tiers == sorted(tiers), "a later tier came before an earlier one"

    # Each file's places come in score order, a tie by time.
    for file_id in layout:
        mine = [(score[(f, t)], t) for f, t, _e in sequence if f == file_id]
        assert all((-a[0], a[1]) < (-b[0], b[1]) for a, b in itertools.pairwise(mine))

    # Inside a tier the files come by best place, a tie by file id, each as one run.
    for tier in set(tiers):
        files_in_tier = [f for (f, _t, _e), k in zip(sequence, tiers, strict=True) if k == tier]
        runs = [f for i, f in enumerate(files_in_tier) if i == 0 or files_in_tier[i - 1] != f]
        assert len(runs) == len(set(runs)), "a file broke its run inside a tier"
        assert runs == sorted(runs, key=lambda f: (-best[f], f))

    # Pages of five never carry more than three places of one file in one tier,
    # and they join to the sequence without a gap.
    pages = [sequence[o : o + 5] for o in range(0, len(sequence), 5)]
    assert [hit for page in pages for hit in page] == sequence
    for o in range(0, len(sequence), 5):
        page_tiers = Counter((f, k) for (f, _t, _e), k in zip(sequence[o : o + 5], tiers[o : o + 5], strict=True))
        assert max(page_tiers.values()) <= 3

    # The order of the input does not matter: the index may hand the candidates
    # in another order on the next request, the answer stays the same.
    again = tiered(_shuffled(random.Random(seed + 1000), layout))  # noqa: S311 - test data, not a secret
    assert again == sequence
    for limit in (5, 10, 15):
        assert again[:limit][:5] == sequence[:5]


# -- the admissible revision -----------------------------------------------------


def test_only_the_segments_of_the_highest_admissible_revision_stay() -> None:
    hits = [
        IndexHit(1, 3, 0, 0, 1.0, "m1 r3 s0"),
        IndexHit(1, 2, 0, 0, 9.0, "m1 r2 s0"),
        IndexHit(1, 2, 1, 900, 8.0, "m1 r2 s1"),
        IndexHit(2, 2, 0, 0, 2.0, "m2 r2 s0"),
        IndexHit(2, 2, 4, 400, 3.0, "m2 r2 s4"),
        IndexHit(3, 5, 0, 0, 7.0, "m3 no current"),
        IndexHit(4, 1, 0, 0, 6.0, "m4 r1 too old"),
    ]

    chosen = admissible(hits, {1: 3, 2: 3, 3: None, 4: 3})

    # media 1: revision 3 was found, so its revision 2 is gone, though it scored higher;
    # media 2: only revision 2 was found, all of its segments stay;
    # media 3: no current, media 4: two below current.
    assert sorted(h.text for h in chosen) == ["m1 r3 s0", "m2 r2 s0", "m2 r2 s4"]


# -- the stage of a hit ------------------------------------------------------------


@pytest.mark.parametrize(
    ("level", "stage"),
    [
        (Level.SAMPLE, "sample"),
        (Level.PREVIEW, "preview"),
        (Level.SELECTIVE, "preview"),
        (Level.REFINED, "final"),
        (Level.REFINED_L3, "final"),
    ],
)
def test_the_stage_follows_the_level(level: Level, stage: str) -> None:
    assert stage_of(int(level)) == stage


# -- the route, with a real state.db and a real index ------------------------------


@pytest.fixture
def api() -> Iterator[TestClient]:
    with TestClient(main.APP) as client:
        yield client


def _services(client: TestClient) -> tuple[Store, SearchIndex]:
    state = client.app.state  # pyright: ignore[reportAttributeAccessIssue]
    return state.services.store, state.services.index


def _publish(store: Store, index: SearchIndex, label: bytes, words: list[Word], level: Level = Level.PREVIEW) -> int:
    sha = hashlib.sha256(label).hexdigest()
    media_id = store.media_for_file_sha256(sha)
    engine = "whisper-turbo" if level >= Level.REFINED else "parakeet"
    prov = Provenance(
        engine=engine,
        model_sha256=MODEL,
        config_version=1,
        profile="balanced",
        level=level,
        epoch=store.media_epoch(media_id),
        language="de",
        input_file_sha256=sha,
    )
    result = store.publish_version(media_id, prov, words)
    assert result.published
    assert result.index_rev is not None
    index.publish(media_id, result.index_rev, segments_from_words(store.effective_words(media_id)))
    index.retire(media_id, keep_rev=result.index_rev)
    store.mark_indexed(media_id, result.index_rev)
    return media_id


def _active(store: Store, file_id: int, media_id: int) -> None:
    store.upsert_file_ref(
        file_id, media_id, storage_id=3, etag="e1", size=1000, mtime=1_700_000_000, state="active", stage="keyed",
        reason=None,
    )  # fmt: skip


def _eight_places() -> list[Word]:
    """Eight segments of equal shape: a filler word, then the term, 5 s apart."""
    words: list[Word] = []
    for i in range(8):
        base = i * STEP_MS
        words.append(Word(base, base + 350, f"Füllwort{i}", f"füllwort{i}", 0.9, "machine"))
        words.append(Word(base + 400, base + 750, SPOKEN, SPOKEN.lower(), 0.9, "machine"))
    return words


def _one_strong_place() -> list[Word]:
    """One segment of the same length that carries the term twice, so it scores higher."""
    return [
        Word(0, 350, SPOKEN, SPOKEN.lower(), 0.9, "machine"),
        Word(400, 750, SPOKEN, SPOKEN.lower(), 0.9, "machine"),
    ]


def _post(client: TestClient, body: dict[str, object]) -> httpx.Response:
    return client.post("/search", headers=signed_headers(), json=body)


def _answer(client: TestClient, limit: int, offset: int | None = None) -> dict[str, object]:
    body: dict[str, object] = {"term": SPOKEN, "limit": limit}
    if offset is not None:
        body["offset"] = offset
    response = _post(client, body)
    assert response.status_code == 200
    return response.json()


def _places(answer: dict[str, object]) -> list[tuple[int, int]]:
    hits = answer["hits"]
    assert isinstance(hits, list)
    return [(int(h["fileId"]), int(h["startMs"])) for h in hits]


# The full sequence for the two contents, written by hand: the strong place of
# file ONE first (best score), then tier 1 of file EIGHT (its places tie, so by
# time), then tier 2 and tier 3 of file EIGHT.
FULL = [
    (ONE, 0),
    (EIGHT, 400),
    (EIGHT, 5400),
    (EIGHT, 10400),
    (EIGHT, 15400),
    (EIGHT, 20400),
    (EIGHT, 25400),
    (EIGHT, 30400),
    (EIGHT, 35400),
]


@pytest.fixture
def two_contents(api: TestClient) -> TestClient:
    store, index = _services(api)
    _active(store, EIGHT, _publish(store, index, b"eight places", _eight_places()))
    _active(store, ONE, _publish(store, index, b"one place", _one_strong_place()))
    return api


def test_the_route_answers_the_hand_written_sequence(two_contents: TestClient) -> None:
    answer = _answer(two_contents, 15)

    assert _places(answer) == FULL
    assert answer["nextOffset"] == 9
    assert answer["hasMore"] is False
    hits = answer["hits"]
    assert isinstance(hits, list)
    for hit in hits:
        assert set(hit) == {"fileId", "startMs", "excerpt", "sample", "stage"}
        assert SPOKEN in hit["excerpt"]
        assert (hit["sample"], hit["stage"]) == (False, "preview")
    assert hits[1]["excerpt"] == f"Füllwort0 {SPOKEN}"


def test_limit_ten_starts_with_limit_five_over_http(two_contents: TestClient) -> None:
    five = _places(_answer(two_contents, 5))
    ten = _places(_answer(two_contents, 10))
    fifteen = _places(_answer(two_contents, 15))

    assert five == FULL[:5]
    assert five == ten[:5] == fifteen[:5]
    assert ten == fifteen[:10]


def test_offset_pages_join_without_a_gap_or_a_duplicate(two_contents: TestClient) -> None:
    first = _answer(two_contents, 5, 0)
    second = _answer(two_contents, 5, 5)
    third = _answer(two_contents, 5, 10)

    joined = _places(first) + _places(second) + _places(third)
    assert joined == _places(_answer(two_contents, 15))
    assert len(set(joined)) == len(joined)
    assert (first["nextOffset"], first["hasMore"]) == (5, True)
    assert (second["nextOffset"], second["hasMore"]) == (9, False)
    assert (third["hits"], third["nextOffset"], third["hasMore"]) == ([], 10, False)


def test_has_more_is_true_exactly_while_a_place_follows_the_cut(two_contents: TestClient) -> None:
    # Positive and negative control at the edge: eight places before the cut leave one, nine leave none.
    assert (_answer(two_contents, 5, 3)["nextOffset"], _answer(two_contents, 5, 3)["hasMore"]) == (8, True)
    assert (_answer(two_contents, 5, 4)["nextOffset"], _answer(two_contents, 5, 4)["hasMore"]) == (9, False)


def test_a_single_file_with_eight_places_fills_a_page_of_five(api: TestClient) -> None:
    store, index = _services(api)
    _active(store, EIGHT, _publish(store, index, b"eight places", _eight_places()))

    answer = _answer(api, 5)

    assert _places(answer) == [(EIGHT, 400), (EIGHT, 5400), (EIGHT, 10400), (EIGHT, 15400), (EIGHT, 20400)]
    assert (answer["nextOffset"], answer["hasMore"]) == (5, True)
    rest = _answer(api, 5, 5)
    assert _places(rest) == [(EIGHT, 25400), (EIGHT, 30400), (EIGHT, 35400)]
    assert rest["hasMore"] is False


def test_a_refined_transcript_is_final(api: TestClient) -> None:
    store, index = _services(api)
    _active(store, ONE, _publish(store, index, b"refined", _one_strong_place(), Level.REFINED))

    hits = _answer(api, 5)["hits"]

    assert isinstance(hits, list)
    assert [(h["fileId"], h["sample"], h["stage"]) for h in hits] == [(ONE, False, "final")]


def test_a_sample_hit_carries_the_stage_sample(api: TestClient) -> None:
    store, index = _services(api)
    sha = hashlib.sha256(b"sample bytes").hexdigest()
    media_id = store.media_for_file_sha256(sha)
    store.put_sample(42, media_id)
    prov = Provenance(
        engine="sample",
        model_sha256=SAMPLE_MODEL_SHA256,
        config_version=1,
        profile="debug",
        level=Level.SAMPLE,
        epoch=0,
        language="de",
        input_file_sha256=sha,
    )
    result = store.publish_version(media_id, prov, sample_api.sample_words(0))
    assert result.index_rev is not None
    index.publish(media_id, result.index_rev, segments_from_words(store.effective_words(media_id)))

    response = _post(api, {"term": "Audiosuche", "limit": 5})

    assert [(h["fileId"], h["sample"], h["stage"]) for h in response.json()["hits"]] == [(42, True, "sample")]


def test_the_older_revision_does_not_mix_with_the_current_one(two_contents: TestClient) -> None:
    store, index = _services(two_contents)
    media_id = store.media_for_file(EIGHT)
    assert media_id is not None
    store.add_correction(media_id, 0, 10, "speaker", "A", author_uid="admin", base_version_id=None, base_text=None)
    current = store.current(media_id)
    assert current is not None
    assert current.index_rev == 2

    # Only revision 1 stands in the index: it is current - 1, so all eight of
    # its segments count, each at its segment start (its words are gone).
    old = [(ONE, 0)] + [(EIGHT, i * STEP_MS) for i in range(8)]
    assert _places(_answer(two_contents, 15)) == old

    # Revision 2 arrives with two segments, revision 1 is not retired yet (a
    # crash before retire): only the two of revision 2 count, none of revision 1.
    index.publish(media_id, 2, segments_from_words(_eight_places()[:4]))
    assert _places(_answer(two_contents, 15)) == [(ONE, 0), (EIGHT, 400), (EIGHT, 5400)]


def test_the_candidate_count_does_not_depend_on_limit_or_offset(
    two_contents: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[int] = []
    original = SearchIndex.search

    def recording(self: SearchIndex, term: str, limit: int) -> list[IndexHit]:
        asked.append(limit)
        return original(self, term, limit)

    monkeypatch.setattr(SearchIndex, "search", recording)
    for limit, offset in ((5, 0), (10, 0), (5, 5), (50, 1200)):
        _answer(two_contents, limit, offset)

    assert asked == [search_api.MAX_CANDIDATES] * 4
    assert search_api.MAX_CANDIDATES == 2000


@pytest.mark.parametrize(
    "body",
    [
        {"term": SPOKEN, "limit": 5, "offset": -1},
        {"term": SPOKEN, "limit": 5, "offset": 1201},
        {"term": SPOKEN, "limit": 5, "offset": True},
        {"term": SPOKEN, "limit": 5, "offset": "5"},
        {"term": SPOKEN, "limit": 0},
        {"term": SPOKEN, "limit": 51},
    ],
)
def test_out_of_range_offset_and_limit_are_refused(api: TestClient, body: dict[str, object]) -> None:
    assert _post(api, body).status_code == 422


def test_the_highest_offset_is_accepted(api: TestClient) -> None:
    # Positive control of the bound above.
    assert search_api.MAX_OFFSET == 1200
    answer = _answer(api, 5, 1200)
    assert (answer["hits"], answer["nextOffset"], answer["hasMore"]) == ([], 1200, False)


def test_an_empty_term_gives_no_hits_and_nothing_more(two_contents: TestClient) -> None:
    response = _post(two_contents, {"term": "   ", "limit": 5, "offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert (body["hits"], body["hasMore"], body["nextOffset"]) == ([], False, 2)
    assert set(body) == {"appVersion", "hits", "nextOffset", "hasMore"}


def test_a_file_named_by_two_contents_shows_the_places_of_one_only(api: TestClient) -> None:
    # File 42 has an active reference to a real transcript and a visible sample
    # of other bytes; both contain the term. The hit follows the excerpt
    # (Store.media_for_file): the real transcript, never a mix of the two.
    store, index = _services(api)
    real_words = [
        Word(0, 350, "Echte", "echte", 0.9, "machine"),
        Word(400, 750, "Audiosuche", "audiosuche", 0.9, "machine"),
    ]
    real = _publish(store, index, b"real bytes", real_words)
    _active(store, 42, real)
    sha = hashlib.sha256(b"sample bytes").hexdigest()
    sampled = store.media_for_file_sha256(sha)
    store.put_sample(42, sampled)
    prov = Provenance(
        engine="sample",
        model_sha256=SAMPLE_MODEL_SHA256,
        config_version=1,
        profile="debug",
        level=Level.SAMPLE,
        epoch=0,
        language="de",
        input_file_sha256=sha,
    )
    result = store.publish_version(sampled, prov, sample_api.sample_words(0))
    assert result.index_rev is not None
    index.publish(sampled, result.index_rev, segments_from_words(store.effective_words(sampled)))
    # Positive control: both contents name file 42.
    assert store.file_ids_for_media(real) == [42]
    assert store.file_ids_for_media(sampled) == [42]

    hits = _post(api, {"term": "Audiosuche", "limit": 10}).json()["hits"]

    assert [(h["fileId"], h["excerpt"], h["sample"], h["stage"]) for h in hits] == [
        (42, "Echte Audiosuche", False, "preview")
    ]
