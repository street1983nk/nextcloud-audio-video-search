"""POST /excerpt gives text only for a reference that may give a hit (plan 02-15c, D-02-01a third addendum).

The playback page asks ``isReadable()`` before it asks for the excerpt, and an
SMB server that denies a file lets that say yes (Findling measurement A6). So
the container itself must not hand out the text of a transcript for a
reference whose read proof failed or is owed (unreadable), that lies in the
trash (trashed) or whose storage is gone (vanished): for every one of them the
route answers exactly as for a file id it has never seen.

Measured at the route itself, with the real app and a real state.db.
"""

import hashlib
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend import main
from audio_video_search_backend.api import sample as sample_api
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import SAMPLE_MODEL_SHA256, Level, Provenance
from audio_video_search_backend.store import repo
from audio_video_search_backend.store.repo import IntakeItem, Store
from tests.conftest import signed_headers

SHA = hashlib.sha256(b"the bytes of the recording").hexdigest()
HEAD = hashlib.sha256(b"the head of the recording").hexdigest()
MODEL = "c" * 64
PREFILTER = "a" * 64
FILE = 42
UNKNOWN = 9
NOW = 1_800_000_000
SPOKEN = "Haushaltsgeheimnis"

NOT_ACTIVE = sorted((state, stage) for state in repo.STATES - {"active"} for stage in repo.STAGES)


@pytest.fixture
def api() -> Iterator[TestClient]:
    with TestClient(main.APP) as client:
        yield client


def _store(client: TestClient) -> Store:
    return client.app.state.services.store  # pyright: ignore[reportAttributeAccessIssue]


def _transcribed(store: Store) -> int:
    """A content with a real transcript; its text is what must not get out."""
    media_id = store.media_for_file_sha256(SHA)
    prov = Provenance(
        engine="parakeet",
        model_sha256=MODEL,
        config_version=1,
        profile="balanced",
        level=Level.PREVIEW,
        epoch=0,
        language="de",
        input_file_sha256=SHA,
    )
    words = [Word(i * 400, i * 400 + 350, w, w.lower(), 0.9, "machine") for i, w in enumerate(["Das", SPOKEN])]
    assert store.publish_version(media_id, prov, words).published
    return media_id


def _reference(store: Store, media_id: int, state: str, stage: str, file_id: int = FILE) -> None:
    store.upsert_file_ref(
        file_id,
        media_id,
        storage_id=3,
        etag="e1",
        size=1000,
        mtime=1_700_000_000,
        state=state,
        stage=stage,
        reason=None,
        prefilter_key=PREFILTER,
        reader_uid="ana",
        proved_at=5,
    )


def _excerpt(client: TestClient, file_id: int = FILE) -> httpx.Response:
    return client.post("/excerpt", headers=signed_headers(), json={"fileId": file_id, "atMs": 0})


def _same_answer(one: httpx.Response, other: httpx.Response) -> bool:
    """Status, body and the headers that describe the body; nothing tells the two apart."""
    return (one.status_code, one.content, one.headers.get("content-type"), one.headers.get("content-length")) == (
        other.status_code,
        other.content,
        other.headers.get("content-type"),
        other.headers.get("content-length"),
    )


def _row(kind: str, queue_id: int, *, versioned: bool) -> IntakeItem:
    return IntakeItem(
        queue_id=queue_id,
        kind=kind,
        file_id=FILE,
        storage_id=3,
        etag="e1" if versioned else None,
        size=1000 if versioned else None,
        mtime=1_700_000_000 if versioned else None,
        prefilter_key=PREFILTER if versioned else None,
        reader_uid="ana" if versioned else None,
    )


@pytest.mark.parametrize(("state", "stage"), NOT_ACTIVE)
def test_a_reference_that_gives_no_hit_is_answered_like_a_file_never_seen(
    api: TestClient, state: str, stage: str
) -> None:
    store = _store(api)
    media_id = _transcribed(store)
    _reference(store, media_id, state, stage)
    assert store.file_ids_for_media(media_id) == []

    answer = _excerpt(api)
    unknown = _excerpt(api, UNKNOWN)

    assert unknown.status_code == 200
    assert unknown.json() == {"known": False, "excerpt": None}
    assert SPOKEN.encode() not in answer.content
    assert _same_answer(answer, unknown)


