"""PR 审查编排器（拆分自 _perform_review）。

编排 ConfigResolver + RunRecorder + ReviewPublisher + 幂等检查 + 克隆 +
review_engine.analyze_pr + 异常处理。方法体压缩到 <150 行。

行为保持与原 `_perform_review` 一致——阶段 7 的测试不改一行仍全绿。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.database import Database
from app.review.engine import ReviewEngine
from app.review.orchestrator.config_resolver import (
    ConfigResolver,
    ConfigurationError,
)
from app.review.orchestrator.publisher import ReviewPublisher
from app.review.orchestrator.recorder import RunRecorder
from app.services.db_service import DBService

logger = logging.getLogger(__name__)


class ReviewOrchestrator:
    """编排一次 PR 审查的完整生命周期。"""

    def __init__(
        self,
        *,
        gitea_client: Any,
        repo_manager: Any,
        review_engine: ReviewEngine,
        database: Database,
    ):
        self.gitea_client = gitea_client
        self.repo_manager = repo_manager
        self.review_engine = review_engine
        self.database = database

    async def run(
        self,
        *,
        owner: str,
        repo_name: str,
        pr_number: int,
        pr_data: Dict[str, Any],
        features: Optional[List[str]],
        focus_areas: Optional[List[str]],
        trigger_type: str = "auto",
        actor_username: Optional[str] = None,
    ) -> bool:
        """执行一次 PR 审查，返回是否成功。"""
        head_sha = pr_data.get("head", {}).get("sha")
        head_branch = pr_data.get("head", {}).get("ref")
        base_branch = pr_data.get("base", {}).get("ref")
        pr_title = pr_data.get("title")

        logger.info(
            f"执行PR审查: {owner}/{repo_name}#{pr_number} - {pr_title} "
            f"({head_branch} -> {base_branch})"
        )

        # 幂等保护：同 PR/head_sha 已有 completed run 则跳过
        if (
            self.database
            and head_sha
            and await self._already_reviewed(owner, repo_name, pr_number, head_sha)
        ):
            logger.info(f"跳过重复审查: {owner}/{repo_name}#{pr_number}")
            return True

        review_run_id: Optional[int] = None
        provider_run_session_id: Optional[str] = None
        repository_id: Optional[int] = None
        actor_user_id: Optional[int] = None
        analysis_mode: Optional[str] = None
        diff_size = 0
        gitea_api_calls = 0

        try:
            # 1. 解析配置（缺失分支在 session 内落 failed run 后 raise）
            async with self.database.session() as session:
                resolver = ConfigResolver(session)
                cfg = await resolver.resolve(
                    owner=owner,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    pr_data=pr_data,
                    trigger_type=trigger_type,
                    features=features,
                    focus_areas=focus_areas,
                    actor_username=actor_username,
                    default_engine=self.review_engine.default_provider_name,
                )
                recorder = RunRecorder(session)
                review_run_id = await recorder.create_run(
                    repository_id=cfg.repository_id,
                    pr_number=pr_number,
                    pr_data=pr_data,
                    trigger_type=trigger_type,
                    engine=cfg.engine,
                    model=cfg.model,
                    repo_config=cfg.repo_config,
                    head_sha=head_sha,
                    focus_areas=cfg.focus_areas,
                    features=cfg.features,
                    config_source=cfg.config_source,
                )
                repository_id = cfg.repository_id
                actor_user_id = cfg.actor_user_id
                features_resolved = cfg.features
                focus_resolved = cfg.focus_areas
                engine = cfg.engine
                model = cfg.model
                api_url = cfg.api_url
                api_key = cfg.api_key
                wire_api = cfg.wire_api
                config_source = cfg.config_source

            # 2. 初始评论 + pending status
            async with self.database.session() as session:
                publisher = ReviewPublisher(session, self.gitea_client)
                comment_id = await publisher.create_initial_comment(
                    owner=owner,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    features=features_resolved,
                )
                if comment_id is not None:
                    gitea_api_calls += 1
                if await publisher.set_pending_status(
                    owner=owner,
                    repo_name=repo_name,
                    head_sha=head_sha,
                    features=features_resolved,
                ):
                    gitea_api_calls += 1

            # 3. 获取 diff
            diff_content = await self.gitea_client.get_pull_request_diff(
                owner, repo_name, pr_number
            )
            gitea_api_calls += 1
            if not diff_content:
                logger.error("无法获取PR diff")
                await self._fail_without_result(
                    owner,
                    repo_name,
                    comment_id,
                    pr_number,
                    head_sha,
                    features_resolved,
                    review_run_id,
                    error="无法获取PR diff",
                    analysis_mode=analysis_mode,
                    diff_size=diff_size,
                    config_source=config_source,
                )
                return False
            diff_size = len(diff_content)

            # 4. 克隆
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
                await self._fail_without_result(
                    owner,
                    repo_name,
                    comment_id,
                    pr_number,
                    head_sha,
                    features_resolved,
                    review_run_id,
                    error="无法克隆仓库，审查中止",
                    analysis_mode=analysis_mode,
                    diff_size=diff_size,
                    config_source=config_source,
                )
                return False
            clone_operations = 1
            analysis_mode = "full"

            # 5. ProviderRun
            if repository_id:
                async with self.database.session() as session:
                    recorder = RunRecorder(session)
                    provider_run_session_id = await recorder.create_provider_run(
                        repository_id=repository_id,
                        engine=engine,
                        analysis_run_id=review_run_id,
                    )

            # 6. 引擎分析
            analysis_result = await self.review_engine.analyze_pr(
                repo_path,
                diff_content,
                focus_resolved,
                pr_data,
                api_url=api_url,
                api_key=api_key,
                engine=engine,
                model=model,
                wire_api=wire_api,
            )
            self.repo_manager.cleanup_repository(owner, repo_name, pr_number)

            if analysis_result is None:
                analysis_error = self.review_engine.last_error or "审查分析过程出错"
                logger.error(f"审查分析失败: {analysis_error}")
                await self._fail_with_result(
                    owner,
                    repo_name,
                    comment_id,
                    pr_number,
                    head_sha,
                    features_resolved,
                    review_run_id,
                    provider_run_session_id,
                    analysis_error,
                    analysis_mode,
                    diff_size,
                    config_source,
                    model,
                    gitea_api_calls,
                    clone_operations,
                )
                return False

            # 7. 发布成功结果
            async with self.database.session() as session:
                publisher = ReviewPublisher(session, self.gitea_client)
                success = await publisher.publish_success(
                    owner=owner,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    comment_id=comment_id,
                    head_sha=head_sha,
                    features=features_resolved,
                    analysis_result=analysis_result,
                )

            # 8. DB 收尾 + usage + provider_run
            async with self.database.session() as session:
                recorder = RunRecorder(session)
                await recorder.complete_run(
                    review_run_id,
                    success=success,
                    analysis_result=analysis_result,
                    diff_size=diff_size,
                    analysis_mode=analysis_mode,
                    config_source=config_source,
                    features=features_resolved,
                    focus_areas=focus_resolved,
                )
                if repository_id:
                    await recorder.record_usage(
                        repository_id=repository_id,
                        analysis_run_id=review_run_id,
                        actor_user_id=actor_user_id,
                        analysis_result=analysis_result,
                        gitea_api_calls=gitea_api_calls,
                        clone_operations=clone_operations,
                    )
                await recorder.complete_provider_run(
                    provider_run_session_id,
                    status="completed",
                    analysis_result=analysis_result,
                    model=model,
                    analysis_run_id=review_run_id,
                )

            logger.info(f"PR审查完成: {owner}/{repo_name}#{pr_number}")
            return success

        except ConfigurationError:
            # 配置缺失分支已在 resolver 内落 failed run + audit，直接返回失败
            return False
        except Exception as e:
            logger.error(f"执行审查异常: {e}", exc_info=True)
            await self._fail_on_exception(review_run_id, provider_run_session_id, e)
            return False

    # ------------------------------------------------------------------
    # 私有：幂等检查
    # ------------------------------------------------------------------

    async def _already_reviewed(
        self, owner: str, repo_name: str, pr_number: int, head_sha: str
    ) -> bool:
        async with self.database.session() as session:
            db_service = DBService(session)
            repo = await db_service.get_repository(owner, repo_name)
            if not repo:
                return False
            existing = await db_service.get_review_run_by_head(
                repo.id, pr_number, head_sha
            )
            return existing is not None

    # ------------------------------------------------------------------
    # 私有：失败收尾（无 analysis_result）
    # ------------------------------------------------------------------

    async def _fail_without_result(
        self,
        owner,
        repo_name,
        comment_id,
        pr_number,
        head_sha,
        features,
        review_run_id,
        *,
        error,
        analysis_mode,
        diff_size,
        config_source,
    ) -> None:
        async with self.database.session() as session:
            publisher = ReviewPublisher(session, self.gitea_client)
            await publisher.publish_error_comment(
                owner=owner,
                repo_name=repo_name,
                comment_id=comment_id,
                pr_number=pr_number,
                error_message=error,
                features=features,
            )
            await publisher.set_error_status(
                owner=owner,
                repo_name=repo_name,
                head_sha=head_sha,
                description=error,
                features=features,
            )
        if review_run_id:
            async with self.database.session() as session:
                await RunRecorder(session).fail_run(
                    review_run_id,
                    error_message=error,
                    analysis_mode=analysis_mode,
                    diff_size=diff_size,
                    config_source=config_source,
                )

    async def _fail_with_result(
        self,
        owner,
        repo_name,
        comment_id,
        pr_number,
        head_sha,
        features,
        review_run_id,
        provider_run_session_id,
        analysis_error,
        analysis_mode,
        diff_size,
        config_source,
        model,
        gitea_api_calls,
        clone_operations,
    ) -> None:
        async with self.database.session() as session:
            publisher = ReviewPublisher(session, self.gitea_client)
            await publisher.publish_error_comment(
                owner=owner,
                repo_name=repo_name,
                comment_id=comment_id,
                pr_number=pr_number,
                error_message=analysis_error,
                features=features,
            )
            await publisher.set_error_status(
                owner=owner,
                repo_name=repo_name,
                head_sha=head_sha,
                description=analysis_error.replace("\n", " ").strip()[:120]
                or "代码审查失败",
                features=features,
            )
        if review_run_id:
            async with self.database.session() as session:
                await RunRecorder(session).fail_run(
                    review_run_id,
                    error_message=analysis_error,
                    analysis_mode=analysis_mode,
                    diff_size=diff_size,
                    config_source=config_source,
                )
        if provider_run_session_id:
            async with self.database.session() as session:
                await RunRecorder(session).complete_provider_run(
                    provider_run_session_id,
                    status="failed",
                    model=model,
                    error=analysis_error,
                    analysis_run_id=review_run_id,
                )

    async def _fail_on_exception(
        self,
        review_run_id: Optional[int],
        provider_run_session_id: Optional[str],
        exc: Exception,
    ) -> None:
        if review_run_id:
            try:
                async with self.database.session() as session:
                    await RunRecorder(session).fail_run(
                        review_run_id,
                        error_message=str(exc),
                    )
            except Exception as db_error:
                logger.error(f"更新数据库记录失败: {db_error}")
        if provider_run_session_id:
            try:
                async with self.database.session() as session:
                    await RunRecorder(session).complete_provider_run(
                        provider_run_session_id,
                        status="failed",
                        error=str(exc),
                        analysis_run_id=review_run_id,
                    )
            except Exception as exc2:
                logger.warning("完成 ProviderRun 失败（非致命）: %s", exc2)
