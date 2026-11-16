"""POST /export and /export/meta: subtitle draft and transcript of one file (plan 04-09).

The contract with ExAppService::export/exportMeta (plan 04-10):

- ``/export`` with ``{"fileId", "format": "srt"|"vtt"|"txt"}`` answers
  ``{"known": true, "partial", "untilMs", "language", "body"}``;
- ``/export/meta`` with ``{"fileId"}`` answers the same without ``body``, so the
  play page knows state, target name and track without loading the text.

Leak rule (X4, T-04-24): a file that is not active, excluded, never seen,
without a current version or without a visible word gets exactly
``{"known": false}``, byte for byte the same on both routes. The gate is the
same as for /excerpt: store.media_for_file and store.preview_view name nothing
for a reference that may not give a hit.

While the file is still in work the export is allowed (D-04-17): ``partial``
is true and ``untilMs`` is the end of the last finished piece; the words are
those of the current version, which holds the finished pieces only.

The language is de, en or fr, never ``und`` (D-04-15, T-04-27): the store
names it from the stored majority or the counters of a running job; a file of
the stock without either gets it detected from its text outside the store
lock and stored once, the first stored answer wins. No language, no export.

Only the snapshot of the words holds the store lock; language detection, cue
building and formatting run in worker threads beside it (T-04-26), so a long
file never blocks search or the worker. Nothing here logs: text, format
content and language belong in no log line (T-04-28).
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Final, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from audio_video_search_backend import file_language
from audio_video_search_backend.api import Services, run_locked, services
from audio_video_search_backend.model.overlay import Word
from audio_video_search_backend.store.repo import FILE_LANGUAGES
from audio_video_search_backend.subtitles.cues import _CONTROL, build_cues
from audio_video_search_backend.subtitles.formats import to_srt, to_txt, to_vtt

router = APIRouter()

# A job in these states may still add pieces; with a finished piece its text is partial (as /excerpt).
_IN_WORK: Final = frozenset({"queued", "running", "waiting"})
_NOT_KNOWN: Final[dict[str, object]] = {"known": False}

type ExportFormat = Literal["srt", "vtt", "txt"]


class MetaRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fileId: Annotated[StrictInt, Field(gt=0)]  # the wire name of the contract


class ExportRequest(MetaRequest):
    format: ExportFormat


@dataclass(frozen=True, slots=True)
class _Snap:
    """What one export reads from the store under the lock."""

    media_id: int
    words: list[Word]
    language: str | None
    partial: bool
    until_ms: int


def _snapshot(opened: Services, file_id: int) -> _Snap | None:
    """The words and state of a file that may be exported, None under the leak rule."""
    store = opened.store
    media_id = store.media_for_file(file_id)
    if media_id is None or store.current(media_id) is None:
        return None
    words = store.effective_words(media_id)
    if not words:
        return None
    view = store.preview_view(file_id)
    partial = view is not None and view.state in _IN_WORK and view.chunks_done > 0
    return _Snap(
        media_id=media_id,
        words=words,
        language=store.file_language(media_id),
        partial=partial,
        until_ms=view.next_start_ms if partial and view is not None else 0,
    )


def _visible(words: Sequence[Word]) -> bool:
    """Whether any word shows a character once control runs are spaces (as cues and TXT clean them)."""
    return any(_CONTROL.sub("", word.surface) for word in words)


def _render(words: Sequence[Word], fmt: ExportFormat) -> str:
    """The body in one format; runs in a worker thread, never under the store lock."""
    if fmt == "txt":
        return to_txt(words)
    cues = build_cues(words)
    return to_srt(cues) if fmt == "srt" else to_vtt(cues)


async def _language(opened: Services, snap: _Snap) -> str | None:
    """The language of the file, detected and stored once for the stock (D-04-15)."""
    if snap.language in FILE_LANGUAGES:
        return snap.language
    detected = await asyncio.to_thread(file_language.detect, snap.words)
    if detected not in FILE_LANGUAGES:
        return None
    store = opened.store

    def store_once() -> str | None:
        store.set_file_language(snap.media_id, detected)
        return store.file_language(snap.media_id)  # the first stored answer wins

    language = await run_locked(opened, store_once)
    return language if language in FILE_LANGUAGES else None


async def _known(opened: Services, file_id: int) -> tuple[_Snap, dict[str, object]] | None:
    """The snapshot and the meta answer of an exportable file, None under the leak rule."""
    snap = await run_locked(opened, lambda: _snapshot(opened, file_id))
    if snap is None or not await asyncio.to_thread(_visible, snap.words):
        return None
    language = await _language(opened, snap)
    if language is None:
        return None
    return snap, {"known": True, "partial": snap.partial, "untilMs": snap.until_ms, "language": language}


@router.post("/export")
async def export(body: ExportRequest, opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    known = await _known(opened, body.fileId)
    if known is None:
        return dict(_NOT_KNOWN)
    snap, answer = known
    answer["body"] = await asyncio.to_thread(_render, snap.words, body.format)
    return answer


@router.post("/export/meta")
async def export_meta(body: MetaRequest, opened: Annotated[Services, Depends(services)]) -> dict[str, object]:
    known = await _known(opened, body.fileId)
    return dict(_NOT_KNOWN) if known is None else known[1]
