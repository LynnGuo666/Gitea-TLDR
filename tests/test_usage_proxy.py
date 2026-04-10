from __future__ import annotations

import asyncio
import gzip
import json
import logging
import sys
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core import settings
from app.services.providers.claude_code import ClaudeCodeProvider
from app.services.providers.usage_proxy import UsageCapturingProxy


class FakeReader:
    def __init__(self, payload: bytes):
        self._buffer = bytearray(payload)

    async def readline(self) -> bytes:
        if not self._buffer:
            return b""
        newline_index = self._buffer.find(b"\n")
        if newline_index == -1:
            line = bytes(self._buffer)
            self._buffer.clear()
            return line
        line = bytes(self._buffer[: newline_index + 1])
        del self._buffer[: newline_index + 1]
        return line

    async def readexactly(self, size: int) -> bytes:
        if len(self._buffer) < size:
            partial = bytes(self._buffer)
            self._buffer.clear()
            raise asyncio.IncompleteReadError(partial=partial, expected=size)
        chunk = bytes(self._buffer[:size])
        del self._buffer[:size]
        return chunk


class FakeWriter:
    def __init__(self):
        self.buffer = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None

    def get_extra_info(self, name: str):
        if name == "peername":
            return ("127.0.0.1", 12345)
        return None


class FakeStreamingResponse:
    def __init__(self, chunks: list[bytes], headers: dict[str, str] | None = None):
        self.status_code = 200
        merged_headers = {
            "content-type": "text/event-stream",
            "cache-control": "no-cache",
        }
        if headers:
            merged_headers.update(headers)
        self.headers = httpx.Headers(merged_headers)
        self._chunks = chunks

    async def aiter_raw(self):
        for chunk in self._chunks:
            yield chunk


class FakeStreamContext:
    def __init__(self, response: FakeStreamingResponse):
        self._response = response

    async def __aenter__(self) -> FakeStreamingResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeClient:
    def __init__(self, response: FakeStreamingResponse):
        self._response = response

    def stream(self, method: str, url: str, headers=None, content=None):
        return FakeStreamContext(self._response)


class FakeJSONResponse:
    def __init__(self, payload: dict):
        self.status_code = 200
        self.headers = httpx.Headers({"content-type": "application/json"})
        self.content = json.dumps(payload).encode("utf-8")


class FakeRequestClient:
    def __init__(self, response: FakeJSONResponse):
        self._response = response

    async def request(self, method: str, url: str, headers=None, content=None):
        del method, url, headers, content
        return self._response


async def _read_http_request(
    reader: asyncio.StreamReader,
) -> tuple[str, str, str, dict[str, str], bytes]:
    request_line = await reader.readline()
    if not request_line:
        return "", "", "", {}, b""

    parts = request_line.decode("utf-8", errors="replace").strip().split(" ", 2)
    if len(parts) < 3:
        return "", "", "", {}, b""
    method, path, version = parts

    headers: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        decoded = line.decode("utf-8", errors="replace").strip()
        key, _, value = decoded.partition(":")
        headers[key.strip().lower()] = value.strip()

    content_length = int(headers.get("content-length", "0"))
    body = await reader.readexactly(content_length) if content_length > 0 else b""
    return method, path, version, headers, body


async def _read_http_response(
    reader: asyncio.StreamReader,
) -> tuple[int, dict[str, str], bytes]:
    status_line = await reader.readline()
    parts = status_line.decode("utf-8", errors="replace").strip().split(" ", 2)
    status_code = int(parts[1])

    headers: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        decoded = line.decode("utf-8", errors="replace").strip()
        key, _, value = decoded.partition(":")
        headers[key.strip().lower()] = value.strip()

    content_length = int(headers.get("content-length", "0"))
    body = await reader.readexactly(content_length) if content_length > 0 else b""
    return status_code, headers, body


async def _send_request(
    writer: asyncio.StreamWriter,
    method: str,
    path: str,
    body: bytes = b"",
    extra_headers: dict[str, str] | None = None,
) -> None:
    headers = {
        "Host": "127.0.0.1",
        "Content-Length": str(len(body)),
    }
    if extra_headers:
        headers.update(extra_headers)

    lines = [f"{method} {path} HTTP/1.1"]
    lines.extend(f"{key}: {value}" for key, value in headers.items())
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8") + body
    writer.write(raw)
    await writer.drain()


