"""
Webhook处理模块
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from app.core import settings
from app.core.database import Database
from app.review.engine import ReviewEngine
from app.gitea.command_parser import CommandParser
from app.services.db_service import DBService
from app.services.repositories import WebhookRepository
from app.gitea.client import GiteaClient
from app.review.orchestrator import ReviewOrchestrator
from app.review.issue_service import IssueAnalysisService
from app.gitea.repo_manager import RepoManager
from app.models import (
    WEBHOOK_STATUS_ERROR,
    WEBHOOK_STATUS_PROCESSING,
    WEBHOOK_STATUS_RETRYING,
    WEBHOOK_STATUS_SUCCESS,
)

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Webhook处理器"""

    def __init__(
        self,
        gitea_client: GiteaClient,
        repo_manager: RepoManager,
        review_engine: ReviewEngine,
        database: Optional[Database] = None,
        bot_username: Optional[str] = None,
    ):
        """初始化实例状态。

        Args:
            gitea_client: Gitea API 客户端实例。
            repo_manager: 仓库管理器实例。
            review_engine: 审查引擎实例。
            database: 数据库实例。
            bot_username: 机器人用户名。

        Returns:
            无返回值。
        """
        self.gitea_client = gitea_client
        self.repo_manager = repo_manager
        self.review_engine = review_engine
        self.database = database
        self.command_parser = CommandParser(bot_username)
        self.issue_analysis_service = IssueAnalysisService(
            gitea_client=gitea_client,
            repo_manager=repo_manager,
            database=database,
        )

    def parse_review_features(self, features_header: Optional[str]) -> List[str]:
        """
        解析审查功能标头

        Args:
            features_header: X-Review-Features标头值

        Returns:
            功能列表
        """
        if not features_header:
            return ["comment"]  # 默认只发评论

        features = [f.strip().lower() for f in features_header.split(",")]
        valid_features = ["comment", "review", "status"]
        return [f for f in features if f in valid_features]

    def parse_review_focus(self, focus_header: Optional[str]) -> List[str]:
        """
        解析审查重点标头

        Args:
            focus_header: X-Review-Focus标头值

        Returns:
            审查重点列表
        """
        if not focus_header:
            return list(settings.default_review_focus)

        focus_areas = [f.strip().lower() for f in focus_header.split(",")]
        valid_areas = ["quality", "security", "performance", "logic"]
        return [f for f in focus_areas if f in valid_areas]

    async def handle_pull_request(
        self,
        payload: Dict[str, Any],
        features: Optional[List[str]],
        focus_areas: Optional[List[str]],
    ) -> bool:
        """
        处理Pull Request事件

        Args:
            payload: Webhook payload
            features: 启用的功能列表（None 表示按仓库配置回退）
            focus_areas: 审查重点列表（None 表示按仓库配置回退）

        Returns:
            是否处理成功
        """
        try:
            action = payload.get("action")
            pr_data = payload.get("pull_request", {})
            repo_data = payload.get("repository", {})

            # 只处理opened和synchronized事件
            if action not in ["opened", "synchronized"]:
                logger.info(f"忽略PR事件: {action}")
                return True

            # 提取关键信息
            owner = repo_data.get("owner", {}).get("login")
            repo_name = repo_data.get("name")
            pr_number = pr_data.get("number")
            pr_title = pr_data.get("title")
            head_branch = pr_data.get("head", {}).get("ref")
            base_branch = pr_data.get("base", {}).get("ref")
            actor_username = self._extract_actor_username(payload)

            # Bot 自触发防护：PR 作者或发送者是 bot 时直接忽略
            pr_author = pr_data.get("user", {}).get("login") or pr_data.get(
                "user", {}
            ).get("username")
            if self._is_bot_actor(pr_author) or self._is_bot_actor(actor_username):
                logger.info("跳过 bot 自触发 PR: %s/%s#%s", owner, repo_name, pr_number)
                return True

            logger.info(
                f"处理PR: {owner}/{repo_name}#{pr_number} "
                f"({head_branch} -> {base_branch})"
            )
            del pr_title  # 避免在日志里泄露标题

            return await self._perform_review(
                owner=owner,
                repo_name=repo_name,
                pr_number=pr_number,
                pr_data=pr_data,
                features=features,
                focus_areas=focus_areas,
                trigger_type="auto",
                actor_username=actor_username,
            )

        except Exception as e:
            logger.error(f"处理PR异常: {e}", exc_info=True)
            return False

    async def _process_with_retry(
        self,
        payload: Dict[str, Any],
        event_type: str,
        handler_func,
        max_retries: int = 3,
        base_delay: float = 5.0,
    ):
        """带重试的 Webhook 处理包装器。

        创建 WebhookLog 记录，失败时自动重试，成功或超过重试次数后更新日志。
        """
        repo_data = payload.get("repository", {})
        owner = repo_data.get("owner", {}).get("login")
        repo_name = repo_data.get("name")
        request_id = str(uuid.uuid4())[:8]

        repository_id = 0
        if self.database and owner and repo_name:
            try:
                async with self.database.session() as session:
                    db_service = DBService(session)
                    repo = await db_service.get_repository(owner, repo_name)
                    if repo:
                        repository_id = repo.id
            except Exception:
                pass

        log_id: Optional[int] = None
        if self.database:
            try:
                async with self.database.session() as session:
                    webhook_repo = WebhookRepository(session)
                    log = await webhook_repo.create_webhook_event(
                        request_id=request_id,
                        repository_id=repository_id,
                        event_type=event_type,
                        payload=json.dumps(payload, ensure_ascii=False),
                        status=WEBHOOK_STATUS_PROCESSING,
                    )
                    log_id = log.id
            except Exception as e:
                logger.warning(f"创建 WebhookLog 失败: {e}")

        last_error: Optional[str] = None
        for attempt in range(max_retries + 1):
            start_time = time.monotonic()
            try:
                success = await handler_func()
                elapsed_ms = int((time.monotonic() - start_time) * 1000)

                if log_id and self.database:
                    await self._update_log(
                        log_id,
                        status=WEBHOOK_STATUS_SUCCESS
                        if success
                        else WEBHOOK_STATUS_ERROR,
                        processing_time_ms=elapsed_ms,
                        error_message=None if success else "handler returned False",
                    )
                return

            except Exception as e:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                last_error = str(e)[:1000]
                logger.error(
                    f"Webhook 处理失败 (尝试 {attempt + 1}/{max_retries + 1}): {last_error}"
                )

                if log_id and self.database:
                    await self._update_log(
                        log_id,
                        status=WEBHOOK_STATUS_RETRYING
                        if attempt < max_retries
                        else WEBHOOK_STATUS_ERROR,
                        processing_time_ms=elapsed_ms,
                        error_message=last_error,
                        increment_retry=True,
                    )

                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    logger.info(f"将在 {delay:.1f}s 后重试...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Webhook 处理最终失败 (request_id={request_id}): {last_error}"
                    )

    async def _update_log(
        self,
        log_id: int,
        status: str,
        processing_time_ms: int,
        error_message: Optional[str] = None,
        increment_retry: bool = False,
    ):
        try:
            if not self.database:
                return
            async with self.database.session() as session:
                repo = WebhookRepository(session)
                await repo.update_webhook_event(
                    event_id=log_id,
                    status=status,
                    error_message=error_message,
                    processing_time_ms=processing_time_ms,
                    increment_retry=increment_retry,
                )
        except Exception:
            pass

    async def process_webhook_async(
        self,
        payload: Dict[str, Any],
        features: Optional[List[str]],
        focus_areas: Optional[List[str]],
    ):
        """异步处理PR webhook（后台任务，带重试）"""
        await self._process_with_retry(
            payload=payload,
            event_type="pull_request",
            handler_func=lambda: self.handle_pull_request(
                payload, features, focus_areas
            ),
        )

    async def process_comment_async(self, payload: Dict[str, Any]):
        """异步处理评论webhook（后台任务，带重试）"""
        await self._process_with_retry(
            payload=payload,
            event_type="issue_comment",
            handler_func=lambda: self.handle_issue_comment(payload),
        )

    async def process_issue_async(self, payload: Dict[str, Any]):
        """异步处理Issue webhook（后台任务，带重试）"""
        await self._process_with_retry(
            payload=payload,
            event_type="issues",
            handler_func=lambda: self.handle_issue(payload),
        )

    async def handle_issue_comment(self, payload: Dict[str, Any]) -> bool:
        """
        处理 Issue 评论事件（用于手动触发 PR 审查或 Issue 分析）

        Args:
            payload: Webhook payload

        Returns:
            是否处理成功
        """
        try:
            action = payload.get("action")
            comment_data = payload.get("comment", {})
            issue_data = payload.get("issue", {})
            repo_data = payload.get("repository", {})

            # 只处理新创建的评论
            if action != "created":
                logger.info(f"忽略评论事件: {action}")
                return True

            # 获取评论内容
            comment_body = comment_data.get("body", "")

            # 解析命令
            command = self.command_parser.parse_comment(comment_body)
            if not command:
                logger.debug("评论中未包含有效的bot命令")
                return True

            commenter = comment_data.get("user", {}).get("login") or comment_data.get(
                "user", {}
            ).get("username")
            if self._is_bot_actor(commenter):
                logger.info("忽略 bot 自发评论中的命令")
                return True

            logger.info(f"检测到手动触发命令: {command.command}")

            # 检查是否是PR
            pull_request = issue_data.get("pull_request")
            if pull_request:
                if command.command != "review":
                    logger.info("PR 评论中的命令不是 /review，忽略")
                    return True

                # 提取PR信息
                owner = repo_data.get("owner", {}).get("login")
                repo_name = repo_data.get("name")
                pr_number = issue_data.get("number")
                actor_username = (
                    comment_data.get("user", {}).get("login")
                    or comment_data.get("user", {}).get("username")
                    or payload.get("sender", {}).get("login")
                    or payload.get("sender", {}).get("username")
                )

                logger.info(
                    f"手动触发PR审查: {owner}/{repo_name}#{pr_number} "
                    f"features={command.features}, focus={command.focus_areas}"
                )

                # 获取完整的PR信息
                pr_data = await self.gitea_client.get_pull_request(
                    owner, repo_name, pr_number
                )
                if not pr_data:
                    logger.error("无法获取PR详情")
                    return False

                # 执行审查
                return await self._perform_review(
                    owner=owner,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    pr_data=pr_data,
                    features=command.features,
                    focus_areas=command.focus_areas,
                    trigger_type="manual",
                    actor_username=actor_username,
                )

            if command.command != "issue":
                logger.info("普通 Issue 评论中的命令不是 /issue，忽略")
                return True

            owner = repo_data.get("owner", {}).get("login")
            repo_name = repo_data.get("name")
            actor_username = (
                comment_data.get("user", {}).get("login")
                or comment_data.get("user", {}).get("username")
                or payload.get("sender", {}).get("login")
                or payload.get("sender", {}).get("username")
            )

            if not await self._is_issue_manual_enabled(owner, repo_name):
                logger.info("仓库未启用手动 /issue 命令，忽略")
                return True

            self.issue_analysis_service.database = self.database
            return await self.issue_analysis_service.analyze_issue(
                payload,
                trigger_type="manual",
                source_comment_id=comment_data.get("id"),
                actor_username=actor_username,
                focus_areas=command.focus_areas,
            )

        except Exception as e:
            logger.error(f"处理评论异常: {e}", exc_info=True)
            return False

    async def handle_issue(self, payload: Dict[str, Any]) -> bool:
        """
        处理普通 Issue 事件。

        Args:
            payload: Webhook payload

        Returns:
            是否处理成功
        """
        try:
            action = payload.get("action")
            issue_data = payload.get("issue", {})
            repo_data = payload.get("repository", {})

            if issue_data.get("pull_request"):
                logger.info("issues webhook 对应的是 PR，忽略")
                return True

            if action not in ["opened", "reopened"]:
                logger.info(f"忽略 Issue 事件: {action}")
                return True

            owner = repo_data.get("owner", {}).get("login")
            repo_name = repo_data.get("name")
            actor_username = (
                payload.get("sender", {}).get("login")
                or payload.get("sender", {}).get("username")
                or issue_data.get("user", {}).get("login")
                or issue_data.get("user", {}).get("username")
            )

            issue_author = issue_data.get("user", {}).get("login") or issue_data.get(
                "user", {}
            ).get("username")
            if self._is_bot_actor(issue_author) or self._is_bot_actor(actor_username):
                logger.info(
                    "跳过 bot 自开 Issue: %s/%s#%s",
                    owner,
                    repo_name,
                    issue_data.get("number"),
                )
                return True

            if not await self._is_issue_auto_enabled(owner, repo_name):
                logger.info("仓库未启用自动 Issue 分析，忽略")
                return True

            self.issue_analysis_service.database = self.database
            return await self.issue_analysis_service.analyze_issue(
                payload,
                trigger_type="auto",
                actor_username=actor_username,
            )
        except Exception as e:
            logger.error(f"处理 Issue 异常: {e}", exc_info=True)
            return False

    async def _perform_review(
        self,
        owner: str,
        repo_name: str,
        pr_number: int,
        pr_data: Dict[str, Any],
        features: Optional[List[str]],
        focus_areas: Optional[List[str]],
        trigger_type: str = "auto",
        actor_username: Optional[str] = None,
    ) -> bool:
        """执行PR审查（薄委托到 ReviewOrchestrator）。

        实际编排逻辑（配置解析 / DB 记录 / 克隆 / 引擎调用 / 评论发布 /
        status / usage / 异常处理）见 app/review/orchestrator/。
        """
        if self.database is None:
            logger.error("数据库未初始化，无法执行审查")
            return False
        orchestrator = ReviewOrchestrator(
            gitea_client=self.gitea_client,
            repo_manager=self.repo_manager,
            review_engine=self.review_engine,
            database=self.database,
        )
        return await orchestrator.run(
            owner=owner,
            repo_name=repo_name,
            pr_number=pr_number,
            pr_data=pr_data,
            features=features,
            focus_areas=focus_areas,
            trigger_type=trigger_type,
            actor_username=actor_username,
        )

    async def _is_issue_auto_enabled(
        self, owner: Optional[str], repo_name: Optional[str]
    ) -> bool:
        """判断仓库是否启用自动 Issue 分析。"""
        if not self.database or not owner or not repo_name:
            return True

        async with self.database.session() as session:
            db_service = DBService(session)
            repo = await db_service.get_repository(owner, repo_name)
            if not repo:
                return True
            feature = await db_service.get_repository_feature(repo.id, "issue")
            if not feature:
                return True
            return bool(feature.enabled and feature.auto_on_open)

    async def _is_issue_manual_enabled(
        self, owner: Optional[str], repo_name: Optional[str]
    ) -> bool:
        """判断仓库是否启用手动 /issue 分析。"""
        if not self.database or not owner or not repo_name:
            return True

        async with self.database.session() as session:
            db_service = DBService(session)
            repo = await db_service.get_repository(owner, repo_name)
            if not repo:
                return True
            feature = await db_service.get_repository_feature(repo.id, "issue")
            if not feature:
                return True
            return bool(feature.enabled and feature.manual_command_enabled)

    def _extract_actor_username(self, payload: Dict[str, Any]) -> Optional[str]:
        """从 Webhook payload 中提取触发者用户名。"""
        return (
            payload.get("sender", {}).get("login")
            or payload.get("sender", {}).get("username")
            or payload.get("pull_request", {}).get("user", {}).get("login")
            or payload.get("pull_request", {}).get("user", {}).get("username")
        )

    def _is_bot_actor(self, username: Optional[str]) -> bool:
        """判断给定用户名是否为配置的 bot 用户，防止自触发。

        使用启动配置中的 bot_username 做静态判断；运行时热更新的
        bot_username 通过 /api/v2/app-settings 修改，此处不做 DB 读取
        （仅用于过滤 bot 自触发，重启后即可同步）。
        """
        if not username:
            return False
        bot_username = settings.bot_username
        if not bot_username:
            return False
        return str(username).strip().lower() == str(bot_username).strip().lower()
