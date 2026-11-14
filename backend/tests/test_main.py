"""The AppAPI contract of the application: lifecycle routes, auth, shutdown."""

import asyncio
import hashlib
import logging
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend import config, main, nc, settings
from audio_video_search_backend.models import catalog, procure
from tests.conftest import signed_headers


def _paths(test_client: TestClient) -> list[str]:
    return [getattr(route, "path", "") for route in test_client.app.routes]  # pyright: ignore[reportAttributeAccessIssue]


def test_heartbeat_answers_without_authentication(client: TestClient) -> None:
    # AppAPI and the Docker HEALTHCHECK call it without a signature.
    response = client.get("/heartbeat")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_lifecycle_routes_exist_once(client: TestClient) -> None:
    paths = _paths(client)

    for path in ("/heartbeat", "/init", "/enabled"):
        assert paths.count(path) == 1, path


def test_entering_the_lifespan_twice_registers_the_routes_once() -> None:
    with TestClient(main.APP):
        pass
    with TestClient(main.APP) as second:
        assert _paths(second).count("/enabled") == 1


def test_an_unsigned_request_is_refused(client: TestClient) -> None:
    assert client.get("/status").status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        signed_headers(secret="wrong"),  # noqa: S106 - a deliberately wrong test value
        signed_headers(app_id="another_app"),
        {key: value for key, value in signed_headers().items() if key != "EX-APP-VERSION"},
    ],
    ids=["wrong secret", "foreign app id", "no version header"],
)
def test_a_badly_signed_request_is_refused(client: TestClient, headers: dict[str, str]) -> None:
    assert client.get("/status", headers=headers).status_code == 401


def test_a_signed_status_request_answers_with_versions_state_and_settings(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def saved(_nc: object) -> dict[str, str]:
        return {"processing_enabled": "0", "max_duration_hours": "12"}

    monkeypatch.setattr(settings, "read", saved)

    response = client.get("/status", headers=signed_headers())

    assert response.status_code == 200
    # The fields of plan 01-08 sit next to the ones of the walking skeleton;
    # tests/test_handshake.py holds how each of them is made.
    assert response.json() == {
        "app_id": "audio_video_search_backend",
        "version": "0.1.0",
        "appVersion": "0.1.0",
        "companion": "ok",
        "companionVersion": "0.1.0",
        "schemaVersion": 3,
        "sampleCount": 0,
        "settings": {"processing_enabled": "0", "max_duration_hours": "12"},
    }


def test_init_acknowledges_at_once_and_prepares_the_models(monkeypatch: pytest.MonkeyPatch) -> None:
    roots: list[Path] = []

    async def prepared(root: Path) -> bool:
        roots.append(root)
        return True

    monkeypatch.setattr(main, "prepare_models", prepared)

    with TestClient(main.APP) as test_client:
        response = test_client.post("/init", headers=signed_headers())

    assert response.status_code == 200
    assert response.json() == {}
    # The shutdown waits for the background task, so it ran by now.
    assert roots == [config.storage_root()]


def test_init_is_signed_like_every_other_route(client: TestClient) -> None:
    assert client.post("/init").status_code == 401


def test_nc_py_api_does_not_fetch_models_on_init(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Positive control of default_init=False: nc_py_api's own task is never reached.
    calls: list[object] = []
    monkeypatch.setattr("nc_py_api.ex_app.integration_fastapi.fetch_models_task", lambda *args: calls.append(args))
    monkeypatch.setattr(main, "prepare_models", _never_ready)

    assert client.post("/init", headers=signed_headers()).status_code == 200
    assert calls == []


async def _never_ready(_root: Path) -> bool:
    return False


# ---------------------------------------------------------------------------
# The models on /init and after a restart (plan 03-07)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def models_not_ready() -> Iterator[None]:
    procure.mark_ready(False)
    yield
    procure.mark_ready(False)


@pytest.fixture
def statuses(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    seen: list[tuple[int, str]] = []

    async def report(progress: int, error: str = "") -> bool:
        seen.append((progress, error))
        return True

    monkeypatch.setattr(nc, "report_init_status", report)
    return seen


def _fake_procure(outcomes: dict[str, str], calls: list[tuple[str, object]]) -> Any:
    async def fake(root: Path, name: str, *, fetch: object = "default", progress: Any = None) -> str:
        del root
        calls.append((name, fetch))
        size = catalog.model_bytes(name)
        if progress is not None:
            for part in (size // 4, size // 2, size):
                await progress(part)
        return outcomes[name]

    return fake


async def test_init_reports_rising_progress_up_to_100_and_sets_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, statuses: list[tuple[int, str]]
) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        procure, "procure", _fake_procure({"silero": procure.PRESENT, "parakeet": procure.PROCURED}, calls)
    )

    assert await main.prepare_models(tmp_path) is True

    progress = [value for value, _error in statuses]
    assert progress[0] == 0
    assert progress[-1] == 100
    assert progress == sorted(set(progress))  # strictly rising, no repeats
    assert max(progress[:-1]) == 99
    assert len(progress) > 3
    assert all(error == "" for _value, error in statuses)
    assert [name for name, _fetch in calls] == ["silero", "parakeet"]
    assert procure.models_ready() is True


async def test_a_wrong_digest_reports_models_failed_and_stays_not_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, statuses: list[tuple[int, str]]
) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        procure, "procure", _fake_procure({"silero": procure.PRESENT, "parakeet": procure.WRONG_DIGEST}, calls)
    )

    assert await main.prepare_models(tmp_path) is False

    assert statuses[-1][1] == main.MODELS_FAILED
    assert all(value < 100 for value, _error in statuses)
    assert procure.models_ready() is False


