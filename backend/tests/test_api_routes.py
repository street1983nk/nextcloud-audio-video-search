"""The container contract of plan 01-03: /sample, /sample/remove, /search, /excerpt.

The gateway is faked in two ways: the route tests replace ``nc.fetch_file_sha256``
with a coroutine, the gateway tests hand ``fetch_file_sha256`` an httpx client
on a MockTransport, so the streaming, hashing and error mapping run for real.
"""

import hashlib
import json
import logging
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend import main, nc
from audio_video_search_backend.api import sample as sample_api
from audio_video_search_backend.index.publish import IndexHit, SearchIndex, Segment
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.store.repo import Store
from tests.conftest import signed_headers

CONTENT = b"RIFF fake media bytes " * 100
SHA = hashlib.sha256(CONTENT).hexdigest()
AT_MS = 61_000
# "Audiosuche" is the seventh word of the sample text, so it starts six slots in.
AUDIOSUCHE_MS = AT_MS + 6 * 400


@pytest.fixture
def fetched(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    """Replace the gateway; every call is recorded."""
    calls: list[tuple[int, str]] = []

    async def fake(file_id: int, user_id: str, *, max_bytes: int) -> nc.FetchResult:
        assert max_bytes == sample_api.MAX_SAMPLE_BYTES
        calls.append((file_id, user_id))
        return nc.FetchResult(sha256=SHA, size=len(CONTENT), error=None)

    monkeypatch.setattr(nc, "fetch_file_sha256", fake)
    return calls


@pytest.fixture
def api(fetched: list[tuple[int, str]]) -> Iterator[TestClient]:
    with TestClient(main.APP) as test_client:
        yield test_client


def _post(client: TestClient, path: str, body: dict[str, object]) -> httpx.Response:
    return client.post(path, headers=signed_headers(), json=body)


def _seed(client: TestClient, file_id: int = 42) -> dict[str, object]:
    response = _post(client, "/sample", {"fileId": file_id, "userId": "admin", "atMs": AT_MS})
    assert response.status_code == 200
    return response.json()


def _search(client: TestClient, term: str, limit: int = 10) -> dict[str, object]:
    response = _post(client, "/search", {"term": term, "limit": limit})
    assert response.status_code == 200
    return response.json()


def _services(client: TestClient) -> tuple[Store, SearchIndex]:
    state = client.app.state  # pyright: ignore[reportAttributeAccessIssue]
    return state.services.store, state.services.index


# -- /sample ----------------------------------------------------------------


def test_sample_publishes_through_the_gateway(api: TestClient, fetched: list[tuple[int, str]]) -> None:
    answer = _seed(api)

    assert answer["result"] == "published"
    assert answer["indexRev"] == 1
    assert isinstance(answer["mediaId"], int)
    assert fetched == [(42, "admin")]
    store, _ = _services(api)
    assert store.media_for_file(42) == answer["mediaId"]
    assert store.pending_index_work() == []


def test_a_second_sample_of_the_same_file_is_stale(api: TestClient) -> None:
    first = _seed(api)
    second = _seed(api)

    assert second == {"result": "stale_rejected", "mediaId": first["mediaId"], "indexRev": None}


@pytest.mark.parametrize("error", ["gateway_denied", "gateway_failed"])
def test_a_gateway_error_is_reported_as_a_code(api: TestClient, monkeypatch: pytest.MonkeyPatch, error: str) -> None:
    async def failing(file_id: int, user_id: str, *, max_bytes: int) -> nc.FetchResult:
        return nc.FetchResult(sha256=None, size=0, error=error)

    monkeypatch.setattr(nc, "fetch_file_sha256", failing)

    response = _post(api, "/sample", {"fileId": 42, "userId": "admin", "atMs": 0})

    assert response.status_code == 200
    assert response.json() == {"error": error}


@pytest.mark.parametrize(
    "body",
    [
        {"fileId": 0, "userId": "admin", "atMs": 0},
        {"fileId": -3, "userId": "admin", "atMs": 0},
        {"fileId": 1, "userId": "admin", "atMs": -1},
        {"fileId": 1, "userId": "admin", "atMs": 86_400_001},
        {"fileId": 1, "userId": "", "atMs": 0},
        {"fileId": 1, "userId": "u" * 65, "atMs": 0},
        {"fileId": True, "userId": "admin", "atMs": 0},
    ],
)
def test_sample_refuses_out_of_range_input(api: TestClient, body: dict[str, object]) -> None:
    assert _post(api, "/sample", body).status_code == 422


def test_routes_need_a_signature(api: TestClient) -> None:
    for path in ("/sample", "/sample/remove", "/search", "/excerpt"):
        assert api.post(path, json={}).status_code == 401, path


# -- /search ----------------------------------------------------------------


def test_search_finds_the_seeded_word_at_its_time(api: TestClient) -> None:
    _seed(api)

    answer = _search(api, "Audiosuche")

    assert answer["appVersion"] == "0.1.0"
    hits = answer["hits"]
    assert isinstance(hits, list)
    assert len(hits) == 1
    assert hits[0]["fileId"] == 42
    assert hits[0]["startMs"] == AUDIOSUCHE_MS
    assert "Audiosuche" in hits[0]["excerpt"]
    assert hits[0]["sample"] is True


def test_every_file_of_a_media_item_gets_one_hit(api: TestClient) -> None:
    _seed(api, 42)
    _seed(api, 43)  # same bytes, same media item, stale but linked

    assert sorted(h["fileId"] for h in _search(api, "Audiosuche")["hits"]) == [42, 43]  # type: ignore[union-attr]


def test_an_empty_term_has_no_hits(api: TestClient) -> None:
    _seed(api)

    assert _search(api, "   ")["hits"] == []


def test_a_long_term_is_cut_not_refused(api: TestClient) -> None:
    _seed(api)

    assert len(_search(api, "Audiosuche " + "x" * 500)["hits"]) == 1  # type: ignore[arg-type]


@pytest.mark.parametrize("limit", [0, 51, -1])
def test_search_refuses_a_limit_outside_one_to_fifty(api: TestClient, limit: int) -> None:
    assert _post(api, "/search", {"term": "x", "limit": limit}).status_code == 422


def test_search_drops_revisions_older_than_current_minus_one(api: TestClient) -> None:
    answer = _seed(api)
    media_id = int(answer["mediaId"])  # type: ignore[arg-type]
    store, index = _services(api)
    for _ in range(2):
        store.add_correction(media_id, 0, 10, "speaker", "A", author_uid="admin", base_version_id=None, base_text=None)
    # current.index_rev is 3 now; revision 1 stays in the index next to nothing else.
    current = store.current(media_id)
    assert current is not None
    assert current.index_rev == 3

    assert _search(api, "Audiosuche")["hits"] == []

    index.publish(media_id, 2, [Segment(0, AT_MS, AT_MS + 1000, "Audiosuche zwei")])
    hits = _search(api, "Audiosuche")["hits"]
    assert [h["excerpt"] for h in hits] == ["Audiosuche zwei"]  # type: ignore[union-attr]


def test_search_keeps_only_the_highest_admissible_revision(api: TestClient) -> None:
    answer = _seed(api)
    media_id = int(answer["mediaId"])  # type: ignore[arg-type]
    store, index = _services(api)
    store.add_correction(media_id, 0, 10, "speaker", "A", author_uid="admin", base_version_id=None, base_text=None)
    # Revision 2 is current, revision 1 still stands (a crash before retire).
    index.publish(media_id, 2, [Segment(0, AT_MS, AT_MS + 1000, "Audiosuche neu")])

    hits = _search(api, "Audiosuche")["hits"]

    assert [h["excerpt"] for h in hits] == ["Audiosuche neu"]  # type: ignore[union-attr]


def test_the_admissible_filter_is_pure() -> None:
    from audio_video_search_backend.api.search import admissible

    hits = [
        IndexHit(1, 1, 0, 0, 3.0, "a"),
        IndexHit(1, 2, 0, 0, 1.0, "b"),
        IndexHit(2, 1, 0, 0, 2.0, "c"),
        IndexHit(3, 5, 0, 0, 9.0, "d"),
    ]

    chosen = admissible(hits, {1: 2, 2: 2, 3: None})

    # Best score first; media 1 keeps revision 2 although revision 1 scored higher.
    assert [(h.media_id, h.index_rev) for h in chosen] == [(2, 1), (1, 2)]


# -- /excerpt ---------------------------------------------------------------


def test_excerpt_of_a_known_file(api: TestClient) -> None:
    _seed(api)

    response = _post(api, "/excerpt", {"fileId": 42, "atMs": AUDIOSUCHE_MS})

    assert response.status_code == 200
    body = response.json()
    assert body["known"] is True
    assert "Audiosuche" in body["excerpt"]


def test_excerpt_takes_the_next_segment_before_the_first_word(api: TestClient) -> None:
    _seed(api)

    body = _post(api, "/excerpt", {"fileId": 42, "atMs": 0}).json()

    assert body["known"] is True
    assert body["excerpt"].startswith("Dies ist")


def test_excerpt_shows_a_correction(api: TestClient) -> None:
    answer = _seed(api)
    store, _ = _services(api)
    store.add_correction(
        int(answer["mediaId"]),  # type: ignore[arg-type]
        AUDIOSUCHE_MS,
        AUDIOSUCHE_MS + 400,
        "text",
        "Mediensuche",
        author_uid="admin",
        base_version_id=None,
        base_text=None,
    )

    body = _post(api, "/excerpt", {"fileId": 42, "atMs": AUDIOSUCHE_MS}).json()

    assert "Mediensuche" in body["excerpt"]
    assert "Audiosuche" not in body["excerpt"]


def test_excerpt_of_an_unknown_file(api: TestClient) -> None:
    assert _post(api, "/excerpt", {"fileId": 9, "atMs": 0}).json() == {"known": False, "excerpt": None}


@pytest.mark.parametrize("body", [{"fileId": 0, "atMs": 0}, {"fileId": 1, "atMs": -5}, {"fileId": 1}])
def test_excerpt_refuses_bad_input(api: TestClient, body: dict[str, object]) -> None:
    assert _post(api, "/excerpt", body).status_code == 422


# -- /sample/remove ---------------------------------------------------------


def test_remove_takes_the_sample_out_of_store_and_index(api: TestClient) -> None:
    answer = _seed(api)

    removed = _post(api, "/sample/remove", {"fileId": 42}).json()

    assert removed == {"result": "removed", "mediaId": answer["mediaId"]}
    assert _search(api, "Audiosuche")["hits"] == []
    assert _post(api, "/excerpt", {"fileId": 42, "atMs": AT_MS}).json() == {"known": False, "excerpt": None}
    assert _post(api, "/sample/remove", {"fileId": 42}).json() == {"result": "not_found", "mediaId": None}


def test_remove_leaves_a_real_transcript_alone(api: TestClient) -> None:
    answer = _seed(api)
    media_id = int(answer["mediaId"])  # type: ignore[arg-type]
    store, index = _services(api)
    real = Provenance(
        engine="parakeet",
        model_sha256="c" * 64,
        config_version=1,
        profile="fast",
        level=Level.PREVIEW,
        epoch=store.media_epoch(media_id),
        language="de",
        input_file_sha256=SHA,
    )
    result = store.publish_version(media_id, real, store.machine_words(1))
    assert result.published
    assert result.index_rev is not None
    index.reconcile(store)

    removed = _post(api, "/sample/remove", {"fileId": 42}).json()

    assert removed == {"result": "not_sample", "mediaId": media_id}
    hits = _search(api, "Audiosuche")["hits"]
    assert [h["sample"] for h in hits] == [False]  # type: ignore[union-attr]


def test_remove_refuses_a_file_id_below_one(api: TestClient) -> None:
    assert _post(api, "/sample/remove", {"fileId": 0}).status_code == 422


# -- privacy of the log -----------------------------------------------------


def test_no_log_line_carries_the_term_the_excerpt_or_a_path(
    api: TestClient, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    caplog.set_level(logging.DEBUG)
    _seed(api)
    _search(api, "Audiosuche")
    _post(api, "/excerpt", {"fileId": 42, "atMs": AT_MS})
    _post(api, "/sample/remove", {"fileId": 42})

    assert caplog.records
    for record in caplog.records:
        line = record.getMessage() + json.dumps({k: str(v) for k, v in vars(record).items()})
        for secret in ("Audiosuche", "Testtreffer", str(tmp_path), "state.db"):
            assert secret not in line, record.getMessage()


# -- lifespan ---------------------------------------------------------------


def test_the_lifespan_opens_store_and_index_under_the_volume_and_reconciles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: list[tuple[int, str]]
) -> None:
    calls: list[int] = []
    original = SearchIndex.reconcile

    def recording(self: SearchIndex, store: Store) -> int:
        calls.append(1)
        return original(self, store)

    monkeypatch.setattr(SearchIndex, "reconcile", recording)

    with TestClient(main.APP) as client:
        _seed(client)
    assert (tmp_path / "state.db").is_file()
    assert any((tmp_path / "index").iterdir())
    assert calls

    # A restart finds the hit again from what lies on the volume.
    with TestClient(main.APP) as client:
        assert len(_search(client, "Audiosuche")["hits"]) == 1  # type: ignore[arg-type]


# -- the gateway client -----------------------------------------------------


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


async def _chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


async def test_the_gateway_stream_is_hashed_chunk_by_chunk() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        chunks = [CONTENT[:700], CONTENT[700:1500], CONTENT[1500:]]
        return httpx.Response(200, content=_chunks(*chunks))

    async with _client(httpx.MockTransport(handler)) as client:
        result = await nc.fetch_file_sha256(42, "alice", max_bytes=10_000, client=client)

    assert result == nc.FetchResult(sha256=SHA, size=len(CONTENT), error=None)
    request = seen[0]
    assert request.url.path == "/ocs/v2.php/apps/audio_video_search/files/42"
    assert request.url.params["userId"] == "alice"
    assert request.headers["EX-APP-ID"] == "audio_video_search_backend"
    assert request.headers["OCS-APIRequest"] == "true"
    assert "AUTHORIZATION-APP-API" in request.headers
    assert "EX-APP-VERSION" in request.headers
    assert "AA-VERSION" in request.headers


@pytest.mark.parametrize(
    ("status", "error"), [(403, "gateway_denied"), (404, "gateway_denied"), (422, "gateway_failed")]
)
async def test_a_gateway_status_maps_to_a_code(status: int, error: str) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(status, text="/secret/path.mp4"))

    async with _client(transport) as client:
        result = await nc.fetch_file_sha256(42, "alice", max_bytes=10_000, client=client)

    assert result == nc.FetchResult(sha256=None, size=0, error=error)


async def test_a_network_error_is_a_failed_gateway() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async with _client(httpx.MockTransport(handler)) as client:
        result = await nc.fetch_file_sha256(42, "alice", max_bytes=10_000, client=client)

    assert result.error == "gateway_failed"
    assert result.sha256 is None


async def test_a_short_answer_is_a_failed_gateway() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Length": "5000"}, content=_chunks(b"only a few bytes"))

    async with _client(httpx.MockTransport(handler)) as client:
        result = await nc.fetch_file_sha256(42, "alice", max_bytes=10_000, client=client)

    assert result.error == "gateway_failed"


async def test_an_endless_stream_stops_at_the_byte_cap() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_chunks(b"x" * 600, b"x" * 600))

    async with _client(httpx.MockTransport(handler)) as client:
        result = await nc.fetch_file_sha256(42, "alice", max_bytes=1000, client=client)

    assert result.error == "gateway_failed"
    assert result.sha256 is None


def test_the_sample_cap_is_eight_gibibytes() -> None:
    assert sample_api.MAX_SAMPLE_BYTES == 8 * 1024**3
