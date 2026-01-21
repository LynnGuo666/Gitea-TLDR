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
from app.api.admin_routes import create_admin_router
from app.core import (
    settings,
    __version__,
    get_version_banner,
    get_version_info,
)
from app.core.admin_auth import ensure_initial_admin
from app.core.context import AppContext
from app.core.database import Database
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

# 全局数据库实例
_database: Database | None = None


async def init_database() -> Database:
    """初始化数据库连接"""
    global _database
    if _database is None:
        _database = Database(settings.effective_database_url)
        await _database.init()
        # 使用 Alembic 迁移而不是简单的 create_tables()
        await _database.run_migrations()
        logger.info(f"数据库初始化完成")
    return _database


async def close_database() -> None:
    """关闭数据库连接"""
    global _database
    if _database is not None:
        await _database.close()
        _database = None


def build_context(database: Database | None = None) -> AppContext:
    """初始化所有服务组件并封装为应用上下文。"""
    gitea_client = GiteaClient(settings.gitea_url, settings.gitea_token, settings.debug)
    repo_manager = RepoManager(settings.work_dir)
    claude_analyzer = ClaudeAnalyzer(settings.claude_code_path, settings.debug)

    # 初始化仓库注册表（支持数据库存储）
    repo_registry = RepoRegistry(settings.work_dir, database=database)

    # 初始化 Webhook 处理器（支持数据库记录）
    webhook_handler = WebhookHandler(
        gitea_client,
        repo_manager,
        claude_analyzer,
        database=database,
        bot_username=settings.bot_username,
    )

    auth_manager = AuthManager()

    return AppContext(
        gitea_client=gitea_client,
        repo_manager=repo_manager,
        claude_analyzer=claude_analyzer,
        webhook_handler=webhook_handler,
        repo_registry=repo_registry,
        auth_manager=auth_manager,
        database=database,
    )


def create_app() -> FastAPI:
    """创建FastAPI应用并绑定生命周期事件。"""
    # 先创建一个不带数据库的 context
    # 数据库会在 lifespan 中初始化后更新 context 的属性
    context = build_context(database=None)

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

        # 初始化数据库
        try:
            database = await init_database()
            logger.info(f"数据库路径: {settings.effective_database_url}")

            # 更新 context 的数据库相关属性
            context.database = database
            context.repo_registry.database = database
            context.webhook_handler.database = database

            # 尝试迁移 JSON 数据到数据库
            try:
                migrated = await context.repo_registry.migrate_from_json()
                if migrated > 0:
                    logger.info(f"已从JSON迁移 {migrated} 条仓库记录到数据库")
            except Exception as e:
                logger.warning(f"JSON数据迁移失败: {e}")

            # 初始化管理员用户
            if settings.admin_enabled and settings.initial_admin_username:
                try:
                    async with database.session() as session:
                        await ensure_initial_admin(
                            session, settings.initial_admin_username
                        )
                        logger.info("管理后台已启用")
                except Exception as e:
                    logger.warning(f"管理员初始化失败: {e}")

        except Exception as e:
            logger.error(f"数据库初始化失败: {e}", exc_info=True)
            logger.warning("服务将以无数据库模式运行")

        try:
            yield
        finally:
            logger.info("Gitea PR Reviewer 关闭")
            await close_database()

    app = FastAPI(
        title="Gitea PR Reviewer",
        description="基于Claude Code的Gitea Pull Request自动审查工具",
        version=__version__,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        app_context = getattr(request.app.state, "context", None)
        if app_context:
            session = app_context.auth_manager.get_session(request)
            request.state.auth_status = {
                "loggedIn": bool(session),
                "user": session.user if session else None,
            }
        response = await call_next(request)
        return response

    @app.middleware("http")
    async def database_middleware(request: Request, call_next):
        app_context = getattr(request.app.state, "context", None)
        if app_context and hasattr(app_context, "database"):
            request.state.database = app_context.database
        response = await call_next(request)
        return response

    app.state.context = context

    # 创建路由
    api_router, public_router = create_api_router(context)
    app.include_router(public_router)
    app.include_router(api_router, prefix="/api")

    # 创建管理后台路由
    if settings.admin_enabled:
        admin_router = create_admin_router(context)
        app.include_router(admin_router, prefix="/api")
        logger.info("管理后台路由已注册")

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
                # 检查是否是 repo 动态路由
                if full_path.startswith("repo/") and full_path.count("/") >= 2:
                    fallback_path = frontend_out_dir / "repo" / "_fallback.html"
                    if fallback_path.exists():
                        return await static_app.get_response(
                            "repo/_fallback.html", request.scope
                        )
                return await static_app.get_response("index.html", request.scope)
            return response
    else:
        logger.warning("前端静态资源未构建，未挂载静态站点")

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