async def test_a_failing_first_model_stops_before_the_second(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, statuses: list[tuple[int, str]]
) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        procure, "procure", _fake_procure({"silero": procure.UNAVAILABLE, "parakeet": procure.PROCURED}, calls)
    )

    assert await main.prepare_models(tmp_path) is False
    assert [name for name, _fetch in calls] == ["silero"]
    assert statuses[-1] == (statuses[-1][0], main.MODELS_FAILED)


def test_models_failed_is_the_approved_text() -> None:
    # 03-01-SUMMARY.md, owner approval 14.11.2026, written out independently here.
    approved = "Audio & Video Search could not download its speech models. Details are in the log of the ExApp."
    assert approved == main.MODELS_FAILED


def _place_small_models(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name, payload in (("silero", b"vad " * 64), ("parakeet", b"asr " * 256)):
        entry = catalog.ModelFile(
            name=f"{name}.onnx",
            url=f"https://huggingface.co/x/{name}.onnx",
            sha256=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
        )
        monkeypatch.setitem(catalog.MODELS, name, (entry,))
        directory = procure.model_dir(root, name)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / entry.name).write_bytes(payload)


def _spy_procure(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    real = procure.procure
    fetches: list[object] = []

    async def spy(root: Path, name: str, **kwargs: Any) -> str:
        fetches.append(kwargs.get("fetch", "default"))
        return await real(root, name, **kwargs)

    monkeypatch.setattr(procure, "procure", spy)
    return fetches


def test_a_restart_with_the_files_present_is_ready_without_a_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    _place_small_models(config.storage_root(), monkeypatch)
    fetches = _spy_procure(monkeypatch)

    with TestClient(main.APP):
        pass

    assert fetches == [None, None]
    assert procure.models_ready() is True


def test_a_restart_without_the_files_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    # Control of the test above: the same start on an empty volume.
    fetches = _spy_procure(monkeypatch)

    with TestClient(main.APP):
        pass

    assert fetches == [None]  # silero is missing, parakeet is not even looked at
    assert procure.models_ready() is False


def test_the_enabled_route_reaches_the_handler(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def register(_nc: object) -> None:
        calls.append("register")

    monkeypatch.setattr(settings, "register", register)

    response = client.put("/enabled?enabled=1", headers=signed_headers())

    assert response.status_code == 200
    assert response.json() == {"error": ""}
    assert calls == ["register"]


class _FakeSettingsApi:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.registered: list[Any] = []
        self.unregistered: list[str] = []

    async def register_form(self, form: Any) -> None:
        if self.fail:
            raise RuntimeError("nextcloud is down")
        self.registered.append(form)

    async def unregister_form(self, form_id: str) -> None:
        self.unregistered.append(form_id)


def _fake_nc(api: _FakeSettingsApi) -> Any:
    return SimpleNamespace(ui=SimpleNamespace(settings=api))


async def test_enabling_registers_the_form_and_disabling_removes_it() -> None:
    api = _FakeSettingsApi()

    assert await main.enabled_handler(True, _fake_nc(api)) == ""
    assert await main.enabled_handler(False, _fake_nc(api)) == ""

    assert [form.id for form in api.registered] == [settings.FORM_ID]
    assert api.unregistered == [settings.FORM_ID]


async def test_a_failing_enable_returns_a_message_and_logs_the_type(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)

    answer = await main.enabled_handler(True, _fake_nc(_FakeSettingsApi(fail=True)))

    assert answer == main.ENABLE_FAILED
    assert any(getattr(record, "error_type", "") == "RuntimeError" for record in caplog.records)


async def test_shutdown_lets_a_short_task_finish_and_cancels_a_hanging_one() -> None:
    finished: list[str] = []

    async def short() -> None:
        await asyncio.sleep(0)
        finished.append("short")

    async def hanging() -> None:
        await asyncio.Event().wait()

    main.start_background(short(), "short")
    main.start_background(hanging(), "hanging")

    cancelled = await main.stop_background(deadline=0.05)

    assert finished == ["short"]
    assert cancelled == 1
    assert await main.stop_background() == 0


def test_main_refuses_to_start_without_a_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_PORT")

    with pytest.raises(SystemExit, match="APP_PORT"):
        main.main()


def test_main_hands_uvicorn_the_graceful_shutdown_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run_app(target: str, **kwargs: Any) -> None:
        seen["target"] = target
        seen.update(kwargs)

    monkeypatch.setattr(main, "run_app", fake_run_app)

    main.main()

    assert seen["target"] == "audio_video_search_backend.main:APP"
    assert seen["timeout_graceful_shutdown"] < 10
    assert seen["log_config"] is None


def test_the_lifespan_starts_the_intake_with_the_services(monkeypatch: pytest.MonkeyPatch) -> None:
    from audio_video_search_backend.api import Services
    from audio_video_search_backend.worker import intake

    started: list[object] = []

    async def record(services: object) -> None:
        started.append(services)

    monkeypatch.setattr(intake, "run_forever", record)
    with TestClient(main.APP):
        pass

    assert len(started) == 1
    assert isinstance(started[0], Services)


def test_the_lifespan_starts_the_capture_with_the_services(monkeypatch: pytest.MonkeyPatch) -> None:
    from audio_video_search_backend.api import Services
    from audio_video_search_backend.worker import capture

    started: list[object] = []

    async def record(services: object) -> None:
        started.append(services)

    monkeypatch.setattr(capture, "run_forever", record)
    with TestClient(main.APP):
        pass

    assert len(started) == 1
    assert isinstance(started[0], Services)
