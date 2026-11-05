"""Environment parsing: broken values fall back, they never stop the container."""

import pytest

from audio_video_search import config


@pytest.mark.parametrize(("value", "expected"), [("DEBUG", "debug"), (" warning ", "warning"), ("loud", "info")])
def test_log_level_falls_back_to_info(monkeypatch: pytest.MonkeyPatch, value: str, expected: str) -> None:
    monkeypatch.setenv(config.LOG_LEVEL_VARIABLE, value)

    assert config.log_level() == expected


def test_binding_mode_names_the_socket_behind_harp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HP_SHARED_KEY", "not-a-real-key")
    monkeypatch.setenv("HP_EXAPP_SOCK", "/run/exapp.sock")

    assert config.binding_mode() == "unix socket /run/exapp.sock (HaRP)"
    assert "not-a-real-key" not in config.binding_mode()
    assert config.unusable_startup_variables() == []


def test_binding_mode_names_the_port_without_harp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_HOST", "0.0.0.0")  # noqa: S104

    assert config.binding_mode() == "tcp 0.0.0.0:23000"


def test_a_port_that_is_not_a_number_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PORT", "http")

    assert config.unusable_startup_variables() == ["APP_PORT"]


def test_the_version_is_the_one_appapi_announced(monkeypatch: pytest.MonkeyPatch) -> None:
    assert config.app_version() == "0.1.0"
    monkeypatch.delenv("APP_VERSION")
    assert config.app_version() == "unknown"


def test_the_shutdown_deadline_stays_under_the_docker_stop_timeout() -> None:
    assert 0 < config.GRACEFUL_SHUTDOWN_SECONDS < 10
