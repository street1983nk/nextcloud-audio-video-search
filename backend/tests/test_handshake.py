"""The other direction of the counterpart state (plan 01-08).

The container asks the PHP app for its handshake at the start and every five
minutes, reports the answer in /status and refuses /sample while the PHP half
is missing. ``nc.fetch_handshake`` is faked with a coroutine that plays back a
script of answers; the nc_py_api side of it is tested against a fake session.
"""

import asyncio
import hashlib
import logging
import time
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend import companion, main, nc, settings
from tests.conftest import signed_headers

CONTENT = b"RIFF fake media bytes " * 100
SHA = hashlib.sha256(CONTENT).hexdigest()
# The real function, taken before the autouse fixture of conftest replaces it.
REAL_FETCH_HANDSHAKE = nc.fetch_handshake


class Handshakes:
    """A scripted fetch_handshake; the last answer repeats."""

    def __init__(self, *answers: tuple[int | None, str | None]) -> None:
        self.answers = list(answers)
        self.calls = 0
        self.third_call = asyncio.Event()

    async def __call__(self) -> tuple[int | None, str | None]:
        self.calls += 1
        if self.calls >= 3:
            self.third_call.set()
        if len(self.answers) > 1:
            return self.answers.pop(0)
        return self.answers[0]


def _script(monkeypatch: pytest.MonkeyPatch, *answers: tuple[int | None, str | None]) -> Handshakes:
    script = Handshakes(*answers)
    monkeypatch.setattr(nc, "fetch_handshake", script)
    return script


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []

    async def fake(file_id: int, _user_id: str, *, max_bytes: int) -> nc.FetchResult:
        assert max_bytes > 0
        calls.append(file_id)
        return nc.FetchResult(sha256=SHA, size=len(CONTENT), error=None)

    monkeypatch.setattr(nc, "fetch_file_sha256", fake)
    return calls


