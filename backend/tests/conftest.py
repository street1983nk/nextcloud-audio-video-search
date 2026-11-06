"""Shared fixtures: the environment AppAPI would set, and signed request headers."""

import base64
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from audio_video_search_backend import APP_ID

if TYPE_CHECKING:
    from audio_video_search_backend.store.repo import Store

# backend/ holds the ExApp (package, Dockerfile, appinfo, l10n, pyproject);
# the repository root holds what both halves share (workflows, docs, READMEs).
BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
SECRET = "test-secret-not-real"  # noqa: S105 - a test value, never a real secret
VERSION = "0.1.0"


@pytest.fixture(autouse=True)
def appapi_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """What AppAPI hands every container, with values that are clearly not real."""
    monkeypatch.setenv("APP_ID", APP_ID)
    monkeypatch.setenv("APP_SECRET", SECRET)
    monkeypatch.setenv("APP_VERSION", VERSION)
    monkeypatch.setenv("APP_PORT", "23000")
    monkeypatch.setenv("NEXTCLOUD_URL", "http://nextcloud.invalid")
    monkeypatch.delenv("HP_SHARED_KEY", raising=False)


def signed_headers(user: str = "admin", secret: str = SECRET, app_id: str = APP_ID) -> dict[str, str]:
    """The three headers AppAPIAuthMiddleware checks."""
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {"EX-APP-ID": app_id, "EX-APP-VERSION": VERSION, "AUTHORIZATION-APP-API": token, "AA-VERSION": "32.0.0"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    """The application with its lifespan entered."""
    from audio_video_search_backend.main import APP

    with TestClient(APP) as test_client:
        yield test_client


@pytest.fixture
def store(tmp_path: Path) -> Iterator["Store"]:
    """A fresh operating state in a temporary directory."""
    from audio_video_search_backend.store.repo import Store

    opened = Store.open(tmp_path / "state.db")
    try:
        yield opened
    finally:
        opened.close()
