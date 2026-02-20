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

logger = logging.getLogger(__name__)


class ClaudeCodeProvider(ReviewProvider):
    """基于 Claude Code CLI 的审查 Provider"""

    PROVIDER_NAME = "claude_code"
    DISPLAY_NAME = "Claude Code"

    def __init__(self, cli_path: str = "claude", debug: bool = False):
        self.cli_path = cli_path
        self.debug = debug

    @property
    def name(self) -> str:
        return self.PROVIDER_NAME

    @property
    def display_name(self) -> str:
        return self.DISPLAY_NAME

    def _build_review_prompt(
        self, focus_areas: List[str], pr_info: dict, custom_prompt: Optional[str] = None
    ) -> str:
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
        self._clear_last_error()
        try:
            prompt = self._build_review_prompt(focus_areas, pr_info, custom_prompt)

            logger.info(f"开始使用 {self.DISPLAY_NAME} 分析PR，仓库路径: {repo_path}")

            if self.debug:
                logger.debug(f"[{self.PROVIDER_NAME} Prompt]\n{prompt}")
                logger.debug(f"[Diff Content Length] {len(diff_content)} characters")

            custom_env = self._build_env(api_url, api_key, model)

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

            stdout, stderr = await process.communicate(
                input=diff_content.encode("utf-8")
            )

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
        self._clear_last_error()
        try:
            prompt = self._build_review_prompt(focus_areas, pr_info, custom_prompt)

            logger.info(f"开始使用 {self.DISPLAY_NAME} 分析PR（简单模式）")

            if self.debug:
                logger.debug(f"[{self.PROVIDER_NAME} Prompt - Simple Mode]\n{prompt}")
                logger.debug(f"[Diff Content Length] {len(diff_content)} characters")

            custom_env = self._build_env(api_url, api_key, model)

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

            stdout, stderr = await process.communicate(
                input=diff_content.encode("utf-8")
            )

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
        custom_env = os.environ.copy()
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
        if model and model.strip():
            result.usage_metadata["model"] = model.strip()

    def _parse_output(self, output: str) -> Optional[ReviewResult]:
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
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        if code_block_match:
            candidate = code_block_match.group(1)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                logger.debug("JSON解析失败（code block）", exc_info=True)

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace : last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                logger.debug("JSON解析失败（brace scan）", exc_info=True)

        return None

    @staticmethod
    def _extract_actionable_error(stderr_text: str, stdout_text: str) -> str:
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
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
