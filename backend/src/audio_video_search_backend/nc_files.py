"""The contract of the reconcile routes of the PHP app (plan 02-19, used by plan 02-20).

- GET  reconcile/mounts: every mount of the mount set with the flags the
  reconcile needs; ``ok`` false when PHP could not read the list.
- GET  reconcile/mounts/{storageId}/slice: file ids with etag, size and mtime
  below one walk root, ascending, ``next`` for the following slice.
- POST reconcile/storages/classify: gone, deselected and present for storages
  the mount list no longer carries.
- POST reconcile/requeue: files the walk found new or changed, handed back to
  the one pre-check of PHP; only PHP writes the work stock (D-02-05).

Every answer is checked against the contract before anything is done with it.
A field outside the contract (above all a path or a name) makes the answer
unusable: the caller sees None and concludes nothing from it. The models are
strict, so a bool never passes as a number and a number never as a string.

The HTTP client and the requests live in nc.py, the one module that may hold a
client (tests/test_boundary.py); this module holds the contract and the bands.
"""

import logging
from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from audio_video_search_backend import nc

LOGGER = logging.getLogger(__name__)

# ReconcileController::MAX_IDS: the list limit of classify and requeue.
MAX_IDS: Final = 256
# StorageService::MAX_SLICE.
MAX_SLICE: Final = 1000
MAX_ETAG_LENGTH: Final = 64

_STRICT: Final = ConfigDict(extra="forbid", strict=True, frozen=True)


class MountEntry(BaseModel):
    """One mount of the mount set, once per (storage, walk root)."""

    model_config = _STRICT

    storageId: int = Field(ge=0)
    rootId: int = Field(ge=0)
    crawlFinished: bool
    capturable: bool
    external: bool
    groupable: bool


class MountList(BaseModel):
    """The answer of GET reconcile/mounts."""

    model_config = _STRICT

    ok: bool
    mounts: list[MountEntry]


class SliceFile(BaseModel):
    """One media file of a slice: its id and the version of its bytes as the cache knows it."""

    model_config = _STRICT

    fileId: int = Field(gt=0)
    etag: str = Field(max_length=MAX_ETAG_LENGTH)
    size: int = Field(ge=0)
    mtime: int = Field(ge=0)


class Slice(BaseModel):
    """The answer of GET reconcile/mounts/{storageId}/slice."""

    model_config = _STRICT

    files: list[SliceFile] = Field(max_length=MAX_SLICE)
    next: int | None = Field(gt=0)


class Classification(BaseModel):
    """The answer of POST reconcile/storages/classify."""

    model_config = _STRICT

    gone: list[int]
    deselected: list[int]
    present: list[int]


class RequeueAnswer(BaseModel):
    """The answer of POST reconcile/requeue: queued as content, and refused by the pre-check."""

    model_config = _STRICT

    enqueued: int = Field(ge=0)
    rejected: int = Field(ge=0)


def _parsed[M: BaseModel](model: type[M], status: int | None, data: object, route: str) -> M | None:
    if data is None:
        return None
    try:
        return model.model_validate(data)
    except ValidationError as error:
        # Only the route kind and the count: the rejected value may be a path.
        LOGGER.warning(
            "reconcile answer outside the contract",
            extra={"route": route, "status": status, "errors": error.error_count()},
        )
        return None


class FileClient:
    """The four reconcile routes over one held client; never raises for the transport."""

    def __init__(self, client: nc.HttpClient | None = None) -> None:
        self._client = client if client is not None else nc.new_reconcile_client()
        self._owned = client is None

    async def aclose(self) -> None:
        if self._owned:
            await self._client.aclose()

    async def mounts(self) -> MountList | None:
        """The mount list, or None when it could not be read or lies outside the contract."""
        status, data = await nc.reconcile_request(self._client, "GET", "mounts")
        return _parsed(MountList, status, data, "mounts")

    async def slice(self, storage_id: int, root_id: int, after: int, limit: int) -> Slice | None:
        """One slice below a walk root, or None."""
        if storage_id <= 0 or root_id <= 0 or after < 0 or not 0 < limit <= MAX_SLICE:
            raise ValueError("invalid slice request")
        status, data = await nc.reconcile_request(
            self._client,
            "GET",
            f"mounts/{storage_id}/slice",
            params={"root": root_id, "after": after, "limit": limit},
        )
        answer = _parsed(Slice, status, data, "slice")
        if answer is not None and len(answer.files) > limit:
            return None
        return answer

    async def classify(self, storage_ids: Sequence[int]) -> Classification | None:
        """gone, deselected and present for the named storages, asked in bands; None when a band failed."""
        gone: list[int] = []
        deselected: list[int] = []
        present: list[int] = []
        ids = list(storage_ids)
        for start in range(0, len(ids), MAX_IDS):
            status, data = await nc.reconcile_request(
                self._client, "POST", "storages/classify", body={"storageIds": ids[start : start + MAX_IDS]}
            )
            answer = _parsed(Classification, status, data, "storages/classify")
            if answer is None:
                return None
            gone += answer.gone
            deselected += answer.deselected
            present += answer.present
        return Classification(gone=gone, deselected=deselected, present=present)

    async def requeue(self, file_ids: Sequence[int]) -> RequeueAnswer | None:
        """Hand files back to the pre-check of PHP in bands; None when a band failed."""
        enqueued = 0
        rejected = 0
        ids = list(file_ids)
        for start in range(0, len(ids), MAX_IDS):
            status, data = await nc.reconcile_request(
                self._client, "POST", "requeue", body={"fileIds": ids[start : start + MAX_IDS]}
            )
            answer = _parsed(RequeueAnswer, status, data, "requeue")
            if answer is None:
                return None
            enqueued += answer.enqueued
            rejected += answer.rejected
        return RequeueAnswer(enqueued=enqueued, rejected=rejected)
