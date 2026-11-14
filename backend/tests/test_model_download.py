"""nc.fetch_model_asset against a mock transport: hosts, schemes, sizes, headers (plan 03-07)."""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from audio_video_search_backend import nc

ALLOWED = frozenset({"huggingface.co", "us.aws.cdn.hf.co"})
START = "https://huggingface.co/repo/resolve/abc/model.onnx"
CDN = "https://us.aws.cdn.hf.co/xet-bridge-us/blob?Signature=x"
BODY = b"0123456789" * 1000

Handler = Callable[[httpx.Request], httpx.Response]


class Recorder:
    """A mock transport that answers by URL and keeps every request it saw."""

    def __init__(self, routes: dict[str, httpx.Response]) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.routes.get(str(request.url), httpx.Response(404))

    def hosts(self) -> list[str]:
        return [request.url.host for request in self.requests]


def _client(recorder: Recorder, **kwargs: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(recorder),
        follow_redirects=False,
        headers={"User-Agent": nc.model_user_agent(), "Accept-Encoding": "identity"},
        **kwargs,  # pyright: ignore[reportArgumentType]
    )


def _redirect(location: str, status: int = 302) -> httpx.Response:
    return httpx.Response(status, headers={"Location": location})


async def _fetch(recorder: Recorder, dest: Path, *, expected_size: int = len(BODY), **kwargs: object) -> str:
    async with _client(recorder, **kwargs) as client:
        return await nc.fetch_model_asset(
            START, dest, expected_size=expected_size, allowed_hosts=ALLOWED, client=client
        )


async def test_a_redirect_to_an_allowed_host_downloads(tmp_path: Path) -> None:
    recorder = Recorder({START: _redirect(CDN), CDN: httpx.Response(200, content=BODY)})
    dest = tmp_path / "model.onnx.part"
    seen: list[bytes] = []

    async def observe(chunk: bytes) -> None:
        seen.append(chunk)

    async with _client(recorder) as client:
        code = await nc.fetch_model_asset(
            START, dest, expected_size=len(BODY), allowed_hosts=ALLOWED, client=client, on_chunk=observe
        )

    assert code == nc.MODEL_FETCHED
    assert dest.read_bytes() == BODY
    assert b"".join(seen) == BODY
    assert recorder.hosts() == ["huggingface.co", "us.aws.cdn.hf.co"]


async def test_a_relative_redirect_stays_on_the_host(tmp_path: Path) -> None:
    # tokens.txt: huggingface.co answers 307 with a path on itself.
    target = "https://huggingface.co/api/resolve-cache/models/repo/abc/tokens.txt"
    recorder = Recorder(
        {
            START: _redirect("/api/resolve-cache/models/repo/abc/tokens.txt", 307),
            target: httpx.Response(200, content=BODY),
        }
    )

    assert await _fetch(recorder, tmp_path / "t.part") == nc.MODEL_FETCHED
    assert recorder.hosts() == ["huggingface.co", "huggingface.co"]


async def test_a_redirect_to_a_foreign_host_asks_nothing_there_and_leaves_no_file(tmp_path: Path) -> None:
    foreign = "https://evil.example.org/model.onnx"
    recorder = Recorder({START: _redirect(foreign), foreign: httpx.Response(200, content=BODY)})
    dest = tmp_path / "model.onnx.part"

    assert await _fetch(recorder, dest) == nc.MODEL_FOREIGN_HOST
    assert not dest.exists()
    assert recorder.hosts() == ["huggingface.co"]


async def test_a_lookalike_host_is_foreign(tmp_path: Path) -> None:
    lookalike = "https://us.aws.cdn.hf.co.evil.example.org/blob"
    recorder = Recorder({START: _redirect(lookalike)})

    assert await _fetch(recorder, tmp_path / "m.part") == nc.MODEL_FOREIGN_HOST
    assert recorder.hosts() == ["huggingface.co"]


async def test_a_redirect_to_plain_http_is_refused(tmp_path: Path) -> None:
    plain = "http://us.aws.cdn.hf.co/xet-bridge-us/blob"
    recorder = Recorder({START: _redirect(plain), plain: httpx.Response(200, content=BODY)})
    dest = tmp_path / "model.onnx.part"

    assert await _fetch(recorder, dest) == nc.MODEL_FOREIGN_HOST
    assert not dest.exists()
    assert recorder.hosts() == ["huggingface.co"]


async def test_a_start_url_outside_the_list_sends_no_request(tmp_path: Path) -> None:
    recorder = Recorder({})
    async with _client(recorder) as client:
        code = await nc.fetch_model_asset(
            "https://example.org/x", tmp_path / "x.part", expected_size=1, allowed_hosts=ALLOWED, client=client
        )

    assert code == nc.MODEL_FOREIGN_HOST
    assert recorder.requests == []


