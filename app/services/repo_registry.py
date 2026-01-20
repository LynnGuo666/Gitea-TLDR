"""简单的仓库配置和密钥存储"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from app.core.database import Database

logger = logging.getLogger(__name__)


class RepoRegistry:
    """用于存储每个仓库的Webhook密钥和基础信息.

    支持两种存储模式：
    1. 数据库模式（优先）：使用 SQLite/PostgreSQL 存储
    2. JSON文件模式（降级）：使用本地 JSON 文件存储
    """

    def __init__(
        self,
        work_dir: str,
        database: Optional["Database"] = None,
        filename: str = "repo_registry.json",
    ):
        """
        初始化仓库注册表

        Args:
            work_dir: 工作目录路径
            database: 数据库管理器（可选，如果提供则使用数据库存储）
            filename: JSON文件名（降级模式使用）
        """
        self.base_path = Path(work_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.base_path / filename
        self.database = database
        self._lock = Lock()
        self._data: Dict[str, Dict[str, str]] = {}

        # 如果没有数据库，加载 JSON 文件
        if not self.database:
            self._load()

    def _load(self) -> None:
        """从 JSON 文件加载数据"""
        if not self.registry_file.exists():
            self.registry_file.write_text("{}", encoding="utf-8")
        try:
            self._data = json.loads(self.registry_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # 如果文件损坏，重置为空以避免运行时失败
            self._data = {}
            self.registry_file.write_text("{}", encoding="utf-8")

    def _save(self) -> None:
        """保存数据到 JSON 文件"""
        self.registry_file.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _key(self, owner: str, repo: str) -> str:
        return f"{owner}/{repo}"

    def get_secret(self, owner: str, repo: str) -> Optional[str]:
        """获取仓库的 webhook 密钥（同步方法，兼容现有代码）"""
        if self.database:
            # 使用数据库时，需要运行异步代码
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 在已运行的事件循环中，创建新任务
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(
                            asyncio.run, self._get_secret_async(owner, repo)
                        )
                        return future.result()
                else:
                    return loop.run_until_complete(self._get_secret_async(owner, repo))
            except RuntimeError:
                return asyncio.run(self._get_secret_async(owner, repo))
        else:
            key = self._key(owner, repo)
            with self._lock:
                repo_info = self._data.get(key, {})
                return repo_info.get("webhook_secret")

    async def _get_secret_async(self, owner: str, repo: str) -> Optional[str]:
        """异步获取仓库密钥"""
        if not self.database:
            return None

        from app.services.db_service import DBService

        async with self.database.session() as session:
            db_service = DBService(session)
            repo_obj = await db_service.get_repository(owner, repo)
            return repo_obj.webhook_secret if repo_obj else None

    async def get_secret_async(self, owner: str, repo: str) -> Optional[str]:
        """异步获取仓库的 webhook 密钥"""
        if self.database:
            return await self._get_secret_async(owner, repo)
        else:
            key = self._key(owner, repo)
            with self._lock:
                repo_info = self._data.get(key, {})
                return repo_info.get("webhook_secret")

    def set_secret(self, owner: str, repo: str, secret: Optional[str]) -> None:
        """设置仓库的 webhook 密钥（同步方法，兼容现有代码）"""
        if self.database:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(
                            asyncio.run, self._set_secret_async(owner, repo, secret)
                        )
                        future.result()
                else:
                    loop.run_until_complete(self._set_secret_async(owner, repo, secret))
            except RuntimeError:
                asyncio.run(self._set_secret_async(owner, repo, secret))
        else:
            key = self._key(owner, repo)
            with self._lock:
                repo_info = self._data.get(key, {})
                if secret is None:
                    repo_info.pop("webhook_secret", None)
                else:
                    repo_info["webhook_secret"] = secret
                self._data[key] = repo_info
                self._save()

    def delete_secret(self, owner: str, repo: str) -> None:
        """删除仓库的 webhook 密钥（同步方法）"""
        self.set_secret(owner, repo, None)

    async def _set_secret_async(
        self, owner: str, repo: str, secret: Optional[str]
    ) -> None:
        """异步设置仓库密钥"""
        if not self.database:
            return

        from app.services.db_service import DBService

        async with self.database.session() as session:
            db_service = DBService(session)
            await db_service.update_repository_secret(owner, repo, secret)

    async def set_secret_async(
        self, owner: str, repo: str, secret: Optional[str]
    ) -> None:
        """异步设置仓库的 webhook 密钥"""
        if self.database:
            await self._set_secret_async(owner, repo, secret)
        else:
            key = self._key(owner, repo)
            with self._lock:
                repo_info = self._data.get(key, {})
                if secret is None:
                    repo_info.pop("webhook_secret", None)
                else:
                    repo_info["webhook_secret"] = secret
                self._data[key] = repo_info
                self._save()

    def get_repo_info(self, owner: str, repo: str) -> Dict[str, str]:
        """获取仓库信息（同步方法）"""
        if self.database:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(
                            asyncio.run, self._get_repo_info_async(owner, repo)
                        )
                        return future.result()
                else:
                    return loop.run_until_complete(
                        self._get_repo_info_async(owner, repo)
                    )
            except RuntimeError:
                return asyncio.run(self._get_repo_info_async(owner, repo))
        else:
            key = self._key(owner, repo)
            with self._lock:
                return self._data.get(key, {})

    async def _get_repo_info_async(self, owner: str, repo: str) -> Dict[str, str]:
        """异步获取仓库信息"""
        if not self.database:
            return {}

        from app.services.db_service import DBService

        async with self.database.session() as session:
            db_service = DBService(session)
            repo_obj = await db_service.get_repository(owner, repo)
            if repo_obj:
                return {
                    "webhook_secret": repo_obj.webhook_secret or "",
                    "is_active": str(repo_obj.is_active),
                }
            return {}

    async def get_repo_info_async(self, owner: str, repo: str) -> Dict[str, str]:
        """异步获取仓库信息"""
        if self.database:
            return await self._get_repo_info_async(owner, repo)
        else:
            key = self._key(owner, repo)
            with self._lock:
                return self._data.get(key, {})

    def list_all(self) -> Dict[str, Dict[str, str]]:
        """列出所有仓库（同步方法）"""
        if self.database:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, self._list_all_async())
                        return future.result()
                else:
                    return loop.run_until_complete(self._list_all_async())
            except RuntimeError:
                return asyncio.run(self._list_all_async())
        else:
            with self._lock:
                return dict(self._data)

    async def _list_all_async(self) -> Dict[str, Dict[str, str]]:
        """异步列出所有仓库"""
        if not self.database:
            return {}

        from app.services.db_service import DBService

        async with self.database.session() as session:
            db_service = DBService(session)
            repos = await db_service.list_repositories()
            result = {}
            for repo in repos:
                key = f"{repo.owner}/{repo.repo_name}"
                result[key] = {
                    "webhook_secret": repo.webhook_secret or "",
                    "is_active": str(repo.is_active),
                }
            return result

    async def list_all_async(self) -> Dict[str, Dict[str, str]]:
        """异步列出所有仓库"""
        if self.database:
            return await self._list_all_async()
        else:
            with self._lock:
                return dict(self._data)

    async def migrate_from_json(self) -> int:
        """
        将 JSON 文件中的数据迁移到数据库

        Returns:
            迁移的记录数
        """
        if not self.database:
            logger.warning("未配置数据库，无法迁移")
            return 0

        # 先加载 JSON 文件
        if not self.registry_file.exists():
            return 0

        try:
            json_data = json.loads(self.registry_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return 0

        if not json_data:
            return 0

        from app.services.db_service import DBService

        count = 0
        async with self.database.session() as session:
            db_service = DBService(session)
            for key, info in json_data.items():
                if "/" not in key:
                    continue
                owner, repo_name = key.split("/", 1)
                secret = info.get("webhook_secret")
                if secret:
                    await db_service.update_repository_secret(owner, repo_name, secret)
                    count += 1
                    logger.info(f"已迁移仓库: {key}")

        logger.info(f"JSON数据迁移完成，共迁移 {count} 条记录")
        return count
