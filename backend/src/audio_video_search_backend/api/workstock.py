"""GET /workstock: one page of the work stock for occ audio_video_search:files.

ADMIN in appinfo/info.xml. Query: ``state`` (one code of the closed list or
absent), ``after`` (the file id the page starts behind, default 0), ``limit``
(1 to 1000, default 1000); anything else is answered 422 by the validation.
The answer is ``{"files": [{"fileId", "mediaId", "storageId", "state",
"stage", "reason"}], "next": int | null}``: ids and codes only, never a path
or a user.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from audio_video_search_backend.api import Services, run_locked, services
from audio_video_search_backend.store import coverage as counting

# The closed list of repo.STATES, spelled out so the validation answers 422;
# tests/test_api_routes.py holds both lists equal.
type WorkstockState = Literal["active", "unreadable", "vanished", "trashed"]

router = APIRouter()


@router.get("/workstock")
async def workstock(
    opened: Annotated[Services, Depends(services)],
    state: Annotated[WorkstockState | None, Query()] = None,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=counting.WORKSTOCK_MAX_LIMIT)] = counting.WORKSTOCK_MAX_LIMIT,
) -> dict[str, object]:
    page = await run_locked(opened, lambda: counting.workstock(opened.store.reading_connection(), state, after, limit))
    return page.as_wire()
