"""Anthropic Messages API 客户端

直调 Anthropic /v1/messages 端点。
消除 CLI 子进程依赖和 UsageCapturingProxy (757行)。
原生获取 response.usage，无需 SSE 代理拦截。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .types import ForgeUsage, ForgeToolCall

logger = logging.getLogger(__name__)

ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_TIMEOUT = 300.0
DEFAULT_CONNECT_TIMEOUT = 30.0


class AnthropicClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

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
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 401:
                raise PermissionError(f"Anthropic API 认证失败: {response.text[:200]}")
            if response.status_code == 429:
                raise RuntimeError(f"Anthropic API 速率限制: {response.text[:200]}")
            if response.status_code >= 500:
                raise RuntimeError(
                    f"Anthropic API 服务器错误 ({response.status_code}): {response.text[:200]}"
                )
            response.raise_for_status()

        data = response.json()
        usage = self._extract_usage(data.get("usage", {}))
        return data, usage

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
