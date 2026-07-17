"""审计数据 Repository。

封装 `audit_events` 表的读写。注入 `AsyncSession`，与 `DBService(session)`
对称——调用方在 `async with database.session() as session` 内构造
`AuditRepository(session)`，不改变现有 session 生命周期。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


class AuditRepository:
    """audit_events 表的访问层。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_audit(
        self,
        *,
        actor_id: Optional[int],
        actor_type: str,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        repository_id: Optional[int] = None,
        request_id: Optional[str] = None,
        source: str = "api",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        before: Any = None,
        after: Any = None,
        error_message: Optional[str] = None,
    ) -> AuditEvent:
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

    async def list_audit_events(
        self, limit: int = 100, offset: int = 0, **filters: Any
    ) -> list[AuditEvent]:
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