def test_the_list_of_states_without_a_hit_is_every_state_but_active() -> None:
    # A new state must be decided here before it can give out text.
    assert {state for state, _stage in NOT_ACTIVE} == {"unreadable", "vanished", "trashed"}
    assert {stage for _state, stage in NOT_ACTIVE} == {"pending", "probing", "fetching", "keyed", "failed"}


@pytest.mark.parametrize("stage", ["keyed", "probing"])
def test_an_active_reference_gets_its_excerpt_as_before(api: TestClient, stage: str) -> None:
    store = _store(api)
    media_id = _transcribed(store)
    # probing: the renewed proof of an active reference is only due, it still gives hits.
    _reference(store, media_id, "active", stage)
    assert store.file_ids_for_media(media_id) == [FILE]

    answer = _excerpt(api)

    assert answer.status_code == 200
    assert answer.json() == {"known": True, "excerpt": f"Das {SPOKEN}"}


def test_another_active_copy_does_not_open_the_excerpt_for_the_one_without_a_hit(api: TestClient) -> None:
    store = _store(api)
    media_id = _transcribed(store)
    _reference(store, media_id, "active", "keyed", file_id=41)
    _reference(store, media_id, "unreadable", "failed")

    assert _excerpt(api, 41).json()["known"] is True
    assert _same_answer(_excerpt(api), _excerpt(api, UNKNOWN))


def test_the_trash_and_a_restore_that_owes_its_proof_give_no_excerpt_until_the_proof_passed(api: TestClient) -> None:
    store = _store(api)
    media_id = _transcribed(store)
    store.reading_connection().execute("UPDATE media SET head_sha256 = ? WHERE media_id = ?", (HEAD, media_id))
    _reference(store, media_id, "active", "keyed")
    assert _excerpt(api).json()["known"] is True

    store.apply_intake([_row("trash", 1, versioned=False)])
    assert _same_answer(_excerpt(api), _excerpt(api, UNKNOWN))

    store.apply_intake([_row("restore", 2, versioned=True)])
    restored = store.file_ref(FILE)
    assert restored is not None
    assert (restored.state, restored.stage) == ("unreadable", "probing")
    assert _same_answer(_excerpt(api), _excerpt(api, UNKNOWN))

    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert _same_answer(_excerpt(api), _excerpt(api, UNKNOWN))
    assert store.confirm_proof(FILE, "e1", NOW)

    assert _excerpt(api).json() == {"known": True, "excerpt": f"Das {SPOKEN}"}


def test_a_renewed_proof_that_fails_takes_the_excerpt_away_at_once(api: TestClient) -> None:
    store = _store(api)
    media_id = _transcribed(store)
    _reference(store, media_id, "active", "probing")
    claimed = store.next_capture(NOW)
    assert claimed is not None
    assert _excerpt(api).json()["known"] is True

    assert store.fail_proof(claimed, "read_denied", retry_at=NOW + 60, now=NOW)

    assert _same_answer(_excerpt(api), _excerpt(api, UNKNOWN))


@pytest.mark.parametrize("state", sorted(repo.STATES - {"active"}))
def test_a_sample_beside_a_reference_without_a_hit_gives_no_excerpt(api: TestClient, state: str) -> None:
    # The rule of the sample layer (D-02-15), unchanged: held here so it stays that way.
    store = _store(api)
    media_id = _transcribed(store)
    _reference(store, media_id, state, "keyed")
    store.put_sample(FILE, media_id)

    assert _same_answer(_excerpt(api), _excerpt(api, UNKNOWN))


def test_a_sample_without_a_reference_keeps_its_excerpt(api: TestClient) -> None:
    store = _store(api)
    media_id = store.media_for_file_sha256(SHA)
    store.put_sample(FILE, media_id)
    prov = Provenance(
        engine="sample",
        model_sha256=SAMPLE_MODEL_SHA256,
        config_version=1,
        profile="debug",
        level=Level.SAMPLE,
        epoch=0,
        language="de",
        input_file_sha256=SHA,
    )
    assert store.publish_version(media_id, prov, sample_api.sample_words(0)).published

    assert _excerpt(api).json() == {"known": True, "excerpt": sample_api.SAMPLE_TEXT}


@pytest.mark.parametrize(("state", "stage"), NOT_ACTIVE)
def test_the_store_names_no_content_for_a_reference_without_a_hit(api: TestClient, state: str, stage: str) -> None:
    store = _store(api)
    media_id = _transcribed(store)
    _reference(store, media_id, state, stage)

    assert store.media_for_file(FILE) is None
