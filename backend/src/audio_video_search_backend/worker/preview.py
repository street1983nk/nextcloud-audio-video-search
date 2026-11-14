"""The preview: one content per step, in chunks of 10 min, findable after every chunk (plan 03-13).

The worker joins the media intake (media/), the engine child (engine/child.py)
and the store (TRANS-01, TRANS-07, TRANS-08, MEDIA-01 to 04). One step works one
job, one step at a time; the store is touched only through ``run_locked`` in
short calls, never while a download, ffprobe, ffmpeg or the engine runs.

The states of a job (preview_job.state, store/repo.py):

- queued: waits for its turn. The claim takes events before crawl, then the
  newest file first (D-03-05), and only a content with an active, keyed
  reference that has a reader.
- running: this step works it. Before the download the free space is checked
  (D-03-17); the download goes to a temporary file with a random name and no
  extension (nc.fetch_media_file) and its sha256 must be the content key,
  otherwise the bytes changed since the capture. Then ffprobe, the duration
  limit (D-03-08), the engine child and the chunk loop.
- waiting: comes back at next_try_at. disk_full waits with its reason for
  DISK_FULL_RETRY_SECONDS (T12 of 03-UI-SPEC); no room for the engine, a
  refused download, other bytes than the key and an engine failure wait
  without a reason. Only an engine failure uses up an attempt; the third one
  skips the job with engine_failed.
- complete: the last chunk is in and the verdict is "transcript".
- skipped: a reason of the probe or the decoder (no_audio, damaged, protected,
  format_unsupported; D-03-20: a file nothing readable is found in is damaged,
  which the extensionless name makes ffprobe say by itself), too_long,
  engine_failed, or the verdict no_speech / unsupported_language.

The chunk loop (TRANS-07, RESEARCH Pattern 2): a chunk starting at
``next_start_ms`` decodes ``[start - CHUNK_CONTEXT_MS, start + CHUNK_MS +
CHUNK_LOOKAHEAD_MS)`` and asks the engine with that decode start as its offset,
so every word time is media time (TRANS-08). It takes the windows that begin
before ``start + CHUNK_MS`` and reach past ``start``; a window that begins in
the context keeps only its words from ``start`` on, so nothing is stored twice
and nothing falls between two chunks. When the decoded range reaches the end of
the file the chunk takes everything. ``next_start_ms`` becomes the end of the
last window taken, or ``start + CHUNK_MS`` without one, and is committed with
the words, the index revision and the counters in one transaction: the words of
every chunk are findable at once (D-07), and a restart goes on from there.

Two outcomes leave a job before its end on purpose:

- YIELDED (D-03-06): after a chunk of a crawl job, when an event job waits, the
  job goes back to queued with its progress; the chunk itself is never cut.
- STALE: the job is no longer this step's to write (another epoch, a foreign
  current version) or the bytes are not the content's. A chunk the store
  refuses ends the job (03-09: never tried again); other bytes wait.

After the last chunk: one second VAD pass over the whole file for a file up to
60 s without a kept word (D-03-16), then the verdict of engine/catch.py.

Logs carry media ids, file ids, outcomes, reason codes and counts; never a word,
a path or a user.
"""

import asyncio
import enum
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from audio_video_search_backend import companion, config, nc, settings
from audio_video_search_backend.api import Services, run_locked
from audio_video_search_backend.engine import child
from audio_video_search_backend.engine.catch import (
    DROP_CONFIDENCE,
    DROP_LANGUAGE,
    DROP_SCRIPT,
    KEEP,
    TRANSCRIPT,
    file_verdict,
    needs_second_pass,
)
from audio_video_search_backend.engine.constants import (
    CHUNK_CONTEXT_MS,
    CHUNK_LOOKAHEAD_MS,
    CHUNK_MS,
    CONFIG_VERSION,
    SAMPLE_RATE,
)
from audio_video_search_backend.engine.parakeet import Window
from audio_video_search_backend.media import decode as decode_module
from audio_video_search_backend.media import probe as probe_module
from audio_video_search_backend.media.decode import DecodeResult
from audio_video_search_backend.media.probe import DAMAGED, ProbeResult
from audio_video_search_backend.model.overlay import Word, normalize
from audio_video_search_backend.model.provenance import Level, Provenance
from audio_video_search_backend.models import catalog, procure
from audio_video_search_backend.store.repo import ChunkCounters, PreviewJob
from audio_video_search_backend.worker.capture import DISK_FULL_RETRY_SECONDS, MAX_CAPTURE_BYTES, tmp_dir

