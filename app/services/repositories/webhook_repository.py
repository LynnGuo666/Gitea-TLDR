"""Webhook 事件 Repository。

封装 `webhook_events` 表的读写。注入 `AsyncSession`，与 `DBService(session)`
对称——调用方在 `async with database.session() as session` 内构造
`WebhookRepository(session)`，不改变现有 session 生命周期。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebhookEvent, WEBHOOK_PENDING_STATUSES


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WebhookRepository:
    """webhook_events 表的访问层。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_webhook_event(
        self,
        request_id: str,
        repository_id: Optional[int],
        event_type: str,
        payload: str,
        status: str = "queued",
    ) -> WebhookEvent:
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

    async def update_webhook_event(
        self, event_id: int, **kwargs: object
    ) -> Optional[WebhookEvent]:
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

    async def list_pending_webhook_events(
        self, min_age_seconds: int = 60, max_age_hours: int = 6
    ) -> list[WebhookEvent]:
        now = _now()
        stmt = select(WebhookEvent).where(
            WebhookEvent.status.in_(WEBHOOK_PENDING_STATUSES),
            WebhookEvent.created_at >= now - timedelta(hours=max_age_hours),
            WebhookEvent.created_at <= now - timedelta(seconds=min_age_seconds),
        )
        result = await self.session.execute(
            stmt.order_by(WebhookEvent.created_at.asc())
        )
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
