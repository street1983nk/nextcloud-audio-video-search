"""The read proof: a copy hangs at a content only after its own reader read the head of it.

The prefilter key (same share, same path in the share, same size, same mtime)
says that two references are very likely the same file. It says nothing about
who may read it: Findling measured (A6) that an SMB server lists a file it
denies to a user and that ``isReadable()`` says yes; only the read itself fails
or hangs. Attaching a copy by the prefilter key alone would hand that user the
transcript of a file the server keeps from them (D-02-01a).

So a copy attaches only after THIS verdict: the first 64 KiB through its own
file id and its own reader, within a time limit, with exactly
``min(65536, size)`` bytes, and with the sha256 the content has as its head.
The same verdict is asked again for an attached reference whose proof is due
(D-02-12); when it fails, the hits of that user are gone at once.

There is one way to say ok, :func:`prove_read`, and it has one ``return`` for
it. Nothing in this module reads the environment, a preference of the admin or
the file system: the verdict cannot be turned off (D-02-10,
tests/test_read_proof_gate.py). The positive control of the acceptance test
runs an image built in CI out of a patched copy and never published.

:class:`StorageBreaker` keeps the container from asking a storage that hangs:
PHP cannot interrupt a hanging smbclient, every try holds a PHP worker until
its own time limit.
"""

import enum
import hmac
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Final

from audio_video_search_backend import nc
from audio_video_search_backend.store.repo import FileRef

LOGGER = logging.getLogger(__name__)

# The reason of a reference that is not asked because its storage hangs.
STORAGE_PAUSED: Final = "storage_paused"
# Timeouts in a row on one storage before it is left alone, and for how long.
TIMEOUTS_TO_OPEN: Final = 3
OPEN_SECONDS: Final = 3600
_HEX64: Final = re.compile(r"[0-9a-f]{64}")

type HeadFetch = Callable[[int, str], Awaitable[nc.HeadResult]]


class ProofOutcome(enum.StrEnum):
    """What one read proof said. Only ok lets a reference hang at a content."""

    OK = "ok"
    READ_DENIED = "read_denied"
    READ_TIMEOUT = "read_timeout"
    ACCESS_CONTROL = "access_control"
    LOCKED = "locked"
    GATEWAY_FAILED = "gateway_failed"
    HEAD_MISMATCH = "head_mismatch"


# The refusals of the head route. 403, 422 and 404 are one answer here: this
# reader does not get the bytes. A code that is not listed (too long, a broken
# stream, anything new) is gateway_failed, never ok.
_REFUSALS: Final = {
    nc.READ_DENIED: ProofOutcome.READ_DENIED,
    nc.NOT_FOUND: ProofOutcome.READ_DENIED,
    nc.EXCLUDED: ProofOutcome.READ_DENIED,
    nc.ACCESS_CONTROL: ProofOutcome.ACCESS_CONTROL,
    nc.LOCKED: ProofOutcome.LOCKED,
    nc.READ_TIMEOUT: ProofOutcome.READ_TIMEOUT,
}


def head_length(size: int) -> int:
    """How long the head of a file of ``size`` bytes is: the whole file up to 64 KiB."""
    return min(nc.HEAD_BYTES, size)


async def prove_read(ref: FileRef, media_head_sha256: str, expected_length: int, fetch: HeadFetch) -> ProofOutcome:
    """Read the head of ``ref`` as its own reader and compare it with the head of a content.

    ``fetch`` is asked with the file id and the reader of this reference and
    of no other. The answer is ok only when it carries no error, a valid
    sha256, exactly ``expected_length`` bytes (which has to be
    ``min(65536, ref.size)``) and the hash ``media_head_sha256``. Other bytes
    are head_mismatch: the caller reads that copy in full. Everything else is
    the refusal it is, and an answer that cannot be judged is gateway_failed.
    """
    reader = ref.reader_uid
    if reader is None:
        # Nobody to read as: no request, and no proof.
        return ProofOutcome.READ_DENIED
    if _HEX64.fullmatch(media_head_sha256) is None:
        # A content without a head cannot be proved against; the copy is read in full.
        return ProofOutcome.HEAD_MISMATCH
    if expected_length != head_length(ref.size):
        return ProofOutcome.GATEWAY_FAILED
    try:
        result = await fetch(ref.file_id, reader)
    except Exception as exc:  # a broken fetch is a failed proof, never a passed one
        LOGGER.exception("read proof fetch raised", extra={"file_id": ref.file_id, "error_type": type(exc).__name__})
        return ProofOutcome.GATEWAY_FAILED
    if result.error is not None:
        return _REFUSALS.get(result.error, ProofOutcome.GATEWAY_FAILED)
    sha = result.sha256
    if sha is None or _HEX64.fullmatch(sha) is None:
        return ProofOutcome.GATEWAY_FAILED
    if result.length != expected_length:
        return ProofOutcome.GATEWAY_FAILED
    if hmac.compare_digest(sha, media_head_sha256):
        return ProofOutcome.OK
    return ProofOutcome.HEAD_MISMATCH


class StorageBreaker:
    """The circuit per storage: three timeouts in a row leave a storage alone for an hour.

    Kept in memory: after a restart the count starts again, which costs at most
    three more timeouts. Any answer of the storage, also a refusal, starts the
    count again; only silence counts.
    """

    def __init__(self, *, threshold: int = TIMEOUTS_TO_OPEN, open_seconds: int = OPEN_SECONDS) -> None:
        self._threshold = threshold
        self._open_seconds = open_seconds
        self._timeouts: dict[int, int] = {}
        self._open_until: dict[int, int] = {}

    def closes_at(self, storage_id: int, now: int) -> int | None:
        """When the storage is asked again, None while it may be asked."""
        until = self._open_until.get(storage_id)
        if until is None:
            return None
        if until <= now:
            del self._open_until[storage_id]
            return None
        return until

    def record(self, storage_id: int, *, timed_out: bool, now: int) -> None:
        """Note the outcome of one request to a storage."""
        if not timed_out:
            self._timeouts.pop(storage_id, None)
            return
        count = self._timeouts.get(storage_id, 0) + 1
        if count < self._threshold:
            self._timeouts[storage_id] = count
            return
        self._timeouts.pop(storage_id, None)
        self._open_until[storage_id] = now + self._open_seconds
        LOGGER.warning(
            "storage paused after timeouts",
            extra={"storage_id": storage_id, "timeouts": count, "seconds": self._open_seconds},
        )
