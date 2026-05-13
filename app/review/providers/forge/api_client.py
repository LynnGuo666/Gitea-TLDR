"""Anthropic Messages API 客户端

直调 Anthropic /v1/messages 端点。
消除 CLI 子进程依赖和 UsageCapturingProxy (757行)。
原生获取 response.usage，无需 SSE 代理拦截。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .types import ForgeUsage, ForgeToolCall

logger = logging.getLogger(__name__)

ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_TIMEOUT = 300.0
DEFAULT_CONNECT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0
MAX_RETRY_DELAY = 8.0


class AnthropicClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    async def create_message(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        *,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stop_sequences: Optional[List[str]] = None,
        temperature: Optional[float] = None,
    ) -> Tuple[Dict[str, Any], ForgeUsage]:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
        }

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system is not None:
            payload["system"] = system
        if tools is not None:
            payload["tools"] = tools
        if stop_sequences is not None:
            payload["stop_sequences"] = stop_sequences
        if temperature is not None:
            payload["temperature"] = temperature

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=DEFAULT_CONNECT_TIMEOUT)
        ) as client:
            last_error: Exception | None = None
            total_attempts = self.max_retries + 1

            for attempt in range(1, total_attempts + 1):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                except (
                    httpx.TimeoutException,
                    httpx.ConnectError,
                    httpx.ReadError,
                    httpx.RemoteProtocolError,
                    httpx.NetworkError,
                ) as exc:
                    last_error = RuntimeError(f"Anthropic API 网络错误: {exc}")
                    if attempt >= total_attempts:
                        raise last_error from exc
                    delay = self._compute_retry_delay(attempt)
                    logger.warning(
                        "Anthropic API 网络错误，准备第 %s/%s 次重试，%.1f 秒后继续: %s",
                        attempt,
                        self.max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code == 401:
                    raise PermissionError(f"Anthropic API 认证失败: {response.text[:200]}")
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    response.raise_for_status()

                if response.status_code == 429 or response.status_code >= 500:
                    if response.status_code == 429:
                        last_error = RuntimeError(
                            f"Anthropic API 速率限制: {response.text[:200]}"
                        )
                    else:
                        last_error = RuntimeError(
                            f"Anthropic API 服务器错误 ({response.status_code}): {response.text[:200]}"
                        )
                    if attempt >= total_attempts:
                        raise last_error
                    delay = self._compute_retry_delay(
                        attempt,
                        retry_after=response.headers.get("retry-after"),
                    )
                    logger.warning(
                        "Anthropic API 返回 %s，准备第 %s/%s 次重试，%.1f 秒后继续",
                        response.status_code,
                        attempt,
                        self.max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                data = response.json()
                usage = self._extract_usage(data.get("usage", {}))
                return data, usage

            if last_error is None:
                raise RuntimeError("Anthropic API 调用失败: 未知错误")
            raise last_error

    def _compute_retry_delay(
        self,
        attempt: int,
        *,
        retry_after: Optional[str] = None,
    ) -> float:
        if retry_after:
            try:
                parsed = float(retry_after)
                if parsed > 0:
                    return min(parsed, MAX_RETRY_DELAY)
            except ValueError:
                pass
        return min(DEFAULT_RETRY_BASE_DELAY * (2 ** (attempt - 1)), MAX_RETRY_DELAY)

    def _extract_usage(self, raw_usage: Dict[str, Any]) -> ForgeUsage:
        return ForgeUsage(
            input_tokens=raw_usage.get("input_tokens", 0),
            output_tokens=raw_usage.get("output_tokens", 0),
            cache_creation_input_tokens=raw_usage.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=raw_usage.get("cache_read_input_tokens", 0),
        )

    def parse_tool_calls(self, content_blocks: List[Dict]) -> List[ForgeToolCall]:
        calls = []
        for block in content_blocks:
            if block.get("type") == "tool_use":
                calls.append(
                    ForgeToolCall(
                        id=block["id"],
                        name=block["name"],
                        arguments=block.get("input", {}),
                    )
                )
        return calls

    def parse_stop_reason(self, data: Dict[str, Any]) -> str:
        return data.get("stop_reason", "unknown")

    def parse_text_content(self, content_blocks: List[Dict]) -> str:
        parts = []
        for block in content_blocks:
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
