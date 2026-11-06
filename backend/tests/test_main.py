"""The AppAPI contract of the application: lifecycle routes, auth, shutdown."""

import asyncio
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend import main, settings
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
        return {"processing_enabled": "0", "max_file_size_mb": "100"}

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
        "schemaVersion": 1,
        "sampleCount": 0,
        "settings": {"processing_enabled": "0", "max_file_size_mb": "100"},
    }


def test_init_acknowledges_at_once(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # The default /init hands the work to a background task that reports progress
    # to Nextcloud; the test holds only the immediate answer.
    monkeypatch.setattr("nc_py_api.ex_app.integration_fastapi.fetch_models_task", lambda *_args: None)

    response = client.post("/init", headers=signed_headers())

    assert response.status_code == 200
    assert response.json() == {}


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
