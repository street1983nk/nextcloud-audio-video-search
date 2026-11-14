"""POST /reconcile/run: one round of the reconcile at once (plan 02-20).

ADMIN in appinfo/info.xml, reached through occ audio_video_search:reconcile
[--reprove] (ExAppService::reconcileNow, plan 02-19). Body ``{"reprove":
bool}``; the round runs sweep, proof planning and walk whatever their stamps
say, after a round of the loop that may be running. The answer is the closed
set of counters ExAppService::RECONCILE_KEYS checks, in that order.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictBool

from audio_video_search_backend.api import Services, services
from audio_video_search_backend.worker.reconcile import Reconciler

router = APIRouter()


class RunRequest(BaseModel):
    # Like every route of the contract: a field this version does not know is ignored.
    model_config = ConfigDict(extra="ignore")

    reprove: StrictBool


def reconciler(request: Request) -> Reconciler:
    """The reconcile of the running application; 503 while the lifespan has not built it."""
    running = getattr(request.app.state, "reconciler", None)
    if not isinstance(running, Reconciler):
        raise HTTPException(status_code=503, detail="not ready")
    return running


@router.post("/reconcile/run")
async def run(
    body: RunRequest,
    _opened: Annotated[Services, Depends(services)],
    running: Annotated[Reconciler, Depends(reconciler)],
) -> dict[str, int | str | None]:
    result = await running.run_once(reprove=body.reprove, force=True)
    return result.as_wire()
