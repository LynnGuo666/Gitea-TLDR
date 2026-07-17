"""配置解析协作类（拆分自 _perform_review 原 :552-686）。

封装「获取 repo / config / credential + 解析 engine / api_url / api_key /
wire_api / model / focus / features + 缺失分支 raise」逻辑。缺失分支会先落
一条 failed analysis_run + audit record_failure 再 raise，与原行为一致。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core import settings
from app.services.audit_service import AuditService
from app.services.db_service import DBService
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ConfigurationError(RuntimeError):
    """配置缺失或不可用——已落 failed run 后由 orchestrator 捕获。"""


@dataclass
class ReviewConfig:
    """一次审查运行解析出的配置快照。"""

    repository_id: int
    repo_config: Any  # RepositoryConfig
    engine: str
    model: Optional[str]
    api_url: Optional[str]
    api_key: Optional[str]
    wire_api: Optional[str]
    config_source: str
    focus_areas: List[str]
    features: List[str]
    actor_user_id: Optional[int] = None


class ConfigResolver:
    """从 DB 解析一次 PR 审查所需的全部配置。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.db_service = DBService(session)

    async def resolve(
        self,
        *,
        owner: str,
        repo_name: str,
        pr_number: int,
        pr_data: Dict[str, Any],
        trigger_type: str,
        features: Optional[List[str]],
        focus_areas: Optional[List[str]],
        actor_username: Optional[str],
        default_engine: str,
    ) -> ReviewConfig:
        """解析配置；配置缺失/凭证不可用时落 failed run + audit 后 raise。"""
        pr_title = pr_data.get("title")
        pr_author = pr_data.get("user", {}).get("login")
        head_branch = pr_data.get("head", {}).get("ref")
        base_branch = pr_data.get("base", {}).get("ref")
        head_sha = pr_data.get("head", {}).get("sha")

        repo = await self.db_service.get_or_create_repository(owner, repo_name)
        repository_id = repo.id

        actor_user_id: Optional[int] = None
        if actor_username:
            actor_user = await self.db_service.get_or_create_user_by_username(
                actor_username
            )
            actor_user_id = actor_user.id

        repo_config = await self.db_service.get_repository_config(
            repository_id, "review"
        )
        if repo_config is None:
            failed = await self.db_service.create_analysis_run(
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
            await self.db_service.complete_analysis_run(
                failed.id,
                status="failed",
                overall_success=False,
                error_message="configuration_required",
            )
            await AuditService(self.session).record_failure(
                actor_id=actor_user_id,
                action="trigger_analysis",
                resource_type="analysis_run",
                resource_id=failed.id,
                error="configuration_required",
                context={"repository_id": repository_id, "source": "webhook"},
            )
            raise ConfigurationError(
                f"configuration_required: 仓库 {owner}/{repo_name} 尚未初始化 review 配置"
            )

        if not repo_config.credential or not repo_config.credential.is_active:
            failed = await self.db_service.create_analysis_run(
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
            await self.db_service.complete_analysis_run(
                failed.id,
                status="failed",
                overall_success=False,
                error_message="credential_unavailable",
            )
            await AuditService(self.session).record_failure(
                actor_id=actor_user_id,
                action="trigger_analysis",
                resource_type="analysis_run",
                resource_id=failed.id,
                error="credential_unavailable",
                context={"repository_id": repository_id, "source": "webhook"},
            )
            raise ConfigurationError("credential_unavailable")

        engine = repo_config.engine or default_engine
        model = repo_config.model
        api_url = repo_config.api_url
        api_key = repo_config.api_key
        wire_api = repo_config.wire_api
        config_source = "repo_config"

        if focus_areas is None:
            focus_areas = repo_config.get_focus()
        if features is None:
            features = repo_config.get_features()

        if api_url or api_key:
            logger.info(f"使用仓库 {owner}/{repo_name} 的自定义 Anthropic 配置")

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
            focus_areas = await self.db_service.get_app_setting(
                "default_review_focus", list(settings.default_review_focus)
            )
        if features is None:
            features = ["comment"]

        return ReviewConfig(
            repository_id=repository_id,
            repo_config=repo_config,
            engine=engine,
            model=model,
            api_url=api_url,
            api_key=api_key,
            wire_api=wire_api,
            config_source=config_source,
            focus_areas=focus_areas,
            features=features,
            actor_user_id=actor_user_id,
        )
