"""
HTTP route definitions for the FastAPI application.
"""

from __future__ import annotations

import hmac
import hashlib
import logging
import secrets
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from fastapi import (
    APIRouter,
    Request,
    Header,
    HTTPException,
    BackgroundTasks,
    Response,
    Query,
    Depends,
)
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from app.core.admin_auth import admin_required
from app.core import (
    settings,
    runtime_settings,
    __version__,
    __release_date__,
    get_version_info,
    get_changelog,
    get_all_changelogs,
    get_all_changelogs_json,
)
from app.core.context import AppContext
from app.models import User
from app.services.provider_config_resolver import (
    clear_provider_overrides,
    has_non_provider_settings,
    resolve_provider_config,
)

logger = logging.getLogger(__name__)


class WebhookSetupRequest(BaseModel):
    """前端用于配置Webhook的请求体"""

    callback_url: Optional[str] = Field(
        default=None, description="可选覆盖webhook回调URL"
    )
    events: list[str] = Field(
        default_factory=lambda: ["pull_request", "issues", "issue_comment"],
        description="需要监听的事件列表",
    )
    bring_bot: bool = Field(default=True, description="是否自动邀请bot账号协作")


class ModelConfigRequest(BaseModel):
    """模型配置请求体"""

    config_name: str = Field(..., description="配置名称")
    repository_id: Optional[int] = Field(
        None, description="关联仓库ID（为空则为全局配置）"
    )
    engine: str = Field("claude_code", description="审查引擎名称")
    model: Optional[str] = Field(None, description="实际LLM模型标识")
    max_tokens: Optional[int] = Field(None, description="最大token数")
    temperature: Optional[float] = Field(None, description="温度参数")
    custom_prompt: Optional[str] = Field(None, description="自定义prompt模板")
    default_features: Optional[List[str]] = Field(None, description="默认功能列表")
    default_focus: Optional[List[str]] = Field(None, description="默认审查重点")
    is_default: bool = Field(False, description="是否为默认配置")


class ProviderConfigRequest(BaseModel):
    """审查引擎配置请求体"""

    model_config = ConfigDict(populate_by_name=True)

    engine: Optional[str] = Field(
        None,
        alias="provider_name",
        description="审查引擎名称，如 claude_code / codex_cli",
    )
    model: Optional[str] = Field(None, description="实际LLM模型标识")
    api_url: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("anthropic_base_url", "provider_api_base_url"),
        description="Provider API Base URL",
    )
    api_key: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("anthropic_auth_token", "provider_auth_token"),
        description="Provider Auth Token",
    )
    inherit_global: Optional[bool] = Field(None, description="是否继承全局 Claude 配置")


ClaudeConfigRequest = ProviderConfigRequest


class ReviewSettingsRequest(BaseModel):
    """审查设置请求体"""

    default_focus: Optional[List[str]] = Field(None, description="默认审查重点")
    default_features: Optional[List[str]] = Field(None, description="默认功能列表")