def test_usage_proxy_supports_multiple_non_streaming_requests_on_same_connection(
    monkeypatch: pytest.MonkeyPatch,
):
    async def scenario() -> None:
        proxy = UsageCapturingProxy("https://api.example.com", debug=True)
        observed_urls: list[str] = []
        reader = FakeReader(
            (
                b"GET /v1/models HTTP/1.1\r\nHost: localhost\r\n\r\n"
                b"GET /v1/models?cursor=2 HTTP/1.1\r\nHost: localhost\r\n\r\n"
            )
        )
        writer = FakeWriter()

        async def fake_passthrough(
            *,
            method: str,
            url: str,
            headers: dict[str, str],
            body: bytes,
            writer: FakeWriter,
            keep_alive: bool,
            conn_id: int,
            request_count: int,
        ) -> bool:
            del method, headers, body, conn_id, request_count
            observed_urls.append(url)
            proxy._write_status_and_headers(
                writer,
                200,
                httpx.Headers({"content-type": "application/json"}),
                content_length=0,
                close_connection=not keep_alive,
            )
            return False

        monkeypatch.setattr(proxy, "_proxy_passthrough", fake_passthrough)

        await proxy._handle_connection(reader, writer)

        response_text = writer.buffer.decode("utf-8")
        assert observed_urls == [
            "https://api.example.com/v1/models",
            "https://api.example.com/v1/models?cursor=2",
        ]
        assert response_text.count("HTTP/1.1 200 OK") == 2
        assert response_text.count("Connection: keep-alive") == 2
        assert writer.closed is True

    asyncio.run(scenario())


def test_usage_proxy_streams_sse_without_rewriting_and_collects_usage():
    async def scenario() -> None:
        sse_payload = (
            b"event: message_start\r\n"
            b'data: {"type":"message_start","message":{"usage":{"input_tokens":10}}}\r\n'
            b"\r\n"
            b"event: ping\r\n"
            b'data: {"type":"ping"}\r\n'
            b"\r\n"
            b"event: message_delta\r\n"
            b'data: {"type":"message_delta","usage":{"output_tokens":3}}\r\n'
            b"\r\n"
            b'data: {"type":"message_delta","usage":{"output_tokens":4}}\r\n'
            b"\r\n"
            b"event: message_stop\r\n"
            b'data: {"type":"message_stop"}\r\n'
            b"\r\n"
        )
        proxy = UsageCapturingProxy("https://api.example.com", debug=True)
        proxy._client = FakeClient(
            FakeStreamingResponse(
                [sse_payload[:25], sse_payload[25:93], sse_payload[93:]]
            )
        )
        writer = FakeWriter()

        should_close = await proxy._proxy_sse(
            method="POST",
            url="https://api.example.com/v1/messages",
            headers={"content-type": "application/json"},
            body=json.dumps({"stream": True}).encode("utf-8"),
            writer=writer,
            conn_id=1,
            request_count=1,
        )

        head, body = bytes(writer.buffer).split(b"\r\n\r\n", 1)
        header_lines = head.decode("utf-8").split("\r\n")
        status_code = int(header_lines[0].split(" ")[1])
        headers = {
            line.split(": ", 1)[0].lower(): line.split(": ", 1)[1]
            for line in header_lines[1:]
            if ": " in line
        }

        assert should_close is True
        assert status_code == 200
        assert headers["content-type"] == "text/event-stream"
        assert headers["connection"] == "close"
        assert body == sse_payload
        assert proxy.usage == {"input_tokens": 10, "output_tokens": 7}
        assert proxy.get_captured_response_text() == sse_payload.decode("utf-8")
        assert proxy.captured_response_content_type == "text/event-stream"

    asyncio.run(scenario())


