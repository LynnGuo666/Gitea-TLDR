"""运行时 ORM 模型导出。

应用代码只导入当前领域模型；旧表仅在 Alembic 迁移脚本中
通过 SQL 读取并重命名为 legacy_*，不再建立运行时 ORM 映射。
"""

from .base import Base, TimestampMixin
from .schema import (
    Actor,
    AnalysisAnnotation,
    AnalysisRun,
    AppSetting,
    AuditEvent,
    AuthSession,
    ProviderCredential,
    ProviderRun,
    Repository,
    RepositoryConfig,
    RepositoryFeature,
    UsageEvent,
    WebhookEvent,
    WEBHOOK_PENDING_STATUSES,
    WEBHOOK_STATUS_ERROR,
    WEBHOOK_STATUS_PROCESSING,
    WEBHOOK_STATUS_QUEUED,
    WEBHOOK_STATUS_RETRYING,
    WEBHOOK_STATUS_SUCCESS,
)

# 兼容还未完全清理的权限/依赖注入类型名；表和语义已经是 Actor。
User = Actor

DEFAULT_ISSUE_FOCUS = ["bug", "duplicate", "design"]

__all__ = [
    "Base",
    "TimestampMixin",
    "Actor",
    "User",
    "AuthSession",
    "AppSetting",
    "Repository",
    "RepositoryFeature",
    "ProviderCredential",
    "RepositoryConfig",
    "AnalysisRun",
    "AnalysisAnnotation",
    "ProviderRun",
    "UsageEvent",
    "WebhookEvent",
    "AuditEvent",
    "DEFAULT_ISSUE_FOCUS",
    "WEBHOOK_PENDING_STATUSES",
    "WEBHOOK_STATUS_QUEUED",
    "WEBHOOK_STATUS_PROCESSING",
    "WEBHOOK_STATUS_RETRYING",
    "WEBHOOK_STATUS_SUCCESS",
    "WEBHOOK_STATUS_ERROR",
]