class IssueSettingsRequest(BaseModel):
    """Issue 设置请求体"""

    issue_enabled: Optional[bool] = Field(None, description="是否启用 Issue 分析")
    auto_on_open: Optional[bool] = Field(None, description="是否自动分析新建/重开 Issue")
    manual_command_enabled: Optional[bool] = Field(
        None, description="是否启用 /issue 手动命令"
    )


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    验证webhook签名

    Args:
        payload: 请求体
        signature: 签名
        secret: 密钥

    Returns:
        是否验证通过
    """
    if not secret:
        return False  # 未配置密钥时拒绝请求

    expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


def create_api_router(context: AppContext) -> tuple[APIRouter, APIRouter]:
    """创建API与公开端点的路由集合。"""

    api_router = APIRouter()
    public_router = APIRouter()

    def _serialize_review_summary(review_session):
        """序列化审查会话的摘要信息。

        Args:
            review_session: 审查会话对象。

        Returns:
            审查摘要字典。
        """
        usage = getattr(review_session, "usage_stat", None)
        return {
            "id": review_session.id,
            "repository_id": review_session.repository_id,
            "repo_full_name": (
                f"{review_session.repository.owner}/{review_session.repository.repo_name}"
                if review_session.repository
                else None
            ),
            "pr_number": review_session.pr_number,
            "pr_title": review_session.pr_title,
            "pr_author": review_session.pr_author,
            "trigger_type": review_session.trigger_type,
            "engine": review_session.engine,
            "enabled_features": review_session.get_features(),
            "focus_areas": review_session.get_focus(),
            "analysis_mode": review_session.analysis_mode,
            "model": review_session.model,
            "config_source": review_session.config_source,
            "overall_severity": review_session.overall_severity,
            "overall_success": review_session.overall_success,
            "error_message": review_session.error_message,
            "inline_comments_count": review_session.inline_comments_count,
            "started_at": (
                review_session.started_at.isoformat() if review_session.started_at else None
            ),
            "completed_at": (
                review_session.completed_at.isoformat()
                if review_session.completed_at
                else None
            ),
            "duration_seconds": review_session.duration_seconds,
            "estimated_input_tokens": (
                usage.estimated_input_tokens if usage else 0
            ),
            "estimated_output_tokens": (
                usage.estimated_output_tokens if usage else 0
            ),
            "cache_creation_input_tokens": (
                usage.cache_creation_input_tokens if usage else 0
            ),
            "cache_read_input_tokens": (
                usage.cache_read_input_tokens if usage else 0
            ),
            "total_tokens": (
                (usage.estimated_input_tokens + usage.estimated_output_tokens)
                if usage
                else 0
            ),
        }

    def _serialize_review_detail(review_session, inline_comments):
        """序列化审查会话的详情信息。

        Args:
            review_session: 审查会话对象。
            inline_comments: 行内评论列表。

        Returns:
            审查详情字典。
        """
        usage = getattr(review_session, "usage_stat", None)
        return {
            "id": review_session.id,
            "repository_id": review_session.repository_id,
            "repo_full_name": (
                f"{review_session.repository.owner}/{review_session.repository.repo_name}"
                if review_session.repository
                else None
            ),
            "engine": review_session.engine,
            "model": review_session.model,
            "config_source": review_session.config_source,
            "pr_number": review_session.pr_number,
            "pr_title": review_session.pr_title,
            "pr_author": review_session.pr_author,
            "head_branch": review_session.head_branch,
            "base_branch": review_session.base_branch,
            "head_sha": review_session.head_sha,
            "trigger_type": review_session.trigger_type,
            "enabled_features": review_session.get_features(),
            "focus_areas": review_session.get_focus(),
            "analysis_mode": review_session.analysis_mode,
            "diff_size_bytes": review_session.diff_size_bytes,
            "overall_severity": review_session.overall_severity,
            "summary_markdown": review_session.summary_markdown,
            "inline_comments_count": review_session.inline_comments_count,
            "overall_success": review_session.overall_success,
            "error_message": review_session.error_message,
            "started_at": (
                review_session.started_at.isoformat() if review_session.started_at else None
            ),
            "completed_at": (
                review_session.completed_at.isoformat()
                if review_session.completed_at
                else None
            ),
            "duration_seconds": review_session.duration_seconds,
            "estimated_input_tokens": (
                usage.estimated_input_tokens if usage else 0
            ),
            "estimated_output_tokens": (
                usage.estimated_output_tokens if usage else 0
            ),
            "cache_creation_input_tokens": (
                usage.cache_creation_input_tokens if usage else 0
            ),
            "cache_read_input_tokens": (
                usage.cache_read_input_tokens if usage else 0
            ),
            "total_tokens": (
                (usage.estimated_input_tokens + usage.estimated_output_tokens)
                if usage
                else 0
            ),
            "inline_comments": [
                {
                    "id": c.id,
                    "file_path": c.file_path,
                    "new_line": c.new_line,
                    "old_line": c.old_line,
                    "severity": c.severity,
                    "comment": c.comment,
                    "suggestion": c.suggestion,
                }
                for c in inline_comments
            ],
        }

    def _serialize_issue_summary(issue_session):
        """序列化 Issue 会话摘要。"""
        usage_stats = getattr(issue_session, "usage_stats", []) or []
        total_input_tokens = sum(s.estimated_input_tokens for s in usage_stats)
        total_output_tokens = sum(s.estimated_output_tokens for s in usage_stats)
        cache_creation_input_tokens = sum(
            s.cache_creation_input_tokens for s in usage_stats
        )
        cache_read_input_tokens = sum(s.cache_read_input_tokens for s in usage_stats)
        analysis_payload = issue_session.get_analysis_payload()

        return {
            "id": issue_session.id,
            "repository_id": issue_session.repository_id,
            "repo_full_name": (
                f"{issue_session.repository.owner}/{issue_session.repository.repo_name}"
                if issue_session.repository
                else None
            ),
            "issue_number": issue_session.issue_number,
            "issue_title": issue_session.issue_title,
            "issue_author": issue_session.issue_author,
            "issue_state": issue_session.issue_state,
            "trigger_type": issue_session.trigger_type,
            "engine": issue_session.engine,
            "model": issue_session.model,
            "config_source": issue_session.config_source,
            "overall_severity": issue_session.overall_severity,
            "overall_success": issue_session.overall_success,
            "error_message": issue_session.error_message,
            "related_issue_count": len(analysis_payload.get("related_issues", [])),
            "solution_count": len(analysis_payload.get("solution_suggestions", [])),
            "started_at": (
                issue_session.started_at.isoformat() if issue_session.started_at else None
            ),
            "completed_at": (
                issue_session.completed_at.isoformat()
                if issue_session.completed_at
                else None
            ),
            "duration_seconds": issue_session.duration_seconds,
            "estimated_input_tokens": total_input_tokens,
            "estimated_output_tokens": total_output_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
        }

    def _serialize_issue_detail(issue_session):
        """序列化 Issue 会话详情。"""
        summary = _serialize_issue_summary(issue_session)
        analysis_payload = issue_session.get_analysis_payload()
        summary.update(
            {
                "source_comment_id": issue_session.source_comment_id,
                "bot_comment_id": issue_session.bot_comment_id,
                "summary_markdown": issue_session.summary_markdown,
                "analysis_payload": analysis_payload,
                "related_issues": analysis_payload.get("related_issues", []),
                "solution_suggestions": analysis_payload.get(
                    "solution_suggestions", []
                ),
                "related_files": analysis_payload.get("related_files", []),
                "next_actions": analysis_payload.get("next_actions", []),
            }
        )
        return summary

    async def _resolve_accessible_repo_ids(db_service, user_repos):
        """解析当前用户可访问的仓库 ID 列表。

        Args:
            db_service: 数据库服务实例。
            user_repos: 当前用户可访问仓库列表。

        Returns:
            可访问仓库 ID 列表。
        """
        repo_ids: list[int] = []
        for repo_item in user_repos:
            owner = repo_item.get("owner", {}).get("username") or repo_item.get(
                "owner", {}
            ).get("login")
            name = repo_item.get("name")
            if not owner or not name:
                continue
            db_repo = await db_service.get_repository(owner, name)
            if db_repo:
                repo_ids.append(db_repo.id)
        return repo_ids

    async def _require_repo_setup_permission(owner: str, repo: str, request: Request):
        """校验当前用户是否具备仓库接入权限。

        Args:
            owner: 仓库所有者。
            repo: 仓库名称。
            request: 请求对象。

        Returns:
            可用于后续调用的 Gitea 客户端实例。
        """
        session_data = context.auth_manager.require_session(request)
        client = context.auth_manager.build_user_client(session_data)

        permissions = await client.check_repo_permissions(owner, repo)
        if permissions is None:
            raise HTTPException(status_code=502, detail="无法获取仓库权限信息")

        is_org = await client.is_organization(owner)
        org_role = None
        if is_org:
            username = session_data.user.get("username") if session_data.user else None
            if username:
                org_role = await client.get_org_membership_role(owner, username)
            if org_role not in {"owner", "admin"}:
                raise HTTPException(status_code=403, detail="需要组织管理员权限")
        elif not permissions.get("admin", False):
            raise HTTPException(status_code=403, detail="需要仓库管理员权限")

        return client

    @public_router.get("/health")
    async def health():
        """健康检查端点"""
        return {"status": "healthy"}

    @public_router.get("/version")
    async def version():
        """版本信息端点"""
        return {
            "version": __version__,
            "release_date": __release_date__,
            "info": get_version_info(),
            "changelog": get_changelog(),
        }

    @public_router.get("/changelog")
    async def changelog():
        """完整更新日志端点"""
        return {
            "version": __version__,
            "changelog": get_all_changelogs(),
        }

    @public_router.get("/changelog/json")
    async def changelog_json():
        """结构化更新日志端点，供前端时间线页面消费"""
        return {
            "version": __version__,
            "history": get_all_changelogs_json(),
        }

    @api_router.get("/config/public")
    async def public_config():
        """提供前端需要的只读配置"""
        return {
            "gitea_url": settings.gitea_url,
            "bot_username": runtime_settings.get("bot_username", settings.bot_username),
            "debug": settings.debug,
            "oauth_enabled": context.auth_manager.enabled,
        }

    @api_router.get("/providers")
    async def list_providers():
        """列出提供方列表。

        Args:
            无。

        Returns:
            可用审查引擎列表及默认引擎。
        """
        provider_labels = {
            "claude_code": "Claude Code",
            "codex_cli": "Codex CLI",
            "forge": "Forge",
        }
        providers = context.review_engine.registry.list_providers()
        return {
            "providers": [
                {
                    "name": p,
                    "label": provider_labels.get(p, p),
                }
                for p in providers
            ],
            "default": runtime_settings.get("default_provider", settings.default_provider),
        }

    @api_router.get("/config/claude-global")
    @api_router.get("/config/provider-global")
    async def get_global_claude_config(request: Request):
        """获取全局 Claude 配置"""
        context.auth_manager.require_session(request)
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            global_config = await db_service.get_global_model_config()

            if not global_config:
                return {
                    "configured": False,
                    "engine": runtime_settings.get("default_provider", settings.default_provider),
                    "model": None,
                    "api_url": None,
                    "has_api_key": False,
                }

            return {
                "configured": bool(global_config.api_url or global_config.api_key),
                "engine": global_config.engine or runtime_settings.get("default_provider", settings.default_provider),
                "model": global_config.model,
                "api_url": global_config.api_url,
                "has_api_key": bool(global_config.api_key),
            }

    @api_router.put("/config/claude-global")
    @api_router.put("/config/provider-global")
    async def update_global_claude_config(
        payload: ProviderConfigRequest,
        request: Request,
        admin: User = Depends(admin_required("config", "write")),
    ):
        """更新全局 Claude 配置"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            global_config = await db_service.get_global_model_config()
            if not global_config:
                global_config = await db_service.create_or_update_model_config(
                    config_name="global-default",
                    repository_id=None,
                    is_default=True,
                )

            if payload.api_url is not None:
                global_config.api_url = payload.api_url or None
            if payload.api_key is not None:
                global_config.api_key = payload.api_key or None
            if payload.engine is not None:
                global_config.engine = payload.engine
            if payload.model is not None:
                global_config.model = payload.model or None

            await session.flush()

            return {
                "success": True,
                "message": "全局 AI 审查配置已保存",
                "engine": global_config.engine,
                "model": global_config.model,
                "api_url": global_config.api_url,
                "has_api_key": bool(global_config.api_key),
            }

    @api_router.get("/version")
    async def api_version():
        """版本信息端点（API前缀）"""
        return {
            "version": __version__,
            "release_date": __release_date__,
            "info": get_version_info(),
            "changelog": get_changelog(),
        }

    @api_router.get("/auth/status")
    async def auth_status(request: Request):
        """返回当前会话状态"""
        return context.auth_manager.get_status_payload(request)

    @api_router.get("/auth/admin-status")
    async def auth_admin_status(request: Request):
        """返回当前登录用户的管理员状态。

        Args:
            request: 请求对象。

        Returns:
            管理员状态信息。
        """
        session = context.auth_manager.get_session(request)
        logged_in = bool(session)

        if not settings.admin_enabled:
            return {
                "enabled": False,
                "logged_in": logged_in,
                "is_admin": False,
                "role": None,
            }

        if not session:
            return {
                "enabled": True,
                "logged_in": False,
                "is_admin": False,
                "role": None,
            }

        database = context.database
        if not database:
            return {
                "enabled": True,
                "logged_in": True,
                "is_admin": False,
                "role": None,
            }

        username = session.user.get("username")
        if not username:
            return {
                "enabled": True,
                "logged_in": True,
                "is_admin": False,
                "role": None,
            }

        async with database.session() as db_session:
            stmt = select(User).where(
                User.username == username,
                User.role.in_(["admin", "super_admin"]),
                User.is_active.is_(True),
            )
            result = await db_session.execute(stmt)
            admin = result.scalar_one_or_none()

        return {
            "enabled": True,
            "logged_in": True,
            "is_admin": bool(admin),
            "role": admin.role if admin else None,
        }

    @api_router.get("/auth/login-url")
    async def auth_login_url():
        """生成OAuth授权地址"""
        if not context.auth_manager.enabled:
            raise HTTPException(status_code=404, detail="OAuth 未启用")
        return {"url": context.auth_manager.build_authorize_url()}

    @api_router.post("/auth/logout")
    async def auth_logout(request: Request, response: Response):
        """注销当前会话"""
        await context.auth_manager.logout_async(
            request, response, database=context.database
        )
        return {"success": True}

    @api_router.get("/auth/callback")
    async def auth_callback(code: str, state: str):
        """OAuth回调，设置登录会话后重定向到主页"""
        redirect = RedirectResponse(url="/", status_code=303)
        return await context.auth_manager.handle_callback(
            code, state, redirect, database=context.database
        )

    @api_router.get("/repos")
    async def list_repos(request: Request):
        """列出当前用户有权访问的所有仓库（包括只读权限）"""
        client = context.auth_manager.build_user_client(
            context.auth_manager.require_session(request)
        )
        repos = await client.list_user_repos()
        if repos is None:
            raise HTTPException(status_code=502, detail="无法从Gitea获取仓库列表")

        # 从数据库获取 is_active 状态
        database = context.database
        if database:
            from app.services.db_service import DBService

            async with database.session() as session:
                db_service = DBService(session)
                for repo in repos:
                    owner = repo.get("owner", {}).get("username") or repo.get(
                        "owner", {}
                    ).get("login")
                    name = repo.get("name")
                    if owner and name:
                        db_repo = await db_service.get_repository(owner, name)
                        repo["is_active"] = db_repo.is_active if db_repo else False

        return {"repos": repos}

    @api_router.get("/repos/{owner}/{repo}/permissions")
    async def check_repo_permissions(owner: str, repo: str, request: Request):
        """
        检查当前用户对仓库的权限

        返回权限信息，用于前端判断是否显示webhook设置等功能
        """
        client = context.auth_manager.build_user_client(
            context.auth_manager.require_session(request)
        )
        permissions = await client.check_repo_permissions(owner, repo)
        if permissions is None:
            raise HTTPException(status_code=502, detail="无法获取仓库权限信息")

        is_org = await client.is_organization(owner)
        org_role = None
        if is_org:
            session = context.auth_manager.require_session(request)
            username = session.user.get("username") if session else None
            if username:
                org_role = await client.get_org_membership_role(owner, username)

        can_setup = permissions.get("admin", False)
        if is_org:
            can_setup = can_setup and org_role in {"owner", "admin"}

        return {
            "owner": owner,
            "repo": repo,
            "permissions": permissions,
            "organization": {
                "is_org": is_org,
                "role": org_role,
            },
            "can_setup_webhook": can_setup,
        }

    @api_router.post("/repos/{owner}/{repo}/setup")
    async def setup_repo_review(
        owner: str, repo: str, payload: WebhookSetupRequest, request: Request
    ):
        """为指定仓库配置Webhook并可选邀请Bot账号"""
        client = await _require_repo_setup_permission(owner, repo, request)

        callback_url = payload.callback_url or str(request.url_for("webhook"))
        secret = await context.repo_registry.get_secret_async(owner, repo) or secrets.token_hex(20)
        await context.repo_registry.set_secret_async(owner, repo, secret)

        webhook_config = {
            "type": "gitea",
            "config": {
                "url": callback_url,
                "content_type": "json",
                "secret": secret,
            },
            "events": payload.events,
            "active": True,
        }

        hook_id = await client.ensure_repo_webhook(owner, repo, webhook_config)
        if hook_id is None:
            raise HTTPException(status_code=502, detail="创建或更新Webhook失败")

        bot_added = False
        if payload.bring_bot and runtime_settings.get("bot_username", settings.bot_username):
            bot_added = await client.add_collaborator(
                owner, repo, runtime_settings.get("bot_username", settings.bot_username)
            )

        return {
            "owner": owner,
            "repo": repo,
            "webhook_id": hook_id,
            "webhook_url": callback_url,
            "bot_invited": bot_added,
            "events": payload.events,
        }

    @api_router.get("/repos/{owner}/{repo}/webhook-status")
    async def get_webhook_status(owner: str, repo: str, request: Request):
        """获取仓库的 Webhook 配置状态"""
        client = context.auth_manager.build_user_client(
            context.auth_manager.require_session(request)
        )

        permissions = await client.check_repo_permissions(owner, repo)
        if permissions is None:
            raise HTTPException(status_code=502, detail="无法获取仓库权限信息")

        is_org = await client.is_organization(owner)
        org_role = None
        if is_org:
            session = context.auth_manager.require_session(request)
            username = session.user.get("username") if session else None
            if username:
                org_role = await client.get_org_membership_role(owner, username)

        can_setup = permissions.get("admin", False)
        if is_org:
            can_setup = can_setup and org_role in {"owner", "admin"}

        # 获取当前服务的回调 URL
        try:
            callback_url = str(request.url_for("webhook"))
        except Exception:
            callback_url = None

        hooks = await client.list_repo_hooks(owner, repo)
        if hooks is None:
            raise HTTPException(status_code=502, detail="无法获取仓库Webhook列表")

        # 查找匹配当前服务的 webhook
        matched_hook = None
        for hook in hooks:
            hook_url = hook.get("config", {}).get("url", "")
            # 检查是否匹配当前服务的回调 URL
            if callback_url and hook_url == callback_url:
                matched_hook = hook
                break
            # 也检查是否包含 pr-reviewer 相关的 URL（兼容不同部署）
            if "webhook" in hook_url or "pr-review" in hook_url.lower():
                matched_hook = hook

        if matched_hook:
            return {
                "configured": True,
                "active": matched_hook.get("active", False),
                "webhook_id": matched_hook.get("id"),
                "events": matched_hook.get("events", []),
                "url": matched_hook.get("config", {}).get("url", ""),
                "created_at": matched_hook.get("created_at"),
                "updated_at": matched_hook.get("updated_at"),
                "can_setup_webhook": can_setup,
            }
        else:
            return {
                "configured": False,
                "active": False,
                "webhook_id": None,
                "events": [],
                "url": None,
                "can_setup_webhook": can_setup,
            }

    @api_router.delete("/repos/{owner}/{repo}/webhook")
    async def delete_webhook(owner: str, repo: str, request: Request):
        """删除仓库的 Webhook"""
        client = context.auth_manager.build_user_client(
            context.auth_manager.require_session(request)
        )

        permissions = await client.check_repo_permissions(owner, repo)
        if permissions is None:
            raise HTTPException(status_code=502, detail="无法获取仓库权限信息")

        is_org = await client.is_organization(owner)
        org_role = None
        if is_org:
            session = context.auth_manager.require_session(request)
            username = session.user.get("username") if session else None
            if username:
                org_role = await client.get_org_membership_role(owner, username)
            if org_role not in {"owner", "admin"}:
                raise HTTPException(status_code=403, detail="需要组织管理员权限")
        elif not permissions.get("admin", False):
            raise HTTPException(status_code=403, detail="需要仓库管理员权限")

        # 先获取 webhook 状态
        try:
            callback_url = str(request.url_for("webhook"))
        except Exception:
            callback_url = None

        hooks = await client.list_repo_hooks(owner, repo)
        if hooks is None:
            raise HTTPException(status_code=502, detail="无法获取仓库Webhook列表")

        # 查找并删除匹配的 webhook
        deleted = False
        for hook in hooks:
            hook_url = hook.get("config", {}).get("url", "")
            if (callback_url and hook_url == callback_url) or "webhook" in hook_url:
                hook_id = hook.get("id")
                if hook_id:
                    success = await client.delete_repo_hook(owner, repo, hook_id)
                    if success:
                        deleted = True
                        context.repo_registry.delete_secret(owner, repo)
                        break

        if deleted:
            return {"success": True, "message": "Webhook 已删除"}
        else:
            raise HTTPException(status_code=404, detail="未找到匹配的Webhook")

    @api_router.post("/repos/{owner}/{repo}/validate-admin")
    async def validate_repo_admin(owner: str, repo: str, request: Request):
        """校验仓库配置权限（组织仓库需管理员）"""
        client = context.auth_manager.build_user_client(
            context.auth_manager.require_session(request)
        )

        permissions = await client.check_repo_permissions(owner, repo)
        if permissions is None:
            raise HTTPException(status_code=502, detail="无法获取仓库权限信息")

        is_org = await client.is_organization(owner)
        org_role = None
        if is_org:
            session = context.auth_manager.require_session(request)
            username = session.user.get("username") if session else None
            if username:
                org_role = await client.get_org_membership_role(owner, username)

        can_setup = permissions.get("admin", False)
        if is_org:
            can_setup = can_setup and org_role in {"owner", "admin"}

        return {
            "owner": owner,
            "repo": repo,
            "permissions": permissions,
            "organization": {
                "is_org": is_org,
                "role": org_role,
            },
            "can_setup_webhook": can_setup,
        }

    # ==================== 审查历史 API ====================

    @api_router.get("/reviews")
    async def list_reviews(
        request: Request,
        owner: Optional[str] = Query(None, description="仓库所有者"),
        repo: Optional[str] = Query(None, description="仓库名称"),
        success: Optional[bool] = Query(None, description="是否成功"),
        limit: int = Query(50, ge=1, le=200, description="返回数量"),
        offset: int = Query(0, ge=0, description="偏移量"),
        admin: User = Depends(admin_required()),
    ):
        """获取审查历史列表"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            sessions = await db_service.list_review_sessions(
                owner=owner,
                repo_name=repo,
                success=success,
                limit=limit,
                offset=offset,
            )

            return {
                "reviews": [_serialize_review_summary(s) for s in sessions],
                "total": len(sessions),
                "limit": limit,
                "offset": offset,
            }

    @api_router.get("/reviews/{review_id}")
    async def get_review(
        review_id: int,
        request: Request,
        admin: User = Depends(admin_required()),
    ):
        """获取审查详情"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            review_session = await db_service.get_review_session(review_id)

            if not review_session:
                raise HTTPException(status_code=404, detail="审查记录不存在")

            inline_comments = await db_service.get_inline_comments(review_id)
            return _serialize_review_detail(review_session, inline_comments)

    @api_router.get("/my/reviews")
    async def list_my_reviews(
        request: Request,
        success: Optional[bool] = Query(None, description="是否成功"),
        limit: int = Query(50, ge=1, le=200, description="返回数量"),
        offset: int = Query(0, ge=0, description="偏移量"),
    ):
        """获取当前用户有权限仓库的审查历史"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        session_data = context.auth_manager.require_session(request)
        client = context.auth_manager.build_user_client(session_data)
        user_repos = await client.list_user_repos()
        if user_repos is None:
            raise HTTPException(status_code=502, detail="无法从Gitea获取用户仓库列表")

        async with database.session() as db_session:
            db_service = DBService(db_session)
            repo_ids = await _resolve_accessible_repo_ids(db_service, user_repos)
            if not repo_ids:
                return {"reviews": [], "total": 0, "limit": limit, "offset": offset}

            sessions = await db_service.list_review_sessions_by_repo_ids(
                repository_ids=repo_ids,
                success=success,
                limit=limit,
                offset=offset,
            )

            return {
                "reviews": [_serialize_review_summary(s) for s in sessions],
                "total": len(sessions),
                "limit": limit,
                "offset": offset,
            }

    @api_router.get("/my/reviews/{review_id}")
    async def get_my_review(review_id: int, request: Request):
        """获取当前用户可见仓库的单条审查详情"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        session_data = context.auth_manager.require_session(request)
        client = context.auth_manager.build_user_client(session_data)
        user_repos = await client.list_user_repos()
        if user_repos is None:
            raise HTTPException(status_code=502, detail="无法从Gitea获取用户仓库列表")

        async with database.session() as db_session:
            db_service = DBService(db_session)
            repo_ids = await _resolve_accessible_repo_ids(db_service, user_repos)
            if not repo_ids:
                raise HTTPException(status_code=404, detail="审查记录不存在")

            review_session = await db_service.get_review_session(review_id)
            if not review_session or review_session.repository_id not in repo_ids:
                raise HTTPException(status_code=404, detail="审查记录不存在")

            inline_comments = await db_service.get_inline_comments(review_id)
            return _serialize_review_detail(review_session, inline_comments)

    @api_router.get("/issues")
    async def list_issues(
        request: Request,
        owner: Optional[str] = Query(None, description="仓库所有者"),
        repo: Optional[str] = Query(None, description="仓库名称"),
        success: Optional[bool] = Query(None, description="是否成功"),
        limit: int = Query(50, ge=1, le=200, description="返回数量"),
        offset: int = Query(0, ge=0, description="偏移量"),
        admin: User = Depends(admin_required()),
    ):
        """获取 Issue 分析历史列表。"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            sessions = await db_service.list_issue_sessions(
                owner=owner,
                repo_name=repo,
                success=success,
                limit=limit,
                offset=offset,
            )
            return {
                "issues": [_serialize_issue_summary(s) for s in sessions],
                "total": len(sessions),
                "limit": limit,
                "offset": offset,
            }

    @api_router.get("/issues/{issue_id}")
    async def get_issue(
        issue_id: int,
        request: Request,
        admin: User = Depends(admin_required()),
    ):
        """获取单条 Issue 分析详情。"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            issue_session = await db_service.get_issue_session(issue_id)
            if not issue_session:
                raise HTTPException(status_code=404, detail="Issue 记录不存在")
            return _serialize_issue_detail(issue_session)

    @api_router.get("/my/issues")
    async def list_my_issues(
        request: Request,
        success: Optional[bool] = Query(None, description="是否成功"),
        limit: int = Query(50, ge=1, le=200, description="返回数量"),
        offset: int = Query(0, ge=0, description="偏移量"),
    ):
        """获取当前用户可访问仓库的 Issue 分析历史。"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        session_data = context.auth_manager.require_session(request)
        client = context.auth_manager.build_user_client(session_data)
        user_repos = await client.list_user_repos()
        if user_repos is None:
            raise HTTPException(status_code=502, detail="无法从Gitea获取用户仓库列表")

        async with database.session() as db_session:
            db_service = DBService(db_session)
            repo_ids = await _resolve_accessible_repo_ids(db_service, user_repos)
            if not repo_ids:
                return {"issues": [], "total": 0, "limit": limit, "offset": offset}

            sessions = await db_service.list_issue_sessions_by_repo_ids(
                repository_ids=repo_ids,
                success=success,
                limit=limit,
                offset=offset,
            )
            return {
                "issues": [_serialize_issue_summary(s) for s in sessions],
                "total": len(sessions),
                "limit": limit,
                "offset": offset,
            }

    @api_router.get("/my/issues/{issue_id}")
    async def get_my_issue(issue_id: int, request: Request):
        """获取当前用户可见仓库的单条 Issue 分析详情。"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        session_data = context.auth_manager.require_session(request)
        client = context.auth_manager.build_user_client(session_data)
        user_repos = await client.list_user_repos()
        if user_repos is None:
            raise HTTPException(status_code=502, detail="无法从Gitea获取用户仓库列表")

        async with database.session() as db_session:
            db_service = DBService(db_session)
            repo_ids = await _resolve_accessible_repo_ids(db_service, user_repos)
            if not repo_ids:
                raise HTTPException(status_code=404, detail="Issue 记录不存在")

            issue_session = await db_service.get_issue_session(issue_id)
            if not issue_session or issue_session.repository_id not in repo_ids:
                raise HTTPException(status_code=404, detail="Issue 记录不存在")

            return _serialize_issue_detail(issue_session)

    # ==================== 使用量统计 API ====================

    @api_router.get("/stats")
    async def get_stats(
        request: Request,
        repository_id: Optional[int] = Query(None, description="仓库ID"),
        start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
        end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    ):
        """获取使用量统计"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        # 解析日期
        start = None
        end = None
        if start_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的开始日期格式")
        if end_date:
            try:
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的结束日期格式")

        if start and end and start > end:
            raise HTTPException(status_code=400, detail="start_date 不能晚于 end_date")

        session_data = context.auth_manager.require_session(request)
        username = (
            session_data.user.get("username")
            if isinstance(session_data.user, dict)
            else None
        )

        async with database.session() as session:
            db_service = DBService(session)
            usage_user_id: Optional[int] = None
            if username:
                usage_user = await db_service.get_or_create_user_by_username(username)
                usage_user_id = usage_user.id

            if repository_id is not None:
                db_repo = await db_service.get_repository_by_id(repository_id)
                if not db_repo:
                    raise HTTPException(status_code=404, detail="仓库不存在")
                client = context.auth_manager.build_user_client(session_data)
                perms = await client.check_repo_permissions(db_repo.owner, db_repo.repo_name)
                if not perms or not perms.get("pull", False):
                    raise HTTPException(status_code=403, detail="无权访问该仓库统计")

            # 获取汇总
            summary = await db_service.get_usage_summary(
                repository_id=repository_id,
                user_id=usage_user_id,
                start_date=start,
                end_date=end,
            )

            # 获取详细记录
            stats = await db_service.get_usage_stats(
                repository_id=repository_id,
                user_id=usage_user_id,
                start_date=start,
                end_date=end,
            )

            return {
                "summary": summary,
                "details": [
                    {
                        "id": s.id,
                        "repository_id": s.repository_id,
                        "review_session_id": s.review_session_id,
                        "issue_session_id": s.issue_session_id,
                        "date": s.stat_date.isoformat() if s.stat_date else None,
                        "estimated_input_tokens": s.estimated_input_tokens,
                        "estimated_output_tokens": s.estimated_output_tokens,
                        "cache_creation_input_tokens": s.cache_creation_input_tokens,
                        "cache_read_input_tokens": s.cache_read_input_tokens,
                        "gitea_api_calls": s.gitea_api_calls,
                        "provider_api_calls": s.provider_api_calls,
                        "claude_api_calls": s.provider_api_calls,
                        "clone_operations": s.clone_operations,
                    }
                    for s in stats
                ],
            }

    # ==================== 模型配置 API ====================

    @api_router.get("/configs")
    async def list_configs(
        request: Request,
        admin: User = Depends(admin_required()),
    ):
        """获取所有模型配置"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            configs = await db_service.list_model_configs()

            return {
                "configs": [
                    {
                        "id": c.id,
                        "repository_id": c.repository_id,
                        "config_name": c.config_name,
                        "engine": c.engine,
                        "model": c.model,
                        "max_tokens": c.max_tokens,
                        "temperature": c.temperature,
                        "custom_prompt": c.custom_prompt,
                        "default_features": c.get_features(),
                        "default_focus": c.get_focus(),
                        "is_default": c.is_default,
                    }
                    for c in configs
                ],
            }

    @api_router.post("/configs")
    async def create_or_update_config(
        payload: ModelConfigRequest,
        request: Request,
        admin: User = Depends(admin_required()),
    ):
        """创建或更新模型配置"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            config = await db_service.create_or_update_model_config(
                config_name=payload.config_name,
                repository_id=payload.repository_id,
                engine=payload.engine,
                max_tokens=payload.max_tokens,
                temperature=payload.temperature,
                custom_prompt=payload.custom_prompt,
                default_features=payload.default_features,
                default_focus=payload.default_focus,
                is_default=payload.is_default,
            )

            if payload.model is not None:
                config.model = payload.model or None
                await session.flush()

            return {
                "id": config.id,
                "repository_id": config.repository_id,
                "config_name": config.config_name,
                "engine": config.engine,
                "model": config.model,
                "is_default": config.is_default,
                "message": "配置已保存",
            }

    # ==================== 仓库管理 API ====================

    @api_router.get("/repos/{owner}/{repo}/pulls")
    async def get_repo_pulls(
        owner: str,
        repo: str,
        request: Request,
        state: str = "all",
        limit: int = 5,
    ):
        """获取仓库最新PR"""
        session_data = context.auth_manager.require_session(request)
        client = context.auth_manager.build_user_client(session_data)
        pulls = await client.list_pull_requests(owner, repo, state=state, limit=limit)

        if pulls is None:
            raise HTTPException(status_code=404, detail="无法获取PR信息")

        return {"pulls": pulls}

    @api_router.get("/repos/{owner}/{repo}/claude-config")
    @api_router.get("/repos/{owner}/{repo}/provider-config")
    async def get_repo_claude_config(owner: str, repo: str, request: Request):
        """获取仓库的 Claude 配置"""
        context.auth_manager.require_session(request)
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            repo_obj = await db_service.get_repository(owner, repo)
            global_config = await db_service.get_global_model_config()
            default_engine = runtime_settings.get(
                "default_provider", settings.default_provider
            )

            if not repo_obj:
                resolved = resolve_provider_config(
                    None,
                    global_config,
                    default_engine=default_engine,
                )
                return {
                    "inherit_global": resolved.inherit_global,
                    "has_global_config": bool(
                        global_config
                        and (global_config.api_url or global_config.api_key)
                    ),
                    "configured": bool(
                        resolved.api_url or resolved.api_key or resolved.model
                    ),
                    "engine": resolved.engine,
                    "model": resolved.model,
                    "api_url": resolved.api_url,
                    "has_api_key": bool(resolved.api_key),
                    "global_api_url": (
                        global_config.api_url if global_config else None
                    ),
                    "global_has_api_key": bool(
                        global_config.api_key if global_config else False
                    ),
                    "global_engine": (
                        global_config.engine
                        if global_config
                        else default_engine
                    ),
                    "global_model": (global_config.model if global_config else None),
                }

            repo_config = await db_service.get_repo_specific_model_config(repo_obj.id)
            resolved = resolve_provider_config(
                repo_config,
                global_config,
                default_engine=default_engine,
            )

            return {
                "inherit_global": resolved.inherit_global,
                "has_global_config": bool(
                    global_config and (global_config.api_url or global_config.api_key)
                ),
                "configured": bool(resolved.api_url or resolved.api_key or resolved.model),
                "engine": resolved.engine,
                "model": resolved.model,
                "api_url": resolved.api_url,
                "has_api_key": bool(resolved.api_key),
                "global_api_url": (global_config.api_url if global_config else None),
                "global_has_api_key": bool(
                    global_config.api_key if global_config else False
                ),
                "global_engine": (
                    global_config.engine if global_config else default_engine
                ),
                "global_model": (global_config.model if global_config else None),
            }

    @api_router.put("/repos/{owner}/{repo}/claude-config")
    @api_router.put("/repos/{owner}/{repo}/provider-config")
    async def update_repo_claude_config(
        owner: str, repo: str, payload: ProviderConfigRequest, request: Request
    ):
        """保存仓库的 Claude 配置"""
        await _require_repo_setup_permission(owner, repo, request)
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)

            if payload.inherit_global:
                repo_obj = await db_service.get_repository(owner, repo)
                if repo_obj:
                    repo_config = await db_service.get_repo_specific_model_config(repo_obj.id)
                    if repo_config:
                        clear_provider_overrides(repo_config)
                        if not has_non_provider_settings(repo_config):
                            await db_service.delete_repo_model_config(repo_obj.id)

                global_config = await db_service.get_global_model_config()
                await session.flush()
                return {
                    "success": True,
                    "inherit_global": True,
                    "message": "已切换为继承全局 Claude 配置",
                    "api_url": (global_config.api_url if global_config else None),
                    "engine": (
                        global_config.engine
                        if global_config
                        else runtime_settings.get("default_provider", settings.default_provider)
                    ),
                    "model": (global_config.model if global_config else None),
                    "has_api_key": bool(
                        global_config.api_key if global_config else False
                    ),
                }

            # 获取或创建仓库
            repo_obj = await db_service.get_or_create_repository(owner, repo)

            # 获取或创建模型配置
            model_config = await db_service.get_model_config(repo_obj.id)
            if not model_config:
                # 创建新的配置
                model_config = await db_service.create_or_update_model_config(
                    config_name=f"{owner}/{repo}",
                    repository_id=repo_obj.id,
                )

            # 更新 Provider 配置
            if payload.api_url is not None:
                model_config.api_url = payload.api_url or None
            if payload.api_key is not None:
                model_config.api_key = payload.api_key or None
            if payload.engine is not None:
                model_config.engine = payload.engine
            if payload.model is not None:
                model_config.model = payload.model or None

            await session.flush()

            return {
                "success": True,
                "inherit_global": False,
                "message": "AI 审查配置已保存",
                "engine": model_config.engine,
                "model": model_config.model,
                "api_url": model_config.api_url,
                "has_api_key": bool(model_config.api_key),
            }

    @api_router.get("/repos/{owner}/{repo}/review-settings")
    async def get_review_settings(owner: str, repo: str, request: Request):
        """获取仓库的审查设置（focus + features）"""
        context.auth_manager.require_session(request)
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            repo_obj = await db_service.get_repository(owner, repo)
            if not repo_obj:
                return {
                    "default_focus": ["quality", "security", "performance", "logic"],
                    "default_features": ["comment"],
                }

            config = await db_service.get_model_config(repo_obj.id)
            return {
                "default_focus": (
                    config.get_focus()
                    if config
                    else ["quality", "security", "performance", "logic"]
                ),
                "default_features": (config.get_features() if config else ["comment"]),
            }

    @api_router.put("/repos/{owner}/{repo}/review-settings")
    async def update_review_settings(
        owner: str, repo: str, payload: ReviewSettingsRequest, request: Request
    ):
        """更新仓库的审查设置"""
        await _require_repo_setup_permission(owner, repo, request)
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            repo_obj = await db_service.get_or_create_repository(owner, repo)

            config = await db_service.get_repo_specific_model_config(repo_obj.id)
            if not config:
                config = await db_service.create_or_update_model_config(
                    config_name=f"{owner}/{repo}",
                    repository_id=repo_obj.id,
                )

            if payload.default_focus is not None:
                config.set_focus(payload.default_focus)
            if payload.default_features is not None:
                config.set_features(payload.default_features)

            await session.flush()

            return {
                "default_focus": config.get_focus(),
                "default_features": config.get_features(),
            }

    @api_router.get("/repos/{owner}/{repo}/issue-settings")
    async def get_issue_settings(owner: str, repo: str, request: Request):
        """获取仓库的 Issue 分析设置。"""
        context.auth_manager.require_session(request)
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            repo_obj = await db_service.get_repository(owner, repo)
            if not repo_obj:
                return {
                    "issue_enabled": True,
                    "auto_on_open": True,
                    "manual_command_enabled": True,
                }

            return {
                "issue_enabled": repo_obj.issue_enabled,
                "auto_on_open": repo_obj.issue_auto_on_open,
                "manual_command_enabled": repo_obj.issue_manual_command_enabled,
            }

    @api_router.put("/repos/{owner}/{repo}/issue-settings")
    async def update_issue_settings(
        owner: str, repo: str, payload: IssueSettingsRequest, request: Request
    ):
        """更新仓库的 Issue 分析设置。"""
        await _require_repo_setup_permission(owner, repo, request)
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            repo_obj = await db_service.update_issue_settings(
                owner,
                repo,
                issue_enabled=payload.issue_enabled,
                issue_auto_on_open=payload.auto_on_open,
                issue_manual_command_enabled=payload.manual_command_enabled,
            )

            return {
                "issue_enabled": repo_obj.issue_enabled,
                "auto_on_open": repo_obj.issue_auto_on_open,
                "manual_command_enabled": repo_obj.issue_manual_command_enabled,
            }

    @api_router.get("/repos/{owner}/{repo}/webhook-secret")
    async def get_webhook_secret(owner: str, repo: str, request: Request):
        """获取仓库的 Webhook Secret"""
        await _require_repo_setup_permission(owner, repo, request)
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            repo_obj = await db_service.get_repository(owner, repo)

            if not repo_obj:
                return {
                    "has_secret": False,
                }

            return {
                "has_secret": bool(repo_obj.webhook_secret),
            }

    @api_router.post("/repos/{owner}/{repo}/webhook-secret/regenerate")
    async def regenerate_webhook_secret(owner: str, repo: str, request: Request):
        """重新生成仓库的 Webhook Secret"""
        await _require_repo_setup_permission(owner, repo, request)
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        new_secret = secrets.token_hex(20)

        async with database.session() as session:
            db_service = DBService(session)
            await db_service.update_repository_secret(owner, repo, new_secret)

        # 同时更新 repo_registry 缓存
        context.repo_registry.set_secret(owner, repo, new_secret)

        return {
            "success": True,
            "webhook_secret": new_secret,
            "message": "Webhook Secret 已重新生成，请同步更新 Gitea 中的配置",
        }

    @api_router.get("/repositories")
    async def list_repositories(
        request: Request,
        admin: User = Depends(admin_required()),
    ):
        """获取所有已配置的仓库"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            repos = await db_service.list_repositories()

            return {
                "repositories": [
                    {
                        "id": r.id,
                        "owner": r.owner,
                        "repo_name": r.repo_name,
                        "full_name": r.full_name,
                        "is_active": r.is_active,
                        "has_webhook_secret": bool(r.webhook_secret),
                        "created_at": r.created_at.isoformat()
                        if r.created_at
                        else None,
                        "updated_at": r.updated_at.isoformat()
                        if r.updated_at
                        else None,
                    }
                    for r in repos
                ],
            }

    @public_router.post("/webhook")
    async def webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        x_gitea_signature: Optional[str] = Header(None),
        x_gitea_event: Optional[str] = Header(None),
        x_review_features: Optional[str] = Header(None),
        x_review_focus: Optional[str] = Header(None),
    ):
        """
        Gitea Webhook端点

        Headers:
            X-Gitea-Signature: Webhook签名
            X-Gitea-Event: 事件类型
            X-Review-Features: 审查功能（comment,review,status）
            X-Review-Focus: 审查重点（quality,security,performance,logic）
        """
        try:
            # 读取请求体
            body = await request.body()

            # 解析JSON以确定仓库信息，从而选择对应的密钥
            payload = await request.json()
            repo_info = (
                payload.get("repository", {}) if isinstance(payload, dict) else {}
            )
            owner_info = (
                repo_info.get("owner", {}) if isinstance(repo_info, dict) else {}
            )
            owner_name = owner_info.get("username") or owner_info.get("login")
            repo_name = repo_info.get("name")
            repo_secret = (
                await context.repo_registry.get_secret_async(owner_name, repo_name)
                if owner_name and repo_name
                else None
            )

            # 验证签名
            secret_for_validation = repo_secret or settings.webhook_secret
            if secret_for_validation:
                # 配置了 secret，必须验证签名
                if not x_gitea_signature or not verify_webhook_signature(
                    body, x_gitea_signature, secret_for_validation
                ):
                    logger.warning("Webhook签名验证失败")
                    raise HTTPException(status_code=401, detail="Invalid signature")
            elif x_gitea_signature:
                # 未配置 secret 但携带了签名，同样拒绝（避免半配置状态被利用）
                logger.warning("收到带签名的 Webhook，但未配置 WEBHOOK_SECRET")
                raise HTTPException(status_code=401, detail="Invalid signature")

            # Debug日志：仅输出事件元数据，避免泄露敏感字段
            if settings.debug:
                logger.debug(
                    "Webhook metadata: event=%s repo=%s/%s action=%s",
                    x_gitea_event,
                    owner_name,
                    repo_name,
                    payload.get("action") if isinstance(payload, dict) else None,
                )

            # 处理Pull Request事件
            if x_gitea_event == "pull_request":
                features = (
                    context.webhook_handler.parse_review_features(x_review_features)
                    if x_review_features
                    else None
                )
                focus_areas = (
                    context.webhook_handler.parse_review_focus(x_review_focus)
                    if x_review_focus
                    else None
                )

                logger.info(f"收到PR webhook，功能: {features}, 重点: {focus_areas}")

                # 添加后台任务
                background_tasks.add_task(
                    context.webhook_handler.process_webhook_async,
                    payload,
                    features,
                    focus_areas,
                )

                # 立即返回202
                return JSONResponse(
                    status_code=202,
                    content={
                        "message": "Webhook received, processing in background",
                        "features": features,
                        "focus_areas": focus_areas,
                    },
                )

            if x_gitea_event == "issues":
                logger.info("收到 issues webhook")
                background_tasks.add_task(
                    context.webhook_handler.process_issue_async,
                    payload,
                )
                return JSONResponse(
                    status_code=202,
                    content={
                        "message": "Issue webhook received, processing in background",
                    },
                )

            # 处理 Issue 评论事件（用于手动触发）
            if x_gitea_event == "issue_comment":
                logger.info("收到issue_comment webhook")

                # 添加后台任务
                background_tasks.add_task(
                    context.webhook_handler.process_comment_async,
                    payload,
                )

                # 立即返回202
                return JSONResponse(
                    status_code=202,
                    content={
                        "message": "Comment webhook received, processing in background",
                    },
                )

            # 其他事件类型
            logger.info(f"忽略事件: {x_gitea_event}")
            return JSONResponse(
                status_code=200,
                content={"message": "Event ignored"},
            )

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"处理webhook异常: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail="内部错误，请查看服务端日志")

    return api_router, public_router