@pytest.fixture
def api(gateway: list[int], monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The application without its periodic check, so every test decides when the PHP app is asked.

    Until a test hands in another script, the PHP app answers ok (conftest).
    """

    async def saved(_nc: object) -> dict[str, str]:
        return {"processing_enabled": "0"}

    async def no_periodic_check(interval_s: int = 300) -> None:
        assert interval_s > 0

    monkeypatch.setattr(settings, "read", saved)
    monkeypatch.setattr(companion, "run_periodic", no_periodic_check)
    with TestClient(main.APP) as test_client:
        yield test_client


def _sample(client: TestClient, file_id: int = 42) -> httpx.Response:
    return client.post("/sample", headers=signed_headers(), json={"fileId": file_id, "userId": "admin", "atMs": 0})


# -- check_once ---------------------------------------------------------------


async def test_a_valid_answer_is_ok_with_the_version(monkeypatch: pytest.MonkeyPatch) -> None:
    _script(monkeypatch, (200, "0.1.0"))

    state = await companion.check_once()

    assert (state.state, state.version) == ("ok", "0.1.0")
    assert state.checked_at is not None
    assert companion.current() == state


async def test_a_404_is_missing_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _script(monkeypatch, (404, None))

    state = await companion.check_once()

    assert (state.state, state.version) == ("missing", None)


async def test_a_network_failure_is_unknown_and_missing_after_three_in_a_row(monkeypatch: pytest.MonkeyPatch) -> None:
    _script(monkeypatch, (None, None))

    seen = [(await companion.check_once()).state for _ in range(4)]

    assert seen == ["unknown", "unknown", "missing", "missing"]


async def test_a_success_in_between_resets_the_failure_count(monkeypatch: pytest.MonkeyPatch) -> None:
    _script(monkeypatch, (None, None), (None, None), (200, "0.1.0"), (500, None), (None, None))

    seen = [(await companion.check_once()).state for _ in range(5)]

    assert seen == ["unknown", "unknown", "ok", "unknown", "unknown"]


@pytest.mark.parametrize("version", [None, "", "latest", "1", "0.1.0; rm -rf", "x" * 40])
async def test_an_answer_without_a_valid_version_is_unknown(
    monkeypatch: pytest.MonkeyPatch, version: str | None
) -> None:
    _script(monkeypatch, (200, version))

    state = await companion.check_once()

    assert (state.state, state.version) == ("unknown", None)


async def test_missing_is_logged_once_per_change_without_a_path(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=companion.__name__)
    _script(monkeypatch, (404, None), (404, None), (200, "0.1.0"), (404, None))

    for _ in range(4):
        await companion.check_once()

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 2
    for record in caplog.records:
        assert getattr(record, "companion", None) in {"ok", "missing", "unknown"}
        assert "/" not in record.getMessage()
        assert "handshake" not in str(record.__dict__.get("reason", ""))


async def test_a_412_before_appapi_enabled_the_container_is_unknown_and_never_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # At its start the container asks before AppAPI has enabled it; Nextcloud
    # answers 412 "ExApp is disabled". That says nothing about the PHP app.
    _script(monkeypatch, (412, None))

    seen = [(await companion.check_once()).state for _ in range(4)]

    assert seen == ["unknown"] * 4


async def test_status_asks_again_while_unknown_even_when_the_answer_is_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _script(monkeypatch, (412, None), (200, "0.1.0"))
    await companion.check_once()

    state = await companion.refresh_if_stale()

    assert (state.state, state.version, script.calls) == ("ok", "0.1.0", 2)


async def test_a_fresh_ok_is_not_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _script(monkeypatch, (200, "0.1.0"))
    await companion.check_once()

    await companion.refresh_if_stale()

    assert script.calls == 1


async def test_the_periodic_check_retries_soon_while_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _script(monkeypatch, (412, None), (412, None), (200, "0.1.0"))

    task = asyncio.create_task(companion.run_periodic(interval_s=3600, retry_s=0))
    await asyncio.wait_for(script.third_call.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert companion.current().state == "ok"


async def test_the_periodic_check_repeats_until_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _script(monkeypatch, (200, "0.1.0"))

    task = asyncio.create_task(companion.run_periodic(interval_s=0))
    await asyncio.wait_for(script.third_call.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert companion.current().state == "ok"


def test_the_lifespan_starts_the_check_and_stops_it_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _script(monkeypatch, (200, "0.1.0"))
    started = time.monotonic()

    with TestClient(main.APP):
        while script.calls == 0 and time.monotonic() - started < 5:
            time.sleep(0.01)

    assert script.calls >= 1
    assert companion.current().state == "ok"
    # The check sleeps five minutes between rounds; the shutdown cancels it
    # instead of waiting out the deadline for background tasks.
    assert time.monotonic() - started < main.TASK_STOP_SECONDS


# -- nc.fetch_handshake ------------------------------------------------------


class _FakeSession:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.paths: list[str] = []

    async def ocs(self, method: str, path: str, **_kwargs: Any) -> Any:
        assert method == "GET"
        self.paths.append(path)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def _fake_client(monkeypatch: pytest.MonkeyPatch, outcome: Any) -> _FakeSession:
    session = _FakeSession(outcome)
    monkeypatch.setattr(nc, "fetch_handshake", REAL_FETCH_HANDSHAKE)
    monkeypatch.setattr(nc, "AsyncNextcloudApp", lambda: SimpleNamespace(_session=session))
    return session


async def test_fetch_handshake_reads_the_version_from_the_ocs_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _fake_client(monkeypatch, {"companionVersion": "0.1.0"})

    assert await nc.fetch_handshake() == (200, "0.1.0")
    assert session.paths == ["/ocs/v2.php/apps/audio_video_search/api/v1/handshake"]


async def test_fetch_handshake_turns_an_odd_answer_into_no_version(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_client(monkeypatch, ["not", "a", "dict"])

    assert await nc.fetch_handshake() == (200, None)


async def test_fetch_handshake_returns_the_status_of_a_nextcloud_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_client(monkeypatch, nc.NextcloudException(404, reason="Not found"))

    assert await nc.fetch_handshake() == (404, None)


async def test_fetch_handshake_never_raises_on_a_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_client(monkeypatch, OSError("connection refused"))

    assert await nc.fetch_handshake() == (None, None)


# -- /status ------------------------------------------------------------------


def test_status_reports_the_fields_of_the_admin_section(api: TestClient) -> None:
    response = api.get("/status", headers=signed_headers())

    assert response.status_code == 200
    assert response.json() == {
        "app_id": "audio_video_search_backend",
        "version": "0.1.0",
        "appVersion": "0.1.0",
        "companion": "ok",
        "companionVersion": "0.1.0",
        "schemaVersion": 1,
        "sampleCount": 0,
        "settings": {"processing_enabled": "0"},
    }


def test_status_counts_the_samples(api: TestClient) -> None:
    assert _sample(api).json()["result"] == "published"

    assert api.get("/status", headers=signed_headers()).json()["sampleCount"] == 1


def test_status_shows_a_missing_companion(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _script(monkeypatch, (404, None))
    monkeypatch.setattr(companion, "STALE_SECONDS", 0.0)

    body = api.get("/status", headers=signed_headers()).json()

    assert (body["companion"], body["companionVersion"]) == ("missing", None)


def test_status_does_not_ask_again_while_the_state_is_fresh(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    api.get("/status", headers=signed_headers())
    script = _script(monkeypatch, (404, None))

    body = api.get("/status", headers=signed_headers()).json()

    assert script.calls == 0
    assert body["companion"] == "ok"


# -- /sample ------------------------------------------------------------------


def test_sample_is_refused_without_the_php_app(
    api: TestClient, gateway: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    _script(monkeypatch, (404, None))
    asyncio.run(companion.check_once())

    response = _sample(api)

    assert response.status_code == 200
    assert response.json() == {"error": "companion_missing"}
    assert gateway == []


def test_an_unknown_companion_is_checked_once_before_the_decision(
    api: TestClient, gateway: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    companion.reset()
    script = _script(monkeypatch, (404, None))

    response = _sample(api)

    assert script.calls == 1
    assert response.json() == {"error": "companion_missing"}
    assert gateway == []


def test_sample_works_once_the_check_says_ok(
    api: TestClient, gateway: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    companion.reset()
    script = _script(monkeypatch, (200, "0.1.0"))

    response = _sample(api)

    assert script.calls == 1
    assert response.json()["result"] == "published"
    assert gateway == [42]
