"""
Claude Code CLI Provider 实现
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core import settings
from .base import InlineComment, ReviewProvider, ReviewResult
from .usage_proxy import UsageCapturingProxy

logger = logging.getLogger(__name__)


class ClaudeCodeProvider(ReviewProvider):
    """基于 Claude Code CLI 的审查 Provider"""

    PROVIDER_NAME = "claude_code"
    DISPLAY_NAME = "Claude Code"
    MAX_DIFF_BYTES = 200_000

    # 脱敏正则：在写入日志前过滤凭证信息，与 base._set_last_error 保持一致
    _REDACT_RE = re.compile(
        r"(?i)(token|key|secret|authorization|password|passwd|bearer|credential)"
        r"\s*[:=]\s*([^\s,;\n]+)"
    )

    # 允许传递给 CLI 子进程的系统/运行时环境变量白名单
    # 白名单策略：只传递最小必要集，避免 DATABASE_URL / SECRET_KEY 等应用敏感变量泄露
    _SAFE_ENV_KEYS = frozenset(
        {
            # 可执行文件查找
            "PATH",
            # 用户主目录（Claude CLI 读取 ~/.claude/ 配置）
            "HOME",
            # 临时目录
            "TMPDIR",
            "TEMP",
            "TMP",
            # 语言/字符集
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "LC_MESSAGES",
            # 用户身份（部分 CLI 工具需要）
            "USER",
            "LOGNAME",
            # Node.js 运行时（Claude CLI 基于 Node）
            "NODE_PATH",
            "NODE_ENV",
            "NODE_EXTRA_CA_CERTS",
            # SSL 证书（企业内网代理环境）
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "REQUESTS_CA_BUNDLE",
            "CURL_CA_BUNDLE",
            # HTTP 代理（企业内网环境）
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "no_proxy",
            # XDG 基础目录（Linux 运行时）
            "XDG_RUNTIME_DIR",
            "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME",
        }
    )

    def __init__(self, cli_path: str = "claude", debug: bool = False):
        """初始化实例状态。

        Args:
            cli_path: CLI 可执行文件路径。
            debug: 是否启用调试模式。

        Returns:
            无返回值。
        """
        self.cli_path = cli_path
        self.debug = debug

    @property
    def name(self) -> str:
        """处理name相关逻辑。

        Args:
            无。

        Returns:
            字符串结果。
        """
        return self.PROVIDER_NAME

    @property
    def display_name(self) -> str:
        """处理display name相关逻辑。

        Args:
            无。

        Returns:
            字符串结果。
        """
        return self.DISPLAY_NAME

    def _build_review_prompt(
        self,
        focus_areas: List[str],
        pr_info: dict,
        diff_content: str,
        custom_prompt: Optional[str] = None,
    ) -> str:
        """处理审查prompt相关逻辑。

        Args:
            focus_areas: 审查关注点列表。
            pr_info: PR 基本信息。
            diff_content: PR 差异内容。
            custom_prompt: 自定义提示词。

        Returns:
            字符串结果。
        """
        focus_map = {
            "quality": "代码质量和最佳实践",
            "security": "安全漏洞（SQL注入、XSS、命令注入等）",
            "performance": "性能问题和优化建议",
            "logic": "逻辑错误和潜在bug",
        }

        focus_text = "、".join([focus_map.get(f, f) for f in focus_areas])

        prompt = f"""请审查以下Pull Request的代码变更。

**PR信息：**
- 标题: {pr_info.get("title", "N/A")}
- 描述: {pr_info.get("body", "N/A")}
- 作者: {pr_info.get("user", {}).get("login", "N/A")}

**审查重点：**
{focus_text}

**代码变更（diff）：**
```diff
{diff_content}
```

请完成以下审查任务：
1. **总体评价**：描述本次变更的整体风险、积极影响
2. **发现的问题**：按严重程度列出（严重/中等/轻微），解释原因
3. **改进建议**：给出可执行的修改建议
4. **优点**：指出值得保留或学习的实现

