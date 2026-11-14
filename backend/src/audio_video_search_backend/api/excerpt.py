"""POST /excerpt: the effective text of one file at one point in time.

The text comes from SQLite and never from the index: machine words of the
current version with the user corrections laid over (store.effective_words).
The answer is the segment that contains ``atMs``, otherwise the next one after
it, otherwise the last one.

Plan 03-14 (D-03-13, UI-SPEC A1 to A13): beside the text the answer names the
stage of the version, whether the file is still in work (``partial``), whether
``atMs`` lies behind the last finished piece (``pendingHere``, then without
text), the reason code of the preview job and, for too_long only, the limit of
the instance in hours (``limitHours``, a setting, never a property of the
file). All of it only under the leak rule (D-02-15c, D-03-13): what a file may
show comes from store.media_for_file and store.preview_view, which both name
nothing for an unreadable, vanished or trashed reference. Such a file, an
excluded one and one never seen get exactly ``{"known": false}``.
"""

from typing import Annotated, Final

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from audio_video_search_backend.api import MAX_AT_MS, Services, run_locked, services
from audio_video_search_backend.api.search import stage_of
from audio_video_search_backend.index.publish import Segment, segments_from_words
from audio_video_search_backend.store.repo import PREVIEW_REASONS

router = APIRouter()

# A job in these states may still add pieces; with a finished piece its text is partial.
_IN_WORK: Final = frozenset({"queued", "running", "waiting"})
_TOO_LONG: Final = "too_long"
_NOT_KNOWN: Final[dict[str, object]] = {"known": False}


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


def _excerpt(opened: Services, file_id: int, at_ms: int) -> dict[str, object]:
    store = opened.store
    view = store.preview_view(file_id)
    media_id = store.media_for_file(file_id)
    current = None if media_id is None else store.current(media_id)
    if view is None and current is None:
        # Not active, excluded, never seen, or an active reference with
        # neither a job nor a version: one answer for all of them.
        return dict(_NOT_KNOWN)

    partial = view is not None and view.state in _IN_WORK and view.chunks_done > 0
    pending_here = partial and view is not None and at_ms >= view.next_start_ms
    text = None
    if current is not None and media_id is not None and not pending_here:
        segment = segment_at(segments_from_words(store.effective_words(media_id)), at_ms)
        text = None if segment is None else segment.text
    # Only a code of the closed list leaves the container, never a raw one.
    reason = view.reason if view is not None and view.reason in PREVIEW_REASONS else None
    answer: dict[str, object] = {
        "known": True,
        "excerpt": text,
        "stage": None if current is None else stage_of(current.level),
        "partial": partial,
        "pendingHere": pending_here,
        "reason": reason,
    }
    if reason == _TOO_LONG:
        answer["limitHours"] = store.max_duration_hours()
    return answer


@router.post("/excerpt")
async def excerpt(body: ExcerptRequest, opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    return await run_locked(opened, lambda: _excerpt(opened, body.fileId, body.atMs))
