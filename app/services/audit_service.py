"""审计服务。"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)

SENSITIVE_FIELD_MASKS = {
    "api_key_enc": "[REDACTED]",
    "access_token_enc": "[REDACTED]",
    "refresh_token_enc": "[REDACTED]",
    "webhook_secret_enc": "[REDACTED]",
    "session_token_hash": "[HASHED]",
}


def redact_payload(value: Any) -> Any:
    """递归脱敏审计 payload。"""
    if isinstance(value, dict):
        return {
            key: SENSITIVE_FIELD_MASKS.get(key, redact_payload(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    return value


class AuditService:
    """业务写操作的统一审计入口。

    依赖 `AsyncSession`（或已有的 `AuditRepository`），消除对 `DBService`
    的反向依赖——audit 是独立领域，不再借用核心域服务落库。
    """

    def __init__(self, session_or_repo: "AsyncSession | AuditRepository"):
        if isinstance(session_or_repo, AuditRepository):
            self._repo = session_or_repo
        else:
            self._repo = AuditRepository(session_or_repo)

    async def record_success(
        self,
        *,
        actor_id: Optional[int] = None,
        actor_type: str = "user",
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        before: Any = None,
        after: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        await self._record(
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status="success",
            before=before,
            after=after,
            context=context,
        )

    async def record_failure(
        self,
        *,
        actor_id: Optional[int] = None,
        actor_type: str = "user",
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        error: Any,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        await self._record(
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status="failed",
            error_message=str(error),
            context=context,
        )

    async def record_denied(
        self,
        *,
        actor_id: Optional[int] = None,
        actor_type: str = "user",
        action: str,
        resource_type: str,
        reason: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        await self._record(
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            status="denied",
            error_message=reason,
            context=context,
        )

    async def _record(
        self,
        *,
        actor_id: Optional[int],
        actor_type: str,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        status: str,
        before: Any = None,
        after: Any = None,
        error_message: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        context = context or {}
        try:
            await self._repo.record_audit(
                actor_id=actor_id,
                actor_type=actor_type,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                repository_id=context.get("repository_id"),
                request_id=context.get("request_id"),
                source=context.get("source", "api"),
                ip_address=context.get("ip_address"),
                user_agent=context.get("user_agent"),
                status=status,
                before=redact_payload(before),
                after=redact_payload(after),
                error_message=error_message,
            )
        except Exception:
            logger.exception(
                "写入审计事件失败: action=%s resource=%s", action, resource_type
            )
