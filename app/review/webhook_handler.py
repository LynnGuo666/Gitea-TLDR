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
from app.review.providers.base import (
    InlineComment,
    ReviewResult,
)
from app.review.engine import ReviewEngine
from app.gitea.command_parser import CommandParser
from app.services.db_service import DBService
from app.services.audit_service import AuditService
from app.services.repositories import UsageRepository, WebhookRepository
from app.gitea.client import GiteaClient
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
            pr_author = pr_data.get("user", {}).get("login") or pr_data.get("user", {}).get("username")
            if self._is_bot_actor(pr_author) or self._is_bot_actor(actor_username):
                logger.info(
                    "跳过 bot 自触发 PR: %s/%s#%s", owner, repo_name, pr_number
                )
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
                        status=WEBHOOK_STATUS_SUCCESS if success else WEBHOOK_STATUS_ERROR,
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
                        status=WEBHOOK_STATUS_RETRYING if attempt < max_retries else WEBHOOK_STATUS_ERROR,
                        processing_time_ms=elapsed_ms,
                        error_message=last_error,
                        increment_retry=True,
                    )

                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
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

            commenter = (
                comment_data.get("user", {}).get("login")
                or comment_data.get("user", {}).get("username")
            )
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

            issue_author = issue_data.get("user", {}).get("login") or issue_data.get("user", {}).get("username")
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
        """
        执行PR审查（核心逻辑，被自动和手动触发共用）

        Args:
            owner: 仓库所有者
            repo_name: 仓库名称
            pr_number: PR编号
            pr_data: PR详细数据
            features: 启用的功能列表
            focus_areas: 审查重点列表
            trigger_type: 触发类型 (auto/manual)

        Returns:
            是否处理成功
        """
        review_run_id = None
        repository_id = None
        analysis_mode = None
        diff_size = 0
        gitea_api_calls = 0
        clone_operations = 0
        actor_user_id = None
        provider_run_session_id: Optional[str] = None

        try:
            pr_title = pr_data.get("title")
            pr_author = pr_data.get("user", {}).get("login")
            head_branch = pr_data.get("head", {}).get("ref")
            base_branch = pr_data.get("base", {}).get("ref")
            head_sha = pr_data.get("head", {}).get("sha")

            logger.info(
                f"执行PR审查: {owner}/{repo_name}#{pr_number} - {pr_title} "
                f"({head_branch} -> {base_branch})"
            )

            # 幂等保护：避免同一 PR/head_sha 被重复审查
            if self.database and head_sha:
                async with self.database.session() as session:
                    db_service = DBService(session)
                    existing_repo = await db_service.get_repository(owner, repo_name)
                    existing = (
                        await db_service.get_review_run_by_head(
                            existing_repo.id, pr_number, head_sha
                        )
                        if existing_repo
                        else None
                    )
                    if existing:
                        logger.info(
                            f"跳过重复审查: {owner}/{repo_name}#{pr_number} "
                            f"head_sha={head_sha} 已有 session id={existing.id}"
                        )
                        return True

            # 查询仓库的 Anthropic 配置
            api_url = None
            api_key = None
            wire_api = None
            engine = self.review_engine.default_provider_name
            model = None
            config_source = "global_default"

            # 创建数据库记录
            if self.database:
                async with self.database.session() as session:
                    db_service = DBService(session)
                    repo = await db_service.get_or_create_repository(owner, repo_name)
                    repository_id = repo.id
                    if actor_username:
                        actor_user = await db_service.get_or_create_user_by_username(
                            actor_username
                        )
                        actor_user_id = actor_user.id

                    repo_config = await db_service.get_repository_config(
                        repository_id, "review"
                    )
                    if repo_config is None:
                        failed = await db_service.create_analysis_run(
                            kind="review",
                            repository_id=repository_id,
                            external_number=pr_number,
                            trigger_type=trigger_type,
                            external_title=pr_title,
                            external_author=pr_author,
                            source_branch=head_branch,
                            target_branch=base_branch,
                            head_sha=head_sha,
                        )
                        await db_service.complete_analysis_run(
                            failed.id,
                            status="failed",
                            overall_success=False,
                            error_message="configuration_required",
                        )
                        await AuditService(session).record_failure(
                            actor_id=actor_user_id,
                            action="trigger_analysis",
                            resource_type="analysis_run",
                            resource_id=failed.id,
                            error="configuration_required",
                            context={"repository_id": repository_id, "source": "webhook"},
                        )
                        raise RuntimeError(
                            f"configuration_required: 仓库 {owner}/{repo_name} 尚未初始化 review 配置"
                        )
                    if not repo_config.credential or not repo_config.credential.is_active:
                        failed = await db_service.create_analysis_run(
                            kind="review",
                            repository_id=repository_id,
                            external_number=pr_number,
                            trigger_type=trigger_type,
                            repository_config_id=repo_config.id,
                            external_title=pr_title,
                            external_author=pr_author,
                            source_branch=head_branch,
                            target_branch=base_branch,
                            head_sha=head_sha,
                        )
                        await db_service.complete_analysis_run(
                            failed.id,
                            status="failed",
                            overall_success=False,
                            error_message="credential_unavailable",
                        )
                        await AuditService(session).record_failure(
                            actor_id=actor_user_id,
                            action="trigger_analysis",
                            resource_type="analysis_run",
                            resource_id=failed.id,
                            error="credential_unavailable",
                            context={"repository_id": repository_id, "source": "webhook"},
                        )
                        raise RuntimeError("credential_unavailable")
                    settings_config = repo_config
                    api_url = repo_config.api_url
                    api_key = repo_config.api_key
                    wire_api = repo_config.wire_api
                    engine = repo_config.engine or engine
                    model = repo_config.model or model
                    config_source = "repo_config"

                    if settings_config:
                        if focus_areas is None:
                            focus_areas = settings_config.get_focus()
                        if features is None:
                            features = settings_config.get_features()

                    if api_url or api_key:
                        logger.info(
                            f"使用仓库 {owner}/{repo_name} 的自定义 Anthropic 配置"
                        )

                    logger.info(
                        "engine_resolved engine=%s config_source=%s credential_id=%s has_api_key=%s wire_api=%s model=%s",
                        engine,
                        config_source,
                        repo_config.credential_id,
                        bool(api_key),
                        wire_api or "-",
                        model or "-",
                    )

                    if focus_areas is None:
                        focus_areas = await db_service.get_app_setting(
                            "default_review_focus", list(settings.default_review_focus)
                        )
                    if features is None:
                        features = ["comment"]

                    review_run = await db_service.create_analysis_run(
                        kind="review",
                        repository_id=repository_id,
                        external_number=pr_number,
                        trigger_type=trigger_type,
                        effective_engine=engine,
                        effective_model=model,
                        repository_config_id=repo_config.id,
                        credential_id=repo_config.credential_id,
                        external_title=pr_title,
                        external_author=pr_author,
                        source_branch=head_branch,
                        target_branch=base_branch,
                        head_sha=head_sha,
                        result_payload={
                            "enabled_features": features,
                            "focus_areas": focus_areas,
                            "config_source": config_source,
                        },
                    )
                    review_run_id = review_run.id

            if focus_areas is None:
                # 走到这里说明 self.database 为空（上方 DB 块整体被跳过），
                # 此时无法读 app_settings，直接用配置默认值。
                focus_areas = list(settings.default_review_focus)
            if features is None:
                features = ["comment"]

            # 创建初始评论（如果启用了comment功能）
            comment_id = None
            if "comment" in features:
                initial_comment = "## 自动代码审查\n\n正在审查中，请稍候..."
                comment_id = await self.gitea_client.create_issue_comment(
                    owner, repo_name, pr_number, initial_comment
                )
                gitea_api_calls += 1
                if comment_id:
                    logger.info(f"已创建初始评论，ID: {comment_id}")

            # 设置初始状态
            if "status" in features:
                await self.gitea_client.create_commit_status(
                    owner,
                    repo_name,
                    head_sha,
                    "pending",
                    description="代码审查进行中...",
                )
                gitea_api_calls += 1

            # 获取PR diff
            diff_content = await self.gitea_client.get_pull_request_diff(
                owner, repo_name, pr_number
            )
            gitea_api_calls += 1

            if not diff_content:
                logger.error("无法获取PR diff")
                # 更新评论为错误状态
                if comment_id:
                    error_comment = "## 自动代码审查\n\n审查失败：无法获取PR diff"
                    await self.gitea_client.update_issue_comment(
                        owner, repo_name, comment_id, error_comment
                    )
                    gitea_api_calls += 1
                if "status" in features:
                    await self.gitea_client.create_commit_status(
                        owner,
                        repo_name,
                        head_sha,
                        "error",
                        description="无法获取PR diff",
                    )
                    gitea_api_calls += 1

                # 更新数据库记录
                if self.database and review_run_id:
                    async with self.database.session() as session:
                        db_service = DBService(session)
                        await db_service.complete_analysis_run(
                            review_run_id,
                            status="failed",
                            overall_success=False,
                            error_message="无法获取PR diff",
                        )
                return False

            diff_size = len(diff_content)

            # 克隆仓库
            clone_url = self.gitea_client.get_clone_url(owner, repo_name)
            repo_path = await self.repo_manager.clone_repository(
                clone_url,
                owner,
                repo_name,
                pr_number,
                head_branch,
                auth_token=self.gitea_client.token,
            )
            if not repo_path:
                logger.error("无法克隆仓库，跳过审查")
                analysis_error = "无法克隆仓库，审查中止"
                if comment_id:
                    error_comment = f"## 自动代码审查\n\n审查失败：{analysis_error}"
                    await self.gitea_client.update_issue_comment(
                        owner, repo_name, comment_id, error_comment
                    )
                    gitea_api_calls += 1
                if "status" in features:
                    await self.gitea_client.create_commit_status(
                        owner,
                        repo_name,
                        head_sha,
                        "error",
                        description=analysis_error,
                    )
                    gitea_api_calls += 1

                # 更新数据库记录
                if self.database and review_run_id:
                    async with self.database.session() as session:
                        db_service = DBService(session)
                        await db_service.complete_analysis_run(
                            review_run_id,
                            status="failed",
                            overall_success=False,
                            error_message=analysis_error,
                        )
                return False

            clone_operations += 1
            analysis_mode = "full"

            # 为所有 provider 统一创建 ProviderRun 记录（status="running"），
            # 后续在结果落库时通过 provider_run_session_id 关联。
            if self.database and repository_id:
                try:
                    async with self.database.session() as session:
                        _db = DBService(session)
                        _fs = await _db.create_provider_run(
                            repository_id,
                            "review",
                            provider=engine,
                            analysis_run_id=review_run_id,
                        )
                        provider_run_session_id = _fs.session_id
                except Exception as _fse:
                    logger.warning("创建 ProviderRun 失败（非致命）: %s", _fse)

            analysis_result = await self.review_engine.analyze_pr(
                repo_path,
                diff_content,
                focus_areas,
                pr_data,
                api_url=api_url,
                api_key=api_key,
                engine=engine,
                model=model,
                wire_api=wire_api,
            )

            # 清理仓库
            self.repo_manager.cleanup_repository(owner, repo_name, pr_number)

            if analysis_result is None:
                analysis_error = self.review_engine.last_error or "审查分析过程出错"
                logger.error(f"审查分析失败: {analysis_error}")
                # 更新评论为错误状态
                if comment_id:
                    error_comment = f"## 自动代码审查\n\n审查失败：{analysis_error}"
                    await self.gitea_client.update_issue_comment(
                        owner, repo_name, comment_id, error_comment
                    )
                    gitea_api_calls += 1
                if "status" in features:
                    status_desc = analysis_error.replace("\n", " ").strip()[:120]
                    await self.gitea_client.create_commit_status(
                        owner,
                        repo_name,
                        head_sha,
                        "error",
                        description=status_desc or "代码审查失败",
                    )
                    gitea_api_calls += 1

                # 更新数据库记录
                if self.database and review_run_id:
                    async with self.database.session() as session:
                        db_service = DBService(session)
                        await db_service.complete_analysis_run(
                            review_run_id,
                            status="failed",
                            overall_success=False,
                            result_payload={
                                "analysis_mode": analysis_mode,
                                "diff_size_bytes": diff_size,
                                "config_source": config_source,
                            },
                            error_message=analysis_error,
                        )

                # 完成 ProviderRun（失败）
                if provider_run_session_id and self.database:
                    try:
                        async with self.database.session() as session:
                            _db = DBService(session)
                            await _db.complete_provider_run(
                                provider_run_session_id,
                                status="failed",
                                model=model,
                                analysis_run_id=review_run_id,
                                error=analysis_error,
                            )
                    except Exception as _fse:
                        logger.warning("完成 ProviderRun 失败（非致命）: %s", _fse)

                return False

            # 根据功能标头发布结果
            success = True

            summary_markdown = analysis_result.summary_text() or "未生成审查报告"

            # 更新或创建评论
            if "comment" in features:
                footer = self._build_review_footer(analysis_result)

                # 评论1：PR 变更概览（更新 loading 占位）
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
                gitea_api_calls += 1

                # 评论2：审查发现（仅问题表格，仅在有问题时创建）
                if analysis_result.pr_overview_markdown:
                    issues_text = (analysis_result.summary_markdown or "").strip()
                    if issues_text:
                        await self.gitea_client.create_issue_comment(
                            owner, repo_name, pr_number,
                            f"## 审查发现\n\n{issues_text}{footer}",
                        )
                        gitea_api_calls += 1

            # 创建 Gitea 正式 Review（行内批注通过此接口发送到 diff 对应行）
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
                gitea_api_calls += 1
                success &= review_success

                # 如果review创建成功且配置了bot_username且启用了auto_request_reviewer，则自动请求审查者
                if self.database:
                    async with self.database.session() as _session:
                        _db = DBService(_session)
                        auto_request = await _db.get_app_setting(
                            "auto_request_reviewer", settings.auto_request_reviewer
                        )
                        bot_username_setting = await _db.get_app_setting(
                            "bot_username", settings.bot_username
                        )
                else:
                    auto_request = settings.auto_request_reviewer
                    bot_username_setting = settings.bot_username
                if (
                    review_success
                    and auto_request
                    and bot_username_setting
                ):
                    await self.gitea_client.request_reviewer(
                        owner, repo_name, pr_number, [bot_username_setting]
                    )
                    gitea_api_calls += 1

            # 设置状态
            if "status" in features:
                state = "failure" if analysis_result.indicates_failure() else "success"
                success &= await self.gitea_client.create_commit_status(
                    owner,
                    repo_name,
                    head_sha,
                    state,
                    description="代码审查完成",
                )
                gitea_api_calls += 1

            # 更新数据库记录
            if self.database and review_run_id:
                async with self.database.session() as session:
                    db_service = DBService(session)

                    # 更新审查会话
                    await db_service.complete_analysis_run(
                        review_run_id,
                        status="completed" if success else "failed",
                        overall_severity=analysis_result.overall_severity,
                        summary_markdown=summary_markdown,
                        overall_success=success,
                        result_payload={
                            "config_source": config_source,
                            "analysis_mode": analysis_mode,
                            "diff_size_bytes": diff_size,
                            "inline_comments_count": len(analysis_result.inline_comments),
                            "enabled_features": features,
                            "focus_areas": focus_areas,
                        },
                    )

                    # 保存行级评论
                    if analysis_result.inline_comments:
                        comments_data = [
                            {
                                "path": c.path,
                                "new_line": c.new_line,
                                "old_line": c.old_line,
                                "severity": c.severity,
                                "comment": c.comment,
                                "suggestion": c.suggestion,
                            }
                            for c in analysis_result.inline_comments
                        ]
                        await db_service.save_analysis_annotations(
                            review_run_id, comments_data
                        )

                    # 记录使用量
                    if repository_id:
                        meta = analysis_result.usage_metadata
                        await UsageRepository(session).record_usage_event(
                            repository_id=repository_id,
                            analysis_run_id=review_run_id,
                            user_id=actor_user_id,
                            input_tokens=meta.get("input_tokens", 0),
                            output_tokens=meta.get("output_tokens", 0),
                            cache_creation_input_tokens=meta.get(
                                "cache_creation_input_tokens", 0
                            ),
                            cache_read_input_tokens=meta.get(
                                "cache_read_input_tokens", 0
                            ),
                            gitea_api_calls=gitea_api_calls,
                            provider_api_calls=1,
                            clone_operations=clone_operations,
                        )

            # 完成 ProviderRun（成功）
            if provider_run_session_id and self.database:
                try:
                    import json as _json

                    meta = analysis_result.usage_metadata
                    _msgs = meta.get("forge_messages") or []
                    async with self.database.session() as session:
                        _db = DBService(session)
                        await _db.complete_provider_run(
                            provider_run_session_id,
                            status="completed",
                            model=meta.get("model") or model,
                            turns=meta.get("turns", 0),
                            tool_calls_count=meta.get("tool_calls", 0),
                            messages_json=_json.dumps(_msgs, ensure_ascii=False) if _msgs else None,
                            input_tokens=meta.get("input_tokens", 0),
                            output_tokens=meta.get("output_tokens", 0),
                            cache_creation_input_tokens=meta.get("cache_creation_input_tokens", 0),
                            cache_read_input_tokens=meta.get("cache_read_input_tokens", 0),
                            analysis_run_id=review_run_id,
                        )
                except Exception as _fse:
                    logger.warning("完成 ProviderRun 失败（非致命）: %s", _fse)

            logger.info(f"PR审查完成: {owner}/{repo_name}#{pr_number}")
            return success

        except Exception as e:
            logger.error(f"执行审查异常: {e}", exc_info=True)

            # 更新数据库记录
            if self.database and review_run_id:
                try:
                    async with self.database.session() as session:
                        db_service = DBService(session)
                        await db_service.complete_analysis_run(
                            review_run_id,
                            status="failed",
                            overall_success=False,
                            error_message=str(e),
                        )
                except Exception as db_error:
                    logger.error(f"更新数据库记录失败: {db_error}")

            # 完成 ProviderRun（异常）
            if provider_run_session_id and self.database:
                try:
                    async with self.database.session() as session:
                        _db = DBService(session)
                        await _db.complete_provider_run(
                            provider_run_session_id,
                            status="failed",
                            analysis_run_id=review_run_id,
                            error=str(e),
                        )
                except Exception as _fse:
                    logger.warning("完成 ProviderRun 失败（非致命）: %s", _fse)

            return False

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

    _PROVIDER_DISPLAY: Dict[str, str] = {
        "forge": "Forge",
        "claude_code": "Claude Code",
        "codex_cli": "Codex CLI",
    }

    def _build_review_footer(self, analysis_result: ReviewResult) -> str:
        """构建评论底部的引擎与模型信息行。"""
        engine = self._PROVIDER_DISPLAY.get(
            analysis_result.provider_name, analysis_result.provider_name
        )
        model = (analysis_result.usage_metadata.get("model") or "").strip()
        if model:
            return f"\n\n---\n*审查引擎：{engine} · 模型：{model}*"
        return f"\n\n---\n*审查引擎：{engine}*"

    def _build_review_comments(
        self, analysis_result: ReviewResult
    ) -> List[Dict[str, Any]]:
        """将行级建议转换成Gitea评论"""
        comments: List[Dict[str, Any]] = []
        for inline in analysis_result.inline_comments:
            payload = self._inline_to_review_comment(inline)
            if payload:
                comments.append(payload)
        return comments

    def _inline_to_review_comment(
        self, inline: InlineComment
    ) -> Optional[Dict[str, Any]]:
        """转换单条行级建议"""
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
