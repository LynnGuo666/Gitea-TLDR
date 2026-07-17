"""数据库服务。

外部 API 使用 /api/v2；内部服务直接面向当前领域模型。
少量旧方法名保留为内部适配，便于分阶段清理 webhook/issue 流程。
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Actor,
    AnalysisAnnotation,
    AnalysisRun,
    AppSetting,
    AuditEvent,
    ProviderCredential,
    ProviderRun,
    Repository,
    RepositoryConfig,
    RepositoryFeature,
    UsageEvent,
    WebhookEvent,
    WEBHOOK_PENDING_STATUSES,
    WEBHOOK_STATUS_QUEUED,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


class DBService:
    """数据库操作服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== Actors ====================

    async def get_or_create_user_by_username(self, username: str) -> Actor:
        stmt = select(Actor).where(
            Actor.external_provider == "gitea",
            Actor.external_username == username,
        )
        result = await self.session.execute(stmt)
        actor = result.scalar_one_or_none()
        if actor:
            return actor
        actor = Actor(
            external_provider="gitea",
            external_username=username,
            display_name=username,
            role="user",
            is_active=True,
        )
        self.session.add(actor)
        await self.session.flush()
        return actor

    async def list_actors(
        self,
        *,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Actor]:
        stmt = select(Actor)
        if role:
            stmt = stmt.where(Actor.role == role)
        if is_active is not None:
            stmt = stmt.where(Actor.is_active == is_active)
        result = await self.session.execute(
            stmt.order_by(Actor.updated_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def update_actor(self, actor_id: int, **fields: Any) -> Optional[Actor]:
        actor = await self.session.get(Actor, actor_id)
        if not actor:
            return None
        for key, value in fields.items():
            if key == "permissions":
                actor.permissions_json = _json(value or [])
            elif hasattr(actor, key) and value is not None:
                setattr(actor, key, value)
        await self.session.flush()
        return actor

    # ==================== App settings ====================

    async def list_app_settings(self, category: Optional[str] = None) -> list[AppSetting]:
        stmt = select(AppSetting)
        if category:
            stmt = stmt.where(AppSetting.category == category)
        result = await self.session.execute(stmt.order_by(AppSetting.category, AppSetting.key))
        return list(result.scalars().all())

    async def update_app_setting(
        self,
        key: str,
        value: Any,
        *,
        category: str = "general",
        description: Optional[str] = None,
        actor_id: Optional[int] = None,
    ) -> AppSetting:
        result = await self.session.execute(select(AppSetting).where(AppSetting.key == key))
        setting = result.scalar_one_or_none()
        if not setting:
            setting = AppSetting(
                key=key,
                category=category,
                value_json=_json(value),
                description=description,
                updated_by_actor_id=actor_id,
            )
            self.session.add(setting)
        else:
            setting.value_json = _json(value)
            if category:
                setting.category = category
            if description is not None:
                setting.description = description
            setting.updated_by_actor_id = actor_id
        await self.session.flush()
        return setting

    async def delete_app_setting(self, key: str) -> bool:
        result = await self.session.execute(select(AppSetting).where(AppSetting.key == key))
        setting = result.scalar_one_or_none()
        if not setting:
            return False
        await self.session.delete(setting)
        await self.session.flush()
        return True

    async def get_app_setting(self, key: str, fallback: Any = None) -> Any:
        """从 DB 读取一个 app setting 值，不存在时返回 fallback。"""
        result = await self.session.execute(select(AppSetting).where(AppSetting.key == key))
        row = result.scalar_one_or_none()
        if not row:
            return fallback
        try:
            return json.loads(row.value_json)
        except Exception:
            return fallback

    # ==================== Repository ====================

    async def get_or_create_repository(self, owner: str, repo_name: str) -> Repository:
        stmt = select(Repository).where(
            Repository.provider == "gitea",
            Repository.owner == owner,
            Repository.name == repo_name,
        )
        result = await self.session.execute(stmt)
        repo = result.scalar_one_or_none()
        if repo:
            return repo
        repo = Repository(
            provider="gitea",
            owner=owner,
            name=repo_name,
            full_name=f"{owner}/{repo_name}",
            is_active=True,
        )
        self.session.add(repo)
        await self.session.flush()
        await self.ensure_repository_feature(repo.id, "review")
        await self.ensure_repository_feature(repo.id, "issue")
        logger.info("创建仓库记录: %s/%s", owner, repo_name)
        return repo

    async def get_repository(self, owner: str, repo_name: str) -> Optional[Repository]:
        stmt = select(Repository).where(
            Repository.provider == "gitea",
            Repository.owner == owner,
            Repository.name == repo_name,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_repository_by_id(self, repo_id: int) -> Optional[Repository]:
        result = await self.session.execute(select(Repository).where(Repository.id == repo_id))
        return result.scalar_one_or_none()

    async def list_repositories(
        self,
        is_active: Optional[bool] = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Repository]:
        stmt = select(Repository)
        if is_active is not None:
            stmt = stmt.where(Repository.is_active == is_active)
        stmt = stmt.order_by(Repository.updated_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_repository_secret(
        self, owner: str, repo_name: str, webhook_secret: Optional[str]
    ) -> Optional[Repository]:
        repo = await self.get_or_create_repository(owner, repo_name)
        repo.webhook_secret = webhook_secret
        await self.session.flush()
        return repo

    async def ensure_repository_feature(
        self,
        repository_id: int,
        scenario: str,
        *,
        enabled: bool = True,
        auto_on_open: bool = True,
        manual_command_enabled: bool = True,
    ) -> RepositoryFeature:
        stmt = select(RepositoryFeature).where(
            RepositoryFeature.repository_id == repository_id,
            RepositoryFeature.scenario == scenario,
        )
        result = await self.session.execute(stmt)
        feature = result.scalar_one_or_none()
        if feature:
            return feature
        feature = RepositoryFeature(
            repository_id=repository_id,
            scenario=scenario,
            enabled=enabled,
            auto_on_open=auto_on_open,
            manual_command_enabled=manual_command_enabled,
        )
        self.session.add(feature)
        await self.session.flush()
        return feature

    async def get_repository_feature(
        self, repository_id: int, scenario: str
    ) -> Optional[RepositoryFeature]:
        result = await self.session.execute(
            select(RepositoryFeature).where(
                RepositoryFeature.repository_id == repository_id,
                RepositoryFeature.scenario == scenario,
            )
        )
        return result.scalar_one_or_none()

    # ==================== Credentials / Templates / Configs ====================

    async def list_provider_credentials(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProviderCredential]:
        result = await self.session.execute(
            select(ProviderCredential)
            .order_by(ProviderCredential.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create_provider_credential(
        self,
        *,
        name: str,
        provider: str,
        api_url: Optional[str],
        api_key: Optional[str],
        scope_type: str = "system",
        scope_key: str = "system",
        actor_id: Optional[int] = None,
    ) -> ProviderCredential:
        cred = ProviderCredential(
            scope_type=scope_type,
            scope_key=scope_key,
            name=name,
            provider=provider,
            api_url=api_url,
            is_active=True,
            created_by_actor_id=actor_id,
        )
        cred.api_key = api_key
        self.session.add(cred)
        await self.session.flush()
        return cred

    async def rotate_provider_credential(
        self, credential_id: int, api_key: str
    ) -> Optional[ProviderCredential]:
        cred = await self.session.get(ProviderCredential, credential_id)
        if not cred:
            return None
        cred.api_key = api_key
        await self.session.flush()
        return cred

    async def update_provider_credential(
        self, credential_id: int, **fields: Any
    ) -> Optional[ProviderCredential]:
        cred = await self.session.get(ProviderCredential, credential_id)
        if not cred:
            return None
        for key, value in fields.items():
            if key == "api_key" and value is not None:
                cred.api_key = value
            elif hasattr(cred, key) and value is not None:
                setattr(cred, key, value)
        await self.session.flush()
        return cred

    async def disable_provider_credential(
        self, credential_id: int
    ) -> Optional[ProviderCredential]:
        cred = await self.session.get(ProviderCredential, credential_id)
        if not cred:
            return None
        cred.is_active = False
        await self.session.flush()
        return cred

    async def delete_provider_credential(self, credential_id: int) -> bool:
        in_use = await self.session.execute(
            select(func.count(RepositoryConfig.id)).where(
                RepositoryConfig.credential_id == credential_id
            )
        )
        if int(in_use.scalar() or 0) > 0:
            raise ValueError("credential_in_use")
        cred = await self.session.get(ProviderCredential, credential_id)
        if not cred:
            return False
        await self.session.delete(cred)
        await self.session.flush()
        return True

    async def get_repository_config(
        self, repository_id: int, scenario: str
    ) -> Optional[RepositoryConfig]:
        stmt = (
            select(RepositoryConfig)
            .options(selectinload(RepositoryConfig.credential))
            .where(
                RepositoryConfig.repository_id == repository_id,
                RepositoryConfig.scenario == scenario,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_repository_config(
        self, repository_id: int, scenario: str, **fields: Any
    ) -> RepositoryConfig:
        cfg = await self.get_repository_config(repository_id, scenario)
        if not cfg:
            raise ValueError("configuration_required")
        for key, value in fields.items():
            if key == "focus":
                cfg.focus_json = _json(value or [])
            elif key == "features":
                cfg.features_json = _json(value or [])
            elif hasattr(cfg, key) and value is not None:
                setattr(cfg, key, value)
        await self.session.flush()
        return cfg

    # ==================== Runs ====================

    async def create_analysis_run(
        self,
        *,
        kind: str,
        repository_id: int,
        external_number: int,
        trigger_type: str,
        external_title: Optional[str] = None,
        external_author: Optional[str] = None,
        external_state: Optional[str] = None,
        source_branch: Optional[str] = None,
        target_branch: Optional[str] = None,
        head_sha: Optional[str] = None,
        source_comment_id: Optional[int] = None,
        bot_comment_id: Optional[int] = None,
        effective_engine: Optional[str] = None,
        effective_model: Optional[str] = None,
        repository_config_id: Optional[int] = None,
        credential_id: Optional[int] = None,
        result_payload: Optional[dict[str, Any]] = None,
    ) -> AnalysisRun:
        run = AnalysisRun(
            kind=kind,
            repository_id=repository_id,
            external_number=external_number,
            external_title=external_title,
            external_author=external_author,
            external_state=external_state,
            source_branch=source_branch,
            target_branch=target_branch,
            head_sha=head_sha,
            trigger_type=trigger_type,
            source_comment_id=source_comment_id,
            bot_comment_id=bot_comment_id,
            effective_engine=effective_engine,
            effective_model=effective_model,
            repository_config_id=repository_config_id,
            credential_id=credential_id,
            status="running",
            result_payload_json=_json(result_payload or {}),
            started_at=_now(),
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def complete_analysis_run(
        self,
        run_id: int,
        *,
        status: str,
        overall_success: Optional[bool] = None,
        overall_severity: Optional[str] = None,
        summary_markdown: Optional[str] = None,
        result_payload: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[AnalysisRun]:
        run = await self.session.get(AnalysisRun, run_id)
        if not run:
            return None
        run.status = status
        run.overall_success = overall_success
        if overall_severity is not None:
            run.overall_severity = overall_severity
        if summary_markdown is not None:
            run.summary_markdown = summary_markdown
        if result_payload is not None:
            run.result_payload_json = _json(result_payload)
        if error_message is not None:
            run.error_message = error_message
        run.completed_at = _now()
        run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
        await self.session.flush()
        return run

    async def update_analysis_run(self, run_id: int, **fields: Any) -> Optional[AnalysisRun]:
        run = await self.session.get(AnalysisRun, run_id)
        if not run:
            return None
        payload = run.get_analysis_payload()
        payload_update = fields.pop("result_payload", None)
        if payload_update:
            payload.update(payload_update)
        for key, value in fields.items():
            if hasattr(run, key) and value is not None:
                setattr(run, key, value)
        if payload_update is not None:
            run.result_payload_json = _json(payload)
        await self.session.flush()
        return run

    async def list_analysis_runs(
        self,
        *,
        kind: Optional[str] = None,
        repository_id: Optional[int] = None,
        repository_ids: Optional[list[int]] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AnalysisRun]:
        stmt = select(AnalysisRun).options(selectinload(AnalysisRun.repository))
        if kind:
            stmt = stmt.where(AnalysisRun.kind == kind)
        if repository_ids is not None:
            stmt = stmt.where(AnalysisRun.repository_id.in_(repository_ids))
        elif repository_id is not None:
            stmt = stmt.where(AnalysisRun.repository_id == repository_id)
        if status:
            stmt = stmt.where(AnalysisRun.status == status)
        stmt = stmt.order_by(AnalysisRun.started_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_analysis_run(self, run_id: int) -> Optional[AnalysisRun]:
        result = await self.session.execute(
            select(AnalysisRun)
            .options(selectinload(AnalysisRun.repository))
            .where(AnalysisRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_review_run_by_head(
        self, repository_id: int, pr_number: int, head_sha: str
    ) -> Optional[AnalysisRun]:
        result = await self.session.execute(
            select(AnalysisRun)
            .where(
                AnalysisRun.kind == "review",
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.external_number == pr_number,
                AnalysisRun.head_sha == head_sha,
            )
            .order_by(AnalysisRun.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_in_flight_issue_run(self, repository_id: int, issue_number: int):
        stmt = select(AnalysisRun).where(
            AnalysisRun.kind == "issue",
            AnalysisRun.repository_id == repository_id,
            AnalysisRun.external_number == issue_number,
            AnalysisRun.status == "running",
        )
        result = await self.session.execute(stmt.order_by(AnalysisRun.started_at.desc()).limit(1))
        return result.scalar_one_or_none()

    async def get_recent_successful_issue_run(
        self, repository_id: int, issue_number: int, within_seconds: int
    ):
        threshold = _now() - timedelta(seconds=within_seconds)
        stmt = select(AnalysisRun).where(
            AnalysisRun.kind == "issue",
            AnalysisRun.repository_id == repository_id,
            AnalysisRun.external_number == issue_number,
            AnalysisRun.overall_success.is_(True),
            AnalysisRun.completed_at >= threshold,
        )
        result = await self.session.execute(stmt.order_by(AnalysisRun.completed_at.desc()).limit(1))
        return result.scalar_one_or_none()

    # ==================== Annotations ====================

    async def save_analysis_annotations(
        self, analysis_run_id: int, comments: list[dict[str, Any]]
    ):
        saved = []
        for item in comments:
            annotation = AnalysisAnnotation(
                analysis_run_id=analysis_run_id,
                annotation_type="inline_comment",
                file_path=item.get("path", ""),
                new_line=item.get("new_line"),
                old_line=item.get("old_line"),
                severity=item.get("severity"),
                body=item.get("comment", ""),
                suggestion=item.get("suggestion"),
                created_at=_now(),
            )
            self.session.add(annotation)
            saved.append(annotation)
        await self.session.flush()
        return saved

    async def list_analysis_annotations(self, analysis_run_id: int):
        result = await self.session.execute(
            select(AnalysisAnnotation).where(
                AnalysisAnnotation.analysis_run_id == analysis_run_id,
            )
        )
        return list(result.scalars().all())

    # ==================== Provider runs ====================

    async def create_provider_run(self, repository_id: Optional[int], scenario: str, provider: str = "forge", analysis_run_id: Optional[int] = None):
        run = ProviderRun(
            analysis_run_id=analysis_run_id,
            repository_id=repository_id,
            provider=provider,
            provider_session_id="fgs-" + secrets.token_hex(8),
            scenario=scenario,
            status="running",
            started_at=_now(),
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def complete_provider_run(self, provider_session_id: str, **kwargs):
        result = await self.session.execute(
            select(ProviderRun).where(ProviderRun.provider_session_id == provider_session_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return None
        run.status = kwargs.get("status", "completed")
        run.model = kwargs.get("model") or run.model
        run.turns = kwargs.get("turns", 0)
        run.tool_calls_count = kwargs.get("tool_calls_count", 0)
        if kwargs.get("messages_json") is not None:
            run.messages_json = kwargs["messages_json"]
        run.input_tokens = kwargs.get("input_tokens", 0)
        run.output_tokens = kwargs.get("output_tokens", 0)
        run.cache_creation_input_tokens = kwargs.get("cache_creation_input_tokens", 0)
        run.cache_read_input_tokens = kwargs.get("cache_read_input_tokens", 0)
        if kwargs.get("analysis_run_id") is not None:
            run.analysis_run_id = kwargs["analysis_run_id"]
        run.error_message = kwargs.get("error")
        run.completed_at = _now()
        run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
        await self.session.flush()
        return run

    async def list_provider_runs(self, provider: Optional[str] = None, scenario: Optional[str] = None, limit: int = 50, offset: int = 0, repository_ids: Optional[list[int]] = None):
        stmt = select(ProviderRun).options(selectinload(ProviderRun.repository))
        if provider:
            stmt = stmt.where(ProviderRun.provider == provider)
        if scenario:
            stmt = stmt.where(ProviderRun.scenario == scenario)
        if repository_ids is not None:
            stmt = stmt.where(ProviderRun.repository_id.in_(repository_ids))
        stmt = stmt.order_by(ProviderRun.started_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_provider_run(self, provider_session_id: str):
        result = await self.session.execute(
            select(ProviderRun)
            .options(selectinload(ProviderRun.repository))
            .where(ProviderRun.provider_session_id == provider_session_id)
        )
        return result.scalar_one_or_none()

    # ==================== Usage ====================

    async def record_usage_event(self, repository_id: int, **kwargs):
        event = UsageEvent(
            analysis_run_id=kwargs.get("analysis_run_id"),
            repository_id=repository_id,
            actor_id=kwargs.get("actor_id") or kwargs.get("user_id"),
            event_date=date.today(),
            provider=kwargs.get("provider"),
            input_tokens=kwargs.get("input_tokens", 0),
            output_tokens=kwargs.get("output_tokens", 0),
            cache_creation_input_tokens=kwargs.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=kwargs.get("cache_read_input_tokens", 0),
            gitea_api_calls=kwargs.get("gitea_api_calls", 0),
            provider_api_calls=kwargs.get("provider_api_calls", 0),
            clone_operations=kwargs.get("clone_operations", 0),
            created_at=_now(),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_usage_events(
        self,
        repository_id: Optional[int] = None,
        actor_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        *,
        limit: int = 200,
        offset: int = 0,
    ):
        stmt = select(UsageEvent)
        if repository_id:
            stmt = stmt.where(UsageEvent.repository_id == repository_id)
        if actor_id is not None:
            stmt = stmt.where(UsageEvent.actor_id == actor_id)
        if start_date:
            stmt = stmt.where(UsageEvent.event_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageEvent.event_date <= end_date)
        result = await self.session.execute(
            stmt.order_by(UsageEvent.event_date.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_usage_summary(self, repository_id: Optional[int] = None, actor_id: Optional[int] = None, user_id: Optional[int] = None, start_date: Optional[date] = None, end_date: Optional[date] = None):
        stmt = select(
            func.sum(UsageEvent.input_tokens).label("total_input_tokens"),
            func.sum(UsageEvent.output_tokens).label("total_output_tokens"),
            func.sum(UsageEvent.cache_creation_input_tokens).label("total_cache_creation_tokens"),
            func.sum(UsageEvent.cache_read_input_tokens).label("total_cache_read_tokens"),
            func.sum(UsageEvent.gitea_api_calls).label("total_gitea_calls"),
            func.sum(UsageEvent.provider_api_calls).label("total_provider_calls"),
            func.sum(UsageEvent.clone_operations).label("total_clone_operations"),
            func.count(UsageEvent.id).label("record_count"),
        )
        if repository_id:
            stmt = stmt.where(UsageEvent.repository_id == repository_id)
        actor_filter = actor_id if actor_id is not None else user_id
        if actor_filter is not None:
            stmt = stmt.where(UsageEvent.actor_id == actor_filter)
        if start_date:
            stmt = stmt.where(UsageEvent.event_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageEvent.event_date <= end_date)
        row = (await self.session.execute(stmt)).one()
        return {
            "total_input_tokens": row.total_input_tokens or 0,
            "total_output_tokens": row.total_output_tokens or 0,
            "total_cache_creation_tokens": row.total_cache_creation_tokens or 0,
            "total_cache_read_tokens": row.total_cache_read_tokens or 0,
            "total_gitea_calls": row.total_gitea_calls or 0,
            "total_provider_calls": row.total_provider_calls or 0,
            "total_clone_operations": row.total_clone_operations or 0,
            "record_count": row.record_count or 0,
            "run_count": row.record_count or 0,
        }

    # ==================== Webhooks ====================

    async def create_webhook_event(self, request_id: str, repository_id: Optional[int], event_type: str, payload: str, status: str = WEBHOOK_STATUS_QUEUED):
        event = WebhookEvent(
            request_id=request_id,
            repository_id=repository_id or None,
            event_type=event_type,
            payload_json=payload,
            status=status,
            processing_time_ms=0,
            retry_count=0,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def update_webhook_event(self, event_id: int, **kwargs):
        event = await self.session.get(WebhookEvent, event_id)
        if not event:
            return None
        for key, value in kwargs.items():
            if key == "increment_retry" and value:
                event.retry_count += 1
            elif hasattr(event, key) and value is not None:
                setattr(event, key, value)
        await self.session.flush()
        return event

    async def list_pending_webhook_events(self, min_age_seconds: int = 60, max_age_hours: int = 6):
        now = _now()
        stmt = select(WebhookEvent).where(
            WebhookEvent.status.in_(WEBHOOK_PENDING_STATUSES),
            WebhookEvent.created_at >= now - timedelta(hours=max_age_hours),
            WebhookEvent.created_at <= now - timedelta(seconds=min_age_seconds),
        )
        result = await self.session.execute(stmt.order_by(WebhookEvent.created_at.asc()))
        return list(result.scalars().all())

    async def list_webhook_events(
        self,
        *,
        repository_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WebhookEvent]:
        stmt = select(WebhookEvent)
        if repository_id is not None:
            stmt = stmt.where(WebhookEvent.repository_id == repository_id)
        if status:
            stmt = stmt.where(WebhookEvent.status == status)
        result = await self.session.execute(
            stmt.order_by(WebhookEvent.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_webhook_event(self, event_id: int) -> Optional[WebhookEvent]:
        return await self.session.get(WebhookEvent, event_id)

    # ==================== Audit ====================

    async def record_audit(self, *, actor_id: Optional[int], actor_type: str, action: str, resource_type: str, resource_id: Optional[int] = None, repository_id: Optional[int] = None, request_id: Optional[str] = None, source: str = "api", ip_address: Optional[str] = None, user_agent: Optional[str] = None, status: str = "success", before: Any = None, after: Any = None, error_message: Optional[str] = None):
        event = AuditEvent(
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            repository_id=repository_id,
            request_id=request_id,
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
            before_json=_json(before) if before is not None else None,
            after_json=_json(after) if after is not None else None,
            status=status,
            error_message=error_message,
            created_at=_now(),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_audit_events(self, limit: int = 100, offset: int = 0, **filters):
        stmt = select(AuditEvent)
        for attr in ["actor_id", "repository_id", "resource_type", "action"]:
            value = filters.get(attr)
            if value is not None:
                stmt = stmt.where(getattr(AuditEvent, attr) == value)
        result = await self.session.execute(
            stmt.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_audit_event(self, event_id: int) -> Optional[AuditEvent]:
        return await self.session.get(AuditEvent, event_id)