输出要求（必须严格遵守）：
- 最终输出为单个JSON对象，不要包含额外文本、注释或代码块标记
- `summary_markdown` 字段使用Markdown编写上述内容，结构清晰
- `overall_severity` 取值：critical/high/medium/low/info
- `inline_comments` 最多5条，逐条包含精确的 `path`、`new_line` (新增行号) 或 `old_line` (删除行号)、`comment`，可选 `suggestion` 与 `severity`
- `suggestion` 字段如果包含代码，必须使用 Markdown 代码块格式（```语言...```）
- 对无法定位的建议，省略该条，确保所有行号与diff一致

JSON结构示例：
{{
  "summary_markdown": "### 总体评价\\n...",
  "overall_severity": "medium",
  "inline_comments": [
    {{
      "path": "app/main.py",
      "new_line": 123,
      "old_line": null,
      "severity": "high",
      "comment": "描述问题与影响",
      "suggestion": "建议修改为：\\n```python\\nresult = safe_function(user_input)\\n```"
    }}
  ]
}}
"""
        if custom_prompt and custom_prompt.strip():
            prompt += f"\n\n**额外审查要求：**\n{custom_prompt.strip()}"
        return prompt

    def _resolve_api_url(self, api_url: Optional[str]) -> Optional[str]:
        """规范化本次调用的 API 地址。

        ClaudeCodeProvider 只接受显式传入的 api_url，不读取父进程环境变量，
        也不回退到官方默认地址。
        """
        normalized = (api_url or "").strip()
        if not normalized:
            return None
        return normalized

    async def _prepare_usage_proxy(
        self, api_url: str
    ) -> Tuple[Optional[UsageCapturingProxy], str]:
        """按配置决定是否启用 usage 代理，并返回有效 base URL。"""
        effective_base_url = api_url.rstrip("/")

        if not settings.claude_usage_proxy_enabled:
            if self.debug or settings.claude_usage_proxy_debug:
                logger.info(
                    "Claude usage 代理已禁用，直连上游: %s", effective_base_url
                )
            return None, effective_base_url

        proxy = UsageCapturingProxy(
            effective_base_url,
            debug=(self.debug or settings.claude_usage_proxy_debug),
        )
        try:
            port = await proxy.start()
        except Exception as proxy_exc:
            logger.warning("usage 捕获代理启动失败，将直连 API: %s", proxy_exc)
            await proxy.stop()
            return None, effective_base_url

        proxy_url = f"http://127.0.0.1:{port}"
        if self.debug or settings.claude_usage_proxy_debug:
            logger.info("Claude usage 代理已启用: %s -> %s", proxy_url, effective_base_url)
        return proxy, proxy_url

    def _build_timeout_error(
        self, proxy: Optional[UsageCapturingProxy], label: str = ""
    ) -> str:
        """构造包含代理诊断信息的超时消息。"""
        message = f"{self.DISPLAY_NAME} 执行超时（300s）{label}"
        if proxy is not None and proxy.last_error:
            message = f"{message}；代理异常：{proxy.last_error}"
        return message

    @staticmethod
    def _log_missing_usage_warning(
        proxy: UsageCapturingProxy, api_url: str, label: str = ""
    ) -> None:
        """当 usage 未提取到时，输出上游原始响应日志以便排查。"""
        if not proxy.has_captured_response_body():
            logger.warning(
                "Claude usage 未提取到%s，且代理未捕获到可诊断的上游响应内容: base_url=%s content_type=%s",
                label,
                api_url,
                proxy.captured_response_content_type or "-",
            )
            return

        logger.warning(
            "Claude usage 未提取到%s，记录上游原始响应内容供排查: "
            "base_url=%s content_type=%s truncated=%s body=%s",
            label,
            api_url,
            proxy.captured_response_content_type or "-",
            proxy.captured_response_truncated,
            proxy.get_captured_response_text(),
        )

    @classmethod
    def _redact_output(cls, text: str) -> str:
        """在写入日志前对输出文本脱敏，防止 API key 等凭证信息进入日志。"""
        return cls._REDACT_RE.sub(r"\1=[REDACTED]", text)

    def _truncate_diff(self, diff_content: str) -> bytes:
        """将 diff 编码为 UTF-8 并按字节上限截断。

        使用字节计数而非字符计数，避免中文等多字节字符导致实际传输量超限。
        """
        diff_bytes = diff_content.encode("utf-8")
        if len(diff_bytes) <= self.MAX_DIFF_BYTES:
            return diff_bytes
        # 截断后重新解码再编码，确保截断点不落在多字节字符中间
        truncated = diff_bytes[: self.MAX_DIFF_BYTES].decode("utf-8", errors="ignore")
        return (truncated + "\n\n... (diff 内容过长，已截断)").encode("utf-8")

    async def _run_cli(
        self,
        prompt: str,
        api_url: str,
        api_key: Optional[str],
        model: Optional[str],
        cwd: Optional[str],
        label: str,
    ) -> Optional[ReviewResult]:
        """执行 Claude CLI 子进程并返回解析后的审查结果。

        Args:
            prompt: 完整的审查提示词（含 diff 内容）。
            api_url: 已解析的 API 地址。
            api_key: API 密钥。
            model: 模型标识。
            cwd: 子进程工作目录；None 表示简单模式（不切换目录）。
            label: 用于日志的模式标签，如 "（简单模式）"。

        Returns:
            解析后的 ReviewResult，失败时返回 None。
        """
        proxy, effective_base_url = await self._prepare_usage_proxy(api_url)
        try:
            custom_env = self._build_env(effective_base_url, api_key, model)
            subprocess_kwargs: Dict[str, Any] = dict(
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=custom_env,
            )
            if cwd is not None:
                subprocess_kwargs["cwd"] = cwd

            process = await asyncio.create_subprocess_exec(
                self.cli_path,
                "-p",
                prompt,
                "--output-format",
                "text",
                **subprocess_kwargs,
            )

            # P1: 添加超时，防止 CLI 挂起导致请求永久阻塞
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=300.0,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                self._set_last_error(self._build_timeout_error(proxy, label))
                return None
        finally:
            if proxy is not None:
                await proxy.stop()

        if process.returncode != 0:
            stderr_text = stderr.decode(errors="ignore").strip()
            stdout_text = stdout.decode(errors="ignore").strip()
            actionable_error = self._extract_actionable_error(stderr_text, stdout_text)
            logger.error(
                "%s 执行失败 (返回码: %d)%s",
                self.DISPLAY_NAME,
                process.returncode,
                label,
            )
            logger.error("Stdout: %s", self._redact_output(stdout_text))
            logger.error("Stderr: %s", self._redact_output(stderr_text))
            self._set_last_error(
                actionable_error
                or f"{self.DISPLAY_NAME} 执行失败，返回码 {process.returncode}"
            )
            return None

        result_text = stdout.decode()
        if self.debug:
            logger.debug("[%s Response%s]\n%s", self.PROVIDER_NAME, label, result_text)
            if stderr:
                logger.debug(
                    "[%s Stderr%s]\n%s", self.PROVIDER_NAME, label, stderr.decode()
                )

        parsed = self._parse_output(result_text)
        if not parsed:
            logger.error("%s 返回结果为空%s", self.DISPLAY_NAME, label)
            self._set_last_error(f"{self.DISPLAY_NAME} 返回结果为空{label}")
            return None

        if proxy is not None:
            if proxy.usage:
                parsed.usage_metadata.update(proxy.usage)
            else:
                self._log_missing_usage_warning(proxy, api_url, label)

        return parsed

    async def analyze_pr(
        self,
        repo_path: Path,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        model: Optional[str] = None,
        wire_api: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        """使用完整仓库上下文分析 PR。

        Args:
            repo_path: 本地仓库路径（作为 CLI 工作目录）。
            diff_content: PR 的差异内容。
            focus_areas: 审查关注点列表。
            pr_info: PR 基本信息。
            api_url: API 地址。
            api_key: API 密钥。
            custom_prompt: 自定义提示词。
            model: 模型名称。
            wire_api: 底层 API 协议标识（保留参数，暂未使用）。

        Returns:
            可能为空的结果。
        """
        self._clear_last_error()
        try:
            truncated_diff = self._truncate_diff(diff_content).decode("utf-8", errors="ignore")
            prompt = self._build_review_prompt(focus_areas, pr_info, truncated_diff, custom_prompt)
            logger.info("开始使用 %s 分析PR，仓库路径: %s", self.DISPLAY_NAME, repo_path)
            if self.debug:
                logger.debug("[%s Prompt]\n%s", self.PROVIDER_NAME, prompt)

            resolved_api_url = self._resolve_api_url(api_url)
            if not resolved_api_url:
                self._set_last_error(
                    f"{self.DISPLAY_NAME} 未配置 api_url，无法发起审查请求"
                )
                return None

            result = await self._run_cli(
                prompt, resolved_api_url, api_key, model,
                cwd=str(repo_path), label="",
            )
            if result:
                self._set_model_metadata(result, model)
                logger.info("%s 分析完成", self.DISPLAY_NAME)
            return result

        except Exception as e:
            logger.error("%s 分析异常: %s", self.DISPLAY_NAME, e, exc_info=True)
            self._set_last_error(f"{self.DISPLAY_NAME} 分析异常: {e}")
            return None

    async def analyze_pr_simple(
        self,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        model: Optional[str] = None,
        wire_api: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        """仅基于 diff 分析 PR（降级模式，不需要本地仓库）。

        Args:
            diff_content: PR 的差异内容。
            focus_areas: 审查关注点列表。
            pr_info: PR 基本信息。
            api_url: API 地址。
            api_key: API 密钥。
            custom_prompt: 自定义提示词。
            model: 模型名称。
            wire_api: 底层 API 协议标识（保留参数，暂未使用）。

        Returns:
            可能为空的结果。
        """
        self._clear_last_error()
        try:
            truncated_diff = self._truncate_diff(diff_content).decode("utf-8", errors="ignore")
            prompt = self._build_review_prompt(focus_areas, pr_info, truncated_diff, custom_prompt)
            logger.info("开始使用 %s 分析PR（简单模式）", self.DISPLAY_NAME)
            if self.debug:
                logger.debug("[%s Prompt - Simple Mode]\n%s", self.PROVIDER_NAME, prompt)

            resolved_api_url = self._resolve_api_url(api_url)
            if not resolved_api_url:
                self._set_last_error(
                    f"{self.DISPLAY_NAME} 未配置 api_url，无法发起审查请求"
                )
                return None

            result = await self._run_cli(
                prompt, resolved_api_url, api_key, model,
                cwd=None, label="（简单模式）",
            )
            if result:
                self._set_model_metadata(result, model)
                logger.info("%s 分析完成（简单模式）", self.DISPLAY_NAME)
            return result

        except Exception as e:
            logger.error("%s 分析异常: %s", self.DISPLAY_NAME, e, exc_info=True)
            self._set_last_error(f"{self.DISPLAY_NAME} 分析异常: {e}")
            return None

    def _build_env(
        self,
        api_url: Optional[str],
        api_key: Optional[str],
        model: Optional[str],
    ) -> dict:
        """处理环境变量相关逻辑。

        Args:
            api_url: API 地址。
            api_key: API 密钥。
            model: 模型名称。

        Returns:
            字典结果。
        """
        # 白名单策略：只保留明确安全的系统变量，防止 DATABASE_URL / SECRET_KEY 等泄露
        custom_env = {
            k: v for k, v in os.environ.items() if k in self._SAFE_ENV_KEYS
        }
        if api_url:
            custom_env["ANTHROPIC_BASE_URL"] = api_url
            if self.debug:
                logger.debug(f"[Custom ANTHROPIC_BASE_URL] {api_url}")
        if api_key:
            custom_env["ANTHROPIC_AUTH_TOKEN"] = api_key
            if self.debug:
                logger.debug("[Custom ANTHROPIC_AUTH_TOKEN] (set)")
        if model and model.strip():
            custom_env["ANTHROPIC_MODEL"] = model.strip()
            if self.debug:
                logger.debug(f"[Custom ANTHROPIC_MODEL] {model.strip()}")
        return custom_env

    @staticmethod
    def _set_model_metadata(result: ReviewResult, model: Optional[str]) -> None:
        """处理模型metadata相关逻辑。

        Args:
            result: 审查结果对象。
            model: 模型名称。

        Returns:
            无返回值。
        """
        if model and model.strip():
            result.usage_metadata["model"] = model.strip()

    def _parse_output(self, output: str) -> Optional[ReviewResult]:
        """处理output相关逻辑。

        Args:
            output: 工具输出文本。

        Returns:
            可能为空的结果。
        """
        sanitized = (output or "").strip()
        if not sanitized:
            return None

        data = self._extract_json_payload(sanitized)
        if not data:
            logger.warning("响应未按JSON格式返回，将使用原始文本作为总结")
            return ReviewResult(
                summary_markdown=sanitized,
                inline_comments=[],
                raw_output=sanitized,
                provider_name=self.PROVIDER_NAME,
            )

        summary = str(
            data.get("summary_markdown")
            or data.get("summary")
            or data.get("report")
            or sanitized
        ).strip()
        severity = data.get("overall_severity") or data.get("severity")
        if isinstance(severity, str):
            severity = severity.strip()

        inline_comments: List[InlineComment] = []
        for item in data.get("inline_comments") or []:
            parsed = self._parse_inline_comment(item)
            if parsed:
                inline_comments.append(parsed)

        return ReviewResult(
            summary_markdown=summary or sanitized,
            inline_comments=inline_comments,
            overall_severity=severity,
            raw_output=sanitized,
            provider_name=self.PROVIDER_NAME,
        )

    def _parse_inline_comment(self, item: Dict[str, Any]) -> Optional[InlineComment]:
        """处理行内评论相关逻辑。

        Args:
            item: 单条解析项数据。

        Returns:
            可能为空的结果。
        """
        if not isinstance(item, dict):
            return None

        path = str(item.get("path") or "").strip()
        comment = str(item.get("comment") or item.get("body") or "").strip()
        if not path or not comment:
            return None

        line_type = (item.get("line_type") or "new").lower()
        new_line = self._coerce_int(
            item.get("new_line") or (item.get("line") if line_type == "new" else None)
        )
        old_line = self._coerce_int(
            item.get("old_line") or (item.get("line") if line_type == "old" else None)
        )

        severity = (
            str(item.get("severity")).strip()
            if isinstance(item.get("severity"), str)
            else item.get("severity")
        )
        suggestion = (
            str(item.get("suggestion")).strip()
            if isinstance(item.get("suggestion"), str)
            else item.get("suggestion")
        )

        return InlineComment(
            path=path,
            comment=comment,
            new_line=new_line,
            old_line=old_line,
            severity=severity,
            suggestion=suggestion,
        )

    def _extract_json_payload(self, text: str) -> Optional[Dict[str, Any]]:
        """处理json请求体相关逻辑。

        Args:
            text: 待解析文本。

        Returns:
            字典结果。
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取 JSON
        # 先提取代码块内容，再用 brace scanner 处理，避免非贪婪 regex 在嵌套 JSON 中提前截断
        for code_block_match in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text):
            block_text = code_block_match.group(1).strip()
            if not block_text.startswith("{"):
                continue
            parsed = self._scan_json_object(block_text)
            if parsed is not None:
                return parsed
        logger.debug("JSON解析失败（code block）")

        # 使用深度追踪找到最外层完整 JSON 对象，避免 find/rfind 的括号错位问题
        start = text.find("{")
        if start != -1:
            parsed = self._scan_json_object(text[start:])
            if parsed is not None:
                return parsed

        return None

    @staticmethod
    def _scan_json_object(text: str) -> Optional[Dict[str, Any]]:
        """从文本开头扫描并解析第一个完整的 JSON 对象（正确处理嵌套括号和字符串）。"""
        depth = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(text):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[: i + 1])
                    except json.JSONDecodeError:
                        logger.debug("JSON解析失败（brace scan）")
                    break
        return None

    @staticmethod
    def _extract_actionable_error(stderr_text: str, stdout_text: str) -> str:
        """处理actionable error相关逻辑。

        Args:
            stderr_text: 标准错误输出文本。
            stdout_text: 标准输出文本。

        Returns:
            字符串结果。
        """
        combined = "\n".join(
            part for part in [stderr_text.strip(), stdout_text.strip()] if part.strip()
        )
        if not combined:
            return ""

        combined = re.sub(r"\x1b\[[0-9;]*m", "", combined)

        for pattern in [
            r"ERROR:\s*[^\n]*",
            r"unexpected status\s+\d{3}[^\n]*",
            r"Error:\s*[^\n]*",
        ]:
            match = re.search(pattern, combined, flags=re.IGNORECASE)
            if match:
                return match.group(0).strip()

        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        filtered = [line for line in lines if not line.startswith("Reconnecting...")]
        if filtered:
            return filtered[-1]
        return lines[-1]

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        """处理int相关逻辑。

        Args:
            value: 配置值。

        Returns:
            可能为空的结果。
        """
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
