"""POST /excerpt gives text only for a reference that may give a hit (plan 02-15c, D-02-01a third addendum).

The playback page asks ``isReadable()`` before it asks for the excerpt, and an
SMB server that denies a file lets that say yes (Findling measurement A6). So
the container itself must not hand out the text of a transcript for a
reference whose read proof failed or is owed (unreadable), that lies in the
trash (trashed) or whose storage is gone (vanished): for every one of them the
route answers exactly as for a file id it has never seen.

Measured at the route itself, with the real app and a real state.db.

Plan 03-14 (D-03-13, UI-SPEC A1 to A13): for an active reference the route
also names the stage, whether the file is still in work (partial), whether the
asked point lies behind the last finished piece (pendingHere), the reason of
the job and, for too_long, the limit of the instance in hours. Every other
file is answered with exactly ``{"known": false}``, byte for byte the same.
The job states are made with the public methods of the store, the way the
worker makes them; every expected answer is written out by hand.
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
from audio_video_search_backend.store.repo import ChunkCounters, IntakeItem, PreviewJob, Store
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

WHOLE_TEXT = {
    "known": True,
    "excerpt": f"Das {SPOKEN}",
    "stage": "preview",
    "partial": False,
    "pendingHere": False,
    "reason": None,
}
UNKNOWN_BODY = b'{"known":false}'


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
    assert unknown.json() == {"known": False}
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
    assert answer.json() == WHOLE_TEXT


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

    assert _excerpt(api).json() == WHOLE_TEXT


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

    # A sample without a real transcript: stage sample, otherwise as before (plan 03-14).
    assert _excerpt(api).json() == {
        "known": True,
        "excerpt": sample_api.SAMPLE_TEXT,
        "stage": "sample",
        "partial": False,
        "pendingHere": False,
        "reason": None,
    }


@pytest.mark.parametrize(("state", "stage"), NOT_ACTIVE)
def test_the_store_names_no_content_for_a_reference_without_a_hit(api: TestClient, state: str, stage: str) -> None:
    store = _store(api)
    media_id = _transcribed(store)
    _reference(store, media_id, state, stage)

    assert store.media_for_file(FILE) is None


# -- plan 03-14: the states of the excerpt block (UI-SPEC A1 to A13) ----------------

CHUNK_END = 600_000
NO_COUNT = ChunkCounters(kept_words=0, drop_script=0, drop_language=0, drop_conf=0, speech_ms=0)
TEXTLESS = ("no_speech", "unsupported_language")
SKIPPED = ("damaged", "protected", "engine_failed", "no_audio", "format_unsupported", "too_long")


def _keyed(store: Store, file_id: int = FILE) -> int:
    """Take the file in, capture and key it like the worker; the store seeds its preview job (queued)."""
    item = IntakeItem(
        queue_id=file_id,
        kind="content",
        file_id=file_id,
        storage_id=3,
        etag="e1",
        size=1000,
        mtime=1_700_000_000,
        prefilter_key=None,
        reader_uid="ana",
    )
    store.apply_intake([item])
    claimed = store.next_capture(NOW)
    assert claimed is not None
    media_id = store.mark_keyed(claimed, SHA, HEAD, NOW)
    assert media_id is not None
    return media_id


def _running(store: Store, media_id: int) -> PreviewJob:
    job = store.next_preview(NOW)
    assert job is not None
    assert job.media_id == media_id
    return job


def _first_piece(store: Store, job: PreviewJob) -> None:
    """One piece of ten minutes with the secret word in it (the preview version becomes current)."""
    prov = Provenance(
        engine="parakeet",
        model_sha256=MODEL,
        config_version=1,
        profile="balanced",
        level=Level.PREVIEW,
        epoch=job.epoch,
        language="de",
        input_file_sha256=SHA,
    )
    words = [Word(299_000, 299_350, "Das", "das", 0.9, "machine"), Word(299_400, 299_900, SPOKEN, "x", 0.9, "machine")]
    assert store.commit_chunk(job, prov=prov, words=words, next_start_ms=CHUNK_END, counters=NO_COUNT)


def _settle(store: Store, job: PreviewJob, reason: str) -> None:
    """Give the job its reason through the method the worker uses for it."""
    if reason in TEXTLESS:
        assert store.finish_preview(job, reason, now=NOW)
    elif reason == "disk_full":
        assert store.defer_preview(job, reason, retry_at=NOW + 3600, now=NOW)
    else:
        assert store.skip_preview(job, reason, None, now=NOW)


def _prepare(store: Store, case: str) -> int:
    """Bring the content of FILE (one active, keyed reference) into the named job state."""
    media_id = _keyed(store)
    if case == "queued":
        return media_id
    job = _running(store, media_id)
    if case in ("complete", "running", "piece_then_yield", "piece_then_disk_full", "piece_then_engine_failed"):
        _first_piece(store, job)
    if case == "complete":
        assert store.finish_preview(job, "transcript", now=NOW)
    elif case == "piece_then_yield":
        assert store.yield_preview(job, now=NOW)
    elif case == "piece_then_disk_full":
        _settle(store, job, "disk_full")
    elif case == "piece_then_engine_failed":
        _settle(store, job, "engine_failed")
    elif case not in ("running", "running_no_piece"):
        _settle(store, job, case)
    return media_id


def _answer(
    excerpt: str | None,
    stage: str | None,
    *,
    partial: bool = False,
    pending: bool = False,
    reason: str | None = None,
    **more: object,
) -> dict[str, object]:
    return {
        "known": True,
        "excerpt": excerpt,
        "stage": stage,
        "partial": partial,
        "pendingHere": pending,
        "reason": reason,
    } | more


TEXT = f"Das {SPOKEN}"
CASES = [
    # A1: the preview of a finished file, the word at atMs.
    ("complete", 300_000, _answer(TEXT, "preview")),
    ("complete", 900_000, _answer(TEXT, "preview")),
    # A2: text of the first piece while the file is still in work.
    ("running", 300_000, _answer(TEXT, "preview", partial=True)),
    ("running", CHUNK_END - 1, _answer(TEXT, "preview", partial=True)),
    # A4: the point lies behind the last finished piece; no text from another place.
    ("running", CHUNK_END, _answer(None, "preview", partial=True, pending=True)),
    ("running", 900_000, _answer(None, "preview", partial=True, pending=True)),
    ("piece_then_yield", 900_000, _answer(None, "preview", partial=True, pending=True)),
    ("piece_then_yield", 300_000, _answer(TEXT, "preview", partial=True)),
    # A5: queued or running without any finished piece and without a version.
    ("queued", 0, _answer(None, None)),
    ("running_no_piece", 0, _answer(None, None)),
    # A6 to A9, A11: the reason of the whole file, the same at every point.
    ("no_speech", 0, _answer(None, None, reason="no_speech")),
    ("no_speech", 900_000, _answer(None, None, reason="no_speech")),
    ("unsupported_language", 0, _answer(None, None, reason="unsupported_language")),
    ("damaged", 0, _answer(None, None, reason="damaged")),
    ("protected", 0, _answer(None, None, reason="protected")),
    ("engine_failed", 0, _answer(None, None, reason="engine_failed")),
    ("no_audio", 0, _answer(None, None, reason="no_audio")),
    ("format_unsupported", 0, _answer(None, None, reason="format_unsupported")),
    # A10: too long, with the limit the instance has set (default 12 hours).
    ("too_long", 0, _answer(None, None, reason="too_long", limitHours=12)),
    # A13: waits for room on the disk; with a finished piece the text of it stays.
    ("disk_full", 0, _answer(None, None, reason="disk_full")),
    ("piece_then_disk_full", 300_000, _answer(TEXT, "preview", partial=True, reason="disk_full")),
    ("piece_then_disk_full", 900_000, _answer(None, "preview", partial=True, pending=True, reason="disk_full")),
    # Skipped after a finished piece: nothing is in work any more, the text of the piece stays.
    ("piece_then_engine_failed", 300_000, _answer(TEXT, "preview", reason="engine_failed")),
    ("piece_then_engine_failed", 900_000, _answer(TEXT, "preview", reason="engine_failed")),
]


@pytest.mark.parametrize(("case", "at_ms", "expected"), CASES)
def test_an_active_reference_gets_stage_progress_and_reason(
    api: TestClient, case: str, at_ms: int, expected: dict[str, object]
) -> None:
    store = _store(api)
    _prepare(store, case)

    answer = _excerpt(api, at_ms=at_ms)

    assert answer.status_code == 200
    assert answer.json() == expected


def test_every_reason_of_the_store_has_a_case() -> None:
    # A new reason must be decided here before it reaches the play page.
    assert set(TEXTLESS) | set(SKIPPED) | {"disk_full"} == repo.PREVIEW_REASONS
    assert {case for case, _at, _expected in CASES} >= repo.PREVIEW_REASONS


@pytest.mark.parametrize("hours", [1, 30])
def test_the_limit_of_too_long_follows_the_setting_of_the_instance(api: TestClient, hours: int) -> None:
    store = _store(api)
    _prepare(store, "too_long")
    store.set_max_duration_hours(hours)

    assert _excerpt(api).json() == _answer(None, None, reason="too_long", limitHours=hours)


def test_the_excerpt_takes_the_stage_from_the_search() -> None:
    # One mapping of level to stage for search and excerpt, never a copy.
    from audio_video_search_backend.api import excerpt as excerpt_api
    from audio_video_search_backend.api import search as search_api

    assert excerpt_api.stage_of is search_api.stage_of


def test_an_unknown_file_gets_known_false_and_nothing_else(api: TestClient) -> None:
    _prepare(_store(api), "no_speech")

    answer = _excerpt(api, UNKNOWN)

    assert answer.status_code == 200
    assert answer.content == UNKNOWN_BODY


LEAK_CASES = ["complete", "running", "no_speech", "too_long", "disk_full", "piece_then_disk_full"]


@pytest.mark.parametrize("case", LEAK_CASES)
@pytest.mark.parametrize(("state", "stage"), NOT_ACTIVE)
def test_a_reference_without_a_hit_hides_text_stage_and_reason_byte_for_byte(
    api: TestClient, case: str, state: str, stage: str
) -> None:
    store = _store(api)
    media_id = _prepare(store, case)
    at_ms = 300_000
    # Positive control: through the active reference the answer does carry what must not get out.
    shown = _excerpt(api, at_ms=at_ms)
    assert shown.json()["known"] is True
    assert shown.content != UNKNOWN_BODY

    _reference(store, media_id, state, stage)

    answer = _excerpt(api, at_ms=at_ms)
    unknown = _excerpt(api, UNKNOWN, at_ms=at_ms)
    assert unknown.content == UNKNOWN_BODY
    assert answer.content == unknown.content
    assert _same_answer(answer, unknown)
    for secret in (SPOKEN, "preview", "partial", "pendingHere", "reason", "limitHours", case):
        assert secret.encode() not in answer.content


def test_an_excluded_file_with_a_reason_is_answered_like_one_never_seen(api: TestClient) -> None:
    store = _store(api)
    _prepare(store, "no_speech")
    assert _excerpt(api).json()["reason"] == "no_speech"

    store.apply_intake([_row("exclude", 7, versioned=False)])

    assert store.file_ref(FILE) is None
    assert _excerpt(api).content == UNKNOWN_BODY
    assert _same_answer(_excerpt(api), _excerpt(api, UNKNOWN))


def test_a_code_outside_the_closed_list_never_leaves_the_container(api: TestClient) -> None:
    # The store checks every code it writes; a row changed by hand still names no raw code.
    store = _store(api)
    media_id = _prepare(store, "damaged")
    assert _excerpt(api).json()["reason"] == "damaged"
    raw = "ffmpeg_exit_183_codec_xyz"
    store.reading_connection().execute("UPDATE preview_job SET reason = ? WHERE media_id = ?", (raw, media_id))

    answer = _excerpt(api)

    assert raw.encode() not in answer.content
    assert answer.json() == _answer(None, None)


def test_an_active_reference_with_a_version_but_without_a_job_keeps_its_text(api: TestClient) -> None:
    # Open point of plan 03-09, decided here: preview_view gives None for an
    # active reference without a job, but media_for_file is the gate of the
    # leak rule and lets this reference through; its text is what it was
    # before plan 03-14, with nothing in work and no reason.
    store = _store(api)
    media_id = _transcribed(store)
    _reference(store, media_id, "active", "keyed")
    assert store.preview_view(FILE) is None

    assert _excerpt(api).json() == WHOLE_TEXT


def test_an_active_reference_without_a_job_and_without_a_version_is_not_known(api: TestClient) -> None:
    store = _store(api)
    media_id = store.media_for_file_sha256(SHA)
    _reference(store, media_id, "active", "keyed")
    assert store.preview_view(FILE) is None

    assert _excerpt(api).content == UNKNOWN_BODY
