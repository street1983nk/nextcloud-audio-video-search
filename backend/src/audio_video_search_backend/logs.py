"""Structured logging: one JSON object per line on stdout.

Docker and the AppAPI log view keep stdout, and a JSON line can be filtered by
level or logger without a regular expression. Two rules from Findling:

- The HTTP client loggers (httpx, httpcore, niquests, urllib3) log every request
  line on INFO, and an OCS path can carry a user id or a file id. Outside debug
  they stand on WARNING.
- Never log a request body, a header or a secret. Pass ids and counts through
  ``extra=`` instead; this formatter copies them into the line.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Final

CLIENT_LOGGERS: Final = ("httpx", "httpcore", "niquests", "urllib3")

# The attributes every LogRecord carries. Anything else on a record came in
# through extra= and belongs in the line.
_STANDARD_ATTRIBUTES: Final = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys() | {"message", "asctime", "taskName"}
)


class JsonFormatter(logging.Formatter):
    """Format a record as one compact JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRIBUTES and not key.startswith("_"):
                line[key] = value if isinstance(value, str | int | float | bool | None) else repr(value)
        if record.exc_info:
            line["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            line["exc"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False)


def configure(level: str) -> None:
    """Route the root logger through the JSON formatter, idempotent per process."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers[:] = []
        uvicorn_logger.propagate = True
    if level != "debug":
        for name in CLIENT_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
