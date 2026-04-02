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

_SSE_IDLE_LOG_INTERVAL_SECONDS = 15.0
_SSE_CHUNK_LOG_EVERY = 20

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

    def __init__(self, real_api_url: str, debug: bool = False) -> None:
        self._real_api_url = (real_api_url or "https://api.anthropic.com").rstrip("/")
        self._debug = debug
        self.usage: Dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self._server: Optional[asyncio.AbstractServer] = None
        self._port: int = 0
        self._serve_task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._connection_counter: int = 0

    @property
    def port(self) -> int:
        return self._port

    async def start(self) -> int:
        """启动代理，返回监听端口。"""
        self.last_error = None
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=30.0),
            http1=True,
            http2=False,
            trust_env=False,
            follow_redirects=False,
        )
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
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.debug("UsageCapturingProxy closed")

    # ------------------------------------------------------------------
    # 连接处理
    # ------------------------------------------------------------------

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """处理单个 TCP 连接，必要时支持同连接多次非流式请求。"""
        self._connection_counter += 1
        conn_id = self._connection_counter
        peer = writer.get_extra_info("peername")
        transport_end = "client_disconnected"
        request_count = 0

        try:
            while True:
                method, path, version, headers, body = await self._read_http_request(
                    reader
                )
                if not method or not path:
                    break

                request_count += 1
                upstream_url = f"{self._real_api_url}{path}"
                upstream_headers = self._build_upstream_headers(headers)
                keep_alive = self._should_keep_alive(version, headers)
                is_messages = path.split("?")[0].rstrip("/") == "/v1/messages"

                if self._debug:
                    logger.info(
                        "Usage proxy conn=%s req=%s peer=%s %s %s stream=%s bytes=%s",
                        conn_id,
                        request_count,
                        peer,
                        method,
                        path,
                        self._detect_streaming(body) if is_messages else False,
                        len(body),
                    )

                if is_messages:
                    should_close = await self._proxy_messages(
                        method=method,
                        url=upstream_url,
                        headers=upstream_headers,
                        body=body,
                        writer=writer,
                        keep_alive=keep_alive,
                        conn_id=conn_id,
                        request_count=request_count,
                    )
                else:
                    should_close = await self._proxy_passthrough(
                        method=method,
                        url=upstream_url,
                        headers=upstream_headers,
                        body=body,
                        writer=writer,
                        keep_alive=keep_alive,
                        conn_id=conn_id,
                        request_count=request_count,
                    )
                if should_close:
                    transport_end = "response_complete"
                    break
        except Exception:
            transport_end = "proxy_error"
            logger.warning("Proxy connection error", exc_info=self._debug)
        finally:
            if self._debug:
                logger.info(
                    "Usage proxy conn=%s peer=%s requests=%s transport_end=%s",
                    conn_id,
                    peer,
                    request_count,
                    transport_end,
                )
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
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        writer: asyncio.StreamWriter,
        keep_alive: bool,
        conn_id: int,
        request_count: int,
    ) -> bool:
        is_streaming = self._detect_streaming(body)
        if is_streaming:
            return await self._proxy_sse(
                method=method,
                url=url,
                headers=headers,
                body=body,
                writer=writer,
                conn_id=conn_id,
                request_count=request_count,
            )
        return await self._proxy_non_streaming(
            method=method,
            url=url,
            headers=headers,
            body=body,
            writer=writer,
            keep_alive=keep_alive,
            conn_id=conn_id,
            request_count=request_count,
            capture_usage=True,
        )

    async def _proxy_sse(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        writer: asyncio.StreamWriter,
        conn_id: int,
        request_count: int,
    ) -> bool:
        """原样透传 SSE 字节流，同时旁路解析 usage。"""
        client = self._require_client()
        response_bytes = 0
        chunk_count = 0
        idle_log_count = 0
        parser_buffer = bytearray()
        event_state: Dict[str, Optional[str]] = {"event": None}
        loop = asyncio.get_running_loop()
        last_chunk_at = loop.time()

        try:
            async with client.stream(method, url, headers=headers, content=body) as resp:
                self._write_status_and_headers(
                    writer,
                    resp.status_code,
                    resp.headers,
                    close_connection=True,
                )
                if self._debug:
                    logger.info(
                        "Usage proxy conn=%s req=%s SSE streaming started status=%s",
                        conn_id,
                        request_count,
                        resp.status_code,
                    )

                if not self._debug:
                    async for chunk in resp.aiter_raw():
                        response_bytes += len(chunk)
                        writer.write(chunk)
                        await writer.drain()
                        self._consume_sse_bytes(parser_buffer, chunk, event_state)
                    return True

                chunk_iter = resp.aiter_raw().__aiter__()
                while True:
                    try:
                        chunk = await asyncio.wait_for(
                            chunk_iter.__anext__(),
                            timeout=_SSE_IDLE_LOG_INTERVAL_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        idle_log_count += 1
                        logger.info(
                            "Usage proxy conn=%s req=%s SSE idle=%ss chunks=%s bytes=%s",
                            conn_id,
                            request_count,
                            int(_SSE_IDLE_LOG_INTERVAL_SECONDS * idle_log_count),
                            chunk_count,
                            response_bytes,
                        )
                        continue
                    except StopAsyncIteration:
                        break

                    chunk_count += 1
                    now = loop.time()
                    gap_ms = int((now - last_chunk_at) * 1000)
                    last_chunk_at = now
                    response_bytes += len(chunk)
                    writer.write(chunk)
                    await writer.drain()
                    self._consume_sse_bytes(parser_buffer, chunk, event_state)
                    if (
                        chunk_count == 1
                        or chunk_count % _SSE_CHUNK_LOG_EVERY == 0
                    ):
                        logger.info(
                            "Usage proxy conn=%s req=%s SSE chunk=%s chunk_bytes=%s total_bytes=%s gap_ms=%s",
                            conn_id,
                            request_count,
                            chunk_count,
                            len(chunk),
                            response_bytes,
                            gap_ms,
                        )
        except Exception as exc:
            self.last_error = (
                f"SSE 转发失败: {type(exc).__name__}: {exc}"
            )
            raise

        if self._debug:
            logger.info(
                "Usage proxy conn=%s req=%s SSE completed bytes=%s usage=%s",
                conn_id,
                request_count,
                response_bytes,
                self.usage,
            )
        return True

    async def _proxy_non_streaming(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        writer: asyncio.StreamWriter,
        keep_alive: bool,
        conn_id: int,
        request_count: int,
        capture_usage: bool = False,
    ) -> bool:
        """转发非流式响应，从完整 JSON 中提取 usage。"""
        client = self._require_client()
        try:
            resp = await client.request(method, url, headers=headers, content=body)
        except Exception as exc:
            self.last_error = (
                f"上游请求失败: {type(exc).__name__}: {exc}"
            )
            raise

        content = resp.content
        if capture_usage:
            self._extract_usage_from_json_body(content)

        self._write_status_and_headers(
            writer,
            resp.status_code,
            resp.headers,
            content_length=len(content),
            close_connection=not keep_alive,
        )
        writer.write(content)
        await writer.drain()

        if self._debug:
            logger.info(
                "Usage proxy conn=%s req=%s status=%s bytes=%s keep_alive=%s",
                conn_id,
                request_count,
                resp.status_code,
                len(content),
                keep_alive,
            )
        return not keep_alive

    # ------------------------------------------------------------------
    # 通用透传代理
    # ------------------------------------------------------------------

    async def _proxy_passthrough(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        writer: asyncio.StreamWriter,
        keep_alive: bool,
        conn_id: int,
        request_count: int,
    ) -> bool:
        """对非 messages 端点做纯透传。"""
        return await self._proxy_non_streaming(
            method=method,
            url=url,
            headers=headers,
            body=body,
            writer=writer,
            keep_alive=keep_alive,
            conn_id=conn_id,
            request_count=request_count,
            capture_usage=False,
        )

    # ------------------------------------------------------------------
    # HTTP 解析辅助
    # ------------------------------------------------------------------

    async def _read_http_request(
        self, reader: asyncio.StreamReader
    ) -> Tuple[str, str, str, Dict[str, str], bytes]:
        """从 TCP 流中读取一个完整的 HTTP/1.1 请求。"""
        request_line = await reader.readline()
        if not request_line:
            return "", "", "", {}, b""

        parts = request_line.decode(errors="replace").strip().split(" ", 2)
        if len(parts) < 3:
            return "", "", "", {}, b""
        method, path, version = parts[0], parts[1], parts[2]

        headers: Dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            decoded = line.decode(errors="replace").strip()
            if ":" in decoded:
                key, _, value = decoded.partition(":")
                # 统一小写存储，HTTP header 大小写不敏感
                headers[key.strip().lower()] = value.strip()

        body = b""
        transfer_encoding = headers.get("transfer-encoding", "").lower()
        if "chunked" in transfer_encoding:
            body = await self._read_chunked_body(reader)
        else:
            content_length = int(headers.get("content-length", "0"))
            if content_length > 0:
                body = await reader.readexactly(content_length)

        return method, path, version, headers, body

    async def _read_chunked_body(self, reader: asyncio.StreamReader) -> bytes:
        """解码 chunked transfer encoding 请求体。"""
        body = b""
        while True:
            size_line = await reader.readline()
            chunk_size = int(size_line.strip().split(b";")[0], 16)
            if chunk_size == 0:
                await reader.readline()  # 消耗末尾 CRLF
                break
            chunk = await reader.readexactly(chunk_size)
            await reader.readline()  # 消耗 chunk 后的 CRLF
            body += chunk
        return body

    def _build_upstream_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """构建转发到上游的请求头，过滤 hop-by-hop 头。"""
        result = {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}
        result["host"] = urlparse(self._real_api_url).netloc
        result.setdefault("accept-encoding", "identity")
        return result

    @staticmethod
    def _write_status_and_headers(
        writer: asyncio.StreamWriter,
        status_code: int,
        headers: httpx.Headers,
        content_length: Optional[int] = None,
        close_connection: bool = False,
    ) -> None:
        """将 HTTP 响应状态行和头写入客户端 socket。"""
        reason = httpx.codes.get_reason_phrase(status_code)
        writer.write(f"HTTP/1.1 {status_code} {reason}\r\n".encode())
        for name, value in headers.items():
            if name.lower() not in _HOP_BY_HOP:
                writer.write(f"{name}: {value}\r\n".encode())
        if content_length is not None:
            writer.write(f"Content-Length: {content_length}\r\n".encode())
        writer.write(
            f"Connection: {'close' if close_connection else 'keep-alive'}\r\n".encode()
        )
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

    def _extract_usage_from_sse(
        self, data_str: str, event_name: Optional[str] = None
    ) -> None:
        """从 SSE data 行提取 usage 字段。

        SSE 事件结构:
          message_start  -> message.usage.input_tokens / cache_*_input_tokens
          message_delta  -> usage.output_tokens（本次调用最终值，每次调用累加）

        Claude Code CLI 在一次审查中可能发起多次 API 调用（工具调用、多轮对话），
        因此所有 token 字段均跨调用累加，而非覆盖或取最大值。
        """
        try:
            event = json.loads(data_str)
        except (json.JSONDecodeError, ValueError):
            return

        event_type = event.get("type")
        if self._debug and (
            event_name in {"message_stop", "ping", "error"}
            or event_type in {"message_stop", "ping", "error"}
        ):
            logger.info(
                "Usage proxy SSE event observed event=%s type=%s keys=%s",
                event_name or "-",
                event_type or "-",
                sorted(event.keys()),
            )

        if event_type == "message_start":
            usage = event.get("message", {}).get("usage", {})
            if "input_tokens" in usage:
                self.usage["input_tokens"] = (
                    self.usage.get("input_tokens", 0) + usage["input_tokens"]
                )
            if "cache_creation_input_tokens" in usage:
                self.usage["cache_creation_input_tokens"] = (
                    self.usage.get("cache_creation_input_tokens", 0)
                    + usage["cache_creation_input_tokens"]
                )
            if "cache_read_input_tokens" in usage:
                self.usage["cache_read_input_tokens"] = (
                    self.usage.get("cache_read_input_tokens", 0)
                    + usage["cache_read_input_tokens"]
                )

        elif event_type == "message_delta":
            usage = event.get("usage", {})
            if "output_tokens" in usage:
                # message_delta 每次调用只触发一次，包含本次调用的最终 output_tokens。
                # 跨多次调用需累加而非取最大值。
                self.usage["output_tokens"] = (
                    self.usage.get("output_tokens", 0) + usage["output_tokens"]
                )

    def _extract_usage_from_json_body(self, payload: bytes) -> None:
        """从非流式 JSON 响应中提取 usage。"""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return

        usage = data.get("usage")
        if not isinstance(usage, dict):
            return
        if "input_tokens" in usage:
            self.usage["input_tokens"] = (
                self.usage.get("input_tokens", 0) + usage["input_tokens"]
            )
        if "output_tokens" in usage:
            self.usage["output_tokens"] = (
                self.usage.get("output_tokens", 0) + usage["output_tokens"]
            )
        if "cache_creation_input_tokens" in usage:
            self.usage["cache_creation_input_tokens"] = (
                self.usage.get("cache_creation_input_tokens", 0)
                + usage["cache_creation_input_tokens"]
            )
        if "cache_read_input_tokens" in usage:
            self.usage["cache_read_input_tokens"] = (
                self.usage.get("cache_read_input_tokens", 0)
                + usage["cache_read_input_tokens"]
            )

    def _consume_sse_bytes(
        self,
        buffer: bytearray,
        chunk: bytes,
        event_state: Optional[Dict[str, Optional[str]]] = None,
    ) -> None:
        """旁路解析 SSE，不改变实际转发出去的字节流。"""
        event_state = event_state or {"event": None}
        buffer.extend(chunk)
        while True:
            newline_index = buffer.find(b"\n")
            if newline_index == -1:
                break
            raw_line = bytes(buffer[:newline_index])
            del buffer[: newline_index + 1]
            line = raw_line.rstrip(b"\r")
            if not line:
                event_state["event"] = None
                continue
            if line.startswith(b"event: "):
                event_state["event"] = line[7:].decode("utf-8", errors="ignore").strip()
                continue
            if line.startswith(b"data: "):
                self._extract_usage_from_sse(
                    line[6:].decode("utf-8", errors="ignore"),
                    event_name=event_state.get("event"),
                )

    @staticmethod
    def _should_keep_alive(version: str, headers: Dict[str, str]) -> bool:
        """根据请求版本与 Connection 头判断是否保持连接。"""
        connection = headers.get("connection", "").lower()
        if version == "HTTP/1.0":
            return "keep-alive" in connection
        return "close" not in connection

    def _require_client(self) -> httpx.AsyncClient:
        """确保代理客户端已经初始化。"""
        if self._client is None:
            raise RuntimeError("UsageCapturingProxy client is not initialized")
        return self._client
