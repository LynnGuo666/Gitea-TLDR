"""
HTTP route definitions for the FastAPI application.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
import secrets
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import (
    APIRouter,
    Request,
    Header,
    HTTPException,
    BackgroundTasks,
    Response,
    Query,
)
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from app.core import (
    settings,
    __version__,
    get_version_info,
    get_changelog,
    get_all_changelogs,
)
from app.core.context import AppContext

logger = logging.getLogger(__name__)


class WebhookSetupRequest(BaseModel):
    """前端用于配置Webhook的请求体"""

    callback_url: Optional[str] = Field(
        default=None, description="可选覆盖webhook回调URL"
    )
    events: list[str] = Field(
        default_factory=lambda: ["pull_request", "issue_comment"],
        description="需要监听的事件列表",
    )
    bring_bot: bool = Field(default=True, description="是否自动邀请bot账号协作")


class ModelConfigRequest(BaseModel):
    """模型配置请求体"""

    config_name: str = Field(..., description="配置名称")
    repository_id: Optional[int] = Field(
        None, description="关联仓库ID（为空则为全局配置）"
    )
    model_name: str = Field("claude", description="模型名称")
    max_tokens: Optional[int] = Field(None, description="最大token数")
    temperature: Optional[float] = Field(None, description="温度参数")
    custom_prompt: Optional[str] = Field(None, description="自定义prompt模板")
    default_features: Optional[List[str]] = Field(None, description="默认功能列表")
    default_focus: Optional[List[str]] = Field(None, description="默认审查重点")
    is_default: bool = Field(False, description="是否为默认配置")


class ClaudeConfigRequest(BaseModel):
    """Claude 配置请求体"""

    anthropic_base_url: Optional[str] = Field(
        None, description="Anthropic API Base URL"
    )
    anthropic_auth_token: Optional[str] = Field(
        None, description="Anthropic Auth Token"
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
        return True  # 如果没有配置密钥，跳过验证

    expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


def create_api_router(context: AppContext) -> tuple[APIRouter, APIRouter]:
    """创建API与公开端点的路由集合。"""

    api_router = APIRouter()
    public_router = APIRouter()

    @public_router.get("/health")
    async def health():
        """健康检查端点"""
        return {"status": "healthy"}

    @public_router.get("/version")
    async def version():
        """版本信息端点"""
        return {
            "version": __version__,
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

    @api_router.get("/config/public")
    async def public_config():
        """提供前端需要的只读配置"""
        return {
            "gitea_url": settings.gitea_url,
            "bot_username": settings.bot_username,
            "debug": settings.debug,
            "oauth_enabled": context.auth_manager.enabled,
        }

    @api_router.get("/auth/status")
    async def auth_status(request: Request):
        """返回当前会话状态"""
        return context.auth_manager.get_status_payload(request)

    @api_router.get("/auth/login-url")
    async def auth_login_url():
        """生成OAuth授权地址"""
        if not context.auth_manager.enabled:
            raise HTTPException(status_code=404, detail="OAuth 未启用")
        return {"url": context.auth_manager.build_authorize_url()}

    @api_router.post("/auth/logout")
    async def auth_logout(request: Request, response: Response):
        """注销当前会话"""
        context.auth_manager.logout(request, response)
        return {"success": True}

    @api_router.get("/auth/callback")
    async def auth_callback(code: str, state: str):
        """OAuth回调，设置登录会话后重定向到主页"""
        redirect = RedirectResponse(url="/", status_code=303)
        return await context.auth_manager.handle_callback(code, state, redirect)

    @api_router.get("/repos")
    async def list_repos(request: Request):
        """列出当前用户有管理员权限的仓库（只有admin权限才能配置webhook）"""
        client = (
            context.auth_manager.build_user_client(
                context.auth_manager.require_session(request)
            )
            if context.auth_manager.enabled
            else context.gitea_client
        )
        repos = await client.list_user_repos()
        if repos is None:
            raise HTTPException(status_code=502, detail="无法从Gitea获取仓库列表")
        # 只返回有admin权限的仓库，因为只有admin才能配置webhook
        admin_repos = [
            repo for repo in repos if repo.get("permissions", {}).get("admin", False)
        ]

        # 从数据库获取 is_active 状态
        database = context.database
        if database:
            from app.services.db_service import DBService

            async with database.session() as session:
                db_service = DBService(session)
                for repo in admin_repos:
                    owner = repo.get("owner", {}).get("username") or repo.get(
                        "owner", {}
                    ).get("login")
                    name = repo.get("name")
                    if owner and name:
                        db_repo = await db_service.get_repository(owner, name)
                        repo["is_active"] = db_repo.is_active if db_repo else True

        return {"repos": admin_repos}

    @api_router.get("/repos/{owner}/{repo}/permissions")
    async def check_repo_permissions(owner: str, repo: str, request: Request):
        """
        检查当前用户对仓库的权限

        返回权限信息，用于前端判断是否显示webhook设置等功能
        """
        client = (
            context.auth_manager.build_user_client(
                context.auth_manager.require_session(request)
            )
            if context.auth_manager.enabled
            else context.gitea_client
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
        client = (
            context.auth_manager.build_user_client(
                context.auth_manager.require_session(request)
            )
            if context.auth_manager.enabled
            else context.gitea_client
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

        callback_url = payload.callback_url or str(request.url_for("webhook"))
        secret = context.repo_registry.get_secret(owner, repo) or secrets.token_hex(20)
        context.repo_registry.set_secret(owner, repo, secret)

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
        if payload.bring_bot and settings.bot_username:
            bot_added = await client.add_collaborator(
                owner, repo, settings.bot_username
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
        client = (
            context.auth_manager.build_user_client(
                context.auth_manager.require_session(request)
            )
            if context.auth_manager.enabled
            else context.gitea_client
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
        client = (
            context.auth_manager.build_user_client(
                context.auth_manager.require_session(request)
            )
            if context.auth_manager.enabled
            else context.gitea_client
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
                    # 调用 Gitea API 删除 webhook
                    delete_url = (
                        f"{client.base_url}/api/v1/repos/{owner}/{repo}/hooks/{hook_id}"
                    )
                    try:
                        import httpx

                        async with httpx.AsyncClient() as http_client:
                            response = await http_client.delete(
                                delete_url, headers=client.headers
                            )
                            if response.status_code in (200, 204):
                                deleted = True
                                # 同时清除本地保存的 secret
                                context.repo_registry.delete_secret(owner, repo)
                                break
                    except Exception as e:
                        logger.error(f"删除webhook失败: {e}")

        if deleted:
            return {"success": True, "message": "Webhook 已删除"}
        else:
            raise HTTPException(status_code=404, detail="未找到匹配的Webhook")

    @api_router.post("/repos/{owner}/{repo}/validate-admin")
    async def validate_repo_admin(owner: str, repo: str, request: Request):
        """校验仓库配置权限（组织仓库需管理员）"""
        client = (
            context.auth_manager.build_user_client(
                context.auth_manager.require_session(request)
            )
            if context.auth_manager.enabled
            else context.gitea_client
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
        limit: int = Query(50, ge=1, le=200, description="返回数量"),
        offset: int = Query(0, ge=0, description="偏移量"),
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
                limit=limit,
                offset=offset,
            )

            return {
                "reviews": [
                    {
                        "id": s.id,
                        "repository_id": s.repository_id,
                        "pr_number": s.pr_number,
                        "pr_title": s.pr_title,
                        "pr_author": s.pr_author,
                        "trigger_type": s.trigger_type,
                        "analysis_mode": s.analysis_mode,
                        "overall_severity": s.overall_severity,
                        "overall_success": s.overall_success,
                        "inline_comments_count": s.inline_comments_count,
                        "started_at": s.started_at.isoformat()
                        if s.started_at
                        else None,
                        "completed_at": s.completed_at.isoformat()
                        if s.completed_at
                        else None,
                        "duration_seconds": s.duration_seconds,
                    }
                    for s in sessions
                ],
                "total": len(sessions),
                "limit": limit,
                "offset": offset,
            }

    @api_router.get("/reviews/{review_id}")
    async def get_review(review_id: int, request: Request):
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

            return {
                "id": review_session.id,
                "repository_id": review_session.repository_id,
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
                "started_at": review_session.started_at.isoformat()
                if review_session.started_at
                else None,
                "completed_at": review_session.completed_at.isoformat()
                if review_session.completed_at
                else None,
                "duration_seconds": review_session.duration_seconds,
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

        async with database.session() as session:
            db_service = DBService(session)

            # 获取汇总
            summary = await db_service.get_usage_summary(
                repository_id=repository_id,
                start_date=start,
                end_date=end,
            )

            # 获取详细记录
            stats = await db_service.get_usage_stats(
                repository_id=repository_id,
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
                        "date": s.stat_date.isoformat() if s.stat_date else None,
                        "estimated_input_tokens": s.estimated_input_tokens,
                        "estimated_output_tokens": s.estimated_output_tokens,
                        "gitea_api_calls": s.gitea_api_calls,
                        "claude_api_calls": s.claude_api_calls,
                        "clone_operations": s.clone_operations,
                    }
                    for s in stats
                ],
            }

    # ==================== 模型配置 API ====================

    @api_router.get("/configs")
    async def list_configs(request: Request):
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
                        "model_name": c.model_name,
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
    async def create_or_update_config(payload: ModelConfigRequest, request: Request):
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
                model_name=payload.model_name,
                max_tokens=payload.max_tokens,
                temperature=payload.temperature,
                custom_prompt=payload.custom_prompt,
                default_features=payload.default_features,
                default_focus=payload.default_focus,
                is_default=payload.is_default,
            )

            return {
                "id": config.id,
                "repository_id": config.repository_id,
                "config_name": config.config_name,
                "model_name": config.model_name,
                "is_default": config.is_default,
                "message": "配置已保存",
            }

    # ==================== 仓库管理 API ====================

    @api_router.get("/repos/{owner}/{repo}/pulls")
    async def get_repo_pulls(owner: str, repo: str, state: str = "all", limit: int = 5):
        """获取仓库最新PR"""
        gitea_client = context.gitea_client
        pulls = await gitea_client.list_pull_requests(
            owner, repo, state=state, limit=limit
        )

        if pulls is None:
            raise HTTPException(status_code=404, detail="无法获取PR信息")

        return {"pulls": pulls}

    @api_router.get("/repos/{owner}/{repo}/claude-config")
    async def get_repo_claude_config(owner: str, repo: str, request: Request):
        """获取仓库的 Claude 配置"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)
            repo_obj = await db_service.get_repository(owner, repo)

            if not repo_obj:
                return {
                    "configured": False,
                    "anthropic_base_url": None,
                    "has_auth_token": False,
                }

            model_config = await db_service.get_model_config(repo_obj.id)
            if not model_config:
                return {
                    "configured": False,
                    "anthropic_base_url": None,
                    "has_auth_token": False,
                }

            return {
                "configured": True,
                "anthropic_base_url": model_config.anthropic_base_url,
                "has_auth_token": bool(model_config.anthropic_auth_token),
            }

    @api_router.put("/repos/{owner}/{repo}/claude-config")
    async def update_repo_claude_config(
        owner: str, repo: str, payload: ClaudeConfigRequest, request: Request
    ):
        """保存仓库的 Claude 配置"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        from app.services.db_service import DBService

        async with database.session() as session:
            db_service = DBService(session)

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

            # 更新 Anthropic 配置
            if payload.anthropic_base_url is not None:
                model_config.anthropic_base_url = payload.anthropic_base_url or None
            if payload.anthropic_auth_token is not None:
                model_config.anthropic_auth_token = payload.anthropic_auth_token or None

            await session.flush()

            return {
                "success": True,
                "message": "Claude 配置已保存",
                "anthropic_base_url": model_config.anthropic_base_url,
                "has_auth_token": bool(model_config.anthropic_auth_token),
            }

    @api_router.get("/repos/{owner}/{repo}/webhook-secret")
    async def get_webhook_secret(owner: str, repo: str, request: Request):
        """获取仓库的 Webhook Secret"""
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
                    "webhook_secret": None,
                }

            return {
                "has_secret": bool(repo_obj.webhook_secret),
                "webhook_secret": repo_obj.webhook_secret,
            }

    @api_router.post("/repos/{owner}/{repo}/webhook-secret/regenerate")
    async def regenerate_webhook_secret(owner: str, repo: str, request: Request):
        """重新生成仓库的 Webhook Secret"""
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
    async def list_repositories(request: Request):
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
                context.repo_registry.get_secret(owner_name, repo_name)
                if owner_name and repo_name
                else None
            )

            # 验证签名
            secret_for_validation = repo_secret or settings.webhook_secret
            if secret_for_validation and x_gitea_signature:
                if not verify_webhook_signature(
                    body, x_gitea_signature, secret_for_validation
                ):
                    logger.warning("Webhook签名验证失败")
                    raise HTTPException(status_code=401, detail="Invalid signature")

            # Debug日志：输出完整的webhook payload
            if settings.debug:
                logger.debug(
                    f"[Webhook Payload] {json.dumps(payload, ensure_ascii=False, indent=2)}"
                )

            # 处理Pull Request事件
            if x_gitea_event == "pull_request":
                # 解析功能和重点
                features = context.webhook_handler.parse_review_features(
                    x_review_features
                )
                focus_areas = context.webhook_handler.parse_review_focus(x_review_focus)

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

            # 处理Issue评论事件（用于手动触发）
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
            raise HTTPException(status_code=500, detail=str(exc))

    return api_router, public_router
