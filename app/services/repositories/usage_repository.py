"""用量数据 Repository。

封装 `usage_events` 表的读写。注入 `AsyncSession`，与 `DBService(session)`
对称——调用方在 `async with database.session() as session` 内构造
`UsageRepository(session)`，不改变现有 session 生命周期。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UsageEvent


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UsageRepository:
    """usage_events 表的访问层。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_usage_event(self, repository_id: int, **kwargs: Any) -> UsageEvent:
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
    ) -> list[UsageEvent]:
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

    async def get_usage_summary(
        self,
        repository_id: Optional[int] = None,
        actor_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict[str, Any]:
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
