"""
FastAPI主应用
"""
import logging
import hmac
import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .config import settings
from .gitea_client import GiteaClient
from .repo_manager import RepoManager
from .claude_analyzer import ClaudeAnalyzer
from .webhook_handler import WebhookHandler
from .repo_registry import RepoRegistry
from .version import __version__, get_version_banner, get_version_info, get_changelog, get_all_changelogs

# 配置日志
logging.basicConfig(
    level=settings.log_level if not settings.debug else "DEBUG",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 打印版本横幅
print(get_version_banner())
logger.info(get_version_info())

# 创建FastAPI应用
app = FastAPI(
    title="Gitea PR Reviewer",
    description="基于Claude Code的Gitea Pull Request自动审查工具",
    version=__version__,
)

frontend_out_dir = Path(__file__).resolve().parent.parent / "frontend" / "out"
if frontend_out_dir.exists():
    app.mount(
        "/ui", StaticFiles(directory=str(frontend_out_dir), html=True), name="ui"
    )
else:
    logger.warning("前端静态资源未构建，未挂载 /ui")

# 初始化组件
gitea_client = GiteaClient(settings.gitea_url, settings.gitea_token, settings.debug)
repo_manager = RepoManager(settings.work_dir)
claude_analyzer = ClaudeAnalyzer(settings.claude_code_path, settings.debug)
webhook_handler = WebhookHandler(
    gitea_client, repo_manager, claude_analyzer, settings.bot_username
)
repo_registry = RepoRegistry(settings.work_dir)


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


@app.get("/")
async def root():
    """健康检查端点"""
    return {
        "status": "ok",
        "service": "Gitea PR Reviewer",
        "version": __version__,
    }


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "healthy"}


@app.get("/version")
async def version():
    """版本信息端点"""
    return {
        "version": __version__,
        "info": get_version_info(),
        "changelog": get_changelog()
    }


@app.get("/changelog")
async def changelog():
    """完整更新日志端点"""
    return {
        "version": __version__,
        "changelog": get_all_changelogs()
    }


@app.get("/api/config/public")
async def public_config():
    """提供前端需要的只读配置"""
    return {
        "gitea_url": settings.gitea_url,
        "bot_username": settings.bot_username,
        "debug": settings.debug,
    }


@app.get("/api/repos")
async def list_repos():
    """列出当前token可访问的仓库"""
    repos = await gitea_client.list_user_repos()
    if repos is None:
        raise HTTPException(status_code=502, detail="无法从Gitea获取仓库列表")
    return {"repos": repos}


@app.post("/api/repos/{owner}/{repo}/setup")
async def setup_repo_review(owner: str, repo: str, payload: WebhookSetupRequest, request: Request):
    """为指定仓库配置Webhook并可选邀请Bot账号"""
    callback_url = payload.callback_url or str(request.url_for("webhook"))
    secret = repo_registry.get_secret(owner, repo) or secrets.token_hex(20)
    repo_registry.set_secret(owner, repo, secret)

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

    hook_id = await gitea_client.ensure_repo_webhook(owner, repo, webhook_config)
    if hook_id is None:
        raise HTTPException(status_code=502, detail="创建或更新Webhook失败")

    bot_added = False
    if payload.bring_bot and settings.bot_username:
        bot_added = await gitea_client.add_collaborator(owner, repo, settings.bot_username)

    return {
        "owner": owner,
        "repo": repo,
        "webhook_id": hook_id,
        "webhook_url": callback_url,
        "bot_invited": bot_added,
        "events": payload.events,
    }


@app.post("/webhook")
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
        repo_info = payload.get("repository", {}) if isinstance(payload, dict) else {}
        owner_info = repo_info.get("owner", {}) if isinstance(repo_info, dict) else {}
        owner_name = owner_info.get("username") or owner_info.get("login")
        repo_name = repo_info.get("name")
        repo_secret = (
            repo_registry.get_secret(owner_name, repo_name)
            if owner_name and repo_name
            else None
        )

        # 验证签名
        secret_for_validation = repo_secret or settings.webhook_secret
        if secret_for_validation and x_gitea_signature:
            if not verify_webhook_signature(body, x_gitea_signature, secret_for_validation):
                logger.warning("Webhook签名验证失败")
                raise HTTPException(status_code=401, detail="Invalid signature")

        # Debug日志：输出完整的webhook payload
        if settings.debug:
            logger.debug(f"[Webhook Payload] {json.dumps(payload, ensure_ascii=False, indent=2)}")

        # 处理Pull Request事件
        if x_gitea_event == "pull_request":
            # 解析功能和重点
            features = webhook_handler.parse_review_features(x_review_features)
            focus_areas = webhook_handler.parse_review_focus(x_review_focus)

            logger.info(f"收到PR webhook，功能: {features}, 重点: {focus_areas}")

            # 添加后台任务
            background_tasks.add_task(
                webhook_handler.process_webhook_async, payload, features, focus_areas
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
        elif x_gitea_event == "issue_comment":
            logger.info("收到issue_comment webhook")

            # 添加后台任务
            background_tasks.add_task(
                webhook_handler.process_comment_async, payload
            )

            # 立即返回202
            return JSONResponse(
                status_code=202,
                content={
                    "message": "Comment webhook received, processing in background",
                },
            )

        # 其他事件类型
        else:
            logger.info(f"忽略事件: {x_gitea_event}")
            return JSONResponse(
                status_code=200, content={"message": "Event ignored"}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理webhook异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("Gitea PR Reviewer 启动")
    logger.info(f"Gitea URL: {settings.gitea_url}")
    logger.info(f"工作目录: {settings.work_dir}")
    logger.info(f"Claude Code路径: {settings.claude_code_path}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("Gitea PR Reviewer 关闭")
    # 可选：清理临时文件
    # repo_manager.cleanup_all()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
