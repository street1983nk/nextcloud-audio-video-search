"""A sample gives text only while its content stands at the sample level (plan 02-16b, owner 13.11.2026).

occ :sample reads the bytes of a file as the user the admin named and points
the sample of that file at the content of those bytes. When that content has a
real transcript, the sample must not hand it out: not as a hit of the search
and not as an excerpt. For such a content the ordinary rules hold, a hit and an
excerpt only through an active reference of the discovery (D-02-01a, D-02-15a
addendum). Before this plan the search named the file and POST /excerpt gave
the real text, with ``sample`` false in the hit, so the debug switch of the PHP
app did not hide it either.

Measured at the routes, with the real app, a real state.db and a real index.
The search is compared with the same search before the sample existed, the
excerpt with the answer for a file id nobody has ever seen.
"""

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend import main, nc
from audio_video_search_backend.api import sample as sample_api
from audio_video_search_backend.index.publish import SearchIndex, segments_from_words
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.store.repo import IntakeItem, Store
from tests.conftest import signed_headers
from tests.test_api_routes import AT_MS, CONTENT, SHA, _seed, _services

MODEL = "c" * 64
FILE = 42
OTHER = 41
UNKNOWN = 9
SPOKEN = "Haushaltsgeheimnis"
REAL_TEXT = f"Das {SPOKEN}"
# The excerpt of the real transcript through an active reference without a preview job (plan 03-14).
REAL_ANSWER = {
    "known": True,
    "excerpt": REAL_TEXT,
    "stage": "preview",
    "partial": False,
    "pendingHere": False,
    "reason": None,
}


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The app with a gateway that always gives the same bytes, the ones of the transcribed content."""

    async def fake(file_id: int, user_id: str, *, max_bytes: int) -> nc.FetchResult:
        del file_id, user_id, max_bytes
        return nc.FetchResult(sha256=SHA, size=len(CONTENT), error=None)

    monkeypatch.setattr(nc, "fetch_file_sha256", fake)
    with TestClient(main.APP) as client:
        yield client


def _transcribe(store: Store, index: SearchIndex) -> int:
    """A real transcript for the content of SHA, published and indexed; its text is what must not get out."""
    media_id = store.media_for_file_sha256(SHA)
    prov = Provenance(
        engine="parakeet",
        model_sha256=MODEL,
        config_version=1,
        profile="balanced",
        level=Level.PREVIEW,
        epoch=store.media_epoch(media_id),
        language="de",
        input_file_sha256=SHA,
    )
    words = [Word(i * 400, i * 400 + 350, w, w.lower(), 0.9, "machine") for i, w in enumerate(["Das", SPOKEN])]
    result = store.publish_version(media_id, prov, words)
    assert result.published
    assert result.index_rev is not None
    index.publish(media_id, result.index_rev, segments_from_words(store.effective_words(media_id)))
    index.retire(media_id, keep_rev=result.index_rev)
    store.mark_indexed(media_id, result.index_rev)
    return media_id


def _reference(store: Store, file_id: int, media_id: int | None, stage: str = "keyed") -> None:
    store.upsert_file_ref(
        file_id, media_id, storage_id=3, etag="e1", size=1000, mtime=1_700_000_000, state="active", stage=stage,
        reason=None,
    )  # fmt: skip


def _pending(file_id: int) -> IntakeItem:
    return IntakeItem(
        queue_id=1,
        kind="content",
        file_id=file_id,
        storage_id=3,
        etag="etag-1",
        size=2200,
        mtime=1_700_000_000,
        prefilter_key=None,
        reader_uid="ana",
    )


def _search(client: TestClient, term: str = SPOKEN) -> httpx.Response:
    return client.post("/search", headers=signed_headers(), json={"term": term, "limit": 10})


def _excerpt(client: TestClient, file_id: int = FILE, at_ms: int = 0) -> httpx.Response:
    return client.post("/excerpt", headers=signed_headers(), json={"fileId": file_id, "atMs": at_ms})


def _same_answer(one: httpx.Response, other: httpx.Response) -> bool:
    """Status, body and the headers that describe the body; nothing tells the two apart."""
    return (one.status_code, one.content, one.headers.get("content-type"), one.headers.get("content-length")) == (
        other.status_code,
        other.content,
        other.headers.get("content-type"),
        other.headers.get("content-length"),
    )


def _hits(client: TestClient, term: str = SPOKEN) -> list[tuple[int, bool]]:
    answer = _search(client, term)
    assert answer.status_code == 200
    return [(int(hit["fileId"]), bool(hit["sample"])) for hit in answer.json()["hits"]]


def _no_text_for_the_sample(client: TestClient, before: httpx.Response) -> None:
    """The search as before the sample existed, the excerpt as for a file never seen, and no real word in either."""
    assert before.status_code == 200
    assert before.json()["hits"] == []
    unknown = _excerpt(client, UNKNOWN)
    assert unknown.json() == {"known": False}

    search = _search(client)
    excerpt = _excerpt(client)

    assert SPOKEN.encode() not in search.content
    assert SPOKEN.encode() not in excerpt.content
    assert _same_answer(search, before)
    assert _same_answer(excerpt, unknown)


def test_the_real_transcript_is_found_through_an_active_reference(api: TestClient) -> None:
    # The positive control of everything below: the term does find the content.
    store, index = _services(api)
    media_id = _transcribe(store, index)
    _reference(store, OTHER, media_id)

    assert _hits(api) == [(OTHER, False)]
    assert _excerpt(api, OTHER).json() == REAL_ANSWER


def test_a_sample_on_a_content_with_a_real_transcript_gives_no_hit_and_no_excerpt(api: TestClient) -> None:
    store, index = _services(api)
    media_id = _transcribe(store, index)
    before = _search(api)

    # The way of occ :sample: the real transcript wins, the sample still points at the content.
    answer = _seed(api, FILE)

    assert answer == {"result": "stale_rejected", "mediaId": media_id, "indexRev": None}
    assert store.sample_media(FILE) == media_id
    assert store.file_ref(FILE) is None
    _no_text_for_the_sample(api, before)
    assert store.file_ids_for_media(media_id) == []
    assert store.media_for_file(FILE) is None


def test_a_sample_beside_an_active_reference_without_content_gives_no_real_text(api: TestClient) -> None:
    store, index = _services(api)
    media_id = _transcribe(store, index)
    before = _search(api)
    store.apply_intake([_pending(FILE)])
    ref = store.file_ref(FILE)
    assert ref is not None
    assert (ref.state, ref.stage, ref.media_id) == ("active", "pending", None)

    store.put_sample(FILE, media_id)

    _no_text_for_the_sample(api, before)
    assert store.file_ids_for_media(media_id) == []
    assert store.media_for_file(FILE) is None


def test_a_real_transcript_published_after_the_sample_takes_the_sample_hit_away(api: TestClient) -> None:
    store, index = _services(api)
    assert _seed(api, FILE)["result"] == "published"
    assert _hits(api, "Audiosuche") == [(FILE, True)]
    assert _excerpt(api).json()["known"] is True
    before = _search(api)
    assert before.json()["hits"] == []

    media_id = _transcribe(store, index)

    assert store.sample_media(FILE) == media_id
    assert _hits(api, "Audiosuche") == []
    _no_text_for_the_sample(api, before)


def test_only_the_file_with_the_active_reference_gets_the_real_text(api: TestClient) -> None:
    store, index = _services(api)
    media_id = _transcribe(store, index)
    _reference(store, OTHER, media_id)
    store.put_sample(FILE, media_id)

    assert _hits(api) == [(OTHER, False)]
    assert store.file_ids_for_media(media_id) == [OTHER]
    assert _excerpt(api, OTHER).json() == REAL_ANSWER
    assert _same_answer(_excerpt(api), _excerpt(api, UNKNOWN))


def test_an_active_reference_of_the_same_file_keeps_hit_and_excerpt_beside_its_sample(api: TestClient) -> None:
    store, index = _services(api)
    media_id = _transcribe(store, index)
    _reference(store, FILE, media_id)
    store.put_sample(FILE, media_id)

    assert _hits(api) == [(FILE, False)]
    assert _excerpt(api).json() == REAL_ANSWER


def test_a_sample_at_the_sample_level_keeps_its_hit_and_its_excerpt(api: TestClient) -> None:
    # The guard: the test result of the walking skeleton itself is untouched.
    store, _index = _services(api)
    answer = _seed(api, FILE)
    media_id = store.sample_media(FILE)
    assert media_id is not None
    current = store.current(media_id)
    assert current is not None
    assert current.level == Level.SAMPLE

    assert answer["result"] == "published"
    assert _hits(api, "Audiosuche") == [(FILE, True)]
    assert store.file_ids_for_media(media_id) == [FILE]
    assert store.media_for_file(FILE) == media_id
    assert _excerpt(api, at_ms=AT_MS).json() == {
        "known": True,
        "excerpt": sample_api.SAMPLE_TEXT,
        "stage": "sample",
        "partial": False,
        "pendingHere": False,
        "reason": None,
    }


def test_a_sample_whose_content_has_no_version_yet_names_its_content_but_gives_no_text(api: TestClient) -> None:
    # Nothing to give out: no current version, so no hit and an excerpt like for an unknown file.
    store, _index = _services(api)
    media_id = store.media_for_file_sha256(SHA)
    store.put_sample(FILE, media_id)

    assert _hits(api) == []
    assert _same_answer(_excerpt(api), _excerpt(api, UNKNOWN))


def test_the_excerpt_of_a_sample_on_a_real_transcript_is_the_answer_for_a_file_never_seen(api: TestClient) -> None:
    # The excerpt route on its own, so its answer is measured whatever the search says.
    store, index = _services(api)
    media_id = _transcribe(store, index)
    store.put_sample(FILE, media_id)

    answer = _excerpt(api)

    assert SPOKEN.encode() not in answer.content
    assert _same_answer(answer, _excerpt(api, UNKNOWN))
