"""
审查引擎 Provider 抽象基类与通用数据结构

所有 Provider 实现（如 ClaudeCodeProvider）都需继承 ReviewProvider 并实现
analyze_pr / analyze_pr_simple 两个抽象方法。
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class InlineComment:
    """行级评论建议 (provider-agnostic)"""

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
class ReviewResult:
    """代码审查结果 (provider-agnostic)"""

    summary_markdown: str
    inline_comments: List[InlineComment] = field(default_factory=list)
    overall_severity: Optional[str] = None
    raw_output: str = ""
    provider_name: str = ""
    usage_metadata: Dict[str, Any] = field(default_factory=dict)

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


@dataclass
class ProviderConfig:
    """Provider 运行时配置"""

    cli_path: str = ""
    debug: bool = False
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class ReviewProvider(ABC):
    """代码审查 Provider 抽象基类

    每个 Provider（如 ClaudeCodeProvider）需要实现：
    - analyze_pr: 使用完整代码库上下文分析 PR
    - analyze_pr_simple: 仅基于 diff 分析 PR（降级模式）
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 标识符，如 'claude_code'"""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """人类可读名称，如 'Claude Code'"""
        ...

    @property
    def last_error(self) -> Optional[str]:
        return getattr(self, "_last_error", None)

    def _clear_last_error(self) -> None:
        setattr(self, "_last_error", None)

    def _set_last_error(self, message: Optional[str]) -> None:
        text = (message or "").strip()
        if not text:
            self._clear_last_error()
            return
        text = re.sub(
            r"(?i)(token|key|secret|authorization)\s*[:=]\s*([^\s,;]+)",
            r"\1=[REDACTED]",
            text,
        )
        if len(text) > 500:
            text = text[:500] + "..."
        setattr(self, "_last_error", text)

    @abstractmethod
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
    ) -> Optional[ReviewResult]: ...

    @abstractmethod
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
    ) -> Optional[ReviewResult]: ...
