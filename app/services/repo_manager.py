"""
代码库管理模块
"""

import os
import shutil
import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RepoManager:
    """代码库管理器"""

    def __init__(self, work_dir: str):
        """
        初始化代码库管理器

        Args:
            work_dir: 工作目录路径
        """
        self.work_dir = Path(work_dir).expanduser().resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def get_repo_path(self, owner: str, repo: str, pr_number: int) -> Path:
        """
        获取仓库的本地路径

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号

        Returns:
            仓库本地路径
        """
        return self.work_dir / f"{owner}_{repo}_pr{pr_number}"

    async def clone_repository(
        self, clone_url: str, owner: str, repo: str, pr_number: int, branch: str
    ) -> Optional[Path]:
        """
        克隆仓库到本地

        Args:
            clone_url: 克隆URL（带认证）
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号
            branch: 要检出的分支

        Returns:
            仓库本地路径，失败返回None
        """
        repo_path = self.get_repo_path(owner, repo, pr_number)

        # 如果目录已存在，先删除
        if repo_path.exists():
            logger.info(f"删除已存在的仓库目录: {repo_path}")
            shutil.rmtree(repo_path)

        try:
            # 克隆仓库
            logger.info(f"开始克隆仓库: {owner}/{repo} 分支: {branch}")
            process = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                "--depth=1",
                "--single-branch",
                "--branch",
                branch,
                clone_url,
                str(repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"克隆仓库失败: {stderr.decode()}")
                return None

            logger.info(f"成功克隆仓库到: {repo_path}")
            return repo_path

        except Exception as e:
            logger.error(f"克隆仓库异常: {e}")
            return None

    async def checkout_pr_branch(
        self, repo_path: Path, base_branch: str, head_branch: str
    ) -> bool:
        """
        检出PR的head分支

        Args:
            repo_path: 仓库路径
            base_branch: 基础分支
            head_branch: PR的head分支

        Returns:
            是否成功
        """
        try:
            # 如果head_branch和base_branch不同，尝试检出
            if head_branch != base_branch:
                logger.info(f"检出分支: {head_branch}")
                process = await asyncio.create_subprocess_exec(
                    "git",
                    "checkout",
                    head_branch,
                    cwd=str(repo_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    logger.error(f"检出分支失败: {stderr.decode()}")
                    return False

            return True

        except Exception as e:
            logger.error(f"检出分支异常: {e}")
            return False

    def cleanup_repository(self, owner: str, repo: str, pr_number: int) -> bool:
        """
        清理仓库目录

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号

        Returns:
            是否成功
        """
        repo_path = self.get_repo_path(owner, repo, pr_number)

        if not repo_path.exists():
            return True

        try:
            logger.info(f"清理仓库目录: {repo_path}")
            shutil.rmtree(repo_path)
            return True
        except Exception as e:
            logger.error(f"清理仓库目录失败: {e}")
            return False

    def cleanup_all(self) -> bool:
        """
        清理所有仓库目录

        Returns:
            是否成功
        """
        try:
            if self.work_dir.exists():
                logger.info(f"清理所有仓库目录: {self.work_dir}")
                shutil.rmtree(self.work_dir)
                self.work_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"清理所有仓库目录失败: {e}")
            return False