async def test_a_larger_answer_is_too_large_without_a_file(tmp_path: Path) -> None:
    recorder = Recorder({START: _redirect(CDN), CDN: httpx.Response(200, content=BODY + b"!")})
    dest = tmp_path / "model.onnx.part"

    assert await _fetch(recorder, dest) == nc.MODEL_TOO_LARGE
    assert not dest.exists()


async def test_a_larger_stream_without_length_is_too_large(tmp_path: Path) -> None:
    async def body():
        yield BODY
        yield b"more"

    recorder = Recorder({START: httpx.Response(200, content=body())})
    dest = tmp_path / "model.onnx.part"

    assert await _fetch(recorder, dest) == nc.MODEL_TOO_LARGE
    assert not dest.exists()


async def test_a_short_answer_is_network_without_a_file(tmp_path: Path) -> None:
    async def body():
        yield BODY[:-1]

    recorder = Recorder({START: httpx.Response(200, content=body())})
    dest = tmp_path / "model.onnx.part"

    assert await _fetch(recorder, dest) == nc.MODEL_NETWORK
    assert not dest.exists()


@pytest.mark.parametrize("status", [403, 404, 500])
async def test_an_error_status_is_http_error(tmp_path: Path, status: int) -> None:
    recorder = Recorder({START: _redirect(CDN), CDN: httpx.Response(status, content=b"page")})
    dest = tmp_path / "model.onnx.part"

    assert await _fetch(recorder, dest) == nc.MODEL_HTTP_ERROR
    assert not dest.exists()


async def test_a_redirect_loop_ends(tmp_path: Path) -> None:
    recorder = Recorder({START: _redirect(START)})

    assert await _fetch(recorder, tmp_path / "m.part") == nc.MODEL_HTTP_ERROR
    assert len(recorder.requests) == nc.MODEL_MAX_REDIRECTS + 1


async def test_a_transport_error_is_network(tmp_path: Path) -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as client:
        code = await nc.fetch_model_asset(
            START, tmp_path / "m.part", expected_size=1, allowed_hosts=ALLOWED, client=client
        )

    assert code == nc.MODEL_NETWORK


# ---------------------------------------------------------------------------
# What leaves the container: no credential, no cookie, a neutral user agent.
# ---------------------------------------------------------------------------

FORBIDDEN_HEADERS = ("authorization", "cookie", "authorization-app-api", "ex-app-id")


def leaked_headers(requests: list[httpx.Request]) -> list[str]:
    """The headers of FORBIDDEN_HEADERS any request carried."""
    return [name for request in requests for name in FORBIDDEN_HEADERS if name in request.headers]


async def test_no_request_carries_a_credential_or_a_cookie(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The environment holds the AppAPI secret (conftest); none of it may travel.
    # The first hop sets a cookie and sends the client back to its own host, so
    # a client that kept its jar would send it along.
    cache = "https://huggingface.co/api/resolve-cache/model.onnx"
    redirect = httpx.Response(
        307, headers={"Location": "/api/resolve-cache/model.onnx", "Set-Cookie": "session=abc; Path=/"}
    )
    recorder = Recorder({START: redirect, cache: httpx.Response(200, content=BODY)})
    monkeypatch.setattr(nc, "new_model_client", lambda: _client(recorder))

    assert await nc.fetch_model_asset(START, tmp_path / "m.part", expected_size=len(BODY), allowed_hosts=ALLOWED) == (
        nc.MODEL_FETCHED
    )
    assert len(recorder.requests) == 2
    assert leaked_headers(recorder.requests) == []
    for request in recorder.requests:
        assert request.headers["user-agent"].startswith("audio_video_search_backend/")


async def test_the_header_check_fires_on_a_planted_header() -> None:
    # Positive control: the same check finds the headers when a test sets them on purpose.
    recorder = Recorder({START: httpx.Response(200, content=BODY)})

    async with _client(recorder) as client:
        await client.get(START, headers={"Authorization": "Bearer planted", "Cookie": "session=abc"})

    assert leaked_headers(recorder.requests) == ["authorization", "cookie"]


async def test_the_real_client_sends_only_the_neutral_headers() -> None:
    async with nc.new_model_client() as client:
        assert client.follow_redirects is False
        assert client.headers["user-agent"] == "audio_video_search_backend/0.1.0"
        assert client.headers["accept-encoding"] == "identity"
        assert "authorization" not in client.headers
        assert len(client.cookies) == 0
