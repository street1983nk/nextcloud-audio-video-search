"""The contract of the PHP work stock: claim, ack, unlock (plan 02-03, 02-05).

The PHP app keeps the discovery in ``oc_avs_queue`` until the container has
written a reference into state.db; the container quits a row only after that
transaction (worker/intake.py). The lock of a claimed row is fixed at 900 s on
the PHP side, so a row the container dies on comes back by itself.

Every answer is checked against the contract before anything is done with it.
A field outside the contract (above all a path or a file name) makes the whole
band unusable: nothing of it is written and nothing is acknowledged
(T-02-17). The models are strict, so a bool never passes as a number.

The HTTP client and the requests live in nc.py, the one module that may hold a
client (tests/test_boundary.py); this module holds the contract and the
batching.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from audio_video_search_backend import nc
from audio_video_search_backend.store.repo import IntakeItem

LOGGER = logging.getLogger(__name__)

# The kinds of QueueMapper::KINDS, in the order of their priority there.
KINDS: Final = ("exclude_storage", "exclude", "delete", "trash", "restore", "content", "metadata")
# Kinds that describe a file and therefore carry etag, size and mtime.
_KINDS_WITH_FILE: Final = frozenset({"content", "metadata", "restore"})
# QueueMapper::MAX_BATCH and the list limit of QueueController.
MAX_BATCH: Final = 256
MAX_UID_LENGTH: Final = 64
MAX_ETAG_LENGTH: Final = 64
_FIRST_NON_SUCCESS: Final = 300
# QueueMapper::ORIGINS (plan 03-04, D-03-05): how PHP came to a row, an event of
# a person or the crawl. The same set as repo.ORIGINS; tests/test_php_gates.py
# (rule 17) holds the three lists together. A row with any other origin is
# outside the contract like every other foreign value.
ORIGINS: Final = frozenset({"event", "crawl"})

Kind = Literal["exclude_storage", "exclude", "delete", "trash", "restore", "content", "metadata"]
type Origin = Literal["event", "crawl"]


class ClaimItem(BaseModel):
    """One row as QueueService::describe hands it out: exactly the ten keys."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    queueId: int = Field(gt=0)
    kind: Kind
    fileId: int | None = Field(gt=0)
    storageId: int = Field(ge=0)
    etag: str | None = Field(max_length=MAX_ETAG_LENGTH)
    size: int | None = Field(ge=0)
    mtime: int | None = Field(ge=0)
    prefilterKey: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    readerUid: str | None = Field(min_length=1, max_length=MAX_UID_LENGTH)
    origin: Origin

    @model_validator(mode="after")
    def _a_file_kind_describes_a_file(self) -> Self:
        if self.kind in _KINDS_WITH_FILE and (
            self.fileId is None or self.etag is None or self.size is None or self.mtime is None
        ):
            raise ValueError("a file kind without its file fields")
        return self

    def to_intake(self) -> IntakeItem:
        return IntakeItem(
            queue_id=self.queueId,
            kind=self.kind,
            file_id=self.fileId,
            storage_id=self.storageId,
            etag=self.etag,
            size=self.size,
            mtime=self.mtime,
            prefilter_key=self.prefilterKey,
            reader_uid=self.readerUid,
            origin=self.origin,
        )


class ClaimStats(BaseModel):
    """Rows per kind of the PHP work stock; ok is false when PHP could not count them."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    ok: bool
    open: dict[str, int]
    dropped: int = Field(default=0, ge=0)

    @field_validator("open", mode="before")
    @classmethod
    def _an_empty_php_array_is_a_list(cls, value: object) -> object:
        # json_encode([]) of PHP is a list, not an object.
        return {} if value == [] else value


class ClaimAnswer(BaseModel):
    """The answer of POST /queues/media/claim."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    claimToken: str = Field(pattern=r"^[0-9a-f]{32}$")
    items: list[ClaimItem] = Field(max_length=MAX_BATCH)
    stats: ClaimStats


@dataclass(frozen=True, slots=True)
class ClaimOutcome:
    """A usable answer, or why there is none: unreachable, or a band outside the contract."""

    answer: ClaimAnswer | None
    reachable: bool
    malformed: int


def _band_size(data: object) -> int:
    items = data.get("items") if isinstance(data, dict) else None
    return len(items) if isinstance(items, list) else 1


class QueueClient:
    """Claim, ack and unlock over one held client; never raises for the transport."""

    def __init__(self, client: nc.HttpClient | None = None) -> None:
        self._client = client if client is not None else nc.new_queue_client()
        self._owned = client is None

    async def aclose(self) -> None:
        if self._owned:
            await self._client.aclose()

    async def claim(self, limit: int) -> ClaimOutcome:
        if not 0 < limit <= MAX_BATCH:
            raise ValueError("invalid claim limit")
        status, data = await nc.queue_post(self._client, "claim", {"limit": limit})
        if data is None:
            return ClaimOutcome(answer=None, reachable=status is not None, malformed=0)
        try:
            answer = ClaimAnswer.model_validate(data)
        except ValidationError as error:
            band = _band_size(data)
            # Only the count and the error type: the rejected value may be a path.
            LOGGER.warning("claim answer outside the contract", extra={"items": band, "errors": error.error_count()})
            return ClaimOutcome(answer=None, reachable=True, malformed=band)
        return ClaimOutcome(answer=answer, reachable=True, malformed=0)

    async def ack(self, token: str, queue_ids: Sequence[int]) -> bool:
        return await self._send("ack", token, queue_ids)

    async def unlock(self, token: str, queue_ids: Sequence[int]) -> bool:
        return await self._send("unlock", token, queue_ids)

    async def _send(self, action: str, token: str, queue_ids: Sequence[int]) -> bool:
        """One request per MAX_BATCH ids; True only when every request was answered with 2xx."""
        ids = list(queue_ids)
        done = True
        for start in range(0, len(ids), MAX_BATCH):
            status, _ = await nc.queue_post(
                self._client, action, {"claimToken": token, "queueIds": ids[start : start + MAX_BATCH]}
            )
            done = done and status is not None and status < _FIRST_NON_SUCCESS
        return done
