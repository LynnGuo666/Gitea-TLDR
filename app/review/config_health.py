"""配置健康检查服务。"""

from __future__ import annotations

import logging
from typing import Any

from app.services.db_service import DBService

logger = logging.getLogger(__name__)


async def check_config_health(
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
    pr_message = "PR 审查未初始化仓库配置"
    pr_resolution = "从模板初始化 review 配置，并选择可用凭证"

    if repository_id is not None:
        repo_config = await db_service.get_repository_config(repository_id, "review")
        if repo_config and repo_config.api_key:
            pr_status = "ok"
            pr_message = "PR 审查已配置 API Key"
        elif repo_config:
            pr_message = "PR 审查配置缺少可用凭证"

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
    issue_message = "Issue 分析未初始化仓库配置"
    issue_resolution = "从模板初始化 issue 配置，并选择可用 Forge 凭证"

    if repository_id is not None:
        repo_issue_config = await db_service.get_repository_config(
            repository_id, "issue"
        )
        if repo_issue_config and repo_issue_config.api_key:
            issue_status = "ok"
            issue_message = "Issue 分析已配置 Forge API Key"
        elif repo_issue_config:
            issue_message = "Issue 分析配置缺少可用凭证"

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


# backward-compat alias（原名 check_repo_config_health）
check_repo_config_health = check_config_health
