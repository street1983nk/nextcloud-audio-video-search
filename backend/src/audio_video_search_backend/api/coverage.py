"""GET /coverage: the numbers of D-02-06 for occ audio_video_search:status.

ADMIN in appinfo/info.xml and signed like every route (AppAPIAuthMiddleware in
main.py). The answer is a fixed set of keys with numbers only:
contents, transcribed, files, byState, byStage, dueWork (store/coverage.py).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from audio_video_search_backend.api import Services, run_locked, services
from audio_video_search_backend.store import coverage as counting

router = APIRouter()


@router.get("/coverage")
async def coverage(opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    found = await run_locked(opened, lambda: counting.coverage(opened.store.reading_connection()))
    return found.as_wire()