LOGGER = logging.getLogger(__name__)

# Pause when there is nothing due; with work the next step follows at once.
IDLE_SECONDS: Final = 15.0
# An engine that fails this often on one job gives up: engine_failed.
MAX_ENGINE_ATTEMPTS: Final = 3
# No room for the engine, or an engine failure: the next try after a minute.
NO_ROOM_RETRY_SECONDS: Final = 60
# A refused download or other bytes than the content key: the capture judges the
# reference meanwhile; until then the job waits instead of downloading in a loop.
FETCH_RETRY_SECONDS: Final = 300
# The admin settings are read at the start and then this often (D-03-09).
SETTINGS_REFRESH_SECONDS: Final = 300
_MS_PER_HOUR: Final = 3_600_000
# The provenance of the preview; phase 6 brings the profiles.
PROFILE: Final = "balanced"
# The language of a preview version: Parakeet names none.
PREVIEW_LANGUAGE: Final = "und"
# The own subdirectory under $APP_PERSISTENT_STORAGE/tmp: the capture tidies only its part files.
PREVIEW_DIRNAME: Final = "preview"
NO_ROOM_REASON: Final = "no_room"
_ENGINE_FAILURES: Final = frozenset({child.TIMEOUT, child.OUT_OF_MEMORY, child.CRASHED})
_BYTES_PER_SAMPLE: Final = 4


class PreviewOutcome(enum.StrEnum):
    """What one step did with one job."""

    IDLE = "idle"
    CHUNK_DONE = "chunk_done"
    COMPLETE = "complete"
    SKIPPED = "skipped"
    DEFERRED = "deferred"
    YIELDED = "yielded"
    STALE = "stale"
    FAILED_ATTEMPT = "failed_attempt"


@dataclass(frozen=True, slots=True)
class PreviewStep:
    outcome: PreviewOutcome
    media_id: int | None = None
    reason: str | None = None
    chunks: int = 0


_IDLE: Final = PreviewStep(PreviewOutcome.IDLE)


class Engine(Protocol):
    """What the worker needs of engine.child.EngineWorker."""

    def start(self) -> str: ...

    def ask(self, pcm: bytes, offset_ms: int, second_pass: bool) -> tuple[str, list[Window]]: ...

    def stop(self) -> None: ...


type Fetch = Callable[[int, str, Path, int, int], AbstractAsyncContextManager[tuple[nc.FetchResult, Path | None]]]
type EngineFactory = Callable[[Path], Engine]
type Probe = Callable[[Path], ProbeResult]
type Decode = Callable[..., DecodeResult]
type SettingsReader = Callable[[], Awaitable[dict[str, str]]]


@dataclass(frozen=True, slots=True)
class Taken:
    """What one chunk keeps of the windows of the engine."""

    words: list[Word]
    counters: ChunkCounters
    next_start_ms: int


def _add(a: ChunkCounters, b: ChunkCounters) -> ChunkCounters:
    return ChunkCounters(
        kept_words=a.kept_words + b.kept_words,
        drop_script=a.drop_script + b.drop_script,
        drop_language=a.drop_language + b.drop_language,
        drop_conf=a.drop_conf + b.drop_conf,
        speech_ms=a.speech_ms + b.speech_ms,
    )


