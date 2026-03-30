"""
Claude Code CLI Provider 实现
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import InlineComment, ReviewProvider, ReviewResult
from .usage_proxy import UsageCapturingProxy

logger = logging.getLogger(__name__)


class ClaudeCodeProvider(ReviewProvider):
    """基于 Claude Code CLI 的审查 Provider"""

    PROVIDER_NAME = "claude_code"
    DISPLAY_NAME = "Claude Code"
    MAX_DIFF_CHARS = 200_000

    # 不应传递给 CLI 子进程的已知凭证环境变量
    _SENSITIVE_ENV_KEYS = frozenset(
        {
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "GITHUB_TOKEN",
            "GITLAB_TOKEN",
            "NPM_TOKEN",
            "PYPI_TOKEN",
            "GIT_CREDENTIALS",
            "NETRC",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
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
        self, focus_areas: List[str], pr_info: dict, custom_prompt: Optional[str] = None
    ) -> str:
        """处理审查prompt相关逻辑。

        Args:
            focus_areas: 审查关注点列表。
            pr_info: PR 基本信息。
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

        prompt = f"""请审查以下Pull Request的代码变更（diff内容已通过stdin提供）。

**PR信息：**
- 标题: {pr_info.get("title", "N/A")}
- 描述: {pr_info.get("body", "N/A")}
- 作者: {pr_info.get("user", {}).get("login", "N/A")}

**审查重点：**
{focus_text}

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
        """分析pr。

        Args:
            repo_path: 本地仓库路径。
            diff_content: PR 的差异内容。
            focus_areas: 审查关注点列表。
            pr_info: PR 基本信息。
            api_url: API 地址。
            api_key: API 密钥。
            custom_prompt: 自定义提示词。
            model: 模型名称。
            wire_api: 底层 API 协议标识。

        Returns:
            可能为空的结果。
        """
        self._clear_last_error()
        try:
            # P5: 截断过长 diff，防止内存溢出和 token 炸弹
            if len(diff_content) > self.MAX_DIFF_CHARS:
                diff_content = (
                    diff_content[: self.MAX_DIFF_CHARS]
                    + "\n\n... (diff 内容过长，已截断)"
                )

            prompt = self._build_review_prompt(focus_areas, pr_info, custom_prompt)

            logger.info(f"开始使用 {self.DISPLAY_NAME} 分析PR，仓库路径: {repo_path}")

            if self.debug:
                logger.debug(f"[{self.PROVIDER_NAME} Prompt]\n{prompt}")
                logger.debug(f"[Diff Content Length] {len(diff_content)} characters")

            # P3: 代理启动失败时降级为直连 API
            proxy: Optional[UsageCapturingProxy] = None
            effective_base_url = api_url or "https://api.anthropic.com"
            try:
                proxy = UsageCapturingProxy(effective_base_url)
                port = await proxy.start()
                effective_base_url = f"http://127.0.0.1:{port}"
            except Exception as proxy_exc:
                logger.warning("usage 捕获代理启动失败，将直连 API: %s", proxy_exc)
                proxy = None

            try:
                custom_env = self._build_env(effective_base_url, api_key, model)

                process = await asyncio.create_subprocess_exec(
                    self.cli_path,
                    "-p",
                    prompt,
                    "--output-format",
                    "text",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(repo_path),
                    env=custom_env,
                )

                # P1: 添加超时，防止 CLI 挂起导致请求永久阻塞
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(input=diff_content.encode("utf-8")),
                        timeout=300.0,
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    self._set_last_error(f"{self.DISPLAY_NAME} 执行超时（300s）")
                    return None
            finally:
                if proxy is not None:
                    await proxy.stop()

            if process.returncode != 0:
                stderr_text = stderr.decode(errors="ignore").strip()
                stdout_text = stdout.decode(errors="ignore").strip()
                actionable_error = self._extract_actionable_error(
                    stderr_text, stdout_text
                )
                logger.error(
                    f"{self.DISPLAY_NAME} 执行失败 (返回码: {process.returncode})"
                )
                logger.error(f"Stdout: {stdout_text}")
                logger.error(f"Stderr: {stderr_text}")
                self._set_last_error(
                    actionable_error
                    or f"{self.DISPLAY_NAME} 执行失败，返回码 {process.returncode}"
                )
                return None

            result = stdout.decode()

            if self.debug:
                logger.debug(f"[{self.PROVIDER_NAME} Response]\n{result}")
                if stderr:
                    logger.debug(f"[{self.PROVIDER_NAME} Stderr]\n{stderr.decode()}")

            parsed_result = self._parse_output(result)
            if not parsed_result:
                logger.error(f"{self.DISPLAY_NAME} 返回结果为空")
                self._set_last_error(f"{self.DISPLAY_NAME} 返回结果为空")
                return None

            # 写入代理捕获的真实 token 用量
            if proxy is not None and proxy.usage:
                parsed_result.usage_metadata.update(proxy.usage)

            self._set_model_metadata(parsed_result, model)

            logger.info(f"{self.DISPLAY_NAME} 分析完成")
            return parsed_result

        except Exception as e:
            logger.error(f"{self.DISPLAY_NAME} 分析异常: {e}", exc_info=True)
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
        """分析pr simple。

        Args:
            diff_content: PR 的差异内容。
            focus_areas: 审查关注点列表。
            pr_info: PR 基本信息。
            api_url: API 地址。
            api_key: API 密钥。
            custom_prompt: 自定义提示词。
            model: 模型名称。
            wire_api: 底层 API 协议标识。

        Returns:
            可能为空的结果。
        """
        self._clear_last_error()
        try:
            # P5: 截断过长 diff，防止内存溢出和 token 炸弹
            if len(diff_content) > self.MAX_DIFF_CHARS:
                diff_content = (
                    diff_content[: self.MAX_DIFF_CHARS]
                    + "\n\n... (diff 内容过长，已截断)"
                )

            prompt = self._build_review_prompt(focus_areas, pr_info, custom_prompt)

            logger.info(f"开始使用 {self.DISPLAY_NAME} 分析PR（简单模式）")

            if self.debug:
                logger.debug(f"[{self.PROVIDER_NAME} Prompt - Simple Mode]\n{prompt}")
                logger.debug(f"[Diff Content Length] {len(diff_content)} characters")

            # P3: 代理启动失败时降级为直连 API
            proxy: Optional[UsageCapturingProxy] = None
            effective_base_url = api_url or "https://api.anthropic.com"
            try:
                proxy = UsageCapturingProxy(effective_base_url)
                port = await proxy.start()
                effective_base_url = f"http://127.0.0.1:{port}"
            except Exception as proxy_exc:
                logger.warning("usage 捕获代理启动失败，将直连 API: %s", proxy_exc)
                proxy = None

            try:
                custom_env = self._build_env(effective_base_url, api_key, model)

                process = await asyncio.create_subprocess_exec(
                    self.cli_path,
                    "-p",
                    prompt,
                    "--output-format",
                    "text",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=custom_env,
                )

                # P1: 添加超时，防止 CLI 挂起导致请求永久阻塞
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(input=diff_content.encode("utf-8")),
                        timeout=300.0,
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    self._set_last_error(f"{self.DISPLAY_NAME} 执行超时（300s）（简单模式）")
                    return None
            finally:
                if proxy is not None:
                    await proxy.stop()

            if process.returncode != 0:
                stderr_text = stderr.decode(errors="ignore").strip()
                stdout_text = stdout.decode(errors="ignore").strip()
                actionable_error = self._extract_actionable_error(
                    stderr_text, stdout_text
                )
                logger.error(
                    f"{self.DISPLAY_NAME} 执行失败 (返回码: {process.returncode})"
                )
                logger.error(f"Stdout: {stdout_text}")
                logger.error(f"Stderr: {stderr_text}")
                self._set_last_error(
                    actionable_error
                    or f"{self.DISPLAY_NAME} 执行失败，返回码 {process.returncode}"
                )
                return None

            result = stdout.decode()

            if self.debug:
                logger.debug(f"[{self.PROVIDER_NAME} Response - Simple Mode]\n{result}")
                if stderr:
                    logger.debug(
                        f"[{self.PROVIDER_NAME} Stderr - Simple Mode]\n"
                        f"{stderr.decode()}"
                    )

            parsed_result = self._parse_output(result)
            if not parsed_result:
                logger.error(f"{self.DISPLAY_NAME} 返回结果为空（简单模式）")
                self._set_last_error(f"{self.DISPLAY_NAME} 返回结果为空（简单模式）")
                return None

            # 写入代理捕获的真实 token 用量
            if proxy is not None and proxy.usage:
                parsed_result.usage_metadata.update(proxy.usage)

            self._set_model_metadata(parsed_result, model)

            logger.info(f"{self.DISPLAY_NAME} 分析完成（简单模式）")
            return parsed_result

        except Exception as e:
            logger.error(f"{self.DISPLAY_NAME} 分析异常: {e}", exc_info=True)
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
        # 从父进程环境变量中去除已知凭证 key，避免泄露给 CLI 子进程
        custom_env = {
            k: v
            for k, v in os.environ.items()
            if k not in self._SENSITIVE_ENV_KEYS
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
        for code_block_match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S):
            candidate = code_block_match.group(1)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        logger.debug("JSON解析失败（code block）")

        # 使用深度追踪找到最外层完整 JSON 对象，避免 find/rfind 的括号错位问题
        start = text.find("{")
        if start != -1:
            depth = 0
            in_string = False
            escape_next = False
            for i in range(start, len(text)):
                ch = text[i]
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
                        candidate = text[start : i + 1]
                        try:
                            return json.loads(candidate)
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
