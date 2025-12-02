"""
FastAPI主应用
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

if __package__ in (None, ""):
    # When executed as `python app/main.py`, ensure project root is importable
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

from app.api import create_api_router
from app.core import (
    settings,
    __version__,
    get_version_banner,
    get_version_info,
)
from app.core.context import AppContext
from app.services import (
    GiteaClient,
    RepoManager,
    ClaudeAnalyzer,
    WebhookHandler,
    RepoRegistry,
    AuthManager,
)

# 配置日志
logging.basicConfig(
    level=settings.log_level if not settings.debug else "DEBUG",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def build_context() -> AppContext:
    """初始化所有服务组件并封装为应用上下文。"""
    gitea_client = GiteaClient(settings.gitea_url, settings.gitea_token, settings.debug)
    repo_manager = RepoManager(settings.work_dir)
    claude_analyzer = ClaudeAnalyzer(settings.claude_code_path, settings.debug)
    webhook_handler = WebhookHandler(
        gitea_client, repo_manager, claude_analyzer, settings.bot_username
    )
    repo_registry = RepoRegistry(settings.work_dir)
    auth_manager = AuthManager()
    return AppContext(
        gitea_client=gitea_client,
        repo_manager=repo_manager,
        claude_analyzer=claude_analyzer,
        webhook_handler=webhook_handler,
        repo_registry=repo_registry,
        auth_manager=auth_manager,
    )


def create_app() -> FastAPI:
    """创建FastAPI应用并绑定生命周期事件。"""
    context = build_context()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动时输出版本信息
        print(get_version_banner())
        logger.info(get_version_info())
        logger.info("Gitea PR Reviewer 启动")
        logger.info(f"Gitea URL: {settings.gitea_url}")
        logger.info(f"工作目录: {settings.work_dir}")
        logger.info(f"Claude Code路径: {settings.claude_code_path}")
        logger.info(f"Debug模式: {'开启' if settings.debug else '关闭'}")
        try:
            yield
        finally:
            logger.info("Gitea PR Reviewer 关闭")
            # 可选：清理临时文件
            # context.repo_manager.cleanup_all()

    app = FastAPI(
        title="Gitea PR Reviewer",
        description="基于Claude Code的Gitea Pull Request自动审查工具",
        version=__version__,
        lifespan=lifespan,
    )

    api_router, public_router = create_api_router(context)
    app.include_router(public_router)
    app.include_router(api_router, prefix="/api")

    frontend_out_dir = Path(__file__).resolve().parent.parent / "frontend" / "out"
    if frontend_out_dir.exists():
        static_app = StaticFiles(directory=str(frontend_out_dir), html=True)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend(full_path: str, request: Request):
            if full_path.startswith("api"):
                raise HTTPException(status_code=404)
            target = full_path or "index.html"
            response = await static_app.get_response(target, request.scope)
            if response.status_code == 404:
                return await static_app.get_response("index.html", request.scope)
            return response
    else:
        logger.warning("前端静态资源未构建，未挂载静态站点")
    app.state.context = context
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