def take(windows: Sequence[Window], start_ms: int, end_ms: int | None, *, count_speech: bool = True) -> Taken:
    """The words and counters of the windows that belong to the chunk ``[start_ms, end_ms)``.

    A window belongs to the chunk when it begins before ``end_ms`` (None: no
    end, the rest of the file) and reaches past ``start_ms``. A window that
    begins before ``start_ms`` was heard in the context: it keeps only its words
    from ``start_ms`` on, and its drops and speech were counted by the chunk
    before. Without a window the next chunk starts at ``end_ms``.
    """
    words: list[Word] = []
    kept = script = language = conf = speech = 0
    last_end: int | None = None
    for window in sorted(windows, key=lambda w: w.start_ms):
        if end_ms is not None and window.start_ms >= end_ms:
            continue
        if window.start_ms < start_ms and window.end_ms <= start_ms:
            continue
        last_end = window.end_ms if last_end is None else max(last_end, window.end_ms)
        own = window.start_ms >= start_ms
        if window.verdict == KEEP:
            for item in window.words:
                if item.start_ms < start_ms or not item.text.strip():
                    continue
                words.append(
                    Word(
                        start_ms=item.start_ms,
                        end_ms=item.end_ms,
                        surface=item.text,
                        norm=normalize(item.text),
                        conf=item.conf,
                        src="machine",
                    )
                )
                kept += 1
        elif own and window.verdict == DROP_SCRIPT:
            script += window.n_words
        elif own and window.verdict == DROP_LANGUAGE:
            language += window.n_words
        elif own and window.verdict == DROP_CONFIDENCE:
            conf += window.n_words
        if count_speech:
            speech += window.speech_ms if own else min(window.speech_ms, window.end_ms - start_ms)
    words.sort(key=lambda w: (w.start_ms, w.end_ms))
    # Without a window the next chunk starts at the end of this one (or here, for the rest of the file).
    next_start = (start_ms if end_ms is None else end_ms) if last_end is None else max(start_ms, last_end)
    counters = ChunkCounters(
        kept_words=kept, drop_script=script, drop_language=language, drop_conf=conf, speech_ms=speech
    )
    return Taken(words=words, counters=counters, next_start_ms=next_start)


def preview_dir() -> Path:
    """$APP_PERSISTENT_STORAGE/tmp/preview, where the file of the running job lives."""
    return tmp_dir() / PREVIEW_DIRNAME


async def read_admin_settings() -> dict[str, str]:
    """The saved admin settings, read from Nextcloud (appconfig_ex) in a client of its own."""
    async with nc.nc_app() as client:
        return await settings.read(client)


def _default_engine(models_root: Path) -> Engine:
    return child.EngineWorker(models_root)


def _pcm_ms(pcm: bytes) -> int:
    return len(pcm) // _BYTES_PER_SAMPLE * 1000 // SAMPLE_RATE


def _clear(directory: Path) -> int:
    """At start: every file a stopped process left in the own directory goes."""
    directory.mkdir(parents=True, exist_ok=True)
    removed = nc.remove_stale_parts(directory)
    for leftover in directory.iterdir():
        if leftover.is_file():
            leftover.unlink(missing_ok=True)
            removed += 1
    return removed


