"""POST /search: places from the index, checked against SQLite, in a fixed tier sequence.

The index is derived and may hold documents of an older revision for a moment
(between publish and retire, or after a crash until reconcile). A candidate is
admissible when its ``index_rev`` equals ``current.index_rev`` of its media item
or is exactly one below it; per media item only the highest admissible revision
found counts, with all of its segments, so two states of one file never mix.

One place is one segment (plan 03-08, D-03-01). Each place of a media item
becomes a place of every file id that points at it. The web dialog of the
unified search asks again with a growing ``limit`` and sends no cursor, so the
places stand in a fixed sequence (``tiered``) and ``offset`` and ``limit`` cut
it: the answer for ``limit`` 10 starts with the one for ``limit`` 5. The number
of index candidates is therefore fixed too (``MAX_CANDIDATES``), never derived
from ``limit`` or ``offset``.

The container checks no rights: PHP rechecks every file id for the user and
takes title and path from the node, never from here.

The time of a place is the start of the first word in the segment that matches
the term, and the segment start when no single word does (a phrase over two
words, or an older revision whose words are gone).
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
from audio_video_search_backend.store.repo import CurrentRow

_LOG: Final = logging.getLogger(__name__)

# Index candidates per request, the same for every limit and offset; a number
# that grew with them would change the sequence between two pages.
MAX_CANDIDATES: Final = 2000
# Places of one file per tier (D-03-02).
PER_TIER: Final = 3
# The deepest offset a client may ask for (Findling MAX_CONTAINER_OFFSET).
MAX_OFFSET: Final = 1200
# Bounds the request body; anything above MAX_TERM_CHARS is cut, not refused.
MAX_TERM_INPUT: Final = 4096

router = APIRouter()

type Place = tuple[float, int, str]


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    term: Annotated[StrictStr, Field(max_length=MAX_TERM_INPUT)]
    limit: Annotated[StrictInt, Field(ge=1, le=50)]
    offset: Annotated[StrictInt, Field(ge=0, le=MAX_OFFSET)] = 0


def admissible(hits: Sequence[IndexHit], current_revs: Mapping[int, int | None]) -> list[IndexHit]:
    """Per media item every segment of the highest admissible revision found, best score first."""
    chosen: dict[int, int] = {}
    for hit in hits:
        current = current_revs.get(hit.media_id)
        if current is None or hit.index_rev not in (current, current - 1):
            continue
        chosen[hit.media_id] = max(chosen.get(hit.media_id, hit.index_rev), hit.index_rev)
    kept = [hit for hit in hits if chosen.get(hit.media_id) == hit.index_rev]
    return sorted(kept, key=lambda h: -h.score)


def tiered(stellen_by_file: Mapping[int, Sequence[Place]], per_tier: int = PER_TIER) -> list[tuple[int, int, str]]:
    """The fixed sequence: tier 1 of every file, then tier 2, files by their best place.

    ``stellen_by_file`` maps a file id to its places ``(score, start_ms, excerpt)``.
    Files sort by best score (tie: file id), places by score (tie: time).
    """
    files = sorted(stellen_by_file, key=lambda f: (-max(s[0] for s in stellen_by_file[f]), f))
    ordered = {f: sorted(stellen_by_file[f], key=lambda s: (-s[0], s[1])) for f in files}
    out: list[tuple[int, int, str]] = []
    tier = 0
    while True:
        added = False
        for f in files:
            for _score, start_ms, excerpt in ordered[f][tier * per_tier : (tier + 1) * per_tier]:
                out.append((f, start_ms, excerpt))
                added = True
        if not added:
            return out
        tier += 1


def stage_of(level: int) -> str:
    """The stage PHP shows: a sample, a preview, or a final transcript from REFINED on."""
    if level == Level.SAMPLE:
        return "sample"
    if level >= Level.REFINED:
        return "final"
    return "preview"


def _places(opened: Services, term: str, hits: Sequence[IndexHit], current: CurrentRow) -> list[Place]:
    """The places of one media item; the words are loaded once for all of its segments."""
    segments = None
    words = None
    places: list[Place] = []
    for hit in hits:
        start_ms = hit.start_ms
        if hit.index_rev == current.index_rev:
            if words is None or segments is None:
                words = opened.store.effective_words(hit.media_id)
                segments = segments_from_words(words)
            if hit.seg_idx < len(segments):
                segment = segments[hit.seg_idx]
                inside = [w for w in words if segment.start_ms <= w.start_ms <= segment.end_ms]
                matched = opened.index.first_match_ms(term, inside)
                start_ms = segment.start_ms if matched is None else matched
        places.append((hit.score, start_ms, hit.text))
    return places


def _search(opened: Services, term: str, offset: int, limit: int) -> tuple[list[dict[str, object]], bool]:
    store, index = opened.store, opened.index
    candidates = index.search(term, MAX_CANDIDATES)
    currents = {hit.media_id: store.current(hit.media_id) for hit in candidates}
    revs = {media_id: (row.index_rev if row is not None else None) for media_id, row in currents.items()}
    by_media: dict[int, list[IndexHit]] = {}
    for hit in admissible(candidates, revs):
        by_media.setdefault(hit.media_id, []).append(hit)

    # file id -> the media items that name it; a file named by two (an active
    # reference and a visible sample of other bytes) takes the one its excerpt
    # comes from (Store.media_for_file), so its places never mix two contents.
    named: dict[int, list[int]] = {}
    for media_id in sorted(by_media):
        for file_id in store.file_ids_for_media(media_id):
            named.setdefault(file_id, []).append(media_id)
    media_of_file: dict[int, int] = {}
    for file_id, media_ids in named.items():
        if len(media_ids) == 1:
            media_of_file[file_id] = media_ids[0]
        else:
            preferred = store.media_for_file(file_id)
            media_of_file[file_id] = preferred if preferred in media_ids else media_ids[0]

    places_of_media: dict[int, list[Place]] = {}
    stellen_by_file: dict[int, list[Place]] = {}
    for file_id, media_id in media_of_file.items():
        current = currents[media_id]
        if current is None:
            continue
        if media_id not in places_of_media:
            places_of_media[media_id] = _places(opened, term, by_media[media_id], current)
        stellen_by_file[file_id] = places_of_media[media_id]

    sequence = tiered(stellen_by_file)
    page = sequence[offset : offset + limit]
    hits: list[dict[str, object]] = []
    for file_id, start_ms, excerpt in page:
        current = currents[media_of_file[file_id]]
        level = Level.PREVIEW if current is None else current.level
        hits.append(
            {
                "fileId": file_id,
                "startMs": start_ms,
                "excerpt": excerpt,
                "sample": level == Level.SAMPLE,
                "stage": stage_of(level),
            }
        )
    return hits, len(sequence) > offset + limit


@router.post("/search")
async def search(body: SearchRequest, opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    term = body.term[:MAX_TERM_CHARS].strip()
    hits, has_more = (
        await run_locked(opened, lambda: _search(opened, term, body.offset, body.limit)) if term else ([], False)
    )
    _LOG.debug("search answered", extra={"hits": len(hits), "limit": body.limit, "offset": body.offset})
    return {
        "appVersion": config.app_version(),
        "hits": hits,
        "nextOffset": body.offset + len(hits),
        "hasMore": has_more,
    }
