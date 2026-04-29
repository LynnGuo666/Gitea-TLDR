"""配置健康检查服务。

复用了 resolve_provider_config / resolve_issue_config，从 DB 与全局配置中判断
仓库各功能模块的配置完整度，返回供前端统一展示的健康状态。
"""

from __future__ import annotations

import logging
from typing import Any

from app.models import DEFAULT_ISSUE_FOCUS
from app.services.db_service import DBService
from app.services.issue_config_resolver import resolve_issue_config
from app.services.provider_config_resolver import resolve_provider_config

logger = logging.getLogger(__name__)


async def check_repo_config_health(
    db_service: DBService,
    owner: str,
    repo_name: str,
) -> dict[str, Any]:
    """返回仓库各配置组件的健康状态。"""
    checks: list[dict[str, Any]] = []

    repo = await db_service.get_repository(owner, repo_name)
    repository_id: int | None = repo.id if repo else None

    # ---- PR 审查 ----
    pr_status = "error"
    pr_message = "PR 审查未配置 API Key/Token"
    pr_resolution = "在仓库设置或全局个人设置中配置 Provider API Key"

    if repository_id is not None:
        repo_config = await db_service.get_repo_specific_model_config(repository_id)
        global_config = await db_service.get_global_model_config()
        resolved = resolve_provider_config(
            repo_config, global_config, default_engine="claude_code"
        )
        if resolved.api_key:
            pr_status = "ok"
            pr_message = "PR 审查已配置 API Key"

    checks.append(
        {
            "component": "pr_review",
            "status": pr_status,
            "message": pr_message,
            "resolution": pr_resolution,
        }
    )

    # ---- Issue 分析 ----
    issue_status = "error"
    issue_message = "Issue 分析未配置 Forge API Key"
    issue_resolution = (
        "在仓库「Issue 分析」标签页或全局 Issue 配置中设置 Forge API Key"
    )

    if repository_id is not None:
        repo_issue_config = await db_service.get_repo_specific_issue_config(
            repository_id
        )
        global_issue_config = await db_service.get_global_issue_config()
        resolved_issue = resolve_issue_config(
            repo_issue_config, global_issue_config, default_engine="forge"
        )
        if resolved_issue.api_key:
            issue_status = "ok"
            issue_message = "Issue 分析已配置 Forge API Key"
    else:
        # 仓库不存在时也尝试读全局 Issue 配置
        global_issue_config = await db_service.get_global_issue_config()
        if global_issue_config is not None:
            resolved_issue = resolve_issue_config(
                None, global_issue_config, default_engine="forge"
            )
            if resolved_issue.api_key:
                issue_status = "ok"
                issue_message = "Issue 分析已配置 Forge API Key（全局）"

    checks.append(
        {
            "component": "issue_analysis",
            "status": issue_status,
            "message": issue_message,
            "resolution": issue_resolution,
        }
    )

    # ---- Webhook ----
    checks.append(
        {
            "component": "webhook",
            "status": "ok",
            "message": "Webhook 配置需在 Gitea 仓库设置中验证",
            "resolution": "在 Gitea 仓库 Settings → Webhooks 中检查",
        }
    )

    # ---- Overall ----
    statuses = [c["status"] for c in checks]
    if "error" in statuses:
        overall = "error"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "ok"

    return {"overall": overall, "checks": checks}
