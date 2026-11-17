"""POST /export and /export/meta: the subtitle draft and the transcript of one file (plan 04-09).

Contract with ExAppService::export/exportMeta (plan 04-10): a file that may
give a hit and has words gets ``{known, partial, untilMs, language[, body]}``,
everything else gets exactly ``{"known": false}``, byte for byte the same as a
file id never seen (leak rule, X4, T-04-24). While the file is still in work
the export is allowed and names the end of the last finished piece (D-04-17).
The language is de, en or fr, never ``und``: a file of the stock without one
gets it determined outside the store lock and stored once (D-04-15). Cue
building and formatting run outside the store lock (T-04-26).

Measured at the routes themselves, with the real app and a real state.db;
the job states are made with the public methods of the store, like the worker.
"""

import threading
from collections.abc import Iterator, Sequence

import httpx
import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend import file_language, main
from audio_video_search_backend.api import Services
from audio_video_search_backend.api import export as export_api
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.store.repo import ChunkCounters, Store
from audio_video_search_backend.subtitles.cues import Cue
from tests.conftest import signed_headers
from tests.test_excerpt_states import (
    CHUNK_END,
    FILE,
    MODEL,
    SHA,
    SPOKEN,
    UNKNOWN,
    _keyed,
    _prepare,
    _reference,
    _row,
    _running,
    _transcribed,
)

UNKNOWN_BODY = b'{"known":false}'
FORMATS = ("srt", "vtt", "txt")


@pytest.fixture
def api() -> Iterator[TestClient]:
    with TestClient(main.APP) as client:
        yield client


