"""POST /sample and /sample/remove: the test result of the walking skeleton.

The seed takes the real way, so the walking skeleton proves it: the bytes of the
file come through the content gateway of the PHP app as a stream and are hashed
on the fly (nc.fetch_file_sha256), the hash finds or creates the media item, and
the transcript is published through the conditional publish of the store with
``engine="sample"`` and ``Level.SAMPLE``. A real transcript (level 100 and up)
always wins over it; a second seed of the same content is ``stale_rejected``.

The remove route takes a sample out of SQLite (Store.remove_sample) and every
index document of its media item; a real transcript is answered with
``not_sample`` and left alone.

Without the PHP app there is no gateway and no search to seed for, so /sample
answers ``companion_missing`` before it touches the gateway (companion.py). An
unknown state is asked once first; only a confirmed absence refuses, an
unreachable instance is left to the gateway to report.

Both routes are ADMIN in appinfo/info.xml and only reached through occ.
"""

import logging
from typing import Annotated, Final

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from audio_video_search_backend import companion, nc
from audio_video_search_backend.api import MAX_AT_MS, MAX_UID_LENGTH, Services, run_locked, services
from audio_video_search_backend.index.publish import segments_from_words
from audio_video_search_backend.model.overlay import Word, normalize
from audio_video_search_backend.model.provenance import SAMPLE_MODEL_SHA256, Level, Provenance

_LOG: Final = logging.getLogger(__name__)

# The text of the test result (German). Fixed, never user content.
SAMPLE_TEXT: Final = "Dies ist ein Testtreffer für die Audiosuche in Audio und Video"
SAMPLE_WORD_STEP_MS: Final = 400
SAMPLE_WORD_LENGTH_MS: Final = 350
# The answer while the PHP app is not there: nothing to work for, no gateway.
COMPANION_MISSING: Final = "companion_missing"
# Upper bound of one streamed read; stops an endless answer of the gateway.
MAX_SAMPLE_BYTES: Final = 8 * 1024**3

router = APIRouter()


class SampleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fileId: Annotated[StrictInt, Field(gt=0)]  # the wire name of the contract
    userId: Annotated[StrictStr, Field(min_length=1, max_length=MAX_UID_LENGTH)]
    atMs: Annotated[StrictInt, Field(ge=0, le=MAX_AT_MS)]


class RemoveRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fileId: Annotated[StrictInt, Field(gt=0)]


def sample_words(at_ms: int) -> list[Word]:
    """The words of the test result from ``at_ms`` on, whole milliseconds."""
    return [
        Word(
            start_ms=at_ms + i * SAMPLE_WORD_STEP_MS,
            end_ms=at_ms + i * SAMPLE_WORD_STEP_MS + SAMPLE_WORD_LENGTH_MS,
            surface=surface,
            norm=normalize(surface),
            conf=1.0,
            src="machine",
        )
        for i, surface in enumerate(SAMPLE_TEXT.split())
    ]


def _seed(opened: Services, file_id: int, sha256: str, size: int, at_ms: int) -> dict[str, object]:
    store, index = opened.store, opened.index
    media_id = store.media_for_file_sha256(sha256)
    store.upsert_file_ref(
        file_id, media_id, storage_id=0, etag="", size=size, mtime=0, state="sample", stage="keyed", reason="sample"
    )
    prov = Provenance(
        engine="sample",
        model_sha256=SAMPLE_MODEL_SHA256,
        config_version=1,
        profile="debug",
        level=Level.SAMPLE,
        # The epoch of the media item, not of the current row: after an epoch
        # bump the current row is older and a seed with its epoch would be stale.
        epoch=store.media_epoch(media_id),
        language="de",
        input_file_sha256=sha256,
    )
    result = store.publish_version(media_id, prov, sample_words(at_ms))
    if not result.published:
        if result.reason != "stale_rejected":
            raise RuntimeError(f"sample not published: {result.reason}")
        return {"result": "stale_rejected", "mediaId": media_id, "indexRev": None}
    if result.index_rev is None:
        raise RuntimeError("published without an index revision")
    index.publish(media_id, result.index_rev, segments_from_words(store.effective_words(media_id)))
    index.retire(media_id, keep_rev=result.index_rev)
    store.mark_indexed(media_id, result.index_rev)
    return {"result": "published", "mediaId": media_id, "indexRev": result.index_rev}


@router.post("/sample")
async def sample(body: SampleRequest, opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    state = companion.current()
    if state.state == companion.UNKNOWN:
        state = await companion.check_once()
    if state.state == companion.MISSING:
        _LOG.info("sample refused", extra={"file_id": body.fileId, "error": COMPANION_MISSING})
        return {"error": COMPANION_MISSING}
    fetched = await nc.fetch_file_sha256(body.fileId, body.userId, max_bytes=MAX_SAMPLE_BYTES)
    if fetched.error is not None or fetched.sha256 is None:
        error = fetched.error or nc.GATEWAY_FAILED
        _LOG.info("sample refused", extra={"file_id": body.fileId, "error": error})
        return {"error": error}
    sha256 = fetched.sha256
    answer = await run_locked(opened, lambda: _seed(opened, body.fileId, sha256, fetched.size, body.atMs))
    _LOG.info("sample answered", extra={"file_id": body.fileId, "result": answer["result"]})
    return answer


def _remove(opened: Services, file_id: int) -> dict[str, object]:
    status, media_id = opened.store.remove_sample(file_id)
    if status == "removed" and media_id is not None:
        opened.index.retire(media_id, keep_rev=0)
    return {"result": status, "mediaId": media_id}


@router.post("/sample/remove")
async def remove(body: RemoveRequest, opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    answer = await run_locked(opened, lambda: _remove(opened, body.fileId))
    _LOG.info("sample remove answered", extra={"file_id": body.fileId, "result": answer["result"]})
    return answer
