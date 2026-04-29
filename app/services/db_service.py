"""
数据库操作服务
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    IssueConfig,
    IssueSession,
    InlineComment,
    ModelConfig,
    Repository,
    ReviewSession,
    User,
    UsageStat,
    WebhookLog,
)

logger = logging.getLogger(__name__)


class DBService:
    """数据库操作服务"""

    def __init__(self, session: AsyncSession):
        """
        初始化数据库服务

        Args:
            session: 异步数据库会话
        """
        self.session = session

    # ==================== Repository 操作 ====================

    async def get_or_create_repository(self, owner: str, repo_name: str) -> Repository:
        """获取或创建仓库记录"""
        stmt = select(Repository).where(
            Repository.owner == owner, Repository.repo_name == repo_name
        )
        result = await self.session.execute(stmt)
        repo = result.scalar_one_or_none()

        if not repo:
            repo = Repository(owner=owner, repo_name=repo_name)
            self.session.add(repo)
            await self.session.flush()
            logger.info(f"创建仓库记录: {owner}/{repo_name}")

        return repo

    async def get_repository(self, owner: str, repo_name: str) -> Optional[Repository]:
        """获取仓库记录"""
        stmt = select(Repository).where(
            Repository.owner == owner, Repository.repo_name == repo_name
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_repository_by_id(self, repo_id: int) -> Optional[Repository]:
        """按 ID 获取仓库记录"""
        stmt = select(Repository).where(Repository.id == repo_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_repository_secret(
        self, owner: str, repo_name: str, webhook_secret: Optional[str]
    ) -> Optional[Repository]:
        """更新仓库的webhook密钥"""
        repo = await self.get_or_create_repository(owner, repo_name)
        repo.webhook_secret = webhook_secret
        await self.session.flush()
        return repo

    async def get_or_create_user_by_username(self, username: str) -> User:
        """按用户名获取或创建用户记录。"""
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                username=username,
                role="user",
                is_active=True,
            )
            self.session.add(user)
            await self.session.flush()
            logger.info("创建用户记录: %s", username)

        return user

    async def list_repositories(
        self, is_active: Optional[bool] = None
    ) -> List[Repository]:
        """获取仓库列表"""
        stmt = select(Repository)
        if is_active is not None:
            stmt = stmt.where(Repository.is_active == is_active)
        stmt = stmt.order_by(Repository.updated_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_issue_settings(
        self,
        owner: str,
        repo_name: str,
        *,
        issue_enabled: Optional[bool] = None,
        issue_auto_on_open: Optional[bool] = None,
        issue_manual_command_enabled: Optional[bool] = None,
    ) -> Repository:
        """更新仓库级 Issue 分析设置。"""
        repo = await self.get_or_create_repository(owner, repo_name)
        if issue_enabled is not None:
            repo.issue_enabled = issue_enabled
        if issue_auto_on_open is not None:
            repo.issue_auto_on_open = issue_auto_on_open
        if issue_manual_command_enabled is not None:
            repo.issue_manual_command_enabled = issue_manual_command_enabled
        await self.session.flush()
        return repo

    # ==================== ModelConfig 操作 ====================

    async def get_model_config(
        self, repository_id: Optional[int] = None
    ) -> Optional[ModelConfig]:
        """获取模型配置（优先仓库级别，否则全局默认）"""
        if repository_id:
            stmt = select(ModelConfig).where(ModelConfig.repository_id == repository_id)
            result = await self.session.execute(stmt)
            config = result.scalar_one_or_none()
            if config:
                return config

        # 获取全局默认配置
        stmt = select(ModelConfig).where(
            ModelConfig.repository_id.is_(None), ModelConfig.is_default.is_(True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_repo_specific_model_config(
        self, repository_id: int
    ) -> Optional[ModelConfig]:
        """获取仓库级配置（不回退到全局）"""
        stmt = select(ModelConfig).where(ModelConfig.repository_id == repository_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_global_model_config(self) -> Optional[ModelConfig]:
        """获取全局默认模型配置"""
        stmt = select(ModelConfig).where(
            ModelConfig.repository_id.is_(None), ModelConfig.is_default.is_(True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_repo_model_config(self, repository_id: int) -> bool:
        """删除仓库级模型配置（启用全局继承）"""
        config = await self.get_repo_specific_model_config(repository_id)
        if not config:
            return False
        await self.session.delete(config)
        await self.session.flush()
        return True

    async def create_or_update_model_config(
        self,
        config_name: str,
        repository_id: Optional[int] = None,
        engine: str = "claude_code",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        custom_prompt: Optional[str] = None,
        default_features: Optional[List[str]] = None,
        default_focus: Optional[List[str]] = None,
        is_default: bool = False,
    ) -> ModelConfig:
        """创建或更新模型配置"""
        # 查找现有配置
        if repository_id:
            stmt = select(ModelConfig).where(ModelConfig.repository_id == repository_id)
        else:
            stmt = select(ModelConfig).where(
                ModelConfig.repository_id.is_(None),
                ModelConfig.config_name == config_name,
            )
        result = await self.session.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            config = ModelConfig(
                repository_id=repository_id,
                config_name=config_name,
            )
            self.session.add(config)

        config.engine = engine
        config.max_tokens = max_tokens
        config.temperature = temperature
        config.custom_prompt = custom_prompt
        config.is_default = is_default

        if default_features is not None:
            config.set_features(default_features)
        if default_focus is not None:
            config.set_focus(default_focus)

        await self.session.flush()
        return config

    async def list_model_configs(self) -> List[ModelConfig]:
        """获取所有模型配置"""
        stmt = select(ModelConfig).order_by(ModelConfig.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ==================== ReviewSession 操作 ====================

    async def get_existing_review_session(
        self,
        owner: str,
        repo_name: str,
        pr_number: int,
        head_sha: str,
    ) -> Optional[ReviewSession]:
        """查询同一 PR（owner/repo + pr_number + head_sha）中已存在的 running/success 会话"""
        stmt = (
            select(ReviewSession)
            .join(Repository)
            .where(
                Repository.owner == owner,
                Repository.repo_name == repo_name,
                ReviewSession.pr_number == pr_number,
                ReviewSession.head_sha == head_sha,
                ReviewSession.overall_success.isnot(
                    False
                ),  # None（running）或 True（success）
            )
            .order_by(ReviewSession.started_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_review_session(
        self,
        repository_id: int,
        pr_number: int,
        trigger_type: str,
        engine: Optional[str] = None,
        model: Optional[str] = None,
        config_source: Optional[str] = None,
        pr_title: Optional[str] = None,
        pr_author: Optional[str] = None,
        head_branch: Optional[str] = None,
        base_branch: Optional[str] = None,
        head_sha: Optional[str] = None,
        enabled_features: Optional[List[str]] = None,
        focus_areas: Optional[List[str]] = None,
    ) -> ReviewSession:
        """创建审查会话"""
        session = ReviewSession(
            repository_id=repository_id,
            pr_number=pr_number,
            trigger_type=trigger_type,
            engine=engine,
            model=model,
            config_source=config_source,
            pr_title=pr_title,
            pr_author=pr_author,
            head_branch=head_branch,
            base_branch=base_branch,
            head_sha=head_sha,
            started_at=datetime.now(timezone.utc),
        )

        if enabled_features:
            session.set_features(enabled_features)
        if focus_areas:
            session.set_focus(focus_areas)

        self.session.add(session)
        await self.session.flush()
        logger.info(
            f"创建审查会话: repository_id={repository_id}, pr_number={pr_number}"
        )
        return session

    async def update_review_session(
        self,
        session_id: int,
        engine: Optional[str] = None,
        model: Optional[str] = None,
        config_source: Optional[str] = None,
        analysis_mode: Optional[str] = None,
        diff_size_bytes: Optional[int] = None,
        overall_severity: Optional[str] = None,
        summary_markdown: Optional[str] = None,
        inline_comments_count: Optional[int] = None,
        overall_success: Optional[bool] = None,
        error_message: Optional[str] = None,
        completed: bool = False,
    ) -> Optional[ReviewSession]:
        """更新审查会话"""
        stmt = select(ReviewSession).where(ReviewSession.id == session_id)
        result = await self.session.execute(stmt)
        review_session = result.scalar_one_or_none()

        if not review_session:
            return None

        if engine is not None:
            review_session.engine = engine
        if model is not None:
            review_session.model = model
        if config_source is not None:
            review_session.config_source = config_source
        if analysis_mode is not None:
            review_session.analysis_mode = analysis_mode
        if diff_size_bytes is not None:
            review_session.diff_size_bytes = diff_size_bytes
        if overall_severity is not None:
            review_session.overall_severity = overall_severity
        if summary_markdown is not None:
            review_session.summary_markdown = summary_markdown
        if inline_comments_count is not None:
            review_session.inline_comments_count = inline_comments_count
        if overall_success is not None:
            review_session.overall_success = overall_success
        if error_message is not None:
            review_session.error_message = error_message

        if completed:
            completed_at = datetime.now(timezone.utc)
            review_session.completed_at = completed_at
            if review_session.started_at:
                started_naive = (
                    review_session.started_at.replace(tzinfo=None)
                    if review_session.started_at.tzinfo
                    else review_session.started_at
                )
                delta = completed_at.replace(tzinfo=None) - started_naive
                review_session.duration_seconds = delta.total_seconds()

        await self.session.flush()
        return review_session

    async def get_review_session(self, session_id: int) -> Optional[ReviewSession]:
        """获取审查会话"""
        stmt = (
            select(ReviewSession)
            .options(
                selectinload(ReviewSession.repository),
                selectinload(ReviewSession.usage_stat),
            )
            .where(ReviewSession.id == session_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_review_sessions(
        self,
        repository_id: Optional[int] = None,
        repository_ids: Optional[List[int]] = None,
        owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ReviewSession]:
        """获取审查会话列表"""
        stmt = select(ReviewSession).options(
            selectinload(ReviewSession.repository),
            selectinload(ReviewSession.usage_stat),
        )

        if repository_ids:
            stmt = stmt.where(ReviewSession.repository_id.in_(repository_ids))
        elif repository_id:
            stmt = stmt.where(ReviewSession.repository_id == repository_id)
        elif owner and repo_name:
            stmt = stmt.join(Repository).where(
                Repository.owner == owner, Repository.repo_name == repo_name
            )

        if success is not None:
            stmt = stmt.where(ReviewSession.overall_success == success)

        stmt = stmt.order_by(ReviewSession.started_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_review_sessions_by_repo_ids(
        self,
        repository_ids: List[int],
        success: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ReviewSession]:
        """获取指定仓库集合的审查会话列表"""
        return await self.list_review_sessions(
            repository_ids=repository_ids,
            success=success,
            limit=limit,
            offset=offset,
        )

    # ==================== IssueSession 操作 ====================

    async def create_issue_session(
        self,
        repository_id: int,
        issue_number: int,
        trigger_type: str,
        engine: Optional[str] = None,
        model: Optional[str] = None,
        config_source: Optional[str] = None,
        issue_title: Optional[str] = None,
        issue_author: Optional[str] = None,
        issue_state: Optional[str] = None,
        source_comment_id: Optional[int] = None,
        bot_comment_id: Optional[int] = None,
    ) -> IssueSession:
        """创建 Issue 分析会话。"""
        session = IssueSession(
            repository_id=repository_id,
            issue_number=issue_number,
            trigger_type=trigger_type,
            engine=engine,
            model=model,
            config_source=config_source,
            issue_title=issue_title,
            issue_author=issue_author,
            issue_state=issue_state,
            source_comment_id=source_comment_id,
            bot_comment_id=bot_comment_id,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(session)
        await self.session.flush()
        logger.info(
            "创建 Issue 会话: repository_id=%s, issue_number=%s",
            repository_id,
            issue_number,
        )
        return session

    async def update_issue_session(
        self,
        session_id: int,
        *,
        engine: Optional[str] = None,
        model: Optional[str] = None,
        config_source: Optional[str] = None,
        issue_state: Optional[str] = None,
        bot_comment_id: Optional[int] = None,
        overall_severity: Optional[str] = None,
        summary_markdown: Optional[str] = None,
        analysis_payload: Optional[Dict[str, Any]] = None,
        overall_success: Optional[bool] = None,
        error_message: Optional[str] = None,
        completed: bool = False,
    ) -> Optional[IssueSession]:
        """更新 Issue 分析会话。"""
        stmt = select(IssueSession).where(IssueSession.id == session_id)
        result = await self.session.execute(stmt)
        issue_session = result.scalar_one_or_none()

        if not issue_session:
            return None

        if engine is not None:
            issue_session.engine = engine
        if model is not None:
            issue_session.model = model
        if config_source is not None:
            issue_session.config_source = config_source
        if issue_state is not None:
            issue_session.issue_state = issue_state
        if bot_comment_id is not None:
            issue_session.bot_comment_id = bot_comment_id
        if overall_severity is not None:
            issue_session.overall_severity = overall_severity
        if summary_markdown is not None:
            issue_session.summary_markdown = summary_markdown
        if analysis_payload is not None:
            issue_session.set_analysis_payload(analysis_payload)
        if overall_success is not None:
            issue_session.overall_success = overall_success
        if error_message is not None:
            issue_session.error_message = error_message

        if completed:
            completed_at = datetime.now(timezone.utc)
            issue_session.completed_at = completed_at
            if issue_session.started_at:
                started_at = issue_session.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                delta = completed_at - started_at
                issue_session.duration_seconds = delta.total_seconds()

        await self.session.flush()
        return issue_session

    async def get_issue_session(self, session_id: int) -> Optional[IssueSession]:
        """获取单条 Issue 分析会话。"""
        stmt = (
            select(IssueSession)
            .options(
                selectinload(IssueSession.repository),
                selectinload(IssueSession.usage_stats),
            )
            .where(IssueSession.id == session_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_issue_sessions(
        self,
        repository_id: Optional[int] = None,
        repository_ids: Optional[List[int]] = None,
        owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[IssueSession]:
        """获取 Issue 分析会话列表。"""
        stmt = select(IssueSession).options(
            selectinload(IssueSession.repository),
            selectinload(IssueSession.usage_stats),
        )

        if repository_ids:
            stmt = stmt.where(IssueSession.repository_id.in_(repository_ids))
        elif repository_id:
            stmt = stmt.where(IssueSession.repository_id == repository_id)
        elif owner and repo_name:
            stmt = stmt.join(Repository).where(
                Repository.owner == owner, Repository.repo_name == repo_name
            )

        if success is not None:
            stmt = stmt.where(IssueSession.overall_success == success)

        stmt = stmt.order_by(IssueSession.started_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_issue_sessions_by_repo_ids(
        self,
        repository_ids: List[int],
        success: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[IssueSession]:
        """获取指定仓库集合的 Issue 分析会话列表。"""
        return await self.list_issue_sessions(
            repository_ids=repository_ids,
            success=success,
            limit=limit,
            offset=offset,
        )

    async def get_in_flight_issue_session(
        self, repository_id: int, issue_number: int
    ) -> Optional[IssueSession]:
        """查询是否存在尚未完成的同一 Issue 分析会话。"""
        stmt = (
            select(IssueSession)
            .where(
                IssueSession.repository_id == repository_id,
                IssueSession.issue_number == issue_number,
                IssueSession.completed_at.is_(None),
            )
            .order_by(IssueSession.started_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recent_successful_issue_session(
        self,
        repository_id: int,
        issue_number: int,
        within_seconds: int,
    ) -> Optional[IssueSession]:
        """查询最近一段时间内是否已有成功完成的 Issue 分析。"""
        threshold = datetime.now(timezone.utc) - timedelta(seconds=within_seconds)
        stmt = (
            select(IssueSession)
            .where(
                IssueSession.repository_id == repository_id,
                IssueSession.issue_number == issue_number,
                IssueSession.overall_success.is_(True),
                IssueSession.completed_at.isnot(None),
                IssueSession.completed_at >= threshold,
            )
            .order_by(IssueSession.completed_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ==================== IssueConfig 操作 ====================

    async def get_repo_specific_issue_config(
        self, repository_id: int
    ) -> Optional[IssueConfig]:
        """获取仓库级 Issue 配置（不回退到全局）"""
        stmt = select(IssueConfig).where(IssueConfig.repository_id == repository_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_global_issue_config(self) -> Optional[IssueConfig]:
        """获取全局默认 Issue 配置"""
        stmt = select(IssueConfig).where(
            IssueConfig.repository_id.is_(None), IssueConfig.is_default.is_(True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_issue_config(
        self,
        *,
        repository_id: Optional[int],
        config_name: str,
        engine: Optional[str] = None,
        model: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        wire_api: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        custom_prompt: Optional[str] = None,
        default_focus: Optional[List[str]] = None,
        is_default: Optional[bool] = None,
        clear_api_key: bool = False,
    ) -> IssueConfig:
        """写入或更新 Issue 配置；字段为 None 表示不修改。"""
        if repository_id is not None:
            stmt = select(IssueConfig).where(
                IssueConfig.repository_id == repository_id
            )
        else:
            stmt = select(IssueConfig).where(
                IssueConfig.repository_id.is_(None),
                IssueConfig.is_default.is_(True),
            )
        result = await self.session.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            config = IssueConfig(
                repository_id=repository_id,
                config_name=config_name,
                engine=engine or "forge",
                is_default=bool(is_default) if is_default is not None else (repository_id is None),
            )
            self.session.add(config)
        else:
            config.config_name = config_name or config.config_name
            if engine is not None:
                config.engine = engine
            if is_default is not None:
                config.is_default = is_default

        if model is not None:
            config.model = model or None
        if api_url is not None:
            config.api_url = api_url or None
        if clear_api_key:
            config.api_key = None
        elif api_key is not None:
            config.api_key = api_key or None
        if wire_api is not None:
            config.wire_api = wire_api or None
        if temperature is not None:
            config.temperature = temperature
        if max_tokens is not None:
            config.max_tokens = max_tokens
        if custom_prompt is not None:
            config.custom_prompt = custom_prompt or None
        if default_focus is not None:
            config.set_focus(default_focus)

        await self.session.flush()
        return config

    async def clear_repo_issue_config(self, repository_id: int) -> bool:
        """删除仓库级 Issue 配置（回退到全局继承）"""
        config = await self.get_repo_specific_issue_config(repository_id)
        if not config:
            return False
        await self.session.delete(config)
        await self.session.flush()
        return True

    # ==================== InlineComment 操作 ====================

    async def save_inline_comments(
        self,
        review_session_id: int,
        comments: List[Dict[str, Any]],
    ) -> List[InlineComment]:
        """保存行级评论"""
        saved_comments = []
        for comment_data in comments:
            comment = InlineComment(
                review_session_id=review_session_id,
                file_path=comment_data.get("path", ""),
                new_line=comment_data.get("new_line"),
                old_line=comment_data.get("old_line"),
                severity=comment_data.get("severity"),
                comment=comment_data.get("comment", ""),
                suggestion=comment_data.get("suggestion"),
            )
            self.session.add(comment)
            saved_comments.append(comment)

        await self.session.flush()
        logger.info(f"保存 {len(saved_comments)} 条行级评论")
        return saved_comments

    async def get_inline_comments(self, review_session_id: int) -> List[InlineComment]:
        """获取审查会话的行级评论"""
        stmt = select(InlineComment).where(
            InlineComment.review_session_id == review_session_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ==================== UsageStat 操作 ====================

    async def record_usage(
        self,
        repository_id: int,
        review_session_id: Optional[int] = None,
        issue_session_id: Optional[int] = None,
        user_id: Optional[int] = None,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        gitea_api_calls: int = 0,
        claude_api_calls: int = 0,
        provider_api_calls: int = 0,
        clone_operations: int = 0,
    ) -> UsageStat:
        """记录使用量统计"""
        stat = UsageStat(
            repository_id=repository_id,
            review_session_id=review_session_id,
            issue_session_id=issue_session_id,
            user_id=user_id,
            stat_date=date.today(),
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
            gitea_api_calls=gitea_api_calls,
            provider_api_calls=provider_api_calls or claude_api_calls,
            clone_operations=clone_operations,
        )
        self.session.add(stat)
        await self.session.flush()
        return stat

    # ==================== WebhookLog 操作 ====================

    async def create_webhook_log(
        self,
        request_id: str,
        repository_id: int,
        event_type: str,
        payload: str,
        status: str = "processing",
    ) -> WebhookLog:
        """创建 Webhook 日志记录。"""
        import time
        from datetime import datetime, timezone

        log = WebhookLog(
            request_id=request_id,
            repository_id=repository_id,
            event_type=event_type,
            payload=payload,
            status=status,
            processing_time_ms=0,
            retry_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def update_webhook_log(
        self,
        log_id: int,
        status: Optional[str] = None,
        error_message: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        increment_retry: bool = False,
    ) -> Optional[WebhookLog]:
        """更新 Webhook 日志记录。"""
        from datetime import datetime, timezone

        stmt = select(WebhookLog).where(WebhookLog.id == log_id)
        result = await self.session.execute(stmt)
        log = result.scalar_one_or_none()
        if not log:
            return None

        if status is not None:
            log.status = status
        if error_message is not None:
            log.error_message = error_message
        if processing_time_ms is not None:
            log.processing_time_ms = processing_time_ms
        if increment_retry:
            log.retry_count = (log.retry_count or 0) + 1

        log.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return log

    async def get_pending_webhook_logs(
        self, min_age_seconds: int = 60, max_age_hours: int = 6
    ) -> List[WebhookLog]:
        """获取状态为 processing 且超时的 Webhook 日志（用于启动恢复）。"""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        max_age = now - timedelta(hours=max_age_hours)
        min_age = now - timedelta(seconds=min_age_seconds)

        stmt = select(WebhookLog).where(
            WebhookLog.status == "processing",
            WebhookLog.created_at >= max_age,
            WebhookLog.created_at <= min_age,
        )
        stmt = stmt.order_by(WebhookLog.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_usage_stats(
        self,
        repository_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[UsageStat]:
        """获取使用量统计"""
        stmt = select(UsageStat)

        if repository_id:
            stmt = stmt.where(UsageStat.repository_id == repository_id)
        if user_id is not None:
            stmt = stmt.where(UsageStat.user_id == user_id)
        if start_date:
            stmt = stmt.where(UsageStat.stat_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStat.stat_date <= end_date)

        stmt = stmt.order_by(UsageStat.stat_date.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_usage_summary(
        self,
        repository_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """获取使用量汇总"""
        stmt = select(
            func.sum(UsageStat.estimated_input_tokens).label("total_input_tokens"),
            func.sum(UsageStat.estimated_output_tokens).label("total_output_tokens"),
            func.sum(UsageStat.cache_creation_input_tokens).label("total_cache_creation_tokens"),
            func.sum(UsageStat.cache_read_input_tokens).label("total_cache_read_tokens"),
            func.sum(UsageStat.gitea_api_calls).label("total_gitea_calls"),
            func.sum(UsageStat.provider_api_calls).label("total_provider_calls"),
            func.sum(UsageStat.clone_operations).label("total_clones"),
            func.count(UsageStat.id).label("record_count"),
        )

        if repository_id:
            stmt = stmt.where(UsageStat.repository_id == repository_id)
        if user_id is not None:
            stmt = stmt.where(UsageStat.user_id == user_id)
        if start_date:
            stmt = stmt.where(UsageStat.stat_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStat.stat_date <= end_date)

        result = await self.session.execute(stmt)
        row = result.one()

        return {
            "total_input_tokens": row.total_input_tokens or 0,
            "total_output_tokens": row.total_output_tokens or 0,
            "total_cache_creation_tokens": row.total_cache_creation_tokens or 0,
            "total_cache_read_tokens": row.total_cache_read_tokens or 0,
            "total_gitea_calls": row.total_gitea_calls or 0,
            "total_provider_calls": row.total_provider_calls or 0,
            "total_claude_calls": row.total_provider_calls or 0,
            "total_clones": row.total_clones or 0,
            "record_count": row.record_count or 0,
        }