def test_usage_proxy_captures_non_streaming_response_body_for_diagnostics():
    async def scenario() -> None:
        payload = {
            "id": "msg_123",
            "type": "message",
            "content": [{"type": "text", "text": "hello"}],
        }
        proxy = UsageCapturingProxy("https://api.example.com", debug=True)
        proxy._client = FakeRequestClient(FakeJSONResponse(payload))
        writer = FakeWriter()

        should_close = await proxy._proxy_non_streaming(
            method="POST",
            url="https://api.example.com/v1/messages",
            headers={"content-type": "application/json"},
            body=b"{}",
            writer=writer,
            keep_alive=False,
            conn_id=1,
            request_count=1,
            capture_usage=True,
        )

        assert should_close is True
        assert proxy.usage == {}
        assert proxy.captured_response_content_type == "application/json"
        assert '"id": "msg_123"' in proxy.get_captured_response_text()

    asyncio.run(scenario())


def test_usage_proxy_extracts_usage_from_gzip_sse_stream():
    async def scenario() -> None:
        sse_payload = (
            b"event: message_start\r\n"
            b'data: {"type":"message_start","message":{"usage":{"input_tokens":12}}}\r\n'
            b"\r\n"
            b"event: message_delta\r\n"
            b'data: {"type":"message_delta","usage":{"output_tokens":5}}\r\n'
            b"\r\n"
            b"event: message_stop\r\n"
            b'data: {"type":"message_stop"}\r\n'
            b"\r\n"
        )
        compressed_payload = gzip.compress(sse_payload)
        proxy = UsageCapturingProxy("https://api.example.com", debug=True)
        proxy._client = FakeClient(
            FakeStreamingResponse(
                [compressed_payload[:40], compressed_payload[40:]],
                headers={
                    "content-type": "text/event-stream",
                    "content-encoding": "gzip",
                },
            )
        )
        writer = FakeWriter()

        should_close = await proxy._proxy_sse(
            method="POST",
            url="https://api.example.com/v1/messages",
            headers={"content-type": "application/json"},
            body=json.dumps({"stream": True}).encode("utf-8"),
            writer=writer,
            conn_id=1,
            request_count=1,
        )

        head, body = bytes(writer.buffer).split(b"\r\n\r\n", 1)
        header_lines = head.decode("utf-8").split("\r\n")
        headers = {
            line.split(": ", 1)[0].lower(): line.split(": ", 1)[1]
            for line in header_lines[1:]
            if ": " in line
        }

        assert should_close is True
        assert headers["content-encoding"] == "gzip"
        assert body == compressed_payload
        assert proxy.usage == {"input_tokens": 12, "output_tokens": 5}
        assert proxy.captured_response_content_encoding == "gzip"
        assert proxy.get_captured_response_text() == sse_payload.decode("utf-8")

    asyncio.run(scenario())


def test_claude_provider_respects_usage_proxy_toggle(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = ClaudeCodeProvider()
    monkeypatch.setattr(settings, "claude_usage_proxy_enabled", False)

    async def scenario() -> None:
        proxy, effective_base_url = await provider._prepare_usage_proxy(
            "https://api.example.com"
        )
        assert proxy is None
        assert effective_base_url == "https://api.example.com"

    asyncio.run(scenario())


def test_usage_proxy_requires_explicit_real_api_url():
    with pytest.raises(ValueError, match="real_api_url"):
        UsageCapturingProxy("")


def test_claude_provider_does_not_inherit_parent_env_base_url_or_auth_token(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = ClaudeCodeProvider()
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://env.example.com")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "env-token")

    custom_env = provider._build_env(
        "https://api.example.com", None, "claude-3-7-sonnet-20250219"
    )

    assert custom_env["ANTHROPIC_BASE_URL"] == "https://api.example.com"
    assert "ANTHROPIC_AUTH_TOKEN" not in custom_env


def test_claude_provider_logs_raw_response_when_usage_is_missing(
    caplog: pytest.LogCaptureFixture,
):
    provider = ClaudeCodeProvider()
    proxy = UsageCapturingProxy("https://api.example.com", debug=True)
    proxy._captured_response_content_type = "application/json"
    proxy._captured_response_content_encoding = "identity"
    proxy._capture_response_bytes(
        b'{"id":"msg_123","type":"message","content":[{"type":"text","text":"hello"}]}'
    )

    with caplog.at_level(logging.WARNING):
        provider._log_missing_usage_warning(
            proxy, "https://api.example.com", "（简单模式）"
        )

    assert "Claude usage 未提取到（简单模式）" in caplog.text
    assert "content_encoding=identity" in caplog.text
    assert '"id":"msg_123"' in caplog.text
