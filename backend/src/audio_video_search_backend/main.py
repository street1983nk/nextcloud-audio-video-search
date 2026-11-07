"""Entry point: FastAPI application, AppAPI lifecycle, graceful shutdown.

The routes AppAPI expects come from nc_py_api's ``set_handlers``:

- ``GET /heartbeat`` answers ``{"status": "ok"}`` without authentication. It is
  the health probe of AppAPI and of the Docker HEALTHCHECK (docker/healthcheck.sh).
- ``POST /init`` acknowledges at once; an app that has to fetch models or build
  an index reports progress from a background task instead of blocking here.
- ``PUT /enabled?enabled=0|1`` calls ``enabled_handler``. It has to be a
  coroutine: a synchronous handler is deprecated in nc-py-api 0.30.x and gone
  in 0.31.0, and pyproject.toml turns that warning into a test failure.

Every other route passes ``AppAPIAuthMiddleware``: it checks EX-APP-ID against
APP_ID, requires EX-APP-VERSION and compares the secret inside
AUTHORIZATION-APP-API with APP_SECRET, and answers 401 otherwise. The user id
comes from that header alone and never from a request body.

Graceful shutdown: uvicorn turns SIGTERM into the end of the lifespan. The
``finally`` block below cancels the background tasks with a deadline below the
ten seconds Docker waits before SIGKILL.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from typing import Any, Final

from fastapi import FastAPI

from audio_video_search_backend import APP_ID, companion, config, logs, settings
from audio_video_search_backend.api import Services, build_router
from audio_video_search_backend.index.publish import SearchIndex
from audio_video_search_backend.nc import AppAPIAuthMiddleware, AsyncNextcloudApp, run_app, set_handlers
from audio_video_search_backend.store.repo import Store
from audio_video_search_backend.worker import capture, intake

LOGGER = logging.getLogger(APP_ID)

# What AppAPI shows the admin when enabling fails. The detail goes to the log.
ENABLE_FAILED: Final = "Audio & Video Search could not register its settings page. Details are in the log of the ExApp."

# How long the shutdown waits for background tasks before it cancels them.
TASK_STOP_SECONDS: Final = 5.0

# Strong references to background tasks, otherwise the event loop may drop them.
_TASKS: set[asyncio.Task[None]] = set()


def start_background(coroutine: Coroutine[Any, Any, None], name: str) -> asyncio.Task[None]:
    """Start a task that the shutdown waits for and, after the deadline, cancels."""
    task = asyncio.get_running_loop().create_task(coroutine, name=name)
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task


async def stop_background(deadline: float = TASK_STOP_SECONDS) -> int:
    """Wait for every background task up to the deadline, cancel the rest; returns how many were cancelled."""
    pending = list(_TASKS)
    if not pending:
        return 0
    _, still_running = await asyncio.wait(pending, timeout=deadline)
    for task in still_running:
        task.cancel()
    await asyncio.gather(*still_running, return_exceptions=True)
    return len(still_running)


async def enabled_handler(enabled: bool, nc: AsyncNextcloudApp) -> str:
    """Register or remove the settings page. An empty string is success for AppAPI."""
    try:
        if enabled:
            await settings.register(nc)
        else:
            await settings.unregister(nc)
    except Exception as exc:
        LOGGER.exception("enable handler failed", extra={"enabled": enabled, "error_type": type(exc).__name__})
        return ENABLE_FAILED
    LOGGER.info("app %s", "enabled" if enabled else "disabled")
    return ""


def open_services() -> Services:
    """Open the store at <volume>/state.db and the index under <volume>/index.

    A missing index directory or a changed version mark rebuilds the index from
    SQLite here (index/publish.py ``open_generation``); that is the only slow
    part, and it runs in a worker thread.
    """
    root = config.storage_root()
    root.mkdir(parents=True, exist_ok=True)
    store = Store.open(root / "state.db")
    try:
        index = SearchIndex.open_generation(root / "index", store)
    except BaseException:
        store.close()
        raise
    return Services(store=store, index=index)


async def reconcile(services: Services) -> None:
    """Work off the index outbox and delete orphans, under the services lock."""

    def locked() -> int:
        with services.lock:
            return services.index.reconcile(services.store)

    try:
        touched = await asyncio.to_thread(locked)
    except Exception as exc:
        LOGGER.exception("reconcile failed", extra={"error_type": type(exc).__name__})
        return
    LOGGER.info("reconcile done", extra={"media": touched})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Configure logging, register the AppAPI routes once, open store and index, stop in order."""
    logs.configure(config.log_level())
    # set_handlers adds routes to the application object, which outlives the
    # lifespan; a test suite that enters it twice would otherwise get two copies.
    if not getattr(app.state, "handlers_registered", False):
        set_handlers(app, enabled_handler)  # pyright: ignore[reportArgumentType]
        app.state.handlers_registered = True
    LOGGER.info("starting", extra={"version": config.app_version(), "binding": config.binding_mode()})
    services = await asyncio.to_thread(open_services)
    app.state.services = services
    start_background(reconcile(services), "reconcile")
    # Is the PHP app there? Asked now and every five minutes (companion.py).
    checker = start_background(companion.run_periodic(), "companion")
    # The PHP work stock: claimed only while the companion state is ok, so not
    # before AppAPI enabled this container (worker/intake.py).
    intake_task = start_background(intake.run_forever(services), "intake")
    # The capture: one full download per open reference, one at a time, also
    # only while the companion state is ok (worker/capture.py).
    capture_task = start_background(capture.run_forever(services), "capture")
    try:
        yield
    finally:
        # The loops never end on their own; they are cancelled instead of waited for.
        checker.cancel()
        intake_task.cancel()
        capture_task.cancel()
        cancelled = await stop_background()
        app.state.services = None
        await asyncio.to_thread(services.close)
        LOGGER.info("stopped", extra={"cancelled_tasks": cancelled})


APP = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
APP.add_middleware(AppAPIAuthMiddleware)
# /search, /excerpt, /sample, /sample/remove, /status; contract in api/__init__.py.
APP.include_router(build_router())


def main() -> None:
    """Start uvicorn the way AppAPI expects: unix socket behind HaRP, TCP otherwise."""
    unusable = config.unusable_startup_variables()
    if unusable:
        raise SystemExit(f"{APP_ID}: cannot start, missing or not a number: {', '.join(unusable)}")
    run_app(
        f"{APP_ID}.main:APP",
        log_level=config.log_level(),
        log_config=None,
        timeout_graceful_shutdown=config.GRACEFUL_SHUTDOWN_SECONDS,
    )


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        main()
