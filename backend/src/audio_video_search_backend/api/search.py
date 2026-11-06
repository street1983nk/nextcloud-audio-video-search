"""POST /search: candidates from the index, checked against SQLite.

The index is derived and may hold documents of an older revision for a moment
(between publish and retire, or after a crash until reconcile). A candidate is
admissible when its ``index_rev`` equals ``current.index_rev`` of its media item
or is exactly one below it; per media item only the highest admissible revision
counts. Each admissible media item becomes one hit per file id that points at
it. The container checks no rights: PHP rechecks every file id for the user
(plan 01-03) and takes title and path from the node, never from here.

The time of a hit is the start of the first word in the segment that matches the
term, and the segment start when no single word does (a phrase over two words,
or an older revision whose words are gone).
"""

import logging
from collections.abc import Mapping, Sequence
from typing import Annotated, Final

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from audio_video_search_backend import config
from audio_video_search_backend.api import Services, run_locked, services
from audio_video_search_backend.index.publish import MAX_TERM_CHARS, IndexHit, segments_from_words
from audio_video_search_backend.model.provenance import Level

_LOG: Final = logging.getLogger(__name__)

# How many index candidates one hit may cost: stale revisions and several
# segments of one media item are filtered out after the index answered.
CANDIDATE_FACTOR: Final = 4
# Bounds the request body; anything above MAX_TERM_CHARS is cut, not refused.
MAX_TERM_INPUT: Final = 4096

router = APIRouter()


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    term: Annotated[StrictStr, Field(max_length=MAX_TERM_INPUT)]
    limit: Annotated[StrictInt, Field(ge=1, le=50)]


def admissible(hits: Sequence[IndexHit], current_revs: Mapping[int, int | None]) -> list[IndexHit]:
    """Per media item the best hit of the highest admissible revision, best score first."""
    best: dict[int, IndexHit] = {}
    for hit in hits:
        current = current_revs.get(hit.media_id)
        if current is None or hit.index_rev not in (current, current - 1):
            continue
        kept = best.get(hit.media_id)
        if kept is None or (hit.index_rev, hit.score) > (kept.index_rev, kept.score):
            best[hit.media_id] = hit
    return sorted(best.values(), key=lambda h: -h.score)


def _search(opened: Services, term: str, limit: int) -> list[dict[str, object]]:
    store, index = opened.store, opened.index
    candidates = index.search(term, limit * CANDIDATE_FACTOR)
    currents = {hit.media_id: store.current(hit.media_id) for hit in candidates}
    revs = {media_id: (row.index_rev if row is not None else None) for media_id, row in currents.items()}
    hits: list[dict[str, object]] = []
    seen: set[int] = set()
    for hit in admissible(candidates, revs):
        current = currents[hit.media_id]
        if current is None:
            continue
        start_ms = hit.start_ms
        if hit.index_rev == current.index_rev:
            words = store.effective_words(hit.media_id)
            segments = segments_from_words(words)
            if hit.seg_idx < len(segments):
                segment = segments[hit.seg_idx]
                inside = [w for w in words if segment.start_ms <= w.start_ms <= segment.end_ms]
                matched = index.first_match_ms(term, inside)
                start_ms = segment.start_ms if matched is None else matched
        for file_id in store.file_ids_for_media(hit.media_id):
            if file_id in seen:
                continue
            seen.add(file_id)
            hits.append(
                {"fileId": file_id, "startMs": start_ms, "excerpt": hit.text, "sample": current.level == Level.SAMPLE}
            )
            if len(hits) >= limit:
                return hits
    return hits


@router.post("/search")
async def search(body: SearchRequest, opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    term = body.term[:MAX_TERM_CHARS].strip()
    hits = await run_locked(opened, lambda: _search(opened, term, body.limit)) if term else []
    _LOG.debug("search answered", extra={"hits": len(hits), "limit": body.limit})
    return {"appVersion": config.app_version(), "hits": hits}
