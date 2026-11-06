"""Configuration out of the environment, read once per call and never cached.

AppAPI sets APP_ID, APP_SECRET, APP_VERSION, APP_PORT, NEXTCLOUD_URL and, behind
HaRP, HP_SHARED_KEY and HP_EXAPP_SOCK. Everything the admin may change is an
<environment-variables> entry of appinfo/info.xml with the prefix AVS_.
An unknown or broken value falls back to the default with a warning, it never
stops the container: a typo in a deploy option must not cost the admin the app.
"""

import os
from typing import Final

KNOWN_LOG_LEVELS: Final = frozenset({"debug", "info", "warning", "error"})
# Short on purpose: AVS_ instead of AUDIO_VIDEO_SEARCH_BACKEND_, one prefix for
# every admin variable of the backend.
ENV_PREFIX: Final = "AVS_"
LOG_LEVEL_VARIABLE: Final = f"{ENV_PREFIX}LOG_LEVEL"
DEFAULT_LOG_LEVEL: Final = "info"

# How long uvicorn waits for running requests after SIGTERM before it closes
# them. Docker sends SIGKILL after 10 seconds by default, so this stays below.
GRACEFUL_SHUTDOWN_SECONDS: Final = 8


def log_level() -> str:
    """The configured log level, falling back to info on anything unknown."""
    level = os.environ.get(LOG_LEVEL_VARIABLE, DEFAULT_LOG_LEVEL).strip().lower()
    return level if level in KNOWN_LOG_LEVELS else DEFAULT_LOG_LEVEL


def app_version() -> str:
    """The version AppAPI deployed, as it announced it to the container."""
    return os.environ.get("APP_VERSION", "unknown")


def behind_harp() -> bool:
    """True when the container talks to Nextcloud through HaRP (unix socket plus frpc)."""
    return bool(os.environ.get("HP_SHARED_KEY"))


def binding_mode() -> str:
    """Where the server listens, without secrets."""
    if behind_harp():
        return f"unix socket {os.environ.get('HP_EXAPP_SOCK', '/tmp/exapp.sock')} (HaRP)"  # noqa: S108
    return f"tcp {os.environ.get('APP_HOST', '127.0.0.1')}:{os.environ.get('APP_PORT', 'unset')}"


def unusable_startup_variables() -> list[str]:
    """The variables that keep the process from starting, named before uvicorn fails on them.

    Only APP_PORT can be checked up front, and only without HaRP: nc_py_api reads
    it with int(environ[...]) and no default, which ends in a bare KeyError deep
    inside the library. APP_ID, APP_SECRET and NEXTCLOUD_URL are read per request,
    so a missing one is a failing request with a clear message instead.
    """
    if behind_harp():
        return []
    return [] if os.environ.get("APP_PORT", "").isdigit() else ["APP_PORT"]
