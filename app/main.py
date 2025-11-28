"""
FastAPI主应用
"""
import logging
import hmac
import hashlib
import json
from typing import Optional
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from .config import settings
from .gitea_client import GiteaClient
from .repo_manager import RepoManager
from .claude_analyzer import ClaudeAnalyzer
from .webhook_handler import WebhookHandler

# 配置日志
logging.basicConfig(
    level=settings.log_level if not settings.debug else "DEBUG",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Gitea PR Reviewer",
    description="自动化PR代码审查工具",
    version="0.1.0",
)

# 初始化组件
gitea_client = GiteaClient(settings.gitea_url, settings.gitea_token, settings.debug)
repo_manager = RepoManager(settings.work_dir)
claude_analyzer = ClaudeAnalyzer(settings.claude_code_path, settings.debug)
webhook_handler = WebhookHandler(gitea_client, repo_manager, claude_analyzer)


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
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "healthy"}


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

        # 验证签名
        if settings.webhook_secret and x_gitea_signature:
            if not verify_webhook_signature(
                body, x_gitea_signature, settings.webhook_secret
            ):
                logger.warning("Webhook签名验证失败")
                raise HTTPException(status_code=401, detail="Invalid signature")

        # 解析JSON
        payload = await request.json()

        # Debug日志：输出完整的webhook payload
        if settings.debug:
            logger.debug(f"[Webhook Payload] {json.dumps(payload, ensure_ascii=False, indent=2)}")

        # 检查事件类型
        if x_gitea_event != "pull_request":
            logger.info(f"忽略非PR事件: {x_gitea_event}")
            return JSONResponse(
                status_code=200, content={"message": "Event ignored"}
            )

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
