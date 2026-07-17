"""审查结果发布协作类（拆分自 _perform_review 原 :688-959）。

封装评论发布（变更概览 + 审查发现）、create_review / request_reviewer、
create_commit_status。所有方法记录 gitea_api_calls 到传入的计数器。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core import settings
from app.review.providers.base import InlineComment, ReviewResult
from app.services.db_service import DBService
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_PROVIDER_DISPLAY: Dict[str, str] = {
    "forge": "Forge",
    "claude_code": "Claude Code",
    "codex_cli": "Codex CLI",
}


class ReviewPublisher:
    """向 Gitea 发布审查结果（评论 / review / status）。"""

    def __init__(self, session: AsyncSession, gitea_client: Any):
        self.session = session
        self.gitea_client = gitea_client
        self.db_service = DBService(session)

    async def create_initial_comment(
        self,
        *,
        owner: str,
        repo_name: str,
        pr_number: int,
        features: List[str],
    ) -> Optional[int]:
        """若启用 comment，创建「正在审查中」占位评论，返回 comment_id。"""
        if "comment" not in features:
            return None
        comment_id = await self.gitea_client.create_issue_comment(
            owner, repo_name, pr_number, "## 自动代码审查\n\n正在审查中，请稍候..."
        )
        return comment_id

    async def set_pending_status(
        self,
        *,
        owner: str,
        repo_name: str,
        head_sha: str,
        features: List[str],
    ) -> bool:
        if "status" not in features:
            return False
        await self.gitea_client.create_commit_status(
            owner,
            repo_name,
            head_sha,
            "pending",
            description="代码审查进行中...",
        )
        return True

    async def publish_error_comment(
        self,
        *,
        owner: str,
        repo_name: str,
        comment_id: Optional[int],
        pr_number: int,
        error_message: str,
        features: List[str],
    ) -> None:
        """失败时更新/创建错误评论。"""
        if "comment" not in features:
            return
        body = f"## 自动代码审查\n\n审查失败：{error_message}"
        if comment_id:
            await self.gitea_client.update_issue_comment(
                owner, repo_name, comment_id, body
            )
        else:
            await self.gitea_client.create_issue_comment(
                owner, repo_name, pr_number, body
            )

    async def set_error_status(
        self,
        *,
        owner: str,
        repo_name: str,
        head_sha: str,
        description: str,
        features: List[str],
    ) -> None:
        if "status" not in features:
            return
        await self.gitea_client.create_commit_status(
            owner,
            repo_name,
            head_sha,
            "error",
            description=description,
        )

    async def publish_success(
        self,
        *,
        owner: str,
        repo_name: str,
        pr_number: int,
        comment_id: Optional[int],
        head_sha: str,
        features: List[str],
        analysis_result: ReviewResult,
    ) -> bool:
        """发布成功结果（概览评论 + 审查发现评论 + review + status），返回 overall success。"""
        success = True
        summary_markdown = analysis_result.summary_text() or "未生成审查报告"
        footer = self._build_review_footer(analysis_result)

        if "comment" in features:
            overview = analysis_result.pr_overview_markdown or summary_markdown
            comment1_body = f"## 代码变更概览\n\n{overview}{footer}"
            if comment_id:
                success &= await self.gitea_client.update_issue_comment(
                    owner, repo_name, comment_id, comment1_body
                )
            else:
                new_comment_id = await self.gitea_client.create_issue_comment(
                    owner, repo_name, pr_number, comment1_body
                )
                success &= new_comment_id is not None

            if analysis_result.pr_overview_markdown:
                issues_text = (analysis_result.summary_markdown or "").strip()
                if issues_text:
                    await self.gitea_client.create_issue_comment(
                        owner,
                        repo_name,
                        pr_number,
                        f"## 审查发现\n\n{issues_text}{footer}",
                    )

        if "review" in features:
            review_comments = self._build_review_comments(analysis_result)
            review_success = await self.gitea_client.create_review(
                owner,
                repo_name,
                pr_number,
                summary_markdown,
                event="COMMENT",
                comments=review_comments if review_comments else None,
                commit_id=head_sha,
            )
            success &= review_success

            if review_success and await self._should_request_reviewer():
                bot_username = await self._bot_username()
                if bot_username:
                    await self.gitea_client.request_reviewer(
                        owner, repo_name, pr_number, [bot_username]
                    )

        if "status" in features:
            state = "failure" if analysis_result.indicates_failure() else "success"
            success &= await self.gitea_client.create_commit_status(
                owner,
                repo_name,
                head_sha,
                state,
                description="代码审查完成",
            )

        return success

    async def _should_request_reviewer(self) -> bool:
        return await self.db_service.get_app_setting(
            "auto_request_reviewer", settings.auto_request_reviewer
        )

    async def _bot_username(self) -> Optional[str]:
        return await self.db_service.get_app_setting(
            "bot_username", settings.bot_username
        )

    @staticmethod
    def _build_review_footer(analysis_result: ReviewResult) -> str:
        engine = _PROVIDER_DISPLAY.get(
            analysis_result.provider_name, analysis_result.provider_name
        )
        model = (analysis_result.usage_metadata.get("model") or "").strip()
        if model:
            return f"\n\n---\n*审查引擎：{engine} · 模型：{model}*"
        return f"\n\n---\n*审查引擎：{engine}*"

    @staticmethod
    def _build_review_comments(analysis_result: ReviewResult) -> List[Dict[str, Any]]:
        comments: List[Dict[str, Any]] = []
        for inline in analysis_result.inline_comments:
            payload = ReviewPublisher._inline_to_review_comment(inline)
            if payload:
                comments.append(payload)
        return comments

    @staticmethod
    def _inline_to_review_comment(inline: InlineComment) -> Optional[Dict[str, Any]]:
        path = (inline.path or "").strip()
        if not path:
            return None
        body = inline.build_body()
        if not body:
            return None
        new_position = inline.new_line if inline.new_line is not None else 0
        old_position = inline.old_line if inline.old_line is not None else 0
        return {
            "path": path,
            "body": body,
            "new_position": new_position,
            "old_position": old_position,
        }
