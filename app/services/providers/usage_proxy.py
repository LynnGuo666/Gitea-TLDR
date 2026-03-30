"""
轻量 HTTP 代理 —— 拦截 Anthropic API 响应中的 token 用量

在 ClaudeCodeProvider 每次 CLI 调用时启动一个临时本地代理，
将 ANTHROPIC_BASE_URL 指向该代理，代理转发请求到真实 API
的同时解析 SSE 流或 JSON 响应中的 usage 字段。
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_HOP_BY_HOP = frozenset(
    h.lower()
    for h in [
        "host",
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "upgrade",
    ]
)


class UsageCapturingProxy:
    """轻量 HTTP 代理，捕获 Anthropic API 的 token 用量。

    每次 analyze_pr 调用创建一个实例，生命周期与 CLI 子进程绑定。
    usage 字典在代理处理请求后被填充，与 ReviewProvider 共享引用。
    """

    def __init__(self, real_api_url: str) -> None:
        self._real_api_url = (real_api_url or "https://api.anthropic.com").rstrip("/")
        self.usage: Dict[str, Any] = {}
        self._server: Optional[asyncio.AbstractServer] = None
        self._port: int = 0
        self._serve_task: Optional[asyncio.Task] = None

    @property
    def port(self) -> int:
        return self._port

    async def start(self) -> int:
        """启动代理，返回监听端口。"""
        self._server = await asyncio.start_server(
            self._handle_connection, "127.0.0.1", 0
        )
        self._port = self._server.sockets[0].getsockname()[1]
        self._serve_task = asyncio.ensure_future(self._server.serve_forever())
        logger.debug(f"UsageCapturingProxy listening on 127.0.0.1:{self._port}")
        return self._port

    async def stop(self) -> None:
        """关闭代理。"""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._serve_task is not None:
            self._serve_task.cancel()
            try:
                await self._serve_task
            except asyncio.CancelledError:
                pass
            self._serve_task = None
        logger.debug("UsageCapturingProxy closed")

    # ------------------------------------------------------------------
    # 连接处理
    # ------------------------------------------------------------------

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """处理单个 TCP 连接（一个 HTTP 请求/响应周期）。"""
        try:
            method, path, headers, body = await self._read_http_request(reader)
            if not method or not path:
                return

            upstream_url = f"{self._real_api_url}{path}"
            upstream_headers = self._build_upstream_headers(headers)
            is_messages = path.rstrip("/") == "/v1/messages"

            async with httpx.AsyncClient(timeout=300.0) as client:
                if is_messages:
                    await self._proxy_messages(
                        client, method, upstream_url, upstream_headers, body, writer
                    )
                else:
                    await self._proxy_passthrough(
                        client, method, upstream_url, upstream_headers, body, writer
                    )
        except Exception:
            logger.debug("Proxy connection error", exc_info=True)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 消息端点代理（带 usage 捕获）
    # ------------------------------------------------------------------

    async def _proxy_messages(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        writer: asyncio.StreamWriter,
    ) -> None:
        is_streaming = self._detect_streaming(body)
        if is_streaming:
            await self._proxy_sse(client, method, url, headers, body, writer)
        else:
            await self._proxy_non_streaming(client, method, url, headers, body, writer)

    async def _proxy_sse(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        writer: asyncio.StreamWriter,
    ) -> None:
        """逐行转发 SSE 流，边转发边解析 usage 事件（零延迟）。"""
        async with client.stream(method, url, headers=headers, content=body) as resp:
            self._write_status_and_headers(writer, resp.status_code, resp.headers)
            async for line in resp.aiter_lines():
                # 先转发，再解析——不阻塞数据流
                writer.write(f"{line}\r\n".encode())
                await writer.drain()
                if line.startswith("data: "):
                    self._extract_usage_from_sse(line[6:])

    async def _proxy_non_streaming(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        writer: asyncio.StreamWriter,
    ) -> None:
        """转发非流式响应，从完整 JSON 中提取 usage。"""
        resp = await client.request(method, url, headers=headers, content=body)
        try:
            usage = resp.json().get("usage")
            if isinstance(usage, dict):
                if "input_tokens" in usage:
                    self.usage["input_tokens"] = usage["input_tokens"]
                if "output_tokens" in usage:
                    self.usage["output_tokens"] = usage["output_tokens"]
        except (json.JSONDecodeError, ValueError, AttributeError):
            pass
        self._write_status_and_headers(writer, resp.status_code, resp.headers)
        writer.write(resp.content)
        await writer.drain()

    # ------------------------------------------------------------------
    # 通用透传代理
    # ------------------------------------------------------------------

    async def _proxy_passthrough(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        writer: asyncio.StreamWriter,
    ) -> None:
        """对非 messages 端点做纯透传。"""
        resp = await client.request(method, url, headers=headers, content=body)
        self._write_status_and_headers(writer, resp.status_code, resp.headers)
        writer.write(resp.content)
        await writer.drain()

    # ------------------------------------------------------------------
    # HTTP 解析辅助
    # ------------------------------------------------------------------

    async def _read_http_request(
        self, reader: asyncio.StreamReader
    ) -> Tuple[str, str, Dict[str, str], bytes]:
        """从 TCP 流中读取一个完整的 HTTP/1.1 请求。"""
        request_line = await reader.readline()
        if not request_line:
            return "", "", {}, b""

        parts = request_line.decode(errors="replace").strip().split(" ", 2)
        if len(parts) < 2:
            return "", "", {}, b""
        method, path = parts[0], parts[1]

        headers: Dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            decoded = line.decode(errors="replace").strip()
            if ":" in decoded:
                key, _, value = decoded.partition(":")
                headers[key.strip()] = value.strip()

        content_length = int(headers.get("Content-Length", "0"))
        body = b""
        if content_length > 0:
            body = await reader.readexactly(content_length)

        return method, path, headers, body

    def _build_upstream_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """构建转发到上游的请求头，过滤 hop-by-hop 头。"""
        result = {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}
        result["host"] = urlparse(self._real_api_url).netloc
        return result

    @staticmethod
    def _write_status_and_headers(
        writer: asyncio.StreamWriter,
        status_code: int,
        headers: httpx.Headers,
    ) -> None:
        """将 HTTP 响应状态行和头写入客户端 socket。"""
        reason = httpx.codes.get_reason_phrase(status_code)
        writer.write(f"HTTP/1.1 {status_code} {reason}\r\n".encode())
        for name, value in headers.items():
            if name.lower() not in _HOP_BY_HOP:
                writer.write(f"{name}: {value}\r\n".encode())
        writer.write(b"\r\n")

    # ------------------------------------------------------------------
    # Usage 提取
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_streaming(body: bytes) -> bool:
        """从请求体判断是否为流式请求。"""
        try:
            return bool(json.loads(body).get("stream"))
        except (json.JSONDecodeError, ValueError):
            return False

    def _extract_usage_from_sse(self, data_str: str) -> None:
        """从 SSE data 行提取 usage 字段。

        SSE 事件结构:
          message_start  -> message.usage.input_tokens
          message_delta  -> usage.output_tokens
        """
        try:
            event = json.loads(data_str)
        except (json.JSONDecodeError, ValueError):
            return

        event_type = event.get("type")

        if event_type == "message_start":
            usage = event.get("message", {}).get("usage", {})
            if "input_tokens" in usage:
                self.usage["input_tokens"] = usage["input_tokens"]

        elif event_type == "message_delta":
            usage = event.get("usage", {})
            if "output_tokens" in usage:
                # 累加增量，SSE 可能包含多段 message_delta
                self.usage["output_tokens"] = (
                    self.usage.get("output_tokens", 0) + usage["output_tokens"]
                )
