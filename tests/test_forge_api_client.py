from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.providers.forge.api_client import AnthropicClient


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        text: str = "",
        json_data: dict | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        request = httpx.Request("POST", "https://example.com/v1/messages")
        response = httpx.Response(
            self.status_code,
            request=request,
            json=self._json_data if self._json_data else None,
            headers=self.headers,
        )
        response.read()
        response.raise_for_status()


def test_anthropic_client_retries_529_three_times_then_succeeds(
    monkeypatch,
):
    calls: list[int] = []
    sleeps: list[float] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            calls.append(1)
            if len(calls) <= 3:
                return FakeResponse(
                    status_code=529,
                    text='{"error":{"message":"overloaded_error"}}',
                )
            return FakeResponse(
                status_code=200,
                json_data={"usage": {"input_tokens": 10, "output_tokens": 5}},
            )

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    monkeypatch.setattr(
        "app.services.providers.forge.api_client.httpx.AsyncClient",
        FakeAsyncClient,
    )
    monkeypatch.setattr("app.services.providers.forge.api_client.asyncio.sleep", fake_sleep)

    data, usage = asyncio.run(
        AnthropicClient(api_key="secret", max_retries=3).create_message(
            model="claude-test",
            messages=[{"role": "user", "content": "hello"}],
        )
    )

    assert len(calls) == 4
    assert sleeps == [1.0, 2.0, 4.0]
    assert data["usage"]["input_tokens"] == 10
    assert usage.output_tokens == 5


def test_anthropic_client_does_not_retry_permission_error(monkeypatch):
    calls: list[int] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            calls.append(1)
            return FakeResponse(status_code=401, text="unauthorized")

    async def fake_sleep(delay: float):
        raise AssertionError("401 不应进入重试等待")

    monkeypatch.setattr(
        "app.services.providers.forge.api_client.httpx.AsyncClient",
        FakeAsyncClient,
    )
    monkeypatch.setattr("app.services.providers.forge.api_client.asyncio.sleep", fake_sleep)

    try:
        asyncio.run(
            AnthropicClient(api_key="secret", max_retries=3).create_message(
                model="claude-test",
                messages=[{"role": "user", "content": "hello"}],
            )
        )
    except PermissionError as exc:
        assert "认证失败" in str(exc)
    else:
        raise AssertionError("预期应抛出 PermissionError")

    assert len(calls) == 1
