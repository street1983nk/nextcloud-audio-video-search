"""POST /excerpt: the effective text of one file at one point in time.

The text comes from SQLite and never from the index: machine words of the
current version with the user corrections laid over (store.effective_words).
The answer is the segment that contains ``atMs``, otherwise the next one after
it, otherwise the last one. A file without a current version is unknown.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from audio_video_search_backend.api import MAX_AT_MS, Services, run_locked, services
from audio_video_search_backend.index.publish import Segment, segments_from_words

router = APIRouter()


class ExcerptRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fileId: Annotated[StrictInt, Field(gt=0)]  # the wire name of the contract
    atMs: Annotated[StrictInt, Field(ge=0, le=MAX_AT_MS)]


def segment_at(segments: list[Segment], at_ms: int) -> Segment | None:
    """The segment that contains ``at_ms``, else the next one, else the last one."""
    for segment in segments:
        if segment.end_ms >= at_ms:
            return segment
    return segments[-1] if segments else None


def _excerpt(opened: Services, file_id: int, at_ms: int) -> str | None:
    store = opened.store
    media_id = store.media_for_file(file_id)
    if media_id is None or store.current(media_id) is None:
        return None
    segment = segment_at(segments_from_words(store.effective_words(media_id)), at_ms)
    return None if segment is None else segment.text


@router.post("/excerpt")
async def excerpt(body: ExcerptRequest, opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    text = await run_locked(opened, lambda: _excerpt(opened, body.fileId, body.atMs))
    return {"known": text is not None, "excerpt": text}
