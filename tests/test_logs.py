"""Structured logging: JSON lines, extras carried, client loggers quiet."""

import io
import json
import logging
import sys

import pytest

from audio_video_search import logs


def _line(record: logging.LogRecord) -> dict[str, object]:
    return json.loads(logs.JsonFormatter().format(record))


def test_a_record_becomes_one_json_object_with_its_extras() -> None:
    record = logging.LogRecord("audio_video_search", logging.INFO, __file__, 1, "processed %d files", (3,), None)
    record.job_id = "j-1"
    record.size = 12.5

    line = _line(record)

    assert line["level"] == "info"
    assert line["logger"] == "audio_video_search"
    assert line["msg"] == "processed 3 files"
    assert line["job_id"] == "j-1"
    assert line["size"] == 12.5
    assert str(line["ts"]).endswith("+00:00")


def test_a_non_scalar_extra_is_written_as_its_repr() -> None:
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "m", None, None)
    record.items = [1, 2]

    assert _line(record)["items"] == "[1, 2]"


def test_an_exception_carries_its_type() -> None:
    try:
        raise ValueError("broken")
    except ValueError:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())

    line = _line(record)

    assert line["exc_type"] == "ValueError"
    assert "broken" in str(line["exc"])


@pytest.mark.parametrize(("level", "client_level"), [("info", logging.WARNING), ("debug", logging.NOTSET)])
def test_configure_quiets_the_http_client_outside_debug(level: str, client_level: int) -> None:
    for name in logs.CLIENT_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)

    logs.configure(level)

    assert logging.getLogger("httpx").level == client_level
    assert len(logging.getLogger().handlers) == 1
    assert isinstance(logging.getLogger().handlers[0].formatter, logs.JsonFormatter)


def test_configure_writes_to_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer = io.StringIO()
    monkeypatch.setattr("sys.stdout", buffer)

    logs.configure("info")
    logging.getLogger("audio_video_search").info("hello", extra={"count": 2})

    line = json.loads(buffer.getvalue().strip().splitlines()[-1])
    assert line["msg"] == "hello"
    assert line["count"] == 2
