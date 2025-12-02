"""
HTTP route definitions for the FastAPI application.
"""
from __future__ import annotations

import hmac
import hashlib
import json
import logging
import secrets
from typing import Optional
from fastapi import (
    APIRouter,
    Request,
    Header,
    HTTPException,
    BackgroundTasks,
    Response,
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
    bring_bot: bool = Field(
        default=True, description="是否自动邀请bot账号协作"
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

    expected_signature = hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


def create_api_router(context: AppContext) -> APIRouter:
    """
    创建包含所有业务端点的APIRouter。
    """
    router = APIRouter()

    @router.get("/")
    async def root():
        """根路径重定向到前端页面"""
        return RedirectResponse(url="/ui/", status_code=307)

    @router.get("/health")
    async def health():
        """健康检查端点"""
        return {"status": "healthy"}

    @router.get("/version")
    async def version():
        """版本信息端点"""
        return {
            "version": __version__,
            "info": get_version_info(),
            "changelog": get_changelog(),
        }

    @router.get("/changelog")
    async def changelog():
        """完整更新日志端点"""
        return {
            "version": __version__,
            "changelog": get_all_changelogs(),
        }

    @router.get("/api/config/public")
    async def public_config():
        """提供前端需要的只读配置"""
        return {
            "gitea_url": settings.gitea_url,
            "bot_username": settings.bot_username,
            "debug": settings.debug,
            "oauth_enabled": context.auth_manager.enabled,
        }

    @router.get("/api/auth/status")
    async def auth_status(request: Request):
        """返回当前会话状态"""
        return context.auth_manager.get_status_payload(request)

    @router.get("/api/auth/login-url")
    async def auth_login_url():
        """生成OAuth授权地址"""
        if not context.auth_manager.enabled:
            raise HTTPException(status_code=404, detail="OAuth 未启用")
        return {"url": context.auth_manager.build_authorize_url()}

    @router.post("/api/auth/logout")
    async def auth_logout(request: Request, response: Response):
        """注销当前会话"""
        context.auth_manager.logout(request, response)
        return {"success": True}

    @router.get("/api/auth/callback")
    async def auth_callback(code: str, state: str):
        """OAuth回调，设置登录会话后重定向到主页"""
        redirect = RedirectResponse(url="/", status_code=303)
        return await context.auth_manager.handle_callback(code, state, redirect)

    @router.get("/api/repos")
    async def list_repos(request: Request):
        """列出当前token可访问的仓库"""
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
        return {"repos": repos}

    @router.post("/api/repos/{owner}/{repo}/setup")
    async def setup_repo_review(
        owner: str, repo: str, payload: WebhookSetupRequest, request: Request
    ):
        """为指定仓库配置Webhook并可选邀请Bot账号"""
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

        client = (
            context.auth_manager.build_user_client(
                context.auth_manager.require_session(request)
            )
            if context.auth_manager.enabled
            else context.gitea_client
        )

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

    @router.post("/webhook")
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
            owner_info = repo_info.get("owner", {}) if isinstance(repo_info, dict) else {}
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
                focus_areas = context.webhook_handler.parse_review_focus(
                    x_review_focus
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

    return router
