"""ForgeProvider — ReviewProvider 接口适配器

将 Forge agentic engine 适配到现有 ReviewProvider 接口。
与 ClaudeCodeProvider/CodexProvider 对外行为一致。

关键映射：
  ForgeResult.structured_data → ReviewResult (来自 submit_review 工具调用)
  ForgeResult.final_text (降级) → ReviewResult (暴力 JSON 提取兜底)
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.core import settings
from ..base import InlineComment, ReviewProvider, ReviewResult
from ..parsing import coerce_int, extract_json_payload, parse_inline_comment
from .api_client import AnthropicClient
from .scenarios.review import run_review
from .types import ForgeResult

logger = logging.getLogger(__name__)

DEFAULT_FORGE_MODEL = "claude-sonnet-4-20250514"
DEFAULT_FORGE_BASE_URL = "https://api.anthropic.com"


class ForgeProvider(ReviewProvider):
    PROVIDER_NAME = "forge"
    DISPLAY_NAME = "Forge"
    MAX_DIFF_BYTES = 200_000

    def __init__(self, cli_path: str = "forge", debug: bool = False):
        self.cli_path = cli_path
        self.debug = debug

    @property
    def name(self) -> str:
        return self.PROVIDER_NAME

    @property
    def display_name(self) -> str:
        return self.DISPLAY_NAME

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
        del wire_api

        resolved_key = api_key or getattr(settings, "forge_api_key", "") or ""
        if not resolved_key:
            self._set_last_error(
                "Forge: 未配置 API Key（FORGE_API_KEY 或 api_key 参数）"
            )
            return None

        resolved_url = api_url or getattr(
            settings, "forge_base_url", DEFAULT_FORGE_BASE_URL
        )
        resolved_model = model or getattr(settings, "forge_model", DEFAULT_FORGE_MODEL)
        resolved_max_turns = max(1, int(getattr(settings, "forge_max_turns", 5) or 5))

        client = AnthropicClient(api_key=resolved_key, base_url=resolved_url)

        if len(diff_content.encode("utf-8")) > self.MAX_DIFF_BYTES:
            diff_content = (
                diff_content[: self.MAX_DIFF_BYTES] + "\n\n... (diff 过长，已截断)"
            )

        try:
            forge_result = await run_review(
                client=client,
                model=resolved_model,
                repo_path=repo_path,
                diff_content=diff_content,
                focus_areas=focus_areas,
                pr_info=pr_info,
                custom_prompt=custom_prompt,
                max_turns=resolved_max_turns,
            )
        except Exception as e:
            logger.exception("Forge 审查运行异常")
            self._set_last_error(f"Forge 运行失败: {e}")
            return None

        if (
            forge_result.error
            and not forge_result.structured_data
            and not forge_result.final_text
        ):
            self._set_last_error(forge_result.error)
            return None

        return self._convert_result(forge_result, resolved_model)

    def _convert_result(self, result: ForgeResult, model: str) -> ReviewResult:
        # 策略1: 结构化数据（来自 submit_review 工具调用）
        if result.structured_data:
            data = result.structured_data
            comments = []
            for c in data.get("inline_comments", []):
                if not c.get("path") or not c.get("comment"):
                    continue
                comments.append(
                    InlineComment(
                        path=c["path"],
                        comment=c["comment"],
                        new_line=coerce_int(c.get("new_line")),
                        old_line=coerce_int(c.get("old_line")),
                        severity=c.get("severity"),
                        suggestion=c.get("suggestion"),
                    )
                )
            return ReviewResult(
                summary_markdown=data.get("summary_markdown", ""),
                inline_comments=comments,
                overall_severity=data.get("overall_severity"),
                raw_output="",
                provider_name=self.PROVIDER_NAME,
                usage_metadata={
                    "input_tokens": result.usage.input_tokens,
                    "output_tokens": result.usage.output_tokens,
                    "cache_creation_input_tokens": result.usage.cache_creation_input_tokens,
                    "cache_read_input_tokens": result.usage.cache_read_input_tokens,
                    "model": model,
                    "turns": result.turns,
                    "tool_calls": result.tool_calls,
                },
            )

        # 策略2: 文本 JSON 提取（降级兜底）
        parsed = extract_json_payload(result.final_text)
        if parsed:
            comments = []
            for c in parsed.get("inline_comments", parsed.get("comments", [])):
                if not c.get("path") or not c.get("comment"):
                    continue
                comment = parse_inline_comment(c)
                if comment:
                    comments.append(comment)
            return ReviewResult(
                summary_markdown=parsed.get(
                    "summary_markdown", parsed.get("summary", "")
                ),
                inline_comments=comments,
                overall_severity=parsed.get("overall_severity", parsed.get("severity")),
                raw_output=result.final_text,
                provider_name=self.PROVIDER_NAME,
                usage_metadata={
                    "input_tokens": result.usage.input_tokens,
                    "output_tokens": result.usage.output_tokens,
                    "model": model,
                    "turns": result.turns,
                },
            )

        # 策略3: 纯文本保底
        return ReviewResult(
            summary_markdown=result.final_text,
            inline_comments=[],
            overall_severity=None,
            raw_output=result.final_text,
            provider_name=self.PROVIDER_NAME,
            usage_metadata={
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "model": model,
                "turns": result.turns,
            },
        )
