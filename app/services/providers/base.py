"""
审查引擎 Provider 抽象基类与通用数据结构

所有 Provider 实现（如 ClaudeCodeProvider）都需继承 ReviewProvider 并实现
analyze_pr 抽象方法。
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


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


IssueFallbackMode = Literal["tool", "text_json", "raw_text"]


@dataclass
class IssueResult:
    """Issue 分析结果 (provider-agnostic)"""

    structured_data: Dict[str, Any] = field(default_factory=dict)
    final_text: str = ""
    fallback_mode: IssueFallbackMode = "tool"
    provider_name: str = ""
    model: str = ""
    usage_metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


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
        """处理last error相关逻辑。

        Args:
            无。

        Returns:
            可能为空的结果。
        """
        return getattr(self, "_last_error", None)

    def _clear_last_error(self) -> None:
        """处理last error相关逻辑。

        Args:
            无。

        Returns:
            无返回值。
        """
        setattr(self, "_last_error", None)

    def _set_last_error(self, message: Optional[str]) -> None:
        """处理last error相关逻辑。

        Args:
            message: 错误消息文本。

        Returns:
            无返回值。
        """
        text = (message or "").strip()
        if not text:
            self._clear_last_error()
            return
        if len(text) > 500:
            text = text[:500] + "..."
        text = re.sub(
            r"(?i)(token|key|secret|authorization|password|passwd|bearer|credential)\s*[:=]\s*([^\s,;]+)",
            r"\1=[REDACTED]",
            text,
        )
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
    ) -> Optional[ReviewResult]:
        """分析PR。

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
        ...

    def supports_issue(self) -> bool:
        """Provider 是否支持 Issue 分析场景；默认不支持。"""
        return False

    async def analyze_issue(
        self,
        repo_path: Path,
        issue_info: Dict[str, Any],
        similar_candidates: List[Dict[str, Any]],
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_turns: Optional[int] = None,
    ) -> Optional[IssueResult]:
        """分析 Issue（可选实现）。

        默认实现抛出 NotImplementedError；实现此方法的 Provider 必须同时
        让 supports_issue() 返回 True。
        """
        raise NotImplementedError(
            f"Provider {self.name} 尚未实现 Issue 分析场景"
        )
