"""
Claude Code CLI调用模块 (backward-compatibility wrapper)

已迁移至 app.services.providers.claude_code.ClaudeCodeProvider
本模块保留旧的导入路径，供现有代码平滑过渡。
"""

import logging
from pathlib import Path
from typing import List, Optional

from app.services.providers.base import InlineComment as InlineCommentSuggestion
from app.services.providers.base import ReviewResult as ClaudeReviewResult
from app.services.providers.claude_code import ClaudeCodeProvider

logger = logging.getLogger(__name__)

__all__ = ["ClaudeAnalyzer", "ClaudeReviewResult", "InlineCommentSuggestion"]


class ClaudeAnalyzer:
    """Claude Code分析器 (backward-compatibility wrapper)"""

    def __init__(self, claude_code_path: str = "claude", debug: bool = False):
        self._provider = ClaudeCodeProvider(cli_path=claude_code_path, debug=debug)

    async def analyze_pr(
        self,
        repo_path: Path,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Optional[ClaudeReviewResult]:
        return await self._provider.analyze_pr(
            repo_path,
            diff_content,
            focus_areas,
            pr_info,
            api_url=api_url,
            api_key=api_key,
        )

    async def analyze_pr_simple(
        self,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Optional[ClaudeReviewResult]:
        return await self._provider.analyze_pr_simple(
            diff_content,
            focus_areas,
            pr_info,
            api_url=api_url,
            api_key=api_key,
        )
