"""
数据库操作服务
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    InlineComment,
    ModelConfig,
    Repository,
    ReviewSession,
    UsageStat,
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

    async def update_repository_secret(
        self, owner: str, repo_name: str, webhook_secret: Optional[str]
    ) -> Optional[Repository]:
        """更新仓库的webhook密钥"""
        repo = await self.get_or_create_repository(owner, repo_name)
        repo.webhook_secret = webhook_secret
        await self.session.flush()
        return repo

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
            started_at=datetime.utcnow(),
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
            completed_at = datetime.utcnow()
            review_session.completed_at = completed_at
            if review_session.started_at:
                delta = completed_at - review_session.started_at
                review_session.duration_seconds = delta.total_seconds()

        await self.session.flush()
        return review_session

    async def get_review_session(self, session_id: int) -> Optional[ReviewSession]:
        """获取审查会话"""
        stmt = (
            select(ReviewSession)
            .options(selectinload(ReviewSession.repository))
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
        stmt = select(ReviewSession).options(selectinload(ReviewSession.repository))

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
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        gitea_api_calls: int = 0,
        claude_api_calls: int = 0,
        provider_api_calls: int = 0,
        clone_operations: int = 0,
    ) -> UsageStat:
        """记录使用量统计"""
        stat = UsageStat(
            repository_id=repository_id,
            review_session_id=review_session_id,
            stat_date=date.today(),
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            gitea_api_calls=gitea_api_calls,
            provider_api_calls=provider_api_calls or claude_api_calls,
            clone_operations=clone_operations,
        )
        self.session.add(stat)
        await self.session.flush()
        return stat

    async def get_usage_stats(
        self,
        repository_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[UsageStat]:
        """获取使用量统计"""
        stmt = select(UsageStat)

        if repository_id:
            stmt = stmt.where(UsageStat.repository_id == repository_id)
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
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """获取使用量汇总"""
        stmt = select(
            func.sum(UsageStat.estimated_input_tokens).label("total_input_tokens"),
            func.sum(UsageStat.estimated_output_tokens).label("total_output_tokens"),
            func.sum(UsageStat.gitea_api_calls).label("total_gitea_calls"),
            func.sum(UsageStat.provider_api_calls).label("total_provider_calls"),
            func.sum(UsageStat.clone_operations).label("total_clones"),
            func.count(UsageStat.id).label("record_count"),
        )

        if repository_id:
            stmt = stmt.where(UsageStat.repository_id == repository_id)
        if start_date:
            stmt = stmt.where(UsageStat.stat_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStat.stat_date <= end_date)

        result = await self.session.execute(stmt)
        row = result.one()

        return {
            "total_input_tokens": row.total_input_tokens or 0,
            "total_output_tokens": row.total_output_tokens or 0,
            "total_gitea_calls": row.total_gitea_calls or 0,
            "total_provider_calls": row.total_provider_calls or 0,
            "total_claude_calls": row.total_provider_calls or 0,
            "total_clones": row.total_clones or 0,
            "record_count": row.record_count or 0,
        }