@pytest.fixture
def detected(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """detect answers "de" and counts its calls; the real identifier is tested in test_file_language.py."""
    calls: list[int] = []

    def fake(words: Sequence[Word]) -> str | None:
        calls.append(len(words))
        return "de"

    monkeypatch.setattr(file_language, "detect", fake)
    return calls


def _services(client: TestClient) -> Services:
    return client.app.state.services  # pyright: ignore[reportAttributeAccessIssue]


def _store(client: TestClient) -> Store:
    return _services(client).store


def _export(client: TestClient, file_id: int = FILE, fmt: str = "vtt") -> httpx.Response:
    return client.post("/export", headers=signed_headers(), json={"fileId": file_id, "format": fmt})


def _meta(client: TestClient, file_id: int = FILE) -> httpx.Response:
    return client.post("/export/meta", headers=signed_headers(), json={"fileId": file_id})


def _publish(store: Store, media_id: int, words: list[Word]) -> None:
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
    assert store.publish_version(media_id, prov, words).published


def _same(one: httpx.Response, other: httpx.Response) -> bool:
    """Status, body and the headers that describe the body; nothing tells the two apart."""
    return (one.status_code, one.content, one.headers.get("content-type"), one.headers.get("content-length")) == (
        other.status_code,
        other.content,
        other.headers.get("content-type"),
        other.headers.get("content-length"),
    )


# -- the whole transcript ----------------------------------------------------


def _finished(store: Store) -> int:
    media_id = _transcribed(store)
    _reference(store, media_id, "active", "keyed")
    return media_id


@pytest.mark.usefixtures("detected")
def test_a_finished_german_transcript_is_exported_as_vtt(api: TestClient) -> None:
    _finished(_store(api))

    answer = _export(api, fmt="vtt").json()

    assert answer["known"] is True
    assert answer["partial"] is False
    assert answer["untilMs"] == 0
    assert answer["language"] == "de"
    assert answer["body"].startswith("WEBVTT\n\n")
    assert SPOKEN in answer["body"]
    assert set(answer) == {"known", "partial", "untilMs", "language", "body"}


@pytest.mark.usefixtures("detected")
def test_srt_starts_with_cue_one_and_txt_carries_the_words(api: TestClient) -> None:
    _finished(_store(api))

    srt = _export(api, fmt="srt").json()["body"]
    txt = _export(api, fmt="txt").json()["body"]

    assert srt.startswith("1\n00:00:00,000 --> ")
    assert txt == f"Das {SPOKEN}\n"


@pytest.mark.usefixtures("detected")
def test_meta_names_the_same_state_without_any_text(api: TestClient) -> None:
    _finished(_store(api))

    answer = _meta(api)

    assert answer.json() == {"known": True, "partial": False, "untilMs": 0, "language": "de"}
    assert SPOKEN.encode() not in answer.content


# -- D-04-17: export while the file is still in work -------------------------


def _running_with_piece(store: Store, *, words_de: int = 0) -> None:
    media_id = _keyed(store)
    job = _running(store, media_id)
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
    counters = ChunkCounters(
        kept_words=2, drop_script=0, drop_language=0, drop_conf=0, speech_ms=900, words_de=words_de
    )
    assert store.commit_chunk(job, prov=prov, words=words, next_start_ms=CHUNK_END, counters=counters)


@pytest.mark.parametrize("fmt", FORMATS)
def test_a_running_file_is_exported_up_to_its_last_finished_piece(
    api: TestClient, detected: list[int], fmt: str
) -> None:
    _running_with_piece(_store(api), words_de=2)

    answer = _export(api, fmt=fmt).json()

    assert answer["known"] is True
    assert answer["partial"] is True
    assert answer["untilMs"] == CHUNK_END
    # The counters of the running job name the language; nothing is detected.
    assert answer["language"] == "de"
    assert detected == []
    assert SPOKEN in answer["body"]
    assert _meta(api).json() == {"known": True, "partial": True, "untilMs": CHUNK_END, "language": "de"}


@pytest.mark.usefixtures("detected")
def test_a_finished_job_is_no_longer_partial(api: TestClient) -> None:
    _prepare(_store(api), "complete")

    assert _meta(api).json() == {"known": True, "partial": False, "untilMs": 0, "language": "de"}


# -- D-04-15: the language of the stock --------------------------------------


def test_a_file_of_the_stock_gets_its_language_once(api: TestClient, detected: list[int]) -> None:
    store = _store(api)
    media_id = _finished(store)
    assert store.file_language(media_id) is None

    first = _export(api).json()
    assert first["language"] == "de"
    assert detected == [2]
    assert store.file_language(media_id) == "de"

    second = _meta(api).json()
    assert second["language"] == "de"
    assert detected == [2]


def test_the_first_stored_language_wins_over_a_later_detection(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(api)
    media_id = _finished(store)

    def racing(words: Sequence[Word]) -> str | None:
        # Another request stored its answer while this one was detecting.
        store.set_file_language(media_id, "fr")
        return "en"

    monkeypatch.setattr(file_language, "detect", racing)

    assert _meta(api).json()["language"] == "fr"
    assert store.file_language(media_id) == "fr"


@pytest.mark.parametrize("route", ["export", "meta"])
def test_without_a_language_the_file_is_not_known(api: TestClient, monkeypatch: pytest.MonkeyPatch, route: str) -> None:
    store = _store(api)
    media_id = _finished(store)
    monkeypatch.setattr(file_language, "detect", lambda words: None)

    answer = _export(api) if route == "export" else _meta(api)

    assert answer.content == UNKNOWN_BODY
    assert store.file_language(media_id) is None
    assert b"und" not in answer.content


# -- leak rule: five cases, one answer ---------------------------------------


def _unknown_file(store: Store) -> int:
    _finished(store)
    return UNKNOWN


def _excluded(store: Store) -> int:
    _finished(store)
    store.apply_intake([_row("exclude", 7, versioned=False)])
    assert store.file_ref(FILE) is None
    return FILE


def _not_active(store: Store) -> int:
    media_id = _transcribed(store)
    _reference(store, media_id, "unreadable", "failed")
    return FILE


def _without_current(store: Store) -> int:
    _prepare(store, "queued")
    return FILE


def _without_words(store: Store) -> int:
    media_id = store.media_for_file_sha256(SHA)
    _publish(store, media_id, [])
    _reference(store, media_id, "active", "keyed")
    assert store.current(media_id) is not None
    return FILE


def _blank_words(store: Store) -> int:
    # Words whose surfaces hold nothing visible: there is no text to export.
    media_id = store.media_for_file_sha256(SHA)
    _publish(store, media_id, [Word(0, 300, " ", "", 0.9, "machine"), Word(400, 700, "\u0007\t", "", 0.9, "machine")])
    _reference(store, media_id, "active", "keyed")
    store.set_file_language(media_id, "de")
    return FILE


LEAK_CASES = {
    "unknown": _unknown_file,
    "excluded": _excluded,
    "not_active": _not_active,
    "without_current": _without_current,
    "without_words": _without_words,
    "blank_words": _blank_words,
}


@pytest.mark.usefixtures("detected")
@pytest.mark.parametrize("case", sorted(LEAK_CASES))
def test_every_file_without_an_export_gets_the_same_bytes(api: TestClient, case: str) -> None:
    file_id = LEAK_CASES[case](_store(api))

    for fmt in FORMATS:
        answer = _export(api, file_id, fmt)
        assert answer.status_code == 200
        assert answer.content == UNKNOWN_BODY
        assert _same(answer, _export(api, 12345, fmt))
    meta = _meta(api, file_id)
    assert meta.content == UNKNOWN_BODY
    assert _same(meta, _meta(api, 12345))


@pytest.mark.usefixtures("detected")
def test_the_leak_cases_have_a_positive_control(api: TestClient) -> None:
    # Through the active reference the same content does give its text.
    _finished(_store(api))
    assert _export(api).content != UNKNOWN_BODY
    assert _meta(api).content != UNKNOWN_BODY


# -- the request is checked before the store ---------------------------------


BAD_BODIES = [
    {"fileId": FILE, "format": "docx"},
    {"fileId": FILE, "format": "VTT"},
    {"fileId": 0, "format": "vtt"},
    {"fileId": -3, "format": "vtt"},
    {"fileId": str(FILE), "format": "vtt"},
    {"fileId": True, "format": "vtt"},
    {"format": "vtt"},
]


@pytest.mark.parametrize("body", BAD_BODIES)
def test_a_bad_export_request_is_refused_before_the_store(
    api: TestClient, monkeypatch: pytest.MonkeyPatch, body: dict[str, object]
) -> None:
    store = _store(api)

    def forbidden(file_id: int) -> None:
        raise AssertionError("the store was asked")

    monkeypatch.setattr(store, "media_for_file", forbidden)
    monkeypatch.setattr(store, "preview_view", forbidden)

    assert api.post("/export", headers=signed_headers(), json=body).status_code == 422


@pytest.mark.parametrize("file_id", [0, -1, "42", None])
def test_a_bad_meta_request_is_refused(api: TestClient, file_id: object) -> None:
    assert api.post("/export/meta", headers=signed_headers(), json={"fileId": file_id}).status_code == 422


def test_unsigned_requests_never_reach_the_routes(api: TestClient) -> None:
    assert api.post("/export", json={"fileId": FILE, "format": "vtt"}).status_code == 401
    assert api.post("/export/meta", json={"fileId": FILE}).status_code == 401


# -- T-04-26: the store lock is free while the cues are built ----------------


@pytest.mark.usefixtures("detected")
def test_the_store_lock_is_free_while_the_cues_are_built(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _finished(_store(api))
    opened = _services(api)
    real = export_api.build_cues
    seen: list[bool] = []

    def waiting(words: Sequence[Word]) -> list[Cue]:
        done = threading.Event()

        def other_request() -> None:
            with opened.lock:  # what run_locked takes for a parallel request
                done.set()

        threading.Thread(target=other_request, daemon=True).start()
        seen.append(done.wait(timeout=5))
        return real(words)

    monkeypatch.setattr(export_api, "build_cues", waiting)

    answer = _export(api, fmt="srt").json()

    assert seen == [True]
    assert answer["known"] is True


def test_the_language_is_detected_outside_the_store_lock(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _finished(_store(api))
    opened = _services(api)
    free: list[bool] = []

    def probing(words: Sequence[Word]) -> str | None:
        took = opened.lock.acquire(timeout=5)
        free.append(took)
        if took:
            opened.lock.release()
        return "en"

    monkeypatch.setattr(file_language, "detect", probing)

    assert _meta(api).json()["language"] == "en"
    assert free == [True]


def test_no_text_and_no_language_reaches_the_log(
    api: TestClient, caplog: pytest.LogCaptureFixture, detected: list[int]
) -> None:
    _finished(_store(api))
    caplog.set_level("DEBUG")

    for fmt in FORMATS:
        _export(api, fmt=fmt)
    _meta(api)

    for record in caplog.records:
        assert SPOKEN not in record.getMessage()
        assert SPOKEN not in str(record.__dict__)