class Preview:
    """One job per step: claim, download, probe, the chunk loop, the verdict."""

    def __init__(
        self,
        services: Services,
        *,
        directory: Path | None = None,
        models_root: Path | None = None,
        fetch: Fetch = nc.fetch_media_file,
        engine_factory: EngineFactory = _default_engine,
        probe: Probe = probe_module.probe,
        decode: Decode = decode_module.decode_chunk,
        clock: Callable[[], float] = time.time,
        read_settings: SettingsReader | None = None,
    ) -> None:
        self._services = services
        self._directory = preview_dir() if directory is None else directory
        self._models_root = config.storage_root() if models_root is None else models_root
        self._fetch = fetch
        self._engine_factory = engine_factory
        self._probe = probe
        self._decode = decode
        self._clock = clock
        self._read_settings = read_admin_settings if read_settings is None else read_settings
        self._serial = asyncio.Lock()

    def _now(self) -> int:
        return int(self._clock())

    async def prepare(self) -> None:
        """At start: the own temporary directory is empty, running jobs are back in the queue."""
        removed = await asyncio.to_thread(_clear, self._directory)
        store = self._services.store
        reset = await run_locked(self._services, store.reset_running)
        LOGGER.info("preview prepared", extra={"removed_files": removed, "reset_jobs": reset})

    async def sync_limits(self, read_settings: SettingsReader) -> int | None:
        """Take the duration limit of the admin settings; returns the jobs brought back, None when unread.

        Only a higher limit brings the jobs skipped as too_long that now fit
        back into the work stock (D-03-09); a lower or equal one touches no job,
        so a file of unknown length that ran past the limit does not come back
        every few minutes. The jobs come back before the new limit is stored:
        a stop between both steps reads the old limit next time and brings
        them back again, which changes nothing. The reader talks to Nextcloud
        outside the services lock; a failed read keeps the stored limit.
        """
        try:
            values = await read_settings()
        except Exception as exc:  # Nextcloud unreachable or an odd answer: the stored limit stays
            LOGGER.warning("settings not read", extra={"error_type": type(exc).__name__})
            return None
        hours = settings.read_max_duration_hours(values)
        store = self._services.store

        def apply() -> tuple[int, int]:
            previous = store.max_duration_hours()
            back = store.requeue_too_long(hours * _MS_PER_HOUR) if hours > previous else 0
            if hours != previous:
                store.set_max_duration_hours(hours)
            return previous, back

        previous, back = await run_locked(self._services, apply)
        if hours != previous:
            LOGGER.info("duration limit changed", extra={"hours": hours, "previous": previous, "jobs_back": back})
        return back

    async def run_once(self) -> PreviewStep:
        async with self._serial:
            return await self._step()

    async def _step(self) -> PreviewStep:
        store = self._services.store
        now = self._now()
        job = await run_locked(self._services, lambda: store.next_preview(now))
        if job is None:
            return _IDLE
        source = await run_locked(self._services, lambda: store.preview_source(job.media_id))
        if source is None:
            # The claim saw a readable reference a moment ago; without one nobody can read it now.
            await run_locked(self._services, lambda: store.yield_preview(job))
            return PreviewStep(PreviewOutcome.STALE, job.media_id)
        file_id, reader, size = source
        if not await self._room_for(size):
            return await self._defer_disk_full(job)
        async with self._fetch(file_id, reader, self._directory, size, MAX_CAPTURE_BYTES) as (result, path):
            if result.error is not None or path is None or result.sha256 is None:
                code = result.error or nc.GATEWAY_FAILED
                if code == nc.DISK_FULL:
                    return await self._defer_disk_full(job)
                return await self._wait(job, PreviewOutcome.DEFERRED, code, FETCH_RETRY_SECONDS)
            sha = result.sha256
            owner = await run_locked(self._services, lambda: store.media_of_file_sha256(sha))
            if owner != job.media_id:
                # Other bytes than the content key: the file changed since the capture (T-03-43).
                return await self._wait(job, PreviewOutcome.STALE, None, FETCH_RETRY_SECONDS)
            return await self._work(job, path, sha)

    async def _room_for(self, size: int) -> bool:
        try:
            free = await asyncio.to_thread(nc.free_bytes, self._directory)
        except OSError:
            return False
        return free >= size + nc.DISK_RESERVE_BYTES

    async def _defer_disk_full(self, job: PreviewJob) -> PreviewStep:
        store = self._services.store
        retry = self._now() + DISK_FULL_RETRY_SECONDS
        done = await run_locked(self._services, lambda: store.defer_preview(job, nc.DISK_FULL, retry_at=retry))
        outcome = PreviewOutcome.DEFERRED if done else PreviewOutcome.STALE
        return PreviewStep(outcome, job.media_id, nc.DISK_FULL)

    async def _wait(
        self, job: PreviewJob, outcome: PreviewOutcome, reason: str | None, seconds: int, *, count: bool = False
    ) -> PreviewStep:
        store = self._services.store
        retry = self._now() + seconds
        done = await run_locked(self._services, lambda: store.retry_preview(job, retry_at=retry, count=count))
        return PreviewStep(outcome if done else PreviewOutcome.STALE, job.media_id, reason)

    async def _skip(self, job: PreviewJob, reason: str, duration_ms: int | None, chunks: int = 0) -> PreviewStep:
        store = self._services.store
        done = await run_locked(self._services, lambda: store.skip_preview(job, reason, duration_ms))
        return PreviewStep(PreviewOutcome.SKIPPED if done else PreviewOutcome.STALE, job.media_id, reason, chunks)

    async def _work(self, job: PreviewJob, path: Path, sha: str) -> PreviewStep:
        probed = await asyncio.to_thread(self._probe, path)
        if probed.reason is not None or probed.stream_index is None:
            return await self._skip(job, probed.reason or DAMAGED, None)
        store = self._services.store
        hours = await run_locked(self._services, store.max_duration_hours)
        max_ms = hours * _MS_PER_HOUR
        if probed.duration_ms is not None and probed.duration_ms > max_ms:
            return await self._skip(job, "too_long", probed.duration_ms)
        engine = self._engine_factory(self._models_root)
        try:
            code = await asyncio.to_thread(engine.start)
            if code != child.OK:
                return await self._wait(job, PreviewOutcome.DEFERRED, NO_ROOM_REASON, NO_ROOM_RETRY_SECONDS)
            return await self._chunks(job, engine, path, probed.stream_index, probed.duration_ms, max_ms, sha)
        finally:
            await asyncio.to_thread(engine.stop)

    async def _engine_failed(self, job: PreviewJob, code: str, duration_ms: int | None, chunks: int) -> PreviewStep:
        if code not in _ENGINE_FAILURES:
            return await self._wait(job, PreviewOutcome.DEFERRED, NO_ROOM_REASON, NO_ROOM_RETRY_SECONDS)
        if job.attempts + 1 >= MAX_ENGINE_ATTEMPTS:
            return await self._skip(job, "engine_failed", duration_ms, chunks)
        step = await self._wait(job, PreviewOutcome.FAILED_ATTEMPT, code, NO_ROOM_RETRY_SECONDS, count=True)
        return PreviewStep(step.outcome, job.media_id, code, chunks)

    async def _commit(self, job: PreviewJob, prov: Provenance, taken: Taken, *, second_pass: bool = False) -> bool:
        store = self._services.store
        return await run_locked(
            self._services,
            lambda: store.commit_chunk(
                job,
                prov=prov,
                words=taken.words,
                next_start_ms=taken.next_start_ms,
                counters=taken.counters,
                second_pass=second_pass,
            ),
        )

    async def _end_stale(self, job: PreviewJob, chunks: int) -> PreviewStep:
        """The store refused a chunk: the job ends here and is never tried again (03-09)."""
        store = self._services.store
        await run_locked(self._services, lambda: store.finish_preview(job, TRANSCRIPT))
        return PreviewStep(PreviewOutcome.STALE, job.media_id, None, chunks)

    async def _chunks(
        self,
        job: PreviewJob,
        engine: Engine,
        path: Path,
        stream_index: int,
        duration_ms: int | None,
        max_ms: int,
        sha: str,
    ) -> PreviewStep:
        store = self._services.store
        prov = Provenance(
            engine="parakeet",
            model_sha256=catalog.MODEL_SHA256,
            config_version=CONFIG_VERSION,
            profile=PROFILE,
            level=Level.PREVIEW,
            epoch=job.epoch,
            language=PREVIEW_LANGUAGE,
            input_file_sha256=sha,
        )
        totals = ChunkCounters(
            kept_words=job.kept_words,
            drop_script=job.drop_script,
            drop_language=job.drop_language,
            drop_conf=job.drop_conf,
            speech_ms=job.speech_ms,
        )
        start = job.next_start_ms
        heard = start
        chunks = 0
        while duration_ms is None or start < duration_ms:
            if duration_ms is None and start >= max_ms:
                return await self._skip(job, "too_long", None, chunks)
            decode_start = max(0, start - CHUNK_CONTEXT_MS)
            wanted = start + CHUNK_MS + CHUNK_LOOKAHEAD_MS - decode_start
            expected = None if duration_ms is None else min(wanted, duration_ms - decode_start)
            decoded = await asyncio.to_thread(
                self._decode, path, stream_index, decode_start, wanted, expected_ms=expected
            )
            if decoded.reason is not None:
                return await self._skip(job, decoded.reason, duration_ms, chunks)
            got = _pcm_ms(decoded.pcm)
            if got == 0:
                if start == 0:
                    # Nothing readable from the very start (D-03-20).
                    return await self._skip(job, DAMAGED, duration_ms, chunks)
                break
            heard = max(heard, decode_start + got)
            code, windows = await asyncio.to_thread(engine.ask, decoded.pcm, decode_start, False)
            if code != child.OK:
                return await self._engine_failed(job, code, duration_ms, chunks)
            # The decoded range reaches the end of a file of known length: this chunk takes the rest.
            # Without a known length the loop goes on until a decode yields no sample.
            last = duration_ms is not None and decode_start + wanted >= duration_ms
            taken = take(windows, start, None if last else start + CHUNK_MS)
            if last and duration_ms is not None:
                taken = Taken(taken.words, taken.counters, max(taken.next_start_ms, duration_ms))
            if not await self._commit(job, prov, taken):
                return await self._end_stale(job, chunks)
            chunks += 1
            totals = _add(totals, taken.counters)
            start = taken.next_start_ms
            if last:
                break
            if job.origin == "crawl" and await run_locked(self._services, store.has_waiting_event):
                done = await run_locked(self._services, lambda: store.yield_preview(job))
                return PreviewStep(PreviewOutcome.YIELDED if done else PreviewOutcome.STALE, job.media_id, None, chunks)
        length = duration_ms if duration_ms is not None else heard
        if needs_second_pass(totals.kept_words, length, job.second_pass == 1):
            decoded = await asyncio.to_thread(self._decode, path, stream_index, 0, length, expected_ms=length)
            if decoded.reason is not None:
                return await self._skip(job, decoded.reason, duration_ms, chunks)
            code, windows = await asyncio.to_thread(engine.ask, decoded.pcm, 0, True)
            if code != child.OK:
                return await self._engine_failed(job, code, duration_ms, chunks)
            # The same audio heard again: words and drops count, the speech of the first pass stays.
            again = take(windows, 0, None, count_speech=False)
            taken = Taken(again.words, again.counters, start)
            if not await self._commit(job, prov, taken, second_pass=True):
                return await self._end_stale(job, chunks)
            chunks += 1
            totals = _add(totals, taken.counters)
        verdict = file_verdict(
            totals.kept_words, totals.drop_script, totals.drop_language, totals.drop_conf, totals.speech_ms, length
        )
        done = await run_locked(self._services, lambda: store.finish_preview(job, verdict))
        if not done:
            return PreviewStep(PreviewOutcome.STALE, job.media_id, None, chunks)
        if verdict == TRANSCRIPT:
            return PreviewStep(PreviewOutcome.COMPLETE, job.media_id, None, chunks)
        return PreviewStep(PreviewOutcome.SKIPPED, job.media_id, verdict, chunks)

    async def run_forever(
        self,
        *,
        idle: float = IDLE_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rounds: int | None = None,
    ) -> None:
        """Step while the PHP app is there and the models are ready; otherwise every ``idle`` seconds.

        The admin settings are taken at the start and then every
        SETTINGS_REFRESH_SECONDS, before the next step.
        """
        await self.prepare()
        done = 0
        next_sync: float | None = None
        while rounds is None or done < rounds:
            done += 1
            if next_sync is None or self._clock() >= next_sync:
                await self.sync_limits(self._read_settings)
                next_sync = self._clock() + SETTINGS_REFRESH_SECONDS
            step = _IDLE
            if companion.current().state == companion.OK and procure.models_ready():
                try:
                    step = await self.run_once()
                except Exception as exc:  # the loop must outlive any single step
                    LOGGER.exception("preview step failed", extra={"error_type": type(exc).__name__})
            if step.outcome == PreviewOutcome.IDLE:
                await sleep(idle)
            else:
                LOGGER.info(
                    "preview step",
                    extra={
                        "media_id": step.media_id,
                        "outcome": step.outcome.value,
                        "reason": step.reason,
                        "chunks": step.chunks,
                    },
                )


async def run_forever(services: Services) -> None:
    """The background task of main.py; it works only once the models are ready."""
    await Preview(services).run_forever()
