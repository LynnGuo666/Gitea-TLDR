"""
数据库连接管理模块
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)


class Database:
    """异步数据库管理器"""

    def __init__(self, database_url: str):
        """
        初始化数据库连接

        Args:
            database_url: 数据库连接URL
        """
        self.database_url = database_url
        self._engine = None
        self._session_factory = None

    async def init(self) -> None:
        """初始化数据库引擎和会话工厂"""
        # 确保 SQLite 数据库目录存在
        if self.database_url.startswith("sqlite"):
            db_path = self.database_url.split("///")[-1]
            if db_path and db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 创建异步引擎
        connect_args = {}
        if "sqlite" in self.database_url:
            connect_args["check_same_thread"] = False

        self._engine = create_async_engine(
            self.database_url,
            echo=False,
            connect_args=connect_args,
            poolclass=StaticPool if "sqlite" in self.database_url else None,
        )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        logger.info(f"数据库初始化完成: {self._mask_url(self.database_url)}")

    async def create_tables(self) -> None:
        """创建所有表（开发环境使用）"""
        from app.models import Base

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表创建完成")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            logger.info("数据库连接已关闭")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话的上下文管理器"""
        if not self._session_factory:
            raise RuntimeError("数据库未初始化，请先调用 init()")

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @staticmethod
    def _mask_url(url: str) -> str:
        """隐藏URL中的敏感信息"""
        if "@" in url:
            # 隐藏密码
            parts = url.split("@")
            prefix = parts[0]
            if ":" in prefix:
                user_part = prefix.rsplit(":", 1)[0]
                return f"{user_part}:****@{parts[1]}"
        return url
