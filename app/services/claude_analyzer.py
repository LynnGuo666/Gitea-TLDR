"""
Claude Code CLI调用模块
"""
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class InlineCommentSuggestion:
    """Claude输出的行级评论建议"""

    path: str
    comment: str
    new_line: Optional[int] = None
    old_line: Optional[int] = None
    severity: Optional[str] = None
    suggestion: Optional[str] = None

    def build_body(self) -> str:
        """组合完整的评论正文"""
        parts: List[str] = []
        if self.severity:
            parts.append(f"**严重级别**: {self.severity}")

        comment_text = (self.comment or "").strip()
        if comment_text:
            parts.append(comment_text)

        suggestion_text = (self.suggestion or "").strip()
        if suggestion_text:
            parts.append(f"**建议**：{suggestion_text}")

        return "\n\n".join(parts).strip()


@dataclass
class ClaudeReviewResult:
    """Claude分析结果数据结构"""

    summary_markdown: str
    inline_comments: List[InlineCommentSuggestion] = field(default_factory=list)
    overall_severity: Optional[str] = None
    raw_output: str = ""

    def summary_text(self) -> str:
        """获取最终展示的总结内容"""
        return (self.summary_markdown or self.raw_output or "").strip()

    def indicates_failure(self) -> bool:
        """判断是否存在严重问题"""
        severity = (self.overall_severity or "").lower()
        if severity in {"critical", "blocker", "high", "failure"}:
            return True

        summary = self.summary_text()
        if not summary:
            return False

        summary_lower = summary.lower()
        if "严重" in summary or "critical" in summary_lower:
            return True

        for comment in self.inline_comments:
            if comment.severity and comment.severity.lower() in {
                "critical",
                "high",
                "blocker",
            }:
                return True

        return False


class ClaudeAnalyzer:
    """Claude Code分析器"""

    def __init__(self, claude_code_path: str = "claude", debug: bool = False):
        """
        初始化Claude分析器

        Args:
            claude_code_path: Claude Code CLI的路径
            debug: 是否开启debug模式
        """
        self.claude_code_path = claude_code_path
        self.debug = debug

    def _build_review_prompt(self, focus_areas: List[str], pr_info: dict) -> str:
        """
        构建审查提示词（不包含diff内容，diff通过stdin传递）

        Args:
            focus_areas: 审查重点领域
            pr_info: PR信息

        Returns:
            审查提示词
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
- 标题: {pr_info.get('title', 'N/A')}
- 描述: {pr_info.get('body', 'N/A')}
- 作者: {pr_info.get('user', {}).get('login', 'N/A')}

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
        return prompt

    async def analyze_pr(
        self,
        repo_path: Path,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
    ) -> Optional[ClaudeReviewResult]:
        """
        使用Claude Code分析PR

        Args:
            repo_path: 仓库本地路径
            diff_content: PR的diff内容
            focus_areas: 审查重点领域
            pr_info: PR信息

        Returns:
            ClaudeReviewResult
        """
        try:
            prompt = self._build_review_prompt(focus_areas, pr_info)

            logger.info(f"开始使用Claude Code分析PR，仓库路径: {repo_path}")

            if self.debug:
                logger.debug(f"[Claude Prompt]\n{prompt}")
                logger.debug(f"[Diff Content Length] {len(diff_content)} characters")

            process = await asyncio.create_subprocess_exec(
                self.claude_code_path,
                "-p",
                prompt,
                "--output-format",
                "text",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(repo_path),
            )

            stdout, stderr = await process.communicate(
                input=diff_content.encode("utf-8")
            )

            if process.returncode != 0:
                logger.error(f"Claude Code执行失败 (返回码: {process.returncode})")
                logger.error(f"Stderr: {stderr.decode()}")
                return None

            result = stdout.decode()

            if self.debug:
                logger.debug(f"[Claude Response]\n{result}")
                if stderr:
                    logger.debug(f"[Claude Stderr]\n{stderr.decode()}")

            parsed_result = self._parse_claude_output(result)
            if not parsed_result:
                logger.error("Claude返回结果为空")
                return None

            logger.info("Claude Code分析完成")
            return parsed_result

        except Exception as e:
            logger.error(f"Claude Code分析异常: {e}", exc_info=True)
            return None

    async def analyze_pr_simple(
        self, diff_content: str, focus_areas: List[str], pr_info: dict
    ) -> Optional[ClaudeReviewResult]:
        """
        简单模式：不依赖完整代码库，仅分析diff

        Args:
            diff_content: PR的diff内容
            focus_areas: 审查重点领域
            pr_info: PR信息

        Returns:
            ClaudeReviewResult
        """
        try:
            prompt = self._build_review_prompt(focus_areas, pr_info)

            logger.info("开始使用Claude Code分析PR（简单模式）")

            if self.debug:
                logger.debug(f"[Claude Prompt - Simple Mode]\n{prompt}")
                logger.debug(f"[Diff Content Length] {len(diff_content)} characters")

            process = await asyncio.create_subprocess_exec(
                self.claude_code_path,
                "-p",
                prompt,
                "--output-format",
                "text",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate(
                input=diff_content.encode("utf-8")
            )

            if process.returncode != 0:
                logger.error(f"Claude Code执行失败 (返回码: {process.returncode})")
                logger.error(f"Stderr: {stderr.decode()}")
                return None

            result = stdout.decode()

            if self.debug:
                logger.debug(f"[Claude Response - Simple Mode]\n{result}")
                if stderr:
                    logger.debug(f"[Claude Stderr - Simple Mode]\n{stderr.decode()}")

            parsed_result = self._parse_claude_output(result)
            if not parsed_result:
                logger.error("Claude返回结果为空（简单模式）")
                return None

            logger.info("Claude Code分析完成（简单模式）")
            return parsed_result

        except Exception as e:
            logger.error(f"Claude Code分析异常: {e}", exc_info=True)
            return None

    def _parse_claude_output(self, output: str) -> Optional[ClaudeReviewResult]:
        """将Claude输出解析为结构化结果"""
        sanitized = (output or "").strip()
        if not sanitized:
            return None

        data = self._extract_json_payload(sanitized)
        if not data:
            logger.warning("Claude响应未按JSON格式返回，将使用原始文本作为总结")
            return ClaudeReviewResult(
                summary_markdown=sanitized,
                inline_comments=[],
                raw_output=sanitized,
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

        inline_comments: List[InlineCommentSuggestion] = []
        for item in data.get("inline_comments") or []:
            parsed = self._parse_inline_comment(item)
            if parsed:
                inline_comments.append(parsed)

        return ClaudeReviewResult(
            summary_markdown=summary or sanitized,
            inline_comments=inline_comments,
            overall_severity=severity,
            raw_output=sanitized,
        )

    def _parse_inline_comment(
        self, item: Dict[str, Any]
    ) -> Optional[InlineCommentSuggestion]:
        """解析单条行级评论"""
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

        return InlineCommentSuggestion(
            path=path,
            comment=comment,
            new_line=new_line,
            old_line=old_line,
            severity=severity,
            suggestion=suggestion,
        )

    def _extract_json_payload(self, text: str) -> Optional[Dict[str, Any]]:
        """尝试从Claude输出中提取JSON"""
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
    def _coerce_int(value: Any) -> Optional[int]:
        """安全地将值转换为int"""
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
